"""Tests for visual effects (click, drag, action info)"""

import sys
import os
import time

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
print("  Visual Effects Tests")
print("=" * 60)


# [1] Imports
print("\n[1] Imports")
def test_import():
    from computer_use_agent.visual_effects import (
        VisualOverlay, init_effects, trigger_click, trigger_drag,
        show_action_info, cleanup
    )
run_test("import all functions", test_import)


# [2] VisualOverlay class
print("\n[2] VisualOverlay")
def test_overlay_init():
    from computer_use_agent.visual_effects import VisualOverlay
    o = VisualOverlay()
    assert o._running == False
    assert o._hwnd is None
    assert o._effects == []
run_test("VisualOverlay init", test_overlay_init)

def test_overlay_stop_not_running():
    from computer_use_agent.visual_effects import VisualOverlay
    o = VisualOverlay()
    o.stop()
    assert o._running == False
run_test("VisualOverlay stop not running", test_overlay_stop_not_running)

def test_overlay_trigger_click():
    from computer_use_agent.visual_effects import VisualOverlay
    o = VisualOverlay()
    o.trigger_click(100, 200)
    assert not o._queue.empty()
run_test("VisualOverlay trigger_click queues", test_overlay_trigger_click)

def test_overlay_trigger_drag():
    from computer_use_agent.visual_effects import VisualOverlay
    o = VisualOverlay()
    o.trigger_drag(100, 100, 200, 200)
    assert not o._queue.empty()
run_test("VisualOverlay trigger_drag queues", test_overlay_trigger_drag)

def test_overlay_show_action_info():
    from computer_use_agent.visual_effects import VisualOverlay
    o = VisualOverlay()
    o.show_action_info("Click", "test thought", "(100, 200)")
    assert not o._queue.empty()
run_test("VisualOverlay show_action_info queues", test_overlay_show_action_info)


# [3] Global functions
print("\n[3] Global functions")
def test_init_disabled():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(False)
    assert visual_effects._enabled == False
    assert visual_effects._overlay is None
run_test("init_effects disabled", test_init_disabled)

def test_init_enabled():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(True)
    assert visual_effects._enabled == True
    assert visual_effects._overlay is not None
    time.sleep(0.3)
    visual_effects.cleanup()
    time.sleep(0.3)
run_test("init_effects enabled", test_init_enabled)

def test_cleanup():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(True)
    time.sleep(0.2)
    visual_effects.cleanup()
    assert visual_effects._enabled == False
    assert visual_effects._overlay is None
    time.sleep(0.3)
run_test("cleanup clears all", test_cleanup)

def test_trigger_click_global():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(True)
    visual_effects.trigger_click(100, 100)
    time.sleep(0.1)
    visual_effects.cleanup()
    time.sleep(0.3)
run_test("trigger_click global", test_trigger_click_global)

def test_trigger_drag_global():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(True)
    visual_effects.trigger_drag(100, 100, 200, 200)
    time.sleep(0.1)
    visual_effects.cleanup()
    time.sleep(0.3)
run_test("trigger_drag global", test_trigger_drag_global)

def test_show_action_info_global():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(True)
    visual_effects.show_action_info("Click", "test", "(100, 100)")
    time.sleep(0.1)
    visual_effects.cleanup()
    time.sleep(0.3)
run_test("show_action_info global", test_show_action_info_global)


# [4] Executor integration
print("\n[4] Executor")
def test_executor_click():
    from computer_use_agent.executor import _trigger_click, _show_action_info
    _trigger_click(100, 100)
    _show_action_info("Click", "test", "(100, 100)")
run_test("executor click + info", test_executor_click)

def test_executor_drag():
    from computer_use_agent.executor import _trigger_drag
    _trigger_drag(100, 100, 200, 200)
run_test("executor drag", test_executor_drag)


# [5] Config
print("\n[5] Config")
def test_config():
    from computer_use_agent import config
    assert hasattr(config, "VISUAL_EFFECTS")
    assert isinstance(config.VISUAL_EFFECTS, bool)
run_test("config VISUAL_EFFECTS", test_config)


# SUMMARY
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
