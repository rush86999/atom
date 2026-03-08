# Architecture Patterns for Coverage Expansion to 80%

**Domain:** Cross-platform test coverage expansion (backend, frontend, mobile, desktop)
**Researched:** March 7, 2026
**Overall Confidence:** HIGH

## Executive Summary

Atom has a sophisticated cross-platform test infrastructure with unified coverage aggregation, quality gate enforcement, coverage trending, and flaky test detection. The architecture for expanding coverage to 80% builds on existing infrastructure: cross-platform aggregation (`cross_platform_coverage_gate.py`), unified test workflows (`unified-tests.yml`), coverage trending (`coverage_trend_analyzer.py`), and property testing (Hypothesis, FastCheck, proptest). The expansion strategy focuses on incremental coverage tracking, coverage-driven development workflows, test prioritization by business impact, and integration with existing quality gates.

**Current Coverage State:**
- **Backend:** 74.55% → Target: 80% (gap: 5.45%, ~11 lines)
- **Frontend:** 21.96% → Target: 80% (gap: 58.04%, ~4,391 lines)
- **Mobile:** 0% → Target: 50% (gap: 50%, ~3,169 lines)
- **Desktop:** 0% → Target: 40% (gap: 40%, TBD lines)

**Key architectural insight:** Coverage expansion is not a separate initiative but an enhancement to existing test infrastructure. New components (coverage gap analysis, test generators, coverage prioritization) integrate with existing workflows (unified-tests-parallel.yml, coverage-trending.yml, platform-retry.yml) through artifact passing, JSON report aggregation, and quality gate enforcement.

---

## Existing Infrastructure Overview

### Test Organization

```
atom/
├── backend/
│   ├── tests/
│   │   ├── unit/              # Unit tests (fast, isolated)
│   │   ├── integration/       # Integration tests (slower, dependencies)
│   │   ├── property/          # Property-based tests (Hypothesis)
│   │   └── e2e_ui/tests/      # E2E UI tests (Playwright)
│   └── pytest.ini             # Pytest configuration (80% fail_under)
├── frontend-nextjs/
│   ├── __tests__/             # Jest tests (per-module thresholds)
│   ├── components/__tests__/  # Component tests
│   └── jest.config.js         # Jest configuration (80% global threshold)
├── mobile/
│   ├── src/__tests__/         # jest-expo tests (60% threshold)
│   └── jest.config.js
├── frontend-nextjs/src-tauri/
│   ├── tests/                 # Rust tests (cargo test)
│   └── coverage/              # Tarpaulin coverage reports
└── .github/workflows/
    ├── unified-tests.yml              # Sequential platform jobs
    ├── unified-tests-parallel.yml     # Matrix-based parallel jobs (Phase 149)
    ├── platform-retry.yml             # Failed test retry logic
    ├── coverage-trending.yml          # Coverage trending automation
    └── frontend-module-coverage.yml   # Per-module enforcement
```

### Coverage Measurement and Reporting

**Backend (pytest):**
- **Measurement:** pytest-cov with coverage.py
- **Report format:** JSON (`coverage.json` with totals, files, branch coverage)
- **Threshold:** 80% line coverage, 70% branch coverage (pytest.ini)
- **Command:** `pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json`

**Frontend (Jest):**
- **Measurement:** Jest built-in coverage with Istanbul
- **Report format:** JSON (`coverage-final.json` with statement/branch/function/line counts)
- **Threshold:** 80% global line coverage, per-module thresholds (75-90%)
- **Command:** `npm run test:ci -- --coverage --coverageReporters=json`

**Mobile (jest-expo):**
- **Measurement:** jest-expo with same Istanbul format
- **Report format:** JSON (`coverage-final.json`)
- **Threshold:** 60% global (needs upgrade to 50% target, eventually 80%)
- **Command:** `npm test -- --coverage`

**Desktop (Tauri/cargo-tarpaulin):**
- **Measurement:** cargo-tarpaulin for Rust coverage
- **Report format:** JSON (`coverage.json`)
- **Threshold:** No formal threshold (needs 40% target)
- **Command:** `cargo tarpaulin --out Json`

**Cross-Platform Aggregation:**
- **Script:** `backend/tests/scripts/aggregate_coverage.py`
- **Output:** Unified coverage JSON with per-platform breakdown
- **Metrics:** Line coverage, branch coverage, weighted overall score
- **Usage:** CI/CD quality gate enforcement, PR comments

### Incremental Coverage Tracking

**Current Infrastructure:**
- Coverage trending: `backend/tests/scripts/coverage_trend_analyzer.py`
- Historical tracking: `backend/tests/coverage_reports/metrics/cross_platform_trend.json`
- Trend visualization: `backend/tests/scripts/generate_coverage_dashboard.py` (HTML)
- Commit tracking: `backend/tests/scripts/update_cross_platform_trending.py`

**Tracking Schema:**
```json
{
  "timestamp": "2026-03-06T20:02:55Z",
  "platforms": {
    "backend": {"coverage_pct": 74.55, "covered": 156, "total": 205},
    "frontend": {"coverage_pct": 21.96, "covered": 1662, "total": 7569},
    "mobile": {"coverage_pct": 0.0, "covered": 0, "total": 6338},
    "desktop": {"coverage_pct": 0.0, "covered": 0, "total": 0}
  },
  "thresholds": {
    "backend": 70.0,
    "frontend": 80.0,
    "mobile": 50.0,
    "desktop": 40.0
  },
  "weighted": {
    "overall_pct": 34.88,
    "platform_breakdown": [
      {"platform": "backend", "coverage_pct": 74.55, "weight": 0.35, "contribution": 26.09}
    ]
  }
}
```

---

## Recommended Architecture

### Component 1: Coverage Gap Analysis Tool

**Purpose:** Identify untested code, prioritize by business impact, generate test recommendations

**File:** `backend/tests/scripts/coverage_gap_analysis.py` (NEW)

**Integration Points:**
- **Input:** Platform coverage JSON files (pytest, Jest, tarpaulin)
- **Output:** `coverage_priorities.json` (ranked files by impact)
- **Downstream:** Test prioritization workflow, coverage expansion phases

**Schema:**
```json
{
  "timestamp": "2026-03-07T12:00:00Z",
  "platform": "backend",
  "overall_coverage": 74.55,
  "target_coverage": 80.0,
  "gap_lines": 11,
  "prioritized_files": [
    {
      "file": "core/agent_governance_service.py",
      "coverage_pct": 65.0,
      "uncovered_lines": 50,
      "business_impact": "critical",
      "complexity": "high",
      "test_priority": 1,
      "estimated_effort": "4h",
      "suggested_tests": [
        "test_agent_governance_maturity_enforcement",
        "test_agent_governance_permission_check",
        "test_agent_governance_audit_trail"
      ]
    }
  ]
}
```

**Algorithms:**
1. **Business impact scoring:** Based on file location (core/ > api/ > tools/), function names (security/critical paths), dependency depth (files imported by many others)
2. **Complexity estimation:** Cyclomatic complexity from AST analysis, uncovered branch count
3. **Test priority ranking:** Weighted score = (business_impact × 0.5) + (coverage_gap × 0.3) + (complexity × 0.2)
4. **Effort estimation:** Historical test write times from previous phases, linear regression based on uncovered lines

### Component 2: Test Generator CLI

**Purpose:** Generate test stubs for uncovered code, scaffold test files, provide testing patterns

**File:** `backend/tests/scripts/generate_test_stubs.py` (NEW)

**Integration Points:**
- **Input:** `coverage_priorities.json` (from gap analysis)
- **Output:** Test file stubs with placeholders for assertions
- **Downstream:** Developer workflow, manual test completion

**Example Usage:**
```bash
# Generate tests for top 10 priority files
python backend/tests/scripts/generate_test_stubs.py \
  --priorities backend/tests/coverage_reports/metrics/coverage_priorities.json \
  --top-n 10 \
  --output backend/tests/generated/

# Generate tests for specific file
python backend/tests/scripts/generate_test_stubs.py \
  --file core/agent_governance_service.py \
  --output backend/tests/unit/test_agent_governance_generated.py
```

**Generated Test Template:**
```python
"""
Auto-generated test stub for core/agent_governance_service.py

Generated: 2026-03-07T12:00:00Z
Coverage gap: 50 lines (35% uncovered)
Business impact: critical
Estimated effort: 4h

TODO: Implement test assertions and mock setup
"""

import pytest
from core.agent_governance_service import AgentGovernanceService


class TestAgentGovernanceServiceGenerated:
    """Auto-generated tests for agent_governance_service.py"""

    def test_agent_governance_maturity_enforcement(self):
        """
        Test maturity-based enforcement for agent actions

        Uncovered lines: 120-145 (25 lines)
        Branches: 2 uncovered (maturity checks for STUDENT/INTERN levels)

        TODO:
        - Setup: Create agent with STUDENT maturity
        - Execute: Trigger action requiring INTERN+ maturity
        - Assert: Action blocked, audit trail created
        """
        # Test implementation needed
        pass

    def test_agent_governance_permission_check(self):
        """
        Test permission checks for agent operations

        Uncovered lines: 150-175 (25 lines)
        Branches: 3 uncovered (permission levels, resource types)

        TODO:
        - Setup: Create agent with AUTONOMOUS maturity
        - Execute: Request access to protected resource
        - Assert: Permission granted/denied based on policy
        """
        # Test implementation needed
        pass
```

**Testing Patterns Library:**
- **Backend:** Pytest fixtures, async test patterns, database mocks, LLM mocking
- **Frontend:** React Testing Library patterns, hook testing, form testing
- **Mobile:** React Native Testing Library, device mocking, platform-specific tests
- **Desktop:** Tauri IPC testing, Rust unit test patterns

### Component 3: Coverage-Driven Development Workflow

**Purpose:** Integrate coverage expansion into daily development workflow, provide real-time feedback

**File:** `scripts/coverage_driven_dev.sh` (NEW)

**Integration Points:**
- **Pre-commit:** Check coverage for modified files only (incremental)
- **Pre-push:** Ensure overall coverage doesn't decrease
- **CI/CD:** Quality gate enforcement (existing `cross_platform_coverage_gate.py`)

**Workflow:**
```bash
#!/bin/bash
# Coverage-driven development workflow

# Step 1: Identify modified files
MODIFIED_FILES=$(git diff --name-only main | grep -E '\.(py|ts|tsx|js|rs)$')

# Step 2: Run coverage for modified files only (incremental)
for file in $MODIFIED_FILES; do
  if [[ $file == *.py ]]; then
    pytest tests/ --cov=$file --cov-report=term-missing
  elif [[ $file == *.ts || $file == *.tsx || $file == *.js ]]; then
    npm test -- --coverage --testPathPattern=$file
  fi
done

# Step 3: Check coverage threshold for new code (80%)
python backend/tests/scripts/incremental_coverage_gate.py \
  --base-branch main \
  --min-new-coverage 80 \
  --strict

# Step 4: Generate test stubs if coverage below threshold
if [ $? -ne 0 ]; then
  echo "Coverage below threshold for new code. Generating test stubs..."
  python backend/tests/scripts/generate_test_stubs.py \
    --files $MODIFIED_FILES \
    --output tests/generated/
fi
```

**Incremental Coverage Gate:**
```python
# backend/tests/scripts/incremental_coverage_gate.py (NEW)
"""
Incremental coverage gate for new/modified code.

Enforces 80% coverage threshold on new code while preventing
overall coverage regression.

Usage:
    python incremental_coverage_gate.py --base-branch main --min-new-coverage 80
"""
import argparse
import subprocess
from pathlib import Path

def get_diff_files(base_branch: str) -> list[str]:
    """Get list of modified files compared to base branch."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_branch}...HEAD"],
        capture_output=True,
        text=True
    )
    return [f for f in result.stdout.strip().split('\n') if f]

def check_new_code_coverage(
    modified_files: list[str],
    min_coverage: float
) -> tuple[bool, float]:
    """
    Check coverage for new/modified code only.

    Returns:
        (passed, actual_coverage)
    """
    # Run coverage with diff filter (git-diff coverage plugin)
    # Backend: pytest --cov=core --cov-context=lib
    # Frontend: jest --coverage --collectCoverageFrom="src/**/*.{ts,tsx}"
    # Implementation depends on coverage tool capabilities
    pass

def check_overall_coverage_regression() -> bool:
    """
    Check if overall coverage decreased compared to base branch.

    Returns:
        False if coverage decreased (regression detected)
    """
    # Load base branch coverage from git
    # Compare with current coverage
    # Return True if current >= base
    pass
```

### Component 4: Test Prioritization Service

**Purpose:** Prioritize test expansion efforts by business impact, dependencies, and risk

**File:** `backend/tests/scripts/test_prioritization_service.py` (NEW)

**Integration Points:**
- **Input:** Coverage gap analysis, dependency graph (AST-based), historical failure rates
- **Output:** `test_expansion_roadmap.json` (phased plan with milestones)
- **Downstream:** Phase planning, resource allocation, sprint planning

**Prioritization Criteria:**
1. **Business Impact:** Critical user-facing features (agent execution, governance, episodic memory)
2. **Dependency Centrality:** Files imported by many other files (high fan-in)
3. **Risk Assessment:** Historical failure rates, security-sensitive code paths
4. **Effort-to-Value Ratio:** Quick wins (high impact, low effort) first

**Roadmap Schema:**
```json
{
  "timestamp": "2026-03-07T12:00:00Z",
  "target_coverage": 80.0,
  "current_coverage": 34.88,
  "phases": [
    {
      "phase": 1,
      "name": "Quick Wins (High Impact, Low Effort)",
      "target_coverage": 50.0,
      "estimated_effort": "2 weeks",
      "files": [
        {
          "file": "core/governance_cache.py",
          "coverage_pct": 60.0,
          "business_impact": "critical",
          "complexity": "low",
          "estimated_effort": "2h",
          "test_priority": 1
        }
      ]
    },
    {
      "phase": 2,
      "name": "Core Services (High Impact, Medium Effort)",
      "target_coverage": 65.0,
      "estimated_effort": "4 weeks",
      "files": [...]
    },
    {
      "phase": 3,
      "name": "Complex Services (High Impact, High Effort)",
      "target_coverage": 80.0,
      "estimated_effort": "8 weeks",
      "files": [...]
    }
  ]
}
```

### Component 5: Coverage Quality Gate Enhancement

**Purpose:** Enforce coverage expansion without blocking development, progressive rollout

**File:** `backend/tests/scripts/cross_platform_coverage_gate.py` (EXISTING - enhance)

**Enhancements:**
1. **Progressive thresholds:** Gradually increase thresholds (70% → 75% → 80%)
2. **New code enforcement:** Strict 80% threshold for new code
3. **Overall coverage guard:** Prevent regression (current coverage must not decrease)
4. **Graceful degradation:** Allow temporary decreases during refactoring (with approval)

**Enhanced CLI:**
```bash
# Existing: Check current thresholds
python backend/tests/scripts/cross_platform_coverage_gate.py --format json

# NEW: Progressive rollout (Phase 1: 70%, Phase 2: 75%, Phase 3: 80%)
python backend/tests/scripts/cross_platform_coverage_gate.py \
  --rollout-phase 2 \
  --format json

# NEW: New code enforcement (strict 80% for new code)
python backend/tests/scripts/cross_platform_coverage_gate.py \
  --new-code-only \
  --min-new-coverage 80 \
  --strict

# NEW: Regression prevention (current coverage >= baseline)
python backend/tests/scripts/cross_platform_coverage_gate.py \
  --baseline-branch main \
  --prevent-regression \
  --strict
```

**CI/CD Integration:**
```yaml
# .github/workflows/unified-tests-parallel.yml (ENHANCED)
aggregate-coverage:
  needs: [test-platform]
  runs-on: ubuntu-latest
  steps:
    - name: Download all coverage artifacts
      uses: actions/download-artifact@v4
      with:
        pattern: '*-coverage'

    - name: Check coverage quality gate
      run: |
        python backend/tests/scripts/cross_platform_coverage_gate.py \
          --rollout-phase ${{ github.ref == 'refs/heads/main' && 3 || 2 }} \
          --new-code-only \
          --min-new-coverage 80 \
          --prevent-regression \
          --baseline-branch main \
          --format json \
          --output-json backend/tests/coverage_reports/metrics/quality_gate_result.json

    - name: Upload quality gate result
      uses: actions/upload-artifact@v4
      with:
        name: quality-gate-result
        path: backend/tests/coverage_reports/metrics/quality_gate_result.json

    - name: Fail if quality gate not met
      if: github.ref == 'refs/heads/main'
      run: |
        python -c "
        import json
        with open('backend/tests/coverage_reports/metrics/quality_gate_result.json') as f:
          result = json.load(f)
        if not result['all_thresholds_passed']:
          print('Quality gate failed')
          exit(1)
        "
```

---

## Integration with Existing Infrastructure

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     Development Workflow                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Pre-commit: Incremental Coverage Check              │
│  • Run coverage on modified files only                           │
│  • Enforce 80% threshold for new code                            │
│  • Generate test stubs if below threshold                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Pre-push: Regression Check                   │
│  • Compare overall coverage to baseline branch                   │
│  • Prevent coverage decrease                                     │
│  • Warn if below progressive threshold (70%→75%→80%)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               CI/CD: Platform Test Execution                     │
│  • unified-tests-parallel.yml: Matrix-based parallel tests       │
│  • Generate coverage JSON for each platform                      │
│  • Upload coverage artifacts for aggregation                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│           CI/CD: Coverage Aggregation & Quality Gate              │
│  • aggregate_coverage.py: Combine platform coverage              │
│  • cross_platform_coverage_gate.py: Enforce thresholds           │
│  • update_cross_platform_trending.py: Track historical trends    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               CI/CD: Coverage Trending & Analysis                 │
│  • coverage-trending.yml: Automated trending on every push       │
│  • coverage_trend_analyzer.py: Detect regressions                │
│  • generate_coverage_dashboard.py: Visual trends (HTML)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PR Comments & Status Checks                   │
│  • Post coverage trend report with +/- indicators                │
│  • Show platform breakdown with gaps                             │
│  • Suggest remediation steps (test stubs, prioritized files)     │
└─────────────────────────────────────────────────────────────────┘
```

### New vs Modified Components

| Component | Status | Purpose | Integration |
|-----------|--------|---------|-------------|
| **coverage_gap_analysis.py** | NEW | Identify untested code, prioritize by impact | Input: Platform coverage JSON → Output: coverage_priorities.json |
| **generate_test_stubs.py** | NEW | Generate test file stubs for uncovered code | Input: coverage_priorities.json → Output: Test file templates |
| **incremental_coverage_gate.py** | NEW | Enforce coverage on new code only | Pre-commit hook, pre-push hook |
| **test_prioritization_service.py** | NEW | Generate phased expansion roadmap | Input: Gap analysis + dependency graph → Output: test_expansion_roadmap.json |
| **coverage_driven_dev.sh** | NEW | Developer workflow script | Pre-commit/pre-push integration |
| **aggregate_coverage.py** | EXISTING | Combine platform coverage JSON | CI/CD workflow (unified-tests-parallel.yml) |
| **cross_platform_coverage_gate.py** | ENHANCED | Enforce progressive thresholds, new code gate | CI/CD quality gate, PR comments |
| **update_cross_platform_trending.py** | EXISTING | Track historical coverage trends | CI/CD workflow (coverage-trending.yml) |
| **coverage_trend_analyzer.py** | EXISTING | Detect coverage regressions | CI/CD workflow (coverage-trending.yml) |
| **generate_coverage_dashboard.py** | EXISTING | Generate HTML trend dashboard | CI/CD workflow (coverage-trending.yml) |

### Build Order

**Phase 1: Infrastructure Enhancement (Week 1-2)**
1. Enhance `cross_platform_coverage_gate.py` with progressive thresholds
2. Create `incremental_coverage_gate.py` for new code enforcement
3. Integrate incremental gate into pre-commit hooks
4. Update CI/CD workflows with new quality gate checks

**Phase 2: Gap Analysis & Prioritization (Week 3-4)**
5. Create `coverage_gap_analysis.py` with business impact scoring
6. Create `test_prioritization_service.py` with roadmap generation
7. Run gap analysis on current codebase
8. Generate phased expansion roadmap (target: 80% overall)

**Phase 3: Test Generation & Tooling (Week 5-6)**
9. Create `generate_test_stubs.py` with testing patterns library
10. Create `coverage_driven_dev.sh` workflow script
11. Integrate test stub generation into pre-commit workflow
12. Document coverage-driven development workflow

**Phase 4: Execution & Monitoring (Week 7+)**
13. Execute phased roadmap (quick wins → core services → complex services)
14. Monitor coverage trends via dashboard (coverage-trending.yml)
15. Adjust priorities based on progress and business needs
16. Celebrate milestones (70% → 75% → 80%)

---

## Scalability Considerations

| Concern | At 100 Tests | At 1,000 Tests | At 10,000 Tests |
|---------|--------------|----------------|-----------------|
| **Test execution time** | <1 min | <5 min (pytest-xdist) | <15 min (parallel jobs + sharding) |
| **Coverage measurement** | <5s | <30s | <2 min |
| **Gap analysis** | <10s | <1 min | <5 min (AST caching) |
| **Test stub generation** | <5s | <30s | <3 min |
| **Trend data storage** | <1 KB | <10 KB | <100 KB (pruned to 30 days) |
| **CI/CD artifact storage** | <1 MB | <10 MB | <50 MB (7-day retention) |

**Performance Optimizations:**
- **Parallel test execution:** pytest-xdist (`-n auto`), Jest (`--maxWorkers=2`), cargo test (`--test-threads=4`)
- **Incremental coverage:** Only measure changed files (git-diff based)
- **AST caching:** Cache dependency graph for gap analysis
- **Trend data pruning:** Keep 30-day history, archive older data
- **Artifact compression:** Gzip JSON artifacts before upload

---

## Common Pitfalls

### Pitfall 1: Blocking Development with Strict Coverage Gates

**What goes wrong:** Set 80% threshold immediately, developers can't merge code, coverage gate becomes bottleneck

**Why it happens:** Big bang approach without progressive rollout, no allowance for new code exploration

**Prevention:**
- Use progressive thresholds (70% → 75% → 80%) with phased rollout
- Enforce 80% on new code only (allow existing code to lag)
- Provide temporary bypass for refactoring (requires approval)
- Separate PR gates (warning only) from main branch gates (strict)

**Detection:** Developer complaints, merge conflicts, decreased velocity

**Mitigation:** Monitor merge velocity, adjust thresholds if needed, provide escape hatch

### Pitfall 2: Testing the Wrong Things (Coverage Without Quality)

**What goes wrong:** High coverage but low-quality tests (meaningless assertions, test flakiness)

**Why it happens:** Focus on coverage percentage instead of test quality, auto-generated tests without review

**Prevention:**
- Require test review for critical paths (security, governance, financial)
- Use property-based testing for invariants (Hypothesis, FastCheck, proptest)
- Track test failure rates (flaky test detection)
- Enforce mutation testing for core services (mutmut, stryker)

**Detection:** High coverage but production bugs, flaky test reruns, low mutation score

**Mitigation:** Code review standards, quality metrics beyond coverage (mutation score, complexity)

### Pitfall 3: Ignoring Business Impact (Testing Low-Value Code First)

**What goes wrong:** Spend effort testing utility functions while critical services remain untested

**Why it happens:** Easy wins first (low-hanging fruit) without considering business value

**Prevention:**
- Prioritize by business impact (core services > utilities > edge cases)
- Use dependency centrality to identify high-fan-in files
- Focus on user-facing features (agent execution, governance, episodic memory)
- Quick wins should still be high-impact (not just easy)

**Detection:** Coverage increases but production incidents remain, high coverage on low-risk code

**Mitigation:** Business impact scoring, risk-based testing, align with product priorities

### Pitfall 4: Coverage Measurement Overhead

**What goes wrong:** Coverage measurement takes longer than test execution, developers skip it

**Why it happens:** Running full coverage on every change, no caching, redundant measurements

**Prevention:**
- Use incremental coverage (measure changed files only)
- Cache coverage data between runs (coverage.py cache, Jest cache)
- Run full coverage only in CI/CD (not on every dev iteration)
- Use fast coverage tools (pytest-cov, Jest built-in, tarpaulin)

**Detection:** Developers disable coverage locally, long test+coverage cycles

**Mitigation:** Incremental coverage, pre-commit hooks (fast), CI/CD (comprehensive)

### Pitfall 5: Test Suite Bloat (Unmaintainable Tests)

**What goes wrong:** Thousands of auto-generated tests, no ownership, test suite becomes unmaintainable

**Why it happens:** Auto-generated tests without review, no test cleanup, redundant tests

**Prevention:**
- Require manual review for auto-generated tests (convert to real tests)
- Archive old tests for deprecated features (don't delete, move to archive/)
- Use test helpers and fixtures to reduce duplication
- Regular test cleanup sprints (delete redundant tests, consolidate helpers)

**Detection:** Test suite takes >30 minutes to run, high flaky test rate, developer confusion

**Mitigation:** Test ownership, regular cleanup, test style guide

---

## Sources

### Primary (HIGH confidence)

- **Existing Atom Infrastructure:**
  - `/Users/rushiparikh/projects/atom/backend/tests/scripts/cross_platform_coverage_gate.py` - Cross-platform coverage enforcement with platform-specific thresholds (786 lines)
  - `/Users/rushiparikh/projects/atom/backend/tests/scripts/aggregate_coverage.py` - Unified coverage aggregation across 4 platforms (755 lines)
  - `/Users/rushiparikh/projects/atom/.github/workflows/unified-tests.yml` - Sequential test execution with coverage artifacts (336 lines)
  - `/Users/rushiparikh/projects/atom/.planning/phases/149-quality-infrastructure-parallel/149-RESEARCH.md` - Parallel execution architecture (matrix strategies, test splitting)
  - `/Users/rushiparikh/projects/atom/.planning/phases/150-quality-infrastructure-trending/150-03-PLAN.md` - Coverage trending automation (338 lines)
  - `/Users/rushiparikh/projects/atom/backend/pytest.ini` - Backend test configuration (80% fail_under, branch coverage)
  - `/Users/rushiparikh/projects/atom/frontend-nextjs/jest.config.js` - Frontend test configuration (80% global, per-module thresholds)
  - `/Users/rushiparikh/projects/atom/mobile/jest.config.js` - Mobile test configuration (60% threshold)
  - `/Users/rushiparikh/projects/atom/backend/tests/coverage_reports/metrics/cross_platform_summary.json` - Current coverage state (34.88% overall)
  - `/Users/rushiparikh/projects/atom/backend/tests/scripts/coverage_trend_analyzer.py` - Coverage regression detection
  - `/Users/rushiparikh/projects/atom/backend/tests/scripts/update_cross_platform_trending.py` - Historical trend tracking
  - `/Users/rushiparikh/projects/atom/backend/tests/scripts/generate_coverage_dashboard.py` - HTML trend visualization

### Secondary (MEDIUM confidence)

- **pytest-xdist Documentation:** https://pytest-xdist.readthedocs.io/ - Parallel test execution with load balancing
- **Jest Coverage:** https://jestjs.io/docs/configuration#collectcoverage-boolean - Coverage collection and reporting
- **GitHub Actions Matrix:** https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs - Matrix strategy for parallel jobs
- **Coverage.py Documentation:** https://coverage.readthedocs.io/ - Python coverage measurement (branch coverage, combining reports)

### Tertiary (LOW confidence)

- **Incremental Coverage Patterns:** General best practices for diff-based coverage analysis (verified against existing Atom infrastructure)
- **Coverage-Driven Development:** Workflow patterns for integrating coverage into development process (based on existing pre-commit hooks in Atom)
- **Test Prioritization:** Business impact scoring algorithms (based on existing coverage_priorities.json patterns)

---

## Metadata

**Confidence breakdown:**
- Architecture: HIGH - Based on existing Atom infrastructure (verified files, workflows, scripts)
- Integration points: HIGH - Verified from actual GitHub Actions workflows and Python scripts
- Build order: HIGH - Logical dependency flow (infrastructure → analysis → generation → execution)
- Pitfalls: HIGH - Based on common CI/CD anti-patterns and existing Atom workflow patterns

**Research date:** March 7, 2026
**Valid until:** April 6, 2026 (30 days - infrastructure stable, thresholds configurable)

**Key decisions for planner:**
1. **Progressive rollout over big bang:** Increase thresholds gradually (70% → 75% → 80%) to avoid blocking development
2. **New code enforcement first:** Strict 80% on new code while allowing existing code to catch up (prevents regression)
3. **Business impact prioritization:** Test critical services first (governance, episodic memory, LLM) not easy utilities
4. **Incremental over comprehensive:** Use git-diff based coverage for development (fast) vs full coverage in CI/CD (comprehensive)
5. **Tooling over manual:** Auto-generate test stubs, provide testing patterns, automate gap analysis (reduce developer friction)
6. **Monitoring over gating:** Use coverage trending to track progress, celebrate milestones, adjust roadmap based on data
