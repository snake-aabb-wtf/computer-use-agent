"""Visual effects - mouse click ripple only

Experimental feature: ripple/wave effect on mouse clicks.
Controlled by VISUAL_EFFECTS in .env (default: off).
"""

import sys
import time
import threading
import queue
import math

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32

    WS_EX_LAYERED = 0x80000
    WS_EX_TRANSPARENT = 0x20
    WS_EX_TOPMOST = 0x8
    WS_EX_TOOLWINDOW = 0x80
    WS_POPUP = 0x80000000
    LWA_COLORKEY = 0x1
    RGB_BLACK = 0x000000


class RippleEffect:
    """Mouse click ripple effect using Win32 overlay."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._hwnd = None
        self._ripples = []
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        time.sleep(0.2)

    def stop(self):
        self._running = False
        if self._hwnd:
            try:
                user32.ShowWindow(self._hwnd, 0)
                user32.DestroyWindow(self._hwnd)
            except Exception:
                pass
        self._hwnd = None

    def trigger(self, x: int, y: int):
        with self._lock:
            self._ripples.append([x, y, 0, 50, 1.0])

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
                self._draw_ripples(hwnd, sw, sh)
                time.sleep(0.033)

        except Exception:
            self._running = False

    def _draw_ripples(self, hwnd, sw, sh):
        try:
            hdc = user32.GetDC(hwnd)

            # Clear
            brush = gdi32.CreateSolidBrush(RGB_BLACK)
            old_brush = gdi32.SelectObject(hdc, brush)
            gdi32.Rectangle(hdc, 0, 0, sw, sh)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.DeleteObject(brush)

            new_ripples = []
            with self._lock:
                for ripple in self._ripples:
                    x, y, radius, max_radius, alpha = ripple
                    radius += 2
                    alpha -= 0.04
                    if alpha > 0 and radius < max_radius:
                        intensity = int(alpha * 255)
                        b = intensity
                        g = int(intensity * 0.7)
                        r = int(intensity * 0.3)
                        color = (b << 16) | (g << 8) | r

                        pen = gdi32.CreatePen(0, 2, color)
                        old_pen = gdi32.SelectObject(hdc, pen)
                        hollow = gdi32.GetStockObject(5)
                        old_brush2 = gdi32.SelectObject(hdc, hollow)

                        gdi32.Ellipse(hdc, x - radius, y - radius, x + radius, y + radius)

                        gdi32.SelectObject(hdc, old_brush2)
                        gdi32.SelectObject(hdc, old_pen)
                        gdi32.DeleteObject(pen)

                        new_ripples.append([x, y, radius, max_radius, alpha])
                self._ripples = new_ripples

            user32.ReleaseDC(hwnd, hdc)
        except Exception:
            pass


# Global state
_ripple = None
_enabled = False


def init_effects(enabled: bool = False):
    global _ripple, _enabled
    _enabled = enabled
    if not enabled:
        return
    _ripple = RippleEffect()
    _ripple.start()


def trigger_ripple(x: int, y: int):
    if _enabled and _ripple:
        _ripple.trigger(x, y)


def cleanup():
    global _ripple, _enabled
    _enabled = False
    if _ripple:
        _ripple.stop()
    _ripple = None
