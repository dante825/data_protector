# Project knowledge

This file gives Codebuff context about your project: goals, commands, conventions, and gotchas.

## What is this?
Project Protector — an AI-powered PII detection, masking, and restoration system. Supports text, CSV, PDF, DOCX, XLSX, and images (JPG/PNG). Uses SpaCy NER + Ollama (local LLM) + Presidio for multi-layered PII detection, EasyOCR/Tesseract for OCR, and AES-256-GCM for encryption.

## Quickstart
- **Python**: 3.11 (conda env `data_protector`)
- **Setup**: `conda env create -f environment.yml && conda activate data_protector` or `python -m venv venv && pip install -r requirements.txt`
- **Run**: `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- **Test**: `pytest tests/`
- **External dep**: Poppler required for PDF processing (update `poppler_path` in `app/services/decrypt_pdf.py`)
- **Admin setup**: `python setup_admin.py`

## Architecture
- **Backend**: FastAPI + Uvicorn (ASGI)
- **Frontend**: Plain HTML/CSS/JS served as static files (no framework)
- **Database**: SQLite via SQLAlchemy (audit logs + auth)
- **Key directories**:
  - `app/` — main application package
  - `app/services/` — core processing: PII detection (`pii_main.py`), encryption (`aes_gcm.py`), processors per file type, decryptors
  - `app/routers/` — FastAPI route handlers (upload, process, download, decrypt, audit, dashboard, human_review)
  - `app/auth/` — JWT auth system (models, schemas, jwt_handler, password_hasher, routers)
  - `app/config/` — LLM configs (Ollama, ChatGPT)
  - `app/middleware/` — audit + auth middleware
  - `app/database/` — DB init for audit and auth
  - `app/dependencies/` — FastAPI dependency injection (auth)
  - `app/resources/` — PII dictionaries
  - `static/` — CSS + JS assets
  - `templates/` — HTML pages (index, login, register, decrypt, audit_dashboard, human_review)
  - `tests/` — pytest tests
- **Data flow**: Upload → OCR (if image/PDF) → PII detection (SpaCy + Ollama + Presidio) → Mask/Encrypt (AES-256-GCM) → Download masked file. Decrypt flow reverses encryption.

## Auth
- JWT-based auth protects all `/api/*` routes
- Access tokens: 24h expiry; Refresh tokens: 7 days
- Passwords hashed with bcrypt (12 rounds)
- Browser auth uses HTTP-only cookies; API auth uses Bearer tokens

## Conventions
- **Language**: Python 3.11, type hints encouraged
- **Framework**: FastAPI with Pydantic schemas
- **Encryption**: AES-256-GCM only (Fernet was removed). JSON format: `{ciphertext, nonce, auth_tag}` (all base64)
- **Routers**: Each router in its own file under `app/routers/`, prefixed with `/api` in `main.py`
- **Error handling**: Try/except blocks with logging; routers loaded with graceful fallback
- **Logging**: Python `logging` module + `rich` for CLI output
- **PII categories**: LOCATIONS, STATUS, RELIGIONS are disabled (not in SELECTABLE_PII_CATEGORIES)

## Gotchas
- No backward compatibility with old Fernet-encrypted files
- SQLite is used (not production-grade); audit and auth are separate DB inits
- Some processor modules have similar logic (text, docx, xlsx, pdf) — not yet consolidated
- First request can be slow due to lazy model loading (SpaCy, EasyOCR)
- `Improvement.md` contains admin credentials — do not commit secrets
