#!/usr/bin/env python3
"""
Simple test script for GEMINI_VERTEX_API_KEY
Tests the Gemini Vertex AI API with the provided key and code example.
"""

import os
import sys
import time
from datetime import datetime

def test_gemini_vertex_api():
    """Test the Gemini Vertex API with the provided key."""
    
    # Set the API key and project
    api_key = "AIzaSyBOQIfYtUDqEySWNQKLx7HmNNBZn8WMGH8"
    project_id = "appencorrect"
    os.environ['GEMINI_VERTEX_API_KEY'] = api_key
    os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
    
    print("="*60)
    print("GEMINI VERTEX API TEST")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"API Key: {api_key[:20]}...")
    print(f"Project ID: {project_id}")
    print(f"Python Environment: {sys.executable}")
    print("-" * 60)
    
    try:
        print("Importing required modules...")
        from google import genai
        from google.genai.types import HttpOptions
        print("✓ Import successful")
        
        print("Initializing client...")
        # Try Vertex AI first (with project), then fall back to regular API
        try:
            import vertexai
            vertexai.init(project="appencorrect", location="us-central1")
            client = genai.Client(vertexai=True, http_options=HttpOptions(api_version="v1"))
            print("✓ Client initialized with Vertex AI (project: appencorrect)")
        except Exception as vertex_error:
            print(f"Vertex AI failed: {vertex_error}")
            print("Falling back to regular API...")
            client = genai.Client(api_key=api_key, http_options=HttpOptions(api_version="v1"))
            print("✓ Client initialized with regular API")
        
        print("Making API request...")
        start_time = time.time()
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="How does AI work?",
        )
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        print("✓ API call successful")
        print("-" * 60)
        print("RESPONSE:")
        print("-" * 60)
        print(response.text)
        print("-" * 60)
        print(f"Response time: {latency_ms:.2f} ms")
        print("✓ TEST PASSED")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Make sure you have the google-genai library installed:")
        print("pip install google-genai")
        return False
        
    except Exception as e:
        print(f"✗ API call failed: {e}")
        print(f"Error type: {type(e).__name__}")
        return False
    
    finally:
        print("="*60)

def check_environment():
    """Check if we're in the correct Python environment."""
    print("Environment Check:")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    
    # Check if we're in the expected virtual environment
    expected_env_path = "/home/ec2-user/autocase_env"
    if expected_env_path in sys.executable:
        print(f"✓ Using expected environment: {expected_env_path}")
    else:
        print(f"⚠ Not using expected environment: {expected_env_path}")
        print("Consider activating the correct environment:")
        print(f"source {expected_env_path}/bin/activate")
    
    print()

if __name__ == "__main__":
    check_environment()
    success = test_gemini_vertex_api()
    
    if success:
        print("Test completed successfully!")
        sys.exit(0)
    else:
        print("Test failed!")
        sys.exit(1)
