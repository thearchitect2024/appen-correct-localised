#!/usr/bin/env python3
"""
AppenCorrect Python API Examples

This file demonstrates various ways to use the AppenCorrect Python API
for text correction without needing to run a Flask server.
"""

import os
from appencorrect import PythonAPI, check_text, correct_text


def basic_usage_examples():
    """Basic usage examples of the Python API."""
    print("=" * 60)
    print("BASIC USAGE EXAMPLES")
    print("=" * 60)
    
    # Initialize the API
    api = PythonAPI()
    
    # Check if the API is ready
    if not api.is_ready():
        print("⚠️  Warning: Gemini API not available. Set GEMINI_API_KEY environment variable.")
        print("Some features may not work properly.\n")
    
    # Example 1: Basic text checking
    print("1. Basic Text Checking")
    print("-" * 30)
    text = "This is a sentance with some erors and bad grammer."
    result = api.check_text(text)
    
    print(f"Original: {result['original_text']}")
    print(f"Corrected: {result['processed_text']}")
    print(f"Found {len(result['corrections'])} corrections:")
    for correction in result['corrections']:
        print(f"  - {correction['original']} → {correction['suggestion']} ({correction['type']})")
    print()
    
    # Example 2: Just get the corrected text
    print("2. Simple Text Correction")
    print("-" * 30)
    corrected = api.correct_text("This is a sentance with erors.")
    print(f"Input: This is a sentance with erors.")
    print(f"Output: {corrected}")
    print()


def homophone_correction_examples():
    """Examples demonstrating context-aware homophone correction."""
    print("=" * 60)
    print("CONTEXT-AWARE HOMOPHONE CORRECTION EXAMPLES ⭐ NEW")
    print("=" * 60)
    
    api = PythonAPI()
    
    # Example 1: there/their/they're corrections
    print("1. There/Their/They're Corrections")
    print("-" * 40)
    text = "The companys quarterly report shows there have been significant improvements in there performance metrics. This achievement is the result of there teams dedication and there commitment to excellence. However, they're still facing some challenges in there market position."
    result = api.check_text(text)
    
    print(f"Original: {text}")
    print(f"Corrected: {result['processed_text']}")
    print("Homophone corrections:")
    for correction in result['corrections']:
        if correction['original'].lower() in ['there', 'their', "they're"]:
            print(f"  ✓ {correction['original']} → {correction['suggestion']} (context-aware)")
    print()
    
    # Example 2: your/you're corrections
    print("2. Your/You're Corrections")
    print("-" * 40)
    text = "Your going to love this product! Your satisfaction is our priority, and you're reviews help us improve."
    result = api.check_text(text)
    
    print(f"Original: {text}")
    print(f"Corrected: {result['processed_text']}")
    print("Homophone corrections:")
    for correction in result['corrections']:
        if correction['original'].lower() in ['your', "you're"]:
            print(f"  ✓ {correction['original']} → {correction['suggestion']} (context-aware)")
    print()
    
    # Example 3: its/it's corrections  
    print("3. Its/It's Corrections")
    print("-" * 40)
    text = "The company lost it's competitive edge, but its still working to regain its market position."
    result = api.check_text(text)
    
    print(f"Original: {text}")
    print(f"Corrected: {result['processed_text']}")
    print("Homophone corrections:")
    for correction in result['corrections']:
        if correction['original'].lower() in ['its', "it's"]:
            print(f"  ✓ {correction['original']} → {correction['suggestion']} (context-aware)")
    print()
    
    # Example 4: Demonstrating preservation of correct usage
    print("4. Preserving Correct Usage")
    print("-" * 40)
    text = "There are many benefits to this approach. Their team works over there in that building."
    result = api.check_text(text)
    
    print(f"Original: {text}")
    print(f"Corrected: {result['processed_text']}")
    if len(result['corrections']) == 0:
        print("✓ No corrections needed - all homophones used correctly!")
    else:
        print("Corrections made:")
        for correction in result['corrections']:
            print(f"  - {correction['original']} → {correction['suggestion']}")
    print()


def specialized_checking_examples():
    """Examples of specialized checking (spelling, grammar, style)."""
    print("=" * 60)
    print("SPECIALIZED CHECKING EXAMPLES")
    print("=" * 60)
    
    api = PythonAPI()
    
    # Example 1: Spelling-only checking
    print("1. Spelling-Only Checking")
    print("-" * 30)
    text = "This sentance has mispelled words but grammer is ok."
    result = api.check_spelling(text)
    
    print(f"Text: {text}")
    print(f"Spelling corrections found: {len(result['corrections'])}")
    for correction in result['corrections']:
        print(f"  - {correction['original']} → {correction['suggestion']}")
    print()
    
    # Example 2: Grammar-only checking
    print("2. Grammar-Only Checking")
    print("-" * 30)
    text = "This are a sentence with grammar problems but spelling is correct."
    result = api.check_grammar(text)
    
    print(f"Text: {text}")
    print(f"Grammar corrections found: {len(result['corrections'])}")
    for correction in result['corrections']:
        print(f"  - {correction['original']} → {correction['suggestion']}")
    print()
    
    # Example 3: Style checking
    print("3. Style Checking")
    print("-" * 30)
    text = "The utilization of verbose and unnecessarily complex linguistic constructions."
    result = api.check_style(text)
    
    print(f"Text: {text}")
    print(f"Style suggestions found: {len(result['corrections'])}")
    for correction in result['corrections']:
        print(f"  - {correction['original']} → {correction['suggestion']}")
    print()


def language_detection_examples():
    """Examples of language detection."""
    print("=" * 60)
    print("LANGUAGE DETECTION EXAMPLES")
    print("=" * 60)
    
    api = PythonAPI()
    
    texts = [
        "Hello, how are you today?",
        "Bonjour, comment allez-vous?",
        "Hola, ¿cómo estás?",
        "Guten Tag, wie geht es Ihnen?",
        "This is a mixed text avec du français."
    ]
    
    for text in texts:
        language = api.detect_language(text)
        print(f"Text: {text}")
        print(f"Detected language: {language or 'Unknown'}")
        print()


def batch_processing_example():
    """Example of processing multiple texts."""
    print("=" * 60)
    print("BATCH PROCESSING EXAMPLE")
    print("=" * 60)
    
    api = PythonAPI()
    
    texts = [
        "This is a sentance with erors.",
        "These are some more problematic texts.",
        "The third text has grammer issues to.",
        "All this texts needs correction."
    ]
    
    results = []
    for i, text in enumerate(texts, 1):
        result = api.check_text(text)
        results.append(result)
        print(f"{i}. Original: {text}")
        print(f"   Corrected: {result['processed_text']}")
        print(f"   Corrections: {len(result['corrections'])}")
        print()
    
    # Summary statistics
    total_corrections = sum(len(r['corrections']) for r in results)
    print(f"Summary: Processed {len(texts)} texts with {total_corrections} total corrections")


def convenience_functions_examples():
    """Examples using convenience functions."""
    print("=" * 60)
    print("CONVENIENCE FUNCTIONS EXAMPLES")
    print("=" * 60)
    
    # Using standalone functions (creates new API instance each time)
    print("1. Using check_text() function")
    print("-" * 30)
    result = check_text("This is a sentance with erors.")
    print(f"Result: {result['processed_text']}")
    print(f"Corrections: {len(result['corrections'])}")
    print()
    
    print("2. Using correct_text() function")
    print("-" * 30)
    corrected = correct_text("This is a sentance with erors.")
    print(f"Corrected: {corrected}")
    print()


def configuration_examples():
    """Examples of different configurations."""
    print("=" * 60)
    print("CONFIGURATION EXAMPLES")
    print("=" * 60)
    
    # Example 1: Different language detectors
    print("1. Different Language Detectors")
    print("-" * 30)
    
    # With langdetect (default)
    api1 = PythonAPI(language_detector='langdetect')
    text = "Bonjour, comment allez-vous?"
    lang1 = api1.detect_language(text)
    print(f"langdetect: {lang1}")
    
    # With lingua (if available)
    api2 = PythonAPI(language_detector='lingua')
    lang2 = api2.detect_language(text)
    print(f"lingua: {lang2}")
    
    # Disabled
    api3 = PythonAPI(language_detector='disabled')
    lang3 = api3.detect_language(text)
    print(f"disabled: {lang3}")
    print()
    
    # Example 2: Custom Gemini model
    print("2. Custom Configuration")
    print("-" * 30)
    api = PythonAPI(
        gemini_model='gemini-2.5-flash',
        language_detector='langdetect'
    )
    
    health = api.health_check()
    print(f"API Status: {health['status']}")
    print(f"Components: {health['components']}")
    print()


def error_handling_examples():
    """Examples of error handling."""
    print("=" * 60)
    print("ERROR HANDLING EXAMPLES")
    print("=" * 60)
    
    # Example 1: Invalid API key
    print("1. Handling API Errors")
    print("-" * 30)
    api = PythonAPI(gemini_api_key="invalid-key")
    
    if not api.is_ready():
        print("API not ready - handling gracefully")
        result = api.check_text("This is a test.")
        print(f"Status: {result['status']}")
        if result['status'] == 'error':
            print(f"Error: {result.get('message', 'Unknown error')}")
    print()
    
    # Example 2: Empty text
    print("2. Handling Empty Input")
    print("-" * 30)
    api = PythonAPI()
    result = api.check_text("")
    print(f"Empty text result: {result}")
    print()


def statistics_and_monitoring_examples():
    """Examples of getting statistics and monitoring."""
    print("=" * 60)
    print("STATISTICS AND MONITORING EXAMPLES")
    print("=" * 60)
    
    api = PythonAPI()
    
    # Process some texts to generate statistics
    texts = [
        "This is a sentance with erors.",
        "Another text with grammer problems.",
        "A third sentance for testing."
    ]
    
    for text in texts:
        api.check_text(text)
    
    # Get statistics
    stats = api.get_statistics()
    print("Processing Statistics:")
    print(f"  Total processed: {stats.get('total_processed', 0)}")
    print(f"  Gemini corrections: {stats.get('gemini_corrections', 0)}")
    print(f"  Cache hits: {stats.get('cache_hits', 0)}")
    print(f"  Language detections: {stats.get('language_detections', 0)}")
    print()
    
    # Health check
    health = api.health_check()
    print("Health Check:")
    print(f"  Status: {health['status']}")
    print(f"  Version: {health['version']}")
    print(f"  Capabilities: {', '.join(health['capabilities'])}")
    print()
    
    # Supported languages
    languages = api.get_supported_languages()
    print(f"Supported languages: {', '.join(languages)}")


def main():
    """Run all examples."""
    print("AppenCorrect Python API Examples")
    print("================================")
    print()
    
    # Check if Gemini API key is set
    if not os.getenv('GEMINI_API_KEY'):
        print("💡 TIP: Set GEMINI_API_KEY environment variable for full functionality")
        print()
    
    try:
        basic_usage_examples()
        homophone_correction_examples()  # ⭐ NEW: Context-aware homophone examples
        specialized_checking_examples()
        language_detection_examples()
        batch_processing_example()
        convenience_functions_examples()
        configuration_examples()
        error_handling_examples()
        statistics_and_monitoring_examples()
        
        print("=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error running examples: {e}")


if __name__ == "__main__":
    main() 