"""Webhook - 任务完成/错误/中断通知 (修复 F5)

通过 HTTP POST 发送任务事件到配置的 URL。
默认在 .env 中配置:
    WEBHOOK_URL=https://your-server/webhook
    WEBHOOK_EVENTS=done,error,interrupted

事件载荷:
    {
        "event": "done" | "error" | "interrupted",
        "task_id": "...",
        "task": "...",
        "result": "..." | null,
        "error": "..." | null,
        "timestamp": "...",
        "duration_seconds": 12.3,
        "stats": {
            "total_steps": 10,
            "total_tokens_in": 1234,
            "total_tokens_out": 567,
            "errors": 0,
        }
    }
"""

import json
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional

from . import config
from .logger import setup_logger

logger = setup_logger()


def _post_json(url: str, payload: dict, timeout: float = 5.0) -> bool:
    """POST JSON 到 URL。返回是否成功。"""
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except urllib.error.URLError as e:
        logger.warning(f"Webhook POST failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Webhook unexpected error: {e}")
        return False


def _enabled_events() -> set:
    """解析 WEBHOOK_EVENTS 配置为集合。"""
    raw = getattr(config, "WEBHOOK_EVENTS", "done,error,interrupted")
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def notify(event: str, task: str, task_id: str = "",
           result: Optional[str] = None, error: Optional[str] = None,
           duration_seconds: float = 0.0, stats: Optional[dict] = None,
           async_send: bool = True) -> bool:
    """发送 webhook 通知。

    Args:
        event: 事件名 (done | error | interrupted)
        task: 任务描述
        task_id: 任务 ID
        result: 任务结果（成功时）
        error: 错误信息（失败时）
        duration_seconds: 任务耗时
        stats: SessionStats 摘要
        async_send: 是否异步发送（默认 True，不阻塞主流程）

    Returns:
        True: 成功（或异步已排队），False: 未配置或失败
    """
    url = getattr(config, "WEBHOOK_URL", "")
    if not url:
        return False

    if event not in _enabled_events():
        return False

    payload = {
        "event": event,
        "task_id": task_id,
        "task": task,
        "result": result,
        "error": error,
        "duration_seconds": round(duration_seconds, 2),
        "timestamp": datetime.now().isoformat(),
        "stats": stats or {},
    }

    if async_send:
        # 异步发送，不阻塞主流程
        t = threading.Thread(
            target=_post_json,
            args=(url, payload),
            daemon=True,
        )
        t.start()
        return True
    else:
        return _post_json(url, payload)


def notify_done(task: str, task_id: str, result: str,
                duration: float, stats: dict) -> bool:
    """任务完成通知。"""
    return notify(
        event="done",
        task=task, task_id=task_id,
        result=result, duration_seconds=duration, stats=stats,
    )


def notify_error(task: str, task_id: str, error: str,
                 duration: float, stats: dict) -> bool:
    """任务失败通知。"""
    return notify(
        event="error",
        task=task, task_id=task_id,
        error=error, duration_seconds=duration, stats=stats,
    )


def notify_interrupted(task: str, task_id: str,
                       duration: float, stats: dict) -> bool:
    """任务中断通知。"""
    return notify(
        event="interrupted",
        task=task, task_id=task_id,
        duration_seconds=duration, stats=stats,
    )
