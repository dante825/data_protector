"""API Key management router"""

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime
import secrets

from app.auth import schemas
from app.auth.jwt_handler import verify_token
from app.database.audit_database import get_audit_db
from app.auth.models import ApiKey, User

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_current_user_from_token(token: str, db: Session) -> User:
    """Get current user from JWT token"""
    payload = verify_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.post("/api-key", response_model=schemas.APIKeyResponse)
async def create_api_key(
    api_key_data: schemas.APIKeyCreate,
    request: Request,
    db: Session = Depends(get_audit_db)
):
    """Create a new API key for the current user"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = auth_header.split(" ")[1]
    user = get_current_user_from_token(token, db)
    
    # Generate API key
    api_key = f"pk_{secrets.token_urlsafe(32)}"
    key_hash = secrets.token_hex(32)  # Hash for storage
    
    db_api_key = ApiKey(
        user_id=user.id,
        key_hash=key_hash,
        name=api_key_data.name,
        scopes=api_key_data.scopes,
        created_at=datetime.utcnow(),
        expires_at=api_key_data.expires_at,
        is_active=True
    )
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    
    return {
        "id": db_api_key.id,
        "name": db_api_key.name,
        "key": api_key,
        "user_id": db_api_key.user_id,
        "is_active": db_api_key.is_active,
        "created_at": db_api_key.created_at,
        "expires_at": db_api_key.expires_at,
        "scopes": db_api_key.scopes
    }


@router.get("/api-keys", response_model=list[schemas.APIKeyResponse])
async def list_api_keys(
    request: Request,
    db: Session = Depends(get_audit_db)
):
    """List API keys for current user"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = auth_header.split(" ")[1]
    user = get_current_user_from_token(token, db)
    
    api_keys = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.is_active == True).all()
    
    return api_keys


@router.delete("/api-key/{key_id}")
async def delete_api_key(
    key_id: int,
    request: Request,
    db: Session = Depends(get_audit_db)
):
    """Delete an API key"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = auth_header.split(" ")[1]
    user = get_current_user_from_token(token, db)
    
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.is_active = False
    db.commit()
    
    return {"message": "API key revoked"}
