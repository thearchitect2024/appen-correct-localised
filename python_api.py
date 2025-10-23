"""
AppenCorrect Python API

A purely Python interface for AppenCorrect text correction functionality.
This API can be used directly in Python applications without needing HTTP requests.

Usage:
    from appencorrect import PythonAPI
    
    # Initialize with default settings
    api = PythonAPI()
    
    # Or with custom configuration
    api = PythonAPI(vllm_url="http://localhost:8000", language_detector="lingua")
    
    # Check text for all errors
    result = api.check_text("This is a sentance with erors.")
    
    # Check only spelling
    result = api.check_spelling("This is a sentance with erors.")
    
    # Check only grammar  
    result = api.check_grammar("This are incorrect grammar.")
    
    # Get statistics
    stats = api.get_statistics()
"""

import os
import logging
from typing import Dict, Any, List, Optional, Union
from core import AppenCorrect


class PythonAPI:
    """
    Pure Python API for AppenCorrect text correction.
    
    This class provides a clean, programmatic interface to all AppenCorrect
    functionality without requiring HTTP requests or Flask server setup.
    """
    
    def __init__(self, 
                 vllm_url: str = 'http://localhost:8000',
                 vllm_model: str = 'Qwen/Qwen2.5-7B-Instruct',
                 language_detector: str = 'langdetect',
                 language: str = 'en_US',
                 custom_instructions: Optional[Dict[str, str]] = None):
        """
        Initialize the AppenCorrect Python API.
        
        Args:
             vllm_url: vLLM server URL (default: http://localhost:8000)
             vllm_model: vLLM model name (default: Qwen/Qwen2.5-7B-Instruct)
             language_detector: Language detection library ('lingua', 'langdetect', or 'disabled')
             language: Default language code (kept for compatibility)
             custom_instructions: Dictionary of custom instructions keyed by use case
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize the core AppenCorrect instance
        self._core = AppenCorrect(
            language=language,
            vllm_url=vllm_url,
            vllm_model=vllm_model,
            language_detector=language_detector,
            custom_instructions=custom_instructions
        )
        
        self.logger.info(f"AppenCorrect Python API initialized - Language detector: {language_detector}, vLLM model: {self._core.vllm_client.model}")
    
    def check_text(self, text: str, options: Optional[Dict[str, Any]] = None, use_case: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform comprehensive text checking (spelling, grammar, and style).
        
        Args:
            text: The text to check
            options: Additional options (maintained for compatibility)
            use_case: Apply custom instructions for specific use case
            
        Returns:
            Dictionary containing:
            - status: 'success' or 'error'
            - original_text: The input text
            - processed_text: Text with corrections applied
            - corrections: List of corrections found
            - statistics: Processing statistics
            
        Example:
            >>> api = PythonAPI()
            >>> result = api.check_text("This is a sentance with erors.")
            >>> print(result['corrections'])
            
            >>> # With custom instructions
            >>> api.set_custom_instructions('code', "Don't correct {}, (), []")
            >>> result = api.check_text("Use {} brackets", use_case='code')
            >>> print(result['corrections'])
            [{'type': 'spelling', 'original': 'sentance', 'suggestion': 'sentence', ...}]
        """
        try:
            return self._core.process_text(text, options, use_case=use_case)
        except Exception as e:
            self.logger.error(f"Error in check_text: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'original_text': text,
                'corrections': [],
                'processed_text': text,
                'statistics': {'total_errors': 0}
            }
    
    def check_spelling(self, text: str) -> Dict[str, Any]:
        """
        Check text for spelling errors only.
        
        Args:
            text: The text to check for spelling errors
            
        Returns:
            Dictionary with spelling corrections only
            
        Example:
            >>> api = PythonAPI()
            >>> result = api.check_spelling("This is a sentance with erors.")
            >>> print(f"Found {len(result['corrections'])} spelling errors")
        """
        try:
            # Use the spelling-only method
            return self._core.check_spelling(text)
            
        except Exception as e:
            self.logger.error(f"Error in check_spelling: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'original_text': text,
                'corrections': [],
                'processed_text': text,
                'statistics': {'total_corrections': 0}
            }
    
    def check_grammar(self, text: str) -> Dict[str, Any]:
        """
        Check text for grammar errors only.
        
        Args:
            text: The text to check for grammar errors
            
        Returns:
            Dictionary with grammar corrections only
            
        Example:
            >>> api = PythonAPI()
            >>> result = api.check_grammar("This are incorrect grammar.")
            >>> print(f"Found {len(result['corrections'])} grammar errors")
        """
        try:
            full_result = self._core.process_text(text)
            
            # Filter for grammar corrections only
            grammar_corrections = [
                c for c in full_result.get('corrections', [])
                if c.get('type') == 'grammar'
            ]
            
            return {
                'status': full_result.get('status', 'success'),
                'original_text': full_result.get('original_text', text),
                'processed_text': full_result.get('processed_text', text),
                'corrections': grammar_corrections,
                'statistics': {
                    'total_corrections': len(grammar_corrections),
                    'spelling_corrections': 0,
                    'grammar_corrections': len(grammar_corrections),
                    'style_suggestions': 0,
                    'processing_time': full_result.get('statistics', {}).get('processing_time', '0s'),
                    'detected_language': full_result.get('statistics', {}).get('detected_language')
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in check_grammar: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'original_text': text,
                'corrections': [],
                'processed_text': text,
                'statistics': {'total_corrections': 0}
            }
    
    def check_style(self, text: str) -> Dict[str, Any]:
        """
        Check text for style suggestions only.
        
        Args:
            text: The text to check for style improvements
            
        Returns:
            Dictionary with style suggestions only
            
        Example:
            >>> api = PythonAPI()
            >>> result = api.check_style("The quick brown fox jumps over the lazy dog.")
            >>> print(f"Found {len(result['corrections'])} style suggestions")
        """
        try:
            full_result = self._core.process_text(text)
            
            # Filter for style corrections only
            style_corrections = [
                c for c in full_result.get('corrections', [])
                if c.get('type') == 'style'
            ]
            
            return {
                'status': full_result.get('status', 'success'),
                'original_text': full_result.get('original_text', text),
                'processed_text': full_result.get('processed_text', text),
                'corrections': style_corrections,
                'statistics': {
                    'total_corrections': len(style_corrections),
                    'spelling_corrections': 0,
                    'grammar_corrections': 0,
                    'style_suggestions': len(style_corrections),
                    'processing_time': full_result.get('statistics', {}).get('processing_time', '0s'),
                    'detected_language': full_result.get('statistics', {}).get('detected_language')
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in check_style: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'original_text': text,
                'corrections': [],
                'processed_text': text,
                'statistics': {'total_corrections': 0}
            }
    
    def correct_text(self, text: str) -> str:
        """
        Simple convenience method that returns just the corrected text.
        
        Args:
            text: The text to correct
            
        Returns:
            The corrected text string
            
        Example:
            >>> api = PythonAPI()
            >>> corrected = api.correct_text("This is a sentance with erors.")
            >>> print(corrected)
            "This is a sentence with errors."
        """
        try:
            result = self._core.process_text(text)
            return result.get('processed_text', text)
        except Exception as e:
            self.logger.error(f"Error in correct_text: {e}")
            return text
    
    def get_corrections_only(self, text: str) -> List[Dict[str, Any]]:
        """
        Get only the list of corrections without other metadata.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of correction dictionaries
            
        Example:
            >>> api = PythonAPI()
            >>> corrections = api.get_corrections_only("This is a sentance.")
            >>> for correction in corrections:
            ...     print(f"{correction['original']} -> {correction['suggestion']}")
        """
        try:
            result = self._core.process_text(text)
            return result.get('corrections', [])
        except Exception as e:
            self.logger.error(f"Error in get_corrections_only: {e}")
            return []
    
    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect the language of the input text.
        
        Args:
            text: The text to analyze
            
        Returns:
            Language name (e.g., 'english', 'french') or None if detection fails
            
        Example:
            >>> api = PythonAPI()
            >>> language = api.detect_language("Bonjour, comment allez-vous?")
            >>> print(language)  # 'french'
        """
        try:
            return self._core.detect_language(text)
        except Exception as e:
            self.logger.error(f"Error in detect_language: {e}")
            return None
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List of supported language codes
            
        Example:
            >>> api = PythonAPI()
            >>> languages = api.get_supported_languages()
            >>> print(languages)  # ['en_US', 'en_GB', 'es_ES', 'fr_FR', ...]
        """
        try:
            return self._core.get_supported_languages()
        except Exception as e:
            self.logger.error(f"Error in get_supported_languages: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics and system status.
        
        Returns:
            Dictionary with statistics and status information
            
        Example:
            >>> api = PythonAPI()
            >>> stats = api.get_statistics()
            >>> print(f"Processed {stats['total_processed']} texts")
        """
        try:
            return self._core.get_statistics()
        except Exception as e:
            self.logger.error(f"Error in get_statistics: {e}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of all components.
        
        Returns:
            Dictionary with health status information
            
        Example:
            >>> api = PythonAPI()
            >>> health = api.health_check()
            >>> print(f"Status: {health['status']}")
        """
        try:
            stats = self._core.get_statistics()
            
            vllm_available = self.test_vllm_connection()
            return {
                'status': 'healthy' if vllm_available else 'degraded',
                'version': '2.0.0-vllm',
                'components': {
                    'vllm_inference': 'available' if vllm_available else 'unavailable',
                    'language_detector': 'available' if stats.get('language_detector_available', False) else 'unavailable',
                    'ai_first_mode': 'enabled'
                },
                'statistics': stats,
                'capabilities': ['spelling', 'grammar', 'style', 'language_detection', 'ai_correction']
            }
            
        except Exception as e:
            self.logger.error(f"Error in health_check: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def is_ready(self) -> bool:
        """
        Check if the API is ready to process text.
        
        Returns:
            True if ready, False otherwise
            
        Example:
            >>> api = PythonAPI()
            >>> if api.is_ready():
            ...     result = api.check_text("Some text")
        """
        try:
            return self.test_vllm_connection()
        except Exception:
            return False
    
    def get_current_model(self) -> str:
        """
        Get the currently configured vLLM model.
        
        Returns:
            The model name currently being used
            
        Example:
            >>> api = PythonAPI()
            >>> model = api.get_current_model()
            >>> print(f"Current model: {model}")
        """
        return self._core.vllm_client.model
    
    def test_vllm_connection(self) -> bool:
        """
        Test the vLLM server connection.
        
        Returns:
            True if vLLM server is reachable, False otherwise
            
        Example:
            >>> api = PythonAPI()
            >>> if api.test_vllm_connection():
            ...     print("vLLM server is ready")
        """
        try:
            return self._core.vllm_client.test_connection()
        except Exception as e:
            self.logger.error(f"Error testing vLLM connection: {e}")
            return False
    
    def get_vllm_status(self) -> Dict[str, Any]:
        """
        Get current vLLM server status.
        
        Returns:
            Dictionary containing vLLM server information:
            - model: Current model name
            - server_url: vLLM server URL
            - connected: Whether server is reachable
            - inference_type: 'local_gpu' for self-hosted vLLM
            
        Example:
            >>> api = PythonAPI()
            >>> status = api.get_vllm_status()
            >>> print(f"Model: {status['model']}")
            >>> print(f"Server: {status['server_url']}")
        """
        try:
            connected = self.test_vllm_connection()
            return {
                'model': self._core.vllm_client.model,
                'server_url': self._core.vllm_client.base_url,
                'connected': connected,
                'inference_type': 'local_gpu',
                'note': 'Self-hosted vLLM on GPU - no per-token costs'
            }
        except Exception as e:
            self.logger.error(f"Error getting vLLM status: {e}")
            return {
                'error': str(e),
                'model': 'unknown',
                'server_url': 'unknown',
                'connected': False
            }
    
    def check_server_health(self) -> Dict[str, Any]:
        """
        Check vLLM server health and availability.
        
        Returns:
            Dictionary with server health check results:
            - healthy: Boolean indicating if server is operational
            - model: Current model name
            - server_url: vLLM server URL
            
        Example:
            >>> api = PythonAPI()
            >>> health = api.check_server_health()
            >>> if health['healthy']:
            ...     result = api.check_text("Some text")
            ... else:
            ...     print(f"Server unavailable")
        """
        try:
            connected = self.test_vllm_connection()
            return {
                'healthy': connected,
                'model': self._core.vllm_client.model,
                'server_url': self._core.vllm_client.base_url,
                'note': 'vLLM does not have rate limits - limited by GPU capacity'
            }
        except Exception as e:
            self.logger.error(f"Error checking server health: {e}")
            return {
                'healthy': False,
                'model': 'unknown',
                'server_url': 'unknown',
                'error': str(e)
            }

    def clear_cache(self) -> None:
        """
        Clear the vLLM response cache.
        
        Useful for testing to ensure fresh API calls for each test.
        
        Example:
            >>> api = PythonAPI()
            >>> api.clear_cache()  # Start with fresh cache
        """
        self._core.clear_cache()

    def set_cache_enabled(self, enabled: bool) -> None:
        """
        Enable or disable caching.
        
        Args:
            enabled: True to enable caching, False to disable
            
        Example:
            >>> api = PythonAPI()
            >>> api.set_cache_enabled(False)  # Disable for testing
            >>> # Run tests...
            >>> api.set_cache_enabled(True)   # Re-enable
        """
        self._core.set_cache_enabled(enabled)

    def disable_cache(self) -> None:
        """
        Disable caching and clear existing cache.
        
        This is the recommended method for model comparison testing
        to ensure each model processes text independently.
        
        Example:
            >>> api = PythonAPI()
            >>> api.disable_cache()  # For model comparison testing
        """
        self._core.disable_cache()
        
    def enable_cache(self) -> None:
        """
        Re-enable caching after testing.
        
        Example:
            >>> api = PythonAPI()
            >>> api.enable_cache()  # Re-enable after testing
        """
        self._core.enable_cache()
        
    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get current cache status and statistics.
        
        Returns:
            Dictionary with cache information including:
            - cache_enabled: Whether caching is currently enabled
            - cache_size: Number of cached responses
            - cache_hits: Number of cache hits since initialization
            
        Example:
            >>> api = PythonAPI()
            >>> status = api.get_cache_status()
            >>> print(f"Cache enabled: {status['cache_enabled']}")
            >>> print(f"Cache size: {status['cache_size']}")
        """
        stats = self._core.get_statistics()
        return {
            'cache_enabled': stats.get('cache_enabled', True),
            'cache_size': stats.get('cache_size', 0),
            'cache_hits': stats.get('cache_hits', 0)
        }

    def assess_comment_quality(self, comment: str, rating_context: Optional[str] = None, 
                              enable_quality_assessment: bool = True) -> Dict[str, Any]:
        """
        Assess the overall quality of a comment in the context of a rating task.
        
        This method evaluates comment quality based on multiple factors including:
        - Grammar and spelling errors
        - Comment length and completeness 
        - Conceptual clarity and relevance
        - Appropriateness for rating task context
        - Overall coherence and helpfulness
        
        LENGTH REQUIREMENTS FOR RATING TASKS:
        - Comments under 100 characters: Maximum score of 4/10 (insufficient explanation)
        - Comments under 300 characters: Cannot achieve excellent (9-10/10) rating
        - Comments 300+ characters: Required for highest quality scores
        
        Args:
            comment: The comment text to assess for quality
            rating_context: Optional context about the rating task for more targeted assessment
            enable_quality_assessment: Feature flag to enable/disable this assessment
            
        Returns:
            Dictionary containing:
            - status: 'success', 'error', or 'disabled'
            - quality_score: Numerical score from 1-10 (10 being highest quality)
            - quality_level: 'excellent', 'good', 'fair', or 'poor'
            - assessment: Detailed explanation of the quality assessment
            - factors: Breakdown of individual quality factors analyzed
            - suggestions: List of specific improvement suggestions
            - strengths: List of identified strengths in the comment
            - comment_analysis: Technical metrics (word count, error count, character count, etc.)
            - original_comment: The original comment text
            - technical_corrections: List of grammar/spelling corrections found
            
        Example:
            >>> api = PythonAPI()
            >>> # Long, detailed comment (300+ characters)
            >>> result = api.assess_comment_quality(
            ...     "This product demonstrates exceptional build quality with attention to detail that exceeds expectations. The materials feel premium and durable, while the design is both functional and aesthetically pleasing. I would highly recommend this to anyone looking for a reliable solution.",
            ...     rating_context="Product review rating task"
            ... )
            >>> print(f"Quality Score: {result['quality_score']}/10")
            >>> print(f"Character Count: {result['comment_analysis']['character_count']}")
            >>> 
            >>> # Short comment (under 100 characters) - will be capped at 4/10
            >>> short_result = api.assess_comment_quality("Good product!")
            >>> print(f"Short comment score: {short_result['quality_score']}/10 (capped)")
        """
        try:
            return self._core.assess_comment_quality(
                comment=comment,
                rating_context=rating_context,
                enable_quality_assessment=enable_quality_assessment
            )
        except Exception as e:
            self.logger.error(f"Error in assess_comment_quality: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'quality_score': None,
                'quality_level': None,
                'assessment': None,
                'factors': {},
                'suggestions': [],
                'strengths': [],
                'comment_analysis': {},
                'original_comment': comment,
                'technical_corrections': []
            }

    def set_custom_instructions(self, use_case: str, instructions: str) -> None:
        """Set custom instructions for a specific use case."""
        self._core.set_custom_instructions(use_case, instructions)

    def get_custom_instructions(self, use_case: str = None) -> Union[str, Dict[str, str]]:
        """Get custom instructions for a specific use case or all instructions."""
        return self._core.get_custom_instructions(use_case)

    def remove_custom_instructions(self, use_case: str) -> bool:
        """Remove custom instructions for a specific use case."""
        return self._core.remove_custom_instructions(use_case)

    def clear_custom_instructions(self) -> None:
        """Clear all custom instructions."""
        self._core.clear_custom_instructions()


# Convenience function for quick usage
def check_text(text: str, **kwargs) -> Dict[str, Any]:
    """
    Quick convenience function for one-off text checking.
    
    Args:
        text: Text to check
        **kwargs: Arguments to pass to PythonAPI constructor
        
    Returns:
        Processing result dictionary
        
    Example:
        >>> from appencorrect.python_api import check_text
        >>> result = check_text("This is a sentance with erors.")
        >>> print(result['processed_text'])
    """
    api = PythonAPI(**kwargs)
    return api.check_text(text)


def correct_text(text: str, **kwargs) -> str:
    """
    Quick convenience function for one-off text correction.
    
    Args:
        text: Text to correct
        **kwargs: Arguments to pass to PythonAPI constructor
        
    Returns:
        Corrected text string
        
    Example:
        >>> from appencorrect.python_api import correct_text
        >>> corrected = correct_text("This is a sentance with erors.")
        >>> print(corrected)
    """
    api = PythonAPI(**kwargs)
    return api.correct_text(text) 