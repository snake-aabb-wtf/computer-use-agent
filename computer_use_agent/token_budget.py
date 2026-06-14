"""Token 预算管理 - 借鉴 Hermes tool_result_storage.py + context_compressor.py

3 层上下文溢出防御:
Layer 1: 单条消息大小限制
Layer 2: 历史条目持久化（截断+预览）
Layer 3: 总 token 预算控制
"""

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger("agent.budget")


# ── 借鉴: tools/budget_config.py - 冻结配置 ──

@dataclass(frozen=True)
class BudgetConfig:
    """预算配置（冻结，运行时不可变）。"""
    max_message_chars: int = 5000      # Layer 1: 单条消息最大字符数
    max_history_chars: int = 200000    # Layer 3: 历史总字符预算
    image_token_estimate: int = 1500   # 每张图片的 token 估算
    chars_per_token: float = 3.5       # 字符/token 比率估算
    compression_threshold: float = 0.5 # 超过上下文窗口 50% 时压缩
    max_history_messages: int = 40     # 最多保留的消息数


DEFAULT_CONFIG = BudgetConfig()


# ── Layer 1: 单条消息截断 ──

def truncate_message(msg: dict, max_chars: int = None) -> dict:
    """截断单条消息内容到安全长度。

    借鉴 Hermes tool_result_storage.py 的 per-tool output cap。
    """
    max_chars = max_chars or DEFAULT_CONFIG.max_message_chars
    content = msg.get("content", "")

    if isinstance(content, str) and len(content) > max_chars:
        truncated = content[:max_chars]
        # 在最后一个换行处截断，避免截断单词
        last_newline = truncated.rfind('\n')
        if last_newline > max_chars * 0.8:
            truncated = truncated[:last_newline]

        msg = dict(msg)  # 不修改原始消息
        msg["content"] = truncated + f"\n... [truncated, {len(content)} chars total]"
        logger.debug(f"Truncated message: {len(content)} -> {len(truncated)} chars")

    elif isinstance(content, list):
        # 多模态消息：截断文本部分
        new_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
                if len(text) > max_chars:
                    part = dict(part)
                    part["text"] = text[:max_chars] + "... [truncated]"
            new_parts.append(part)
        msg = dict(msg)
        msg["content"] = new_parts

    return msg


# ── Layer 2: 历史条目管理 ──

def compact_history_entry(msg: dict) -> dict:
    """压缩单条历史条目，保留关键信息。

    借鉴 Hermes 的 persisted-output 模式：
    - 保留前 N 个字符作为预览
    - 标记为已压缩
    """
    content = msg.get("content", "")

    if isinstance(content, str) and len(content) > DEFAULT_CONFIG.max_message_chars:
        preview_len = 500
        preview = content[:preview_len]
        last_nl = preview.rfind('\n')
        if last_nl > preview_len * 0.7:
            preview = preview[:last_nl]

        msg = dict(msg)
        msg["content"] = (
            f"{preview}\n"
            f"... [compacted, full length: {len(content)} chars]"
        )
        msg["_compacted"] = True

    return msg


# ── Layer 3: 总预算控制 ──

def estimate_tokens(text: str) -> int:
    """估算文本的 token 数。

    借鉴 Hermes model_metadata.py 的估算公式:
    - 文本: 字符数 / chars_per_token
    - 图片: 固定 1500 tokens
    """
    if not text:
        return 0
    return int(len(text) / DEFAULT_CONFIG.chars_per_token)


def estimate_message_tokens(msg: dict) -> int:
    """估算单条消息的 token 数。"""
    content = msg.get("content", "")

    if isinstance(content, str):
        return estimate_tokens(content)
    elif isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    total += estimate_tokens(part.get("text", ""))
                elif part.get("type") == "image_url":
                    total += DEFAULT_CONFIG.image_token_estimate
        return total
    return 0


def estimate_history_tokens(history: list[dict]) -> int:
    """估算整个历史的 token 数。"""
    return sum(estimate_message_tokens(m) for m in history)


def enforce_history_budget(history: list[dict], config: BudgetConfig = None) -> list[dict]:
    """强制执行历史预算限制。

    借鉴 Hermes enforce_turn_budget:
    1. 检查总字符数是否超预算
    2. 按大小排序，压缩最大的条目
    3. 如果仍然超预算，删除最旧的条目
    """
    config = config or DEFAULT_CONFIG

    # 快速检查：消息数限制
    if len(history) > config.max_history_messages:
        # 保留前 2 条（通常是任务描述）+ 最近的 N 条
        keep_recent = config.max_history_messages - 2
        history = history[:2] + history[-keep_recent:]
        logger.debug(f"Cropped history to {len(history)} messages")

    # 检查总字符数
    total_chars = sum(
        len(str(m.get("content", ""))) for m in history
    )

    if total_chars <= config.max_history_chars:
        return history

    logger.warning(
        f"History budget exceeded: {total_chars} > {config.max_history_chars} chars"
    )

    # 按内容大小排序，压缩最大的条目（跳过前 2 条）
    indexed = list(enumerate(history))
    to_compress = indexed[2:]  # 不动前 2 条
    to_compress.sort(key=lambda x: len(str(x[1].get("content", ""))), reverse=True)

    for idx, msg in to_compress:
        if total_chars <= config.max_history_chars:
            break
        old_len = len(str(msg.get("content", "")))
        history[idx] = compact_history_entry(msg)
        new_len = len(str(history[idx].get("content", "")))
        total_chars -= (old_len - new_len)

    # 如果还超，删除最旧的
    while total_chars > config.max_history_chars and len(history) > 4:
        removed = history.pop(2)  # 保留前 2 条
        total_chars -= len(str(removed.get("content", "")))
        logger.debug("Removed old message to fit budget")

    return history


# ── 预检：API 调用前检查 ──

def should_compress(history: list[dict], context_window: int = 128000) -> bool:
    """检查是否需要在 API 调用前压缩历史。

    借鉴 Hermes context_compressor.should_compress:
    - 估算当前 token 数
    - 如果超过 context_window 的 compression_threshold，返回 True
    """
    tokens = estimate_history_tokens(history)
    threshold = int(context_window * DEFAULT_CONFIG.compression_threshold)
    if tokens > threshold:
        logger.info(
            f"Preflight: {tokens} tokens > {threshold} threshold, should compress"
        )
        return True
    return False
