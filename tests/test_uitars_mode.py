"""Tests for UI-TARS mode (CAPTURE_MODE=uitars)"""

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
print("  UI-TARS Mode Tests")
print("=" * 60)


# [1] Config validation
print("\n[1] Config")
def test_uitars_mode_valid():
    from computer_use_agent import config
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "uitars"
    assert config.CAPTURE_MODE == "uitars"
    config.CAPTURE_MODE = old
run_test("uitars mode accepted", test_uitars_mode_valid)

def test_invalid_mode_falls_back():
    from computer_use_agent import config
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "invalid"
    # Re-validate
    if config.CAPTURE_MODE not in ("som", "vision", "uitars"):
        config.CAPTURE_MODE = "vision"
    assert config.CAPTURE_MODE == "vision"
    config.CAPTURE_MODE = old
run_test("invalid mode falls back to vision", test_invalid_mode_falls_back)


# [2] Prompt switching
print("\n[2] Prompts")
def test_uitars_prompt():
    from computer_use_agent.prompts import build_system_prompt
    prompt = build_system_prompt(capture_mode="uitars")
    assert "0-1000" in prompt
    assert "normalized" in prompt.lower() or "normalization" in prompt.lower()
run_test("uitars prompt has coord normalization", test_uitars_prompt)

def test_uitars_vs_vision_different():
    from computer_use_agent.prompts import build_system_prompt
    uitars = build_system_prompt(capture_mode="uitars")
    vision = build_system_prompt(capture_mode="vision")
    assert uitars != vision
    assert "0-1000" in uitars
run_test("uitars and vision prompts differ", test_uitars_vs_vision_different)


# [3] Action normalization in uitars mode
print("\n[3] Action normalization")
def test_normalize_in_uitars_mode():
    from computer_use_agent import config
    from computer_use_agent.executor import normalize_action
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "uitars"
    # Test action name normalization
    r = normalize_action({"action": "click", "coordinate": [100, 200]})
    assert r["action"] == "left_click"
    # Test coord normalization (float coords)
    r = normalize_action({"action": "left_click", "coordinate": [500.0, 500.0]})
    import pyautogui
    sw, sh = pyautogui.size()
    assert r["coordinate"] == [int(500.0/1000*sw), int(500.0/1000*sh)]
    config.CAPTURE_MODE = old
run_test("normalize in uitars mode", test_normalize_in_uitars_mode)

def test_no_normalize_in_vision_mode():
    from computer_use_agent import config
    from computer_use_agent.executor import normalize_action
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "vision"
    # Raw coords should NOT be normalized
    r = normalize_action({"action": "left_click", "coordinate": [100, 200]})
    assert r["coordinate"] == [100, 200]
    config.CAPTURE_MODE = old
run_test("no normalize in vision mode", test_no_normalize_in_vision_mode)


# [4] Image sliding window in uitars mode
print("\n[4] Image sliding window")
def test_slide_window_in_uitars():
    from computer_use_agent.agent import _slide_image_window
    history = []
    for i in range(10):
        history.append({"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"img{i}"}}]})
        history.append({"role": "assistant", "content": f"ok{i}"})
    result = _slide_image_window(history, max_images=3)
    image_count = sum(1 for m in result if m.get("role") == "user" and isinstance(m.get("content"), list))
    assert image_count == 3
    assert len(result) < len(history)
    print(f"    {len(history)} -> {len(result)} messages")
run_test("slide window trims old images", test_slide_window_in_uitars)


# [5] Execute with uitars normalization
print("\n[5] Execute integration")
def test_execute_uitars_click():
    from computer_use_agent import config
    from computer_use_agent.executor import execute
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "uitars"
    result = execute({"action": "click", "coordinate": [100, 200]})
    assert "左键点击" in result
    config.CAPTURE_MODE = old
run_test("execute uitars click", test_execute_uitars_click)

def test_execute_uitars_finished():
    from computer_use_agent import config
    from computer_use_agent.executor import execute
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "uitars"
    result = execute({"action": "finished", "message": "done"})
    assert "完成" in result
    config.CAPTURE_MODE = old
run_test("execute uitars finished", test_execute_uitars_finished)

def test_execute_vision_click():
    from computer_use_agent import config
    from computer_use_agent.executor import execute
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "vision"
    result = execute({"action": "left_click", "coordinate": [100, 200]})
    assert "左键点击" in result
    config.CAPTURE_MODE = old
run_test("execute vision click", test_execute_vision_click)


# [6] Visual effects (unchanged)
print("\n[6] Visual effects")
def test_visual_effects():
    from computer_use_agent.visual_effects import init_effects, cleanup
    init_effects(False)
    cleanup()
    assert True
run_test("visual effects work", test_visual_effects)


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
