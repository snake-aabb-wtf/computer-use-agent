"""screen - 截图模块

支持三种模式:
- vision: 纯截图 + 网格覆盖
- som: UIA 元素树 + 编号覆盖层
- uitars: 纯截图（坐标归一化）
"""

import base64, io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageGrab
from . import config


# ═══════════════════════════════════════════════════════════
# 网格覆盖（借鉴: 给模型视觉参考点）
# ═══════════════════════════════════════════════════════════

def _draw_grid(img: Image.Image, spacing: int = 200) -> Image.Image:
    """在截图上画网格线，给模型提供坐标参考。"""
    overlay = img.copy()
    draw = ImageDraw.Draw(overlay, "RGBA")
    w, h = img.size

    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except (OSError, IOError):
        font = ImageFont.load_default()

    grid_color = (255, 255, 255, 120)  # 白色半透明
    text_bg = (0, 0, 0, 160)           # 黑色背景
    text_color = (255, 255, 255, 255)  # 白色文字

    # 画竖线 + 顶部坐标标注
    for x in range(spacing, w, spacing):
        draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
        label = str(x)
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0] + 4
        lh = bbox[3] - bbox[1] + 4
        draw.rectangle([x+1, 1, x+1+lw, 1+lh], fill=text_bg)
        draw.text((x+3, 2), label, fill=text_color, font=font)

    # 画横线 + 左侧坐标标注
    for y in range(spacing, h, spacing):
        draw.line([(0, y), (w, y)], fill=grid_color, width=1)
        label = str(y)
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0] + 4
        lh = bbox[3] - bbox[1] + 4
        draw.rectangle([1, y+1, 1+lw, y+1+lh], fill=text_bg)
        draw.text((3, y+2), label, fill=text_color, font=font)

    return overlay


def _image_to_base64(img: Image.Image) -> str:
    """PIL Image -> base64 string."""
    buf = io.BytesIO()
    img.save(buf, format=config.SCREENSHOT_FORMAT.upper())
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ═══════════════════════════════════════════════════════════
# 截图函数
# ═══════════════════════════════════════════════════════════

def capture():
    """Vision 模式截图：纯截图 + 网格覆盖。"""
    screenshot = ImageGrab.grab()
    if config.CAPTURE_MODE == "vision":
        screenshot = _draw_grid(screenshot)
    return _image_to_base64(screenshot)


def capture_and_save(step=0):
    """截图并保存到本地。"""
    screenshot = ImageGrab.grab()
    save_dir = Path(config.SCREENSHOT_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)
    filepath = save_dir / f"step_{step:04d}.{config.SCREENSHOT_FORMAT}"
    screenshot.save(filepath)
    if config.CAPTURE_MODE == "vision":
        screenshot = _draw_grid(screenshot)
    return _image_to_base64(screenshot), filepath


def capture_som():
    """SOM 模式截图：UIA 元素树 + 编号覆盖层。"""
    from .uia_tree import get_elements, render_som, image_to_base64, format_elements_text
    screenshot = ImageGrab.grab()
    elements = get_elements(max_elements=100)
    som_image = render_som(screenshot, elements)
    return image_to_base64(som_image), elements, format_elements_text(elements)


def get_screen_size():
    """返回屏幕分辨率。"""
    return ImageGrab.grab().size
