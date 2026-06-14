"""Windows UIA element tree + SOM overlay rendering

Borrowed from Hermes cua_backend.py SOM (Set-of-Mark) pattern:
- Get all interactable elements via Windows UIA
- Draw red border + number label on each element
- Model selects elements by number instead of guessing coordinates
"""

import io
import logging
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("agent.uia")


@dataclass
class UIElement:
    index: int
    role: str
    label: str
    bounds: tuple = (0, 0, 0, 0)
    enabled: bool = True

    def center(self):
        x, y, w, h = self.bounds
        return x + w // 2, y + h // 2

    def description(self):
        parts = [f"[{self.index}] {self.role}"]
        if self.label:
            parts.append(f'"{self.label}"')
        parts.append(f"({self.bounds[0]},{self.bounds[1]})")
        return " ".join(parts)


def get_elements(max_elements=100):
    try:
        import uiautomation as auto
    except ImportError:
        logger.warning("uiautomation not installed")
        return []
    try:
        root = auto.GetRootControl()
        elements = []
        _walk_tree(root, elements, max_elements, 0, 15)
        elements.sort(key=lambda e: (e.bounds[1], e.bounds[0]))
        for i, elem in enumerate(elements):
            elem.index = i + 1
        logger.info(f"Found {len(elements)} elements")
        return elements
    except Exception as e:
        logger.error(f"UIA failed: {e}")
        return []


def _walk_tree(node, elements, max_elements, depth, max_depth):
    if len(elements) >= max_elements or depth > max_depth:
        return
    try:
        children = node.GetChildren()
    except Exception:
        return
    for child in children:
        if len(elements) >= max_elements:
            break
        try:
            role = child.GetClassName()
            name = child.Name or ""
            rect = child.BoundingRectangle
            if rect is None or rect.left == rect.right or rect.top == rect.bottom:
                continue
            bounds = (int(rect.left), int(rect.top),
                      int(rect.right - rect.left), int(rect.bottom - rect.top))
            if _is_interactable(child, role):
                elements.append(UIElement(
                    index=len(elements) + 1,
                    role=_simplify_role(role),
                    label=name[:50],
                    bounds=bounds,
                    enabled=child.IsEnabled,
                ))
            _walk_tree(child, elements, max_elements, depth + 1, max_depth)
        except Exception:
            continue


_INTERACTABLE = {"Button", "Hyperlink", "MenuItem", "Edit", "ComboBox",
                 "CheckBox", "RadioButton", "Slider", "TabItem", "ListItem",
                 "DataItem", "ToolBar", "MenuBar", "Window", "Pane"}

_ROLE_MAP = {
    "Button": "Button", "Hyperlink": "Link", "MenuItem": "MenuItem",
    "Edit": "TextField", "ComboBox": "Dropdown", "CheckBox": "Checkbox",
    "RadioButton": "Radio", "Slider": "Slider", "TabItem": "Tab",
    "ListItem": "ListItem", "DataItem": "DataItem",
    "ToolBar": "Toolbar", "MenuBar": "MenuBar", "Window": "Window",
    "Pane": "Panel", "Text": "Text", "Image": "Image",
}


def _is_interactable(node, class_name):
    try:
        if not node.IsEnabled:
            return False
        rect = node.BoundingRectangle
        if rect is None or rect.left < -100 or rect.top < -100:
            return False
        for kw in _INTERACTABLE:
            if kw.lower() in class_name.lower():
                return True
        ctrl_type = str(node.ControlTypeName)
        for kw in ["Button", "Hyperlink", "MenuItem", "Edit",
                    "ComboBox", "CheckBox", "RadioButton", "Slider",
                    "TabItem", "ListItem", "DataItem"]:
            if kw in ctrl_type:
                return True
        return False
    except Exception:
        return False


def _simplify_role(class_name):
    for key, value in _ROLE_MAP.items():
        if key.lower() in class_name.lower():
            return value
    return class_name[:20] if class_name else "Unknown"


def render_som(screenshot, elements, max_elements=100, font_size=14):
    overlay = screenshot.copy()
    draw = ImageDraw.Draw(overlay, "RGBA")
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()
    for elem in elements[:max_elements]:
        x, y, w, h = elem.bounds
        if x < 0 or y < 0 or x > screenshot.width or y > screenshot.height:
            continue
        draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 0, 200), width=2)
        label = str(elem.index)
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0] + 8
        lh = bbox[3] - bbox[1] + 4
        ly = max(0, y - lh - 2)
        draw.rectangle([x, ly, x + lw, ly + lh], fill=(255, 0, 0, 220))
        draw.text((x + 4, ly + 2), label, fill=(255, 255, 255, 255), font=font)
    return overlay


def image_to_base64(img, fmt="PNG"):
    import base64
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def format_elements_text(elements, max_elements=100):
    return "\n".join(elem.description() for elem in elements[:max_elements])
