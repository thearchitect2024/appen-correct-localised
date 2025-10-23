#!/usr/bin/env python3
"""
100 Concurrent Users Load Test for AppenCorrect

Tests the performance of 50 workers + Redis cache with 100 concurrent users
making real text correction requests.
"""

import asyncio
import aiohttp
import time
import json
import statistics
import random
from datetime import datetime
import psutil
import os

# Test configuration
API_KEY = "appencorrect_6cc586912e264062afdc0810f22d075a"
BASE_URL = "http://localhost:5006"
CONCURRENT_USERS = 100
REQUESTS_PER_USER = 5
TOTAL_REQUESTS = CONCURRENT_USERS * REQUESTS_PER_USER

# Diverse test sentences with errors
TEST_SENTENCES = [
    "This is a test sentance with some erors.",
    "The managment team needs to imporve there performace.",
    "I beleive the systme is working perfecly now.",
    "Please reviw this documant for any mistaks.",
    "The analiysis shows that we need to optmize our proces.",
    "Your welcom to join the meating tommorow at 3pm.",
    "The new fetures will be avaliable next week.",
    "We apreciate your paitence during this maintenace.",
    "The recomendations were sucsesfully implemnted.",
    "This sentance has multipel erors that need corection.",
    "The performace improvemnts are significent.",
    "Please folow the instrucions carefuly.",
    "The databas conection is experincing some isues.",
    "We expct the problms to be resloved soon.",
    "The apliction is currntly undergong maintance.",
    "Your acount will be updtd automaticaly.",
    "Please contct support if you experince any problms.",
    "The schedul has been chaangd to acommodate evry one.",
    "This is exelent work with minmal erors.",
    "The technoligy stack incldes many powerfull tools."
]

# Cache test sentences (should be instant on repeat)
CACHE_TEST_SENTENCES = [
    "This exact sentence will test cache performance.",
    "Another sentence for cache hit testing.", 
    "Redis cache should make this super fast."
]

class LoadTestStats:
    def __init__(self):
        self.response_times = []
        self.cache_hits = 0
        self.errors = 0
        self.successful_requests = 0
        self.corrections_found = 0
        self.start_time = None
        self.end_time = None
        
    def add_result(self, response_time, was_successful, corrections_count=0, was_cached=False):
        self.response_times.append(response_time)
        if was_successful:
            self.successful_requests += 1
            self.corrections_found += corrections_count
            if was_cached:
                self.cache_hits += 1
        else:
            self.errors += 1
    
    def get_summary(self):
        if not self.response_times:
            return "No data collected"
        
        total_time = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        return {
            'total_requests': len(self.response_times),
            'successful_requests': self.successful_requests,
            'error_rate': f"{(self.errors/len(self.response_times)*100):.1f}%",
            'cache_hit_rate': f"{(self.cache_hits/self.successful_requests*100):.1f}%" if self.successful_requests > 0 else "0%",
            'total_corrections': self.corrections_found,
            'avg_response_time': f"{statistics.mean(self.response_times):.3f}s",
            'median_response_time': f"{statistics.median(self.response_times):.3f}s",
            'min_response_time': f"{min(self.response_times):.3f}s",
            'max_response_time': f"{max(self.response_times):.3f}s",
            'p95_response_time': f"{statistics.quantiles(self.response_times, n=20)[18]:.3f}s",
            'throughput': f"{len(self.response_times)/total_time:.1f}" if total_time > 0 else "0",
            'total_test_time': f"{total_time:.1f}s"
        }

async def make_request(session, user_id, request_id, sentence):
    """Make a single API request."""
    start_time = time.time()
    
    try:
        data = {
            "text": f"User {user_id} Request {request_id}: {sentence}",
            "language": "english"
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        
        async with session.post(f"{BASE_URL}/check", json=data, headers=headers, timeout=30) as response:
            end_time = time.time()
            response_time = end_time - start_time
            
            if response.status == 200:
                result = await response.json()
                corrections_count = len(result.get('corrections', []))
                processing_time = float(result.get('statistics', {}).get('processing_time', '0s').replace('s', ''))
                was_cached = processing_time < 0.1  # Cached responses are very fast
                
                return {
                    'success': True,
                    'response_time': response_time,
                    'corrections': corrections_count,
                    'cached': was_cached,
                    'processing_time': processing_time,
                    'user_id': user_id,
                    'request_id': request_id
                }
            else:
                return {
                    'success': False,
                    'response_time': response_time,
                    'status_code': response.status,
                    'user_id': user_id,
                    'request_id': request_id
                }
                
    except Exception as e:
        end_time = time.time()
        return {
            'success': False,
            'response_time': end_time - start_time,
            'error': str(e),
            'user_id': user_id,
            'request_id': request_id
        }

async def simulate_user(session, user_id, stats):
    """Simulate one user making multiple requests."""
    print(f"👤 Starting User {user_id}")
    
    for request_id in range(REQUESTS_PER_USER):
        # Mix of regular and cache test sentences
        if request_id == 0:
            # First request - use cache test sentence for predictable caching
            sentence = CACHE_TEST_SENTENCES[user_id % len(CACHE_TEST_SENTENCES)]
        else:
            # Regular requests with random sentences
            sentence = random.choice(TEST_SENTENCES)
        
        result = await make_request(session, user_id, request_id, sentence)
        
        stats.add_result(
            response_time=result['response_time'],
            was_successful=result['success'],
            corrections_count=result.get('corrections', 0),
            was_cached=result.get('cached', False)
        )
        
        # Brief delay between requests from same user
        await asyncio.sleep(0.1)
    
    print(f"✅ User {user_id} completed")

def get_system_stats():
    """Get current system resource usage."""
    # Get AppenCorrect process
    appencorrect_process = None
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'cpu_percent']):
        try:
            if 'app:app' in ' '.join(proc.info['cmdline']) and '5006' in ' '.join(proc.info['cmdline']):
                appencorrect_process = proc
                break
        except:
            continue
    
    memory = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=1)
    
    stats = {
        'system_memory_total': f"{memory.total / 1024**3:.1f}GB",
        'system_memory_used': f"{memory.used / 1024**3:.1f}GB",
        'system_memory_percent': f"{memory.percent:.1f}%",
        'system_cpu_percent': f"{cpu:.1f}%",
        'cpu_cores': psutil.cpu_count()
    }
    
    if appencorrect_process:
        try:
            app_memory = appencorrect_process.memory_info()
            stats.update({
                'appencorrect_memory_mb': f"{app_memory.rss / 1024**2:.1f}MB",
                'appencorrect_cpu_percent': f"{appencorrect_process.cpu_percent():.1f}%",
                'appencorrect_threads': appencorrect_process.num_threads(),
                'appencorrect_pid': appencorrect_process.pid
            })
        except:
            stats['appencorrect_status'] = 'Process info unavailable'
    else:
        stats['appencorrect_status'] = 'Process not found'
    
    return stats

async def run_load_test():
    """Run the complete load test."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                AppenCorrect Load Test                        ║
║             100 Concurrent Users + Redis Cache              ║
╠══════════════════════════════════════════════════════════════╣
║  👥 Concurrent Users: {CONCURRENT_USERS:<10}                            ║
║  📝 Requests per User: {REQUESTS_PER_USER:<10}                          ║
║  🎯 Total Requests: {TOTAL_REQUESTS:<10}                              ║
║  ⚡ Workers: 50 threads                                    ║
║  💾 Cache: Redis enabled                                   ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    stats = LoadTestStats()
    
    # Get baseline system stats
    print("📊 Baseline System Stats:")
    baseline_stats = get_system_stats()
    for key, value in baseline_stats.items():
        print(f"   {key}: {value}")
    
    print(f"\n🚀 Starting load test at {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    stats.start_time = time.time()
    
    # Create aiohttp session with proper limits
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(
        limit=150,  # Higher than concurrent users
        limit_per_host=150,
        keepalive_timeout=30
    )
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        # Create tasks for all users
        tasks = []
        for user_id in range(CONCURRENT_USERS):
            task = simulate_user(session, user_id, stats)
            tasks.append(task)
        
        # Run all users concurrently
        print(f"👥 Launching {CONCURRENT_USERS} concurrent users...")
        
        # Monitor progress
        completed = 0
        start_monitoring = time.time()
        
        for completed_task in asyncio.as_completed(tasks):
            await completed_task
            completed += 1
            
            # Progress updates every 20 users
            if completed % 20 == 0 or completed == CONCURRENT_USERS:
                elapsed = time.time() - start_monitoring
                print(f"   Progress: {completed}/{CONCURRENT_USERS} users completed ({elapsed:.1f}s)")
    
    stats.end_time = time.time()
    
    # Get final system stats
    print("\n📊 Final System Stats:")
    final_stats = get_system_stats()
    for key, value in final_stats.items():
        print(f"   {key}: {value}")
    
    # Print comprehensive results
    print("\n" + "=" * 60)
    print("📈 LOAD TEST RESULTS")
    print("=" * 60)
    
    summary = stats.get_summary()
    for key, value in summary.items():
        print(f"📊 {key.replace('_', ' ').title()}: {value}")
    
    print(f"\n🎯 Performance Analysis:")
    
    # Calculate cache effectiveness
    cache_rate = float(summary['cache_hit_rate'].replace('%', ''))
    print(f"   Cache Effectiveness: {cache_rate:.1f}% hit rate")
    
    # Throughput analysis
    throughput = float(summary['throughput'])
    print(f"   System Throughput: {throughput:.1f} requests/second")
    
    # Response time analysis
    avg_time = float(summary['avg_response_time'].replace('s', ''))
    if avg_time < 0.1:
        print(f"   Response Speed: 🚀 EXCELLENT (<0.1s average)")
    elif avg_time < 0.5:
        print(f"   Response Speed: ✅ VERY GOOD (<0.5s average)")
    elif avg_time < 1.0:
        print(f"   Response Speed: 👍 GOOD (<1s average)")
    else:
        print(f"   Response Speed: ⚠️ NEEDS OPTIMIZATION (>1s average)")
    
    # Error rate analysis
    error_rate = float(summary['error_rate'].replace('%', ''))
    if error_rate < 1:
        print(f"   Reliability: 🌟 EXCELLENT (<1% errors)")
    elif error_rate < 5:
        print(f"   Reliability: ✅ GOOD (<5% errors)")
    else:
        print(f"   Reliability: ⚠️ NEEDS ATTENTION ({error_rate}% errors)")
    
    # Memory analysis
    app_memory = final_stats.get('appencorrect_memory_mb', '0MB').replace('MB', '')
    try:
        memory_mb = float(app_memory)
        if memory_mb < 500:
            print(f"   Memory Usage: ✅ EFFICIENT ({memory_mb:.1f}MB)")
        elif memory_mb < 1000:
            print(f"   Memory Usage: 👍 ACCEPTABLE ({memory_mb:.1f}MB)")
        else:
            print(f"   Memory Usage: ⚠️ HIGH ({memory_mb:.1f}MB)")
    except:
        print(f"   Memory Usage: {app_memory}")
    
    print(f"\n💡 Recommendations:")
    if throughput > 50:
        print(f"   🎉 Excellent throughput! System can handle high load")
    elif throughput > 20:
        print(f"   👍 Good throughput for current hardware")
    else:
        print(f"   ⚠️ Consider optimizing or upgrading hardware")
    
    if cache_rate > 70:
        print(f"   🚀 Cache working excellently! Major cost savings")
    elif cache_rate > 30:
        print(f"   👍 Cache providing good benefits")
    else:
        print(f"   💡 Cache hit rate could be improved")
    
    return summary

if __name__ == "__main__":
    print("🧪 AppenCorrect 100-User Load Test")
    print("Testing 50 workers + Redis cache performance")
    print()
    
    try:
        # Run the async load test
        results = asyncio.run(run_load_test())
        print("\n✅ Load test completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Load test interrupted by user")
    except Exception as e:
        print(f"\n❌ Load test failed: {e}")
        import traceback
        traceback.print_exc()
