"""Visual effects - breathing border + mouse ripple

Experimental feature: tech-feel blue breathing border around screen
and ripple/wave effect on mouse clicks.

Controlled by VISUAL_EFFECTS in .env (default: off).
"""

import sys
import time
import threading
import math

# Windows-only (uses tkinter for overlay)
if sys.platform == "win32":
    import tkinter as tk
    from tkinter import Canvas


class BreathingBorder:
    """Full-screen overlay with animated blue breathing border.

    Uses tkinter transparent fullscreen window.
    """

    def __init__(self):
        self._running = False
        self._thread = None
        self._root = None
        self._canvas = None
        self._opacity = 0.0
        self._direction = 1  # 1 = fading in, -1 = fading out

    def start(self):
        """Start the breathing border animation."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the breathing border animation."""
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
        self._root = None
        self._canvas = None

    def _run(self):
        """Run the tkinter overlay in a separate thread."""
        try:
            self._root = tk.Tk()
            self._root.title("")
            self._root.overrideredirect(True)  # No title bar
            self._root.attributes("-topmost", True)
            self._root.attributes("-alpha", 0.0)

            # Full screen
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            self._root.geometry(f"{sw}x{sh}+0+0")

            # Transparent background
            self._root.config(bg="black")
            self._root.attributes("-transparentcolor", "black")

            # Canvas for border drawing
            self._canvas = Canvas(
                self._root, width=sw, height=sh,
                bg="black", highlightthickness=0
            )
            self._canvas.pack()

            # Start animation loop
            self._animate()

            self._root.mainloop()
        except Exception:
            self._running = False

    def _animate(self):
        """Animate the breathing border."""
        if not self._running or not self._canvas:
            return

        try:
            sw = self._canvas.winfo_width()
            sh = self._canvas.winfo_height()

            # Breathing: oscillate opacity 0.0 ~ 0.6
            self._opacity += self._direction * 0.02
            if self._opacity >= 0.6:
                self._opacity = 0.6
                self._direction = -1
            elif self._opacity <= 0.0:
                self._opacity = 0.0
                self._direction = 1

            # Convert opacity to alpha (0-255)
            alpha = int(self._opacity * 255)
            # Blue color with breathing alpha
            color_hex = f"#{alpha:02x}{int(alpha*0.6):02x}{min(255, alpha+80):02x}"

            self._canvas.delete("border")

            # Draw border rectangles (4 sides)
            border_width = 4
            for i in range(border_width):
                offset = i
                # Top
                self._canvas.create_line(
                    offset, offset, sw - offset, offset,
                    fill=color_hex, width=1, tags="border"
                )
                # Bottom
                self._canvas.create_line(
                    offset, sh - offset, sw - offset, sh - offset,
                    fill=color_hex, width=1, tags="border"
                )
                # Left
                self._canvas.create_line(
                    offset, offset, offset, sh - offset,
                    fill=color_hex, width=1, tags="border"
                )
                # Right
                self._canvas.create_line(
                    sw - offset, offset, sw - offset, sh - offset,
                    fill=color_hex, width=1, tags="border"
                )

            self._canvas.tag_raise("border")
            self._root.after(50, self._animate)  # 20 FPS
        except Exception:
            pass


class RippleEffect:
    """Mouse click ripple/wave effect.

    Shows expanding circles at click position.
    """

    def __init__(self):
        self._root = None
        self._canvas = None
        self._running = False

    def start(self):
        """Initialize the ripple overlay."""
        if self._running:
            return
        try:
            self._root = tk.Tk()
            self._root.title("")
            self._root.overrideredirect(True)
            self._root.attributes("-topmost", True)
            self._root.attributes("-alpha", 0.0)

            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            self._root.geometry(f"{sw}x{sh}+0+0")

            self._root.config(bg="black")
            self._root.attributes("-transparentcolor", "black")

            self._canvas = Canvas(
                self._root, width=sw, height=sh,
                bg="black", highlightthickness=0
            )
            self._canvas.pack()

            self._running = True
            self._root.mainloop()
        except Exception:
            self._running = False

    def stop(self):
        """Stop the ripple overlay."""
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
        self._root = None
        self._canvas = None

    def trigger(self, x: int, y: int):
        """Trigger a ripple effect at (x, y)."""
        if not self._running or not self._canvas:
            return
        try:
            self._canvas.after(0, lambda: self._animate_ripple(x, y))
        except Exception:
            pass

    def _animate_ripple(self, x: int, y: int):
        """Animate expanding circles at click position."""
        if not self._canvas:
            return

        max_radius = 40
        num_circles = 5
        duration = 500  # ms
        step_time = duration // (num_circles * 2)

        for i in range(num_circles * 2):
            if not self._running:
                break
            radius = max_radius * (i / (num_circles * 2))
            alpha = max(0, 1.0 - (i / (num_circles * 2)))
            color_val = int(alpha * 100)
            color = f"#{color_val:02x}{color_val+50:02x}{min(255, color_val+120):02x}"

            tag = f"ripple_{x}_{y}_{i}"
            self._canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                outline=color, width=2, tags=tag
            )

            # Schedule removal
            self._canvas.after(
                step_time * 2,
                lambda t=tag: self._canvas.delete(t) if self._canvas else None
            )


# Global instances
_border = None
_ripple = None
_enabled = False


def init_effects(enabled: bool = False):
    """Initialize visual effects if enabled."""
    global _border, _ripple, _enabled
    _enabled = enabled
    if not enabled:
        return

    _border = BreathingBorder()
    _ripple = RippleEffect()

    # Start ripple overlay in background thread
    ripple_thread = threading.Thread(target=_ripple.start, daemon=True)
    ripple_thread.start()
    time.sleep(0.1)  # Let tkinter initialize


def start_border():
    """Start the breathing border animation."""
    if _enabled and _border:
        _border.start()


def stop_border():
    """Stop the breathing border animation."""
    if _border:
        _border.stop()


def trigger_ripple(x: int, y: int):
    """Trigger a ripple effect at the given position."""
    if _enabled and _ripple:
        _ripple.trigger(x, y)


def cleanup():
    """Clean up all visual effects."""
    global _border, _ripple, _enabled
    _enabled = False
    if _border:
        _border.stop()
    if _ripple:
        _ripple.stop()
    _border = None
    _ripple = None
