# Stack Research: Automated Bug Discovery

**Domain:** Automated Bug Discovery (Fuzzing, Chaos Engineering, Property-Based Testing, Headless Browser Automation)
**Researched:** March 24, 2026
**Confidence:** HIGH

---

## Executive Summary

Atom already has a solid testing foundation with **Hypothesis** (property-based testing), **Atheris** (fuzzing), **Playwright** (E2E), and custom chaos engineering helpers. This research identifies specific library additions needed for comprehensive automated bug discovery targeting **50+ bugs** in the v8.0 milestone.

**Key Finding:** Most infrastructure exists. Primary needs are:
1. **Fuzzing enhancements** (Atheris already present, needs corpus management)
2. **Visual regression testing** (new capability)
3. **Memory leak detection** (new capability)
4. **Network chaos simulation** (enhancement to existing chaos helpers)
5. **Headless browser multi-engine support** (Playwright + Firefox/WebKit)
6. **Performance profiling integration** (pytest-benchmark for baseline establishment)

---

## Recommended Stack Additions

### Core Bug Discovery Libraries

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Atheris** | 2.2.0+ | Coverage-guided fuzzing for Python | Google's fuzzer with libFuzzer integration, already in requirements-testing.txt, best-in-class for finding crashes |
| **Hypothesis** | 6.151.5+ | Property-based testing (already in requirements.txt) | Python's leading PBT framework, generates edge cases automatically |
| **Playwright** | 1.58.0+ | Headless browser automation (already installed) | Multi-browser support (Chromium/Firefox/WebKit), auto-waiting, network interception |
| **Schemathesis** | 3.30.0+ | API contract testing via OpenAPI (already in requirements-testing.txt) | Hypothesis-powered API fuzzing, finds spec violations, integrates with FastAPI |
| **Percy** | 3.0+ | Visual regression testing | CI/CD integrated visual diffs, screenshots comparison, GitHub integration |
| **pytest-benchmark** | 4.0.0+ | Performance benchmarking | Track performance over time, detect regressions, JSON output for CI/CD |
| **memray** | 1.0+ | Memory leak detection (Python 3.11+) | Bloomberg's memory profiler, detects leaks, native extensions support |
| **Toxiproxy-Python** | 2.0+ | Network chaos simulation | Latency/packet loss injection, already in chaos_helpers.py (needs formalization) |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-parallel** | 0.1.0+ | Parallel test execution | Large fuzzing campaigns, multi-core utilization |
| **aiohttp** | 3.8.0+ | Async HTTP client for chaos testing | Simulating concurrent load during chaos scenarios |
| **rich** | 13.0+ | Terminal output formatting | Better fuzzing/chaos test reports (optional UX enhancement) |
| **coverage** | 7.0+ | Code coverage for fuzzing corpus | Measure fuzzing effectiveness, identify uncovered branches |
| **pytest-timeout** | 2.2.0+ | Test timeout enforcement | Prevent infinite loops in fuzz/chaos tests |
| **factory-boy** | 3.3.0+ | Test data factories (already installed) | Generate realistic test data for property-based tests |
| **faker** | 22.7.0+ | Fake data generation (already installed) | Realistic test data for E2E scenarios |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **k6** | Load testing (already in use Phase 236) | Grafana's load tester, JS-based, threshold enforcement |
| **pytest-xdist** | Parallel pytest execution (already installed) | Worker-based isolation for E2E tests |
| **pytest-json-report** | Structured JSON output | For automated bug filing service parsing |
| **allure-pytest** | Test reporting aggregation | Consolidate results across test types |

---

## Installation

```bash
# Core Bug Discovery (add to requirements-testing.txt)
pip install atheris>=2.2.0
pip install hypothesis>=6.151.5
pip install schemathesis>=3.30.0
pip install percy>=3.0.0
pip install pytest-benchmark>=4.0.0
pip install memray>=1.0.0
pip install toxiproxy-python>=2.0.0

# Already installed (verify versions)
pip install "playwright==1.58.0"
pip install "pytest-playwright==0.5.2"
pip install "pytest-xdist==3.6.1"
pip install "pytest-timeout>=2.2.0"
pip install "pytest-json-report>=0.6.0"
pip install "allure-pytest>=2.13.0"

# Browser engines for Playwright
playwright install chromium
playwright install firefox
playwright install webkit
```

---

## Integration with Existing Infrastructure

### 1. Fuzzing Enhancement (Atheris)

**Current State:** `backend/tests/fuzzy_tests/` exists with `fuzz_helpers.py`

**Enhancements Needed:**
- **Corpus management**: Save/reduce interesting test cases
- **Continuous fuzzing**: CI/CD integration for nightly fuzz runs
- **Crash triage**: Automatic deduplication and bug filing

**Integration Points:**
```python
# backend/tests/fuzzy_tests/fuzz_helpers.py (existing)
# Add corpus management:
def save_to_corpus(data: bytes, crash_path: str):
    """Save interesting input to corpus directory."""
    os.makedirs(os.path.dirname(crash_path), exist_ok=True)
    with open(crash_path, 'wb') as f:
        f.write(data)

# backend/tests/fuzzy_tests/currency_parser_fuzz.py (existing)
# Extend with:
# - Corpus directory: backend/tests/fuzzy_tests/corpus/currency_parser/
# - Crash directory: backend/tests/fuzzy_tests/crashes/currency_parser/
```

**New File:** `backend/tests/fuzzy_tests/scripts/run_fuzz_campaigns.py`
- Orchestrates multiple fuzzers in parallel
- Generates coverage reports
- Files bugs for crashes

### 2. Property-Based Testing (Hypothesis)

**Current State:** `backend/tests/property_tests/` has 100+ invariant tests

**Enhancements Needed:**
- **Stateful testing**: Test complex state machines (agent lifecycle)
- **Contract testing**: API invariants via Schemathesis
- **Performance properties**: Verify response time constraints

**Integration Points:**
```python
# backend/tests/property_tests/api_contracts/ (new)
# Use Schemathesis for OpenAPI contract testing:
import schemathesis
from hypothesis import settings

schema = schemathesis.from_path("backend/openapi.json")

@schema.parametrize()
@settings(max_examples=100)
def test_api_contracts(case):
    """Test all API endpoints with Hypothesis-generated inputs."""
    response = case.call()
    assert response.status_code < 500  # No server errors
```

### 3. Visual Regression Testing (Percy)

**Current State:** Playwright 1.58.0 installed, no visual regression

**New Capability:**
```python
# backend/tests/visual_regression/test_canvas_regression.py (new)
from playwright.sync_api import Page
from percy import percy_snapshot

def test_canvas_visual_regression(authenticated_page: Page):
    """Test canvas presentation has no visual regressions."""
    authenticated_page.goto("/canvas/test-canvas")

    # Capture screenshot for Percy comparison
    percy_snapshot(authenticated_page, "canvas-presentation")
```

**Integration:** `.github/workflows/visual-regression.yml`
- Runs on PR to main
- Percy CLI uploads screenshots
- GitHub comment with diff URL

### 4. Memory Leak Detection (memray)

**Current State:** No memory leak detection

**New Capability:**
```python
# backend/tests/memory_leaks/test_agent_memory_leaks.py (new)
from memray import Tracker
import pytest

def test_agent_execution_no_leaks():
    """Verify agent execution doesn't leak memory."""
    with Tracker("/tmp/agent_memory.bin") as tracker:
        # Execute agent 100 times
        for i in range(100):
            execute_agent("test-agent")

    # Analyze memory allocations
    # memray flamegraph /tmp/agent_memory.bin
    # memray summary /tmp/agent_memory.bin
```

**Integration:** Add to Phase 236 (stress testing) plans
- Run memray before/after load tests
- Compare memory usage
- File bug if >100MB increase

### 5. Network Chaos Simulation (Toxiproxy)

**Current State:** `backend/tests/chaos/chaos_helpers.py` has mock-based failures

**Enhancement Needed:** Real network chaos with Toxiproxy
```python
# backend/tests/chaos/test_network_chaos_toxiproxy.py (new)
import toxiproxy

def test_api_resilience_to_latency():
    """Test API handles 500ms latency gracefully."""
    # Create toxiproxy client
    proxy = toxiproxy.ToxiproxyClient("http://localhost:8474")

    # Create proxy
    proxy.create_proxy("api_proxy", "localhost:8000", "localhost:8000")

    # Add 500ms latency
    proxy.toxic("api_proxy", "latency", "downstream", latency=500)

    # Test API still responds
    response = requests.get("http://localhost:8000/health/live")
    assert response.status_code == 200

    # Clean up
    proxy.destroy_proxy("api_proxy")
```

### 6. Headless Browser Multi-Engine (Playwright)

**Current State:** Chromium only (default)

**Enhancement:** Test Firefox/WebKit for cross-browser bugs
```python
# backend/tests/cross_browser/test_canvas_multi_engine.py (new)
import pytest
from playwright.sync_api import Page

@pytest.mark.parametrize("browser_name", ["firefox", "webkit"])
def test_canvas_firefox_webkit(browser_name: str, page: Page):
    """Test canvas presentation works on Firefox and WebKit."""
    # Playwright pytest plugin handles browser launch
    page.goto("/canvas/test-canvas")

    # Verify canvas loads
    assert page.locator("canvas").count() == 1
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **Atheris** | libFuzzer (C++ only) | Use libFuzzer if testing C/C++ extensions, not Python code |
| **Hypothesis** | QuickCheck (Haskell), PropEr (Erlang) | Use language-native tools if not Python |
| **Playwright** | Selenium, Puppeteer | Selenium for legacy browser support, Puppeteer for Chrome-only |
| **Percy** | BackstopJS, Chromatic | BackstopJS for open-source alternative, Chromatic for Storybook |
| **memray** | tracemalloc, memory_profiler | tracemalloc for stdlib-only, memory_profiler for older Python |
| **Toxiproxy** | Chaos Monkey, Gremlin | Chaos Monkey for Kubernetes, Gremlin for cloud-native chaos |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **python-fuzz** | Package doesn't exist on PyPI (removed from requirements-testing.txt) | Atheris |
| **chaos-toolkit** | Package doesn't exist on PyPI (removed from requirements-testing.txt) | Custom chaos_helpers.py + Toxiproxy |
| **Selenium** | Slower, less reliable than Playwright, no auto-waiting | Playwright 1.58.0+ |
| **Puppeteer** | Chrome-only, Playwright supports Chromium/Firefox/WebKit | Playwright 1.58.0+ |
| **unittest-chaos** | Outdated, unmaintained | pytest + chaos_helpers.py |
| **mutmut** | Slow mutation testing (already in requirements-testing.txt but rarely used) | Focus on fuzzing/property tests instead |
| **Bandit** | Static analysis (already in requirements-testing.txt) | Use for security, not bug discovery |
| **pip-audit** | Dependency vulnerability scanning (already in requirements.txt) | Use for security, not functional bugs |

---

## Stack Patterns by Variant

**If fuzzing Python code:**
- Use **Atheris** with libFuzzer backend
- Because: Coverage-guided, best-in-class for Python, Google-maintained
- Corpus management: Save interesting inputs to `backend/tests/fuzzy_tests/corpus/`

**If testing API contracts:**
- Use **Schemathesis** (Hypothesis-powered)
- Because: Auto-generates edge cases for OpenAPI specs, integrates with FastAPI
- Alternative: Manual Hypothesis tests for non-OpenAPI endpoints

**If visual regression testing:**
- Use **Percy** for CI/CD integration
- Because: GitHub integration, diff URLs, easy triage
- Alternative: BackstopJS for open-source projects

**If memory leak detection:**
- Use **memray** for Python 3.11+
- Because: Bloomberg-maintained, native extensions support, flamegraphs
- Alternative: tracemalloc (stdlib) for simpler cases

**If network chaos testing:**
- Use **Toxiproxy-Python** for realistic network failures
- Because: Proxy-based, real network conditions, not mocks
- Alternative: chaos_helpers.py mocks for unit tests

**If cross-browser testing:**
- Use **Playwright** multi-engine (Chromium/Firefox/WebKit)
- Because: Single API, auto-waiting, network interception
- Alternative: Selenium for legacy IE support

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| **atheris>=2.2.0** | Python 3.8+, requires clang/libFuzzer | Linux/macOS only, no Windows support |
| **hypothesis>=6.151.5** | Python 3.8+, pytest 7.4+ | Downgrade to 6.92.0 if PyPI issues |
| **schemathesis>=3.30.0** | Python 3.8+, aiohttp 3.8+ | Requires FastAPI OpenAPI spec |
| **playwright==1.58.0** | Python 3.8+, pytest-playwright 0.5.2 | Pin to 1.58.0 for E2E stability |
| **percy>=3.0.0** | Python 3.7+, Playwright/Selenium | Requires Percy CLI and project token |
| **pytest-benchmark>=4.0.0** | Python 3.8+, pytest 7.0+ | Use with pytest-cov for coverage correlation |
| **memray>=1.0.0** | Python 3.11+ only | **Critical:** Requires Python 3.11+, won't work on 3.10 |
| **toxiproxy-python>=2.0.0** | Python 3.7+, Toxiproxy server 3.x | Requires separate Toxiproxy server process |

---

## Phased Rollout

### Phase 1: Foundation (Week 1)
- Install Atheris, verify existing fuzz tests run
- Set up corpus management (`backend/tests/fuzzy_tests/corpus/`)
- Create fuzz campaign orchestration script

### Phase 2: Visual Regression (Week 2)
- Install Percy CLI and Python package
- Create baseline screenshots for critical pages
- Integrate with CI/CD (`.github/workflows/visual-regression.yml`)

### Phase 3: Memory Leaks (Week 3)
- Install memray (verify Python 3.11+)
- Create memory leak tests for agent execution
- Add to Phase 236 stress testing plans

### Phase 4: Network Chaos (Week 4)
- Install Toxiproxy server and Python client
- Enhance existing `chaos_helpers.py` with Toxiproxy integration
- Create network chaos test suite

### Phase 5: Cross-Browser (Week 5)
- Install Firefox/WebKit Playwright engines
- Create cross-browser test suite for canvas
- Integrate with CI/CD matrix strategy

---

## Source Verification

### Primary Sources (Context7/Official Docs)
- **Atheris**: https://github.com/google/atheris (Google's official repo, 2.2k stars)
- **Hypothesis**: https://hypothesis.works/ (official site, Python's leading PBT)
- **Schemathesis**: https://schemathesis.readthedocs.io/ (official docs, Hypothesis-powered)
- **Playwright**: https://playwright.dev/python/ (official docs, Microsoft-backed)
- **Percy**: https://percy.io/integrations/python (official integration docs)
- **memray**: https://bloomberg.github.io/memray/ (official docs, Bloomberg-maintained)
- **pytest-benchmark**: https://pytest-benchmark.readthedocs.io/ (official docs)
- **Toxiproxy**: https://toxiproxy.io/ (official site, chaos engineering)

### Secondary Sources (Web Search - MEDIUM confidence)
- **Fuzzing best practices**: Google OSS-Fuzz documentation
- **Property-based testing**: Hypothesis strategies guide
- **Visual regression**: Percy blog vs BackstopJS comparison
- **Memory profiling**: memray vs tracemalloc benchmarks
- **Chaos engineering**: Principles of Chaos community

### Existing Codebase Analysis (HIGH confidence)
- **Atheris integration**: `backend/tests/fuzzy_tests/fuzz_helpers.py` (already exists)
- **Hypothesis tests**: `backend/tests/property_tests/` (100+ tests)
- **Chaos helpers**: `backend/tests/chaos/chaos_helpers.py` (comprehensive)
- **Playwright E2E**: `backend/tests/e2e_ui/` (91 tests, Phase 234)
- **k6 load tests**: `backend/tests/load/` (Phase 236-01)

---

## Critical Gaps Identified

1. **Visual Regression Testing**: COMPLETELY MISSING
   - No screenshot comparison capability
   - Percy integration needed for UI bug discovery
   - **Priority**: HIGH for canvas/workflow UI bugs

2. **Memory Leak Detection**: COMPLETELY MISSING
   - No memory profiling in CI/CD
   - memray integration needed for long-running agent leaks
   - **Priority**: HIGH for daemon mode and episodic memory

3. **Cross-Browser Testing**: PARTIAL
   - Chromium only currently (Playwright default)
   - Firefox/WebKit needed for cross-platform bugs
   - **Priority**: MEDIUM for desktop/mobile compatibility

4. **Network Chaos**: MOCK-ONLY
   - chaos_helpers.py uses mocks, not real network failures
   - Toxiproxy needed for realistic latency/packet loss
   - **Priority**: MEDIUM for API resilience bugs

5. **Corpus Management**: BASIC
   - No fuzzing corpus persistence
   - No crash deduplication
   - **Priority**: LOW (existing fuzz tests still work)

---

## Testing Strategy Matrix

| Bug Type | Primary Tool | Secondary Tool | CI/CD Integration |
|----------|--------------|----------------|-------------------|
| **Crashes** | Atheris (fuzzing) | Hypothesis (PBT) | Nightly fuzz campaigns |
| **Visual Regressions** | Percy (screenshots) | Playwright (visual) | PR to main |
| **Memory Leaks** | memray (profiling) | pytest-benchmark (trends) | Weekly stress tests |
| **API Contract Violations** | Schemathesis (OpenAPI) | Hypothesis (custom) | PR to main |
| **Network Resilience** | Toxiproxy (chaos) | chaos_helpers.py (mocks) | Weekly chaos tests |
| **Performance Regressions** | pytest-benchmark | k6 (load) | Weekly load tests |
| **Cross-Browser Bugs** | Playwright (multi-engine) | Manual testing | PR to main |

---

## Recommended Dependencies for `requirements-bug-discovery.txt`

```txt
# Automated Bug Discovery Dependencies
# For v8.0 milestone: Discover 50+ bugs via fuzzing, chaos, PBT, visual regression

# Core Fuzzing
atheris>=2.2.0  # Coverage-guided fuzzing (Google)

# Property-Based Testing (already in requirements.txt)
# hypothesis>=6.151.5  # Keep version pin
hypothesis>=6.92.0,<7.0.0  # Conservative pin

# API Contract Testing (already in requirements-testing.txt)
# schemathesis>=3.30.0  # Keep version pin

# Visual Regression Testing
percy>=3.0.0  # Screenshot comparison for CI/CD

# Memory Leak Detection (Python 3.11+ only)
memray>=1.0.0  # Memory profiler (Bloomberg)

# Network Chaos Simulation
toxiproxy-python>=2.0.0  # Real network failures (not mocks)

# Performance Benchmarking (already in requirements-testing.txt)
# pytest-benchmark>=4.0.0  # Keep version pin

# Cross-Browser Testing (Playwright engines installed separately)
# playwright==1.58.0  # Already pinned

# Test Utilities (already in requirements.txt)
# pytest-timeout>=2.2.0  # Already present
# pytest-json-report>=0.6.0  # Already present
# allure-pytest>=2.13.0  # Already present

# Corpus Management
coverage[toml]>=7.0.0  # Coverage-guided fuzzing metrics
```

---

## Next Steps

1. **Verify Python 3.11+ requirement** for memray
   - Check CI/CD runner Python versions
   - Upgrade if needed (Personal Edition defaults to 3.11)

2. **Create `requirements-bug-discovery.txt`** with above dependencies

3. **Set up Percy project** and get API token
   - Sign up at https://percy.io/
   - Create project for Atom
   - Add `PERCY_TOKEN` to GitHub secrets

4. **Install Toxiproxy server** (separate from Python package)
   - Download binary: https://github.com/gholland/toxiproxy/releases
   - Run as Docker container in CI/CD

5. **Create fuzzing corpus directory structure**
   - `backend/tests/fuzzy_tests/corpus/`
   - `backend/tests/fuzzy_tests/crashes/`
   - Add to `.gitignore` (crashes/ should be committed)

6. **Enhance `chaos_helpers.py`** with Toxiproxy integration
   - Add `ToxiproxyChaosSimulator` class
   - Keep existing mock-based simulators for unit tests

---

*Stack research for: Automated Bug Discovery (Atom v8.0)*
*Researched: March 24, 2026*
*Confidence: HIGH (based on existing infrastructure analysis + official documentation)*
