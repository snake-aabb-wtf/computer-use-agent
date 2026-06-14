"""LLM 客户端 - 借鉴 Hermes 的重试/退避/空响应恢复/流式输出"""

import json
import time
import random
import threading
from openai import OpenAI, APIError, RateLimitError, APITimeoutError, APIConnectionError
from . import config


_client: OpenAI | None = None


def get_client() -> OpenAI:
    """获取或创建 OpenAI 客户端（单例）。"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
            timeout=config.REQUEST_TIMEOUT,
        )
    return _client


# ── 借鉴: conversation_loop.py jittered backoff (retry_utils.py line 19-56) ──

def _jittered_backoff(retry: int, base: float = 2.0, cap: float = 60.0) -> float:
    """指数退避 + 随机抖动，防止雪崩。"""
    delay = min(cap, base * (2 ** retry))
    jitter = random.uniform(0, delay * 0.5)
    return delay + jitter


# ── 借鉴: error_classifier.py 错误分类 ──

def _classify_error(error: Exception) -> dict:
    """分类 API 错误，决定重试策略。"""
    if isinstance(error, RateLimitError):
        return {"retryable": True, "reason": "rate_limit", "backoff": True}
    elif isinstance(error, APITimeoutError):
        return {"retryable": True, "reason": "timeout", "backoff": True}
    elif isinstance(error, APIConnectionError):
        return {"retryable": True, "reason": "connection", "backoff": True}
    elif isinstance(error, APIError):
        status = getattr(error, "status_code", 0)
        if status == 429:
            return {"retryable": True, "reason": "rate_limit", "backoff": True}
        elif status in (500, 502, 503, 504):
            return {"retryable": True, "reason": "server_error", "backoff": True}
        elif status == 401:
            return {"retryable": False, "reason": "auth"}
        elif status == 402:
            return {"retryable": False, "reason": "billing"}
        elif status == 400:
            return {"retryable": False, "reason": "bad_request"}
        return {"retryable": True, "reason": f"http_{status}", "backoff": True}
    return {"retryable": True, "reason": "unknown", "backoff": True}


# ── 借鉴: conversation_loop.py 空响应恢复 (line 4064-4332) ──

def _recover_empty_response(raw: str, retry_count: int, history: list) -> str:
    """空响应多阶段恢复。"""
    # Stage 1: 检查 reasoning_content 是否有内容（推理模型）
    if not raw and retry_count == 0:
        return ""  # 上层已处理

    # Stage 2: 重试时注入提示
    if retry_count == 1:
        return "__nudge__"

    # Stage 3: 返回 wait 让用户看到状态
    return ""


# ── 流式输出支持 ──

class StreamPrinter:
    """实时打印 LLM 流式输出。"""

    def __init__(self, logger):
        self.logger = logger
        self.buffer = ""
        self.printed = False

    def on_delta(self, delta: str):
        """收到一个 delta 时调用。"""
        if delta:
            self.buffer += delta
            if not self.printed:
                self.logger.info(f"  💭 ", end="")
                self.printed = True
            print(delta, end="", flush=True)

    def finish(self):
        """流结束时调用。"""
        if self.printed:
            print()  # 换行


def chat(
    screenshot_b64: str,
    history: list[dict],
    system_prompt: str,
    logger=None,
    max_retries: int = 3,
    stream: bool = False,
) -> dict:
    """发送截图和历史给 LLM，返回解析后的动作 JSON。

    借鉴 Hermes:
    - 重试 + 指数退避 (conversation_loop.py line 1164-3497)
    - 空响应恢复 (line 4064-4332)
    - 流式输出支持
    """
    client = get_client()

    # 构建消息
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{screenshot_b64}",
                    "detail": "high",
                },
            },
            {
                "type": "text",
                "text": "这是当前屏幕截图。分析屏幕内容，决定下一步操作。直接返回 JSON，不要加任何额外文本。",
            },
        ],
    })

    last_error = None
    for retry in range(max_retries + 1):
        try:
            t0 = time.time()

            # 流式 vs 非流式
            if stream:
                response = _chat_streaming(client, messages, logger)
            else:
                response = client.chat.completions.create(
                    model=config.LLM_MODEL,
                    messages=messages,
                    max_tokens=config.LLM_MAX_TOKENS,
                    temperature=config.LLM_TEMPERATURE,
                )

            elapsed = time.time() - t0
            message = response.choices[0].message

            # 提取内容（兼容推理模型）
            raw = message.content
            if not raw and hasattr(message, "reasoning_content") and message.reasoning_content:
                raw = message.reasoning_content
            if not raw:
                raw = ""
            raw = raw.strip()

            tokens_in = response.usage.prompt_tokens if response.usage else 0
            tokens_out = response.usage.completion_tokens if response.usage else 0
            finish_reason = response.choices[0].finish_reason

            # 借鉴: 空响应恢复
            if not raw:
                if retry < max_retries:
                    nudge = _recover_empty_response(raw, retry + 1, history)
                    if nudge == "__nudge__":
                        # 注入提示让模型重试
                        history.append({
                            "role": "assistant",
                            "content": "",
                        })
                        history.append({
                            "role": "user",
                            "content": "请返回一个 JSON 动作。",
                        })
                        if logger:
                            logger.warning(f"  ⚠ Empty response, retrying ({retry+1}/{max_retries})")
                        continue
                    # Stage 3: 返回 wait
                    return _parse_action("", elapsed, tokens_in, tokens_out)

            # finish_reason 检查
            if finish_reason == "length" and not raw:
                if logger:
                    logger.warning(f"  ⚠ Response truncated (length), retrying")
                continue

            return _parse_action(raw, elapsed, tokens_in, tokens_out)

        except Exception as e:
            last_error = e
            classified = _classify_error(e)

            if not classified["retryable"]:
                if logger:
                    logger.error(f"  ❌ Fatal error: {classified['reason']}: {e}")
                return {
                    "thought": f"API 错误: {e}",
                    "action": "wait",
                    "seconds": 5,
                    "_error": True,
                }

            if retry < max_retries:
                wait = _jittered_backoff(retry) if classified.get("backoff") else 1.0
                if logger:
                    logger.warning(
                        f"  ⚠ {classified['reason']}: {e} "
                        f"(retry {retry+1}/{max_retries}, wait {wait:.1f}s)"
                    )
                time.sleep(wait)
            else:
                if logger:
                    logger.error(f"  ❌ Max retries exceeded: {e}")

    # 所有重试失败
    return {
        "thought": f"API 调用失败 ({max_retries} 次重试): {last_error}",
        "action": "done",
        "message": f"API 错误，无法继续: {last_error}",
        "_error": True,
    }


def _chat_streaming(client: OpenAI, messages: list, logger=None):
    """流式 API 调用。"""
    stream = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        max_tokens=config.LLM_MAX_TOKENS,
        temperature=config.LLM_TEMPERATURE,
        stream=True,
    )

    collected_content = []
    collected_reasoning = []
    prompt_tokens = 0
    completion_tokens = 0

    for chunk in stream:
        if not chunk.choices:
            # usage 信息可能在最后一个 chunk
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0
            continue

        delta = chunk.choices[0].delta
        finish = chunk.choices[0].finish_reason

        if delta and delta.content:
            collected_content.append(delta.content)
            if logger:
                print(delta.content, end="", flush=True)

        if delta and hasattr(delta, "reasoning_content") and delta.reasoning_content:
            collected_reasoning.append(delta.reasoning_content)

        if finish:
            break

    # 拼装成兼容 response 的对象
    content = "".join(collected_content)
    reasoning = "".join(collected_reasoning) if collected_reasoning else None

    class _Msg:
        pass
    class _Choice:
        pass
    class _Usage:
        pass
    class _Resp:
        pass

    msg = _Msg()
    msg.content = content
    msg.reasoning_content = reasoning
    msg.role = "assistant"

    choice = _Choice()
    choice.message = msg
    choice.finish_reason = finish or "stop"

    usage = _Usage()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    resp = _Resp()
    resp.choices = [choice]
    resp.usage = usage

    if logger and collected_content:
        print()  # 换行

    return resp


def _parse_action(
    raw: str, elapsed: float, tokens_in: int, tokens_out: int
) -> dict:
    """解析 LLM 返回的 JSON 动作。

    借鉴 Hermes message_sanitization.py 的 5 级 JSON 修复级联。
    """
    from .sanitization import repair_json

    text = raw
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # 尝试提取 JSON 部分
    start = text.find("{")
    end = text.rfind("}") + 1
    json_text = text[start:end] if start != -1 and end > start else text

    # 借鉴: 5 级 JSON 修复级联
    repaired = repair_json(json_text)
    try:
        action = json.loads(repaired)
    except json.JSONDecodeError:
        action = {}

    # 修复后如果缺少 action 字段，补上 wait
    if "action" not in action:
        action = {
            "thought": f"JSON missing action field: {raw[:200]}",
            "action": "wait",
            "seconds": 1,
        }

    action["_elapsed"] = round(elapsed, 2)
    action["_tokens_in"] = tokens_in
    action["_tokens_out"] = tokens_out
    action["_raw"] = raw
    return action
