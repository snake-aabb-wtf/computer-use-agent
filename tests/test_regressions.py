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
