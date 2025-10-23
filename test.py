#!/usr/bin/env python3
"""
AppenCorrect Performance Testing Script

Tests text correction on sentences from CSV files and records detailed metrics.
Supports both OpenAI and Gemini APIs based on the OPENAI_MODEL environment variable.

Usage:
    python test.py --rows 10 --file tests/sentences_eng.csv
    python test.py --rows 50 --file tests/sentences.csv --output results_custom.csv
"""

import argparse
import csv
import time
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple
import logging
from dotenv import load_dotenv

# Add the current directory to Python path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import AppenCorrect

# Load environment variables
load_dotenv()

# Configure logging to be less verbose during testing
logging.basicConfig(level=logging.WARNING)

def count_tokens_approximate(text: str) -> int:
    """
    Approximate token count using simple word-based estimation.
    This is a rough estimate - actual token count depends on the specific tokenizer.
    
    Args:
        text: Input text to count tokens for
        
    Returns:
        Approximate token count
    """
    if not text:
        return 0
    
    # Simple approximation: ~1.3 tokens per word for English, ~1.5 for other languages
    words = len(text.split())
    # Add some tokens for punctuation and special characters
    estimated_tokens = int(words * 1.4) + text.count(',') + text.count('.') + text.count('!') + text.count('?')
    
    return max(1, estimated_tokens)  # Minimum 1 token


def load_sentences_from_csv(file_path: str, max_rows: int = None) -> List[str]:
    """
    Load sentences from CSV file.
    
    Args:
        file_path: Path to the CSV file
        max_rows: Maximum number of rows to load (None for all)
        
    Returns:
        List of sentences
    """
    sentences = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for i, row in enumerate(reader):
                if max_rows and i >= max_rows:
                    break
                    
                # Get the sentence from the 'sentences' column (handle BOM character)
                sentence = row.get('sentences', row.get('\ufeffsentences', '')).strip()
                if sentence:
                    sentences.append(sentence)
                    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}")
        sys.exit(1)
    
    return sentences


def test_sentence_correction(corrector: AppenCorrect, sentence: str) -> Dict[str, Any]:
    """
    Test sentence correction and collect metrics.
    
    Args:
        corrector: AppenCorrect instance
        sentence: Sentence to test
        
    Returns:
        Dictionary with test results and metrics
    """
    start_time = time.time()
    
    try:
        # Process the sentence
        result = corrector.process_text(sentence)
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        # Extract results
        status = result.get('status', 'unknown')
        original_text = result.get('original_text', sentence)
        processed_text = result.get('processed_text', sentence)
        corrections = result.get('corrections', [])
        statistics = result.get('statistics', {})
        
        # Calculate token counts
        input_tokens = count_tokens_approximate(original_text)
        output_tokens = count_tokens_approximate(processed_text)
        
        # Count correction types
        spelling_corrections = len([c for c in corrections if c.get('type') == 'spelling'])
        grammar_corrections = len([c for c in corrections if c.get('type') == 'grammar'])
        style_corrections = len([c for c in corrections if c.get('type') == 'style'])
        
        return {
            'status': status,
            'original_text': original_text,
            'processed_text': processed_text,
            'latency_ms': round(latency_ms, 2),
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_corrections': len(corrections),
            'spelling_corrections': spelling_corrections,
            'grammar_corrections': grammar_corrections,
            'style_corrections': style_corrections,
            'api_type': getattr(corrector, 'api_type', 'unknown'),
            'model': getattr(corrector, 'selected_model', 'unknown'),
            'processing_time': statistics.get('processing_time', 'unknown'),
            'detected_language': statistics.get('detected_language', 'unknown'),
            'corrections_detail': str(corrections) if corrections else 'none'
        }
        
    except Exception as e:
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        return {
            'status': 'error',
            'original_text': sentence,
            'processed_text': sentence,
            'latency_ms': round(latency_ms, 2),
            'input_tokens': count_tokens_approximate(sentence),
            'output_tokens': count_tokens_approximate(sentence),
            'total_corrections': 0,
            'spelling_corrections': 0,
            'grammar_corrections': 0,
            'style_corrections': 0,
            'api_type': getattr(corrector, 'api_type', 'unknown'),
            'model': getattr(corrector, 'selected_model', 'unknown'),
            'processing_time': 'error',
            'detected_language': 'unknown',
            'corrections_detail': f'ERROR: {str(e)}',
            'error': str(e)
        }


def save_results_to_csv(results: List[Dict[str, Any]], output_file: str) -> None:
    """
    Save test results to CSV file.
    
    Args:
        results: List of test result dictionaries
        output_file: Output CSV file path
    """
    if not results:
        print("No results to save.")
        return
    
    # Define CSV headers
    headers = [
        'timestamp',
        'sentence_id',
        'status',
        'original_text',
        'processed_text',
        'latency_ms',
        'input_tokens',
        'output_tokens',
        'total_corrections',
        'spelling_corrections',
        'grammar_corrections',
        'style_corrections',
        'api_type',
        'model',
        'processing_time',
        'detected_language',
        'corrections_detail'
    ]
    
    # Add error column if any results have errors
    if any('error' in result for result in results):
        headers.append('error')
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            
            # Write header
            writer.writeheader()
            
            # Write results
            for i, result in enumerate(results, 1):
                row = {
                    'timestamp': datetime.now().isoformat(),
                    'sentence_id': i,
                    **result
                }
                writer.writerow(row)
                
        print(f"Results saved to: {output_file}")
        
    except Exception as e:
        print(f"Error saving results to CSV: {e}")


def print_summary(results: List[Dict[str, Any]]) -> None:
    """
    Print summary statistics of the test results.
    
    Args:
        results: List of test result dictionaries
    """
    if not results:
        print("No results to summarize.")
        return
    
    total_tests = len(results)
    successful_tests = len([r for r in results if r['status'] == 'success'])
    failed_tests = total_tests - successful_tests
    
    avg_latency = sum(r['latency_ms'] for r in results) / total_tests
    total_input_tokens = sum(r['input_tokens'] for r in results)
    total_output_tokens = sum(r['output_tokens'] for r in results)
    total_corrections = sum(r['total_corrections'] for r in results)
    
    api_type = results[0].get('api_type', 'unknown') if results else 'unknown'
    model = results[0].get('model', 'unknown') if results else 'unknown'
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"API Type: {api_type}")
    print(f"Model: {model}")
    print(f"Total sentences tested: {total_tests}")
    print(f"Successful tests: {successful_tests}")
    print(f"Failed tests: {failed_tests}")
    print(f"Success rate: {(successful_tests/total_tests)*100:.1f}%")
    print(f"Average latency: {avg_latency:.2f} ms")
    print(f"Total input tokens: {total_input_tokens}")
    print(f"Total output tokens: {total_output_tokens}")
    print(f"Total corrections found: {total_corrections}")
    print(f"Average corrections per sentence: {total_corrections/total_tests:.2f}")
    print("="*60)


def main():
    """Main function to run the testing script."""
    parser = argparse.ArgumentParser(
        description='Test AppenCorrect on sentences from CSV files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test.py --rows 10
  python test.py --rows 50 --file tests/sentences.csv
  python test.py --rows 25 --file tests/sentences_eng.csv --output my_results.csv
        """
    )
    
    parser.add_argument(
        '--rows', '-r',
        type=int,
        default=10,
        help='Number of rows/sentences to test (default: 10)'
    )
    
    parser.add_argument(
        '--file', '-f',
        type=str,
        default='tests/sentences_eng.csv',
        help='Path to the CSV file containing sentences (default: tests/sentences_eng.csv)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output CSV filename (default: auto-generated with timestamp)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.rows <= 0:
        print("Error: Number of rows must be positive.")
        sys.exit(1)
    
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist.")
        sys.exit(1)
    
    # Generate output filename if not provided
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(args.file))[0]
        api_model = os.getenv('OPENAI_MODEL', 'unknown').replace('/', '_').replace(':', '_')
        args.output = f"test_results_{base_name}_{api_model}_{timestamp}.csv"
    
    print("AppenCorrect Performance Testing")
    print("="*40)
    print(f"Input file: {args.file}")
    print(f"Sentences to test: {args.rows}")
    print(f"Output file: {args.output}")
    print(f"Current model: {os.getenv('OPENAI_MODEL', 'not set')}")
    print()
    
    # Load sentences
    print("Loading sentences...")
    sentences = load_sentences_from_csv(args.file, args.rows)
    
    if not sentences:
        print("No sentences found in the file.")
        sys.exit(1)
    
    print(f"Loaded {len(sentences)} sentences.")
    
    # Initialize AppenCorrect
    print("Initializing AppenCorrect...")
    try:
        corrector = AppenCorrect()
        print(f"Using {corrector.api_type.upper()} API with model: {corrector.selected_model}")
        
        # Check API availability
        if not corrector.api_available:
            print(f"Error: {corrector.api_type.upper()} API not available: {corrector.api_unavailable_reason}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error initializing AppenCorrect: {e}")
        sys.exit(1)
    
    # Run tests
    print(f"\nTesting {len(sentences)} sentences...")
    print("Progress: ", end="", flush=True)
    
    results = []
    for i, sentence in enumerate(sentences):
        # Show progress
        if i % max(1, len(sentences) // 20) == 0:
            print(".", end="", flush=True)
        
        result = test_sentence_correction(corrector, sentence)
        results.append(result)
    
    print(" Done!")
    
    # Save results
    print(f"\nSaving results to {args.output}...")
    save_results_to_csv(results, args.output)
    
    # Print summary
    print_summary(results)


if __name__ == "__main__":
    main()