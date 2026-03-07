import re
from typing import List, Tuple, Optional, Dict
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    SpacyRecognizer,
    PhoneRecognizer,
    EmailRecognizer,
    CreditCardRecognizer,
)

PRESIDIO_ENABLED = False
analyzer = None


def merge_consecutive_entities(text: str, results: List[RecognizerResult], max_gap: int = 5) -> List[RecognizerResult]:
    """Merge consecutive tokens of the same entity type into single entities.
    
    For example: "Nor Hafizan bin Ahmad" -> single PERSON entity
    
    Args:
        text: The original text being analyzed
        results: List of RecognizerResult from Presidio
        max_gap: Maximum gap between tokens to consider them as one entity
    
    Returns:
        Merged list of RecognizerResult
    """
    if not results:
        return []
    
    # Sort by start position
    sorted_results = sorted(results, key=lambda x: (x.start, x.entity_type))
    merged = []
    
    i = 0
    while i < len(sorted_results):
        current = sorted_results[i]
        entity_type = current.entity_type
        start = current.start
        end = current.end
        
        # Look ahead for consecutive tokens of same type
        j = i + 1
        while j < len(sorted_results):
            next_item = sorted_results[j]
            
            # Must be same entity type and close together
            if (next_item.entity_type == entity_type and 
                next_item.start - end <= max_gap and
                # Don't merge across sentence boundaries
                text[start:next_item.end].count('.') == 0):
                end = next_item.end
                j += 1
            else:
                break
        
        # Create merged entity
        merged.append(RecognizerResult(
            entity_type=entity_type,
            start=start,
            end=end,
            score=current.score,
        ))
        i = j
    
    return merged


def load_presidio() -> bool:
    """Initialize Presidio Analyzer Engine with custom recognizers"""
    global analyzer, PRESIDIO_ENABLED
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        
        # Create NLP engine with spaCy
        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
            }
        ).create_engine()
        
        analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=["en"]
        )
        
        PRESIDIO_ENABLED = True
        print("✅ Presidio Analyzer initialized successfully with spaCy")
        return True
    except Exception as e:
        print(f"[WARN] Failed to initialize Presidio: {e}")
        print("[INFO] Presidio PII detection disabled")
        PRESIDIO_ENABLED = False
        return False


class MalaysianICRecognizer:
    """Custom recognizer for Malaysian IC/NRIC numbers"""
    
    def __init__(self):
        self.patterns = [
            r"\b\d{6}-\d{2}-\d{4}\b",  # 920312-10-8888
            r"\b\d{12}\b",  # 123456789012 (12 consecutive digits)
        ]
        self.context = [
            "ic", "nric", "no kad", "kad pengenalan", "mykad",
            "identity card", "ic number", "ic no"
        ]
    
    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []
        for pattern in self.patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Check context for IC patterns
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context_window = text[start:end].lower()
                
                # Skip if it's just 12 digits without IC context
                if len(match.group()) == 12:
                    has_context = any(c in context_window for c in self.context)
                    if not has_context:
                        continue
                
                results.append(RecognizerResult(
                    entity_type="MALAYSIAN_IC",
                    start=match.start(),
                    end=match.end(),
                    score=0.95,
                ))
        return results


class EthnicRecognizer:
    """Custom recognizer for ethnic/religious affiliations"""
    
    def __init__(self):
        self.ethnic_terms = {
            # Malaysian ethnic groups
            "malay", "melayu", "bumiputera", "bumiputera",
            "chinese", "cina", "mandarin", "cantonese", "hokkien", "teochew", "hakka",
            "indian", "india", "tamil", "malayalam", "telugu", "hindu", "sikh",
            "iban", "dayak", "kayan", "kenyah", "bidayuh", "orang asli",
            "korean", "japanese", "japanese", "european", "eurasian",
            # Religious affiliations
            "muslim", "islam", "buddhist", "buddhism", "christian", "christianity",
            "hindu", "hinduism", "sikh", "sikhism", "catholic", "protestant",
            "atheist", "agnostic", "non-religious",
        }
        
        self.context = [
            "ethnic", "religion", "religious", "race", "bangsa", "kaum",
            "amal", "religion", "faith"
        ]
    
    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []
        words = re.findall(r'\b\w+\b', text.lower())
        
        for i, word in enumerate(words):
            if word in self.ethnic_terms:
                # Find position in original text
                pattern = r'\b' + re.escape(word) + r'\b'
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Check context
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    context_window = text[start:end].lower()
                    
                    has_context = any(c in context_window for c in self.context)
                    if has_context or i > 0:
                        results.append(RecognizerResult(
                            entity_type="ETHNIC",
                            start=match.start(),
                            end=match.end(),
                            score=0.85,
                        ))
        return results


class MalaysianOrgRecognizer:
    """Custom recognizer for Malaysian organization names"""
    
    def __init__(self):
        self.suffixes = [
            "sdn bhd", "sdn. bhd.", "sendirian berhad", "berhad", "bhd.",
            "holdings", "holding", "group", "corporation", "corp",
            "ltd", "limited", "inc", "incorporated", "company", "co.",
            "associates", "partners", "enterprise", "industries",
            "malaysia", "malaysian", "kuala lumpur", "kl", "pj",
        ]
    
    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []
        
        # Find potential org names with suffixes - limit to 1-3 words before suffix
        suffix_pattern = '|'.join(re.escape(s) for s in self.suffixes)
        pattern = rf'\b([A-Z][A-Za-z&]+(?:\s+[A-Za-z&]{{1,3}}){{0,2}})\s+(?:{suffix_pattern})\b'
        
        for match in re.finditer(pattern, text, re.IGNORECASE):
            org_name = match.group(1).strip()
            name_start = match.start()
            name_end = name_start + len(org_name)
            
            skip_phrases = ["private limited", "public limited", "company limited", 
                          "holdings limited", "group limited", "and company"]
            if any(phrase in match.group().lower() for phrase in skip_phrases):
                if "limited" not in match.group().lower() or len(match.group()) > 15:
                    pass
                else:
                    continue
            
            results.append(RecognizerResult(
                entity_type="ORG",
                start=name_start,
                end=name_end,
                score=0.90,
            ))
        return results


class MalaysianNameRecognizer:
    """Custom recognizer for Malaysian names with common prefixes"""
    
    def __init__(self):
        self.prefixes = [
            "cik", "pn", "tn", "puan", "tuan", "dato", "datuk", "datin",
            "dr", "prof", "madam", "mr", "mrs", "miss", "nor", "Allah",
        ]
        self.suffixes = [
            "bin", "binti", "bt", "ibni",
        ]
    
    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []
        
        # Pattern: prefix + name - simpler approach
        prefix_pattern = r'\b(c i k|p n|t n|p u a n|t u a n|d a t o|d a t u k|d a t i n|d r|p r o f|m r|m r s|m i s s|n o r|a l l a h)\b'
        
        # Helper to check if position is at a word boundary
        def is_word_boundary(s, pos):
            if pos >= len(s):
                return True
            if pos < 0:
                return True
            return not s[pos].isalnum()
        
        for match in re.finditer(prefix_pattern, text, re.IGNORECASE | re.VERBOSE):
            prefix_start = match.start()
            prefix_end = match.end()
            
            # Find the capitalized name after the prefix
            name_start = prefix_end
            while name_start < len(text) and text[name_start] in ' \t':
                name_start += 1
            
            if name_start >= len(text):
                continue
                
            # Collect the name words (1-4 capitalized words)
            name_parts = []
            while name_start < len(text):
                # Check if we're at a word boundary
                if is_word_boundary(text, name_start):
                    break
                    
                # Match a word
                word_match = re.match(r'[A-Za-z]+', text[name_start:])
                if not word_match:
                    break
                    
                word = word_match.group()
                # Only include if it looks like a name (starts with uppercase or is short like "bin")
                if word[0].isupper() or word.lower() in ['bin', 'binti', 'bt', 'ibni']:
                    name_parts.append(word)
                    name_start += len(word)
                else:
                    break
                    
                # Skip whitespace
                while name_start < len(text) and text[name_start] in ' \t':
                    name_start += 1
                    
                # Stop after 4 name parts max
                if len(name_parts) >= 4:
                    break
            
            if name_parts:
                full_name_start = prefix_start
                full_name_end = name_start
                results.append(RecognizerResult(
                    entity_type="PERSON",
                    start=full_name_start,
                    end=full_name_end,
                    score=0.95,
                ))
        return results


def analyze_with_presidio(text: str, categories: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """
    Analyze text with Presidio for PII detection.
    
    Args:
        text: Text to analyze
        categories: List of categories to detect (NAMES, ORG_NAMES, ETHNIC, etc.)
    
    Returns:
        List of (label, value) tuples
    """
    global analyzer
    
    if not PRESIDIO_ENABLED:
        if not load_presidio():
            return []
    
    if not text or len(text.strip()) < 5:
        return []
    
    if categories is None:
        categories = ["NAMES", "ORG_NAMES", "ETHNIC", "IC", "EMAIL", "PHONE", "CREDIT_CARD"]
    
    results = []
    seen = set()
    
    try:
        # Map Presidio entity types to our labels
        entity_mapping = {
            "PERSON": "NAMES",
            "ORG": "ORG_NAMES",
            "EMAIL_ADDRESS": "EMAIL",
            "PHONE_NUMBER": "PHONE",
            "CREDIT_CARD": "CREDIT_CARD",
            "NRP": "PASSPORT",
            "IP_ADDRESS": "IP_ADDRESS",
            "MALAYSIAN_IC": "IC",
            "ETHNIC": "ETHNIC",
        }
        
        # Run Presidio analyzer
        detected = analyzer.analyze(
            text=text,
            language="en",
            entities=list(entity_mapping.keys()),
            score_threshold=0.3,  # Lowered to catch more names
            return_decision_process=False,
        )
        
        # Merge consecutive tokens of same entity type (e.g., "Nor Hafizan bin Ahmad" -> single name)
        detected = merge_consecutive_entities(text, detected)
        
        # Expand PERSON entities to include common Malaysian name prefixes and suffixes
        name_prefixes = ["nor", "tn", "pn", "dato", "datuk", "datin", "tuan", "puan", "cik", "allah", "dr", "prof", "sri", "sha", "mohd", "mu"]
        name_suffixes = ["bin", "binti", "bt", "ibni"]
        expanded_detected = []
        
        # First, merge again after initial detection
        for item in detected:
            if item.entity_type == "PERSON":
                value = text[item.start:item.end]
                
                # Check for prefix before the name
                if item.start >= 3:
                    # Get the word before this entity
                    start_idx = item.start - 1
                    while start_idx >= 0 and text[start_idx] == ' ':
                        start_idx -= 1
                    word_end = start_idx + 1
                    while start_idx >= 0 and text[start_idx].isalnum():
                        start_idx -= 1
                    prefix_word = text[start_idx+1:word_end].lower() if start_idx < word_end - 1 else ""
                    
                    if prefix_word in name_prefixes or len(prefix_word) <= 4:
                        # Include the prefix
                        prefix_start = start_idx + 1
                        expanded_detected.append(RecognizerResult(
                            entity_type=item.entity_type,
                            start=prefix_start,
                            end=item.end,
                            score=item.score,
                        ))
                        continue
                            
                # Check for suffix at the end (bin, binti, bt)
                if item.end < len(text) - 1:
                    # Get the word after this entity
                    end_idx = item.end
                    while end_idx < len(text) and text[end_idx] == ' ':
                        end_idx += 1
                    word_end = end_idx
                    while word_end < len(text) and text[word_end].isalnum():
                        word_end += 1
                    suffix_word = text[end_idx:word_end].lower() if end_idx < word_end else ""
                    
                    if suffix_word in name_suffixes:
                        # Include suffix and potentially next word
                        suffix_end = word_end
                        # Include the next word if it's a typical father's name
                        if word_end < len(text):
                            next_space = text.find(' ', word_end)
                            if next_space > word_end:
                                next_word = text[word_end:next_space].lower()
                                if len(next_word) > 0 and next_word[0].isupper():
                                    suffix_end = next_space
                        expanded_detected.append(RecognizerResult(
                            entity_type=item.entity_type,
                            start=item.start,
                            end=suffix_end,
                            score=item.score,
                        ))
                        continue
                            
            expanded_detected.append(item)
        detected = expanded_detected
        
        # Re-merge after expansion
        detected = merge_consecutive_entities(text, detected)
        
        for item in detected:
            entity_type = item.entity_type
            label = entity_mapping.get(entity_type, entity_type)
            
            # Skip categories not enabled
            if categories and label not in categories and entity_type not in categories:
                continue
            
            value = text[item.start:item.end].strip()
            if value and len(value) > 1 and value.lower() not in seen:
                seen.add(value.lower())
                results.append((label, value))
        
        # Run custom recognizers
        custom_recognizers = [
            MalaysianICRecognizer(),
            EthnicRecognizer(),
            MalaysianOrgRecognizer(),
            MalaysianNameRecognizer(),
        ]
        
        for recognizer in custom_recognizers:
            try:
                custom_results = recognizer.analyze(text)
                for item in custom_results:
                    label = item.entity_type
                    label = item.entity_type
                    
                    # Map entity types to our labels
                    label_mapping = {
                        "ORG": "ORG_NAMES",
                        "MALAYSIAN_IC": "IC",
                    }
                    label = label_mapping.get(label, label)
                    
                    if categories and label not in categories:
                        continue
                    
                    value = text[item.start:item.end].strip()
                    if value and len(value) > 1 and value.lower() not in seen:
                        seen.add(value.lower())
                        results.append((label, value))
            except Exception as e:
                print(f"[WARN] Custom recognizer error in {recognizer.__class__.__name__}: {e}")
                continue
        
        print(f"[Presidio] Found {len(results)} PII items")
        
    except Exception as e:
        print(f"[ERROR] Presidio analysis failed: {e}")
        return []
    
    return results


def extract_pii_with_presidio(text: str, enabled_categories: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """
    Presidio-based PII extraction (primary detector).
    
    Args:
        text: Text to analyze
        enabled_categories: List of enabled PII categories
    
    Returns:
        List of (label, value) tuples
    """
    if not text or len(text.strip()) < 5:
        return []
    
    if enabled_categories is None:
        enabled_categories = ["NAMES", "ORG_NAMES", "ETHNIC", "IC", "EMAIL", "PHONE", "CREDIT_CARD"]
    
    return analyze_with_presidio(text, enabled_categories)
