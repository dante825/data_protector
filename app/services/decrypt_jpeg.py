import base64
import cv2
import numpy as np
import json
from app.services.aes_gcm import decrypt_with_metadata
import io

def decrypt_masked_image_to_bytes(masked_image_path: str, json_path: str, key_path: str):
    image = cv2.imread(masked_image_path)
    if image is None:
        raise ValueError("Unable to read image (possibly not written yet or path error): {masked_image_path}")

    with open(key_path, "rb") as f:
        key = f.read()

    with open(json_path, "r", encoding="utf-8") as f:
        encrypted_data = json.load(f)

    print(f"starting decryption of {len(encrypted_data)} encrypted regions")

    for i, entry in enumerate(encrypted_data):
        try:
            bbox = entry["bbox"]
            roi_b64 = entry.get("original_image_base64")

            if roi_b64:
                roi_data = base64.b64decode(roi_b64)
                roi_array = np.frombuffer(roi_data, dtype=np.uint8)
                roi = cv2.imdecode(roi_array, cv2.IMREAD_COLOR)

                if roi is not None:
                    x_coords = [int(p[0]) for p in bbox]
                    y_coords = [int(p[1]) for p in bbox]
                    x_min, x_max = min(x_coords), max(x_coords)
                    y_min, y_max = min(y_coords), max(y_coords)

                    print(f"Region {i+1}: coordinates ({x_min},{y_min}) to ({x_max},{y_max}), ROI size: {roi.shape}")

                    x_min = max(0, x_min)
                    y_min = max(0, y_min)
                    x_max = min(image.shape[1], x_max)
                    y_max = min(image.shape[0], y_max)

                    if (y_max - y_min) > 0 and (x_max - x_min) > 0:
                        target_h, target_w = y_max - y_min, x_max - x_min

                        if roi.shape[0] != target_h or roi.shape[1] != target_w:
                            roi_resized = cv2.resize(roi, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
                        else:
                            roi_resized = roi

                        expand_pixels = 1
                        x_min_exp = max(0, x_min - expand_pixels)
                        y_min_exp = max(0, y_min - expand_pixels)
                        x_max_exp = min(image.shape[1], x_max + expand_pixels)
                        y_max_exp = min(image.shape[0], y_max + expand_pixels)

                        masked_region = image[y_min_exp:y_max_exp, x_min_exp:x_max_exp]
                        exp_h, exp_w = y_max_exp - y_min_exp, x_max_exp - x_min_exp
                        if exp_h != target_h or exp_w != target_w:
                            roi_y_offset = y_min - y_min_exp
                            roi_x_offset = x_min - x_min_exp

                            roi_expanded = np.zeros((exp_h, exp_w, 3), dtype=np.uint8)

                            roi_expanded[roi_y_offset:roi_y_offset+target_h,
                                       roi_x_offset:roi_x_offset+target_w] = roi_resized
                            if roi_y_offset > 0:
                                roi_expanded[:roi_y_offset, :] = roi_expanded[roi_y_offset:roi_y_offset+1, :]
                            if roi_y_offset + target_h < exp_h:
                                roi_expanded[roi_y_offset+target_h:, :] = roi_expanded[roi_y_offset+target_h-1:roi_y_offset+target_h, :]
                            if roi_x_offset > 0:
                                roi_expanded[:, :roi_x_offset] = roi_expanded[:, roi_x_offset:roi_x_offset+1]
                            if roi_x_offset + target_w < exp_w:
                                roi_expanded[:, roi_x_offset+target_w:] = roi_expanded[:, roi_x_offset+target_w-1:roi_x_offset+target_w]

                            image[y_min_exp:y_max_exp, x_min_exp:x_max_exp] = roi_expanded
                        else:
                            image[y_min:y_max, x_min:x_max] = roi_resized

                        print(f"region {i+1} decrypted (expanded area: {exp_w}x{exp_h})")
                    else:
                        print(f"region {i+1} failed: invalid coordinates")
                else:
                    print(f"region {i+1} ROI decoding failed, skipping")
            else:
                print(f"region {i+1} missing original image data, skipping")

        except Exception as e:
            print(f"decryption of region {i+1} failed: {e}")
            continue

    image = post_process_decrypted_image(image, encrypted_data)

    cv2.imwrite("/tmp/debug_decrypted_result.png", image)
    print("decrypted image saved to /tmp/debug_decrypted_result.png")

    _, buffer = cv2.imencode('.png', image)
    img_bytes = buffer.tobytes()
    return img_bytes

def post_process_decrypted_image(image, encrypted_data):
    processed_image = image.copy()

    for i, entry in enumerate(encrypted_data):
        try:
            bbox = entry["bbox"]
            x_coords = [int(p[0]) for p in bbox]
            y_coords = [int(p[1]) for p in bbox]
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)

            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(image.shape[1], x_max)
            y_max = min(image.shape[0], y_max)

            if (y_max - y_min) > 0 and (x_max - x_min) > 0:
                region = processed_image[y_min:y_max, x_min:x_max]

                black_mask = np.all(region < 10, axis=2)

                if np.any(black_mask):
                    inpaint_mask = black_mask.astype(np.uint8) * 255

                    if np.sum(inpaint_mask) > 0:
                        repaired_region = cv2.inpaint(region, inpaint_mask, 3, cv2.INPAINT_TELEA)
                        processed_image[y_min:y_max, x_min:x_max] = repaired_region
                        print(f"region {i+1} post-processed, fixed {np.sum(black_mask)} black pixels")

        except Exception as e:
            print(f"post-processing of region {i+1} failed: {e}")
            continue

    return processed_image
