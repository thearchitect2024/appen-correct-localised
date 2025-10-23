"""
AppenCorrect Flask API

Provides REST endpoints for text correction services with AI-first approach.
Includes API key authentication and management.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
from jsonschema import validate, ValidationError
from core import AppenCorrect
from api_auth import require_api_key, track_api_usage, get_api_key_manager
from auth import require_auth, authenticate_user, create_session, logout_user, render_login_page, is_authenticated, create_user, render_forgot_password_page, render_reset_password_page, generate_password_reset_token, verify_reset_token, reset_password_with_token

# Email service is optional - not needed for core text correction
try:
    from email_service import send_password_reset_email, test_email_configuration
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_password_reset_email(*args, **kwargs):
        return False
    def test_email_configuration():
        return False, "Email service not configured"

# Configure logging
logger = logging.getLogger(__name__)

# Request validation schemas
CHECK_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "minLength": 1, "maxLength": 10000},
        "language": {"type": "string", "default": "auto", "description": "Language/dialect code (e.g., 'english', 'french', 'en-US', 'fr-CA', 'es-MX') or 'auto' for detection"},
        "use_case": {"type": "string", "maxLength": 100, "description": "Use case for custom instructions (e.g., 'code_comments', 'academic_writing')"},
        "options": {
            "type": "object", 
            "properties": {
                "ai_first_mode": {"type": "boolean"}
            },
            "additionalProperties": False
        }
    },
    "required": ["text"],
    "additionalProperties": False
}

FEEDBACK_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "original": {"type": "string", "minLength": 1, "maxLength": 1000},
        "ai_suggestion": {"type": "string", "minLength": 1, "maxLength": 1000},
        "user_correction": {"type": "string", "maxLength": 1000},
        "feedback_type": {"type": "string", "enum": ["positive", "negative", "manual_correction", "missing_error", "text_confirmed_clean"]},
        "correction_type": {"type": "string", "enum": ["spelling", "grammar", "style", "missed_error", "general"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "full_text": {"type": "string", "maxLength": 10000}
    },
    "required": ["original", "ai_suggestion", "feedback_type"],
    "additionalProperties": False
}

QUALITY_ASSESSMENT_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "comment": {"type": "string", "minLength": 1, "maxLength": 5000},
        "rating_context": {"type": "string", "maxLength": 1000},
        "enable_quality_assessment": {"type": "boolean"}
    },
    "required": ["comment"],
    "additionalProperties": False
}

CUSTOM_INSTRUCTIONS_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "use_case": {"type": "string", "minLength": 1, "maxLength": 100},
        "instructions": {"type": "string", "minLength": 1, "maxLength": 10000}
    },
    "required": ["use_case", "instructions"],
    "additionalProperties": False
}

class AppenCorrectAPI:
    """Flask API wrapper for AppenCorrect functionality."""
    
    def __init__(self, config=None):
        """Initialize API with configuration."""
        self.config = config or {}
        self._checker = None
        self._checkers_by_api_key = {}  # Cache AppenCorrect instances per API key
        
    def _get_checker(self):
        """Get or create AppenCorrect instance per API key."""
        # Try to get API key from request context (set by require_api_key decorator)
        api_key_info = getattr(request, 'api_key_info', None)
        
        if api_key_info:
            # Use per-API-key instances for custom instructions isolation
            api_key_id = api_key_info['key_id']
            
            if api_key_id not in self._checkers_by_api_key:
                self._checkers_by_api_key[api_key_id] = AppenCorrect()
                logger.info(f"Created new AppenCorrect instance for API key: {api_key_id}")
            
            return self._checkers_by_api_key[api_key_id]
        else:
            # Fallback for non-authenticated requests (demo endpoints)
            if self._checker is None:
                self._checker = AppenCorrect()
                logger.info(f"Flask API initialized - vLLM model: {self._checker.vllm_client.model}")
            return self._checker
    
    def health_check(self):
        """Health check endpoint with component status."""
        try:
            checker = self._get_checker()
            
            # Test vLLM connection
            try:
                vllm_status = checker.vllm_client.test_connection()
            except Exception as e:
                logger.warning(f"vLLM connection test failed: {e}")
                vllm_status = False
            
            # Test email service configuration
            email_status, email_message = test_email_configuration()
            
            # Component status
            components = {
                'vllm_inference': 'available' if vllm_status else 'unavailable',
                'language_detector': 'available',  # Always available
                'ai_first_mode': 'enabled',
                'email_service': 'available' if email_status else 'unavailable'
            }
            
            overall_status = 'healthy' if vllm_status else 'degraded'
            
            return jsonify({
                'status': overall_status,
                'timestamp': datetime.utcnow().isoformat(),
                'version': '2.0.0-vllm',
                'components': components,
                'capabilities': ['spelling', 'grammar', 'language_detection', 'ai_correction']
            })
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'status': 'error',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }), 500
    
    def check_text(self):
        """Main text checking endpoint."""
        try:
            # Validate request
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body must be JSON'}), 400
                
            validate(data, CHECK_REQUEST_SCHEMA)
            
            text = data['text']
            language = data.get('language', 'auto')
            use_case = data.get('use_case')
            options = data.get('options', {})
            
            # Get checker and process text
            checker = self._get_checker()
            result = checker.process_text(text, options=options, language=language if language != 'auto' else None, use_case=use_case)
            
            return jsonify(result)
            
        except ValidationError as e:
            return jsonify({'error': f'Invalid request: {e.message}'}), 400
        except Exception as e:
            logger.error(f"Error checking text: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    def check_spelling(self):
        """Spelling-only checking endpoint."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body must be JSON'}), 400
                
            validate(data, CHECK_REQUEST_SCHEMA)
            
            text = data['text']
            language = data.get('language', 'auto')
            use_case = data.get('use_case')
            checker = self._get_checker()
            
            # Use the spelling-only method
            result = checker.check_spelling(text, language=language if language != 'auto' else None, use_case=use_case)
            
            return jsonify({
                'original_text': result.get('original_text'),
                'processed_text': result.get('processed_text'),
                'corrections': result.get('corrections', []),
                'statistics': result.get('statistics', {})
            })
            
        except ValidationError as e:
            return jsonify({'error': f'Invalid request: {e.message}'}), 400
        except Exception as e:
            logger.error(f"Error checking spelling: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    def check_grammar(self):
        """Grammar-only checking endpoint."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body must be JSON'}), 400
                
            validate(data, CHECK_REQUEST_SCHEMA)
            
            text = data['text']
            language = data.get('language', 'auto')
            use_case = data.get('use_case')
            checker = self._get_checker()
            result = checker.process_text(text, language=language if language != 'auto' else None, use_case=use_case)
            
            # Filter for grammar corrections only
            grammar_corrections = [
                c for c in result.get('corrections', []) 
                if c.get('type') == 'grammar'
            ]
            
            return jsonify({
                'original_text': result.get('original_text'),
                'processed_text': result.get('processed_text'),
                'corrections': grammar_corrections,
                'statistics': {
                    'total_corrections': len(grammar_corrections),
                    'spelling_corrections': 0,
                    'grammar_corrections': len(grammar_corrections)
                }
            })
            
        except ValidationError as e:
            return jsonify({'error': f'Invalid request: {e.message}'}), 400
        except Exception as e:
            logger.error(f"Error checking grammar: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    def submit_feedback(self):
        """Submit feedback on AI correction suggestions."""
        try:
            # Validate request
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body must be JSON'}), 400
                
            validate(data, FEEDBACK_REQUEST_SCHEMA)
            
            # Extract feedback data
            original = data['original']
            ai_suggestion = data['ai_suggestion']
            user_correction = data.get('user_correction', '')
            feedback_type = data['feedback_type']
            correction_type = data.get('correction_type', 'unknown')
            confidence = data.get('confidence', 0.0)
            full_text = data.get('full_text', '')
            
            # Log feedback for analysis
            feedback_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'original': original,
                'ai_suggestion': ai_suggestion,
                'user_correction': user_correction,
                'feedback_type': feedback_type,
                'correction_type': correction_type,
                'confidence': confidence,
                'full_text': full_text,
                'source': 'demo_interface'
            }
            
            # Log to file for future model training
            # Log to both general log and dedicated feedback log
            logger.info(f"Feedback received: {feedback_entry}")
            
            # Log to dedicated feedback log
            feedback_logger = logging.getLogger('feedback')
            feedback_logger.info(f"FEEDBACK: {json.dumps(feedback_entry, default=str)}")
            
            # TODO: In production, save to database for model improvement
            # feedback_db.store_feedback(feedback_entry)
            
            return jsonify({
                'status': 'success',
                'message': 'Feedback received successfully',
                'feedback_id': f"fb_{int(datetime.utcnow().timestamp())}"
            })
            
        except ValidationError as e:
            return jsonify({'error': f'Invalid feedback request: {e.message}'}), 400
        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            return jsonify({'error': 'Failed to submit feedback'}), 500
    
    def get_feedback_data(self):
        """Get user feedback data from log files for admin interface."""
        try:
            import json
            from datetime import datetime, timedelta
            
            feedback_data = []
            feedback_log_path = 'logs/feedback.log'
            
            # Check if log file exists
            if not os.path.exists(feedback_log_path):
                return jsonify({
                    'feedback': [],
                    'stats': {'total': 0, 'positive': 0, 'negative': 0, 'missing_error': 0, 'text_confirmed_clean': 0}
                })
            
            # Read feedback log
            try:
                with open(feedback_log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and 'FEEDBACK:' in line:
                            try:
                                # Extract JSON part after "FEEDBACK: "
                                json_part = line.split('FEEDBACK: ', 1)[1]
                                feedback_entry = json.loads(json_part)
                                feedback_data.append(feedback_entry)
                            except (json.JSONDecodeError, IndexError) as e:
                                logger.warning(f"Could not parse feedback line: {line[:100]}...")
                                continue
            except Exception as e:
                logger.error(f"Error reading feedback log: {e}")
                return jsonify({'error': 'Failed to read feedback data'}), 500
            
            # Sort by timestamp (newest first)
            feedback_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Limit to most recent entries to avoid performance issues
            feedback_data = feedback_data[:500]
            
            # Calculate stats
            stats = {
                'total': len(feedback_data),
                'positive': len([f for f in feedback_data if f.get('feedback_type') == 'positive']),
                'negative': len([f for f in feedback_data if f.get('feedback_type') == 'negative']),
                'missing_error': len([f for f in feedback_data if f.get('feedback_type') == 'missing_error']),
                'text_confirmed_clean': len([f for f in feedback_data if f.get('feedback_type') == 'text_confirmed_clean']),
                'manual_correction': len([f for f in feedback_data if f.get('feedback_type') == 'manual_correction'])
            }
            
            return jsonify({
                'feedback': feedback_data,
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Error getting feedback data: {e}")
            return jsonify({'error': 'Failed to retrieve feedback data'}), 500

    def get_cost_analytics(self):
        """Get cost analytics data for API usage."""
        try:
            key_id = request.args.get('key_id')
            days = int(request.args.get('days', 30))
            export_format = request.args.get('format', 'json')
            
            # Calculate date range
            from datetime import datetime, timedelta
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            manager = get_api_key_manager()
            
            with manager._get_db_connection() as conn:
                if key_id:
                    # Get FRESH AI costs for specific API key (non-cached requests)
                    fresh_results = conn.execute('''
                        SELECT 
                            DATE(timestamp) as date,
                            COALESCE(endpoint, 'unknown') as endpoint,
                            COUNT(*) as requests,
                            SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
                            SUM(COALESCE(output_tokens, 0)) as total_output_tokens,
                            SUM(COALESCE(estimated_cost_usd, 0)) as total_cost,
                            AVG(COALESCE(processing_time_ms, 0)) as avg_processing_time,
                            COALESCE(model_used, 'Qwen/Qwen2.5-7B-Instruct') as model_used,
                            'fresh' as request_type
                        FROM api_usage 
                        WHERE key_id = ? AND timestamp >= ? AND timestamp <= ? 
                        AND processing_time_ms >= 100
                        GROUP BY DATE(timestamp), endpoint, model_used
                        ORDER BY date DESC, total_cost DESC
                    ''', (key_id, start_date.isoformat(), end_date.isoformat())).fetchall()
                    
                    # Get CACHED response stats for specific API key
                    cached_results = conn.execute('''
                        SELECT 
                            DATE(timestamp) as date,
                            COALESCE(endpoint, 'unknown') as endpoint,
                            COUNT(*) as requests,
                            SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
                            SUM(COALESCE(output_tokens, 0)) as total_output_tokens,
                            0 as total_cost,
                            AVG(COALESCE(processing_time_ms, 0)) as avg_processing_time,
                            COALESCE(model_used, 'Qwen/Qwen2.5-7B-Instruct') as model_used,
                            'cached' as request_type
                        FROM api_usage 
                        WHERE key_id = ? AND timestamp >= ? AND timestamp <= ? 
                        AND processing_time_ms < 100
                        GROUP BY DATE(timestamp), endpoint, model_used
                        ORDER BY date DESC, requests DESC
                    ''', (key_id, start_date.isoformat(), end_date.isoformat())).fetchall()
                    
                    # Combine results
                    results = list(fresh_results) + list(cached_results)
                    
                    # Get summary for the key
                    summary = conn.execute('''
                        SELECT 
                            COUNT(*) as total_requests,
                            SUM(input_tokens) as total_input_tokens,
                            SUM(output_tokens) as total_output_tokens,
                            SUM(estimated_cost_usd) as total_cost,
                            AVG(processing_time_ms) as avg_processing_time
                        FROM api_usage 
                        WHERE key_id = ? AND timestamp >= ? AND timestamp <= ?
                    ''', (key_id, start_date.isoformat(), end_date.isoformat())).fetchone()
                    
                else:
                    # Get FRESH AI costs for all API keys (non-cached requests)
                    fresh_results = conn.execute('''
                        SELECT 
                            COALESCE(key_id, 'unknown') as key_id,
                            DATE(timestamp) as date,
                            COALESCE(endpoint, 'unknown') as endpoint,
                            COUNT(*) as requests,
                            SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
                            SUM(COALESCE(output_tokens, 0)) as total_output_tokens,
                            SUM(COALESCE(estimated_cost_usd, 0)) as total_cost,
                            AVG(COALESCE(processing_time_ms, 0)) as avg_processing_time,
                            COALESCE(model_used, 'Qwen/Qwen2.5-7B-Instruct') as model_used,
                            'fresh' as request_type
                        FROM api_usage 
                        WHERE timestamp >= ? AND timestamp <= ? 
                        AND processing_time_ms >= 100
                        GROUP BY key_id, DATE(timestamp), endpoint, model_used
                        ORDER BY date DESC, total_cost DESC
                    ''', (start_date.isoformat(), end_date.isoformat())).fetchall()
                    
                    # Get CACHED response stats for all API keys
                    cached_results = conn.execute('''
                        SELECT 
                            COALESCE(key_id, 'unknown') as key_id,
                            DATE(timestamp) as date,
                            COALESCE(endpoint, 'unknown') as endpoint,
                            COUNT(*) as requests,
                            SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
                            SUM(COALESCE(output_tokens, 0)) as total_output_tokens,
                            0 as total_cost,
                            AVG(COALESCE(processing_time_ms, 0)) as avg_processing_time,
                            COALESCE(model_used, 'Qwen/Qwen2.5-7B-Instruct') as model_used,
                            'cached' as request_type
                        FROM api_usage 
                        WHERE timestamp >= ? AND timestamp <= ? 
                        AND processing_time_ms < 100
                        GROUP BY key_id, DATE(timestamp), endpoint, model_used
                        ORDER BY date DESC, requests DESC
                    ''', (start_date.isoformat(), end_date.isoformat())).fetchall()
                    
                    # Combine results
                    results = list(fresh_results) + list(cached_results)
                    
                    # Get summary for all keys
                    summary = conn.execute('''
                        SELECT 
                            COUNT(*) as total_requests,
                            SUM(input_tokens) as total_input_tokens,
                            SUM(output_tokens) as total_output_tokens,
                            SUM(estimated_cost_usd) as total_cost,
                            AVG(processing_time_ms) as avg_processing_time
                        FROM api_usage 
                        WHERE timestamp >= ? AND timestamp <= ?
                    ''', (start_date.isoformat(), end_date.isoformat())).fetchone()
                
                # Convert results to list of dicts
                cost_data = [dict(row) for row in results]
                summary_data = dict(summary) if summary else {}
                
                # Handle CSV export
                if export_format == 'csv':
                    import csv
                    import io
                    from flask import make_response
                    
                    output = io.StringIO()
                    writer = csv.writer(output)
                    
                    # Write CSV headers
                    if key_id:
                        writer.writerow(['Date', 'Endpoint', 'Requests', 'Input Tokens', 'Output Tokens', 'Total Cost USD', 'Avg Processing Time MS', 'Model'])
                        for row in cost_data:
                            writer.writerow([
                                row.get('date', ''),
                                row.get('endpoint', ''),
                                row.get('requests', 0),
                                row.get('total_input_tokens', 0),
                                row.get('total_output_tokens', 0),
                                f"{row.get('total_cost', 0):.6f}",
                                row.get('avg_processing_time', 0),
                                row.get('model_used', '')
                            ])
                    else:
                        writer.writerow(['API Key ID', 'Date', 'Requests', 'Input Tokens', 'Output Tokens', 'Total Cost USD', 'Avg Processing Time MS', 'Model'])
                        for row in cost_data:
                            writer.writerow([
                                row.get('key_id', ''),
                                row.get('date', ''),
                                row.get('requests', 0),
                                row.get('total_input_tokens', 0),
                                row.get('total_output_tokens', 0),
                                f"{row.get('total_cost', 0):.6f}",
                                row.get('avg_processing_time', 0),
                                row.get('model_used', '')
                            ])
                    
                    # Create CSV response
                    response = make_response(output.getvalue())
                    response.headers['Content-Type'] = 'text/csv'
                    response.headers['Content-Disposition'] = f'attachment; filename=appencorrect_costs_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.csv'
                    return response
                
                return jsonify({
                    'status': 'success',
                    'period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'days': days
                    },
                    'summary': {
                        'total_requests': summary_data.get('total_requests', 0),
                        'total_input_tokens': summary_data.get('total_input_tokens', 0),
                        'total_output_tokens': summary_data.get('total_output_tokens', 0),
                        'total_cost_usd': float(summary_data.get('total_cost', 0) or 0),
                        'avg_processing_time_ms': float(summary_data.get('avg_processing_time', 0) or 0),
                        'cost_per_request': float(summary_data.get('total_cost', 0) or 0) / max(1, summary_data.get('total_requests', 1))
                    },
                    'cost_data': cost_data,
                    'pricing': {
                        'input_tokens_per_usd': 0,  # Self-hosted vLLM - no per-token cost
                        'output_tokens_per_usd': 0,  # Self-hosted vLLM - no per-token cost
                        'currency': 'USD',
                        'model': 'Qwen/Qwen2.5-7B-Instruct',
                        'note': 'Self-hosted vLLM - costs based on GPU instance pricing'
                    }
                })
            
        except Exception as e:
            logger.error(f"Error getting cost analytics: {e}")
            return jsonify({'error': 'Failed to retrieve cost analytics'}), 500

    def get_logs(self):
        """Get application logs for admin monitoring."""
        try:
            lines = int(request.args.get('lines', 100))
            log_level = request.args.get('level', 'all')  # all, error, warning, info
            export_format = request.args.get('format', 'json')
            
            # Limit lines for performance
            lines = min(lines, 10000)
            
            log_file_path = 'logs/appencorrect.log'
            
            if not os.path.exists(log_file_path):
                return jsonify({'error': 'Log file not found'}), 404
            
            try:
                # Read last N lines from log file
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                
                # Filter by log level if specified
                filtered_lines = []
                for line in recent_lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Basic log level filtering
                    if log_level == 'error' and ' - ERROR - ' not in line:
                        continue
                    elif log_level == 'warning' and ' - WARNING - ' not in line:
                        continue
                    elif log_level == 'info' and ' - INFO - ' not in line:
                        continue
                    # 'all' includes everything
                    
                    filtered_lines.append(line)
                
                # Handle different export formats
                if export_format == 'text' or export_format == 'raw':
                    from flask import make_response
                    
                    content = '\n'.join(filtered_lines)
                    response = make_response(content)
                    response.headers['Content-Type'] = 'text/plain'
                    
                    if export_format == 'raw':
                        # For download
                        response.headers['Content-Disposition'] = f'attachment; filename=appencorrect_{datetime.utcnow().strftime("%Y%m%d_%H%M")}.log'
                    
                    return response
                
                # JSON format (default)
                return jsonify({
                    'status': 'success',
                    'log_info': {
                        'file': log_file_path,
                        'total_lines_in_file': len(all_lines),
                        'lines_returned': len(filtered_lines),
                        'filter_level': log_level,
                        'lines_requested': lines
                    },
                    'logs': filtered_lines
                })
                
            except UnicodeDecodeError:
                return jsonify({'error': 'Log file encoding issue'}), 500
            except Exception as e:
                logger.error(f"Error reading log file: {e}")
                return jsonify({'error': 'Failed to read log file'}), 500
            
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return jsonify({'error': 'Failed to retrieve logs'}), 500

    def set_custom_instructions(self):
        """Set custom instructions for a specific use case."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body must be JSON'}), 400
            validate(data, CUSTOM_INSTRUCTIONS_REQUEST_SCHEMA)
            
            use_case = data['use_case']
            instructions = data['instructions']
            
            checker = self._get_checker()
            api_key_id = getattr(request, 'api_key_info', {}).get('key_id')
            checker.set_custom_instructions(use_case, instructions, api_key_id)
            
            return jsonify({
                'status': 'success',
                'message': f'Custom instructions set for use case: {use_case}',
                'use_case': use_case
            })
        except ValidationError as e:
            return jsonify({'error': f'Invalid request: {e.message}'}), 400
        except Exception as e:
            logger.error(f"Error setting custom instructions: {e}")
            return jsonify({'error': 'Internal server error'}), 500

    def get_custom_instructions(self):
        """Get custom instructions for a specific use case or all instructions."""
        try:
            use_case = request.args.get('use_case')
            checker = self._get_checker()
            api_key_id = getattr(request, 'api_key_info', {}).get('key_id')
            instructions = checker.get_custom_instructions(use_case, api_key_id)
            
            if use_case:
                return jsonify({
                    'status': 'success',
                    'use_case': use_case,
                    'instructions': instructions
                })
            else:
                return jsonify({
                    'status': 'success',
                    'custom_instructions': instructions
                })
        except Exception as e:
            logger.error(f"Error getting custom instructions: {e}")
            return jsonify({'error': 'Internal server error'}), 500

    def remove_custom_instructions(self):
        """Remove custom instructions for a specific use case."""
        try:
            use_case = request.args.get('use_case')
            if not use_case:
                return jsonify({'error': 'use_case parameter is required'}), 400
            
            checker = self._get_checker()
            api_key_id = getattr(request, 'api_key_info', {}).get('key_id')
            removed = checker.remove_custom_instructions(use_case, api_key_id)
            
            if removed:
                return jsonify({
                    'status': 'success',
                    'message': f'Custom instructions removed for use case: {use_case}',
                    'use_case': use_case
                })
            else:
                return jsonify({
                    'status': 'not_found',
                    'message': f'No custom instructions found for use case: {use_case}',
                    'use_case': use_case
                }), 404
        except Exception as e:
            logger.error(f"Error removing custom instructions: {e}")
            return jsonify({'error': 'Internal server error'}), 500

    def assess_comment_quality(self):
        """Assess the quality of a comment for rating tasks."""
        try:
            # Validate request
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body must be JSON'}), 400
                
            validate(data, QUALITY_ASSESSMENT_REQUEST_SCHEMA)
            
            comment = data['comment']
            rating_context = data.get('rating_context')
            enable_quality_assessment = data.get('enable_quality_assessment', True)
            
            # Get checker and assess comment quality
            checker = self._get_checker()
            result = checker.assess_comment_quality(
                comment=comment,
                rating_context=rating_context,
                enable_quality_assessment=enable_quality_assessment
            )
            
            return jsonify(result)
            
        except ValidationError as e:
            return jsonify({'error': f'Invalid request: {e.message}'}), 400
        except Exception as e:
            logger.error(f"Error assessing comment quality: {e}")
            return jsonify({'error': 'Internal server error'}), 500

    def create_api_key(self):
        """Create a new API key."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body must be JSON'}), 400
            
            name = data.get('name', '').strip()
            description = data.get('description', '').strip()
            rate_limit = data.get('rate_limit_per_hour', 1000)
            
            if not name:
                return jsonify({'error': 'API key name is required'}), 400
            
            if rate_limit < 1 or rate_limit > 10000:
                return jsonify({'error': 'Rate limit must be between 1 and 10000 requests per hour'}), 400
            
            manager = get_api_key_manager()
            key_data = manager.generate_api_key(
                name=name,
                description=description,
                rate_limit_per_hour=rate_limit,
                created_by='web_interface'
            )
            
            return jsonify({
                'success': True,
                'message': 'API key created successfully',
                'api_key': key_data['api_key'],  # Only shown once
                'key_id': key_data['key_id'],
                'name': key_data['name'],
                'rate_limit_per_hour': key_data['rate_limit_per_hour']
            })
            
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return jsonify({'error': 'Failed to create API key'}), 500

    def list_api_keys(self):
        """List all API keys."""
        try:
            manager = get_api_key_manager()
            keys = manager.list_api_keys()
            
            return jsonify({
                'success': True,
                'api_keys': keys,
                'total_count': len(keys)
            })
            
        except Exception as e:
            logger.error(f"Error listing API keys: {e}")
            return jsonify({'error': 'Failed to list API keys'}), 500

    def deactivate_api_key(self, key_id):
        """Deactivate an API key."""
        try:
            manager = get_api_key_manager()
            manager.deactivate_api_key(key_id)
            
            return jsonify({
                'success': True,
                'message': f'API key {key_id} deactivated successfully'
            })
            
        except Exception as e:
            logger.error(f"Error deactivating API key: {e}")
            return jsonify({'error': 'Failed to deactivate API key'}), 500

    def get_api_usage_stats(self):
        """Get API usage statistics."""
        try:
            key_id = request.args.get('key_id')
            
            # Validate and sanitize parameters
            if key_id == '':
                key_id = None
            
            try:
                days = int(request.args.get('days', 7))
                if days < 1 or days > 365:
                    days = 7
            except (ValueError, TypeError):
                days = 7
            
            manager = get_api_key_manager()
            stats = manager.get_usage_stats(key_id=key_id, days=days)
            
            return jsonify({
                'success': True,
                'usage_stats': stats,
                'period_days': days,
                'key_id': key_id
            })
            
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}")
            return jsonify({'error': 'Failed to get usage statistics'}), 500

def create_app(config=None):
    """Create and configure Flask application."""
    app = Flask(__name__, template_folder='templates')
    
    # Configure CORS - Allow requests from Appen domains
    CORS(app, 
         origins=[
             'https://view.appen.io',
             'https://*.appen.io',
             'https://appen.com',
             'https://*.appen.com',
             'http://localhost:*',  # For development
             'https://localhost:*'  # For development with HTTPS
         ],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization', 'X-API-Key'],
         supports_credentials=True
    )
    
    # Configure session management
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'appencorrect-dev-key-change-in-production')
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Apply configuration
    if config:
        app.config.update(config)
    
    # Initialize API
    api = AppenCorrectAPI(config)
    
    # Register routes
    @app.route('/')
    def demo():
        """Serve the demo page."""
        return render_template('demo.html')
    
    @app.route('/api-docs')
    @require_auth
    def api_docs():
        """Serve the API documentation page - requires Appen email login."""
        # Get base URL from environment or use current request URL
        api_base_url = os.getenv('API_BASE_URL', request.url_root.rstrip('/'))
        return render_template('api_docs.html', api_base_url=api_base_url)
    
    @app.route('/api-management')
    @require_auth
    def api_management():
        """Serve the API management page - requires Appen email login."""
        return render_template('api_management.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login page for Appen email authentication."""
        if request.method == 'GET':
            # Check if already authenticated
            if is_authenticated():
                # Redirect to the page they were trying to access
                next_page = request.args.get('next', '/api-management')
                return redirect(next_page)
            
            return render_login_page(mode='login')
        
        # Handle POST request
        try:
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '').strip()
            
            if not email:
                return render_login_page(mode='login', error="Email address is required")
            
            # Authenticate user
            success, message = authenticate_user(email, password)
            
            if success:
                # Create session
                create_session(email)
                logger.info(f"Successful login for Appen user: {email}")
                
                # Redirect to the page they were trying to access
                next_page = request.args.get('next', '/api-management')
                return redirect(next_page)
            else:
                logger.warning(f"Failed login attempt for email: {email}")
                return render_login_page(mode='login', error=message)
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return render_login_page(mode='login', error="Login system error. Please try again.")

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """Registration page for new Appen users."""
        if request.method == 'GET':
            # Check if already authenticated
            if is_authenticated():
                return redirect('/api-management')
            
            return render_login_page(mode='register')
        
        # Handle POST request
        try:
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            if not email:
                return render_login_page(mode='register', error="Email address is required")
            
            if not password:
                return render_login_page(mode='register', error="Password is required")
            
            if password != confirm_password:
                return render_login_page(mode='register', error="Passwords do not match")
            
            # Create user
            success, message = create_user(email, password)
            
            if success:
                logger.info(f"New Appen user registered: {email}")
                return render_login_page(mode='login', success="Account created successfully! Please login.")
            else:
                logger.warning(f"Failed registration attempt for email: {email}")
                return render_login_page(mode='register', error=message)
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return render_login_page(mode='register', error="Registration system error. Please try again.")

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        """Forgot password page."""
        if request.method == 'GET':
            return render_forgot_password_page()
        
        # Handle POST request
        try:
            email = request.form.get('email', '').strip().lower()
            
            if not email:
                return render_forgot_password_page(error="Email address is required")
            
            # Generate reset token (this creates the token even if user doesn't exist - security)
            success, result = generate_password_reset_token(email)
            
            if success:
                reset_token = result
                logger.info(f"Password reset requested for: {email}")
                
                # Send reset email instead of displaying link (security fix)
                email_sent = send_password_reset_email(email, reset_token, request.url_root)
                
                if email_sent:
                    return render_forgot_password_page(success=f"""
                        Password reset instructions have been sent to <strong>{email}</strong>.
                        <br><br>
                        Please check your email and follow the instructions to reset your password.
                        The reset link will expire in <strong>1 hour</strong>.
                        <br><br>
                        <em>If you don't see the email, check your spam folder.</em>
                    """)
                else:
                    logger.error(f"Failed to send password reset email to {email}")
                    return render_forgot_password_page(error="Failed to send reset email. Please try again or contact support.")
            else:
                # Always show success message for security (don't reveal if user exists)
                return render_forgot_password_page(success=f"""
                    If an account exists for <strong>{email}</strong>, password reset instructions have been sent.
                    <br><br>
                    Please check your email and follow the instructions to reset your password.
                    <br><br>
                    <em>If you don't see the email, check your spam folder.</em>
                """)
                
        except Exception as e:
            logger.error(f"Forgot password error: {e}")
            return render_forgot_password_page(error="System error. Please try again.")

    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        """Password reset page."""
        # Verify token
        email = verify_reset_token(token)
        if not email:
            return render_forgot_password_page(error="Invalid or expired reset link. Please request a new one.")
        
        if request.method == 'GET':
            return render_reset_password_page(token, email)
        
        # Handle POST request
        try:
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            if not password:
                return render_reset_password_page(token, email, error="Password is required")
            
            if password != confirm_password:
                return render_reset_password_page(token, email, error="Passwords do not match")
            
            # Reset password
            success, message = reset_password_with_token(token, password)
            
            if success:
                logger.info(f"Password reset completed for: {email}")
                return render_login_page(mode='login', success="Password reset successfully! Please login with your new password.")
            else:
                return render_reset_password_page(token, email, error=message)
                
        except Exception as e:
            logger.error(f"Password reset error: {e}")
            return render_reset_password_page(token, email, error="System error. Please try again.")
    
    @app.route('/logout')
    def logout():
        """Logout current user."""
        user_email = session.get('user_email', 'unknown')
        logout_user()
        logger.info(f"User logged out: {user_email}")
        return redirect(url_for('demo'))
    
    @app.route('/health')
    def health():
        """Health check endpoint - no auth required."""
        return api.health_check()
    
    # Demo endpoint (no auth required for web interface)
    @app.route('/demo/check', methods=['POST'])
    def demo_check():
        """Demo text checking endpoint - no authentication required."""
        return api.check_text()
    
    @app.route('/demo/assess/quality', methods=['POST'])
    def demo_assess_quality():
        """Demo quality assessment endpoint - no authentication required."""
        return api.assess_comment_quality()
    
    @app.route('/demo/feedback', methods=['POST'])
    def demo_feedback():
        """Demo feedback endpoint - no authentication required."""
        return api.submit_feedback()
    
    # Protected API endpoints (require API key)
    @app.route('/check', methods=['POST'])
    @require_api_key
    @track_api_usage
    def check():
        """Main text checking endpoint."""
        return api.check_text()
    
    @app.route('/check/spelling', methods=['POST'])
    @require_api_key
    @track_api_usage
    def check_spelling():
        """Spelling-only endpoint."""
        return api.check_spelling()
    
    @app.route('/check/grammar', methods=['POST'])
    @require_api_key
    @track_api_usage
    def check_grammar():
        """Grammar-only endpoint."""
        return api.check_grammar()
    
    @app.route('/feedback', methods=['POST'])
    @require_api_key
    @track_api_usage
    def submit_feedback():
        """Submit feedback on AI corrections."""
        return api.submit_feedback()
    
    @app.route('/assess/quality', methods=['POST'])
    @require_api_key
    @track_api_usage
    def assess_comment_quality():
        """Assess comment quality for rating tasks."""
        return api.assess_comment_quality()
    
    # API Management endpoints (require authentication)
    @app.route('/api/keys', methods=['POST'])
    @require_auth
    def create_api_key():
        """Create a new API key - requires Appen email login."""
        return api.create_api_key()
    
    @app.route('/api/keys', methods=['GET'])
    @require_auth
    def list_api_keys():
        """List all API keys - requires Appen email login."""
        return api.list_api_keys()
    
    @app.route('/api/keys/<key_id>/deactivate', methods=['POST'])
    @require_auth
    def deactivate_api_key(key_id):
        """Deactivate an API key - requires Appen email login."""
        return api.deactivate_api_key(key_id)
    
    @app.route('/api/usage', methods=['GET'])
    @require_auth
    def get_usage_stats():
        """Get API usage statistics - requires Appen email login."""
        return api.get_api_usage_stats()
    
    @app.route('/api/feedback', methods=['GET'])
    @require_auth
    def get_feedback_data():
        """Get user feedback data - requires Appen email login."""
        return api.get_feedback_data()
    
    @app.route('/api/cost-analytics', methods=['GET'])
    @require_auth
    def get_cost_analytics():
        """Get cost analytics data - requires Appen email login."""
        return api.get_cost_analytics()
    
    @app.route('/api/logs', methods=['GET'])
    @require_auth
    def get_logs():
        """Get application logs - requires Appen email login."""
        return api.get_logs()
    
    # Cache Control endpoints (require API key for testing) ⭐ NEW
    @app.route('/api/cache/toggle', methods=['POST'])
    @require_api_key
    def toggle_cache():
        """Toggle cache on/off for specific API key - requires API key."""
        try:
            data = request.get_json() or {}
            enabled = data.get('enabled', True)
            
            # Get the API-key specific checker instance
            checker = api._get_checker()
            
            # Toggle cache for this specific API key's instance
            checker.set_cache_enabled(bool(enabled))
            
            status = "enabled" if checker.cache_enabled else "disabled"
            api_key_id = request.api_key_info['key_id']
            logger.info(f"Cache {status} for API key: {api_key_id}")
            
            return jsonify({
                'success': True,
                'cache_enabled': checker.cache_enabled,
                'cache_size': len(checker.api_cache),
                'api_key_id': api_key_id,
                'message': f'Cache {status} for this API key',
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error toggling cache: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Failed to toggle cache'
            }), 500
    
    @app.route('/api/cache/status', methods=['GET'])
    @require_api_key
    def get_cache_status():
        """Get cache status for specific API key - requires API key."""
        try:
            # Get the API-key specific checker instance
            checker = api._get_checker()
            
            # Get global cache info for reference
            from cache_client import get_cache
            global_cache = get_cache()
            
            api_key_id = request.api_key_info['key_id']
            
            return jsonify({
                'success': True,
                'cache_enabled': checker.cache_enabled,
                'cache_size': len(checker.api_cache),
                'cache_hits': checker.stats['cache_hits'],
                'api_key_id': api_key_id,
                'global_cache_available': global_cache.is_available(),
                'global_cache_connected': global_cache.connected,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Failed to get cache status'
            }), 500
    
    # Custom Instructions endpoints (require API key)
    @app.route('/custom-instructions', methods=['POST'])
    @require_api_key
    @track_api_usage
    def set_custom_instructions():
        """Set custom instructions for a specific use case."""
        return api.set_custom_instructions()

    @app.route('/custom-instructions', methods=['PUT'])
    @require_api_key
    @track_api_usage
    def update_custom_instructions():
        """Update custom instructions for a specific use case."""
        return api.set_custom_instructions()  # Same logic as POST

    @app.route('/custom-instructions', methods=['GET'])
    @require_api_key
    @track_api_usage
    def get_custom_instructions():
        """Get custom instructions for a specific use case or all instructions."""
        return api.get_custom_instructions()

    @app.route('/custom-instructions', methods=['DELETE'])
    @require_api_key
    @track_api_usage
    def remove_custom_instructions():
        """Remove custom instructions for a specific use case."""
        return api.remove_custom_instructions()
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({'error': 'Method not allowed'}), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app 