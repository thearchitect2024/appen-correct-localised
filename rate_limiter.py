"""
Rate limiter for Gemini API calls based on model-specific limits.

Implements rate limiting for:
- Gemini 2.5 Flash: 1,000 RPM, 1,000,000 TPM, 10,000 RPD
- Gemini 2.5 Flash-Lite: 4,000 RPM, 4,000,000 TPM, No limit RPD
- Gemini 2.0 Flash: 2,000 RPM, 4,000,000 TPM, No limit RPD
"""

import time
import threading
import logging
from collections import deque
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ModelLimits:
    """Rate limits for a specific model."""
    requests_per_minute: int
    tokens_per_minute: int
    requests_per_day: Optional[int] = None  # None means no limit
    
    def __str__(self):
        rpd_str = f"{self.requests_per_day:,}" if self.requests_per_day else "No limit"
        return f"RPM: {self.requests_per_minute:,}, TPM: {self.tokens_per_minute:,}, RPD: {rpd_str}"

# Model-specific rate limits based on Google's documentation
MODEL_LIMITS = {
    'gemini-2.5-flash': ModelLimits(
        requests_per_minute=1000,
        tokens_per_minute=1_000_000,
        requests_per_day=10_000
    ),
    'gemini-2.5-flash-lite': ModelLimits(
        requests_per_minute=4000,
        tokens_per_minute=4_000_000,
        requests_per_day=None  # No limit
    ),
    'gemini-2.0-flash': ModelLimits(
        requests_per_minute=2000,
        tokens_per_minute=4_000_000,
        requests_per_day=None  # No limit
    )
}

class TokenCounter:
    """Estimates token count for rate limiting purposes."""
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for text.
        Using a conservative estimate of ~4 characters per token for most languages.
        """
        if not text:
            return 0
        
        # Conservative estimate: 4 characters per token
        # This tends to overestimate, which is safer for rate limiting
        estimated_tokens = len(text) // 4
        
        # Minimum of 1 token for non-empty text
        return max(1, estimated_tokens)
    
    @staticmethod
    def estimate_request_tokens(messages: list, system_message: str = None) -> int:
        """Estimate total tokens for a request."""
        total_chars = 0
        
        # Count message content
        for message in messages:
            if isinstance(message, dict) and 'content' in message:
                total_chars += len(str(message['content']))
            elif isinstance(message, str):
                total_chars += len(message)
        
        # Count system message
        if system_message:
            total_chars += len(system_message)
        
        # Add some overhead for API structure (~10%)
        total_chars = int(total_chars * 1.1)
        
        return TokenCounter.estimate_tokens(str(total_chars))

class RateLimiter:
    """Thread-safe rate limiter for Gemini API calls."""
    
    def __init__(self, model: str = 'gemini-2.5-flash'):
        """
        Initialize rate limiter for specific model.
        
        Args:
            model: Gemini model name
        """
        self.model = model
        self.limits = MODEL_LIMITS.get(model, MODEL_LIMITS['gemini-2.5-flash'])
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Request tracking (timestamp, tokens)
        self._minute_requests = deque()  # (timestamp, token_count)
        self._day_requests = deque()     # (timestamp,)
        
        # Current minute/day tracking
        self._current_minute_requests = 0
        self._current_minute_tokens = 0
        self._current_day_requests = 0
        
        logger.info(f"Rate limiter initialized for {model} - {self.limits}")
    
    def update_model(self, model: str) -> None:
        """Update rate limiter for different model."""
        with self._lock:
            if model != self.model:
                old_model = self.model
                self.model = model
                self.limits = MODEL_LIMITS.get(model, MODEL_LIMITS['gemini-2.5-flash'])
                logger.info(f"Rate limiter updated: {old_model} -> {model} - {self.limits}")
    
    def _cleanup_old_requests(self) -> None:
        """Remove requests older than tracking windows."""
        now = time.time()
        
        # Clean minute window (60 seconds)
        minute_ago = now - 60
        while self._minute_requests and self._minute_requests[0][0] < minute_ago:
            _, tokens = self._minute_requests.popleft()
            self._current_minute_requests -= 1
            self._current_minute_tokens -= tokens
        
        # Clean day window (24 hours)
        if self.limits.requests_per_day:
            day_ago = now - (24 * 60 * 60)
            while self._day_requests and self._day_requests[0] < day_ago:
                self._day_requests.popleft()
                self._current_day_requests -= 1
    
    def can_make_request(self, estimated_tokens: int) -> Tuple[bool, str, float]:
        """
        Check if request can be made within rate limits.
        
        Args:
            estimated_tokens: Estimated token count for the request
            
        Returns:
            (can_proceed, reason, wait_time_seconds)
        """
        with self._lock:
            self._cleanup_old_requests()
            
            # Check requests per minute
            if self._current_minute_requests >= self.limits.requests_per_minute:
                wait_time = 60 - (time.time() % 60)  # Wait until next minute
                return False, f"RPM limit exceeded ({self._current_minute_requests}/{self.limits.requests_per_minute})", wait_time
            
            # Check tokens per minute
            if self._current_minute_tokens + estimated_tokens > self.limits.tokens_per_minute:
                wait_time = 60 - (time.time() % 60)  # Wait until next minute
                return False, f"TPM limit exceeded ({self._current_minute_tokens + estimated_tokens}/{self.limits.tokens_per_minute})", wait_time
            
            # Check requests per day (if applicable)
            if self.limits.requests_per_day and self._current_day_requests >= self.limits.requests_per_day:
                # Calculate time until next day (midnight UTC)
                now = time.time()
                seconds_in_day = 24 * 60 * 60
                wait_time = seconds_in_day - (now % seconds_in_day)
                return False, f"RPD limit exceeded ({self._current_day_requests}/{self.limits.requests_per_day})", wait_time
            
            return True, "OK", 0.0
    
    def record_request(self, estimated_tokens: int) -> None:
        """Record a request for rate limiting tracking."""
        with self._lock:
            now = time.time()
            
            # Record for minute tracking
            self._minute_requests.append((now, estimated_tokens))
            self._current_minute_requests += 1
            self._current_minute_tokens += estimated_tokens
            
            # Record for day tracking (if applicable)
            if self.limits.requests_per_day:
                self._day_requests.append(now)
                self._current_day_requests += 1
            
            self._cleanup_old_requests()
    
    def wait_if_needed(self, estimated_tokens: int, max_wait: float = 60.0) -> bool:
        """
        Wait if needed to respect rate limits.
        
        Args:
            estimated_tokens: Estimated token count for the request
            max_wait: Maximum time to wait in seconds
            
        Returns:
            True if can proceed, False if wait time exceeds max_wait
        """
        can_proceed, reason, wait_time = self.can_make_request(estimated_tokens)
        
        if can_proceed:
            return True
        
        if wait_time > max_wait:
            logger.warning(f"⏰ Rate limit wait time ({wait_time:.1f}s) exceeds max wait ({max_wait}s) - {reason}")
            return False
        
        if wait_time > 0:
            logger.info(f"⏳ Rate limiting: waiting {wait_time:.1f}s - {reason}")
            time.sleep(wait_time)
        
        return True
    
    def get_status(self) -> Dict[str, any]:
        """Get current rate limiter status."""
        with self._lock:
            self._cleanup_old_requests()
            
            return {
                'model': self.model,
                'limits': {
                    'requests_per_minute': self.limits.requests_per_minute,
                    'tokens_per_minute': self.limits.tokens_per_minute,
                    'requests_per_day': self.limits.requests_per_day
                },
                'current_usage': {
                    'requests_this_minute': self._current_minute_requests,
                    'tokens_this_minute': self._current_minute_tokens,
                    'requests_today': self._current_day_requests if self.limits.requests_per_day else None
                },
                'utilization': {
                    'rpm_percent': (self._current_minute_requests / self.limits.requests_per_minute) * 100,
                    'tpm_percent': (self._current_minute_tokens / self.limits.tokens_per_minute) * 100,
                    'rpd_percent': ((self._current_day_requests / self.limits.requests_per_day) * 100) if self.limits.requests_per_day else None
                }
            }

# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = threading.Lock()

def get_rate_limiter(model: str = 'gemini-2.5-flash') -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _global_rate_limiter
    
    with _rate_limiter_lock:
        if _global_rate_limiter is None:
            _global_rate_limiter = RateLimiter(model)
        else:
            _global_rate_limiter.update_model(model)
        
        return _global_rate_limiter

def estimate_request_tokens(messages: list, system_message: str = None) -> int:
    """Convenience function to estimate tokens for a request."""
    return TokenCounter.estimate_request_tokens(messages, system_message)

def check_rate_limit(model: str, messages: list, system_message: str = None, max_wait: float = 60.0) -> bool:
    """
    Check and wait for rate limits if needed.
    
    Args:
        model: Gemini model name
        messages: Request messages
        system_message: System message (optional)
        max_wait: Maximum time to wait for rate limits
        
    Returns:
        True if can proceed, False if rate limited
    """
    rate_limiter = get_rate_limiter(model)
    estimated_tokens = estimate_request_tokens(messages, system_message)
    
    if rate_limiter.wait_if_needed(estimated_tokens, max_wait):
        rate_limiter.record_request(estimated_tokens)
        return True
    
    return False 