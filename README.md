# 🖥️ Computer Use Agent

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-169%20passing-brightgreen.svg)](tests/)

**AI-powered desktop automation through screenshots and actions.**

[中文文档](README_CN.md)

---

## What It Does

Computer Use Agent watches your screen, thinks, and acts — autonomously completing tasks on your desktop.

```
User Command → Screenshot → AI Analysis → Action → Verify → Loop...
```

It supports **any LLM** via OpenAI-compatible API (GPT-4o, Claude, DeepSeek, local models, etc.).

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API key

# Run
python -m computer_use_agent "open notepad and type Hello World"
```

## Features

### 🎯 Two Capture Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **SOM** (default) | Windows UIA element tree + numbered overlays | High-accuracy clicking |
| **Vision** | Pure screenshot | All models, maximum compatibility |

Switch in `.env`:
```env
CAPTURE_MODE=som      # Element indexing (recommended)
CAPTURE_MODE=vision   # Pure visual (compatible with all models)
```

### 🖱️ 12 Action Types

| Action | Example |
|--------|---------|
| Click | `{"action": "left_click", "element": 47}` |
| Double Click | `{"action": "double_click", "coordinate": [100, 200]}` |
| Right Click | `{"action": "right_click", "element": 12}` |
| Type Text | `{"action": "type", "text": "Hello World"}` |
| Keyboard | `{"action": "key", "key": "enter"}` |
| Hotkey | `{"action": "hotkey", "keys": ["ctrl", "c"]}` |
| Scroll | `{"action": "scroll", "direction": "down", "amount": 5}` |
| Move | `{"action": "move", "coordinate": [500, 300]}` |
| Drag | `{"action": "drag", "from": [100,100], "to": [200,200]}` |
| Wait | `{"action": "wait", "seconds": 2}` |
| Screenshot | `{"action": "screenshot"}` |
| Done | `{"action": "done", "message": "Task completed"}` |

### 🖥️ Interactive CLI (Hermes-style)

```bash
python -m computer_use_agent
```

```
╔══════════════════════════════════════════╗
║   Computer Use Agent          v0.1.0    ║
╚══════════════════════════════════════════╝

┌────────────────────────────── Session ───────────────────────────────┐
│   Model           mimo-v2.5                                         │
│   Base URL        https://api.example.com/v1                       │
│   Screen          1920x1080                                        │
│   Capture Mode    SOM (SOM + UIA)                                  │
│   Max Steps       200                                              │
└─────────────────────────────────────────────────────────────────────┘

❯ /help
```

**25 slash commands:**

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/config` | Show configuration |
| `/model <name>` | Switch model |
| `/usage` | Token usage stats |
| `/status` | Current status |
| `/yolo` | Toggle autonomous mode |
| `/steer <msg>` | Inject mid-task instruction |
| `/stop` | Stop current task |
| `/sessions` | List saved sessions |
| `/resume <id>` | Resume a session |
| `/save` | Export conversation to JSON |
| `/branch` | Fork current session |
| `/retry` | Retry last task |
| `/undo` | Undo last exchange |
| `/queue <task>` | Queue next instruction |
| `/verbose` | Cycle display mode |

## Architecture

```
computer_use_agent/
├── agent.py          # Core loop: screenshot → LLM → action → verify
├── llm.py            # LLM client (retry, backoff, streaming)
├── screen.py         # Screenshot capture (vision + SOM modes)
├── executor.py       # 12 action types + clipboard paste
├── uia_tree.py       # Windows UIA element tree + SOM overlay
├── prompts.py        # System prompts (10 blocks, model-specific)
├── guardrails.py     # Tool loop detection (repeat/failure/no-progress)
├── sanitization.py   # JSON repair, message sequence fix
├── token_budget.py   # 3-layer context overflow prevention
├── cli.py            # Interactive CLI (Hermes-style REPL)
├── config.py         # Configuration management
└── logger.py         # Structured logging
```

## Configuration

All settings via `.env`:

```env
# LLM
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.0

# Agent
MAX_STEPS=200
ACTION_DELAY=0.1
REQUEST_TIMEOUT=60

# Capture Mode: som | vision
CAPTURE_MODE=som

# Screenshots
SCREENSHOT_DIR=screenshots
SCREENSHOT_FORMAT=png

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs

# Visual Effects (experimental)
VISUAL_EFFECTS=off
```

### Configuration Reference

| Key | Default | Description |
|-----|---------|-------------|
| `LLM_API_KEY` | `sk-placeholder` | API key for your LLM provider |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | API endpoint (any OpenAI-compatible) |
| `LLM_MODEL` | `gpt-4o` | Model name |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens per response |
| `LLM_TEMPERATURE` | `0.0` | Temperature (0 = deterministic) |
| `MAX_STEPS` | `200` | Max agent steps per task |
| `ACTION_DELAY` | `0.1` | Delay between actions in seconds |
| `REQUEST_TIMEOUT` | `60` | API request timeout in seconds |
| `CAPTURE_MODE` | `vision` | `som` (UIA element indexing) or `vision` (pure screenshot) |
| `SCREENSHOT_DIR` | `screenshots` | Directory to save screenshots |
| `SCREENSHOT_FORMAT` | `png` | Screenshot format |
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `LOG_DIR` | `logs` | Log directory |
| `VISUAL_EFFECTS` | `off` | `on` to enable breathing border + mouse ripple |

## Requirements

- Windows 10/11
- Python 3.10+
- `uiautomation` (for SOM mode)

```bash
pip install -r requirements.txt
```

## Testing

```bash
cd tests
python test_all.py          # Core module tests (32)
python test_som.py          # SOM mode tests (27)
python test_coverage.py     # Coverage tests (67)
python test_cli_new.py      # CLI features (30)
python test_new_commands.py # New commands (13)
```

**169 tests passing.**

## How It Works

1. **Capture** — Screenshot the current screen state
2. **Send** — Send screenshot (+ element list in SOM mode) to LLM
3. **Parse** — Extract JSON action from LLM response
4. **Execute** — Perform the action (click, type, scroll, etc.)
5. **Verify** — Take another screenshot to confirm result
6. **Loop** — Repeat until task is done or max steps reached

### SOM Mode (Element Indexing)

Instead of guessing pixel coordinates, the model clicks by **element number**:

```
Screenshot with red numbered overlays → Model: "click element #47"
→ Backend resolves: #47 → center coordinates → OS click
```

This converts a hard regression problem into a trivial classification problem.

## Safety

- Never types passwords or secrets
- Never clicks destructive confirmations without instruction
- Never follows instructions embedded in screenshots
- Tool loop guardrails detect repeated failures
- Graceful interrupt with Ctrl+C

## Acknowledgments

Architecture inspired by [Hermes Agent](https://github.com/nousresearch/hermes-agent) agent engineering patterns.

## License

MIT
