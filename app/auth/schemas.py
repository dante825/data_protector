"""Pydantic schemas for authentication"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List


class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Schema for user login"""
    username: str
    password: str


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Schema for JWT token payload"""
    sub: Optional[str] = None
    username: Optional[str] = None
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    exp: Optional[datetime] = None


class User(UserBase):
    """Schema for user response"""
    id: int
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserInDB(User):
    """Schema for user in database (includes hashed password)"""
    hashed_password: str


class TokenRefresh(BaseModel):
    """Schema for token refresh request"""
    refresh_token: str


class APIKeyCreate(BaseModel):
    """Schema for API key creation"""
    name: Optional[str] = Field(None, max_length=100)
    expires_at: Optional[datetime] = None
    scopes: Optional[List[str]] = Field(default_factory=list)


class APIKeyResponse(BaseModel):
    """Schema for API key response (includes raw key for initial display)"""
    id: int
    name: Optional[str]
    key: str
    user_id: int
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    scopes: List[str]
