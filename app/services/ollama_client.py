#!/usr/bin/env python3
"""
Ollama adapter for PII detection with Malaysian context support.
"""

import os
import json
import time
from typing import Any, Dict, List, Optional

try:
    import ollama
except ImportError:
    ollama = None

from app.config.ollama_config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
    OLLAMA_MAX_TOKENS,
    OLLAMA_TIMEOUT_FIRST,
    OLLAMA_TIMEOUT_SUBSEQUENT,
    OLLAMA_MAX_RETRIES,
    OLLAMA_RETRY_DELAY,
    OLLAMA_PRELOAD_MODEL,
    OLLAMA_ENABLED
)

# Client singleton
_ollama_client = None
_model_loaded = False
_last_call_time = None


def get_client() -> Optional[Any]:
    """Get or create Ollama client."""
    global _ollama_client, _model_loaded
    
    if not OLLAMA_ENABLED or ollama is None:
        return None
    
    if _ollama_client is None:
        try:
            os.environ['OLLAMA_HOST'] = OLLAMA_BASE_URL
            _ollama_client = ollama.Client(host=OLLAMA_BASE_URL)
            
            # Pre-load model if configured
            if OLLAMA_PRELOAD_MODEL:
                preload_model()
                
            _model_loaded = True
        except Exception as e:
            print(f"[WARN] Failed to initialize Ollama client: {e}")
            _model_loaded = False
            return None
    
    return _ollama_client


def preload_model():
    """Pre-load the model into memory to avoid cold start."""
    global _model_loaded
    
    if not _model_loaded:
        try:
            client = get_client()
            if client:
                print(f"[INFO] Pre-loading Ollama model: {OLLAMA_MODEL}")
                # Create a minimal request to load the model
                prompt = "x /no_think" if "qwen3" in OLLAMA_MODEL.lower() else "x"
                client.generate(model=OLLAMA_MODEL, prompt=prompt, options={"temperature": 0})
                _model_loaded = True
                print(f"[INFO] Ollama model pre-loaded successfully")
        except Exception as e:
            print(f"[WARN] Failed to pre-load Ollama model: {e}")
            _model_loaded = False


def generate_json(system_prompt: str, user_prompt: str, use_json_mode: bool = True) -> str:
    """
    Generate a JSON response using Ollama.
    
    Args:
        system_prompt: System prompt
        user_prompt: User prompt
        use_json_mode: Use JSON format mode for more reliable output
    
    Returns:
        Raw JSON string or empty string on failure
    """
    global _last_call_time
    
    client = get_client()
    if not client:
        return ""
    
    # Calculate timeout based on whether this is first call
    elapsed_since_last = 0
    if _last_call_time:
        elapsed_since_last = time.time() - _last_call_time
    
    if _last_call_time is None or elapsed_since_last > 300:  # 5 minutes
        timeout = OLLAMA_TIMEOUT_FIRST  # Cold start
    else:
        timeout = OLLAMA_TIMEOUT_SUBSEQUENT  # Hot model
    
    # Prepare messages
    # Append /no_think for qwen3 models to disable slow thinking mode
    user_content = user_prompt.strip()
    if "qwen3" in OLLAMA_MODEL.lower():
        user_content += " /no_think"
    
    messages = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_content}
    ]
    
    # Prepare options
    options = {
        "temperature": OLLAMA_TEMPERATURE,
        "num_predict": OLLAMA_MAX_TOKENS
    }
    
    # Try with retries
    last_error = None
    for attempt in range(OLLAMA_MAX_RETRIES):
        try:
            # Prepare chat parameters
            chat_params = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "options": options
            }
            if use_json_mode:
                chat_params["format"] = "json"
            
            response = client.chat(**chat_params)
            
            # Update last call time
            _last_call_time = time.time()
            
            return response.message.content.strip()
            
        except Exception as e:
            last_error = e
            if attempt < OLLAMA_MAX_RETRIES - 1:
                wait_time = OLLAMA_RETRY_DELAY * (2 ** attempt)
                print(f"[WARN] Ollama attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                print(f"[WARN] Ollama failed after {OLLAMA_MAX_RETRIES} attempts: {e}")
                return ""


def test_connection() -> tuple[bool, str]:
    """Test if Ollama API is reachable."""
    global _model_loaded
    
    try:
        client = get_client()
        if not client:
            return False, "Ollama client not initialized"
        
        # Test with minimal prompt
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": "Hi"}],
            options={"temperature": 0, "num_predict": 10}
        )
        
        _model_loaded = True
        return True, f"Ollama connection successful (model: {OLLAMA_MODEL})"
        
    except Exception as e:
        _model_loaded = False
        return False, f"Ollama connection failed: {str(e)}"


def unload_model():
    """Unload the model from memory."""
    global _model_loaded, _ollama_client
    
    _model_loaded = False
    _ollama_client = None
