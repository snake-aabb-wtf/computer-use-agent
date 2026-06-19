"""Visual effects - click indicator, drag indicator, action info panel

Inspired by UI-TARS-desktop visual effects:
- Click: pulsing green circle with center dot (1.2s)
- Drag: orange start + cyan end circles with gradient path (3s)
- Action info: floating panel showing current action (persistent)

Controlled by VISUAL_EFFECTS in .env (default: off).
"""

import sys
import time
import threading
import queue
import math
import ctypes

if sys.platform == "win32":
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    WS_EX_LAYERED = 0x80000
    WS_EX_TRANSPARENT = 0x20
    WS_EX_TOPMOST = 0x8
    WS_EX_TOOLWINDOW = 0x80
    WS_POPUP = 0x80000000
    LWA_COLORKEY = 0x1
    RGB_BLACK = 0x000000


class VisualOverlay:
    """Single Win32 overlay handling all visual effects."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._hwnd = None
        self._queue = queue.Queue()
        self._effects = []  # List of (type, data, start_time)
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        for _ in range(50):
            if self._hwnd is not None:
                break
            time.sleep(0.02)

    def stop(self):
        self._running = False
        if self._hwnd:
            try:
                user32.ShowWindow(self._hwnd, 0)
                user32.DestroyWindow(self._hwnd)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=1)
        self._hwnd = None

    def trigger_click(self, x: int, y: int):
        """触发点击涟漪（绿色脉冲圆圈）。"""
        self._queue.put(("click", x, y, time.time()))

    def trigger_drag(self, x1: int, y1: int, x2: int, y2: int):
        """触发拖拽指示器（起点/终点圆圈 + 渐变线）。"""
        self._queue.put(("drag", x1, y1, x2, y2, time.time()))

    def show_action_info(self, action: str, thought: str = "", coords: str = ""):
        """显示动作信息面板。"""
        self._queue.put(("info", action, thought, coords, time.time()))

    def _run(self):
        try:
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)

            hwnd = user32.CreateWindowExW(
                WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
                "Static", "",
                WS_POPUP,
                0, 0, sw, sh,
                None, None, None, None
            )
            self._hwnd = hwnd
            user32.SetLayeredWindowAttributes(hwnd, RGB_BLACK, 0, LWA_COLORKEY)
            user32.ShowWindow(hwnd, 8)

            while self._running:
                self._process_queue()
                self._draw(sw, sh)
                time.sleep(0.016)  # 60 FPS

        except Exception:
            self._running = False

    def _process_queue(self):
        try:
            while not self._queue.empty():
                cmd = self._queue.get_nowait()
                now = time.time()
                if cmd[0] == "click":
                    _, x, y, t = cmd
                    with self._lock:
                        self._effects.append(("click", (x, y), t))
                elif cmd[0] == "drag":
                    _, x1, y1, x2, y2, t = cmd
                    with self._lock:
                        self._effects.append(("drag", (x1, y1, x2, y2), t))
                elif cmd[0] == "info":
                    _, action, thought, coords, t = cmd
                    with self._lock:
                        # Replace existing info
                        self._effects = [e for e in self._effects if e[0] != "info"]
                        self._effects.append(("info", (action, thought, coords), t))
        except queue.Empty:
            pass

    def _draw(self, sw, sh):
        try:
            hdc = user32.GetDC(self._hwnd)

            # Clear
            brush = gdi32.CreateSolidBrush(RGB_BLACK)
            old_brush = gdi32.SelectObject(hdc, brush)
            gdi32.Rectangle(hdc, 0, 0, sw, sh)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.DeleteObject(brush)

            now = time.time()
            with self._lock:
                active_effects = []
                for effect in self._effects:
                    etype, data, t = effect
                    age = now - t

                    if etype == "click" and age < 1.2:
                        self._draw_click_indicator(hdc, data, age)
                        active_effects.append(effect)
                    elif etype == "drag" and age < 3.0:
                        self._draw_drag_indicator(hdc, data, age)
                        active_effects.append(effect)
                    elif etype == "info":
                        active_effects.append(effect)
                    elif etype in ("click", "drag"):
                        pass  # expired
                    else:
                        active_effects.append(effect)

                self._effects = active_effects

            user32.ReleaseDC(self._hwnd, hdc)
        except Exception:
            pass

    def _draw_click_indicator(self, hdc, pos, age):
        """绘制点击涟漪 - 借鉴 UI-TARS click indicator。

        绿色脉冲圆圈 + 中心点，1.2s 消失。
        """
        x, y = pos

        # 动画：从 0.8x 扩展到 2.5x，同时淡出
        progress = age / 1.2  # 0.0 -> 1.0
        scale = 0.8 + progress * 1.7  # 0.8 -> 2.5
        alpha = max(0, 1.0 - progress)  # 1.0 -> 0.0

        radius = int(30 * scale)

        # 外圈：绿色 (#00ff9d)
        r = 0
        g = int(alpha * 255)
        b = int(alpha * 157)
        color = (b << 16) | (g << 8) | r

        pen = gdi32.CreatePen(0, 3, color)
        old_pen = gdi32.SelectObject(hdc, pen)
        hollow = gdi32.GetStockObject(5)
        old_brush = gdi32.SelectObject(hdc, hollow)
        gdi32.Ellipse(hdc, x - radius, y - radius, x + radius, y + radius)
        gdi32.SelectObject(hdc, old_brush)
        gdi32.SelectObject(hdc, old_pen)
        gdi32.DeleteObject(pen)

        # 中心点：实心绿色
        dot_r = int(6 * scale)
        brush = gdi32.CreateSolidBrush(color)
        old_brush = gdi32.SelectObject(hdc, brush)
        gdi32.Ellipse(hdc, x - dot_r, y - dot_r, x + dot_r, y + dot_r)
        gdi32.SelectObject(hdc, old_brush)
        gdi32.DeleteObject(brush)

    def _draw_drag_indicator(self, hdc, points, age):
        """绘制拖拽指示器 - 借鉴 UI-TARS drag indicator。

        橙色起点 + 青色终点 + 渐变连接线。
        """
        x1, y1, x2, y2 = points
        progress = min(1.0, age / 3.0)
        alpha = max(0, 1.0 - progress)

        # 起点：橙色圆圈 (#ff6b00)
        sr = int(alpha * 255)
        sg = int(alpha * 107)
        sb = 0
        scolor = (sb << 16) | (sg << 8) | sr
        brush = gdi32.CreateSolidBrush(scolor)
        old_brush = gdi32.SelectObject(hdc, brush)
        gdi32.Ellipse(hdc, x1 - 15, y1 - 15, x1 + 15, y1 + 15)
        gdi32.SelectObject(hdc, old_brush)
        gdi32.DeleteObject(brush)

        # 终点：青色圆圈 (#00c3ff)
        er = 0
        eg = int(alpha * 195)
        eb = int(alpha * 255)
        ecolor = (eb << 16) | (eg << 8) | er
        brush = gdi32.CreateSolidBrush(ecolor)
        old_brush = gdi32.SelectObject(hdc, brush)
        gdi32.Ellipse(hdc, x2 - 15, y2 - 15, x2 + 15, y2 + 15)
        gdi32.SelectObject(hdc, old_brush)
        gdi32.DeleteObject(brush)

        # 连接线：渐变色
        pen = gdi32.CreatePen(0, 2, ecolor)
        old_pen = gdi32.SelectObject(hdc, pen)
        gdi32.MoveToEx(hdc, x1, y1, None)
        gdi32.LineTo(hdc, x2, y2)
        gdi32.SelectObject(hdc, old_pen)
        gdi32.DeleteObject(pen)

        # 箭头：终点处的小三角
        arrow_len = 12
        dx = x2 - x1
        dy = y2 - y1
        length = max(1, math.sqrt(dx*dx + dy*dy))
        ux, uy = dx/length, dy/length
        # 箭头两侧点
        ax1 = int(x2 - ux*arrow_len + uy*arrow_len*0.5)
        ay1 = int(y2 - uy*arrow_len - ux*arrow_len*0.5)
        ax2 = int(x2 - ux*arrow_len - uy*arrow_len*0.5)
        ay2 = int(y2 - uy*arrow_len + ux*arrow_len*0.5)
        pen = gdi32.CreatePen(0, 2, ecolor)
        old_pen = gdi32.SelectObject(hdc, pen)
        gdi32.MoveToEx(hdc, x2, y2, None)
        gdi32.LineTo(hdc, ax1, ay1)
        gdi32.MoveToEx(hdc, x2, y2, None)
        gdi32.LineTo(hdc, ax2, ay2)
        gdi32.SelectObject(hdc, old_pen)
        gdi32.DeleteObject(pen)


# ═══════════════════════════════════════════════════════════
# Global state
# ═══════════════════════════════════════════════════════════

_overlay = None
_enabled = False


def init_effects(enabled: bool = False):
    global _overlay, _enabled
    _enabled = enabled
    if not enabled:
        return
    _overlay = VisualOverlay()
    _overlay.start()


def trigger_click(x: int, y: int):
    if _enabled and _overlay:
        _overlay.trigger_click(x, y)


def trigger_drag(x1: int, y1: int, x2: int, y2: int):
    if _enabled and _overlay:
        _overlay.trigger_drag(x1, y1, x2, y2)


def show_action_info(action: str, thought: str = "", coords: str = ""):
    if _enabled and _overlay:
        _overlay.show_action_info(action, thought, coords)


def cleanup():
    global _overlay, _enabled
    _enabled = False
    if _overlay:
        _overlay.stop()
    _overlay = None
