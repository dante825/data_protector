from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from app.auth.models import User
from fastapi.staticfiles import StaticFiles
from app.middleware.audit_middleware import AuditMiddleware
from app.database.audit_database import init_audit_database
from app.database.auth_database import init_auth_database
from app.dependencies.auth_deps import get_current_user
from app.auth.jwt_handler import verify_token
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Project Protector API", version="0.1")

# Initialize databases (optional, non-blocking)
audit_enabled = False
auth_enabled = False

try:
    import sqlalchemy
    from app.database.audit_database import init_audit_database
    init_audit_database()
    audit_enabled = True
    logger.info("✅ Audit database initialized successfully")
except ImportError:
    logger.warning("⚠️ SQLAlchemy not available - audit system disabled")
except Exception as e:
    logger.warning(f"⚠️ Audit system initialization failed: {e} - continuing without audit")

try:
    from app.database.auth_database import init_auth_database
    init_auth_database()
    auth_enabled = True
    logger.info("✅ Auth database initialized successfully")
except Exception as e:
    logger.warning(f"⚠️ Auth system initialization failed: {e} - continuing without auth")

# Add audit middleware only if audit system is working
if audit_enabled:
    try:
        app.add_middleware(AuditMiddleware)
        logger.info("✅ Audit middleware enabled")
    except Exception as e:
        logger.warning(f"⚠️ Failed to add audit middleware: {e}")
        audit_enabled = False

# Add auth middleware to protect all /api routes
try:
    from app.middleware.auth_middleware import AuthMiddleware
    app.add_middleware(AuthMiddleware)
    logger.info("✅ Auth middleware enabled")
except Exception as e:
    logger.warning(f"⚠️ Failed to add auth middleware: {e}")

# Import routers with error handling
try:
    from app.routers import upload
    app.include_router(upload.router, prefix="/api")
    print("✅ Upload router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load upload router: {e}")

try:
    from app.routers import download_router
    app.include_router(download_router.router, prefix="/api")
    print("✅ Download router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load download router: {e}")

try: 
    from app.routers import process_router
    app.include_router(process_router.router, prefix="/api")
    print("✅ Process router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load process router: {e}")

try:
    from app.routers import decrypt_router
    app.include_router(decrypt_router.router, prefix="/api")
    print("✅ Decrypt router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load decrypt router: {e}")

# Load auth routers
if auth_enabled:
    try:
        from app.auth.routers.auth_router import router as auth_router
        app.include_router(auth_router, prefix="/api")
        print("✅ Auth router loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load auth router: {e}")

# Load audit routers only if audit system is enabled
if audit_enabled:
    try:
        from app.routers import audit_router
        app.include_router(audit_router.router)
        print("✅ Audit router loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load audit router: {e}")

    try:
        from app.routers import dashboard_router
        app.include_router(dashboard_router.router)
        print("✅ Dashboard router loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load dashboard router: {e}")
else:
    print("⚠️ Audit routers disabled - audit system not available")

# Load Human Review router
try:
    from app.routers import human_review
    app.include_router(human_review.router)
    print("✅ Human Review router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load Human Review router: {e}")

# Initialize DeepSeek client if enabled (for enhanced PII detection)
try:
    from app.services.pii_main import load_deepseek_client
    load_deepseek_client()
except Exception as e:
    logger.warning(f"DeepSeek initialization failed: {e}")

# Create static directories if they don't exist
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Check if user is authenticated (via cookie or token)
async def check_user_authenticated(request: Request) -> bool:
    """Check if user has valid authentication token"""
    if not auth_enabled:
        return True
    
    # Check Authorization header (for API calls)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        if verify_token(token):
            return True
    
    # Check cookie for browser visits
    token = request.cookies.get("access_token")
    if token:
        payload = verify_token(token)
        if payload:
            return True
    
    # Check sessionStorage (for JavaScript-based auth)
    # Note: This won't work for server-side checks, so we skip it
    
    return False

# Serve the main page
@app.get("/")
async def read_index(request: Request):
    if not await check_user_authenticated(request):
        return RedirectResponse(url="/login")
    return FileResponse('templates/index.html')

# Serve the decrypt page
@app.get("/decrypt")
async def read_decrypt(request: Request):
    if not await check_user_authenticated(request):
        return RedirectResponse(url="/login")
    return FileResponse('templates/decrypt.html')

# Serve the login page
@app.get("/login")
async def read_login():
    return FileResponse('templates/login.html')

# Serve the registration page
@app.get("/register")
async def read_register():
    return FileResponse('templates/register.html')
