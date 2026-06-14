"""screen"""
import base64, io
from pathlib import Path
from PIL import ImageGrab
from . import config

def capture():
    screenshot = ImageGrab.grab()
    buf = io.BytesIO()
    screenshot.save(buf, format=config.SCREENSHOT_FORMAT.upper())
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def capture_and_save(step=0):
    screenshot = ImageGrab.grab()
    save_dir = Path(config.SCREENSHOT_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)
    filepath = save_dir / f"step_{step:04d}.{config.SCREENSHOT_FORMAT}"
    screenshot.save(filepath)
    buf = io.BytesIO()
    screenshot.save(buf, format=config.SCREENSHOT_FORMAT.upper())
    return base64.b64encode(buf.getvalue()).decode("utf-8"), filepath

def capture_som():
    from .uia_tree import get_elements, render_som, image_to_base64, format_elements_text
    screenshot = ImageGrab.grab()
    elements = get_elements(max_elements=100)
    som_image = render_som(screenshot, elements)
    return image_to_base64(som_image), elements, format_elements_text(elements)

def get_screen_size():
    return ImageGrab.grab().size
