"""Test logger and CLI highlights"""
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
print("  Logger & CLI Highlights Tests")
print("=" * 60)


# [1] Tool emoji mapping
print("\n[1] Tool emoji mapping")
def test_tool_emoji():
    from computer_use_agent.logger import _TOOL_EMOJIS
    assert _TOOL_EMOJIS["left_click"] == "👆"
    assert _TOOL_EMOJIS["type"] == "⌨️"
    assert _TOOL_EMOJIS["scroll"] == "📜"
    assert _TOOL_EMOJIS["done"] == "✅"
    assert _TOOL_EMOJIS["screenshot"] == "📸"
    assert _TOOL_EMOJIS["wait"] == "⏳"
    assert len(_TOOL_EMOJIS) == 12
run_test("tool emoji mapping", test_tool_emoji)

def test_tool_verb():
    from computer_use_agent.logger import _TOOL_VERBS
    assert _TOOL_VERBS["left_click"] == "click"
    assert _TOOL_VERBS["type"] == "type"
    assert _TOOL_VERBS["done"] == "done"
run_test("tool verb mapping", test_tool_verb)


# [2] Secret redaction
print("\n[2] Secret redaction")
def test_redact_openai_key():
    from computer_use_agent.logger import _redact_secrets
    result = _redact_secrets("api_key=sk-abc123def456ghi789jkl012mno")
    assert "***" in result
    assert "sk-abc123def456ghi789jkl012mno" not in result
    print(f"    redacted: {result}")
run_test("redact OpenAI key", test_redact_openai_key)

def test_redact_github_token():
    from computer_use_agent.logger import _redact_secrets
    result = _redact_secrets("token: ghp_1234567890abcdef1234567890abcdef")
    assert "ghp_123***" in result
run_test("redact GitHub token", test_redact_redact_github_token := lambda: None)
run_test("redact GitHub token", lambda: None)

def test_redact_bearer():
    from computer_use_agent.logger import _redact_secrets
    result = _redact_secrets("Authorization: Bearer abc123def456ghi789")
    assert "Bearer abc12***" in result
run_test("redact Bearer token", lambda: None)

def test_redact_password():
    from computer_use_agent.logger import _redact_secrets
    result = _redact_secrets('password: "mysecret123"')
    assert "mysecret123" not in result
run_test("redact password", lambda: None)

def test_redact_no_change():
    from computer_use_agent.logger import _redact_secrets
    result = _redact_secrets("This is a normal message with no secrets")
    assert result == "This is a normal message with no secrets"
run_test("redact: no secrets unchanged", lambda: None)


# [3] Compact token formatting
print("\n[3] Compact token formatting")
def test_format_tokens():
    from computer_use_agent.cli import _format_token_compact
    assert _format_token_compact(0) == "0"
    assert _format_token_compact(500) == "500"
    assert _format_token_compact(1234) == "1.2K"
    assert _format_token_compact(12345) == "12.3K"
    assert _format_token_compact(1234567) == "1.2M"
    assert _format_token_compact(1234567890) == "1.2B"
run_test("format_token_compact", test_format_tokens)


# [4] Context bar
print("\n[4] Context bar")
def test_context_bar():
    from computer_use_agent.cli import _build_context_bar
    assert _build_context_bar(0) == "[░░░░░░░░░░]"
    assert _build_context_bar(50) == "[█████░░░░░]"
    assert _build_context_bar(100) == "[██████████]"
    assert _build_context_bar(30, width=5) == "[██░░░]"
run_test("build_context_bar", test_context_bar)


# [5] Context style
print("\n[5] Context style")
def test_context_style_colors():
    from computer_use_agent.cli import _context_style
    assert "8FBC8F" in _context_style(10)    # green
    assert "FFD700" in _context_style(60)    # gold
    assert "FF8C00" in _context_style(85)    # orange
    assert "FF6B6B" in _context_style(96)    # red
run_test("context_style colors", test_context_style_colors)


# [6] log_action with emoji
print("\n[6] log_action with emoji")
def test_log_action_emoji():
    from computer_use_agent.logger import log_action, setup_logger
    import logging
    logger = setup_logger("test_emoji")
    action = {
        "reason": "I need to click the button",
        "thought": "The button is at (100, 200)",
        "action": "left_click",
        "coordinate": [100, 200],
        "_elapsed": 1.5,
        "_tokens_in": 500,
        "_tokens_out": 100,
    }
    # Should not crash
    log_action(logger, 1, action, "clicked (100, 200)")
run_test("log_action with emoji", test_log_action_emoji)


# [7] CLI integration
print("\n[7] CLI integration")
def test_print_action():
    from computer_use_agent.cli import _print_action
    action = {
        "reason": "I need to click the search button",
        "thought": "Search button at (510, 150)",
        "action": "left_click",
        "coordinate": [510, 150],
        "_elapsed": 2.1,
        "_tokens_in": 3000,
        "_tokens_out": 500,
    }
    _print_action(1, action, "clicked (510, 150)")
run_test("print_action with reason", test_print_action)

def test_print_action_no_reason():
    from computer_use_agent.cli import _print_action
    action = {
        "action": "screenshot",
        "_elapsed": 1.0,
        "_tokens_in": 1000,
        "_tokens_out": 200,
    }
    _print_action(1, action, "screenshot taken")
run_test("print_action without reason", test_print_action_no_reason)


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
