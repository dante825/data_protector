"""
A tiny adapter around openai for DeepSeek API integration.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI, APIError
    from httpx import Timeout as HTTPXTimeout
except Exception:
    OpenAI = None

from .deepseek_config import (
    DEEPSEEK_MODEL,
    DEEPSEEK_TEMPERATURE,
    DEEPSEEK_MAX_OUTPUT_TOKENS,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_TIMEOUT,
    DEEPSEEK_MAX_RETRIES,
    get_api_key,
)


class DeepSeekClient:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or get_api_key()
        if not key:
            raise RuntimeError("DeepSeek API key not found. Set DEEPSEEK_API_KEY.")
        if OpenAI is None:
            raise RuntimeError("openai package not installed. Add 'openai' to requirements.txt")
        
        self.client = OpenAI(
            api_key=key,
            base_url=DEEPSEEK_BASE_URL,
            timeout=HTTPXTimeout(float(DEEPSEEK_TIMEOUT))
        )
        self.model = DEEPSEEK_MODEL
        self.max_retries = DEEPSEEK_MAX_RETRIES

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate a response intended to be JSON-only. Returns the raw text.
        """
        content = [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ]
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=content,
                    temperature=DEEPSEEK_TEMPERATURE,
                    max_tokens=DEEPSEEK_MAX_OUTPUT_TOKENS,
                )
                return (resp.choices[0].message.content or "").strip()
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    raise last_error
        raise last_error

    def test_connection(self) -> tuple[bool, str]:
        """Test if DeepSeek API is reachable and configured correctly."""
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a test assistant."},
                    {"role": "user", "content": "Reply with just 'OK'"},
                ],
                temperature=0.0,
                max_tokens=10,
            )
            return True, "DeepSeek API connection successful"
        except Exception as e:
            return False, f"DeepSeek API connection failed: {str(e)}"
