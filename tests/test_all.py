"""测试脚本 - 报错后暂停，等待用户确认"""

import sys
import os
import time
import traceback

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows UTF-8
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
        traceback.print_exc()


print("=" * 60)
print("  Computer Use Agent - Tests")
print("=" * 60)

# ── [1] CONFIG ──
print("\n[1] config.py")
def test_config():
    from computer_use_agent import config
    assert config.LLM_API_KEY, "LLM_API_KEY empty"
    assert config.LLM_BASE_URL, "LLM_BASE_URL empty"
    assert config.LLM_MODEL, "LLM_MODEL empty"
    print(f"    API_KEY: {config.LLM_API_KEY[:10]}...")
    print(f"    BASE_URL: {config.LLM_BASE_URL}")
    print(f"    MODEL: {config.LLM_MODEL}")
    print(f"    MAX_STEPS: {config.MAX_STEPS}")
    print(f"    ACTION_DELAY: {config.ACTION_DELAY}")
run_test("load config", test_config)

# ── [2] SCREEN ──
print("\n[2] screen.py")
def test_capture():
    from computer_use_agent.screen import capture
    import base64
    b64 = capture()
    assert len(b64) > 100, f"base64 too short: {len(b64)}"
    decoded = base64.b64decode(b64)
    assert decoded[:4] == b'\x89PNG', "not PNG"
    print(f"    base64 size: {len(b64)} chars")
run_test("capture screenshot", test_capture)

def test_screen_size():
    from computer_use_agent.screen import get_screen_size
    w, h = get_screen_size()
    print(f"    resolution: {w}x{h}")
run_test("get screen size", test_screen_size)

# ── [3] EXECUTOR (dry run - only test parsing, skip actual clicks) ──
print("\n[3] executor.py (logic only)")
def test_executor_logic():
    from computer_use_agent.executor import _normalize_key
    assert _normalize_key("return") == "enter"
    assert _normalize_key("esc") == "escape"
    assert _normalize_key("cmd") == "win"
    assert _normalize_key("del") == "delete"
    assert _normalize_key("pgup") == "pageup"
    assert _normalize_key("arrowup") == "up"
    print("    key aliases OK")
run_test("key alias mapping", test_executor_logic)

# ── [4] LLM JSON PARSING ──
print("\n[4] llm.py (JSON parsing)")
def test_parse_json():
    from computer_use_agent.llm import _parse_action
    # standard
    r = _parse_action('{"thought":"test","action":"left_click","coordinate":[100,200]}', 1.0, 100, 50)
    assert r["action"] == "left_click"
    assert r["coordinate"] == [100, 200]
    assert r["_tokens_in"] == 100
    # markdown wrapped
    r = _parse_action('```json\n{"thought":"t","action":"key","key":"enter"}\n```', 0.5, 10, 5)
    assert r["action"] == "key"
    # invalid
    r = _parse_action("not json", 0.1, 10, 5)
    assert r["action"] == "wait"
    # embedded
    r = _parse_action('ok {"thought":"x","action":"done","message":"done"}', 0.3, 10, 5)
    assert r["action"] == "done"
    # hotkey
    r = _parse_action('{"thought":"copy","action":"hotkey","keys":["ctrl","c"]}', 0.5, 10, 5)
    assert r["keys"] == ["ctrl", "c"]
    print("    all parse cases OK")
run_test("JSON parsing", test_parse_json)

# ── [5] LOGGER ──
print("\n[5] logger.py")
def test_logger():
    from computer_use_agent.logger import setup_logger, log_action
    import logging
    logger = setup_logger("test")
    assert logger is not None
    fh = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(fh) > 0, "no file handler"
    log_action(logger, 1, {"thought":"t","action":"click","_elapsed":1,"_tokens_in":10,"_tokens_out":5}, "ok")
    print("    logger + file handler OK")
run_test("logger create and write", test_logger)

# ── [6] LLM LIVE ──
print("\n[6] LLM live connection")
def test_llm_client():
    from computer_use_agent.llm import get_client
    client = get_client()
    print(f"    client base_url: {client.base_url}")
run_test("LLM client init", test_llm_client)

def test_llm_text():
    from computer_use_agent.llm import get_client
    from computer_use_agent import config
    client = get_client()
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": "Reply with only the word OK, nothing else"}],
        max_tokens=100,
    )
    msg = resp.choices[0].message
    text = (msg.content or msg.reasoning_content or "").strip()
    print(f"    LLM reply: '{text}'")
    assert len(text) > 0, "empty reply"
run_test("LLM text request", test_llm_text)

def test_llm_vision():
    from computer_use_agent.llm import get_client, _parse_action
    from computer_use_agent.screen import capture
    from computer_use_agent import config
    from computer_use_agent.prompts import build_system_prompt
    client = get_client()
    img_b64 = capture()
    messages = [
        {"role": "system", "content": build_system_prompt(1366, 768)},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}},
            {"type": "text", "text": "This is the current screenshot. Analyze and decide the next action. Return ONLY JSON."},
        ]},
    ]
    resp = client.chat.completions.create(model=config.LLM_MODEL, messages=messages, max_tokens=4096)
    msg = resp.choices[0].message
    raw = (msg.content or msg.reasoning_content or "").strip()
    tokens_in = resp.usage.prompt_tokens if resp.usage else 0
    tokens_out = resp.usage.completion_tokens if resp.usage else 0
    action = _parse_action(raw, 0, tokens_in, tokens_out)
    print(f"    action: {action.get('action')}")
    print(f"    thought: {action.get('thought','')[:120]}")
    print(f"    tokens: {tokens_in} in / {tokens_out} out")
    assert "action" in action
run_test("LLM vision + JSON", test_llm_vision)


# -- [7] NEW FEATURES (Hermes patterns) --
print("\n[7] New features (Hermes patterns)")

def test_jittered_backoff():
    from computer_use_agent.llm import _jittered_backoff
    d0 = _jittered_backoff(0, base=2.0, cap=60.0)
    d1 = _jittered_backoff(1, base=2.0, cap=60.0)
    d2 = _jittered_backoff(2, base=2.0, cap=60.0)
    assert d0 >= 2.0, f"backoff too small: {d0}"
    assert d1 >= 4.0, f"backoff too small: {d1}"
    assert d2 >= 8.0, f"backoff too small: {d2}"
    assert d2 <= 90.0, f"backoff too large: {d2}"  # cap + jitter
    print(f"    backoff: {d0:.1f}s, {d1:.1f}s, {d2:.1f}s")
run_test("jittered backoff", test_jittered_backoff)

def test_error_classification():
    from computer_use_agent.llm import _classify_error
    # Test with regular Python exceptions (unknown classification)
    r = _classify_error(ValueError("something went wrong"))
    assert r["retryable"] == True
    assert r["reason"] == "unknown"
    r = _classify_error(KeyboardInterrupt("ctrl+c"))
    assert r["retryable"] == True
    assert r["reason"] == "unknown"
    r = _classify_error(RuntimeError("boom"))
    assert r["retryable"] == True
    assert r["reason"] == "unknown"
    print("    unknown errors classified as retryable")
run_test("error classification", test_error_classification)

def test_session_stats():
    from computer_use_agent.agent import SessionStats
    stats = SessionStats()
    assert stats.total_steps == 0
    stats.update({"_tokens_in": 100, "_tokens_out": 50, "_elapsed": 1.0, "action": "left_click"})
    stats.update({"_tokens_in": 200, "_tokens_out": 80, "_elapsed": 2.0, "action": "done"})
    stats.update({"_tokens_in": 50, "_tokens_out": 20, "_elapsed": 0.5, "action": "wait"})
    assert stats.total_steps == 3
    assert stats.total_tokens_in == 350
    assert stats.total_tokens_out == 150
    assert stats.total_actions == 1  # only left_click counts (done/wait excluded)
    s = stats.summary()
    assert "Steps: 3" in s
    print(f"    stats: {s}")
run_test("session stats tracking", test_session_stats)

def test_history_compression():
    from computer_use_agent.agent import _compress_history
    # Create 50 turns of history
    history = []
    for i in range(50):
        history.append({"role": "user", "content": f"step {i}"})
        history.append({"role": "assistant", "content": f'{{"action":"left_click","coordinate":[{i},{i}]}}'})
    compressed = _compress_history(history)
    assert len(compressed) < len(history), f"compression failed: {len(compressed)} >= {len(history)}"
    # Should have summary + recent
    assert compressed[0]["role"] == "user"
    assert "历史摘要" in compressed[0]["content"]
    assert compressed[1]["role"] == "assistant"
    print(f"    {len(history)} turns -> {len(compressed)} turns")
run_test("history compression", test_history_compression)

def test_history_no_compress_small():
    from computer_use_agent.agent import _compress_history
    history = [{"role": "user", "content": "test"}] * 10
    result = _compress_history(history)
    assert len(result) == len(history), "small history should not be compressed"
run_test("no compress for small history", test_history_no_compress_small)

def test_parse_action_with_retry_nudge():
    from computer_use_agent.llm import _recover_empty_response
    r = _recover_empty_response("", 0, [])
    assert r == ""  # first retry, no nudge
    r = _recover_empty_response("", 2, [])
    assert r == ""  # stage 3, return empty
run_test("empty response recovery stages", test_parse_action_with_retry_nudge)


# -- [8] SANITIZATION MODULE --
print("\n[8] sanitization.py")

def test_repair_json_valid():
    from computer_use_agent.sanitization import repair_json
    r = repair_json('{"action":"click","coordinate":[100,200]}')
    assert '"action"' in r
    assert '"click"' in r
run_test("repair_json valid input", test_repair_json_valid)

def test_repair_json_trailing_comma():
    from computer_use_agent.sanitization import repair_json
    r = repair_json('{"action": "click", "x": 100,}')
    import json
    obj = json.loads(r)
    assert obj["action"] == "click"
    assert obj["x"] == 100
run_test("repair_json trailing comma", test_repair_json_trailing_comma)

def test_repair_json_unclosed_brace():
    from computer_use_agent.sanitization import repair_json
    r = repair_json('{"action": "click", "x": 100')
    import json
    obj = json.loads(r)
    assert obj["action"] == "click"
run_test("repair_json unclosed brace", test_repair_json_unclosed_brace)

def test_repair_json_extra_closing():
    from computer_use_agent.sanitization import repair_json
    r = repair_json('{"action": "click"}}]')
    import json
    obj = json.loads(r)
    assert obj["action"] == "click"
run_test("repair_json extra closing brackets", test_repair_json_extra_closing)

def test_repair_json_empty():
    from computer_use_agent.sanitization import repair_json
    r = repair_json("")
    assert r == "{}"
    r = repair_json("not json at all")
    assert r == "{}"
run_test("repair_json empty/invalid", test_repair_json_empty)

def test_repair_json_control_chars():
    from computer_use_agent.sanitization import repair_json
    r = repair_json('{"text": "line1\nline2\ttab"}')
    import json
    obj = json.loads(r)
    assert "line1" in obj["text"]
run_test("repair_json control chars", test_repair_json_control_chars)

def test_repair_message_sequence():
    from computer_use_agent.sanitization import repair_message_sequence
    # Consecutive user messages should be merged
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "user", "content": "world"},
    ]
    result = repair_message_sequence(msgs)
    assert len(result) == 1
    assert "hello" in result[0]["content"]
    assert "world" in result[0]["content"]
run_test("repair_message_sequence merge users", test_repair_message_sequence)

def test_repair_message_orphan_tool():
    from computer_use_agent.sanitization import repair_message_sequence
    msgs = [
        {"role": "tool", "content": "result", "tool_call_id": "orphan_123"},
        {"role": "user", "content": "hello"},
    ]
    result = repair_message_sequence(msgs)
    assert len(result) == 1
    assert result[0]["role"] == "user"
run_test("repair_message_sequence drop orphan tool", test_repair_message_orphan_tool)

def test_repair_tool_name():
    from computer_use_agent.sanitization import repair_tool_name
    valid = ["left_click", "right_click", "type", "key", "scroll", "done"]
    assert repair_tool_name("left_click", valid) == "left_click"
    assert repair_tool_name("Left_Click", valid) == "left_click"
    assert repair_tool_name("left-click", valid) == "left_click"
    assert repair_tool_name("leftclick", valid) == "left_click"
run_test("repair_tool_name fuzzy match", test_repair_tool_name)

def test_sanitize_api_messages():
    from computer_use_agent.sanitization import sanitize_api_messages
    msgs = [
        {"role": "system", "content": "you are helpful"},
        {"role": "invalid", "content": "bad"},
        {"role": "user", "content": "hello"},
    ]
    result = sanitize_api_messages(msgs)
    assert len(result) == 2
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
run_test("sanitize_api_messages drop invalid", test_sanitize_api_messages)


# -- [9] TOKEN BUDGET MODULE --
print("\n[9] token_budget.py")

def test_truncate_message():
    from computer_use_agent.token_budget import truncate_message
    msg = {"role": "user", "content": "x" * 10000}
    result = truncate_message(msg, max_chars=500)
    assert len(result["content"]) < 1000
    assert "truncated" in result["content"]
run_test("truncate_message", test_truncate_message)

def test_estimate_tokens():
    from computer_use_agent.token_budget import estimate_tokens
    tokens = estimate_tokens("hello world")
    assert tokens > 0
    assert tokens < 10
    print(f"    'hello world' ~ {tokens} tokens")
run_test("estimate_tokens", test_estimate_tokens)

def test_estimate_history_tokens():
    from computer_use_agent.token_budget import estimate_history_tokens
    history = [
        {"role": "user", "content": "test message " * 100},
        {"role": "assistant", "content": '{"action":"click"}'},
    ]
    tokens = estimate_history_tokens(history)
    assert tokens > 0
    print(f"    2 messages ~ {tokens} tokens")
run_test("estimate_history_tokens", test_estimate_history_tokens)

def test_enforce_history_budget_crop():
    from computer_use_agent.token_budget import enforce_history_budget, BudgetConfig
    config = BudgetConfig(max_history_messages=10)
    history = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
    result = enforce_history_budget(history, config)
    assert len(result) <= 10
    print(f"    20 msgs -> {len(result)} msgs")
run_test("enforce_history_budget crop", test_enforce_history_budget_crop)

def test_should_compress():
    from computer_use_agent.token_budget import should_compress
    # Small history -> no compression
    small = [{"role": "user", "content": "hi"}]
    assert should_compress(small, context_window=128000) == False
run_test("should_compress small history", test_should_compress)

def test_budget_config_frozen():
    from computer_use_agent.token_budget import BudgetConfig
    config = BudgetConfig()
    try:
        config.max_message_chars = 999
        assert False, "Should be frozen"
    except AttributeError:
        pass
run_test("BudgetConfig is frozen", test_budget_config_frozen)


# -- [10] AGENT INTEGRATION --
print("\n[10] Agent integration")

def test_agent_prepare_messages():
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    agent.history = [
        {"role": "user", "content": "task"},
        {"role": "user", "content": "oops duplicate"},
        {"role": "assistant", "content": '{"action":"click"}'},
        {"role": "user", "content": "result"},
    ]
    prepared = agent._prepare_messages()
    # Should have merged consecutive users
    user_count = sum(1 for m in prepared if m.get("role") == "user")
    assert user_count <= 2  # merged + result
run_test("agent prepare messages", test_agent_prepare_messages)


# ── SUMMARY ──
print(f"\n{'='*60}")
print(f"  Results: {passed} passed, {failed} failed")
if errors:
    print(f"\n  Failed:")
    for name, err in errors:
        print(f"    - {name}: {err}")
print(f"{'='*60}")

# 报错时暂停
if failed > 0:
    print("\n  Some tests failed. Check errors above.")
    input("  Press Enter to exit...")
else:
    print("\n  All tests passed!")
    input("  Press Enter to exit...")
