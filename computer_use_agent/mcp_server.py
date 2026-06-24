"""MCP (Model Context Protocol) Server - 修复 F3

通过 stdio transport 暴露 CUA 能力给外部 MCP 客户端
(Claude Desktop / Cursor / Zed / Continue 等)。

启动:
    cua --mcp

提供工具:
    - cua.run_task       提交一个任务
    - cua.stop_task      停止当前任务
    - cua.get_status     查询任务状态
    - cua.screenshot     抓取当前屏幕
    - cua.list_monitors  列出显示器

实现说明:
    - 遵循 MCP 协议 (2024-11-05)
    - 使用 stdio transport (JSON-RPC 2.0 over stdin/stdout)
    - 零外部依赖（与 HTTP API 一样的设计哲学）
"""

import sys
import json
import uuid
import queue
import threading
import logging
import time
import base64
from typing import Any, Optional

from . import config
from .agent import Agent
from .logger import setup_logger

logger = logging.getLogger("agent.mcp")

# ── 任务管理（独立于 HTTP API，避免冲突） ──

_task_queue: queue.Queue = queue.Queue()
_task_results: dict[str, dict] = {}
_task_lock = threading.Lock()
_current_task_id: Optional[str] = None
_active_agent: Optional[Agent] = None
_active_agent_lock = threading.Lock()


def _submit_task(task: str) -> str:
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


def _worker():
    """后台 worker 线程：从队列取任务执行。"""
    global _current_task_id, _active_agent

    agent = Agent(save_screenshots=False)
    with _active_agent_lock:
        _active_agent = agent

    while True:
        task_id, task_text = _task_queue.get()
        if task_id is None:
            break
        # 跳过已取消的任务
        with _task_lock:
            if _task_results.get(task_id, {}).get("status") == "cancelled":
                continue
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


def _stop_current():
    """中断当前任务。"""
    with _active_agent_lock:
        agent = _active_agent
    if agent is not None:
        agent.interrupt(reason="MCP stop_task")
    with _task_lock:
        if _current_task_id:
            existing = _task_results.get(_current_task_id, {})
            existing["status"] = "cancelled"
            existing["error"] = "Stopped by user"
            existing["finished_at"] = time.time()


# ── MCP 工具实现 ──

def _tool_run_task(args: dict) -> dict:
    """工具: cua.run_task - 提交一个任务并立即返回 task_id。"""
    task = args.get("task", "")
    if not isinstance(task, str) or not task.strip():
        return {"error": "'task' must be a non-empty string"}
    task_id = _submit_task(task.strip())
    return {"task_id": task_id, "status": "accepted"}


def _tool_stop_task(args: dict) -> dict:
    """工具: cua.stop_task - 停止当前正在运行的任务。"""
    _stop_current()
    return {"status": "stopped"}


def _tool_get_status(args: dict) -> dict:
    """工具: cua.get_status - 查询任务状态。"""
    task_id = args.get("task_id", "")
    if not task_id:
        return {"error": "missing 'task_id'"}
    with _task_lock:
        info = _task_results.get(task_id)
    if info is None:
        return {"error": "task not found"}
    return {"task_id": task_id, **info}


def _tool_screenshot(args: dict) -> dict:
    """工具: cua.screenshot - 抓取当前屏幕。"""
    from .screen import _grab_image
    try:
        img = _grab_image()
        from io import BytesIO
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return {
            "format": "png",
            "width": img.size[0],
            "height": img.size[1],
            "data": b64,
        }
    except Exception as e:
        return {"error": f"screenshot failed: {e}"}


def _tool_list_monitors(args: dict) -> dict:
    """工具: cua.list_monitors - 列出所有显示器。"""
    try:
        from .screen import list_monitors
        monitors = list_monitors()
        return {"monitors": monitors, "count": len(monitors)}
    except Exception as e:
        return {"error": str(e)}


# ── MCP 协议核心（JSON-RPC 2.0 over stdio） ──

# 工具定义表
TOOLS = [
    {
        "name": "cua.run_task",
        "description": "Submit a desktop automation task. Returns immediately with a task_id; use cua.get_status to poll.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Natural language task description (e.g. 'open notepad and type Hello World')"
                }
            },
            "required": ["task"],
        },
    },
    {
        "name": "cua.stop_task",
        "description": "Stop the currently running task.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cua.get_status",
        "description": "Get the status of a previously submitted task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID returned by run_task"}
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "cua.screenshot",
        "description": "Capture the current screen. Returns base64-encoded PNG.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cua.list_monitors",
        "description": "List all available monitors with their dimensions.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

# 工具分发表
TOOL_DISPATCH = {
    "cua.run_task": _tool_run_task,
    "cua.stop_task": _tool_stop_task,
    "cua.get_status": _tool_get_status,
    "cua.screenshot": _tool_screenshot,
    "cua.list_monitors": _tool_list_monitors,
}

SERVER_INFO = {
    "name": "computer-use-agent",
    "version": "0.2.0",
}

SERVER_CAPABILITIES = {
    "tools": {"listChanged": False},
}


def _make_response(req_id, result):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


def _make_error(req_id, code, message, data=None):
    err = {
        "code": code,
        "message": message,
    }
    if data is not None:
        err["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": err,
    }


def _handle_initialize(req_id, params):
    """处理 initialize 请求。"""
    return _make_response(req_id, {
        "protocolVersion": "2024-11-05",
        "serverInfo": SERVER_INFO,
        "capabilities": SERVER_CAPABILITIES,
    })


def _handle_list_tools(req_id, params):
    """处理 tools/list 请求。"""
    return _make_response(req_id, {"tools": TOOLS})


def _handle_call_tool(req_id, params):
    """处理 tools/call 请求。"""
    name = params.get("name", "")
    args = params.get("arguments", {}) or {}

    handler = TOOL_DISPATCH.get(name)
    if handler is None:
        return _make_error(req_id, -32601, f"Unknown tool: {name}")

    try:
        result = handler(args)
        # MCP 要求返回 content 列表
        return _make_response(req_id, {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
            "isError": "error" in result,
        })
    except Exception as e:
        return _make_response(req_id, {
            "content": [{"type": "text", "text": f"Tool error: {e}"}],
            "isError": True,
        })


def _dispatch_request(req: dict) -> Optional[dict]:
    """根据 method 分发请求到对应 handler。返回 None 表示是通知（不回复）。"""
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {}) or {}

    # 通知（没有 id）—— 不回复
    if req_id is None and method.startswith("notifications/"):
        logger.debug(f"Notification: {method}")
        return None

    if method == "initialize":
        return _handle_initialize(req_id, params)
    elif method == "tools/list":
        return _handle_list_tools(req_id, params)
    elif method == "tools/call":
        return _handle_call_tool(req_id, params)
    elif method == "ping":
        return _make_response(req_id, {})
    else:
        return _make_error(req_id, -32601, f"Method not found: {method}")


def run_mcp_server() -> int:
    """MCP Server 主入口（stdio transport）。"""
    setup_logger()
    logger.info("MCP Server starting (stdio transport)...")

    # 启动 worker 线程
    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()

    # 从 stdin 读 JSON-RPC 请求，向 stdout 写响应
    stdin = sys.stdin
    stdout = sys.stdout

    try:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                err = _make_error(None, -32700, f"Parse error: {e}")
                stdout.write(json.dumps(err) + "\n")
                stdout.flush()
                continue

            response = _dispatch_request(req)
            if response is not None:
                stdout.write(json.dumps(response) + "\n")
                stdout.flush()
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        _task_queue.put((None, None))  # 停止 worker
        logger.info("MCP Server stopped")
    return 0
