---
phase: 09-1-api-route-governance-resolution
plan: 35
type: execute
wave: 1
depends_on: []
files_modified:
  - api/agent_status_endpoints.py
  - api/supervised_queue_routes.py
  - api/supervision_routes.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "agent_status_endpoints.py tested with 50%+ coverage (134 lines → ~67 lines covered)"
    - "supervised_queue_routes.py tested with 50%+ coverage (109 lines → ~55 lines covered)"
    - "supervision_routes.py tested with 50%+ coverage (112 lines → ~56 lines covered)"
    - "All tests passing (no blockers)"
    - "Test execution statistics documented"
  artifacts:
    - path: "tests/api/test_agent_status_endpoints.py"
      provides: "Agent status endpoint tests"
      min_lines: 200
    - path: "tests/api/test_supervised_queue_routes.py"
      provides: "Supervised queue route tests"
      min_lines: 200
    - path: "tests/api/test_supervision_routes.py"
      provides: "Supervision route tests"
      min_lines: 200
  key_links:
    - from: "test_agent_status_endpoints.py"
      to: "api/agent_status_endpoints.py"
      via: "Endpoint coverage"
      pattern: "50%+"
    - from: "test_supervised_queue_routes.py"
      to: "api/supervised_queue_routes.py"
      via: "Route coverage"
      pattern: "50%+"
    - from: "test_supervision_routes.py"
      to: "api/supervision_routes.py"
      via: "Supervision endpoint coverage"
      pattern: "50%+"
status: pending
created: 2026-02-14
gap_closure: false
---

# Plan 35: Agent Status & Supervision Routes

**Status:** Pending
**Wave:** 1
**Dependencies:** None

## Objective

Create comprehensive tests for agent status endpoints and supervision-related API routes to achieve 50%+ coverage across all three files.

## Context

Phase 9.1 targets 27-29% overall coverage (+5-7% from 22.15% baseline) by testing zero-coverage API routes and governance-dependent paths.

**Files in this plan:**

1. **api/agent_status_endpoints.py** (134 lines, 0% coverage)
   - Agent status tracking and monitoring endpoints
   - Real-time agent state management
   - Status query and update operations

2. **api/supervised_queue_routes.py** (109 lines, 0% coverage)
   - Supervised agent queue management
   - Queue position and status tracking
   - Approval workflow for SUPERVISED agents

3. **api/supervision_routes.py** (112 lines, 0% coverage)
   - Real-time supervision endpoint routes
   - Intervention and correction controls
   - Supervision session management

**Total Production Lines:** 355
**Expected Coverage at 50%:** ~178 lines
**Target Coverage Contribution:** +1.5-2.0% overall

## Success Criteria

**Must Have (truths that become verifiable):**
1. agent_status_endpoints.py tested with 50%+ coverage (134 lines → ~67 lines covered)
2. supervised_queue_routes.py tested with 50%+ coverage (109 lines → ~55 lines covered)
3. supervision_routes.py tested with 50%+ coverage (112 lines → ~56 lines covered)
4. All tests passing (no blockers)
5. Test execution statistics documented

**Should Have:**
- Error handling tests (400, 404, 500 status codes)
- Governance integration tests (SUPERVISED agent permissions)
- Queue workflow tests (enqueue, dequeue, position tracking)

**Could Have:**
- Performance tests (concurrent status updates)
- Load tests (high-frequency status queries)

**Won't Have:**
- Integration tests with real agent execution
- End-to-end supervision workflow tests

## Tasks

### Task 1: Create test_agent_status_endpoints.py

**File:** CREATE: `tests/api/test_agent_status_endpoints.py` (200+ lines)

**Action:**
Create comprehensive tests for agent status endpoints:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.agent_status_endpoints import router
from core.agent_governance_service import AgentGovernanceService

# Tests to implement:
# 1. Test GET /agents/{agent_id}/status - 200 status, correct status object
# 2. Test GET /agents/{agent_id}/status - 404 for non-existent agent
# 3. Test PUT /agents/{agent_id}/status - 200 status, status updated
# 4. Test PUT /agents/{agent_id}/status - 400 for invalid status transition
# 5. Test GET /agents/status/active - 200 status, list of active agents
# 6. Test GET /agents/status/inactive - 200 status, list of inactive agents
# 7. Test GET /agents/{agent_id}/status/history - 200 status, status history
# 8. Test WebSocket /agents/{agent_id}/status/stream - connection established
# 9. Test governance integration (STUDENT/INTERN/SUPERVISED/AUTONOMOUS status checks)
# 10. Test error handling (500 status for service failures)
```

**Coverage Targets:**
- Status retrieval (GET /agents/{agent_id}/status)
- Status updates (PUT /agents/{agent_id}/status)
- Status filtering (GET /agents/status/active, /inactive)
- Status history (GET /agents/{agent_id}/status/history)
- WebSocket streaming (/agents/{agent_id}/status/stream)
- Error handling (404, 400, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_agent_status_endpoints.py -v --cov=api/agent_status_endpoints --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 200+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 2: Create test_supervised_queue_routes.py

**File:** CREATE: `tests/api/test_supervised_queue_routes.py` (200+ lines)

**Action:**
Create comprehensive tests for supervised queue routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.supervised_queue_routes import router
from core.agent_governance_service import AgentGovernanceService

# Tests to implement:
# 1. Test POST /supervised/queue/enqueue - 200 status, agent queued
# 2. Test POST /supervised/queue/enqueue - 400 for AUTONOMOUS agents (not allowed)
# 3. Test POST /supervised/queue/dequeue/{agent_id} - 200 status, agent dequeued
# 4. Test GET /supervised/queue/position/{agent_id} - 200 status, position returned
# 5. Test GET /supervised/queue/position/{agent_id} - 404 for agent not in queue
# 6. Test GET /supervised/queue - 200 status, all queued agents
# 7. Test PUT /supervised/queue/approve/{agent_id} - 200 status, agent approved
# 8. Test PUT /supervised/queue/reject/{agent_id} - 200 status, agent rejected
# 9. Test DELETE /supervised/queue/{agent_id} - 200 status, agent removed from queue
# 10. Test queue limit enforcement (max 10 agents in queue)
```

**Coverage Targets:**
- Enqueue operations (POST /supervised/queue/enqueue)
- Dequeue operations (POST /supervised/queue/dequeue/{agent_id})
- Position queries (GET /supervised/queue/position/{agent_id})
- Queue listing (GET /supervised/queue)
- Approval workflow (PUT /supervised/queue/approve/{agent_id})
- Rejection workflow (PUT /supervised/queue/reject/{agent_id})
- Queue removal (DELETE /supervised/queue/{agent_id})
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_supervised_queue_routes.py -v --cov=api/supervised_queue_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 200+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 3: Create test_supervision_routes.py

**File:** CREATE: `tests/api/test_supervision_routes.py` (200+ lines)

**Action:**
Create comprehensive tests for supervision routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.supervision_routes import router
from core.supervision_service import SupervisionService

# Tests to implement:
# 1. Test POST /supervision/start/{agent_id} - 200 status, supervision started
# 2. Test POST /supervision/start/{agent_id} - 400 for SUPERVISED agents
# 3. Test POST /supervision/pause/{agent_id} - 200 status, supervision paused
# 4. Test POST /supervision/correct/{agent_id} - 200 status, correction applied
# 5. Test POST /supervision/terminate/{agent_id} - 200 status, supervision terminated
# 6. Test GET /supervision/session/{agent_id} - 200 status, session details
# 7. Test GET /supervision/session/{agent_id} - 404 for no active session
# 8. Test GET /supervision/history/{agent_id} - 200 status, supervision history
# 9. Test WebSocket /supervision/stream/{agent_id} - connection established
# 10. Test intervention counting (pause, correct, terminate actions)
```

**Coverage Targets:**
- Session start (POST /supervision/start/{agent_id})
- Session pause (POST /supervision/pause/{agent_id})
- Session correction (POST /supervision/correct/{agent_id})
- Session termination (POST /supervision/terminate/{agent_id})
- Session queries (GET /supervision/session/{agent_id})
- Supervision history (GET /supervision/history/{agent_id})
- WebSocket streaming (/supervision/stream/{agent_id})
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_supervision_routes.py -v --cov=api/supervision_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 200+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 4: Run test suite and document coverage

**Action:**
Run all three test files and document coverage statistics:

```bash
source venv/bin/activate && python -m pytest \
  tests/api/test_agent_status_endpoints.py \
  tests/api/test_supervised_queue_routes.py \
  tests/api/test_supervision_routes.py \
  -v \
  --cov=api/agent_status_endpoints \
  --cov=api/supervised_queue_routes \
  --cov=api/supervision_routes \
  --cov-report=term-missing \
  --cov-report=html:tests/coverage_reports/html
```

**Verify:**
```bash
# Check coverage output:
# agent_status_endpoints.py: 50%+
# supervised_queue_routes.py: 50%+
# supervision_routes.py: 50%+
```

**Done:**
- All tests passing
- Coverage targets met (50%+ each file)
- Test execution statistics documented in plan summary

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_agent_status_endpoints.py | agent_status_endpoints.py | Endpoint coverage | 50%+ |
| test_supervised_queue_routes.py | supervised_queue_routes.py | Route coverage | 50%+ |
| test_supervision_routes.py | supervision_routes.py | Supervision endpoint coverage | 50%+ |

## Progress Tracking

**Starting Coverage:** 22.15%
**Target Coverage (Plan 35):** 23.65-24.15% (+1.5-2.0%)
**Actual Coverage:** Documented in summary after execution

## Notes

- Wave 1 plan (no dependencies)
- Focus on agent status tracking and supervision workflow endpoints
- Governance integration (SUPERVISED agent permissions) critical for queue tests
- WebSocket streaming tests for both status and supervision routes
- Error handling tests (400, 404, 500) essential for robust coverage

**Estimated Duration:** 90 minutes
