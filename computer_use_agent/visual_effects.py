"""Visual effects - breathing border + mouse ripple

Uses Win32 API for overlay rendering (no tkinter threading issues).
"""

import sys
import time
import threading
import ctypes
import ctypes.wintypes

if sys.platform == "win32":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Win32 constants
    WS_EX_LAYERED = 0x80000
    WS_EX_TRANSPARENT = 0x20
    WS_EX_TOPMOST = 0x8
    WS_EX_TOOLWINDOW = 0x80
    WS_POPUP = 0x80000000
    LWA_ALPHA = 0x2
    LWA_COLORKEY = 0x1
    RGB_BLACK = 0x000000


class BreathingBorder:
    """Full-screen overlay with animated blue breathing border using Win32."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._hwnd = None
        self._opacity = 0.0
        self._direction = 1
        self._border_width = 4

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
                user32.ShowWindow(self._hwnd, 0)  # SW_HIDE
                user32.DestroyWindow(self._hwnd)
            except Exception:
                pass
        self._hwnd = None

    def _run(self):
        try:
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)

            # Create layered, transparent, topmost popup window
            hwnd = user32.CreateWindowExW(
                WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
                "Static", "",
                WS_POPUP,
                0, 0, sw, sh,
                None, None, None, None
            )
            self._hwnd = hwnd

            # Make window transparent (black = transparent)
            user32.SetLayeredWindowAttributes(hwnd, RGB_BLACK, 0, LWA_COLORKEY)

            # Show the window
            user32.ShowWindow(hwnd, 8)  # SW_SHOWNA (no activation)

            while self._running:
                self._draw_border(hwnd, sw, sh)
                time.sleep(0.05)  # 20 FPS

        except Exception:
            self._running = False

    def _draw_border(self, hwnd, sw, sh):
        """Draw the breathing border using GDI."""
        try:
            # Breathing animation
            self._opacity += self._direction * 0.02
            if self._opacity >= 0.5:
                self._opacity = 0.5
                self._direction = -1
            elif self._opacity <= 0.0:
                self._opacity = 0.0
                self._direction = 1

            # Get DC
            hdc = user32.GetDC(hwnd)

            # Create blue brush with breathing intensity
            intensity = int(self._opacity * 255)
            b = intensity
            g = int(intensity * 0.5)
            r = int(intensity * 0.2)
            color = (b << 16) | (g << 8) | r  # BGR format

            brush = gdi32.CreateSolidBrush(color)
            old_brush = gdi32.SelectObject(hdc, brush)

            # Draw border rectangles (4 sides)
            bw = self._border_width
            # Top
            gdi32.Rectangle(hdc, 0, 0, sw, bw)
            # Bottom
            gdi32.Rectangle(hdc, 0, sh - bw, sw, sh)
            # Left
            gdi32.Rectangle(hdc, 0, 0, bw, sh)
            # Right
            gdi32.Rectangle(hdc, sw - bw, 0, sw, sh)

            # Cleanup
            gdi32.SelectObject(hdc, old_brush)
            gdi32.DeleteObject(brush)
            user32.ReleaseDC(hwnd, hdc)

        except Exception:
            pass


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
                time.sleep(0.033)  # 30 FPS

        except Exception:
            self._running = False

    def _draw_ripples(self, hwnd, sw, sh):
        try:
            hdc = user32.GetDC(hwnd)
            # Clear with black (transparent)
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
                        # Draw circle using Ellipse
                        intensity = int(alpha * 255)
                        b = intensity
                        g = int(intensity * 0.7)
                        r = int(intensity * 0.3)
                        color = (b << 16) | (g << 8) | r

                        pen = gdi32.CreatePen(0, 2, color)
                        old_pen = gdi32.SelectObject(hdc, pen)
                        hollow_brush = gdi32.GetStockObject(5)  # NULL_BRUSH
                        old_brush2 = gdi32.SelectObject(hdc, hollow_brush)

                        gdi32.Ellipse(hdc, x - radius, y - radius, x + radius, y + radius)

                        gdi32.SelectObject(hdc, old_brush2)
                        gdi32.SelectObject(hdc, old_pen)
                        gdi32.DeleteObject(pen)

                        new_ripples.append([x, y, radius, max_radius, alpha])
                self._ripples = new_ripples

            user32.ReleaseDC(hwnd, hdc)
        except Exception:
            pass


# GDI functions
gdi32 = ctypes.windll.gdi32

# Global state
_border = None
_ripple = None
_enabled = False


def init_effects(enabled: bool = False):
    global _border, _ripple, _enabled
    _enabled = enabled
    if not enabled:
        return
    _border = BreathingBorder()
    _ripple = RippleEffect()
    _border.start()
    _ripple.start()


def start_border():
    if _border:
        _border.start()


def stop_border():
    if _border:
        _border.stop()


def trigger_ripple(x: int, y: int):
    if _enabled and _ripple:
        _ripple.trigger(x, y)


def cleanup():
    global _border, _ripple, _enabled
    _enabled = False
    if _border:
        _border.stop()
    if _ripple:
        _ripple.stop()
    _border = None
    _ripple = None
