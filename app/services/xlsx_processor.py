import os
import json
import re
import hashlib
from app.services.aes_gcm import encrypt_with_metadata, generate_key as generate_key_aes
from openpyxl import load_workbook
from app.services.pii_main import extract_all_pii

def mask_xlsx_sensitive_text(xlsx_path: str, key_path: str = None, enabled_pii_categories=None):
    if key_path is None:
        key_path = xlsx_path.replace(".xlsx", ".key")

    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
    else:
        key = generate_key_aes()
        with open(key_path, "wb") as f:
            f.write(key)

    wb = load_workbook(xlsx_path)

    full_text = ""
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.strip():
                    full_text += cell.value + " "

    all_pii_list = extract_all_pii(full_text, enabled_pii_categories)
    print(f"print all_pii_list: '{all_pii_list}'")
    
    unique_pii = {}
    masked_pii = []

    for label, value in all_pii_list:
        if value not in unique_pii:
            try:
                encrypted = encrypt_with_metadata(value, key)
                encrypted_str = json.dumps(encrypted)
                value_hash = hashlib.md5(value.encode()).hexdigest()[:8]
                unique_tag = f"[ENC:{label}_{value_hash}]"

                unique_pii[value] = {"encrypted": encrypted_str, "tag": unique_tag}
                masked_pii.append({
                    "original": value,
                    "encrypted": encrypted_str,
                    "label": label,
                    "masked": unique_tag
                })
            except Exception as e:
                print(f"[ERROR] Failed to encrypt '{value}': {e}")

    sorted_pii_items = sorted(unique_pii.items(), key=lambda x: len(x[0]), reverse=True)

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.strip():
                    masked_text = cell.value

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
                    cell.value = masked_text

    output_path = xlsx_path.replace(".xlsx", ".masked.xlsx")
    wb.save(output_path)
    
    json_output_path = xlsx_path.replace(".xlsx", ".masked.json")
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(masked_pii, f, indent=2)

    return {
        "status": "success",
        "masked_file": output_path,
        "json_output": json_output_path,
        "key_file": key_path
    }
