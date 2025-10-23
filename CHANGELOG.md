# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2024-12-19

### Added
- **Comment Quality Assessment**: New AI-powered feature to assess comment quality for rating tasks
  - Quality scoring (1-10) with detailed explanations
  - Multi-factor analysis: technical quality, content quality, length appropriateness, task suitability
  - Length requirements for rating tasks (100/300 character thresholds)
  - Improvement suggestions and strengths identification
- **Enhanced Python API**: Extended PythonAPI class with comment quality methods
- **REST API Endpoints**: New `/assess/quality` endpoint for comment quality assessment
- **Comprehensive Documentation**: Extensive examples and usage guides
- **Rate Limiting**: Built-in rate limiting for Gemini API protection
- **Smart Caching**: Response caching to improve performance and reduce API costs
- **Multi-Language Support**: Enhanced language detection with multiple detector options
- **Error Handling**: Comprehensive error management and logging
- **Statistics Tracking**: Usage analytics and performance metrics

### Changed
- **AI-First Approach**: Primary processing now uses Google Gemini AI
- **Core Architecture**: Refactored for better modularity and extensibility
- **API Interface**: Standardized response formats across all endpoints
- **Documentation**: Complete rewrite with comprehensive examples and guides

### Technical Details
- Python 3.8+ support
- Google Gemini 2.5 Flash Lite integration
- Flask web framework
- Comprehensive test suite with pytest
- Proprietary Appen License

## [1.0.0] - Initial Release
- Basic text correction functionality
- Simple API structure
- Limited language support 