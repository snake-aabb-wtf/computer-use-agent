# Plugin Development Guide

Plugins let you extend Computer Use Agent with **custom actions** that the LLM can
invoke alongside the built-in actions (`left_click`, `type`, etc.). Use cases:

- **Domain-specific tools** — e.g. "send_email", "create_jira_ticket", "query_database"
- **External API calls** — "fetch_weather", "translate_text", "summarize_url"
- **Local automation** — "run_script", "read_clipboard", "system_notify"
- **Sandbox extensions** — limit what the agent can do, audit specific actions

## Quick start

### 1. Create the plugin directory

```bash
mkdir -p ~/.config/cua/plugins
```

### 2. Write a plugin file

```python
# ~/.config/cua/plugins/hello.py
from computer_use_agent.plugins import ActionRegistry

def register(registry: ActionRegistry):
    @registry.register(
        name="send_email",
        description="Send an email via SMTP. Use this for sending notifications.",
        schema={
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string", "description": "Email subject"},
                "body":    {"type": "string", "description": "Email body"},
            },
            "required": ["to", "subject", "body"],
        },
    )
    def send_email(to: str, subject: str, body: str) -> str:
        # Replace with real SMTP / API call
        print(f"[PLUGIN] send_email to={to} subject={subject!r} body_len={len(body)}")
        return f"📧 Email sent to {to}: {subject}"
```

### 3. Use it

Run CUA. The agent will discover the plugin automatically and the LLM can now call
`send_email` action. The system prompt is extended with the plugin's action schema.

## Plugin discovery

Plugins are loaded from these locations (in order):

| Location | Default | Override via |
|---|---|---|
| `$XDG_CONFIG_HOME/cua/plugins/` | `~/.config/cua/plugins/` | `XDG_CONFIG_HOME` env |
| `$CUA_PLUGINS_DIR` | _(none)_ | `CUA_PLUGINS_DIR` env |
| `~/.cua/plugins/` | `~/.cua/plugins/` | — |

Each `*.py` file (not starting with `_`) is loaded as a module. A module is treated
as a plugin if it defines a `register(registry)` function.

## Plugin API

### `ActionRegistry`

```python
class ActionRegistry:
    def register(
        self,
        name: str,
        description: str = "",
        schema: dict | None = None,
    ) -> Callable:
        """Decorator: register a function as an action."""

    def register_method(
        self,
        name: str,
        fn: Callable,
        description: str = "",
        schema: dict | None = None,
    ) -> None:
        """Imperative: register a function directly."""

    def get(self, name: str) -> tuple[Callable, dict]:
        """Returns (function, metadata_dict)."""

    def has(self, name: str) -> bool: ...
    def list_names(self) -> list[str]: ...
    def list_all(self) -> list[dict]: ...
```

### Function signature

The action function receives parameters as **keyword arguments** based on the JSON
schema's `properties`. The LLM sees the schema and decides which values to provide.

```python
@registry.register(name="my_action", description="...", schema={...})
def my_action(param1: str, param2: int = 0) -> str:
    # Return a string describing the result (sent back to LLM)
    return f"result for {param1}"
```

The return value is included in the agent's history as the action result.

### Schema

If you don't provide `schema`, the registry tries to infer it from the function
signature using `_infer_schema`:

```python
def my_fn(name: str, count: int, optional: bool = True) -> str:
    """..."""

# Inferred schema:
{
    "type": "object",
    "properties": {
        "name":     {"type": "string"},
        "count":    {"type": "integer"},
        "optional": {"type": "boolean"},
    },
    "required": ["name", "count"],
}
```

For complex types, provide an explicit schema:

```python
schema = {
    "type": "object",
    "properties": {
        "tags":  {"type": "array", "items": {"type": "string"}},
        "meta":  {"type": "object"},
        "level": {"type": "string", "enum": ["info", "warn", "error"]},
    },
    "required": ["level"],
}
```

## Examples

### Example 1: HTTP API call

```python
# ~/.config/cua/plugins/weather.py
import urllib.request
import json
from computer_use_agent.plugins import ActionRegistry

def register(registry: ActionRegistry):
    @registry.register(
        name="get_weather",
        description="Get current weather for a city. Use when user asks about weather.",
        schema={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'Tokyo'"},
            },
            "required": ["city"],
        },
    )
    def get_weather(city: str) -> str:
        url = f"https://wttr.in/{city}?format=j1"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
            current = data["current_condition"][0]
            return (
                f"Weather in {city}: {current['temp_C']}°C, "
                f"{current['weatherDesc'][0]['value']}, "
                f"humidity {current['humidity']}%"
            )
        except Exception as e:
            return f"Failed to fetch weather: {e}"
```

### Example 2: Read clipboard

```python
# ~/.config/cua/plugins/clipboard.py
import subprocess
from computer_use_agent.plugins import ActionRegistry

def register(registry: ActionRegistry):
    @registry.register(
        name="read_clipboard",
        description="Read the current text content of the system clipboard.",
        schema={"type": "object", "properties": {}},
    )
    def read_clipboard() -> str:
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip() or "(clipboard is empty)"
        except FileNotFoundError:
            # macOS / Linux fallback
            r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            return r.stdout or "(clipboard is empty)"
```

### Example 3: Imperative registration (multiple actions per file)

```python
# ~/.config/cua/plugins/dev_tools.py
import subprocess
from computer_use_agent.plugins import ActionRegistry

def _run(cmd: str) -> str:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return r.stdout + r.stderr

def register(registry: ActionRegistry):
    registry.register_method(
        name="run_shell",
        fn=lambda cmd: _run(cmd),
        description="Run a shell command and return its output. Use carefully.",
        schema={
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "Shell command to execute"},
            },
            "required": ["cmd"],
        },
    )

    registry.register_method(
        name="read_file",
        fn=lambda path: open(path, encoding="utf-8").read(),
        description="Read the contents of a text file.",
        schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
            },
            "required": ["path"],
        },
    )
```

## Plugin safety

Plugins run with **the same privileges as the CUA process**. A malicious plugin
can:

- Read / write any file the user can
- Make network requests
- Execute arbitrary code

**Only install plugins you trust.** Review the source before dropping a `.py` file
into `~/.config/cua/plugins/`.

For production use, consider:

- Sandboxing CUA itself (Docker, VM)
- Auditing plugin code in version control
- Using the `LOG_FORMAT=json` to capture all plugin invocations

## Testing plugins

```python
# test_my_plugin.py
from computer_use_agent.plugins import ActionRegistry, reset_registry
from computer_use_agent.i18n import set_language

def test_my_plugin():
    set_language("en-US")
    reset_registry()
    reg = ActionRegistry()

    # Load your plugin
    import my_plugin
    my_plugin.register(reg)

    # Verify it's registered
    assert "my_action" in reg
    fn, meta = reg.get("my_action")
    assert meta["description"]

    # Call it
    result = fn(param1="hello", param2=42)
    assert "result" in result.lower()
```

## Debugging

Enable debug logging to see plugin discovery:

```bash
LOG_LEVEL=DEBUG cua
```

You'll see lines like:
```
[DEBUG] Registered action: send_email
[INFO]  Loaded 3 user plugin(s)
```

To see all registered actions at runtime:

```python
from computer_use_agent.plugins import get_registry
reg = get_registry()
for meta in reg.list_all():
    print(f"- {meta['name']}: {meta['description']}")
```

## Distributing plugins

For teams, you can package plugins as a Python package with an entry point:

```toml
# pyproject.toml of your plugin package
[project.entry-points."computer_use_agent.plugins"]
my_plugin = "my_pkg.plugin:register"
```

When that package is installed in the same environment as CUA, your plugin is
auto-discovered (this feature is reserved for future versions; for now, the
filesystem-based discovery in `~/.config/cua/plugins/` is the supported path).
