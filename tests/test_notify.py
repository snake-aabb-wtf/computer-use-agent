"""Tests for task completion notification"""

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
print("  Notification Tests")
print("=" * 60)


# [1] Module imports
print("\n[1] Import tests")

def test_import_notify():
    from computer_use_agent.notify import notify_completion, _bring_to_front, _play_sound
run_test("import notify module", test_import_notify)


# [2] bring_to_front
print("\n[2] _bring_to_front")

def test_bring_to_front_no_crash():
    from computer_use_agent.notify import _bring_to_front
    _bring_to_front()  # should not crash
run_test("_bring_to_front no crash", test_bring_to_front_no_crash)

def test_bring_to_front_returns():
    from computer_use_agent.notify import _bring_to_front
    result = _bring_to_front()
    # function returns None, just verify no exception
    assert result is None
run_test("_bring_to_front returns None", test_bring_to_front_returns)


# [3] play_sound
print("\n[3] _play_sound")

def test_play_sound_no_crash():
    from computer_use_agent.notify import _play_sound
    _play_sound()  # should not crash even if no audio device
run_test("_play_sound no crash", test_play_sound_no_crash)


# [4] notify_completion
print("\n[4] notify_completion")

def test_notify_completion_no_crash():
    from computer_use_agent.notify import notify_completion
    notify_completion()  # full notification flow
run_test("notify_completion no crash", test_notify_completion_no_crash)


# [5] CLI integration
print("\n[5] CLI integration")

def test_cli_imports_notify():
    from computer_use_agent.cli import CLI
    # Verify CLI module can be imported (notify is imported lazily inside _run_task)
    assert CLI is not None
run_test("CLI imports with notify", test_cli_imports_notify)


# [6] Platform detection
print("\n[6] Platform detection")

def test_platform_is_windows():
    assert sys.platform == "win32"
run_test("platform is Windows", test_platform_is_windows)

def test_ctypes_available():
    import ctypes
    assert hasattr(ctypes.windll, "kernel32")
    assert hasattr(ctypes.windll, "user32")
run_test("ctypes.windll available", test_ctypes_available)

def test_winsound_available():
    import winsound
    assert hasattr(winsound, "MessageBeep")
    assert hasattr(winsound, "MB_ICONASTERISK")
run_test("winsound available", test_winsound_available)


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
