"""动作执行器 - 12 种桌面操作

借鉴 UI-TARS-desktop:
- 动作名称归一化 (60+ 变体 -> 20 标准名)
- 坐标归一化 (0-1000 -> 实际像素)
"""

import time
import subprocess
import platform
import pyautogui

# pyautogui 安全设置
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# ═══════════════════════════════════════════════════════════
# 动作名称归一化 (借鉴 UI-TARS actionTypeMap)
# ═══════════════════════════════════════════════════════════

_ACTION_MAP = {
    # click variants
    "click": "left_click",
    "left_click": "left_click",
    "left_single": "left_click",
    "leftsingle": "left_click",
    "leftclick": "left_click",
    # double click variants
    "double_click": "double_click",
    "left_double": "double_click",
    "doubleclick": "double_click",
    "leftdouble": "double_click",
    # right click variants
    "right_click": "right_click",
    "right_single": "right_click",
    "rightsingle": "right_click",
    "rightclick": "right_click",
    # type variants
    "type": "type",
    "input": "type",
    "typewrite": "type",
    # key variants
    "key": "key",
    "press": "key",
    "presskey": "key",
    # hotkey variants
    "hotkey": "hotkey",
    "hot_key": "hotkey",
    "keycombo": "hotkey",
    "key_combo": "hotkey",
    # scroll variants
    "scroll": "scroll",
    "mouse_scroll": "scroll",
    # move variants
    "move": "move",
    "mouse_move": "move",
    "moveto": "move",
    "move_to": "move",
    "hover": "move",
    # drag variants
    "drag": "drag",
    "mouse_drag": "drag",
    "dragto": "drag",
    "drag_to": "drag",
    # wait
    "wait": "wait",
    "sleep": "wait",
    "pause": "wait",
    # screenshot
    "screenshot": "screenshot",
    "capture": "screenshot",
    # done
    "done": "done",
    "finished": "done",
    "complete": "done",
    "finish": "done",
    "call_user": "done",
}


def normalize_action(action: dict) -> dict:
    """归一化动作名称和坐标。

    借鉴 UI-TARS:
    1. 动作名称: 60+ 变体 -> 20 标准名
    2. 坐标: 0-1000 归一化 -> 实际像素
    """
    act = action.get("action", "")
    normalized = _ACTION_MAP.get(act.lower(), act)
    if normalized != act:
        action = dict(action)
        action["action"] = normalized

    # 坐标归一化 (0-1000 -> 实际像素)
    # 借鉴 UI-TARS: 只有浮点数坐标才认为是归一化坐标
    if "coordinate" in action:
        coord = action["coordinate"]
        if isinstance(coord, (list, tuple)) and len(coord) == 2:
            x, y = coord
            # 只有 x 或 y 是浮点数时才归一化
            if isinstance(x, float) or isinstance(y, float):
                sw, sh = pyautogui.size()
                action = dict(action)
                action["coordinate"] = [int(x / 1000 * sw), int(y / 1000 * sh)]

    if "from" in action and "to" in action:
        fr = action["from"]
        to = action["to"]
        if isinstance(fr, (list, tuple)) and isinstance(to, (list, tuple)):
            sw, sh = pyautogui.size()
            new_from = list(fr)
            new_to = list(to)
            if 0 <= fr[0] <= 1000 and 0 <= fr[1] <= 1000:
                new_from = [int(fr[0] / 1000 * sw), int(fr[1] / 1000 * sh)]
            if 0 <= to[0] <= 1000 and 0 <= to[1] <= 1000:
                new_to = [int(to[0] / 1000 * sw), int(to[1] / 1000 * sh)]
            if new_from != list(fr) or new_to != list(to):
                action = dict(action)
                action["from"] = new_from
                action["to"] = new_to

    return action


# ═══════════════════════════════════════════════════════════
# 按键别名映射
# ═══════════════════════════════════════════════════════════
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


def _trigger_ripple(x: int, y: int):
    """Trigger visual ripple effect if enabled."""
    try:
        from . import config
        if config.VISUAL_EFFECTS:
            from .visual_effects import trigger_ripple
            trigger_ripple(x, y)
    except Exception:
        pass


# SOM 元素缓存 - 由 agent.py 设置
_som_elements: list = []


def set_som_elements(elements: list):
    """设置当前 SOM 元素列表，供 executor 解析 element=N。"""
    global _som_elements
    _som_elements = elements


def _resolve_click_target(action: dict) -> tuple[int, int]:
    """解析点击目标：优先 element=N，fallback 到 coordinate=[x,y]。"""
    if "element" in action:
        elem_idx = action["element"]
        for elem in _som_elements:
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
    # 检测是否全是 ASCII 可打印字符
    is_ascii = all(32 <= ord(c) <= 126 for c in text)

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
        # Windows: 使用 PowerShell 设置剪贴板
        # 使用 -NoProfile -NonInteractive 避免干扰
        cmd = [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            f"Set-Clipboard -Value '{text.replace(chr(39), chr(39)+chr(39))}'"
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
        except Exception:
            # 备用方案：使用 pyperclip
            try:
                import pyperclip
                pyperclip.copy(text)
            except ImportError:
                # 最后手段：逐字符输入（慢但可靠）
                for char in text:
                    pyautogui.press(char) if len(char) == 1 else None
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
    """执行一个动作，返回执行结果描述。"""
    # 借鉴 UI-TARS: 归一化动作名称和坐标
    action = normalize_action(action)

    act = action.get("action", "")
    thought = action.get("thought", "")

    try:
        if act == "left_click":
            x, y = _resolve_click_target(action)
            pyautogui.click(x, y, button="left")
            _trigger_ripple(x, y)
            if "element" in action:
                return f"左键点击元素 #{action['element']} ({x}, {y})"
            return f"左键点击 ({x}, {y})"

        elif act == "double_click":
            x, y = _resolve_click_target(action)
            pyautogui.doubleClick(x, y)
            _trigger_ripple(x, y)
            if "element" in action:
                return f"双击元素 #{action['element']} ({x}, {y})"
            return f"双击 ({x}, {y})"

        elif act == "right_click":
            x, y = _resolve_click_target(action)
            pyautogui.rightClick(x, y)
            _trigger_ripple(x, y)
            if "element" in action:
                return f"右键点击元素 #{action['element']} ({x}, {y})"
            return f"右键点击 ({x}, {y})"

        elif act == "type":
            text = action["text"]
            _type_text(text)
            return f"输入文本 ({len(text)} 字符)"

        elif act == "key":
            key = _normalize_key(action["key"])
            pyautogui.press(key)
            return f"按键 [{key}]"

        elif act == "hotkey":
            keys = [_normalize_key(k) for k in action["keys"]]
            pyautogui.hotkey(*keys)
            return f"组合键 [{'+'.join(keys)}]"

        elif act == "scroll":
            direction = action.get("direction", "down")
            amount = action.get("amount", 5)
            # 借鉴: 浏览器需要大幅滚动，每个单位 = 3 次滚动
            # pyautogui.scroll() 每个 click 只滚动几行
            # 乘以 3 让 amount=5 等于滚动 15 个 click（约半页）
            clicks = -amount * 3 if direction == "down" else amount * 3
            pyautogui.scroll(clicks)
            return f"滚动 {direction} ×{amount}"

        elif act == "move":
            x, y = action["coordinate"]
            pyautogui.moveTo(x, y)
            return f"移动鼠标到 ({x}, {y})"

        elif act == "drag":
            fx, fy = action["from"]
            tx, ty = action["to"]
            pyautogui.moveTo(fx, fy)
            pyautogui.drag(tx - fx, ty - fy, duration=0.3)
            return f"拖拽 ({fx},{fy}) → ({tx},{ty})"

        elif act == "wait":
            seconds = action.get("seconds", 1)
            time.sleep(seconds)
            return f"等待 {seconds}s"

        elif act == "screenshot":
            return "重新截图（无操作）"

        elif act == "done":
            msg = action.get("message", "任务完成")
            return f"✅ 完成: {msg}"

        else:
            return f"未知动作: {act}"

    except Exception as e:
        return f"❌ 执行失败 [{act}]: {e}"
