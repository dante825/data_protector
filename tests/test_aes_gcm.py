"""
Unit tests for AES-256-GCM encryption module
Tests encryption/decryption round-trip and tamper detection
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.aes_gcm import (
    generate_key,
    encrypt,
    decrypt,
    encrypt_with_metadata,
    decrypt_with_metadata
)


class TestAES256GCM:
    """Test AES-256-GCM encryption functions"""
    
    @pytest.fixture
    def key(self):
        """Generate a test key"""
        return generate_key()
    
    def test_generate_key_returns_32_bytes(self, key):
        """Verify key is 32 bytes (256 bits)"""
        assert len(key) == 32
    
    def test_encrypt_decrypt_round_trip(self, key):
        """Test basic encryption and decryption"""
        plaintext = "Hello, World! This is a test."
        ciphertext = encrypt(plaintext, key)
        decrypted = decrypt(ciphertext, key)
        
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_with_special_characters(self, key):
        """Test encryption with special characters and unicode"""
        plaintext = "Special chars: @#$%^&*()中文العربية"
        ciphertext = encrypt(plaintext, key)
        decrypted = decrypt(ciphertext, key)
        
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_empty_string(self, key):
        """Test encryption with empty string"""
        plaintext = ""
        ciphertext = encrypt(plaintext, key)
        decrypted = decrypt(ciphertext, key)
        
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_large_text(self, key):
        """Test encryption with larger text"""
        plaintext = "A" * 10000  # 10KB of text
        ciphertext = encrypt(plaintext, key)
        decrypted = decrypt(ciphertext, key)
        
        assert decrypted == plaintext
    
    def test_encrypt_different_nonce(self, key):
        """Test that different nonces produce different ciphertexts"""
        plaintext = "Same text different nonce"
        
        ciphertext1 = encrypt(plaintext, key)
        ciphertext2 = encrypt(plaintext, key)
        
        # Ciphertexts should be different due to random nonce
        assert ciphertext1 != ciphertext2
        
        # But both should decrypt to same plaintext
        assert decrypt(ciphertext1, key) == plaintext
        assert decrypt(ciphertext2, key) == plaintext
    
    def test_encrypt_with_metadata_returns_dict(self, key):
        """Test structured encryption returns correct dict structure"""
        plaintext = "Metadata test"
        result = encrypt_with_metadata(plaintext, key)
        
        assert isinstance(result, dict)
        assert "ciphertext" in result
        assert "nonce" in result
        assert "auth_tag" in result
        
        assert isinstance(result["ciphertext"], str)
        assert isinstance(result["nonce"], str)
        assert isinstance(result["auth_tag"], str)
    
    def test_encrypt_with_metadata_decrypt_round_trip(self, key):
        """Test structured encryption and decryption"""
        plaintext = "Structured encryption test"
        encrypted = encrypt_with_metadata(plaintext, key)
        decrypted = decrypt_with_metadata(encrypted, key)
        
        assert decrypted == plaintext
    
    def test_decrypt_with_metadata_tamper_ciphertext(self, key):
        """Test that tampered ciphertext is detected"""
        plaintext = "Tamper detection test"
        encrypted = encrypt_with_metadata(plaintext, key)
        
        # Tamper with ciphertext
        encrypted["ciphertext"] = "a" * len(encrypted["ciphertext"])
        
        with pytest.raises(Exception):  # InvalidTag or similar
            decrypt_with_metadata(encrypted, key)
    
    def test_decrypt_with_metadata_tamper_nonce(self, key):
        """Test that tampered nonce is detected"""
        plaintext = "Nonce tamper test"
        encrypted = encrypt_with_metadata(plaintext, key)
        
        # Tamper with nonce
        encrypted["nonce"] = "a" * len(encrypted["nonce"])
        
        with pytest.raises(Exception):  # InvalidTag or similar
            decrypt_with_metadata(encrypted, key)
    
    def test_decrypt_with_metadata_tamper_auth_tag(self, key):
        """Test that tampered auth_tag is detected"""
        plaintext = "Auth tag tamper test"
        encrypted = encrypt_with_metadata(plaintext, key)
        
        # Tamper with auth_tag
        encrypted["auth_tag"] = "a" * len(encrypted["auth_tag"])
        
        with pytest.raises(Exception):  # InvalidTag or similar
            decrypt_with_metadata(encrypted, key)
    
    def test_wrong_key_fails(self, key):
        """Test that wrong key cannot decrypt"""
        plaintext = "Wrong key test"
        ciphertext = encrypt(plaintext, key)
        
        wrong_key = generate_key()
        
        with pytest.raises(Exception):  # InvalidTag or similar
            decrypt(ciphertext, wrong_key)
    
    def test_multiple_encryption_decryption(self, key):
        """Test multiple sequential encryption/decryption operations"""
        texts = [
            "First message",
            "Second message",
            "Third message with numbers 12345",
            "Fourth message with symbols !@#$%",
        ]
        
        for text in texts:
            ciphertext = encrypt(text, key)
            decrypted = decrypt(ciphertext, key)
            assert decrypted == text
    
    def test_decrypt_with_metadata_multiple_entries(self, key):
        """Test decrypting multiple entries from JSON-like structure"""
        entries = [
            {"original": "Entry 1", "masked": "[ENC:TEST_12345678]"},
            {"original": "Entry 2", "masked": "[ENC:TEST_87654321]"},
            {"original": "Entry 3 中文", "masked": "[ENC:TEST_ABCDEF12]"},
        ]
        
        for entry in entries:
            encrypted = encrypt_with_metadata(entry["original"], key)
            decrypted = decrypt_with_metadata(encrypted, key)
            assert decrypted == entry["original"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
