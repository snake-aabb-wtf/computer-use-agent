"""CLI 新功能测试 - 借鉴 Hermes 的模式"""

import sys
import os

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        os.system("chcp 65001 >nul 2>&1")

passed = 0
failed = 0
errors = []


def run_test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        failed += 1
        errors.append((name, e))
        print(f"  [FAIL] {name}: {e}")
        import traceback
        traceback.print_exc()


print("=" * 60)
print("  CLI New Features Tests")
print("=" * 60)


# ── [1] SessionDB ──
print("\n[1] SessionDB (SQLite)")

def test_sessiondb_init():
    from computer_use_agent.cli import SessionDB
    db = SessionDB(":memory:")
    assert db is not None
run_test("SessionDB init", test_sessiondb_init)

def test_sessiondb_save_and_get():
    from computer_use_agent.cli import SessionDB
    db = SessionDB(":memory:")
    db.save_session("test_001", "open notepad", "done", 5, 1000, 500)
    sessions = db.get_recent_sessions(10)
    assert len(sessions) == 1
    assert sessions[0]["id"] == "test_001"
    assert sessions[0]["task"] == "open notepad"
    assert sessions[0]["steps"] == 5
    assert sessions[0]["tokens_in"] == 1000
    assert sessions[0]["tokens_out"] == 500
run_test("SessionDB save and get", test_sessiondb_save_and_get)

def test_sessiondb_save_message():
    from computer_use_agent.cli import SessionDB
    db = SessionDB(":memory:")
    db.save_session("s1", "task", "result", 1, 10, 5)
    db.save_message("s1", "user", "hello")
    db.save_message("s1", "assistant", '{"action":"click"}')
    # Messages saved (can verify by re-reading if we add a getter)
    assert True
run_test("SessionDB save messages", test_sessiondb_save_message)

def test_sessiondb_multiple_sessions():
    import time
    from computer_use_agent.cli import SessionDB
    db = SessionDB(":memory:")
    db.save_session("s1", "task1", "r1", 1, 10, 5)
    time.sleep(0.01)  # ensure different timestamps
    db.save_session("s2", "task2", "r2", 2, 20, 10)
    time.sleep(0.01)
    db.save_session("s3", "task3", "r3", 3, 30, 15)
    sessions = db.get_recent_sessions(2)
    assert len(sessions) == 2
    # Most recent should be s3 (latest timestamp)
    assert sessions[0]["id"] == "s3"
run_test("SessionDB multiple sessions", test_sessiondb_multiple_sessions)


# ── [2] StatusBar ──
print("\n[2] StatusBar")

def test_statusbar_init():
    from computer_use_agent.cli import StatusBar
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    sb = StatusBar(agent)
    assert sb is not None
run_test("StatusBar init", test_statusbar_init)

def test_statusbar_render():
    from computer_use_agent.cli import StatusBar
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    sb = StatusBar(agent)
    # Simulate some stats
    agent.stats.update({"_tokens_in": 1000, "_tokens_out": 500, "_elapsed": 2.0, "action": "click"})
    agent.stats.update({"_tokens_in": 2000, "_tokens_out": 800, "_elapsed": 3.0, "action": "done"})
    rendered = sb.render(80)
    assert "mimo-v2.5" in rendered
    assert "Step" in rendered
    assert "Act" in rendered
    print(f"    rendered: {rendered}")
run_test("StatusBar render", test_statusbar_render)

def test_statusbar_elapsed():
    from computer_use_agent.cli import StatusBar
    from computer_use_agent.agent import Agent
    import time
    agent = Agent(save_screenshots=False)
    sb = StatusBar(agent)
    sb.start_step()
    time.sleep(0.1)
    elapsed = sb.step_elapsed()
    assert "s" in elapsed
    assert len(elapsed) > 0
run_test("StatusBar elapsed", test_statusbar_elapsed)


# ── [3] Token formatting ──
print("\n[3] Token formatting")

def test_format_token_compact():
    from computer_use_agent.cli import _format_token_compact
    assert _format_token_compact(0) == "0"
    assert _format_token_compact(500) == "500"
    assert _format_token_compact(1234) == "1.2K"
    assert _format_token_compact(12345) == "12.3K"
    assert _format_token_compact(1234567) == "1.2M"
    assert _format_token_compact(1234567890) == "1.2B"
    print("    0->0, 500->500, 1234->1.2K, 1.2M, 1.2B")
run_test("format_token_compact", test_format_token_compact)

def test_build_context_bar():
    from computer_use_agent.cli import _build_context_bar
    assert _build_context_bar(0) == "[░░░░░░░░░░]"
    assert _build_context_bar(50) == "[█████░░░░░]"
    assert _build_context_bar(100) == "[██████████]"
    assert _build_context_bar(30, width=5) == "[██░░░]"
    print("    0%, 50%, 100%, custom width all OK")
run_test("build_context_bar", test_build_context_bar)

def test_context_style():
    from computer_use_agent.cli import _context_style
    assert "green" in _context_style(10).lower() or "8FBC8F" in _context_style(10)
    assert "red" in _context_style(96).lower() or "FF6B6B" in _context_style(96)
    assert "orange" in _context_style(85).lower() or "FF8C00" in _context_style(85)
    assert "gold" in _context_style(60).lower() or "FFD700" in _context_style(60)
run_test("context_style", test_context_style)


# ── [4] Paste detection ──
print("\n[4] Paste detection")

def test_is_paste_short():
    from computer_use_agent.cli import _is_paste
    assert _is_paste("hello") == False
    assert _is_paste("a" * 100) == False
run_test("is_paste short text", test_is_paste_short)

def test_is_paste_long():
    from computer_use_agent.cli import _is_paste
    assert _is_paste("a" * 600) == True
run_test("is_paste long text", test_is_paste_long)

def test_is_paste_multiline():
    from computer_use_agent.cli import _is_paste
    assert _is_paste("line1\nline2\nline3\nline4\nline5") == True
run_test("is_paste multiline", test_is_paste_multiline)


# ── [5] Slash commands ──
print("\n[5] Slash commands")

def test_commands_registry():
    from computer_use_agent.cli import COMMANDS
    assert "/help" in COMMANDS
    assert "/quit" in COMMANDS
    assert "/config" in COMMANDS
    assert "/usage" in COMMANDS
    assert "/retry" in COMMANDS
    assert "/undo" in COMMANDS
    assert "/sessions" in COMMANDS
    assert "/title" in COMMANDS
    assert len(COMMANDS) >= 15
    print(f"    {len(COMMANDS)} commands")
run_test("commands registry", test_commands_registry)

def test_handle_quit():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    result = _handle_command("/quit", agent, db, [None], ["s1"])
    assert result == True
run_test("/quit", test_handle_quit)

def test_handle_usage():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    agent.stats.update({"_tokens_in": 1000, "_tokens_out": 500, "_elapsed": 1.0, "action": "click"})
    db = SessionDB(":memory:")
    result = _handle_command("/usage", agent, db, [None], ["s1"])
    assert result == False
run_test("/usage", test_handle_usage)

def test_handle_undo():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    agent.history = [{"role": "user", "content": "task"}, {"role": "assistant", "content": "response"}]
    db = SessionDB(":memory:")
    _handle_command("/undo", agent, db, [None], ["s1"])
    assert len(agent.history) == 0
run_test("/undo", test_handle_undo)

def test_handle_title():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    _handle_command("/title", agent, db, ["open notepad"], ["s1"])
    assert True  # no error
run_test("/title", test_handle_title)

def test_handle_sessions():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    db.save_session("s1", "task1", "done", 1, 10, 5)
    result = _handle_command("/sessions", agent, db, [None], ["s1"])
    assert result == False
run_test("/sessions", test_handle_sessions)

def test_handle_model():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    from computer_use_agent import config
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    old = config.LLM_MODEL
    _handle_command("/model test-model", agent, db, [None], ["s1"])
    assert config.LLM_MODEL == "test-model"
    config.LLM_MODEL = old
run_test("/model", test_handle_model)

def test_handle_steps():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    from computer_use_agent import config
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    old = config.MAX_STEPS
    _handle_command("/steps 50", agent, db, [None], ["s1"])
    assert config.MAX_STEPS == 50
    config.MAX_STEPS = old
run_test("/steps", test_handle_steps)


# ── [6] Imports ──
print("\n[6] Module imports")

def test_import_all():
    from computer_use_agent.cli import (
        CLI, main, _print_banner, _print_help, _print_config,
        _print_usage, _print_action, _print_done, _handle_command,
        COMMANDS, SessionDB, StatusBar, _format_token_compact,
        _build_context_bar, _context_style, _is_paste,
    )
run_test("import all CLI symbols", test_import_all)

def test_import_new_modules():
    from computer_use_agent.sanitization import (
        repair_json, repair_message_sequence, repair_tool_name,
        sanitize_api_messages,
    )
    from computer_use_agent.token_budget import (
        truncate_message, estimate_tokens, estimate_message_tokens,
        estimate_history_tokens, enforce_history_budget, should_compress,
        BudgetConfig,
    )
run_test("import all new modules", test_import_new_modules)


# ── [7] New session commands ──
print("\n[7] New session commands")

def test_sessions_with_data():
    from computer_use_agent.cli import _handle_sessions
    from computer_use_agent.cli import SessionDB
    db = SessionDB(":memory:")
    db.save_session("s1", "open notepad", "done", 5, 1000, 500)
    db.save_message("s1", "user", "open notepad")
    db.save_message("s1", "assistant", '{"action":"left_click"}')
    _handle_sessions(db, "current_session")  # should not error
run_test("/sessions with data", test_sessions_with_data)

def test_resume_by_id():
    from computer_use_agent.cli import _handle_resume
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    db = SessionDB(":memory:")
    db.save_session("s1", "open notepad", "done", 5, 1000, 500)
    db.save_message("s1", "user", "open notepad")
    db.save_message("s1", "assistant", '{"action":"left_click"}')
    agent = Agent(save_screenshots=False)
    session_id = ["current"]
    last_task = [None]
    _handle_resume(agent, db, "s1", session_id, last_task)
    assert session_id[0] == "s1"
    assert len(agent.history) == 2
    assert last_task[0] == "open notepad"
run_test("/resume by ID", test_resume_by_id)

def test_resume_by_index():
    from computer_use_agent.cli import _handle_resume
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    db = SessionDB(":memory:")
    db.save_session("s1", "task1", "done", 1, 10, 5)
    db.save_message("s1", "user", "task1")
    db.save_session("s2", "task2", "done", 2, 20, 10)
    db.save_message("s2", "user", "task2")
    agent = Agent(save_screenshots=False)
    session_id = ["current"]
    last_task = [None]
    _handle_resume(agent, db, "1", session_id, last_task)
    assert session_id[0] in ("s1", "s2")
    assert len(agent.history) >= 1
run_test("/resume by index", test_resume_by_index)

def test_resume_not_found():
    from computer_use_agent.cli import _handle_resume
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    db = SessionDB(":memory:")
    agent = Agent(save_screenshots=False)
    _handle_resume(agent, db, "nonexistent", ["current"], [None])
    assert len(agent.history) == 0  # no change
run_test("/resume not found", test_resume_not_found)

def test_save_conversation():
    from computer_use_agent.cli import _handle_save
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    agent.history = [{"role": "user", "content": "task"}, {"role": "assistant", "content": '{"action":"click"}'}]
    _handle_save(agent, "test_session", "open notepad")
    # Check file was created
    saved_dir = __import__('pathlib').Path("logs/saved")
    files = list(saved_dir.glob("conversation_*.json"))
    assert len(files) > 0
    # Clean up
    files[-1].unlink()
run_test("/save conversation", test_save_conversation)

def test_branch_conversation():
    from computer_use_agent.cli import _handle_branch
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    db = SessionDB(":memory:")
    db.save_session("old_session", "original", "done", 1, 10, 5)
    agent = Agent(save_screenshots=False)
    agent.history = [{"role": "user", "content": "task"}]
    agent.stats.update({"_tokens_in": 100, "_tokens_out": 50, "_elapsed": 1.0, "action": "click"})
    session_id = ["old_session"]
    last_task = ["original"]
    _handle_branch(agent, db, "my fork", session_id, last_task)
    assert session_id[0] != "old_session"
    assert last_task[0] == "my fork"
    # Check parent_id
    new_session = db.get_session(session_id[0])
    assert new_session is not None
run_test("/branch conversation", test_branch_conversation)

def test_format_time_ago():
    from computer_use_agent.cli import _format_time_ago
    from datetime import datetime, timedelta
    now = datetime.now().isoformat()
    assert _format_time_ago(now) == "just now"
    hour_ago = (datetime.now() - timedelta(hours=2)).isoformat()
    assert "h ago" in _format_time_ago(hour_ago)
    day_ago = (datetime.now() - timedelta(days=3)).isoformat()
    assert "d ago" in _format_time_ago(day_ago)
run_test("format_time_ago", test_format_time_ago)


# ── SUMMARY ──
print(f"\n{'='*60}")
print(f"  Results: {passed} passed, {failed} failed")
if errors:
    print(f"\n  Failed:")
    for name, err in errors:
        print(f"    - {name}: {err}")
print(f"{'='*60}")

if failed > 0:
    input("\n  Some tests failed. Press Enter to exit...")
else:
    input("\n  All tests passed! Press Enter to exit...")
