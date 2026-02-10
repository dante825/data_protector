# decrypt_text.py
import json
from app.services.aes_gcm import decrypt_with_metadata
import os
import pandas as pd

def decrypt_masked_file(masked_file_path, json_path, key_path):
    try:
        ext = os.path.splitext(masked_file_path)[1].lower()

        with open(key_path, "rb") as f:
            key = f.read()

        with open(json_path, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)

        if ext == ".csv":
            df = pd.read_csv(masked_file_path, dtype=str).fillna("")

            print(f"[INFO] Start decrypting CSV file, total {len(mapping_data)} mapping items")
            print(f"[INFO] CSV shape: {df.shape}")
            
            tag_to_original = {}
            for entry in mapping_data:
                original_text = decrypt_entry(entry["encrypted"], key)
                tag_to_original[entry["masked"]] = original_text
            
            sorted_tags = sorted(tag_to_original.items(), key=lambda x: len(x[0]), reverse=True)
            for tag, original_value in sorted_tags:
                df = df.replace(tag, original_value, regex=False)
                print(f"[DEBUG] replacing '{tag}' -> '{original_value}'")

            decrypted_file_path = masked_file_path.replace(".masked.csv", ".decrypted.csv")
            df.to_csv(decrypted_file_path, index=False)
            print(f"[INFO] csv decrypted: {decrypted_file_path}")

        elif ext == ".txt":
            with open(masked_file_path, "r", encoding="utf-8") as f:
                masked_content = f.read()

            decrypted_content = masked_content
            sorted_entries = sorted(mapping_data, key=lambda x: len(x["masked"]), reverse=True)
            
            for entry in sorted_entries:
                unique_tag = entry["masked"]
                original_text = decrypt_entry(entry["encrypted"], key)
                decrypted_content = decrypted_content.replace(unique_tag, original_text)

            decrypted_file_path = masked_file_path.replace(".masked.txt", ".decrypted.txt")
            with open(decrypted_file_path, "w", encoding="utf-8") as f:
                f.write(decrypted_content)

        else:
            return {"status": "error", "message": f"Unsupported file extension: {ext}"}

        return {
            "status": "success",
            "decrypted_file": decrypted_file_path
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

def decrypt_entry(encrypted_data, key):
    """Decrypt an entry from JSON-encrypted format"""
    if isinstance(encrypted_data, str):
        try:
            encrypted = json.loads(encrypted_data)
            return decrypt_with_metadata(encrypted, key)
        except (json.JSONDecodeError, KeyError):
            # Legacy Fernet format (if any still exists)
            return encrypted_data
    return encrypted_data
