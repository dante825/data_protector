"""
AES-256-GCM Encryption Module
Replaces Fernet with authenticated encryption using AES-256-GCM
"""
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64


def generate_key() -> bytes:
    """
    Generate a secure 256-bit (32-byte) AES key.
    Compatible with Fernet key size.
    
    Returns:
        bytes: 32-byte AES-256 key
    """
    return AESGCM.generate_key(bit_length=256)


def encrypt(text: str, key: bytes) -> bytes:
    """
    Encrypt text using AES-256-GCM.
    
    Args:
        text: Plaintext to encrypt
        key: 32-byte AES-256 key
    
    Returns:
        bytes: Ciphertext (includes nonce + auth_tag)
    """
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(key)
    
    ciphertext = aesgcm.encrypt(nonce, text.encode('utf-8'), None)
    
    # Combine nonce + ciphertext for storage
    return nonce + ciphertext


def decrypt(ciphertext: bytes, key: bytes) -> str:
    """
    Decrypt ciphertext using AES-256-GCM.
    
    Args:
        ciphertext: Encrypted data (nonce + ciphertext)
        key: 32-byte AES-256 key
    
    Returns:
        str: Decrypted plaintext
    
    Raises:
        cryptography.exceptions.InvalidTag: If authentication fails (tampered data)
    """
    nonce = ciphertext[:12]  # First 12 bytes are nonce
    actual_ciphertext = ciphertext[12:]
    
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, actual_ciphertext, None)
    
    return plaintext.decode('utf-8')


def encrypt_with_metadata(text: str, key: bytes) -> dict:
    """
    Encrypt text and return structured metadata for JSON storage.
    
    Args:
        text: Plaintext to encrypt
        key: 32-byte AES-256 key
    
    Returns:
        dict:加密数据，含ciphertext、nonce、auth_tag（base64编码）
    """
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(key)
    
    ciphertext = aesgcm.encrypt(nonce, text.encode('utf-8'), None)
    
    # Extract auth tag (last 16 bytes of ciphertext)
    auth_tag = ciphertext[-16:]
    actual_ciphertext = ciphertext[:-16]
    
    return {
        "ciphertext": base64.b64encode(actual_ciphertext).decode('utf-8'),
        "nonce": base64.b64encode(nonce).decode('utf-8'),
        "auth_tag": base64.b64encode(auth_tag).decode('utf-8')
    }


def decrypt_with_metadata(data: dict, key: bytes) -> str:
    """
    Decrypt using structured metadata from JSON storage.
    
    Args:
        data: Dict with ciphertext、nonce、auth_tag (base64 encoded)
        key: 32-byte AES-256 key
    
    Returns:
        str: Decrypted plaintext
    
    Raises:
        cryptography.exceptions.InvalidTag: If authentication fails (tampered data)
    """
    ciphertext = base64.b64decode(data["ciphertext"])
    nonce = base64.b64decode(data["nonce"])
    auth_tag = base64.b64decode(data["auth_tag"])
    
    # Combine ciphertext and auth tag for decryption
    encrypted_data = ciphertext + auth_tag
    
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, encrypted_data, None)
    
    return plaintext.decode('utf-8')
