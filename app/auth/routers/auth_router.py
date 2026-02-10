"""Authentication router with login, register, logout"""
from datetime import datetime
import secrets

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.auth import schemas
from app.auth.jwt_handler import create_access_token, create_refresh_token, create_session_id
from app.auth.password_hasher import hash_password, verify_password
from app.database.audit_database import get_audit_db
from app.auth.models import User, UserSession

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_user_by_username(db: Session, username: str) -> User:
    """Get user by username"""
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> User:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate) -> User:
    """Create a new user"""
    hashed_password = hash_password(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/register", response_model=schemas.User)
async def register_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_audit_db)
):
    """Register a new user"""
    # Check if user already exists
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    db_user = create_user(db, user)
    
    return db_user


@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_audit_db),
    request: Request = None
):
    """Login and get access tokens"""
    user = get_user_by_username(db, form_data.username)
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create access and refresh tokens
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "session_id": create_session_id()},
        expires_in=60 * 24  # 24 hours
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.id}
    )
    
    # Create user session
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "") if request else ""
    
    user_session = UserSession(
        user_id=user.id,
        session_id=secrets.token_hex(16),
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.utcnow(),
        last_activity=datetime.utcnow(),
        is_active=True
    )
    db.add(user_session)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh-token", response_model=schemas.Token)
async def refresh_access_token(
    refresh_data: schemas.TokenRefresh,
    db: Session = Depends(get_audit_db)
):
    """Refresh access token using refresh token"""
    from app.auth.jwt_handler import verify_token
    
    payload = verify_token(refresh_data.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # Get user
    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create new tokens
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "session_id": create_session_id()},
        expires_in=60 * 24  # 24 hours
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.id}
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/logout")
async def logout_user(
    request: Request,
    db: Session = Depends(get_audit_db)
):
    """Logout current user"""
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = verify_token(token)
        
        if payload:
            session_id = payload.get("session_id")
            if session_id:
                user_session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
                if user_session:
                    user_session.is_active = False
                    user_session.logout_time = datetime.utcnow()
                    db.commit()
    
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=schemas.User)
async def read_users_me(
    request: Request,
    db: Session = Depends(get_audit_db)
):
    """Get current user info"""
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = verify_token(token)
        
        if payload:
            user_id = payload.get("user_id")
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return user
    
    raise HTTPException(status_code=401, detail="Not authenticated")
