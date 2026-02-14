---
phase: 08-80-percent-coverage-push
plan: 40
type: execute
wave: 2
depends_on: []
files_modified:
  - api/device_capabilities.py
  - api/agent_routes.py
  - api/social_media_routes.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "device_capabilities.py tested with 50%+ coverage (248 lines → ~124 lines covered)"
    - "agent_routes.py tested with 50%+ coverage (247 lines → ~124 lines covered)"
    - "social_media_routes.py tested with 50%+ coverage (242 lines → ~121 lines covered)"
    - "All tests passing (no blockers)"
    - "Test execution statistics documented"
  artifacts:
    - path: "tests/api/test_device_capabilities.py"
      provides: "Device capabilities tests"
      min_lines: 200
    - path: "tests/api/test_agent_routes.py"
      provides: "Agent routes tests"
      min_lines: 200
    - path: "tests/api/test_social_media_routes.py"
      provides: "Social media routes tests"
      min_lines: 200
  key_links:
    - from: "test_device_capabilities.py"
      to: "api/device_capabilities.py"
      via: "Device endpoint coverage"
      pattern: "50%+"
    - from: "test_agent_routes.py"
      to: "api/agent_routes.py"
      via: "Agent route coverage"
      pattern: "50%+"
    - from: "test_social_media_routes.py"
      to: "api/social_media_routes.py"
      via: "Social media endpoint coverage"
      pattern: "50%+"
status: pending
created: 2026-02-14
gap_closure: false
---

# Plan 40: Device Capabilities, Agent Routes & Social Media

**Status:** Pending
**Wave:** 2
**Dependencies:** None

## Objective

Create comprehensive tests for device capabilities, agent routes, and social media API routes to achieve 50%+ coverage across all three files.

## Context

Phase 9.2 targets 32-35% overall coverage (+28.12% from 3.9% current) by testing zero-coverage API routes.

**Files in this plan:**

1. **api/device_capabilities.py** (248 lines, 0% coverage)
   - Device capability checks and validations
   - Camera, screen recording, location, notifications, command execution
   - Device permission management
   - Device info and configuration

2. **api/agent_routes.py** (247 lines, 0% coverage)
   - Agent CRUD operations
   - Agent lifecycle management (create, update, delete)
   - Agent status tracking and monitoring
   - Agent configuration and capabilities

3. **api/social_media_routes.py** (242 lines, 0% coverage)
   - Social media platform integrations
   - Content posting and scheduling
   - Social media analytics and monitoring
   - Platform account management

**Total Production Lines:** 737
**Expected Coverage at 50%:** ~369 lines
**Target Coverage Contribution:** +1.5-2.0% overall

## Success Criteria

**Must Have (truths that become verifiable):**
1. device_capabilities.py tested with 50%+ coverage (248 lines → ~124 lines covered)
2. agent_routes.py tested with 50%+ coverage (247 lines → ~124 lines covered)
3. social_media_routes.py tested with 50%+ coverage (242 lines → ~121 lines covered)
4. All tests passing (no blockers)
5. Test execution statistics documented

**Should Have:**
- Error handling tests (400, 404, 500 status codes)
- Permission checks (INTERN+, SUPERVISED+, AUTONOMOUS)
- Device capability validation tests
- Social media platform integration tests

**Could Have:**
- Performance tests (concurrent device operations)
- Rate limiting tests (API throttling)
- Social media content scheduling tests

**Won't Have:**
- Integration tests with real device hardware
- End-to-end social media workflow tests
- Real-time social media streaming tests

## Tasks

### Task 1: Create test_device_capabilities.py

**File:** CREATE: `tests/api/test_device_capabilities.py` (200+ lines)

**Action:**
Create comprehensive tests for device capabilities:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.device_capabilities import router
from core.device_service import DeviceService

# Tests to implement:
# 1. Test GET /capabilities - 200 status, list of capabilities
# 2. Test GET /capabilities/{device_id} - 200 status, device capabilities
# 3. Test POST /capabilities/check - 200 status, capability check result
# 4. Test POST /capabilities/request - 200 status, capability requested
# 5. Test POST /permissions/Grant - 200 status, permission granted
# 6. Test POST /permissions/Revoke - 200 status, permission revoked
# 7. Test GET /device/info - 200 status, device info
# 8. Test PUT /device/info - 200 status, device info updated
# 9. Test POST /device/register - 201 status, device registered
# 10. Test DELETE /device/{device_id} - 200 status, device deleted
```

**Coverage Targets:**
- Capability listing (GET /capabilities)
- Capability checks (POST /capabilities/check)
- Permission management (POST /permissions/Grant, /permissions/Revoke)
- Device info and configuration (GET /device/info, PUT /device/info)
- Device registration and deletion (POST /device/register, DELETE /device/{device_id})
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_device_capabilities.py -v --cov=api/device_capabilities --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 200+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 2: Create test_agent_routes.py

**File:** CREATE: `tests/api/test_agent_routes.py` (200+ lines)

**Action:**
Create comprehensive tests for agent routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.agent_routes import router
from core.agent_service import AgentService

# Tests to implement:
# 1. Test POST /agents - 201 status, agent created
# 2. Test GET /agents - 200 status, list of agents
# 3. Test GET /agents/{agent_id} - 200 status, agent details
# 4. Test PUT /agents/{agent_id} - 200 status, agent updated
# 5. Test PUT /agents/{agent_id}/status - 200 status, agent status updated
# 6. Test PUT /agents/{agent_id}/config - 200 status, agent config updated
# 7. Test DELETE /agents/{agent_id} - 200 status, agent deleted
# 8. Test GET /agents/{agent_id}/capabilities - 200 status, agent capabilities
# 9. Test POST /agents/{agent_id}/train - 200 status, training initiated
# 10. Test GET /agents/{agent_id}/status - 200 status, agent status
```

**Coverage Targets:**
- Agent CRUD operations (POST /agents, GET /agents, GET /agents/{agent_id})
- Agent updates (PUT /agents/{agent_id}, PUT /agents/{agent_id}/status, PUT /agents/{agent_id}/config)
- Agent deletion (DELETE /agents/{agent_id})
- Agent capabilities (GET /agents/{agent_id}/capabilities)
- Agent training (POST /agents/{agent_id}/train)
- Agent status (GET /agents/{agent_id}/status)
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_agent_routes.py -v --cov=api/agent_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 200+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 3: Create test_social_media_routes.py

**File:** CREATE: `tests/api/test_social_media_routes.py` (200+ lines)

**Action:**
Create comprehensive tests for social media routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.social_media_routes import router
from core.social_media_service import SocialMediaService

# Tests to implement:
# 1. Test POST /social/post - 200 status, content posted
# 2. Test GET /social/posts/{post_id} - 200 status, post details
# 3. Test DELETE /social/posts/{post_id} - 200 status, post deleted
# 4. Test GET /social/schedule - 200 status, scheduled posts
# 5. Test POST /social/schedule - 201 status, post scheduled
# 6. Test PUT /social/schedule/{schedule_id} - 200 status, schedule updated
# 7. Test DELETE /social/schedule/{schedule_id} - 200 status, schedule deleted
# 8. Test GET /social/analytics - 200 status, analytics data
# 9. Test GET /social/accounts - 200 status, connected accounts
# 10. Test POST /social/accounts/connect - 200 status, account connected
# 11. Test DELETE /social/accounts/{account_id} - 200 status, account disconnected
```

**Coverage Targets:**
- Content posting (POST /social/post)
- Post management (GET /social/posts/{post_id}, DELETE /social/posts/{post_id})
- Content scheduling (GET /social/schedule, POST /social/schedule, PUT /social/schedule/{schedule_id}, DELETE /social/schedule/{schedule_id})
- Social media analytics (GET /social/analytics)
- Account management (GET /social/accounts, POST /social/accounts/connect, DELETE /social/accounts/{account_id})
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_social_media_routes.py -v --cov=api/social_media_routes --cov-report=term-missing
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
  tests/api/test_device_capabilities.py \
  tests/api/test_agent_routes.py \
  tests/api/test_social_media_routes.py \
  -v \
  --cov=api/device_capabilities \
  --cov=api/agent_routes \
  --cov=api/social_media_routes \
  --cov-report=term-missing \
  --cov-report=html:tests/coverage_reports/html
```

**Verify:**
```bash
# Check coverage output:
# device_capabilities.py: 50%+
# agent_routes.py: 50%+
# social_media_routes.py: 50%+
```

**Done:**
- All tests passing
- Coverage targets met (50%+ each file)
- Test execution statistics documented in plan summary

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_device_capabilities.py | device_capabilities.py | Device endpoint coverage | 50%+ |
| test_agent_routes.py | agent_routes.py | Agent route coverage | 50%+ |
| test_social_media_routes.py | social_media_routes.py | Social media endpoint coverage | 50%+ |

## Progress Tracking

**Starting Coverage:** 3.9%
**Target Coverage (Plan 40):** 5.4-5.9% (+1.5-2.0%)
**Actual Coverage:** Documented in summary after execution

## Notes

- Wave 2 plan (no dependencies)
- Focus on device capabilities, agent management, and social media integration
- Device permission tests (INTERN+, SUPERVISED+, AUTONOMOUS)
- Agent lifecycle tests (create, update, delete, status, config)
- Social media platform tests (Twitter, LinkedIn, Facebook integration)
- Error handling tests (400, 404, 500) essential

**Estimated Duration:** 90 minutes
