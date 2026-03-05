#!/usr/bin/env python3
"""
Ollama API configuration for PII Detection enhancement
"""

import os

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")

# Generation settings
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
OLLAMA_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "2048"))

# Aggressive detection mode (detects more items, may have more false positives)
OLLAMA_AGGRESSIVE_MODE = os.getenv("OLLAMA_AGGRESSIVE_MODE", "true").lower() == "true"
LLM_MIN_TEXT_LENGTH = int(os.getenv("LLM_MIN_TEXT_LENGTH", "100"))

# Timeout settings (in seconds)
OLLAMA_TIMEOUT_FIRST = int(os.getenv("OLLAMA_TIMEOUT_FIRST", "120"))  # Cold start timeout
OLLAMA_TIMEOUT_SUBSEQUENT = int(os.getenv("OLLAMA_TIMEOUT_SUBSEQUENT", "60"))  # Hot model timeout

# Request settings
OLLAMA_MAX_RETRIES = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
OLLAMA_RETRY_DELAY = int(os.getenv("OLLAMA_RETRY_DELAY", "2"))  # seconds

# Pre-load settings
OLLAMA_PRELOAD_MODEL = os.getenv("OLLAMA_PRELOAD_MODEL", "true").lower() == "true"

# Enable/disable LLM detection
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").lower() == "true"


def is_configured() -> bool:
    """Check if Ollama is properly configured."""
    return OLLAMA_ENABLED
