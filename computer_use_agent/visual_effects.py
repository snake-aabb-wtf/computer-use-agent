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
        self._time = 0.0

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
        """Draw sci-fi breathing border with glow and corner accents."""
        try:
            # Animation time
            self._time += 0.05

            # Breathing: smooth sine wave
            breath = (math.sin(self._time * 2.0) + 1.0) / 2.0  # 0.0 ~ 1.0

            # Flash pulse: sharp spike every 2 seconds
            flash = max(0, math.sin(self._time * 3.14) ** 20)  # sharp pulse

            # Combined intensity
            intensity = breath * 0.4 + flash * 0.6

            hdc = user32.GetDC(hwnd)

            # --- Layer 1: Outer glow (wide, dim) ---
            glow_alpha = int(intensity * 60)
            glow_color = (glow_alpha << 16) | (int(glow_alpha * 1.5) << 8) | min(255, glow_alpha + 40)
            brush = gdi32.CreateSolidBrush(glow_color)
            old_brush = gdi32.SelectObject(hdc, brush)
            gw = 8
            gdi32.Rectangle(hdc, 0, 0, sw, gw)
            gdi32.Rectangle(hdc, 0, sh - gw, sw, sh)
            gdi32.Rectangle(hdc, 0, 0, gw, sh)
            gdi32.Rectangle(hdc, sw - gw, 0, sw, sh)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.DeleteObject(brush)

            # --- Layer 2: Main border (bright cyan) ---
            main_alpha = int(intensity * 255)
            # Cyan: low R, high G, high B
            main_r = int(main_alpha * 0.1)
            main_g = int(main_alpha * 0.8)
            main_b = main_alpha
            main_color = (main_b << 16) | (main_g << 8) | main_r
            brush = gdi32.CreateSolidBrush(main_color)
            old_brush = gdi32.SelectObject(hdc, brush)
            bw = 3
            gdi32.Rectangle(hdc, 10, 10, sw - 10, 10 + bw)
            gdi32.Rectangle(hdc, 10, sh - 10 - bw, sw - 10, sh - 10)
            gdi32.Rectangle(hdc, 10, 10, 10 + bw, sh - 10)
            gdi32.Rectangle(hdc, sw - 10 - bw, 10, sw - 10, sh - 10)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.DeleteObject(brush)

            # --- Layer 3: Inner bright line (white/cyan) ---
            inner_alpha = int(intensity * 200)
            inner_color = (inner_alpha << 16) | (min(255, inner_alpha + 30) << 8) | min(255, inner_alpha + 50)
            pen = gdi32.CreatePen(0, 1, inner_color)
            old_pen = gdi32.SelectObject(hdc, pen)
            hollow = gdi32.GetStockObject(5)
            old_brush2 = gdi32.SelectObject(hdc, hollow)
            gdi32.Rectangle(hdc, 14, 14, sw - 14, sh - 14)
            gdi32.SelectObject(hdc, old_brush2)
            gdi32.SelectObject(hdc, old_pen)
            gdi32.DeleteObject(pen)

            # --- Layer 4: Corner accents (L-shaped) ---
            corner_len = 60
            corner_w = 2
            corner_alpha = int(intensity * 255)
            cr = int(corner_alpha * 0.2)
            cg = int(corner_alpha * 1.0)
            cb = min(255, corner_alpha + 30)
            corner_color = (cb << 16) | (cg << 8) | cr
            pen = gdi32.CreatePen(0, corner_w, corner_color)
            old_pen = gdi32.SelectObject(hdc, pen)

            # Top-left corner
            gdi32.MoveToEx(hdc, 20, 20, None)
            gdi32.LineTo(hdc, 20 + corner_len, 20)
            gdi32.MoveToEx(hdc, 20, 20, None)
            gdi32.LineTo(hdc, 20, 20 + corner_len)

            # Top-right corner
            gdi32.MoveToEx(hdc, sw - 20, 20, None)
            gdi32.LineTo(hdc, sw - 20 - corner_len, 20)
            gdi32.MoveToEx(hdc, sw - 20, 20, None)
            gdi32.LineTo(hdc, sw - 20, 20 + corner_len)

            # Bottom-left corner
            gdi32.MoveToEx(hdc, 20, sh - 20, None)
            gdi32.LineTo(hdc, 20 + corner_len, sh - 20)
            gdi32.MoveToEx(hdc, 20, sh - 20, None)
            gdi32.LineTo(hdc, 20, sh - 20 - corner_len)

            # Bottom-right corner
            gdi32.MoveToEx(hdc, sw - 20, sh - 20, None)
            gdi32.LineTo(hdc, sw - 20 - corner_len, sh - 20)
            gdi32.MoveToEx(hdc, sw - 20, sh - 20, None)
            gdi32.LineTo(hdc, sw - 20, sh - 20 - corner_len)

            gdi32.SelectObject(hdc, old_pen)
            gdi32.DeleteObject(pen)

            # --- Layer 5: Scanning line (moving along border) ---
            scan_pos = int((self._time * 100) % (2 * (sw + sh)))
            scan_alpha = int(intensity * 180)
            scan_color = (min(255, scan_alpha + 80) << 16) | (min(255, scan_alpha + 120) << 8) | min(255, scan_alpha + 150)
            pen = gdi32.CreatePen(0, 2, scan_color)
            old_pen = gdi32.SelectObject(hdc, pen)

            # Map scan_pos to border position
            perimeter = 2 * (sw + sh)
            pos = scan_pos % perimeter
            if pos < sw:
                # Top edge, left to right
                sx, sy = pos, 12
                ex, ey = pos + 40, 12
            elif pos < sw + sh:
                # Right edge, top to bottom
                sx, sy = sw - 12, pos - sw
                ex, ey = sw - 12, pos - sw + 40
            elif pos < 2 * sw + sh:
                # Bottom edge, right to left
                p = pos - sw - sh
                sx, sy = sw - p, sh - 12
                ex, ey = sw - p - 40, sh - 12
            else:
                # Left edge, bottom to top
                p = pos - 2 * sw - sh
                sx, sy = 12, sh - p
                ex, ey = 12, sh - p - 40

            gdi32.MoveToEx(hdc, sx, sy, None)
            gdi32.LineTo(hdc, ex, ey)

            gdi32.SelectObject(hdc, old_pen)
            gdi32.DeleteObject(pen)

            user32.ReleaseDC(hwnd, hdc)

        except Exception:
            pass

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
