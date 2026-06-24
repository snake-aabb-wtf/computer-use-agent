"""Agent 核心循环 - 深度借鉴 Hermes agent 工程"""

import time
import sys
import threading

from . import config
from .screen import capture, capture_and_save, capture_som
from .llm import chat
from .executor import execute, set_som_elements
from .prompts import build_system_prompt
from .screen import get_screen_size
from .logger import setup_logger, log_action, log_action_json
from .sanitization import repair_message_sequence, sanitize_api_messages
from .token_budget import (
    enforce_history_budget, should_compress, estimate_history_tokens,
    DEFAULT_CONFIG as BUDGET_CONFIG,
)
from .guardrails import ToolCallGuardrails


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
    """会话级统计。修复 C7: 区分 api_calls 与 total_steps。"""

    def __init__(self):
        self.total_steps = 0
        self.api_calls = 0      # 实际 LLM API 调用次数（不含 wait/screenshot 之后重发）
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.total_llm_time = 0.0
        self.total_actions = 0
        self.errors = 0

    def update(self, action: dict):
        # 修复 C7: 只有 LLM 实际被调用（_tokens_in > 0 或 _elapsed > 0）时才计入 api_calls
        if action.get("_tokens_in", 0) > 0 or action.get("_elapsed", 0) > 0:
            self.api_calls += 1
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
            f"API calls: {self.api_calls} | "
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
        # 修复 B1: 用跨平台 threading.Event 替代 signal.signal
        self._interrupt_event = threading.Event()
        # 兼容保留 _interrupted 属性（同步 bool 镜像）
        self._interrupted = False
        self._consecutive_errors = 0

        # 借鉴: 系统提示词三层架构
        try:
            w, h = get_screen_size()
        except Exception:
            w, h = 0, 0
        self.system_prompt = build_system_prompt(w, h, config.LLM_MODEL, config.CAPTURE_MODE)

        # 修复 F1.3: 注入屏幕元信息到 system_prompt 末尾
        try:
            from .screen import get_screen_info
            info = get_screen_info()
            monitor_info = (
                f"\n\n[Screen Info]\n"
                f"- Active capture size: {info['screen_size'][0]}x{info['screen_size'][1]}\n"
                f"- Platform: {info['platform']}\n"
            )
            if len(info['all_monitors']) > 1:
                monitor_info += f"- Total monitors: {len(info['all_monitors'])}\n"
                for m in info['all_monitors']:
                    marker = " (primary)" if m.get('is_primary') else ""
                    monitor_info += f"  Monitor {m['index']}: {m['width']}x{m['height']} at ({m['left']},{m['top']}){marker}\n"
            self.system_prompt += monitor_info
        except Exception:
            pass

        # 借鉴: 工具循环护栏 (tool_guardrails.py)
        self.guardrails = ToolCallGuardrails()

        # 借鉴: 活动心跳 (run_agent.py _touch_activity)
        self._last_activity = time.time()
        self._activity_lock = threading.Lock()
        self._stale_warned = False

        # 借鉴: /steer 和 /queue 命令注入点 (修复 D1)
        self._pending_steer: list[str] = []
        self._pending_queue: list[str] = []

    def interrupt(self, reason: str = ""):
        """请求停止 Agent 任务（跨平台可调用）。
        修复 B1: 任何线程可调用此方法设置中断标志。
        """
        if not self._interrupt_event.is_set():
            self._interrupt_event.set()
            self._interrupted = True
            suffix = f" ({reason})" if reason else ""
            self.logger.warning(f"\n  ⚠ Interrupt requested{suffix}, finishing current step...")

    def is_interrupted(self) -> bool:
        return self._interrupt_event.is_set()

    def reset_interrupt(self):
        """清除中断标志（用于重置 Agent 跑下一个任务）。"""
        self._interrupt_event.clear()
        self._interrupted = False
        self._stale_warned = False

    def _touch_activity(self, desc: str = ""):
        """借鉴: 活动心跳 (run_agent.py _touch_activity)。"""
        with self._activity_lock:
            self._last_activity = time.time()
            self._stale_warned = False

    def _is_stale(self, timeout: float = 300) -> bool:
        """检查是否超时 (D2 修复: 真正接入主循环)。"""
        with self._activity_lock:
            return (time.time() - self._last_activity) > timeout

    def _check_stale(self) -> bool:
        """主循环中检查活动心跳；过期则注入反思 hint。
        返回 True 表示已提示（避免重复）。"""
        if self._is_stale(getattr(config, "STALE_TIMEOUT", 300)):
            if not self._stale_warned:
                self._stale_warned = True
                self.history.append({
                    "role": "user",
                    "content": (
                        "[System] No activity for a while. "
                        "If you are stuck, consider taking a screenshot, "
                        "reflecting on the current state, or finishing the task."
                    ),
                })
                self.logger.warning("  ⏳ Stale activity detected, injected reflection hint")
            return True
        return False

    def steer(self, message: str):
        """修复 D1: 注入中途指令，下次 _prepare_messages 时合并入历史。"""
        self._pending_steer.append(message)
        self.logger.info(f"  📨 Steer queued: {message[:60]}")

    def queue_task(self, task: str):
        """修复 D1: 排队下一个任务，主循环完成后自动执行。"""
        self._pending_queue.append(task)
        self.logger.info(f"  📋 Queued: {task[:60]}")

    def _consume_steer(self) -> list[str]:
        """取出并清空待注入指令。"""
        pending = list(self._pending_steer)
        self._pending_steer.clear()
        return pending

    def _consume_queue(self) -> list[str]:
        """取出并清空排队任务。"""
        pending = list(self._pending_queue)
        self._pending_queue.clear()
        return pending

    def _emit_webhook(self, event: str, result: str = None, error: str = None):
        """修复 F5.2: 触发 Webhook 通知（异步，不阻塞主流程）。"""
        try:
            from .webhook import notify
            duration = time.time() - getattr(self, "_task_start_time", time.time())
            stats_dict = {
                "total_steps": self.stats.total_steps,
                "api_calls": self.stats.api_calls,
                "total_tokens_in": self.stats.total_tokens_in,
                "total_tokens_out": self.stats.total_tokens_out,
                "errors": self.stats.errors,
            }
            notify(
                event=event,
                task=getattr(self, "_current_task", ""),
                task_id=getattr(self, "_current_task_id", ""),
                result=result,
                error=error,
                duration_seconds=duration,
                stats=stats_dict,
                async_send=True,
            )
        except Exception as e:
            # Webhook 失败不应影响主流程
            self.logger.debug(f"Webhook emit failed: {e}")

    @staticmethod
    def _cleanup_old_screenshots(keep: int = None):
        """修复 S3: 清理 SCREENSHOT_DIR 中多余的旧截图，保留最近 N 个。

        keep 为 None 时使用 config.SCREENSHOT_KEEP。
        """
        if keep is None:
            keep = getattr(config, "SCREENSHOT_KEEP", 50)
        if keep <= 0:
            return
        try:
            from pathlib import Path
            save_dir = Path(config.SCREENSHOT_DIR)
            if not save_dir.exists():
                return
            files = sorted(
                [p for p in save_dir.glob(f"step_*.{config.SCREENSHOT_FORMAT}")],
                key=lambda p: p.name,
            )
            if len(files) <= keep:
                return
            for p in files[: len(files) - keep]:
                try:
                    p.unlink()
                except OSError:
                    pass
        except Exception:
            pass

    def _stop_effects(self):
        """停止视觉效果。"""
        try:
            from .visual_effects import cleanup
            cleanup()
        except Exception:
            pass

    def _prepare_messages(self) -> list[dict]:
        """API 调用前的消息准备流水线。

        借鉴:
        - Hermes: 消息序列修复、预算强制执行、最终净化
        - UI-TARS: 图片滑动窗口 (仅 uitars 模式)

        修复:
        - D4: 接入 should_compress() 进行预检压缩评估
        - D1: 消费 _pending_steer 注入中途指令
        """
        # 0. 修复 D1: 消费待注入指令
        pending_steer = self._consume_steer()
        if pending_steer:
            for msg in pending_steer:
                self.history.append({"role": "user", "content": msg})
            self.logger.info(f"  📨 Injected {len(pending_steer)} steer message(s)")

        # 1. 修复消息序列
        self.history = repair_message_sequence(self.history)

        # 2. 借鉴 UI-TARS: 图片滑动窗口 (仅 uitars 模式)
        if config.CAPTURE_MODE == "uitars":
            self.history = _slide_image_window(self.history, max_images=5)

        # 3. 修复 D4: 预检压缩评估
        try:
            est_tokens = estimate_history_tokens(self.history)
            should_c, reason = should_compress(self.history)
            if should_c:
                self.logger.info(
                    f"  📉 Compression recommended ({reason}, ~{est_tokens} tokens)"
                )
        except Exception:
            pass  # 评估失败不阻断主流程

        # 4. 强制执行预算
        self.history = enforce_history_budget(self.history)

        # 5. 最终净化
        messages = sanitize_api_messages(self.history)

        return messages

    def run(self, task: str, stream: bool = False) -> str:
        """执行一个任务。

        修复 D3: 新增 stream 参数。
        stream=True 时让 LLM 调用走流式 API（_chat_streaming）。
        修复 F5: 在 done / error / interrupted / max-steps 路径触发 Webhook。
        """
        self.logger.info(f"🚀 Task: {task}")
        self.logger.info(f"   Model: {config.LLM_MODEL} | Max steps: {config.MAX_STEPS}")
        self._touch_activity("task_start")
        # 修复: 让外部可读取 stream 设置
        self._stream = stream
        # 修复 F5: 记录任务开始时间供 webhook 使用
        self._task_start_time = time.time()
        self._current_task = task
        self._current_task_id = f"agent-{int(self._task_start_time * 1000)}"

        self.history.append({"role": "user", "content": task})

        # 启动视觉效果（如果启用）
        if config.VISUAL_EFFECTS:
            try:
                from .visual_effects import init_effects
                init_effects(True)
            except Exception:
                pass

        for step in range(1, config.MAX_STEPS + 1):
            # 修复 B1: 跨平台中断检查（threading.Event）
            if self._interrupt_event.is_set():
                self.logger.warning("⏹ Interrupted by user")
                if config.VISUAL_EFFECTS:
                    self._stop_effects()
                # 修复 F5.2: 触发 interrupted webhook
                self._emit_webhook("interrupted", result="已中断")
                return "已中断"

            # 修复 D1: 主循环结束自动消费排队任务
            if step == 1:
                pass  # 第一次迭代前会在循环外处理

            # 修复 D9: 活动心跳检查 - 注入反思 hint（每 10 步检查一次）
            if step > 1 and step % 10 == 0:
                self._check_stale()

            self.logger.info(f"\n{'─'*50}")
            self.logger.info(f"📸 Step {step}/{config.MAX_STEPS}")

            # 借鉴: 定期重新注入当前任务，防止上下文漂移
            if step > 1 and step % 10 == 0:
                self.history.append({
                    "role": "user",
                    "content": f"[Task Reminder] Your current task is: \"{task}\". Do NOT deviate to other tasks. If the task is done, return done.",
                })

            # 1. 截图
            self._touch_activity("screenshot")
            if config.CAPTURE_MODE == "som":
                # SOM 模式：UIA 元素树 + 编号覆盖层
                # 修复 B4: capture_som 现在返回 (img_b64, elements, elements_text, som_image)
                # som_image 是已渲染的 PIL.Image，避免 agent 重复抓屏
                result = capture_som()
                if len(result) == 4:
                    img_b64, elements, elements_text, som_image = result
                else:
                    # 向后兼容旧版本
                    img_b64, elements, elements_text = result
                    som_image = None
                set_som_elements(elements)
                if self.save_screenshots and som_image is not None:
                    from pathlib import Path
                    save_dir = Path(config.SCREENSHOT_DIR)
                    save_dir.mkdir(parents=True, exist_ok=True)
                    filepath = save_dir / f"step_{step:04d}.png"
                    som_image.save(filepath)
                    self.logger.info(f"   SOM: {len(elements)} elements, saved: {filepath}")
                elif self.save_screenshots:
                    self.logger.info(f"   SOM: {len(elements)} elements found")
            else:
                # Vision 模式：纯截图
                if self.save_screenshots:
                    img_b64, path = capture_and_save(step)
                    self.logger.info(f"   Saved: {path}")
                else:
                    img_b64 = capture()

            # 2. 预检上下文压缩（已移除自动压缩，改为 /compact 手动触发）

            # 3. 消息准备流水线
            prepared = self._prepare_messages()

            # 4. 发送给 LLM
            self._touch_activity("llm_call")
            self.logger.info(f"🧠 → {config.LLM_MODEL}...")
            # 修复 C3: 用 spinner 包装 LLM 调用，让用户看到 "🤔 Thinking..."
            try:
                from rich.console import Console
                from rich.spinner import Spinner
                from rich.live import Live
                _console = Console()
                spinner = Spinner("dots", text=f"  🤔 Thinking... ({config.LLM_MODEL})")
                with Live(spinner, console=_console, transient=True, refresh_per_second=10):
                    action = chat(
                        img_b64, prepared, self.system_prompt,
                        logger=self.logger,
                        stream=getattr(self, "_stream", False),
                    )
            except ImportError:
                # rich 不可用时退化
                action = chat(
                    img_b64, prepared, self.system_prompt,
                    logger=self.logger,
                    stream=getattr(self, "_stream", False),
                )

            log_action_json(self.logger, step, action)
            self.stats.update(action)

            # 5. 错误计数与恢复
            if action.get("_error"):
                self._consecutive_errors += 1
                if self._consecutive_errors >= 5:
                    self.logger.error("  ❌ 5 consecutive errors, aborting")
                    # 修复 F5.2: 触发 error webhook
                    self._emit_webhook("error", error="Too many consecutive errors")
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
                # 修复 D1: done 后消费排队任务
                queued = self._consume_queue()
                if queued:
                    next_task = queued.pop(0)
                    self.logger.info(f"\n▶ Auto-running queued task: {next_task[:60]}")
                    return self.run(next_task)
                # 修复 F5.2: 触发 done webhook
                self._emit_webhook("done", result=msg)
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
                    if self._interrupt_event.is_set():
                        break
                    time.sleep(min(0.2, delay - elapsed))
                    elapsed += 0.2

        # 修复 D1: 消费排队任务（自动跑下一个）
        queued = self._consume_queue()
        if queued:
            next_task = queued.pop(0)
            self.logger.info(f"\n▶ Auto-running queued task: {next_task[:60]}")
            return self.run(next_task)

        self.logger.warning(f"⚠ Max steps {config.MAX_STEPS} reached")
        self.logger.info(f"   {self.stats.summary()}")
        if config.VISUAL_EFFECTS:
            self._stop_effects()
        # 修复 F5.2: 触发 error webhook（max steps 也算未完成）
        self._emit_webhook("error", error=f"Max steps {config.MAX_STEPS} reached")
        return f"Max steps {config.MAX_STEPS} reached"
