"""Authentication configuration"""

import os
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    """Authentication configuration"""
    # JWT Settings
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password settings
    BCRYPT_ROUNDS: int = 12
    
    # Rate limiting
    LOGIN_RATE_LIMIT: int = 5  # requests per minute
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    model_config = {"extra": "allow"}  # Allow extra fields from .env


auth_settings = AuthSettings()
