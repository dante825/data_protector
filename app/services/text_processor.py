import os
import json
import base64
import hashlib
import pandas as pd
import re
from app.services.aes_gcm import encrypt_with_metadata, decrypt_with_metadata
from app.services.pii_main import extract_all_pii
from app.resources.dictionaries import NAMES, ORG_NAMES

def read_text_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".txt", ".csv"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""

def run_text_processing(file_path: str, enabled_pii_categories=None, key_str: str = None):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        from app.services.aes_gcm import generate_key as generate_key_aes
        key = key_str.encode() if key_str else generate_key_aes()

        if ext == ".csv":
            return process_csv_optimized(file_path, key, enabled_pii_categories)
        else:
            return process_text_optimized(file_path, key, enabled_pii_categories)

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

def process_csv_optimized(file_path: str, key, enabled_pii_categories=None):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        full_content = f.read()

    print(f"[INFO] Starting PII extraction, enabled categories: {enabled_pii_categories}")
    pii_list = extract_all_pii(full_content, enabled_pii_categories)

    all_pii_list = pii_list
    print(f"[INFO] Total found {len(all_pii_list)} PII items")
    
    pii_mapping = {}
    mapping = []
    
    for label, value in all_pii_list:
        if value not in pii_mapping:
            try:
                encrypted = encrypt_with_metadata(value, key)
                encrypted_str = json.dumps(encrypted)
                
                value_hash = hashlib.md5(value.encode()).hexdigest()[:8]
                unique_tag = f"[ENC:{label}_{value_hash}]"
                
                pii_mapping[value] = {"encrypted": encrypted_str, "tag": unique_tag}
                mapping.append({
                    "original": value,
                    "encrypted": encrypted_str,
                    "label": label,
                    "masked": unique_tag
                })
            except Exception as e:
                print(f"[ERROR] Failed to encrypt '{value}': {e}")

    df = pd.read_csv(file_path, dtype=str).fillna("")
    
    sorted_pii_items = sorted(pii_mapping.items(), key=lambda x: len(x[0]), reverse=True)
    
    print(f"[INFO] starting masking of {len(sorted_pii_items)} PII items")
    for pii_value, pii_info in sorted_pii_items:
        df = df.replace(pii_value, pii_info["tag"], regex=False)
        print(f"[DEBUG] masking '{pii_value}' -> '{pii_info['tag']}'")

    print(f"[INFO] Masking completed: {df.shape}")

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.dirname(file_path)
    masked_csv_path = os.path.join(output_dir, base_name + ".masked.csv")
    json_output_path = os.path.join(output_dir, base_name + ".masked.json")
    key_file_path = os.path.join(output_dir, base_name + ".key")

    df.to_csv(masked_csv_path, index=False)
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    with open(key_file_path, "wb") as f:
        f.write(key)

    return {
        "status": "success",
        "masked_file": masked_csv_path,
        "json_output": json_output_path,
        "key_file": key_file_path
    }

def process_text_optimized(file_path: str, key, enabled_pii_categories=None):
    content = read_text_file(file_path)

    print("[INFO] Starting PII extraction...")
    all_pii_list = extract_all_pii(content, enabled_pii_categories)

    print(f"[INFO] Total found {len(all_pii_list)} PII items")
    
    unique_pii = {}
    mapping = []
    
    for label, value in all_pii_list:
        if value not in unique_pii:
            try:
                encrypted = encrypt_with_metadata(value, key)
                encrypted_str = json.dumps(encrypted)
                
                value_hash = hashlib.md5(value.encode()).hexdigest()[:8]
                unique_tag = f"[ENC:{label}_{value_hash}]"
                
                unique_pii[value] = {"encrypted": encrypted_str, "tag": unique_tag}
                mapping.append({
                    "original": value,
                    "encrypted": encrypted_str,
                    "label": label,
                    "masked": unique_tag
                })
            except Exception as e:
                print(f"[ERROR] Failed to encrypt '{value}': {e}")

    sorted_pii_items = sorted(unique_pii.items(), key=lambda x: len(x[0]), reverse=True)

    masked_text = content
    for pii_value, pii_info in sorted_pii_items:
        parts = re.split(r'(\[ENC:[^\]]+\])', masked_text)

        for i in range(len(parts)):
            if i % 2 == 0 and not parts[i].startswith('[ENC:'):
                escaped_pii = re.escape(pii_value)
                if len(pii_value) == 1 and pii_value.isdigit():
                    pattern = r'\b' + escaped_pii + r'\b'
                else:
                    pattern = escaped_pii
                parts[i] = re.sub(pattern, pii_info["tag"], parts[i])

        masked_text = ''.join(parts)

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.dirname(file_path)
    masked_file_path = os.path.join(output_dir, base_name + ".masked.txt")
    json_output_path = os.path.join(output_dir, base_name + ".masked.json")
    key_file_path = os.path.join(output_dir, base_name + ".key")

    with open(masked_file_path, "w", encoding="utf-8") as f:
        f.write(masked_text)
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    with open(key_file_path, "wb") as f:
        f.write(key)

    return {
        "status": "success",
        "masked_file": masked_file_path,
        "json_output": json_output_path,
        "key_file": key_file_path
    }
