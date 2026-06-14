"""Task completion notification - bring window to front + play sound

Borrowed from Hermes activity heartbeat pattern.
When a task completes, the user should immediately notice.
"""

import os
import sys
import ctypes
import winsound
import subprocess


def notify_completion():
    """Bring CLI window to foreground and play notification sound."""
    _bring_to_front()
    _play_sound()


def _bring_to_front():
    """Bring the current console window to the foreground."""
    try:
        if sys.platform == "win32":
            # Windows: use SetForegroundWindow via ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        # Fallback: try using PowerShell
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "Add-Type -Name Win -Namespace Native -MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);'; "
                 "[Native.Win]::SetForegroundWindow([Console]::GetConsoleWindow())"],
                capture_output=True, timeout=3,
            )
        except Exception:
            pass


def _play_sound():
    """Play the system notification sound."""
    try:
        if sys.platform == "win32":
            # Windows: play system notification sound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass
