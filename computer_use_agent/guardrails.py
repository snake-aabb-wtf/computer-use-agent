"""工具循环护栏 - 借鉴 Hermes tool_guardrails.py

核心模式:
1. 精确失败检测 - 相同工具+相同参数+失败 = 追踪
2. 同工具失败累积 - 任何同一工具的失败都计数
3. 无进展检测 - 只读工具产生相同结果 = 卡住了
"""

import hashlib
import json
import time
import logging
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger("agent.guardrails")


@dataclass
class ToolCallSignature:
    """工具调用签名 - 工具名 + 参数哈希。"""
    tool_name: str
    args_hash: str

    @classmethod
    def from_action(cls, action: dict) -> "ToolCallSignature":
        act = action.get("action", "unknown")
        # 排除元数据字段后计算哈希
        clean = {k: v for k, v in action.items() if not k.startswith("_")}
        args_str = json.dumps(clean, sort_keys=True, ensure_ascii=False)
        args_hash = hashlib.sha256(args_str.encode()).hexdigest()[:16]
        return cls(tool_name=act, args_hash=args_hash)


@dataclass
class GuardrailDecision:
    """护栏决策。"""
    action: str  # "allow" | "warn" | "block" | "halt"
    message: str = ""


class ToolCallGuardrails:
    """借鉴 Hermes ToolCallGuardrailController。

    检测三种循环模式:
    1. 精确失败 - 相同签名失败
    2. 同工具失败 - 同一工具累积失败
    3. 无进展 - 只读操作产生相同结果
    """

    def __init__(
        self,
        exact_fail_warn: int = 3,
        exact_fail_block: int = 6,
        same_tool_warn: int = 4,
        same_tool_halt: int = 10,
        no_progress_block: int = 6,
    ):
        # 精确失败追踪 {signature: [timestamps]}
        self._exact_failures: dict[str, list[float]] = {}
        # 同工具失败计数 {tool_name: count}
        self._tool_failures: dict[str, int] = {}
        # 无进展追踪 {result_hash: count}
        self._no_progress: dict[str, int] = {}

        self.exact_fail_warn = exact_fail_warn
        self.exact_fail_block = exact_fail_block
        self.same_tool_warn = same_tool_warn
        self.same_tool_halt = same_tool_halt
        self.no_progress_block = no_progress_block

        # 最近结果哈希（滑动窗口）
        self._recent_results: deque = deque(maxlen=20)

    def check(self, action: dict, result: str, failed: bool = False) -> GuardrailDecision:
        """检查是否应该阻止/警告。"""
        sig = ToolCallSignature.from_action(action)
        sig_key = f"{sig.tool_name}:{sig.args_hash}"
        now = time.time()

        # 1. 精确失败检测
        if failed:
            if sig_key not in self._exact_failures:
                self._exact_failures[sig_key] = []
            self._exact_failures[sig_key].append(now)

            # 清理 5 分钟前的记录
            cutoff = now - 300
            self._exact_failures[sig_key] = [
                t for t in self._exact_failures[sig_key] if t > cutoff
            ]

            fail_count = len(self._exact_failures[sig_key])
            if fail_count >= self.exact_fail_block:
                msg = f"BLOCKED: Same action failed {fail_count} times ({sig.tool_name}). Try a completely different approach."
                logger.warning(msg)
                return GuardrailDecision("block", msg)
            elif fail_count >= self.exact_fail_warn:
                msg = f"WARNING: Same action failed {fail_count} times. Consider a different approach."
                logger.warning(msg)
                return GuardrailDecision("warn", msg)

        # 2. 同工具失败累积
        if failed:
            self._tool_failures[sig.tool_name] = self._tool_failures.get(sig.tool_name, 0) + 1
            count = self._tool_failures[sig.tool_name]
            if count >= self.same_tool_halt:
                msg = f"HALT: {sig.tool_name} has failed {count} times total. Stopping to reassess."
                logger.warning(msg)
                return GuardrailDecision("halt", msg)
            elif count >= self.same_tool_warn:
                msg = f"WARNING: {sig.tool_name} has failed {count} times. Try a different approach."
                return GuardrailDecision("warn", msg)

        # 3. 无进展检测（只读操作）
        if not failed and sig.tool_name in ("screenshot", "wait"):
            result_hash = hashlib.sha256(result.encode()).hexdigest()[:16]
            self._recent_results.append(result_hash)

            # 检查最近 N 次结果是否相同
            if len(self._recent_results) >= 5:
                recent = list(self._recent_results)[-5:]
                if len(set(recent)) == 1:
                    self._no_progress[result_hash] = self._no_progress.get(result_hash, 0) + 1
                    if self._no_progress[result_hash] >= self.no_progress_block:
                        msg = f"BLOCKED: No progress detected. The last 5 screenshots look identical. Try a different action."
                        logger.warning(msg)
                        return GuardrailDecision("block", msg)
                else:
                    # 有进展，重置计数
                    self._no_progress.clear()

        return GuardrailDecision("allow")

    def on_success(self, action: dict):
        """成功后重置该工具的失败计数。"""
        sig = ToolCallSignature.from_action(action)
        # 精确失败: 移除该签名的记录
        sig_key = f"{sig.tool_name}:{sig.args_hash}"
        self._exact_failures.pop(sig_key, None)
        # 同工具失败: 减半
        if sig.tool_name in self._tool_failures:
            self._tool_failures[sig.tool_name] = max(0, self._tool_failures[sig.tool_name] // 2)

    def reset(self):
        """重置所有计数。"""
        self._exact_failures.clear()
        self._tool_failures.clear()
        self._no_progress.clear()
        self._recent_results.clear()

    def summary(self) -> dict:
        """返回当前状态摘要。"""
        return {
            "exact_failures": len(self._exact_failures),
            "tool_failures": dict(self._tool_failures),
            "no_progress": dict(self._no_progress),
        }
