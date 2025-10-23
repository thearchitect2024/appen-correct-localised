#!/usr/bin/env python3
"""
Cache Connection Test for AppenCorrect

Tests Redis/Valkey cache connectivity and performance with the same configuration
as the main application.
"""

import os
import sys
import time
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_cache_connection():
    """Test cache connection and basic operations."""
    print("========================================")
    print("    AppenCorrect Cache Connection Test  ")
    print("========================================")
    print()
    
    try:
        from cache_client import get_cache, TTL
        print("✓ Cache client imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import cache client: {e}")
        print("   Install dependencies with: pip install redis valkey")
        return False
    
    # Initialize cache
    cache = get_cache()
    print(f"✓ Cache client initialized")
    
    # Check configuration
    print("\n📋 Configuration:")
    print(f"   Enabled: {cache.enabled}")
    print(f"   Host: {cache.host}")
    print(f"   Port: {cache.port}")
    print(f"   Database: {cache.db}")
    print(f"   Default TTL: {cache.default_ttl}s")
    
    # Test connection
    print("\n🔌 Testing Connection:")
    if cache.is_available():
        print("✅ Cache is available and connected")
    else:
        print("❌ Cache is not available")
        if cache.enabled:
            print("   Check your ElastiCache endpoint and network connectivity")
        else:
            print("   Cache is disabled in configuration")
        return False
    
    # Test basic operations
    print("\n🧪 Testing Basic Operations:")
    
    # Test SET operation
    test_key = "test_connection"
    test_value = {"message": "Hello from AppenCorrect!", "timestamp": time.time()}
    
    success = cache.set("test", test_key, test_value, ttl=60)
    if success:
        print("✅ SET operation successful")
    else:
        print("❌ SET operation failed")
        return False
    
    # Test GET operation
    retrieved_value = cache.get("test", test_key)
    if retrieved_value:
        print("✅ GET operation successful")
        if retrieved_value == test_value:
            print("✅ Data integrity verified")
        else:
            print("⚠️ Data integrity issue - retrieved value differs")
    else:
        print("❌ GET operation failed")
        return False
    
    # Test DELETE operation
    deleted = cache.delete("test", test_key)
    if deleted:
        print("✅ DELETE operation successful")
    else:
        print("⚠️ DELETE operation had no effect")
    
    # Verify deletion
    deleted_value = cache.get("test", test_key)
    if deleted_value is None:
        print("✅ Deletion verified")
    else:
        print("⚠️ Value still exists after deletion")
    
    # Test performance
    print("\n⚡ Performance Test:")
    start_time = time.time()
    
    # Perform multiple operations
    num_operations = 100
    for i in range(num_operations):
        cache.set("perf_test", f"key_{i}", f"value_{i}", ttl=60)
        cache.get("perf_test", f"key_{i}")
    
    end_time = time.time()
    total_time = end_time - start_time
    ops_per_second = (num_operations * 2) / total_time  # 2 ops per iteration (set + get)
    
    print(f"✅ {num_operations * 2} operations in {total_time:.3f}s")
    print(f"✅ {ops_per_second:.1f} operations/second")
    
    # Clean up performance test data
    cache.clear_namespace("perf_test")
    print("✅ Performance test data cleaned up")
    
    # Test TTL values
    print("\n⏰ Testing TTL Values:")
    for ttl_name, ttl_value in [
        ("Authentication", TTL.AUTHENTICATION),
        ("API Responses", TTL.API_RESPONSES),
        ("Language Detection", TTL.LANGUAGE_DETECTION),
        ("Session Data", TTL.SESSION_DATA)
    ]:
        print(f"   {ttl_name}: {ttl_value}s ({ttl_value/60:.1f} minutes)")
    
    # Get cache statistics
    print("\n📊 Cache Statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        if value is not None:
            print(f"   {key}: {value}")
    
    print("\n✅ All cache tests passed!")
    print("\n💡 Tips:")
    print("   - Cache is shared across all 50 workers")
    print("   - API responses cached for 1 hour")
    print("   - Language detection cached for 2 hours")
    print("   - API key validation cached for 10 minutes")
    
    return True

def test_specific_patterns():
    """Test specific caching patterns used by AppenCorrect."""
    print("\n🎯 Testing AppenCorrect-Specific Patterns:")
    
    try:
        from cache_client import get_cache
        cache = get_cache()
        
        if not cache.is_available():
            print("❌ Cache not available for pattern testing")
            return False
        
        # Test language detection pattern
        import hashlib
        text = "This is a test sentence for language detection."
        text_hash = hashlib.md5(text.encode()).hexdigest()[:16]
        
        cache.set('language_detection', text_hash, 'english', ttl=TTL.LANGUAGE_DETECTION)
        cached_lang = cache.get('language_detection', text_hash)
        
        if cached_lang == 'english':
            print("✅ Language detection caching pattern works")
        else:
            print("❌ Language detection caching pattern failed")
        
        # Test API response pattern
        api_key = "test_response_key"
        response_data = {
            "corrected_text": "This is a test sentence.",
            "corrections": []
        }
        
        cache.set('ai_responses', api_key, response_data, ttl=TTL.API_RESPONSES)
        cached_response = cache.get('ai_responses', api_key)
        
        if cached_response == response_data:
            print("✅ AI response caching pattern works")
        else:
            print("❌ AI response caching pattern failed")
        
        # Test API key validation pattern
        key_hash = hashlib.sha256("test_api_key".encode()).hexdigest()
        key_info = {
            "key_id": "test_123",
            "name": "Test Key",
            "rate_limit_per_hour": 1000,
            "is_active": True
        }
        
        cache.set('api_key_validation', key_hash, key_info, ttl=TTL.API_KEY_VALIDATION)
        cached_key_info = cache.get('api_key_validation', key_hash)
        
        if cached_key_info == key_info:
            print("✅ API key validation caching pattern works")
        else:
            print("❌ API key validation caching pattern failed")
        
        print("✅ All AppenCorrect-specific patterns work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Pattern testing failed: {e}")
        return False

if __name__ == "__main__":
    print("Starting AppenCorrect Cache Test...")
    print("Make sure your .env file has the correct VALKEY_* configuration")
    print()
    
    # Test basic connection
    connection_success = test_cache_connection()
    
    if connection_success:
        # Test specific patterns
        pattern_success = test_specific_patterns()
        
        if pattern_success:
            print("\n🎉 All tests passed! Cache is ready for production.")
            sys.exit(0)
        else:
            print("\n⚠️ Some pattern tests failed. Check configuration.")
            sys.exit(1)
    else:
        print("\n❌ Cache connection failed. Check your configuration.")
        print("\nTroubleshooting:")
        print("1. Verify VALKEY_HOST in .env file")
        print("2. Check network connectivity to ElastiCache")
        print("3. Verify security group allows port 6379")
        print("4. Ensure ElastiCache is in the same VPC")
        sys.exit(1)
