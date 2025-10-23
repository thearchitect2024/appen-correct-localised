#!/usr/bin/env python3
"""
AppenCorrect - Main Application Entry Point

A comprehensive spelling and grammar checker combining:
- PyEnchant spell checking (Windows-compatible)
- LanguageTool for grammar analysis
- Gemini AI for contextual validation

Usage:
    python app.py                           # Run development server
    waitress-serve --host=0.0.0.0 --port=5006 app:app  # Run with Waitress
"""

import os
import logging
from dotenv import load_dotenv
from api import create_app

# Load environment variables
load_dotenv()

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure logging with UTF-8 encoding for Windows compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/appencorrect.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Configure separate feedback logger
feedback_logger = logging.getLogger('feedback')
feedback_handler = logging.FileHandler('logs/feedback.log', encoding='utf-8')
feedback_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
feedback_logger.addHandler(feedback_handler)
feedback_logger.setLevel(logging.INFO)
feedback_logger.propagate = False  # Don't propagate to root logger

# Create configuration from environment variables
config = {}
if os.getenv('APPENCORRECT_DISABLE_GEMINI'):
    config['APPENCORRECT_DISABLE_GEMINI'] = True
if os.getenv('APPENCORRECT_DISABLE_SPELLING'):
    config['APPENCORRECT_DISABLE_SPELLING'] = True  
if os.getenv('APPENCORRECT_DISABLE_GRAMMAR'):
    config['APPENCORRECT_DISABLE_GRAMMAR'] = True

# Create Flask application
app = create_app(config)

if __name__ == '__main__':
    # Development server - for production use Waitress
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                        AppenCorrect                          ║
    ║              Spelling & Grammar Checker API                  ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  Demo:   http://localhost:5006/                              ║
    ║  Health: http://localhost:5006/health                        ║
    ║                                                              ║
    ║  For production use:                                         ║
    ║  waitress-serve --host=0.0.0.0 --port=5006 app:app          ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(debug=False, host='0.0.0.0', port=5006) 