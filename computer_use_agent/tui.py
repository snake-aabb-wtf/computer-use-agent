"""TUI 实时状态面板 - 修复 C2

使用 rich.live.Live 提供实时状态展示：
- 顶部：当前 step、tokens、模型、本步耗时
- 中部：当前动作 + 坐标 + 思考
- 底部：累计状态

可由 --plain 禁用
"""

import time
from typing import Optional
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.layout import Layout
from rich.align import Align

from . import config


class StatusPanel:
    """实时状态面板（轻量级 rich.live.Live 包装）。"""

    def __init__(self, agent, console: Optional[Console] = None, plain: bool = False):
        self.agent = agent
        self.console = console or Console()
        self.plain = plain
        self._live: Optional[Live] = None
        self._step_start: float = 0.0
        self._last_action: dict = {}
        self._last_thought: str = ""

    def __enter__(self):
        if self.plain:
            return self
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        if self._live is not None:
            self._live.__exit__(*args)
            self._live = None

    def start_step(self):
        self._step_start = time.time()

    def update_action(self, action: dict):
        """更新当前显示的动作。"""
        self._last_action = action or {}
        self._last_thought = action.get("thought", "")
        if self._live is not None:
            self._live.update(self._render())

    def update_thought(self, text: str):
        """流式追加思考文本。"""
        if not text:
            return
        self._last_thought += text
        if self._live is not None:
            self._live.update(self._render())

    def stop(self):
        if self._live is not None:
            self._live.update(self._render())
            self._live.stop()
            self._live = None

    def _render(self) -> Panel:
        """渲染当前状态面板。"""
        stats = self.agent.stats
        elapsed = time.time() - self._step_start if self._step_start else 0.0

        # 状态行
        status_line = Text()
        status_line.append("  ", style="dim")
        status_line.append("Step ", style="bold")
        status_line.append(f"{stats.total_steps}/{config.MAX_STEPS}", style="cyan")
        status_line.append(" │ ", style="dim")
        status_line.append("Tokens ", style="bold")
        status_line.append(
            f"{stats.total_tokens_in}→{stats.total_tokens_out}", style="green"
        )
        status_line.append(" │ ", style="dim")
        status_line.append(f"Step {elapsed:.1f}s", style="yellow")
        if stats.errors:
            status_line.append(" │ ", style="dim")
            status_line.append(f"⚠ {stats.errors} err", style="red")
        status_line.append(" │ ", style="dim")
        status_line.append(config.LLM_MODEL[:20], style="magenta")

        # 当前动作
        action = self._last_action
        act_name = action.get("action", "—")
        coord = action.get("coordinate", "")
        coord_str = f" @ {coord}" if coord else ""

        action_line = Text()
        action_line.append("  ⚡ ", style="bold yellow")
        action_line.append(str(act_name), style="bold cyan")
        action_line.append(coord_str, style="dim")

        # 思考
        thought = self._last_thought or "—"
        if len(thought) > 200:
            thought = thought[:200] + "..."
        thought_line = Text()
        thought_line.append("  💭 ", style="bold")
        thought_line.append(thought, style="dim")

        content = Text()
        content.append(status_line)
        content.append("\n")
        content.append(action_line)
        content.append("\n")
        content.append(thought_line)

        return Panel(
            content,
            title="[bold gold3]⚙  CUA Status[/]",
            border_style="gold3",
            padding=(0, 1),
        )


def make_status_table(agent, width: int = 80) -> str:
    """兼容旧版 _print_usage 的简单文本状态（无 TUI 时使用）。"""
    stats = agent.stats
    lines = [
        f"Steps: {stats.total_steps}",
        f"Actions: {stats.total_actions}",
        f"Tokens: {stats.total_tokens_in}→{stats.total_tokens_out}",
        f"Errors: {stats.errors}",
    ]
    return " | ".join(lines)
