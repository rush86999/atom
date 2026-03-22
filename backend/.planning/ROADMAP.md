# Atom Test Coverage Initiative - Roadmap

**Project**: Atom AI-Powered Business Automation Platform
**Initiative**: Test Coverage Improvement & Quality Assurance
**Current Coverage**: 21.35% (as of 2026-03-21)
**Target Coverage**: 50% (Phase 10 goal) → 80% (ultimate goal)

---

## Current Milestone: v3.3 Bug Fixing & Coverage Expansion

**Goal**: Fix all blocking test issues and expand coverage from 21.35% to 50%

### Phase 218: Fix Test Collection Errors
**Status**: PLANNED
**Priority**: CRITICAL (blocking test execution)
**Plans:** 1 plan

**Goal**: Fix 2 test files with collection errors that prevent tests from running

**Requirements**:
- REQ-001: All test files must collect without errors
- REQ-002: All test dependencies must be available or mocked

**Gap Closure**: Closes collection errors blocking full test suite execution

**Plans:**
- [ ] 218-01-PLAN.md — Make aiofiles optional in trajectory.py and fix test imports

**Success Criteria**:
- [ ] `pytest tests/core/test_time_expression_parser.py --collect-only` succeeds
- [ ] `pytest tests/core/test_trace_validator.py --collect-only` succeeds
- [ ] Full test suite collects with 0 errors

**Estimated Time**: 1-2 hours

---

### Phase 219: Fix Industry Workflow Test Failures
**Status**: PENDING
**Priority**: CRITICAL (quality gate blocking)

**Goal**: Fix all 10 failing tests in `test_industry_workflow_endpoints.py`

**Requirements**:
- REQ-003: 98%+ test pass rate required for coverage expansion
- REQ-004: All industry workflow endpoints must have passing tests

**Gap Closure**: Closes test failures blocking progress on coverage goals

**Tasks**:
1. Investigate 10 failing tests in `test_industry_workflow_endpoints.py`
   - Analyze failure patterns and root causes
   - Determine if test fixtures or implementation needs fixes
2. Fix test assertions or implementation bugs
   - Update tests to match actual API behavior
   - Fix implementation if tests are correct
3. Verify all 10 tests passing
   - Run full test suite for the file
   - Confirm 100% pass rate
4. Update test documentation
   - Document any test pattern changes
   - Add notes for future maintainers

**Success Criteria**:
- [ ] All 10 tests in `test_industry_workflow_endpoints.py` passing
- [ ] Overall test pass rate ≥98%
- [ ] No regression in other tests

**Estimated Time**: 2-3 hours

---

### Phase 220: Improve Test Assertion Density
**Status**: PENDING
**Priority**: HIGH (test quality)

**Goal**: Bring 5 test files with low assertion density above 0.15 threshold

**Requirements**:
- REQ-005: All test files must have assertion density ≥0.15
- REQ-006: Tests must validate behavior, not just execute code

**Gap Closure**: Closes test quality gaps identified in coverage report

**Tasks**:
1. Improve `test_user_management_monitoring.py` assertion density (0.054 → 0.15+)
   - Add assertions for expected outcomes
   - Remove no-op test code
2. Improve `test_supervision_learning_integration.py` assertion density (0.042 → 0.15+)
   - Add validation for learning outcomes
   - Add assertions for supervision states
3. Improve `test_mcp_a2a_tools.py` assertion density (0.141 → 0.15+)
   - Add tool execution result assertions
   - Validate side effects
4. Improve `test_email_api_ingestion.py` assertion density (0.105 → 0.15+)
   - Add email processing assertions
   - Validate database state changes
5. Improve `test_auth_routes_coverage.py` assertion density (0.091 → 0.15+)
   - Add auth outcome assertions
   - Validate token/session creation
6. Verify all files meet 0.15 threshold
   - Run assertion density checker
   - Confirm all files pass
7. Document assertion density patterns
   - Create best practices guide
   - Add examples to testing docs

**Success Criteria**:
- [ ] All 5 test files ≥0.15 assertion density
- [ ] No tests marked with low assertion density warning
- [ ] Test quality documentation updated

**Estimated Time**: 4-6 hours

---

### Phase 221: High-Impact Coverage Expansion (Zero → 40%)
**Status**: PENDING
**Priority**: HIGH (primary coverage goal)

**Goal**: Add test coverage to 10 largest zero-coverage modules (minimum 40% coverage each)

**Requirements**:
- REQ-007: Critical code paths must have test coverage
- REQ-008: Target highest-impact files first (max coverage gain per test)

**Gap Closure**: Closes largest coverage gap from 21.35% toward 50% target

**Tasks**:
1. Identify 10 largest zero-coverage files (>200 lines)
   - Analyze coverage report for zero-coverage modules
   - Prioritize by lines of code and criticality
   - Focus on: core services, API routes, tools
2. Write unit tests for each target file (minimum 40% coverage)
   - Test core functionality and public APIs
   - Test error handling and edge cases
   - Use appropriate test patterns (unit, integration, property)
3. Focus areas based on coverage analysis:
   - API routes: agent_guidance, analytics_dashboard, debug_routes
   - Core services: active_intervention, admin_bootstrap, agent_coordination
   - Tools: calendar_tool, canvas_tools (coding, docs, email, orchestration)
4. Verify coverage improvement
   - Run full coverage report
   - Confirm overall coverage increased by 5-10 percentage points
   - Validate individual file coverage ≥40%

**Target Files** (from coverage report):
1. `core/agent_coordination.py` (131 lines, 0%)
2. `core/agent_learning_enhanced.py` (118 lines, 0%)
3. `core/agent_request_manager.py` (130 lines, 0%)
4. `core/ai_workflow_optimization_endpoints.py` (137 lines, 0%)
5. `core/analytics_endpoints.py` (119 lines, 0%)
6. `tools/calendar_tool.py` (123 lines, 0%)
7. `api/agent_guidance_routes.py` (171 lines, 0%)
8. `api/analytics_dashboard_routes.py` (114 lines, 0%)
9. `api/debug_routes.py` (296 lines, 0%)
10. `api/financial_audit_routes.py` (66 lines, 0%)

**Success Criteria**:
- [ ] All 10 target files achieve ≥40% coverage
- [ ] Overall coverage increased from 21.35% to ~30%+
- [ ] All new tests pass reliably
- [ ] Coverage trend shows positive trajectory

**Estimated Time**: 12-16 hours (2-3 days)

---

## Optional Phases (Can Defer)

### Phase 222: Medium-Impact Coverage Expansion
**Status**: PENDING
**Priority**: MEDIUM

**Goal**: Improve coverage from 30% to 40% by targeting medium-impact files

**Tasks**: Target 15 files with 1-20% coverage, achieve 40% each

**Estimated Time**: 8-12 hours

---

### Phase 223: Property-Based Testing Expansion
**Status**: PENDING
**Priority**: MEDIUM

**Goal**: Add Hypothesis property tests for system invariants

**Tasks**: Add property tests for governance, episodic memory, and streaming invariants

**Estimated Time**: 6-8 hours

---

## Progress Tracking

### Coverage Metrics
- **Baseline**: 15.2% (Phase 09)
- **Current**: 21.35% (2026-03-21)
- **Phase 221 Target**: ~30%+
- **Milestone Target**: 50%
- **Ultimate Goal**: 80%

### Quality Metrics
- **Test Pass Rate**: ~97% (need 98%+)
- **Collection Errors**: 2 files (need 0)
- **Assertion Density**: 5 files below threshold (need 0)
- **Flaky Tests**: TBD

---

## Dependencies

**Phase 218** → **Phase 219** → **Phase 220** → **Phase 221** → **Phase 222** → **Phase 223**

- Phase 218 must complete before 219 (blocking test execution)
- Phase 219 must complete before 220 (quality gate for expansion)
- Phase 220 should complete before 221 (good test hygiene)
- Phases 221-223 can run in parallel if resources allow

---

*Last Updated: 2026-03-21*
*Next Action: Execute Phase 218 - Fix Test Collection Errors*
