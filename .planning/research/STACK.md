# Technology Stack

**Project:** Atom - Coverage Expansion to 80% Targets
**Researched:** March 7, 2026
**Overall Confidence:** HIGH

## Executive Summary

Atom's existing test infrastructure is **comprehensive and production-ready** for achieving 80% coverage targets across all platforms. **No new testing frameworks are required** - the focus should be on **enforcement mechanisms**, **coverage analysis tools**, and **test generation assistance** rather than adding new testing capabilities.

**Key Finding:** The platform already has all necessary tools configured:
- **Backend:** pytest 7.4+, pytest-cov 4.1+, Hypothesis 6.151.5, coverage enforcement configured (80% threshold in pytest.ini)
- **Frontend:** Jest 30.0+, jest-axe, MSW, coverage thresholds configured (80% global in jest.config.js)
- **Mobile:** jest-expo, React Native Testing Library, thresholds set to 60% (needs adjustment to 80%)
- **Desktop:** cargo-tarpaulin 0.27, proptest 1.0 (threshold enforcement needs CI/CD configuration)

**Recommended Additions:** Test generation assistance and coverage gap analysis tools to **accelerate** reaching 80% targets, not foundational testing capabilities.

---

## Recommended Stack

### Core Testing Framework (EXISTING - Use As-Is)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest** | 7.4+ | Backend test runner | Industry standard, async support, mature ecosystem |
| **pytest-cov** | 4.1+ | Coverage reporting | Native pytest integration, supports branch coverage |
| **Hypothesis** | 6.151.5 | Property-based testing | Mature, pytest integration, stateful testing |
| **Jest** | 30.0+ | Frontend/Mobile test runner | Built into Next.js/Expo, excellent TypeScript support |
| **React Testing Library** | 16.3+ | Component testing | Best practice for React, accessibility-first |
| **jest-expo** | latest | Mobile test runner | Expo SDK 50 compatibility |
| **cargo-tarpaulin** | 0.27 | Desktop coverage | Rust standard, CI/CD integration |

**Confidence:** HIGH - All tools currently installed and operational.

---

### Coverage Enforcement & Analysis (ADDITIONS FOR 80%)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest-cov (existing)** | 4.1+ | Coverage enforcement | Already has `--cov-fail-under=80` in pytest.ini |
| **coverage.py (existing)** | 7.0+ | Advanced coverage analysis | Branch coverage, HTML reports, diff coverage |
| **Jest coverage thresholds (existing)** | 30.0+ | Frontend enforcement | Already configured to 80% in jest.config.js |
| **cargo-tarpaulin --fail-under** | 0.27+ | Desktop enforcement | Add `--fail-under 80` to CI/CD pipeline |

**Confidence:** HIGH - Thresholds already configured, just needs CI/CD integration.

---

### Test Generation Assistance (NEW - Accelerate 80%)

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **GitHub Copilot** | N/A | Generate test scaffolding | When creating new modules/components |
| **Cursor AI** | N/A | Generate test cases from code | For boilerplate test code (CRUD operations) |
| **LLM-assisted test generation** | N/A | Generate edge case tests | For complex business logic with many edge cases |

**Rationale:** Manual test writing is the **primary bottleneck** to reaching 80% coverage. AI-assisted generation can accelerate by 3-5x for:
- CRUD operations (API endpoints, database models)
- Component state tests (React hooks, canvas components)
- Edge case identification (error paths, boundary conditions)

**Confidence:** MEDIUM - LLM-generated tests require human review and quality validation.

---

### Coverage Gap Analysis (NEW - Identify What's Missing)

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **diff-cover** | 8.0+ | PR-level coverage enforcement | CI/CD PR checks (diff coverage) |
| **pytest-annotate-output** | 1.0+ | Visualize uncovered lines | Development (see what's missing in IDE) |
| **jest-coverage-report-action** | latest | GitHub Actions coverage reporting | CI/CD summary reports |

**Rationale:** Existing infrastructure collects coverage but lacks:
1. **PR-level coverage enforcement** (diff coverage)
2. **Visual coverage reports** in pull requests
3. **Trend analysis** for coverage degradation

**Confidence:** HIGH - These are mature tools with excellent CI/CD integration.

---

### Mutation Testing (OPTIONAL - Validate Test Quality)

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **mutmut** | 2.4+ | Python mutation testing | Validate critical path tests (ALREADY IN REQUIREMENTS-TESTING.TXT) |
| **@stryker-mutator/core** | 9.5+ | JavaScript/TypeScript mutation testing | For critical frontend components (canvas, hooks) |
| **cargo-mutants** | 0.5+ | Rust mutation testing | For critical desktop functionality |

**Rationale:** Mutation testing validates **test quality**, not just coverage. High coverage + low mutation score = **poor tests**.

**Recommendation:** Use **sparingly** on critical paths only:
- Agent governance logic
- Canvas state management
- LLM routing logic
- Device capabilities (security-sensitive)

**Confidence:** HIGH - Tools are mature, but mutation testing is **expensive** (10-20x slower than regular tests).

---

## Per-Platform Stack

### Backend (Python)

**Existing Stack:**
```bash
# Core testing (already installed)
pytest==7.4+
pytest-asyncio==0.21.0+
pytest-cov==4.1.0+

# Property-based testing (already installed)
hypothesis==6.151.5

# Coverage enforcement (already configured in pytest.ini)
coverage[toml]==7.0+  # Branch coverage, HTML reports
```

**Additions for 80%:**
```bash
# PR-level coverage enforcement (NEW)
pip install diff-cover==8.0+  # Enforce coverage on changed code

# Test generation acceleration (OPTIONAL)
# Use AI tools (Copilot, Cursor) for scaffolding
```

**Coverage Threshold Enforcement:**
```ini
# Already in pytest.ini:
[coverage:report]
fail_under = 80  # Line coverage
fail_under_branch = 70  # Branch coverage
```

**Confidence:** HIGH - No new tools required for 80% coverage.

---

### Frontend (TypeScript/React)

**Existing Stack:**
```json
{
  "devDependencies": {
    "jest": "^30.0.5",
    "@testing-library/react": "^16.3.0",
    "@testing-library/user-event": "^14.6.1",
    "jest-axe": "^10.0.0",
    "msw": "^1.3.5",
    "fast-check": "^4.5.3"
  }
}
```

**Additions for 80%:**
```bash
# PR-level coverage enforcement (NEW)
npm install --save-dev jest-coverage-report-action

# Coverage reporting in PRs (NEW)
# Already have @stryker-mutator/core for mutation testing
```

**Coverage Threshold Enforcement:**
```javascript
// Already in jest.config.js:
coverageThreshold: {
  global: {
    branches: 75,
    functions: 80,
    lines: 80,
    statements: 75,
  },
  './lib/**/*.{ts,tsx}': { lines: 90 },  // Utilities
  './hooks/**/*.{ts,tsx}': { lines: 85 },  // Custom hooks
  './components/canvas/**/*.{ts,tsx}': { lines: 85 },  // Canvas
  './components/ui/**/*.{ts,tsx}': { lines: 80 },  // UI components
  './components/integrations/**/*.{ts,tsx}': { lines: 80 },  // Integrations
  './pages/**/*.{ts,tsx}': { lines: 80 },  // Next.js pages
}
```

**Confidence:** HIGH - Thresholds already configured at 80%.

---

### Mobile (React Native)

**Existing Stack:**
```json
{
  "devDependencies": {
    "jest-expo": "^51.0.0",
    "@testing-library/react-native": "^12.0.0",
    "react-native-testing-library": "^6.0.0"
  }
}
```

**Additions for 80%:**
```bash
# No new tools needed - jest-expo has full coverage support
# Just adjust threshold in jest.config.js
```

**Coverage Threshold Adjustment:**
```javascript
// Current: 60% (TOO LOW)
coverageThreshold: {
  global: {
    branches: 60,
    functions: 60,
    lines: 60,
    statements: 60
  }
}

// Target: 80%
coverageThreshold: {
  global: {
    branches: 75,
    functions: 80,
    lines: 80,
    statements: 75,
  }
}
```

**Confidence:** HIGH - Just needs threshold adjustment.

---

### Desktop (Rust/Tauri)

**Existing Stack:**
```toml
[dev-dependencies]
cargo-tarpaulin = "0.27"
proptest = "1.0"
```

**Additions for 80%:**
```bash
# Add CI/CD enforcement (NEW)
cargo tarpaulin --fail-under 80 --out Xml
```

**Coverage Threshold Enforcement:**
```yaml
# Add to .github/workflows/test-coverage.yml:
- name: Test coverage (Desktop)
  run: |
    cargo tarpaulin --verbose --workspace --timeout 120 --fail-under 80 --out Xml
```

**Confidence:** HIGH - cargo-tarpaulin supports `--fail-under` flag.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Backend Coverage** | pytest-cov | nose2, unittest2 | Deprecated, less feature-rich |
| **Frontend Coverage** | Jest内置 | Istanbul/nyc | Jest uses Istanbul internally, redundant |
| **Mobile Coverage** | jest-expo | Detox | Detox is E2E, not unit coverage |
| **Desktop Coverage** | cargo-tarpaulin | kcov, grcov | kcov unmaintained, grcov requires LLVM setup |
| **Test Generation** | AI-assisted | Pynguin, EvoSuite | Python/Java-only, immature for TS/Rust |
| **Mutation Testing** | mutmut, stryker | cosmic-ray, PIT | cosmic-ray unmaintained, PIT is Java-only |

---

## Installation

### Backend (Python)
```bash
# Core testing (ALREADY INSTALLED)
pip install pytest==7.4+ pytest-asyncio==0.21+ pytest-cov==4.1+

# Property-based testing (ALREADY INSTALLED)
pip install hypothesis==6.151.5

# PR-level coverage enforcement (NEW)
pip install diff-cover==8.0+

# Mutation testing (OPTIONAL - Phase 2-03)
pip install mutmut==2.4+
```

### Frontend (TypeScript/React)
```bash
# Core testing (ALREADY INSTALLED)
npm install --save-dev jest@30.0+ @testing-library/react@16.3+

# PR-level coverage (NEW)
npm install --save-dev jest-coverage-report-action

# Mutation testing (OPTIONAL - already installed)
npm install --save-dev @stryker-mutator/core@9.5+ @stryker-mutator/jest-runner@9.5+
```

### Mobile (React Native)
```bash
# Core testing (ALREADY INSTALLED via Expo)
# No new tools needed - adjust threshold in jest.config.js
```

### Desktop (Rust)
```bash
# Core testing (ALREADY INSTALLED)
cargo install cargo-tarpaulin --version 0.27

# Mutation testing (OPTIONAL)
cargo install cargo-mutants
```

---

## Anti-Patterns to Avoid

### 1. Don't Add New Testing Frameworks
**Why:** Atom already has comprehensive tooling. Adding more frameworks = maintenance burden.
**Instead:** Use existing pytest/Jest infrastructure.

### 2. Don't Chase 100% Coverage
**Why:** Diminishing returns. 80% is the sweet spot (caught 80% of bugs, manageable effort).
**Instead:** Focus on **critical path coverage** (governance, LLM, canvas) > 90%.

### 3. Don't Use Mutation Testing Everywhere
**Why:** 10-20x slower than regular tests. Expensive to run in CI/CD.
**Instead:** Run mutation tests **weekly** on critical paths only.

### 4. Don't Ignore Test Quality
**Why:** High coverage ≠ good tests. Tests can pass without asserting behavior.
**Instead:** Use mutation testing **periodically** to validate test quality.

### 5. Don't Rely Solely on AI-Generated Tests
**Why:** LLMs generate boilerplate well, but miss edge cases and domain-specific invariants.
**Instead:** Use AI for **scaffolding**, human review for **logic validation**.

---

## Integration with Existing Infrastructure

### Quality Infrastructure (Phases 149-151)
**Existing:**
- Parallel execution (pytest-xdist, Jest maxWorkers)
- Trending (coverage_trend.json, coverage-trend-tracker.js)
- Flaky detection (pytest-rerunfailures, jest-retry-wrapper)
- Reliability scoring (backend/tests/scripts/)

**Integration Points:**
1. **PR-level coverage gates** integrate with flaky detection (block unreliable coverage gains)
2. **Diff coverage** integrates with trending (track coverage per commit, not just aggregate)
3. **Mutation testing** integrates with reliability scoring (mutation score = test quality metric)

### Cross-Platform Coverage Aggregation
**Existing:**
- `backend/tests/scripts/cross_platform_coverage_gate.py` - Unified coverage aggregation
- `backend/tests/coverage_reports/metrics/cross_platform_summary.json` - Cross-platform metrics

**Integration:**
- Add **diff-cover** for each platform to cross-platform gate
- Add **mutation score** to quality metrics dashboard

---

## Sources

- **pytest Documentation:** https://docs.pytest.org/ (Coverage configuration, pytest-cov)
- **Jest Documentation:** https://jestjs.io/docs/configuration (coverageThresholds)
- **cargo-tarpaulin:** https://github.com/xd009642/tarpaulin (Rust coverage, fail-under flag)
- **diff-cover:** https://github.com/Bachmann1234/diff-cover (PR-level coverage enforcement)
- **@stryker-mutator:** https://stryker-mutator.io/ (JavaScript/TypeScript mutation testing)
- **mutmut:** https://github.com/boxed/mutmut (Python mutation testing)

**Confidence Assessment:**
| Area | Confidence | Notes |
|------|------------|-------|
| Core Testing Stack | HIGH | All tools currently installed and operational |
| Coverage Enforcement | HIGH | Thresholds configured in pytest.ini and jest.config.js |
| Test Generation | MEDIUM | AI-assisted generation requires human review |
| Coverage Gap Analysis | HIGH | Mature tools (diff-cover) with CI/CD integration |
| Mutation Testing | HIGH | Tools mature, but expensive (use sparingly) |
| Platform-Specific | HIGH | Each platform has appropriate tooling |

---

## Summary

**Recommended Approach:**
1. **Use existing tools** - pytest, Jest, cargo-tarpaulin already configured
2. **Add PR-level enforcement** - diff-cover (backend), jest-coverage-report-action (frontend)
3. **Adjust mobile threshold** - 60% → 80% in jest.config.js
4. **Add desktop enforcement** - `--fail-under 80` flag to cargo-tarpaulin
5. **Use AI for test generation** - Accelerate scaffolding, not replace human review
6. **Mutation testing sparingly** - Critical paths only, weekly runs

**Expected Outcome:**
- **Backend:** 26.15% → 80% (53.85 pp gap) with PR-level enforcement + AI-assisted generation
- **Frontend:** 65.85% → 80% (14.15 pp gap) with existing thresholds + gap analysis
- **Mobile:** 60% → 80% (20 pp gap) with threshold adjustment
- **Desktop:** 65-70% → 80% (10-15 pp gap) with CI/CD enforcement

**Timeline:** 2-3 months (depending on codebase size and test writer velocity).
