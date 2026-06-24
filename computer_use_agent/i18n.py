"""国际化基础设施 - 修复 C8

简单的 JSON 翻译表，支持中英文切换。
不引入 gettext（避免编译 .mo 文件）。

用法:
    from .i18n import t
    print(t("goodbye"))  # 根据当前语言返回 "Goodbye!" 或 "再见！"
"""

import os
import json
import threading
from pathlib import Path
from typing import Optional

# 翻译表（key -> {lang: text}）
_TRANSLATIONS = {
    # 通用
    "goodbye": {"zh-CN": "再见！", "en-US": "Goodbye!"},
    "yes": {"zh-CN": "是", "en-US": "yes"},
    "no": {"zh-CN": "否", "en-US": "no"},
    "on": {"zh-CN": "开", "en-US": "on"},
    "off": {"zh-CN": "关", "en-US": "off"},
    "error": {"zh-CN": "错误", "en-US": "error"},
    "loading": {"zh-CN": "加载中...", "en-US": "Loading..."},
    "thinking": {"zh-CN": "思考中...", "en-US": "Thinking..."},

    # Slash 命令
    "cmd_help": {"zh-CN": "显示帮助信息", "en-US": "Show help"},
    "cmd_quit": {"zh-CN": "退出程序", "en-US": "Quit"},
    "cmd_config": {"zh-CN": "显示当前配置", "en-US": "Show config"},
    "cmd_screen": {"zh-CN": "查看屏幕分辨率", "en-US": "Show screen size"},
    "cmd_history": {"zh-CN": "查看会话历史", "en-US": "Show history"},
    "cmd_compact": {"zh-CN": "手动压缩上下文", "en-US": "Compact context"},
    "cmd_reset": {"zh-CN": "重置会话历史", "en-US": "Reset session"},
    "cmd_model": {"zh-CN": "切换模型", "en-US": "Switch model"},
    "cmd_steps": {"zh-CN": "设置最大步数", "en-US": "Set max steps"},
    "cmd_delay": {"zh-CN": "设置操作延迟", "en-US": "Set action delay"},
    "cmd_usage": {"zh-CN": "查看 token 用量", "en-US": "Show token usage"},
    "cmd_retry": {"zh-CN": "重试上一个任务", "en-US": "Retry last task"},
    "cmd_undo": {"zh-CN": "撤销最后一条", "en-US": "Undo last"},
    "cmd_title": {"zh-CN": "显示当前任务", "en-US": "Show task title"},
    "cmd_sessions": {"zh-CN": "查看历史会话", "en-US": "Show sessions"},
    "cmd_resume": {"zh-CN": "恢复历史会话", "en-US": "Resume session"},
    "cmd_save": {"zh-CN": "导出会话", "en-US": "Save session"},
    "cmd_branch": {"zh-CN": "分叉当前会话", "en-US": "Branch session"},
    "cmd_yolo": {"zh-CN": "切换 YOLO 模式", "en-US": "Toggle YOLO mode"},
    "cmd_steer": {"zh-CN": "注入指令", "en-US": "Steer task"},
    "cmd_stop": {"zh-CN": "停止当前任务", "en-US": "Stop task"},
    "cmd_verbose": {"zh-CN": "切换详细输出", "en-US": "Toggle verbose"},
    "cmd_status": {"zh-CN": "查看当前状态", "en-US": "Show status"},
    "cmd_queue": {"zh-CN": "排队下一条指令", "en-US": "Queue next task"},
    "cmd_clear": {"zh-CN": "清屏", "en-US": "Clear screen"},

    # 状态
    "task_started": {"zh-CN": "🚀 任务开始", "en-US": "🚀 Task started"},
    "task_completed": {"zh-CN": "✅ 任务完成", "en-US": "✅ Task completed"},
    "task_interrupted": {"zh-CN": "⏹ 已中断", "en-US": "⏹ Interrupted"},
    "task_failed": {"zh-CN": "❌ 任务失败", "en-US": "❌ Task failed"},

    # 错误
    "unknown_command": {"zh-CN": "未知命令", "en-US": "Unknown command"},
    "invalid_number": {"zh-CN": "无效数字", "en-US": "Invalid number"},
    "no_task_to_retry": {"zh-CN": "没有可重试的任务", "en-US": "No task to retry"},
    "session_not_found": {"zh-CN": "会话不存在", "en-US": "Session not found"},
    "auth_required": {"zh-CN": "需要鉴权", "en-US": "Authentication required"},

    # 执行器动作描述 (修复 F8.1)
    "act_left_click": {"zh-CN": "左键点击 ({0}, {1})", "en-US": "Left click ({0}, {1})"},
    "act_left_click_element": {"zh-CN": "左键点击元素 #{0} ({1}, {2})", "en-US": "Left click element #{0} ({1}, {2})"},
    "act_double_click": {"zh-CN": "双击 ({0}, {1})", "en-US": "Double click ({0}, {1})"},
    "act_double_click_element": {"zh-CN": "双击元素 #{0} ({1}, {2})", "en-US": "Double click element #{0} ({1}, {2})"},
    "act_right_click": {"zh-CN": "右键点击 ({0}, {1})", "en-US": "Right click ({0}, {1})"},
    "act_right_click_element": {"zh-CN": "右键点击元素 #{0} ({1}, {2})", "en-US": "Right click element #{0} ({1}, {2})"},
    "act_type_text": {"zh-CN": "输入文本 ({0} 字符)", "en-US": "Type text ({0} chars)"},
    "act_press_key": {"zh-CN": "按键 [{0}]", "en-US": "Press [{0}]"},
    "act_hold_key": {"zh-CN": "长按 [{0}] {1}s", "en-US": "Hold [{0}] {1}s"},
    "act_hotkey": {"zh-CN": "组合键 {0}", "en-US": "Hotkey {0}"},
    "act_scroll": {"zh-CN": "滚动 {0} ×{1}", "en-US": "Scroll {0} ×{1}"},
    "act_move_mouse": {"zh-CN": "移动鼠标到 ({0}, {1})", "en-US": "Move mouse to ({0}, {1})"},
    "act_drag": {"zh-CN": "拖拽 ({0},{1}) → ({2},{3}) hold={4}s", "en-US": "Drag ({0},{1}) → ({2},{3}) hold={4}s"},
    "act_wait": {"zh-CN": "等待 {0}s", "en-US": "Wait {0}s"},
    "act_screenshot": {"zh-CN": "重新截图（无操作）", "en-US": "Re-capture (no action)"},
}

# 当前语言（线程局部以支持未来多线程）
_state = threading.local()


def set_language(lang: str):
    """设置当前语言。"""
    if lang not in ("zh-CN", "en-US"):
        lang = "zh-CN"  # 默认
    _state.lang = lang


def get_language() -> str:
    """获取当前语言。优先从 LANGUAGE env 读取。"""
    if hasattr(_state, "lang"):
        return _state.lang
    env_lang = os.getenv("LANGUAGE", "")
    if env_lang in ("zh-CN", "en-US"):
        return env_lang
    if env_lang.startswith("en"):
        return "en-US"
    return "zh-CN"  # 默认中文


def t(key: str, *args, default: Optional[str] = None, lang: Optional[str] = None) -> str:
    """翻译一个 key（支持位置参数占位符 {0}, {1}, ...）。

    Args:
        key: 翻译键
        *args: 占位符参数（用于 str.format）
        default: 未找到翻译时返回的默认文本（默认原样返回 key）
        lang: 强制使用某种语言（None 用当前语言）

    Examples:
        t("act_press_key", "ctrl+c")
        t("goodbye", lang="en-US")
    """
    if lang is None:
        lang = get_language()
    if key in _TRANSLATIONS:
        template = _TRANSLATIONS[key].get(lang) or _TRANSLATIONS[key].get("zh-CN") or default or key
    elif default is not None:
        template = default
    else:
        template = key

    if args:
        try:
            return template.format(*args)
        except (IndexError, KeyError, ValueError):
            return template
    return template


def all_commands() -> dict:
    """获取所有命令的本地化描述（用于 /help 与 argparse）。"""
    return {
        "/help": t("cmd_help"),
        "/quit": t("cmd_quit"),
        "/exit": t("cmd_quit"),
        "/config": t("cmd_config"),
        "/screen": t("cmd_screen"),
        "/history": t("cmd_history"),
        "/compact": t("cmd_compact"),
        "/reset": t("cmd_reset"),
        "/model": t("cmd_model"),
        "/steps": t("cmd_steps"),
        "/delay": t("cmd_delay"),
        "/usage": t("cmd_usage"),
        "/retry": t("cmd_retry"),
        "/undo": t("cmd_undo"),
        "/title": t("cmd_title"),
        "/sessions": t("cmd_sessions"),
        "/resume": t("cmd_resume"),
        "/save": t("cmd_save"),
        "/branch": t("cmd_branch"),
        "/yolo": t("cmd_yolo"),
        "/steer": t("cmd_steer"),
        "/stop": t("cmd_stop"),
        "/verbose": t("cmd_verbose"),
        "/status": t("cmd_status"),
        "/queue": t("cmd_queue"),
        "/clear": t("cmd_clear"),
    }


def load_custom_translations(file_path: str) -> int:
    """从 JSON 文件加载额外翻译。

    Returns: 新增的 key 数量。
    """
    path = Path(file_path)
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        added = 0
        for key, translations in data.items():
            if isinstance(translations, dict):
                if key not in _TRANSLATIONS:
                    _TRANSLATIONS[key] = {}
                    added += 1
                _TRANSLATIONS[key].update(translations)
        return added
    except Exception:
        return 0
