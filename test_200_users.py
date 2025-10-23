#!/usr/bin/env python3
"""
200 Concurrent Users Stress Test for AppenCorrect
Tests the limits of 50 workers + Redis cache
"""

import asyncio
import aiohttp
import time
import statistics
import random
import psutil

# Test configuration
API_KEY = "appencorrect_6cc586912e264062afdc0810f22d075a"
BASE_URL = "http://localhost:5006"
CONCURRENT_USERS = 200
REQUESTS_PER_USER = 2  # Keep test manageable
TOTAL_REQUESTS = CONCURRENT_USERS * REQUESTS_PER_USER

# Test sentences with mix of cache opportunities
TEST_SENTENCES = [
    "This is a test sentance with erors.",      # Repeated for cache hits
    "The managment team needs to imporve.",      # Repeated for cache hits
    "Cache test with differnt erors here.",      # Repeated for cache hits
    "Please reviw this documant for mistaks.",
    "The analiysis shows optmization needed.",
    "Your welcom to join the meating tommorow.",
    "The new fetures will be avaliable soon.",
    "We apreciate your paitence during maintenace.",
    "This sentance has multipel erors to fix.",
    "The performace improvemnts are significent.",
]

response_times = []
errors = []
cache_hits = 0
fresh_requests = 0

async def make_request(session, user_id, request_id):
    """Make a single API request with detailed tracking."""
    
    # First 50 users use repeated sentences for cache testing
    if user_id < 50:
        sentence = TEST_SENTENCES[user_id % 3]  # Repeat first 3 sentences
    else:
        sentence = random.choice(TEST_SENTENCES)
    
    data = {
        "text": f"User{user_id}R{request_id}: {sentence}",
        "language": "english"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    start_time = time.time()
    
    try:
        async with session.post(f"{BASE_URL}/check", json=data, headers=headers, timeout=20) as response:
            end_time = time.time()
            response_time = end_time - start_time
            
            if response.status == 200:
                result = await response.json()
                processing_time = float(result.get('statistics', {}).get('processing_time', '0s').replace('s', ''))
                
                # Track cache vs fresh
                global cache_hits, fresh_requests
                if processing_time < 0.1:
                    cache_hits += 1
                else:
                    fresh_requests += 1
                
                response_times.append(response_time)
                
                return {
                    'success': True,
                    'response_time': response_time,
                    'processing_time': processing_time,
                    'corrections': len(result.get('corrections', [])),
                    'user_id': user_id
                }
            else:
                errors.append({'user_id': user_id, 'status': response.status, 'time': response_time})
                return {'success': False, 'status': response.status, 'response_time': response_time}
                
    except asyncio.TimeoutError:
        end_time = time.time()
        response_time = end_time - start_time
        errors.append({'user_id': user_id, 'error': 'timeout', 'time': response_time})
        return {'success': False, 'error': 'timeout', 'response_time': response_time}
    except Exception as e:
        end_time = time.time()
        response_time = end_time - start_time
        errors.append({'user_id': user_id, 'error': str(e), 'time': response_time})
        return {'success': False, 'error': str(e), 'response_time': response_time}

async def simulate_user(session, user_id):
    """Simulate one user making requests."""
    results = []
    for request_id in range(REQUESTS_PER_USER):
        result = await make_request(session, user_id, request_id)
        results.append(result)
        await asyncio.sleep(0.1)  # Brief delay between user's requests
    return results

def get_memory_stats():
    """Get current memory usage."""
    memory = psutil.virtual_memory()
    
    # Find AppenCorrect process
    app_memory = "Unknown"
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
        try:
            if 'app:app' in ' '.join(proc.info['cmdline']) and '5006' in ' '.join(proc.info['cmdline']):
                app_memory = f"{proc.info['memory_info'].rss / 1024**2:.1f}MB"
                break
        except:
            continue
    
    return {
        'system_memory_used': f"{memory.used / 1024**3:.1f}GB",
        'system_memory_percent': f"{memory.percent:.1f}%",
        'appencorrect_memory': app_memory
    }

async def run_200_user_test():
    """Run 200 concurrent user test."""
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              200 CONCURRENT USERS STRESS TEST               ║
║                  Testing System Limits                      ║
╠══════════════════════════════════════════════════════════════╣
║  👥 Concurrent Users: {CONCURRENT_USERS:<10}                           ║
║  📝 Requests per User: {REQUESTS_PER_USER:<10}                          ║  
║  🎯 Total Requests: {TOTAL_REQUESTS:<10}                              ║
║  ⚡ Workers: 50 threads                                    ║
║  💾 Cache: Redis enabled                                   ║
║  🔥 Load: 2x previous test                                 ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    print("📊 Baseline Memory:")
    baseline = get_memory_stats()
    for key, value in baseline.items():
        print(f"   {key}: {value}")
    
    print(f"\n🚀 Starting 200-user test at {time.strftime('%H:%M:%S')}")
    print("=" * 60)
    
    start_time = time.time()
    
    # Larger connection limits for 200 users
    timeout = aiohttp.ClientTimeout(total=25)
    connector = aiohttp.TCPConnector(
        limit=250,
        limit_per_host=250,
        keepalive_timeout=30
    )
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [simulate_user(session, user_id) for user_id in range(CONCURRENT_USERS)]
        
        print(f"👥 Launching {CONCURRENT_USERS} concurrent users...")
        
        # Monitor progress every 50 completions
        completed = 0
        for completed_task in asyncio.as_completed(tasks):
            await completed_task
            completed += 1
            
            if completed % 50 == 0:
                elapsed = time.time() - start_time
                print(f"   {completed}/{CONCURRENT_USERS} users completed ({elapsed:.1f}s)")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n📊 Final Memory:")
    final = get_memory_stats()
    for key, value in final.items():
        print(f"   {key}: {value}")
    
    # Calculate detailed statistics
    print("\n" + "=" * 60)
    print("📈 200-USER STRESS TEST RESULTS")
    print("=" * 60)
    
    successful_requests = len(response_times)
    total_attempts = TOTAL_REQUESTS
    
    print(f"📊 Success Rate: {successful_requests}/{total_attempts} ({successful_requests/total_attempts*100:.1f}%)")
    print(f"📊 Error Count: {len(errors)}")
    print(f"📊 Cache Hits: {cache_hits}")
    print(f"📊 Fresh Requests: {fresh_requests}")
    print(f"📊 Cache Hit Rate: {cache_hits/(cache_hits+fresh_requests)*100:.1f}%" if cache_hits+fresh_requests > 0 else "0%")
    
    if response_times:
        sorted_times = sorted(response_times)
        n = len(sorted_times)
        
        print(f"\n⏱️  RESPONSE TIME BREAKDOWN:")
        print(f"   Mean:     {statistics.mean(sorted_times):.3f}s")
        print(f"   Median:   {statistics.median(sorted_times):.3f}s")
        
        # Calculate precise percentiles
        for p in [75, 90, 95, 99]:
            index = int((p / 100) * n)
            if index >= n:
                index = n - 1
            print(f"   {p}th:     {sorted_times[index]:.3f}s")
        
        print(f"   Min:      {min(sorted_times):.3f}s")
        print(f"   Max:      {max(sorted_times):.3f}s")
    
    print(f"\n🚀 THROUGHPUT:")
    print(f"   Total Throughput: {successful_requests/total_time:.1f} req/sec")
    print(f"   Test Duration: {total_time:.1f}s")
    
    # Analysis
    success_rate = successful_requests/total_attempts*100
    avg_time = statistics.mean(sorted_times) if sorted_times else 0
    
    print(f"\n🎯 STRESS TEST ANALYSIS:")
    if success_rate >= 95:
        print(f"   ✅ Reliability: EXCELLENT ({success_rate:.1f}% success)")
    elif success_rate >= 90:
        print(f"   👍 Reliability: GOOD ({success_rate:.1f}% success)")
    else:
        print(f"   ⚠️ Reliability: STRESSED ({success_rate:.1f}% success)")
    
    if avg_time < 3:
        print(f"   🚀 Performance: EXCELLENT ({avg_time:.1f}s avg)")
    elif avg_time < 6:
        print(f"   👍 Performance: GOOD ({avg_time:.1f}s avg)")
    else:
        print(f"   ⚠️ Performance: STRESSED ({avg_time:.1f}s avg)")
    
    if len(errors) == 0:
        print(f"   🌟 Error Rate: PERFECT (0 errors)")
    elif len(errors) < 10:
        print(f"   ✅ Error Rate: LOW ({len(errors)} errors)")
    else:
        print(f"   ⚠️ Error Rate: HIGH ({len(errors)} errors)")

if __name__ == "__main__":
    try:
        asyncio.run(run_200_user_test())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
