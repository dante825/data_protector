"""Authentication dependencies for FastAPI"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.jwt_handler import verify_token
from app.database.audit_database import get_audit_db
from app.auth.models import User, UserSession


async def get_current_user(request: Request, db: Session = Depends(get_audit_db)) -> User:
    """Get current authenticated user from JWT token"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = auth_header.split(" ")[1]
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")
    
    request.state.user = user
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    return current_user


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current admin user"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def get_user_by_token(token: str, db: Session = Depends(get_audit_db)) -> User:
    """Get user by JWT token"""
    payload = verify_token(token)
    
    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user
