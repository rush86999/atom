# End-to-End Testing Scenarios for Atom

Comprehensive E2E tests validating Atom's high-impact features from an end-user perspective.

## Overview

This directory contains 10 comprehensive end-to-end testing scenarios that validate Atom's high-impact features. Each scenario is independent, uses in-memory SQLite for fast execution, and supports real API keys for LLM providers.

**Testing Approach:**
- **Independent Scenarios**: Each test is self-contained with its own setup/teardown
- **Database**: In-memory SQLite for fast execution
- **LLM Integration**: Real API calls (OpenAI/Anthropic) with environment variable configuration
- **Coverage**: All 10 high-impact features

## Test Scenarios

| Scenario | File | Feature Coverage |
|----------|------|------------------|
| 1 | `test_scenario_01_governance.py` | Agent Governance & Maturity-Based Routing |
| 2 | `test_scenario_02_streaming.py` | Multi-Provider LLM Streaming |
| 3 | `test_scenario_03_canvas.py` | Canvas Presentations with Governance |
| 4 | `test_scenario_04_guidance.py` | Real-Time Agent Guidance System |
| 5 | `test_scenario_05_browser.py` | Browser Automation with Playwright |
| 6 | `test_scenario_06_episodes.py` | Episodic Memory & Retrieval |
| 7 | `test_scenario_07_graduation.py` | Agent Graduation Framework |
| 8 | `test_scenario_08_training.py` | Student Agent Training System |
| 9 | `test_scenario_09_device.py` | Device Capabilities & Permissions |
| 10 | `test_scenario_10_deeplinks_feedback.py` | Deep Linking & Enhanced Feedback |

## Quick Start

### Prerequisites

```bash
# Install dependencies
cd /Users/rushiparikh/projects/atom/backend
pip install -e .

# Install Playwright for browser automation tests
playwright install chromium
```

### Environment Configuration

```bash
# Required for LLM streaming tests (Scenario 2)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional: Other providers
export DEEPSEEK_API_KEY="sk-..."
export GEMINI_API_KEY="..."

# Feature flags (set by conftest.py automatically)
export STREAMING_GOVERNANCE_ENABLED=true
export CANVAS_GOVERNANCE_ENABLED=true
export BROWSER_AUTOMATION_ENABLED=true
export EPISODIC_MEMORY_ENABLED=true
```

### Running Tests

```bash
# Run all E2E scenarios
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/e2e/ -v -m e2e

# Run specific scenario
pytest tests/e2e/test_scenario_01_governance.py -v -s

# Run with coverage
pytest tests/e2e/ -v -m e2e --cov=core --cov-report=html

# Run in parallel (faster)
pytest tests/e2e/ -v -m e2e -n auto

# Generate HTML report
pytest tests/e2e/ -v -m e2e --html=e2e_report.html --self-contained-html

# Skip slow tests
pytest tests/e2e/ -v -m e2e -m "not slow"
```

## Test Structure

Each scenario follows this structure:

```python
import pytest
from typing import Dict, Any

@pytest.mark.e2e
def test_specific_scenario(
    db_session,           # Database session
    test_client,          # FastAPI test client
    test_agents,          # All maturity levels
    auth_headers,         # Authentication headers
    performance_monitor,  # Performance tracking
):
    # 1. Setup: Create test data
    # 2. Execution: Run end-to-end workflow
    # 3. Assertions: Verify expected outcomes
    # 4. Teardown: Automatic via fixtures
    pass
```

## Fixtures

### Database Fixtures
- `db_session` - In-memory SQLite session with auto-rollback
- `db_engine` - SQLAlchemy engine

### Client Fixtures
- `test_client` - FastAPI TestClient for HTTP requests
- `async_client` - Async HTTP client for async operations
- `websocket_client` - WebSocket connection manager

### Authentication Fixtures
- `test_user_token` - JWT token for test user
- `auth_headers` - Pre-configured auth headers

### Agent Fixtures
- `student_agent` - STUDENT maturity level agent
- `intern_agent` - INTERN maturity level agent
- `supervised_agent` - SUPERVISED maturity level agent
- `autonomous_agent` - AUTONOMOUS maturity level agent
- `test_agents` - Dictionary of all agents by maturity level

### Service Fixtures
- `governance_cache` - Fresh cache instance for each test
- `governance_service` - AgentGovernanceService instance

### Performance Fixtures
- `performance_monitor` - Track and assert performance metrics

### Test Data Fixtures
- `sample_chart_data` - Chart data for canvas presentations
- `sample_form_data` - Form data for canvas presentations
- `sample_episode_data` - Episode data for episodic memory

## Performance Targets

| Metric | Target | Scenario |
|--------|--------|----------|
| Cached governance check | <1ms | 1, 7, 8 |
| Agent resolution | <50ms | 1 |
| Streaming overhead | <50ms | 2 |
| Episode creation | <5s | 6, 7 |
| Temporal retrieval | <10ms | 6 |
| Semantic retrieval | <100ms | 6 |
| Browser session creation | <5s | 5 |

## Debugging

### Verbose Output
```bash
pytest tests/e2e/test_scenario_01_governance.py -v -s
```

### Post-Mortem Debugging
```bash
pytest tests/e2e/test_scenario_01_governance.py -v -s --pdb
```

### Database Inspection
```python
def test_example(db_session):
    from core.models import AgentRegistry

    # Inspect database state
    agents = db_session.query(AgentRegistry).all()
    print(f"Total agents: {len(agents)}")
```

### API Response Inspection
```python
def test_example(test_client, auth_headers):
    response = test_client.get("/api/agents", headers=auth_headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
```

## Coverage Goals

- **Target**: >80% coverage for tested modules
- **Critical**: All API endpoints covered
- **Error Handling**: All error paths tested
- **Integration**: All service integrations validated

## Continuous Integration

### GitHub Actions Example
```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -e .
          playwright install chromium
      - name: Run E2E tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANHROPOC_API_KEY }}
        run: |
          PYTHONPATH=./backend pytest backend/tests/e2e/ -v -m e2e
```

## Known Limitations

1. **Browser Automation**: Requires Playwright Chromium installation
2. **LLM Streaming**: Requires real API keys (uses test keys if not provided)
3. **Parallel Execution**: Some scenarios may conflict if run in parallel
4. **External Services**: Tests may fail if external services are unavailable

## Troubleshooting

### Issue: "No module named 'core'"
**Solution**: Set PYTHONPATH
```bash
export PYTHONPATH=/Users/rushiparikh/projects/atom/backend
```

### Issue: "Playwright not installed"
**Solution**: Install Playwright browsers
```bash
playwright install chromium
```

### Issue: "API key required"
**Solution**: Set environment variables or skip API tests
```bash
export OPENAI_API_KEY="sk-..."
# Or skip tests requiring API keys
pytest tests/e2e/ -v -m e2e -m "not requires_api_keys"
```

### Issue: Tests timeout
**Solution**: Increase timeout or run individually
```bash
pytest tests/e2e/test_scenario_02_streaming.py -v -s --timeout=60
```

## Contributing

When adding new E2E tests:

1. Create a new `test_scenario_XX_name.py` file
2. Use `@pytest.mark.e2e` decorator
3. Follow the structure: Setup → Execution → Assertions
4. Document the test purpose and flow
5. Add performance assertions where applicable
6. Update this README with the new scenario

## Resources

- **Main Documentation**: `/Users/rushiparikh/projects/atom/CLAUDE.md`
- **API Documentation**: `/Users/rushiparikh/projects/atom/backend/docs/`
- **Service Layer**: `/Users/rushiparikh/projects/atom/backend/core/`
- **API Routes**: `/Users/rushiparikh/projects/atom/backend/api/`

## Support

For issues or questions about E2E testing:
1. Check the scenario docstring for test details
2. Review the fixture definitions in `conftest.py`
3. Inspect the service implementation in `core/`
4. Check API route implementations in `api/`
