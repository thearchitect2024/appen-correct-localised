#!/usr/bin/env python3
"""
Test connection to new ElastiCache instance
Usage: python3 test_new_cache.py YOUR-NEW-ENDPOINT.cache.amazonaws.com
"""

import sys
import os
sys.path.append('/home/ec2-user/apps/AppenCorrect')

def test_redis_connection(host):
    """Test connection to Redis/ElastiCache"""
    print(f"🔌 Testing connection to: {host}")
    print("=" * 50)
    
    # Set environment variables
    os.environ['VALKEY_HOST'] = host
    os.environ['VALKEY_PORT'] = '6379'
    os.environ['VALKEY_DB'] = '0'
    os.environ['VALKEY_ENABLED'] = 'true'
    
    try:
        from cache_client import CacheClient
        
        # Initialize cache client
        cache = CacheClient()
        
        print(f"✓ Cache client initialized")
        print(f"  Host: {cache.host}")
        print(f"  Port: {cache.port}")
        print(f"  Database: {cache.db}")
        print(f"  Connected: {cache.connected}")
        
        if cache.connected:
            print("\n🧪 Running cache tests...")
            
            # Test SET
            test_key = "test:connection"
            test_value = "Hello from AppenCorrect!"
            
            result = cache.set("test", test_key, test_value, ttl=60)
            if result:
                print("✅ SET operation successful")
            else:
                print("❌ SET operation failed")
                return False
            
            # Test GET
            retrieved = cache.get("test", test_key)
            if retrieved == test_value:
                print("✅ GET operation successful")
                print(f"   Retrieved: {retrieved}")
            else:
                print("❌ GET operation failed")
                print(f"   Expected: {test_value}")
                print(f"   Got: {retrieved}")
                return False
            
            # Test DELETE
            deleted = cache.delete("test", test_key)
            if deleted:
                print("✅ DELETE operation successful")
            else:
                print("⚠️  DELETE operation failed (key might not exist)")
            
            # Test stats
            try:
                stats = cache.get_stats()
                print(f"\n📊 Cache Statistics:")
                print(f"   Available: {stats.get('available', 'Unknown')}")
                print(f"   Connected: {stats.get('connected', 'Unknown')}")
                if 'hit_rate' in stats:
                    print(f"   Hit Rate: {stats['hit_rate']:.1f}%")
            except Exception as e:
                print(f"⚠️  Could not get stats: {e}")
            
            print("\n🎉 All tests passed! ElastiCache is ready for AppenCorrect!")
            return True
            
        else:
            print("❌ Cache not connected")
            print("\n🔧 Troubleshooting:")
            print("1. Check security group allows port 6379")
            print("2. Verify ElastiCache is in same VPC")
            print("3. Ensure subnet group includes current subnet")
            return False
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Verify the endpoint URL is correct")
        print("2. Check network connectivity")
        print("3. Ensure ElastiCache is running")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 test_new_cache.py YOUR-ENDPOINT.cache.amazonaws.com")
        print("Example: python3 test_new_cache.py appencorrect-redis.abc123.cache.amazonaws.com")
        sys.exit(1)
    
    endpoint = sys.argv[1]
    success = test_redis_connection(endpoint)
    
    if success:
        print(f"\n✅ Ready to update .env with:")
        print(f"VALKEY_HOST={endpoint}")
        print(f"VALKEY_PORT=6379")
        print(f"VALKEY_DB=0")
        print(f"VALKEY_ENABLED=true")
    else:
        print("\n❌ Fix the connection issues before proceeding")
        sys.exit(1)
