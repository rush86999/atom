# Testing at Atom - Quick Start Guide

**Time to complete:** 15 minutes (setup) + 15 minutes (first test)
**Last Updated:** March 7, 2026
**Milestone:** v5.2 Complete Codebase Coverage

This guide gets you running tests and writing your first test across all platforms at Atom. By the end, you'll have verified your test setup and written your first test.

## Prerequisites

Before starting, ensure you have:

- **Cloned the repo:**
  ```bash
  git clone https://github.com/rush86999/atom.git
  cd atom
  ```

- **Installed dependencies:** See [INSTALLATION.md](../INSTALLATION.md) for platform-specific setup instructions

---

## Step 1: Verify Test Setup (5 min)

Choose your platform below and run the verification command. This confirms your environment is ready for testing.

### Backend (Python/FastAPI)

```bash
cd backend
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_monitoring.py::TestSmokeTestMetrics -v
# Expected: 4 tests pass in <5 seconds
```

**What you should see:**
```
test_smoke_test_metrics_are_defined PASSED
test_track_smoke_test_success PASSED
test_track_smoke_test_failure PASSED
test_track_smoke_test_passed PASSED
```

### Frontend (Next.js/React)

```bash
cd frontend-nextjs
npm test -- --listTests
# Expected: Lists 500+ test files
```

**What you should see:**
```
Lists 500+ test files including:
  - components/canvas/__tests__/*.test.tsx
  - src/__tests__/*.test.ts
  - tests/property/__tests__/*.test.ts
```

### Mobile (React Native)

```bash
cd mobile
npm test -- --listTests
# Expected: Lists 100+ test files
```

**What you should see:**
```
Lists 100+ test files including:
  - src/__tests__/contexts/*.test.tsx
  - src/__tests__/hooks/*.test.ts
  - src/__tests__/services/*.test.ts
```

### Desktop (Tauri/Rust)

```bash
cd frontend-nextjs/src-tauri
cargo test --no-run
# Expected: Compiles 83 tests
```

**What you should see:**
```
Compiling...
Finished dev [unoptimized + debuginfo] target(s) in XX.XXs
```

---

## Step 2: Run Your First Test (5 min)

Now that your setup is verified, run an existing test to see the testing framework in action.

### Backend: Run a governance test

```bash
cd backend
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/unit/episodes/test_episode_segmentation_service.py::TestEpisodeSegmentationService::test_get_agent_maturity -v
# Expected: 1 test passes
```

**What you should see:**
```
tests/unit/episodes/test_episode_segmentation_service.py::TestEpisodeSegmentationService::test_get_agent_maturity PASSED
```

### Frontend: Run a canvas component test

```bash
cd frontend-nextjs
npm test -- components/canvas/__tests__/bar-chart.test.tsx
# Expected: Test suite runs and shows results
```

### Mobile: Run an auth context test

```bash
cd mobile
npm test -- src/__tests__/contexts/AuthContext.test.tsx
# Expected: Test suite runs and shows results
```

### Desktop: Run a platform-specific test

```bash
cd frontend-nextjs/src-tauri
cargo test test_platform_helpers
# Expected: Test runs and shows results
```

---

## Step 3: Write Your First Test (15 min)

This tutorial walks you through writing a backend test. The same concepts apply to other platforms (see platform-specific guides in Next Steps).

### Create a test file

```bash
cd backend/tests
touch test_my_first_test.py
```

### Write the test

Open `test_my_first_test.py` and add:

```python
"""
My first test at Atom.

This test demonstrates the basics of pytest testing:
1. Test function naming (test_*)
2. Using fixtures for test data
3. Assertions to verify behavior
"""

import pytest
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, MaturityLevel


def test_create_agent_returns_id():
    """Verify that creating an agent returns an agent ID."""
    # Create a test agent
    agent = AgentRegistry(
        id="test-agent-001",
        name="Test Agent",
        maturity=MaturityLevel.STUDENT,
        description="A test agent for onboarding"
    )

    # Verify the agent was created with an ID
    assert agent.id is not None
    assert agent.id == "test-agent-001"
    assert agent.name == "Test Agent"
    assert agent.maturity == MaturityLevel.STUDENT


def test_agent_maturity_levels():
    """Verify that agents have different maturity levels."""
    levels = [
        MaturityLevel.STUDENT,
        MaturityLevel.INTERN,
        MaturityLevel.SUPERVISED,
        MaturityLevel.AUTONOMOUS
    ]

    # Verify all maturity levels exist
    assert len(levels) == 4
    assert MaturityLevel.STUDENT in levels
    assert MaturityLevel.AUTONOMOUS in levels
```

### Run your test

```bash
cd backend
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_my_first_test.py -v
# Expected: 2 tests pass
```

**What you should see:**
```
tests/test_my_first_test.py::test_create_agent_returns_id PASSED
tests/test_my_first_test.py::test_agent_maturity_levels PASSED
```

**Congratulations!** You've written your first test at Atom.

---

## Troubleshooting

### "Module not found" error

**Problem:** Python can't find the `core` module.

**Solution:** Ensure you're in the correct directory and set PYTHONPATH:
```bash
cd backend
export PYTHONPATH=/Users/rushiparikh/projects/atom/backend
pytest tests/test_my_first_test.py -v
```

### "Permission denied" error

**Problem:** Can't execute `python` command.

**Solution:** Try using `python3` instead:
```bash
python3 -m pytest tests/test_my_first_test.py -v
```

### "cargo test fails" error

**Problem:** Rust toolchain not installed.

**Solution:** Verify Rust installation:
```bash
rustc --version
cargo --version
```

If not installed, see [INSTALLATION.md](../INSTALLATION.md) for Rust setup instructions.

### "Jest fails to run" error

**Problem:** Node modules not installed.

**Solution:** Install dependencies:
```bash
cd frontend-nextjs  # or mobile
npm install
```

### Tests timeout or hang

**Problem:** Tests taking too long or stuck.

**Solution:** Run a smaller subset first:
```bash
# Backend: Run single test file
pytest tests/test_my_first_test.py -v

# Frontend/Mobile: Run specific test file
npm test -- test_my_first_test.test.ts

# Desktop: Run specific test
cargo test test_name
```

---

## Next Steps

You've successfully run your first test and written your own test. Continue your learning journey:

### Platform-Specific Guides

- **Backend Testing Guide** → [backend/tests/docs/COVERAGE_GUIDE.md](TESTING_INDEX.md)
  - pytest patterns, fixtures, coverage measurement
  - Target: 70%+ coverage

- **Frontend Testing Guide** → [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) *(coming soon in Phase 152)*
  - Jest, React Testing Library, MSW, jest-axe
  - Target: 80%+ coverage

- **Mobile Testing Guide** → [MOBILE_TESTING_GUIDE.md](MOBILE_TESTING_GUIDE.md) *(coming soon in Phase 152)*
  - jest-expo, React Native Testing Library
  - Target: 50%+ coverage

- **Desktop Testing Guide** → [DESKTOP_TESTING_GUIDE.md](DESKTOP_TESTING_GUIDE.md) *(coming soon in Phase 152)*
  - cargo test, proptest, tarpaulin
  - Target: 40%+ coverage

### Advanced Testing Techniques

- **Property Testing** → [PROPERTY_TESTING_PATTERNS.md](PROPERTY_TESTING_PATTERNS.md)
  - FastCheck (frontend/mobile/desktop)
  - Hypothesis (backend)
  - Test invariants instead of specific examples

- **E2E Testing** → [E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md)
  - Playwright (web)
  - API-level tests (mobile)
  - Tauri integration (desktop)

- **Cross-Platform Coverage** → [CROSS_PLATFORM_COVERAGE.md](CROSS_PLATFORM_COVERAGE.md)
  - Weighted coverage calculation
  - Platform-specific thresholds
  - Quality gates

### Testing Quality & Reliability

- **Flaky Test Detection** → [backend/tests/docs/FLAKY_TEST_QUARANTINE.md](TESTING_INDEX.md)
  - Multi-run flaky detection (10 runs, 30% threshold)
  - SQLite quarantine tracking
  - Auto-removal policies

- **Parallel Execution** → [backend/tests/docs/PARALLEL_EXECUTION_GUIDE.md](E2E_TESTING_GUIDE.md)
  - Matrix strategy (4 platforms in parallel)
  - Target: <15 min total execution time

- **Test Isolation** → [backend/tests/docs/TEST_ISOLATION_PATTERNS.md](TESTING_INDEX.md)
  - Independent tests (no shared state)
  - Fixture patterns
  - Resource conflict prevention

### Full Documentation Index

- **Testing Documentation Index** → [TESTING_INDEX.md](TESTING_INDEX.md)
  - Central hub for all testing documentation
  - Use case navigation
  - Quick reference tables

---

## Quick Reference

### Test Execution Commands

| Platform | Command | Time |
|----------|---------|------|
| Backend | `pytest tests/ -v -n auto` | ~8-10 min |
| Frontend | `npm test -- --watchAll=false` | ~3-5 min |
| Mobile | `npm test -- --watchAll=false` | ~2-3 min |
| Desktop | `cargo test` | ~3-4 min |

### Coverage Commands

| Platform | Command | Output |
|----------|---------|--------|
| Backend | `pytest --cov=core --cov=api --cov-report=json` | coverage.json |
| Frontend | `npm test -- --coverage` | coverage/coverage-final.json |
| Mobile | `npm test -- --coverage` | coverage/coverage-final.json |
| Desktop | `cargo tarpaulin --out Json` | coverage/tarpaulin-report.json |

---

## Need Help?

- **Testing questions:** Ask in Slack #testing channel
- **Documentation issues:** Open a docs issue on GitHub
- **Onboarding sessions:** Join weekly "Testing at Atom" office hours
- **Quick lookup:** Check [TESTING_INDEX.md](TESTING_INDEX.md) for full documentation

**Happy testing!** 🧪
