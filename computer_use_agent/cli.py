"""交互式 CLI - 深度借鉴 Hermes CLI 系统"""

import os
import sys
import time
import json
import sqlite3
import threading
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
from .token_budget import estimate_history_tokens, estimate_message_tokens


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

    def save_session(self, session_id: str, task: str, result: str,
                     steps: int, tokens_in: int, tokens_out: int,
                     parent_id: str = None):
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO sessions
               (id, task, started_at, ended_at, steps, tokens_in, tokens_out, result, parent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, task, datetime.now().isoformat(),
             datetime.now().isoformat(), steps, tokens_in, tokens_out, result, parent_id)
        )
        conn.commit()

    def save_message(self, session_id: str, role: str, content: str):
        conn = self._conn()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat())
        )
        conn.commit()

    def get_session(self, session_id: str) -> dict | None:
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def get_messages(self, session_id: str) -> list[dict]:
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def end_session(self, session_id: str, reason: str = "completed"):
        conn = self._conn()
        conn.execute(
            "UPDATE sessions SET ended_at = ?, result = ? WHERE id = ?",
            (datetime.now().isoformat(), reason, session_id)
        )
        conn.commit()

    def get_recent_sessions(self, limit: int = 10) -> list[dict]:
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT s.*, 
                      (SELECT content FROM messages WHERE session_id = s.id AND role = 'user' LIMIT 1) as preview
               FROM sessions s 
               WHERE s.ended_at IS NULL OR s.ended_at != 'resumed_other'
               ORDER BY s.started_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


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

        # 估算上下文使用率 (假设 200K 上下文窗口)
        history_tokens = estimate_history_tokens(self.agent.history)
        context_pct = min(100, history_tokens / 2000)

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
    capture_label = f"{config.CAPTURE_MODE.upper()} (SOM + UIA)" if config.CAPTURE_MODE == "som" else "VISION (pure screenshot)"
    info.add_row("Capture Mode", f"[{GREEN if config.CAPTURE_MODE == 'som' else CYAN}]{capture_label}[/]")
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
    """借鉴 Hermes /usage 命令。"""
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
    table.add_row("API calls", str(stats.total_steps))
    table.add_row("Actions", str(stats.total_actions))
    table.add_row("Errors", str(stats.errors))
    table.add_row("LLM time", f"{stats.total_llm_time:.1f}s")
    table.add_row("Context tokens", f"~{history_tokens:,}")
    table.add_row("Messages", str(len(agent.history)))
    console.print(table)


def _print_action(step: int, action: dict, result: str):
    act = action.get("action", "?")
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

    line = Text()
    line.append(f"  [{step:02d}] ", style=DIM)
    line.append(f"{act}", style=f"bold {color}")
    line.append(f"  {result}", style=SILVER)
    line.append(f"  ({elapsed}s, {tokens_in}→{tokens_out}tok)", style=DIM)
    console.print(line)

    if thought:
        console.print(f"      [{DIM}]{escape(thought)}[/{DIM}]")


def _print_done(message: str, stats):
    text = Text()
    text.append(f"  ✅ ", style=GREEN)
    text.append(f"{message}", style=f"bold {GREEN}")
    text.append(f"\n  {stats.summary()}", style=SILVER)
    console.print(Panel(text, border_style=GREEN, box=box.ROUNDED))


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
        sessions = session_db.get_recent_sessions(10)
        sessions = [s for s in sessions if s.get("id") != session_id[0]]
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
                    last_task: list, session_id: list) -> bool:
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("/quit", "/exit"):
        console.print(f"  [{GREEN}]Goodbye![/{GREEN}]")
        return True

    elif command == "/help":
        _print_help()

    elif command == "/config":
        _print_config()

    elif command == "/screen":
        w, h = get_screen_size()
        console.print(f"  Screen: [{CYAN}]{w}x{h}[/{CYAN}]")

    elif command == "/usage":
        _print_usage(agent)

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
        agent.stats = __import__('computer_use_agent.agent', fromlist=['SessionStats']).SessionStats()
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
            return False  # signal to rerun
        else:
            console.print(f"  [{DIM}]No task to retry[/{DIM}]")

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
        # 借鉴: /steer 运行中注入指令 (cli.py line 9069)
        if arg:
            if hasattr(agent, '_pending_steer'):
                agent._pending_steer.append(arg)
            else:
                agent._pending_steer = [arg]
            console.print(f"  [{GREEN}]Steer queued: {escape(arg[:50])}[/{GREEN}]")
        else:
            console.print(f"  [{DIM}]Usage: /steer <instruction>[/{DIM}]")

    elif command == "/stop":
        # 借鉴: /stop 停止任务 (cli.py line 5878)
        agent._interrupted = True
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
        console.print(f"  Model:     [{CYAN}]{config.LLM_MODEL}[/{CYAN}]")
        console.print(f"  Steps:     {stats.total_steps}/{config.MAX_STEPS}")
        console.print(f"  Actions:   {stats.total_actions}")
        console.print(f"  Tokens:    {stats.total_tokens_in}→{stats.total_tokens_out}")
        console.print(f"  Context:   ~{history_tokens:,} tokens")
        console.print(f"  Messages:  {len(agent.history)}")
        console.print(f"  Errors:    {stats.errors}")
        console.print(f"  YOLO:      [{GREEN if getattr(agent, '_yolo', False) else RED}]{'ON' if getattr(agent, '_yolo', False) else 'OFF'}[/]")
        console.print(f"  Interrupt: {'YES' if agent._interrupted else 'NO'}")

    elif command == "/queue":
        # 借鉴: /queue 排队下一条指令 (cli.py line 9058)
        if arg:
            if hasattr(agent, '_pending_queue'):
                agent._pending_queue.append(arg)
            else:
                agent._pending_queue = [arg]
            console.print(f"  [{GREEN}]Queued: {escape(arg[:50])}[/{GREEN}]")
        else:
            queue = getattr(agent, '_pending_queue', [])
            if queue:
                for i, t in enumerate(queue):
                    console.print(f"  [{DIM}]{i+1}. {escape(t[:60])}[/{DIM}]")
            else:
                console.print(f"  [{DIM}]Queue empty[/{DIM}]")

    elif command == "/clear":
        os.system("cls" if os.name == "nt" else "clear")

    else:
        console.print(f"  [{RED}]Unknown: {escape(command)}[/{RED}]")

    return False


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
                should_quit = _handle_command(
                    text, self.agent, self.session_db,
                    self._last_task, self._session_id
                )
                if should_quit:
                    break
                # /retry 特殊处理
                if text.strip() == "/retry" and self._last_task[0]:
                    text = self._last_task[0]
                else:
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

        result = self.agent.run(task)

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


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            os.system("chcp 65001 >nul 2>&1")

    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        task = " ".join(sys.argv[1:])
        agent = Agent(save_screenshots=True)
        _print_banner()
        console.print(Panel(
            f"[{GOLD}]{escape(task)}[/{GOLD}]",
            title=f"[{BRONZE}]Task[/{BRONZE}]",
            border_style=BRONZE,
        ))
        agent.run(task)
        return

    cli = CLI()
    cli.run()
