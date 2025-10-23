"""
API Authentication System for AppenCorrect

Provides API key generation, validation, and management functionality.
"""

import os
import json
import uuid
import hashlib
import sqlite3
import logging
import time
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from contextlib import contextmanager

# Import cache client with fallback
try:
    from cache_client import get_cache, TTL
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

logger = logging.getLogger(__name__)

class APIKeyManager:
    """Manages API keys for AppenCorrect access."""
    
    def __init__(self, db_path=None):
        """Initialize API key manager with SQLite database."""
        # Use environment variable for database path, fallback to default
        self.db_path = db_path or os.getenv('DATABASE_PATH', 'api_keys.db')
        self._last_timestamp_updates = {}  # Track when we last updated each key's timestamp
        
        # Initialize Redis cache
        self.cache = get_cache() if CACHE_AVAILABLE else None
        if self.cache and self.cache.is_available():
            logger.info("✓ API Auth cache initialized and connected")
        
        self._init_database()
    
    def _init_database(self):
        """Initialize the API keys database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT UNIQUE NOT NULL,
                    key_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    usage_count INTEGER DEFAULT 0,
                    rate_limit_per_hour INTEGER DEFAULT 1000,
                    created_by TEXT DEFAULT 'system'
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    request_size INTEGER DEFAULT 0,
                    response_size INTEGER DEFAULT 0,
                    processing_time_ms INTEGER DEFAULT 0,
                    status_code INTEGER DEFAULT 200,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    model_used TEXT DEFAULT 'gemini-2.5-flash-lite',
                    estimated_cost_usd DECIMAL(10,8) DEFAULT 0.0,
                    FOREIGN KEY (key_id) REFERENCES api_keys (key_id)
                )
            ''')
            
            # Add new columns to existing tables (for database migration)
            try:
                conn.execute('ALTER TABLE api_usage ADD COLUMN input_tokens INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                conn.execute('ALTER TABLE api_usage ADD COLUMN output_tokens INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass  # Column already exists
                
            try:
                conn.execute('ALTER TABLE api_usage ADD COLUMN model_used TEXT DEFAULT "gemini-2.5-flash-lite"')
            except sqlite3.OperationalError:
                pass  # Column already exists
                
            try:
                conn.execute('ALTER TABLE api_usage ADD COLUMN estimated_cost_usd DECIMAL(10,8) DEFAULT 0.0')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Create custom instructions table for persistent storage
            conn.execute('''
                CREATE TABLE IF NOT EXISTS custom_instructions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_key_id TEXT NOT NULL,
                    use_case TEXT NOT NULL,
                    instructions TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(api_key_id, use_case),
                    FOREIGN KEY (api_key_id) REFERENCES api_keys (key_id)
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_api_keys_key_id ON api_keys(key_id);
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_custom_instructions_api_key ON custom_instructions(api_key_id);
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_api_usage_key_id ON api_usage(key_id);
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp);
            ''')
            
            conn.commit()
            logger.info("API keys database initialized")
    
    @contextmanager
    def _get_db_connection(self):
        """Get database connection with enhanced concurrency optimizations."""
        # Increased timeout for high-concurrency scenarios
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Enhanced performance optimizations for 300 worker threads
        conn.execute('PRAGMA journal_mode = WAL')  # Better concurrent access
        conn.execute('PRAGMA synchronous = NORMAL')  # Faster writes
        conn.execute('PRAGMA cache_size = 20000')  # Increased memory cache
        conn.execute('PRAGMA temp_store = MEMORY')  # Use memory for temp tables
        conn.execute('PRAGMA mmap_size = 268435456')  # 256MB memory mapping
        conn.execute('PRAGMA wal_autocheckpoint = 1000')  # Less frequent checkpoints
        conn.execute('PRAGMA busy_timeout = 30000')  # 30-second busy timeout
        
        try:
            yield conn
        finally:
            conn.close()
    
    def generate_api_key(self, name, description="", rate_limit_per_hour=1000, created_by="system"):
        """
        Generate a new API key.
        
        Args:
            name: Human-readable name for the API key
            description: Optional description
            rate_limit_per_hour: Requests per hour limit for this key
            created_by: Who created this key
            
        Returns:
            dict: Contains the API key and metadata
        """
        # Generate unique key ID and actual API key
        key_id = f"ak_{uuid.uuid4().hex[:16]}"  # Short unique ID
        api_key = f"appencorrect_{uuid.uuid4().hex}"  # Full API key
        
        # Hash the API key for secure storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        with self._get_db_connection() as conn:
            conn.execute('''
                INSERT INTO api_keys (key_id, key_hash, name, description, rate_limit_per_hour, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (key_id, key_hash, name, description, rate_limit_per_hour, created_by))
            conn.commit()
        
        logger.info(f"Generated new API key: {key_id} for {name}")
        
        return {
            'key_id': key_id,
            'api_key': api_key,  # Only returned once during creation
            'name': name,
            'description': description,
            'rate_limit_per_hour': rate_limit_per_hour,
            'created_at': datetime.utcnow().isoformat(),
            'is_active': True
        }
    
    def validate_api_key(self, api_key):
        """
        Validate an API key and return key information.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            dict or None: Key information if valid, None if invalid
        """
        if not api_key or not api_key.startswith('appencorrect_'):
            return None
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Check cache first for API key validation
        if self.cache and self.cache.is_available():
            cached_result = self.cache.get('api_key_validation', key_hash)
            if cached_result:
                logger.debug(f"API key validation cache hit")
                return cached_result
        
        with self._get_db_connection() as conn:
            result = conn.execute('''
                SELECT key_id, name, description, rate_limit_per_hour, usage_count, is_active
                FROM api_keys 
                WHERE key_hash = ? AND is_active = 1
            ''', (key_hash,)).fetchone()
            
            if result:
                # Update last used timestamp only once per hour to reduce DB lock contention
                key_id = result['key_id']
                now = datetime.utcnow()
                last_update = self._last_timestamp_updates.get(key_id)
                
                # Only update if it's been more than an hour since last update
                if not last_update or (now - last_update).total_seconds() > 3600:
                    try:
                        conn.execute('''
                            UPDATE api_keys 
                            SET last_used_at = CURRENT_TIMESTAMP 
                            WHERE key_hash = ?
                        ''', (key_hash,))
                        conn.commit()
                        self._last_timestamp_updates[key_id] = now
                        logger.debug(f"Updated last_used_at for API key: {key_id}")
                    except sqlite3.Error as e:
                        # If timestamp update fails, don't fail the validation
                        logger.warning(f"Failed to update last_used_at for {key_id}: {e}")
                
                result_dict = dict(result)
                
                # Cache the successful validation (but not failures for security)
                if self.cache and self.cache.is_available():
                    self.cache.set('api_key_validation', key_hash, result_dict, ttl=TTL.API_KEY_VALIDATION)
                
                return result_dict
        
        return None
    
    def check_rate_limit(self, key_id, endpoint=""):
        """
        Check if API key has exceeded rate limits.
        
        Args:
            key_id: The API key ID
            endpoint: The endpoint being accessed
            
        Returns:
            bool: True if within limits, False if exceeded
        """
        with self._get_db_connection() as conn:
            # Get key's rate limit
            key_info = conn.execute('''
                SELECT rate_limit_per_hour FROM api_keys WHERE key_id = ?
            ''', (key_id,)).fetchone()
            
            if not key_info:
                return False
            
            rate_limit = key_info['rate_limit_per_hour']
            
            # Count requests in the last hour
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            usage_count = conn.execute('''
                SELECT COUNT(*) as count FROM api_usage 
                WHERE key_id = ? AND timestamp > ?
            ''', (key_id, hour_ago.isoformat())).fetchone()['count']
            
            return usage_count < rate_limit
    
    def record_usage(self, key_id, endpoint, request_size=0, response_size=0, processing_time_ms=0, status_code=200, 
                     input_tokens=0, output_tokens=0, model_used='gemini-2.5-flash-lite'):
        """Record API usage for tracking and billing with cost calculation and retry logic."""
        # Calculate cost based on September 2025 Gemini pricing
        # Only charge for fresh AI processing, not cached responses
        if processing_time_ms < 100:  # Cached response - no Gemini API cost
            total_cost = 0.0
        else:
            # Fresh AI processing - calculate actual costs
            # Input: $0.10 per 1M tokens, Output: $0.40 per 1M tokens
            input_cost = input_tokens * 0.0000001  # $0.10 / 1,000,000
            output_cost = output_tokens * 0.0000004  # $0.40 / 1,000,000
            total_cost = input_cost + output_cost
        
        # Retry logic for database lock contention under high concurrency
        max_retries = 5
        base_delay = 0.1  # 100ms base delay
        
        for attempt in range(max_retries):
            try:
                with self._get_db_connection() as conn:
                    conn.execute('''
                        INSERT INTO api_usage (key_id, endpoint, request_size, response_size, processing_time_ms, status_code,
                                             input_tokens, output_tokens, model_used, estimated_cost_usd)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (key_id, endpoint, request_size, response_size, processing_time_ms, status_code,
                          input_tokens, output_tokens, model_used, total_cost))
                    
                    # Update total usage count
                    conn.execute('''
                        UPDATE api_keys 
                        SET usage_count = usage_count + 1 
                        WHERE key_id = ?
                    ''', (key_id,))
                    
                    conn.commit()
                    
                    if total_cost > 0:
                        logger.debug(f"API usage recorded for {key_id}: {input_tokens} input + {output_tokens} output tokens = ${total_cost:.6f}")
                    
                    # Success - break out of retry loop
                    break
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    # Database lock - retry with exponential backoff + jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                    logger.warning(f"Database lock detected, retrying in {delay:.3f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    # Max retries exceeded or different error
                    logger.error(f"Failed to record API usage after {max_retries} attempts: {e}")
                    # Don't raise the exception - log the failure but continue serving the request
                    break
            except Exception as e:
                logger.error(f"Unexpected error recording API usage: {e}")
                break
    
    def list_api_keys(self):
        """List all API keys (without revealing the actual keys)."""
        with self._get_db_connection() as conn:
            results = conn.execute('''
                SELECT key_id, name, description, created_at, last_used_at, 
                       is_active, usage_count, rate_limit_per_hour, created_by
                FROM api_keys 
                ORDER BY created_at DESC
            ''').fetchall()
            
            return [dict(row) for row in results]
    
    def deactivate_api_key(self, key_id):
        """Deactivate an API key."""
        with self._get_db_connection() as conn:
            conn.execute('''
                UPDATE api_keys 
                SET is_active = 0 
                WHERE key_id = ?
            ''', (key_id,))
            conn.commit()
            
        logger.info(f"Deactivated API key: {key_id}")
    
    def get_usage_stats(self, key_id=None, days=7):
        """Get usage statistics for API keys."""
        try:
            with self._get_db_connection() as conn:
                since_date = datetime.utcnow() - timedelta(days=days)
                since_date_str = since_date.isoformat()
                
                if key_id:
                    # Stats for specific key
                    results = conn.execute('''
                        SELECT endpoint, COUNT(*) as count, 
                               AVG(processing_time_ms) as avg_processing_time,
                               SUM(request_size) as total_request_size,
                               SUM(response_size) as total_response_size
                        FROM api_usage 
                        WHERE key_id = ? AND timestamp > ?
                        GROUP BY endpoint
                        ORDER BY count DESC
                    ''', (key_id, since_date_str)).fetchall()
                else:
                    # Overall stats
                    results = conn.execute('''
                        SELECT key_id, COUNT(*) as count,
                               AVG(processing_time_ms) as avg_processing_time,
                               SUM(request_size) as total_request_size,
                               SUM(response_size) as total_response_size
                        FROM api_usage 
                        WHERE timestamp > ?
                        GROUP BY key_id
                        ORDER BY count DESC
                    ''', (since_date_str,)).fetchall()
                
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error in get_usage_stats: {e}")
            return []

# Global API key manager instance
_api_key_manager = None

def get_api_key_manager():
    """Get global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager

def require_api_key(f):
    """Decorator to require valid API key for endpoint access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from header
        api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization')
        
        if api_key and api_key.startswith('Bearer '):
            api_key = api_key[7:]  # Remove 'Bearer ' prefix
        
        if not api_key:
            return jsonify({
                'error': 'API key required',
                'message': 'Provide API key in X-API-Key header or Authorization: Bearer <key>'
            }), 401
        
        # Validate API key
        manager = get_api_key_manager()
        key_info = manager.validate_api_key(api_key)
        
        if not key_info:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'The provided API key is invalid or inactive'
            }), 401
        
        # Check rate limits
        if not manager.check_rate_limit(key_info['key_id'], request.endpoint):
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': f'Rate limit of {key_info["rate_limit_per_hour"]} requests per hour exceeded'
            }), 429
        
        # Store key info in request context for usage tracking
        request.api_key_info = key_info
        
        return f(*args, **kwargs)
    
    return decorated_function

def track_api_usage(f):
    """Decorator to track API usage after successful requests with token counting and cost calculation."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = datetime.utcnow()
        
        try:
            response = f(*args, **kwargs)
            
            # Track usage if API key info is available
            if hasattr(request, 'api_key_info'):
                end_time = datetime.utcnow()
                processing_time = int((end_time - start_time).total_seconds() * 1000)
                
                # Handle different request types
                if request.method in ['POST', 'PUT', 'PATCH']:
                    request_data = request.get_json() or {}
                    request_size = len(json.dumps(request_data))
                else:
                    # For GET/DELETE, track query parameters instead
                    request_data = dict(request.args)
                    request_size = len(str(request_data))
                
                # Extract response size (approximate)
                if hasattr(response, 'data'):
                    response_size = len(response.data)
                else:
                    response_size = len(str(response))
                
                status_code = response.status_code if hasattr(response, 'status_code') else 200
                
                # Count tokens for cost calculation
                input_tokens = 0
                output_tokens = 0
                model_used = 'gemini-2.5-flash-lite'
                
                try:
                    # Import token counter
                    from rate_limiter import TokenCounter
                    
                    # Always count input tokens from request text
                    if 'text' in request_data:
                        input_tokens = TokenCounter.estimate_tokens(request_data['text'])
                        logger.debug(f"Input tokens counted: {input_tokens} for text length {len(request_data['text'])}")
                    
                    # Count output tokens from response
                    if response.is_json:
                        response_json = response.get_json()
                        
                        # For all responses (cached or fresh), count output tokens
                        if response_json and 'processed_text' in response_json:
                            output_tokens = TokenCounter.estimate_tokens(response_json['processed_text'])
                            logger.debug(f"Output tokens from processed_text: {output_tokens}")
                        elif response_json and 'corrections' in response_json:
                            # Count tokens in all corrections
                            corrections_text = ' '.join([c.get('suggestion', '') for c in response_json.get('corrections', [])])
                            output_tokens = TokenCounter.estimate_tokens(corrections_text) if corrections_text.strip() else 0
                            logger.debug(f"Output tokens from corrections: {output_tokens}")
                        
                        # Extract model from response statistics if available
                        if response_json and 'statistics' in response_json:
                            stats = response_json['statistics']
                            if 'api_type' in stats and stats['api_type'] == 'gemini':
                                model_used = 'gemini-2.5-flash-lite'
                    
                    logger.debug(f"Token counting result: {input_tokens} input + {output_tokens} output = ${(input_tokens * 0.0000001 + output_tokens * 0.0000004):.6f}")
                
                except ImportError:
                    logger.warning("TokenCounter not available for cost tracking")
                except Exception as e:
                    logger.warning(f"Error counting tokens: {e}")
                
                manager = get_api_key_manager()
                manager.record_usage(
                    key_id=request.api_key_info['key_id'],
                    endpoint=request.endpoint,
                    request_size=request_size,
                    response_size=response_size,
                    processing_time_ms=processing_time,
                    status_code=status_code,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model_used=model_used
                )
            
            return response
            
        except Exception as e:
            # Track failed requests too
            if hasattr(request, 'api_key_info'):
                end_time = datetime.utcnow()
                processing_time = int((end_time - start_time).total_seconds() * 1000)
                
                manager = get_api_key_manager()
                manager.record_usage(
                    key_id=request.api_key_info['key_id'],
                    endpoint=request.endpoint,
                    processing_time_ms=processing_time,
                    status_code=500
                )
            
            raise e
    
    return decorated_function
