"""config"""
import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

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

CAPTURE_MODE = _str("CAPTURE_MODE", "vision")

SCREENSHOT_DIR = _str("SCREENSHOT_DIR", "screenshots")
SCREENSHOT_FORMAT = _str("SCREENSHOT_FORMAT", "png")

LOG_LEVEL = _str("LOG_LEVEL", "INFO")
LOG_DIR = _str("LOG_DIR", "logs")
