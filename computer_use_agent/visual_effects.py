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
        """Draw sci-fi border: pure blue outer -> transparent inner (gradient)."""
        try:
            self._time += 0.05

            # Breathing: smooth sine wave
            breath = (math.sin(self._time * 2.0) + 1.0) / 2.0  # 0.0 ~ 1.0

            # Flash pulse: sharp spike every 2 seconds
            flash = max(0, math.sin(self._time * 3.14) ** 20)

            # Combined intensity
            intensity = breath * 0.4 + flash * 0.6

            hdc = user32.GetDC(hwnd)

            # 5 layers: pure blue (opaque) -> transparent (inner)
            # Layer 1: Outermost, pure blue, full intensity
            # Layer 2: Slightly inward, less blue
            # Layer 3: Middle, dimmer
            # Layer 4: Inner, faint
            # Layer 5: Innermost, nearly invisible

            layers = [
                {"offset": 0,  "width": 6,  "alpha": 1.0},    # pure blue
                {"offset": 8,  "width": 4,  "alpha": 0.7},    # bright blue
                {"offset": 14, "width": 3,  "alpha": 0.45},   # medium blue
                {"offset": 19, "width": 2,  "alpha": 0.25},   # dim blue
                {"offset": 23, "width": 1,  "alpha": 0.1},    # faint blue
            ]

            for layer in layers:
                off = layer["offset"]
                w = layer["width"]
                a = layer["alpha"] * intensity

                # Pure blue color with alpha
                r = int(a * 10)           # very low red
                g = int(a * 80)           # some green for glow
                b = int(a * 255)          # full blue
                color = (b << 16) | (g << 8) | r

                brush = gdi32.CreateSolidBrush(color)
                old_brush = gdi32.SelectObject(hdc, brush)

                # Top
                gdi32.Rectangle(hdc, off, off, sw - off, off + w)
                # Bottom
                gdi32.Rectangle(hdc, off, sh - off - w, sw - off, sh - off)
                # Left
                gdi32.Rectangle(hdc, off, off, off + w, sh - off)
                # Right
                gdi32.Rectangle(hdc, sw - off - w, off, sw - off, sh - off)

                gdi32.SelectObject(hdc, old_brush)
                gdi32.DeleteObject(brush)

            # Corner accents (bright blue, at outermost position)
            corner_len = 50
            corner_alpha = intensity
            cr = int(corner_alpha * 10)
            cg = int(corner_alpha * 120)
            cb = int(corner_alpha * 255)
            corner_color = (cb << 16) | (cg << 8) | cr
            pen = gdi32.CreatePen(0, 2, corner_color)
            old_pen = gdi32.SelectObject(hdc, pen)

            # Top-left
            gdi32.MoveToEx(hdc, 5, 5, None)
            gdi32.LineTo(hdc, 5 + corner_len, 5)
            gdi32.MoveToEx(hdc, 5, 5, None)
            gdi32.LineTo(hdc, 5, 5 + corner_len)
            # Top-right
            gdi32.MoveToEx(hdc, sw - 5, 5, None)
            gdi32.LineTo(hdc, sw - 5 - corner_len, 5)
            gdi32.MoveToEx(hdc, sw - 5, 5, None)
            gdi32.LineTo(hdc, sw - 5, 5 + corner_len)
            # Bottom-left
            gdi32.MoveToEx(hdc, 5, sh - 5, None)
            gdi32.LineTo(hdc, 5 + corner_len, sh - 5)
            gdi32.MoveToEx(hdc, 5, sh - 5, None)
            gdi32.LineTo(hdc, 5, sh - 5 - corner_len)
            # Bottom-right
            gdi32.MoveToEx(hdc, sw - 5, sh - 5, None)
            gdi32.LineTo(hdc, sw - 5 - corner_len, sh - 5)
            gdi32.MoveToEx(hdc, sw - 5, sh - 5, None)
            gdi32.LineTo(hdc, sw - 5, sh - 5 - corner_len)

            gdi32.SelectObject(hdc, old_pen)
            gdi32.DeleteObject(pen)

            # Scanning light along outermost border
            scan_pos = int((self._time * 100) % (2 * (sw + sh)))
            scan_alpha = intensity
            sr = int(scan_alpha * 50)
            sg = int(scan_alpha * 150)
            sb = int(scan_alpha * 255)
            scan_color = (sb << 16) | (sg << 8) | sr
            pen = gdi32.CreatePen(0, 3, scan_color)
            old_pen = gdi32.SelectObject(hdc, pen)

            perimeter = 2 * (sw + sh)
            pos = scan_pos % perimeter
            if pos < sw:
                sx, sy = pos, 3
                ex, ey = min(pos + 50, sw), 3
            elif pos < sw + sh:
                sx, sy = sw - 3, pos - sw
                ex, ey = sw - 3, min(pos - sw + 50, sh)
            elif pos < 2 * sw + sh:
                p = pos - sw - sh
                sx, sy = sw - p, sh - 3
                ex, ey = max(sw - p - 50, 0), sh - 3
            else:
                p = pos - 2 * sw - sh
                sx, sy = 3, sh - p
                ex, ey = 3, max(sh - p - 50, 0)

            gdi32.MoveToEx(hdc, sx, sy, None)
            gdi32.LineTo(hdc, ex, ey)

            gdi32.SelectObject(hdc, old_pen)
            gdi32.DeleteObject(pen)

            user32.ReleaseDC(hwnd, hdc)

        except Exception:
            pass

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
