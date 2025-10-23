#!/usr/bin/env python3
"""
Detailed Response Time Analysis for AppenCorrect Load Test

Gets precise percentile breakdowns and response time distributions.
"""

import asyncio
import aiohttp
import time
import statistics
import random

# Test configuration
API_KEY = "appencorrect_6cc586912e264062afdc0810f22d075a"
BASE_URL = "http://localhost:5006"
CONCURRENT_USERS = 100
REQUESTS_PER_USER = 3  # Shorter test for quick results
TOTAL_REQUESTS = CONCURRENT_USERS * REQUESTS_PER_USER

# Mix of sentences for realistic cache patterns
TEST_SENTENCES = [
    "This is a test sentance with some erors.",
    "The managment team needs to imporve there performace.", 
    "I beleive the systme is working perfecly now.",
    "Please reviw this documant for any mistaks.",
    "The analiysis shows that we need to optmize our proces.",
]

response_times = []
cache_pattern_times = []
fresh_request_times = []

async def make_request(session, user_id, request_id):
    """Make a single API request and track timing."""
    
    # Use repeated sentences to test cache effectiveness
    if request_id == 0:
        # First request per user - use same sentence to test cache
        sentence = TEST_SENTENCES[0]  # Everyone uses same sentence
        is_cache_test = True
    else:
        # Subsequent requests - mix of repeated and unique
        sentence = random.choice(TEST_SENTENCES)
        is_cache_test = False
    
    data = {
        "text": f"User{user_id}: {sentence}",
        "language": "english"
    }
    
    headers = {
        "Content-Type": "application/json", 
        "X-API-Key": API_KEY
    }
    
    start_time = time.time()
    
    try:
        async with session.post(f"{BASE_URL}/check", json=data, headers=headers, timeout=15) as response:
            end_time = time.time()
            response_time = end_time - start_time
            
            if response.status == 200:
                result = await response.json()
                processing_time = float(result.get('statistics', {}).get('processing_time', '0s').replace('s', ''))
                was_cached = processing_time < 0.1
                
                # Categorize timing
                response_times.append(response_time)
                
                if is_cache_test:
                    cache_pattern_times.append(response_time)
                    
                if processing_time > 0.3:  # Fresh AI request
                    fresh_request_times.append(response_time)
                
                return {
                    'success': True,
                    'response_time': response_time,
                    'processing_time': processing_time,
                    'cached': was_cached,
                    'corrections': len(result.get('corrections', []))
                }
            else:
                return {'success': False, 'response_time': response_time, 'status': response.status}
                
    except Exception as e:
        end_time = time.time()
        return {'success': False, 'response_time': end_time - start_time, 'error': str(e)}

async def simulate_user(session, user_id):
    """Simulate one user making requests."""
    results = []
    for request_id in range(REQUESTS_PER_USER):
        result = await make_request(session, user_id, request_id)
        results.append(result)
        await asyncio.sleep(0.05)  # Brief delay between requests
    return results

def calculate_percentiles(data):
    """Calculate detailed percentiles."""
    if not data:
        return {}
    
    sorted_data = sorted(data)
    n = len(sorted_data)
    
    percentiles = {}
    for p in [50, 75, 90, 95, 99, 99.5, 99.9]:
        if p == 50:
            percentiles[f'p{p}'] = statistics.median(sorted_data)
        else:
            index = int((p / 100) * n)
            if index >= n:
                index = n - 1
            percentiles[f'p{p}'] = sorted_data[index]
    
    percentiles['mean'] = statistics.mean(sorted_data)
    percentiles['min'] = min(sorted_data)
    percentiles['max'] = max(sorted_data)
    percentiles['std_dev'] = statistics.stdev(sorted_data) if len(sorted_data) > 1 else 0
    
    return percentiles

async def run_detailed_test():
    """Run focused test for detailed response time analysis."""
    
    print("🎯 Detailed Response Time Analysis")
    print("=" * 50)
    print(f"Concurrent Users: {CONCURRENT_USERS}")
    print(f"Requests per User: {REQUESTS_PER_USER}")  
    print(f"Total Requests: {TOTAL_REQUESTS}")
    print(f"Cache Pattern: First request per user uses same text")
    print()
    
    start_time = time.time()
    
    timeout = aiohttp.ClientTimeout(total=20)
    connector = aiohttp.TCPConnector(limit=120, limit_per_host=120)
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [simulate_user(session, user_id) for user_id in range(CONCURRENT_USERS)]
        
        print(f"🚀 Launching {CONCURRENT_USERS} concurrent users...")
        all_results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Flatten results
    flat_results = [result for user_results in all_results for result in user_results]
    successful_requests = [r for r in flat_results if r['success']]
    
    print(f"\n⏱️  Test completed in {total_time:.1f} seconds")
    print(f"✅ Success rate: {len(successful_requests)}/{len(flat_results)} ({len(successful_requests)/len(flat_results)*100:.1f}%)")
    
    # Calculate detailed percentiles
    all_times = response_times
    fresh_times = fresh_request_times
    cache_times = cache_pattern_times
    
    print("\n" + "=" * 60)
    print("📊 DETAILED RESPONSE TIME STATISTICS")
    print("=" * 60)
    
    if all_times:
        print("\n🌐 ALL REQUESTS:")
        all_stats = calculate_percentiles(all_times)
        print(f"   Mean:    {all_stats['mean']:.3f}s")
        print(f"   Median:  {all_stats['p50']:.3f}s") 
        print(f"   75th:    {all_stats['p75']:.3f}s")
        print(f"   90th:    {all_stats['p90']:.3f}s")
        print(f"   95th:    {all_stats['p95']:.3f}s")
        print(f"   99th:    {all_stats['p99']:.3f}s")
        print(f"   99.5th:  {all_stats['p99.5']:.3f}s")
        print(f"   99.9th:  {all_stats['p99.9']:.3f}s")
        print(f"   Min:     {all_stats['min']:.3f}s")
        print(f"   Max:     {all_stats['max']:.3f}s")
        print(f"   Std Dev: {all_stats['std_dev']:.3f}s")
    
    if fresh_times:
        print(f"\n🆕 FRESH AI REQUESTS ({len(fresh_times)} requests):")
        fresh_stats = calculate_percentiles(fresh_times)
        print(f"   Mean:    {fresh_stats['mean']:.3f}s")
        print(f"   90th:    {fresh_stats['p90']:.3f}s")
        print(f"   95th:    {fresh_stats['p95']:.3f}s")
        print(f"   99th:    {fresh_stats['p99']:.3f}s")
    
    if cache_times:
        print(f"\n⚡ CACHE PATTERN REQUESTS ({len(cache_times)} requests):")
        cache_stats = calculate_percentiles(cache_times)
        print(f"   Mean:    {cache_stats['mean']:.3f}s")
        print(f"   90th:    {cache_stats['p90']:.3f}s")
        print(f"   95th:    {cache_stats['p95']:.3f}s")
        print(f"   99th:    {cache_stats['p99']:.3f}s")
    
    print(f"\n📈 THROUGHPUT ANALYSIS:")
    print(f"   Total Throughput: {len(all_times)/total_time:.1f} req/sec")
    print(f"   Requests Completed: {len(successful_requests)}")
    print(f"   Test Duration: {total_time:.1f}s")
    
    return all_stats

if __name__ == "__main__":
    try:
        asyncio.run(run_detailed_test())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
