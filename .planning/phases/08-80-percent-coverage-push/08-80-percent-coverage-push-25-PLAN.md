---
phase: 08-80-percent-coverage-push
plan: 25
wave: 4
depends_on: []
status: pending
created: 2026-02-13
gap_closure: false
---

# Plan 25: Database & Workflow Infrastructure

**Status:** Pending
**Wave:** 4 (parallel with Plans 23, 24, 26)
**Dependencies:** None

## Objective

Create comprehensive baseline unit tests for 4 database and workflow infrastructure files, achieving 50% average coverage to contribute +0.7-0.9% toward Phase 8.7's 17-18% overall coverage goal.

## Context

Phase 8.7 targets 17-18% overall coverage. This plan focuses on database helpers and episodic memory infrastructure:

1. **database_helper.py** (549 lines) - Database connection management
2. **episode_segmentation_service.py** (362 lines) - Episode segmentation logic
3. **agent_graduation_service.py** (358 lines) - Agent graduation criteria
4. **meta_agent_training_orchestrator.py** (373 lines) - Training orchestration

**Total Production Lines:** 1,642
**Expected Coverage at 50%:** ~821 lines
**Coverage Contribution:** +0.7-0.9 percentage points

## Success Criteria

**Must Have:**
1. Database helper has 50%+ test coverage (connection management, transactions)
2. Episode segmentation service has 50%+ test coverage (segmentation logic)
3. Agent graduation service has 50%+ test coverage (graduation criteria)
4. Meta agent training orchestrator has 50%+ test coverage (training workflows)

## Tasks

### Task 1: Create test_database_helper.py

**Files:**
- CREATE: `backend/tests/unit/test_database_helper.py` (500+ lines, 30-35 tests)

**Action:**
```bash
# Test database connection pooling
# Test transaction management
# Test query execution
# Test connection error handling
# Test database health checks
```

**Done:**
- 30-35 tests for database operations
- Connection pooling tested
- Transaction rollback validated

### Task 2: Create test_episode_segmentation_service.py

**Files:**
- CREATE: `backend/tests/unit/test_episode_segmentation_service.py` (350+ lines, 25-30 tests)

**Action:**
```bash
# Test time-based episode segmentation
# Test topic change detection
# Test task completion segmentation
# Test episode boundary identification
```

**Done:**
- 25-30 tests for segmentation logic
- Time gaps tested
- Topic changes validated

### Task 3: Create test_agent_graduation_service.py

**Files:**
- CREATE: `backend/tests/unit/test_agent_graduation_service.py` (350+ lines, 25-30 tests)

**Action:**
```bash
# Test graduation eligibility calculation
# Test episode count requirements
# Test intervention rate thresholds
# Test constitutional compliance score
# Test maturity level promotion
```

**Done:**
- 25-30 tests for graduation logic
- Eligibility criteria tested
- Promotion logic validated

### Task 4: Create test_meta_agent_training_orchestrator.py

**Files:**
- CREATE: `backend/tests/unit/test_meta_agent_training_orchestrator.py` (350+ lines, 25-30 tests)

**Action:**
```bash
# Test training workflow orchestration
# Test training scenario selection
# Test training progress tracking
# Test training completion
```

**Done:**
- 25-30 tests for training workflows
- Orchestration logic tested
- Progress tracking validated

---

## Key Links

| From | To | Via |
|------|-----|-----|
| test_database_helper.py | core/database_helper.py | mock_db |
| test_episode_segmentation_service.py | core/episode_segmentation_service.py | AsyncMock |
| test_agent_graduation_service.py | core/agent_graduation_service.py | AsyncMock |
| test_meta_agent_training_orchestrator.py | core/meta_agent_training_orchestrator.py | AsyncMock |

## Progress Tracking

**Plan 25 Target:** +0.7-0.9 percentage points
**Estimated Tests:** 110-140
**Duration:** 2 hours
