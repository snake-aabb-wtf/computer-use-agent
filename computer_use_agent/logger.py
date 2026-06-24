"""日志模块 - 借鉴 Hermes logger 架构

- 结构化日志 + 彩色输出
- 工具完成消息带 emoji
- 秘密自动脱敏
- 修复 F6: 支持 text / json 两种格式
- 修复 S3: 使用 RotatingFileHandler (10MB × 5)
"""

import json
import re
import logging
import logging.handlers
import sys
import os
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
# 修复 S2: 扩展脱敏规则覆盖更多厂商与格式
# ═══════════════════════════════════════════════════════════

_SECRET_PATTERNS = [
    # OpenAI 标准 key
    re.compile(r'sk-[A-Za-z0-9]{20,}'),
    # OpenAI 新格式 (sk-proj-, sk-ant-, sk-svcacct- 等)
    re.compile(r'sk-(?:proj|ant|svcacct)-[A-Za-z0-9_\-]{20,}'),
    # Anthropic
    re.compile(r'sk-ant-[A-Za-z0-9_\-]{32,}'),
    # Google AI / Gemini
    re.compile(r'AIza[0-9A-Za-z_\-]{35}'),
    # GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)
    re.compile(r'gh[pousr]_[A-Za-z0-9]{36,}'),
    # Bearer 头 (Authorization: Bearer xxx)
    re.compile(r'(?i)(authorization:\s*bearer\s+)([A-Za-z0-9\-._~+/]+=*)'),
    # AWS Access Key
    re.compile(r'AKIA[0-9A-Z]{16}'),
    # 通用密码 / 密钥字段
    re.compile(r'(?i)(password["\s:=]+)([^\s,;"\']+)'),
    re.compile(r'(?i)(api[_-]?key["\s:=]+)([^\s,;"\']+)'),
    re.compile(r'(?i)(secret["\s:=]+)([^\s,;"\']+)'),
    re.compile(r'(?i)(token["\s:=]+)([^\s,;"\']+)'),
    # 私钥块
    re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----'),
]


def _redact_secrets(text: str) -> str:
    """脱敏敏感信息。修复 S2: 保留 key 前缀以便于调试。"""
    def _partial(m: re.Match) -> str:
        s = m.group(0)
        if len(s) <= 8:
            return "***"
        return s[:4] + "***" + s[-4:]

    def _kv_partial(m: re.Match) -> str:
        prefix = m.group(1)
        return prefix + "***"

    for i, pattern in enumerate(_SECRET_PATTERNS):
        if i in (5, 7, 8, 9, 10):
            text = pattern.sub(_kv_partial, text)
        elif i == 6:
            text = pattern.sub(lambda m: m.group(1) + "***", text)
        else:
            text = pattern.sub(_partial, text)
    return text


# ═══════════════════════════════════════════════════════════
# Logger setup
# ═══════════════════════════════════════════════════════════

def setup_logger(name: str = "agent") -> logging.Logger:
    """创建并配置 logger。

    修复 F6.1: 支持 LOG_FORMAT=json 输出结构化日志
    修复 F6.2: 使用 RotatingFileHandler (10MB × 5)
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    # 控制台输出（彩色 + 流式）
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(_ColorFormatter())
    logger.addHandler(console)

    # 文件输出
    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_format = getattr(config, "LOG_FORMAT", "text")
    log_file = log_dir / f"agent_{datetime.now():%Y%m%d_%H%M%S}.log"

    # 修复 F6.2: RotatingFileHandler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,                # 保留 5 个备份
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)

    if log_format == "json":
        # 修复 F6.1: JSON 结构化日志
        file_handler.setFormatter(_JsonFormatter())
    else:
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


class _JsonFormatter(logging.Formatter):
    """修复 F6.1: JSON 结构化日志格式化器。

    输出格式:
    {
      "ts": "2026-06-24T10:30:45.123Z",
      "level": "INFO",
      "module": "agent",
      "message": "...",
      "redacted": true
    }
    """
    # 标准字段（不放到 extra 中）
    _STD_FIELDS = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime",
    })

    def format(self, record: logging.LogRecord) -> str:
        from datetime import timezone
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        # 基础字段
        obj = {
            "ts": ts,
            "level": record.levelname,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        # extra 字段
        for key, val in record.__dict__.items():
            if key not in self._STD_FIELDS and not key.startswith("_"):
                obj[key] = val
        # 脱敏
        text = json.dumps(obj, ensure_ascii=False, default=str)
        return _redact_secrets(text)


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

    logger.info(
        f"  {emoji} {verb:10} {result}  {elapsed:.1f}s ({tokens_in}→{tokens_out}tok)",
        extra={"step": step, "action": act, "elapsed": elapsed,
               "tokens_in": tokens_in, "tokens_out": tokens_out},
    )

    if reason:
        logger.info(f"     {reason}")


def log_action_json(logger: logging.Logger, step: int, action: dict):
    """将完整动作 JSON 写入 debug 日志。"""
    clean = {k: v for k, v in action.items() if not k.startswith("_")}
    logger.debug(f"  JSON: {json.dumps(clean, ensure_ascii=False)}",
                 extra={"step": step, "action_data": clean})
