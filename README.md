# AppenCorrect

🎯 **Advanced AI-Powered Text Correction & Comment Quality Assessment**

A comprehensive spelling, grammar, and comment quality assessment system powered by Google's Gemini AI with multi-layered text analysis capabilities.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-Appen%2FAppenCorrect-blue.svg)](https://github.com/Appen/AppenCorrect)
[![API: REST](https://img.shields.io/badge/API-REST-green.svg)](https://restfulapi.net/)

## 🌟 Features

### 🔧 **Core Text Correction**
- **AI-First Approach**: Powered by Google Gemini AI for contextual understanding
- **Context-Aware Homophone Correction**: Intelligent detection of which instances of "there/their/they're", "your/you're", "its/it's" need correction based on grammatical context ⭐ *NEW*
- **Multi-Language Support**: Automatic language detection (English, French, Spanish, German, Italian)
- **Comprehensive Analysis**: Spelling, grammar, and style corrections
- **Precise Position-Based Corrections**: Uses exact API positions for reliable text replacement
- **Language-Specific Rules**: Tailored correction rules for different languages

### 🎯 **Comment Quality Assessment** ⭐ *NEW*
- **Quality Scoring**: 1-10 numerical scores with quality levels (excellent, good, fair, poor)
- **Multi-Factor Analysis**: 
  - Technical Quality (30%): Grammar, spelling, formatting
  - Content Quality (40%): Clarity, relevance, completeness
  - Length Appropriateness (15%): Adequate detail without being excessive
  - Rating Task Suitability (15%): Helpfulness, objectivity, professional tone
- **Contextual Assessment**: Task-specific evaluation for rating scenarios
- **Improvement Suggestions**: AI-generated specific recommendations
- **Strengths Identification**: Highlights what works well in comments

### 🚀 **Multiple Interfaces**
- **Python API**: Direct programmatic access
- **REST API**: HTTP endpoints for web integration
- **Flask Web Interface**: Interactive demo interface with precision highlighting ⭐ *IMPROVED*
  - Perfect text alignment for error highlighting
  - Context-aware correction suggestions
  - Real-time homophone detection and correction

### ⚡ **Performance & Reliability**
- **Redis/Valkey Cache**: High-performance caching with 81.7% hit rate for instant responses ⭐ *NEW*
- **300 Worker Threads**: Optimized for high-concurrency workloads (handles 500+ concurrent users) ⭐ *NEW*
- **Smart Caching**: Reduces API calls and improves response times by up to 70%
- **Rate Limiting**: Built-in protection for API usage with configurable limits
- **Error Handling**: Comprehensive error management and logging
- **Statistics Tracking**: Usage analytics and performance metrics
- **Load Testing Suite**: Comprehensive testing tools for 100, 200, and 500 concurrent users ⭐ *NEW*

### 🔐 **Enterprise Management** ⭐ *NEW*
- **API Key Management**: Full lifecycle management with rate limiting and usage tracking
- **Cost Analytics**: AI API usage monitoring and cost optimization insights
- **Real-time Log Viewer**: Live system monitoring with filtering and search capabilities
- **User Feedback System**: Integrated feedback collection and analysis
- **Custom Instructions**: Configurable AI behavior for specific use cases
- **Authentication System**: Secure access control for management interfaces

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- Google Gemini API key
- Redis/ElastiCache instance (optional, for high-performance caching) ⭐ *NEW*

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/Appen/AppenCorrect.git
cd AppenCorrect

# Install dependencies (includes Redis support)
pip install -r requirements.txt

# Set up environment variables
cp env.example .env
# Edit .env and add your GEMINI_API_KEY and Redis configuration
```

### Redis/Valkey Cache Setup ⭐ *NEW*

For high-performance production deployments with instant cache responses:

```bash
# Install Redis dependencies
pip install redis==5.0.1 valkey==5.0.8

# Configure Redis in .env file
VALKEY_HOST=your-redis-endpoint.cache.amazonaws.com
VALKEY_PORT=6379
VALKEY_DB=0
VALKEY_ENABLED=true
VALKEY_SSL=true  # For ElastiCache
VALKEY_DEFAULT_TTL=3600

# Test cache connection
python3 test_cache.py
```

**Performance Benefits:**
- 🚀 **0.000s response time** for cached requests
- 📈 **81.7% cache hit rate** in production workloads
- 💰 **70% reduction** in AI API costs
- ⚡ **8x faster** completion under high load

See [REDIS_SETUP.md](REDIS_SETUP.md) for detailed setup instructions.

### Package Installation

```bash
# Install as a package (for use in other projects)
pip install -e .
```

## 🔑 Configuration

Create a `.env` file in the project root:

```env
# Required: Google Gemini API key
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Gemini model selection
GEMINI_MODEL=gemini-2.5-flash-lite

# Optional: Language detector preference
LANGUAGE_DETECTOR=langdetect  # or 'lingua' or 'disabled'

# Performance Configuration ⭐ NEW
WORKERS=300
TIMEOUT=30
MAX_REQUESTS=1000
MAX_REQUESTS_JITTER=50

# Redis/Valkey Cache Configuration ⭐ NEW
VALKEY_HOST=your-redis-endpoint.cache.amazonaws.com
VALKEY_PORT=6379
VALKEY_DB=0
VALKEY_PASSWORD=
VALKEY_SSL=true
VALKEY_ENABLED=true
VALKEY_DEFAULT_TTL=3600

# Flask Configuration
FLASK_DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=5005
SECRET_KEY=your-secret-key-change-in-production

# Application Configuration
APPENCORRECT_DISABLE_GEMINI=false
APPENCORRECT_DISABLE_SPELLING=false
APPENCORRECT_DISABLE_GRAMMAR=false
```

## 🚀 Quick Start

### Python API Usage

```python
from appencorrect import PythonAPI

# Initialize the API
api = PythonAPI()

# 🎯 NEW: Assess comment quality for rating tasks
result = api.assess_comment_quality(
    comment="This product demonstrates excellent build quality with attention to detail that exceeds expectations. The materials feel premium and durable, while the design is both functional and aesthetically pleasing. I would highly recommend this to anyone looking for a reliable, well-crafted solution that provides outstanding value for the investment.",
    rating_context="Product review rating task"
)

print(f"Quality Score: {result['quality_score']}/10")
print(f"Quality Level: {result['quality_level']}")
print(f"Assessment: {result['assessment']}")
print(f"Character Count: {result['comment_analysis']['character_count']}")

# Show improvement suggestions
for suggestion in result['suggestions']:
    print(f"💡 {suggestion}")

# Show technical corrections
for correction in result['technical_corrections']:
    print(f"🔧 {correction['original']} → {correction['suggestion']}")

# Example of short comment with length penalty
short_result = api.assess_comment_quality(
    comment="Good product!",  # Only 13 characters
    rating_context="Product review rating task"
)
print(f"\nShort comment score: {short_result['quality_score']}/10 (capped due to length)")

# ✏️ Regular text correction
corrected = api.correct_text("This sentance has erors.")
print(f"Corrected: {corrected}")

# 📊 Detailed analysis
result = api.check_text("Your text here")
print(f"Found {len(result['corrections'])} corrections")
```

### REST API Usage

Start the server:
```bash
python app.py
```

**Comment Quality Assessment:**
```bash
curl -X POST http://localhost:5006/assess/quality \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "This product is really good and I like it alot.",
    "rating_context": "Product review rating task"
  }'
```

**Text Correction:**
```bash
curl -X POST http://localhost:5006/check \
  -H "Content-Type: application/json" \
  -d '{"text": "This sentance has erors."}'
```

**Homophone-Specific Correction:** ⭐ *NEW*
```bash
curl -X POST http://localhost:5006/check \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The companys quarterly report shows there have been significant improvements in there performance metrics."
  }'
```

**Per-API-Key Cache Control:** ⭐ *NEW*
```bash
# Check current cache status for your API key
curl -X GET https://appencorrect.xlostxcoz.com/api/cache/status \
  -H "X-API-Key: your_api_key"

# Disable cache for your API key only (safe for production)
curl -X POST https://appencorrect.xlostxcoz.com/api/cache/toggle \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"enabled": false}'

# Re-enable cache for your API key
curl -X POST https://appencorrect.xlostxcoz.com/api/cache/toggle \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"enabled": true}'

# 🔒 ISOLATION: Each API key has independent cache control
# ✅ Production Safe: Disabling cache only affects YOUR API key
# 🧪 Perfect for A/B testing and performance analysis

# For local development, use:
# curl -X GET http://localhost:5006/api/cache/status \
#   -H "X-API-Key: your_api_key"

# Example with test API key (ready to copy-paste):
# curl -X GET https://appencorrect.xlostxcoz.com/api/cache/status \
#   -H "X-API-Key: appencorrect_6cc586912e264062afdc0810f22d075a"
```

### Web Interface

Visit `http://localhost:5006` for the interactive demo interface featuring:

- **✨ Perfect Highlighting Alignment**: Error words are precisely highlighted without position drift
- **🧠 Context-Aware Corrections**: Smart homophone detection based on grammatical context  
- **⚡ Real-Time Processing**: Instant feedback with position-accurate corrections
- **🎯 Professional Text Examples**: Pre-loaded examples demonstrating advanced correction capabilities

## 📚 API Reference

### Python API Methods

#### Comment Quality Assessment
```python
assess_comment_quality(comment, rating_context=None, enable_quality_assessment=True)
```
- **comment**: Text to assess
- **rating_context**: Optional context for task-specific evaluation
- **Returns**: Quality score, level, assessment, suggestions, and technical analysis

#### Text Correction
```python
# Comprehensive checking
check_text(text, options=None)

# Specific checks
check_spelling(text)
check_grammar(text)

# Simple correction
correct_text(text)  # Returns just the corrected text
```

#### Utility Methods
```python
detect_language(text)           # Detect text language
get_statistics()                # API usage statistics
health_check()                  # System health status
is_ready()                      # Check if API is ready
```

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/assess/quality` | POST | Assess comment quality |
| `/check` | POST | Comprehensive text checking |
| `/check/spelling` | POST | Spelling-only checking |
| `/check/grammar` | POST | Grammar-only checking |
| `/demo/check` | POST | Demo interface text checking with enhanced homophone logic ⭐ |
| `/feedback` | POST | Submit feedback on corrections |
| `/health` | GET | Health check |
| `/` | GET | Interactive demo web interface |
| `/api-management` | GET | API key management interface |

#### Enterprise Management Endpoints ⭐ *NEW*
| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/keys` | GET | List all API keys | Appen Login |
| `/api/keys` | POST | Create new API key | Appen Login |
| `/api/keys/<id>/deactivate` | POST | Deactivate API key | Appen Login |
| `/api/usage` | GET | Get usage statistics | Appen Login |
| `/api/feedback` | GET | Get feedback data | Appen Login |
| `/api/cost-analytics` | GET | Get cost analytics | Appen Login |
| `/api/logs` | GET | Get system logs | Appen Login |
| `/custom-instructions` | GET/POST/PUT/DELETE | Manage custom instructions | API Key |

#### Per-API-Key Cache Control Endpoints ⭐ *NEW*
| Endpoint | Method | Description | Auth Required | Scope |
|----------|--------|-------------|---------------|-------|
| `/api/cache/status` | GET | Get cache status for your API key | API Key | Per-API-Key |
| `/api/cache/toggle` | POST | Enable/disable cache for your API key only | API Key | Per-API-Key |

## 🎯 Comment Quality Assessment

The comment quality feature evaluates text based on multiple criteria:

### Quality Factors

1. **Technical Quality (30%)**
   - Grammar and spelling accuracy
   - Sentence structure and clarity
   - Proper punctuation and formatting

2. **Content Quality (40%)**
   - Conceptual clarity and coherence
   - Relevance to the topic/task
   - Completeness of explanation
   - Logical flow of ideas

3. **Length Appropriateness (15%)**
   - Adequate detail without being excessive
   - Conciseness while maintaining completeness
   - Appropriate depth for the context

4. **Rating Task Suitability (15%)**
   - Helpfulness for decision-making
   - Objectivity and fairness
   - Professional tone and language
   - Constructive feedback approach

### Length Requirements for Rating Tasks

- **🚨 Under 100 characters**: Maximum score of 4/10 (insufficient explanation)
- **⚠️ Under 300 characters**: Cannot achieve excellent (9-10/10) rating
- **✅ 300+ characters**: Required for highest quality scores in rating contexts

### Quality Levels

- **🌟 Excellent (9-10)**: Exceptional quality, minimal issues, highly valuable (requires 300+ characters)
- **👍 Good (7-8)**: High quality with minor issues, valuable contribution
- **⚠️ Fair (5-6)**: Adequate quality with some issues, acceptable
- **❌ Poor (1-4)**: Multiple issues affecting quality, needs improvement (comments under 100 chars max out here)

## 🧠 Context-Aware Homophone Correction ⭐ *NEW*

AppenCorrect now features intelligent homophone detection that understands grammatical context to make precise corrections:

### Smart Detection Patterns

**✅ Correctly Preserves:**
- `"there have been improvements"` → Existential usage, keeps "there"
- `"over there by the building"` → Positional usage, keeps "there"
- `"you're going to succeed"` → Contraction usage, keeps "you're"

**🔧 Intelligently Corrects:**
- `"there performance metrics"` → Possessive usage, changes to "their"
- `"there team's dedication"` → Possessive usage, changes to "their"
- `"your going to succeed"` → Contraction needed, changes to "you're"

### Supported Homophones

- **there/their/they're**: Existential vs possessive vs contraction
- **your/you're**: Possessive vs contraction
- **its/it's**: Possessive vs contraction
- **to/too/two**: Preposition vs adverb vs number
- **were/where/wear**: Past tense vs location vs clothing
- And many more common homophone pairs

### How It Works

1. **Context Analysis**: Examines 20 characters around each homophone
2. **Pattern Matching**: Uses regex patterns to identify correct usage
3. **Selective Correction**: Only corrects instances that don't match correct patterns
4. **Position Precision**: Uses exact API positions to avoid correction conflicts

## 📁 Project Structure

```
AppenCorrect/
├── __init__.py               # Package initialization & main imports
├── core.py                   # Core text processing logic
├── python_api.py             # Python API interface (main API class)
├── api.py                    # REST API endpoints (Flask routes)
├── gemini_api.py             # Google Gemini AI integration
├── rate_limiter.py           # Rate limiting utilities & protection
├── cache_client.py           # Redis/Valkey cache client ⭐ NEW
├── api_auth.py               # API key management & authentication ⭐ NEW
├── auth.py                   # User authentication system ⭐ NEW
├── email_service.py          # Email notification service ⭐ NEW
├── app.py                    # Main Flask application entry point
├── templates/                # Web interface templates
│   ├── demo.html             # Interactive demo interface
│   ├── api_management.html   # API key management interface ⭐ NEW
│   └── demo_backup.html      # Demo interface backup
├── examples/                 # Usage examples & demonstrations
│   ├── python_api_examples.py    # Python API usage examples
│   └── comment_quality_examples.py  # Comment quality assessment examples
├── tests/                    # Comprehensive test suite & load testing ⭐ ENHANCED
│   ├── __init__.py           # Test package initialization
│   ├── test_core.py          # Core functionality tests
│   ├── test_api.py           # REST API endpoint tests
│   ├── load_test_100_users.py    # 100 concurrent users load test ⭐ NEW
│   ├── test_200_users.py     # 200 concurrent users stress test ⭐ NEW
│   ├── test_500_users.py     # 500 concurrent users extreme test ⭐ NEW
│   ├── cache_hit_test.py     # Cache performance testing ⭐ NEW
│   ├── test_cache.py         # Redis cache connection test ⭐ NEW
│   ├── test_new_cache.py     # New cache endpoint testing ⭐ NEW
│   ├── detailed_stats_test.py    # Performance statistics testing ⭐ NEW
│   ├── stress_test.py        # System stress testing ⭐ NEW
│   ├── sentences.csv         # Test data for text correction
│   ├── sentences_eng.csv     # English test sentences
│   └── sentences_fr.csv      # French test sentences
├── logs/                     # Application logs directory
│   ├── appencorrect.log      # Main application log
│   └── feedback.log          # User feedback log (for model training)
├── appencorrect_optimized.service  # Systemd service (300 workers) ⭐ NEW
├── REDIS_SETUP.md            # Redis/Valkey setup guide ⭐ NEW
├── setup.py                  # Package setup & installation config
├── requirements.txt          # Python dependencies
├── env.example              # Environment variables template (enhanced) ⭐ UPDATED
├── README.md                 # Project documentation (this file)
├── LICENSE                   # MIT License
├── CHANGELOG.md              # Version history & change log
└── .gitignore               # Git ignore rules ⭐ NEW
```

## 🧪 Testing

Run the test suite:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=appencorrect

# Run specific test file
pytest tests/test_core.py
```

Run example scripts:
```bash
# Comment quality examples
python examples/comment_quality_examples.py

# Python API examples
python examples/python_api_examples.py
```

## 🔧 Development

### Setting up for Development

```bash
# Clone and install in development mode
git clone https://github.com/Appen/AppenCorrect.git
cd AppenCorrect
pip install -e .

# Install development dependencies
pip install pytest pytest-cov pytest-flask

# Set up pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Running the Application

```bash
# Development server
python app.py

# Production server (using Waitress) ⭐ OPTIMIZED
pip install waitress
waitress-serve --host=0.0.0.0 --port=5006 --threads=300 --connection-limit=1200 app:app

# High-performance production with systemd service ⭐ NEW
sudo cp appencorrect_optimized.service /etc/systemd/system/appencorrect.service
sudo systemctl daemon-reload
sudo systemctl enable appencorrect
sudo systemctl start appencorrect

# Monitor production service
sudo systemctl status appencorrect
journalctl -u appencorrect -f
```

#### Production Performance Configuration ⭐ *NEW*
- **300 Worker Threads**: Handles 500+ concurrent users
- **1200 Connection Limit**: Optimized for high-traffic scenarios  
- **Redis Caching**: 81.7% hit rate for instant responses
- **Rate Limiting**: API protection with 4,000 RPM limits
- **Auto-restart**: Systemd service with health monitoring

## 📊 Performance

### Redis/Valkey High-Performance Caching ⭐ *NEW*
- **81.7% cache hit rate** in production workloads
- **0.000s response time** for cached requests (instant!)
- **70% reduction** in AI API costs
- **Cross-worker cache sharing** eliminates duplicate AI calls
- **SSL/TLS encryption** for secure ElastiCache connections
- **Automatic TTL management** with configurable expiration

### Production-Scale Concurrency ⭐ *NEW*
- **300 worker threads** (optimized from 150)
- **Handles 500+ concurrent users** with 100% success rate
- **8x faster completion** under extreme load (16s → 2s)
- **No worker queue bottlenecks** under high traffic
- **Rate limiting protection** prevents system overload

### Load Testing & Benchmarking ⭐ *NEW*
```bash
# Test different concurrency levels
python3 load_test_100_users.py    # 100 concurrent users, 500 requests
python3 test_200_users.py         # 200 concurrent users, 400 requests  
python3 test_500_users.py         # 500 concurrent users, 1000 requests

# Cache hit rate testing
python3 cache_hit_test.py          # Demonstrates 81.7% hit rate

# Performance results:
# - 100 users: 45.7 req/sec, 1.56s avg response
# - 200 users: 49.7 req/sec, 3.03s avg response  
# - 500 users: 61.9 req/sec, 0.95s avg response (with rate limiting)
```

### Cache Performance Testing ⭐ *NEW*
```bash
# Check current cache status
curl -X GET https://appencorrect.xlostxcoz.com/api/cache/status \
  -H "X-API-Key: your_api_key"

# Disable cache for baseline testing
curl -X POST https://appencorrect.xlostxcoz.com/api/cache/toggle \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"enabled": false}'

# Run your load tests without cache
python3 test_500_users.py

# Re-enable cache and test again
curl -X POST https://appencorrect.xlostxcoz.com/api/cache/toggle \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"enabled": true}'

# Run same test with cache enabled
python3 test_500_users.py

# Performance comparison example:
# Without cache: 0.607s response time
# With cache: 0.005s response time (121x faster!)
```

### Traditional Caching
- Smart caching reduces API calls by up to 70%
- Cache can be disabled for testing: `api.disable_cache()`
- Cache statistics available via `api.get_cache_status()`

### Rate Limiting
- Built-in rate limiting for Gemini API (4,000 RPM)
- Automatic retry with exponential backoff
- Configurable limits and timeouts
- HTTP 429 protection under extreme load

### Language Detection
- Multiple detector options: `lingua`, `langdetect`, or `disabled`
- Automatic fallback between detectors
- Language-specific optimization rules

## 🤝 Contributing

1. Fork the repository on [GitHub](https://github.com/Appen/AppenCorrect/fork)
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run tests: `pytest`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request on [GitHub](https://github.com/Appen/AppenCorrect/pulls)

## 📜 License

This project is proprietary software owned by Appen Limited. See the [LICENSE](LICENSE) file for details.

**⚠️ CONFIDENTIAL:** This software is for internal Appen use only and contains proprietary algorithms and methodologies.

## 🆘 Support

- **Documentation**: See examples in the `examples/` directory
- **Issues**: Create an issue on [GitHub](https://github.com/Appen/AppenCorrect/issues)
- **API Key**: Get your Gemini API key from [Google AI Studio](https://aistudio.google.com/)

## 🆕 Recent Updates

### Version 3.0.0 - Production-Scale Performance & Enterprise Features ⭐ *LATEST*

**🚀 High-Performance Caching & Concurrency:**
- **Redis/Valkey Integration**: 81.7% cache hit rate with 0.000s response times
- **300 Worker Threads**: Increased from 150, eliminates queue bottlenecks  
- **500+ Concurrent Users**: Handles extreme load with 100% success rate
- **8x Performance Improvement**: 16s → 2s completion under high load
- **SSL/TLS Support**: Secure ElastiCache connections with certificate validation

**🔐 Enterprise Management Suite:**
- **API Key Management**: Full lifecycle with rate limiting and usage tracking
- **Real-time Log Viewer**: Live system monitoring with search and filtering
- **Cost Analytics**: AI API usage monitoring and optimization insights
- **User Feedback System**: Integrated collection and analysis dashboard
- **Custom Instructions**: Configurable AI behavior for specific use cases
- **Appen Authentication**: Secure access control for management interfaces

**📊 Comprehensive Load Testing:**
- **Multi-tier Testing**: 100, 200, and 500 concurrent user test suites
- **Cache Performance Testing**: Hit rate analysis and optimization tools
- **Stress Testing**: System limit identification and bottleneck analysis
- **Production Benchmarks**: Real-world performance metrics and monitoring

**⚡ System Optimizations:**
- **Systemd Service**: Production deployment with auto-restart and monitoring
- **Rate Limiting**: 4,000 RPM API protection with HTTP 429 responses
- **Connection Pooling**: Optimized database and cache connections
- **Memory Efficiency**: <320MB usage under 500+ concurrent users

### Version 2.4.0 - Context-Aware Corrections & UI Improvements

**🧠 Smart Homophone Detection:**
- Added context-aware correction logic for there/their/they're, your/you're, its/it's
- Intelligent pattern matching prevents incorrect homophone corrections  
- Selective correction targeting only improper usage instances

**🎯 Frontend Precision Improvements:**
- Fixed highlighting alignment issues that caused rightward drift
- Implemented position-based correction replacement for exact accuracy
- Enhanced "Fix All" functionality with proper position sorting
- Added prevention of duplicate processing after corrections

## 🔄 Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## 👥 Authors

- **Appen Automation Solutions Team**
- **Contributors**: See GitHub contributors

---

<div align="center">

**🎯 AppenCorrect - Elevating Text Quality with AI-Powered Analysis**

</div> 