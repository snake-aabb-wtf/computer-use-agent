"""Task completion notification - bring window to front + play sound

When a task completes, the user should immediately notice.
"""

import os
import sys
import ctypes
import ctypes.wintypes
import winsound


def notify_completion():
    """Bring CLI window to foreground and play notification sound."""
    _bring_to_front()
    _play_sound()


def _bring_to_front():
    """Bring the 'Computer Use Agent' window to the foreground."""
    if sys.platform != "win32":
        return

    try:
        user32 = ctypes.windll.user32
        # FindWindowW(NULL, title) 通过标题名查找窗口
        hwnd = user32.FindWindowW(None, "Computer Use Agent")
        if hwnd:
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return

        # Fallback: FindWindow with other titles
        for title in ["Python", "python", "cmd", "PowerShell", "Terminal"]:
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                return
    except Exception:
        pass


def _play_sound():
    """Play the system notification sound."""
    try:
        if sys.platform == "win32":
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass
