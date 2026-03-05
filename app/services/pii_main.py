# OCR/pii_main.py
import json
import re
from typing import List, Tuple, Optional

from app.config.ollama_config import OLLAMA_ENABLED
from app.services.ollama_client import generate_json
ollama_enabled = OLLAMA_ENABLED
ollama_client = None


# Regex patterns for critical PII types (fallback detection)
REGEX_PATTERNS = {
    'IC': [
        r'\b\d{6}-\d{2}-\d{4}\b',  # 920312-10-8888
        r'\b\d{12}\b',  # 123456789012 (12 consecutive digits)
    ],
    'EMAIL': [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    ],
    'PHONE': [
        r'\b\+?6?0?\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b',  # Malaysian phone formats
        r'\b\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b',
    ],
    'CREDIT_CARD': [
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        r'\b\d{13,19}\b',
    ],
    'PASSPORT': [
        r'\b[A-Z]{1,2}\d{6,9}\b',  # Passport numbers
    ],
}


def extract_pii_with_regex(text: str) -> List[Tuple[str, str]]:
    """
    Fallback regex-based PII detection for critical types.
    Used when LLM fails or as supplementary detection.
    
    Returns:
        List of (label, value) tuples
    """
    results = []
    seen = set()
    
    for pii_type, patterns in REGEX_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                value = match.strip()
                if len(value) >= 5 and value not in seen:
                    seen.add(value)
                    results.append((pii_type, value))
    
    if results:
        print(f"[REGEX-FALLBACK] Found {len(results)} PII items via regex")
        for label, value in results:
            print(f"  - {label}: {value}")
    
    return results


def load_ollama_client():
    """Initialize Ollama client if available"""
    global ollama_client, ollama_enabled
    try:
        from app.config.ollama_config import OLLAMA_ENABLED
        from app.services.ollama_client import generate_json
        ollama_enabled = OLLAMA_ENABLED
        ollama_client = True
        print("✅ Ollama API client initialized successfully")
        return True
    except Exception as e:
        print(f"[WARN] Failed to initialize Ollama client: {e}")
        print("[INFO] Ollama PII detection disabled")
        ollama_enabled = False
        return False


def chunk_text_intelligently(text: str, max_chunk_size: int = 3000) -> List[str]:
    """
    Intelligently chunk text to avoid breaking PII entities across chunks

    Args:
        text: Text to chunk
        max_chunk_size: Maximum characters per chunk

    Returns:
        List of text chunks
    """
    if len(text) <= max_chunk_size:
        return [text]

    chunks = []
    current_chunk = ""

    # Split by paragraphs first, then sentences if needed
    paragraphs = text.split('\n\n')

    for paragraph in paragraphs:
        # If adding this paragraph would exceed chunk size
        if len(current_chunk) + len(paragraph) > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # If single paragraph is too long, split by sentences
            if len(paragraph) > max_chunk_size:
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) > max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                    current_chunk += sentence + ". "
            else:
                current_chunk = paragraph
        else:
            current_chunk += "\n\n" + paragraph if current_chunk else paragraph

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# === LLM Detection Settings ===
LLM_CONFIDENCE_THRESHOLD = 0.5
LLM_MIN_TEXT_LENGTH = 100

# === General ignored words (non-sensitive, no encryption required) ===
IGNORE_WORDS = {
    "malaysia", "mykad", "identity", "card", "kad", "pengenalan",
    "warganegara", "lelaki", "perempuan", "bujang", "kawin",
    "lel", "per", "male", "female", "citizen", "not citizen"
}

# ✅ Optional PII Category Definitions
SELECTABLE_PII_CATEGORIES = {
    "NAMES": "Personal names and identities",
    "ORG_NAMES": "Company and organization names",
    "ETHNIC": "Ethnic/religious affiliations (LLM detection only)"
}

# ✅ Non-selective PII categories (always masked)
NON_SELECTABLE_PII_CATEGORIES = {
    "IC": "Malaysian IC numbers",
    "Email": "Email addresses",
    "DOB": "Date of birth",
    "Bank Account": "Bank account numbers",
    "Passport": "Passport numbers",
    "Phone": "Phone numbers",
    "Credit Card": "Credit card numbers",
    "Address": "Street addresses",
    "Vehicle Registration": "Vehicle registration numbers"
}


def extract_pii_with_ollama(text: str, enabled_categories: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """
    Use Ollama to identify PII in text with Malaysian context focus
    Uses generate_json function from ollama_client module

    Args:
        text: Text to analyze
        enabled_categories: List of enabled PII categories

    Returns:
        List of (label, value) tuples
    """
    if not ollama_enabled:
        return []

    if not text or len(text.strip()) < 20:
        return []

    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())
    
    # Always include non-selectable categories for detection (they should always be masked)
    all_detection_categories = list(set(enabled_categories + ['IC', 'EMAIL', 'PHONE', 'ACCOUNT', 'CREDIT_CARD', 'PASSPORT', 'ADDRESS', 'DOB']))

    text_chunks = chunk_text_intelligently(text, max_chunk_size=3000)
    all_results = []

    print(f"[Ollama] Processing {len(text_chunks)} text chunks")

    for chunk_idx, chunk in enumerate(text_chunks):
        try:
            categories_desc = {
                "NAMES": "Personal names (Malaysian names like 'Ahmad bin Ali', 'WONG JUN KEAT', 'Ramba anak Sumping')",
                "ORG_NAMES": "Company and organization names (Sdn Bhd, Berhad, Holdings, Ltd, Inc)",
                "ETHNIC": "Ethnic/religious affiliations",
                "IC": "Malaysian IC/NRIC numbers (format: 123456-78-9012)",
                "EMAIL": "Email addresses",
                "PHONE": "Phone numbers (+60123456789, 03-77855409, 012-555-2389)",
                "ACCOUNT": "Bank account numbers (10-16 digits)",
                "CREDIT_CARD": "Credit card numbers",
                "PASSPORT": "Passport numbers",
                "ADDRESS": "Street addresses",
                "DOB": "Date of birth"
            }

            enabled_desc = [f"- {cat}: {categories_desc.get(cat, cat)}" for cat in all_detection_categories if cat in categories_desc]
            categories_text = "\n".join(enabled_desc)

            prompt = f"""Anda adalah pakar pengesanan PII yang mengetahui dokumen kewangan dan identiti Malaysia.

Semak teks berikut dan kenal pasti entiti PII. Fokus pada kategori-kategori ini:
{categories_text}

PERATURAN PENGDALIAN PENTING:
1. SENTIASA kenal pasti item sensitif ini regardless of category settings:
   - Nombor IC (format: 123456-78-9012 atau sejenis)
   - Nombor akaun (urutan digit panjang: 1234567890123456)
   - Nombor telefon (+60123456789, 03-77855409, dll)
   - Alamat e-mel
   - Nombor kad kredit

2. Untuk konteks Malaysia:
   - Nama Inggeris: Kenal pasti nama pertama + nama keluarga (contoh: Yap En Chong, Alfred Lee Chee Shing, Jeremy Tan Choo Hau, Dennis Smith)
   - Nama India: Kenal pasti nama dengan corak patronimik (contoh: Raj Kumar a/l Subramaniam, Priya Devi a/l Venkat, Lim Wei Jian)
   - Nama Melayu: Kenal pasti corak bin/binti/anak (contoh: Ahmad bin Ali, Siti binti Hassan, Janting anak Sumping)
    - Nama Cina: Kenal pasti nama penuh dalam aksara Cina (contoh: 王伟, 李娜, 张强, 刘芳, 陈杰, 杨明)
   - Lokasi: Bandar-bandar Malaysia (KUALA LUMPUR, PETALING JAYA, JOHOR BAHRU, dll)
   - Bank: Nama bank Malaysia (Maybank, CIMB, Public Bank, dll)

3. ABAIKAN artefak dokumen ini:
   - MALAYSIA, KAD PENGENALAN, IDENTITY CARD, LELAKI, PEREMPUAN, WARGANEGARA
   - COPY, CONFIDENTIAL, SPECIMEN, SAMPLE
   - Label dan tajuk borang

4. Khas untuk penyata bank:
   - Nama pemegang akaun
   - Nombor akaun (biasanya 10-16 digit)
   - Nombor rujukan transaksi
   - Kod cawangan dan alamat
   - Nombor telefon dan maklum balas

Kembalikan HANYA array JSON dengan format yang tepat ini:
[
  {{"category": "NAMES", "value": "WONG JUN KEAT", "confidence": 0.95}},
  {{"category": "ACCOUNT", "value": "1234567890123456", "confidence": 1.0}},
  {{"category": "PHONE", "value": "03-77855409", "confidence": 0.9}}
]

Teks untuk dianalisis (ketua {chunk_idx + 1}/{len(text_chunks)}):
{chunk}"""

            system_prompt = "Anda adalah pakar pengesanan PII. Kembalikan JSON yang sah sahaja."
            response_text = generate_json(system_prompt, prompt)

            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1

            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                pii_data = json.loads(json_text)

                chunk_results = []
                for item in pii_data:
                    if isinstance(item, dict) and 'category' in item and 'value' in item:
                        category = item['category']
                        value = item['value'].strip()
                        confidence = item.get('confidence', 0.5)
                        
                        if confidence >= LLM_CONFIDENCE_THRESHOLD and value:
                            chunk_results.append((category, value))
                
                all_results.extend(chunk_results)
                print(f"[Ollama] Chunk {chunk_idx + 1}: Found {len(chunk_results)} PII items")
            else:
                print(f"[WARN] Ollama chunk {chunk_idx + 1}: No valid JSON in response")

        except json.JSONDecodeError as e:
            print(f"[WARN] Ollama chunk {chunk_idx + 1}: JSON parsing failed: {e}")
            continue
        except Exception as e:
            print(f"[WARN] Ollama chunk {chunk_idx + 1}: Processing failed: {e}")
            continue

    print(f"[Ollama] Total found across all chunks: {len(all_results)} PII items")
    return all_results


def extract_entities_with_ollama(text: str, enabled_categories: list) -> list:
    """
    Extract PII entities using Ollama with proper entity boundary detection.
    Focuses on extracting COMPLETE entity names including all parts (not partial matches).
    Malaysian context: bin, binti, anak patterns, organization suffixes (Sdn Bhd, Berhad, etc.)
    
    Args:
        text: Text to analyze
        enabled_categories: List of enabled PII categories (NAMES, ORG_NAMES)
    
    Returns:
        List of (label, value) tuples with high-confidence entities
    """
    print(f"[Ollama-ENTITIES] Starting entity extraction with boundary detection...")
    
    if not ollama_enabled:
        print("[Ollama-ENTITIES] Ollama not enabled, returning empty list")
        return []
    
    if not text or len(text.strip()) < 20:
        print("[Ollama-ENTITIES] Text too short, returning empty list")
        return []
    
    if not enabled_categories:
        print("[Ollama-ENTITIES] No categories enabled, returning empty list")
        return []
    
    text_chunks = chunk_text_intelligently(text, max_chunk_size=3000)
    all_results = []
    
    print(f"[Ollama-ENTITIES] Processing {len(text_chunks)} text chunks")
    
    for chunk_idx, chunk in enumerate(text_chunks):
        try:
            categories_parts = []
            if "NAMES" in enabled_categories:
                categories_parts.append("PERSONAL NAMES: Extract COMPLETE names including ALL parts. Examples: 'Ahmad bin Ali', 'WONG JUN KEAT'.")
            if "ORG_NAMES" in enabled_categories:
                categories_parts.append("ORGANIZATION NAMES: Extract COMPLETE names including ALL suffixes (Sdn Bhd, Berhad, Holdings, Ltd, Inc). Examples: 'ABC Holdings Berhad', 'XYZ Sdn Bhd'.")
            
            categories_text = " ".join(categories_parts)
            
            prompt = f"""Extract PII entities from the text. 

{categories_text}

INSTRUCTIONS:
- Extract COMPLETE entity names - NEVER partial matches
- Return only the entity text, don't add explanations
- Include all name/suffix parts

Return ONLY a JSON array with this exact format:
[
  {{"category": "NAMES"|"ORG_NAMES", "value": "COMPLETE ENTITY TEXT", "confidence": 0.95}}
]

Text to analyze (chunk {chunk_idx + 1}/{len(text_chunks)}):
{chunk}"""

            system_prompt = "Return only valid JSON with complete entity names."
            response_text = generate_json(system_prompt, prompt)
            
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                pii_data = json.loads(json_text)
                
                chunk_results = []
                for item in pii_data:
                    if isinstance(item, dict) and 'category' in item and 'value' in item:
                        category = item['category']
                        value = item['value'].strip()
                        confidence = item.get('confidence', 0.5)
                        
                        if category in enabled_categories and confidence >= LLM_CONFIDENCE_THRESHOLD and value:
                            chunk_results.append((category, value))
                
                all_results.extend(chunk_results)
                print(f"[Ollama-ENTITIES] Chunk {chunk_idx + 1}: Found {len(chunk_results)} entities")
            else:
                print(f"[WARN] Ollama-ENTITIES chunk {chunk_idx + 1}: No valid JSON in response")
                
        except json.JSONDecodeError as e:
            print(f"[WARN] Ollama-ENTITIES chunk {chunk_idx + 1}: JSON parsing failed: {e}")
            continue
        except Exception as e:
            print(f"[WARN] Ollama-ENTITIES chunk {chunk_idx + 1}: Processing failed: {e}")
            continue
    
    print(f"[Ollama-ENTITIES] Total found across all chunks: {len(all_results)} entities")
    return all_results


def detect_missed_pii_with_llm(text: str, detected_pii: List[Tuple[str, str]], enabled_categories: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """
    Secondary LLM scan to find PII that was missed by initial detection
    Uses context-aware prompting to identify subtle/indirect PII
    
    Args:
        text: Original full text
        detected_pii: PII already detected by initial scan
        enabled_categories: Categories to check for missed items
        
    Returns:
        List of newly detected PII items
    """
    if not text or len(text.strip()) < LLM_MIN_TEXT_LENGTH:
        print("[LLM-MISSED] Skipping missed detection (text too short or empty)")
        return []
    
    if not ollama_enabled:
        print("[LLM-MISSED] Skipping missed detection (Ollama not available)")
        return []
    
    if not detected_pii:
        print("[LLM-MISSED] No detected PII to compare against")
        return []
    
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())
    
    detected_values = {val.lower() for _, val in detected_pii}
    
    print(f"[LLM-MISSED] Scanning for missed PII in {len(text)} chars, comparing against {len(detected_values)} detected items")
    
    try:
        text_chunks = chunk_text_intelligently(text, max_chunk_size=2500)
        missed_items = []
        
        for chunk_idx, chunk in enumerate(text_chunks):
            try:
                categories_desc = {
                    "NAMES": "Malaysian personal names including:\n"
                            "  - English names: First + Last names (Yap En Chong, Alfred Lee)\n"
                            "  - Chinese names: 2-4 character Chinese characters (王伟, 李娜)\n"
                            "  - Indian names: Patronymic patterns (Raj Kumar a/l Subramaniam)\n"
                            "  - Malay names: bin/binti/anak patterns (Ahmad bin Ali, Siti binti Hassan)",
                    "ACCOUNT": "Bank account numbers (10-16 digits)",
                    "PHONE": "Malaysian phone numbers (+60123456789, 03-77855409)",
                    "IC": "Malaysian IC numbers (123456-78-9012)",
                    "EMAIL": "Email addresses",
                    "CREDIT_CARD": "Credit card numbers",
                }
                
                enabled_desc = [f"- {cat}: {categories_desc.get(cat, cat)}" for cat in enabled_categories if cat in categories_desc]
                categories_text = "\n".join(enabled_desc)
                
                detected_text = "\n".join([f"- {val}" for val in list(detected_values)[:10]])
                if len(detected_values) > 10:
                    detected_text += f"\n... and {len(detected_values) - 10} more"
                
                prompt = f"""You are a PII detection specialist reviewing a document for missed sensitive information.

ORIGINAL TEXT (chunk {chunk_idx + 1}/{len(text_chunks)}):
{chunk}

PREVIOUSLY DETECTED PII (DO NOT DETECT THESE AGAIN):
{detected_text}

YOUR TASK:
Scan the text above for ANY PII that matches these categories but was NOT in the detected list:
{categories_text}

CRITICAL INSTRUCTIONS:
1. Find names that weren't caught:
   - Full names with multiple parts
   - Names with titles (Dr., Mr., Ms.)
   - Names with apostrophes or hyphens
   - Names followed by identifying info (IC, phone, account)
   - Chinese names in any context (even embedded in other text)
   - Names that are split across lines or have unusual spacing

2. Find contact info:
   - Phone numbers with any separators (+, -, spaces)
   - Email addresses with subaddresses (user+tag@gmail.com)
   - Account numbers embedded in sentences

3. Find IC numbers:
   - Any 12-digit sequences that could be IC numbers
   - IC numbers with unconventional separators

4. DO NOT return general information, amounts, dates (unless birth dates), or generic terms

Return ONLY a JSON array of NEW items that should be masked:
[
  {{"category": "NAMES"|"ACCOUNT"|"PHONE"|"IC"|"EMAIL"|"CREDIT_CARD", "value": "DETECTED VALUE", "confidence": 0.8, "reason": "why this is PII"}}
]

If no new PII found, return an empty array: []"""
                
                system_prompt = "Anda adalah pakar pengesanan PII. Kembalikan JSON yang sah sahaja."
                response_text = generate_json(system_prompt, prompt)
                
                json_start = response_text.find('[')
                json_end = response_text.rfind(']') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_text = response_text[json_start:json_end]
                    try:
                        missed_data = json.loads(json_text)
                        
                        for item in missed_data:
                            if isinstance(item, dict) and 'category' in item and 'value' in item:
                                category = item['category']
                                value = item['value'].strip()
                                confidence = item.get('confidence', 0.5)
                                
                                if value.lower() not in detected_values:
                                    if confidence >= LLM_CONFIDENCE_THRESHOLD and value:
                                        missed_items.append((category, value))
                                        print(f"[LLM-MISSED] Found missed PII: {category} = '{value}' (confidence: {confidence})")
                                    
                    except json.JSONDecodeError:
                        pass
                        
            except Exception as e:
                print(f"[LLM-MISSED] Error in chunk {chunk_idx + 1}: {e}")
                continue
        
        print(f"[LLM-MISSED] Total missed PII found: {len(missed_items)}")
        return missed_items
        
    except Exception as e:
        print(f"[LLM-MISSED] Failed to scan for missed PII: {e}")
        return []


# ✅ Main function: Extract all PII (Ollama-only detection)
def extract_all_pii(text, enabled_categories=None):
    """
    Extract PII using Ollama LLM as the sole detection method.

    Args:
        text: Text to analyze
        enabled_categories: A list of selective PII categories to enable, such as ['NAMES', 'ORG_NAMES']
                If None, all categories are enabled.

    Returns:
        list: PII entity list [(label, value), ...]
    """
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())

    if not ollama_enabled:
        load_ollama_client()

    print(f"[INFO] PII detection started - Enabled categories: {enabled_categories}")
    print(f"[INFO] Detection method: Ollama LLM only")

    # --- 1. Broad PII detection with Ollama (IC, phone, email, names, accounts, etc.) ---
    ollama_broad_results = []
    if len(text.strip()) >= LLM_MIN_TEXT_LENGTH:
        print("[INFO] Starting Ollama broad PII detection...")
        ollama_broad_results = extract_pii_with_ollama(text, enabled_categories)
        print(f"[Ollama-BROAD] Found {len(ollama_broad_results)} PII items")
    else:
        print(f"[INFO] Ollama broad detection skipped (text too short: {len(text.strip())} chars < {LLM_MIN_TEXT_LENGTH})")

    # --- 2. Focused entity extraction for NAMES/ORG_NAMES ---
    entity_categories = [c for c in enabled_categories if c in ("NAMES", "ORG_NAMES")]
    ollama_entity_results = []
    if entity_categories and len(text.strip()) >= LLM_MIN_TEXT_LENGTH:
        print("[INFO] Starting Ollama entity extraction with boundary detection...")
        ollama_entity_results = extract_entities_with_ollama(text, entity_categories)
        print(f"[Ollama-ENTITIES] Found {len(ollama_entity_results)} entities")

    # --- 3. Merge all Ollama results ---
    all_results = ollama_broad_results + ollama_entity_results
    print(f"[MERGE] Total raw results: {len(all_results)}")
    
    # --- 3.5. Regex fallback for critical PII types ---
    if len(text.strip()) >= 20:
        print("[INFO] Running regex fallback for critical PII types...")
        regex_results = extract_pii_with_regex(text)
        if regex_results:
            all_results.extend(regex_results)
            print(f"[REGEX] Added {len(regex_results)} PII items from regex fallback")

    # --- 4. Deduplication + Filtering Non-sensitive Words ---
    seen = set()
    stage1_filtered = []
    for label, value in all_results:
        clean_val = value.strip().lower()
        if not clean_val or clean_val in IGNORE_WORDS:
            continue
        if clean_val not in seen:
            seen.add(clean_val)
            stage1_filtered.append((label, value.strip()))

    print(f"[STAGE-1] After dedup/filtering: {len(stage1_filtered)} PII candidates")

    # Deduplicate: for overlapping PII matches, keep only the longest one
    print("[INFO] Deduplicating PII by selecting longest match for overlapping patterns...")
    deduped_results = []
    used_values = set()
    
    sorted_results = sorted(stage1_filtered, key=lambda x: len(x[1]), reverse=True)
    
    for label, value in sorted_results:
        value_clean = value.strip()
        should_skip = False
        for used in used_values:
            if value_clean.lower() in used.lower():
                should_skip = True
                print(f"[DEDUP] Skipping '{value}' (contained in '{used}')")
                break
        
        if not should_skip:
            used_values.add(value_clean.lower())
            deduped_results.append((label, value))
            print(f"[DEDUP] Keeping '{value}' (label: {label})")

    print(f"[DEDUP] After deduplication: {len(deduped_results)} PII candidates")
    stage1_filtered = deduped_results
    
    # --- 5. Stage 2: LLM Missed Items Detection ---
    if len(stage1_filtered) > 0 and len(text.strip()) >= LLM_MIN_TEXT_LENGTH:
        print(f"[INFO] Stage 2: Detecting missed PII items with LLM ({len(stage1_filtered)} already found)...")
        missed_items = detect_missed_pii_with_llm(text, stage1_filtered, enabled_categories)
        
        if missed_items:
            print(f"[STAGE-2] LLM missed detection: Found {len(missed_items)} additional PII items")
            stage1_filtered.extend(missed_items)
            print(f"[STAGE-2] Total PII items after missed detection: {len(stage1_filtered)}")
        else:
            print("[STAGE-2] No missed PII items detected")
    else:
        print("[INFO] Stage 2: Skipping missed detection (no candidates or text too short)")

    # --- 6. Final validation and deduplication ---
    print("[INFO] Final validation and deduplication of all PII items...")
    seen = set()
    final_results = []
    for label, value in stage1_filtered:
        clean_val = value.strip().lower()
        if not clean_val or clean_val in IGNORE_WORDS:
            continue
        if clean_val not in seen:
            seen.add(clean_val)
            final_results.append((label, value.strip()))
    
    print(f"[FINAL] Finally detected {len(final_results)} PII items")
    return final_results
