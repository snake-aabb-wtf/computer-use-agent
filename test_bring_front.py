"""Debug: find all Python windows and bring one to front"""
import subprocess
import ctypes
import ctypes.wintypes
import os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

pid = os.getpid()
print(f"Python PID: {pid}")

# EnumWindows callback
found = []
WINENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

def callback(hwnd, lParam):
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            lpdw_pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
            if lpdw_pid.value == pid:
                found.append((hwnd, title))
    return True

user32.EnumWindows(WINENUMPROC(callback), 0)

print(f"Found {len(found)} windows for PID {pid}:")
for hwnd, title in found:
    print(f"  hwnd={hex(hwnd)} title='{title}'")

if found:
    # Bring the first window to front
    hwnd = found[0][0]
    SW_RESTORE = 9
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    print(f"\nBrought to front: {hex(hwnd)}")
else:
    print("\nNo windows found for current PID")
    print("Trying FindWindow approaches...")

    # Try common window titles
    for title in ["Computer Use Agent", "Python", "cmd", "PowerShell", "Terminal"]:
        h = user32.FindWindowW(None, title)
        if h:
            print(f"  Found: '{title}' -> {hex(h)}")
            user32.ShowWindow(h, 9)
            user32.SetForegroundWindow(h)
            print(f"  Brought to front: {hex(h)}")
            break
        else:
            print(f"  Not found: '{title}'")
