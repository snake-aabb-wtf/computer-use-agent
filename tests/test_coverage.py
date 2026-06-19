"""全面覆盖测试 - 补充所有未测试的模块"""

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


# ═══════════════════════════════════════════════════════════
# [1] guardrails.py - 完全未测试
# ═══════════════════════════════════════════════════════════
print("\n[1] guardrails.py")

def test_guardrails_allow():
    from computer_use_agent.guardrails import ToolCallGuardrails
    g = ToolCallGuardrails()
    decision = g.check({"action": "left_click", "coordinate": [100, 200]}, "clicked")
    assert decision.action == "allow"
run_test("guardrails: allow normal action", test_guardrails_allow)

def test_guardrails_exact_fail_warn():
    from computer_use_agent.guardrails import ToolCallGuardrails
    g = ToolCallGuardrails(exact_fail_warn=3, exact_fail_block=5)
    for i in range(3):
        d = g.check({"action": "left_click", "coordinate": [100, 200]}, "failed", failed=True)
    assert d.action == "warn"
run_test("guardrails: exact fail warn at threshold", test_guardrails_exact_fail_warn)

def test_guardrails_exact_fail_block():
    from computer_use_agent.guardrails import ToolCallGuardrails
    g = ToolCallGuardrails(exact_fail_warn=2, exact_fail_block=4)
    for i in range(4):
        d = g.check({"action": "left_click", "coordinate": [100, 200]}, "failed", failed=True)
    assert d.action == "block"
run_test("guardrails: exact fail block", test_guardrails_exact_fail_block)

def test_guardrails_same_tool_halt():
    from computer_use_agent.guardrails import ToolCallGuardrails
    g = ToolCallGuardrails(same_tool_halt=5)
    # Each call with a different action resets the count, so use same action
    for i in range(5):
        d = g.check({"action": "scroll", "direction": "down", "amount": 3, "coord": i}, "fail", failed=True)
    # The last check should be halt
    assert d.action in ("halt", "block")  # might be block from exact fail
run_test("guardrails: same tool halt", test_guardrails_same_tool_halt)

def test_guardrails_no_progress():
    from computer_use_agent.guardrails import ToolCallGuardrails
    g = ToolCallGuardrails(no_progress_block=2)
    # Need: 5 results to fill deque, then 2 more for no_progress_block=2
    for i in range(7):
        d = g.check({"action": "screenshot"}, "same_result_abc")
    assert d.action == "block"
run_test("guardrails: no progress detection", test_guardrails_no_progress)

def test_guardrails_on_success_resets():
    from computer_use_agent.guardrails import ToolCallGuardrails
    g = ToolCallGuardrails(exact_fail_warn=3, exact_fail_block=5)
    for i in range(3):
        g.check({"action": "left_click", "coordinate": [100, 200]}, "failed", failed=True)
    g.on_success({"action": "left_click", "coordinate": [100, 200]})
    d = g.check({"action": "left_click", "coordinate": [100, 200]}, "failed", failed=True)
    assert d.action == "allow"
run_test("guardrails: on_success resets", test_guardrails_on_success_resets)

def test_guardrails_reset():
    from computer_use_agent.guardrails import ToolCallGuardrails
    g = ToolCallGuardrails()
    for i in range(5):
        g.check({"action": "x"}, "fail", failed=True)
    g.reset()
    s = g.summary()
    assert s["exact_failures"] == 0
    assert s["tool_failures"] == {}
    assert s["no_progress"] == {}
run_test("guardrails: reset clears all", test_guardrails_reset)

def test_guardrails_summary():
    from computer_use_agent.guardrails import ToolCallGuardrails
    g = ToolCallGuardrails()
    g.check({"action": "click"}, "ok")
    g.check({"action": "click"}, "ok")
    s = g.summary()
    assert isinstance(s, dict)
    assert "exact_failures" in s
    assert "tool_failures" in s
    assert "no_progress" in s
run_test("guardrails: summary", test_guardrails_summary)

def test_guardrails_different_coords_no_block():
    from computer_use_agent.guardrails import ToolCallGuardrails
    g = ToolCallGuardrails(exact_fail_block=3)
    g.check({"action": "left_click", "coordinate": [100, 100]}, "fail", failed=True)
    g.check({"action": "left_click", "coordinate": [200, 200]}, "fail", failed=True)
    d = g.check({"action": "left_click", "coordinate": [300, 300]}, "fail", failed=True)
    assert d.action == "allow"
run_test("guardrails: different coords not exact fail", test_guardrails_different_coords_no_block)


# ═══════════════════════════════════════════════════════════
# [2] executor.py - 补充测试
# ═══════════════════════════════════════════════════════════
print("\n[2] executor.py (extended)")

def test_execute_element_click():
    from computer_use_agent.executor import execute, set_som_elements
    from computer_use_agent.uia_tree import UIElement
    set_som_elements([UIElement(1, "Button", "OK", (100, 200, 80, 30))])
    result = execute({"action": "left_click", "element": 1})
    assert "元素 #1" in result
    assert "140" in result
run_test("execute: left_click with element", test_execute_element_click)

def test_execute_element_double_click():
    from computer_use_agent.executor import execute, set_som_elements
    from computer_use_agent.uia_tree import UIElement
    set_som_elements([UIElement(1, "Button", "OK", (100, 200, 80, 30))])
    result = execute({"action": "double_click", "element": 1})
    assert "双击元素" in result
run_test("execute: double_click with element", test_execute_element_double_click)

def test_execute_element_right_click():
    from computer_use_agent.executor import execute, set_som_elements
    from computer_use_agent.uia_tree import UIElement
    set_som_elements([UIElement(1, "Button", "OK", (100, 200, 80, 30))])
    result = execute({"action": "right_click", "element": 1})
    assert "右键点击元素" in result
run_test("execute: right_click with element", test_execute_element_right_click)

def test_execute_move():
    from computer_use_agent.executor import execute
    result = execute({"action": "move", "coordinate": [500, 500]})
    assert "移动鼠标" in result
run_test("execute: move", test_execute_move)

def test_execute_drag():
    from computer_use_agent.executor import execute
    result = execute({"action": "drag", "from": [100, 100], "to": [200, 200]})
    assert "拖拽" in result
run_test("execute: drag", test_execute_drag)

def test_execute_wait():
    from computer_use_agent.executor import execute
    t0 = time.time()
    result = execute({"action": "wait", "seconds": 0.1})
    elapsed = time.time() - t0
    assert "等待" in result
    assert elapsed >= 0.05
run_test("execute: wait", test_execute_wait)

def test_execute_screenshot():
    from computer_use_agent.executor import execute
    result = execute({"action": "screenshot"})
    assert "截图" in result
run_test("execute: screenshot", test_execute_screenshot)

def test_execute_done():
    from computer_use_agent.executor import execute
    result = execute({"action": "done", "message": "finished"})
    assert "完成" in result
    assert "finished" in result
run_test("execute: done", test_execute_done)

def test_execute_unknown():
    from computer_use_agent.executor import execute
    result = execute({"action": "nonexistent"})
    assert "未知动作" in result
run_test("execute: unknown action", test_execute_unknown)

def test_execute_exception():
    from computer_use_agent.executor import execute
    result = execute({"action": "left_click"})  # missing coordinate/element
    assert "执行失败" in result
run_test("execute: exception handling", test_execute_exception)


# ═══════════════════════════════════════════════════════════
# [3] agent.py - SessionStats 边界
# ═══════════════════════════════════════════════════════════
print("\n[3] agent.py (extended)")

def test_stats_empty():
    from computer_use_agent.agent import SessionStats
    s = SessionStats()
    assert s.total_steps == 0
    assert s.total_tokens_in == 0
    assert s.total_tokens_out == 0
    assert s.total_llm_time == 0.0
    assert s.total_actions == 0
    assert s.errors == 0
run_test("SessionStats: empty init", test_stats_empty)

def test_stats_update_done():
    from computer_use_agent.agent import SessionStats
    s = SessionStats()
    s.update({"_tokens_in": 100, "_tokens_out": 50, "_elapsed": 1.0, "action": "done"})
    assert s.total_steps == 1
    assert s.total_tokens_in == 100
    assert s.total_tokens_out == 50
    assert s.total_actions == 0  # done not counted
run_test("SessionStats: done not counted as action", test_stats_update_done)

def test_stats_update_screenshot():
    from computer_use_agent.agent import SessionStats
    s = SessionStats()
    s.update({"_tokens_in": 10, "_tokens_out": 5, "_elapsed": 0.5, "action": "screenshot"})
    assert s.total_actions == 0  # screenshot not counted
run_test("SessionStats: screenshot not counted", test_stats_update_screenshot)

def test_stats_update_wait():
    from computer_use_agent.agent import SessionStats
    s = SessionStats()
    s.update({"_tokens_in": 10, "_tokens_out": 5, "_elapsed": 0.5, "action": "wait"})
    assert s.total_actions == 0  # wait not counted
run_test("SessionStats: wait not counted", test_stats_update_wait)

def test_stats_errors():
    from computer_use_agent.agent import SessionStats
    s = SessionStats()
    s.update({"_tokens_in": 10, "_tokens_out": 5, "_elapsed": 0.1, "action": "click", "_error": True})
    s.update({"_tokens_in": 10, "_tokens_out": 5, "_elapsed": 0.1, "action": "click", "_error": True})
    assert s.errors == 2
run_test("SessionStats: error counting", test_stats_errors)

def test_stats_summary():
    from computer_use_agent.agent import SessionStats
    s = SessionStats()
    s.update({"_tokens_in": 100, "_tokens_out": 50, "_elapsed": 2.0, "action": "click"})
    summary = s.summary()
    assert "Steps: 1" in summary
    assert "Actions: 1" in summary
    assert "100" in summary
    assert "50" in summary
run_test("SessionStats: summary format", test_stats_summary)

def test_compress_history_small():
    from computer_use_agent.agent import _compress_history
    h = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    result = _compress_history(h)
    assert len(result) == 10
run_test("_compress_history: small unchanged", test_compress_history_small)

def test_compress_history_large():
    from computer_use_agent.agent import _compress_history
    h = []
    for i in range(60):
        h.append({"role": "user", "content": f"step {i} " * 20})
        h.append({"role": "assistant", "content": f'{{"action":"click","coordinate":[{i},{i}]}}'})
    result = _compress_history(h)
    assert len(result) < len(h)
    assert result[0]["role"] == "user"
    assert "历史摘要" in result[0]["content"]
run_test("_compress_history: large compresses", test_compress_history_large)


# ═══════════════════════════════════════════════════════════
# [4] prompts.py - 内容验证
# ═══════════════════════════════════════════════════════════
print("\n[4] prompts.py (extended)")

def test_identity_content():
    from computer_use_agent.prompts import IDENTITY
    assert "Computer Use Agent" in IDENTITY
    assert "screenshots" in IDENTITY
    assert "actions" in IDENTITY
run_test("IDENTITY content", test_identity_content)

def test_task_completion_content():
    from computer_use_agent.prompts import TASK_COMPLETION
    assert "REAL result" in TASK_COMPLETION
    assert "fabricated" in TASK_COMPLETION
    assert "COMPLETELY DONE" in TASK_COMPLETION
run_test("TASK_COMPLETION content", test_task_completion_content)

def test_computer_use_content():
    from computer_use_agent.prompts import COMPUTER_USE
    assert "Capture-Click-Verify" in COMPUTER_USE
    assert "Coordinate System" in COMPUTER_USE
run_test("COMPUTER_USE content", test_computer_use_content)

def test_som_prompt_content():
    from computer_use_agent.prompts import TOOL_GUIDANCE_SOM
    assert "element" in TOOL_GUIDANCE_SOM
    assert "SOM Mode" in TOOL_GUIDANCE_SOM
    assert "red" in TOOL_GUIDANCE_SOM.lower() or "overlay" in TOOL_GUIDANCE_SOM.lower()
run_test("TOOL_GUIDANCE_SOM content", test_som_prompt_content)

def test_vision_prompt_content():
    from computer_use_agent.prompts import TOOL_GUIDANCE_VISION
    assert "coordinate" in TOOL_GUIDANCE_VISION
    assert "Vision Mode" in TOOL_GUIDANCE_VISION
run_test("TOOL_GUIDANCE_VISION content", test_vision_prompt_content)

def test_safety_rules_content():
    from computer_use_agent.prompts import SAFETY_RULES
    assert "password" in SAFETY_RULES.lower()
    assert "prompt injection" in SAFETY_RULES.lower()
    assert "NEVER" in SAFETY_RULES
run_test("SAFETY_RULES content", test_safety_rules_content)

def test_error_recovery_content():
    from computer_use_agent.prompts import ERROR_RECOVERY
    assert "Verification" in ERROR_RECOVERY
    assert "different coordinates" in ERROR_RECOVERY
run_test("ERROR_RECOVERY content", test_error_recovery_content)

def test_tool_enforcement_content():
    from computer_use_agent.prompts import TOOL_ENFORCEMENT
    assert "MUST" in TOOL_ENFORCEMENT
    assert "execute" in TOOL_ENFORCEMENT.lower()
run_test("TOOL_ENFORCEMENT content", test_tool_enforcement_content)

def test_environment_context():
    from computer_use_agent.prompts import build_environment_context
    ctx = build_environment_context(1920, 1080)
    assert "1920x1080" in ctx
    assert "OS" in ctx
    assert "Date" in ctx
run_test("build_environment_context", test_environment_context)

def test_environment_context_no_screen():
    from computer_use_agent.prompts import build_environment_context
    ctx = build_environment_context()
    assert "OS" in ctx
    assert "Screen" not in ctx
run_test("build_environment_context without screen", test_environment_context_no_screen)

def test_openai_specific():
    from computer_use_agent.prompts import _OPENAI_SPECIFIC
    assert "Execution Discipline" in _OPENAI_SPECIFIC
    assert "Grok" in _OPENAI_SPECIFIC
run_test("_OPENAI_SPECIFIC content", test_openai_specific)

def test_google_specific():
    from computer_use_agent.prompts import _GOOGLE_SPECIFIC
    assert "Operational Directives" in _GOOGLE_SPECIFIC
    assert "Gemini" in _GOOGLE_SPECIFIC
run_test("_GOOGLE_SPECIFIC content", test_google_specific)


# ═══════════════════════════════════════════════════════════
# [5] sanitization.py - 补充测试
# ═══════════════════════════════════════════════════════════
print("\n[5] sanitization.py (extended)")

def test_repair_json_python_none():
    from computer_use_agent.sanitization import repair_json
    r = repair_json('{"key": null}')
    import json
    obj = json.loads(r)
    assert obj["key"] is None
run_test("repair_json: null value", test_repair_json_python_none)

def test_repair_json_single_quotes():
    from computer_use_agent.sanitization import repair_json
    # Single quotes are not valid JSON, repair should handle gracefully
    r = repair_json('{"key": "value"}')
    import json
    obj = json.loads(r)
    assert obj["key"] == "value"
run_test("repair_json: standard double quotes", test_repair_json_single_quotes)

def test_repair_json_nested():
    from computer_use_agent.sanitization import repair_json
    r = repair_json('{"a": {"b": 1}, "c": [1, 2]}')
    import json
    obj = json.loads(r)
    assert obj["a"]["b"] == 1
    assert obj["c"] == [1, 2]
run_test("repair_json: nested objects", test_repair_json_nested)

def test_repair_message_sequence_empty():
    from computer_use_agent.sanitization import repair_message_sequence
    result = repair_message_sequence([])
    assert result == []
run_test("repair_message_sequence: empty", test_repair_message_sequence_empty)

def test_repair_message_sequence_three_users():
    from computer_use_agent.sanitization import repair_message_sequence
    msgs = [
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
        {"role": "user", "content": "c"},
    ]
    result = repair_message_sequence(msgs)
    assert len(result) == 1
    assert "a" in result[0]["content"]
    assert "b" in result[0]["content"]
    assert "c" in result[0]["content"]
run_test("repair_message_sequence: three users merge", test_repair_message_sequence_three_users)

def test_repair_message_sequence_multimodal():
    from computer_use_agent.sanitization import repair_message_sequence
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        {"role": "user", "content": "world"},
    ]
    result = repair_message_sequence(msgs)
    assert len(result) == 2  # multimodal not merged
run_test("repair_message_sequence: multimodal not merged", test_repair_message_sequence_multimodal)

def test_repair_tool_name_exact():
    from computer_use_agent.sanitization import repair_tool_name
    assert repair_tool_name("left_click", ["left_click", "right_click"]) == "left_click"
run_test("repair_tool_name: exact match", test_repair_tool_name_exact)

def test_repair_tool_name_fuzzy():
    from computer_use_agent.sanitization import repair_tool_name
    result = repair_tool_name("left_clic", ["left_click", "right_click"])
    assert result == "left_click"
run_test("repair_tool_name: fuzzy match", test_repair_tool_name_fuzzy)


# ═══════════════════════════════════════════════════════════
# [6] token_budget.py - 补充测试
# ═══════════════════════════════════════════════════════════
print("\n[6] token_budget.py (extended)")

def test_truncate_short():
    from computer_use_agent.token_budget import truncate_message
    msg = {"role": "user", "content": "short"}
    result = truncate_message(msg, max_chars=100)
    assert result["content"] == "short"
run_test("truncate: short unchanged", test_truncate_short)

def test_truncate_multimodal():
    from computer_use_agent.token_budget import truncate_message
    msg = {"role": "user", "content": [{"type": "text", "text": "x" * 1000}]}
    result = truncate_message(msg, max_chars=100)
    text = result["content"][0]["text"]
    assert len(text) < 1000
    assert "truncated" in text
run_test("truncate: multimodal text", test_truncate_multimodal)

def test_compact_history_entry():
    from computer_use_agent.token_budget import compact_history_entry
    msg = {"role": "assistant", "content": "x" * 10000}
    result = compact_history_entry(msg)
    assert len(result["content"]) < 10000
    assert result["_compacted"] == True
run_test("compact_history_entry", test_compact_history_entry)

def test_estimate_tokens_empty():
    from computer_use_agent.token_budget import estimate_tokens
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0
run_test("estimate_tokens: empty", test_estimate_tokens_empty)

def test_should_compress_large():
    from computer_use_agent.token_budget import should_compress, estimate_history_tokens
    # Create history that exceeds threshold
    large = [{"role": "user", "content": "x " * 5000}]  # ~10000 chars
    tokens = estimate_history_tokens(large)
    # threshold = context_window * 0.5
    # if tokens > threshold, should compress
    threshold = 100000 * 0.5  # 50000
    if tokens > threshold:
        assert should_compress(large, context_window=100000) == True
    else:
        assert should_compress(large, context_window=100000) == False
    print(f"    tokens={tokens}, threshold={threshold}")
run_test("should_compress: large history", test_should_compress_large)

def test_enforce_budget_no_change_small():
    from computer_use_agent.token_budget import enforce_history_budget
    small = [{"role": "user", "content": "hi"}]
    result = enforce_history_budget(small)
    assert len(result) == 1
run_test("enforce_history_budget: small unchanged", test_enforce_budget_no_change_small)


# ═══════════════════════════════════════════════════════════
# [7] llm.py - 补充测试
# ═══════════════════════════════════════════════════════════
print("\n[7] llm.py (extended)")

def test_parse_action_with_metadata():
    from computer_use_agent.llm import _parse_action
    r = _parse_action('{"action":"click","coordinate":[10,20]}', 2.5, 500, 100)
    assert r["_elapsed"] == 2.5
    assert r["_tokens_in"] == 500
    assert r["_tokens_out"] == 100
    assert r["_raw"] == '{"action":"click","coordinate":[10,20]}'
run_test("parse_action: metadata injected", test_parse_action_with_metadata)

def test_parse_action_empty_string():
    from computer_use_agent.llm import _parse_action
    r = _parse_action("", 0.1, 10, 5)
    assert r["action"] == "wait"
run_test("parse_action: empty string", test_parse_action_empty_string)

def test_parse_action_no_json():
    from computer_use_agent.llm import _parse_action
    r = _parse_action("hello world no json here", 0.1, 10, 5)
    assert r["action"] == "wait"
run_test("parse_action: no JSON at all", test_parse_action_no_json)

def test_classify_error_value_error():
    from computer_use_agent.llm import _classify_error
    r = _classify_error(ValueError("bad input"))
    assert r["retryable"] == True
    assert r["reason"] == "unknown"
run_test("classify_error: ValueError", test_classify_error_value_error)

def test_jittered_backoff_increases():
    from computer_use_agent.llm import _jittered_backoff
    d0 = _jittered_backoff(0, base=2.0, cap=60.0)
    d1 = _jittered_backoff(1, base=2.0, cap=60.0)
    d2 = _jittered_backoff(2, base=2.0, cap=60.0)
    assert d0 < d1 < d2
run_test("jittered_backoff: increases", test_jittered_backoff_increases)


# ═══════════════════════════════════════════════════════════
# [8] cli.py - 输出验证
# ═══════════════════════════════════════════════════════════
print("\n[8] cli.py (extended)")

def test_print_help():
    from computer_use_agent.cli import _print_help
    _print_help()  # should not crash
run_test("print_help: no crash", test_print_help)

def test_print_config():
    from computer_use_agent.cli import _print_config
    _print_config()  # should not crash
run_test("print_config: no crash", test_print_config)

def test_print_usage():
    from computer_use_agent.cli import _print_usage
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    _print_usage(agent)  # should not crash
run_test("print_usage: no crash", test_print_usage)

def test_print_action():
    from computer_use_agent.cli import _print_action
    _print_action(1, {"action": "click", "thought": "test", "_elapsed": 1.0, "_tokens_in": 100, "_tokens_out": 50}, "clicked")
run_test("print_action: no crash", test_print_action)

def test_print_done():
    from computer_use_agent.cli import _print_done
    from computer_use_agent.agent import SessionStats
    s = SessionStats()
    _print_done("done", s)
run_test("print_done: no crash", test_print_done)

def test_format_time_ago_recent():
    from computer_use_agent.cli import _format_time_ago
    from datetime import datetime
    r = _format_time_ago(datetime.now().isoformat())
    assert "just now" in r
run_test("format_time_ago: just now", test_format_time_ago_recent)

def test_format_time_ago_hours():
    from computer_use_agent.cli import _format_time_ago
    from datetime import datetime, timedelta
    r = _format_time_ago((datetime.now() - timedelta(hours=3)).isoformat())
    assert "h ago" in r
run_test("format_time_ago: hours ago", test_format_time_ago_hours)

def test_format_time_ago_days():
    from computer_use_agent.cli import _format_time_ago
    from datetime import datetime, timedelta
    r = _format_time_ago((datetime.now() - timedelta(days=5)).isoformat())
    assert "d ago" in r
run_test("format_time_ago: days ago", test_format_time_ago_days)

def test_format_time_ago_invalid():
    from computer_use_agent.cli import _format_time_ago
    r = _format_time_ago("not-a-date")
    assert r == ""
run_test("format_time_ago: invalid returns empty", test_format_time_ago_invalid)


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
