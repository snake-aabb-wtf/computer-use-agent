"""日志模块 - 结构化日志，记录每步操作"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from . import config


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
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(file_handler)

    return logger


class _ColorFormatter(logging.Formatter):
    """彩色控制台格式化器。"""

    COLORS = {
        logging.DEBUG: "\033[36m",    # cyan
        logging.INFO: "\033[32m",     # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",    # red
        logging.CRITICAL: "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        level = record.levelname.ljust(7)
        msg = record.getMessage()
        return f"{color}{level}{self.RESET} | {msg}"


def log_action(logger: logging.Logger, step: int, action: dict, result: str):
    """记录一个动作的执行结果。"""
    reason = action.get("reason", "")
    thought = action.get("thought", "")
    act = action.get("action", "?")
    elapsed = action.get("_elapsed", 0)
    tokens_in = action.get("_tokens_in", 0)
    tokens_out = action.get("_tokens_out", 0)

    logger.info(
        f"STEP {step:03d} | {act} | {result} | "
        f"LLM {elapsed}s ({tokens_in}→{tokens_out} tokens)"
    )
    if reason:
        logger.info(f"  💡 {reason}")
    if thought:
        logger.debug(f"  🧠 {thought}")


def log_action_json(logger: logging.Logger, step: int, action: dict):
    """将完整动作 JSON 写入 debug 日志。"""
    # 去掉内部元数据避免日志冗余
    clean = {k: v for k, v in action.items() if not k.startswith("_")}
    logger.debug(f"  📋 ACTION JSON: {json.dumps(clean, ensure_ascii=False)}")
