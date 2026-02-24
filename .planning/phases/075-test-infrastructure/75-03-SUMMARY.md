---
phase: 75-test-infrastructure-fixtures
plan: 03
subsystem: testing
tags: [test-fixtures, e2e-testing, factory-pattern, data-generation]

# Dependency graph
requires:
  - phase: 75-test-infrastructure-fixtures
    plan: 02
    provides: auth fixtures and page objects
provides:
  - Test data factories for E2E UI tests (user, agent, skill, project, episode, canvas, chat)
  - Helper functions for unique email, username, password generation
  - Batch creation helpers for multiple test entities
affects: [e2e-ui-tests, test-data-generation, parallel-execution]

# Tech tracking
tech-stack:
  added: [test_data_factory.py module]
  patterns: [function-based factories, unique_test_id collision prevention, realistic defaults]

key-files:
  created:
    - backend/tests/e2e_ui/fixtures/test_data_factory.py
  modified: []

key-decisions:
  - "Function-based factories (not factory_boy) for simplicity in E2E tests"
  - "unique_test_id parameter prevents parallel execution collisions"
  - "Realistic default values (not 'test1', 'foo' placeholders)"
  - "Dictionary return type (not ORM instances) for API-first design"

patterns-established:
  - "Pattern: unique_test_id from worker_id + uuid4 for collision prevention"
  - "Pattern: **kwargs overrides for field customization"
  - "Pattern: Batch creation helpers for multiple test entities"

# Metrics
duration: 4min
completed: 2026-02-23
---

# Phase 75: Test Infrastructure & Fixtures - Plan 03 Summary

**Test data factories for generating unique, realistic test data in E2E UI tests with UUID-based uniqueness to prevent parallel execution collisions**

## Performance

- **Duration:** 4 minutes (245 seconds)
- **Started:** 2026-02-23T16:35:17Z
- **Completed:** 2026-02-23T16:39:22Z
- **Tasks:** 1
- **Files created:** 1 (524 lines)

## Accomplishments

- **test_data_factory.py created** with 7 factory functions for all major entities
- **unique_test_id collision prevention** using worker_id + uuid4 pattern
- **Realistic default values** (not placeholder strings like "test1" or "foo")
- **Full kwargs support** for field overrides in all factories
- **Helper functions** for common data generation (email, username, password)
- **Batch creation helpers** for generating multiple entities efficiently
- **Comprehensive docstrings** with usage examples for all functions
- **62 uses of unique_test_id** ensuring parallel execution safety

## Task Commits

1. **Task 1: Create test data factories for E2E UI tests** - `a7b9a1f8` (feat)

**Plan metadata:** `a7b9a1f8` (feat: test data factories)

## Files Created

### Created
- `backend/tests/e2e_ui/fixtures/test_data_factory.py` - Complete test data factory module with:
  - **7 factory functions**: user_factory, agent_factory, skill_factory, project_factory, episode_factory, canvas_factory, chat_message_factory
  - **4 helper functions**: random_email, random_username, random_password, random_project_name
  - **3 batch creation helpers**: create_user_batch, create_agent_batch, create_skill_batch
  - **524 lines** with comprehensive documentation
  - **Function-based design** (not class-based factory_boy)
  - **Dictionary return type** for API-first test setup

## Factory Functions Overview

### user_factory(unique_test_id, **kwargs)
Generates user test data with unique email, username, display name.

**Defaults:**
- email: `test.user.{unique_test_id}@example.com`
- username: `testuser_{unique_test_id}`
- display_name: `Test User {short_id}`
- password: `SecureTestPassword123!` (consistent for tests)
- role: `MEMBER`
- specialty: `Quality Assurance`

### agent_factory(unique_test_id, **kwargs)
Generates agent test data with governance maturity levels.

**Defaults:**
- name: `Test Agent {short_id}`
- category: `testing`
- maturity_level: `INTERN`
- confidence_score: `0.6` (auto-adjusted based on maturity)
- capabilities: `["markdown", "charts"]`

**Special behavior:** confidence_score auto-adjusts based on maturity_level (STUDENT: 0.4, INTERN: 0.6, SUPERVISED: 0.8, AUTONOMOUS: 0.95)

### skill_factory(unique_test_id, **kwargs)
Generates skill test data for marketplace testing.

**Defaults:**
- name: `test-skill-{short_id}`
- display_name: `Test Skill {short_id}`
- category: `productivity`
- permissions: `["read:basic", "write:basic"]`
- version: `1.0.0`

### project_factory(unique_test_id, **kwargs)
Generates project test data for workspace testing.

**Defaults:**
- name: `Test Project {short_id}`
- owner_id: `user_{short_id}`
- status: `ACTIVE`
- type: `automation`
- budget: `10000.00`

### episode_factory(unique_test_id, **kwargs)
Generates episodic memory test data for agent learning.

**Defaults:**
- title: `Test Episode {short_id}`
- episode_type: `testing`
- status: `completed`
- maturity_at_time: `INTERN`
- constitutional_score: `0.85`

### canvas_factory(unique_test_id, **kwargs)
Generates canvas presentation test data for agent communication.

**Defaults:**
- canvas_id: `canvas_{unique_test_id}`
- type: `form`
- components: Text and button components
- layout: `vertical` with `medium` spacing

### chat_message_factory(unique_test_id, **kwargs)
Generates chat message test data for conversation testing.

**Defaults:**
- content: `Test message {unique_test_id}`
- role: `user`
- agent_id: `agent_{short_id}`
- timestamp: Current UTC time

## Usage Examples

### Basic Factory Usage
```python
from backend.tests.e2e_ui.fixtures.test_data_factory import user_factory, agent_factory

# In a test with worker_id fixture
user_data = user_factory(worker_id)
agent_data = agent_factory(worker_id, maturity_level="AUTONOMOUS")

# user_data = {
#     "email": "test.user.gw0_abc123@example.com",
#     "username": "testuser_gw0_abc123",
#     "display_name": "Test User gw0_abc1",
#     "password": "SecureTestPassword123!",
#     ...
# }
```

### Field Overrides with **kwargs
```python
# Override specific fields
admin_user = user_factory(worker_id, role="ADMIN", email="admin@example.com")
autonomous_agent = agent_factory(worker_id, maturity_level="AUTONOMOUS", confidence_score=0.98)
```

### Batch Creation
```python
from backend.tests.e2e_ui.fixtures.test_data_factory import create_user_batch, create_agent_batch

# Create multiple users with sequential IDs
users = create_user_batch(worker_id, count=5)
agents = create_agent_batch(worker_id, count=3, category="automation")
```

### Helper Functions
```python
from backend.tests.e2e_ui.fixtures.test_data_factory import random_email, random_password

email = random_email(worker_id)  # "test.user.gw0_abc123@example.com"
password = random_password()  # "SecureTestPassword123!"
```

## Decisions Made

- **Function-based factories over factory_boy**: Chosen for simplicity and API-first design. Factories return dictionaries (not ORM instances) suitable for API requests and test setup.
- **unique_test_id collision prevention**: All factories use unique_test_id (from worker_id + uuid4) to prevent parallel execution collisions. 62 occurrences ensure comprehensive coverage.
- **Realistic default values**: Rejected placeholder strings like "test1" or "foo". All defaults are realistic and descriptive (e.g., "Test Agent gw0_abc1").
- **Dictionary return type**: Factories return dictionaries (not SQLAlchemy models) for API-first test setup. Tests can POST to API endpoints or insert into database as needed.
- **Consistent password**: All users get "SecureTestPassword123!" for test simplicity while meeting security requirements.

## Deviations from Plan

None - plan executed exactly as specified. All requirements met:
- ✅ All 7 factories created (user, agent, skill, project, episode, canvas, chat_message)
- ✅ All factories accept unique_test_id parameter
- ✅ All factories support **kwargs for field overrides
- ✅ Generated data includes unique_test_id in relevant fields
- ✅ Realistic default values (not placeholders)
- ✅ 524 lines (exceeds minimum 200 lines)
- ✅ Helper functions created (random_email, random_username, random_password, random_project_name)

## Issues Encountered

None - all tasks completed successfully with no blocking issues.

## Verification Results

All verification steps passed:

1. ✅ **user_factory exists** - Factory function created with email, username, display_name, password
2. ✅ **agent_factory exists** - Factory function created with maturity_level, confidence_score auto-adjustment
3. ✅ **62 unique_test_id occurrences** - Exceeds minimum requirement of 7
4. ✅ **Import test passes** - All factories execute correctly
5. ✅ **kwargs override works** - Custom email and role override successful
6. ✅ **Uniqueness verified** - Different unique_test_id produces different data
7. ✅ **Realistic data** - No placeholder strings like "test1" or "foo"
8. ✅ **524 lines** - Exceeds minimum 200 lines requirement

## Next Phase Readiness

✅ **Test data factories complete** - All factories created and verified

**Ready for:**
- Plan 75-04: Worker-based Database Isolation (unique_test_id integration)
- Plan 75-05: API-First Setup Utilities (factory-based data generation)
- E2E UI test implementation (Phases 76-80)

**Recommendations for usage:**
1. Use factories in E2E UI tests for consistent test data generation
2. Combine with worker_id fixture for parallel execution safety
3. Use batch helpers for creating multiple test entities efficiently
4. Override fields with **kwargs for test-specific scenarios

---

*Phase: 75-test-infrastructure-fixtures*
*Plan: 03*
*Completed: 2026-02-23*
*Commit: a7b9a1f8*
