"""Tests for visual effects (mouse ripple)"""

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
        RippleEffect, init_effects, trigger_ripple, cleanup
    )
run_test("import all functions", test_import)


# [2] RippleEffect
print("\n[2] RippleEffect")
def test_ripple_init():
    from computer_use_agent.visual_effects import RippleEffect
    r = RippleEffect()
    assert r._running == False
    assert r._hwnd is None
    assert r._ripples == []
run_test("RippleEffect init", test_ripple_init)

def test_ripple_stop_when_not_running():
    from computer_use_agent.visual_effects import RippleEffect
    r = RippleEffect()
    r.stop()
    assert r._running == False
run_test("RippleEffect stop when not running", test_ripple_stop_when_not_running)

def test_ripple_trigger():
    from computer_use_agent.visual_effects import RippleEffect
    r = RippleEffect()
    r.trigger(100, 100)
    r.trigger(200, 200)
    assert len(r._ripples) == 2
run_test("RippleEffect trigger queues ripple", test_ripple_trigger)

def test_ripple_trigger_no_crash():
    from computer_use_agent.visual_effects import RippleEffect
    r = RippleEffect()
    r.trigger(100, 100)  # not running, should be safe
run_test("RippleEffect trigger not running safe", test_ripple_trigger_no_crash)


# [3] Global functions
print("\n[3] Global functions")
def test_init_disabled():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(False)
    assert visual_effects._enabled == False
    assert visual_effects._ripple is None
run_test("init_effects disabled", test_init_disabled)

def test_init_enabled():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(True)
    assert visual_effects._enabled == True
    assert visual_effects._ripple is not None
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
    assert visual_effects._ripple is None
    time.sleep(0.3)
run_test("cleanup clears all", test_cleanup)

def test_trigger_ripple_global():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(True)
    visual_effects.trigger_ripple(100, 100)
    visual_effects.trigger_ripple(200, 200)
    time.sleep(0.1)
    visual_effects.cleanup()
    time.sleep(0.3)
run_test("trigger_ripple global", test_trigger_ripple_global)

def test_trigger_disabled():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(False)
    visual_effects.trigger_ripple(100, 100)  # no-op
    visual_effects.cleanup()
run_test("trigger_ripple disabled no-op", test_trigger_disabled)


# [4] Config
print("\n[4] Config")
def test_config():
    from computer_use_agent import config
    assert hasattr(config, "VISUAL_EFFECTS")
    assert isinstance(config.VISUAL_EFFECTS, bool)
    print(f"    VISUAL_EFFECTS={config.VISUAL_EFFECTS}")
run_test("config VISUAL_EFFECTS", test_config)


# [5] Executor
print("\n[5] Executor")
def test_executor_ripple():
    from computer_use_agent.executor import _trigger_ripple
    _trigger_ripple(100, 100)
run_test("executor _trigger_ripple", test_executor_ripple)


# [6] Win32
print("\n[6] Win32 API")
def test_win32():
    import ctypes
    assert hasattr(ctypes.windll, "user32")
    assert hasattr(ctypes.windll, "gdi32")
run_test("Win32 API available", test_win32)


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
