#!/usr/bin/env python3
"""Script to reset admin password"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.auth_database import init_auth_database, get_auth_db_sync
from app.auth.models import User
from app.auth.password_hasher import hash_password


def reset_admin_password(new_password: str) -> User:
    """Reset the admin user's password"""
    init_auth_database()
    
    db = get_auth_db_sync()
    try:
        admin_user = db.query(User).filter(User.is_admin == True).first()
        
        if not admin_user:
            raise ValueError("No admin user found")
        
        admin_user.hashed_password = hash_password(new_password)
        db.commit()
        db.refresh(admin_user)
        
        return admin_user
        
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import secrets
    import string
    
    # Generate secure password
    password = ''.join([
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation),
        ''.join(secrets.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(8))
    ])
    
    print("🛡️ Project Protector - Admin Password Reset")
    print("=" * 50)
    print()
    
    admin_user = reset_admin_password(password)
    
    print(f"✅ Admin password reset successfully!")
    print()
    print("👤 Admin Details:")
    print(f"   Username: {admin_user.username}")
    print(f"   Email: {admin_user.email}")
    print(f"   Is Active: {admin_user.is_active}")
    print(f"   Is Admin: {admin_user.is_admin}")
    print()
    print("🔐 New Password (record this!):")
    print(f"   {password}")
    print()
