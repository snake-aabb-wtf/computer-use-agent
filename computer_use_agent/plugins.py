"""插件系统 - 修复 F7

用户可在以下位置放置插件：
1. `~/.config/cua/plugins/*.py` (XDG 标准)
2. `CUA_PLUGINS_DIR` 环境变量指定的目录
3. `cua_plugins` Python 包 (命名空间包)

每个插件是一个 .py 文件，必须定义 `register(registry)` 函数：

示例插件 `~/.config/cua/plugins/hello.py`:
    from computer_use_agent.plugins import ActionRegistry

    def register(registry: ActionRegistry):
        @registry.register(
            name="send_email",
            description="发送邮件到指定地址（示例插件）",
            schema={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        )
        def send_email(to: str, subject: str, body: str) -> str:
            # 实际发送邮件逻辑
            return f"📧 Email sent to {to}: {subject}"
"""

import os
import sys
import logging
import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Callable, Optional, Any

logger = logging.getLogger("agent.plugins")


class ActionRegistry:
    """动作注册中心。

    用法:
        registry = ActionRegistry()
        # 用装饰器注册
        @registry.register(name="my_action", description="...", schema={...})
        def my_action(x: int) -> str:
            return f"x={x}"
        # 用方法注册
        registry.register_method("another", some_fn, description="...")
        # 查询
        if "my_action" in registry:
            fn, meta = registry.get("my_action")
            result = fn(x=42)
    """

    def __init__(self):
        self._actions: dict[str, dict] = {}

    def register(
        self,
        name: str,
        description: str = "",
        schema: Optional[dict] = None,
    ):
        """装饰器：注册一个动作。"""
        def decorator(fn: Callable) -> Callable:
            self.register_method(name, fn, description=description, schema=schema)
            return fn
        return decorator

    def register_method(
        self,
        name: str,
        fn: Callable,
        description: str = "",
        schema: Optional[dict] = None,
    ) -> None:
        """直接注册一个函数为动作。"""
        if name in self._actions:
            logger.warning(f"Action '{name}' already registered, overwriting")
        self._actions[name] = {
            "fn": fn,
            "description": description or (fn.__doc__ or "").strip(),
            "schema": schema or _infer_schema(fn),
        }
        logger.debug(f"Registered action: {name}")

    def get(self, name: str) -> tuple[Callable, dict]:
        """获取已注册的动作。返回 (fn, metadata)。"""
        if name not in self._actions:
            raise KeyError(f"Action '{name}' not registered")
        return self._actions[name]["fn"], self._actions[name]

    def has(self, name: str) -> bool:
        return name in self._actions

    def __contains__(self, name: str) -> bool:
        return self.has(name)

    def list_names(self) -> list[str]:
        return list(self._actions.keys())

    def list_all(self) -> list[dict]:
        """列出所有动作的元数据。"""
        return [
            {"name": name, "description": meta["description"], "schema": meta["schema"]}
            for name, meta in self._actions.items()
        ]


def _infer_schema(fn: Callable) -> dict:
    """从函数签名推断 JSON schema（简易实现）。"""
    try:
        sig = inspect.signature(fn)
        properties = {}
        required = []
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        for pname, param in sig.parameters.items():
            if param.annotation in type_map:
                properties[pname] = {"type": type_map[param.annotation]}
            else:
                properties[pname] = {"type": "string"}
            if param.default is inspect.Parameter.empty:
                required.append(pname)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    except Exception:
        return {"type": "object"}


# ── 插件加载 ──

def _get_plugin_dirs() -> list[Path]:
    """获取所有插件目录。"""
    dirs = []

    # 1. XDG 标准 (~/.config/cua/plugins/)
    xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    xdg_plugin = Path(xdg_config) / "cua" / "plugins"
    if xdg_plugin.exists():
        dirs.append(xdg_plugin)

    # 2. CUA_PLUGINS_DIR 环境变量
    env_dir = os.environ.get("CUA_PLUGINS_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.exists():
            dirs.append(p)

    # 3. 用户目录下的 ~/.cua/plugins/
    user_plugin = Path.home() / ".cua" / "plugins"
    if user_plugin.exists():
        dirs.append(user_plugin)

    return dirs


def discover_and_load(registry: ActionRegistry) -> int:
    """发现并加载所有插件到 registry。

    Returns:
        加载的插件数量
    """
    loaded = 0
    plugin_dirs = _get_plugin_dirs()
    if not plugin_dirs:
        return 0

    for d in plugin_dirs:
        logger.debug(f"Scanning plugin dir: {d}")
        for f in sorted(d.glob("*.py")):
            if f.name.startswith("_"):
                continue
            try:
                if _load_plugin_file(registry, f):
                    loaded += 1
            except Exception as e:
                logger.warning(f"Failed to load plugin {f}: {e}")
    return loaded


def _load_plugin_file(registry: ActionRegistry, path: Path) -> bool:
    """从 .py 文件加载插件。"""
    spec = importlib.util.spec_from_file_location(
        f"cua_plugin_{path.stem}", path
    )
    if spec is None or spec.loader is None:
        return False
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # 调用 register(registry) 函数
    if hasattr(module, "register") and callable(module.register):
        module.register(registry)
        logger.info(f"Loaded plugin: {path.name}")
        return True
    else:
        logger.warning(f"Plugin {path.name} has no register() function")
        return False


# ── 全局注册中心 ──

_GLOBAL_REGISTRY: Optional[ActionRegistry] = None


def get_registry() -> ActionRegistry:
    """获取全局注册中心（首次调用时自动发现插件）。"""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ActionRegistry()
        # 内置动作直接注册
        _register_builtin(_GLOBAL_REGISTRY)
        # 用户插件
        n = discover_and_load(_GLOBAL_REGISTRY)
        if n > 0:
            logger.info(f"Loaded {n} user plugin(s)")
    return _GLOBAL_REGISTRY


def _register_builtin(registry: ActionRegistry) -> None:
    """注册内置动作（占位，未来可扩展）。"""
    # 目前没有内置；executor.py 里的 left_click / type 等走专用路径
    pass


def reset_registry() -> None:
    """重置全局注册中心（用于测试）。"""
    global _GLOBAL_REGISTRY
    _GLOBAL_REGISTRY = None
