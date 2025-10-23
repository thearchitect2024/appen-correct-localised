"""
Redis/Valkey Cache Client for AppenCorrect

Provides caching functionality using AWS ElastiCache (Valkey/Redis) with fallback support.
Implements consistent cache key patterns and TTL management.
"""

import os
import json
import hashlib
import logging
from typing import Any, Optional, Union, Dict
from functools import wraps
import time

# Load environment variables - only if not already loaded
try:
    from dotenv import load_dotenv
    # Only load if GEMINI_API_KEY is not already in environment
    # This prevents race conditions in multi-threaded environments
    if 'GEMINI_API_KEY' not in os.environ:
        load_dotenv()
except ImportError:
    pass  # dotenv not available

# Try importing redis clients in order of preference
try:
    import valkey as redis_client
    CACHE_CLIENT_TYPE = "valkey"
except ImportError:
    try:
        import redis as redis_client
        CACHE_CLIENT_TYPE = "redis"
    except ImportError:
        redis_client = None
        CACHE_CLIENT_TYPE = "none"

logger = logging.getLogger(__name__)

class CacheClient:
    """Redis/Valkey cache client with AWS ElastiCache support and fallback handling."""
    
    def __init__(self):
        """Initialize cache client with configuration from environment variables."""
        self.enabled = os.getenv('VALKEY_ENABLED', 'true').lower() == 'true'
        self.client = None
        self.connected = False
        
        # Connection retry tracking
        self._last_connection_attempt = 0
        self._connection_retry_delay = 60  # Start with 60 seconds
        self._max_retry_delay = 300  # Max 5 minutes
        self._connection_failed_permanently = False
        
        if not self.enabled:
            logger.info("Cache is disabled via VALKEY_ENABLED=false")
            return
            
        if redis_client is None:
            logger.warning("No Redis/Valkey client available. Install with: pip install redis valkey")
            self.enabled = False
            return
        
        # Cache configuration
        self.host = os.getenv('VALKEY_HOST', 'localhost')
        self.port = int(os.getenv('VALKEY_PORT', 6379))
        self.db = int(os.getenv('VALKEY_DB', 1))
        self.password = os.getenv('VALKEY_PASSWORD', '') or None
        self.ssl = os.getenv('VALKEY_SSL', 'false').lower() == 'true'
        self.default_ttl = int(os.getenv('VALKEY_DEFAULT_TTL', 3600))
        
        # Connection pool settings for high concurrency
        self.socket_connect_timeout = 5
        self.socket_timeout = 30
        self.retry_on_timeout = True
        self.health_check_interval = 30
        
        logger.info(f"Initializing cache client ({CACHE_CLIENT_TYPE}) - Host: {self.host}:{self.port}, DB: {self.db}")
        
        # Try initial connection, but don't fail if it doesn't work
        self._connect()
    
    def _connect(self):
        """Establish connection to Redis/Valkey with retry logic and exponential backoff."""
        if not self.enabled or redis_client is None:
            return False
        
        # Check if we should retry based on exponential backoff
        current_time = time.time()
        if (self._connection_failed_permanently or 
            (self._last_connection_attempt > 0 and 
             current_time - self._last_connection_attempt < self._connection_retry_delay)):
            return False
        
        self._last_connection_attempt = current_time
            
        try:
            # Use direct client configuration exactly like chatbot (no connection pool for SSL)
            client_kwargs = {
                'host': self.host,
                'port': self.port,
                'db': self.db,
                'decode_responses': True,
                'socket_connect_timeout': 5,
                'socket_timeout': 5
            }
            
            # Add password if provided
            if self.password:
                client_kwargs['password'] = self.password
            
            # Add SSL configuration exactly like chatbot
            if self.ssl:
                client_kwargs['ssl'] = True
                client_kwargs['ssl_cert_reqs'] = None
                client_kwargs['ssl_check_hostname'] = False
            
            self.client = redis_client.Redis(**client_kwargs)
            
            # Test connection
            self.client.ping()
            self.connected = True
            
            # Reset retry delay on successful connection
            self._connection_retry_delay = 60
            self._connection_failed_permanently = False
            
            logger.info(f"✓ Cache connected successfully ({CACHE_CLIENT_TYPE})")
            return True
            
        except Exception as e:
            # Only log error on first attempt or after long delays to reduce spam
            if self._connection_retry_delay <= 60:
                logger.error(f"Cache connection failed: {e}")
            else:
                logger.debug(f"Cache connection still failing: {e}")
            
            self.connected = False
            self.client = None
            
            # Implement exponential backoff
            self._connection_retry_delay = min(self._connection_retry_delay * 2, self._max_retry_delay)
            
            # After 10 minutes of failures, stop trying until restart
            if self._connection_retry_delay >= self._max_retry_delay:
                self._connection_failed_permanently = True
                logger.warning(f"Cache connection permanently failed after multiple attempts. Will not retry until restart.")
            
            return False
    
    def is_available(self) -> bool:
        """Check if cache is available and connected."""
        if not self.enabled or not self.client:
            # Try to reconnect if enough time has passed
            if self.enabled and not self._connection_failed_permanently:
                self._connect()
            return self.connected
            
        try:
            self.client.ping()
            return True
        except:
            self.connected = False
            # Try to reconnect if enough time has passed
            if not self._connection_failed_permanently:
                self._connect()
            return False
    
    def _make_key(self, namespace: str, key: str, **kwargs) -> str:
        """Create consistent cache key with namespace and optional parameters."""
        # Include relevant parameters in the key for specificity
        if kwargs:
            key_parts = [str(v) for k, v in sorted(kwargs.items()) if v is not None]
            if key_parts:
                key = f"{key}:{':'.join(key_parts)}"
        
        # Hash long keys to avoid Redis key length limits
        if len(key) > 200:
            key = hashlib.md5(key.encode()).hexdigest()
        
        return f"appencorrect:{namespace}:{key}"
    
    def get(self, namespace: str, key: str, **kwargs) -> Optional[Any]:
        """Get value from cache with automatic JSON deserialization."""
        if not self.is_available():
            return None
            
        try:
            cache_key = self._make_key(namespace, key, **kwargs)
            value = self.client.get(cache_key)
            
            if value is None:
                return None
                
            # Try to deserialize JSON, fallback to string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value.decode() if isinstance(value, bytes) else value
                
        except Exception as e:
            logger.warning(f"Cache get error for {namespace}:{key}: {e}")
            return None
    
    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None, **kwargs) -> bool:
        """Set value in cache with automatic JSON serialization."""
        if not self.is_available():
            return False
            
        try:
            cache_key = self._make_key(namespace, key, **kwargs)
            ttl = ttl or self.default_ttl
            
            # Serialize value to JSON if possible
            if isinstance(value, (dict, list, tuple)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
            
            result = self.client.setex(cache_key, ttl, serialized_value)
            return bool(result)
            
        except Exception as e:
            logger.warning(f"Cache set error for {namespace}:{key}: {e}")
            return False
    
    def delete(self, namespace: str, key: str, **kwargs) -> bool:
        """Delete value from cache."""
        if not self.is_available():
            return False
            
        try:
            cache_key = self._make_key(namespace, key, **kwargs)
            result = self.client.delete(cache_key)
            return bool(result)
            
        except Exception as e:
            logger.warning(f"Cache delete error for {namespace}:{key}: {e}")
            return False
    
    def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace. Returns number of keys deleted."""
        if not self.is_available():
            return 0
            
        try:
            pattern = f"appencorrect:{namespace}:*"
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
            
        except Exception as e:
            logger.warning(f"Cache clear namespace error for {namespace}: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics and connection info."""
        stats = {
            'enabled': self.enabled,
            'connected': self.connected,
            'client_type': CACHE_CLIENT_TYPE,
            'host': self.host if self.enabled else None,
            'port': self.port if self.enabled else None,
            'db': self.db if self.enabled else None,
        }
        
        if self.is_available():
            try:
                info = self.client.info()
                stats.update({
                    'memory_used': info.get('used_memory_human', 'Unknown'),
                    'total_connections': info.get('total_connections_received', 0),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                })
                
                # Calculate hit rate
                hits = stats['keyspace_hits']
                misses = stats['keyspace_misses']
                if hits + misses > 0:
                    stats['hit_rate'] = round(hits / (hits + misses) * 100, 2)
                else:
                    stats['hit_rate'] = 0
                    
            except Exception as e:
                logger.warning(f"Error getting cache stats: {e}")
        
        return stats

# Global cache instance
_cache_client = None

def get_cache() -> CacheClient:
    """Get global cache client instance."""
    global _cache_client
    if _cache_client is None:
        try:
            _cache_client = CacheClient()
        except Exception as e:
            # Prevent recursion by creating a disabled cache client
            _cache_client = type('DisabledCache', (), {
                'enabled': False,
                'connected': False,
                'is_available': lambda: False,
                'get': lambda *args, **kwargs: None,
                'set': lambda *args, **kwargs: False,
                'delete': lambda *args, **kwargs: False,
                'clear_namespace': lambda *args, **kwargs: 0,
                'get_stats': lambda: {'enabled': False, 'connected': False, 'error': str(e)}
            })()
            logger.error(f"Cache initialization failed, using disabled cache: {e}")
    return _cache_client

def cached(namespace: str, ttl: Optional[int] = None, key_func: Optional[callable] = None):
    """
    Decorator for caching function results.
    
    Args:
        namespace: Cache namespace for the function
        ttl: Time to live in seconds (uses default if None)
        key_func: Function to generate cache key from args/kwargs
    
    Example:
        @cached('api_responses', ttl=3600)
        def expensive_api_call(text, language):
            return call_external_api(text, language)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation from function name and arguments
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_result = cache.get(namespace, cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {namespace}:{cache_key}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache miss for {namespace}:{cache_key}")
            result = func(*args, **kwargs)
            
            # Cache the result
            cache.set(namespace, cache_key, result, ttl=ttl)
            
            return result
        return wrapper
    return decorator

# TTL constants based on the chatbot patterns
class TTL:
    """Common TTL values for different types of data."""
    AUTHENTICATION = 300      # 5 minutes
    USER_DATA = 3600         # 1 hour  
    API_RESPONSES = 3600     # 1 hour
    TEMPORARY = 60           # 1 minute
    SESSION_DATA = 86400     # 24 hours
    LANGUAGE_DETECTION = 7200 # 2 hours
    API_KEY_VALIDATION = 600  # 10 minutes
