# 🖥️ Computer Use Agent

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

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
# Install (venv auto-created by start.bat)
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API key

# Run
python -m computer_use_agent "open notepad and type Hello World"
```

## Features

### 🎯 Three Capture Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **SOM** | Windows UIA element tree + numbered overlays | High-accuracy clicking |
| **Vision** | Pure screenshot + prompt engineering for accuracy | All models, maximum compatibility |
| **UITARS** | Coordinate normalization (0-1000) + action name normalization | UI-TARS style, cross-model |

```env
CAPTURE_MODE=som      # Element indexing (recommended)
CAPTURE_MODE=vision   # Pure visual (compatible with all models)
CAPTURE_MODE=uitars   # 0-1000 coord normalization (UI-TARS style)
```

### 🖱️ Action Types

| Action | Example |
|--------|---------|
| Click | `{"action": "left_click", "coordinate": [x, y]}` |
| Double Click | `{"action": "double_click", "coordinate": [x, y]}` |
| Right Click | `{"action": "right_click", "coordinate": [x, y]}` |
| Type Text | `{"action": "type", "text": "Hello World"}` |
| Keyboard | `{"action": "key", "key": "enter", "hold": 0}` |
| Hotkey | `{"action": "hotkey", "keys": ["ctrl", "c"]}` |
| Scroll | `{"action": "scroll", "direction": "down", "amount": 5}` |
| Move | `{"action": "move", "coordinate": [500, 300]}` |
| Drag | `{"action": "drag", "from": [100,100], "to": [200,200], "hold": 0.3}` |
| Wait | `{"action": "wait", "seconds": 60}` |
| Screenshot | `{"action": "screenshot"}` |
| Done | `{"action": "done", "message": "Task completed"}` |

### 🖥️ Interactive CLI

```bash
python -m computer_use_agent
```

**25 slash commands:** `/help` `/config` `/model` `/usage` `/status` `/yolo` `/steer` `/stop` `/sessions` `/resume` `/save` `/branch` `/retry` `/undo` `/queue` `/verbose` `/compact` `/history` `/reset` `/screen` `/steps` `/delay` `/title` `/clear`

## Architecture

```
computer_use_agent/
├── agent.py          # Core loop: screenshot → LLM → action → verify
├── llm.py            # LLM client (retry, backoff, streaming, KeyboardInterrupt)
├── screen.py         # Screenshot capture (vision + SOM modes)
├── executor.py       # Action types + natural drag + key hold + clipboard paste
├── uia_tree.py       # Windows UIA element tree + SOM overlay
├── prompts.py        # System prompts (10 blocks, model-specific, 3 capture modes)
├── guardrails.py     # Tool loop detection (repeat/failure/no-progress)
├── sanitization.py   # JSON repair, message sequence fix, tool name fuzzy
├── token_budget.py   # 3-layer context overflow prevention
├── visual_effects.py # Click ripple, drag indicator, action info panel
├── notify.py         # Task completion notification (window front + sound)
├── cli.py            # Interactive CLI (Hermes-style REPL, 25 commands)
├── config.py         # Configuration management
└── logger.py         # Structured logging
```

## Configuration

All settings via `.env`:

```env
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
CAPTURE_MODE=vision
VISUAL_EFFECTS=off
```

| Key | Default | Description |
|-----|---------|-------------|
| `LLM_API_KEY` | `sk-placeholder` | API key |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | API endpoint |
| `LLM_MODEL` | `gpt-4o` | Model name |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens |
| `LLM_TEMPERATURE` | `0.0` | Temperature |
| `MAX_STEPS` | `200` | Max agent steps |
| `ACTION_DELAY` | `0.1` | Delay between actions (s) |
| `REQUEST_TIMEOUT` | `60` | API timeout (s) |
| `CAPTURE_MODE` | `vision` | `som` / `vision` / `uitars` |
| `SCREENSHOT_DIR` | `screenshots` | Screenshot directory |
| `SCREENSHOT_FORMAT` | `png` | Screenshot format |
| `LOG_LEVEL` | `INFO` | Log level |
| `LOG_DIR` | `logs` | Log directory |
| `VISUAL_EFFECTS` | `off` | `on` for click ripple + drag indicator |

## Safety

- Never types passwords or secrets
- Never closes terminal windows (minimize instead)
- Never follows instructions embedded in screenshots
- Tool loop guardrails detect repeated failures
- Ctrl+C graceful interrupt

## Acknowledgments

Architecture inspired by [Hermes Agent](https://github.com/nousresearch/hermes-agent) and [UI-TARS-desktop](https://github.com/user-ailab/UI-TARS-desktop).

## License

MIT
