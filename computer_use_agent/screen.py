"""screen - 截图模块

支持三种模式:
- vision: 纯截图 + 网格覆盖
- som: UIA 元素树 + 编号覆盖层
- uitars: 纯截图（坐标归一化）

修复 F1: 多显示器支持（mss）+ 自定义捕获区
"""

import base64, io
import platform
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageGrab
from . import config


# ── 多显示器支持（mss） ──

_mss_instance = None

def _get_mss():
    """懒加载 mss 实例。"""
    global _mss_instance
    if _mss_instance is None:
        try:
            import mss
            _mss_instance = mss.mss()
        except (ImportError, Exception) as e:
            _mss_instance = False  # 标记为不可用
    return _mss_instance if _mss_instance else None


def list_monitors() -> list[dict]:
    """列出所有可用显示器 (修复 F1)。

    Returns:
        list of dict: {index, left, top, width, height, is_primary}
    """
    mss_inst = _get_mss()
    if mss_inst is None:
        # 回退：返回主显示器（通过 pyautogui 或 ImageGrab）
        try:
            w, h = pyautogui_size()
            return [{"index": 0, "left": 0, "top": 0, "width": w, "height": h, "is_primary": True}]
        except Exception:
            return [{"index": 0, "left": 0, "top": 0, "width": 1920, "height": 1080, "is_primary": True}]
    monitors = []
    for i, m in enumerate(mss_inst.monitors):
        monitors.append({
            "index": i,
            "left": m["left"],
            "top": m["top"],
            "width": m["width"],
            "height": m["height"],
            "is_primary": (i == 1),  # mss 中 index 0 = 全部，1+ = 单个显示器
        })
    return monitors


def pyautogui_size():
    """获取主屏幕尺寸（兼容 pyautogui）。"""
    try:
        import pyautogui
        return pyautogui.size()
    except Exception:
        # ImageGrab 总是可用
        return ImageGrab.grab().size


def _parse_region(region_str: str) -> dict | None:
    """解析 CAPTURE_REGION 环境变量 (x,y,w,h) -> mss monitor dict。

    Args:
        region_str: 形如 "100,200,800,600" 的字符串

    Returns:
        mss 格式的 monitor dict 或 None
    """
    if not region_str:
        return None
    try:
        parts = [int(p.strip()) for p in region_str.split(",")]
        if len(parts) != 4:
            return None
        x, y, w, h = parts
        if w <= 0 or h <= 0:
            return None
        return {"left": x, "top": y, "width": w, "height": h}
    except (ValueError, AttributeError):
        return None


def _resolve_capture_target() -> dict | None:
    """根据配置决定截图目标 (monitor 或 region)。

    Returns:
        dict: mss 格式的 monitor dict；None 表示使用整个主屏幕
    """
    # 优先 region
    region = _parse_region(getattr(config, "CAPTURE_REGION", ""))
    if region:
        return region

    # 然后 monitor
    monitor_idx = getattr(config, "MONITOR_INDEX", 0)
    if monitor_idx <= 0:
        return None  # 主屏幕（默认行为）

    mss_inst = _get_mss()
    if mss_inst is None:
        return None

    monitors = mss_inst.monitors
    # mss 中 monitors[0] = 所有显示器的虚拟桌面
    # monitors[1], monitors[2]... = 各显示器
    target_idx = monitor_idx
    if 0 <= target_idx < len(monitors):
        return monitors[target_idx]
    return None


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

    grid_color = (0, 255, 255, 100)    # 亮青色半透明，在浅色/深色背景都可见
    text_bg = (0, 0, 0, 180)          # 黑色背景
    text_color = (0, 255, 255, 255)   # 亮青色文字

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

def _grab_image() -> Image.Image:
    """统一抓屏入口（修复 F1: 支持多显示器与自定义区域）。"""
    target = _resolve_capture_target()
    mss_inst = _get_mss()
    if mss_inst is not None and target is not None:
        # 使用 mss 抓取指定 monitor/region
        try:
            sct = mss_inst.grab(target)
            # mss 返回 BGRA；转为 PIL RGB
            return Image.frombytes("RGB", sct.size, sct.bgra, "raw", "BGRX")
        except Exception:
            pass
    # 默认：主屏幕（ImageGrab）
    return ImageGrab.grab()


def capture():
    """Vision 模式截图：纯截图 + 网格覆盖。"""
    screenshot = _grab_image()
    if config.CAPTURE_MODE == "vision":
        screenshot = _draw_grid(screenshot)
    return _image_to_base64(screenshot)


def capture_and_save(step=0):
    """截图并保存到本地（包含参考线）。"""
    screenshot = _grab_image()
    if config.CAPTURE_MODE == "vision":
        screenshot = _draw_grid(screenshot)
    save_dir = Path(config.SCREENSHOT_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)
    filepath = save_dir / f"step_{step:04d}.{config.SCREENSHOT_FORMAT}"
    screenshot.save(filepath)
    return _image_to_base64(screenshot), filepath


def capture_som():
    """SOM 模式截图：UIA 元素树 + 编号覆盖层。

    修复 B4: 现在额外返回渲染好的 PIL.Image 对象 (som_image)，
    避免 agent 在保存时重复 ImageGrab.grab()。
    返回值: (img_b64, elements, elements_text, som_image)
    """
    from .uia_tree import get_elements, render_som, image_to_base64, format_elements_text
    screenshot = _grab_image()  # 修复 F1: 使用多显示器感知的抓屏
    elements = get_elements(max_elements=100)
    som_image = render_som(screenshot, elements)
    return (
        image_to_base64(som_image),
        elements,
        format_elements_text(elements),
        som_image,
    )


def get_screen_size():
    """返回当前捕获目标的分辨率（修复 F1）。"""
    target = _resolve_capture_target()
    if target:
        return (target["width"], target["height"])
    return ImageGrab.grab().size


def get_screen_info() -> dict:
    """返回屏幕元信息（用于注入到 LLM context，修复 F1）。"""
    monitors = list_monitors()
    target = _resolve_capture_target()
    width, height = get_screen_size()
    return {
        "screen_size": [width, height],
        "active_monitor": target,
        "all_monitors": monitors,
        "platform": platform.system(),
    }
