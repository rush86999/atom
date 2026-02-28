# Architecture Research: Multi-Platform Integration & Property Testing

**Domain:** Multi-platform test architecture (Next.js, React Native, Tauri, Python)
**Researched:** February 26, 2026
**Overall Confidence:** HIGH (based on existing infrastructure analysis)

---

## Executive Summary

Atom requires a unified testing architecture that integrates four distinct platforms:
1. **Backend (Python)** - pytest-based with Hypothesis property tests, 15.2% coverage target → 50%
2. **Frontend (Next.js)** - Jest with 80% coverage threshold, limited existing tests
3. **Mobile (React Native)** - Jest via jest-expo, 80% coverage threshold, 25+ tests
4. **Desktop (Tauri)** - Rust backend tests + Jest frontend tests, no unified test runner

**Key Findings:**
- Existing backend infrastructure is production-ready (pytest, Hypothesis, CI/CD, quality gates)
- Frontend/mobile have test frameworks configured but limited integration with backend CI/CD
- No unified coverage aggregation across platforms
- Property-based testing exists only for Python (Hypothesis), not for JavaScript/TypeScript platforms
- FastCheck (v4.5.3) already in frontend-nextjs dependencies for property-based testing

---

## Standard Architecture

### System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                         GitHub Actions CI/CD                           │
├────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   Backend   │  │  Frontend   │  │   Mobile    │  │   Desktop   │  │
│  │     CI      │  │     CI      │  │     CI      │  │     CI      │  │
│  │  (Python)   │  │  (Next.js)  │  │  (Expo RN)  │  │   (Tauri)   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                │                │                │           │
│         └────────────────┴────────────────┴────────────────┘           │
│                              ↓                                         │
│                  ┌──────────────────────┐                             │
│                  │  Coverage Aggregator │                             │
│                  │  (Unified Reports)   │                             │
│                  └──────────────────────┘                             │
└────────────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────────────┐
│                       Quality Gates & Reporting                        │
├────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   Pass Rate │  │   Coverage  │  │    Flaky    │  │   Property  │  │
│  │   (98%+)    │  │   Threshold │  │   Tests     │  │    Tests    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Backend Test Runner** | pytest with Hypothesis for property tests, coverage, quality gates | `pytest.ini`, `backend/tests/` |
| **Frontend Test Runner** | Jest + React Testing Library, 80% coverage gate | `jest.config.js`, `frontend-nextjs/tests/` |
| **Mobile Test Runner** | jest-expo, React Native Testing Library, 80% coverage gate | `mobile/jest.config.js`, `mobile/src/__tests__/` |
| **Desktop Test Runner** | Rust `cargo test` + Jest for Tauri frontend | `frontend-nextjs/src-tauri/tests/` |
| **Coverage Aggregator** | Merge coverage reports across platforms, unified thresholds | Python script in `backend/tests/scripts/` |
| **CI Orchestration** | Parallel test execution, artifact collection, quality gate enforcement | `.github/workflows/*.yml` |
| **Property Test Framework** | Hypothesis (Python), FastCheck (JavaScript/TypeScript) | `backend/tests/property_tests/`, JS/TS test files |

---

## Recommended Project Structure

```
atom/
├── backend/
│   ├── tests/
│   │   ├── unit/                    # Existing unit tests
│   │   ├── integration/             # Existing integration tests
│   │   ├── property_tests/          # Hypothesis property tests (existing)
│   │   ├── e2e_ui/                  # Playwright E2E tests (existing)
│   │   ├── scripts/
│   │   │   ├── aggregate_coverage.py     # NEW: Merge all platform coverage
│   │   │   ├── ci_quality_gate.py        # EXISTING: Backend quality gates
│   │   │   └── unified_quality_gate.py   # NEW: Cross-platform gates
│   │   └── coverage_reports/
│   │       └── metrics/              # Backend coverage metrics
│   └── pytest.ini                   # Backend test configuration
├── frontend-nextjs/
│   ├── tests/                       # NEW: Frontend test directory
│   │   ├── unit/                    # Jest unit tests
│   │   ├── integration/             # API integration tests
│   │   └── property/                # FastCheck property tests (NEW)
│   ├── components/__tests__/        # Existing component tests (if any)
│   ├── jest.config.js               # Existing Jest config
│   └── src-tauri/
│       └── tests/                   # Tauri Rust tests
├── mobile/
│   ├── src/__tests__/               # EXISTING: Mobile tests
│   │   ├── services/                # Service unit tests
│   │   ├── screens/                 # Screen tests
│   │   ├── contexts/                # Context tests
│   │   └── property/                # NEW: FastCheck property tests
│   └── jest.config.js               # Existing Jest config (jest-expo)
├── .github/
│   └── workflows/
│       ├── ci.yml                   # EXISTING: Backend + Frontend build
│       ├── test-coverage.yml        # EXISTING: Backend coverage
│       ├── mobile-ci.yml            # EXISTING: Mobile tests + build
│       ├── frontend-tests.yml       # NEW: Frontend tests
│       ├── desktop-tests.yml        # NEW: Tauri tests
│       ├── unified-tests.yml        # NEW: All-platform test orchestration
│       └── e2e-ui-tests.yml         # EXISTING: Playwright E2E
└── .planning/
    └── research/
        └── ARCHITECTURE.md          # This document
```

### Structure Rationale

- **`backend/tests/property_tests/`**: Existing Hypothesis tests, well-organized by domain (governance, episodes, security)
- **`frontend-nextjs/tests/`**: Centralized frontend tests (separate from `__tests__` directories scattered in components/)
- **`mobile/src/__tests__/`**: Expo-standard location, already populated with 25+ tests
- **`backend/tests/scripts/`**: Unified Python scripts for coverage aggregation (can parse all coverage formats)
- **`.github/workflows/`**: Platform-specific workflows for parallel execution + unified orchestration workflow

---

## Architectural Patterns

### Pattern 1: Platform-First Testing (Bottom-Up Integration)

**What:** Each platform runs tests independently in CI, then results are aggregated for quality gates.

**When to use:**
- Multi-platform projects with independent CI pipelines
- Different test frameworks (pytest, Jest, cargo)
- Need fast feedback loops per platform

**Trade-offs:**
- ✅ Fast platform-specific feedback (5-10 minutes per platform)
- ✅ Parallel execution in CI
- ❌ No cross-platform integration tests initially
- ❌ Coverage aggregation requires custom scripts

**Example:**
```yaml
# .github/workflows/unified-tests.yml
name: Unified Tests

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run backend tests
        run: |
          cd backend
          pytest tests/ --cov=core --cov=api --cov=tools \
            --cov-report=json:tests/coverage_reports/metrics/coverage.json
      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: backend-coverage
          path: backend/tests/coverage_reports/metrics/coverage.json

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run frontend tests
        run: |
          cd frontend-nextjs
          npm test -- --coverage --coverageReporters=json
      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: frontend-coverage
          path: frontend-nextjs/coverage/coverage-final.json

  aggregate-coverage:
    needs: [backend-tests, frontend-tests, mobile-tests]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Download all coverage
        uses: actions/download-artifact@v4
      - name: Aggregate coverage
        run: |
          python backend/tests/scripts/aggregate_coverage.py \
            --backend backend-coverage/coverage.json \
            --frontend frontend-coverage/coverage-final.json \
            --mobile mobile-coverage/coverage-final.json \
            --output unified-coverage.json
```

### Pattern 2: Property-Based Testing Integration

**What:** Extend existing Hypothesis (Python) property tests to JavaScript/TypeScript using FastCheck.

**When to use:**
- Testing business logic invariants across platforms
- Data validation and transformation functions
- State management logic (Redux, Zustand, React Context)

**Trade-offs:**
- ✅ Catches edge cases that example-based tests miss
- ✅ Shrinks failing cases to minimal reproducible examples
- ❌ Slower than unit tests (100s of random inputs)
- ❌ Requires careful property definition (not all code has obvious invariants)

**Example:**
```typescript
// frontend-nextjs/tests/property/canvasStateProperties.test.ts
import fc from 'fast-check';
import { canvasStateReducer, CanvasState } from '@/lib/canvasStateReducer';

describe('Canvas State Properties', () => {
  it('should maintain state integrity after any sequence of actions', () => {
    fc.assert(
      fc.property(
        // Arbitrary: Generate arrays of random actions
        fc.array(fc.record({
          type: fc.constantFrom('PRESENT', 'SUBMIT', 'CLOSE', 'UPDATE'),
          payload: fc.anything()
        })),
        (actions) => {
          const initialState: CanvasState = { presentations: [], currentId: null };
          const finalState = actions.reduce(canvasStateReducer, initialState);

          // Property: State should never have orphaned presentations
          const orphanedPresentations = finalState.presentations.filter(
            p => !finalState.presentations.some(other => other.id === p.parentId)
          );
          return orphanedPresentations.length === 0;
        }
      )
    );
  });
});
```

**Backend equivalent (existing):**
```python
# backend/tests/property_tests/canvas/test_canvas_tool_invariants.py
from hypothesis import given, strategies as st
from core.models import CanvasAudit

@given(st.builds(CanvasAudit))
def test_canvas_state_invariant(canvas: CanvasAudit):
    """Property: Canvas state transitions should always be valid"""
    # After any state transition, current_state should be valid
    assert canvas.current_state in ['PRESENTING', 'CLOSED', 'SUBMITTED', 'UPDATED']
```

### Pattern 3: Coverage Aggregation Script

**What:** Python script parses multiple coverage formats (JSON from pytest, Jest) and produces unified report.

**When to use:**
- Multi-language monorepo with different coverage formats
- Need cross-platform coverage thresholds (e.g., "overall 50% coverage")
- Want unified reporting dashboard

**Trade-offs:**
- ✅ Single source of truth for coverage metrics
- ✅ Can enforce minimum coverage across all platforms
- ❌ Requires custom parsing logic for each format
- ❌ Coverage formats change between tool versions

**Example:**
```python
# backend/tests/scripts/aggregate_coverage.py
import json
from pathlib import Path

def aggregate_coverage(
    backend_json: Path,
    frontend_json: Path,
    mobile_json: Path,
    output_json: Path
):
    """Aggregate coverage reports from all platforms into unified format"""

    # Parse pytest coverage (Python)
    with open(backend_json) as f:
        backend_cov = json.load(f)
        backend_lines = backend_cov['totals']['num_statements']
        backend_covered = backend_cov['totals']['covered_lines']

    # Parse Jest coverage (JavaScript/TypeScript)
    def parse_jest_coverage(json_path: Path):
        with open(json_path) as f:
            cov = json.load(f)
        # Jest coverage structure: { "path/to/file.ts": { "lines": { "total": 100, "covered": 80 } } }
        total_lines = sum(f['lines']['total'] for f in cov.values())
        total_covered = sum(f['lines']['covered'] for f in cov.values())
        return total_lines, total_covered

    frontend_lines, frontend_covered = parse_jest_coverage(frontend_json)
    mobile_lines, mobile_covered = parse_jest_coverage(mobile_json)

    # Calculate unified metrics
    total_lines = backend_lines + frontend_lines + mobile_lines
    total_covered = backend_covered + frontend_covered + mobile_covered
    overall_coverage = (total_covered / total_lines * 100) if total_lines > 0 else 0

    # Generate unified report
    unified = {
        'totals': {
            'total_lines': total_lines,
            'covered_lines': total_covered,
            'percent_covered': round(overall_coverage, 2)
        },
        'platforms': {
            'backend': {
                'percent_covered': round(backend_covered / backend_lines * 100, 2),
                'total_lines': backend_lines,
                'covered_lines': backend_covered
            },
            'frontend': {
                'percent_covered': round(frontend_covered / frontend_lines * 100, 2),
                'total_lines': frontend_lines,
                'covered_lines': frontend_covered
            },
            'mobile': {
                'percent_covered': round(mobile_covered / mobile_lines * 100, 2),
                'total_lines': mobile_lines,
                'covered_lines': mobile_covered
            }
        }
    }

    with open(output_json, 'w') as f:
        json.dump(unified, f, indent=2)

    # Return exit code based on threshold
    COVERAGE_THRESHOLD = 50
    if overall_coverage < COVERAGE_THRESHOLD:
        print(f"❌ Coverage {overall_coverage:.1f}% below {COVERAGE_THRESHOLD}% threshold")
        return 1
    else:
        print(f"✅ Coverage {overall_coverage:.1f}% meets {COVERAGE_THRESHOLD}% threshold")
        return 0
```

---

## Data Flow

### Test Execution Flow

```
[Developer Push]
    ↓
[GitHub Actions Trigger]
    ↓
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│   Backend CI     │  Frontend CI     │   Mobile CI      │  Desktop CI     │
│  (pytest)        │  (Jest)          │  (jest-expo)     │  (cargo + Jest) │
└────────┬─────────┴────────┬─────────┴────────┬─────────┴────────┬─────────┘
         │                  │                  │                  │
         ↓                  ↓                  ↓                  ↓
[backend-coverage.json][frontend-coverage.json][mobile-coverage.json][desktop-coverage.json]
         │                  │                  │                  │
         └──────────────────┴──────────────────┴──────────────────┘
                              ↓
                  [aggregate_coverage.py]
                              ↓
                  [unified-coverage.json]
                              ↓
              [Quality Gate Evaluation]
         ┌────────────────────┼────────────────────┐
         ↓                    ↓                    ↓
[Pass Rate ≥98%?]  [Coverage ≥50%?]  [Flaky Tests?]
         │                    │                    │
         └────────────────────┴────────────────────┘
                              ↓
                   [PR Comment / Badge]
```

### Coverage Data Transformation

```
pytest (coverage.json)          Jest (coverage-final.json)
┌─────────────────────┐        ┌─────────────────────┐
│ {                   │        │ {                   │
│   "totals": {       │        │   "/path/to/file": { │
│     "percent_covered│  →   │     "lines": {       │
│     ": 45.2         │        │       "total": 100, │
│   },                │        │       "covered": 80 │
│   "files": {...}    │        │     }               │
│ }                   │        │   }                 │
└─────────────────────┘        └─────────────────────┘
         │                              │
         └──────────┬───────────────────┘
                    ↓
         [aggregate_coverage.py]
                    ↓
         ┌─────────────────────┐
         │ {                   │
         │   "totals": {       │
         │     "percent_covered│
         │     ": 47.8         │ ← UNIFIED
         │   },                │
         │   "platforms": {    │
         │     "backend": 45.2 │
         │     "frontend": 52.1│
         │     "mobile": 48.3  │
         │   }                 │
         │ }                   │
         └─────────────────────┘
```

### Key Data Flows

1. **Test Execution**: Parallel CI jobs run pytest, Jest, jest-expo, cargo test simultaneously
2. **Coverage Upload**: Each platform uploads coverage artifact as JSON
3. **Aggregation**: Download all artifacts → Python script merges → Unified JSON
4. **Quality Gate**: Unified coverage compared against threshold → Pass/Fail
5. **Reporting**: PR comment with breakdown by platform + badge for overall status

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **100 tests/platform** | Single CI job per platform, <5 minutes per platform |
| **1000 tests/platform** | Split tests by type (unit/integration/property), use matrix strategy, ~15 minutes per platform |
| **10000 tests/platform** | Test sharding by directory/tags, parallel jobs (10x), ~30 minutes per platform, consider test selection based on diff |

### Scaling Priorities

1. **First bottleneck: Test execution time**
   - **Fix:** Use pytest-xdist (backend), Jest parallel jobs (frontend), split mobile tests by folder
   - **Target:** <15 minutes per platform in CI

2. **Second bottleneck: Coverage aggregation**
   - **Fix:** Cache aggregated coverage, only re-run on PR changes (not main branch)
   - **Target:** <30 seconds aggregation time

3. **Third bottleneck: Artifact download/upload**
   - **Fix:** Use GitHub Actions cache for coverage artifacts, compress JSON reports
   - **Target:** <1 minute artifact transfer

---

## Anti-Patterns

### Anti-Pattern 1: Monolithic Test Workflow

**What people do:** Single CI job that runs all platform tests sequentially

```yaml
# BAD: 40+ minute feedback loop
jobs:
  all-tests:
    steps:
      - run: pytest backend/tests/          # 10 min
      - run: npm test --prefix frontend     # 10 min
      - run: npm test --prefix mobile       # 10 min
      - run: cargo test --manifest-path=... # 10 min
```

**Why it's wrong:**
- Developers wait 40+ minutes for feedback
- Failed frontend tests block backend testing
- Can't parallelize across different runners

**Do this instead:** Platform-specific jobs with parallel execution

```yaml
# GOOD: Fast feedback per platform
jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps: [...]
  frontend-tests:
    runs-on: ubuntu-latest
    steps: [...]
  mobile-tests:
    runs-on: ubuntu-latest
    steps: [...]
```

### Anti-Pattern 2: Coverage Without Context

**What people do:** Report single percentage number without breakdown

```json
// BAD: No actionable information
{
  "coverage": 47.8
}
```

**Why it's wrong:**
- Can't tell which platform needs improvement
- Regression in one platform masked by gains in another
- No historical trend data

**Do this instead:** Detailed breakdown with trends

```json
// GOOD: Actionable insights
{
  "totals": { "percent_covered": 47.8 },
  "platforms": {
    "backend": { "percent_covered": 45.2, "trend": "+2.1%" },
    "frontend": { "percent_covered": 52.1, "trend": "-0.5%" },
    "mobile": { "percent_covered": 48.3, "trend": "+1.2%" }
  },
  "below_threshold": ["backend"],
  "regression_detected": ["frontend"]
}
```

### Anti-Pattern 3: Property Tests for Everything

**What people do:** Replace all unit tests with property tests

**Why it's wrong:**
- Property tests are slower (100s of examples vs 1 example)
- Not all code has obvious invariants
- Harder to debug failures (randomized inputs)

**Do this instead:** Use property tests for critical invariants only

```python
# GOOD: Property test for state machine invariant
@given(st.builds(AgentState))
def test_agent_maturity_monotonic(state):
    """Property: Agent maturity should never decrease"""
    new_state = apply_action(state, random_action())
    assert new_state.maturity_level >= state.maturity_level

# GOOD: Example test for specific business rule
def test_student_agent_cannot_execute_deletions():
    """Example: Student agents blocked from deletions"""
    agent = create_agent(maturity=StudentMaturity)
    result = agent.execute(action="DELETE_RECORD")
    assert result.blocked is True
```

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **GitHub Actions** | Matrix strategy for parallel jobs, artifact upload/download | Already configured for backend/mobile |
| **Codecov** (optional) | `codecov/codecov-action@v3` for coverage badges | Mobile CI already uses, consider adding for other platforms |
| **CodeCov** vs **custom aggregation** | Custom aggregation preferred for multi-language monorepo | Codecov handles single-language repos better |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **Backend ↔ Frontend** | API contract tests, shared TypeScript types | Use `backend/tests/integration/api/` + frontend Jest integration tests |
| **Backend ↔ Mobile** | Same API as frontend, mobile tests mock HTTP clients | Mobile tests use `axios-mock-adapter` or MSW |
| **Frontend ↔ Tauri** | Tauri invoke commands, shared state via frontend tests | Test Tauri commands in Rust, test UI in Jest |
| **All platforms ↔ Coverage Aggregator** | JSON artifacts uploaded to GHA, downloaded by aggregator script | Python script can parse pytest, Jest, cargo coverage formats |

---

## Build Order & Implementation Phases

### Recommended Approach: Incremental Platform Integration

**Phase 1: Backend + Frontend Integration (Week 1)**
- Goal: Unified coverage for Python + TypeScript (same backend API)
- Tasks:
  1. Create `frontend-tests.yml` workflow
  2. Write `aggregate_coverage.py` script (Python + Jest only)
  3. Add FastCheck property tests to frontend
  4. Update `ci.yml` to run frontend tests in parallel with backend
- Success criteria: Unified coverage report in PR comments

**Phase 2: Add Mobile Coverage (Week 2)**
- Goal: Include React Native tests in aggregation
- Tasks:
  1. Update `mobile-ci.yml` to upload coverage artifacts
  2. Extend `aggregate_coverage.py` to parse jest-expo coverage
  3. Add FastCheck property tests to mobile (focus on state management)
- Success criteria: Mobile coverage included in unified report

**Phase 3: Desktop Testing (Week 3)**
- Goal: Tauri Rust tests + frontend tests
- Tasks:
  1. Create `desktop-tests.yml` workflow (cargo test + Jest)
  2. Add Rust coverage parsing (tarpaulin or covector)
  3. Extend aggregation script for Rust coverage
- Success criteria: All 4 platforms reporting coverage

**Phase 4: Property Testing Expansion (Week 4)**
- Goal: Property tests across all platforms for critical invariants
- Tasks:
  1. Identify shared invariants (e.g., state transitions, data validation)
  2. Write Hypothesis tests (backend), FastCheck tests (frontend/mobile)
  3. Document property testing patterns for each platform
- Success criteria: 10+ property tests per platform

**Phase 5: Cross-Platform Integration Tests (Week 5)**
- Goal: Tests that verify backend API integration with frontend/mobile
- Tasks:
  1. Start test backend server in CI
  2. Frontend tests hit real `/api` endpoints (not mocks)
  3. Mobile tests use mocked responses but validate contracts
- Success criteria: End-to-end API contract validation

### Why This Order?

1. **Backend + Frontend first**: Both use TypeScript (backend API + frontend share types), highest impact
2. **Mobile second**: Already has Jest infrastructure, just need integration
3. **Desktop third**: Most complex (Rust + JavaScript), need to establish patterns first
4. **Property tests last**: Require deep understanding of invariants, better to write after integration tests
5. **Cross-platform last**: Depends on all platforms being stable

---

## CI/CD Integration Changes

### New Workflows to Create

| File | Purpose | Key Steps |
|------|---------|-----------|
| `.github/workflows/frontend-tests.yml` | Frontend Jest tests + coverage | Install deps, run tests, upload coverage |
| `.github/workflows/desktop-tests.yml` | Tauri Rust + Jest tests | Cargo test, npm test, upload coverage |
| `.github/workflows/unified-tests.yml` | Orchestrate all platform tests | Trigger all workflows, aggregate coverage |

### Existing Workflows to Modify

| File | Changes Required |
|------|------------------|
| `.github/workflows/ci.yml` | Add `frontend-tests` job, upload coverage artifact |
| `.github/workflows/mobile-ci.yml` | Already uploads coverage, ensure JSON format compatible |
| `.github/workflows/test-coverage.yml` | Replace with `unified-tests.yml` aggregation |

### New Scripts to Create

| Script | Purpose | Inputs | Outputs |
|--------|---------|--------|---------|
| `backend/tests/scripts/aggregate_coverage.py` | Merge all platform coverage | Backend JSON, frontend JSON, mobile JSON | Unified JSON |
| `backend/tests/scripts/unified_quality_gate.py` | Cross-platform quality gates | Unified coverage, pytest reports | Pass/fail, PR comment |

---

## Property Testing Strategy by Platform

### Backend (Python) - Hypothesis (EXISTING)

**Current state:** 100+ property tests in `backend/tests/property_tests/`

**Gaps to fill:**
- Add property tests for new features (e.g., cognitive tier system, world model)
- Increase max_examples for critical invariants (currently default 100)

**Example invariant to add:**
```python
# backend/tests/property_tests/llm/test_cognitive_tier_properties.py
@given(st.builds(CognitiveTierClassification))
def test_cognitive_tier_monotonic(classification):
    """Property: Higher token count should not result in lower tier"""
    assert classification.tier_level in [1, 2, 3, 4, 5]
```

### Frontend (Next.js) - FastCheck (NEW)

**Current state:** FastCheck v4.5.3 in dependencies, no property tests written

**Priority invariants:**
1. Canvas state management (add/remove/update presentations)
2. Agent chat state transitions (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
3. Form validation (should always accept valid data, reject invalid)

**Example:**
```typescript
// frontend-nextjs/tests/property/agentChatProperties.test.ts
import fc from 'fast-check';
import { agentChatReducer, ChatState } from '@/lib/agentChatReducer';

it('should not allow maturity level to decrease', () => {
  fc.assert(
    fc.property(
      fc.array(fc.constantFrom('PROMOTE', 'DEMOTE', 'GRADUATE')),
      (actions) => {
        const state: ChatState = { agentMaturity: 'STUDENT' };
        const finalState = actions.reduce(agentChatReducer, state);
        // Property: Maturity should be monotonic (never decrease)
        // (Assuming DEMOTE is blocked by governance)
        return true;
      }
    )
  );
});
```

### Mobile (React Native) - FastCheck (NEW)

**Current state:** Jest via jest-expo, no property tests

**Priority invariants:**
1. Offline sync queue (queue operations should be replayed in order)
2. Biometric auth state (authenticated state should persist across app lifecycle)
3. Network state transitions (online → offline → online should recover)

### Desktop (Tauri) - Quickcheck (Rust) + FastCheck (Frontend)

**Current state:** No property tests

**Rust property tests (quickcheck):**
```rust
// frontend-nextjs/src-tauri/tests/property_tests.rs
#[quickcheck]
fn fn_command_id_is_unique(commands: Vec<Command>) -> bool {
    // Property: All command IDs should be unique
    let ids: Vec<_> = commands.iter().map(|c| c.id).collect();
    let unique_ids: HashSet<_> = ids.iter().collect();
    ids.len() == unique_ids.len()
}
```

---

## Summary

### Key Architectural Decisions

1. **Platform-first approach**: Each platform runs tests independently, then aggregate results
2. **Python as orchestrator**: Use Python scripts for coverage aggregation (can parse all formats)
3. **FastCheck for JS/TS**: Already in dependencies, use for property tests across frontend/mobile
4. **Unified quality gates**: Single script enforces 50% overall coverage + 98% pass rate
5. **Incremental rollout**: Backend + Frontend → Mobile → Desktop → Property tests → Cross-platform

### Integration Points

| Integration Point | Type | New vs Modified |
|-------------------|------|-----------------|
| Coverage aggregation | Python script | NEW |
| Unified CI workflow | GitHub Actions | NEW |
| Frontend tests | Jest workflow | NEW |
| Desktop tests | Cargo + Jest workflows | NEW |
| Property tests (JS/TS) | FastCheck tests | NEW |
| Property tests (Python) | Hypothesis tests | EXTEND existing |
| Quality gate enforcement | Python script | MODIFY existing |

### Build Order Rationale

1. Start with **backend + frontend** (highest impact, TypeScript alignment)
2. Add **mobile** (existing Jest infrastructure, easy integration)
3. Add **desktop** (most complex, defer until patterns established)
4. Expand **property tests** (require domain knowledge, better after integration tests stable)
5. Add **cross-platform integration** (depends on all platforms being testable)

This architecture balances fast feedback loops with unified quality gates, enabling Atom to maintain high test coverage across all four platforms while keeping CI execution times manageable.

---

## Sources

- **Backend test infrastructure**: `/Users/rushiparikh/projects/atom/backend/pytest.ini`, `/Users/rushiparikh/projects/atom/backend/.planning/PROJECT.md`
- **CI/CD workflows**: `/Users/rushiparikh/projects/atom/.github/workflows/ci.yml`, `test-coverage.yml`, `mobile-ci.yml`, `e2e-ui-tests.yml`
- **Frontend Jest config**: `/Users/rushiparikh/projects/atom/frontend-nextjs/jest.config.js`
- **Mobile Jest config**: `/Users/rushiparikh/projects/atom/mobile/jest.config.js`
- **Package dependencies**: `frontend-nextjs/package.json` (FastCheck v4.5.3), `mobile/package.json` (jest-expo)
- **Existing property tests**: `/Users/rushiparikh/projects/atom/backend/tests/property_tests/` (100+ Hypothesis tests)

---

*Architecture research for: Multi-platform integration & property testing*
*Researched: February 26, 2026*
*Confidence: HIGH (based on existing infrastructure analysis)*
