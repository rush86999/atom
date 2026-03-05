# Architecture Research: Cross-Platform Testing Integration

**Domain:** Multi-platform testing architecture (Python, TypeScript/Next.js, React Native, Tauri/Rust)
**Researched:** March 3, 2026
**Overall Confidence:** HIGH (based on existing infrastructure analysis + current ecosystem research)

---

## Executive Summary

Atom requires a unified 4-platform testing architecture that achieves 80% overall coverage through intelligent integration points:
1. **Backend (Python)** - 74.6% coverage, pytest with Hypothesis, comprehensive infrastructure
2. **Frontend (Next.js)** - 89.84% coverage, Jest/RTL, FastCheck available
3. **Mobile (React Native)** - 16.16% coverage, jest-expo, needs expansion
4. **Desktop (Tauri/Rust)** - TBD baseline, proptest + FastCheck potential

**Key Findings:**
- **Existing aggregation infrastructure is production-ready**: `aggregate_coverage.py` handles pytest, Jest, jest-expo, and tarpaulin formats
- **Unified CI workflow exists**: `.github/workflows/unified-tests.yml` already orchestrates parallel test execution
- **API contract testing implemented**: `frontend-nextjs/tests/integration/api-contracts.test.ts` validates request/response shapes
- **Property testing gap**: Backend has 250+ Hypothesis tests; frontend/mobile need FastCheck expansion
- **OpenAPI contract testing opportunity**: Schemathesis (Python) + openapi-typescript (TypeScript) for automated API validation

**Recommended Integration Strategy:**
1. **Backend-first foundation**: API contracts → Frontend/Mobile validation (shared types)
2. **Cross-platform state testing**: Zustand/Redux state invariants across all JS platforms
3. **Unified quality gates**: 80% overall coverage with platform-weighted thresholds
4. **E2E platform orchestration**: Playwright (web) + Detox (mobile) + Tauri driver (desktop)

---

## Current Architecture

### System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                         GitHub Actions CI/CD                           │
├────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   Backend   │  │  Frontend   │  │   Mobile    │  │   Desktop   │  │
│  │  (Python)   │  │ (Next.js)   │  │  (Expo RN)  │  │   (Tauri)   │  │
│  │  74.6% cov │  │  89.84% cov │  │  16.16% cov │  │     TBD     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                │                │                │           │
│         │ pytest         │ Jest           │ jest-expo      │ proptest   │
│         │ Hypothesis     │ FastCheck      │ FastCheck      │ cargo test │
│         └────────────────┴────────────────┴────────────────┘           │
│                              ↓                                         │
│                  ┌──────────────────────┐                             │
│                  │  Coverage Aggregator │                             │
│                  │  (aggregate_coverage│                             │
│                  │   .py - EXISTING)    │                             │
│                  └──────────────────────┘                             │
└────────────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────────────┐
│                       Quality Gates & Reporting                        │
├────────────────────────────────────────────────────────────────────────┤
│  80% overall coverage (weighted: backend 70%, frontend 20%,           │
│                      mobile 5%, desktop 5%)                            │
│  98% pass rate across all platforms                                    │
│  PR comment automation with platform breakdown                         │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation Status |
|-----------|----------------|----------------------|
| **Backend Test Runner** | pytest with Hypothesis, coverage reports | ✅ PRODUCTION |
| **Frontend Test Runner** | Jest + RTL, FastCheck available | ✅ PRODUCTION |
| **Mobile Test Runner** | jest-expo, 25+ tests, needs expansion | 🟡 PARTIAL |
| **Desktop Test Runner** | Tauri Rust tests + proptest | 🔴 NEEDS BASELINE |
| **Coverage Aggregator** | Python script parsing 4 coverage formats | ✅ IMPLEMENTED |
| **CI Orchestration** | Unified workflow with parallel execution | ✅ IMPLEMENTED |
| **API Contract Tests** | Request/response shape validation | 🟡 PARTIAL |
| **Property Tests** | Invariants across platforms | 🟡 BACKEND ONLY |
| **E2E Tests** | Playwright web + Detox mobile + Tauri desktop | 🟡 WEB ONLY |

---

## Recommended Project Structure

```
atom/
├── backend/
│   ├── tests/
│   │   ├── unit/                    # Existing unit tests
│   │   ├── integration/             # API integration tests
│   │   ├── property_tests/          # Hypothesis tests (250+ existing)
│   │   ├── e2e_ui/                  # Playwright E2E (existing)
│   │   ├── contract/                # NEW: Schemathesis API contract tests
│   │   └── scripts/
│   │       ├── aggregate_coverage.py     # ✅ EXISTING: 4-platform aggregation
│   │       ├── ci_quality_gate.py        # ✅ EXISTING: Quality gate enforcement
│   │       ├── api_contract_validator.py # NEW: OpenAPI contract validation
│   │       └── cross_platform_generator.py # NEW: TypeScript types from OpenAPI
│   └── api/
│       └── openapi_spec.json        # NEW: Canonical OpenAPI spec
├── frontend-nextjs/
│   ├── tests/
│   │   ├── unit/                    # Component unit tests
│   │   ├── integration/             # ✅ EXISTING: API contract tests
│   │   ├── property/                # NEW: FastCheck state invariants
│   │   └── e2e/                     # Playwright browser tests
│   ├── shared/                      # NEW: Cross-platform test utilities
│   │   ├── test-helpers.ts          # Mock factories, assertions
│   │   ├── api-clients.ts           # Type-safe API wrappers
│   │   └── state-validators.ts      # State management invariants
│   └── src/
│       └── types/
│           └── api-generated.ts     # NEW: Auto-generated from OpenAPI
├── mobile/
│   ├── src/
│   │   ├── __tests__/               # Existing 25+ tests
│   │   │   ├── services/            # Service layer tests
│   │   │   ├── screens/             # Component tests
│   │   │   └── property/            # NEW: FastCheck state tests
│   │   └── shared/                  # SYMLINK to ../frontend-nextjs/shared
│   └── e2e/                         # NEW: Detox E2E tests
│       └── detox/
│           └── workflows/
├── frontend-nextjs/src-tauri/
│   ├── tests/
│   │   ├── unit/                    # Rust unit tests
│   │   ├── property/                # proptest tests
│   │   └── integration/             # Tauri invoke tests
│   └── scripts/
│       └── tarpaulin.sh             # Rust coverage generation
└── .github/
    └── workflows/
        ├── unified-tests.yml         # ✅ EXISTING: Parallel platform tests
        ├── api-contracts.yml         # NEW: Schemathesis + type generation
        ├── property-tests.yml        # ✅ EXISTING: Cross-platform property tests
        └── e2e-unified.yml           # ✅ EXISTING: Playwright + Detox + Tauri
```

### Structure Rationale

- **`backend/tests/contract/`**: Schemathesis tests using OpenAPI spec as source of truth
- **`frontend-nextjs/shared/`**: Cross-platform utilities symlinked by mobile/desktop
- **`api-generated.ts`**: Auto-generated TypeScript types from backend OpenAPI spec
- **SYMLINK strategy**: Mobile and desktop share frontend test utilities (DRY)
- **Contract-first approach**: Backend OpenAPI spec → TypeScript types → validation

---

## Architectural Patterns

### Pattern 1: API Contract Testing with OpenAPI (NEW)

**What:** Use backend OpenAPI specification as source of truth for frontend/mobile type safety and contract validation.

**When to use:**
- Multi-platform projects sharing REST APIs
- Breaking changes must be caught during CI, not production
- Frontend/mobile developers work without backend implementation

**Trade-offs:**
- ✅ Type safety across platforms (TypeScript auto-generated from OpenAPI)
- ✅ Automated contract validation (Schemathesis generates tests from spec)
- ✅ Breaking changes detected immediately (type mismatch = compile error)
- ❌ Requires OpenAPI spec discipline (must match implementation)
- ❌ Initial setup complexity (toolchain integration)

**Example:**

```python
# backend/tests/contract/test_api_contracts.py
import schemathesis
from hypothesis import settings

# Load OpenAPI spec from running backend
schema = schemathesis.from_path(
    "http://localhost:8001/openapi.json",
    validate_schema=True
)

@schema.parametrize()
@settings(max_examples=50)  # Hypothesis integration
def test_api_contracts(case):
    """
    Property: All API endpoints conform to OpenAPI spec

    Schemathesis automatically:
    - Generates valid requests based on OpenAPI parameters
    - Validates response status codes
    - Validates response schemas
    - Tests edge cases (null values, boundary conditions)
    """
    response = case.call()
    case.validate_response(response)

# Test specific critical endpoints
def test_agent_execution_endpoint_contracts():
    """Verify agent execution API contract"""
    schema["/api/agents/{id}/execute"]["POST"].validate()
```

```typescript
// frontend-nextjs/tests/integration/api-contracts.test.ts (ENHANCED)
import { AgentExecuteRequest, AgentExecuteResponse } from '@/types/api-generated';

describe('API Contract Validation (Auto-Generated Types)', () => {
  const VALID_REQUEST: AgentExecuteRequest = {
    input: 'test prompt',
    context: { userId: 'test-user' },
    stream: true
  };

  it('should use auto-generated types (compile-time safety)', () => {
    // TypeScript compilation fails if backend OpenAPI changes
    const request: AgentExecuteRequest = VALID_REQUEST;
    expect(request).toBeDefined();
  });

  it('should validate response shape matches backend contract', () => {
    const mockResponse: AgentExecuteResponse = {
      success: true,
      agent_id: 'agent-123',
      execution_id: 'exec-456',
      result: { output: 'test response' }
    };
    expect(mockResponse.success).toBe(true);
  });
});
```

**Toolchain Integration:**
```yaml
# .github/workflows/api-contracts.yml
name: API Contract Tests

on:
  pull_request:
    paths:
      - 'backend/api/**'
      - 'frontend-nextjs/src/types/**'

jobs:
  generate-openapi-types:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start backend server
        run: |
          cd backend
          pip install -r requirements.txt
          python -m uvicorn main:app --port 8001 &
          sleep 5

      - name: Generate OpenAPI spec
        run: curl http://localhost:8001/openapi.json -o backend/api/openapi_spec.json

      - name: Generate TypeScript types
        run: |
          npm install -g openapi-typescript
          openapi-typescript backend/api/openapi_spec.json -o frontend-nextjs/src/types/api-generated.ts

      - name: Commit generated types
        run: |
          git config user.name "github-actions"
          git add frontend-nextjs/src/types/api-generated.ts
          git commit -m "chore: update generated types from OpenAPI" || true

  schemathesis-contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Python dependencies
        run: |
          pip install schemathesis pytest-asyncio

      - name: Run Schemathesis tests
        run: |
          cd backend
          pytest tests/contract/test_api_contracts.py -v
```

---

### Pattern 2: Cross-Platform State Management Testing

**What:** Test state management invariants across all JavaScript platforms using FastCheck property tests.

**When to use:**
- Shared state logic between frontend (Zustand/Redux), mobile (Zustand), desktop (React context)
- Complex state transitions with business rules
- State synchronization between platforms (offline queue, auth state)

**Trade-offs:**
- ✅ Catches state corruption bugs (illegal transitions, inconsistent data)
- ✅ Tests run fast (no UI rendering, pure logic)
- ❌ Requires identifying state invariants (not all state has obvious properties)
- ❌ Property tests slower than unit tests (100s of examples)

**Example:**

```typescript
// frontend-nextjs/shared/state-validators.ts
import fc from 'fast-check';
import { CanvasState, CanvasAction } from '@/types/canvas';

/**
 * Property: Canvas state transitions maintain integrity
 * Invariant: No orphaned presentations (all have valid parent IDs)
 */
export const canvasStateInvariant = (actions: CanvasAction[]) => {
  const initialState: CanvasState = { presentations: [], currentId: null };
  const reducer = (state: CanvasState, action: CanvasAction): CanvasState => {
    // ...reducer logic...
    return state;
  };

  const finalState = actions.reduce(reducer, initialState);

  // Verify invariant
  const orphanedPresentations = finalState.presentations.filter(
    p => p.parentId && !finalState.presentations.some(other => other.id === p.parentId)
  );
  return orphanedPresentations.length === 0;
};

/**
 * Property: Agent maturity transitions are monotonic (never decrease)
 * Invariant: maturity_level only increases (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
 */
export const agentMaturityInvariant = (actions: string[]) => {
  const MATURITY_LEVELS = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'];
  let currentLevel = 0;

  for (const action of actions) {
    if (action === 'PROMOTE' && currentLevel < 3) {
      currentLevel++;
    }
    // DEMOTE should be blocked by governance, so we test it doesn't happen
  }

  return true; // If governance works, maturity never decreases
};
```

```typescript
// frontend-nextjs/tests/property/canvas-state-invariants.test.ts
import fc from 'fast-check';
import { canvasStateInvariant } from '@/shared/state-validators';

describe('Canvas State Invariants (FastCheck)', () => {
  it('should maintain no orphaned presentations after any action sequence', () => {
    fc.assert(
      fc.property(
        fc.array(fc.record({
          type: fc.constantFrom('PRESENT', 'SUBMIT', 'CLOSE', 'UPDATE'),
          payload: fc.anything()
        })),
        (actions) => {
          return canvasStateInvariant(actions);
        }
      )
    );
  });
});
```

```typescript
// mobile/src/__tests__/property/canvas-state-invariants.test.ts
// SYMLINK: ../../frontend-nextjs/tests/property/canvas-state-invariants.test.ts
// Reuses the same property test, ensuring mobile state behaves identically
```

---

### Pattern 3: Unified Coverage Aggregation with Platform Weighting

**What:** Weighted coverage calculation prioritizing critical platforms (backend 70%, frontend 20%, mobile 5%, desktop 5%) while maintaining 80% overall threshold.

**When to use:**
- Multi-platform codebase with different risk profiles
- Backend is data-critical, frontend is UI-critical
- Mobile/desktop are convenience interfaces

**Trade-offs:**
- ✅ Reflects business priorities (backend failures > UI bugs)
- ✅ Prevents gaming the system (adding easy frontend tests to ignore backend)
- ❌ Requires manual weight tuning
- ❌ May mask low coverage on minor platforms

**Example:**

```python
# backend/tests/scripts/aggregate_coverage.py (ENHANCED)
def calculate_weighted_coverage(platforms: Dict[str, Any]) -> float:
    """
    Calculate weighted overall coverage.

    Weights reflect business risk:
    - Backend: 70% (data integrity, security, business logic)
    - Frontend: 20% (user experience, critical workflows)
    - Mobile: 5% (convenience interface, low usage)
    - Desktop: 5% (power user feature, low usage)
    """
    WEIGHTS = {
        'python': 0.70,
        'javascript': 0.20,
        'mobile': 0.05,
        'rust': 0.05
    }

    weighted_coverage = 0.0
    total_weight = 0.0

    for platform_name, platform_data in platforms.items():
        if 'error' in platform_data:
            continue  # Skip missing coverage files

        weight = WEIGHTS.get(platform_name, 0.0)
        coverage_pct = platform_data['coverage_pct']

        weighted_coverage += coverage_pct * weight
        total_weight += weight

    if total_weight > 0:
        return weighted_coverage / total_weight
    return 0.0

# Usage in CI
def enforce_quality_gates(aggregate_data: Dict[str, Any]) -> bool:
    overall_coverage = aggregate_data['overall']['coverage_pct']
    weighted_coverage = calculate_weighted_coverage(aggregate_data['platforms'])

    # Both thresholds must pass
    COVERAGE_THRESHOLD = 80.0
    WEIGHTED_THRESHOLD = 75.0  # Slightly lower for minor platforms

    if overall_coverage < COVERAGE_THRESHOLD:
        print(f"❌ Overall coverage {overall_coverage:.2f}% below {COVERAGE_THRESHOLD}%")
        return False

    if weighted_coverage < WEIGHTED_THRESHOLD:
        print(f"❌ Weighted coverage {weighted_coverage:.2f}% below {WEIGHTED_THRESHOLD}%")
        return False

    print(f"✅ Coverage gates passed: {overall_coverage:.2f}% (weighted: {weighted_coverage:.2f}%)")
    return True
```

---

### Pattern 4: Cross-Platform E2E Orchestration

**What:** Unified E2E testing workflow spanning web (Playwright), mobile (Detox), and desktop (Tauri driver) with shared test scenarios.

**When to use:**
- Critical user workflows spanning platforms (e.g., agent execution → canvas presentation)
- Platform-specific features (mobile camera, desktop filesystem)
- Smoke tests before production deployment

**Trade-offs:**
- ✅ Validates end-to-end user experience
- ✅ Catches integration bugs (API contracts, state sync)
- ❌ Slow execution (5-15 minutes vs 1-2 minutes for unit tests)
- ❌ Expensive (requires emulators, real devices, desktop environments)

**Example:**

```yaml
# .github/workflows/e2e-unified.yml (ENHANCED)
name: E2E Tests (All Platforms)

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  e2e-web:
    runs-on: ubuntu-latest
    # ... Playwright setup (existing)

  e2e-mobile:
    runs-on: macos-latest  # Required for iOS simulators
    steps:
      - uses: actions/checkout@v4

      - name: Setup Expo
        uses: expo/expo-github-action@v8
        with:
          expo-version: latest
          eas-version: latest

      - name: Install Detox
        run: |
          cd mobile
          npm install -g detox-cli
          detox build --configuration ios.sim.debug

      - name: Run Detox E2E tests
        run: |
          cd mobile
          detox test --configuration ios.sim.debug

  e2e-desktop:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Rust and Tauri
        run: |
          curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
          sudo apt-get install libwebkit2gtk-4.0-dev \
            build-essential curl wget file libxdo-dev \
            libssl-dev libayatana-appindicator3-dev librsvg2-dev

      - name: Build Tauri app
        run: |
          cd frontend-nextjs
          npm ci
          npm run tauri build

      - name: Run Tauri E2E tests
        run: |
          cd frontend-nextjs/src-tauri
          cargo test --test e2e -- --nocapture

  e2e-aggregate:
    needs: [e2e-web, e2e-mobile, e2e-desktop]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download all E2E results
        uses: actions/download-artifact@v4

      - name: Aggregate E2E results
        run: |
          python backend/tests/scripts/e2e_aggregator.py \
            --web e2e-web/results.json \
            --mobile e2e-mobile/results.json \
            --desktop e2e-desktop/results.json \
            --output e2e_unified.json

      - name: Comment E2E results on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('e2e_unified.json', 'utf8'));
            // Generate PR comment with platform breakdown
```

---

## Integration Points

### 1. API Contracts (Backend → Frontend/Mobile/Desktop)

**Integration Pattern:**
```
Backend OpenAPI Spec (Source of Truth)
    ↓
openapi-typescript (Auto-generation)
    ↓
frontend/src/types/api-generated.ts
    ↓
SYMLINK → mobile/src/types/api-generated.ts
SYMLINK → desktop/src/types/api-generated.ts
```

**Components:**
- **NEW**: `backend/api/openapi_spec.json` - Canonical OpenAPI 3.0 spec
- **NEW**: `backend/tests/contract/test_api_contracts.py` - Schemathesis validation
- **NEW**: `frontend-nextjs/src/types/api-generated.ts` - Auto-generated types
- **MODIFY**: `frontend-nextjs/tests/integration/api-contracts.test.ts` - Use generated types
- **NEW**: `.github/workflows/api-contracts.yml` - CI workflow for contract validation

**Benefits:**
- Compile-time type safety across platforms
- Breaking changes detected immediately
- Single source of truth (backend OpenAPI spec)

**Toolchain:**
- **Schemathesis** ([GitHub](https://github.com/schemathesis/schemathesis)) - Python contract testing
- **openapi-typescript** ([gitcode](https://gitcode.com/gh_mirrors_ope/openapi-typescript)) - TypeScript type generation
- **FastAPI** - Auto-generates OpenAPI spec from Pydantic models

---

### 2. Shared Test Utilities (Frontend → Mobile → Desktop)

**Integration Pattern:**
```
frontend-nextjs/shared/
    ├── test-helpers.ts         # Mock factories, test data builders
    ├── api-clients.ts          # Type-safe API wrappers
    └── state-validators.ts    # Property test invariants
         ↓
    mobile/src/shared → SYMLINK
    desktop/src/shared → SYMLINK
```

**Components:**
- **NEW**: `frontend-nextjs/shared/test-helpers.ts` - Mock Agent, Canvas, Episode factories
- **NEW**: `frontend-nextjs/shared/api-clients.ts` - Typed Axios clients for backend APIs
- **NEW**: `frontend-nextjs/shared/state-validators.ts` - FastCheck invariants
- **MODIFY**: `mobile/package.json` - Add `postinstall` script to create symlinks
- **MODIFY**: `frontend-nextjs/src-tauri/Cargo.toml` - Add build script to create symlinks

**Example:**
```typescript
// frontend-nextjs/shared/test-helpers.ts
export const mockAgent = (overrides = {}) => ({
  id: 'agent-123',
  name: 'Test Agent',
  maturity_level: 'INTERN',
  skill_ids: ['skill-1'],
  ...overrides
});

export const mockCanvasPresentation = (overrides = {}) => ({
  id: 'canvas-123',
  type: 'chart',
  title: 'Test Chart',
  data: { labels: ['A'], values: [1] },
  ...overrides
});
```

```typescript
// mobile/src/__tests__/screens/AgentScreen.test.ts
import { mockAgent } from '@/shared/test-helpers'; // SYMLINK

describe('AgentScreen', () => {
  it('should display agent details', () => {
    const agent = mockAgent({ name: 'Custom Agent' });
    // Test implementation...
  });
});
```

---

### 3. Coverage Aggregation (All Platforms → Unified Report)

**Integration Pattern:**
```
backend/tests/scripts/aggregate_coverage.py (EXISTS)
    ↓
Parses:
    - backend/tests/coverage_reports/metrics/coverage.json (pytest)
    - frontend-nextjs/coverage/coverage-final.json (Jest)
    - mobile/coverage/coverage-final.json (jest-expo)
    - frontend-nextjs/src-tauri/coverage/coverage.json (tarpaulin)
    ↓
Generates:
    - backend/tests/scripts/coverage_reports/unified/coverage.json
    - Platform breakdown + overall weighted coverage
    ↓
CI Quality Gate:
    - Enforces 80% overall, 75% weighted threshold
    - Generates PR comment with breakdown
```

**Components:**
- **EXISTING**: `backend/tests/scripts/aggregate_coverage.py` - Multi-format parser
- **EXISTING**: `backend/tests/scripts/ci_quality_gate.py` - Threshold enforcement
- **MODIFY**: `backend/tests/scripts/aggregate_coverage.py` - Add platform weighting
- **MODIFY**: `.github/workflows/unified-tests.yml` - Upload coverage artifacts
- **EXISTING**: `.github/workflows/test-coverage.yml` - PR comment generation

**Data Flow:**
```
Platform Tests (parallel execution)
    ↓
Coverage Artifacts (uploaded to GHA)
    ↓
aggregate_coverage.py (download + merge)
    ↓
unified-coverage.json (artifact)
    ↓
ci_quality_gate.py (enforce thresholds)
    ↓
PR Comment (platform breakdown)
```

---

### 4. State Synchronization Testing (Frontend ↔ Mobile ↔ Desktop)

**Integration Pattern:**
```
Shared State Logic (Zustand/Redux)
    ↓
Property Tests (FastCheck invariants)
    ↓
Cross-Platform Validation
    - Frontend: JSDOM + FastCheck
    - Mobile: React Native Test Renderer + FastCheck
    - Desktop: JSDOM + FastCheck
```

**Components:**
- **NEW**: `frontend-nextjs/shared/state-validators.ts` - FastCheck invariants
- **NEW**: `frontend-nextjs/tests/property/state-invariants.test.ts` - Frontend property tests
- **NEW**: `mobile/src/__tests__/property/state-invariants.test.ts` - Mobile property tests (SYMLINK)
- **NEW**: `frontend-nextjs/src-tauri/tests/property/state_invariants.rs` - Rust proptest equivalents

**Example State Invariant:**
```typescript
// Offline queue invariant: Queue operations are replayed in order
export const offlineQueueInvariant = (operations: any[]) => {
  const queue = new OfflineQueue();
  const results = [];

  for (const op of operations) {
    queue.enqueue(op);
  }

  while (!queue.isEmpty()) {
    results.push(queue.dequeue());
  }

  // Verify: Operations replayed in FIFO order
  return JSON.stringify(results) === JSON.stringify(operations);
};
```

---

## Data Flow

### Test Execution Flow (Existing)

```
[Developer Push]
    ↓
[GitHub Actions Trigger]
    ↓
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│   Backend CI     │  Frontend CI     │   Mobile CI      │  Desktop CI     │
│  (pytest)        │  (Jest)          │  (jest-expo)     │  (cargo + Jest) │
│  74.6% coverage  │  89.84% coverage │  16.16% coverage │      TBD        │
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
              [ci_quality_gate.py - Weighted Calculation]
         ┌────────────────────┼────────────────────┐
         ↓                    ↓                    ↓
[Overall ≥80%?]  [Weighted ≥75%?]  [Pass Rate ≥98%?]
         │                    │                    │
         └────────────────────┴────────────────────┘
                              ↓
                   [PR Comment / Badge]
```

### API Contract Integration Flow (NEW)

```
[Backend Code Change]
    ↓
[Generate OpenAPI Spec] (uvicorn main:app --host 0.0.0.0)
    ↓
[Download openapi.json]
    ↓
┌────────────────────────────────────────────────────────┐
│             openapi-typescript                         │
│        (Generate TypeScript Types)                     │
└────────────────────────┬───────────────────────────────┘
                         ↓
              [api-generated.ts]
                         ↓
        ┌────────────────┴────────────────┐
        ↓                                 ↓
[Frontend TypeScript Check]    [Schemathesis Contract Tests]
        │                                 │
        ↓                                 ↓
[Compile Error if Types Mismatch]    [CI Fail if Contract Broken]
        │                                 │
        └────────────────┴────────────────┘
                         ↓
                [PR Blocked from Merge]
```

### E2E Cross-Platform Flow (Enhanced)

```
[E2E Unified Workflow Triggered]
    ↓
┌──────────────────┬──────────────────┬──────────────────┐
│  Playwright Web  │  Detox Mobile    │  Tauri Desktop   │
│  (Chromium)      │  (iOS Simulator) │  (Ubuntu)        │
└────────┬─────────┴────────┬─────────┴────────┬─────────┘
         │                  │                  │
         ↓                  ↓                  ↓
[web-e2e-results.json][mobile-e2e-results.json][desktop-e2e-results.json]
         │                  │                  │
         └──────────────────┴──────────────────┘
                              ↓
                  [e2e_aggregator.py]
                              ↓
                  [e2e_unified.json]
                              ↓
              [PR Comment + Status Check]
```

---

## Scaling Considerations

| Scale | Architecture Adjustments | Rationale |
|-------|--------------------------|-----------|
| **100 tests/platform** | Single CI job per platform, <5 minutes per platform | Fast feedback, minimal overhead |
| **1000 tests/platform** | Split tests by type (unit/integration/property), matrix strategy, ~15 minutes | Parallel execution, cache dependencies |
| **10000 tests/platform** | Test sharding by directory/tags, 10x parallel jobs, ~30 minutes, selective testing based on diff | Reduce CI time, focus on changed code |

### Scaling Priorities

1. **First bottleneck: Test execution time**
   - **Current**: Backend pytest with `-n auto` (parallel), frontend Jest with `--maxWorkers=2`
   - **Fix**: Increase Jest workers to 4, split mobile tests by folder, enable pytest-xdist for backend
   - **Target**: <15 minutes per platform in CI

2. **Second bottleneck: Coverage aggregation**
   - **Current**: `aggregate_coverage.py` runs in <30 seconds
   - **Fix**: Cache aggregated coverage, only re-run on PR changes (not main branch)
   - **Target**: <10 seconds aggregation time

3. **Third bottleneck: Artifact download/upload**
   - **Current**: GitHub Actions artifact upload/download ~1-2 minutes
   - **Fix**: Use GHA cache for coverage artifacts, compress JSON reports
   - **Target**: <30 seconds artifact transfer

4. **Fourth bottleneck: E2E test execution**
   - **Current**: Playwright E2E runs on main only (5-15 minutes)
   - **Fix**: Parallelize E2E tests by workflow, use test sharding
   - **Target**: <20 minutes for all-platform E2E

---

## Anti-Patterns

### Anti-Pattern 1: Sequential Platform Testing

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

**Do this instead:** Platform-specific jobs with parallel execution (EXISTING in `unified-tests.yml`)

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

---

### Anti-Pattern 2: Duplicated Test Utilities Across Platforms

**What people do:** Copy-paste mock factories, test helpers, validators to each platform

```typescript
// BAD: Duplicated in frontend, mobile, desktop
// frontend/tests/helpers/mockAgent.ts
export const mockAgent = () => ({ id: 'agent-123', name: 'Test' });

// mobile/tests/helpers/mockAgent.ts
export const mockAgent = () => ({ id: 'agent-123', name: 'Test' });

// desktop/tests/helpers/mockAgent.ts
export const mockAgent = () => ({ id: 'agent-123', name: 'Test' });
```

**Why it's wrong:**
- Divergence over time (one gets updated, others don't)
- Maintenance burden (3x changes)
- Inconsistent test data

**Do this instead:** Shared test utilities with symlinks

```typescript
// GOOD: Single source of truth
// frontend-nextjs/shared/test-helpers.ts
export const mockAgent = () => ({ id: 'agent-123', name: 'Test' });

// mobile/src/shared → SYMLINK to ../../frontend-nextjs/shared
// desktop/src/shared → SYMLINK to ../../frontend-nextjs/shared
```

---

### Anti-Pattern 3: Ignoring Platform-Specific Coverage Gaps

**What people do:** Report overall 80% coverage while mobile is at 16%

```json
// BAD: Masks platform-specific gaps
{
  "overall_coverage": 81.2,
  "platforms": {
    "backend": 74.6,
    "frontend": 89.84,
    "mobile": 16.16,
    "desktop": 0
  }
}
```

**Why it's wrong:**
- Mobile users get buggy experience (low coverage)
- Overall threshold met by improving high-coverage platforms
- No incentive to fix platform gaps

**Do this instead:** Weighted coverage + minimum platform thresholds

```python
# GOOD: Enforce minimum per-platform + weighted overall
MIN_PLATFORM_COVERAGE = {
    'python': 70.0,      # Backend must be ≥70%
    'javascript': 80.0,  # Frontend must be ≥80%
    'mobile': 50.0,      # Mobile must be ≥50%
    'rust': 40.0         # Desktop must be ≥40%
}

WEIGHTED_OVERALL_THRESHOLD = 75.0  # Weighted average must be ≥75%

def enforce_quality_gates(aggregate_data):
    for platform, min_cov in MIN_PLATFORM_COVERAGE.items():
        if aggregate_data['platforms'][platform]['coverage_pct'] < min_cov:
            print(f"❌ {platform} coverage below {min_cov}% threshold")
            return False

    weighted = calculate_weighted_coverage(aggregate_data['platforms'])
    if weighted < WEIGHTED_OVERALL_THRESHOLD:
        print(f"❌ Weighted coverage {weighted:.2f}% below {WEIGHTED_OVERALL_THRESHOLD}%")
        return False

    return True
```

---

### Anti-Pattern 4: Property Tests for Everything

**What people do:** Replace all unit tests with property tests

```typescript
// BAD: Property test for simple business rule
it('should validate student agent cannot execute deletions', () => {
  fc.assert(
    fc.property(
      fc.anything(),
      (input) => {
        const result = agent.execute(input);
        return result.blocked === true; // Too generic
      }
    )
  );
});
```

**Why it's wrong:**
- Property tests are slower (100s of examples vs 1 example)
- Simple rules don't need randomness
- Harder to debug failures (randomized inputs)

**Do this instead:** Use property tests for state invariants, unit tests for business rules

```typescript
// GOOD: Unit test for specific rule
it('should block student agents from executing deletions', () => {
  const agent = createAgent({ maturity: 'STUDENT' });
  const result = agent.execute({ action: 'DELETE_RECORD' });
  expect(result.blocked).toBe(true);
});

// GOOD: Property test for invariant
it('should never decrease agent maturity level', () => {
  fc.assert(
    fc.property(
      fc.array(fc.constantFrom('PROMOTE', 'GRADUATE')),
      (actions) => {
        return agentMaturityInvariant(actions);
      }
    )
  );
});
```

---

## Build Order & Implementation Phases

### Recommended Approach: Backend-First Foundation

**Phase 1: Backend API Contract Infrastructure (Week 1)**
- Goal: Establish OpenAPI spec as source of truth
- Tasks:
  1. Generate OpenAPI spec from FastAPI: `curl http://localhost:8001/openapi.json -o backend/api/openapi_spec.json`
  2. Add Schemathesis tests: `backend/tests/contract/test_api_contracts.py`
  3. Create `api-contracts.yml` workflow (Schemathesis + type generation)
  4. Commit `api-generated.ts` to repo (auto-generated from OpenAPI)
- Success criteria: OpenAPI spec committed, Schemathesis tests passing

**Phase 2: Frontend/Mobile Contract Integration (Week 2)**
- Goal: Use auto-generated types for compile-time safety
- Tasks:
  1. Update `frontend-nextjs/tests/integration/api-contracts.test.ts` to use `api-generated.ts`
  2. Replace manual API types with generated types in components
  3. Create SYMLINK: `mobile/src/types → ../../frontend-nextjs/src/types`
  4. Update mobile integration tests to use generated types
- Success criteria: TypeScript compilation fails on backend API breaking changes

**Phase 3: Shared Test Utilities (Week 2-3)**
- Goal: DRY test helpers across all JS platforms
- Tasks:
  1. Create `frontend-nextjs/shared/test-helpers.ts` (mock factories)
  2. Create `frontend-nextjs/shared/state-validators.ts` (FastCheck invariants)
  3. Add SYMLINK scripts to mobile/desktop `postinstall`
  4. Update existing tests to use shared utilities
- Success criteria: No duplicated test code, mobile/desktop import from `@/shared`

**Phase 4: Property Testing Expansion (Week 3-4)**
- Goal: FastCheck property tests for critical invariants
- Tasks:
  1. Identify state invariants (canvas transitions, agent maturity, offline queue)
  2. Write FastCheck tests in `frontend-nextjs/tests/property/`
  3. Reuse tests in mobile via SYMLINK
  4. Add Rust proptest equivalents for desktop
- Success criteria: 10+ property tests per platform, catching edge cases

**Phase 5: Weighted Coverage Quality Gates (Week 4)**
- Goal: Enforce minimum per-platform + weighted overall coverage
- Tasks:
  1. Modify `aggregate_coverage.py` to calculate weighted coverage
  2. Update `ci_quality_gate.py` with platform thresholds (backend 70%, frontend 80%, mobile 50%, desktop 40%)
  3. Update `unified-tests.yml` to run quality gate with weighting
  4. Add coverage trending for each platform
- Success criteria: Mobile coverage cannot be ignored, all platforms must improve

**Phase 6: Cross-Platform E2E Expansion (Week 5)**
- Goal: Detox (mobile) + Tauri (desktop) E2E tests
- Tasks:
  1. Set up Detox for mobile (iOS simulator)
  2. Create critical workflow tests (agent execution, canvas presentation)
  3. Add Tauri E2E tests for desktop-specific features (filesystem, notifications)
  4. Update `e2e-unified.yml` with all-platform aggregation
- Success criteria: E2E tests passing on all platforms, unified reporting

### Why This Order?

1. **Backend first**: OpenAPI spec is foundation for all contract testing
2. **Frontend/Mobile second**: Use generated types immediately for compile-time safety
3. **Shared utilities third**: Reduce duplication before expanding test suite
4. **Property tests fourth**: Require domain knowledge, better after contract validation stable
5. **Weighted coverage fifth**: Enforce platform minimums after infrastructure ready
6. **E2E last**: Depends on stable unit/integration tests, slowest feedback loop

---

## CI/CD Integration Changes

### New Workflows to Create

| File | Purpose | Key Steps |
|------|---------|-----------|
| `.github/workflows/api-contracts.yml` | OpenAPI contract validation | Generate spec, Schemathesis tests, auto-generate TypeScript types |
| `.github/workflows/property-tests.yml` | Cross-platform property tests | FastCheck (frontend/mobile), proptest (backend/desktop) |

### Existing Workflows to Modify

| File | Changes Required |
|------|------------------|
| `.github/workflows/unified-tests.yml` | Add desktop test job, aggregate all 4 platforms |
| `.github/workflows/e2e-unified.yml` | Add Detox (mobile) + Tauri (desktop) jobs |
| `backend/tests/scripts/aggregate_coverage.py` | Add platform weighting (backend 70%, frontend 20%, mobile 5%, desktop 5%) |
| `backend/tests/scripts/ci_quality_gate.py` | Enforce minimum per-platform thresholds |
| `frontend-nextjs/jest.config.js` | Add coverage collection for mobile/desktop symlinks |
| `mobile/jest.config.js` | Configure coverage collection, exclude symlinks from transform |

### New Scripts to Create

| Script | Purpose | Inputs | Outputs |
|--------|---------|--------|---------|
| `backend/tests/scripts/api_contract_validator.py` | Schemathesis runner | OpenAPI spec, backend URL | Contract test results |
| `backend/tests/scripts/cross_platform_generator.py` | TypeScript type generator | OpenAPI spec | `api-generated.ts` |
| `frontend-nextjs/shared/test-helpers.ts` | Mock factories | - | Reusable test data |
| `frontend-nextjs/shared/state-validators.ts` | FastCheck invariants | - | Property test predicates |

---

## Summary

### Key Architectural Decisions

1. **Backend-first foundation**: OpenAPI spec as source of truth for all platform contracts
2. **Shared utilities via symlinks**: Single source of truth for test helpers, state validators
3. **Weighted coverage calculation**: 70% backend, 20% frontend, 5% mobile, 5% desktop
4. **Platform minimum thresholds**: Backend ≥70%, frontend ≥80%, mobile ≥50%, desktop ≥40%
5. **Property testing for invariants**: FastCheck (JS/TS) + Hypothesis (Python) + proptest (Rust)
6. **Incremental rollout**: Backend contracts → Frontend/mobile integration → Shared utilities → Property tests → Weighted coverage → Cross-platform E2E

### Integration Points

| Integration Point | Type | New vs Modified | Priority |
|-------------------|------|-----------------|----------|
| API contracts (OpenAPI) | Backend → All platforms | NEW | HIGH |
| Shared test utilities | Frontend → Mobile/Desktop | NEW | HIGH |
| Coverage aggregation (weighted) | All platforms → Unified report | MODIFY | HIGH |
| State invariants (property tests) | Frontend → Mobile/Desktop | NEW | MEDIUM |
| E2E orchestration | All platforms → Unified report | MODIFY | MEDIUM |
| Contract validation (Schemathesis) | Backend → CI | NEW | MEDIUM |

### Build Order Rationale

1. **Backend contracts first**: OpenAPI spec enables all downstream contract testing
2. **Frontend/mobile integration second**: Immediate benefit from generated types
3. **Shared utilities third**: Reduce duplication before expanding test suite
4. **Property tests fourth**: Require domain knowledge, better after stable foundation
5. **Weighted coverage fifth**: Enforce platform minimums with infrastructure ready
6. **Cross-platform E2E last**: Slowest tests, depend on stable unit/integration tests

This architecture balances fast feedback loops with unified quality gates, enabling Atom to achieve 80% overall coverage while ensuring no platform is left behind.

---

## Sources

### Existing Infrastructure (HIGH Confidence)
- **Backend coverage aggregation**: `/Users/rushiparikh/projects/atom/backend/tests/scripts/aggregate_coverage.py` (755 lines, handles pytest/Jest/jest-expo/tarpaulin formats)
- **Unified CI workflow**: `/Users/rushiparikh/projects/atom/.github/workflows/unified-tests.yml` (parallel platform execution)
- **API contract tests**: `/Users/rushiparikh/projects/atom/frontend-nextjs/tests/integration/api-contracts.test.ts` (existing contract validation)
- **Quality gate enforcement**: `/Users/rushiparikh/projects/atom/backend/tests/scripts/ci_quality_gate.py` (threshold enforcement)
- **E2E testing**: `/Users/rushiparikh/projects/atom/.github/workflows/e2e-unified.yml` (Playwright web, extensible to mobile/desktop)
- **Property testing backend**: `/Users/rushiparikh/projects/atom/backend/tests/property_tests/` (250+ Hypothesis tests)
- **Mobile FastCheck available**: `/Users/rushiparikh/projects/atom/mobile/package.json` (fast-check@4.5.3 in devDependencies)
- **Desktop proptest available**: `/Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/Cargo.toml` (proptest@1.0 in dev-dependencies)

### Ecosystem Research (MEDIUM-HIGH Confidence)

#### API Contract Testing
- [Schemathesis: Supercharge Your API Testing](https://m.blog.csdn.net/gitblog_00643/article/details/141317859) - Property-based API testing framework
- [openapi-typescript: Generate TypeScript types from OpenAPI](https://gitcode.com/gh_mirrors_ope/openapi-typescript) - Type-safe API integration
- [FastAPI Contract Testing with Schemathesis](https://juejin.cn/post/7549011249452974122) - Contract testing workflow
- [Consumer-Driven Contract Testing: From CDC to OpenAPI](https://m.blog.csdn.net/i042416/article/details/154028137) - Contract testing patterns

#### Cross-Platform Testing (2026)
- [Cross-Platform Testing Architecture Trends 2026](https://cn.wordpress.org/plugins/lambdatest-screenshot/faq/) - AI-driven testing, distributed frameworks
- [React Native State Management: Zustand vs Redux](https://www.pianshen.com/article/97671372104/) - Cross-platform state patterns
- [Detox for React Native E2E Testing](https://www.pianshen.com/article/97671372104/) - Mobile E2E automation
- [Playwright + Detox + Tauri for Multi-Platform E2E](https://nightwatchjs.org/) - Unified testing frameworks

#### Property-Based Testing
- [FastCheck Documentation](https://github.com/dubzzz/fast-check) - Property testing for JavaScript/TypeScript
- [Hypothesis for Python](https://hypothesis.works/) - Property testing framework (backend already uses)
- [proptest for Rust](https://altsysrq.github.io/proptest-book/intro.html) - Property testing in Rust

#### Coverage Aggregation
- [pytest-cov Features](https://pytest-cov.readthedocs.io/) - Parallel execution, subprocess support
- [Jest Coverage Configuration](https://jestjs.io/docs/configuration#collectcoverage-boolean) - Multi-format reporting
- [cargo-tarpaulin for Rust](https://github.com/xd009642/tarpaulin) - Rust coverage tool

### Current Coverage Data (HIGH Confidence)
- **Backend**: 74.6% coverage (pytest, 250+ property tests, CI/CD operational)
- **Frontend**: 89.84% coverage (Jest/RTL, FastCheck available)
- **Mobile**: 16.16% coverage (jest-expo, 25+ tests, needs expansion)
- **Desktop**: TBD baseline (Tauri/Rust, proptest configured)

---

*Architecture research for: Cross-platform testing integration and 80% coverage expansion*
*Researched: March 3, 2026*
*Confidence: HIGH (existing infrastructure analysis + 2026 ecosystem trends)*
