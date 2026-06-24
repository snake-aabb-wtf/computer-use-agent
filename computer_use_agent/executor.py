"""动作执行器 - 12 种桌面操作

借鉴 UI-TARS:
- 动作名称归一化 (60+ 变体 -> 20 标准名)
- 坐标归一化 (0-1000 -> 实际像素)
"""

import time
import subprocess
import platform
import pyautogui

# pyautogui 安全设置
# 修复 B6: FAILSAFE 改为可配置（默认 False；启用 FAILSAFE 时把鼠标移到屏幕角落可紧急停止）
# 警告：pyautogui.FAILSAFE 启用后会让自动化在鼠标撞角时崩溃，仅在你需要"硬件 kill switch"时打开
import os as _os

def _resolve_pyautogui_failsafe() -> bool:
    """从 PYAUTOGUI_FAILSAFE 环境变量解析（默认 False）。"""
    raw = _os.getenv("PYAUTOGUI_FAILSAFE")
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")

pyautogui.FAILSAFE = _resolve_pyautogui_failsafe()
pyautogui.PAUSE = 0


# 修复 F8.1: i18n 辅助
def _i(key: str, *args) -> str:
    """获取国际化字符串（fallback 到中文）。"""
    try:
        from .i18n import t
        return t(key, *args) if args else t(key)
    except Exception:
        return key

# ═══════════════════════════════════════════════════════════
# 动作名称归一化 (借鉴 UI-TARS actionTypeMap)
# ═══════════════════════════════════════════════════════════

_ACTION_MAP = {
    "click": "left_click", "left_click": "left_click", "left_single": "left_click",
    "leftsingle": "left_click", "leftclick": "left_click",
    "double_click": "double_click", "left_double": "double_click",
    "doubleclick": "double_click", "leftdouble": "double_click",
    "right_click": "right_click", "right_single": "right_click",
    "rightsingle": "right_click", "rightclick": "right_click",
    "type": "type", "input": "type", "typewrite": "type",
    "key": "key", "press": "key", "presskey": "key",
    "hotkey": "hotkey", "hot_key": "hotkey", "keycombo": "hotkey", "key_combo": "hotkey",
    "scroll": "scroll", "mouse_scroll": "scroll",
    "move": "move", "mouse_move": "move", "moveto": "move", "move_to": "move", "hover": "move",
    "drag": "drag", "mouse_drag": "drag", "dragto": "drag", "drag_to": "drag",
    "wait": "wait", "sleep": "wait", "pause": "wait",
    "screenshot": "screenshot", "capture": "screenshot",
    "done": "done", "finished": "done", "complete": "done", "finish": "done", "call_user": "done",
}


def normalize_action(action: dict) -> dict:
    """归一化动作名称和坐标 (借鉴 UI-TARS)。"""
    act = action.get("action", "")
    normalized = _ACTION_MAP.get(act.lower(), act)
    if normalized != act:
        action = dict(action)
        action["action"] = normalized

    # 坐标归一化: 浮点数 0-1000 -> 实际像素
    if "coordinate" in action:
        coord = action["coordinate"]
        if isinstance(coord, (list, tuple)) and len(coord) == 2:
            x, y = coord
            if isinstance(x, float) or isinstance(y, float):
                sw, sh = pyautogui.size()
                action = dict(action)
                action["coordinate"] = [int(x / 1000 * sw), int(y / 1000 * sh)]

    if "from" in action and "to" in action:
        fr = action["from"]
        to = action["to"]
        if isinstance(fr, (list, tuple)) and isinstance(to, (list, tuple)):
            sw, sh = pyautogui.size()
            new_from, new_to = list(fr), list(to)
            if isinstance(fr[0], float) or isinstance(fr[1], float):
                new_from = [int(fr[0] / 1000 * sw), int(fr[1] / 1000 * sh)]
            if isinstance(to[0], float) or isinstance(to[1], float):
                new_to = [int(to[0] / 1000 * sw), int(to[1] / 1000 * sh)]
            if new_from != list(fr) or new_to != list(to):
                action = dict(action)
                action["from"] = new_from
                action["to"] = new_to

    return action


# ═══════════════════════════════════════════════════════════
# 按键别名映射
_KEY_ALIASES = {
    "return": "enter",
    "ret": "enter",
    "esc": "escape",
    "ctl": "ctrl",
    "cmd": "win",
    "command": "win",
    "spacebar": "space",
    "del": "delete",
    "ins": "insert",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "arrowup": "up",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
}


def _normalize_key(key: str) -> str:
    return _KEY_ALIASES.get(key.lower(), key.lower())


def _trigger_click(x: int, y: int):
    """触发视觉点击效果。"""
    try:
        from . import config
        if config.VISUAL_EFFECTS:
            from .visual_effects import trigger_click
            trigger_click(x, y)
    except Exception:
        pass


def _trigger_drag(x1: int, y1: int, x2: int, y2: int):
    """触发视觉拖拽效果。"""
    try:
        from . import config
        if config.VISUAL_EFFECTS:
            from .visual_effects import trigger_drag
            trigger_drag(x1, y1, x2, y2)
    except Exception:
        pass


def _show_action_info(action: str, thought: str = "", coords: str = ""):
    """显示动作信息面板。"""
    try:
        from . import config
        if config.VISUAL_EFFECTS:
            from .visual_effects import show_action_info
            show_action_info(action, thought, coords)
    except Exception:
        pass


# SOM 元素缓存 - 由 agent.py 设置
# 修复 S4: 加锁保护
import threading as _threading
_som_elements: list = []
_som_lock = _threading.Lock()


def set_som_elements(elements: list):
    """设置当前 SOM 元素列表，供 executor 解析 element=N。"""
    global _som_elements
    with _som_lock:
        _som_elements = list(elements) if elements else []


def _resolve_click_target(action: dict) -> tuple[int, int]:
    """解析点击目标：优先 element=N，fallback 到 coordinate=[x,y]。"""
    if "element" in action:
        elem_idx = action["element"]
        with _som_lock:
            elements_snapshot = list(_som_elements)
        for elem in elements_snapshot:
            if elem.index == elem_idx:
                return elem.center()
        # 找不到元素，fallback 到屏幕中心
        import pyautogui
        w, h = pyautogui.size()
        return w // 2, h // 2
    return action["coordinate"]


def _type_text(text: str):
    """输入文本 - 使用剪贴板粘贴，支持中文和特殊字符。

    借鉴 Hermes 的剪贴板策略:
    - 短文本 (<=10字符): pyautogui.typewrite 快速输入
    - 长文本/含特殊字符: 剪贴板粘贴
    """
    # 修复 D6: 把制表符和换行也视为可打印 ASCII（typewrite 不支持）
    is_ascii = all(32 <= ord(c) <= 126 or c in "\t\n\r" for c in text)

    if is_ascii and len(text) <= 10:
        # 短 ASCII 文本直接打字
        pyautogui.typewrite(text, interval=0.01)
    else:
        # 长文本或含非 ASCII 字符：用剪贴板粘贴
        _clipboard_paste(text)


def _clipboard_paste(text: str):
    """通过剪贴板粘贴文本，支持中文、日文、韩文等。"""
    os_name = platform.system()

    if os_name == "Windows":
        # Windows: 使用 PowerShell 通过 stdin 设置剪贴板，避免命令注入和长度限制
        try:
            process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", "-"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "[System.Windows.Forms.Clipboard]::SetText($input)"
            )
            process.communicate(
                (script + "\n" + text).encode("utf-8"),
                timeout=5
            )
        except Exception:
            # 备用方案：使用 pyperclip
            try:
                import pyperclip
                pyperclip.copy(text)
            except ImportError:
                return

        # 粘贴
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)

    elif os_name == "Darwin":
        # macOS: 使用 pbcopy
        try:
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            process.communicate(text.encode("utf-8"))
        except Exception:
            pass
        time.sleep(0.05)
        pyautogui.hotkey("command", "v")
        time.sleep(0.1)

    else:
        # Linux: 使用 xclip 或 xsel
        try:
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE
            )
            process.communicate(text.encode("utf-8"))
        except FileNotFoundError:
            try:
                process = subprocess.Popen(
                    ["xsel", "--clipboard", "--input"],
                    stdin=subprocess.PIPE
                )
                process.communicate(text.encode("utf-8"))
            except Exception:
                pass
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)


def execute(action: dict) -> str:
    """执行一个动作，返回执行结果描述。

    Args:
        action: 动作字典，必须包含 "action" 字段

    Returns:
        执行结果的文字描述
    """
    # 借鉴 UI-TARS: 仅在 uitars 模式下归一化
    from . import config
    if config.CAPTURE_MODE == "uitars":
        action = normalize_action(action)

    act = action.get("action", "")
    thought = action.get("thought", "")

    try:
        if act == "left_click":
            x, y = _resolve_click_target(action)
            _show_action_info("Click", action.get("thought", ""), f"({x}, {y})")
            _trigger_click(x, y)
            time.sleep(0.15)
            pyautogui.click(x, y, button="left")
            if "element" in action:
                return _i("act_left_click_element", action['element'], x, y)
            return _i("act_left_click", x, y)

        elif act == "double_click":
            x, y = _resolve_click_target(action)
            _show_action_info("Double Click", action.get("thought", ""), f"({x}, {y})")
            _trigger_click(x, y)
            time.sleep(0.15)
            pyautogui.doubleClick(x, y)
            if "element" in action:
                return _i("act_double_click_element", action['element'], x, y)
            return _i("act_double_click", x, y)

        elif act == "right_click":
            x, y = _resolve_click_target(action)
            _show_action_info("Right Click", action.get("thought", ""), f"({x}, {y})")
            _trigger_click(x, y)
            time.sleep(0.15)
            pyautogui.rightClick(x, y)
            if "element" in action:
                return _i("act_right_click_element", action['element'], x, y)
            return _i("act_right_click", x, y)

        elif act == "type":
            text = action["text"]
            _type_text(text)
            return _i("act_type_text", len(text))

        elif act == "key":
            key = _normalize_key(action["key"])
            hold_time = action.get("hold", 0)
            if hold_time > 0:
                # 长按：按住指定时间后松开
                pyautogui.keyDown(key)
                time.sleep(hold_time)
                pyautogui.keyUp(key)
                return _i("act_hold_key", key, hold_time)
            else:
                pyautogui.press(key)
                return _i("act_press_key", key)

        elif act == "hotkey":
            keys = [_normalize_key(k) for k in action["keys"]]
            pyautogui.hotkey(*keys)
            return f"组合键 [{'+'.join(keys)}]"

        elif act == "scroll":
            direction = action.get("direction", "down")
            amount = action.get("amount", 5)
            # 借鉴: 浏览器需要大幅滚动，每个单位 = 3 次滚动
            # pyautogui.scroll() 每个 click 只滚动几行
            # 乘以 100 让 amount=5 等于滚动 500 个 click（约 10 页）
            clicks = -amount * 100 if direction == "down" else amount * 100
            pyautogui.scroll(clicks)
            return _i("act_scroll", direction, amount)

        elif act == "move":
            x, y = action["coordinate"]
            pyautogui.moveTo(x, y)
            return _i("act_move_mouse", x, y)

        elif act == "drag":
            fx, fy = action["from"]
            tx, ty = action["to"]
            hold_time = action.get("hold", 0.3)
            _show_action_info("Drag", action.get("thought", ""), f"({fx},{fy}) -> ({tx},{ty})")
            _trigger_drag(fx, fy, tx, ty)
            # 借鉴 UI-TARS: 自然拖拽 - 移动→按住→停留→逐步移动→松开
            pyautogui.moveTo(fx, fy)
            pyautogui.mouseDown()
            time.sleep(hold_time)
            steps = 10
            for i in range(1, steps + 1):
                cx = fx + (tx - fx) * i / steps
                cy = fy + (ty - fy) * i / steps
                pyautogui.moveTo(cx, cy)
                time.sleep(0.02)
            pyautogui.mouseUp()
            return _i("act_drag", fx, fy, tx, ty, hold_time)

        elif act == "wait":
            seconds = action.get("seconds", 1)
            time.sleep(seconds)
            return _i("act_wait", seconds)

        elif act == "screenshot":
            return _i("act_screenshot")

        elif act == "done":
            msg = action.get("message", "任务完成")
            return f"✅ 完成: {msg}"

        else:
            return f"未知动作: {act}"

    except Exception as e:
        return f"❌ 执行失败 [{act}]: {e}"
