# OCR/pii_main.py
import re
import os
import json
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from app.resources.dictionaries import NAMES, ORG_NAMES

from app.config.ollama_config import OLLAMA_ENABLED
from app.services.ollama_client import generate_json
ollama_enabled = OLLAMA_ENABLED
ollama_client = None

# === Delay loading models ===
ner_pipeline = None
model_loaded = False

def load_model():
    """Lazy load the ML model only when needed"""
    global ner_pipeline, model_loaded
    if not model_loaded:
        try:
            print("🔄 Loading ML model for PII detection...")
            from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

            model_name = "dslim/bert-base-NER"
            tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
            model = AutoModelForTokenClassification.from_pretrained(model_name)

            # Create pipeline with simple aggregation for token merging
            ner_pipeline = pipeline(
                task="ner",
                model=model,
                tokenizer=tokenizer,
                framework="pt",
                aggregation_strategy=None
            )
            model_loaded = True
            print("✅ ML model loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load ML model: {e}")
            # Fallback to regex-only detection
            model_loaded = False

# === Gemini API Integration ===

# === DeepSeek API Integration ===
deepseek_enabled = False
deepseek_client = None

def load_deepseek_client():
    """Initialize DeepSeek client if API key is available"""
    global deepseek_client, deepseek_enabled
    try:
        from app.config.deepseek_adapter import DeepSeekClient
    except Exception as e:
        print(f"[WARN] DeepSeek adapter not available: {e}")
        print("[INFO] DeepSeek PII detection disabled - using Presidio + NER only")
        deepseek_enabled = False
        return False

    try:
        deepseek_client = DeepSeekClient()
        deepseek_enabled = True
        print("✅ DeepSeek API client initialized successfully")
        if deepseek_client:
            is_valid, msg = deepseek_client.test_connection()
            print(f"[INFO] DeepSeek API: {msg}")
        return True
    except Exception as e:
        print(f"[WARN] Failed to initialize DeepSeek client: {e}")
        print("[INFO] DeepSeek PII detection disabled - using Presidio + NER only")
        deepseek_enabled = False
        return False

gemini_enabled = False
gemini_client = None

# === DeepSeek API Integration ===
deepseek_enabled = False
deepseek_client = None

def load_gemini_client():
    """Initialize Gemini client if API key is available"""
    global gemini_client, gemini_enabled
    try:
        from app.config.gemini_adapter import GeminiClient
    except Exception as e:
        print(f"[WARN] Gemini adapter not available: {e}")
        print("[INFO] Gemini PII detection disabled - using Presidio + NER only")
        gemini_enabled = False
        return False

    try:
        gemini_client = GeminiClient()
        gemini_enabled = True
        print("✅ Gemini API client initialized successfully")
        return True
    except Exception as e:
        print(f"[WARN] Failed to initialize Gemini client: {e}")
        print("[INFO] Gemini PII detection disabled - using Presidio + NER only")
        gemini_enabled = False
        return False

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

def extract_pii_with_gemini(text: str, enabled_categories: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """
    Use Gemini to identify PII in text with focus on Malaysian context and intelligent chunking

    Args:
        text: Text to analyze
        enabled_categories: List of enabled PII categories

    Returns:
        List of (label, value) tuples
    """
    if not gemini_enabled or not gemini_client:
        return []

    if not text or len(text.strip()) < 20:  # Minimum meaningful text length
        return []

    # Default to all categories if none specified
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())

    # Chunk text if it's too long for the LLM
    text_chunks = chunk_text_intelligently(text, max_chunk_size=3000)
    all_results = []

    print(f"[Gemini] Processing {len(text_chunks)} text chunks")

    for chunk_idx, chunk in enumerate(text_chunks):
        try:
            # Create enhanced category-specific prompt for financial documents
            categories_desc = {
                "NAMES": "Personal names (Malaysian names like 'Ahmad bin Ali', 'WONG JUN KEAT', 'Ramba anak Sumping')",
            }

            enabled_desc = [f"- {cat}: {categories_desc.get(cat, cat)}" for cat in enabled_categories if cat in categories_desc]
            categories_text = "\n".join(enabled_desc)

            # Enhanced prompt for better financial document detection
            prompt = f"""You are a PII detection expert specializing in Malaysian financial and identity documents.

Analyze the following text and identify PII entities. Focus on these categories:
{categories_text}

CRITICAL DETECTION RULES:
1. ALWAYS detect these sensitive items regardless of category settings:
   - IC numbers (format: 123456-78-9012 or similar)
   - Account numbers (long digit sequences: 1234567890123456)
   - Phone numbers (+60123456789, 03-77855409, etc.)
   - Email addresses
   - Credit card numbers

2. For Malaysian context:
   - Names: Look for Malaysian naming patterns (bin, binti, anak)
    - English names: Detect first + last names (e.g., Yap En Chong, Alfred Lee Chee Shing, Jeremy Tan Choo Hau, Dennis Smith)
    - Indian names: Detect names with patronymic patterns (e.g., Raj Kumar a/l Subramaniam, Priya Devi a/l Venkat, Lim Wei Jian)
    - Malay names: Detect bin/binti/anak patterns (e.g., Ahmad bin Ali, Siti binti Hassan, Janting anak Sumping)
    - Chinese names: Detect full names in Chinese characters (e.g., 王伟, 李娜, 张强, 刘芳, 陈杰, 杨明)
   - Locations: Malaysian cities (KUALA LUMPUR, PETALING JAYA, JOHOR BAHRU, etc.)
   - Banks: Malaysian bank names (Maybank, CIMB, Public Bank, etc.)

3. IGNORE these document artifacts:
   - MALAYSIA, KAD PENGENALAN, IDENTITY CARD, LELAKI, PEREMPUAN, WARGANEGARA
   - COPY, CONFIDENTIAL, SPECIMEN, SAMPLE
   - Form labels and headers

4. For bank statements specifically:
   - Account holder names
   - Account numbers (typically 10-16 digits)
   - Transaction reference numbers
   - Branch codes and addresses
   - Phone numbers and contact details

Return ONLY a JSON array with this exact format:
[
  {{"category": "NAMES", "value": "WONG JUN KEAT", "confidence": 0.95}},
  {{"category": "ACCOUNT", "value": "1234567890123456", "confidence": 1.0}},
  {{"category": "PHONE", "value": "03-77855409", "confidence": 0.9}}
]

Text to analyze (chunk {chunk_idx + 1}/{len(text_chunks)}):
{chunk}"""

            # Call Gemini API via adapter
            system_prompt = "You are a PII detection expert. Return only valid JSON."
            response_text = gemini_client.generate_json(system_prompt, prompt)

            # Extract JSON from response (handle cases where GPT adds extra text)
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1

            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                pii_data = json.loads(json_text)

                # Convert to our format and filter by confidence
                chunk_results = []
                for item in pii_data:
                    if isinstance(item, dict) and 'category' in item and 'value' in item:
                        category = item['category']
                        value = item['value'].strip()
                        confidence = item.get('confidence', 0.8)

                        # Only include high-confidence results
                        if confidence >= 0.7 and value:
                            chunk_results.append((category, value))

                all_results.extend(chunk_results)
                print(f"[Gemini] Chunk {chunk_idx + 1}: Found {len(chunk_results)} PII items")
            else:
                print(f"[WARN] Gemini chunk {chunk_idx + 1}: No valid JSON in response")

        except json.JSONDecodeError as e:
            print(f"[WARN] Gemini chunk {chunk_idx + 1}: JSON parsing failed: {e}")
            continue
        except Exception as e:
            print(f"[WARN] Gemini chunk {chunk_idx + 1}: Processing failed: {e}")
            continue

    print(f"[Gemini] Total found across all chunks: {len(all_results)} PII items")
    return all_results
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

    text_chunks = chunk_text_intelligently(text, max_chunk_size=3000)
    all_results = []

    print(f"[Ollama] Processing {len(text_chunks)} text chunks")

    for chunk_idx, chunk in enumerate(text_chunks):
        try:
            categories_desc = {
                "NAMES": "Personal names (Malaysian names like 'Ahmad bin Ali', 'WONG JUN KEAT', 'Ramba anak Sumping')",
                "RELIGIONS": "Religious affiliations",
                "TRANSACTION NAME": "Transaction descriptions and references"
            }

            enabled_desc = [f"- {cat}: {categories_desc.get(cat, cat)}" for cat in enabled_categories if cat in categories_desc]
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
                        confidence = item.get('confidence', 0.8)

                        if confidence >= 0.7 and value:
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


def validate_pii_with_gemini_context(text: str, candidate_pii: List[Tuple[str, str]], enabled_categories: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """
    Stage 2: Use Gemini to validate and filter PII candidates based on context

    Args:
        text: Original full text for context
        candidate_pii: List of (label, value) tuples from Stage 1 detection
        enabled_categories: List of enabled PII categories

    Returns:
        Filtered list of (label, value) tuples that are truly PII
    """
    if not gemini_enabled or not gemini_client:
        print("[INFO] Gemini contextual validation skipped (not enabled)")
        return candidate_pii

    if not candidate_pii:
        print("[INFO] No PII candidates to validate")
        return []

    if len(text.strip()) < 50:
        print("[INFO] Text too short for contextual validation")
        return candidate_pii

    print(f"[Gemini-VALIDATION] Starting contextual validation of {len(candidate_pii)} candidates")

    try:
    # Prepare candidate list for Gemini analysis
        candidates_text = "\n".join([f"- {label}: '{value}'" for label, value in candidate_pii])

        # Create context-aware validation prompt
        prompt = f"""You are a PII validation expert specializing in Malaysian documents.

I have detected potential PII entities in a document, but need your help to filter out false positives and validate which items are truly sensitive personal information that should be masked.

ORIGINAL DOCUMENT CONTEXT:
{text[:2000]}{"..." if len(text) > 2000 else ""}

DETECTED PII CANDIDATES:
{candidates_text}

VALIDATION RULES:
1. **ALWAYS KEEP as PII (regardless of context)**:
   - IC numbers (123456-78-9012 format)
   - Phone numbers (+60123456789, 03-77855409)
   - Email addresses
   - Credit card numbers
   - Bank account numbers (long digit sequences)

2. **EVALUATE CONTEXTUALLY**:
   - Personal names: Keep if referring to individuals (account holders, customers)
   - Organization names: Remove if just company headers/logos (PUBLIC BANK, MAYBANK)
   - Locations: Keep if personal addresses, remove if just branch locations
   - Amounts: Remove if transaction amounts, keep if account numbers
   - Dates: Remove if transaction dates, keep if birth dates

3. **MALAYSIAN CONTEXT**:
   - Names like "WONG JUN KEAT", "Ahmad bin Ali" are personal names → KEEP
   - Bank names like "PUBLIC BANK", "MAYBANK" in headers → REMOVE
   - Cities like "KUALA LUMPUR" in addresses → KEEP, in branch info → REMOVE
   - "MALAYSIA" as country name → REMOVE

4. **DOCUMENT ARTIFACTS TO REMOVE**:
   - Bank names in headers/letterheads
   - Branch names and codes
   - Transaction categories/descriptions
   - Currency symbols and amounts
   - Form labels and instructions

Return ONLY a JSON array of items that should be KEPT (truly sensitive PII):
[
  {{"label": "NAMES", "value": "WONG JUN KEAT", "reason": "Personal account holder name"}},
  {{"label": "IC", "value": "123456-78-9012", "reason": "Personal identification number"}},
  {{"label": "PHONE", "value": "03-77855409", "reason": "Personal contact number"}}
]

Focus on protecting individual privacy while removing corporate/institutional information."""

        # Call Gemini for validation
        system_prompt = (
            "You are a PII validation expert. Return only valid JSON with items that truly need privacy protection."
        )
        response_text = gemini_client.generate_json(system_prompt, prompt)
        # Extract JSON from response
        json_start = response_text.find('[')
        json_end = response_text.rfind(']') + 1
        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            validated_data = json.loads(json_text)
            # Convert back to our format
            validated_results = []
            for item in validated_data:
                if isinstance(item, dict) and 'label' in item and 'value' in item:
                    label = item['label']
                    value = item['value'].strip()
                    reason = item.get('reason', 'Validated by Gemini')
                    if value:
                        validated_results.append((label, value))
                        print(f"[Gemini-VALIDATION] KEEP: {label} = '{value}' ({reason})")

            # Show what was filtered out
            original_values = {value.lower() for _, value in candidate_pii}
            validated_values = {value.lower() for _, value in validated_results}
            filtered_out = original_values - validated_values

            if filtered_out:
                print(f"[Gemini-VALIDATION] FILTERED OUT: {len(filtered_out)} items")
                for value in list(filtered_out)[:5]:  # Show first 5
                    print(f"[Gemini-VALIDATION] REMOVED: '{value}' (document artifact)")
                if len(filtered_out) > 5:
                    print(f"[Gemini-VALIDATION] ... and {len(filtered_out) - 5} more")

            print(f"[Gemini-VALIDATION] Final result: {len(validated_results)}/{len(candidate_pii)} candidates validated as true PII")
            return validated_results
        else:
            print("[WARN] Gemini validation: No valid JSON in response")
            return candidate_pii

    except json.JSONDecodeError as e:
        print(f"[WARN] Gemini validation JSON parsing failed: {e}")
        return candidate_pii
    except Exception as e:
        print(f"[WARN] Gemini validation failed: {e}")
        return candidate_pii

def combine_pii_results(presidio_results: List[Tuple[str, str]],
                       ner_results: List[Tuple[str, str]],
                       gemini_results: List[Tuple[str, str]],
                       ollama_results: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Combine results from multiple PII detection methods using enhanced consensus mechanism
    Args:
        presidio_results: Results from Presidio/regex detection
        ner_results: Results from NER model (may be empty if failed)
        gemini_results: Results from Gemini
        ollama_results: Results from Ollama
    Returns:
        Combined and deduplicated results
    """
    # Track which methods provided results
    methods_used = []
    if presidio_results:
        methods_used.append("Presidio/Regex")
    if ner_results:
        methods_used.append("NER")
    if gemini_results:
        methods_used.append("Gemini")
    if ollama_results:
        methods_used.append("Ollama")
    print(f"[CONSENSUS] Active detection methods: {', '.join(methods_used)}")
    # Combine all results
    all_results = presidio_results + ner_results + gemini_results + ollama_results
    if not all_results:
        print("[CONSENSUS] No PII detected by any method")
        return []
    # Group by normalized value for deduplication
    value_groups = {}
    for label, value in all_results:
        normalized_value = value.strip().lower()
        if normalized_value not in value_groups:
            value_groups[normalized_value] = []
        value_groups[normalized_value].append((label, value))
    # Apply enhanced consensus logic
    final_results = []
    for normalized_value, candidates in value_groups.items():
        if len(candidates) == 1:
            # Single detection - include it
            label, value = candidates[0]
            final_results.append((label, value))
        else:
            # Multiple detections - use consensus with priority
            # Priority: Gemini > Presidio/Regex > NER for conflicting labels
            label_votes = {}
            label_sources = {}
            for label, value in candidates:
                if label not in label_votes:
                    label_votes[label] = 0
                    label_sources[label] = []
                label_votes[label] += 1
                # Determine source method (approximate)
                if (label, value) in ollama_results:
                    label_sources[label].append("Ollama")
                elif (label, value) in gemini_results:
                    label_sources[label].append("Gemini")
                elif (label, value) in presidio_results:
                    label_sources[label].append("Presidio")
                else:
                    label_sources[label].append("NER")
            # Choose best label with priority weighting
            best_label = None
            best_score = 0
            for label, votes in label_votes.items():
                score = votes
                # Boost score based on source reliability
                if "Gemini" in label_sources[label]:
                    score += 2  # Gemini gets priority for context awareness
                if "Ollama" in label_sources[label]:
                    score += 1
                if "Presidio" in label_sources[label]:
                    score += 1  # Regex patterns are reliable
                if score > best_score:
                    best_score = score
                    best_label = label
            # Get the best value (prefer original case)
            best_value = next(value for label, value in candidates if label == best_label)
            final_results.append((best_label, best_value))

    print(f"[CONSENSUS] Combined {len(all_results)} detections into {len(final_results)} final results")
    return final_results

# === General ignored words (non-sensitive, no encryption required) ===
IGNORE_WORDS = {
    "malaysia", "mykad", "identity", "card", "kad", "pengenalan",
    "warganegara", "lelaki", "perempuan", "bujang", "kawin",
    "lel", "per", "male", "female", "citizen", "not citizen"
}

# === Enhanced regular expression extractor ===
def extract_ic(text):
    """Extract Malaysian Identity Card Number"""
    patterns = [
        r"\b\d{6}-\d{2}-\d{4}\b", 
        r"\b\d{12}\b",            
        r"\b\d{6}\s\d{2}\s\d{4}\b"
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))

    # Verify IC number format
    validated_matches = []
    for match in matches:
        clean_ic = re.sub(r'[-\s]', '', match)
        if len(clean_ic) == 12 and validate_malaysian_ic(clean_ic):
            validated_matches.append(match)

    return validated_matches

def extract_email(text):
    """Extract email addresses"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)

def extract_dob(text):
    """Extract date of birth"""
    patterns = [
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",      # DD/MM/YYYY or D/M/YYYY
        r"\b\d{1,2}-\d{1,2}-\d{4}\b",      # DD-MM-YYYY
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",      # YYYY-MM-DD
        r"\b\d{1,2}\s+\w+\s+\d{4}\b",     # DD Month YYYY
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    return matches

def extract_bank_account(text):
    """Retrieve bank account number"""
    patterns = [
        r"\b\d{10,16}\b",                 
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4,8}\b",
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        # Filter out matches that might be phone numbers or other numbers
        for match in found:
            clean_num = re.sub(r'[-\s]', '', match)
            if 10 <= len(clean_num) <= 16 and not is_phone_number(clean_num):
                matches.append(match)
    return matches

def extract_phone(text):
    """Extract phone number (Malaysian format)"""
    patterns = [
        r'\+60\d{1,2}[-\s]?\d{7,8}',       
        r'\b01\d[-\s]?\d{7,8}\b',          
        r'\b03[-\s]?\d{8}\b',              
        r'\b0[4-9]\d[-\s]?\d{7}\b',        
        r'\b\d{3}[-\s]?\d{7,8}\b',         
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for match in found:
            if validate_phone_number(match):
                matches.append(match)
    return matches

def extract_money(text):
    pattern = r'\b(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?\b'
    
    raw_matches = re.findall(pattern, text)
    filtered_matches = []
    seen = set()

    for match in raw_matches:
        try:
            normalized = match.replace(',', '')
            num = float(normalized)
            if 0.01 <= num <= 10_000_000 and match not in seen:
                filtered_matches.append(match)
                seen.add(match)
        except ValueError:
            continue

    return filtered_matches

def extract_gender(text):
    return re.findall(r'\b(LELAKI|PEREMPUAN|MALE|FEMALE)\b', text, re.I)

def extract_nationality(text):
    return re.findall(r'\b(WARGANEGARA|WARGA ASING|CITIZEN|NON-CITIZEN)\b', text, re.I)

def extract_passport(text):
    # Match passport number format: 1 letter + 7 numbers, or similar format
    patterns = [
        r'\b[A-Z]\d{7,8}\b',      # H12345678 or H1234567
        r'\b[A-Z]{1,2}\d{6,7}\b', # HK1234567 or A1234567
        r'\b\d{8,9}[A-Z]\b'       # 12345678A
    ]
    
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    
    return matches

def extract_credit_card(text):
    """Extract credit card numbers"""
    patterns = [
        r"\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",      # Visa
        r"\b5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", # Mastercard
        r"\b3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5}\b",             # American Express
        r"\b6(?:011|5\d{2})[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", # Discover
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for match in found:
            clean_cc = re.sub(r'[\s-]', '', match)
            if validate_credit_card(clean_cc):
                matches.append(match)
    return matches


def extract_chinese_names(text):
    """Extract Chinese character names (2-4 characters)"""
    patterns = [
        r'[\u4e00-\u9fff]{2,4}',
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for match in found:
            if validate_chinese_name(match):
                matches.append(match)
    return matches

def validate_chinese_name(name):
    """Validate Chinese name format (2-4 Chinese characters)"""
    if len(name) < 2 or len(name) > 4:
        return False
    for char in name:
        if not (0x4e00 <= ord(char) <= 0x9fff):
            return False
    return True

def extract_malaysian_address(text):
    """Extract Malaysia Address"""
    patterns = [
        r"\b\d+[A-Za-z]?,?\s+[A-Za-z\s]+,\s*\d{5}\s+[A-Za-z\s]+\b",
        r"\b[A-Za-z\s]+,\s*\d{5}\s+[A-Za-z\s]+,\s*[A-Za-z\s]+\b",
        r"\bNo\.?\s*\d+[A-Za-z]?,?\s+[A-Za-z\s]+,\s*\d{5}\b",   
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    return matches

def extract_vehicle_registration(text):
    """Extract license plate number"""
    patterns = [
        r"\b[A-Z]{1,3}\s?\d{1,4}\s?[A-Z]?\b",
        r"\b[A-Z]{2}\d{4}[A-Z]\b",            
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for match in found:
            if validate_vehicle_plate(match):
                matches.append(match)
    return matches

# === Validation Function ===
def validate_malaysian_ic(ic_number: str) -> bool:
    if len(ic_number) != 12 or not ic_number.isdigit():
        return False

    try:
        # Verify that the date of birth is legitimate
        year = int(ic_number[:2])
        month = int(ic_number[2:4])
        day = int(ic_number[4:6])
        full_year = 2000 + year if year <= 30 else 1900 + year
        datetime(full_year, month, day)
    except ValueError:
        return False
    return True

def validate_credit_card(cc_number):
    """Validating credit card numbers using the Luhn algorithm"""
    def luhn_checksum(card_num):
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_num)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10
    return luhn_checksum(cc_number) == 0

def validate_phone_number(phone):
    """Validate phone number format"""
    clean_phone = re.sub(r'[\s+\-]', '', phone)

    # Malaysia Mobile Number Verification
    if clean_phone.startswith('60'):
        clean_phone = clean_phone[2:]

    # mobile patterns
    mobile_patterns = [
        r'^01[0-9]\d{7,8}$',
        r'^03\d{8}$',      
        r'^0[4-9]\d{7,8}$',
    ]

    for pattern in mobile_patterns:
        if re.match(pattern, clean_phone):
            return True

    return False

def validate_vehicle_plate(plate):
    """Verify license plate number format"""
    clean_plate = re.sub(r'\s', '', plate.upper())

    # Malaysian license plate format
    patterns = [
        r'^[A-Z]{1,3}\d{1,4}[A-Z]?$',\
        r'^[A-Z]{2}\d{4}[A-Z]$',       
    ]

    for pattern in patterns:
        if re.match(pattern, clean_plate):
            return True

    return False

def is_phone_number(number_str):
    """Check if a numeric string is possibly a phone number"""
    clean_num = re.sub(r'[\s-]', '', number_str)
    return len(clean_num) in [10, 11, 12] and (clean_num.startswith('01') or clean_num.startswith('03'))

# === Malaysia location whitelist (to prevent accidental merging) ===
def extract_from_dictionaries(text, enabled_categories=None):
    """
    Extracts PII from a dictionary, supporting selective category filtering

    Args:
        text: The text to be analyzed
        enabled_categories: A list of enabled selective PII categories

    Returns:
        list: [(label, value), ...] 
    """
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())

    print(f"[DEBUG] 字典提取，启用类别: {enabled_categories}")
    print("[DEBUG] 原始文本：", text)

    results = []
    text_lower = text.lower()

    # 1. Full name matching (highest priority)
    if "NAMES" in enabled_categories:
        for name in NAMES:
            if name.lower() in text_lower:
                # Make sure it matches the entire word, not a partial one
                pattern = r'\b' + re.escape(name.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("NAMES", name))
                    print(f"[DEBUG] Find full name: {name}")

    # 2. Full organization name matching
    if "ORG_NAMES" in enabled_categories:
        for org in ORG_NAMES:
            if org.lower() in text_lower:
                pattern = r'\b' + re.escape(org.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("ORG_NAMES", org))
                    print(f"[DEBUG] Find the organization name: {org}")

    # 3. Race Matching
    print(f"[DEBUG] Dictionary matching results: Found {len(results)} PII items")
    for label, value in results:
        print(f"[DEBUG]   - {label}: {value}")
    return results

# ✅ Optional PII Category Definitions
SELECTABLE_PII_CATEGORIES = {
    "NAMES": "Personal names and identities",
    "ORG_NAMES": "Company and organization names"
}

# ✅ Non-selective PII categories (always masked)
NON_SELECTABLE_PII_CATEGORIES = {
    "IC": "Malaysian IC numbers",
    "Email": "Email addresses",
    "DOB": "Date of birth",
    "Bank Account": "Bank account numbers",
    "Passport": "Passport numbers",
    "Phone": "Phone numbers",
    "Money": "Financial amounts",
    "Credit Card": "Credit card numbers",
    "Address": "Street addresses",
    "Vehicle Registration": "Vehicle registration numbers"
}

# ✅ Main function: Extract all PII (with selective filtering + Gemini enhancement)
def extract_all_pii(text, enabled_categories=None):
    """
    Extract PII, support selective category filtering, and integrate Gemini enhanced detection

    Args:
        text: Text to analyze
        enabled_categories: A list of selective PII categories to enable, such as ['NAMES', 'ORG_NAMES']
                If None, all categories are enabled.

    Returns:
        list: PII实体列表 [(label, value), ...]
    """
    # If not specified, all optional categories are enabled by default.
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())

    # Initialize Gemini client if not already done
    if not gemini_enabled:
        load_gemini_client()

    # Initialize Ollama client if not already done
    if not ollama_enabled:
        load_ollama_client()

    print(f"[INFO] PII detection started - Enabled categories: {enabled_categories}")
    print(f"[INFO] Detection methods: NER + Regex + Dictionary + {'Gemini' if gemini_enabled else 'No Gemini'} + {'Ollama' if ollama_enabled else 'No Ollama'}")

    presidio_regex_results = []
    ner_results = []
    gemini_results = []
    ollama_results = []

    # --- 1. NER extraction (fine-grained) with token limit handling ---
    try:
        # Load model if not already loaded
        if not model_loaded:
            load_model()

        if ner_pipeline is not None:
            # Handle token limit by chunking text for NER
            text_length = len(text.split())
            max_tokens = 300  # Conservative limit for NER model (model limit is ~512 tokens)

            if text_length > max_tokens:
                print(f"[NER] Text too long ({text_length} tokens), chunking for NER processing...")
                # Split text into smaller chunks for NER
                words = text.split()
                chunk_size = max_tokens
                ner_raw_results = []

                for i in range(0, len(words), chunk_size):
                    chunk_words = words[i:i + chunk_size]
                    chunk_text = " ".join(chunk_words)

                    # Additional safety check - if chunk is still too long, skip it
                    if len(chunk_text.split()) > max_tokens:
                        print(f"[WARN] NER chunk {i//chunk_size + 1} still too long, skipping")
                        continue

                    try:
                        chunk_results = ner_pipeline(chunk_text)
                        ner_raw_results.extend(chunk_results)
                        print(f"[NER] Processed chunk {i//chunk_size + 1}: {len(chunk_results)} entities")
                    except Exception as chunk_e:
                        print(f"[WARN] NER chunk {i//chunk_size + 1} failed: {chunk_e}")
                        continue
            else:
                ner_raw_results = ner_pipeline(text)
        else:
            print("[WARN] NER model not available, using regex-only detection")
            ner_raw_results = []
        tokens = []
        for ent in ner_raw_results:
            word = ent["word"]
            entity = ent["entity"].replace("B-", "").replace("I-", "")
            # Determine whether it is the beginning of a new word
            is_new_word = word.startswith("▁") or (not word.startswith("##") and not word.startswith("▁"))
            clean_word = word.replace("##", "").replace("▁", "")
            tokens.append({
                "word": clean_word,
                "entity": entity,
                "is_new_word": is_new_word
            })

        current_word = ""
        current_label = ""

        for tok in tokens:
            # If it is a new word, end the current word
            if current_label and tok["is_new_word"]:
                if current_word:
                    ner_results.append((current_label, current_word))
                current_word = tok["word"]
                current_label = tok["entity"]
            # If it is a continuation (starting with ## or ), and the entity types are the same, then concatenate
            elif current_label == tok["entity"]:
                current_word += tok["word"]
            # Different types, end the old one first, then start the new one
            else:
                if current_word:
                    ner_results.append((current_label, current_word))
                current_word = tok["word"]
                current_label = tok["entity"]

        # End the last one
        if current_word:
            ner_results.append((current_label, current_word))

        print(f"[NER] Found {len(ner_results)} entities")

    except Exception as e:
        print(f"[WARN] NER extraction failed: {e}")
    print("[INFO] Continuing with regex and Gemini detection methods")

    # --- 2. Enhanced regular rule supplement ---
    extractors = {
        "IC": extract_ic,
        "Email": extract_email,
        "DOB": extract_dob,
        "Bank Account": extract_bank_account,
        "Passport": extract_passport,
        "Phone": extract_phone,
        "Money": extract_money,
        "Gender": extract_gender,
        "Nationality": extract_nationality,
        "Credit Card": extract_credit_card,
        "Address": extract_malaysian_address,
         "Names": extract_chinese_names,
        "Vehicle Registration": extract_vehicle_registration,
    }

    print(f"[INFO] Start regular extraction, total {len(extractors)} PII types")

    for label, func in extractors.items():
        matches = func(text)
        for match in matches:
            presidio_regex_results.append((label, match.strip()))

    # --- 3. Dictionary matching supplement (selective filtering) ---
    dict_results = extract_from_dictionaries(text, enabled_categories)
    for label, value in dict_results:
        presidio_regex_results.append((label, value))

    print(f"[PRESIDIO/REGEX] Found {len(presidio_regex_results)} entities")

    # --- 4. Gemini Enhanced Detection ---
    if gemini_enabled and len(text.strip()) >= 20:  # Use LLM for meaningful text
        print("[INFO] Starting Gemini enhanced detection...")
        gemini_results = extract_pii_with_gemini(text, enabled_categories)
        print(f"[Gemini] Found {len(gemini_results)} entities")
    else:
        if not gemini_enabled:
            print("[INFO] Gemini detection skipped (not enabled)")
        else:
            print(f"[INFO] Gemini detection skipped (text too short: {len(text.strip())} chars < 20)")

    # --- 5. Ollama Enhanced Detection (Malaysian-focused) ---
    if ollama_enabled and len(text.strip()) >= 20:
        print("[INFO] Starting Ollama enhanced detection...")
        ollama_results = extract_pii_with_ollama(text, enabled_categories)
        print(f"[Ollama] Found {len(ollama_results)} entities")
    else:
        if not ollama_enabled:
            print("[INFO] Ollama detection skipped (not enabled)")
        else:
            print(f"[INFO] Ollama detection skipped (text too short: {len(text.strip())} chars < 20)")

    # --- 6. Result merging and consensus mechanism (Stage 1 Complete) ---
    print("[INFO] Stage 1: Apply consensus mechanism to merge test results...")
    stage1_results = combine_pii_results(presidio_regex_results, ner_results, gemini_results, ollama_results)

    # --- 6. Deduplication + Filtering Non-sensitive Words (Stage 1 Filtering) ---
    seen = set()
    stage1_filtered = []
    for label, value in stage1_results:
        clean_val = value.strip().lower()
        # Skipping empty values and ignoring words
        if not clean_val or clean_val in IGNORE_WORDS:
            continue
        if clean_val not in seen:
            seen.add(clean_val)
            stage1_filtered.append((label, value.strip()))  # Keep original case

    print(f"[STAGE-1] Initially detected {len(stage1_filtered)} PII candidates")

    # --- 7. Stage 2: Gemini Contextual Validation (ADDITIVE, not filtering) ---
    if len(stage1_filtered) > 0 and len(text.strip()) >= 100:  # Only for substantial documents
        print("[INFO] Stage 2: Starting Gemini contextual validation...")
        gemini_validated = validate_pii_with_gemini_context(text, stage1_filtered, enabled_categories)

        # Calculate filtering statistics for logging
        filtered_count = len(stage1_filtered) - len(gemini_validated)
        if filtered_count > 0:
            print(f"[STAGE-2] Gemini validation: {len(gemini_validated)}/{len(stage1_filtered)} items passed validation")
        else:
            print(f"[STAGE-2] Gemini validation: All candidates passed validation")

        # IMPORTANT: Use ALL Stage 1 results, not just Gemini-validated ones
        # This ensures comprehensive PII protection while benefiting from Gemini's accuracy insights
        final_results = stage1_filtered
        print(f"[STAGE-2] Retaining all Stage 1 detection results to ensure comprehensive protection")
    else:
        print("[INFO] Stage 2: Skipping contextual validation (document too short or no candidates)")
        final_results = stage1_filtered

    print(f"[FINAL] Finally detected {len(final_results)} PII items")
    return final_results
