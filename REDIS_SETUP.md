# Redis/Valkey Cache Setup for AppenCorrect

This guide walks you through setting up high-performance Redis/Valkey caching with 50 workers for AppenCorrect.

## 🚀 Performance Improvements

With Redis cache and 50 workers, you'll see:
- **10-15x faster** response times for cached requests
- **50x concurrent** request handling capacity  
- **Cross-worker** cache sharing (no duplicate AI calls)
- **Reduced API costs** through intelligent caching

## 📋 Prerequisites

- AppenCorrect application already installed
- Access to Redis instance at private IP: `10.0.16.112`
- Python environment with write access

## 🔧 Installation Steps

### 1. Install Cache Dependencies

```bash
cd /home/ec2-user/apps/AppenCorrect
pip install redis==5.0.1 valkey==5.0.8
```

### 2. Configure Environment Variables

Edit your `.env` file (create from `env.example` if needed):

```bash
cp env.example .env
```

Add these Redis/Valkey configuration settings to `.env`:

```env
# Performance Configuration
WORKERS=50
TIMEOUT=30
MAX_REQUESTS=1000
MAX_REQUESTS_JITTER=50

# Redis/Valkey Cache Configuration
VALKEY_HOST=autoai-correct-0g4w6b.serverless.usw2.cache.amazonaws.com
VALKEY_PORT=6379
VALKEY_DB=0
VALKEY_PASSWORD=
VALKEY_SSL=false
VALKEY_ENABLED=true
VALKEY_DEFAULT_TTL=3600

# Your existing API keys
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### 3. Test Cache Connection

Run the cache connection test:

```bash
python3 test_cache.py
```

Expected output:
```
✅ Cache is available and connected
✅ SET operation successful
✅ GET operation successful
✅ All tests passed! Cache is ready for production.
```

### 4. Start the Server

**Option A: Waitress (Recommended for I/O-bound workloads)**
```bash
./start_server.sh
```

**Option B: Gunicorn (Maximum performance)**
```bash
./start_gunicorn.sh
```

**Option C: Manual Waitress**
```bash
waitress-serve --host=0.0.0.0 --port=5006 --threads=50 app:app
```

## 📊 Cache Strategy

### Cache Namespaces and TTLs

| Data Type | Namespace | TTL | Purpose |
|-----------|-----------|-----|---------|
| AI Responses | `ai_responses` | 1 hour | Cache expensive LLM calls |
| Language Detection | `language_detection` | 2 hours | Cache language auto-detection |
| API Key Validation | `api_key_validation` | 10 minutes | Speed up authentication |
| Custom Instructions | `custom_instructions` | 24 hours | User-specific settings |

### Cache Key Patterns

```
appencorrect:ai_responses:gemini:a1b2c3:english:default
appencorrect:language_detection:d4e5f6
appencorrect:api_key_validation:hash123
```

## 🔍 Monitoring and Troubleshooting

### Check Cache Status

```bash
python3 -c "
from cache_client import get_cache
cache = get_cache()
print('Cache Status:', cache.get_stats())
"
```

### View Cache Statistics

The cache client provides real-time statistics:
- Hit rate percentage
- Memory usage
- Total connections
- Response times

### Common Issues

**Cache Not Connecting:**
1. Check network connectivity: `telnet 10.0.16.112 6379`
2. Verify security group allows port 6379 from this instance
3. Ensure Redis instance is running and accessible from this VPC

**Performance Issues:**
1. Monitor cache hit rates (should be >70%)
2. Check worker memory usage
3. Verify TTL settings are appropriate

**Database Conflicts:**
- Use `VALKEY_DB=1` (database 1) to avoid conflicts with other applications

## 🎯 Performance Tuning

### Optimal Settings for 50 Workers

```env
# Server Configuration
WORKERS=50
TIMEOUT=30
MAX_REQUESTS=1000

# Cache Configuration  
VALKEY_DEFAULT_TTL=3600
VALKEY_DB=1
```

### Expected Performance

| Metric | Before Cache | With Cache |
|--------|-------------|------------|
| Response Time | 1-3 seconds | 50-200ms |
| Throughput | 2-5 req/sec | 50-125 req/sec |
| API Costs | 100% | 30-50% (70% cache hit rate) |
| Memory Usage | Low | Medium |

## 🛡️ Security Considerations

- Cache database separation (`VALKEY_DB=1`)
- No sensitive data in cache keys
- Short TTLs for authentication data
- Automatic cache key hashing for privacy

## 🔄 Cache Management

### Clear All Cache

```bash
python3 -c "
from cache_client import get_cache
cache = get_cache()
cache.clear_namespace('ai_responses')
cache.clear_namespace('language_detection')
print('Cache cleared')
"
```

### Disable Cache (Emergency)

Set in `.env`:
```env
VALKEY_ENABLED=false
```

The application will automatically fall back to in-memory caching.

## 📈 Success Metrics

Monitor these indicators for successful deployment:

1. **Cache Hit Rate**: >70% for AI responses
2. **Response Times**: <500ms for cached requests  
3. **Throughput**: >50 requests/second
4. **Error Rate**: <1% 
5. **Memory Usage**: Stable under load

## 🆘 Support

If you encounter issues:

1. **Run diagnostics**: `python3 test_cache.py`
2. **Check logs**: Look for cache-related messages in application logs
3. **Verify network**: Test ElastiCache connectivity
4. **Fallback mode**: Set `VALKEY_ENABLED=false` if needed

The application is designed to work with or without cache - it will gracefully degrade to in-memory caching if Redis/Valkey is unavailable.
