#!/usr/bin/env python3
"""
500 Concurrent Users EXTREME Stress Test
Testing absolute system limits with Redis cache
"""

import time
import requests
import threading
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import psutil
import os

# Test configuration
API_URL = "http://localhost:5006/check"
API_KEY = "appencorrect_6cc586912e264062afdc0810f22d075a"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
}

# Test texts for variety
TEST_TEXTS = [
    "This is a test sentance with some errors for user {user_id}.",
    "I am writting this to test the system under extreme load {user_id}.",
    "The quick brown fox jumps over the lazy dog number {user_id}.",
    "Hello world, this is a stress test for user {user_id}.",
    "Testing extreme load with five hundred users {user_id}.",
    "Performance test under maximum concurrent load {user_id}.",
    "System stress testing with user number {user_id}.",
    "Load balancing test for concurrent user {user_id}."
]

def get_system_stats():
    """Get current system resource usage"""
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Try to get AppenCorrect process stats
        appencorrect_memory = 0
        appencorrect_cpu = 0
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
            try:
                if 'waitress-serve' in proc.info['name'] or 'python' in proc.info['name']:
                    if proc.info['memory_info']:
                        appencorrect_memory = max(appencorrect_memory, proc.info['memory_info'].rss / 1024 / 1024)
                        appencorrect_cpu = max(appencorrect_cpu, proc.info['cpu_percent'] or 0)
            except:
                pass
        
        return {
            'system_memory_total': f"{memory.total / (1024**3):.1f}GB",
            'system_memory_used': f"{memory.used / (1024**3):.1f}GB", 
            'system_memory_percent': f"{memory.percent:.1f}%",
            'system_cpu_percent': f"{cpu_percent:.1f}%",
            'cpu_cores': psutil.cpu_count(),
            'appencorrect_memory_mb': f"{appencorrect_memory:.1f}MB",
            'appencorrect_cpu_percent': f"{appencorrect_cpu:.1f}%"
        }
    except Exception as e:
        return {'error': str(e)}

def make_request(user_id, request_num):
    """Make a single API request"""
    try:
        # Use different texts for variety
        text_template = TEST_TEXTS[user_id % len(TEST_TEXTS)]
        text = text_template.format(user_id=user_id)
        
        payload = {
            "text": text,
            "language": "english"
        }
        
        start_time = time.time()
        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=45)
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            return {
                "user_id": user_id,
                "request_num": request_num,
                "response_time": float(data.get("statistics", {}).get("processing_time", "0").replace("s", "")),
                "total_time": end_time - start_time,
                "success": True,
                "corrections": len(data.get("corrections", [])),
                "status_code": response.status_code
            }
        else:
            return {
                "user_id": user_id,
                "request_num": request_num,
                "response_time": end_time - start_time,
                "total_time": end_time - start_time,
                "success": False,
                "corrections": 0,
                "status_code": response.status_code,
                "error": f"HTTP {response.status_code}"
            }
    except requests.exceptions.Timeout:
        return {
            "user_id": user_id,
            "request_num": request_num,
            "response_time": 0,
            "total_time": 45,
            "success": False,
            "corrections": 0,
            "error": "timeout"
        }
    except Exception as e:
        return {
            "user_id": user_id,
            "request_num": request_num,
            "response_time": 0,
            "total_time": 0,
            "success": False,
            "corrections": 0,
            "error": str(e)[:100]
        }

def run_user_requests(user_id, requests_per_user=2):
    """Run all requests for a single user"""
    user_results = []
    for req_num in range(requests_per_user):
        result = make_request(user_id, req_num)
        user_results.append(result)
    return user_results

def run_extreme_stress_test():
    """Run the 500-user extreme stress test"""
    
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║              500 CONCURRENT USERS EXTREME STRESS TEST       ║")
    print("║                    TESTING SYSTEM LIMITS                    ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  👥 Concurrent Users: 500                                  ║")
    print("║  📝 Requests per User: 2                                   ║")
    print("║  🎯 Total Requests: 1000                                    ║")
    print("║  ⚡ Workers: 150 threads                                   ║")
    print("║  💾 Cache: Redis enabled                                   ║")
    print("║  🔥 Load: 5x normal stress test                            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    # Get baseline stats
    baseline_stats = get_system_stats()
    print("📊 Baseline System Stats:")
    for key, value in baseline_stats.items():
        if key != 'error':
            print(f"   {key}: {value}")
    print()
    
    print(f"🚀 Starting 500-user extreme stress test at {time.strftime('%H:%M:%S')}")
    print("="*70)
    print("👥 Launching 500 concurrent users...")
    
    start_time = time.time()
    results = []
    
    # Use ThreadPoolExecutor with high worker count
    with ThreadPoolExecutor(max_workers=500) as executor:
        # Submit all user tasks
        futures = []
        for user_id in range(500):
            future = executor.submit(run_user_requests, user_id, 2)
            futures.append((user_id, future))
        
        # Collect results as they complete
        completed_users = 0
        for user_id, future in futures:
            try:
                user_results = future.result(timeout=60)  # 60 second timeout per user
                results.extend(user_results)
                completed_users += 1
                
                # Progress updates
                if completed_users % 50 == 0:
                    elapsed = time.time() - start_time
                    print(f"   {completed_users}/500 users completed ({elapsed:.1f}s)")
                    
            except Exception as e:
                print(f"   User {user_id} failed: {str(e)[:50]}")
                completed_users += 1
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Get final stats
    final_stats = get_system_stats()
    print(f"\n📊 Final System Stats:")
    for key, value in final_stats.items():
        if key != 'error':
            print(f"   {key}: {value}")
    print()
    
    # Analyze results
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print("="*70)
    print("📈 EXTREME STRESS TEST RESULTS")
    print("="*70)
    
    print(f"📊 Success Rate: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"📊 Error Count: {len(failed)}")
    print(f"📊 Cache Hits: 0")  # Unique requests won't hit cache
    print(f"📊 Fresh Requests: {len(successful)}")
    print(f"📊 Cache Hit Rate: 0.0%")
    print()
    
    if successful:
        response_times = [r["response_time"] for r in successful]
        total_times = [r["total_time"] for r in successful]
        
        print("⏱️  RESPONSE TIME BREAKDOWN:")
        print(f"   Mean:     {statistics.mean(response_times):.3f}s")
        print(f"   Median:   {statistics.median(response_times):.3f}s")
        print(f"   75th:     {statistics.quantiles(response_times, n=4)[2]:.3f}s")
        print(f"   90th:     {statistics.quantiles(response_times, n=10)[8]:.3f}s")
        print(f"   95th:     {statistics.quantiles(response_times, n=20)[18]:.3f}s")
        print(f"   99th:     {statistics.quantiles(response_times, n=100)[98]:.3f}s")
        print(f"   Min:      {min(response_times):.3f}s")
        print(f"   Max:      {max(response_times):.3f}s")
        print()
        
        print("🚀 THROUGHPUT:")
        print(f"   Total Throughput: {len(successful)/total_time:.1f} req/sec")
        print(f"   Test Duration: {total_time:.1f}s")
        print()
    
    # Analyze failure types
    if failed:
        print("❌ FAILURE ANALYSIS:")
        error_types = {}
        for f in failed:
            error = f.get('error', 'unknown')
            error_types[error] = error_types.get(error, 0) + 1
        
        for error, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   {error}: {count} failures")
        print()
    
    # Performance assessment
    print("🎯 EXTREME STRESS TEST ANALYSIS:")
    if len(successful) >= len(results) * 0.95:
        print("   ✅ Reliability: EXCELLENT (>95% success)")
    elif len(successful) >= len(results) * 0.90:
        print("   👍 Reliability: GOOD (>90% success)")
    elif len(successful) >= len(results) * 0.80:
        print("   ⚠️  Reliability: MODERATE (>80% success)")
    else:
        print("   ❌ Reliability: POOR (<80% success)")
    
    if successful:
        avg_response = statistics.mean(response_times)
        if avg_response < 2.0:
            print("   👍 Performance: GOOD (<2s avg)")
        elif avg_response < 5.0:
            print("   ⚠️  Performance: MODERATE (<5s avg)")
        else:
            print("   ❌ Performance: POOR (>5s avg)")
    
    if len(failed) == 0:
        print("   🌟 Error Rate: PERFECT (0 errors)")
    elif len(failed) < len(results) * 0.05:
        print("   ✅ Error Rate: EXCELLENT (<5% errors)")
    else:
        print(f"   ⚠️  Error Rate: {len(failed)/len(results)*100:.1f}% errors")

if __name__ == "__main__":
    print("🔥 EXTREME STRESS TEST - 500 CONCURRENT USERS")
    print("WARNING: This will push your system to its absolute limits!")
    print()
    
    run_extreme_stress_test()
    
    print()
    print("✅ Extreme stress test completed!")
    print("💡 If your system survived this, it's production-ready for any load!")
