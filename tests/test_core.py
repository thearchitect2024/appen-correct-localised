"""
Unit tests for AppenCorrect core functionality.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from appencorrect.core import AppenCorrect, Correction


class TestAppenCorrect:
    """Test cases for the main AppenCorrect class."""
    
    def test_init_default_configuration(self):
        """Test default initialization."""
        with patch('appencorrect.core.Hunspell'), \
             patch('appencorrect.core.LanguageTool'), \
             patch('appencorrect.core.call_gemini_api') as mock_gemini:
            
            mock_gemini.return_value = {'text': 'Hello'}
            checker = AppenCorrect()
            
            assert checker.language == 'en_US'
            assert checker.gemini_model == 'gemini-2.0-flash'
    
    def test_init_custom_configuration(self):
        """Test initialization with custom configuration."""
        with patch('appencorrect.core.Hunspell'), \
             patch('appencorrect.core.LanguageTool'), \
             patch('appencorrect.core.call_gemini_api') as mock_gemini:
            
            mock_gemini.return_value = {'text': 'Hello'}
            checker = AppenCorrect(
                language='es_ES',
                gemini_api_key='test-api-key',
                gemini_model='gemini-2.0-flash'
            )
            
            assert checker.language == 'es_ES'
            assert checker.gemini_api_key == 'test-api-key'
            assert checker.gemini_model == 'gemini-2.0-flash'
    
    def test_spell_checking_basic(self):
        """Test basic spell checking functionality."""
        with patch('appencorrect.core.LanguageTool'), \
             patch('requests.get'):
            
            # Mock Hunspell
            mock_hunspell = Mock()
            mock_hunspell.spell.side_effect = lambda word: word not in ['teh', 'wrod']
            mock_hunspell.suggest.side_effect = lambda word: {
                'teh': ['the', 'tea'],
                'wrod': ['word', 'world']
            }.get(word, [])
            
            with patch('appencorrect.core.Hunspell', return_value=mock_hunspell):
                checker = AppenCorrect()
                
                text = "This is teh wrod test"
                corrections = checker.check_spelling(text)
                
                assert len(corrections) == 2
                assert corrections[0].original == 'teh'
                assert corrections[0].suggestion == 'the'
                assert corrections[1].original == 'wrod'
                assert corrections[1].suggestion == 'word'
    
    def test_spell_checking_no_errors(self):
        """Test spell checking with no errors."""
        with patch('appencorrect.core.LanguageTool'), \
             patch('requests.get'):
            
            # Mock Hunspell - all words correct
            mock_hunspell = Mock()
            mock_hunspell.spell.return_value = True
            
            with patch('appencorrect.core.Hunspell', return_value=mock_hunspell):
                checker = AppenCorrect()
                
                text = "This is a perfect sentence"
                corrections = checker.check_spelling(text)
                
                assert len(corrections) == 0
    
    def test_grammar_checking_basic(self):
        """Test basic grammar checking functionality."""
        with patch('appencorrect.core.Hunspell'), \
             patch('requests.get'):
            
            # Mock LanguageTool
            mock_match = Mock()
            mock_match.ruleId = 'GRAMMAR_ERROR'
            mock_match.category = 'GRAMMAR'
            mock_match.offset = 5
            mock_match.errorLength = 3
            mock_match.message = 'Grammar error detected'
            mock_match.replacements = ['is']
            
            mock_lt = Mock()
            mock_lt.check.return_value = [mock_match]
            
            with patch('appencorrect.core.LanguageTool', return_value=mock_lt):
                checker = AppenCorrect()
                
                text = "This are a test"
                corrections = checker.check_grammar(text)
                
                assert len(corrections) == 1
                assert corrections[0].type == 'grammar'
                assert corrections[0].suggestion == 'is'
                assert corrections[0].confidence == 0.9
    
    def test_process_text_full_pipeline(self):
        """Test the complete text processing pipeline."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            
            # Mock Hunspell
            mock_hunspell = Mock()
            mock_hunspell.spell.side_effect = lambda word: word != 'teh'
            mock_hunspell.suggest.return_value = ['the']
            
            # Mock LanguageTool
            mock_match = Mock()
            mock_match.ruleId = 'GRAMMAR_ERROR'
            mock_match.category = 'GRAMMAR'
            mock_match.offset = 8
            mock_match.errorLength = 3
            mock_match.message = 'Grammar error'
            mock_match.replacements = ['is']
            
            mock_lt = Mock()
            mock_lt.check.return_value = [mock_match]
            
            with patch('appencorrect.core.Hunspell', return_value=mock_hunspell), \
                 patch('appencorrect.core.LanguageTool', return_value=mock_lt):
                
                checker = AppenCorrect()
                
                text = "This is teh are test"
                result = checker.process_text(text)
                
                assert result['status'] == 'success'
                assert result['original_text'] == text
                assert len(result['corrections']) >= 1  # At least spelling error
                assert 'statistics' in result
                assert 'processing_time' in result['statistics']
    
    def test_gemini_validation_success(self):
        """Test successful Gemini validation."""
        with patch('appencorrect.core.Hunspell'), \
             patch('appencorrect.core.LanguageTool'):
            
            # Mock successful Gemini connection and API response
            with patch('appencorrect.core.call_gemini_api') as mock_gemini:
                mock_gemini.side_effect = [
                    {'text': 'Hello'},  # For connection test
                    {
                        'text': json.dumps({
                            'validated_corrections': [],
                            'additional_suggestions': [
                                {
                                    'original': 'good',
                                    'suggestion': 'excellent',
                                    'reasoning': 'Better word choice',
                                    'position': [0, 4]
                                }
                            ],
                            'rejected_corrections': []
                        })
                    }  # For validation
                ]
                
                checker = AppenCorrect(gemini_api_key='test-key')
                
                # Create some test corrections
                corrections = [
                    Correction(
                        type='spelling',
                        position=(0, 4),
                        original='test',
                        suggestion='best',
                        confidence=0.8,
                        reasoning='Spelling correction',
                        source='hunspell'
                    )
                ]
                
                result = checker.gemini_validate("test text", corrections)
                
                # Should have original + additional suggestions
                assert len(result) >= 1
                assert checker.stats['gemini_validations'] == 1
    
    def test_gemini_validation_failure_fallback(self):
        """Test Gemini validation with fallback to original corrections."""
        with patch('appencorrect.core.Hunspell'), \
             patch('appencorrect.core.LanguageTool'):
            
            # Mock failed Gemini connection
            with patch('appencorrect.core.call_gemini_api') as mock_gemini:
                mock_gemini.side_effect = Exception("Connection failed")
                
                checker = AppenCorrect(gemini_api_key='test-key')
                assert not checker.gemini_available
                
                # Should return original corrections unchanged
                corrections = [
                    Correction(
                        type='spelling',
                        position=(0, 4),
                        original='test',
                        suggestion='best',
                        confidence=0.8,
                        reasoning='Spelling correction',
                        source='hunspell'
                    )
                ]
                
                result = checker.gemini_validate("test text", corrections)
                assert result == corrections
    
    def test_apply_corrections(self):
        """Test applying corrections to text."""
        with patch('appencorrect.core.Hunspell'), \
             patch('appencorrect.core.LanguageTool'), \
             patch('appencorrect.core.call_gemini_api'):
            
            checker = AppenCorrect()
            
            text = "This is teh wrod"
            corrections = [
                Correction(
                    type='spelling',
                    position=(8, 11),  # 'teh'
                    original='teh',
                    suggestion='the',
                    confidence=0.8,
                    reasoning='Spelling correction',
                    source='hunspell'
                ),
                Correction(
                    type='spelling',
                    position=(12, 16),  # 'wrod'
                    original='wrod',
                    suggestion='word',
                    confidence=0.8,
                    reasoning='Spelling correction',
                    source='hunspell'
                )
            ]
            
            result = checker._apply_corrections(text, corrections)
            assert result == "This is the word"
    
    def test_get_supported_languages(self):
        """Test getting supported languages."""
        with patch('appencorrect.core.Hunspell'), \
             patch('appencorrect.core.LanguageTool'), \
             patch('appencorrect.core.call_gemini_api'):
            
            checker = AppenCorrect()
            languages = checker.get_supported_languages()
            
            assert isinstance(languages, list)
            assert 'en_US' in languages
            assert 'es_ES' in languages
    
    def test_get_statistics(self):
        """Test getting processing statistics."""
        with patch('appencorrect.core.Hunspell'), \
             patch('appencorrect.core.LanguageTool'), \
             patch('appencorrect.core.call_gemini_api'):
            
            checker = AppenCorrect()
            stats = checker.get_statistics()
            
            assert 'total_processed' in stats
            assert 'spelling_errors_found' in stats
            assert 'grammar_errors_found' in stats
            assert 'spell_checker_available' in stats
            assert 'grammar_checker_available' in stats
            assert 'gemini_available' in stats


if __name__ == '__main__':
    pytest.main([__file__]) 