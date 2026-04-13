# Feature Landscape: Coverage Expansion to 70%

**Domain:** Test Coverage Expansion for AI Automation Platform
**Researched:** 2026-04-13
**Overall confidence:** HIGH (based on existing Phase 8.5 research, Phase 258 verification, and industry standards)

---

## Executive Summary

Comprehensive test coverage expansion typically follows a **layered approach**: fix test infrastructure blockers → measure baseline → target high-impact files → enforce quality gates → iterate with progressive thresholds. For v11.0's goal of reaching 70% coverage (backend 18.25% → 70%, frontend 14.61% → 70%), the key is **prioritizing by impact** (files >200 lines with <10% coverage) and **maintaining quality gates** throughout the expansion process.

**Different from v10.0:** v10.0 achieved quality infrastructure (gates, documentation, property tests) but left coverage at 18.25% backend / 14.61% frontend. v11.0 focuses on **execution** of coverage expansion waves with realistic 70% targets (pragmatic vs. v10.0's 80%).

**Key insight:** Industry standard for production code is 70-80% coverage. 70% is the **minimum acceptable threshold** (Google uses 60%, many enterprise teams target 75%). 100% is counterproductive (diminishing returns, test maintenance burden).

---

## Key Findings

**Stack:** pytest-cov (backend), Jest/nyc (frontend), property-based testing (Hypothesis), quality gates (CI/CD enforcement)
**Architecture:** Layered expansion strategy (baseline → high-impact files → API routes → edge cases)
**Critical pitfall:** Starting with low-value files (small utilities) provides minimal coverage impact vs. targeting largest zero-coverage files first

---

## Table Stakes

Features users expect for a production-ready coverage expansion. Missing = expansion feels incomplete or unsustainable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Baseline measurement** | Cannot improve what you don't measure; need starting point for progress tracking | Low | ✅ DONE (Phase 251: 18.25% backend, Phase 254: 14.61% frontend) |
| **Coverage report generation** | HTML reports show exact missing lines; JSON enables trend tracking | Low | ✅ DONE (pytest-cov, nyc configured) |
| **High-impact file identification** | Testing largest files first maximizes coverage increase per hour spent | Medium | ⚠️ PARTIAL (Phase 251 identified 77 zero-coverage backend files; frontend less clear) |
| **Quality gate enforcement** | Prevents coverage regression; gates enforce minimum standards | Medium | ✅ DONE (Phase 258: 70% → 75% → 80% progressive thresholds, CI/CD blocking) |
| **Test infrastructure unblocking** | Cannot expand coverage if tests cannot run (syntax errors, missing models, import errors) | High | ⚠️ PARTIAL (Phase 266 schema migration unblocked 900+ tests; 300+ still blocked by import errors) |
| **Coverage trend tracking** | Shows progress over time; identifies concerning drops (↑↓→ indicators) | Low | ✅ DONE (Phase 258: quality_metrics.json with 30-day history) |
| **Property-based testing integration** | Catches edge cases unit tests miss; validates invariants across thousands of inputs | High | ✅ DONE (Phase 252: 96 property tests, 100% pass rate) |
| **Branch coverage measurement** | More accurate than line coverage; catches untested conditional branches | Low | ✅ DONE (pytest-cov branch=true configured, but only 3.87% branch coverage achieved) |
| **Documentation of coverage targets** | Clear goals prevent scope creep; progressive thresholds manage expectations | Low | ✅ DONE (docs/testing/COVERAGE_REPORT_GUIDE.md, 1,377 lines of QA docs) |

**Status:** 7/9 table stakes complete (78%). Missing: clear frontend high-impact file list, remaining test infrastructure unblocking.

---

## Differentiators

Features that set coverage expansion apart from basic "write more tests" approaches. Not expected, but highly valued for efficiency and sustainability.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **AI-assisted test generation** | 10x faster baseline creation for zero-coverage files; targets uncovered lines automatically | Medium | ⚠️ EVALUATE (Cover-Agent, CoverUp available; efficacy on complex business logic unvalidated) |
| **Wave-based expansion strategy** | Breaks 50pp gap into manageable chunks (waves of 5-10pp); maintains momentum with measurable progress | Low | ✅ PLANNED (v11.0 multi-wave approach: fix tests → backend waves → frontend waves) |
| **Progressive threshold enforcement** | Realistic targets (70% → 75% → 80%) vs. unrealistic 80% overnight; reduces developer resistance | Low | ✅ DONE (Phase 258 quality-gate-config.yml) |
| **Diff coverage enforcement** | Prevents PRs from dropping coverage; focuses on new code, not historical debt | Medium | ⚠️ CONFIGURED (diff-cover available; enforcement unclear in Phase 258) |
| **Mutation testing for quality validation** | Verifies tests actually catch bugs (not just execute code); identifies weak tests | High | ❌ NOT IMPLEMENTED (mutmut available; Phase 8.5 research noted as "future enhancement") |
| **Flaky test detection and quarantine** | Prevents unreliable tests from blocking PRs; maintains trust in test suite | Medium | ✅ DONE (pytest-rerunfailures configured, 3 reruns; SQLite quarantine for known flaky tests) |
| **Coverage-per-component breakdown** | Identifies weak modules (e.g., fleet_admiral.py 0% vs. governance_cache.py 85.2%); guides targeting | Low | ✅ DONE (Phase 266 report shows component-level coverage) |
| **Emergency bypass mechanism** | Allows temporary gate disable for emergencies; prevents gate from blocking critical fixes | Low | ✅ DONE (EMERGENCY_BYPASS env var in quality gate config) |
| **Assert-to-test ratio tracking** | Identifies test proliferation (many asserts, few tests) vs. meaningful coverage | Low | ❌ NOT TRACKED (Phase 154 research mentioned; implementation unclear) |
| **Complexity-aware coverage targets** | Higher coverage for critical paths (auth, payments) vs. lower for utilities (helpers, DTOs) | Medium | ❌ NOT IMPLEMENTED (uniform 70% target across all files) |

**Status:** 5/10 differentiators implemented (50%). v11.0 should consider complexity-aware targets (critical paths vs. utilities).

---

## Anti-Features

Features to explicitly NOT build during coverage expansion.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **100% coverage enforcement** | Diminishing returns; tests implementation details not behavior; high maintenance burden | Target 70-80% (industry standard); focus on business logic, not edge cases |
| **Coverage for coverage's sake** | Tests without assertions (execute code but don't validate); false confidence | Enforce test quality (assertions, behavior validation); use mutation testing to identify weak tests |
| **Manual coverage tracking** | Spreadsheets, manual calculations are error-prone; not CI-integrated | Use pytest-cov/nyc for automated measurement; quality_metrics.json for trend tracking |
| **Custom coverage calculation scripts** | Reinventing the wheel; coverage.py/coverage.py are industry standards | Use pytest-cov (backend), nyc (frontend); customize via .coverage-rc not new scripts |
| **Testing implementation details** | Brittle tests (break on refactoring); test behavior, not internal state | Test public APIs and observable behavior; use black-box testing for integration tests |
| **Over-mocking external dependencies** | Tests pass but production fails; mocks hide real integration issues | Use integration tests for end-to-end validation; mock only external services (APIs, databases) |
| **Neglecting branch coverage** | Line coverage looks good (80%) but branch coverage poor (30%); misses conditional paths | Enable branch coverage in pytest-cov; write tests for both true/false branches |
| **Ignoring frontend test failures** | 1,504 failing frontend tests (28.8% failure rate) block accurate coverage measurement | Fix frontend tests first (Phase 250 approach); then expand coverage |
| **Starting with low-value files** | Testing 50-line helpers provides minimal impact; coverage increases <1% | Prioritize by lines of code (largest zero-coverage files first) |
| **Writing tests without coverage targets** | Tests may not address uncovered lines; redundant effort | Always run `--cov-report=term-missing` to see exact missing lines; target gaps explicitly |

---

## Feature Dependencies

```
Test Fixes → Coverage Measurement (baseline)
Coverage Measurement → High-Impact File Identification
High-Impact File Identification → Wave 1 Coverage Expansion
Wave 1 → Wave 2 → Wave 3 (iterative waves)
Quality Gates → All Waves (enforcement throughout)
Coverage Expansion → Mutation Testing (quality validation)
Coverage Expansion → Documentation Updates (trends, strategies)
```

**Critical Path:** Fix failing tests (unblock measurement) → Measure baseline → Identify high-impact files → Execute Wave 1 → Enforce quality gates → Wave 2 → Wave 3 → Target 70%

**Parallel Paths:** Backend waves and frontend waves can run in parallel (different teams, different coverage files)

---

## MVP Recommendation

**For v11.0 Coverage Completion (70% target):**

### Prioritize (MVP - Must Have)

1. **Frontend Test Fixes** (Phase 250-style)
   - Fix 1,504 failing tests (28.8% failure rate → 100% pass rate)
   - Unblock accurate frontend coverage measurement
   - **Complexity:** High (many failures, diverse root causes)
   - **Impact:** HIGH - cannot expand coverage without working tests

2. **Backend High-Impact File Coverage** (Wave 1)
   - Target files >200 lines with <10% coverage
   - Current low-hanging fruit: `fleet_admiral.py` (0%, 856 lines), `atom_meta_agent.py` (0%, 645 lines), `queen_agent.py` (0%, 523 lines)
   - **Complexity:** Medium (large files, but clear coverage gaps)
   - **Impact:** HIGH - largest coverage increase per hour spent

3. **Frontend High-Impact File Coverage** (Wave 1)
   - Identify zero-coverage files >200 lines (frontend less clear than backend)
   - Target auth, agents, workflows, canvas components (critical paths)
   - **Complexity:** Medium (needs frontend coverage baseline refinement)
   - **Impact:** HIGH - frontend has larger gap (-55.39pp to 70% vs. backend -51.75pp)

4. **Quality Gate Maintenance**
   - Enforce 70% threshold throughout expansion
   - Monitor trends (↑↓→ indicators)
   - Prevent coverage regression
   - **Complexity:** Low (infrastructure exists, monitor and adjust)
   - **Impact:** MEDIUM - prevents backsliding, maintains standards

### Defer (Post-MVP)

5. **Mutation Testing** (Quality Validation)
   - Use mutmut to verify test quality
   - Identify weak tests (execute code but don't catch bugs)
   - **Complexity:** High (new tool, test execution time increases)
   - **Impact:** MEDIUM - improves test quality but not required for 70% target
   - **Defer to:** v11.1 or v12.0 (after 70% achieved)

6. **AI-Assisted Test Generation**
   - Evaluate Cover-Agent, CoverUp for baseline test creation
   - **Complexity:** Medium (tool setup, prompt engineering, result validation)
   - **Impact:** HIGH if effective (10x faster), LOW if poor quality
   - **Defer to:** Wave 2 or 3 (after manual approach establishes patterns)

7. **Complexity-Aware Coverage Targets**
   - Higher targets for critical paths (80-90% for auth, payments, data loss prevention)
   - Lower targets for utilities (50-60% for helpers, DTOs)
   - **Complexity:** Medium (file classification, policy definition, enforcement)
   - **Impact:** MEDIUM - more realistic targets, but adds complexity
   - **Defer to:** After 70% uniform target achieved

8. **Assert-to-Test Ratio Tracking**
   - Identify test proliferation (many asserts, few tests)
   - **Complexity:** Low (add metric to quality_metrics.json)
   - **Impact:** LOW - nice-to-have metric, not critical for 70% target
   - **Defer to:** v11.1 (quality refinement phase)

---

## Industry Benchmarks (2026)

| Metric | Industry Standard | Atom v10.0 Actual | v11.0 Target |
|--------|-------------------|-------------------|--------------|
| **Backend Coverage** | 70-80% (Google 60%, enterprise 75%) | 18.25% | 70% |
| **Frontend Coverage** | 70-80% (complex UIs often 60-70%) | 14.61% | 70% |
| **Test Pass Rate** | 100% (blocking gate) | 71.2% frontend, 99.3% backend | 100% |
| **Branch Coverage** | 60-70% (more meaningful than line) | 3.87% backend | 50% (stretch goal) |
| **Property Tests** | 30+ invariants (Hypothesis guide) | 96 tests (100% pass) | Maintain + expand |
| **Flaky Test Rate** | <1% (ideal), <5% (acceptable) | Unknown (reruns configured) | <5% |
| **Test Execution Time** | <30 min (full suite) | 74 seconds (backend, 928 tests) | <10 min (backend+frontend) |
| **Coverage Regression** | 0% (blocked by gate) | Enforced (Phase 258) | Maintain enforcement |

**Sources:** Phase 8.5 research (HIGH confidence), Phase 258 verification (HIGH confidence), industry standards from testing documentation (MEDIUM confidence - based on training data, web search unavailable due to rate limits).

---

## Coverage Expansion Strategies

### Strategy 1: High-Impact File Prioritization (Recommended for v11.0)

**What:** Target largest zero-coverage files first for maximum coverage increase per hour.

**When to use:** Starting from low baseline (<20% coverage), need quick wins to demonstrate progress.

**Example (Backend - Phase 266 data):**
```
Top 5 zero-coverage files:
1. fleet_admiral.py: 0% (856 lines) → Target 50% (+428 lines)
2. atom_meta_agent.py: 0% (645 lines) → Target 50% (+323 lines)
3. queen_agent.py: 0% (523 lines) → Target 50% (+262 lines)
4. agent_routes.py: 2.1% (18/850 lines) → Target 50% (+407 lines)
5. workflow_routes.py: 3.4% (28/820 lines) → Target 50% (+382 lines)

Total potential: +1,802 lines (10% of overall backend coverage)
Estimated effort: 3-5 days (for 50% coverage on these 5 files)
```

**Pros:**
- Maximizes coverage increase per hour
- Demonstrates visible progress quickly
- Focuses on complex business logic (not utilities)

**Cons:**
- Large files can be intimidating
- May miss integration dependencies
- Requires understanding of complex systems

**Implementation:**
1. Run `pytest --cov-report=json` to generate coverage.json
2. Parse JSON, filter by `percent_covered == 0` and `num_statements > 200`
3. Sort by `num_statements` descending
4. For each file: write tests targeting public methods, happy path, error cases
5. Re-run coverage, verify increase

**See also:** Phase 8.5 RESEARCH.md "Pattern 4: Coverage-Driven Test Generation"

---

### Strategy 2: Wave-Based Expansion (Recommended for v11.0)

**What:** Break 50pp gap into waves of 5-10pp, execute sequentially with quality gates.

**When to use:** Large gap (>40pp), need maintainable pace with continuous validation.

**Example (Backend - 18.25% → 70%):**
```
Wave 1: 18.25% → 30% (+11.75pp, ~10,600 lines)
- Target: High-impact files (>200 lines, <10% coverage)
- Duration: 1 week
- Files: fleet_admiral, atom_meta_agent, queen_agent, agent_routes, workflow_routes

Wave 2: 30% → 45% (+15pp, ~13,600 lines)
- Target: API routes (100+ endpoints), governance, canvas, LLM service
- Duration: 1 week
- Files: api/*.py (routes), core/agent_governance_service.py, core/llm/*.py

Wave 3: 45% → 60% (+15pp, ~13,600 lines)
- Target: Core services, episodic memory, workflow engine
- Duration: 1 week
- Files: core/episode_*.py, core/workflow_engine.py, tools/*.py

Wave 4: 60% → 70% (+10pp, ~9,100 lines)
- Target: Edge cases, error paths, integration tests
- Duration: 1 week
- Files: All modules <70%, focus on remaining gaps
```

**Pros:**
- Manageable chunks (5-10pp per wave)
- Continuous validation (quality gates after each wave)
- Maintains momentum (visible progress weekly)
- Parallelizable (backend Wave 1 and frontend Wave 1 can run simultaneously)

**Cons:**
- Requires upfront planning (wave definitions, file lists)
- May need to adjust targets based on actual progress
- Risk of "leftover" difficult files in later waves

**Implementation:**
1. Define wave targets (percentage gaps, file lists, durations)
2. Execute Wave 1, enforce quality gates (70% threshold for new code, diff coverage)
3. Measure coverage, update trends in quality_metrics.json
4. Adjust Wave 2 targets based on Wave 1 learnings
5. Repeat until 70% achieved

**See also:** Phase 258 quality-gate-config.yml (progressive thresholds), Phase 266 report (gap analysis)

---

### Strategy 3: Property-Based Testing Integration (Complementary)

**What:** Use property tests to validate invariants across thousands of inputs, catching edge cases unit tests miss.

**When to use:** Critical business logic (financial calculations, data integrity, state management).

**Example (Backend - Phase 252):**
```
Property tests created: 96 tests, 100% pass rate
Invariants validated:
- Governance: Agent maturity checks, permission enforcement
- Episodes: Segment ordering, metadata consistency
- Database: Transaction atomicity, constraint validation
- LLM: API round-trips, response structure validation

Example invariant (test_state_update_immutability):
@given(st.integers(), st.text())
@settings(max_examples=100)
def test_state_update_immutability(initial_count, initial_name):
    """
    INVARIANT: State update should not mutate input state
    VALIDATED_BUG: Shallow copy caused reference sharing
    """
    state = {"count": initial_count, "name": initial_name}
    state_copy = copy.deepcopy(state)
    update_state(state, {"count": initial_count + 1})
    assert state == state_copy  # Original unchanged
```

**Pros:**
- Finds edge cases (null, empty, large numbers, Unicode)
- Validates invariants across thousands of inputs
- Documents system behavior through invariants
- Catches bugs unit tests miss (off-by-one, boundary conditions)

**Cons:**
- Slower than unit tests (100+ examples per test)
- Requires invariant identification (not all code has clear invariants)
- Debugging failures can be complex (shrunk counterexamples)

**Implementation:**
1. Identify invariants (from docs/testing/property-testing.md INVARIANTS.md)
2. Write property test with Hypothesis (backend) or FastCheck (frontend)
3. Set max_examples based on test speed (50-200)
4. Run continuously, investigate failures
5. Document VALIDATED_BUG findings in docstrings

**See also:** docs/testing/property-testing.md (1,413 lines), Phase 252 verification (96 property tests)

---

### Strategy 4: AI-Assisted Test Generation (Evaluate for Wave 2+)

**What:** Use AI tools (Cover-Agent, CoverUp) to generate baseline tests automatically.

**When to use:** Zero-coverage files with clear interfaces (no complex business logic).

**Example (Phase 8.5 research):**
```bash
# Install Cover-Agent
pip install cover-agent

# Generate tests for zero-coverage file
cover-agent \
  --source-file=core/workflow_analytics_endpoints.py \
  --test-file=tests/unit/test_workflow_analytics_endpoints.py \
  --coverage-report=tests/coverage_reports/metrics/coverage.json \
  --test-cmd="pytest tests/unit/test_workflow_analytics_endpoints.py -v" \
  --max-iterations=10

# Review generated tests, adjust as needed
# Run coverage to verify increase
pytest tests/unit/test_workflow_analytics_endpoints.py \
  --cov=core/workflow_analytics_endpoints.py \
  --cov-report=term-missing
```

**Pros:**
- 10x faster baseline creation (minutes vs. hours)
- Targets uncovered lines automatically
- Reduces repetitive test writing

**Cons:**
- Quality varies (may miss edge cases, over-mock)
- Requires manual review and adjustment
- Efficacy on complex business logic unvalidated

**Implementation:**
1. Select zero-coverage file with simple interface (DTOs, utilities)
2. Run Cover-Agent with coverage report
3. Review generated tests (check assertions, mocking)
4. Add edge cases, fix over-mocked dependencies
5. Re-run coverage, verify increase
6. If effective, scale to similar files; if not, revert to manual

**See also:** Phase 8.5 RESEARCH.md "AI-Assisted Test Generation" section

---

## Quality Gates (Table Stakes + Differentiators)

### Gate 1: Coverage Threshold Enforcement (✅ IMPLEMENTED)

**What:** CI/CD blocks PRs if coverage below threshold (70% baseline, progressive to 80%).

**Status:** ✅ DONE (Phase 258)
- `.github/workflows/quality-gate.yml` enforces 70% threshold
- Progressive: 70% → 75% (2026-05-01) → 80% (2026-06-01)
- Backend and frontend enforced separately
- Exits with error code if below threshold
- Posts PR comments with coverage results

**Configuration:**
```yaml
# .github/quality-gate-config.yml
coverage_thresholds:
  backend:
    phase_1: 70  # 2026-04-13 to 2026-04-30
    phase_2: 75  # 2026-05-01 to 2026-05-31
    phase_3: 80  # 2026-06-01 onwards
  frontend:
    phase_1: 70
    phase_2: 75
    phase_3: 80
```

**See also:** Phase 258 verification (QUAL-01, QUAL-02, QUAL-03 satisfied)

---

### Gate 2: 100% Test Pass Rate Enforcement (✅ IMPLEMENTED)

**What:** CI/CD blocks PRs if any test fails (all tests must pass before merge).

**Status:** ✅ DONE (Phase 258)
- Quality gate runs pytest (backend) and vitest (frontend)
- Build fails if any test fails (exit code 1)
- `test_pass_rate.required: 100` with `enforcement: block`

**Rationale:** Prevents broken tests from entering main branch; maintains trust in test suite.

**See also:** Phase 258 verification (QUAL-02 satisfied)

---

### Gate 3: Build Gate (✅ IMPLEMENTED)

**What:** CI/CD prevents merging if build fails (tests, coverage, linting).

**Status:** ✅ DONE (Phase 258)
- `build_gates.block_on_failure: true`
- Quality gate job runs after backend-tests and frontend-tests
- Blocks merge if coverage below threshold or tests fail

**Rationale:** Enforces quality standards before code integration; prevents broken builds.

**See also:** Phase 258 verification (QUAL-03 satisfied)

---

### Gate 4: Diff Coverage Enforcement (⚠️ CONFIGURED, UNCLEAR ENFORCEMENT)

**What:** Prevents PRs from dropping coverage (focus on new code, not historical debt).

**Status:** ⚠️ PARTIAL (diff-cover available, enforcement unclear)
- Phase 8.5 research mentioned diff-cover for PR coverage enforcement
- Phase 258 verification did not confirm diff-cover integration
- May need configuration update

**Expected behavior:**
```bash
# Check PR coverage diff
diff-cover coverage.json --compare-branch=origin/main --fail-under=70
```

**Rationale:** Prevents coverage regression in new code; allows historical debt to be addressed incrementally.

**Action item:** Verify diff-cover enforcement in quality-gate.yml, add if missing.

---

### Gate 5: Emergency Bypass (✅ IMPLEMENTED)

**What:** Temporary mechanism to disable gates for critical fixes (prevents gate from blocking urgent work).

**Status:** ✅ DONE (Phase 258)
- `EMERGENCY_BYPASS` environment variable
- Allows gate bypass when set to `true`
- Documented in quality gate config

**Usage:**
```yaml
# .github/workflows/quality-gate.yml
- name: Enforce Coverage Threshold
  if: env.EMERGENCY_BYPASS != 'true'
  run: |
    python .github/scripts/enforce-coverage.py
```

**Rationale:** Rarely needed, but prevents gate from being a blocker in emergencies. Use sparingly, document reasons.

---

## Measurement Tools (Table Stakes)

### Tool 1: pytest-cov (Backend) ✅

**What:** pytest plugin for coverage.py integration, generates HTML/JSON reports.

**Version:** 4.1+
**Status:** ✅ CONFIGURED (backend/.coverage-rc)
- Measures line and branch coverage
- Generates HTML reports (htmlcov/)
- Generates JSON reports (coverage.json)
- Integrates with pytest (single command: `pytest --cov`)

**Usage:**
```bash
# Measure backend coverage
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html --cov-report=json

# View missing lines
pytest tests/unit/test_workflow_engine.py --cov=core/workflow_engine.py --cov-report=term-missing

# Output shows exact missing lines:
# core/workflow_engine.py:456: line 456 not covered
# core/workflow_engine.py:478: line 478 not covered
```

**Configuration:**
```ini
# backend/.coverage-rc
[run]
source = core, api, tools
omit =
    tests/*
    */migrations/*
    */__pycache__/*
    venv/*

[report]
branch = true  # Enable branch coverage
precision = 2  # 2 decimal places
```

**See also:** Phase 8.5 RESEARCH.md "Standard Stack" section

---

### Tool 2: nyc (Istanbul) (Frontend) ✅

**What:** JavaScript/TypeScript coverage tool, integrates with Jest/vitest.

**Version:** Latest (npm package)
**Status:** ✅ CONFIGURED (frontend-nextjs/.coverage-rc)
- Measures line, branch, function, statement coverage
- Generates HTML reports (coverage/)
- Integrates with vitest (`npm run test:coverage`)

**Usage:**
```bash
# Measure frontend coverage
npm run test:coverage

# View HTML report
open coverage/index.html

# Exclude files from coverage
# frontend-nextjs/.coverage-rc
{
  "exclude": [
    "**/*.d.ts",
    "**/*.stories.tsx",
    "node_modules/"
  ],
  "threshold": {
    "global": {
      "lines": 70,
      "branches": 70,
      "functions": 70,
      "statements": 70
    }
  }
}
```

**See also:** Phase 254 verification (frontend baseline 14.61%)

---

### Tool 3: Hypothesis (Property-Based Testing) ✅

**What:** Python property-based testing framework, generates thousands of inputs.

**Version:** 6.151.5
**Status:** ✅ CONFIGURED (96 property tests, 100% pass rate)
- Finds edge cases unit tests miss
- Shrinks failures to minimal counterexamples
- Validates invariants (immutability, round-trip, idempotency)

**Usage:**
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@given(st.integers(), st.text())
@settings(max_examples=100)
def test_state_update_immutability(initial_count, initial_name):
    """
    INVARIANT: State update should not mutate input state
    """
    state = {"count": initial_count, "name": initial_name}
    state_copy = copy.deepcopy(state)
    update_state(state, {"count": initial_count + 1})
    assert state == state_copy  # Original unchanged
```

**Best practices:**
- Set `max_examples` based on test speed (50-200)
- Use deterministic seeds for reproducibility (`@settings(seed=12345)`)
- Document invariants in docstrings
- Add VALIDATED_BUG section when bugs found

**See also:** docs/testing/property-testing.md (1,413 lines), Phase 252 verification

---

### Tool 4: quality_metrics.json (Trend Tracking) ✅

**What:** JSON file storing historical coverage data, trend indicators, gap analysis.

**Version:** Custom script (`.github/scripts/calculate-quality-metrics.py`)
**Status:** ✅ IMPLEMENTED (Phase 258)
- Maintains 30-day history
- Calculates trends (↑↓→ indicators)
- Computes gaps to target
- Generates dashboard from JSON

**Schema:**
```json
{
  "last_updated": "2026-04-12T23:30:00Z",
  "backend": {
    "coverage_percent": 18.25,
    "lines_covered": 6179,
    "total_lines": 33861,
    "gap_to_target": 51.75,
    "trend": "↑ 2.3pp",
    "history": [
      {"date": "2026-04-01", "coverage": 15.95},
      {"date": "2026-04-08", "coverage": 17.13},
      {"date": "2026-04-12", "coverage": 18.25}
    ]
  },
  "frontend": {
    "coverage_percent": 14.61,
    "lines_covered": 12450,
    "total_lines": 85195,
    "gap_to_target": 55.39,
    "trend": "→ 0.0pp",
    "history": [...]
  }
}
```

**Usage:**
```bash
# Update metrics (run by quality-metrics.yml workflow)
python .github/scripts/calculate-quality-metrics.py

# Generate dashboard
python .github/scripts/generate-dashboard.py

# View dashboard
cat docs/testing/QUALITY_DASHBOARD.md
```

**See also:** Phase 258 verification (quality_metrics.json verified, dashboard generated)

---

## Complexity Assessment

| Feature | Complexity | Reasoning |
|---------|------------|-----------|
| **Baseline measurement** | Low | Tooling exists (pytest-cov, nyc), automated execution |
| **Coverage report generation** | Low | Built-in to pytest-cov/nyc, HTML/JSON output |
| **High-impact file identification** | Medium | Requires parsing coverage.json, filtering, sorting (but scriptable) |
| **Quality gate enforcement** | Medium | CI/CD integration (GitHub Actions), threshold configuration, enforcement logic |
| **Test infrastructure unblocking** | High | Diverse root causes (syntax errors, missing models, imports), requires investigation |
| **Coverage trend tracking** | Low | JSON storage, Python script for calculation (already implemented) |
| **Property-based testing integration** | High | Requires invariant identification, strategy composition, test debugging |
| **Branch coverage measurement** | Low | Enable in pytest-cov config (`branch = true`), automatic measurement |
| **AI-assisted test generation** | Medium | Tool setup, prompt engineering, result validation, manual adjustment |
| **Wave-based expansion strategy** | Medium | Upfront planning (wave definitions, file lists), execution management |
| **Mutation testing** | High | New tool (mutmut), test execution time increases, weak test identification |
| **Diff coverage enforcement** | Medium | diff-cover integration, PR comparison, threshold configuration |
| **Flaky test detection** | Medium | pytest-rerunfailures configuration, SQLite quarantine, monitoring |

**Overall complexity:** MEDIUM (6/13 features high complexity, 5/13 medium, 2/13 low)

**v11.0 focus:** Low-Medium complexity features (baseline, reports, high-impact identification, quality gates, wave execution). Defer High complexity (mutation testing, AI generation) to v11.1+.

---

## Roadmap Implications

Based on research, suggested phase structure for v11.0:

### Phase 250 (Replay): Frontend Test Fixes
- **Addresses:** 1,504 failing tests (28.8% failure rate → 100% pass rate)
- **Avoids:** Coverage expansion on broken test suite (inaccurate measurement)
- **Dependencies:** None (unblocks all frontend work)
- **Duration:** 1 week
- **Complexity:** High (many failures, diverse root causes)
- **Expected outcome:** Frontend tests passing, accurate coverage measurement possible

### Phase 251 (Replay): Backend Coverage Baseline
- **Addresses:** Confirm backend baseline (18.25%), identify high-impact files
- **Avoids:** Wasting time on low-value files (small utilities)
- **Dependencies:** None (baseline already measured in Phase 251, verify current state)
- **Duration:** 2-3 days
- **Complexity:** Low (tooling exists, parsing coverage.json)
- **Expected outcome:** High-impact file list (>200 lines, <10% coverage), confirmed baseline

### Phase 252 (Replay): Backend Property Tests
- **Addresses:** Maintain 96 property tests (100% pass rate), expand invariants
- **Avoids:** Weak unit tests (execute code but don't validate invariants)
- **Dependencies:** Phase 251 (need baseline to identify gaps)
- **Duration:** 3-5 days
- **Complexity:** High (invariant identification, strategy composition)
- **Expected outcome:** +10-20 property tests, coverage increase from invariants validated

### Phase 253b (Replay): Backend Coverage Wave 1
- **Addresses:** Backend 18.25% → 30% (+11.75pp, ~10,600 lines)
- **Targets:** High-impact files (>200 lines, <10% coverage)
- **Files:** fleet_admiral.py (0%, 856 lines), atom_meta_agent.py (0%, 645 lines), queen_agent.py (0%, 523 lines), agent_routes.py (2.1%), workflow_routes.py (3.4%)
- **Dependencies:** Phase 251 (high-impact file list), Phase 252 (property tests for invariants)
- **Duration:** 1 week
- **Complexity:** Medium (large files, but clear gaps)
- **Expected outcome:** Backend coverage 30%, quality gates passing

### Phase 254 (Replay): Frontend Coverage Baseline
- **Addresses:** Confirm frontend baseline (14.61%), identify high-impact files
- **Avoids:** Wasting time on low-value components
- **Dependencies:** Phase 250 (frontend tests passing)
- **Duration:** 2-3 days
- **Complexity:** Low (tooling exists, parsing coverage.json)
- **Expected outcome:** Frontend high-impact file list, confirmed baseline

### Phase 255 (Replay): Frontend Coverage Wave 1
- **Addresses:** Frontend 14.61% → 30% (+15.39pp, ~13,100 lines)
- **Targets:** High-impact components (>200 lines, <10% coverage), auth, agents, workflows, canvas
- **Dependencies:** Phase 254 (high-impact file list), Phase 250 (tests passing)
- **Duration:** 1 week
- **Complexity:** Medium (component testing, mocking, integration)
- **Expected outcome:** Frontend coverage 30%, quality gates passing

### Phase 256 (Replay): Frontend Coverage Wave 2
- **Addresses:** Frontend 30% → 50% (+20pp, ~17,000 lines)
- **Targets:** API routes, state management (useCanvasState, reducers), hooks, utilities
- **Dependencies:** Phase 255 (Wave 1 complete)
- **Duration:** 1 week
- **Complexity:** Medium (broader coverage, edge cases)
- **Expected outcome:** Frontend coverage 50%

### Phase 257: TDD & Property Test Documentation (✅ DONE)
- **Addresses:** Document TDD workflow, property test patterns
- **Status:** ✅ COMPLETE (Phase 258 verification: 1,377 lines of QA docs)
- **Skip:** Already done

### Phase 258: Quality Gates & Final Documentation (✅ DONE)
- **Addresses:** Quality gate enforcement, metrics dashboard, documentation
- **Status:** ✅ COMPLETE (Phase 258 verification: all requirements satisfied)
- **Skip:** Already done

### Phase 259 (New): Backend Coverage Wave 2
- **Addresses:** Backend 30% → 50% (+20pp, ~18,100 lines)
- **Targets:** API routes (100+ endpoints), governance, canvas, LLM service
- **Dependencies:** Phase 253b (Wave 1 complete)
- **Duration:** 1 week
- **Complexity:** Medium (API integration testing, mocking)
- **Expected outcome:** Backend coverage 50%

### Phase 260 (New): Frontend Coverage Wave 3
- **Addresses:** Frontend 50% → 70% (+20pp, ~17,000 lines)
- **Targets:** Remaining gaps, edge cases, error paths, integration tests
- **Dependencies:** Phase 256 (Wave 2 complete)
- **Duration:** 1 week
- **Complexity:** Medium-High (edge cases, error handling)
- **Expected outcome:** Frontend coverage 70% ✅ TARGET ACHIEVED

### Phase 261 (New): Backend Coverage Wave 3
- **Addresses:** Backend 50% → 70% (+20pp, ~18,100 lines)
- **Targets:** Core services, episodic memory, workflow engine, tools
- **Dependencies:** Phase 259 (Wave 2 complete)
- **Duration:** 1 week
- **Complexity:** Medium-High (complex business logic, integration)
- **Expected outcome:** Backend coverage 70% ✅ TARGET ACHIEVED

### Phase 262 (New): Verification & Documentation
- **Addresses:** Final verification, trend analysis, documentation updates
- **Targets:** Confirm 70% backend/frontend, update QUALITY_DASHBOARD.md, document lessons learned
- **Dependencies:** Phase 260 (frontend 70%), Phase 261 (backend 70%)
- **Duration:** 2-3 days
- **Complexity:** Low (verification, reporting)
- **Expected outcome:** v11.0 complete, 70% coverage achieved, documentation updated

**Phase ordering rationale:**
1. **Fix tests first** (Phase 250) - Cannot measure coverage accurately if tests fail
2. **Measure baselines** (Phase 251, 254) - Identify high-impact files, establish starting point
3. **Property tests** (Phase 252) - Validate invariants before coverage expansion (catch design flaws early)
4. **Wave 1 parallel** (Phase 253b, 255) - Backend and frontend can run in parallel (different teams, different files)
5. **Wave 2 parallel** (Phase 259, 256) - Continue expansion, maintain momentum
6. **Wave 3 parallel** (Phase 261, 260) - Final push to 70% target
7. **Verification** (Phase 262) - Confirm targets, document results, celebrate success

**Research flags for phases:**
- **Phase 250 (frontend test fixes):** Needs deeper research into failure root causes (syntax errors, missing models, Pydantic v2 migration, import errors)
- **Phase 252 (property tests):** Standard patterns established (docs/testing/property-testing.md), unlikely to need research
- **Phase 253b, 255-261 (coverage waves):** Standard execution (write tests, measure coverage, enforce gates), unlikely to need research

**Estimated timeline:** 8-10 weeks (including parallel waves, assuming 2-3 phases can run simultaneously)
- **Critical path:** 250 → 251 → 253b → 259 → 261 → 262 (backend: ~6 weeks)
- **Frontend path:** 250 → 254 → 255 → 256 → 260 (parallel with backend, ~5 weeks)
- **Buffer:** 1-2 weeks for unexpected issues (test infrastructure blockers, integration complexity)
- **Stretch goal:** Complete in 6-7 weeks with aggressive parallelization

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | HIGH | pytest-cov, nyc, Hypothesis are industry standards, verified in Phase 258 |
| **Coverage Strategies** | HIGH | Based on Phase 8.5 research (comprehensive), Phase 266 report (proven results) |
| **Quality Gates** | HIGH | Phase 258 verified all requirements satisfied (6/6), infrastructure production-ready |
| **Property Testing** | HIGH | 1,413-line guide, 96 tests with 100% pass rate, patterns established |
| **Frontend Coverage** | MEDIUM | Baseline measured (14.61%), but high-impact file identification less clear than backend |
| **AI Test Generation** | MEDIUM | Tools verified (Cover-Agent, CoverUp), but efficacy on complex business logic unvalidated |
| **Mutation Testing** | MEDIUM | mutmut available, but not implemented; Phase 8.5 research noted as "future enhancement" |
| **Wave-Based Execution** | HIGH | Strategy based on Phase 266 success (doubled coverage from 8.5% to 17.13%) |

**Overall confidence:** HIGH (based on existing research, verified infrastructure, proven strategies)

**Gaps to Address:**
1. **Frontend high-impact file list** - Phase 254 identified baseline (14.61%), but need clearer zero-coverage file prioritization (backend has 77 zero-coverage files, frontend less clear)
2. **AI test generation efficacy** - Cover-Agent evaluation needed (test on simple files first, measure quality vs. manual approach)
3. **Test infrastructure blockers** - Phase 266 unblocked 900+ tests with schema migration, but 300+ still blocked by import errors (google_calendar_service, asana_real_service, microsoft365_service)
4. **Branch coverage focus** - Currently 3.87% branch coverage (vs. 17.13% line coverage); need explicit branch testing strategy (write tests for both true/false branches)

---

## Sources

### Primary (HIGH confidence)

- **Phase 8.5 RESEARCH.md** - Comprehensive Python test coverage research (556 lines)
  - Coverage: pytest-cov, coverage.py, Hypothesis, AI test generation (Cover-Agent, CoverUp)
  - Patterns: Unit test structure, FastAPI testing, async service testing, coverage-driven generation
  - Pitfalls: Starting with low-value files, testing without targets, ignoring branch coverage
  - File: `/Users/rushiparikh/projects/atom/.planning/phases/08.5-coverage-expansion/08.5-coverage-expansion-RESEARCH.md`

- **Phase 258 VERIFICATION.md** - Quality gates and documentation verification
  - Coverage: Quality infrastructure (gates, metrics, dashboard), progressive thresholds (70% → 75% → 80%)
  - Requirements satisfied: 6/6 (QUAL-01 through QUAL-04, DOC-03, DOC-04)
  - Artifacts: 17 files (5 config, 6 scripts, 5 docs, 1 workflow), 1,377 lines of QA docs
  - Status: ✅ PASSED, production-ready
  - File: `/Users/rushiparikh/projects/atom/.planning/phases/258-quality-gates-final-documentation/258-VERIFICATION.md`

- **Phase 266 Final Coverage Report** - Backend coverage 17.13% (doubled from 8.5%)
  - Coverage: Schema migration unblocking, coverage doubling, gap analysis to 80%
  - High-impact files: fleet_admiral.py (0%, 856 lines), atom_meta_agent.py (0%, 645 lines), queen_agent.py (0%, 523 lines)
  - Remaining blockers: Import errors (300+ tests), missing models (200+ tests), Pydantic v2 migration (150+ tests)
  - File: `/Users/rushiparikh/projects/atom/backend/tests/coverage_reports/266_final_coverage_report.md`

- **Property Testing Patterns Guide** - 1,413-line comprehensive guide
  - Coverage: 12 patterns (invariant-first, state machine, round-trip, generator composition, idempotency, boundary values, associative/commutative, algebraic properties, compression, normalization, parallel execution, resource management)
  - Frameworks: Hypothesis (Python), FastCheck (TypeScript), proptest (Rust)
  - Best practices: VALIDATED_BUG documentation, deterministic seeds, numRuns tuning, test isolation, generator customization, error message quality
  - File: `/Users/rushiparikh/projects/atom/docs/testing/property-testing.md`

### Secondary (MEDIUM confidence)

- **Milestone v10.0 Audit Report** - Requirements gaps analysis
  - Coverage: 12/15 phases verified (80%), 4/15 have VERIFICATION.md (27%)
  - Requirements: 25/36 satisfied (69%), 8/36 partial (22%), 3/36 unsatisfied (8%)
  - Gaps: Missing VERIFICATION.md for 11 phases, requirements checkboxes outdated
  - File: `/Users/rushiparikh/projects/atom/.planning/MILESTONE-v10.0-AUDIT.md`

- **PROJECT.md** - Current state and v11.0 goals
  - Coverage: v11.0 targets (70% backend/frontend, fix 1,504 failing tests, high-impact file prioritization)
  - Strategy: Frontend test fixes first, backend coverage waves, frontend coverage expansion, pragmatic 70% targets
  - Success metrics: 100% test pass rate, 70% coverage (backend + frontend), quality gates maintained
  - File: `/Users/rushiparikh/projects/atom/.planning/PROJECT.md`

### Tertiary (LOW confidence)

- **Industry Standards for Coverage Targets** - Based on training knowledge (web search unavailable due to rate limits)
  - Google: 60% acceptable, 80% excellent
  - Enterprise: 75-80% typical target
  - 100%: Counterproductive (diminishing returns, test maintenance burden)
  - **Note:** Verify with current sources when web search available (rate limit resets 2026-05-01)

- **Coverage Expansion Best Practices** - Based on Phase 8.5 research and training knowledge
  - Prioritize high-impact files (>200 lines, <10% coverage)
  - Use wave-based expansion (5-10pp per wave)
  - Enforce quality gates throughout (prevent regression)
  - Combine unit tests with property tests (invariants + edge cases)
  - **Note:** Strategies validated by Phase 266 success (doubled coverage), but industry best practices should be verified when web search available

---

**Document Version:** 1.0
**Last Updated:** 2026-04-13
**Maintainer:** v11.0 Research Team

**For questions or updates, see:** `.planning/research/STACK.md` (technology stack), `.planning/research/ARCHITECTURE.md` (architecture patterns), `.planning/research/PITFALLS.md` (domain pitfalls)
