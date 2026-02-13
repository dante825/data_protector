# Change Log

All notable changes to Project Protector will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

 ## [Unreleased]

 ### Added
 - Comprehensive name detection for all ethnicities (English, Indian, Malay, Chinese)
 - Enhanced LLM prompts with name examples for all name types
 - English names: Yap En Chong, Alfred Lee Chee Shing, Jeremy Tan Choo Hau, Dennis Smith
 - Indian names: Raj Kumar a/l Subramaniam, Priya Devi a/l Venkat, Lim Wei Jian
 - Malay names: Ahmad bin Ali, Siti binti Hassan, Lim Wei Jian, Janting anak Sumping
 - Chinese character names: 王伟, 李娜, 张强, 刘芳, 陈杰, 杨明
 - Names dictionary expanded with 70+ new names from all ethnic groups
- User and Session database models

### Changed
- **Encryption**: Replaced Fernet with AES-256-GCM across all processor modules

## [1.0.0] - 2026-02-10

### Added
- Full JWT-based authentication system with user registration and login
- API key management for programmatic access
- Authentication middleware protecting all `/api/*` routes
- User session tracking and logout functionality
- Token refresh mechanism with JWT pairs

### Changed
- **Encryption**: Replaced Fernet with AES-256-GCM across all processor modules

### Security
- All API endpoints now require valid JWT token in `Authorization: Bearer <token>` header
- Passwords hashed with bcrypt (12 rounds)
- JWT access tokens expire in 24 hours
- JWT refresh tokens expire in 7 days

## Previous Versions

See git history for earlier changes.

## [1.0.0] - 2026-02-10

The initial release of Project Protector with comprehensive PII detection,
AES-256-GCM encryption, and full JWT authentication system.

### Added
- Multi-layered PII detection (SpaCy NER, Gemini API, Presidio)
- OCR support for PDF/image files via EasyOCR and Tesseract
- End-to-end encryption with decryption restoration mode
- Full JWT authentication system (registration, login, logout)
- API key management
- Comprehensive audit logging system
- Web UI with FastAPI and static assets

### Changed
- N/A

### Security
- See Authentication section below

---

## Recent Additions: JWT Authentication (Feb 10, 2026)

### Summary
Implemented comprehensive JWT-based authentication and authorization system to protect all API routes.

### New Endpoints
| Endpoint | Method | Description |
|---------|-----|-----------|
| `/api/auth/register` | POST | Register a new user |
| `/api/auth/login` | POST | Login and receive JWT tokens |
| `/api/auth/logout` | POST | Logout current user |
| `/api/auth/refresh-token` | POST | Refresh access token |
| `/api/auth/me` | GET | Get current user information |
| `/api/auth/api-key` | POST | Generate API key |
| `/api/auth/api-keys` | GET | List API keys |
| `/api/auth/api-key/{id}` | DELETE | Revoke API key |

### Protected Endpoints (All require JWT)
| Endpoint | Method | Protected |
|---------|-----|-------|
| `/api/upload_files` | POST | ✅ |
| `/api/process/{task_id}` | POST | ✅ |
| `/api/download/{task_id}` | GET | ✅ |
| `/api/decrypt` | POST | ✅ |
| `/api/audit/*` | GET | ✅ |
| `/api/human-review/*` | GET/POST | ✅ |

### New Files
- `app/auth/__init__.py` - Auth module
- `app/auth/schemas.py` - Pydantic schemas
- `app/auth/models.py` - User, ApiKey, UserSession models
- `app/auth/jwt_handler.py` - JWT token generation/validation
- `app/auth/password_hasher.py` - Bcrypt password hashing
- `app/auth/routers/auth_router.py` - Auth endpoints
- `app/auth/routers/api_key_router.py` - API key management
- `app/database/auth_database.py` - Auth database initialization
- `app/dependencies/auth_deps.py` - FastAPI auth dependencies
- `app/middleware/auth_middleware.py` - JWT authentication middleware
- `app/config/auth_config.py` - JWT configuration

### Updated Files
- `app/main.py` - Include auth middleware and auth routers
- `app/routers/upload.py` - Protected with auth dependency
- `app/routers/process_router.py` - Protected with auth dependency
- `app/routers/download_router.py` - Protected with auth dependency
- `app/routers/decrypt_router.py` - Protected with auth dependency
- `app/models/audit_models.py` - Added user relationships
- `requirements.txt` - Added python-jose, passlib, pydantic-settings

### Breaking Changes
- All API routes now require JWT authentication
- Existing files encrypted with Fernet are incompatible with new system
- Users must re-upload files after encryption migration

### Testing
- All router imports verified ✅
- JWT token generation verified ✅
- Password hashing verified ✅
- Auth middleware integrated ✅

### Security Features
- JWT access tokens: 24-hour expiry
- JWT refresh tokens: 7-day expiry
- Password hashing: bcrypt with 12 rounds
- Session tracking with logout support
- API key generation and revocation

---

## Recent Migration: Fernet → AES-256-GCM (Feb 10, 2026)

### Summary
Complete replacement of Fernet encryption with AES-256-GCM authenticated encryption.

### Files Modified
1. `app/services/aes_gcm.py` - New encryption module (117 lines)
2. `app/services/ocr_jpeg.py` - Updated key generation and encryption calls
3. `app/services/text_processor.py` - Updated to use AES-256-GCM
4. `app/services/decrypt_text.py` - Updated decryption to use AES-256-GCM
5. `app/services/docx_processor.py` - Updated encryption/decryption
6. `app/services/decrypt_docx.py` - Updated decryption to use AES-256-GCM
7. `app/services/xlsx_processor.py` - Updated encryption, added `run_xlsx_processing()`
8. `app/services/manual_masking_service.py` - Updated encryption
9. `app/services/decrypt_jpeg.py` - Updated decryption to use AES-256-GCM
10. `tests/test_aes_gcm.py` - New unit tests (172 lines)

### JSON Format Change
**Before (Fernet):**
```json
{"encrypted": "fG...encoded_text...="}
```

**After (AES-256-GCM):**
```json
{
  "ciphertext": "base64_ciphertext",
  "nonce": "base64_nonce",
  "auth_tag": "base64_auth_tag"
}
```

### Breaking Changes
- No backward compatibility with Fernet-encrypted files
- New files use AES-256-GCM format only
- Re-process old Fernet-encrypted files to migrate

### Benefits
- Authenticated encryption (confidentiality + integrity)
- Tamper detection via auth_tag
- No padding oracle attacks
- Better performance with parallelizable encryption
