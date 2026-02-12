#!/usr/bin/env python3
"""
Test script to validate Ollama PII detection feasibility.
"""

import json
import time
from typing import Dict


def test_ollama_connectivity(model: str = "qwen3-next:80b") -> bool:
    """Test if Ollama is accessible and can respond."""
    try:
        import ollama
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": "Hello"}],
            timeout=10
        )
        print(f"Ollama connectivity test passed - Model: {response.get('model', 'unknown')}")
        return True
    except Exception as e:
        print(f"Ollama connectivity test failed: {e}")
        return False


def test_malaysian_name_detection(model: str = "qwen3-next:80b") -> bool:
    """Test if model can detect Malaysian names."""
    test_text = "Customer: WONG JUN KEAT, IC: 900101-14-1234, Kuala Lumpur"
    
    prompt = f"""Extract PII from: {test_text}
Return JSON: [{{"category": "NAMES"|"IC", "value": ". ..", "confidence": 0.95}}]"""
    
    try:
        import ollama
        start = time.time()
        response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}], timeout=30)
        elapsed = time.time() - start
        
        response_text = response.get("message", {}).get("content", "").strip()
        json_start = response_text.find('[')
        json_end = response_text.rfind(']') + 1
        
        if json_start >= 0 and json_end > json_start:
            results = json.loads(response_text[json_start:json_end])
            names = [r for r in results if r.get("category") == "NAMES"]
            if names:
                print(f"Malaysian name detection PASSED - time: {elapsed:.2f}s, found: {len(results)} PII")
                return True
            else:
                print(f"Malaysian name detection - names not detected")
                return False
        else:
            print(f"Malaysian name detection - JSON parsing failed")
            return False
    except Exception as e:
        print(f"Malaysian name detection failed: {e}")
        return False


def test_malaysian_context(model: str = "qwen3-next:80b") -> bool:
    """Test Malaysian context awareness with bin/binti/anak patterns."""
    test_texts = [
        "Account: AHMAD BIN ALI, IC: 850515-10-5678",
        "Individual: JANTING ANAK SUMPING, Iban, Sarawak",
        "Customer: LIEW MEI LING, Chinese ethnicity"
    ]
    
    try:
        import ollama
        all_passed = True
        
        for text in test_texts:
            prompt = f"""Extract PII. Focus on Malaysian names (bin, binti, anak patterns).
Return JSON with category, value, confidence: {text}"""
            
            response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}], timeout=30)
            response_text = response.get("message", {}).get("content", "").strip()
            
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                results = json.loads(response_text[json_start:json_end])
                has_names = any(r.get("category") == "NAMES" for r in results)
                print(f"Context test PASSED - {text[:40]}... ({len(results)} items)")
                if not has_names:
                    all_passed = False
            else:
                print(f"Context test - JSON parsing failed")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"Malaysian context test failed: {e}")
        return False


def test_response_time(model: str = "qwen3-next:80b") -> None:
    """Benchmark response times."""
    import ollama
    
    sample = "WONG JUN KEAT, IC: 900101-14-1234"
    
    for label, count in [("Short", 1), ("Medium", 5), ("Long", 10)]:
        text = sample * count
        start = time.time()
        try:
            response = ollama.chat(model=model, messages=[{"role": "user", "content": f"Extract PII: {text[:1000]}"}], timeout=60)
            elapsed = time.time() - start
            print(f"Response time {label}: {elapsed:.2f}s")
        except Exception as e:
            print(f"Response time {label} FAILED: {e}")


def main():
    """Run tests."""
    print("Ollama PII Detection Feasibility Test")
    print("=" * 50)
    
    model = "qwen3-next:80b"
    print(f"Model: {model}\n")
    
    results = {}
    
    results["Connectivity"] = test_ollama_connectivity()
    print()
    
    results["Malaysian Name Detection"] = test_malaysian_name_detection()
    print()
    
    results["Malaysian Context"] = test_malaysian_context()
    print()
    
    print("Response time benchmark:")
    test_response_time()
    
    print("\n" + "=" * 50)
    print("Summary:")
    for name, passed in results.items():
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
    print("=" * 50)


if __name__ == "__main__":
    main()
