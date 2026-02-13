# Phase 8.7 Testing Plan - Zero-Coverage Files by Size

**Created:** 2026-02-13
**Phase:** 8.7 - Next Phase Coverage Expansion
**Current Coverage:** 15.87%
**Target Coverage:** 17-18% (+2-3 percentage points)
**Strategy:** Focus on top zero-coverage files by size for maximum impact

---

## Executive Summary

Phase 8.7 continues the momentum from Phase 8.6 with a focused approach on the largest zero-coverage files. Based on Phase 8.6 learnings showing a 3.38x velocity acceleration when targeting high-impact files (>150 lines), this phase prioritizes the top 15-20 zero-coverage files by size.

**Key Metrics:**
- Current coverage: 15.87%
- Target coverage: 17-18% (+2-3 percentage points)
- Total codebase lines: 112,125
- Lines needed for +2%: 2,243 lines
- Lines needed for +3%: 3,364 lines
- Zero-coverage files remaining: 99

**Phase 8.6 Learnings Applied:**
1. High-impact files (>150 lines) provide 3.38x velocity
2. Target 50% average coverage per file (sustainable)
3. 4 plans per wave with 3-4 files each = optimal flow
4. Focus on workflow, governance, and API files for maximum impact

---

## Top Zero-Coverage Files by Size

### Priority 1: Largest Files (500+ lines) - MAXIMUM IMPACT

| File | Lines | Module | Priority |
|------|-------|--------|----------|
| api/maturity_routes.py | 714 | api | CRITICAL |
| core/competitive_advantage_dashboard.py | 699 | core | HIGH |
| core/integration_enhancement_endpoints.py | 600 | core | HIGH |
| core/constitutional_validator.py | 587 | core | CRITICAL |
| core/database_helper.py | 549 | core | HIGH |
| core/enterprise_user_management.py | 545 | core | MEDIUM |
| api/agent_guidance_routes.py | 537 | api | HIGH |
| core/embedding_service.py | 526 | core | MEDIUM |
| api/analytics_dashboard_routes.py | 507 | api | MEDIUM |
| api/integration_dashboard_routes.py | 506 | api | MEDIUM |

**Total Lines:** 5,770
**Estimated Coverage Impact:** +1.3-1.5% (at 50% average coverage)

### Priority 2: Large Files (400-500 lines) - HIGH IMPACT

| File | Lines | Module | Priority |
|------|-------|--------|----------|
| core/byok_cost_optimizer.py | 483 | core | HIGH |
| core/agent_request_manager.py | 482 | core | HIGH |
| core/competitive_advantage_endpoints.py | 474 | core | MEDIUM |
| api/dashboard_data_routes.py | 472 | api | MEDIUM |
| core/logging_config.py | 471 | core | LOW |
| core/error_middleware.py | 467 | core | LOW |
| core/analytics_endpoints.py | 456 | core | MEDIUM |
| api/document_ingestion_routes.py | 450 | api | MEDIUM |
| api/auth_routes.py | 437 | api | HIGH |
| core/governance_helper.py | 436 | core | HIGH |

**Total Lines:** 4,678
**Estimated Coverage Impact:** +1.0-1.2% (at 50% average coverage)

### Priority 3: Medium Files (300-400 lines) - MODERATE IMPACT

| File | Lines | Module | Priority |
|------|-------|--------|----------|
| api/feedback_enhanced.py | 399 | api | MEDIUM |
| core/feedback_analytics_service.py | 391 | core | MEDIUM |
| api/feedback_analytics.py | 385 | api | MEDIUM |
| api/multi_integration_workflow_routes.py | 380 | api | HIGH |
| core/websocket_manager.py | 377 | core | CRITICAL |
| core/episode_retrieval_service.py | 376 | core | HIGH |
| core/meta_agent_training_orchestrator.py | 373 | core | HIGH |
| core/episode_segmentation_service.py | 362 | core | HIGH |
| core/agent_graduation_service.py | 358 | core | HIGH |
| tools/browser_tool.py | 355 | tools | MEDIUM |

**Total Lines:** 3,756
**Estimated Coverage Impact:** +0.8-1.0% (at 50% average coverage)

---

## Module Breakdown

### Core Module (core/)

**Total Zero-Coverage Files:** 65
**Total Lines:** ~25,000
**Key Files for Phase 8.7:**
- constitutional_validator.py (587 lines) - CRITICAL
- database_helper.py (549 lines) - HIGH
- agent_request_manager.py (482 lines) - HIGH
- websocket_manager.py (377 lines) - CRITICAL
- episode_retrieval_service.py (376 lines) - HIGH

**Strategy:** Focus on governance, database, and episodic memory services.

### API Module (api/)

**Total Zero-Coverage Files:** 22
**Total Lines:** ~9,500
**Key Files for Phase 8.7:**
- maturity_routes.py (714 lines) - CRITICAL
- agent_guidance_routes.py (537 lines) - HIGH
- analytics_dashboard_routes.py (507 lines) - MEDIUM
- integration_dashboard_routes.py (506 lines) - MEDIUM
- auth_routes.py (437 lines) - HIGH

**Strategy:** Focus on maturity, governance, and dashboard endpoints.

### Tools Module (tools/)

**Total Zero-Coverage Files:** 6
**Total Lines:** ~1,800
**Key Files for Phase 8.7:**
- browser_tool.py (355 lines) - MEDIUM

**Strategy:** Browser automation already has partial coverage (17%), focus on other tools.

---

## Coverage Impact Calculation

### Current State

- **Overall coverage:** 15.87%
- **Total codebase lines:** 112,125
- **Covered lines:** ~17,795
- **Uncovered lines:** ~94,330

### Target Calculation

To achieve 17-18% overall coverage (+2-3 percentage points):

| Metric | Value |
|--------|-------|
| Lines needed for +2% | 2,243 lines |
| Lines needed for +3% | 3,364 lines |
| At 50% average coverage | 4,486-6,728 production lines |
| At 60% average coverage | 3,738-5,607 production lines |

### Realistic Target

Based on Phase 8.6 velocity (+1.42% per plan with 4 files × 50% coverage):

**Conservative Estimate (+2%):**
- 4 plans × 4 files = 16 files
- Average 200 lines per file = 3,200 production lines
- At 50% coverage = 1,600 lines covered
- **Impact:** +1.4% overall coverage

**Moderate Estimate (+2.5%):**
- 4 plans × 4 files = 16 files
- Average 250 lines per file = 4,000 production lines
- At 50% coverage = 2,000 lines covered
- **Impact:** +1.8% overall coverage

**Stretch Estimate (+3%):**
- 4 plans × 4 files = 16 files
- Average 300 lines per file = 4,800 production lines
- At 60% coverage = 2,880 lines covered
- **Impact:** +2.6% overall coverage

---

## File Selection Strategy

### Priority 1: Critical Governance Files

**Files:**
1. constitutional_validator.py (587 lines) - Constitutional compliance validation
2. websocket_manager.py (377 lines) - Real-time communication
3. maturity_routes.py (714 lines) - Maturity management API
4. agent_guidance_routes.py (537 lines) - Agent guidance API

**Why:** These are critical system components with zero coverage. Constitutional validator and websocket manager are core infrastructure.

**Total Lines:** 2,215
**Target Coverage:** 60% (higher for critical path)
**Lines to Cover:** 1,329
**Estimated Tests:** 180-220

### Priority 2: Database & Workflow Files

**Files:**
1. database_helper.py (549 lines) - Database utilities
2. agent_request_manager.py (482 lines) - Request orchestration
3. episode_retrieval_service.py (376 lines) - Memory retrieval
4. episode_segmentation_service.py (362 lines) - Memory segmentation

**Why:** Database and episodic memory are core platform features with zero coverage.

**Total Lines:** 1,769
**Target Coverage:** 50% average
**Lines to Cover:** 885
**Estimated Tests:** 120-150

### Priority 3: API Integration Files

**Files:**
1. integration_enhancement_endpoints.py (600 lines) - Integration API
2. analytics_dashboard_routes.py (507 lines) - Analytics API
3. integration_dashboard_routes.py (506 lines) - Dashboard API
4. multi_integration_workflow_routes.py (380 lines) - Workflow API

**Why:** API endpoints are integration points with zero coverage.

**Total Lines:** 1,993
**Target Coverage:** 50% average
**Lines to Cover:** 997
**Estimated Tests:** 140-170

### Priority 4: Enterprise & Analytics Files

**Files:**
1. competitive_advantage_dashboard.py (699 lines) - Analytics dashboard
2. enterprise_user_management.py (545 lines) - User management
3. byok_cost_optimizer.py (483 lines) - Cost optimization
4. analytics_endpoints.py (456 lines) - Analytics API

**Why:** Enterprise features and analytics have zero coverage.

**Total Lines:** 2,183
**Target Coverage:** 40% average (lower for complex orchestration)
**Lines to Cover:** 873
**Estimated Tests:** 120-150

---

## Per-File Targets

### Coverage Targets by File Type

| File Type | Target Coverage | Rationale |
|-----------|-----------------|-----------|
| Governance services | 60% | Critical path, higher standard |
| Database helpers | 50% | Core infrastructure |
| API routes | 50% | Integration points |
| Analytics/dashboards | 40% | Complex orchestration |
| Enterprise features | 40% | Business logic |
| Websocket/real-time | 60% | Critical infrastructure |

### Test Estimates by File Size

| File Lines | Target Coverage | Lines to Cover | Est. Tests |
|------------|-----------------|----------------|------------|
| 700+ | 50% | 350+ | 100-120 |
| 500-700 | 50% | 250-350 | 80-100 |
| 400-500 | 50% | 200-250 | 60-80 |
| 300-400 | 50% | 150-200 | 50-70 |

---

## Testing Strategy

### Phase 8.6 Learnings Applied

#### 1. High-Impact File Selection

**Pattern:** Only files >150 lines for optimal ROI

**Implementation:**
- Prioritize files >400 lines (maximum impact)
- Group related files for efficient context switching
- Focus on governance, database, and workflow modules

**Why:** Phase 8.6 showed 3.38x velocity acceleration with high-impact files.

#### 2. Test Structure (from Plan 15-18)

**Framework:** pytest with fixtures and mocks

**Patterns:**
- Use fixtures for database models (direct creation, not factories)
- Mock external services (LLM, WebSocket, HTTP clients)
- Test both success and error paths
- Include edge cases and boundary conditions

**Example:**
```python
def test_function_success():
    # Arrange
    mock_service = AsyncMock()
    mock_service.execute.return_value = {"status": "success"}

    # Act
    result = await function_under_test(mock_service)

    # Assert
    assert result["status"] == "success"
    mock_service.execute.assert_called_once()

def test_function_error():
    # Arrange
    mock_service = AsyncMock()
    mock_service.execute.side_effect = ValueError("Test error")

    # Act & Assert
    with pytest.raises(ValueError, match="Test error"):
        await function_under_test(mock_service)

def test_function_edge_case():
    # Boundary condition
    result = function_under_test(input_value="")
    assert result is None
```

#### 3. Coverage Targets

**Standard:** 50% average coverage per file (proven sustainable)

**Adjustments:**
- 60% for critical governance files (constitutional_validator, websocket_manager)
- 40% for complex orchestration files (dashboards, enterprise features)
- 50% for standard API routes and database helpers

**Why:** Phase 8.6 achieved 13.02% coverage with 50% average per file.

#### 4. Execution Pattern

**Structure:** 4 plans, 3-4 files per plan

**Metrics:**
- ~30-40 tests per file
- 1.5-2 hours per plan execution
- +0.6-0.8% coverage impact per plan

**Why:** Consistent with Phase 8.6 velocity (+1.42% per plan).

### Test Template

```python
# Test structure from Phase 8.6
import pytest
from unittest.mock import AsyncMock, MagicMock

def test_{function}_success():
    """Test successful {function} execution."""
    # Arrange
    # Act
    # Assert

def test_{function}_error():
    """Test {function} error handling."""
    # Arrange error condition
    # Act & Assert exception

def test_{function}_edge_case():
    """Test {function} boundary condition."""
    # Boundary condition

def test_{function}_integration():
    """Test {function} with real dependencies."""
    # Integration test with database
```

---

## Phase 8.7 Plan Breakdown

### Plan 23: Critical Governance Infrastructure

**Focus:** Constitutional compliance and real-time communication

**Files:**
1. constitutional_validator.py (587 lines)
2. websocket_manager.py (377 lines)
3. governance_helper.py (436 lines)
4. agent_request_manager.py (482 lines)

**Total Lines:** 1,882
**Target Coverage:** 60% average (~1,129 lines, higher for critical path)
**Estimated Tests:** 150-180
**Duration:** 2-3 hours
**Expected Impact:** +1.0-1.2% overall coverage

**Why:** These are critical system components with zero coverage. Constitutional validator and websocket manager are core infrastructure for agent governance.

**Test Strategy:**
- Mock WebSocket connections
- Test constitutional rules validation
- Test request lifecycle management
- Test governance decision caching

---

### Plan 24: Maturity & Agent Guidance APIs

**Focus:** Maturity management and agent guidance endpoints

**Files:**
1. maturity_routes.py (714 lines)
2. agent_guidance_routes.py (537 lines)
3. auth_routes.py (437 lines)
4. episode_retrieval_service.py (376 lines)

**Total Lines:** 2,064
**Target Coverage:** 50% average (~1,032 lines)
**Estimated Tests:** 140-170
**Duration:** 2-3 hours
**Expected Impact:** +0.9-1.1% overall coverage

**Why:** Maturity and agent guidance are key platform features with zero coverage.

**Test Strategy:**
- FastAPI TestClient for endpoint testing
- Mock maturity level transitions
- Test agent guidance workflows
- Test episode retrieval with mock memory

---

### Plan 25: Database & Workflow Infrastructure

**Focus:** Database helpers and workflow orchestration

**Files:**
1. database_helper.py (549 lines)
2. episode_segmentation_service.py (362 lines)
3. agent_graduation_service.py (358 lines)
4. meta_agent_training_orchestrator.py (373 lines)

**Total Lines:** 1,642
**Target Coverage:** 50% average (~821 lines)
**Estimated Tests:** 110-140
**Duration:** 2 hours
**Expected Impact:** +0.7-0.9% overall coverage

**Why:** Database and episodic memory are core platform features.

**Test Strategy:**
- Test database connection management
- Test episode segmentation logic
- Test graduation criteria calculation
- Test training orchestration workflows

---

### Plan 26: API Integration & Summary

**Focus:** Integration endpoints and Phase 8.7 summary

**Files:**
1. integration_enhancement_endpoints.py (600 lines)
2. multi_integration_workflow_routes.py (380 lines)
3. analytics_dashboard_routes.py (507 lines)
4. PHASE_8_7_SUMMARY.md (create)

**Total Lines:** 1,487 (production)
**Target Coverage:** 50% average (~744 lines)
**Estimated Tests:** 100-130
**Duration:** 2 hours
**Expected Impact:** +0.6-0.8% overall coverage

**Why:** Integration APIs are key platform features with zero coverage.

**Test Strategy:**
- Test integration workflow execution
- Test multi-integration coordination
- Test analytics dashboard data
- Create comprehensive Phase 8.7 summary report

---

## Total Phase 8.7 Summary

### Overall Metrics

| Metric | Value |
|--------|-------|
| **Total Files** | 15-16 |
| **Total Production Lines** | ~7,075 |
| **Lines to Cover** | ~3,726 (52.7% average) |
| **Estimated Tests** | 500-620 |
| **Overall Coverage Impact** | +3.2-4.0% |
| **Target Coverage** | 19.0-20.0% |
| **Total Duration** | 8-10 hours |

### By Priority

| Priority | Files | Lines | Coverage | Impact |
|----------|-------|-------|----------|--------|
| Critical governance | 4 | 1,882 | 60% | +1.0-1.2% |
| Maturity & guidance | 4 | 2,064 | 50% | +0.9-1.1% |
| Database & workflow | 4 | 1,642 | 50% | +0.7-0.9% |
| API integration | 4 | 1,487 | 50% | +0.6-0.8% |

### By Module

| Module | Files | Lines | Coverage | Impact |
|--------|-------|-------|----------|--------|
| core | 9 | 4,200 | 53% | +2.0% |
| api | 6 | 2,875 | 50% | +1.3% |

---

## Success Criteria

### Coverage Targets

- [ ] Overall coverage reaches 17-18% (+2-3 percentage points)
- [ ] 15-16 zero-coverage files tested
- [ ] 50% average coverage per file achieved
- [ ] 60% coverage for critical governance files

### Test Quality

- [ ] All tests follow Phase 8.6 patterns (AsyncMock, fixtures)
- [ ] Both success and error paths tested
- [ ] Edge cases and boundary conditions covered
- [ ] No test infrastructure gaps (mocks, fixtures)

### Documentation

- [ ] PHASE_8_7_SUMMARY.md created
- [ ] Coverage metrics updated
- [ ] Lessons learned documented

---

## Risk Mitigation

### Risk 1: Complex WebSocket Testing

**Issue:** websocket_manager.py has complex async WebSocket connections

**Mitigation:** Use AsyncMock pattern from Phase 8.6, mock WebSocket protocol

### Risk 2: Database Integration Tests

**Issue:** database_helper.py requires real database connections

**Mitigation:** Use transaction rollback pattern, create test fixtures

### Risk 3: Constitutional Validator Complexity

**Issue:** constitutional_validator.py has complex rule validation

**Mitigation:** Focus on happy path and key error cases, accept 40-50% coverage

### Risk 4: API Endpoint Dependencies

**Issue:** API routes have many dependencies (database, services, WebSocket)

**Mitigation:** Use dependency override pattern, mock all external services

---

## Next Steps

1. **Execute Plan 23:** Critical Governance Infrastructure (constitutional_validator, websocket_manager)
2. **Execute Plan 24:** Maturity & Agent Guidance APIs (maturity_routes, agent_guidance_routes)
3. **Execute Plan 25:** Database & Workflow Infrastructure (database_helper, episode_segmentation)
4. **Execute Plan 26:** API Integration & Summary (integration endpoints, PHASE_8_7_SUMMARY.md)
5. **Generate Phase 8.7 Summary Report:** Coverage achieved, lessons learned, next phase recommendations

---

## Conclusion

Phase 8.7 continues the momentum from Phase 8.6 with a focused approach on the largest zero-coverage files. By targeting 15-16 high-impact files with realistic coverage targets (50% average), we expect to achieve +3.2-4.0% overall coverage, reaching 19-20% overall coverage.

The strategy is based on Phase 8.6 learnings showing 3.38x velocity acceleration when targeting high-impact files (>150 lines). The 4-plan breakdown ensures efficient execution with consistent velocity (+0.8-1.0% per plan).
