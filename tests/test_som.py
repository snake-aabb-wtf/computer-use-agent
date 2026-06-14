"""SOM 模式全面自动化测试"""

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
print("  SOM Mode Tests")
print("=" * 60)


# ═══════════════════════════════════════════════════════════
# [1] UIElement 数据类
# ═══════════════════════════════════════════════════════════
print("\n[1] UIElement dataclass")

def test_uielement_center():
    from computer_use_agent.uia_tree import UIElement
    elem = UIElement(index=1, role="Button", label="OK", bounds=(100, 200, 80, 30))
    cx, cy = elem.center()
    assert cx == 140, f"center x: {cx}"
    assert cy == 215, f"center y: {cy}"
run_test("UIElement.center()", test_uielement_center)

def test_uielement_description():
    from computer_use_agent.uia_tree import UIElement
    elem = UIElement(index=5, role="Button", label="Submit", bounds=(10, 20, 80, 30))
    desc = elem.description()
    assert "[5]" in desc
    assert "Button" in desc
    assert "Submit" in desc
    assert "(10,20)" in desc
run_test("UIElement.description()", test_uielement_description)

def test_uielement_description_no_label():
    from computer_use_agent.uia_tree import UIElement
    elem = UIElement(index=1, role="Panel", label="", bounds=(0, 0, 100, 50))
    desc = elem.description()
    assert "[1]" in desc
    assert "Panel" in desc
run_test("UIElement.description() no label", test_uielement_description_no_label)


# ═══════════════════════════════════════════════════════════
# [2] render_som - SOM 覆盖层渲染
# ═══════════════════════════════════════════════════════════
print("\n[2] render_som")

def test_render_som_basic():
    from computer_use_agent.uia_tree import UIElement, render_som
    from PIL import Image
    img = Image.new("RGB", (800, 600), "white")
    elements = [
        UIElement(1, "Button", "OK", (100, 100, 80, 30)),
        UIElement(2, "TextField", "Name", (100, 200, 200, 25)),
    ]
    overlay = render_som(img, elements)
    assert overlay.size == (800, 600)
    assert overlay.mode == "RGB"
run_test("render_som basic", test_render_som_basic)

def test_render_som_empty():
    from computer_use_agent.uia_tree import render_som
    from PIL import Image
    img = Image.new("RGB", (800, 600), "white")
    overlay = render_som(img, [])
    assert overlay.size == (800, 600)
run_test("render_som empty elements", test_render_som_empty)

def test_render_som_out_of_bounds():
    from computer_use_agent.uia_tree import UIElement, render_som
    from PIL import Image
    img = Image.new("RGB", (800, 600), "white")
    elements = [
        UIElement(1, "Button", "OK", (-100, -100, 80, 30)),  # out of bounds
        UIElement(2, "Button", "Cancel", (900, 900, 80, 30)),  # out of bounds
        UIElement(3, "Button", "Valid", (100, 100, 80, 30)),  # in bounds
    ]
    overlay = render_som(img, elements)
    assert overlay.size == (800, 600)
run_test("render_som skips out-of-bounds", test_render_som_out_of_bounds)

def test_render_som_max_elements():
    from computer_use_agent.uia_tree import UIElement, render_som
    from PIL import Image
    img = Image.new("RGB", (800, 600), "white")
    elements = [UIElement(i, "Button", f"B{i}", (10, 10, 50, 20)) for i in range(200)]
    overlay = render_som(img, elements, max_elements=50)
    assert overlay.size == (800, 600)
run_test("render_som respects max_elements", test_render_som_max_elements)


# ═══════════════════════════════════════════════════════════
# [3] image_to_base64 / format_elements_text
# ═══════════════════════════════════════════════════════════
print("\n[3] Utilities")

def test_image_to_base64():
    from computer_use_agent.uia_tree import image_to_base64
    from PIL import Image
    import base64
    img = Image.new("RGB", (100, 100), "red")
    b64 = image_to_base64(img)
    assert isinstance(b64, str)
    decoded = base64.b64decode(b64)
    assert decoded[:4] == b'\x89PNG'
run_test("image_to_base64 returns valid PNG", test_image_to_base64)

def test_format_elements_text():
    from computer_use_agent.uia_tree import UIElement, format_elements_text
    elements = [
        UIElement(1, "Button", "OK", (100, 200, 80, 30)),
        UIElement(2, "TextField", "Name", (100, 300, 200, 25)),
    ]
    text = format_elements_text(elements)
    assert "[1]" in text
    assert "[2]" in text
    assert "Button" in text
    assert "TextField" in text
run_test("format_elements_text", test_format_elements_text)

def test_format_elements_text_max():
    from computer_use_agent.uia_tree import UIElement, format_elements_text
    elements = [UIElement(i, "Button", f"B{i}", (0, 0, 10, 10)) for i in range(50)]
    text = format_elements_text(elements, max_elements=5)
    assert text.count("[") == 5
run_test("format_elements_text max_elements", test_format_elements_text_max)


# ═══════════════════════════════════════════════════════════
# [4] get_elements - UIA 获取
# ═══════════════════════════════════════════════════════════
print("\n[4] get_elements (UIA)")

def test_get_elements_returns_list():
    from computer_use_agent.uia_tree import get_elements
    result = get_elements(max_elements=10)
    assert isinstance(result, list)
    print(f"    Found {len(result)} elements")
run_test("get_elements returns list", test_get_elements_returns_list)

def test_get_elements_returns_uielements():
    from computer_use_agent.uia_tree import get_elements, UIElement
    elements = get_elements(max_elements=5)
    for elem in elements:
        assert isinstance(elem, UIElement)
        assert elem.index > 0
        assert elem.role
        assert len(elem.bounds) == 4
run_test("get_elements returns UIElement objects", test_get_elements_returns_uielements)

def test_get_elements_sorted():
    from computer_use_agent.uia_tree import get_elements
    elements = get_elements(max_elements=50)
    if len(elements) > 1:
        for i in range(1, len(elements)):
            prev_y = elements[i-1].bounds[1]
            curr_y = elements[i].bounds[1]
            if prev_y == curr_y:
                assert elements[i-1].bounds[0] <= elements[i].bounds[0]
            else:
                assert prev_y <= curr_y
run_test("get_elements sorted by position", test_get_elements_sorted)


# ═══════════════════════════════════════════════════════════
# [5] executor - element=N 点击
# ═══════════════════════════════════════════════════════════
print("\n[5] executor element click")

def test_resolve_click_element():
    from computer_use_agent.executor import _resolve_click_target, set_som_elements
    from computer_use_agent.uia_tree import UIElement
    set_som_elements([
        UIElement(1, "Button", "OK", (100, 200, 80, 30)),
        UIElement(2, "Button", "Cancel", (300, 400, 80, 30)),
    ])
    x, y = _resolve_click_target({"action": "left_click", "element": 1})
    assert x == 140
    assert y == 215
    x, y = _resolve_click_target({"action": "left_click", "element": 2})
    assert x == 340
    assert y == 415
run_test("resolve_click_target by element", test_resolve_click_element)

def test_resolve_click_coordinate():
    from computer_use_agent.executor import _resolve_click_target, set_som_elements
    set_som_elements([])
    x, y = _resolve_click_target({"action": "left_click", "coordinate": [500, 300]})
    assert x == 500
    assert y == 300
run_test("resolve_click_target by coordinate", test_resolve_click_coordinate)

def test_resolve_click_element_not_found():
    from computer_use_agent.executor import _resolve_click_target, set_som_elements
    set_som_elements([])
    x, y = _resolve_click_target({"action": "left_click", "element": 999})
    import pyautogui
    w, h = pyautogui.size()
    assert x == w // 2
    assert y == h // 2
run_test("resolve_click_target element not found fallback", test_resolve_click_element_not_found)

def test_set_som_elements():
    from computer_use_agent.executor import set_som_elements, _som_elements
    set_som_elements([1, 2, 3])
    from computer_use_agent.executor import _som_elements as elems
    assert len(elems) == 3
run_test("set_som_elements", test_set_som_elements)


# ═══════════════════════════════════════════════════════════
# [6] screen - capture_som
# ═══════════════════════════════════════════════════════════
print("\n[6] screen.capture_som")

def test_capture_som():
    from computer_use_agent.screen import capture_som
    b64, elements, text = capture_som()
    assert isinstance(b64, str)
    assert len(b64) > 100
    assert isinstance(elements, list)
    assert isinstance(text, str)
    print(f"    elements: {len(elements)}, b64: {len(b64)} chars")
run_test("capture_som returns (b64, elements, text)", test_capture_som)

def test_capture_som_elements_are_uielements():
    from computer_use_agent.screen import capture_som
    from computer_use_agent.uia_tree import UIElement
    _, elements, _ = capture_som()
    for elem in elements:
        assert isinstance(elem, UIElement)
run_test("capture_som elements are UIElement", test_capture_som_elements_are_uielements)


# ═══════════════════════════════════════════════════════════
# [7] prompts - SOM/Vision 模式切换
# ═══════════════════════════════════════════════════════════
print("\n[7] prompts mode switching")

def test_som_prompt_contains_element():
    from computer_use_agent.prompts import build_system_prompt
    prompt = build_system_prompt(capture_mode="som")
    assert "element" in prompt
    assert "SOM" in prompt
    assert "red SOM overlay" in prompt or "numbered overlay" in prompt or "element number" in prompt
run_test("SOM prompt mentions element", test_som_prompt_contains_element)

def test_vision_prompt_no_element():
    from computer_use_agent.prompts import build_system_prompt
    prompt = build_system_prompt(capture_mode="vision")
    assert "coordinate" in prompt
    assert "element" not in prompt.lower() or "element index" not in prompt.lower()
run_test("Vision prompt no element", test_vision_prompt_no_element)

def test_som_vs_vision_different():
    from computer_use_agent.prompts import build_system_prompt
    som = build_system_prompt(capture_mode="som")
    vis = build_system_prompt(capture_mode="vision")
    assert som != vis
    # SOM should have element guidance
    assert "element" in som
    # Vision should have coordinate guidance
    assert "coordinate" in vis
run_test("SOM and Vision prompts are different", test_som_vs_vision_different)

def test_model_specific_prompt():
    from computer_use_agent.prompts import build_system_prompt
    prompt_gpt = build_system_prompt(model="gpt-4o", capture_mode="vision")
    prompt_other = build_system_prompt(model="mimo-v2.5", capture_mode="vision")
    assert len(prompt_gpt) > len(prompt_other)
    assert "Execution Discipline" in prompt_gpt
run_test("GPT model gets extra guidance", test_model_specific_prompt)


# ═══════════════════════════════════════════════════════════
# [8] config - CAPTURE_MODE
# ═══════════════════════════════════════════════════════════
print("\n[8] config CAPTURE_MODE")

def test_capture_mode_config():
    from computer_use_agent import config
    assert hasattr(config, "CAPTURE_MODE")
    assert config.CAPTURE_MODE in ("som", "vision")
    print(f"    CAPTURE_MODE: {config.CAPTURE_MODE}")
run_test("config has CAPTURE_MODE", test_capture_mode_config)


# ═══════════════════════════════════════════════════════════
# [9] Integration - SOM agent flow
# ═══════════════════════════════════════════════════════════
print("\n[9] Integration")

def test_agent_uses_som_in_som_mode():
    from computer_use_agent import config
    from computer_use_agent.prompts import build_system_prompt
    old_mode = config.CAPTURE_MODE
    config.CAPTURE_MODE = "som"
    prompt = build_system_prompt(1366, 768, "mimo-v2.5", "som")
    assert "element" in prompt
    config.CAPTURE_MODE = old_mode
run_test("agent SOM mode uses element prompt", test_agent_uses_som_in_som_mode)

def test_agent_uses_vision_in_vision_mode():
    from computer_use_agent import config
    from computer_use_agent.prompts import build_system_prompt
    old_mode = config.CAPTURE_MODE
    config.CAPTURE_MODE = "vision"
    prompt = build_system_prompt(1366, 768, "mimo-v2.5", "vision")
    assert "coordinate" in prompt
    config.CAPTURE_MODE = old_mode
run_test("agent Vision mode uses coordinate prompt", test_agent_uses_vision_in_vision_mode)

def test_full_som_pipeline():
    from computer_use_agent.screen import capture_som
    from computer_use_agent.executor import set_som_elements, _resolve_click_target
    from computer_use_agent.prompts import build_system_prompt
    from computer_use_agent import config

    # 1. Capture SOM
    b64, elements, text = capture_som()
    assert len(b64) > 100

    # 2. Set elements for executor
    set_som_elements(elements)

    # 3. Build SOM prompt
    prompt = build_system_prompt(1366, 768, config.LLM_MODEL, "som")
    assert "element" in prompt

    # 4. If elements exist, resolve a click
    if elements:
        elem = elements[0]
        x, y = _resolve_click_target({"action": "left_click", "element": elem.index})
        assert x > 0 and y > 0
        print(f"    Full pipeline OK: {len(elements)} elements, click at ({x},{y})")
    else:
        print("    Full pipeline OK: no elements found (normal if no windows)")
run_test("full SOM pipeline", test_full_som_pipeline)


# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
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
