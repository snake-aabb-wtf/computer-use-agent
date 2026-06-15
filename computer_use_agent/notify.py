"""Task completion notification - bring window to front + play sound

When a task completes, the user should immediately notice.
"""

import os
import sys
import ctypes
import ctypes.wintypes
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
            # Method 1: GetConsoleWindow
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                # ShowWindow + SetForegroundWindow 组合
                SW_RESTORE = 9
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                return

            # Method 2: FindWindow 查找控制台窗口
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW("ConsoleWindowClass", None)
            if not hwnd:
                hwnd = user32.FindWindowW("tty", None)
            if hwnd:
                SW_RESTORE = 9
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                return

            # Method 3: PowerShell
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Add-Type -Name Win -Namespace Native -MemberDefinition "
                 "'[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);"
                 "[DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);'; "
                 "$hwnd = [Console]::GetConsoleWindow(); "
                 "if ($hwnd) { [Native.Win]::ShowWindow($hwnd, 9); [Native.Win]::SetForegroundWindow($hwnd) } "
                 "else { $proc = Get-Process -Name python* -ErrorAction SilentlyContinue | Select-Object -First 1; "
                 "if ($proc) { [Native.Win]::ShowWindow($proc.MainWindowHandle, 9); [Native.Win]::SetForegroundWindow($proc.MainWindowHandle) } }"],
                capture_output=True, timeout=5,
            )
    except Exception:
        pass


def _play_sound():
    """Play the system notification sound."""
    try:
        if sys.platform == "win32":
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass
