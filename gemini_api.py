# gemini_api.py
# author: rraught@appen.com
# date: 2025-02-07
# version: 0.4

import time
import logging
import os

import google.genai as genai
from rate_limiter import check_rate_limit, get_rate_limiter
from env_loader import get_env_var

def call_gemini_api(
    messages, 
    system_message=None, 
    api_key=None, 
    model=None, 
    max_retries=2,  # Reduced from 3 for speed
    backoff_factor=1.5,  # Reduced from 2 for speed
    timeout=30,  # Timeout for API calls
    quick_mode=False  # Ultra-fast mode with minimal retries
):
    """
    Calls the Gemini 2.0 Flash API using the google.genai client.
    
    Args:
        messages (list): List of message dictionaries with 'content'.
        system_message (str): Optional system message to prepend.
        api_key (str): Your Gemini API key.
        model (str): Model name (default is "gemini-2.5-flash-lite").
        max_retries (int): Maximum number of retry attempts.
        backoff_factor (float): Backoff multiplier for retries.
        timeout (int): Request timeout in seconds.
        quick_mode (bool): Use minimal retries for speed.
    
    Returns:
        dict: Response with 'text' key containing the generated text.
    
    Raises:
        Exception: If the API call fails after all retries.
    """
    import time
    import logging
    import google.genai as genai

    logger = logging.getLogger(__name__)
    
    # Quick mode optimizations for speed
    if quick_mode:
        max_retries = 1
        timeout = 15
        backoff_factor = 1.0
    
    # Ultra-fast mode for maximum speed
    if quick_mode and timeout > 10:
        max_retries = 0  # No retries for ultra-fast
        timeout = 8      # Shorter timeout
    
    # Set default model if not provided
    if not model:
        model = "gemini-2.5-flash-lite"
    
    # Debug API key before client creation
    if not api_key:
        logger.error(f"🚨 No API key provided to call_gemini_api - env fallback: {bool(get_env_var('GEMINI_API_KEY'))}")
        raise ValueError("API key must be provided or available in environment")
    else:
        logger.debug(f"🔑 API key received: {len(api_key)} chars")
    
    # Initialize the Gemini client.
    client = genai.Client(api_key=api_key)
    
    # Combine the system message and the messages into a single input string.
    input_text = ""
    if system_message:
        input_text += system_message + "\n"
    for msg in messages:
        input_text += msg.get("content", "") + "\n"
    input_text = input_text.strip()
    
    # Check rate limits before making request
    if not check_rate_limit(model, messages, system_message, max_wait=60.0):
        rate_limiter = get_rate_limiter(model)
        status = rate_limiter.get_status()
        raise Exception(f"Rate limit exceeded for {model}. Current usage: "
                       f"RPM: {status['current_usage']['requests_this_minute']}/{status['limits']['requests_per_minute']}, "
                       f"TPM: {status['current_usage']['tokens_this_minute']}/{status['limits']['tokens_per_minute']}")
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempt {attempt} to call Gemini API ({model}).")
            
            # Simple direct API call - no complex timeout handling
            response = client.models.generate_content(
                model=model,
                contents=input_text
            )
            
            logger.info(f"Received response from Gemini API ({model}).")
            return {"text": response.text}
                    
        except Exception as e:
            logger.error(f"Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                raise
            if not quick_mode:  # Skip backoff in quick mode
                time.sleep(backoff_factor ** attempt)
    
    raise Exception("Failed to get a successful response from Gemini API after retries.")


def test_gemini_connection(api_key=None, model=None):
    """Test connection to Gemini API.
    
    Args:
        api_key: Optional API key (defaults to environment variable)
        model: Optional model name (defaults to gemini-2.5-flash-lite)
        
    Returns:
        bool: True if connection successful, False otherwise
    """
    if not api_key:
        api_key = get_env_var('GEMINI_API_KEY')
    
    if not api_key:
        return False
    
    try:
        response = call_gemini_api(
            messages=[{"content": "Hello"}],
            api_key=api_key,
            model=model or "gemini-2.5-flash-lite",
            max_retries=1,
            quick_mode=True
        )
        return bool(response and response.get('text'))
    except Exception:
        return False


def get_rate_limit_status(model=None):
    """Get current rate limiting status for a model.
    
    Args:
        model: Model name (defaults to current rate limiter model)
        
    Returns:
        dict: Rate limiting status information
    """
    try:
        rate_limiter = get_rate_limiter(model or 'gemini-2.5-flash-lite')
        if model:
            rate_limiter.update_model(model)
        return rate_limiter.get_status()
    except Exception as e:
        return {
            'error': str(e),
            'model': model,
            'limits': None,
            'current_usage': None,
            'utilization': None
        }
