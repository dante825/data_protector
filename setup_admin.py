#!/usr/bin/env python3
"""Script to initialize the first system administrator user"""

import os
import sys
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.auth_database import init_auth_database, get_auth_db_sync
from app.auth.models import User
from app.auth.password_hasher import hash_password


def setup_first_admin(username: str = "admin", 
                      email: str = "admin@Protector.local", 
                      password: str = None) -> User:
    """
    Initialize the first system administrator user.
    
    Args:
        username: Admin username (default: "admin")
        email: Admin email (default: "admin@Protector.local")
        password: Admin password (optional, will prompt if not provided)
    
    Returns:
        The created User object
    """
    print("🛡️ Project Protector - First Administrator Setup")
    print("=" * 50)
    
    if password is None:
        import getpass
        password = getpass.getpass("Enter admin password: ")
        confirm_password = getpass.getpass("Confirm admin password: ")
        
        if password != confirm_password:
            print("❌ Passwords do not match!")
            sys.exit(1)
        
        if len(password) < 8:
            print("❌ Password must be at least 8 characters!")
            sys.exit(1)
    
    print("\nInitializing authentication database...")
    init_auth_database()
    
    print("Creating first administrator user...")
    
    db = get_auth_db_sync()
    try:
        existing_admin = db.query(User).filter(User.is_admin == True).first()
        
        if existing_admin:
            print(f"⚠️  Admin user already exists: {existing_admin.username}")
            overwrite = input("Overwrite? (yes/no): ").strip().lower()
            
            if overwrite != "yes":
                print("Aborted.")
                return existing_admin
            
            existing_admin.username = username
            existing_admin.email = email
            existing_admin.hashed_password = hash_password(password)
            existing_admin.full_name = "System Administrator"
            existing_admin.is_active = True
            existing_admin.created_at = datetime.utcnow()
            
            db.commit()
            print(f"✅ Admin user updated: {username}")
            return existing_admin
        
        hashed_password = hash_password(password)
        
        admin_user = User(
            username=username,
            email=email,
            full_name="System Administrator",
            hashed_password=hashed_password,
            is_active=True,
            is_admin=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"✅ First administrator user created successfully!")
        print(f"\n👤 Admin Details:")
        print(f"   Username: {admin_user.username}")
        print(f"   Email: {admin_user.email}")
        print(f"   Is Admin: {admin_user.is_admin}")
        print(f"   Created: {admin_user.created_at}")
        print(f"\n🔐 Use these credentials to log in to the system")
        
        return admin_user
        
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to create admin user: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Initialize the first system administrator user for Project Protector"
    )
    parser.add_argument(
        "--username", "-u",
        type=str,
        default=None,
        help="Admin username (default: admin)"
    )
    parser.add_argument(
        "--email", "-e",
        type=str,
        default=None,
        help="Admin email (default: admin@Protector.local)"
    )
    parser.add_argument(
        "--password", "-p",
        type=str,
        default=None,
        help="Admin password (will prompt if not provided)"
    )
    
    args = parser.parse_args()
    
    setup_first_admin(
        username=args.username,
        email=args.email,
        password=args.password
    )
