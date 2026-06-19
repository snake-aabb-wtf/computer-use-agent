"""API 接口测试"""

import sys
import os
import json
import time
import threading
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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


def _req(method, path, data=None):
    url = f"http://127.0.0.1:2025{path}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code


def _start_server():
    from computer_use_agent.api import serve
    t = threading.Thread(target=serve, kwargs={"host": "127.0.0.1", "port": 2025}, daemon=True)
    t.start()
    for _ in range(30):
        try:
            urllib.request.urlopen("http://127.0.0.1:2025/health", timeout=0.5)
            return t
        except Exception:
            time.sleep(0.1)
    raise TimeoutError("Server did not start")


print("=" * 60)
print("  API Interface Tests")
print("=" * 60)

server_thread = _start_server()

# [1] Health
print("\n[1] Health check")
def test_health():
    data, code = _req("GET", "/health")
    assert code == 200
    assert data["status"] == "ok"
    assert "busy" in data
run_test("GET /health returns ok", test_health)

# [2] Root
print("\n[2] Root endpoint")
def test_root():
    data, code = _req("GET", "/")
    assert code == 200
    assert data["service"] == "computer-use-agent"
    assert "endpoints" in data
run_test("GET / returns service info", test_root)

# [3] Submit task
print("\n[3] Submit task")
def test_submit():
    data, code = _req("POST", "/run", {"task": "reply OK"})
    assert code == 202
    assert "id" in data
    assert data["status"] == "accepted"
run_test("POST /run accepts task", test_submit)

# [4] Missing task
print("\n[4] Validation")
def test_missing_task():
    data, code = _req("POST", "/run", {"wrong": "field"})
    assert code == 400
    assert "error" in data
run_test("POST /run with missing task returns 400", test_missing_task)

# [5] Status tracking
print("\n[5] Status tracking")
def test_status():
    data, code = _req("POST", "/run", {"task": "reply OK"})
    task_id = data["id"]
    time.sleep(0.5)
    data, code = _req("GET", f"/status/{task_id}")
    assert code == 200
    assert data["id"] == task_id
    assert data["status"] in ("queued", "running", "done", "error")
run_test("GET /status/<id> tracks task", test_status)

# [6] Not found
print("\n[6] Not found")
def test_not_found():
    data, code = _req("GET", "/status/nonexistent")
    assert code == 404
run_test("GET /status/nonexistent returns 404", test_not_found)

# [7] Stop
print("\n[7] Stop")
def test_stop():
    data, code = _req("POST", "/stop")
    assert code == 200
    assert data["status"] == "stopped"
run_test("POST /stop returns stopped", test_stop)

# [8] API module imports
print("\n[8] Module imports")
def test_api_module():
    from computer_use_agent.api import _submit_task, _task_results, _task_lock
    task_id = _submit_task("test import")
    assert len(task_id) == 12
    with _task_lock:
        assert task_id in _task_results
run_test("api module submit works", test_api_module)

# Cleanup
print(f"\n{'='*60}")
print(f"  Results: {passed} passed, {failed} failed")
if errors:
    print(f"\n  Failed:")
    for name, err in errors:
        print(f"    - {name}: {err}")
print(f"{'='*60}")

if failed == 0:
    print("\n  All tests passed!")
