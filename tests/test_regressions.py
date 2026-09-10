import io
import queue


def test_api_stop_marks_current_task_without_lock_deadlock(monkeypatch):
    from computer_use_agent import api

    class FakeAgent:
        def __init__(self):
            self.interrupted = False

        def interrupt(self, reason=""):
            self.interrupted = True

    agent = FakeAgent()
    task_id = "current-task"
    monkeypatch.setattr(api, "_active_agent", agent)
    monkeypatch.setattr(api, "_current_task_id", task_id)
    monkeypatch.setattr(
        api,
        "_task_results",
        {task_id: {"status": "running", "finished_at": None}},
    )

    assert api._stop_current() == task_id
    assert agent.interrupted is True
    assert api._task_results[task_id]["status"] == "cancelled"
    assert api._task_results[task_id]["error"] == "Task stopped by user"


def test_worker_skips_cancelled_tasks_and_uses_one_agent_per_task(monkeypatch):
    from computer_use_agent import api

    task_queue = queue.Queue()
    results = {
        "cancelled": {"status": "cancelled", "finished_at": None},
        "first": {"status": "queued", "result": None, "error": None},
        "second": {"status": "queued", "result": None, "error": None},
    }
    task_queue.put(("cancelled", "must not run"))
    task_queue.put(("first", "first task"))
    task_queue.put(("second", "second task"))
    task_queue.put((None, None))

    class FakeAgent:
        instances = []

        def __init__(self, save_screenshots=True):
            self.tasks = []
            FakeAgent.instances.append(self)

        def run(self, task):
            self.tasks.append(task)
            return f"done: {task}"

    monkeypatch.setattr(api, "_task_queue", task_queue)
    monkeypatch.setattr(api, "_task_results", results)
    monkeypatch.setattr(api, "_current_task_id", None)
    monkeypatch.setattr(api, "_active_agent", None)
    monkeypatch.setattr(api, "Agent", FakeAgent)

    api._worker()

    assert [agent.tasks for agent in FakeAgent.instances] == [["first task"], ["second task"]]
    assert results["cancelled"]["status"] == "cancelled"
    assert results["first"]["status"] == "done"
    assert results["second"]["status"] == "done"
    assert task_queue.unfinished_tasks == 0


def test_api_read_json_rejects_non_objects_and_invalid_lengths():
    from computer_use_agent.api import _APIHandler

    handler = object.__new__(_APIHandler)
    handler.headers = {"Content-Length": "7"}
    handler.rfile = io.BytesIO(b"[1, 2]")
    assert handler._read_json() is None

    handler.headers = {"Content-Length": "not-a-number"}
    handler.rfile = io.BytesIO(b"")
    assert handler._read_json() is None


def test_ui_tars_converts_integer_coords_using_capture_geometry(monkeypatch):
    from computer_use_agent import config
    from computer_use_agent.executor import normalize_action

    monkeypatch.setattr(config, "CAPTURE_MODE", "uitars")
    monkeypatch.setattr(
        "computer_use_agent.executor._ui_tars_geometry",
        lambda: (1000, 500, 100, 200),
    )

    action = normalize_action({"action": "click", "coordinate": [500, 1000]})
    assert action["action"] == "left_click"
    assert action["coordinate"] == [600, 700]

    drag = normalize_action(
        {"action": "drag", "from": [0, 0], "to": [1000, 1000]}
    )
    assert drag["from"] == [100, 200]
    assert drag["to"] == [1100, 700]


def test_vision_coords_are_not_normalized(monkeypatch):
    from computer_use_agent import config
    from computer_use_agent.executor import normalize_action

    monkeypatch.setattr(config, "CAPTURE_MODE", "vision")
    action = normalize_action({"action": "left_click", "coordinate": [500.0, 500.0]})
    assert action["coordinate"] == [500.0, 500.0]


def test_screenshot_mime_matches_configured_format(monkeypatch):
    from computer_use_agent import config
    from computer_use_agent.screen import get_screenshot_mime_type

    monkeypatch.setattr(config, "CAPTURE_MODE", "vision")
    monkeypatch.setattr(config, "SCREENSHOT_FORMAT", "jpeg")
    assert get_screenshot_mime_type() == "image/jpeg"

    monkeypatch.setattr(config, "CAPTURE_MODE", "som")
    assert get_screenshot_mime_type() == "image/png"


def test_som_overlay_translates_desktop_coordinates_to_capture_region():
    from PIL import Image

    from computer_use_agent.uia_tree import UIElement, render_som

    image = Image.new("RGB", (100, 100), "white")
    element = UIElement(index=1, role="Button", label="OK", bounds=(110, 220, 20, 20))
    rendered = render_som(image, [element], offset=(100, 200))

    red_pixel = rendered.getpixel((10, 20))
    assert red_pixel[0] > 200 and red_pixel[1] < 100


def test_mcp_logger_stream_is_separate_from_stdout(monkeypatch, tmp_path):
    import logging

    from computer_use_agent.logger import setup_logger

    stream = io.StringIO()
    monkeypatch.setattr("computer_use_agent.config.LOG_DIR", str(tmp_path))
    logger_name = "test_mcp_stdout_isolation"
    logger = setup_logger(logger_name, stream=stream)
    logger.info("protocol-safe log")

    console_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
    ]
    assert console_handlers
    assert console_handlers[0].stream is stream
    assert "protocol-safe log" in stream.getvalue()


def test_invalid_som_element_does_not_click_screen_center(monkeypatch):
    from computer_use_agent import config
    from computer_use_agent import executor
    from computer_use_agent.uia_tree import UIElement

    monkeypatch.setattr(config, "CAPTURE_MODE", "som")
    clicked = []
    monkeypatch.setattr(
        executor.pyautogui,
        "click",
        lambda *args, **kwargs: clicked.append((args, kwargs)),
    )
    executor.set_som_elements([UIElement(1, "Button", "OK", (100, 200, 80, 30))])

    result = executor.execute({"action": "left_click", "element": 999})

    assert "执行失败" in result
    assert clicked == []


def test_api_uses_threading_http_server(monkeypatch):
    from computer_use_agent import api

    seen = {}

    class FakeServer:
        def __init__(self, address, handler):
            seen["address"] = address
            seen["handler"] = handler

        def serve_forever(self):
            raise KeyboardInterrupt

        def shutdown(self):
            seen["shutdown"] = True

        def server_close(self):
            seen["closed"] = True

    monkeypatch.setattr(api, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(api, "_worker", lambda: None)

    api.serve(host="127.0.0.1", port=29999)

    assert seen["address"] == ("127.0.0.1", 29999)
    assert seen["handler"] is api._APIHandler
    assert seen["shutdown"] is True
    assert seen["closed"] is True


def test_agent_dry_run_skips_action_execution(monkeypatch):
    from computer_use_agent import agent as agent_module
    from computer_use_agent import config

    monkeypatch.setattr(config, "CAPTURE_MODE", "vision")
    monkeypatch.setattr(config, "MAX_STEPS", 1)
    monkeypatch.setattr(agent_module, "get_screen_size", lambda: (100, 100))
    monkeypatch.setattr(agent_module, "capture", lambda: "screenshot-data")
    monkeypatch.setattr(agent_module, "build_system_prompt", lambda *args: "prompt")
    monkeypatch.setattr(
        agent_module,
        "chat",
        lambda *args, **kwargs: {
            "action": "left_click",
            "coordinate": [10, 20],
            "thought": "preview click",
            "_raw": '{"action":"left_click","coordinate":[10,20]}',
            "_elapsed": 0.01,
        },
    )

    def should_not_execute(action):
        raise AssertionError("dry-run must not execute actions")

    monkeypatch.setattr(agent_module, "execute", should_not_execute)

    preview_agent = agent_module.Agent(save_screenshots=False, dry_run=True)
    result = preview_agent.run("click the button")

    assert result.startswith("DRY RUN: skipped execution")
    assert preview_agent.stats.total_steps == 1


def test_agent_writes_recording_events_for_completed_task(monkeypatch):
    from computer_use_agent import agent as agent_module
    from computer_use_agent import config

    class FakeSink:
        def __init__(self):
            self.headers = []
            self.steps = []
            self.footers = []

        def write_header(self, model, task):
            self.headers.append((model, task))

        def write_step(self, step, thought, action, result):
            self.steps.append((step, thought, action, result))

        def write_footer(self, status, result, total_steps):
            self.footers.append((status, result, total_steps))

    monkeypatch.setattr(config, "CAPTURE_MODE", "vision")
    monkeypatch.setattr(config, "MAX_STEPS", 1)
    monkeypatch.setattr(agent_module, "get_screen_size", lambda: (100, 100))
    monkeypatch.setattr(agent_module, "capture", lambda: "screenshot-data")
    monkeypatch.setattr(agent_module, "build_system_prompt", lambda *args: "prompt")
    monkeypatch.setattr(
        agent_module,
        "chat",
        lambda *args, **kwargs: {
            "action": "done",
            "message": "finished",
            "thought": "task is complete",
            "_raw": '{"action":"done","message":"finished"}',
            "_elapsed": 0.01,
        },
    )

    sink = FakeSink()
    task_agent = agent_module.Agent(save_screenshots=False)
    result = task_agent.run("finish the task", record_sink=sink)

    assert result == "finished"
    assert sink.headers == [(config.LLM_MODEL, "finish the task")]
    assert len(sink.steps) == 1
    assert sink.steps[0][0] == 1
    assert sink.steps[0][1] == "task is complete"
    assert sink.steps[0][2]["action"] == "done"
    assert sink.steps[0][3] == "finished"
    assert sink.footers == [("done", "finished", 1)]


def test_plugin_action_is_exposed_in_prompt():
    from computer_use_agent.prompts import build_plugin_guidance

    prompt = build_plugin_guidance([
        {
            "name": "send_email",
            "description": "Send an email",
            "schema": {
                "type": "object",
                "properties": {"to": {"type": "string"}},
                "required": ["to"],
            },
        }
    ])

    assert "send_email" in prompt
    assert "Send an email" in prompt
    assert '"required":["to"]' in prompt


def test_plugin_action_dispatches_arguments(monkeypatch):
    from computer_use_agent import executor

    class FakeRegistry:
        def has(self, name):
            return name == "make_note"

        def get(self, name):
            return (lambda title: f"saved:{title}"), {}

    monkeypatch.setattr(executor, "get_registry", lambda: FakeRegistry())
    result = executor.execute({
        "action": "make_note",
        "arguments": {"title": "hello"},
    })

    assert result == "saved:hello"
