"""Authentication database initialization"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth.models import Base as AuthBase

# SQLite database URL for user/auth data
AUTH_DATABASE_URL = "sqlite:///./auth.db"

# Create engine
engine = create_engine(AUTH_DATABASE_URL, connect_args={"check_same_thread": False})

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_auth_database():
    """Initialize the user authentication database"""
    AuthBase.metadata.create_all(bind=engine)


def get_auth_db():
    """Get database session for auth operations"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_auth_db_sync():
    """Get database session for auth operations (sync)"""
    return SessionLocal()
