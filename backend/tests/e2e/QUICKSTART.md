# E2E Testing Quick Start Guide

## Overview

This guide provides step-by-step instructions for running the end-to-end tests for Atom's high-impact features.

## Prerequisites

### 1. Install Dependencies

```bash
cd /Users/rushiparikh/projects/atom/backend

# Install pytest and plugins
pip install pytest pytest-asyncio pytest-cov pytest-benchmark pytest-xdist

# Install test dependencies
pip install httpx playwright freezegun

# Install Playwright browsers (for Scenario 5)
playwright install chromium
```

### 2. Configure Environment

```bash
# Required for LLM streaming tests (Scenario 2)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional: Other providers
export DEEPSEEK_API_KEY="sk-..."
export GEMINI_API_KEY="..."

# Feature flags (automatically set by conftest.py)
export ATOM_ENVIRONMENT=test
export ATOM_DATABASE_URL="sqlite:///:memory:"
```

## Running Tests

### Run All E2E Scenarios

```bash
cd /Users/rushiparikh/projects/atom/backend
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/e2e/ -v -m e2e
```

### Run Individual Scenario

```bash
# Scenario 1: Agent Governance
pytest tests/e2e/test_scenario_01_governance.py -v -s

# Scenario 2: LLM Streaming
pytest tests/e2e/test_scenario_02_streaming.py -v -s

# Scenario 3: Canvas Presentations
pytest tests/e2e/test_scenario_03_canvas.py -v -s

# And so on...
```

### Run with Coverage

```bash
pytest tests/e2e/ -v -m e2e --cov=core --cov-report=html
open htmlcov/index.html
```

### Run in Parallel (Faster)

```bash
pytest tests/e2e/ -v -m e2e -n auto
```

### Generate HTML Report

```bash
pytest tests/e2e/ -v -m e2e --html=e2e_report.html --self-contained-html
open e2e_report.html
```

## Test Scenarios

| # | Scenario | Description | Duration |
|---|----------|-------------|----------|
| 1 | Governance | Agent maturity-based routing | ~5s |
| 2 | Streaming | Multi-provider LLM streaming | ~30s* |
| 3 | Canvas | Canvas presentations & forms | ~5s |
| 4 | Guidance | Real-time agent guidance | ~5s |
| 5 | Browser | Browser automation | ~10s* |
| 6 | Episodes | Episodic memory & retrieval | ~5s |
| 7 | Graduation | Agent graduation framework | ~5s |
| 8 | Training | Student agent training | ~5s |
| 9 | Device | Device capabilities & permissions | ~5s |
| 10 | Deeplinks/Feedback | Deep linking & feedback | ~5s |

*Requires real API keys or Playwright installation

## Expected Results

All tests should pass with output similar to:

```
tests/e2e/test_scenario_01_governance.py::test_agent_governance_maturity_routing PASSED
tests/e2e/test_scenario_02_streaming.py::test_multi_provider_llm_streaming PASSED
tests/e2e/test_scenario_03_canvas.py::test_canvas_presentations_with_governance PASSED
tests/e2e/test_scenario_04_guidance.py::test_real_time_agent_guidance PASSED
tests/e2e/test_scenario_05_browser.py::test_browser_automation_with_playwright PASSED
tests/e2e/test_scenario_06_episodes.py::test_episodic_memory_and_retrieval PASSED
tests/e2e/test_scenario_07_graduation.py::test_agent_graduation_framework PASSED
tests/e2e/test_scenario_08_training.py::test_student_agent_training_system PASSED
tests/e2e/test_scenario_09_device.py::test_device_capabilities_and_permissions PASSED
tests/e2e/test_scenario_10_deeplinks_feedback.py::test_deeplinking_and_enhanced_feedback PASSED

=== 10 passed in 45.23s ===
```

## Troubleshooting

### "No module named 'pytest'"
```bash
pip install pytest pytest-asyncio
```

### "Playwright not installed"
```bash
playwright install chromium
```

### "API key required"
Either provide real API keys or skip tests that require them:
```bash
pytest tests/e2e/ -v -m e2e -m "not requires_api_keys"
```

### Tests timeout
Increase timeout or run individually:
```bash
pytest tests/e2e/test_scenario_02_streaming.py -v -s --timeout=120
```

## Next Steps

1. **Review Results**: Check the HTML report for detailed results
2. **Check Coverage**: Open `htmlcov/index.html` to see coverage report
3. **Debug Failures**: Use `-v -s` flags for verbose output
4. **Extend Tests**: Add new scenarios following the existing pattern

## Additional Resources

- [README.md](./README.md) - Comprehensive E2E testing documentation
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - Contribution guidelines
- [CLAUDE.md](../../CLAUDE.md) - Project architecture and context
