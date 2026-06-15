"""日志模块 - 借鉴 Hermes logger 架构

- 结构化日志 + 彩色输出
- 工具完成消息带 emoji
- 秘密自动脱敏
"""

import json
import re
import logging
import sys
from datetime import datetime
from pathlib import Path
from . import config


# ═══════════════════════════════════════════════════════════
# 借鉴 Hermes: 工具 emoji 映射
# ═══════════════════════════════════════════════════════════

_TOOL_EMOJIS = {
    "left_click": "👆",
    "double_click": "👆👆",
    "right_click": "🖱️",
    "type": "⌨️",
    "key": "⌨️",
    "hotkey": "⌨️",
    "scroll": "📜",
    "move": "🖱️",
    "drag": "↔️",
    "wait": "⏳",
    "screenshot": "📸",
    "done": "✅",
}

_TOOL_VERBS = {
    "left_click": "click",
    "double_click": "double-click",
    "right_click": "right-click",
    "type": "type",
    "key": "press",
    "hotkey": "hotkey",
    "scroll": "scroll",
    "move": "move",
    "drag": "drag",
    "wait": "wait",
    "screenshot": "capture",
    "done": "done",
}


# ═══════════════════════════════════════════════════════════
# 借鉴 Hermes: 秘密脱敏 (redact.py)
# ═══════════════════════════════════════════════════════════

_SECRET_PATTERNS = [
    re.compile(r'sk-[A-Za-z0-9]{20,}'),           # OpenAI API keys
    re.compile(r'ghp_[A-Za-z0-9]{36}'),            # GitHub tokens
    re.compile(r'Bearer [A-Za-z0-9\-._~+/]+=*', re.IGNORECASE),  # Bearer tokens
    re.compile(r'password["\s:=]+\S+', re.IGNORECASE),  # Passwords
    re.compile(r'api_key["\s:=]+\S+', re.IGNORECASE),   # API keys
]


def _redact_secrets(text: str) -> str:
    """脱敏敏感信息。"""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: m.group()[:6] + "***", text)
    return text


# ═══════════════════════════════════════════════════════════
# Logger setup
# ═══════════════════════════════════════════════════════════

def setup_logger(name: str = "agent") -> logging.Logger:
    """创建并配置 logger。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(_ColorFormatter())
    logger.addHandler(console)

    # 文件输出
    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"agent_{datetime.now():%Y%m%d_%H%M%S}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_RedactingFormatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(file_handler)

    return logger


class _ColorFormatter(logging.Formatter):
    """彩色控制台格式化器。"""
    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        level = record.levelname.ljust(7)
        msg = record.getMessage()
        return f"{color}{level}{self.RESET} | {msg}"


class _RedactingFormatter(logging.Formatter):
    """日志文件脱敏格式化器（借鉴 Hermes RedactingFormatter）。"""
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return _redact_secrets(original)


# ═══════════════════════════════════════════════════════════
# 工具完成消息 (借鉴 Hermes get_cute_tool_message)
# ═══════════════════════════════════════════════════════════

def log_action(logger: logging.Logger, step: int, action: dict, result: str):
    """记录一个动作的执行结果。带 emoji + 耗时。"""
    reason = action.get("reason", "")
    act = action.get("action", "?")
    elapsed = action.get("_elapsed", 0)
    tokens_in = action.get("_tokens_in", 0)
    tokens_out = action.get("_tokens_out", 0)

    emoji = _TOOL_EMOJIS.get(act, "🔧")
    verb = _TOOL_VERBS.get(act, act)

    # 借鉴 Hermes: ┊ emoji verb result elapsed
    logger.info(
        f"  {emoji} {verb:10} {result}  {elapsed:.1f}s ({tokens_in}→{tokens_out}tok)"
    )

    if reason:
        logger.info(f"     {reason}")


def log_action_json(logger: logging.Logger, step: int, action: dict):
    """将完整动作 JSON 写入 debug 日志。"""
    clean = {k: v for k, v in action.items() if not k.startswith("_")}
    logger.debug(f"  JSON: {json.dumps(clean, ensure_ascii=False)}")
