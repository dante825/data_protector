from docx import Document
import json
from app.services.aes_gcm import decrypt_with_metadata

def decrypt_masked_docx(masked_path: str, json_path: str, key_path: str):
    with open(key_path, "rb") as f:
        key = f.read()

    with open(json_path, "r", encoding="utf-8") as f:
        masked_info = json.load(f)

    document = Document(masked_path)

    tag_to_original = {}
    for entry in masked_info:
        encrypted_data = entry["encrypted"]
        if isinstance(encrypted_data, str):
            try:
                encrypted = json.loads(encrypted_data)
                original = decrypt_with_metadata(encrypted, key)
            except (json.JSONDecodeError, KeyError):
                original = encrypted_data
        else:
            original = encrypted_data
        tag_to_original[entry["masked"]] = original

    for para in document.paragraphs:
        para_text = para.text
        for masked_tag, original_text in tag_to_original.items():
            para_text = para_text.replace(masked_tag, original_text)
        para.text = para_text

    decrypted_path = masked_path.replace(".masked.docx", ".decrypted.docx")
    document.save(decrypted_path)
    return {
        "status": "success",
        "decrypted_file": decrypted_path
    }
