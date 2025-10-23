"""
Unit tests for AppenCorrect Flask API.
"""

import pytest
import json
from unittest.mock import Mock, patch
from appencorrect import create_app
from appencorrect.core import Correction


@pytest.fixture
def app():
    """Create test Flask application."""
    config = {
        'TESTING': True,
        'APPENCORRECT_GEMINI_API_KEY': 'test-api-key',
        'APPENCORRECT_DEFAULT_LANGUAGE': 'en_US'
    }
    return create_app(config)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestHealthEndpoint:
    """Test cases for the /health endpoint."""
    
    def test_health_check_success(self, client):
        """Test successful health check."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.get_statistics.return_value = {
                'spell_checker_available': True,
                'grammar_checker_available': True,
                'gemini_available': False
            }
            mock_checker_class.return_value = mock_checker
            
            response = client.get('/health')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'healthy'
            assert 'components' in data
            assert data['components']['spell_checker'] is True
    
    def test_health_check_failure(self, client):
        """Test health check with component failure."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker_class.side_effect = Exception("Component failure")
            
            response = client.get('/health')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'unhealthy'


class TestCheckEndpoint:
    """Test cases for the /check endpoint."""
    
    def test_check_text_success(self, client):
        """Test successful text checking."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.process_text.return_value = {
                'status': 'success',
                'original_text': 'Test text',
                'corrections': [],
                'processed_text': 'Test text',
                'statistics': {
                    'total_errors': 0,
                    'spelling_errors': 0,
                    'grammar_errors': 0,
                    'style_suggestions': 0,
                    'processing_time': '0.001s',
                    'gemini_available': False
                }
            }
            mock_checker_class.return_value = mock_checker
            
            response = client.post('/check', 
                                 json={'text': 'Test text'},
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'success'
            assert data['original_text'] == 'Test text'
    
    def test_check_text_with_corrections(self, client):
        """Test text checking with corrections found."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.process_text.return_value = {
                'status': 'success',
                'original_text': 'Teh test',
                'corrections': [
                    {
                        'type': 'spelling',
                        'position': [0, 3],
                        'original': 'Teh',
                        'suggestion': 'The',
                        'confidence': 0.8,
                        'reasoning': 'Spelling error',
                        'source': 'hunspell'
                    }
                ],
                'processed_text': 'The test',
                'statistics': {
                    'total_errors': 1,
                    'spelling_errors': 1,
                    'grammar_errors': 0,
                    'style_suggestions': 0,
                    'processing_time': '0.002s',
                    'gemma_available': False
                }
            }
            mock_checker_class.return_value = mock_checker
            
            response = client.post('/check',
                                 json={'text': 'Teh test'},
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['corrections']) == 1
            assert data['corrections'][0]['original'] == 'Teh'
            assert data['corrections'][0]['suggestion'] == 'The'
    
    def test_check_text_with_options(self, client):
        """Test text checking with custom options."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.process_text.return_value = {
                'status': 'success',
                'original_text': 'Test',
                'corrections': [],
                'processed_text': 'Test',
                'statistics': {
                    'total_errors': 0,
                    'spelling_errors': 0,
                    'grammar_errors': 0,
                    'style_suggestions': 0,
                    'processing_time': '0.001s',
                    'gemini_available': False
                }
            }
            mock_checker_class.return_value = mock_checker
            
            request_data = {
                'text': 'Test',
                'language': 'es_ES',
                'options': {
                    'spelling': True,
                    'grammar': False,
                    'gemini_validation': False
                }
            }
            
            response = client.post('/check',
                                 json=request_data,
                                 content_type='application/json')
            
            assert response.status_code == 200
            
            # Verify the checker was called with correct options
            mock_checker.process_text.assert_called_once()
            args, kwargs = mock_checker.process_text.call_args
            assert args[0] == 'Test'  # text
            if len(args) > 1:  # options passed as second argument
                assert args[1] == request_data['options']
    
    def test_check_text_invalid_json(self, client):
        """Test text checking with invalid JSON."""
        response = client.post('/check',
                             data='invalid json',
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_check_text_missing_text(self, client):
        """Test text checking without text field."""
        response = client.post('/check',
                             json={'language': 'en_US'},
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_check_text_too_long(self, client):
        """Test text checking with text exceeding maximum length."""
        long_text = 'x' * 50001  # Exceeds default limit
        
        response = client.post('/check',
                             json={'text': long_text},
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Text too long' in data['error']
    
    def test_check_text_processing_error(self, client):
        """Test text checking with processing error."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.process_text.side_effect = Exception("Processing failed")
            mock_checker_class.return_value = mock_checker
            
            response = client.post('/check',
                                 json={'text': 'Test'},
                                 content_type='application/json')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'error'


class TestLanguagesEndpoint:
    """Test cases for the /languages endpoint."""
    
    def test_get_languages_success(self, client):
        """Test successful language listing."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.get_supported_languages.return_value = [
                'en_US', 'en_GB', 'es_ES', 'fr_FR'
            ]
            mock_checker_class.return_value = mock_checker
            
            response = client.get('/languages')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'supported_languages' in data
            assert 'en_US' in data['supported_languages']
            assert data['default_language'] == 'en_US'
    
    def test_get_languages_error(self, client):
        """Test language listing with error."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.get_supported_languages.side_effect = Exception("Language error")
            mock_checker_class.return_value = mock_checker
            
            response = client.get('/languages')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data


class TestStatisticsEndpoint:
    """Test cases for the /stats endpoint."""
    
    def test_get_statistics_success(self, client):
        """Test successful statistics retrieval."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.get_statistics.return_value = {
                'total_processed': 10,
                'spelling_errors_found': 5,
                'grammar_errors_found': 3,
                'gemma_validations': 2
            }
            mock_checker_class.return_value = mock_checker
            
            response = client.get('/stats')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'statistics' in data
            assert 'total_instances' in data
    
    def test_get_statistics_error(self, client):
        """Test statistics retrieval with error."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker_class.side_effect = Exception("Stats error")
            
            response = client.get('/stats')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data


class TestSpecializedEndpoints:
    """Test cases for specialized checking endpoints."""
    
    def test_check_spelling_only_success(self, client):
        """Test spelling-only endpoint."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.check_spelling.return_value = [
                Correction(
                    type='spelling',
                    position=(0, 3),
                    original='teh',
                    suggestion='the',
                    confidence=0.8,
                    reasoning='Spelling correction',
                    source='hunspell'
                )
            ]
            mock_checker_class.return_value = mock_checker
            
            response = client.post('/check/spelling',
                                 json={'text': 'teh test'},
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['corrections']) == 1
            assert data['corrections'][0]['type'] == 'spelling'
            assert data['error_count'] == 1
    
    def test_check_grammar_only_success(self, client):
        """Test grammar-only endpoint."""
        with patch('appencorrect.core.AppenCorrect') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.check_grammar.return_value = [
                Correction(
                    type='grammar',
                    position=(5, 8),
                    original='are',
                    suggestion='is',
                    confidence=0.9,
                    reasoning='Subject-verb agreement',
                    source='languagetool'
                )
            ]
            mock_checker_class.return_value = mock_checker
            
            response = client.post('/check/grammar',
                                 json={'text': 'This are wrong'},
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['corrections']) == 1
            assert data['corrections'][0]['type'] == 'grammar'
    
    def test_specialized_endpoint_missing_text(self, client):
        """Test specialized endpoints without text."""
        response = client.post('/check/spelling',
                             json={},
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Text is required' in data['error']


class TestErrorHandlers:
    """Test cases for error handlers."""
    
    def test_404_handler(self, client):
        """Test 404 error handler."""
        response = client.get('/nonexistent')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error'] == 'Endpoint not found'
    
    def test_405_handler(self, client):
        """Test 405 error handler."""
        response = client.put('/health')  # PUT not allowed on GET endpoint
        
        assert response.status_code == 405
        data = json.loads(response.data)
        assert data['error'] == 'Method not allowed'


if __name__ == '__main__':
    pytest.main([__file__]) 