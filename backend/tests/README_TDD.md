# Atom Test Directory Structure

Organized test infrastructure for comprehensive coverage.

## Directory Layout

```
backend/tests/
├── standalone/              # Standalone TDD test suites (no pytest dependencies)
│   ├── test_trigger_standalone.py              (86.93% coverage)
│   ├── test_agent_governance_standalone.py     (63.11% coverage)
│   ├── test_byok_handler_standalone.py         (27.83% coverage)
│   └── test_episode_segmentation_standalone.py (11.30% coverage)
│
├── scripts/                 # Test runner scripts
│   ├── run_trigger_test.py
│   └── ...
│
├── unit/                    # Unit tests (pytest-based)
│   └── core/
│
├── integration/             # Integration tests
├── coverage_reports/        # Coverage reports and analysis
│   ├── BUG_FIXES_SUMMARY.md
│   ├── TDD_BUG_DISCOVERY_REPORT_PHASE1.md
│   ├── TDD_PROGRESS_REPORT_PHASE2.md
│   └── ...
│
└── conftest.py              # Pytest configuration
```

## Running Tests

### Standalone Tests (Recommended for TDD)
Fast, isolated tests with coverage measurement:

```bash
# Run standalone test suite
cd backend
python3 tests/standalone/test_trigger_standalone.py

# With coverage
python3 -m coverage run --source=core.trigger_interceptor tests/standalone/test_trigger_standalone.py
python3 -m coverage report --show-missing
```

### Pytest Tests
For integration and unit tests:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=core --cov-report=html

# Run specific test type
pytest tests/unit/core/ -v
pytest tests/integration/ -v
```

## Test Coverage Goals

| Priority | Module | Target | Status |
|----------|--------|--------|--------|
| P0 | trigger_interceptor.py | 80% | ✅ 86.93% |
| P0 | agent_governance_service.py | 80% | 🟡 63.11% |
| P0 | llm/byok_handler.py | 80% | 🟡 27.83% |
| P0 | episode_segmentation_service.py | 80% | 🟡 11.30% |
| P1 | browser_tool.py | 80% | ⏳ 12.71% |
| P1 | device_tool.py | 80% | ⏳ 12.86% |

**Overall Target:** 80% coverage across all modules

## Bug Discovery

TDD approach has discovered **6 critical bugs**:

1. ✅ Missing UserActivity models
2. ✅ Missing Queue models
3. ✅ SaaS Tier dependency (fixed for open-source)
4. ✅ Missing TenantIntegrationConfig
5. ✅ Budget service missing tenant_id
6. ✅ AgentFeedback workspace_id field

See `coverage_reports/BUG_FIXES_SUMMARY.md` for details.

## Adding New Tests

1. **For new modules:** Create standalone test file in `tests/standalone/`
2. **For bug fixes:** Add tests to existing standalone file
3. **For integration:** Use pytest in `tests/integration/`

### Standalone Test Template

```python
#!/usr/bin/env python3
"""
Standalone Tests for [Module Name]

Coverage Target: 80%+
Priority: P0/P1/P2
"""
import sys
import os
sys.path.insert(0, '.')
os.environ['ENVIRONMENT'] = 'development'

from core.[module] import [ClassName]
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


def test_basic_functionality():
    """Test basic functionality"""
    print("Testing basic functionality...")
    # Your test here
    assert True
    print("✓ Basic functionality tests passed")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Running [Module] Tests (Standalone)")
    print("=" * 60)
    
    try:
        test_basic_functionality()
        # Add more tests...
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

## Coverage Measurement

```bash
# Single module
python3 -m coverage run --source=core.[module] tests/standalone/test_[module]_standalone.py
python3 -m coverage report --show-missing

# Multiple modules
python3 -m coverage run --source=core. \
  tests/standalone/test_trigger_standalone.py \
  tests/standalone/test_agent_governance_standalone.py
python3 -m coverage report --show-missing
```

## Documentation

- `BUG_FIXES_SUMMARY.md` - All bugs discovered and fixed
- `TDD_BUG_DISCOVERY_REPORT_PHASE1.md` - Phase 1 discovery report
- `TDD_PROGRESS_REPORT_PHASE2.md` - Phase 2 progress tracking

---

**Last Updated:** 2026-04-02  
**Test Count:** 71 tests across 4 modules  
**Average Coverage:** 47.29% (weighted)
