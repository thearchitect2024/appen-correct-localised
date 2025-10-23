"""
Core AppenCorrect implementation using AI-first text correction with language detection.
"""

import re
import time
import json
import logging
import os
import hashlib
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Tuple, Optional, Union
from dataclasses import dataclass

# Import centralized environment loader
from env_loader import get_env_var

# Import cache client with fallback
try:
    from cache_client import get_cache, cached, TTL
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    # Fallback decorator that does nothing
    def cached(namespace: str, ttl: Optional[int] = None, key_func: Optional[callable] = None):
        def decorator(func):
            return func
        return decorator

# Language detection imports
try:
    from lingua import Language, LanguageDetectorBuilder
    LINGUA_AVAILABLE = True
except ImportError:
    LINGUA_AVAILABLE = False

try:
    import langdetect
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

try:
    from vllm_client import create_vllm_client
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    create_vllm_client = None
    raise ImportError("vLLM client module is required. Install with: pip install vllm")


@dataclass
class Correction:
    """Represents a single text correction."""
    type: str  # 'spelling', 'grammar', 'style'
    position: Tuple[int, int]  # (start, end)
    original: str
    suggestion: str
    source: str  # 'vllm'
    
    def to_dict(self):
        """Convert correction to dictionary for JSON serialization."""
        return {
            'type': self.type,
            'position': list(self.position),
            'original': self.original,
            'suggestion': self.suggestion,
            'source': self.source
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create correction from dictionary."""
        return cls(
            type=data['type'],
            position=tuple(data['position']),
            original=data['original'],
            suggestion=data['suggestion'],
            source=data['source']
        )


# Language-specific grammar rules
LANGUAGE_RULES = {
    'french': {
        'comma_conjunctions': {
            'rule': "In French, do not place commas before or after coordinating conjunctions: mais (but), où (where/or), et (and), donc (therefore/so), or (now/well), ni (nor), car (because/for). Exception: Use commas when connecting independent clauses of significant length or when there's a natural pause for clarity.",
            'description': "French comma usage with coordinating conjunctions (MODEONC mnemonic)"
        },
        'adjective_agreement': {
            'rule': "French adjectives must agree in gender and number: masculine -e (grand→grande), plural +s (grand→grands, grande→grandes). Past participles with être also agree: 'elle est partie' (feminine), 'ils sont partis' (masculine plural).",
            'description': "French adjective agreement with nouns in gender and number"
        },
        'tout_agreement': {
            'rule': "FRENCH TOUT RULES: (1) As ADJECTIVE: 'tout' agrees - 'tout le temps', 'tous les hommes', 'toute la journée', 'toutes les femmes'. (2) As ADVERB (meaning 'completely'): 'tout' NEVER agrees - 'ils sont tout pourris' (they are completely rotten), 'elles sont tout heureuses' (they are completely happy). Don't confuse 'ils sont tout pourris' (completely rotten) with 'ils sont tous là' (they are all there).",
            'description': "French tout/tous/toute/toutes: adjective agreement vs adverbial invariability"
        },
        'negative_constructions': {
            'rule': "French negation requires both parts: ne + pas/plus/jamais/rien. Examples: 'ne... pas' (not), 'ne... plus' (no more), 'ne... jamais' (never). Don't forget the 'ne': 'Je ne sais pas' (not 'Je sais pas').",
            'description': "French negative constructions and verb agreement in negative context"
        },
        'formal_vs_informal_french': {
            'rule': "FORMAL FRENCH CORRECTIONS: (1) Replace 'T'as' with 'As-tu' in questions. (2) Replace 'où' with 'là où' when referring to a specific location/place. (3) Use 'clefs' (not 'clés') as the plural of 'clé'. Example: 'T'as mis les clé ou...' → 'As-tu mis les clefs là où...'",
            'description': "Formal French question formation, location references, and plural consistency"
        },
        'verb_preposition_usage': {
            'rule': "Do NOT correct 'se rappeler de' - both 'se rappeler' and 'se rappeler de' are valid French.",
            'description': "French verb preposition usage: preserve both valid forms of se rappeler"
        },
        'temporal_consistency': {
            'rule': "French temporal markers require consistent tenses: 'maintenant' (now) + present tense, 'hier' (yesterday) + past tense, 'demain' (tomorrow) + future tense. Example: 'maintenant elle dormait' → 'maintenant elle dort'.",
            'description': "French temporal consistency between time markers and verb tenses"
        },
        'pronoun_consistency': {
            'rule': "French pronouns in subordinate clauses must match the subject: 'Ils ont promis qu'ils viendraient' (not 'qu'il viendrait'). Maintain number and person consistency.",
            'description': "French pronoun consistency in subordinate clauses"
        },
        'repetition_errors': {
            'rule': "Avoid word repetition in negation: 'Je ne connais pas' (not 'Je connais ne connais pas'). Check for duplicate words or phrases.",
            'description': "French repetition and negation errors"
        },
        'elision_rules': {
            'rule': "French elision before vowels: 'bien qu'ambitieux' (not 'bien que ambitieux'), 'jusqu'à' (not 'jusque à'). Apply elision with que, de, le, se before vowels/silent h.",
            'description': "French elision before vowels and silent h"
        },
        'gender_agreement_determiners': {
            'rule': "French determiners must match noun gender: 'un délicieux gâteau' (masc.) or 'une délicieuse tarte' (fem.). Check un/une with adjective agreement.",
            'description': "French gender agreement between determiners, adjectives, and nouns"
        },
        'se_rendre_compte_invariable': {
            'rule': "'Se rendre compte' always uses invariable 'rendu' regardless of subject gender/number: 'Elle s'est rendu compte' (not 'rendue'), 'Ils se sont rendu compte' (not 'rendus'). Exception to usual être past participle agreement.",
            'description': "French 'se rendre compte': invariable past participle 'rendu' exception"
        }
    },
    'english': {
        'collective_nouns': {
            'rule': "Use singular collective nouns when referring to the group as a unit: 'jury' (not 'juries'), 'team' (not 'teams'), 'staff' (not 'staffs'), 'committee' (not 'committees'). Example: 'The jury will find in our favor' (not 'The juries will find in our favor').",
            'description': "English collective noun usage: singular when referring to group as unit"
        },
        'contraction_preservation': {
            'rule': "Preserve contractions unless they create ambiguity or are inappropriate for formal writing. Don't unnecessarily expand: 'We're' to 'We are', 'It's' to 'It is', 'Don't' to 'Do not'. Only expand if the context requires formal tone or if the contraction creates confusion.",
            'description': "English contraction preservation: don't expand unnecessarily"
        },
        'parallel_structure': {
            'rule': "Maintain parallel structure in compound phrases connected by 'and' or 'or'. When listing items, ensure grammatical consistency and logical number agreement: 'prognosis and survival rates' (both plural when referring to multiple subjects), 'to run and to jump' (both infinitives). Pay special attention to number consistency when both items logically refer to the same plural subject - if one is plural, the other should match.",
            'description': "English parallel structure: maintain consistency and logical number agreement in compound phrases"
        },
        'types_of_constructions': {
            'rule': "After quantifying phrases like 'types of', 'kinds of', 'forms of', 'varieties of', use singular nouns because plurality is already expressed by the quantifier: 'types of cancer' (not 'cancers'), 'kinds of food' (not 'foods'), 'forms of treatment' (not 'treatments').",
            'description': "English 'types of' constructions: use singular noun after quantifying phrases"
        },
        'mandatory_capitalization': {
            'rule': "MANDATORY CAPITALIZATION RULES: (1) First word of every sentence must be capitalized. (2) Standalone 'i' must ALWAYS be 'I' regardless of position. (3) Proper nouns must be capitalized. Examples: 'what is this?' → 'What is this?', 'i love it' → 'I love it', 'china' → 'China'. These are not style suggestions - they are required corrections.",
            'description': "English mandatory capitalization: sentence starts, standalone 'i', proper nouns"
        },
        'punctuation_boundary_errors': {
            'rule': "CRITICAL: Always check spelling of words immediately before punctuation marks (.?!,;:). Common missed errors: 'thaat?' should be 'that?', 'iss.' should be 'is.', 'misstake!' should be 'mistake!'. The punctuation mark does not protect the word from spelling correction - always examine the word itself regardless of what follows it.",
            'description': "English punctuation boundary spelling: check words before punctuation marks"
        }
    },
    'spanish': {
        # Can add Spanish-specific rules here if needed
    }
}


class AppenCorrect:
    """
    AI-first AppenCorrect implementation with language detection and language-specific rules.
    """
    
    def __init__(self, language='en_US', vllm_url=None, vllm_model=None,
                 language_detector='langdetect', custom_instructions=None):
        """
        Initialize AppenCorrect with vLLM local GPU inference.
        
        Args:
            language: Language code (e.g. 'en_US', 'es_ES') - kept for compatibility
            vllm_url: vLLM server URL (default: http://localhost:8000 or from VLLM_URL env)
            vllm_model: vLLM model name (default: Qwen/Qwen2.5-7B-Instruct or from VLLM_MODEL env)
            language_detector: Language detection library to use ('lingua', 'langdetect', or 'disabled')
            custom_instructions: Optional custom instructions for specific use cases
        """
        self.language = language
        
        # Initialize logger first
        self.logger = logging.getLogger(__name__)
        
        # Initialize custom instructions
        self.custom_instructions = custom_instructions or {}
        
        # Initialize vLLM client (REQUIRED)
        if not VLLM_AVAILABLE:
            raise RuntimeError("vLLM client module not available. Install with: pip install vllm")
        
        try:
            self.vllm_client = create_vllm_client(
                base_url=vllm_url or os.getenv('VLLM_URL', 'http://localhost:8000'),
                model=vllm_model or os.getenv('VLLM_MODEL', 'Qwen/Qwen2.5-7B-Instruct')
            )
            self.api_type = 'vllm'
            self.selected_model = self.vllm_client.model
            self.logger.info(f"✓ vLLM client initialized - URL: {self.vllm_client.base_url}, Model: {self.selected_model}")
        except Exception as e:
            self.logger.error(f"Failed to initialize vLLM client: {e}")
            raise RuntimeError(f"vLLM initialization failed: {e}. Ensure vLLM server is running at {vllm_url or os.getenv('VLLM_URL', 'http://localhost:8000')}")
        
        self.language_detector = language_detector
        
        # Initialize Redis cache
        self.cache = get_cache() if CACHE_AVAILABLE else None
        if self.cache and self.cache.is_available():
            self.logger.info("✓ Redis/Valkey cache initialized and connected")
        elif CACHE_AVAILABLE:
            self.logger.warning("⚠️ Redis/Valkey cache client available but not connected - using fallback")
        else:
            self.logger.info("ℹ️ Redis/Valkey cache not available - using in-memory cache only")
        
        # Log model selection details
        self.logger.info(f"AppenCorrect Core initialized - API: {self.api_type}, Model: {self.selected_model}")
        
        # Initialize language detector
        self.lang_detector = self._init_language_detector()
        
        # Test vLLM connection
        self.api_unavailable_reason = None
        self.api_available = self.vllm_client.test_connection()
        if not self.api_available:
            self.api_unavailable_reason = f"vLLM server not reachable at {self.vllm_client.base_url}"
            self.logger.error(f"vLLM server unavailable: {self.api_unavailable_reason}")
            raise RuntimeError(f"Cannot connect to vLLM server at {self.vllm_client.base_url}. Start it with: ./start_vllm_server.sh")
        
        if self.api_available:
            self.logger.info(f"{self.api_type.upper()} API connection successful - Model: {self.selected_model}")
        else:
            self.logger.error(f"{self.api_type.upper()} API not available - Model: {self.selected_model}, Reason: {self.api_unavailable_reason}")
        
        # Enhanced cache for API responses with size management
        self.api_cache = {}
        self.cache_access_counts = {}  # Track access frequency for LRU eviction
        self.cache_enabled = True  # Allow disabling cache for testing
        self.cache_max_size = 1000  # Limit cache size to prevent memory issues
        self.cache_hits_threshold = 5  # Clear cache after 5 uses to keep it fresh
        
        # Statistics tracking
        self.stats = {
            'total_processed': 0,
            'vllm_corrections': 0,
            'cache_hits': 0,
            'language_detections': 0
        }
    
    def _init_language_detector(self):
        """Initialize language detector based on configuration."""
        if self.language_detector == 'disabled':
            self.logger.info("Language detection disabled")
            return None
        
        if self.language_detector == 'lingua' and LINGUA_AVAILABLE:
            try:
                # Initialize Lingua detector with common languages
                languages = [Language.ENGLISH, Language.FRENCH, Language.SPANISH, Language.GERMAN, Language.ITALIAN]
                detector = LanguageDetectorBuilder.from_languages(*languages).build()
                self.logger.info("Language detector initialized: Lingua")
                return detector
            except Exception as e:
                self.logger.warning(f"Failed to initialize Lingua detector: {e}")
                
        if self.language_detector == 'langdetect' and LANGDETECT_AVAILABLE:
            try:
                # langdetect doesn't need initialization, just check availability
                self.logger.info("Language detector initialized: langdetect")
                return 'langdetect'
            except Exception as e:
                self.logger.warning(f"Failed to initialize langdetect: {e}")
        
        # Fallback to other detector or disabled
        if self.language_detector != 'lingua' and LINGUA_AVAILABLE:
            try:
                languages = [Language.ENGLISH, Language.FRENCH, Language.SPANISH, Language.GERMAN, Language.ITALIAN]
                detector = LanguageDetectorBuilder.from_languages(*languages).build()
                self.logger.info("Language detector fallback: Lingua")
                return detector
            except Exception as e:
                self.logger.warning(f"Lingua fallback failed: {e}")
        
        if self.language_detector != 'langdetect' and LANGDETECT_AVAILABLE:
            self.logger.info("Language detector fallback: langdetect")
            return 'langdetect'
        
        self.logger.warning("No language detector available")
        return None
    
    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect the language of the input text with Redis caching.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Language code (e.g. 'english', 'french') or None if detection fails
        """
        if not self.lang_detector:
            return None
        
        if len(text.strip()) < 10:  # Skip very short texts
            return None
        
        # Check cache first for language detection
        if self.cache and self.cache.is_available():
            # Create cache key from text hash for privacy
            text_hash = hashlib.md5(text.encode()).hexdigest()[:16]
            cached_lang = self.cache.get('language_detection', text_hash)
            if cached_lang:
                self.logger.debug(f"Language detection cache hit: {cached_lang}")
                return cached_lang
        
        try:
            if self.lang_detector == 'langdetect':
                # Use langdetect
                detected = langdetect.detect(text)
                # Map langdetect codes to our language names
                language_map = {
                    'en': 'english',
                    'fr': 'french', 
                    'es': 'spanish',
                    'de': 'german',
                    'it': 'italian'
                }
                result = language_map.get(detected)
                if result:
                    self.stats['language_detections'] += 1
                    # Cache the successful detection
                    if self.cache and self.cache.is_available():
                        self.cache.set('language_detection', text_hash, result, ttl=TTL.LANGUAGE_DETECTION)
                return result
            
            else:
                # Use Lingua
                detected_language = self.lang_detector.detect_language_of(text)
                if detected_language:
                    # Map Lingua languages to our language names
                    language_map = {
                        Language.ENGLISH: 'english',
                        Language.FRENCH: 'french',
                        Language.SPANISH: 'spanish', 
                        Language.GERMAN: 'german',
                        Language.ITALIAN: 'italian'
                    }
                    result = language_map.get(detected_language)
                    if result:
                        self.stats['language_detections'] += 1
                        # Cache the successful detection
                        if self.cache and self.cache.is_available():
                            self.cache.set('language_detection', text_hash, result, ttl=TTL.LANGUAGE_DETECTION)
                    return result
                    
        except Exception as e:
            self.logger.warning(f"Language detection failed: {e}")
        
        return None
    
    def _manage_cache(self, cache_key, value):
        """Manage cache size and implement LRU eviction."""
        if not self.cache_enabled:
            return
            
        # Check if cache is getting too large
        if len(self.api_cache) >= self.cache_max_size:
            # Remove least recently used items (bottom 20%)
            items_to_remove = max(1, len(self.api_cache) // 5)
            
            # Sort by access count (ascending) to find least used items
            sorted_keys = sorted(self.cache_access_counts.keys(), 
                               key=lambda k: self.cache_access_counts.get(k, 0))
            
            for key in sorted_keys[:items_to_remove]:
                if key in self.api_cache:
                    del self.api_cache[key]
                if key in self.cache_access_counts:
                    del self.cache_access_counts[key]
            
            self.logger.debug(f"Cache cleanup: removed {items_to_remove} items, cache size now: {len(self.api_cache)}")
        
        # Add new item to cache
        self.api_cache[cache_key] = value
        self.cache_access_counts[cache_key] = 1
    
    def set_custom_instructions(self, use_case: str, instructions: str, api_key_id: str = None) -> None:
        """Set custom instructions for a specific use case (persistent storage)."""
        if api_key_id:
            # Store in database for persistence
            try:
                import sqlite3
                from datetime import datetime
                
                with sqlite3.connect('api_keys.db') as conn:
                    # Use INSERT OR REPLACE for upsert behavior
                    conn.execute('''
                        INSERT OR REPLACE INTO custom_instructions 
                        (api_key_id, use_case, instructions, updated_at)
                        VALUES (?, ?, ?, ?)
                    ''', (api_key_id, use_case, instructions, datetime.utcnow().isoformat()))
                    conn.commit()
                
                self.logger.info(f"Custom instructions stored in database for API key {api_key_id}, use case: {use_case}")
            except Exception as e:
                self.logger.error(f"Failed to store custom instructions in database: {e}")
                # Fallback to memory storage
                self.custom_instructions[use_case] = instructions
        else:
            # Fallback to memory storage (for demo mode or when no API key)
            self.custom_instructions[use_case] = instructions
            self.logger.info(f"Custom instructions set in memory for use case: {use_case}")

    def get_custom_instructions(self, use_case: str = None, api_key_id: str = None) -> Union[str, Dict[str, str]]:
        """Get custom instructions for a specific use case or all instructions (from database)."""
        if api_key_id:
            # Read from database
            try:
                import sqlite3
                
                with sqlite3.connect('api_keys.db') as conn:
                    conn.row_factory = sqlite3.Row
                    
                    if use_case is None:
                        # Get all instructions for this API key
                        cursor = conn.execute('''
                            SELECT use_case, instructions 
                            FROM custom_instructions 
                            WHERE api_key_id = ?
                        ''', (api_key_id,))
                        
                        results = cursor.fetchall()
                        return {row['use_case']: row['instructions'] for row in results}
                    else:
                        # Get specific use case for this API key
                        cursor = conn.execute('''
                            SELECT instructions 
                            FROM custom_instructions 
                            WHERE api_key_id = ? AND use_case = ?
                        ''', (api_key_id, use_case))
                        
                        result = cursor.fetchone()
                        return result['instructions'] if result else ""
                        
            except Exception as e:
                self.logger.error(f"Failed to get custom instructions from database: {e}")
                # Fallback to memory
                if use_case is None:
                    return self.custom_instructions.copy()
                return self.custom_instructions.get(use_case, "")
        else:
            # Fallback to memory storage (for demo mode)
            if use_case is None:
                return self.custom_instructions.copy()
            return self.custom_instructions.get(use_case, "")

    def remove_custom_instructions(self, use_case: str, api_key_id: str = None) -> bool:
        """Remove custom instructions for a specific use case (from database)."""
        if api_key_id:
            # Remove from database
            try:
                import sqlite3
                
                with sqlite3.connect('api_keys.db') as conn:
                    cursor = conn.execute('''
                        DELETE FROM custom_instructions 
                        WHERE api_key_id = ? AND use_case = ?
                    ''', (api_key_id, use_case))
                    
                    rows_deleted = cursor.rowcount
                    conn.commit()
                    
                    if rows_deleted > 0:
                        self.logger.info(f"Custom instructions removed from database for API key {api_key_id}, use case: {use_case}")
                        return True
                    else:
                        return False
                        
            except Exception as e:
                self.logger.error(f"Failed to remove custom instructions from database: {e}")
                # Fallback to memory
                if use_case in self.custom_instructions:
                    del self.custom_instructions[use_case]
                    return True
                return False
        else:
            # Fallback to memory storage (for demo mode)
            if use_case in self.custom_instructions:
                del self.custom_instructions[use_case]
                self.logger.info(f"Custom instructions removed from memory for use case: {use_case}")
                return True
            return False

    def clear_custom_instructions(self, api_key_id: str = None) -> None:
        """Clear all custom instructions (from database)."""
        if api_key_id:
            # Clear from database
            try:
                import sqlite3
                
                with sqlite3.connect('api_keys.db') as conn:
                    conn.execute('''
                        DELETE FROM custom_instructions 
                        WHERE api_key_id = ?
                    ''', (api_key_id,))
                    conn.commit()
                
                self.logger.info(f"All custom instructions cleared from database for API key: {api_key_id}")
            except Exception as e:
                self.logger.error(f"Failed to clear custom instructions from database: {e}")
                # Fallback to memory
                self.custom_instructions.clear()
        else:
            # Fallback to memory storage (for demo mode)
            self.custom_instructions.clear()
            self.logger.info("All custom instructions cleared from memory")
    
    def _sanitize_language_parameter(self, language_param: str) -> Optional[str]:
        """
        Sanitize and validate language parameter to prevent prompt injection attacks.
        
        Args:
            language_param: Raw language parameter from user input
            
        Returns:
            Sanitized language string if valid, None if suspicious/invalid
        """
        import re
        
        # Remove any whitespace
        language_param = language_param.strip()
        
        # Check length - legitimate language codes are short
        if len(language_param) > 50:
            self.logger.warning(f"Language parameter too long, rejecting: {language_param[:50]}...")
            return None
        
        # Only allow alphanumeric, hyphens, underscores - block injection attempts
        if not re.match(r'^[a-zA-Z0-9_-]+$', language_param):
            self.logger.warning(f"Language parameter contains invalid characters, rejecting: {language_param}")
            return None
        
        # Block suspicious patterns that could be injection attempts
        suspicious_patterns = [
            r'ignore',
            r'instruction',
            r'previous',
            r'system',
            r'prompt',
            r'override',
            r'admin',
            r'root',
            r'execute',
            r'eval',
            r'script'
        ]
        
        language_lower = language_param.lower()
        for pattern in suspicious_patterns:
            if pattern in language_lower:
                self.logger.warning(f"Language parameter contains suspicious content, rejecting: {language_param}")
                return None
        
        # Passed validation
        return language_param

    def _build_language_specific_system_message(self, detected_language: Optional[str]) -> str:
        """
        Build language-specific additions to the system message.
        
        Args:
            detected_language: The detected language code
            
        Returns:
            Additional system message content for the detected language
        """
        if not detected_language or detected_language not in LANGUAGE_RULES:
            return ""
        
        language_rules = LANGUAGE_RULES[detected_language]
        if not language_rules:
            return ""
        
        rules_text = "\n\nLANGUAGE-SPECIFIC RULES:\n"
        for rule_name, rule_data in language_rules.items():
            rules_text += f"- {rule_data['rule']}\n"
        
        return rules_text
    
    def process_text(self, text: str, options: Optional[Dict[str, bool]] = None, language: Optional[str] = None, use_case: Optional[str] = None) -> Dict[str, Any]:
        """
        AI-first processing pipeline with language detection and language-specific rules.
        
        Args:
            text: Input text to process
            options: Processing options (maintained for compatibility, but AI-first is always used)
            language: Override language for processing (e.g., 'french', 'english'). If None, auto-detect
            use_case: Apply custom instructions for specific use case (e.g., 'code_comments', 'academic_writing')
            
        Returns:
            Complete analysis result with AI corrections and statistics
        """
        start_time = time.time()
        
        if not self.api_available:
            detailed_error = f"{self.api_type.upper()} API not available - cannot process text. Reason: {self.api_unavailable_reason}"
            self.logger.error(detailed_error)
            return {
                'status': 'error',
                'message': f'{self.api_type.upper()} API not available. {self.api_unavailable_reason}',
                'original_text': text,
                'corrections': [],
                'processed_text': text,
                'statistics': {
                    'total_errors': 0,
                    'processing_time': f"{time.time() - start_time:.3f}s",
                    'api_available': False,
                    'api_type': self.api_type,
                    'ai_first_mode': True,
                    'unavailable_reason': self.api_unavailable_reason
                }
            }
        
        # Use AI for comprehensive analysis
        try:
            ai_corrections = self._comprehensive_ai_check(text, language_override=language, use_case=use_case)
            all_corrections = ai_corrections
        except Exception as e:
            self.logger.error(f"AI processing failed: {e}")
            return {
                'status': 'error',
                'message': f'AI processing failed: {e}',
                'original_text': text,
                'corrections': [],
                'processed_text': text,
                'statistics': {
                    'total_errors': 0,
                    'processing_time': f"{time.time() - start_time:.3f}s",
                    'api_available': self.api_available,
                    'api_type': self.api_type,
                    'ai_first_mode': True
                }
            }
        
        # Sort corrections by position
        all_corrections.sort(key=lambda c: c.position[0])
        
        # Apply corrections to create processed text
        processed_text = self._apply_corrections(text, all_corrections)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Update statistics
        self.stats['total_processed'] += 1
        if all_corrections:
            self.stats['vllm_corrections'] += 1
        
        # Prepare response
        result = {
            'status': 'success',
            'original_text': text,
            'corrections': [
                {
                    'type': c.type,
                    'position': list(c.position),
                    'original': c.original,
                    'suggestion': c.suggestion,
                    'source': c.source
                }
                for c in all_corrections
            ],
            'processed_text': processed_text,
            'statistics': {
                'total_errors': len(all_corrections),
                'spelling_errors': len([c for c in all_corrections if c.type == 'spelling']),
                'grammar_errors': len([c for c in all_corrections if c.type == 'grammar']),
                'style_suggestions': len([c for c in all_corrections if c.type == 'style']),
                'processing_time': f"{processing_time:.3f}s",
                'api_available': self.api_available,
                'api_type': self.api_type,
                'ai_first_mode': True,
                'detected_language': self.detect_language(text) if len(text) >= 10 else None
            }
        }
        
        return result
    
    def check_spelling(self, text: str, language: Optional[str] = None, use_case: Optional[str] = None) -> Dict[str, Any]:
        """
        Check text for spelling errors only using AI with a specialized prompt.
        
        Args:
            text: Input text to process
            language: Override language for processing (e.g., 'french', 'english'). If None, auto-detect
            use_case: Apply custom instructions for specific use case (e.g., 'code_comments', 'academic_writing')
            
        Returns:
            Analysis result with ONLY spelling corrections
        """
        try:
            # Use the specialized spelling-only AI check
            spelling_corrections = self._spelling_only_ai_check(text, language_override=language, use_case=use_case)
            
            # Apply only spelling corrections to text
            processed_text = text
            if spelling_corrections:
                # Sort corrections by position (reverse order to maintain positions)
                sorted_corrections = sorted(spelling_corrections, key=lambda x: x.position[0] if x.position else 0, reverse=True)
                for correction in sorted_corrections:
                    if correction.original and correction.suggestion and correction.position:
                        start, end = correction.position
                        processed_text = processed_text[:start] + correction.suggestion + processed_text[end:]
            
            # Build statistics
            spelling_count = len(spelling_corrections)
            
            return {
                'status': 'success',
                'original_text': text,
                'processed_text': processed_text,
                'corrections': [c.to_dict() for c in spelling_corrections],
                'statistics': {
                    'total_corrections': spelling_count,
                    'spelling_corrections': spelling_count,
                    'grammar_corrections': 0,
                    'style_suggestions': 0,
                    'total_errors': spelling_count,
                    'spelling_errors': spelling_count,
                    'grammar_errors': 0,
                    'processing_time': '0.000s',  # Will be updated by caller
                    'detected_language': self.detect_language(text) if len(text) >= 10 else None,
                    'api_type': self.api_type,
                    'api_available': self.api_available
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in check_spelling: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'original_text': text,
                'processed_text': text,
                'corrections': [],
                'statistics': {'total_corrections': 0}
            }
    
    def _spelling_only_ai_check(self, text: str, language_override: Optional[str] = None, use_case: Optional[str] = None) -> List[Correction]:
        """
        Send text to AI for SPELLING-ONLY checking with a specialized prompt.
        
        Args:
            text: Input text to analyze
            language_override: Override language (e.g., 'french', 'english'). If None, auto-detect
            use_case: Apply custom instructions for specific use case. If None, use default processing
            
        Returns:
            List of AI-generated SPELLING corrections only
        """
        try:
            # Detect language if not overridden
            detected_language = None
            if not language_override:
                detected_language = self.detect_language(text)
                self.stats['language_detections'] += 1
            
            # Build language instruction if provided
            language_instruction = ""
            if language_override and language_override != 'auto':
                # Validate and sanitize language parameter to prevent prompt injection
                sanitized_language = self._sanitize_language_parameter(language_override)
                if sanitized_language:
                    language_instruction = f"""

LANGUAGE/DIALECT CONTEXT: The text should be corrected using {sanitized_language} conventions.
- DO NOT flag regional spelling variants as errors (e.g., "realise" vs "realize", "colour" vs "color")
- ONLY suggest corrections for words that are actually misspelled
- If a word is correctly spelled in ANY variant of the language, do not mark it as an error"""
            
            # Create specialized spelling-only prompt
            system_message = """You are an expert proofreader. Find spelling mistakes in the text. Be thorough but focused ONLY on spelling errors.

WHAT TO CORRECT (Spelling Errors):
1. Words with wrong letters: "teh" → "the", "recieve" → "receive", "seperate" → "separate"
2. Common misspellings: "definately" → "definitely", "beleive" → "believe", "writting" → "writing"
3. Letter transpositions: "sentance" → "sentence", "erors" → "errors", "freinds" → "friends"
4. Wrong letter combinations: "speling" → "spelling", "queivoca" → "equivoca"

WHAT NOT TO CORRECT (Not Spelling Errors):
1. Word choice from different languages: "riguardo" (Italian) should NOT become "respecto" (Spanish)
2. Regional spelling variants: "realise/colour" (British) vs "realize/color" (American) - both correct
3. Grammar issues: "I are" → "I am", "he have" → "he has" (grammar, not spelling)
4. Missing words: "go store" → "go to store" (missing word, not misspelling)
5. Accent marks on otherwise correct words: "politicos" → "políticos" (word choice, not spelling)
6. Verb conjugation errors: "are" is correctly spelled, even if grammatically wrong with "I"

KEY DISTINCTION:
- SPELLING ERROR = Wrong letters in a word that should exist in that language
- WORD CHOICE = Using a correct word from wrong language/context

EXAMPLES:
✅ CORRECT THESE (Real spelling errors):
- "teh" → "the"
- "recieve" → "receive" 
- "queivoca" → "equivoca" (wrong letters in Spanish word)
- "definately" → "definitely"
- "sentance" → "sentence"

❌ DON'T CORRECT THESE (Not spelling errors):
- "riguardo" → "respecto" (both are correct words, just different languages)
- "colour" → "color" (regional variants)
- "politicos" → "políticos" (accent preference, not misspelling)
- "I are" → "I am" (grammar error - "are" is spelled correctly)
- "he have" → "he has" (grammar error - "have" is spelled correctly)

Respond with JSON only:
{
  "corrected_text": "text with spelling corrections applied",
  "corrections": [
    {
      "original": "misspelled word",
      "suggestion": "correct spelling", 
      "type": "spelling"
    }
  ]
}

If no spelling errors: {"corrected_text": "[original text]", "corrections": []}"""
            
            # Add language instruction if provided
            if language_instruction:
                system_message += language_instruction
            
            # Add custom instructions for the specific use case
            if use_case:
                # Get custom instructions from database (with fallback to memory)
                custom_instructions = ""
                
                # Try to get API key from current request context
                try:
                    from flask import request as flask_request
                    api_key_id = getattr(flask_request, 'api_key_info', {}).get('key_id') if flask_request else None
                    
                    if api_key_id:
                        custom_instructions = self.get_custom_instructions(use_case, api_key_id)
                    else:
                        # Fallback to memory storage
                        custom_instructions = self.custom_instructions.get(use_case, "")
                except:
                    # If Flask context is not available, use memory storage
                    custom_instructions = self.custom_instructions.get(use_case, "")
                
                if custom_instructions:
                    system_message += f"\n\nCUSTOM INSTRUCTIONS FOR '{use_case.upper()}':\n{custom_instructions}"
            
            # Create user message
            user_message = f"Check this text for spelling errors only:\n\n{text}"
            
            # Call AI API
            if self.api_type == 'vllm':
                # Use vLLM for local inference
                prompt = f"{system_message}\n\n{user_message}"
                generated_text = self.vllm_client.generate(
                    prompt=prompt,
                    max_tokens=1000,
                    temperature=0.2
                )
                response = {'text': generated_text} if generated_text else None
            
            if not response or not response.get('text'):
                self.logger.warning(f"Empty response from {self.api_type.upper()} API for spelling check")
                self.logger.debug(f"Response was: {response}")
                return []
            
            self.logger.debug(f"AI response for spelling check: {response.get('text', '')[:200]}...")
            
            # Parse the response
            corrections = self._parse_complete_correction_response(response['text'], text)
            
            # Filter to ensure only spelling corrections (extra safety)
            spelling_corrections = [c for c in corrections if c.type == 'spelling']
            
            return spelling_corrections
            
        except Exception as e:
            self.logger.error(f"Spelling-only AI check failed: {e}")
            return []

    def _comprehensive_ai_check(self, text: str, language_override: Optional[str] = None, use_case: Optional[str] = None) -> List[Correction]:
        """
        Send text to AI (OpenAI or Gemini) for comprehensive spelling, grammar, and style checking.
        
        Args:
            text: Input text to analyze
            language_override: Override language (e.g., 'french', 'english'). If None, auto-detect
            use_case: Apply custom instructions for specific use case. If None, use default processing
            
        Returns:
            List of AI-generated corrections
        """
        try:
            # Use language override or detect language for language-specific rules
            if language_override and language_override != 'auto':
                detected_language = language_override
                self.logger.info(f"Using language override: {language_override}")
            else:
                detected_language = self.detect_language(text)
                if detected_language:
                    self.logger.info(f"Auto-detected language: {detected_language}")
            
            language_rules = self._build_language_specific_system_message(detected_language)
            
            # Check Redis cache first (faster and shared across workers)
            text_hash = hashlib.md5(text.encode()).hexdigest()[:16]
            redis_cache_key = f"{self.api_type}:{text_hash}:{detected_language or 'unknown'}:{use_case or 'default'}"
            
            if self.cache and self.cache.is_available():
                cached_result = self.cache.get('ai_responses', redis_cache_key)
                if cached_result:
                    self.stats['cache_hits'] += 1
                    self.logger.debug(f"Redis cache hit for AI response")
                    # Convert back from serialized format
                    if isinstance(cached_result, list) and cached_result and isinstance(cached_result[0], dict):
                        return [Correction.from_dict(item) for item in cached_result]
                    return cached_result
            
            # Check in-memory cache as fallback
            cache_key = f"comprehensive:{self.api_type}:{hash(text)}:{detected_language or 'unknown'}:{use_case or 'default'}"
            if self.cache_enabled and cache_key in self.api_cache:
                self.stats['cache_hits'] += 1
                # Track cache access for LRU management
                self.cache_access_counts[cache_key] = self.cache_access_counts.get(cache_key, 0) + 1
                return self.api_cache[cache_key]
            
            # Build system message with language specification
            language_instruction = ""
            if language_override and language_override != 'auto':
                # Validate and sanitize language parameter to prevent prompt injection
                sanitized_language = self._sanitize_language_parameter(language_override)
                if sanitized_language:
                    language_instruction = f"""

LANGUAGE/DIALECT CONTEXT: The text should be corrected using {sanitized_language} conventions.
- DO NOT flag regional spelling variants as errors (e.g., "realise" vs "realize", "colour" vs "color")
- ONLY suggest corrections that align with {sanitized_language} if the word is actually misspelled
- If a word is correctly spelled in ANY English variant, do not mark it as an error"""
            
            system_message = f"""You are an expert proofreader. Find ONLY actual spelling mistakes, grammar errors, and style issues.

CRITICAL RULES:
1. Regional spelling variants are NOT errors (British: realise/colour, American: realize/color)
2. Only flag words that are actually misspelled or grammatically incorrect
3. Do not "correct" valid words to different regional variants{language_instruction}

CRITICAL: Respond with VALID JSON only. Follow this EXACT format:

{{
  "corrected_text": "the fully corrected text",
  "corrections": [
    {{
      "original": "exact word/phrase with error",
      "suggestion": "corrected version", 
      "type": "spelling"
    }},
    {{
      "original": "another error",
      "suggestion": "corrected version",
      "type": "grammar"
    }}
  ]
}}

JSON REQUIREMENTS (CRITICAL):
- Use double quotes for ALL strings
- Add commas between array elements  
- NO trailing commas after last element
- NO extra text outside JSON
- Escape quotes inside strings with backslash
- Test your JSON is valid before responding

If no errors found: {{"corrected_text": "[original text]", "corrections": []}}

EXAMPLES:
- "realise" in British context: NOT an error
- "realize" in American context: NOT an error  
- "realis" in any context: IS an error → "realise" or "realize"
- "teh": IS an error → "the"

Only flag actual mistakes, never valid regional variants."""
            
            # Add custom instructions for the specific use case
            if use_case:
                # Get custom instructions from database (with fallback to memory)
                custom_instructions = ""
                
                # Try to get API key from current request context
                try:
                    from flask import request as flask_request
                    api_key_id = getattr(flask_request, 'api_key_info', {}).get('key_id') if flask_request else None
                    
                    if api_key_id:
                        custom_instructions = self.get_custom_instructions(use_case, api_key_id)
                    else:
                        # Fallback to memory storage
                        custom_instructions = self.custom_instructions.get(use_case, "")
                        
                except Exception as e:
                    # If flask context not available, fallback to memory
                    custom_instructions = self.custom_instructions.get(use_case, "")
                    self.logger.debug(f"Using memory fallback for custom instructions: {e}")
                
                if custom_instructions:
                    system_message += f"\n\nCUSTOM INSTRUCTIONS FOR {use_case.upper()}:\n{custom_instructions}"
                    self.logger.debug(f"Applied custom instructions for use case: {use_case}")
            
            # Add language-specific rules if detected
            system_message += language_rules

            user_message = f"Fix all errors in this text:\n\n{text}"
            
            # Call appropriate API based on selected model
            if self.api_type == 'vllm':
                self.logger.debug(f"🤖 Calling vLLM - Model: {self.vllm_client.model}, Language: {detected_language or 'unknown'}")
                prompt = f"{system_message}\n\n{user_message}"
                generated_text = self.vllm_client.generate(
                    prompt=prompt,
                    max_tokens=1024,
                    temperature=0.2
                )
                
                if generated_text:
                    corrections = self._parse_complete_correction_response(generated_text, text)
                else:
                    corrections = []
            
            # Cache the result with smart cache management
            if self.cache_enabled:
                self._manage_cache(cache_key, corrections)
            
            # Also cache in Redis for cross-worker sharing
            if self.cache and self.cache.is_available():
                # Convert corrections to serializable format
                serializable_corrections = [correction.to_dict() for correction in corrections]
                self.cache.set('ai_responses', redis_cache_key, serializable_corrections, ttl=TTL.API_RESPONSES)
                
            return corrections
            
        except Exception as e:
            self.logger.error(f"Comprehensive AI check failed: {e}")
            return []
    
    def _parse_complete_correction_response(self, response: str, text: str) -> List[Correction]:
        """Parse structured correction response with individual corrections."""
        corrections = []
        
        try:
            # Handle empty or None responses
            if not response or not response.strip():
                self.logger.warning("Empty response from AI API")
                return corrections
            
            # Strip markdown code blocks if present
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            # Handle empty response after cleaning
            if not cleaned_response:
                self.logger.warning("Empty response after cleaning markdown")
                return corrections
            
            # Clean up common JSON issues
            cleaned_response = self._clean_json_response(cleaned_response)
            
            # Parse JSON with better error handling
            try:
                result = json.loads(cleaned_response)
            except json.JSONDecodeError as json_error:
                # Log the problematic response for debugging
                self.logger.warning(f"JSON parsing failed, attempting repair. Error: {json_error}")
                self.logger.debug(f"Problematic response (first 500 chars): {cleaned_response[:500]}")
                
                # Try json-repair library first (most robust)
                try:
                    import json_repair
                    repaired_response = json_repair.repair(cleaned_response)
                    result = json.loads(repaired_response)
                    self.logger.debug("JSON repaired successfully using json-repair library")
                except Exception as repair_error:
                    self.logger.debug(f"json-repair library failed: {repair_error}")
                    
                    # Fallback to enhanced regex repair
                    repaired_response = self._repair_json_response_enhanced(cleaned_response)
                    if repaired_response:
                        result = json.loads(repaired_response)
                        self.logger.debug("JSON repaired using enhanced regex fallback")
                    else:
                        # If all repair attempts fail, log and continue with empty result
                        self.logger.warning(f"All JSON repair attempts failed for: {json_error}")
                        return corrections
            
            # Extract corrections array
            corrections_array = result.get('corrections', [])
            
            # Track used positions and seen corrections to handle duplicates and multiple instances
            used_positions = set()
            seen_corrections = set()  # Track (original, suggestion) pairs to avoid duplicates
            
            for correction_data in corrections_array:
                original = correction_data.get('original', '')
                suggestion = correction_data.get('suggestion', '')
                correction_type = correction_data.get('type', 'grammar')

                # Skip empty corrections
                if not original or not suggestion:
                    continue
                    
                # Create a unique key for this correction type
                correction_key = (original.lower(), suggestion.lower())
                
                # Skip if we've already processed this exact correction
                if correction_key in seen_corrections:
                    self.logger.debug(f"Skipping duplicate correction: '{original}' -> '{suggestion}'")
                    continue
                
                seen_corrections.add(correction_key)
                
                # Find positions of original text in input (context-aware for homophones)
                positions = self._find_best_position(text, original, suggestion, used_positions)
                
                self.logger.debug(f"Processing correction: '{original}' -> '{suggestion}'")
                self.logger.debug(f"Found {len(positions)} positions: {positions}")
                
                for pos in positions:
                    # Show context around each position for debugging
                    context_start = max(0, pos - 15)
                    context_end = min(len(text), pos + len(original) + 15)
                    context = text[context_start:context_end]
                    self.logger.debug(f"Position {pos}: '{original}' in context '...{context}...'")
                    
                    correction = Correction(
                        type=correction_type,
                        position=(pos, pos + len(original)),
                        original=original,
                        suggestion=suggestion,
                        source=self.api_type
                    )
                    corrections.append(correction)
                    # Mark this position as used
                    used_positions.add((pos, pos + len(original)))
            
        except Exception as e:
            self.logger.error(f"Failed to parse correction response: {e}")

        
        return corrections
    
    def _clean_json_response(self, response: str) -> str:
        """Clean common JSON formatting issues in AI responses."""
        import re
        
        # Remove control characters that break JSON parsing
        response = re.sub(r'[\x00-\x1f\x7f]', '', response)
        
        # Fix common escape sequence issues
        response = response.replace('\\"', '"')
        response = response.replace('\\n', ' ')
        response = response.replace('\\t', ' ')
        
        # Remove any trailing commas before closing brackets/braces
        response = re.sub(r',(\s*[}\]])', r'\1', response)
        
        return response
    
    def _repair_json_response_enhanced(self, response: str) -> str:
        """Attempt to repair malformed JSON responses with enhanced logic."""
        import re
        
        try:
            # Try to find and extract just the JSON part if there's extra text
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                potential_json = json_match.group(0)
                
                # Multiple repair strategies
                repair_attempts = [
                    self._fix_missing_commas,
                    self._fix_unterminated_strings,
                    self._fix_trailing_commas,
                    self._fix_unescaped_quotes,
                    self._fix_malformed_arrays
                ]
                
                for repair_func in repair_attempts:
                    try:
                        repaired = repair_func(potential_json)
                        if repaired:
                            # Test if the repair worked
                            json.loads(repaired)
                            self.logger.debug(f"JSON repaired using {repair_func.__name__}")
                            return repaired
                    except (json.JSONDecodeError, Exception):
                        continue
                
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # If all repair attempts fail, return None
        return None
    
    def _fix_missing_commas(self, json_str: str) -> str:
        """Fix missing commas between JSON elements with enhanced patterns."""
        import re
        
        # Enhanced comma fixing patterns
        
        # 1. Missing commas between object properties (most common)
        json_str = re.sub(r'"\s*(\n\s*)"([^"]+)":', r'",\1"\2":', json_str)
        
        # 2. Missing commas between array elements (objects)
        json_str = re.sub(r'}\s*(\n\s*){', r'},\1{', json_str)
        
        # 3. Missing commas after any value before new property
        json_str = re.sub(r'(["\d}\]])\s*(\n\s*)"([^"]+)":', r'\1,\2"\3":', json_str)
        
        # 4. Missing commas in single-line JSON (char 172 type errors)
        json_str = re.sub(r'}\s*{', r'},{', json_str)  # Objects in array
        json_str = re.sub(r'"\s*"([^"]*)":', r'","\1":', json_str)  # Properties
        
        # 5. Missing commas after quoted values
        json_str = re.sub(r'("(?:[^"\\]|\\.)*")\s*("(?:[^"\\]|\\.)*":\s*)', r'\1,\2', json_str)
        
        # 6. Missing commas after numbers/booleans
        json_str = re.sub(r'(\d|true|false)\s*(\n\s*)"([^"]+)":', r'\1,\2"\3":', json_str)
        
        return json_str
    
    def _fix_unterminated_strings(self, json_str: str) -> str:
        """Fix unterminated strings by adding closing quotes."""
        lines = json_str.split('\n')
        fixed_lines = []
        
        for line in lines:
            # If line has an odd number of quotes and doesn't end with quote, comma, or brace
            if line.count('"') % 2 == 1 and not line.strip().endswith(('"', ',', '}', ']')):
                if ':' in line and not line.strip().endswith('"'):
                    line = line.rstrip() + '"'
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_trailing_commas(self, json_str: str) -> str:
        """Remove trailing commas before closing brackets/braces."""
        import re
        return re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    def _fix_unescaped_quotes(self, json_str: str) -> str:
        """Fix unescaped quotes within string values."""
        import re
        
        # This is tricky - try to escape quotes that are clearly within string values
        # Look for patterns like: "text with "quote" inside"
        def escape_inner_quotes(match):
            full_match = match.group(0)
            # Simple heuristic: if there are quotes inside, escape them
            if full_match.count('"') > 2:
                # Keep first and last quote, escape middle ones
                content = full_match[1:-1]  # Remove outer quotes
                content = content.replace('"', '\\"')
                return f'"{content}"'
            return full_match
        
        # Apply to string values (between : and , or })
        json_str = re.sub(r':\s*"([^"]*"[^"]*)"(?=[,}])', escape_inner_quotes, json_str)
        
        return json_str
    
    def _fix_malformed_arrays(self, json_str: str) -> str:
        """Fix malformed arrays with missing brackets."""
        import re
        
        # If corrections section is malformed, try to fix it
        if '"corrections":' in json_str and not re.search(r'"corrections":\s*\[', json_str):
            # Try to add missing opening bracket
            json_str = re.sub(r'"corrections":\s*{', '"corrections": [{', json_str)
            # Try to add missing closing bracket before final }
            json_str = re.sub(r'}\s*}$', '}]}', json_str)
        
        return json_str
    
    def _find_best_position(self, text: str, target: str, suggestion: str, used_positions: set) -> List[int]:
        """
        Find the best position(s) for a correction, using context clues to avoid
        correcting instances that are already correct.
        
        Args:
            text: The text to search in
            target: The string to find
            suggestion: The suggested replacement
            used_positions: Set of (start, end) tuples already used
            
        Returns:
            List of start positions where target should be corrected
        """
        positions = []
        start = 0
        
        # Common homophones that need smart positioning
        HOMOPHONES = {
            'there', 'their', 'theyre', "they're",
            'your', 'youre', "you're", 
            'its', "it's",
            'were', 'where', 'wear',
            'to', 'too', 'two',
            'than', 'then',
            'accept', 'except',
            'affect', 'effect',
            'lose', 'loose'
        }
        
        # Context patterns that suggest correct vs incorrect usage
        CORRECT_CONTEXTS = {
            'there': [
                r'\bthere\s+(is|are|was|were|have|has|will|being)\b',  # "there are", "there have been"
                r'\b(over|out|up|down|right|left)\s+there\b',  # positional "there"
                r'\bthere\s*,',  # "there, in the distance" 
            ],
            'their': [
                r'\btheir\s+\w+',  # "their house", "their car" - possessive before nouns
            ],
            'your': [
                r'\byour\s+\w+',  # "your house" - possessive before nouns  
            ],
            'its': [
                r'\bits\s+\w+',  # "its color" - possessive before nouns
            ]
        }
        
        is_homophone = target.lower() in HOMOPHONES
        all_positions = []
        
        # Find all instances first
        while True:
            pos = text.find(target, start)
            if pos == -1:
                break
                
            # Check if this position overlaps with any used position
            target_end = pos + len(target)
            overlap = False
            
            for used_start, used_end in used_positions:
                if not (target_end <= used_start or pos >= used_end):
                    overlap = True
                    break
                    
            if not overlap:
                # For standalone words like "i", ensure it's actually a standalone word
                if target.lower() == 'i':
                    # Check if it's a standalone word (surrounded by whitespace or punctuation)
                    is_standalone = True
                    if pos > 0 and text[pos-1].isalnum():
                        is_standalone = False
                    if pos + len(target) < len(text) and text[pos + len(target)].isalnum():
                        is_standalone = False
                    
                    if is_standalone:
                        all_positions.append(pos)
                else:
                    all_positions.append(pos)
            
            start = pos + 1
        
        # For homophones, use context analysis to find incorrect instances
        if is_homophone and len(all_positions) > 1:
            target_lower = target.lower()
            self.logger.debug(f"Found {len(all_positions)} instances of homophone '{target}' at positions: {all_positions}")
            
            for pos in all_positions:
                # Get context around this position (20 chars each side)
                context_start = max(0, pos - 20)
                context_end = min(len(text), pos + len(target) + 20)
                context = text[context_start:context_end].lower()
                
                # Check if this instance appears to be correct based on context
                is_likely_correct = False
                
                # Check if this instance appears to be correct based on context
                if target_lower in CORRECT_CONTEXTS:
                    for pattern in CORRECT_CONTEXTS[target_lower]:
                        if re.search(pattern, context, re.IGNORECASE):
                            is_likely_correct = True
                            self.logger.debug(f"Position {pos} appears correct due to pattern: {pattern}")
                            break
                
                # If this instance seems incorrect (or we can't determine), include it
                if not is_likely_correct:
                    positions.append(pos)
                    self.logger.debug(f"Position {pos} selected for correction (context: '{context.strip()}')")
                else:
                    self.logger.debug(f"Position {pos} skipped (appears correct)")
            
            # If we couldn't find a clearly incorrect instance, fall back to first
            if not positions and all_positions:
                positions.append(all_positions[0])
                self.logger.debug(f"No clearly incorrect instance found, using first position {all_positions[0]}")
                
        else:
            # For non-homophones or single instances, return all positions
            positions = all_positions
            
        self.logger.debug(f"Final result for '{target}': {len(positions)} positions selected: {positions}")
        return positions
        
    def _find_all_positions(self, text: str, target: str, used_positions: set) -> List[int]:
        """Legacy method - now delegates to _find_best_position for better accuracy."""
        return self._find_best_position(text, target, '', used_positions)
    
    def _apply_corrections(self, text: str, corrections: List[Correction]) -> str:
        """Apply corrections to text, handling overlapping corrections."""
        if not corrections:
            return text
        
        # Sort corrections by position (reverse order to maintain indices)
        sorted_corrections = sorted(corrections, key=lambda c: c.position[0], reverse=True)
        
        result = text
        applied_positions = []
        
        for correction in sorted_corrections:
            start, end = correction.position
            
            # Skip corrections with invalid positions
            if start < 0 or end <= start or start >= len(result):
                continue
            
            # Check for overlaps with already applied corrections
            overlaps = False
            for applied_start, applied_end in applied_positions:
                if not (end <= applied_start or start >= applied_end):
                    overlaps = True
                    break
            
            if not overlaps:
                # Apply the correction
                result = result[:start] + correction.suggestion + result[end:]
                # Adjust future positions based on length change
                length_diff = len(correction.suggestion) - (end - start)
                applied_positions = [(s + length_diff if s >= start else s, 
                                    e + length_diff if e > start else e) 
                                   for s, e in applied_positions]
                applied_positions.append((start, start + len(correction.suggestion)))
        
        return result
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        languages = ['en_US', 'en_GB', 'es_ES', 'fr_FR', 'de_DE', 'it_IT']
        return languages
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current processing statistics."""
        return {
            'total_processed': self.stats['total_processed'],
            'vllm_corrections': self.stats['vllm_corrections'],
            'cache_hits': self.stats['cache_hits'],
            'language_detections': self.stats['language_detections'],
            'api_available': self.api_available,
            'api_type': self.api_type,
            'api_unavailable_reason': self.api_unavailable_reason,
            'language_detector_available': self.lang_detector is not None,
            'cache_size': len(self.api_cache),
            'cache_enabled': self.cache_enabled
        }
    
    def get_api_status(self) -> Dict[str, Any]:
        """Get detailed vLLM API status for debugging."""
        return {
            'api_type': 'vllm',
            'available': self.api_available,
            'unavailable_reason': self.api_unavailable_reason,
            'url': self.vllm_client.base_url if self.vllm_client else None,
            'model': self.selected_model,
            'vllm_available': VLLM_AVAILABLE
        }
    
    def clear_cache(self) -> None:
        """Clear the vLLM API response cache."""
        self.api_cache.clear()
        self.logger.info("vLLM cache cleared")
    
    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable caching for testing purposes."""
        self.cache_enabled = enabled
        self.logger.info(f"{self.api_type.upper()} cache {'enabled' if enabled else 'disabled'}")
        
    def disable_cache(self) -> None:
        """Disable caching and clear existing cache - useful for testing."""
        self.cache_enabled = False
        self.api_cache.clear()
        self.logger.info("vLLM cache disabled and cleared for testing")
        
    def enable_cache(self) -> None:
        """Re-enable caching."""
        self.cache_enabled = True
        self.logger.info(f"{self.api_type.upper()} cache re-enabled") 

    def assess_comment_quality(self, comment: str, rating_context: Optional[str] = None, 
                              enable_quality_assessment: bool = True) -> Dict[str, Any]:
        """
        Assess the overall quality of a comment in the context of a rating task.
        
        This method evaluates comment quality based on multiple factors:
        - Grammar and spelling errors
        - Comment length and completeness
        - Conceptual clarity and relevance
        - Appropriateness for rating task context
        - Overall coherence and helpfulness
        
        Args:
            comment: The comment text to assess
            rating_context: Optional context about the rating task
            enable_quality_assessment: Feature flag to enable/disable this assessment
            
        Returns:
            Dictionary containing:
            - status: 'success' or 'error'
            - quality_score: Numerical score (1-10)
            - quality_level: 'excellent', 'good', 'fair', 'poor'
            - assessment: Detailed quality assessment explanation
            - factors: Breakdown of quality factors analyzed
            - suggestions: Improvement suggestions if applicable
            - comment_analysis: Technical analysis (length, errors, etc.)
        """
        if not enable_quality_assessment:
            return {
                'status': 'disabled',
                'message': 'Comment quality assessment is disabled',
                'quality_score': None,
                'quality_level': None,
                'assessment': None
            }
        
        if not self.api_available:
            detailed_error = f"{self.api_type.upper()} API not available - cannot assess comment quality. Reason: {self.api_unavailable_reason}"
            self.logger.error(detailed_error)
            return {
                'status': 'error',
                'message': f'{self.api_type.upper()} API not available for quality assessment. {self.api_unavailable_reason}',
                'quality_score': None,
                'quality_level': None,
                'assessment': None,
                'unavailable_reason': self.api_unavailable_reason
            }
        
        try:
            # First get technical analysis of the comment
            corrections_result = self.process_text(comment)
            corrections = corrections_result.get('corrections', [])
            
                         # Build comprehensive quality assessment prompt
            system_message = """You are an expert evaluator assessing comment quality for rating tasks. Evaluate comments based on multiple quality dimensions and provide detailed feedback.

ASSESSMENT CRITERIA:
1. Technical Quality (30%):
   - Grammar and spelling accuracy
   - Sentence structure and clarity
   - Proper punctuation and formatting

2. Content Quality (40%):
   - Conceptual clarity and coherence
   - Relevance to the topic/task
   - Completeness of explanation
   - Logical flow of ideas

3. Length Appropriateness (15%):
   - Adequate detail without being excessive
   - Conciseness while maintaining completeness
   - Appropriate depth for the context

4. Rating Task Suitability (15%):
   - Helpfulness for decision-making
   - Objectivity and fairness
   - Professional tone and language
   - Constructive feedback approach

CRITICAL LENGTH REQUIREMENTS FOR RATING TASKS:
- Comments under 100 characters are automatically capped at 4/10 (maximum) - insufficient explanation
- Comments under 300 characters cannot achieve 9-10/10 (excellent) - lack depth needed for rating justification
- For 5/5 rating quality, comments should be at least 300 characters to properly explain reasoning

SCORING SCALE (1-10):
- 9-10: Excellent - Exceptional quality, minimal issues, highly valuable (requires 300+ characters)
- 7-8: Good - High quality with minor issues, valuable contribution
- 5-6: Fair - Adequate quality with some issues, acceptable
- 3-4: Poor - Multiple issues affecting quality, needs improvement (comments under 100 chars max out here)
- 1-2: Very Poor - Major issues, significant problems

Return ONLY valid JSON:
{
  "quality_score": 8,
  "quality_level": "good",
  "assessment": "Detailed explanation of the overall quality assessment",
  "factors": {
    "technical_quality": {"score": 8, "notes": "grammar and spelling analysis"},
    "content_quality": {"score": 7, "notes": "conceptual clarity analysis"},
    "length_appropriateness": {"score": 8, "notes": "length and detail analysis"},
    "rating_task_suitability": {"score": 9, "notes": "suitability for rating tasks"}
  },
  "suggestions": ["specific improvement suggestion 1", "suggestion 2"],
  "strengths": ["identified strength 1", "strength 2"],
  "comment_analysis": {
    "word_count": 45,
    "sentence_count": 3,
    "error_count": 2,
    "complexity_level": "moderate"
  }
}"""

            # Prepare user message with context
            comment_length = len(comment)
            user_message = f"Assess the quality of this comment ({comment_length} characters)"
            if rating_context:
                user_message += f" in the context of: {rating_context}"
            user_message += f":\n\n\"{comment}\"\n\nRemember: Comments under 100 chars max at 4/10, under 300 chars cannot reach 9-10/10."
            
            # Add technical error information if available
            if corrections:
                error_summary = f"\n\nTechnical errors detected: {len(corrections)} issues found:"
                for i, correction in enumerate(corrections[:5]):  # Limit to first 5 errors
                    error_summary += f"\n- {correction.get('type', 'unknown')}: '{correction.get('original', '')}' → '{correction.get('suggestion', '')}'"
                if len(corrections) > 5:
                    error_summary += f"\n- ... and {len(corrections) - 5} more errors"
                user_message += error_summary
            
            # Check cache for quality assessment
            cache_key = f"quality:{self.api_type}:{hash(comment)}:{hash(rating_context or '')}"
            if self.cache_enabled and cache_key in self.api_cache:
                self.stats['cache_hits'] += 1
                # Track cache access for LRU management
                self.cache_access_counts[cache_key] = self.cache_access_counts.get(cache_key, 0) + 1
                return self.api_cache[cache_key]
            
            # Call vLLM for quality assessment
            self.logger.debug(f"🎯 Calling vLLM for comment quality assessment - Model: {self.vllm_client.model}")
            prompt = f"{system_message}\n\n{user_message}"
            generated_text = self.vllm_client.generate(
                prompt=prompt,
                max_tokens=1024,
                temperature=0.2
            )
            
            if generated_text:
                quality_result = self._parse_quality_assessment_response(generated_text, comment, corrections)
            else:
                quality_result = {
                    'status': 'error',
                    'message': 'No response from vLLM quality assessment',
                    'quality_score': None,
                    'quality_level': None,
                    'assessment': None
                }
            
            # Cache the result with smart cache management
            if self.cache_enabled and quality_result.get('status') == 'success':
                self._manage_cache(cache_key, quality_result)
                
            return quality_result
                
        except Exception as e:
            self.logger.error(f"Comment quality assessment failed: {e}")
            return {
                'status': 'error',
                'message': f'Quality assessment failed: {str(e)}',
                'quality_score': None,
                'quality_level': None,
                'assessment': None
            }
    
    def _parse_quality_assessment_response(self, response: str, original_comment: str, 
                                         corrections: List[Dict]) -> Dict[str, Any]:
        """Parse the AI response for comment quality assessment."""
        try:
            # Clean the response
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            # Parse JSON response
            result = json.loads(cleaned_response)
            
            # Validate and set defaults
            quality_score = result.get('quality_score', 5)
            quality_level = result.get('quality_level', 'fair')
            
            # Map score to level if level is missing or inconsistent
            if not quality_level or quality_level not in ['excellent', 'good', 'fair', 'poor']:
                if quality_score >= 9:
                    quality_level = 'excellent'
                elif quality_score >= 7:
                    quality_level = 'good'
                elif quality_score >= 5:
                    quality_level = 'fair'
                else:
                    quality_level = 'poor'
            
            # Add actual comment analysis data
            word_count = len(original_comment.split())
            sentence_count = len([s for s in original_comment.split('.') if s.strip()])
            error_count = len(corrections)
            character_count = len(original_comment)
            
            # Update comment analysis with real data
            if 'comment_analysis' not in result:
                result['comment_analysis'] = {}
            
            result['comment_analysis'].update({
                'word_count': word_count,
                'sentence_count': sentence_count,
                'error_count': error_count,
                'character_count': character_count
            })
            
            # Enforce length-based scoring requirements for rating tasks
            original_score = quality_score
            length_penalty_applied = False
            length_notes = []
            
            if character_count < 100:
                # Comments under 100 characters are capped at 4/10 (poor-fair range)
                if quality_score > 4:
                    quality_score = 4
                    quality_level = 'poor'
                    length_penalty_applied = True
                    length_notes.append("Score capped at 4/10 due to insufficient length (<100 characters)")
                    
            elif character_count < 300:
                # Comments under 300 characters cannot achieve excellent (9-10)
                if quality_score >= 9:
                    quality_score = 8
                    quality_level = 'good'
                    length_penalty_applied = True
                    length_notes.append("Score capped at 8/10 - needs 300+ characters for excellent rating")
            
            # Update assessment if length penalty was applied
            if length_penalty_applied:
                original_assessment = result.get('assessment', '')
                penalty_note = f" [Length-adjusted: {original_score}→{quality_score}. {'; '.join(length_notes)}]"
                result['assessment'] = original_assessment + penalty_note
                
                # Add to suggestions if not already present
                suggestions = result.get('suggestions', [])
                if character_count < 100:
                    length_suggestion = "Expand the comment to at least 100 characters to provide adequate explanation for rating decisions"
                elif character_count < 300:
                    length_suggestion = "Expand the comment to at least 300 characters to achieve excellent quality and properly justify rating decisions"
                
                if length_suggestion and length_suggestion not in suggestions:
                    suggestions.insert(0, length_suggestion)
                    result['suggestions'] = suggestions
            
            return {
                'status': 'success',
                'quality_score': quality_score,
                'quality_level': quality_level,
                'assessment': result.get('assessment', 'Quality assessment completed'),
                'factors': result.get('factors', {}),
                'suggestions': result.get('suggestions', []),
                'strengths': result.get('strengths', []),
                'comment_analysis': result['comment_analysis'],
                'original_comment': original_comment,
                'technical_corrections': corrections
            }
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse quality assessment JSON: {e}")
            return {
                'status': 'error',
                'message': f'Failed to parse AI response: {str(e)}',
                'quality_score': None,
                'quality_level': None,
                'assessment': f'Raw response: {response[:200]}...' if len(response) > 200 else response
            }
        except Exception as e:
            self.logger.error(f"Error processing quality assessment: {e}")
            return {
                'status': 'error',
                'message': f'Processing error: {str(e)}',
                'quality_score': None,
                'quality_level': None,
                'assessment': None
            } 
