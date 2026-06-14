"""Diagnostic test for visual effects - trace the entire flow"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        os.system("chcp 65001 >nul 2>&1")

print("=" * 60)
print("  Visual Effects Diagnostic")
print("=" * 60)

# 1. .env
print("\n[1] .env")
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
with open(env_path, encoding="utf-8") as f:
    content = f.read()
print(f"  VISUAL_EFFECTS={'on' if 'VISUAL_EFFECTS=on' in content else 'off'}")

# 2. Config
print("\n[2] Config")
from computer_use_agent import config
print(f"  VISUAL_EFFECTS = {config.VISUAL_EFFECTS}")

# 3. Module
print("\n[3] Module import")
from computer_use_agent.visual_effects import BreathingBorder, RippleEffect, init_effects, trigger_ripple, cleanup
print("  [OK] All functions imported")

# 4. BreathingBorder class
print("\n[4] BreathingBorder class")
ve = BreathingBorder()
print(f"  [OK] Created: running={ve._running}")

# 5. init_effects
print("\n[5] init_effects(True)")
from computer_use_agent import visual_effects
visual_effects.init_effects(True)
print(f"  _enabled = {visual_effects._enabled}")
print(f"  _border = {visual_effects._border}")
print(f"  _ripple = {visual_effects._ripple}")
if visual_effects._border:
    print(f"  _border._running = {visual_effects._border._running}")

# 6. trigger_ripple (no-op when not running)
print("\n[6] trigger_ripple")
trigger_ripple(100, 100)
print("  [OK] trigger_ripple did not crash")

# 7. cleanup
print("\n[7] cleanup")
cleanup()
print(f"  _enabled = {visual_effects._enabled}")
print(f"  _border = {visual_effects._border}")

# 8. Executor
print("\n[8] Executor")
from computer_use_agent.executor import _trigger_ripple
_trigger_ripple(100, 100)
print("  [OK] executor _trigger_ripple did not crash")

# 9. Tkinter
print("\n[9] Tkinter quick test")
import tkinter as tk
root = tk.Tk()
root.title("test")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.geometry("200x100+100+100")
root.config(bg="black")
root.attributes("-transparentcolor", "black")
canvas = tk.Canvas(root, width=200, height=100, bg="black", highlightthickness=0)
canvas.pack()
canvas.create_rectangle(10, 10, 190, 90, outline="#0066ff", width=3)
root.after(500, root.destroy)
root.mainloop()
print("  [OK] Tkinter overlay works")

print("\n" + "=" * 60)
print("  All checks passed")
print("=" * 60)
