"""Tests for visual effects (breathing border + ripple)"""

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
print("  Visual Effects Tests")
print("=" * 60)


# [1] Module imports
print("\n[1] Import tests")

def test_import_visual_effects():
    from computer_use_agent.visual_effects import (
        BreathingBorder, RippleEffect,
        init_effects, start_border, stop_border,
        trigger_ripple, cleanup
    )
run_test("import visual_effects module", test_import_visual_effects)


# [2] BreathingBorder class (no tkinter mainloop)
print("\n[2] BreathingBorder")

def test_breathing_border_init():
    from computer_use_agent.visual_effects import BreathingBorder
    b = BreathingBorder()
    assert b._running == False
    assert b._root is None
    assert b._canvas is None
    assert b._opacity == 0.0
    assert b._direction == 1
run_test("BreathingBorder init", test_breathing_border_init)

def test_breathing_border_stop_when_not_running():
    from computer_use_agent.visual_effects import BreathingBorder
    b = BreathingBorder()
    b.stop()  # should not crash
    assert b._running == False
run_test("BreathingBorder stop when not running", test_breathing_border_stop_when_not_running)

def test_breathing_border_opacity_animation():
    from computer_use_agent.visual_effects import BreathingBorder
    b = BreathingBorder()
    # Test opacity math without tkinter
    b._opacity = 0.0
    b._direction = 1
    # Simulate animation steps
    for _ in range(30):
        b._opacity += b._direction * 0.02
        if b._opacity >= 0.6:
            b._opacity = 0.6
            b._direction = -1
        elif b._opacity <= 0.0:
            b._opacity = 0.0
            b._direction = 1
    assert 0.0 <= b._opacity <= 0.6
    assert b._direction in (-1, 1)
run_test("BreathingBorder opacity animation math", test_breathing_border_opacity_animation)


# [3] RippleEffect class (no tkinter mainloop)
print("\n[3] RippleEffect")

def test_ripple_init():
    from computer_use_agent.visual_effects import RippleEffect
    r = RippleEffect()
    assert r._running == False
    assert r._root is None
run_test("RippleEffect init", test_ripple_init)

def test_ripple_trigger_when_not_running():
    from computer_use_agent.visual_effects import RippleEffect
    r = RippleEffect()
    r.trigger(100, 100)  # should not crash when not running
run_test("RippleEffect trigger when not running", test_ripple_trigger_when_not_running)

def test_ripple_stop_when_not_running():
    from computer_use_agent.visual_effects import RippleEffect
    r = RippleEffect()
    r.stop()  # should not crash
    assert r._running == False
run_test("RippleEffect stop when not running", test_ripple_stop_when_not_running)


# [4] Global functions (no tkinter)
print("\n[4] Global functions")

def test_init_effects_disabled():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(False)
    assert visual_effects._enabled == False
    assert visual_effects._border is None
    assert visual_effects._ripple is None
run_test("init_effects disabled", test_init_effects_disabled)

def test_cleanup():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(False)
    visual_effects.cleanup()
    assert visual_effects._enabled == False
    assert visual_effects._border is None
    assert visual_effects._ripple is None
run_test("cleanup clears everything", test_cleanup)

def test_start_stop_border_no_effects():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(False)
    visual_effects.start_border()  # should be no-op
    visual_effects.stop_border()   # should be no-op
    visual_effects.cleanup()
run_test("start/stop border when disabled", test_start_stop_border_no_effects)

def test_trigger_ripple_disabled():
    from computer_use_agent import visual_effects
    visual_effects.init_effects(False)
    visual_effects.trigger_ripple(100, 100)  # should be no-op
    visual_effects.cleanup()
run_test("trigger_ripple when disabled", test_trigger_ripple_disabled)

def test_trigger_ripple_no_border():
    from computer_use_agent import visual_effects
    # Ensure global state is clean
    visual_effects._enabled = False
    visual_effects._ripple = None
    visual_effects.trigger_ripple(100, 100)  # should not crash
run_test("trigger_ripple with no ripple instance", test_trigger_ripple_no_border)


# [5] Config integration
print("\n[5] Config integration")

def test_visual_effects_config():
    from computer_use_agent import config
    assert hasattr(config, "VISUAL_EFFECTS")
    assert isinstance(config.VISUAL_EFFECTS, bool)
    print(f"    VISUAL_EFFECTS: {config.VISUAL_EFFECTS}")
run_test("config has VISUAL_EFFECTS", test_visual_effects_config)


# [6] Executor ripple integration
print("\n[6] Executor integration")

def test_executor_trigger_ripple():
    from computer_use_agent.executor import _trigger_ripple
    _trigger_ripple(100, 100)  # should not crash
run_test("executor _trigger_ripple no crash", test_executor_trigger_ripple)


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
