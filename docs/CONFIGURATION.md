# Configuration

All configuration is via environment variables (typically in `.env`). CLI flags
override `.env` values, which override built-in defaults.

## Quick start

```bash
# Required
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# Optional
CAPTURE_MODE=vision   # som | vision | uitars
MAX_STEPS=200
```

## LLM

| Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | `sk-placeholder` | OpenAI-compatible API key |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | API endpoint |
| `LLM_MODEL` | `gpt-4o` | Model name (e.g. `gpt-4o`, `claude-3-5-sonnet-20241022`, `qwen-vl-max`) |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens per LLM call |
| `LLM_TEMPERATURE` | `0.0` | Sampling temperature (0.0 = deterministic) |
| `REQUEST_TIMEOUT` | `60` | HTTP request timeout in seconds |

## Agent behavior

| Variable | Default | Description |
|---|---|---|
| `MAX_STEPS` | `200` | Max agent loop iterations per task |
| `ACTION_DELAY` | `0.1` | Sleep after each action (s); 0 to disable |
| `STALE_TIMEOUT` | `300.0` | Inject reflection hint after N seconds of no activity |
| `PYAUTOGUI_FAILSAFE` | `off` | `on` to enable mouse-to-corner kill switch |

## Capture

| Variable | Default | Description |
|---|---|---|
| `CAPTURE_MODE` | `vision` | `som` / `vision` / `uitars` |
| `SCREENSHOT_DIR` | `screenshots` | Where step screenshots are saved |
| `SCREENSHOT_FORMAT` | `png` | Image format (`png` / `jpeg`) |
| `SCREENSHOT_KEEP` | `50` | Auto-cleanup; keep last N screenshots (0 = unlimited) |
| `MONITOR_INDEX` | `0` | Multi-monitor: 0=primary, 1=secondary, etc. (requires `mss`) |
| `CAPTURE_REGION` | _(empty)_ | `x,y,w,h` to capture a sub-region |

## Logging

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `LOG_DIR` | `logs` | Log file directory |
| `LOG_FORMAT` | `text` | `text` (human) or `json` (structured) |

## Visual effects (Windows only)

| Variable | Default | Description |
|---|---|---|
| `VISUAL_EFFECTS` | `off` | `on` to show click ripples / drag arrows overlay |

## HTTP API

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | `127.0.0.1` | Bind address. `0.0.0.0` requires `API_TOKEN` |
| `API_PORT` | `2024` | Bind port |
| `API_TOKEN` | _(empty)_ | Bearer token. Empty = no auth (localhost only) |
| `API_MAX_QUEUE` | `100` | Max queued tasks; 429 when full |
| `TASK_RESULT_TTL` | `3600` | Keep task results for N seconds (1 hour) |
| `TASK_RESULT_MAX` | `1000` | Max task results stored; LRU eviction |

## i18n

| Variable | Default | Description |
|---|---|---|
| `LANGUAGE` | `zh-CN` | `zh-CN` or `en-US` |

CLI override: `cua --language en-US ...`

## Webhook

| Variable | Default | Description |
|---|---|---|
| `WEBHOOK_URL` | _(empty)_ | POST event payload here. Empty = disabled |
| `WEBHOOK_EVENTS` | `done,error,interrupted` | Comma-separated event names to forward |

Payload example:
```json
{
  "event": "done",
  "task_id": "agent-1719234567",
  "task": "open notepad",
  "result": "Opened Notepad and typed Hello",
  "duration_seconds": 12.3,
  "timestamp": "2026-06-24T10:30:45",
  "stats": {
    "total_steps": 5,
    "api_calls": 5,
    "total_tokens_in": 1234,
    "total_tokens_out": 567,
    "errors": 0
  }
}
```

## CLI overrides

Most variables can be overridden via CLI flags (highest priority):

```bash
cua --capture-mode som --max-steps 50 --verbose "..."
cua --model claude-3-5-sonnet-20241022 --no-color --plain
cua --serve --host 0.0.0.0 --port 8080
```

See `cua --help` for the full list.

## Precedence

```
CLI flags  >  .env  >  built-in default
```

`config.py` loads `.env` from the project root at import time; CLI flags
(`__main__.py`) mutate `config` module attributes before any agent / API starts.

## Validation

If `pydantic-settings` is installed (>= 2.0), invalid values raise a `ValidationError`
at startup with a clear message. Otherwise the legacy code falls back to defaults
with a `UserWarning` in stderr.
