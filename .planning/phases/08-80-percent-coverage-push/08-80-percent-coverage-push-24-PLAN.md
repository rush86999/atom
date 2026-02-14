---
phase: 08-80-percent-coverage-push
plan: 24
wave: 4
depends_on: []
status: pending
created: 2026-02-13
gap_closure: false
---

# Plan 24: Maturity & Agent Guidance APIs

**Status:** Pending
**Wave:** 4 (parallel with Plans 23, 25, 26)
**Dependencies:** None

## Objective

Create comprehensive baseline unit tests for 4 maturity and agent guidance API files, achieving 50% average coverage to contribute +0.9-1.1% toward Phase 8.7's 17-18% overall coverage goal.

## Context

Phase 8.7 targets 17-18% overall coverage. This plan focuses on maturity management and agent guidance endpoints:

1. **maturity_routes.py** (714 lines) - Maturity level transitions
2. **agent_guidance_routes.py** (537 lines) - Agent guidance workflows
3. **auth_routes.py** (437 lines) - Authentication endpoints
4. **episode_retrieval_service.py** (376 lines) - Episode memory retrieval

**Total Production Lines:** 2,064
**Expected Coverage at 50%:** ~1,032 lines
**Coverage Contribution:** +0.9-1.1 percentage points

## Success Criteria

**Must Have:**
1. Maturity routes API has 50%+ test coverage (FastAPI TestClient)
2. Agent guidance routes API has 50%+ test coverage
3. Auth routes API has 50%+ test coverage
4. Episode retrieval service has 50%+ test coverage (AsyncMock)

## Tasks

### Task 1: Create test_maturity_routes.py

**Files:**
- CREATE: `backend/tests/api/test_maturity_routes.py` (700+ lines, 35-40 tests)

**Action:**
```bash
# Use FastAPI TestClient for endpoint testing
# Test maturity level transitions (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
# Test permission checks by maturity level
# Test maturity assessment endpoints
```

**Done:**
- 35-40 tests covering all maturity endpoints
- TestClient for API testing
- Mock authentication for protected routes

### Task 2: Create test_agent_guidance_routes.py

**Files:**
- CREATE: `backend/tests/api/test_agent_guidance_routes.py` (550+ lines, 30-35 tests)

**Action:**
```bash
# Test agent guidance workflow endpoints
# Test real-time guidance request handling
# Test guidance response structure
# Test integration with canvas system
```

**Done:**
- 30-35 tests for guidance endpoints
- WebSocket integration tested
- Canvas coordination mocked

### Task 3: Create test_auth_routes.py

**Files:**
- CREATE: `backend/tests/api/test_auth_routes.py` (450+ lines, 25-30 tests)

**Action:**
```bash
# Test authentication endpoints (signup, login, logout)
# Test JWT token refresh flow
# Test session management
# Test password reset flow
```

**Done:**
- 25-30 tests for auth endpoints
- JWT validation tested
- Session management validated

### Task 4: Create test_episode_retrieval_service.py

**Files:**
- CREATE: `backend/tests/unit/test_episode_retrieval_service.py` (400+ lines, 25-30 tests)

**Action:**
```bash
# Test temporal episode retrieval
# Test semantic episode retrieval
# Test context-aware retrieval
# Test episode access control
```

**Done:**
- 25-30 tests for retrieval modes
- Episode memory mocked
- Access control validated

---

## Key Links

| From | To | Via |
|------|-----|-----|
| test_maturity_routes.py | api/maturity_routes.py | TestClient |
| test_agent_guidance_routes.py | api/agent_guidance_routes.py | TestClient |
| test_auth_routes.py | api/auth_routes.py | TestClient |
| test_episode_retrieval_service.py | core/episode_retrieval_service.py | AsyncMock |

## Progress Tracking

**Plan 24 Target:** +0.9-1.1 percentage points
**Estimated Tests:** 140-170
**Duration:** 2-3 hours
