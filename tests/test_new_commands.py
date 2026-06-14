"""测试新 CLI 命令"""

import sys
import os

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
print("  New CLI Commands Tests")
print("=" * 60)


# ── [1] /yolo ──
print("\n[1] /yolo")

def test_yolo_toggle():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    # Default: off
    assert getattr(agent, '_yolo', False) == False
    _handle_command("/yolo", agent, db, [None], ["s1"])
    assert agent._yolo == True
    _handle_command("/yolo", agent, db, [None], ["s1"])
    assert agent._yolo == False
run_test("/yolo toggle", test_yolo_toggle)


# ── [2] /steer ──
print("\n[2] /steer")

def test_steer_queued():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    _handle_command("/steer click the blue button", agent, db, [None], ["s1"])
    assert hasattr(agent, '_pending_steer')
    assert len(agent._pending_steer) == 1
    assert "blue button" in agent._pending_steer[0]
run_test("/steer queues message", test_steer_queued)

def test_steer_empty():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    _handle_command("/steer", agent, db, [None], ["s1"])
    # Should not crash, just show usage
run_test("/steer empty shows usage", test_steer_empty)


# ── [3] /stop ──
print("\n[3] /stop")

def test_stop_sets_interrupt():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    assert agent._interrupted == False
    _handle_command("/stop", agent, db, [None], ["s1"])
    assert agent._interrupted == True
run_test("/stop sets interrupt", test_stop_sets_interrupt)


# ── [4] /verbose ──
print("\n[4] /verbose")

def test_verbose_cycles():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    # Default: normal
    _handle_command("/verbose", agent, db, [None], ["s1"])
    assert agent._verbose_mode == "verbose"
    _handle_command("/verbose", agent, db, [None], ["s1"])
    assert agent._verbose_mode == "quiet"
    _handle_command("/verbose", agent, db, [None], ["s1"])
    assert agent._verbose_mode == "normal"
run_test("/verbose cycles modes", test_verbose_cycles)


# ── [5] /status ──
print("\n[5] /status")

def test_status_shows_info():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    agent.stats.update({"_tokens_in": 100, "_tokens_out": 50, "_elapsed": 1.0, "action": "click"})
    _handle_command("/status", agent, db, [None], ["s1"])
    # Should not crash
run_test("/status shows info", test_status_shows_info)


# ── [6] /queue ──
print("\n[6] /queue")

def test_queue_add():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    _handle_command("/queue open notepad", agent, db, [None], ["s1"])
    assert hasattr(agent, '_pending_queue')
    assert len(agent._pending_queue) == 1
    assert "notepad" in agent._pending_queue[0]
run_test("/queue adds task", test_queue_add)

def test_queue_multiple():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    _handle_command("/queue task1", agent, db, [None], ["s1"])
    _handle_command("/queue task2", agent, db, [None], ["s1"])
    assert len(agent._pending_queue) == 2
run_test("/queue multiple tasks", test_queue_multiple)

def test_queue_empty():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    db = SessionDB(":memory:")
    _handle_command("/queue", agent, db, [None], ["s1"])
    # Should show "Queue empty"
run_test("/queue empty shows message", test_queue_empty)


# ── [7] Command count ──
print("\n[7] Command registry")

def test_all_commands_present():
    from computer_use_agent.cli import COMMANDS
    required = ["/yolo", "/steer", "/stop", "/verbose", "/status", "/queue"]
    for cmd in required:
        assert cmd in COMMANDS, f"Missing: {cmd}"
    assert len(COMMANDS) >= 25
    print(f"    {len(COMMANDS)} commands total")
run_test("all new commands in registry", test_all_commands_present)


# ── [8] Integration: yolo affects agent behavior ──
print("\n[8] Integration")

def test_yolo_in_agent():
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    # Agent should have _yolo attribute accessible
    agent._yolo = True
    assert agent._yolo == True
    agent._yolo = False
    assert agent._yolo == False
run_test("yolo flag on agent", test_yolo_in_agent)

def test_steer_in_agent():
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    agent._pending_steer = ["click here"]
    assert len(agent._pending_steer) == 1
run_test("steer queue on agent", test_steer_in_agent)

def test_verbose_in_agent():
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    agent._verbose_mode = "verbose"
    assert agent._verbose_mode == "verbose"
run_test("verbose mode on agent", test_verbose_in_agent)


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
