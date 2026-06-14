"""Tests for UI-TARS patterns (normalization, sliding window)"""

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
print("  UI-TARS Patterns Tests")
print("=" * 60)


# [1] Action Name Normalization
print("\n[1] Action name normalization")

def test_normalize_click():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "click", "coordinate": [100, 200]})
    assert r["action"] == "left_click"
run_test("normalize: click -> left_click", test_normalize_click)

def test_normalize_left_single():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "left_single", "coordinate": [100, 200]})
    assert r["action"] == "left_click"
run_test("normalize: left_single -> left_click", test_normalize_left_single)

def test_normalize_double_click():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "double_click", "coordinate": [100, 200]})
    assert r["action"] == "double_click"
run_test("normalize: double_click stays", test_normalize_double_click)

def test_normalize_right_click():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "right_click", "coordinate": [100, 200]})
    assert r["action"] == "right_click"
run_test("normalize: right_click stays", test_normalize_right_click)

def test_normalize_type():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "type", "text": "hello"})
    assert r["action"] == "type"
run_test("normalize: type stays", test_normalize_type)

def test_normalize_input():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "input", "text": "hello"})
    assert r["action"] == "type"
run_test("normalize: input -> type", test_normalize_input)

def test_normalize_hotkey():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "hotkey", "keys": ["ctrl", "c"]})
    assert r["action"] == "hotkey"
run_test("normalize: hotkey stays", test_normalize_hotkey)

def test_normalize_finished():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "finished", "message": "done"})
    assert r["action"] == "done"
run_test("normalize: finished -> done", test_normalize_finished)

def test_normalize_complete():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "complete", "message": "done"})
    assert r["action"] == "done"
run_test("normalize: complete -> done", test_normalize_complete)

def test_normalize_wait():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "wait", "seconds": 2})
    assert r["action"] == "wait"
run_test("normalize: wait stays", test_normalize_wait)

def test_normalize_capture():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "capture"})
    assert r["action"] == "screenshot"
run_test("normalize: capture -> screenshot", test_normalize_capture)

def test_normalize_scroll():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "mouse_scroll", "direction": "down", "amount": 3})
    assert r["action"] == "scroll"
run_test("normalize: mouse_scroll -> scroll", test_normalize_scroll)

def test_normalize_drag():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "drag", "from": [100, 100], "to": [200, 200]})
    assert r["action"] == "drag"
run_test("normalize: drag stays", test_normalize_drag)

def test_normalize_move():
    from computer_use_agent.executor import normalize_action
    r = normalize_action({"action": "hover", "coordinate": [500, 500]})
    assert r["action"] == "move"
run_test("normalize: hover -> move", test_normalize_move)


# [2] Coordinate Normalization
print("\n[2] Coordinate normalization")

def test_normalize_coords_raw():
    from computer_use_agent.executor import normalize_action
    # Raw pixel coords (small values) should stay as-is
    r = normalize_action({"action": "left_click", "coordinate": [100, 200]})
    assert r["coordinate"] == [100, 200]
run_test("normalize: raw coords stay", test_normalize_coords_raw)

def test_normalize_coords_01000():
    from computer_use_agent.executor import normalize_action
    import pyautogui
    sw, sh = pyautogui.size()
    # 0-1000 normalized coords should be converted
    r = normalize_action({"action": "left_click", "coordinate": [500.0, 500.0]})
    expected_x = int(500.0 / 1000 * sw)
    expected_y = int(500.0 / 1000 * sh)
    assert r["coordinate"] == [expected_x, expected_y], f"got {r['coordinate']}"
run_test("normalize: 0-1000 coords converted", test_normalize_coords_01000)

def test_normalize_coords_mixed():
    from computer_use_agent.executor import normalize_action
    # Mix of normalized and pixel coords
    r = normalize_action({"action": "left_click", "coordinate": [500.0, 200]})
    # x=500.0 is float in 0-1000 range -> converted
    # y=200 is int, might be pixel -> stays
    assert "coordinate" in r
run_test("normalize: mixed coords handled", test_normalize_coords_mixed)

def test_normalize_drag_coords():
    from computer_use_agent.executor import normalize_action
    import pyautogui
    sw, sh = pyautogui.size()
    r = normalize_action({"action": "drag", "from": [100.0, 100.0], "to": [500.0, 500.0]})
    assert r["from"][0] == int(100.0 / 1000 * sw)
    assert r["to"][0] == int(500.0 / 1000 * sw)
run_test("normalize: drag coords converted", test_normalize_drag_coords)


# [3] Image Sliding Window
print("\n[3] Image sliding window")

def test_slide_window_no_images():
    from computer_use_agent.agent import _slide_image_window
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "ok"},
    ]
    result = _slide_image_window(history, max_images=3)
    assert len(result) == 2
run_test("slide_window: no images unchanged", test_slide_window_no_images)

def test_slide_window_few_images():
    from computer_use_agent.agent import _slide_image_window
    history = [
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "img1"}}]},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "img2"}}]},
        {"role": "assistant", "content": "ok"},
    ]
    result = _slide_image_window(history, max_images=5)
    assert len(result) == 4  # all kept
run_test("slide_window: few images unchanged", test_slide_window_few_images)

def test_slide_window_many_images():
    from computer_use_agent.agent import _slide_image_window
    history = []
    for i in range(10):
        history.append({"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"img{i}"}}]})
        history.append({"role": "assistant", "content": f"ok{i}"})
    result = _slide_image_window(history, max_images=3)
    # Should keep only last 3 images + their responses
    image_count = sum(1 for m in result if m.get("role") == "user" and isinstance(m.get("content"), list))
    assert image_count == 3
    assert len(result) < len(history)
run_test("slide_window: many images trimmed", test_slide_window_many_images)

def test_slide_window_preserves_text():
    from computer_use_agent.agent import _slide_image_window
    history = [
        {"role": "user", "content": "initial task"},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "img1"}}]},
        {"role": "assistant", "content": "ok"},
    ]
    result = _slide_image_window(history, max_images=1)
    # Text message should be preserved
    assert any(m.get("content") == "initial task" for m in result)
run_test("slide_window: preserves text messages", test_slide_window_preserves_text)


# [4] Integration
print("\n[4] Integration")

def test_normalize_in_execute():
    from computer_use_agent.executor import execute
    # Test with normalized action name
    result = execute({"action": "click", "coordinate": [100, 200]})
    assert "左键点击" in result
run_test("execute: normalized action works", test_normalize_in_execute)

def test_finished_action():
    from computer_use_agent.executor import execute
    result = execute({"action": "finished", "message": "task done"})
    assert "完成" in result
run_test("execute: finished action", test_finished_action)


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
