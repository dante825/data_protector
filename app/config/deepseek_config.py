"""
DeepSeek API configuration for PII Detection enhancement
"""

import os

# Default model and generation settings
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TEMPERATURE = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.1"))
DEEPSEEK_MAX_OUTPUT_TOKENS = int(os.getenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "1200"))

# Connection settings
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_TIMEOUT = int(os.getenv("DEEPSEEK_TIMEOUT", "30"))
DEEPSEEK_MAX_RETRIES = int(os.getenv("DEEPSEEK_MAX_RETRIES", "3"))

# Env var names to try for the API key
API_KEY_ENV_VARS = ("DEEPSEEK_API_KEY",)


def get_api_key() -> str | None:
    """Return the DeepSeek API key from common env var names."""
    for name in API_KEY_ENV_VARS:
        val = os.getenv(name)
        if val and val.strip():
            return val.strip()
    return None


def is_configured() -> bool:
    """Check if DeepSeek API is properly configured."""
    return get_api_key() is not None
