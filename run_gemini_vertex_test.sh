#!/bin/bash

# Test script runner for GEMINI_VERTEX_API_KEY
# This script activates the autocase_env and runs the Gemini Vertex test

echo "========================================="
echo "GEMINI VERTEX API TEST RUNNER"
echo "========================================="

# Define the virtual environment path
VENV_PATH="/home/ec2-user/autocase_env"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    echo "Please create the virtual environment first:"
    echo "python3 -m venv $VENV_PATH"
    exit 1
fi

# Activate the virtual environment
echo "Activating virtual environment: $VENV_PATH"
source "$VENV_PATH/bin/activate"

# Verify activation
if [ "$VIRTUAL_ENV" != "$VENV_PATH" ]; then
    echo "Error: Failed to activate virtual environment"
    exit 1
fi

echo "✓ Virtual environment activated: $VIRTUAL_ENV"
echo

# Check if google-genai is installed
echo "Checking dependencies..."
if python -c "import google.genai" 2>/dev/null; then
    echo "✓ google-genai is already installed"
else
    echo "Installing google-genai..."
    pip install google-genai
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install google-genai"
        exit 1
    fi
    echo "✓ google-genai installed successfully"
fi

# Check if vertexai is installed (for Vertex AI support)
if python -c "import vertexai" 2>/dev/null; then
    echo "✓ vertexai is already installed"
else
    echo "Installing google-cloud-aiplatform..."
    pip install google-cloud-aiplatform
    if [ $? -ne 0 ]; then
        echo "Warning: Failed to install google-cloud-aiplatform (Vertex AI will not be available)"
    else
        echo "✓ google-cloud-aiplatform installed successfully"
    fi
fi

echo
echo "Running Gemini Vertex API test..."
echo "-----------------------------------------"

# Run the test script
python /home/ec2-user/apps/AppenCorrect/test_gemini_vertex.py

# Capture the exit code
exit_code=$?

echo
echo "Test completed with exit code: $exit_code"

# Deactivate virtual environment
deactivate

exit $exit_code
