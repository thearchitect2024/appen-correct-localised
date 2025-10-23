# AppenCorrect Performance Testing

This directory contains a comprehensive testing framework for evaluating AppenCorrect's performance across different models and sentence types.

## Files Created

- **`test.py`** - Main testing script
- **`run_test_example.bat`** - Windows batch file with example commands
- **`run_test_example.sh`** - Unix/Linux shell script with example commands
- **`TEST_README.md`** - This documentation file

## Quick Start

### 1. Set up your environment
Make sure your `.env` file contains:
```env
# For OpenAI API testing
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=your_openai_key_here

# For Gemini API testing
# OPENAI_MODEL=gemini-2.5-flash-lite
# GEMINI_API_KEY=your_gemini_key_here
```

### 2. Run basic tests
```bash
# Test 10 English sentences (default)
python test.py --rows 10

# Test 25 French sentences
python test.py --rows 25 --file tests/sentences.csv

# Test with custom output filename
python test.py --rows 15 --file tests/sentences_eng.csv --output my_results.csv
```

### 3. Run example test suites
```bash
# Windows
run_test_example.bat

# Unix/Linux/Mac
./run_test_example.sh
```

## Command Line Options

- **`--rows, -r`** - Number of sentences to test (default: 10)
- **`--file, -f`** - Path to CSV file with sentences (default: tests/sentences_eng.csv)
- **`--output, -o`** - Output CSV filename (auto-generated if not specified)

## Output Files

The script generates timestamped CSV files with detailed metrics:

**Filename format:** `test_results_{source}_{model}_{timestamp}.csv`

**Columns include:**
- `timestamp` - When the test was run
- `sentence_id` - Sequential ID of the sentence
- `status` - Success/error status
- `original_text` - Input sentence
- `processed_text` - Corrected sentence
- `latency_ms` - Processing time in milliseconds
- `input_tokens` - Estimated input token count
- `output_tokens` - Estimated output token count
- `total_corrections` - Number of corrections made
- `spelling_corrections` - Spelling error corrections
- `grammar_corrections` - Grammar error corrections
- `style_corrections` - Style suggestion corrections
- `api_type` - Which API was used (openai/gemini)
- `model` - Specific model used
- `processing_time` - Processing time from the API
- `detected_language` - Auto-detected language
- `corrections_detail` - Detailed correction information

## Test Data Files

- **`tests/sentences_eng.csv`** - English sentences with various errors
- **`tests/sentences.csv`** - French sentences with various errors

You can add your own CSV files with a `sentences` column header.

## Model Switching

The system automatically switches APIs based on the `OPENAI_MODEL` setting:

- **Models containing "mini"** → OpenAI API (e.g., `gpt-4o-mini`, `o1-mini`)
- **Models containing "gemini"** → Gemini API (e.g., `gemini-2.5-flash-lite`)
- **Other models** → Default to Gemini API

## Performance Comparison Example

To compare different models:

1. **Test with OpenAI:**
   ```bash
   # Set in .env: OPENAI_MODEL=gpt-4o-mini
   python test.py --rows 50 --file tests/sentences_eng.csv
   ```

2. **Test with Gemini:**
   ```bash
   # Set in .env: OPENAI_MODEL=gemini-2.5-flash-lite
   python test.py --rows 50 --file tests/sentences_eng.csv
   ```

3. **Compare the results** by analyzing the generated CSV files

## Summary Statistics

After each test run, you'll see a summary including:
- Total sentences tested
- Success/failure rates
- Average latency
- Token usage statistics
- Total corrections found
- API and model information

## Troubleshooting

**Common issues:**
- **"API not available"** - Check your API key in the `.env` file
- **"File not found"** - Verify the path to your sentences CSV file
- **"No sentences found"** - Ensure your CSV has a `sentences` column header
- **Import errors** - Make sure you're running from the project root directory

**Debug mode:**
```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
python test.py --rows 5
```