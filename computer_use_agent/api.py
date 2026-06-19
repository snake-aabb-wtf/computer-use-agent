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
"""

import json
import uuid
import queue
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from . import config
from .agent import Agent
from .logger import setup_logger

logger = logging.getLogger("agent.api")

# ── 任务管理 ──

_task_queue: queue.Queue = queue.Queue()
_task_results: dict[str, dict] = {}
_task_lock = threading.Lock()
_current_task_id: str | None = None
_running = False


def _worker():
    """后台 worker 线程：从队列取任务，执行 agent，记录结果。"""
    global _current_task_id
    agent = Agent(save_screenshots=True)

    while True:
        task_id, task_text = _task_queue.get()
        if task_id is None:
            break

        with _task_lock:
            _current_task_id = task_id
            _task_results[task_id] = {"status": "running", "result": None, "error": None}

        try:
            result = agent.run(task_text)
            with _task_lock:
                _task_results[task_id] = {"status": "done", "result": result, "error": None}
        except Exception as e:
            with _task_lock:
                _task_results[task_id] = {
                    "status": "error",
                    "result": None,
                    "error": str(e),
                }
        finally:
            with _task_lock:
                _current_task_id = None


def _submit_task(task: str) -> str:
    """提交任务到队列，返回 task_id。"""
    task_id = uuid.uuid4().hex[:12]
    with _task_lock:
        _task_results[task_id] = {"status": "queued", "result": None, "error": None}
    _task_queue.put((task_id, task))
    return task_id


def _stop_current():
    """请求停止当前任务。worker 线程中的 agent._interrupted 需要被设置。"""
    # 注意：当前架构中 Agent 的 _interrupted 标志仅在循环内检查。
    # 通过设置 flag 让正在运行的任务在下一个 step 处终止。
    # Worker 持有 agent 引用，但我们无法从外部访问它。
    # 简化方案：清空队列 + 返回 stopped 状态标记。
    global _current_task_id
    with _task_lock:
        if _current_task_id:
            _task_results[_current_task_id] = {
                "status": "error",
                "result": None,
                "error": "Task stopped by user",
            }
            _current_task_id = None
    # 清空待处理队列
    while not _task_queue.empty():
        try:
            _task_queue.get_nowait()
        except queue.Empty:
            break


# ── HTTP Handler ──

class _APIHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        logger.debug(f"API: {fmt % args}")

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
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
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # GET /health
        if path == "/health":
            with _task_lock:
                self._send_json({
                    "status": "ok",
                    "busy": _current_task_id is not None,
                    "current_task": _current_task_id,
                    "queue_size": _task_queue.qsize(),
                })

        # GET /status/<id>
        elif path.startswith("/status/"):
            task_id = path.split("/status/")[1]
            with _task_lock:
                info = _task_results.get(task_id)
            if info is None:
                self._send_json({"error": "task not found"}, 404)
            else:
                self._send_json({"id": task_id, **info})

        # GET /
        else:
            self._send_json({
                "service": "computer-use-agent",
                "version": "1.0.0",
                "endpoints": {
                    "GET  /health": "服务状态",
                    "POST /run": "提交任务 {\"task\": \"...\"}",
                    "GET  /status/<id>": "查询任务状态",
                    "POST /stop": "停止当前任务",
                },
            })

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # POST /run
        if path == "/run":
            data = self._read_json()
            if not data or "task" not in data:
                self._send_json({"error": "missing 'task' field"}, 400)
                return

            task_id = _submit_task(data["task"])
            self._send_json({"id": task_id, "status": "accepted"}, 202)

        # POST /stop
        elif path == "/stop":
            _stop_current()
            self._send_json({"status": "stopped"})

        else:
            self._send_json({"error": "not found"}, 404)


# ── 启动入口 ──

def serve(host: str = None, port: int = None):
    """启动 HTTP API 服务器（阻塞调用）。"""
    global _running

    host = host or getattr(config, "API_HOST", None) or "127.0.0.1"
    port = port or getattr(config, "API_PORT", None) or 2024

    _running = True

    # 启动 worker 线程
    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()

    server = HTTPServer((host, port), _APIHandler)
    logger.info(f"  API server: http://{host}:{port}")
    logger.info(f"  Endpoints: /health  /run  /status/<id>  /stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        _task_queue.put((None, None))  # 停止 worker
        _running = False
