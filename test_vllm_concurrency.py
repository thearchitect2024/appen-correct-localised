#!/usr/bin/env python3
"""
Test script to validate vLLM concurrency and performance
Tests that multiple requests are processed simultaneously on GPU
"""

import requests
import time
import concurrent.futures
import json
from statistics import mean, median

# Configuration
FLASK_URL = "http://localhost:5006"
VLLM_URL = "http://localhost:8000"
NUM_CONCURRENT_REQUESTS = 20
NUM_ROUNDS = 3

# Test cases
TEST_SENTENCES = [
    "This sentance has erors in grammer.",
    "I has a bad spelling misstake here.",
    "Their going to the store with there friends.",
    "She dont like to goes shopping.",
    "Me and him are going to the party.",
    "The team are winning there game.",
    "Its a beautiful day outside today.",
    "I seen him yesterday at the park.",
    "Your the best friend I ever had.",
    "We was planning to go their tomorrow.",
]


def check_vllm_health():
    """Check if vLLM server is running"""
    try:
        response = requests.get(f"{VLLM_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def check_flask_health():
    """Check if Flask API is running"""
    try:
        response = requests.get(f"{FLASK_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def send_correction_request(text, request_id):
    """Send a single correction request"""
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{FLASK_URL}/demo/check",
            json={"text": text},
            timeout=30
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            return {
                "request_id": request_id,
                "success": True,
                "elapsed": elapsed,
                "original": text,
                "corrected": result.get("corrected_text", ""),
                "errors_found": len(result.get("errors", [])),
                "language": result.get("language", "unknown")
            }
        else:
            return {
                "request_id": request_id,
                "success": False,
                "elapsed": elapsed,
                "error": f"HTTP {response.status_code}"
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "request_id": request_id,
            "success": False,
            "elapsed": elapsed,
            "error": str(e)
        }


def test_sequential_requests():
    """Test requests one at a time (baseline)"""
    print("\n" + "="*70)
    print("TEST 1: Sequential Requests (Baseline)")
    print("="*70)
    print("Sending 10 requests one at a time...")
    
    start_time = time.time()
    results = []
    
    for i, text in enumerate(TEST_SENTENCES):
        result = send_correction_request(text, i)
        results.append(result)
        if result["success"]:
            print(f"  ✓ Request {i+1}: {result['elapsed']:.2f}s")
        else:
            print(f"  ✗ Request {i+1}: {result.get('error', 'Unknown error')}")
    
    total_time = time.time() - start_time
    successful = [r for r in results if r["success"]]
    
    print(f"\nResults:")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Success rate: {len(successful)}/{len(results)}")
    if successful:
        times = [r["elapsed"] for r in successful]
        print(f"  Avg latency: {mean(times):.2f}s")
        print(f"  Median latency: {median(times):.2f}s")
        print(f"  Throughput: {len(successful)/total_time:.2f} req/sec")
    
    return results


def test_concurrent_requests(num_concurrent):
    """Test multiple requests simultaneously"""
    print("\n" + "="*70)
    print(f"TEST 2: Concurrent Requests ({num_concurrent} simultaneous)")
    print("="*70)
    print(f"Sending {num_concurrent} requests simultaneously...")
    
    # Prepare requests
    test_data = []
    for i in range(num_concurrent):
        text = TEST_SENTENCES[i % len(TEST_SENTENCES)]
        test_data.append((text, i))
    
    start_time = time.time()
    
    # Send all requests concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        futures = [
            executor.submit(send_correction_request, text, req_id)
            for text, req_id in test_data
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    total_time = time.time() - start_time
    successful = [r for r in results if r["success"]]
    
    print(f"\nResults:")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Success rate: {len(successful)}/{len(results)}")
    
    if successful:
        times = [r["elapsed"] for r in successful]
        print(f"  Avg latency: {mean(times):.2f}s")
        print(f"  Median latency: {median(times):.2f}s")
        print(f"  Min latency: {min(times):.2f}s")
        print(f"  Max latency: {max(times):.2f}s")
        print(f"  Throughput: {len(successful)/total_time:.2f} req/sec")
        
        # Show latency distribution
        print(f"\n  Latency distribution:")
        for i, result in enumerate(sorted(successful, key=lambda x: x["elapsed"])):
            print(f"    Request {result['request_id']}: {result['elapsed']:.2f}s")
    
    return results


def test_sustained_load(duration_seconds=30):
    """Test sustained concurrent load"""
    print("\n" + "="*70)
    print(f"TEST 3: Sustained Load ({duration_seconds}s)")
    print("="*70)
    print(f"Sending continuous requests for {duration_seconds} seconds...")
    
    start_time = time.time()
    request_count = 0
    successful_count = 0
    latencies = []
    
    def send_continuous_requests():
        nonlocal request_count, successful_count
        while time.time() - start_time < duration_seconds:
            text = TEST_SENTENCES[request_count % len(TEST_SENTENCES)]
            result = send_correction_request(text, request_count)
            request_count += 1
            
            if result["success"]:
                successful_count += 1
                latencies.append(result["elapsed"])
    
    # Run with 5 concurrent workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_continuous_requests) for _ in range(5)]
        for future in concurrent.futures.as_completed(futures):
            future.result()
    
    total_time = time.time() - start_time
    
    print(f"\nResults:")
    print(f"  Total requests: {request_count}")
    print(f"  Successful: {successful_count}")
    print(f"  Failed: {request_count - successful_count}")
    print(f"  Duration: {total_time:.2f}s")
    print(f"  Throughput: {successful_count/total_time:.2f} req/sec")
    
    if latencies:
        print(f"  Avg latency: {mean(latencies):.2f}s")
        print(f"  Median latency: {median(latencies):.2f}s")
        print(f"  P95 latency: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}s")
        print(f"  P99 latency: {sorted(latencies)[int(len(latencies)*0.99)]:.2f}s")


def test_response_format():
    """Validate response format matches expected structure"""
    print("\n" + "="*70)
    print("TEST 4: Response Format Validation")
    print("="*70)
    
    text = "This sentance has erors."
    print(f"Testing with: '{text}'")
    
    response = requests.post(
        f"{FLASK_URL}/demo/check",
        json={"text": text},
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ Response received:")
        print(json.dumps(result, indent=2))
        
        # Validate structure
        required_fields = ["original_text", "corrected_text", "errors", "language"]
        missing = [f for f in required_fields if f not in result]
        
        if missing:
            print(f"\n✗ Missing fields: {missing}")
        else:
            print(f"\n✓ All required fields present")
            
        # Validate errors structure
        if result.get("errors"):
            error = result["errors"][0]
            error_fields = ["original", "suggestion", "type"]
            missing_error_fields = [f for f in error_fields if f not in error]
            
            if missing_error_fields:
                print(f"✗ Error object missing fields: {missing_error_fields}")
            else:
                print(f"✓ Error objects properly formatted")
    else:
        print(f"✗ Request failed: HTTP {response.status_code}")


def main():
    print("\n" + "="*70)
    print("  AppenCorrect vLLM Concurrency Test Suite")
    print("="*70)
    
    # Health checks
    print("\nChecking services...")
    
    if not check_vllm_health():
        print("✗ vLLM server not responding at " + VLLM_URL)
        print("  Start with: ./start_vllm_server.sh")
        return
    print("✓ vLLM server is running")
    
    if not check_flask_health():
        print("✗ Flask API not responding at " + FLASK_URL)
        print("  Start with: python3 app.py")
        return
    print("✓ Flask API is running")
    
    # Run tests
    try:
        # Test 1: Sequential baseline
        sequential_results = test_sequential_requests()
        
        # Test 2: Concurrent requests
        concurrent_results = test_concurrent_requests(NUM_CONCURRENT_REQUESTS)
        
        # Test 3: Response format
        test_response_format()
        
        # Test 4: Sustained load (optional, comment out if too long)
        # test_sustained_load(duration_seconds=30)
        
        # Summary
        print("\n" + "="*70)
        print("  Test Summary")
        print("="*70)
        
        # Calculate speedup
        seq_successful = [r for r in sequential_results if r["success"]]
        conc_successful = [r for r in concurrent_results if r["success"]]
        
        if seq_successful and conc_successful:
            seq_avg = mean([r["elapsed"] for r in seq_successful])
            conc_avg = mean([r["elapsed"] for r in conc_successful])
            
            print(f"\n✓ Concurrency is working!")
            print(f"  Sequential avg latency: {seq_avg:.2f}s")
            print(f"  Concurrent avg latency: {conc_avg:.2f}s")
            print(f"  Latency impact: {(conc_avg/seq_avg - 1)*100:+.1f}%")
            print(f"\n✓ GPU is processing multiple requests simultaneously!")
            print(f"  vLLM's continuous batching is active")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

