"""
Centralized Environment Variable Loader for AppenCorrect

This module ensures environment variables are loaded exactly once,
preventing race conditions in multi-threaded environments.
"""

import os
import threading
from typing import Optional

# Thread-safe singleton pattern for environment loading
_env_loaded = False
_env_lock = threading.Lock()

def load_environment_once() -> bool:
    """
    Load environment variables exactly once in a thread-safe manner.
    
    Returns:
        bool: True if environment was loaded, False if already loaded
    """
    global _env_loaded
    
    with _env_lock:
        if _env_loaded:
            return False
            
        try:
            from dotenv import load_dotenv
            load_dotenv()
            _env_loaded = True
            
            # Debug log for API key tracking
            import logging
            logger = logging.getLogger(__name__)
            gemini_key = os.getenv('GEMINI_API_KEY')
            if gemini_key:
                logger.debug(f"🔄 Env loaded - GEMINI_API_KEY: {len(gemini_key)} chars")
            else:
                logger.warning(f"🔄 Env loaded - GEMINI_API_KEY: missing")
            
            return True
        except ImportError:
            # dotenv not available, but mark as loaded to prevent retries
            _env_loaded = True
            return False

def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get environment variable, ensuring environment is loaded first.
    
    Args:
        key: Environment variable name
        default: Default value if not found
        
    Returns:
        Environment variable value or default
    """
    # Ensure environment is loaded
    load_environment_once()
    return os.getenv(key, default)

def is_env_loaded() -> bool:
    """Check if environment variables have been loaded."""
    return _env_loaded

# Load environment variables immediately when this module is imported
load_environment_once()
