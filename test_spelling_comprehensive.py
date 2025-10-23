#!/usr/bin/env python3
"""
Comprehensive tests for the spelling-only endpoint
Tests various types of errors to ensure proper classification
"""

import requests
import json

API_URL = "http://localhost:5006/check/spelling"
API_KEY = "appencorrect_6cc586912e264062afdc0810f22d075a"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
}

# Test cases with expected behavior
TEST_CASES = [
    {
        "name": "Clear spelling errors (should be corrected)",
        "text": "This sentance has speling erors and recieve is wrong.",
        "language": "en",
        "should_correct": ["sentance", "speling", "erors", "recieve"],
        "should_not_correct": []
    },
    {
        "name": "Spanish with real spelling error",
        "text": "Los politicos se queivoca riguardo los",
        "language": "es", 
        "should_correct": ["queivoca"],  # This is clearly misspelled
        "should_not_correct": ["riguardo", "politicos"]  # Word choice, not spelling
    },
    {
        "name": "Mixed real spelling vs word choice",
        "text": "I definately beleive this riguardo is importante",
        "language": "en",
        "should_correct": ["definately", "beleive"],  # Real spelling errors
        "should_not_correct": ["riguardo", "importante"]  # Foreign words, not misspellings
    },
    {
        "name": "Common misspellings",
        "text": "teh quick brown fox seperate from there freinds",
        "language": "en",
        "should_correct": ["teh", "seperate", "freinds"],
        "should_not_correct": ["there"]  # Correct word, even if wrong context
    },
    {
        "name": "Regional variants (should NOT be corrected)",
        "text": "I realise the colour is grey and organised properly",
        "language": "en-GB",
        "should_correct": [],
        "should_not_correct": ["realise", "colour", "grey", "organised"]
    },
    {
        "name": "Grammar vs spelling",
        "text": "I are writting a sentance with bad grammer",
        "language": "en",
        "should_correct": ["writting", "sentance", "grammer"],  # Spelling errors
        "should_not_correct": ["I are"]  # Grammar error, not spelling
    }
]

def test_spelling_endpoint():
    """Test the spelling endpoint with various cases."""
    print("🔍 COMPREHENSIVE SPELLING ENDPOINT TESTS")
    print("=" * 60)
    
    all_passed = True
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   Text: '{test_case['text']}'")
        
        # Make API request
        payload = {
            "text": test_case['text'],
            "language": test_case['language']
        }
        
        try:
            response = requests.post(API_URL, json=payload, headers=HEADERS)
            
            if response.status_code != 200:
                print(f"   ❌ API Error: {response.status_code} - {response.text}")
                all_passed = False
                continue
                
            result = response.json()
            corrections = result.get('corrections', [])
            corrected_words = [c['original'] for c in corrections]
            
            print(f"   Found corrections: {corrected_words}")
            
            # Check if expected corrections were made
            missing_corrections = []
            for word in test_case['should_correct']:
                if word not in corrected_words:
                    missing_corrections.append(word)
            
            # Check if unexpected corrections were made
            unexpected_corrections = []
            for correction in corrections:
                original = correction['original']
                if original in test_case['should_not_correct']:
                    unexpected_corrections.append(original)
            
            # Report results
            if missing_corrections:
                print(f"   ❌ MISSING corrections: {missing_corrections}")
                all_passed = False
            
            if unexpected_corrections:
                print(f"   ❌ UNEXPECTED corrections: {unexpected_corrections}")
                all_passed = False
                
            if not missing_corrections and not unexpected_corrections:
                print(f"   ✅ PASSED")
            else:
                print(f"   ❌ FAILED")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED - Prompt needs adjustment")
    
    return all_passed

if __name__ == "__main__":
    test_spelling_endpoint()
