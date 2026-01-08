# Atom Platform - End-to-End Test Framework

## Overview

A comprehensive end-to-end testing framework for the Atom Platform that validates all features from frontend to backend, verifies marketing claims using LLM assessment, and ensures production readiness.

## Key Features

- 🔍 **End-to-End Testing**: Tests all features from Next.js frontend to FastAPI backend
- 🤖 **LLM Verification**: Independently validates marketing claims using OpenAI GPT-4
- 🔐 **Credential Validation**: Automatically checks for required API keys and credentials
- 📊 **Comprehensive Reporting**: Generates detailed test reports with marketing claim verification
- 🎯 **Marketing Claim Validation**: Verifies 8 core marketing claims against actual test results
- 🔄 **Cross-Platform Testing**: Tests 33+ service integrations across communication, productivity, and business tools

## Test Categories

### Core Functionality
- Natural language workflow creation
- Conversational automation
- AI memory and context management
- Service registry and integration discovery

### Communication Services
- Slack integration
- Discord integration
- Email (Gmail/Outlook) integration
- Microsoft Teams integration
- Cross-platform messaging coordination

### Productivity Services
- Asana integration
- Notion integration
- Linear integration
- Trello integration
- Monday.com integration
- Cross-platform task coordination

### Voice Integration
- Text-to-speech capabilities
- Speech-to-text conversion
- Voice command processing
- Wake word detection
- Voice-triggered workflows

## Quick Start

### Prerequisites

1. **Clone the repository**:
   ```bash
   git clone https://github.com/rush86999/atom.git
   cd atom
   ```

2. **Install dependencies**:
   ```bash
   cd e2e-tests
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   Copy the template file and configure your credentials:
   ```bash
   cp config/.env.template .env
   # Edit .env with your API keys and credentials
   ```

### Running Tests

#### 1. Validate Environment
```bash
python run_tests.py --validate-only
```

#### 2. List Available Test Categories
```bash
python run_tests.py --list-categories
```

#### 3. Run All Tests
```bash
python run_tests.py
```

#### 4. Run Specific Categories
```bash
python run_tests.py core communication
```

#### 5. Run with Custom Report
```bash
python run_tests.py --report-file my_report.json
```

#### 6. Skip LLM Verification
```bash
python run_tests.py --skip-llm
```

## Required Credentials

### Core Testing
- `OPENAI_API_KEY`: For LLM-based marketing claim verification

### Communication Services
- `SLACK_BOT_TOKEN`: Slack workspace integration
- `DISCORD_BOT_TOKEN`: Discord server integration
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`: Gmail integration
- `OUTLOOK_CLIENT_ID`, `OUTLOOK_CLIENT_SECRET`: Outlook integration

### Productivity Services
- `ASANA_ACCESS_TOKEN`: Asana workspace integration
- `NOTION_API_KEY`: Notion workspace integration
- `LINEAR_API_KEY`: Linear workspace integration
- `TRELLO_API_KEY`: Trello board integration
- `MONDAY_API_KEY`: Monday.com workspace integration

### Voice Integration
- `ELEVENLABS_API_KEY`: Text-to-speech capabilities

## Marketing Claims Verified

The framework automatically verifies these 8 core marketing claims:

1. **Natural Language Workflow**: "Just describe what you want to automate and Atom builds complete workflows"
2. **Cross-Platform Coordination**: "Works across all your tools seamlessly"
3. **Conversational Automation**: "Automates complex workflows through natural language chat"
4. **AI Memory**: "Remembers conversation history and context"
5. **Voice Integration**: "Seamless voice-to-action capabilities"
6. **Production Ready**: "Production-ready architecture with FastAPI backend and Next.js frontend"
7. **Service Integrations**: "33+ service integrations available"
8. **BYOK Support**: "Complete BYOK (Bring Your Own Key) system"

## Test Architecture

### Directory Structure
```
e2e-tests/
├── config/
│   └── test_config.py          # Test configuration and credential validation
├── tests/
│   ├── test_core.py            # Core functionality tests
│   ├── test_communication.py   # Communication services tests
│   ├── test_productivity.py    # Productivity services tests
│   ├── test_voice.py           # Voice integration tests
│   └── ...                     # Additional test modules
├── utils/
│   └── llm_verifier.py         # LLM-based marketing claim verification
├── test_runner.py              # Main test runner
├── run_tests.py                # CLI entry point
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

### Test Flow

1. **Credential Validation**: Checks for required API keys and credentials
2. **Service Connectivity**: Verifies backend and frontend accessibility
3. **Feature Testing**: Executes end-to-end tests for each feature
4. **LLM Verification**: Independently assesses test outputs against marketing claims
5. **Report Generation**: Creates comprehensive test reports with verification results

## Test Reports

The framework generates detailed JSON reports including:

- Overall test status and duration
- Test category results with pass/fail counts
- Marketing claim verification with confidence scores
- Service connectivity status
- Error details and debugging information

Example report structure:
```json
{
  "overall_status": "PASSED",
  "duration_seconds": 245.67,
  "total_tests": 25,
  "tests_passed": 24,
  "tests_failed": 1,
  "marketing_claims_verified": {
    "total": 8,
    "verified": 7,
    "verification_rate": 0.875
  },
  "category_results": {
    "core": {
      "tests_run": 5,
      "tests_passed": 5,
      "tests_failed": 0,
      "marketing_claims_verified": {
        "natural_language_workflow": {
          "verified": true,
          "confidence": 0.92,
          "reason": "Test demonstrated workflow creation through natural language commands"
        }
      }
    }
  }
}
```

## Development

### Adding New Test Categories

1. Create a new test module in `tests/` directory
2. Implement the `run_tests()` function
3. Add required credentials to `TestConfig.REQUIRED_CREDENTIALS`
4. Map marketing claims in `TestRunner._verify_category_claims()`

### Example Test Module Structure
```python
def run_tests(config: TestConfig) -> Dict[str, Any]:
    results = {
        "tests_run": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "test_details": {},
        "test_outputs": {},
    }
    
    # Add individual test functions
    results.update(_test_feature_one(config))
    results.update(_test_feature_two(config))
    
    return results
```

### Custom Test Scenarios

Use the LLM verifier to generate test scenarios:
```python
from utils.llm_verifier import LLMVerifier

verifier = LLMVerifier()
scenario = verifier.generate_test_scenario(
    feature="natural_language_workflow",
    marketing_claims=["Just describe what you want to automate"]
)
```

## Troubleshooting

### Common Issues

1. **Missing Credentials**: Use `--list-categories` to see missing credentials
2. **Service Connectivity**: Ensure backend and frontend services are running
3. **LLM Verification Failures**: Check OpenAI API key and quota
4. **Timeout Errors**: Increase timeout values in test configuration

### Debug Mode

Run with verbose output for detailed debugging:
```bash
python run_tests.py --verbose
```

## Continuous Integration

The framework is designed for CI/CD integration:

```yaml
# Example GitHub Actions workflow
name: E2E Tests
on: [push, pull_request]
jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd e2e-tests
          pip install -r requirements.txt
      - name: Run E2E tests
        run: |
          cd e2e-tests
          python run_tests.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          # ... other credentials
```

## Contributing

1. Follow the existing test structure and patterns
2. Include comprehensive test outputs for LLM verification
3. Add proper credential validation for new services
4. Update the README with new test categories and requirements

## License

This E2E test framework is part of the Atom Platform and follows the same AGPL license.

## Support

For issues and questions:
- Create an issue in the main repository
- Check the existing test documentation
- Review the test reports for detailed error information