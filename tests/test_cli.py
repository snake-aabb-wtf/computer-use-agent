"""CLI 模块测试"""

import sys
import os
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
print("  CLI Module Tests")
print("=" * 60)


# ── [1] Import ──
print("\n[1] Import tests")

def test_import_cli():
    from computer_use_agent.cli import CLI, main, _print_banner, _print_help
    from computer_use_agent.cli import _print_config, _handle_command, COMMANDS
run_test("import cli module", test_import_cli)

def test_commands_registry():
    from computer_use_agent.cli import COMMANDS
    assert "/help" in COMMANDS
    assert "/quit" in COMMANDS
    assert "/config" in COMMANDS
    assert "/model" in COMMANDS
    assert "/steps" in COMMANDS
    assert "/delay" in COMMANDS
    assert "/history" in COMMANDS
    assert "/reset" in COMMANDS
    assert "/clear" in COMMANDS
    print(f"    {len(COMMANDS)} commands registered")
run_test("commands registry", test_commands_registry)


# ── [2] Banner & Output ──
print("\n[2] Output formatting")

def test_print_banner():
    from computer_use_agent.cli import _print_banner
    from rich.console import Console
    # 验证不报错
    _print_banner()
run_test("print banner", test_print_banner)

def test_print_help():
    from computer_use_agent.cli import _print_help
    _print_help()
run_test("print help", test_print_help)

def test_print_config():
    from computer_use_agent.cli import _print_config
    _print_config()
run_test("print config", test_print_config)

def test_print_action():
    from computer_use_agent.cli import _print_action
    action = {
        "action": "left_click",
        "thought": "Click the button",
        "coordinate": [100, 200],
        "_elapsed": 1.5,
        "_tokens_in": 500,
        "_tokens_out": 100,
    }
    _print_action(1, action, "left_click (100, 200)")
run_test("print action", test_print_action)


# ── [3] Command Handling ──
print("\n[3] Command handling")

def test_handle_quit():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    result = _handle_command("/quit", agent)
    assert result == True, f"expected True, got {result}"
run_test("/quit returns True", test_handle_quit)

def test_handle_exit():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    result = _handle_command("/exit", agent)
    assert result == True
run_test("/exit returns True", test_handle_exit)

def test_handle_help():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    result = _handle_command("/help", agent)
    assert result == False
run_test("/help returns False", test_handle_help)

def test_handle_config():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    result = _handle_command("/config", agent)
    assert result == False
run_test("/config returns False", test_handle_config)

def test_handle_model():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent import config
    old_model = config.LLM_MODEL
    agent = Agent(save_screenshots=False)
    _handle_command("/model gpt-4o-mini", agent)
    assert config.LLM_MODEL == "gpt-4o-mini"
    config.LLM_MODEL = old_model  # restore
run_test("/model changes model", test_handle_model)

def test_handle_steps():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent import config
    old = config.MAX_STEPS
    agent = Agent(save_screenshots=False)
    _handle_command("/steps 50", agent)
    assert config.MAX_STEPS == 50
    config.MAX_STEPS = old
run_test("/steps changes max steps", test_handle_steps)

def test_handle_delay():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    from computer_use_agent import config
    old = config.ACTION_DELAY
    agent = Agent(save_screenshots=False)
    _handle_command("/delay 0.5", agent)
    assert config.ACTION_DELAY == 0.5
    config.ACTION_DELAY = old
run_test("/delay changes delay", test_handle_delay)

def test_handle_reset():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    agent.history.append({"role": "user", "content": "test"})
    _handle_command("/reset", agent)
    assert len(agent.history) == 0
run_test("/reset clears history", test_handle_reset)

def test_handle_unknown():
    from computer_use_agent.cli import _handle_command
    from computer_use_agent.agent import Agent
    agent = Agent(save_screenshots=False)
    result = _handle_command("/bogus", agent)
    assert result == False
run_test("/unknown command handled", test_handle_unknown)


# ── [4] CLI Class ──
print("\n[4] CLI class")

def test_cli_init():
    from computer_use_agent.cli import CLI
    cli = CLI()
    assert cli.agent is not None
    assert cli.session is not None
run_test("CLI init", test_cli_init)


# ── SUMMARY ──
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
