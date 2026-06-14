"""Agent 核心循环 - 深度借鉴 Hermes agent 工程"""

import time
import signal
import sys
import threading

from . import config
from .screen import capture, capture_and_save, capture_som
from .llm import chat
from .executor import execute, set_som_elements
from .prompts import get_system_prompt, build_system_prompt
from .screen import get_screen_size
from .logger import setup_logger, log_action, log_action_json
from .sanitization import repair_message_sequence, sanitize_api_messages
from .token_budget import (
    enforce_history_budget, should_compress, estimate_history_tokens,
)
from .guardrails import ToolCallGuardrails, GuardrailDecision


# ── 借鉴: 上下文压缩 (context_compressor.py) ──

MAX_HISTORY_TURNS = 20


def _compress_history(history: list[dict]) -> list[dict]:
    """压缩历史：将旧轮次合并为摘要，保留最近 N 轮。"""
    if len(history) <= MAX_HISTORY_TURNS * 2:
        return history

    keep_recent = MAX_HISTORY_TURNS * 2
    old = history[:-keep_recent]
    recent = history[-keep_recent:]

    summary_parts = []
    for msg in old:
        if msg["role"] == "user":
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > 100:
                summary_parts.append(f"User: {content[:100]}...")
            elif isinstance(content, str):
                summary_parts.append(f"User: {content}")
        elif msg["role"] == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str):
                if '"action"' in content:
                    summary_parts.append(f"Agent: [acted] {content[:80]}...")
                else:
                    summary_parts.append(f"Agent: {content[:80]}...")

    summary = " | ".join(summary_parts[-10:])

    compressed = [
        {"role": "user", "content": f"[历史摘要] 之前的操作: {summary}"},
        {"role": "assistant", "content": '{"thought":"已了解历史上下文","action":"screenshot"}'},
    ]
    compressed.extend(recent)
    return compressed


# ── 借鉴: 成本追踪 (conversation_loop.py line 1879-1991) ──

class SessionStats:
    """会话级统计。"""

    def __init__(self):
        self.total_steps = 0
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.total_llm_time = 0.0
        self.total_actions = 0
        self.errors = 0

    def update(self, action: dict):
        self.total_tokens_in += action.get("_tokens_in", 0)
        self.total_tokens_out += action.get("_tokens_out", 0)
        self.total_llm_time += action.get("_elapsed", 0)
        self.total_steps += 1
        if action.get("_error"):
            self.errors += 1
        act = action.get("action", "")
        if act not in ("screenshot", "wait", "done"):
            self.total_actions += 1

    def summary(self) -> str:
        return (
            f"Steps: {self.total_steps} | "
            f"Actions: {self.total_actions} | "
            f"Tokens: {self.total_tokens_in}→{self.total_tokens_out} | "
            f"LLM time: {self.total_llm_time:.1f}s | "
            f"Errors: {self.errors}"
        )


# ── 借鉴 UI-TARS: 图片滑动窗口 ──

def _slide_image_window(history: list[dict], max_images: int = 5) -> list[dict]:
    """借鉴 UI-TARS 的图片滑动窗口。

    只保留最近 N 张截图，防止上下文溢出。
    """
    image_indices = []
    for i, msg in enumerate(history):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        image_indices.append(i)
                        break

    if len(image_indices) > max_images:
        to_remove = set(image_indices[:len(image_indices) - max_images])
        history = [msg for i, msg in enumerate(history) if i not in to_remove]

    return history


# ── Agent 主类 ──

class Agent:
    """桌面操作 Agent。"""

    def __init__(self, save_screenshots: bool = True):
        self.logger = setup_logger()
        self.save_screenshots = save_screenshots
        self.history: list[dict] = []
        self.stats = SessionStats()
        self._interrupted = False
        self._consecutive_errors = 0

        # 借鉴: 系统提示词三层架构
        try:
            w, h = get_screen_size()
        except Exception:
            w, h = 0, 0
        self.system_prompt = build_system_prompt(w, h, config.LLM_MODEL, config.CAPTURE_MODE)

        # 借鉴: 工具循环护栏 (tool_guardrails.py)
        self.guardrails = ToolCallGuardrails()

        # 借鉴: 活动心跳 (run_agent.py _touch_activity)
        self._last_activity = time.time()
        self._activity_lock = threading.Lock()

        # 借鉴: 线程级中断 (run_agent.py interrupt)
        if sys.platform != "win32":
            signal.signal(signal.SIGINT, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame):
        self._interrupted = True
        self.logger.warning("\n  ⚠ Interrupt requested, finishing current step...")

    def _touch_activity(self, desc: str = ""):
        """借鉴: 活动心跳 (run_agent.py _touch_activity)。"""
        with self._activity_lock:
            self._last_activity = time.time()

    def _is_stale(self, timeout: float = 300) -> bool:
        """检查是否超时。"""
        with self._activity_lock:
            return (time.time() - self._last_activity) > timeout

    def _stop_effects(self):
        """停止视觉效果。"""
        try:
            from .visual_effects import stop_border, cleanup
            stop_border()
            cleanup()
        except Exception:
            pass

    def _prepare_messages(self) -> list[dict]:
        """API 调用前的消息准备流水线。

        借鉴:
        - Hermes: 消息序列修复、预算强制执行、最终净化
        - UI-TARS: 图片滑动窗口 (仅 uitars 模式)
        """
        # 1. 修复消息序列
        self.history = repair_message_sequence(self.history)

        # 2. 借鉴 UI-TARS: 图片滑动窗口 (仅 uitars 模式)
        if config.CAPTURE_MODE == "uitars":
            self.history = _slide_image_window(self.history, max_images=5)

        # 3. 强制执行预算
        self.history = enforce_history_budget(self.history)

        # 4. 最终净化
        messages = sanitize_api_messages(self.history)

        return messages

    def run(self, task: str) -> str:
        """执行一个任务。"""
        self.logger.info(f"🚀 Task: {task}")
        self.logger.info(f"   Model: {config.LLM_MODEL} | Max steps: {config.MAX_STEPS}")
        self._touch_activity("task_start")

        self.history.append({"role": "user", "content": task})

        # 启动视觉效果（如果启用）
        if config.VISUAL_EFFECTS:
            try:
                from .visual_effects import init_effects
                init_effects(True)
            except Exception:
                pass

        for step in range(1, config.MAX_STEPS + 1):
            # 借鉴: 中断检查点 (200ms 间隔)
            if self._interrupted:
                self.logger.warning("⏹ Interrupted by user")
                if config.VISUAL_EFFECTS:
                    self._stop_effects()
                return "已中断"

            self.logger.info(f"\n{'─'*50}")
            self.logger.info(f"📸 Step {step}/{config.MAX_STEPS}")

            # 1. 截图
            self._touch_activity("screenshot")
            if config.CAPTURE_MODE == "som":
                # SOM 模式：UIA 元素树 + 编号覆盖层
                img_b64, elements, elements_text = capture_som()
                set_som_elements(elements)
                if self.save_screenshots:
                    from pathlib import Path
                    save_dir = Path(config.SCREENSHOT_DIR)
                    save_dir.mkdir(parents=True, exist_ok=True)
                    from PIL import ImageGrab
                    img = ImageGrab.grab()
                    img.save(save_dir / f"step_{step:04d}.png")
                    self.logger.info(f"   SOM: {len(elements)} elements found")
            else:
                # Vision 模式：纯截图
                if self.save_screenshots:
                    img_b64, path = capture_and_save(step)
                    self.logger.info(f"   Saved: {path}")
                else:
                    img_b64 = capture()

            # 2. 预检上下文压缩
            if should_compress(self.history):
                self.logger.info("  🗜 Compressing history (preflight)...")
                self.history = _compress_history(self.history)
                self.history = enforce_history_budget(self.history)

            # 3. 消息准备流水线
            prepared = self._prepare_messages()

            # 4. 发送给 LLM
            self._touch_activity("llm_call")
            self.logger.info(f"🧠 → {config.LLM_MODEL}...")
            action = chat(
                img_b64, prepared, self.system_prompt,
                logger=self.logger,
                stream=False,
            )

            log_action_json(self.logger, step, action)
            self.stats.update(action)

            # 5. 错误计数与恢复
            if action.get("_error"):
                self._consecutive_errors += 1
                if self._consecutive_errors >= 5:
                    self.logger.error("  ❌ 5 consecutive errors, aborting")
                    return "Too many consecutive errors"
                self.history.append({
                    "role": "assistant",
                    "content": action.get("_raw", ""),
                })
                self.history.append({
                    "role": "user",
                    "content": "The previous action failed. Please try a different approach or wait.",
                })
                time.sleep(2)
                continue
            else:
                self._consecutive_errors = 0

            # 6. 判断完成
            act = action.get("action", "")
            if act == "done":
                msg = action.get("message", "Task completed")
                self.logger.info(f"\n✅ {msg}")
                self.logger.info(f"   {self.stats.summary()}")
                if config.VISUAL_EFFECTS:
                    self._stop_effects()
                return msg

            # 7. 执行动作
            self._touch_activity(f"execute_{act}")
            result = execute(action)
            log_action(self.logger, step, action, result)

            # 8. 借鉴: 工具循环护栏 (tool_guardrails.py)
            action_failed = "❌" in result
            guardrail = self.guardrails.check(action, result, failed=action_failed)
            if guardrail.action == "block":
                self.logger.warning(f"  🛡 {guardrail.message}")
                self.history.append({
                    "role": "assistant",
                    "content": action.get("_raw", str(action)),
                })
                self.history.append({
                    "role": "user",
                    "content": f"[System] {guardrail.message}",
                })
                continue
            elif guardrail.action == "halt":
                self.logger.error(f"  🛡 {guardrail.message}")
                return f"Guardrail halt: {guardrail.message}"
            elif guardrail.action == "warn":
                self.logger.warning(f"  🛡 {guardrail.message}")
                self.history.append({
                    "role": "user",
                    "content": f"[System] {guardrail.message}",
                })
            else:
                # 成功，更新护栏状态
                self.guardrails.on_success(action)

            # 9. 动作后截图验证 + 失败检测
            follow_up_screenshot = ""
            if act not in ("screenshot", "wait", "done") and not action_failed:
                try:
                    follow_up_b64 = capture()
                    follow_up_screenshot = " 操作后的屏幕已更新。"
                except Exception:
                    pass

            # 10. 更新历史
            self.history.append({
                "role": "assistant",
                "content": action.get("_raw", str(action)),
            })

            if action_failed:
                self.history.append({
                    "role": "user",
                    "content": f"Action failed: {result}. The screen has NOT changed. Please try a different action.",
                })
            else:
                self.history.append({
                    "role": "user",
                    "content": f"Action executed: {result}{follow_up_screenshot}",
                })

            # 11. 中断友好的延迟 (200ms 检查)
            self._touch_activity("delay")
            if act not in ("wait", "screenshot"):
                delay = config.ACTION_DELAY
                elapsed = 0
                while elapsed < delay:
                    if self._interrupted:
                        break
                    time.sleep(min(0.2, delay - elapsed))
                    elapsed += 0.2

        self.logger.warning(f"⚠ Max steps {config.MAX_STEPS} reached")
        self.logger.info(f"   {self.stats.summary()}")
        if config.VISUAL_EFFECTS:
            self._stop_effects()
        return f"Max steps {config.MAX_STEPS} reached"
