import cv2
import numpy as np
import os
import json
import uuid
from typing import List, Dict, Any
from app.services.aes_gcm import generate_key as generate_key_aes, encrypt_with_metadata, decrypt_with_metadata
import base64

def process_manual_masking(image_path: str, selections, task_id: str) -> Dict[str, Any]:
    try:
        print(f"[INFO] Starting manual masking for {image_path}")
        print(f"[INFO] Processing {len(selections)} manual selections")
        
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        original_height, original_width = image.shape[:2]
        print(f"[INFO] Image dimensions: {original_width}x{original_height}")
        
        masked_image = image.copy()
        
        key = generate_key_aes()
        
        masked_areas = []
        areas_masked = 0
        
        for i, selection in enumerate(selections):
            try:
                if hasattr(selection, 'dict'):
                    sel_dict = selection.dict()
                elif hasattr(selection, '__dict__'):
                    sel_dict = selection.__dict__
                else:
                    sel_dict = selection

                x = int(sel_dict.get('x', 0))
                y = int(sel_dict.get('y', 0))
                width = int(sel_dict.get('width', 0))
                height = int(sel_dict.get('height', 0))
                selection_type = sel_dict.get('selection_type', 'rectangle')

                print(f"[DEBUG] Processing selection {i+1}: x={x}, y={y}, w={width}, h={height}")

                if x < 0 or y < 0 or width <= 0 or height <= 0:
                    print(f"[WARN] Invalid selection coordinates")
                    continue
                
                x = max(0, min(x, original_width - 1))
                y = max(0, min(y, original_height - 1))
                width = min(width, original_width - x)
                height = min(height, original_height - y)
                
                if width <= 0 or height <= 0:
                    print(f"[WARN] Selection outside image bounds")
                    continue
                
                area_to_mask = image[y:y+height, x:x+width]

                success, roi_encoded = cv2.imencode('.png', area_to_mask)
                if not success:
                    print(f"[WARN] Failed to encode region, skipping")
                    continue

                roi_base64 = base64.b64encode(roi_encoded).decode('utf-8')

                text_to_encrypt = f"Manual_Selection_{i+1}_Area_{x}_{y}_{width}_{height}"

                encrypted = encrypt_with_metadata(text_to_encrypt, key)
                encrypted_str = json.dumps(encrypted)

                if selection_type == "rectangle":
                    cv2.rectangle(masked_image, (x, y), (x + width, y + height), (0, 0, 0), -1)
                elif selection_type == "blur":
                    roi = masked_image[y:y+height, x:x+width]
                    blurred_roi = cv2.GaussianBlur(roi, (51, 51), 0)
                    masked_image[y:y+height, x:x+width] = blurred_roi
                else:
                    cv2.rectangle(masked_image, (x, y), (x + width, y + height), (0, 0, 0), -1)

                masked_areas.append({
                    "cipher": encrypted_str,
                    "bbox": [[x, y], [x + width, y], [x + width, y + height], [x, y + height]],
                    "confidence": 1.0,
                    "original_image_base64": roi_base64
                })
                
                areas_masked += 1
                print(f"[SUCCESS] Masked area {i+1}")
                
            except Exception as e:
                print(f"[ERROR] Failed to process selection {i+1}: {e}")
                continue
        
        name, ext = os.path.splitext(image_path)
        output_image_path = f"{name}_masked{ext}"
        output_json_path = f"{name}_masked.json"
        key_file_path = f"{name}.key"
        
        cv2.imwrite(output_image_path, masked_image)
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(masked_areas, f, indent=2)
        
        with open(key_file_path, 'wb') as f:
            f.write(key)
        
        print(f"[SUCCESS] Manual masking completed: {areas_masked}/{len(selections)} areas")
        print(f"[SUCCESS] Masked image: {output_image_path}")
        print(f"[SUCCESS] Encryption key: {key_file_path}")

        return output_image_path, output_json_path, key_file_path
        
    except Exception as e:
        print(f"[ERROR] Manual masking failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

def decrypt_manual_selection(encrypted_data: str, key_path: str) -> Dict[str, Any]:
    try:
        with open(key_path, 'rb') as f:
            key = f.read()
        
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        decrypted_data = encrypted_bytes.decode('utf-8')
        
        area_data = json.loads(decrypted_data)
        
        return area_data
        
    except Exception as e:
        print(f"[ERROR] Failed to decrypt manual selection: {e}")
        return {}

def validate_manual_selections(selections: List[Dict], image_width: int, image_height: int) -> List[Dict]:
    validated_selections = []
    
    for i, selection in enumerate(selections):
        try:
            x = max(0, min(int(selection.get('x', 0)), image_width - 1))
            y = max(0, min(int(selection.get('y', 0)), image_height - 1))
            width = max(1, min(int(selection.get('width', 1)), image_width - x))
            height = max(1, min(int(selection.get('height', 1)), image_height - y))
            
            selection_type = selection.get('selection_type', 'rectangle')
            if selection_type not in ['rectangle', 'blur', 'freehand']:
                selection_type = 'rectangle'
            
            validated_selection = {
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'selection_type': selection_type
            }
            
            validated_selections.append(validated_selection)
            
        except Exception as e:
            print(f"[WARN] Invalid selection {i+1}: {e}")
            continue
    
    return validated_selections
