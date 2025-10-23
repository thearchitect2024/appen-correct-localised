#!/usr/bin/env python3
"""
Cache Hit Rate Test - Shows actual cache performance
Tests with repeated content to demonstrate cache effectiveness
"""

import time
import requests
import threading
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

# Test configuration
API_URL = "http://localhost:5006/check"
API_KEY = "appencorrect_6cc586912e264062afdc0810f22d075a"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
}

# Test texts that will be repeated to trigger cache hits
TEST_TEXTS = [
    "This is a test sentance with some errors.",
    "I am writting this to test the cache system.",
    "The quick brown fox jumps over the lazy dog.",
    "Hello world, this is a cache performance test.",
    "Testing cache hits with repeated content."
]

def make_request(text, user_id, request_num):
    """Make a single API request"""
    try:
        payload = {
            "text": text,
            "language": "english"
        }
        
        start_time = time.time()
        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            return {
                "user_id": user_id,
                "request_num": request_num,
                "text": text,
                "response_time": float(data.get("statistics", {}).get("processing_time", "0").replace("s", "")),
                "cache_status": data.get("statistics", {}).get("cache_status", "unknown"),
                "success": True,
                "corrections": len(data.get("corrections", [])),
                "status_code": response.status_code
            }
        else:
            return {
                "user_id": user_id,
                "request_num": request_num,
                "text": text,
                "response_time": end_time - start_time,
                "cache_status": "error",
                "success": False,
                "corrections": 0,
                "status_code": response.status_code
            }
    except Exception as e:
        return {
            "user_id": user_id,
            "request_num": request_num,
            "text": text,
            "response_time": 0,
            "cache_status": "error",
            "success": False,
            "corrections": 0,
            "error": str(e)
        }

def run_cache_test(num_users=50, requests_per_user=4):
    """Run cache effectiveness test"""
    
    print("🧪 AppenCorrect Cache Hit Rate Test")
    print("="*60)
    print(f"👥 Users: {num_users}")
    print(f"📝 Requests per user: {requests_per_user}")
    print(f"🎯 Total requests: {num_users * requests_per_user}")
    print(f"📚 Test texts: {len(TEST_TEXTS)} (repeated for cache hits)")
    print()
    
    results = []
    start_time = time.time()
    
    # Use ThreadPoolExecutor for concurrent requests
    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = []
        
        # Submit all requests
        for user_id in range(num_users):
            for req_num in range(requests_per_user):
                # Cycle through test texts to create cache hits
                text = TEST_TEXTS[req_num % len(TEST_TEXTS)]
                future = executor.submit(make_request, text, user_id, req_num)
                futures.append(future)
        
        # Collect results as they complete
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            
            if completed % 20 == 0:
                print(f"   Progress: {completed}/{len(futures)} requests completed")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Analyze results
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    # Group by response time ranges to identify cache hits
    fast_responses = [r for r in successful if r["response_time"] < 0.1]  # Likely cache hits
    medium_responses = [r for r in successful if 0.1 <= r["response_time"] < 1.0]
    slow_responses = [r for r in successful if r["response_time"] >= 1.0]
    
    # Calculate statistics
    if successful:
        response_times = [r["response_time"] for r in successful]
        avg_response = statistics.mean(response_times)
        median_response = statistics.median(response_times)
        min_response = min(response_times)
        max_response = max(response_times)
    else:
        avg_response = median_response = min_response = max_response = 0
    
    print()
    print("="*60)
    print("📊 CACHE HIT RATE TEST RESULTS")
    print("="*60)
    
    print(f"📊 Total Requests: {len(results)}")
    print(f"✅ Successful: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"📊 Success Rate: {len(successful)/len(results)*100:.1f}%")
    print()
    
    print("⚡ CACHE PERFORMANCE ANALYSIS:")
    print(f"🚀 Fast responses (<0.1s): {len(fast_responses)} ({len(fast_responses)/len(successful)*100:.1f}%)")
    print(f"🏃 Medium responses (0.1-1.0s): {len(medium_responses)} ({len(medium_responses)/len(successful)*100:.1f}%)")
    print(f"🐌 Slow responses (>1.0s): {len(slow_responses)} ({len(slow_responses)/len(successful)*100:.1f}%)")
    print()
    
    print("⏱️ RESPONSE TIME STATISTICS:")
    print(f"📊 Average: {avg_response:.3f}s")
    print(f"📊 Median: {median_response:.3f}s")
    print(f"📊 Min: {min_response:.3f}s")
    print(f"📊 Max: {max_response:.3f}s")
    print()
    
    print("🚀 THROUGHPUT:")
    print(f"📊 Total Time: {total_time:.1f}s")
    print(f"📊 Requests/second: {len(successful)/total_time:.1f}")
    print()
    
    print("💡 CACHE EFFECTIVENESS:")
    if len(fast_responses) > len(successful) * 0.3:
        print("🎉 EXCELLENT: High cache hit rate detected!")
    elif len(fast_responses) > len(successful) * 0.1:
        print("👍 GOOD: Moderate cache hit rate")
    else:
        print("⚠️ LIMITED: Low cache hit rate - check cache configuration")
    
    print()
    print("📋 DETAILED BREAKDOWN BY TEXT:")
    for i, text in enumerate(TEST_TEXTS):
        text_results = [r for r in successful if r["text"] == text]
        if text_results:
            text_times = [r["response_time"] for r in text_results]
            fast_count = len([r for r in text_results if r["response_time"] < 0.1])
            print(f"   Text {i+1}: {len(text_results)} requests, {fast_count} fast (<0.1s), avg: {statistics.mean(text_times):.3f}s")

if __name__ == "__main__":
    print("🔥 Starting Cache Hit Rate Test...")
    print("This test uses repeated content to demonstrate cache effectiveness")
    print()
    
    run_cache_test(num_users=30, requests_per_user=6)
    
    print()
    print("✅ Cache hit rate test completed!")
