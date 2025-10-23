"""
AppenCorrect: Comprehensive Spelling and Grammar Checker

A multi-layered text correction system combining:
- PyEnchant spell checking (Windows-compatible)
- LanguageTool for grammar analysis
- Gemini AI for contextual validation

Python API Usage:
    from appencorrect import PythonAPI
    
    api = PythonAPI()
    result = api.check_text("This is a sentance with erors.")
    
Or use convenience functions:
    from appencorrect import check_text, correct_text
    
    result = check_text("This is a sentance.")
    corrected = correct_text("This is a sentance.")
"""

__version__ = "2.0.0"
__author__ = "Appen Automation Solutions Team"

from .core import AppenCorrect
from .api import create_app
from .python_api import PythonAPI, check_text, correct_text

__all__ = ['AppenCorrect', 'create_app', 'PythonAPI', 'check_text', 'correct_text'] 