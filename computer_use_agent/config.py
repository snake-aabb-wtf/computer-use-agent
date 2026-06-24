"""config - 配置管理

修复 S1: 用 pydantic-settings 替换原手写 int/float/str 转换，
获得类型校验、错误提示和环境变量绑定。

保留模块级常量（向后兼容）：LLM_API_KEY、LLM_BASE_URL 等仍然可以直接
`from . import config; config.LLM_API_KEY` 访问。
"""

import os
import warnings
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


# 修复 S1: 用 pydantic-settings 提供配置校验
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field

    class Settings(BaseSettings):
        """统一配置（带类型校验和环境变量绑定）。"""

        model_config = SettingsConfigDict(
            env_file=str(_env_path) if _env_path.exists() else None,
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )

        # LLM
        llm_api_key: str = Field(default="sk-placeholder", alias="LLM_API_KEY")
        llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
        llm_model: str = Field(default="gpt-4o", alias="LLM_MODEL")
        llm_max_tokens: int = Field(default=4096, ge=1, alias="LLM_MAX_TOKENS")
        llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0, alias="LLM_TEMPERATURE")

        # Agent
        max_steps: int = Field(default=200, ge=1, alias="MAX_STEPS")
        action_delay: float = Field(default=0.1, ge=0.0, alias="ACTION_DELAY")
        request_timeout: int = Field(default=60, ge=1, alias="REQUEST_TIMEOUT")
        stale_timeout: float = Field(default=300.0, ge=0.0, alias="STALE_TIMEOUT")

        # Capture
        capture_mode: Literal["som", "vision", "uitars"] = Field(
            default="vision", alias="CAPTURE_MODE"
        )
        screenshot_dir: str = Field(default="screenshots", alias="SCREENSHOT_DIR")
        screenshot_format: str = Field(default="png", alias="SCREENSHOT_FORMAT")
        screenshot_keep: int = Field(default=50, ge=0, alias="SCREENSHOT_KEEP")

        # 多显示器 (F1)
        monitor_index: int = Field(default=0, ge=0, alias="MONITOR_INDEX")
        capture_region: str = Field(default="", alias="CAPTURE_REGION")  # x,y,w,h

        # Logging
        log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
            default="INFO", alias="LOG_LEVEL"
        )
        log_dir: str = Field(default="logs", alias="LOG_DIR")
        log_format: Literal["text", "json"] = Field(default="text", alias="LOG_FORMAT")

        # Visual effects
        visual_effects: bool = Field(default=False, alias="VISUAL_EFFECTS")

        # pyautogui 安全
        pyautogui_failsafe: bool = Field(default=False, alias="PYAUTOGUI_FAILSAFE")

        # HTTP API
        api_host: str = Field(default="127.0.0.1", alias="API_HOST")
        api_port: int = Field(default=2024, ge=1, le=65535, alias="API_PORT")
        api_token: str = Field(default="", alias="API_TOKEN")
        api_max_queue: int = Field(default=100, ge=1, alias="API_MAX_QUEUE")

        # 资源管理 (S3)
        task_result_ttl: int = Field(default=3600, ge=0, alias="TASK_RESULT_TTL")
        task_result_max: int = Field(default=1000, ge=0, alias="TASK_RESULT_MAX")

        # Webhook (F5)
        webhook_url: str = Field(default="", alias="WEBHOOK_URL")
        webhook_events: str = Field(default="done,error,interrupted", alias="WEBHOOK_EVENTS")

    # 加载并验证配置（坏值会抛出 ValidationError，被 main 捕获后打印友好错误）
    try:
        _settings = Settings()
    except Exception as e:
        warnings.warn(f"[config] Invalid configuration: {e}. Falling back to defaults.")
        # 重新加载默认配置（防止启动崩溃）
        _settings = Settings(_env_file=None)

    # 向下兼容：暴露模块级大写常量
    LLM_API_KEY = _settings.llm_api_key
    LLM_BASE_URL = _settings.llm_base_url
    LLM_MODEL = _settings.llm_model
    LLM_MAX_TOKENS = _settings.llm_max_tokens
    LLM_TEMPERATURE = _settings.llm_temperature

    MAX_STEPS = _settings.max_steps
    ACTION_DELAY = _settings.action_delay
    REQUEST_TIMEOUT = _settings.request_timeout
    STALE_TIMEOUT = _settings.stale_timeout

    CAPTURE_MODE = _settings.capture_mode
    SCREENSHOT_DIR = _settings.screenshot_dir
    SCREENSHOT_FORMAT = _settings.screenshot_format
    SCREENSHOT_KEEP = _settings.screenshot_keep

    MONITOR_INDEX = _settings.monitor_index
    CAPTURE_REGION = _settings.capture_region

    LOG_LEVEL = _settings.log_level
    LOG_DIR = _settings.log_dir
    LOG_FORMAT = _settings.log_format

    VISUAL_EFFECTS = _settings.visual_effects
    PYAUTOGUI_FAILSAFE = _settings.pyautogui_failsafe

    API_HOST = _settings.api_host
    API_PORT = _settings.api_port
    API_TOKEN = _settings.api_token
    API_MAX_QUEUE = _settings.api_max_queue

    TASK_RESULT_TTL = _settings.task_result_ttl
    TASK_RESULT_MAX = _settings.task_result_max

    WEBHOOK_URL = _settings.webhook_url
    WEBHOOK_EVENTS = _settings.webhook_events

except ImportError:
    # pydantic-settings 不可用时退回原始实现
    warnings.warn("[config] pydantic-settings not available, using legacy config")

    def _int(key, default):
        return int(os.getenv(key, str(default)))

    def _float(key, default):
        return float(os.getenv(key, str(default)))

    def _str(key, default=""):
        return os.getenv(key, default)

    LLM_API_KEY = _str("LLM_API_KEY", "sk-placeholder")
    LLM_BASE_URL = _str("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = _str("LLM_MODEL", "gpt-4o")
    LLM_MAX_TOKENS = _int("LLM_MAX_TOKENS", 4096)
    LLM_TEMPERATURE = _float("LLM_TEMPERATURE", 0.0)

    MAX_STEPS = _int("MAX_STEPS", 200)
    ACTION_DELAY = _float("ACTION_DELAY", 0.1)
    REQUEST_TIMEOUT = _int("REQUEST_TIMEOUT", 60)
    STALE_TIMEOUT = _float("STALE_TIMEOUT", 300.0)

    CAPTURE_MODE = _str("CAPTURE_MODE", "vision")
    if CAPTURE_MODE not in ("som", "vision", "uitars"):
        CAPTURE_MODE = "vision"
    SCREENSHOT_DIR = _str("SCREENSHOT_DIR", "screenshots")
    SCREENSHOT_FORMAT = _str("SCREENSHOT_FORMAT", "png")
    SCREENSHOT_KEEP = _int("SCREENSHOT_KEEP", 50)

    MONITOR_INDEX = _int("MONITOR_INDEX", 0)
    CAPTURE_REGION = _str("CAPTURE_REGION", "")

    LOG_LEVEL = _str("LOG_LEVEL", "INFO")
    LOG_DIR = _str("LOG_DIR", "logs")
    LOG_FORMAT = _str("LOG_FORMAT", "text")

    VISUAL_EFFECTS = _str("VISUAL_EFFECTS", "off").lower() in ("1", "true", "yes", "on")
    PYAUTOGUI_FAILSAFE = _str("PYAUTOGUI_FAILSAFE", "off").lower() in ("1", "true", "yes", "on")

    API_HOST = _str("API_HOST", "127.0.0.1")
    API_PORT = _int("API_PORT", 2024)
    API_TOKEN = _str("API_TOKEN", "")
    API_MAX_QUEUE = _int("API_MAX_QUEUE", 100)

    TASK_RESULT_TTL = _int("TASK_RESULT_TTL", 3600)
    TASK_RESULT_MAX = _int("TASK_RESULT_MAX", 1000)

    WEBHOOK_URL = _str("WEBHOOK_URL", "")
    WEBHOOK_EVENTS = _str("WEBHOOK_EVENTS", "done,error,interrupted")


# 帮助函数：将 API_TOKEN 暴露为布尔（是否启用鉴权）
def auth_enabled() -> bool:
    """是否启用 HTTP API 鉴权。"""
    return bool(API_TOKEN)


# 公开 settings 对象供高级用户使用
try:
    settings = _settings  # type: ignore[name-defined]
except NameError:
    settings = None
