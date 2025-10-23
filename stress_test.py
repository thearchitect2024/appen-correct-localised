#!/usr/bin/env python3
"""
AppenCorrect Stress Test - 500 Concurrent Connections
Generates diverse sentences with errors to test system performance.
"""

import asyncio
import aiohttp
import time
import random
import json
from datetime import datetime

# Test sentences with various error types
SENTENCE_TEMPLATES = [
    "The {adjective} {noun} {verb} {adverb} through the {location}.",
    "I {verb} to {action} my {noun} {adverb} because it was {adjective}.", 
    "What is the {adjective} {noun} that {verb} in {location}?",
    "This {noun} has many {adjective} {plural_noun} that need {action}.",
    "The {adjective} {noun} {verb} {adverb} when {condition}.",
    "How can we {action} the {adjective} {noun} more {adverb}?",
    "The {noun} was {adjective} and {adjective2} during the {event}.",
    "I {verb} the {noun} will {action} {adverb} in the {location}.",
    "What kind of {adjective} {plural_noun} {verb} {adverb}?",
    "The {adjective} {noun} {verb} because {reason}."
]

# Word lists with intentional errors
WORDS = {
    'adjective': ['beautifull', 'wonderfull', 'amasing', 'incredibel', 'fantastc', 'awsome', 'excelent', 'perfet'],
    'noun': ['sentance', 'documant', 'analiysis', 'performanc', 'sistem', 'machien', 'proccess', 'requirment'],
    'verb': ['proces', 'analiz', 'determin', 'evaluat', 'demonstrat', 'implament', 'optmize', 'achiev'],
    'adverb': ['efficently', 'accuratly', 'consistantly', 'immediatly', 'automaticaly', 'sucessfully', 'definitly', 'completly'],
    'plural_noun': ['erors', 'misstakes', 'improvments', 'changees', 'requirments', 'analisees', 'documants', 'sistems'],
    'location': ['databas', 'servr', 'memori', 'cach', 'netwrk', 'sistem', 'platfrom', 'environmnt'],
    'action': ['corect', 'proces', 'analyz', 'optmize', 'implment', 'evaluat', 'determin', 'achiev'],
    'adjective2': ['efficent', 'relabl', 'accurte', 'consistnt', 'optimzed', 'enhanceed', 'improovd', 'advanceed'],
    'event': ['testin', 'procesing', 'analisys', 'evaluasion', 'implementasion', 'optimizasion', 'performanc', 'executon'],
    'condition': ['necesary', 'requird', 'importnt', 'critcal', 'esential', 'mandatry', 'optionl', 'reccomended'],
    'reason': ['it was necesary', 'the sistem requird it', 'performanc was bad', 'erors were found', 'optimizasion was needd']
}

def generate_test_sentence():
    """Generate a random sentence with spelling errors."""
    template = random.choice(SENTENCE_TEMPLATES)
    
    # Fill in template with random words
    sentence = template
    for word_type in WORDS:
        if f'{{{word_type}}}' in sentence:
            word = random.choice(WORDS[word_type])
            sentence = sentence.replace(f'{{{word_type}}}', word)
    
    return sentence

async def make_request(session, api_key, sentence, request_id):
    """Make a single API request."""
    url = "https://appencorrect.xlostxcoz.com/check"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    data = {
        "text": f"Request {request_id}: {sentence}",
        "language": "english"
    }
    
    start_time = time.time()
    try:
        async with session.post(url, headers=headers, json=data, timeout=30) as response:
            response_time = time.time() - start_time
            
            if response.status == 200:
                result = await response.json()
                corrections = len(result.get('corrections', []))
                return {
                    'request_id': request_id,
                    'status': 'success',
                    'response_time': response_time,
                    'corrections_found': corrections,
                    'cached': result.get('statistics', {}).get('processing_time', '1s').startswith('0.0')
                }
            else:
                return {
                    'request_id': request_id,
                    'status': 'error',
                    'response_time': response_time,
                    'error_code': response.status,
                    'corrections_found': 0,
                    'cached': False
                }
                
    except Exception as e:
        response_time = time.time() - start_time
        return {
            'request_id': request_id,
            'status': 'exception',
            'response_time': response_time,
            'error': str(e),
            'corrections_found': 0,
            'cached': False
        }

async def run_stress_test(api_key, num_requests=500, batch_size=50):
    """Run stress test with specified number of requests."""
    print(f"🚀 Starting stress test: {num_requests} requests in batches of {batch_size}")
    print(f"📝 Using API key: {api_key[:20]}...")
    print("=" * 80)
    
    # Generate unique sentences
    sentences = [generate_test_sentence() for _ in range(num_requests)]
    print(f"📚 Generated {len(sentences)} unique test sentences")
    
    # Statistics tracking
    results = []
    start_time = time.time()
    
    # Create session with connection limits
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
    timeout = aiohttp.ClientTimeout(total=60)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Process in batches to avoid overwhelming
        for batch_start in range(0, num_requests, batch_size):
            batch_end = min(batch_start + batch_size, num_requests)
            batch_sentences = sentences[batch_start:batch_end]
            
            print(f"🔄 Processing batch {batch_start//batch_size + 1}: requests {batch_start+1}-{batch_end}")
            
            # Create tasks for this batch
            tasks = []
            for i, sentence in enumerate(batch_sentences):
                request_id = batch_start + i + 1
                task = make_request(session, api_key, sentence, request_id)
                tasks.append(task)
            
            # Execute batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    results.append({
                        'status': 'exception', 
                        'error': str(result),
                        'response_time': 0
                    })
                else:
                    results.append(result)
            
            # Brief pause between batches
            await asyncio.sleep(0.5)
    
    # Calculate statistics
    total_time = time.time() - start_time
    
    successful = len([r for r in results if r.get('status') == 'success'])
    errors = len([r for r in results if r.get('status') != 'success'])
    cached_responses = len([r for r in results if r.get('cached', False)])
    
    avg_response_time = sum(r.get('response_time', 0) for r in results) / len(results)
    total_corrections = sum(r.get('corrections_found', 0) for r in results)
    
    print("\n" + "=" * 80)
    print("📊 STRESS TEST RESULTS")
    print("=" * 80)
    print(f"Total Requests: {num_requests}")
    print(f"Successful: {successful} ({successful/num_requests*100:.1f}%)")
    print(f"Failed: {errors} ({errors/num_requests*100:.1f}%)")
    print(f"Cached Responses: {cached_responses} ({cached_responses/num_requests*100:.1f}%)")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Requests/Second: {num_requests/total_time:.2f}")
    print(f"Avg Response Time: {avg_response_time:.3f}s")
    print(f"Total Corrections Found: {total_corrections}")
    print("\n📈 Performance Assessment:")
    
    if successful/num_requests >= 0.99:
        print("✅ EXCELLENT: >99% success rate")
    elif successful/num_requests >= 0.95:
        print("✅ GOOD: >95% success rate") 
    elif successful/num_requests >= 0.90:
        print("⚠️ ACCEPTABLE: >90% success rate")
    else:
        print("❌ POOR: <90% success rate - needs investigation")
    
    if num_requests/total_time >= 10:
        print("🚀 EXCELLENT: >10 req/sec throughput")
    elif num_requests/total_time >= 5:
        print("✅ GOOD: >5 req/sec throughput")
    else:
        print("⚠️ SLOW: <5 req/sec throughput")
    
    # Show sample errors if any
    error_results = [r for r in results if r.get('status') != 'success']
    if error_results:
        print(f"\n🔍 Sample Errors (showing first 5 of {len(error_results)}):")
        for error in error_results[:5]:
            print(f"  Request {error.get('request_id', '?')}: {error.get('error', error.get('error_code', 'Unknown'))}")

if __name__ == "__main__":
    import sys
    
    # Configuration
    API_KEY = "appencorrect_6cc586912e264062afdc0810f22d075a"
    NUM_REQUESTS = 500
    BATCH_SIZE = 50
    
    # Allow command line override
    if len(sys.argv) > 1:
        NUM_REQUESTS = int(sys.argv[1])
    if len(sys.argv) > 2:
        BATCH_SIZE = int(sys.argv[2])
    
    print(f"🧪 AppenCorrect Stress Test")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Target: {NUM_REQUESTS} requests in batches of {BATCH_SIZE}")
    print()
    
    # Run the stress test
    asyncio.run(run_stress_test(API_KEY, NUM_REQUESTS, BATCH_SIZE))
