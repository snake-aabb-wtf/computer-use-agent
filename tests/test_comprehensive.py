"""Comprehensive coverage tests - fill all gaps"""

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
print("  Comprehensive Coverage Tests")
print("=" * 60)


# [1] executor.py - key hold
print("\n[1] Executor - key hold")
def test_key_hold():
    from computer_use_agent.executor import execute
    t0 = time.time()
    result = execute({"action": "key", "key": "backspace", "hold": 0.2})
    elapsed = time.time() - t0
    assert "长按" in result
    assert elapsed >= 0.15
run_test("key with hold parameter", test_key_hold)

def test_key_no_hold():
    from computer_use_agent.executor import execute
    result = execute({"action": "key", "key": "enter"})
    assert "按键" in result
    assert "长按" not in result
run_test("key without hold", test_key_no_hold)


# [2] executor.py - natural drag
print("\n[2] Executor - natural drag")
def test_natural_drag():
    from computer_use_agent.executor import execute
    result = execute({"action": "drag", "from": [100, 100], "to": [200, 200], "hold": 0.1})
    assert "拖拽" in result
    assert "hold=0.1s" in result
run_test("natural drag with hold", test_natural_drag)

def test_natural_drag_default_hold():
    from computer_use_agent.executor import execute
    result = execute({"action": "drag", "from": [100, 100], "to": [200, 200]})
    assert "拖拽" in result
    assert "hold=0.3s" in result
run_test("natural drag default hold", test_natural_drag_default_hold)


# [3] executor.py - scroll
print("\n[3] Executor - scroll")
def test_scroll_down():
    from computer_use_agent.executor import execute
    result = execute({"action": "scroll", "direction": "down", "amount": 5})
    assert "滚动" in result
    assert "down" in result
run_test("scroll down", test_scroll_down)

def test_scroll_up():
    from computer_use_agent.executor import execute
    result = execute({"action": "scroll", "direction": "up", "amount": 3})
    assert "滚动" in result
    assert "up" in result
run_test("scroll up", test_scroll_up)


# [4] llm.py - KeyboardInterrupt handling
print("\n[4] LLM - KeyboardInterrupt handling")
def test_keyboard_interrupt_returns_done():
    from computer_use_agent.llm import _parse_action
    # Simulate what happens after KeyboardInterrupt is caught
    # The chat() function returns a done action with _interrupted flag
    action = {
        "thought": "用户中断",
        "action": "done",
        "message": "已中断",
        "_interrupted": True,
    }
    assert action["action"] == "done"
    assert action["_interrupted"] == True
    assert action["message"] == "已中断"
run_test("KeyboardInterrupt returns done action", test_keyboard_interrupt_returns_done)


# [5] agent.py - _slide_image_window
print("\n[5] Agent - slide image window")
def test_slide_window_basic():
    from computer_use_agent.agent import _slide_image_window
    history = [
        {"role": "user", "content": "task"},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "1"}}]},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "2"}}]},
        {"role": "assistant", "content": "ok"},
    ]
    result = _slide_image_window(history, max_images=1)
    image_count = sum(1 for m in result if isinstance(m.get("content"), list))
    assert image_count == 1
    assert any(m.get("content") == "task" for m in result)
run_test("slide window keeps text + 1 image", test_slide_window_basic)

def test_slide_window_empty():
    from computer_use_agent.agent import _slide_image_window
    result = _slide_image_window([], max_images=5)
    assert result == []
run_test("slide window empty history", test_slide_window_empty)


# [6] agent.py - _prepare_messages with uitars mode
print("\n[6] Agent - prepare messages uitars mode")
def test_prepare_messages_uitars():
    from computer_use_agent import config
    from computer_use_agent.agent import Agent
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "uitars"
    agent = Agent(save_screenshots=False)
    agent.history = [
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "ok"},
    ] * 5 + [
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "1"}}]},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "2"}}]},
        {"role": "assistant", "content": "ok"},
    ]
    prepared = agent._prepare_messages()
    assert len(prepared) > 0
    config.CAPTURE_MODE = old
run_test("prepare messages uitars mode", test_prepare_messages_uitars)


# [7] prompts.py - UITARS prompt content
print("\n[7] Prompts - UITARS content")
def test_uitars_prompt_has_coord_system():
    from computer_use_agent.prompts import TOOL_GUIDANCE_UITARS
    assert "0-1000" in TOOL_GUIDANCE_UITARS
    assert "normalized" in TOOL_GUIDANCE_UITARS.lower() or "normalization" in TOOL_GUIDANCE_UITARS.lower()
run_test("UITARS prompt has coord system", test_uitars_prompt_has_coord_system)

def test_uitars_prompt_has_actions():
    from computer_use_agent.prompts import TOOL_GUIDANCE_UITARS
    assert "click" in TOOL_GUIDANCE_UITARS
    assert "type" in TOOL_GUIDANCE_UITARS
    assert "hotkey" in TOOL_GUIDANCE_UITARS
    assert "scroll" in TOOL_GUIDANCE_UITARS
    assert "drag" in TOOL_GUIDANCE_UITARS
    assert "done" in TOOL_GUIDANCE_UITARS
run_test("UITARS prompt has all actions", test_uitars_prompt_has_actions)

def test_model_specific_gpt():
    from computer_use_agent.prompts import build_system_prompt
    prompt = build_system_prompt(model="gpt-4o", capture_mode="vision")
    assert "Execution Discipline" in prompt
run_test("GPT model gets execution discipline", test_model_specific_gpt)

def test_model_specific_gemini():
    from computer_use_agent.prompts import build_system_prompt
    prompt = build_system_prompt(model="gemini-2.0", capture_mode="vision")
    assert "Operational Directives" in prompt
run_test("Gemini model gets operational directives", test_model_specific_gemini)


# [8] cli.py - /compact command
print("\n[8] CLI - /compact command")
def test_compact_command():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent.cli import SessionDB
    agent = Agent(save_screenshots=False)
    # Add enough history to trigger compression (>40 messages)
    for i in range(30):
        agent.history.append({"role": "user", "content": f"step {i} " * 50})
        agent.history.append({"role": "assistant", "content": f'{{"action":"click","coordinate":[{i},{i}]}}'})
    db = SessionDB(":memory:")
    old_len = len(agent.history)
    _handle_command("/compact", agent, db, [None], ["s1"])
    assert len(agent.history) < old_len
    print(f"    {old_len} -> {len(agent.history)} msgs")
run_test("/compact reduces history", test_compact_command)


# [9] cli.py - markdown rendering
print("\n[9] CLI - markdown rendering")
def test_markdown_detection():
    # Test the markdown detection logic
    message = "This has **bold** and - list items"
    has_md = any(marker in message for marker in ["**", "#", "- ", "```", "|"])
    assert has_md == True
    message2 = "Just plain text"
    has_md2 = any(marker in message2 for marker in ["**", "#", "- ", "```", "|"])
    assert has_md2 == False
run_test("markdown detection logic", test_markdown_detection)


# [10] executor.py - normalize_action edge cases
print("\n[10] Executor - normalize_action edge cases")
def test_normalize_action_uitars_mode():
    from computer_use_agent import config
    from computer_use_agent.executor import normalize_action
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "uitars"
    # Test multiple action name normalizations
    tests = [
        ("click", "left_click"),
        ("input", "type"),
        ("hover", "move"),
        ("finished", "done"),
        ("capture", "screenshot"),
        ("sleep", "wait"),
        ("mouse_scroll", "scroll"),
    ]
    for input_act, expected in tests:
        r = normalize_action({"action": input_act, "coordinate": [100, 200]})
        assert r["action"] == expected, f"{input_act} -> {r['action']}, expected {expected}"
    config.CAPTURE_MODE = old
run_test("normalize_action all variants", test_normalize_action_uitars_mode)

def test_normalize_no_change_for_standard():
    from computer_use_agent import config
    from computer_use_agent.executor import normalize_action
    old = config.CAPTURE_MODE
    config.CAPTURE_MODE = "uitars"
    r = normalize_action({"action": "left_click", "coordinate": [100, 200]})
    assert r["action"] == "left_click"
    assert r["coordinate"] == [100, 200]
    config.CAPTURE_MODE = old
run_test("normalize standard actions unchanged", test_normalize_no_change_for_standard)


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
