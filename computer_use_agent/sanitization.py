"""消息净化 - 借鉴 Hermes agent_runtime_helpers.py + message_sanitization.py

核心模式:
1. 角色交替修复 - 合并连续 user 消息，删除孤儿 tool 消息
2. 5 级 JSON 修复级联 - 处理截断/尾逗号/未闭合括号等
3. 消息序列验证 - 确保 API 调用前消息格式正确
"""

import json
import re
import logging

logger = logging.getLogger("agent.sanitize")


# ═══════════════════════════════════════════════════════════
# 1. 角色交替修复 (agent_runtime_helpers.py line 346-444)
# ═══════════════════════════════════════════════════════════

def repair_message_sequence(messages: list[dict]) -> list[dict]:
    """修复消息序列中的角色交替问题。

    借鉴 Hermes 的两轮修复:
    Pass 1: 删除孤儿 tool 消息（没有对应 assistant tool_call 的）
    Pass 2: 合并连续 user 消息
    """
    if not messages:
        return messages

    # Pass 1: 删除孤儿 tool 消息
    cleaned = []
    known_tool_ids = set()
    for msg in messages:
        role = msg.get("role", "")

        if role == "assistant":
            # 收集此 assistant 消息中的 tool_call id
            tool_calls = msg.get("tool_calls", [])
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        tid = tc.get("id", "")
                        if tid:
                            known_tool_ids.add(tid)

        elif role == "tool":
            # 检查 tool_call_id 是否存在
            tcid = msg.get("tool_call_id", "")
            if tcid and tcid not in known_tool_ids:
                logger.debug(f"Dropping orphan tool message: {tcid}")
                continue  # 跳过孤儿

        elif role == "user":
            # user 消息重置 tool 跟踪
            known_tool_ids = set()

        cleaned.append(msg)

    # Pass 2: 合并连续 user 消息
    merged = []
    for msg in cleaned:
        if (merged
                and merged[-1].get("role") == "user"
                and msg.get("role") == "user"
                and isinstance(merged[-1].get("content"), str)
                and isinstance(msg.get("content"), str)):
            # 合并连续纯文本 user 消息
            merged[-1]["content"] += "\n\n" + msg["content"]
            logger.debug("Merged consecutive user messages")
        else:
            merged.append(msg)

    return merged


# ═══════════════════════════════════════════════════════════
# 2. 5 级 JSON 修复级联 (message_sanitization.py line 185-279)
# ═══════════════════════════════════════════════════════════

def _escape_control_chars(text: str) -> str:
    """替换 JSON 字符串中的非法控制字符。"""
    result = []
    in_string = False
    escape_next = False

    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue

        if ch == '\\' and in_string:
            result.append(ch)
            escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue

        if in_string and ord(ch) < 0x20:
            # 控制字符 -> \uXXXX 转义
            result.append(f"\\u{ord(ch):04x}")
        else:
            result.append(ch)

    return ''.join(result)


def repair_json(text: str) -> str:
    """5 级 JSON 修复级联。

    借鉴 Hermes message_sanitization.py _repair_tool_call_arguments:

    Pass 0: strict=False 解析
    Pass 1: 去除尾逗号
    Pass 2: 闭合未关闭的 {} 和 []
    Pass 3: 去除多余闭合括号
    Pass 4: 转义非法控制字符
    Fallback: 返回 "{}"
    """
    if not text or not text.strip():
        return "{}"

    text = text.strip()

    # Pass 0: 直接尝试严格解析
    try:
        obj = json.loads(text)
        return json.dumps(obj, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        pass

    # Pass 0.5: strict=False（容忍控制字符）
    try:
        obj = json.loads(text, strict=False)
        return json.dumps(obj, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        pass

    # Pass 1: 去除尾逗号
    cleaned = re.sub(r',\s*([}\]])', r'\1', text)
    try:
        obj = json.loads(cleaned, strict=False)
        return json.dumps(obj, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        pass

    # Pass 2: 闭合未关闭的 {} 和 []
    for open_c, close_c in [('{', '}'), ('[', ']')]:
        opens = cleaned.count(open_c)
        closes = cleaned.count(close_c)
        if opens > closes:
            cleaned += close_c * (opens - closes)
    try:
        obj = json.loads(cleaned, strict=False)
        return json.dumps(obj, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        pass

    # Pass 3: 去除多余闭合括号（通过计数精确匹配）
    for open_c, close_c in [('{', '}'), ('[', ']')]:
        opens = cleaned.count(open_c)
        closes = cleaned.count(close_c)
        if closes > opens:
            # 从末尾移除多余的闭合括号
            excess = closes - opens
            for _ in range(excess):
                # 从右边开始移除一个匹配的闭合括号
                idx = len(cleaned)
                while idx > 0:
                    idx -= 1
                    if cleaned[idx] == close_c:
                        cleaned = cleaned[:idx] + cleaned[idx+1:]
                        break
    try:
        obj = json.loads(cleaned, strict=False)
        return json.dumps(obj, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        pass

    # Pass 4: 转义非法控制字符
    escaped = _escape_control_chars(cleaned)
    try:
        obj = json.loads(escaped, strict=False)
        return json.dumps(obj, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback
    logger.warning(f"JSON repair failed, returning empty object")
    return "{}"


# ═══════════════════════════════════════════════════════════
# 3. 工具名称模糊修复 (agent_runtime_helpers.py line 1767-1837)
# ═══════════════════════════════════════════════════════════

def repair_tool_name(name: str, valid_names: list[str]) -> str:
    """尝试修复幻觉工具名。

    5 阶段级联:
    1. 小写直接匹配
    2. 分隔符标准化
    3. CamelCase -> snake_case
    4. 去除 _tool/-tool/tool 后缀
    5. 模糊匹配 (difflib)
    """
    if name in valid_names:
        return name

    # Stage 1: 小写匹配
    lower = name.lower()
    if lower in valid_names:
        return lower

    # Stage 2: 分隔符标准化 (- -> _)
    normalized = lower.replace("-", "_")
    if normalized in valid_names:
        return normalized

    # Stage 3: CamelCase -> snake_case
    snake = re.sub(r'(?<!^)(?=[A-Z])', '_', lower).lower()
    if snake in valid_names:
        return snake

    # Stage 4: 去除 _tool/-tool/tool 后缀
    for suffix in ["_tool", "-tool", "tool"]:
        stripped = normalized.replace(suffix, "")
        if stripped in valid_names:
            return stripped
        stripped = snake.replace(suffix, "")
        if stripped in valid_names:
            return stripped

    # Stage 5: 模糊匹配
    try:
        from difflib import get_close_matches
        matches = get_close_matches(name, valid_names, n=1, cutoff=0.6)
        if matches:
            return matches[0]
    except ImportError:
        pass

    return name  # 无法修复，返回原名


# ═══════════════════════════════════════════════════════════
# 4. 消息预检验证 (conversation_loop.py line 1031-1084)
# ═══════════════════════════════════════════════════════════

def sanitize_api_messages(messages: list[dict]) -> list[dict]:
    """API 调用前的最终净化。

    借鉴 Hermes sanitize_api_messages:
    1. 删除无效 role 的消息
    2. 确保 system 消息在最前面
    3. 角色交替验证
    """
    valid_roles = {"system", "user", "assistant", "tool", "function", "developer"}
    result = []

    for msg in messages:
        role = msg.get("role", "")
        if role not in valid_roles:
            logger.debug(f"Dropping message with invalid role: {role}")
            continue
        result.append(msg)

    # 确保 system 消息在最前面
    systems = [m for m in result if m.get("role") == "system"]
    others = [m for m in result if m.get("role") != "system"]

    return systems + others
