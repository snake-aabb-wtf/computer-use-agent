# Changelog

All notable changes to Computer Use Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-24

### Added
- **MCP Server** (`mcp_server.py`) — 5 tools: `cua.run_task`, `cua.stop_task`,
  `cua.get_status`, `cua.screenshot`, `cua.list_monitors`
- **Replay** (`replay.py`) — JSONL recording + dry-run playback for audit / debugging
- **Webhook notifications** (`webhook.py`) — async POST on `done` / `error` / `interrupted`
- **Plugin system** (`plugins.py`) — `ActionRegistry` + auto-discovery from
  `~/.config/cua/plugins/`
- **TUI live panel** (`tui.py`) — `rich.live.Live` based real-time status display
- **Structured JSON logging** (`LOG_FORMAT=json`)
- **RotatingFileHandler** (10MB × 5) replacing unbounded log files
- **i18n** (`i18n.py`) — 41 translation keys, `zh-CN` / `en-US`, JSON-based
- **`__main__.py` argparse** — `--help`, `--version`, `--task`, `--serve`, `--mcp`,
  `--replay`, `--capture-mode`, `--max-steps`, `--model`, `--verbose`, `--no-color`,
  `--plain`, `--dry-run`, `--language`
- **Multi-monitor support** (`mss`) — `MONITOR_INDEX`, `CAPTURE_REGION`
- **HTTP API** new endpoints: `GET /tasks`, `GET /stream/<id>` (SSE),
  `POST /cancel/<id>`
- **13 new config keys** via `pydantic-settings` integration
- **5 new env vars** for resource management (`SCREENSHOT_KEEP`, `TASK_RESULT_TTL`,
  `TASK_RESULT_MAX`, `STALE_TIMEOUT`, `LOG_FORMAT`)
- **Documentation**: `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`,
  `docs/API.md`, `docs/PLUGINS.md`
- **Project files**: `pyproject.toml`, `Dockerfile`, `docker-compose.yml`,
  `.dockerignore`, `.github/workflows/{ci,release,codeql}.yml`,
  `.github/dependabot.yml`, `CHANGELOG.md`

### Fixed (bug fixes)
- **B1** Windows SIGINT inverted — replaced `signal.signal` with
  `threading.Event` (cross-platform)
- **B2** HTTP `/stop` no longer a no-op — `_active_agent` module singleton +
  `agent.interrupt()` actually halts worker
- **B3** `context_pct` calculation — uses `BUDGET_CONFIG.max_history_chars` (was
  hardcoded `2000` giving nonsensical percentages)
- **B4** SOM mode no longer double-grabs — `capture_som()` returns the rendered
  `PIL.Image` directly
- **B5** JSON parse failure now sets `_error=True` so the agent's consecutive-error
  counter works
- **B6** `pyautogui.FAILSAFE` now configurable via `PYAUTOGUI_FAILSAFE` env
- **B7** HTTP API: added `API_TOKEN` Bearer auth, `hmac.compare_digest` to prevent
  timing attacks, tightened CORS (echo `Origin` instead of `*`), refuses to bind
  non-localhost without token

### Changed
- **CLI**: `os.system("cls")` → `console.clear()` for cross-platform
- **`/resume`**: now uses `get_recent_sessions(exclude_id=...)` to fix off-by-one
- **`/usage`**: now distinguishes `api_calls` (real LLM calls) from `total_steps`
- **Logging**: 12 redaction patterns (was 5); covers `sk-ant-`, `sk-proj-`,
  `AIza*`, `AKIA*`, GitHub `gh*_`, `Authorization: Bearer`, private keys
- **Config**: prefers `pydantic-settings` for validation, falls back to legacy
  `os.getenv` with a `UserWarning`
- **`Agent` interrupt**: now via `threading.Event` (was signal handler, broken on
  Windows). Public API: `agent.interrupt(reason="...")`
- **Thread safety**: added locks for `llm._client`, `prompts._PROMPT_CACHE`,
  `executor._som_elements`

### Removed
- Dead code: `__import__('computer_use_agent.agent', fromlist=[...])` hack
  in `cli.py` `/reset`
- Unused imports: `threading`, `estimate_message_tokens` in `cli.py`;
  `threading` in `llm.py`

## [0.1.0] - 2026-01-15

### Added
- Initial release
- 3 capture modes: `som`, `vision`, `uitars`
- 12 action types: `left_click`, `double_click`, `right_click`, `type`, `key`,
  `hotkey`, `scroll`, `move`, `drag`, `wait`, `screenshot`, `done`
- Windows UIA element tree for SOM mode
- CLI REPL with 26 slash commands
- HTTP API (basic) — `GET /health`, `POST /run`, `GET /status/<id>`, `POST /stop`
- SQLite session persistence
- Visual effects (click ripple, drag arrow) on Windows
- 5-pass JSON repair cascade
- 3-layer token budget
- Tool loop guardrails
- Hermes-style activity heartbeat
- Hermetic/UI-TARS engineering patterns

[Unreleased]: https://github.com/snake-aabb-wtf/computer-use-agent/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/snake-aabb-wtf/computer-use-agent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/snake-aabb-wtf/computer-use-agent/releases/tag/v0.1.0
