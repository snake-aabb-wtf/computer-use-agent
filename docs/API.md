# API Reference

Computer Use Agent v0.2.0 exposes **two programmatic interfaces**:

1. **HTTP REST API** — fire-and-forget task submission, polling for status
2. **MCP (Model Context Protocol) Server** — bidirectional, real-time for AI agents

Both are optional and run alongside the CLI. The HTTP API uses Python stdlib
(`http.server`); MCP uses stdlib + JSON-RPC over stdio. **Zero external dependencies**.

## Quick start

```bash
# HTTP API
cua --serve --port 8080

# MCP Server (for Claude Desktop / Cursor / Zed)
cua --mcp

# One-shot task
cua "open notepad and type Hello World"
```

---

## HTTP REST API

### Authentication

| Condition | Auth required |
|---|---|
| `API_HOST=127.0.0.1` (default) and `API_TOKEN` not set | No |
| `API_HOST=0.0.0.0` and `API_TOKEN` not set | **Server refuses to start** |
| `API_TOKEN=<value>` (any host) | **Yes** — `Authorization: Bearer <API_TOKEN>` |

The token comparison uses `hmac.compare_digest` to prevent timing attacks.

### CORS

| Condition | Behavior |
|---|---|
| `API_TOKEN` set | `Access-Control-Allow-Origin: *` |
| `API_TOKEN` not set | Echoes request `Origin` only if from localhost |

### Endpoints

#### `GET /` — Service info

```http
GET / HTTP/1.1
```

Response 200:
```json
{
  "service": "computer-use-agent",
  "version": "0.2.0",
  "endpoints": { ... },
  "auth": "Bearer token required (API_TOKEN is set)" | "none (localhost only)"
}
```

#### `GET /health` — Health check

Response 200:
```json
{
  "status": "ok",
  "busy": false,
  "current_task": null,
  "queue_size": 0,
  "tasks_tracked": 12
}
```

#### `POST /run` — Submit a task

```http
POST /run HTTP/1.1
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{
  "task": "open notepad and type Hello World"
}
```

Response 202 (accepted):
```json
{
  "id": "a3f8b2c1d4e5",
  "status": "accepted"
}
```

Error responses:
- `400 {"error": "missing 'task' field"}` — no `task` in body
- `400 {"error": "'task' must be a non-empty string"}` — empty / non-string
- `401 {"error": "unauthorized", "hint": "..."}` — missing/invalid token
- `429 {"error": "queue full", "limit": 100}` — `API_MAX_QUEUE` reached

#### `GET /status/<id>` — Poll task status

```http
GET /status/a3f8b2c1d4e5 HTTP/1.1
```

Response 200:
```json
{
  "id": "a3f8b2c1d4e5",
  "status": "running",   // queued | running | done | error | cancelled
  "result": null,
  "error": null,
  "task": "open notepad and type Hello World",
  "started_at": 1719234567.123,
  "finished_at": null
}
```

#### `GET /tasks` — List all tasks

```http
GET /tasks HTTP/1.1
```

Response 200:
```json
{
  "tasks": [
    {"id": "...", "status": "...", ...},
    ...
  ],
  "count": 5
}
```

#### `GET /stream/<id>` — Server-Sent Events

```http
GET /stream/a3f8b2c1d4e5 HTTP/1.1
Accept: text/event-stream
```

Response (chunked):
```
data: {"id": "a3f8b2c1d4e5", "status": "running", ...}

data: {"id": "a3f8b2c1d4e5", "status": "done", "result": "Opened Notepad", "finished_at": 1719234579.456}

```

The stream closes when the task reaches a terminal state.

#### `POST /stop` — Stop current task

```http
POST /stop HTTP/1.1
```

Response 200:
```json
{"status": "stopped"}
```

Calls `Agent.interrupt()` via the worker thread; the task is marked as `error` with
`"Task stopped by user"`.

#### `POST /cancel/<id>` — Cancel a specific task

```http
POST /cancel/a3f8b2c1d4e5 HTTP/1.1
```

Behavior:
- If `<id>` is the **currently running** task → calls `_stop_current()` (real interrupt)
- If `<id>` is **queued** → marks `status=cancelled` (worker skips on pickup)
- If `<id>` is **already finished** → returns current status with a `note` field

### Example: curl workflow

```bash
# 1. Submit
TASK_ID=$(curl -s -X POST http://localhost:2024/run \
  -H "Content-Type: application/json" \
  -d '{"task": "open notepad"}' | jq -r .id)

# 2. Poll (or use stream)
while true; do
  STATUS=$(curl -s http://localhost:2024/status/$TASK_ID | jq -r .status)
  echo "Status: $STATUS"
  [[ "$STATUS" == "done" || "$STATUS" == "error" || "$STATUS" == "cancelled" ]] && break
  sleep 2
done

# 3. Get result
curl -s http://localhost:2024/status/$TASK_ID | jq .
```

---

## MCP Server

The MCP (Model Context Protocol) server lets AI agents in **Claude Desktop, Cursor,
Zed, Continue, etc.** drive CUA directly through standardized tool calls.

### Setup (Claude Desktop example)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

Restart Claude Desktop; the `cua.*` tools will appear.

### Protocol

- Transport: **stdio** (JSON-RPC 2.0 over stdin/stdout)
- Protocol version: **2024-11-05**
- One process per MCP client (Claude Desktop spawns one)

### Tools

#### `cua.run_task` — Submit a task

Input:
```json
{
  "task": "open notepad and type Hello World"
}
```

Output:
```json
{
  "task_id": "a3f8b2c1d4e5",
  "status": "accepted"
}
```

#### `cua.stop_task` — Stop the running task

Input: `{}`

Output: `{"status": "stopped"}`

#### `cua.get_status` — Query task status

Input:
```json
{"task_id": "a3f8b2c1d4e5"}
```

Output:
```json
{
  "task_id": "a3f8b2c1d4e5",
  "status": "running",
  "result": null,
  "error": null,
  "task": "open notepad",
  "started_at": 1719234567.123,
  "finished_at": null
}
```

#### `cua.screenshot` — Capture current screen

Input: `{}`

Output:
```json
{
  "format": "png",
  "width": 1920,
  "height": 1080,
  "data": "<base64-encoded PNG>"
}
```

#### `cua.list_monitors` — List available monitors

Input: `{}`

Output:
```json
{
  "monitors": [
    {"index": 0, "left": 0, "top": 0, "width": 1920, "height": 1080, "is_primary": true}
  ],
  "count": 1
}
```

### Example: full client loop

```python
import json
import subprocess

proc = subprocess.Popen(
    ["cua-mcp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)

def call(method, params=None, id_=1):
    req = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    return json.loads(line)

# 1. Initialize
init = call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})
print(init["result"]["serverInfo"])
# {"name": "computer-use-agent", "version": "0.2.0"}

# 2. Submit task
task = call("tools/call", {
    "name": "cua.run_task",
    "arguments": {"task": "open notepad"}
}, id_=2)
content = json.loads(task["result"]["content"][0]["text"])
task_id = content["task_id"]
print(f"Submitted: {task_id}")

# 3. Poll
import time
while True:
    status_resp = call("tools/call", {
        "name": "cua.get_status",
        "arguments": {"task_id": task_id}
    }, id_=3)
    info = json.loads(status_resp["result"]["content"][0]["text"])
    print(f"Status: {info['status']}")
    if info["status"] in ("done", "error", "cancelled"):
        break
    time.sleep(2)

print(f"Result: {info['result']}")
proc.terminate()
```

---

## Webhook

If `WEBHOOK_URL` is set, CUA POSTs task events to that URL.

```json
{
  "event": "done",  // done | error | interrupted
  "task_id": "agent-1719234567",
  "task": "open notepad",
  "result": "Opened Notepad and typed Hello",
  "error": null,
  "duration_seconds": 12.3,
  "timestamp": "2026-06-24T10:30:45.123+00:00",
  "stats": {
    "total_steps": 5,
    "api_calls": 5,
    "total_tokens_in": 1234,
    "total_tokens_out": 567,
    "errors": 0
  }
}
```

Filter events via `WEBHOOK_EVENTS=done,error` (comma-separated).

The POST is **asynchronous** (daemon thread) and **non-blocking**.

---

## Comparison

| Feature | HTTP API | MCP Server |
|---|---|---|
| Transport | HTTP (TCP) | stdio (JSON-RPC) |
| Suitable for | Dashboards, scripts, polling | AI agents (Claude Desktop) |
| Auth | Bearer token (optional) | Process-level (no auth needed) |
| Real-time progress | SSE (`/stream/<id>`) | Polling only |
| Multi-tenant | Yes (queue) | No (one process per client) |
| Restart on code change | Manual | Auto (Claude Desktop restarts) |

## Limits

- `API_MAX_QUEUE` (default 100) — max queued tasks
- `TASK_RESULT_TTL` (default 3600s) — task results pruned after 1 hour
- `TASK_RESULT_MAX` (default 1000) — LRU eviction
- `MAX_STEPS` (default 200) — max agent loop iterations per task
- `LOG_FORMAT=json` recommended for production observability
