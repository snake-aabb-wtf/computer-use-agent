# 🖥️ Computer Use Agent

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version 0.2.0](https://img.shields.io/badge/version-0.2.0-orange.svg)](CHANGELOG.md)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](.github/workflows/ci.yml)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple.svg)](https://modelcontextprotocol.io/)

**AI-powered desktop automation through screenshots and actions.** Drives any
OpenAI-compatible LLM to control the mouse, keyboard, and screen — turning
natural-language tasks into automated actions on Windows, macOS, and Linux.

[中文文档](README_CN.md) · [Architecture](docs/ARCHITECTURE.md) · [API Reference](docs/API.md) · [Configuration](docs/CONFIGURATION.md) · [Plugins](docs/PLUGINS.md) · [Changelog](CHANGELOG.md)

---

## ✨ What's new in v0.2.0

- **🔌 MCP Server** — Connect Claude Desktop, Cursor, Zed directly to CUA via the
  [Model Context Protocol](https://modelcontextprotocol.io/). 5 tools exposed:
  `cua.run_task` / `cua.stop_task` / `cua.get_status` / `cua.screenshot` / `cua.list_monitors`
- **🧩 Plugin system** — Drop a Python file in `~/.config/cua/plugins/` to teach the
  LLM custom actions (send email, query internal API, etc.)
- **🖥️ Multi-monitor support** — via `mss`; configure with `MONITOR_INDEX` / `CAPTURE_REGION`
- **📡 Webhook notifications** — async POST on `done` / `error` / `interrupted`
- **🌐 i18n** — `LANGUAGE=en-US` switches interface; 41 translation keys
- **📊 Structured JSON logs** — `LOG_FORMAT=json` for log aggregation
- **🛠️ HTTP API v2** — `GET /tasks` / `GET /stream/<id>` (SSE) / `POST /cancel/<id>`
  / `API_TOKEN` Bearer auth / `hmac.compare_digest` timing-safe
- **🐳 Docker** — `python:3.12-slim` + `xvfb` + `tini` + non-root user
- **🩹 7 critical bug fixes** — Windows SIGINT, HTTP `/stop` actually working,
  context% math, SOM double-grab, JSON parse error counting, etc.

See [CHANGELOG.md](CHANGELOG.md) for the full list.

---

## 🎬 Quick start

### Option A: pip / pipx (recommended)

```bash
# Install
pip install computer-use-agent
# or with pipx (isolated):
pipx install computer-use-agent

# Configure (one-time)
export LLM_API_KEY=sk-...
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_MODEL=gpt-4o

# Use
cua "open notepad and type Hello World"
```

### Option B: Docker

```bash
docker run -it --rm \
  -e LLM_API_KEY=sk-... \
  -e LLM_BASE_URL=https://api.openai.com/v1 \
  -e LLM_MODEL=gpt-4o \
  -p 127.0.0.1:2024:2024 \
  ghcr.io/snake-aabb-wtf/computer-use-agent:0.2.0 \
  cua --serve --host 0.0.0.0
```

### Option C: From source (development)

```bash
git clone https://github.com/snake-aabb-wtf/computer-use-agent.git
cd computer-use-agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env       # then edit
python -m computer_use_agent "open notepad"
```

### 30-second demo

```bash
# 1. CLI — one-shot task
cua "open the calculator app and compute 2+2"

# 2. REPL — interactive
cua
> /help                    # list 26 commands
> open Settings and turn on dark mode
> /usage                   # show token spend
> /quit

# 3. HTTP API — for other agents
cua --serve --port 8080 &
curl -X POST http://127.0.0.1:8080/run \
  -H "Content-Type: application/json" \
  -d '{"task": "open browser and search weather"}'

# 4. MCP Server — for Claude Desktop / Cursor
cua --mcp
# then add to ~/.config/claude_desktop_config.json (see docs/API.md)
```

---

## 🎯 Three capture modes

| Mode | Mechanism | Click target | Best for |
|------|-----------|--------------|----------|
| **`som`** *(default)* | Windows UIA element tree + numbered red overlay | `element: 7` | Highest accuracy, Windows-only |
| **`vision`** | Pure screenshot + cyan coordinate grid | `coordinate: [x, y]` | Cross-platform, all models |
| **`uitars`** | Pure screenshot + 0–1000 normalized coords | `coordinate: [x, y]` (× screen_size/1000) | UI-TARS / Qwen-VL models |

```env
# In .env
CAPTURE_MODE=som      # Element indexing (Windows)
CAPTURE_MODE=vision   # Pure visual (any OS, any model)
CAPTURE_MODE=uitars   # 0-1000 coords (UI-TARS style)
```

## 🖱️ Action types

The LLM emits JSON actions; CUA normalizes 60+ name variants into 12 standard types:

| Action | JSON | Example |
|---|---|---|
| Left click | `left_click` | `{"action": "left_click", "coordinate": [100, 200]}` |
| Double click | `double_click` | `{"action": "double_click", "coordinate": [100, 200]}` |
| Right click | `right_click` | `{"action": "right_click", "coordinate": [100, 200]}` |
| Type text | `type` | `{"action": "type", "text": "Hello World"}` (CJK via clipboard) |
| Press key | `key` | `{"action": "key", "key": "enter"}` |
| Hold key | `key` | `{"action": "key", "key": "shift", "hold": 2.0}` |
| Hotkey combo | `hotkey` | `{"action": "hotkey", "keys": ["ctrl", "shift", "p"]}` |
| Scroll | `scroll` | `{"action": "scroll", "direction": "down", "amount": 5}` |
| Move mouse | `move` | `{"action": "move", "coordinate": [500, 300]}` |
| Drag | `drag` | `{"action": "drag", "from": [100,100], "to": [200,200], "hold": 0.3}` |
| Wait | `wait` | `{"action": "wait", "seconds": 2}` |
| Re-screenshot | `screenshot` | `{"action": "screenshot"}` |
| Done | `done` | `{"action": "done", "message": "Task completed"}` |

## 🖥️ Interactive REPL (26 slash commands)

```bash
cua
> open the file manager
> /help                    # all 26 commands
> /status                  # show session stats
> /steer focus on the search box  # inject mid-task instruction
> /queue close the dialog  # queue next task
> /stop                    # stop current task
> /compact                 # manually compress history
> /usage                   # token / cost report
> /sessions                # list past sessions
> /resume 1                # restore session #1
> /save                    # export to JSON
> /branch "variant A"      # fork current session
> /model gpt-4o            # switch model on the fly
> /capture-mode som        # switch to SOM mode
> /steps 50                # limit steps
> /clear                   # clear screen
> /quit
```

Full command list: `/help` / `/config` / `/model` / `/usage` / `/status` / `/yolo` /
`/steer` / `/stop` / `/sessions` / `/resume` / `/save` / `/branch` / `/retry` / `/undo` /
`/queue` / `/verbose` / `/compact` / `/history` / `/reset` / `/screen` / `/steps` / `/delay` /
`/title` / `/clear`

---

## 🔌 HTTP REST API

Let other agents (or your own scripts) drive CUA via REST. Zero new dependencies —
pure Python stdlib.

```bash
# Start server
cua --serve --port 8080
```

```bash
# Submit a task
curl -X POST http://127.0.0.1:8080/run \
  -H "Content-Type: application/json" \
  -d '{"task": "open calculator and compute 2+2"}'
# → {"id": "a1b2c3d4e5f6", "status": "accepted"}

# Poll status
curl http://127.0.0.1:8080/status/a1b2c3d4e5f6
# → {"id": "a1b2c3d4e5f6", "status": "done", "result": "...", "finished_at": ...}

# Real-time progress (SSE)
curl -N http://127.0.0.1:8080/stream/a1b2c3d4e5f6

# Cancel a queued or running task
curl -X POST http://127.0.0.1:8080/cancel/a1b2c3d4e5f6
```

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Service info + endpoint list |
| `/health` | GET | Status, busy/idle, queue size |
| `/tasks` | GET | List all tasks (with metadata) |
| `/run` | POST | Submit task (queue if busy; 429 when full) |
| `/status/<id>` | GET | Task status: `queued` → `running` → `done`/`error` |
| `/stream/<id>` | GET | Server-Sent Events (real-time progress) |
| `/stop` | POST | Stop current task (truly interrupts via `Agent.interrupt()`) |
| `/cancel/<id>` | POST | Cancel a specific task |

Authentication: set `API_TOKEN=...` to require Bearer auth. Uses
`hmac.compare_digest` to prevent timing attacks. See [docs/API.md](docs/API.md) for
full reference.

---

## 🧠 MCP Server (Model Context Protocol)

Make CUA available to Claude Desktop, Cursor, Zed, Continue, or any MCP-compatible
client:

```bash
# Start the MCP server (stdio JSON-RPC)
cua --mcp
```

Then add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cua": {
      "command": "cua-mcp",
      "args": []
    }
  }
}
```

Restart Claude Desktop — the `cua.*` tools will appear:

- `cua.run_task(task)` → submit a task
- `cua.stop_task()` → stop the running task
- `cua.get_status(task_id)` → poll status
- `cua.screenshot()` → capture the current screen
- `cua.list_monitors()` → enumerate displays

## 🧩 Plugin system

Teach the LLM your own custom actions. Drop a Python file in
`~/.config/cua/plugins/`:

```python
# ~/.config/cua/plugins/send_email.py
from computer_use_agent.plugins import ActionRegistry

def register(registry: ActionRegistry):
    @registry.register(
        name="send_email",
        description="Send an email via SMTP",
        schema={
            "type": "object",
            "properties": {
                "to":      {"type": "string"},
                "subject": {"type": "string"},
                "body":    {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    )
    def send_email(to: str, subject: str, body: str) -> str:
        # ... your implementation ...
        return f"📧 Sent to {to}: {subject}"
```

CUA auto-discovers and registers the plugin. The LLM can now call `send_email`
alongside built-in actions. See [docs/PLUGINS.md](docs/PLUGINS.md) for the full guide.

## 📡 Webhook notifications

Get a POST when tasks finish:

```env
WEBHOOK_URL=https://your-server/webhook
WEBHOOK_EVENTS=done,error,interrupted
```

Payload:
```json
{
  "event": "done",
  "task_id": "agent-1719234567",
  "task": "open notepad",
  "result": "Opened Notepad",
  "duration_seconds": 12.3,
  "stats": {"total_steps": 5, "api_calls": 5, "tokens_in": 1234, "tokens_out": 567}
}
```

## 📼 Session replay

Record a session and replay it later for debugging / auditing / dataset:

```bash
# After running a task, /save exports a JSONL file
cua
> open notepad and type Hello
> /save
Saved to: logs/saved/conversation_20260624_103045.json

# Replay (dry-run by default)
cua --replay logs/saved/conversation_20260624_103045.json --verbose
```

---

## 🛡️ Safety

CUA is designed to be safe by default:

- **HTTP API** binds to `127.0.0.1` only; `0.0.0.0` requires `API_TOKEN`
- **Bearer auth** uses `hmac.compare_digest` (no timing attacks)
- **CORS** echoes request `Origin` (no `*` wildcard)
- **`pyautogui.FAILSAFE`** opt-in via `PYAUTOGUI_FAILSAFE=on` (mouse-to-corner kill)
- **Never types** passwords / API keys (logger redacts 12 secret patterns)
- **Never closes** terminal windows (minimizes instead)
- **Tool loop guardrails** detect repeated failures, no-progress loops
- **Cross-platform interrupt** via `threading.Event` (no signal-handler hack)
- **Webhook auth** via shared secret

---

## ⚙️ Configuration

All settings via environment variables (typically in `.env`). CLI flags override
`.env` values, which override built-in defaults.

```bash
# Required
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# Optional
CAPTURE_MODE=vision        # som | vision | uitars
MAX_STEPS=200
API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
LANGUAGE=en-US
LOG_FORMAT=json
WEBHOOK_URL=https://...
```

See **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** for the full reference (all
40+ env vars with defaults & descriptions).

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Entry points                                                       │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────────┐                          │
│  │ CLI  │  │ REPL │  │ API  │  │   MCP    │  ← you are here          │
│  └──┬───┘  └──┬───┘  └──┬───┘  └────┬─────┘                          │
│     └────────┴─────────┴──────────┘                                 │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Agent.run(task)                                              │ │
│  │   for step in 1..MAX_STEPS:                                  │ │
│  │     capture screenshot ──▶ screen.py (mss / ImageGrab)        │ │
│  │     _prepare_messages() ──▶ 3-layer token budget             │ │
│  │     chat(screenshot, history) ──▶ llm.py (OpenAI SDK)         │ │
│  │     parse JSON action                                       │ │
│  │     execute(action) ──▶ executor.py (pyautogui / uiautomation)│ │
│  │     guardrail check (loop / no-progress)                      │ │
│  │     append to history                                       │ │
│  │   on done/error/interrupted:                                 │ │
│  │     notify webhook / record replay                          │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full deep-dive
(modules, threading model, data flow, security).

---

## 📁 Project structure

```
computer-use-agent/
├── computer_use_agent/       # 22 Python modules
│   ├── __main__.py           # argparse CLI entry
│   ├── agent.py              # Main loop
│   ├── llm.py                # OpenAI client + retry + JSON parse
│   ├── executor.py           # 12 action types
│   ├── screen.py             # Multi-monitor capture
│   ├── uia_tree.py           # Windows UIA element tree
│   ├── api.py                # HTTP REST API
│   ├── cli.py                # Interactive REPL (26 commands)
│   ├── tui.py                # Live status panel
│   ├── mcp_server.py         # MCP server (stdio JSON-RPC)
│   ├── plugins.py            # Plugin system
│   ├── replay.py             # JSONL session replay
│   ├── webhook.py            # Async notifications
│   ├── i18n.py               # zh-CN / en-US translations
│   ├── logger.py             # Rotating logs + JSON formatter
│   ├── prompts.py            # 10-block system prompt
│   ├── sanitization.py       # 5-pass JSON repair
│   ├── token_budget.py       # 3-layer context budget
│   ├── guardrails.py         # Loop detection
│   ├── visual_effects.py     # Win32 click/drag overlay
│   └── notify.py             # Windows notification
├── tests/                    # 13 test files
├── docs/                     # ARCHITECTURE / CONFIGURATION / API / PLUGINS
├── .github/workflows/        # CI / Release / CodeQL
├── Dockerfile + docker-compose.yml
├── pyproject.toml            # 4 console_scripts
├── CHANGELOG.md              # v0.2.0 release notes
└── CONTRIBUTING.md
```

---

## 🧪 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check computer_use_agent/
ruff format --check computer_use_agent/

# Type check
mypy computer_use_agent/ --ignore-missing-imports

# Security scan
bandit -r computer_use_agent/ -ll
```

CI runs automatically on every push:
- 3 OS × 3 Python version matrix (Linux / Windows / macOS × 3.10 / 3.11 / 3.12)
- Smoke test (verify all modules import)
- Lint (ruff + bandit)
- CodeQL security analysis

## 🤝 Contributing

We welcome PRs! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup
- Code style (ruff + mypy)
- Conventional Commits
- PR template & review process

## 📜 License

MIT — see [LICENSE](LICENSE).

## 🙏 Acknowledgments

Architecture inspired by:

- [Hermes Agent](https://github.com/nousresearch/hermes-agent) — engineering patterns
  (retry, backoff, history compression, guardrails)
- [UI-TARS-desktop](https://github.com/user-ailab/UI-TARS-desktop) — capture modes,
  action normalization, visual feedback

Built with [pyautogui](https://github.com/asweigart/pyautogui),
[mss](https://github.com/BoboTiG/ebook-reader-dict), [Rich](https://github.com/Textualize/rich),
[prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit), and
[OpenAI Python SDK](https://github.com/openai/openai-python).

---

**[⬆ Back to top](#-computer-use-agent)**
