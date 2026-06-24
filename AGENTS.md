# AGENTS.md — Computer Use Agent (v0.2.0)

> This document is for AI agents maintaining this codebase. It provides
> comprehensive context about the project architecture, conventions, and
> key implementation details. **Last updated for v0.2.0 (2026-06-24).**

## Project Overview

**Computer Use Agent** is an AI-powered desktop automation tool. It takes
screenshots, sends them to an LLM, receives action instructions, executes
mouse/keyboard operations, and loops until the task is complete.

**Core loop:**
```
Screenshot → Send to LLM → Parse JSON action → Execute action → Verify with next screenshot → Repeat
```

**Tech stack:** Python 3.10+, OpenAI SDK (compatible with any provider),
pyautogui, PIL, mss (multi-monitor), uiautomation (Windows UIA), Rich,
prompt_toolkit. Optional: pydantic-settings for config validation.

**Entry points (4):**
- `cua` (alias for `python -m computer_use_agent`) — REPL / one-shot
- `cua-serve` — HTTP API server
- `cua-mcp` — MCP server (stdio JSON-RPC)
- `cua --replay <file>` — Session replay

## Directory Structure

```
computer_use_agent/             # 22 Python modules
├── __init__.py                 # __version__ = "0.2.0"
├── __main__.py                 # argparse CLI entry
├── agent.py                    # Main loop, SessionStats, history compression
├── llm.py                      # OpenAI client + retry/backoff/streaming/JSON parse
├── executor.py                 # 12 action types + clipboard paste for CJK
├── screen.py                   # Multi-monitor capture (mss / ImageGrab)
├── uia_tree.py                 # Windows UIA element tree + SOM overlay
├── api.py                      # HTTP REST API (stdlib, Bearer auth, SSE, cancel)
├── cli.py                      # Interactive REPL (Hermes-style, 26 commands)
├── tui.py                      # rich.live status panel
├── mcp_server.py               # MCP server (stdio JSON-RPC 2.0)
├── plugins.py                  # Plugin system (ActionRegistry + auto-discovery)
├── replay.py                   # JSONL session record + dry-run playback
├── webhook.py                  # Async HTTP POST on done/error/interrupted
├── i18n.py                     # zh-CN / en-US translations
├── logger.py                   # Rotating logs + JSON formatter + 12-pattern redaction
├── prompts.py                  # 10-block system prompt + platform hints
├── sanitization.py             # 5-pass JSON repair
├── token_budget.py             # 3-layer context overflow defense
├── guardrails.py               # Loop detection (3 strategies)
├── visual_effects.py           # Win32 click/drag/info overlay
├── notify.py                   # Windows notification
└── config.py                   # pydantic-settings + legacy fallback

tests/                          # 13 test files
├── test_all.py                 # Core module tests
├── test_api.py
├── test_cli.py                 # Legacy (kept for reference)
├── test_cli_new.py
├── test_comprehensive.py
├── test_coverage.py
├── test_logger_cli.py
├── test_new_commands.py
├── test_notify.py
├── test_som.py
├── test_uitars_mode.py
├── test_visual.py
└── test_visual_diag.py

docs/                           # Deep-dive documentation
├── ARCHITECTURE.md             # 3 mermaid diagrams + module map
├── CONFIGURATION.md            # All 40+ env vars
├── API.md                      # HTTP + MCP + Webhook reference
└── PLUGINS.md                  # Custom action dev guide

.github/
├── workflows/
│   ├── ci.yml                  # 11 jobs (3 OS × 3 Python + smoke + lint)
│   ├── release.yml             # OIDC-based PyPI publish
│   └── codeql.yml              # Security scan
├── dependabot.yml              # pip / github-actions / docker
├── pull_request_template.md
├── ISSUE_TEMPLATE/
└── release-notes/v0.2.0.md

Dockerfile + docker-compose.yml + .dockerignore
pyproject.toml                  # 4 console_scripts + 5 optional-deps
CHANGELOG.md                    # Keep a Changelog format
CONTRIBUTING.md                 # Conventional Commits + PR flow
README.md / README_CN.md
requirements.txt
```

## Key Architecture Decisions

### 1. Capture Mode Switching

The agent supports THREE capture modes, configured via `CAPTURE_MODE` in `.env`:

- **`som`** (recommended): Uses Windows UIA to get all interactable elements,
  draws red numbered overlays on the screenshot, sends element list to model.
  Model clicks by element index (`{"element": N}`). Highest accuracy, Windows-only.
- **`vision`**: Pure screenshot. Model clicks by pixel coordinates
  (`{"coordinate": [x, y]}`). Cross-platform, works with any model.
- **`uitars`**: Pure screenshot + 0-1000 normalized coords (UI-TARS style).
  For Qwen-VL / UI-TARS-family models.

**Critical:** The prompt text changes based on capture mode. `prompts.py` has `TOOL_GUIDANCE_SOM` and `TOOL_GUIDANCE_VISION` — never mix them up. When adding new action types, update BOTH prompt blocks.

### 2. Prompt Architecture

Prompts are assembled in `prompts.py:build_system_prompt()`. The system prompt is built ONCE per session and cached. It consists of:

1. `IDENTITY` — Who the agent is
2. `TASK_COMPLETION` — Anti-fabrication, anti-premature-stop
3. `COMPUTER_USE` — Capture-Click-Verify loop
4. `TOOL_GUIDANCE_SOM` or `TOOL_GUIDANCE_VISION` — Mode-specific actions
5. `OUTPUT_FORMAT` — JSON-only response requirement
6. `SAFETY_RULES` — Anti-injection, no secrets, no destructive actions
7. `ERROR_RECOVERY` — Verification checklist
8. `WORKFLOW_GUIDANCE` — One-action-per-response principle
9. `TOOL_ENFORCEMENT` — Force action over description
10. `build_environment_context()` — OS, screen size, date
11. Model-specific blocks (`_OPENAI_SPECIFIC`, `_GOOGLE_SPECIFIC`)

**When modifying prompts:** Always rebuild the system prompt by clearing `_DEFAULT_PROMPT = None` in `prompts.py`.

### 3. Agent Loop (agent.py)

The main loop in `agent.run()`:

```python
for step in range(1, MAX_STEPS + 1):
    # 1. Interrupt check
    # 2. Screenshot (SOM or Vision mode)
    # 3. Preflight compression check
    # 4. Prepare messages (sanitize + budget)
    # 5. Send to LLM
    # 6. Check for errors (consecutive error counter)
    # 7. Check if done
    # 8. Execute action
    # 9. Guardrails check (loop detection)
    # 10. Update history
    # 11. Delay with interrupt check
```

**Key patterns borrowed from Hermes:**
- Activity heartbeat (`_touch_activity`) prevents idle timeout
- Guardrails detect repeated failures and no-progress loops
- History compression prevents context overflow
- Message sanitization repairs role alternation

### 4. LLM Client (llm.py)

The `chat()` function handles:
- Retry with jittered exponential backoff (up to `max_retries`)
- Error classification (rate limit, timeout, auth, etc.)
- Empty response recovery (multi-stage)
- Reasoning model compatibility (checks `reasoning_content` when `content` is None)
- Streaming support (optional)

**Important:** Many models return `content=None` and put the response in `reasoning_content`. Always check both fields.

### 5. JSON Repair (sanitization.py)

The `repair_json()` function uses a 5-pass cascade:
1. `json.loads(strict=False)` — tolerates control chars
2. Strip trailing commas
3. Close unclosed `{}` and `[]`
4. Remove excess closing brackets
5. Escape invalid control characters
6. Fallback: return `"{}"`

This handles truncated responses from reasoning models, which is common.

### 6. Tool Guardrails (guardrails.py)

Three detection strategies:
1. **Exact failure**: Same tool + same args + failure → warn at 3, block at 6
2. **Same tool failure**: Any failure of same tool → warn at 4, halt at 10
3. **No progress**: Same screenshot hash 5+ times → block at 6

The `ToolCallSignature` uses SHA256 of the canonical action JSON.

### 7. Token Budget (token_budget.py)

3-layer defense against context overflow:
- **Layer 1:** Truncate single messages exceeding `max_message_chars`
- **Layer 2:** Compact old history entries (keep preview, mark as compacted)
- **Layer 3:** Enforce total history budget (crop old messages)

`BudgetConfig` is a frozen dataclass — runtime immutability enforced.

## Coding Conventions

### File Encoding
- ALL Python files MUST be UTF-8 encoded
- NEVER use PowerShell `Set-Content` for Python files with Chinese — it writes GBK
- Use the `write` tool or Python `codecs.open()` with explicit `encoding='utf-8'`

### Imports
- Use relative imports within the package: `from . import config`
- External imports at the top of file
- Lazy imports for optional dependencies (e.g., `uiautomation`)

### Error Handling
- Use `try/except Exception` broadly in the agent loop — never let the agent crash
- Log errors but continue execution
- The agent should always return a string result, never raise

### Naming
- snake_case for functions and variables
- UPPER_CASE for constants
- Class names: PascalCase
- Private functions: `_prefix`

### Testing
- Tests go in `tests/` directory
- Use `sys.path.insert(0, ...)` to find the package
- Never use `input()` in tests that run in CI
- All test files must handle Windows encoding (UTF-8 reconfigure)

## Common Pitfalls

### 1. PowerShell Encoding
PowerShell `Set-Content` uses system encoding (GBK on Chinese Windows), not UTF-8. This corrupts Python files with Chinese characters. Always use the `write` tool or Python with explicit `encoding='utf-8'`.

### 2. Reasoning Models
Models like `mimo-v2.5`, `deepseek-reasoner`, etc. return `content=None` and put the actual response in `reasoning_content`. The code in `llm.py` handles this, but if you add new code that reads `message.content`, always check `reasoning_content` too.

### 3. UIA API Changes
The `uiautomation` library uses `ClassName` (property), not `GetClassName()` (method). If UIA tree walking fails with `AttributeError`, check the API.

### 4. SOM Element Limits
`get_elements(max_elements=100)` caps at 100 elements. If you increase this, the prompt may overflow. The model also struggles with >200 elements.

### 5. History Growth
Each step adds ~2 messages to history. With 200 steps, that's 400+ messages. The compression and budget systems handle this, but monitor token usage.

## Configuration Reference

All config is in `.env` and loaded by `config.py`:

| Key | Default | Description |
|-----|---------|-------------|
| `LLM_API_KEY` | `sk-placeholder` | API key |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | API endpoint |
| `LLM_MODEL` | `gpt-4o` | Model name |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens |
| `LLM_TEMPERATURE` | `0.0` | Temperature |
| `MAX_STEPS` | `200` | Max agent steps |
| `ACTION_DELAY` | `0.1` | Delay between actions (seconds) |
| `REQUEST_TIMEOUT` | `60` | API timeout (seconds) |
| `CAPTURE_MODE` | `vision` | `som` or `vision` |
| `SCREENSHOT_DIR` | `screenshots` | Screenshot save directory |
| `SCREENSHOT_FORMAT` | `png` | Screenshot format |
| `LOG_LEVEL` | `INFO` | Log level |
| `LOG_DIR` | `logs` | Log directory |

## External Dependencies

| Package | Purpose |
|---------|---------|
| `openai` | LLM API client |
| `pyautogui` | Mouse/keyboard control |
| `Pillow` | Screenshot capture, SOM overlay rendering |
| `uiautomation` | Windows UIA element tree access |
| `rich` | CLI output formatting |
| `prompt_toolkit` | Interactive CLI input |
| `python-dotenv` | .env file loading |
| `pydantic-settings` | (optional, not currently used) |

## Git Workflow

- Commits use conventional format: `feat:`, `fix:`, `test:`, `docs:`
- One logical change per commit
- Run tests before committing: `cd tests && python test_all.py`
- Push to `main` branch directly (no PR workflow yet)
