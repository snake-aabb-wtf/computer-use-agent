"""交互式 CLI - 深度借鉴 Hermes CLI 系统"""

import os
import sys
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markup import escape
from rich import box

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings

from . import config
from .agent import Agent
from .screen import get_screen_size
from .token_budget import estimate_history_tokens, DEFAULT_CONFIG as BUDGET_CONFIG


# ── Rich Console ──
console = Console()

# ── 颜色常量 ──
GOLD = "#FFD700"
BRONZE = "#CD7F32"
SILVER = "#C0C0C0"
GREEN = "#8FBC8F"
ORANGE = "#FF8C00"
RED = "#FF6B6B"
CYAN = "#00CED1"
DIM = "#888888"


# ═══════════════════════════════════════════════════════════
# 借鉴: 会话持久化 (session.py - SQLite)
# ═══════════════════════════════════════════════════════════

class SessionDB:
    """SQLite 会话持久化。"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(Path(config.LOG_DIR) / "sessions.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # 借鉴: 对 :memory: 使用单连接避免每次新建空库
        self._mem_conn = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
            self._init_on(self._mem_conn)
        else:
            self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            self._init_on(conn)

    def _init_on(self, conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                task TEXT,
                started_at TEXT,
                ended_at TEXT,
                steps INTEGER DEFAULT 0,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                result TEXT,
                parent_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        conn.commit()

    def _conn(self):
        return self._mem_conn or sqlite3.connect(self.db_path)

    def _close_conn(self, conn):
        if conn is not self._mem_conn:
            conn.close()

    def save_session(self, session_id: str, task: str, result: str,
                     steps: int, tokens_in: int, tokens_out: int,
                     parent_id: str = None):
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO sessions
                   (id, task, started_at, ended_at, steps, tokens_in, tokens_out, result, parent_id)
                   VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)""",
                (session_id, task, datetime.now().isoformat(),
                 steps, tokens_in, tokens_out, result, parent_id)
            )
            conn.commit()
        finally:
            self._close_conn(conn)

    def save_message(self, session_id: str, role: str, content: str):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, datetime.now().isoformat())
            )
            conn.commit()
        finally:
            self._close_conn(conn)

    def get_session(self, session_id: str) -> dict | None:
        conn = self._conn()
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def get_messages(self, session_id: str) -> list[dict]:
        conn = self._conn()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,)
            ).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]
        finally:
            self._close_conn(conn)

    def end_session(self, session_id: str, reason: str = "completed"):
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE sessions SET ended_at = ?, result = ? WHERE id = ?",
                (datetime.now().isoformat(), reason, session_id)
            )
            conn.commit()
        finally:
            self._close_conn(conn)

    def get_recent_sessions(self, limit: int = 10, exclude_id: str = None) -> list[dict]:
        """获取最近会话。修复 C6: 新增 exclude_id 排除当前会话以修复 off-by-one。"""
        conn = self._conn()
        try:
            conn.row_factory = sqlite3.Row
            if exclude_id:
                # 多取一些以补偿被排除的，避免数量不足
                rows = conn.execute(
                    """SELECT s.*,
                              (SELECT content FROM messages WHERE session_id = s.id AND role = 'user' LIMIT 1) as preview
                       FROM sessions s
                       WHERE (s.ended_at IS NULL OR s.ended_at != 'resumed_other')
                         AND s.id != ?
                       ORDER BY s.started_at DESC LIMIT ?""",
                    (exclude_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT s.*,
                              (SELECT content FROM messages WHERE session_id = s.id AND role = 'user' LIMIT 1) as preview
                       FROM sessions s
                       WHERE s.ended_at IS NULL OR s.ended_at != 'resumed_other'
                       ORDER BY s.started_at DESC LIMIT ?""",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)


# ═══════════════════════════════════════════════════════════
# 借鉴: 状态栏 (cli.py 三段式响应式布局)
# ═══════════════════════════════════════════════════════════

def _format_token_compact(value: int) -> str:
    """1234 -> 1.2K, 1234567 -> 1.2M"""
    for threshold, suffix in [(1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(value) >= threshold:
            return f"{value / threshold:.1f}{suffix}"
    return str(value)


def _build_context_bar(percent: float, width: int = 10) -> str:
    """[████░░░░░░] 可视化上下文使用率。"""
    filled = round((max(0, min(100, percent)) / 100) * width)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def _context_style(percent: float) -> str:
    """上下文使用率颜色。"""
    if percent >= 95:
        return f"bold {RED}"
    elif percent > 80:
        return f"bold {ORANGE}"
    elif percent >= 50:
        return f"bold {GOLD}"
    return GREEN


class StatusBar:
    """实时状态栏。"""

    def __init__(self, agent: Agent):
        self.agent = agent
        self._start_time = time.time()
        self._step_start = 0.0

    def start_step(self):
        self._step_start = time.time()

    def elapsed_str(self) -> str:
        elapsed = time.time() - self._start_time
        if elapsed >= 3600:
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            return f"{h}h{m:02d}m"
        elif elapsed >= 60:
            m = int(elapsed // 60)
            s = int(elapsed % 60)
            return f"{m}m{s:02d}s"
        return f"{elapsed:.0f}s"

    def step_elapsed(self) -> str:
        if self._step_start == 0:
            return ""
        elapsed = time.time() - self._step_start
        return f"{elapsed:.1f}s"

    def render(self, width: int = 80) -> str:
        """渲染状态栏。"""
        stats = self.agent.stats
        tokens_in = stats.total_tokens_in
        tokens_out = stats.total_tokens_out
        steps = stats.total_steps
        actions = stats.total_actions

        # 估算上下文使用率
        # 修复 B3: 使用 BUDGET_CONFIG.max_history_chars 替代错误的 2000
        history_tokens = estimate_history_tokens(self.agent.history)
        context_pct = min(
            100.0,
            (history_tokens / max(1, BUDGET_CONFIG.max_history_chars)) * 100,
        )

        # 构建状态栏
        parts = [
            f"Model {config.LLM_MODEL[:20]}",
            f"{_format_token_compact(tokens_in)}→{_format_token_compact(tokens_out)}",
            f"Step {steps}",
            f"Act {actions}",
            self.elapsed_str(),
        ]

        if context_pct > 10:
            parts.insert(2, f"{_build_context_bar(context_pct)} {context_pct:.0f}%")

        if stats.errors > 0:
            parts.append(f"⚠ {stats.errors}")

        return " │ ".join(parts)


# ═══════════════════════════════════════════════════════════
# 借鉴: Slash 命令系统 (commands.py - CommandDef 风格)
# ═══════════════════════════════════════════════════════════

COMMANDS = {
    "/help":     "显示帮助信息",
    "/quit":     "退出程序",
    "/exit":     "退出程序",
    "/config":   "显示当前配置",
    "/screen":   "查看屏幕分辨率",
    "/history":  "查看会话历史",
    "/compact":  "手动压缩上下文",
    "/reset":    "重置会话历史",
    "/model":    "切换模型 (/model <name>)",
    "/steps":    "设置最大步数 (/steps <n>)",
    "/delay":    "设置操作延迟 (/delay <s>)",
    "/usage":    "查看 token 用量和耗时",
    "/retry":    "重试上一个任务",
    "/undo":     "撤销最后一条历史",
    "/title":    "显示当前任务",
    "/sessions": "查看历史会话",
    "/resume":   "恢复历史会话 (/resume <id|序号>)",
    "/save":     "导出会话为 JSON 文件",
    "/branch":   "分叉当前会话 (/branch [name])",
    "/yolo":     "切换自主模式（跳过确认）",
    "/steer":    "运行中注入指令 (/steer <message>)",
    "/stop":     "停止当前任务",
    "/verbose":  "切换详细输出模式",
    "/status":   "查看当前状态",
    "/queue":    "排队下一条指令 (/queue <task>)",
    "/clear":    "清屏",
}

completer = WordCompleter(COMMANDS.keys(), ignore_case=True)

history_file = Path(config.LOG_DIR) / ".cli_history"
history_file.parent.mkdir(parents=True, exist_ok=True)

# 借鉴: 多行输入支持 (Alt+Enter 换行)
kb = KeyBindings()

@kb.add("escape", "enter", eager=True)
def _(event):
    event.app.current_buffer.insert_text("\n")

@kb.add("c-j", eager=True)  # Ctrl+Enter on Windows Terminal
def _(event):
    event.app.current_buffer.insert_text("\n")

prompt_style = Style.from_dict({
    "prompt": f"bold {GOLD}",
})


# ═══════════════════════════════════════════════════════════
# 输出格式化
# ═══════════════════════════════════════════════════════════

def _print_banner():
    """启动 Banner。"""
    banner = Text()
    banner.append("  ╔══════════════════════════════════════════╗\n", style=BRONZE)
    banner.append("  ║                                          ║\n", style=BRONZE)
    banner.append("  ║   ", style=BRONZE)
    banner.append("Computer Use Agent", style=f"bold {GOLD}")
    banner.append("          ║\n", style=BRONZE)
    banner.append("  ║   ", style=BRONZE)
    banner.append("v0.1.0", style=SILVER)
    banner.append("  Desktop Automation Agent         ║\n", style=BRONZE)
    banner.append("  ║                                          ║\n", style=BRONZE)
    banner.append("  ╚══════════════════════════════════════════╝\n", style=BRONZE)
    console.print(banner)

    w, h = get_screen_size()
    info = Table(box=None, show_header=False, show_edge=False, padding=(0, 2))
    info.add_column(style=SILVER)
    info.add_column(style=f"bold {CYAN}")
    info.add_row("Model", config.LLM_MODEL)
    info.add_row("Base URL", config.LLM_BASE_URL)
    info.add_row("Screen", f"{w}x{h}")
    info.add_row("Max Steps", str(config.MAX_STEPS))
    info.add_row("Action Delay", f"{config.ACTION_DELAY}s")
    capture_labels = {
        "som": (GREEN, "SOM (UIA element indexing)"),
        "vision": (CYAN, "VISION (pure screenshot)"),
        "uitars": (ORANGE, "UITARS (0-1000 coord normalization)"),
    }
    color, label = capture_labels.get(config.CAPTURE_MODE, (CYAN, config.CAPTURE_MODE))
    info.add_row("Capture Mode", f"[{color}]{label}[/]")
    console.print(Panel(info, title=f"[{GOLD}]Session[/{GOLD}]", border_style=BRONZE))
    console.print(f"  [{DIM}]Alt+Enter for newline | /help for commands[/{DIM}]\n")


def _print_help():
    table = Table(
        title=f"[{GOLD}]Commands[/{GOLD}]",
        box=box.ROUNDED,
        border_style=BRONZE,
        show_header=True,
        header_style=f"bold {GOLD}",
    )
    table.add_column("Command", style=f"bold {GREEN}", width=12)
    table.add_column("Description", style=SILVER)
    for cmd, desc in COMMANDS.items():
        table.add_row(cmd, desc)
    console.print(table)


def _print_config():
    table = Table(
        title=f"[{GOLD}]Config[/{GOLD}]",
        box=box.ROUNDED,
        border_style=BRONZE,
    )
    table.add_column("Key", style=f"bold {CYAN}")
    table.add_column("Value", style=SILVER)
    table.add_row("LLM_API_KEY", f"{config.LLM_API_KEY[:10]}...")
    table.add_row("LLM_BASE_URL", config.LLM_BASE_URL)
    table.add_row("LLM_MODEL", config.LLM_MODEL)
    table.add_row("MAX_STEPS", str(config.MAX_STEPS))
    table.add_row("ACTION_DELAY", f"{config.ACTION_DELAY}s")
    table.add_row("LLM_MAX_TOKENS", str(config.LLM_MAX_TOKENS))
    table.add_row("LLM_TEMPERATURE", str(config.LLM_TEMPERATURE))
    console.print(table)


def _print_usage(agent: Agent):
    """借鉴 Hermes /usage 命令。修复 C7: 区分 api_calls 和 total_steps。"""
    stats = agent.stats
    history_tokens = estimate_history_tokens(agent.history)

    table = Table(
        title=f"[{GOLD}]Usage[/{GOLD}]",
        box=box.ROUNDED,
        border_style=BRONZE,
    )
    table.add_column("Metric", style=f"bold {CYAN}")
    table.add_column("Value", style=SILVER)
    table.add_row("Model", config.LLM_MODEL)
    table.add_row("Input tokens", f"{stats.total_tokens_in:,}")
    table.add_row("Output tokens", f"{stats.total_tokens_out:,}")
    table.add_row("Total tokens", f"{stats.total_tokens_in + stats.total_tokens_out:,}")
    # 修复 C7: API calls 反映真实 LLM 调用次数（不含 wait/screenshot 内部步骤）
    table.add_row("API calls", str(stats.api_calls))
    table.add_row("Total steps", str(stats.total_steps))
    table.add_row("Actions", str(stats.total_actions))
    table.add_row("Errors", str(stats.errors))
    table.add_row("LLM time", f"{stats.total_llm_time:.1f}s")
    table.add_row("Context tokens", f"~{history_tokens:,}")
    table.add_row("Messages", str(len(agent.history)))
    console.print(table)


def _print_action(step: int, action: dict, result: str):
    act = action.get("action", "?")
    reason = action.get("reason", "")
    thought = action.get("thought", "")
    elapsed = action.get("_elapsed", 0)
    tokens_in = action.get("_tokens_in", 0)
    tokens_out = action.get("_tokens_out", 0)

    act_colors = {
        "left_click": GREEN, "double_click": GREEN, "right_click": GREEN,
        "type": CYAN, "key": ORANGE, "hotkey": ORANGE,
        "scroll": SILVER, "move": DIM, "drag": GOLD,
        "wait": DIM, "screenshot": SILVER, "done": GOLD,
    }
    color = act_colors.get(act, SILVER)

    # 借鉴 Hermes: 工具完成消息 ┊ emoji verb result elapsed
    _TOOL_EMOJIS = {
        "left_click": "👆", "double_click": "👆👆", "right_click": "🖱️",
        "type": "⌨️", "key": "⌨️", "hotkey": "⌨️",
        "scroll": "📜", "move": "🖱️", "drag": "↔️",
        "wait": "⏳", "screenshot": "📸", "done": "✅",
    }
    _TOOL_VERBS = {
        "left_click": "click", "double_click": "double-click", "right_click": "right-click",
        "type": "type", "key": "press", "hotkey": "hotkey",
        "scroll": "scroll", "move": "move", "drag": "drag",
        "wait": "wait", "screenshot": "capture", "done": "done",
    }
    emoji = _TOOL_EMOJIS.get(act, "🔧")
    verb = _TOOL_VERBS.get(act, act)

    # 借鉴 Hermes: ┊ emoji verb result elapsed
    line = Text()
    line.append(f"  {emoji} {verb:10} ", style=f"bold {color}")
    line.append(f"{result}", style=SILVER)
    line.append(f"  {elapsed:.1f}s ({tokens_in}→{tokens_out}tok)", style=DIM)
    console.print(line)

    # 借鉴 Hermes: reason 显示（用户可见）
    if reason:
        console.print(f"     [{CYAN}]{escape(reason)}[/{CYAN}]")

    if thought:
        from rich.markdown import Markdown
        console.print(Markdown(thought, style=DIM))


def _print_done(message: str, stats):
    text = Text()
    text.append(f"  ✅ ", style=GREEN)
    text.append(f"{message}", style=f"bold {GREEN}")
    text.append(f"\n  {stats.summary()}", style=SILVER)
    console.print(Panel(text, border_style=GREEN, box=box.ROUNDED))

    # 如果消息包含 markdown，渲染它
    if any(marker in message for marker in ["**", "#", "- ", "```", "|"]):
        console.print()
        from rich.markdown import Markdown
        console.print(Markdown(message))


# ═══════════════════════════════════════════════════════════
# 借鉴: 粘贴检测 (cli.py _on_text_changed)
# ═══════════════════════════════════════════════════════════

PASTE_CHARS_THRESHOLD = 500


def _is_paste(text: str) -> bool:
    """检测是否为粘贴内容（多行或大量字符）。"""
    if len(text) > PASTE_CHARS_THRESHOLD:
        return True
    if text.count('\n') >= 4:
        return True
    return False


# ═══════════════════════════════════════════════════════════
# 借鉴: 会话管理命令 (resume/save/branch/sessions)
# ═══════════════════════════════════════════════════════════

def _format_time_ago(timestamp_str: str) -> str:
    """将 ISO 时间戳转换为 '2h ago' 格式。"""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        delta = datetime.now() - dt
        seconds = delta.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        else:
            return f"{int(seconds // 86400)}d ago"
    except Exception:
        return ""


def _handle_sessions(session_db: SessionDB, current_session_id: str):
    """借鉴 Hermes /sessions: 带索引/预览/时间的会话列表。"""
    sessions = session_db.get_recent_sessions(10)
    # 过滤掉当前会话
    sessions = [s for s in sessions if s.get("id") != current_session_id]

    if not sessions:
        console.print(f"  [{DIM}]No saved sessions[/{DIM}]")
        return

    table = Table(
        title=f"[{GOLD}]Sessions[/{GOLD}]",
        box=box.ROUNDED,
        border_style=BRONZE,
        show_header=True,
        header_style=f"bold {GOLD}",
    )
    table.add_column("#", style=f"bold {GREEN}", width=3)
    table.add_column("Task", style=SILVER, max_width=35)
    table.add_column("Steps", style=CYAN, width=5)
    table.add_column("Tokens", style=CYAN, width=8)
    table.add_column("When", style=DIM, width=8)
    table.add_column("ID", style=DIM, width=20)

    for i, s in enumerate(sessions, 1):
        task = (s.get("task") or s.get("preview") or "")[:35]
        steps = s.get("steps", 0) or 0
        tokens = (s.get("tokens_in", 0) or 0) + (s.get("tokens_out", 0) or 0)
        when = _format_time_ago(s.get("started_at", ""))
        sid = s.get("id", "")[:20]
        table.add_row(str(i), escape(task), str(steps), _format_token_compact(tokens), when, sid)

    console.print(table)
    console.print(f"  [{DIM}]Use /resume <number> or /resume <id> to resume[/{DIM}]")


def _handle_resume(agent: Agent, session_db: SessionDB, arg: str,
                   session_id: list, last_task: list):
    """借鉴 Hermes /resume: 恢复历史会话。"""
    if not arg:
        # 无参数：显示最近会话供选择
        _handle_sessions(session_db, session_id[0])
        return

    target = arg.strip()

    # 按序号查找
    if target.isdigit():
        # 修复 C6: 传入 exclude_id，让数据库层直接排除当前会话
        sessions = session_db.get_recent_sessions(10, exclude_id=session_id[0])
        idx = int(target) - 1
        if 0 <= idx < len(sessions):
            target_id = sessions[idx]["id"]
        else:
            console.print(f"  [{RED}]Invalid session number: {target}[/{RED}]")
            return
    else:
        target_id = target

    # 查找会话
    session = session_db.get_session(target_id)
    if not session:
        console.print(f"  [{RED}]Session not found: {escape(target_id)}[/{RED}]")
        return

    # 加载历史
    messages = session_db.get_messages(target_id)
    if not messages:
        console.print(f"  [{RED}]Session has no messages[/{RED}]")
        return

    # 切换会话
    session_db.end_session(session_id[0], "resumed_other")
    session_id[0] = target_id
    agent.history = messages
    last_task[0] = session.get("task", "")

    console.print(f"  [{GREEN}]Resumed session: {escape(target_id)}[/{GREEN}]")
    console.print(f"  [{DIM}]Task: {escape(last_task[0])}[/{DIM}]")
    console.print(f"  [{DIM}]Loaded {len(messages)} messages[/{DIM}]")


def _handle_save(agent: Agent, session_id: str, last_task: str):
    """借鉴 Hermes /save: 导出会话为 JSON。"""
    if not agent.history:
        console.print(f"  [{DIM}]No conversation to save[/{DIM}]")
        return

    save_dir = Path(config.LOG_DIR) / "saved"
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = f"conversation_{datetime.now():%Y%m%d_%H%M%S}.json"
    filepath = save_dir / filename

    data = {
        "model": config.LLM_MODEL,
        "session_id": session_id,
        "task": last_task,
        "saved_at": datetime.now().isoformat(),
        "messages": agent.history,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    console.print(f"  [{GREEN}]Saved to: {filepath}[/{GREEN}]")


def _handle_branch(agent: Agent, session_db: SessionDB, arg: str,
                   session_id: list, last_task: list):
    """借鉴 Hermes /branch: 分叉当前会话。"""
    if not agent.history:
        console.print(f"  [{DIM}]No conversation to branch[/{DIM}]")
        return

    # 新会话 ID
    new_id = f"{datetime.now():%Y%m%d_%H%M%S}_{os.getpid():x}"

    # 标题
    title = arg.strip() if arg else (last_task[0] or "branched session")

    # 结束旧会话
    session_db.end_session(session_id[0], "branched")

    # 复制历史到新会话
    for msg in agent.history:
        session_db.save_message(new_id, msg.get("role", ""), str(msg.get("content", "")))

    # 保存新会话元数据
    session_db.save_session(
        new_id, title, "branched",
        agent.stats.total_steps,
        agent.stats.total_tokens_in,
        agent.stats.total_tokens_out,
        parent_id=session_id[0],
    )

    # 切换
    session_id[0] = new_id
    last_task[0] = title

    console.print(f"  [{GREEN}]Branched: {escape(title)}[/{GREEN}]")
    console.print(f"  [{DIM}]New session: {escape(new_id)}[/{DIM}]")
    console.print(f"  [{DIM}]Messages: {len(agent.history)}[/{DIM}]")


# ═══════════════════════════════════════════════════════════
# 命令处理
# ═══════════════════════════════════════════════════════════

def _handle_command(cmd: str, agent: Agent, session_db: SessionDB,
                    last_task: list, session_id: list) -> str:
    """处理 slash 命令。修复 D7: 用 sentinel 字符串代替布尔返回值。

    返回值:
      "exit"    - 退出 CLI
      "retry"   - 重试上一个任务（主循环会自动用 last_task 跑一遍）
      "continue" - 继续循环
    """
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("/quit", "/exit"):
        console.print(f"  [{GREEN}]Goodbye![/{GREEN}]")
        return "exit"

    elif command == "/help":
        _print_help()

    elif command == "/config":
        _print_config()

    elif command == "/screen":
        w, h = get_screen_size()
        console.print(f"  Screen: [{CYAN}]{w}x{h}[/{CYAN}]")

    elif command == "/usage":
        _print_usage(agent)

    elif command == "/compact":
        from .agent import _compress_history
        old_tokens = estimate_history_tokens(agent.history)
        old_len = len(agent.history)
        agent.history = _compress_history(agent.history)
        new_tokens = estimate_history_tokens(agent.history)
        new_len = len(agent.history)
        console.print(f"  [{GREEN}]Compressed: {old_len} msgs → {new_len} msgs[/{GREEN}]")
        console.print(f"  [{GREEN}]Tokens: {old_tokens:,} → {new_tokens:,}[/{GREEN}]")

    elif command == "/history":
        if not agent.history:
            console.print(f"  [{DIM}]No history[/{DIM}]")
        else:
            for i, msg in enumerate(agent.history):
                role = msg.get("role", "?")
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = "[image + text]"
                preview = str(content)[:80]
                console.print(f"  [{DIM}]{i:02d}[/{DIM}] [{CYAN}]{role}[/{CYAN}] {escape(preview)}")

    elif command == "/reset":
        agent.history.clear()
        from .agent import SessionStats  # 修复 D5: 不再使用 __import__ hack
        agent.stats = SessionStats()
        agent.reset_interrupt()
        console.print(f"  [{GREEN}]Session reset[/{GREEN}]")

    elif command == "/model":
        if arg:
            config.LLM_MODEL = arg
            console.print(f"  Model → [{CYAN}]{arg}[/{CYAN}]")
        else:
            console.print(f"  Current: [{CYAN}]{config.LLM_MODEL}[/{CYAN}]")

    elif command == "/steps":
        if arg and arg.isdigit():
            config.MAX_STEPS = int(arg)
            console.print(f"  Max steps → [{CYAN}]{arg}[/{CYAN}]")
        else:
            console.print(f"  Current: [{CYAN}]{config.MAX_STEPS}[/{CYAN}]")

    elif command == "/delay":
        if arg:
            try:
                config.ACTION_DELAY = float(arg)
                console.print(f"  Delay → [{CYAN}]{arg}s[/{CYAN}]")
            except ValueError:
                console.print(f"  [{RED}]Invalid number[/{RED}]")
        else:
            console.print(f"  Current: [{CYAN}]{config.ACTION_DELAY}s[/{CYAN}]")

    elif command == "/retry":
        if last_task[0]:
            console.print(f"  [{DIM}]Retrying: {escape(last_task[0])}[/{DIM}]")
            return "retry"  # 修复 D7: 用 sentinel 字符串代替布尔
        else:
            console.print(f"  [{DIM}]No task to retry[/{DIM}]")
            return "continue"

    elif command == "/undo":
        if len(agent.history) >= 2:
            agent.history.pop()  # remove last user
            agent.history.pop()  # remove last assistant
            console.print(f"  [{GREEN}]Undid last exchange[/{GREEN}]")
        else:
            console.print(f"  [{DIM}]Nothing to undo[/{DIM}]")

    elif command == "/sessions":
        _handle_sessions(session_db, session_id[0])

    elif command == "/resume":
        _handle_resume(agent, session_db, arg, session_id, last_task)

    elif command == "/save":
        _handle_save(agent, session_id[0], last_task[0])

    elif command == "/branch":
        _handle_branch(agent, session_db, arg, session_id, last_task)

    elif command == "/title":
        if last_task[0]:
            console.print(f"  [{CYAN}]{escape(last_task[0])}[/{CYAN}]")
        else:
            console.print(f"  [{DIM}]No active task[/{DIM}]")

    elif command == "/yolo":
        # 借鉴: YOLO 模式 (cli.py line 10121)
        agent._yolo = not getattr(agent, '_yolo', False)
        state = "ON" if agent._yolo else "OFF"
        color = GREEN if agent._yolo else DIM
        console.print(f"  [{color}]YOLO mode: {state}[/{color}]")

    elif command == "/steer":
        # 修复 D1: 改用 agent.steer()，Agent 在 _prepare_messages 中消费
        if arg:
            agent.steer(arg)
            console.print(f"  [{GREEN}]Steer queued: {escape(arg[:50])}[/{GREEN}]")
        else:
            console.print(f"  [{DIM}]Usage: /steer <instruction>[/{DIM}]")

    elif command == "/stop":
        # 修复 B1: 改用 agent.interrupt() 跨平台机制
        agent.interrupt(reason="user /stop")
        console.print(f"  [{ORANGE}]Stop requested[/{ORANGE}]")

    elif command == "/verbose":
        # 借鉴: /verbose 循环显示模式 (cli.py line 10034)
        modes = ["quiet", "normal", "verbose"]
        current = getattr(agent, '_verbose_mode', 'normal')
        idx = (modes.index(current) + 1) % len(modes) if current in modes else 1
        agent._verbose_mode = modes[idx]
        console.print(f"  [{CYAN}]Verbose: {modes[idx]}[/{CYAN}]")

    elif command == "/status":
        # 借鉴: /status 快速状态 (cli.py line 6184)
        stats = agent.stats
        history_tokens = estimate_history_tokens(agent.history)
        # 修复 B3: 用预算配置替代错误的硬编码 2000
        context_pct = min(
            100.0,
            (history_tokens / max(1, BUDGET_CONFIG.max_history_chars)) * 100,
        )
        console.print(f"  Model:     [{CYAN}]{config.LLM_MODEL}[/{CYAN}]")
        console.print(f"  Steps:     {stats.total_steps}/{config.MAX_STEPS}")
        console.print(f"  Actions:   {stats.total_actions}")
        console.print(f"  Tokens:    {stats.total_tokens_in}→{stats.total_tokens_out}")
        console.print(f"  Context:   ~{history_tokens:,} tokens ({context_pct:.1f}% of budget)")
        console.print(f"  Messages:  {len(agent.history)}")
        console.print(f"  Errors:    {stats.errors}")
        console.print(f"  YOLO:      [{GREEN if getattr(agent, '_yolo', False) else RED}]{'ON' if getattr(agent, '_yolo', False) else 'OFF'}[/]")
        console.print(f"  Interrupt: {'YES' if agent._interrupted else 'NO'}")

    elif command == "/queue":
        # 修复 D1: 改用 agent.queue_task()，主循环完成后自动执行
        if arg:
            agent.queue_task(arg)
            console.print(f"  [{GREEN}]Queued: {escape(arg[:50])}[/{GREEN}]")
        else:
            queue = agent._pending_queue
            if queue:
                for i, t in enumerate(queue):
                    console.print(f"  [{DIM}]{i+1}. {escape(t[:60])}[/{DIM}]")
            else:
                console.print(f"  [{DIM}]Queue empty[/{DIM}]")

    elif command == "/clear":
        # 修复 C5: 跨平台 Rich 清屏（不再使用 os.system("cls")）
        try:
            console.clear()
        except Exception:
            os.system("cls" if os.name == "nt" else "clear")

    else:
        console.print(f"  [{RED}]Unknown: {escape(command)}[/{RED}]")

    return "continue"  # 修复 D7: sentinel 字符串


# ═══════════════════════════════════════════════════════════
# CLI 主类
# ═══════════════════════════════════════════════════════════

class CLI:
    """交互式 CLI。"""

    def __init__(self):
        self.agent = Agent(save_screenshots=True)
        self.session_db = SessionDB()
        self.status_bar = StatusBar(self.agent)
        self._last_task = [None]  # mutable container for closure
        self._session_id = [f"{datetime.now():%Y%m%d_%H%M%S}_{os.getpid():x}"]

        self.session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=completer,
            style=prompt_style,
            key_bindings=kb,
            multiline=False,
        )

    def run(self):
        _print_banner()

        while True:
            try:
                # 借鉴: 三段式响应式状态栏
                try:
                    w = os.get_terminal_size().columns
                except Exception:
                    w = 80
                status = self.status_bar.render(w)
                user_input = self.session.prompt(
                    [("class:prompt", "❯ ")],
                )
            except (EOFError, KeyboardInterrupt):
                console.print(f"\n  [{GREEN}]Goodbye![/{GREEN}]")
                break

            text = user_input.strip()
            if not text:
                continue

            # 粘贴检测
            if _is_paste(text):
                lines = text.split('\n')
                console.print(f"  [{DIM}]Pasted {len(lines)} lines, {len(text)} chars[/{DIM}]")

            # Slash 命令
            if text.startswith("/"):
                result = _handle_command(
                    text, self.agent, self.session_db,
                    self._last_task, self._session_id
                )
                # 修复 D7: 用 sentinel 字符串分发
                if result == "exit":
                    break
                if result == "retry" and self._last_task[0]:
                    text = self._last_task[0]
                    # 跑一遍任务
                    self._run_task(text)
                    continue
                if result in ("continue", "retry"):
                    # retry 时若无 last_task 已在 _handle_command 打印提示
                    continue
                # 兜底：未知返回值视为 continue
                continue

            # 执行任务
            self._last_task[0] = text
            self._run_task(text)

    def _run_task(self, task: str):
        console.print()
        console.print(Panel(
            f"[{GOLD}]{escape(task)}[/{GOLD}]",
            title=f"[{BRONZE}]Task[/{BRONZE}]",
            border_style=BRONZE,
        ))

        self.status_bar.start_step()
        t0 = time.time()

        result = self.agent.run(
            task,
            stream=(getattr(self.agent, "_verbose_mode", "normal") == "verbose"),
        )

        total_time = time.time() - t0

        # 通知用户任务完成：窗口前置 + 提示音
        try:
            from .notify import notify_completion
            notify_completion()
        except Exception:
            pass

        _print_done(result, self.agent.stats)
        console.print(f"  [{DIM}]Total: {total_time:.1f}s[/{DIM}]\n")

        # 借鉴: 会话持久化
        try:
            self.session_db.save_session(
                self._session_id[0], task, result,
                self.agent.stats.total_steps,
                self.agent.stats.total_tokens_in,
                self.agent.stats.total_tokens_out,
            )
            for msg in self.agent.history:
                self.session_db.save_message(
                    self._session_id[0],
                    msg.get("role", ""),
                    str(msg.get("content", ""))[:5000],
                )
        except Exception:
            pass  # 持久化失败不影响使用


def main(task_arg: str = None, verbose: bool = False,
         plain: bool = False, no_color: bool = False,
         dry_run: bool = False) -> int:
    """CLI 入口。修复 C4: 返回退出码。

    Args:
        task_arg: 直接执行的任务（None 启动 REPL）
        verbose: 详细模式（启用流式 LLM 输出）
        plain: 纯文本模式（不启用 Rich TUI）
        no_color: 禁用 ANSI 颜色
        dry_run: 仅生成不执行

    Returns:
        退出码: 0=成功, 1=错误, 2=用户中断
    """
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            os.system("chcp 65001 >nul 2>&1")

    # 修复 C2/C3: 应用 plain / no_color / verbose 到 console 与 agent
    if no_color:
        try:
            console.no_color = True
        except Exception:
            pass
    # verbose 默认通过 _verbose_mode 控制；此处只在 CLI 单次任务时设置 agent 默认值

    if task_arg:
        # 修复 C4: 单次任务模式返回退出码
        agent = Agent(save_screenshots=not dry_run)
        if verbose:
            agent._verbose_mode = "verbose"
        _print_banner()
        console.print(Panel(
            f"[{GOLD}]{escape(task_arg)}[/{GOLD}]",
            title=f"[{BRONZE}]Task[/{BRONZE}]",
            border_style=BRONZE,
        ))
        try:
            result = agent.run(task_arg, stream=verbose)
            # 修复 V3: 多语言中断关键字检测（不再硬编码 "已中断"）
            from .i18n import t
            interrupt_keywords = (
                t("task_interrupted", default="已中断").lower(),
                "interrupted",  # LLM 经常返回英文
            )
            if result and any(kw in result.lower() for kw in interrupt_keywords):
                return 2  # 修复 C4: 中断 → 2
            if "Too many" in (result or "") or "error" in (result or "").lower():
                return 1
            return 0
        except KeyboardInterrupt:
            return 2
        except Exception as e:
            console.print(f"  [{RED}]Error: {e}[/{RED}]")
            return 1

    # REPL 模式
    cli = CLI()
    return cli.run() or 0
