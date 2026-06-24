"""HTTP API — 让其他终端型 Agent 通过 REST 接口驱动 computer-use-agent

零依赖（纯 stdlib http.server + json），任何语言/框架都能调用。

启动方式:
    python -m computer_use_agent --serve          # 默认 127.0.0.1:2024
    python -m computer_use_agent --serve --port 8080

接口:
    GET  /health          → {"status":"ok","busy":false}
    POST /run             → {"task":"..."} → {"id":"...","status":"accepted"}
    GET  /status/<id>     → {"id":"...","status":"running|done|error","result":"..."}
    POST /stop            → {"status":"stopped"}
    GET  /tasks           → 列出所有任务
    GET  /stream/<id>     → Server-Sent Events 实时进度

安全 (修复 B7):
- API_TOKEN 环境变量设置后需要 Bearer Token 鉴权
- 仅绑定 127.0.0.1 时无需 Token（默认）
- 绑定 0.0.0.0 / 公网 IP 时强制要求 API_TOKEN，否则拒绝启动
- CORS: 本地回显 Origin（默认）；有 API_TOKEN 时才允许通配
"""

import json
import uuid
import queue
import threading
import time
import logging
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from . import config
from .agent import Agent
from .logger import setup_logger

logger = logging.getLogger("agent.api")

# ── 任务管理 ──

_task_queue: queue.Queue = queue.Queue()
_task_results: dict[str, dict] = {}   # id -> {status, result, error, finished_at}
_task_lock = threading.Lock()
_current_task_id: str | None = None
_active_agent: Agent | None = None  # 修复 B2: 把 agent 提升为模块级单例
_active_agent_lock = threading.Lock()
_running = False


def _prune_old_results():
    """修复 S3: 清理过期的任务结果，避免内存无限增长。"""
    if not (config.TASK_RESULT_TTL > 0 and config.TASK_RESULT_MAX > 0):
        return
    now = time.time()
    with _task_lock:
        # TTL 过期清理
        expired = [
            tid for tid, info in _task_results.items()
            if info.get("finished_at")
            and now - info["finished_at"] > config.TASK_RESULT_TTL
        ]
        for tid in expired:
            _task_results.pop(tid, None)
        # 超过上限时按 finished_at 淘汰最旧的
        if len(_task_results) > config.TASK_RESULT_MAX:
            oldest = sorted(
                (t for t in _task_results.items() if t[1].get("finished_at")),
                key=lambda kv: kv[1]["finished_at"],
            )
            for tid, _ in oldest[: len(_task_results) - config.TASK_RESULT_MAX]:
                _task_results.pop(tid, None)


def _worker():
    """后台 worker 线程：从队列取任务，执行 agent，记录结果。"""
    global _current_task_id, _active_agent

    # 修复 B2: agent 提升为模块级，_stop_current() 可通过 _active_agent 中断
    agent = Agent(save_screenshots=True)
    with _active_agent_lock:
        _active_agent = agent

    while True:
        task_id, task_text = _task_queue.get()
        if task_id is None:
            break

        with _task_lock:
            _current_task_id = task_id
            _task_results[task_id] = {
                "status": "running",
                "result": None,
                "error": None,
                "task": task_text,
                "started_at": time.time(),
                "finished_at": None,
            }

        try:
            result = agent.run(task_text)
            with _task_lock:
                _task_results[task_id] = {
                    "status": "done",
                    "result": result,
                    "error": None,
                    "task": task_text,
                    "started_at": _task_results[task_id]["started_at"],
                    "finished_at": time.time(),
                }
        except Exception as e:
            with _task_lock:
                _task_results[task_id] = {
                    "status": "error",
                    "result": None,
                    "error": str(e),
                    "task": task_text,
                    "started_at": _task_results[task_id]["started_at"],
                    "finished_at": time.time(),
                }
        finally:
            with _task_lock:
                _current_task_id = None
            _prune_old_results()


def _submit_task(task: str) -> str:
    """提交任务到队列，返回 task_id。"""
    task_id = uuid.uuid4().hex[:12]
    with _task_lock:
        _task_results[task_id] = {
            "status": "queued",
            "result": None,
            "error": None,
            "task": task,
            "started_at": None,
            "finished_at": None,
        }
    _task_queue.put((task_id, task))
    return task_id


def _stop_current():
    """修复 B2: 真正停止当前任务。

    通过 _active_agent.interrupt() 设置 threading.Event，
    Agent 在下个 step 检查点处停止。
    """
    global _current_task_id
    with _active_agent_lock:
        agent = _active_agent
    if agent is not None:
        agent.interrupt(reason="api /stop")

    with _task_lock:
        if _current_task_id:
            existing = _task_results.get(_current_task_id, {})
            existing["status"] = "error"
            existing["error"] = "Task stopped by user"
            existing["finished_at"] = time.time()
        _current_task_id = None

    # 清空待处理队列
    while not _task_queue.empty():
        try:
            _task_queue.get_nowait()
        except queue.Empty:
            break


def _is_local_host(host: str) -> bool:
    """判断是否绑定到本机回环地址。"""
    if host in ("127.0.0.1", "localhost", "::1"):
        return True
    try:
        ip = socket.gethostbyname(host)
        return ip.startswith("127.") or ip == "::1"
    except Exception:
        return False


# ── HTTP Handler ──

class _APIHandler(BaseHTTPRequestHandler):
    server_version = "ComputerUseAgent/0.2"

    def log_message(self, fmt, *args):
        logger.debug(f"API: {fmt % args}")

    # ── 修复 B7: CORS 与鉴权 ──

    def _origin_allowed(self) -> bool:
        """根据绑定地址与是否设置 API_TOKEN 决定 CORS 策略。"""
        if not config.API_TOKEN:
            # 未设置 Token 时仅放行本机
            return self._client_is_local()
        return True  # 设置了 Token 的情况下，调用方在 _check_auth 中验证

    def _client_is_local(self) -> bool:
        client = self.client_address[0] if self.client_address else ""
        return client in ("127.0.0.1", "::1", "localhost")

    def _check_auth(self) -> bool:
        """若设置了 API_TOKEN，强制验证 Authorization 头。"""
        if not config.API_TOKEN:
            return True  # 无 Token 配置时跳过（仅本机访问）
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            # 用 hmac.compare_digest 防时序攻击
            import hmac
            return hmac.compare_digest(auth[7:].strip(), config.API_TOKEN)
        return False

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # 修复 B7: CORS 不再硬编码 *；本地回显 Origin，否则不发送
        origin = self.headers.get("Origin")
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        elif config.API_TOKEN:
            # 设置了 Token 时允许通配（认证通过后）
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_auth_required(self):
        body = json.dumps({"error": "unauthorized", "hint": "Authorization: Bearer <API_TOKEN>"}).encode("utf-8")
        self.send_response(401)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("WWW-Authenticate", 'Bearer realm="computer-use-agent"')
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return None

    def do_OPTIONS(self):
        # 修复 B7: 收紧 CORS
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        elif config.API_TOKEN:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # 修复 B7: 鉴权检查
        if not self._check_auth():
            return self._send_auth_required()

        # GET /health (无需鉴权之外的特殊处理)
        if path == "/health":
            with _task_lock:
                self._send_json({
                    "status": "ok",
                    "busy": _current_task_id is not None,
                    "current_task": _current_task_id,
                    "queue_size": _task_queue.qsize(),
                    "tasks_tracked": len(_task_results),
                })
            return

        # GET /status/<id>
        if path.startswith("/status/"):
            # 修复: 精确分割，忽略查询参数
            tail = path[len("/status/"):]
            task_id = tail.split("/")[0].split("?")[0]
            with _task_lock:
                info = _task_results.get(task_id)
            if info is None:
                self._send_json({"error": "task not found"}, 404)
            else:
                self._send_json({"id": task_id, **info})
            return

        # GET /tasks
        if path == "/tasks":
            with _task_lock:
                self._send_json({
                    "tasks": [
                        {"id": tid, **{k: v for k, v in info.items() if k != "task"}}
                        for tid, info in _task_results.items()
                    ],
                    "count": len(_task_results),
                })
            return

        # GET /stream/<id>  (SSE)
        if path.startswith("/stream/"):
            tail = path[len("/stream/"):]
            task_id = tail.split("/")[0].split("?")[0]
            self._stream_task(task_id)
            return

        # GET /
        if path == "/":
            self._send_json({
                "service": "computer-use-agent",
                "version": "0.2.0",
                "endpoints": {
                    "GET  /health": "服务状态",
                    "POST /run": "提交任务 {\"task\": \"...\"}",
                    "GET  /status/<id>": "查询任务状态",
                    "GET  /stream/<id>": "Server-Sent Events 实时进度",
                    "GET  /tasks": "列出所有任务",
                    "POST /stop": "停止当前任务",
                },
                "auth": "API_TOKEN" if config.API_TOKEN else "none (localhost only)",
            })
            return

        self._send_json({"error": "not found"}, 404)

    def _stream_task(self, task_id: str):
        """Server-Sent Events 实时任务进度。"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_payload = None
        try:
            while True:
                with _task_lock:
                    info = _task_results.get(task_id)
                if info is None:
                    self.wfile.write(b"event: error\ndata: {\"error\": \"task not found\"}\n\n")
                    self.wfile.flush()
                    return
                payload = json.dumps({"id": task_id, **info}, ensure_ascii=False)
                if payload != last_payload:
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_payload = payload
                if info.get("finished_at"):
                    return
                time.sleep(0.5)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # 修复 B7: 鉴权检查
        if not self._check_auth():
            return self._send_auth_required()

        # POST /run
        if path == "/run":
            data = self._read_json()
            if not data or "task" not in data:
                self._send_json({"error": "missing 'task' field"}, 400)
                return
            task_text = data["task"]
            # 修复: 校验非空字符串
            if not isinstance(task_text, str) or not task_text.strip():
                self._send_json({"error": "'task' must be a non-empty string"}, 400)
                return
            # 修复: 队列上限
            if (
                config.API_MAX_QUEUE > 0
                and _task_queue.qsize() >= config.API_MAX_QUEUE
            ):
                self._send_json(
                    {"error": "queue full", "limit": config.API_MAX_QUEUE},
                    429,
                )
                return
            task_id = _submit_task(task_text)
            self._send_json({"id": task_id, "status": "accepted"}, 202)
            return

        # POST /stop (停止当前正在运行的任务)
        if path == "/stop":
            _stop_current()
            self._send_json({"status": "stopped"})
            return

        # POST /cancel/<id> (修复 F2.5: 取消指定任务 — 包括 queued)
        if path.startswith("/cancel/"):
            tail = path[len("/cancel/"):]
            task_id = tail.split("/")[0].split("?")[0]
            if not task_id:
                self._send_json({"error": "missing task id"}, 400)
                return
            with _task_lock:
                info = _task_results.get(task_id)
            if info is None:
                self._send_json({"error": "task not found"}, 404)
                return
            # 标记为已取消
            with _task_lock:
                if task_id == _current_task_id:
                    # 当前正在跑的任务，需要 interrupt
                    _stop_current()
                    self._send_json({"id": task_id, "status": "cancelled"})
                elif info.get("status") == "queued":
                    # 队列中的任务，标记 cancelled（worker 启动时跳过）
                    info["status"] = "cancelled"
                    info["error"] = "Cancelled by user"
                    info["finished_at"] = time.time()
                    self._send_json({"id": task_id, "status": "cancelled"})
                else:
                    self._send_json(
                        {"id": task_id, "status": info.get("status"), "note": "task already finished"},
                    )
            return

        self._send_json({"error": "not found"}, 404)


# ── 启动入口 ──

def serve(host: str = None, port: int = None):
    """启动 HTTP API 服务器（阻塞调用）。"""
    global _running

    host = host or getattr(config, "API_HOST", None) or "127.0.0.1"
    port = port or getattr(config, "API_PORT", None) or 2024

    # 修复 B7: 公网绑定时强制要求 API_TOKEN
    if not _is_local_host(host) and not config.API_TOKEN:
        raise RuntimeError(
            f"Refusing to bind to non-localhost host '{host}' without API_TOKEN. "
            "Set API_TOKEN env var to enable remote access."
        )

    _running = True

    # 启动 worker 线程
    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()

    server = HTTPServer((host, port), _APIHandler)
    logger.info(f"  API server: http://{host}:{port}")
    logger.info(f"  Endpoints: /health  /run  /status/<id>  /stream/<id>  /tasks  /stop")
    if config.API_TOKEN:
        logger.info("  Auth: Bearer token required (API_TOKEN is set)")
    else:
        logger.info("  Auth: none (localhost only)")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        _task_queue.put((None, None))  # 停止 worker
        _running = False
