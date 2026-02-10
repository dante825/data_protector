"""Authentication middleware for JWT token verification"""

from fastapi import Request, HTTPException, Depends
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Callable

from app.auth.jwt_handler import verify_token
from app.database.audit_database import get_audit_db
from app.auth.models import User, UserSession


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to verify JWT tokens on protected routes"""
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/auth/login",
            "/auth/register",
            "/auth/refresh-token",
            "/api/docs",
            "/api/openapi.json",
            "/api/redoc",
            "/",
            "/health",
            "/favicon.ico",
            "/static/",
        ]
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip auth for excluded paths
        path = request.url.path
        if any(path.startswith(exclude) for exclude in self.exclude_paths):
            return await call_next(request)
        
        # Skip if not an API route
        if not path.startswith("/api/"):
            return await call_next(request)
        
        # Get bearer token
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing authorization header")
        
        token = auth_header.split(" ")[1]
        
        # Verify token
        payload = verify_token(token)
        
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Get user from database
        db = get_audit_db()
        try:
            user = db.query(User).filter(User.id == payload.get("user_id")).first()
            
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            
            if not user.is_active:
                raise HTTPException(status_code=400, detail="User is inactive")
            
            # Add user to request state
            request.state.user = user
            request.state.token_payload = payload
            
            # Update session activity
            session_id = payload.get("session_id")
            if session_id:
                user_session = db.query(UserSession).filter(
                    UserSession.session_id == session_id
                ).first()
                if user_session:
                    user_session.last_activity = datetime.utcnow()
                    db.commit()
            
        finally:
            db.close()
        
        return await call_next(request)


# Helper dependency to get current user
def get_current_user(request: Request) -> User:
    """Get current user from request state"""
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return request.state.user