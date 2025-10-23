#!/bin/bash
# Example shell script to run AppenCorrect performance tests
# Make sure your .env file is configured with OPENAI_MODEL and appropriate API key

echo "Running AppenCorrect Performance Tests"
echo "======================================"

echo ""
echo "Test 1: 5 English sentences"
python test.py --rows 5 --file tests/sentences_eng.csv

echo ""
echo "Test 2: 5 French sentences"
python test.py --rows 5 --file tests/sentences.csv

echo ""
echo "Test 3: 10 English sentences with custom output name"
python test.py --rows 10 --file tests/sentences_eng.csv --output my_custom_test.csv

echo ""
echo "Tests completed! Check the generated CSV files for detailed results."