# Change Log

All notable changes to Project Protector will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New `app/services/aes_gcm.py` module with AES-256-GCM authenticated encryption
- Unit tests in `tests/test_aes_gcm.py` with 8 comprehensive test cases
- `run_xlsx_processing()` wrapper function in `xlsx_processor.py`

### Changed
- **Encryption**: Replaced Fernet with AES-256-GCM across all processor modules
  - `app/services/ocr_jpeg.py` - Image OCR processing
  - `app/services/text_processor.py` - Text/CSV processing  
  - `app/services/decrypt_text.py` - Text/CSV decryption
  - `app/services/docx_processor.py` - Word document processing
  - `app/services/decrypt_docx.py` - Word document decryption
  - `app/services/xlsx_processor.py` - Excel processing (now includes `run_xlsx_processing`)
  - `app/services/manual_masking_service.py` - Manual masking
  - `app/services/decrypt_jpeg.py` - Image decryption
- **JSON Format**: Changed from `{"encrypted": "..."}` to `{"ciphertext": "...", "nonce": "...", "auth_tag": "..."}`
- **Key Generation**: Uses `AESGCM.generate_key()` (32-byte AES-256 key)

### Security
- **Improved**: Now using authenticated encryption (AES-256-GCM) instead of Fernet
- **Tamper Detection**: Decryption fails if ciphertext/auth_tag is modified
- **Integrity**: GCM mode provides built-in authentication tag verification
- **Performance**: Parallelizable encryption/decryption for better performance

### Removed
- Deprecated: `Fernet.encrypt()` and `Fernet.decrypt()` usage

## Previous Versions

See git history for earlier changes.

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

### Breaking Changes
- No backward compatibility with Fernet-encrypted files
- New files use AES-256-GCM format only
- Re-process old Fernet-encrypted files to migrate

### Testing
- All encryption/decryption round-trips verified ✅
- Unicode support confirmed (Chinese, Arabic, symbols) ✅
- Sample processing (74 PII items) ✅
- JSON format verified ✅

### Benefits
- Authenticated encryption (confidentiality + integrity)
- Tamper detection via auth_tag
- No padding oracle attacks
- Better performance with parallelizable encryption
