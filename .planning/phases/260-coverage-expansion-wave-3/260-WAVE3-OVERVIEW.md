# Phase 260: Coverage Expansion Wave 3 - Overview

**Phase:** 260
**Wave:** 3 - Coverage Expansion
**Status:** Ready to Execute
**Date:** April 12, 2026

## Executive Summary

Phase 260 Wave 3 continues the backend coverage expansion initiative with three comprehensive plans targeting API routes, tools, and integration services. Building on the success of Phase 259 (workflow engine, proposal service) and aiming to reach the 80% coverage target, Wave 3 adds ~104 new tests across high-impact files with minimal current coverage.

## Wave Objectives

**Primary Goal:** Increase backend code coverage from ~25-31% (Phase 259 baseline) to ~36-49% through systematic test expansion.

**Expected Impact:** +11-18 percentage points across all three plans

**Test Coverage:**
- Plan 260-01: ~45 tests (API Routes)
- Plan 260-02: ~35 tests (Tools)
- Plan 260-03: ~24 tests (Integration Services)
- **Total: ~104 new tests**

## Plans Overview

### Plan 260-01: Test API Routes
**File:** `.planning/phases/260-coverage-expansion-wave-3/260-01-PLAN.md`

**Targets:**
- `api/canvas_routes.py` (384 lines) - Canvas state, context, recording, summarization
- `api/agent_routes.py` (769 lines) - Agent lifecycle, execution, meta-agent operations
- `api/workflow_template_routes.py` - Template CRUD, instantiation

**Test Count:** ~45 tests (15 per route file)
**Expected Impact:** +5-8 percentage points
**Key Features:**
- FastAPI TestClient for API testing
- Mock database and external dependencies
- Governance integration testing
- WebSocket endpoint validation
- Error response verification

**Execution Time:** 60-75 minutes

### Plan 260-02: Test Tools
**File:** `.planning/phases/260-coverage-expansion-wave-3/260-02-PLAN.md`

**Targets:**
- `tools/browser_tool.py` (819 lines) - CDP control, Playwright integration
- `tools/device_tool.py` (1,292 lines) - Camera, location, screen recording, shell
- `tools/calendar_tool.py` - Google Calendar integration

**Test Count:** ~35 tests (12+12+11)
**Expected Impact:** +4-6 percentage points
**Key Features:**
- Extensive mocking of external APIs (Playwright, device APIs, Google Calendar)
- Governance permission testing by maturity level
- Session management testing
- Audit trail verification
- WebSocket communication mocking

**Execution Time:** 75-90 minutes

### Plan 260-03: Test Integration Services
**File:** `.planning/phases/260-coverage-expansion-wave-3/260-03-PLAN.md`

**Targets:**
- `core/agent_integration_gateway.py` - External platform routing
- `core/integration_service.py` - Integration lifecycle management
- `integrations/slack_routes.py` - Slack API endpoints

**Test Count:** ~24 tests (8 per service)
**Expected Impact:** +2-4 percentage points
**Key Features:**
- External API mocking (Slack, Discord, WhatsApp)
- Integration lifecycle testing (register, validate, delete)
- OAuth flow testing
- Webhook event handling
- Platform routing verification

**Execution Time:** 60-75 minutes

## Coverage Projections

### Current State (Phase 259 Baseline)
- **Coverage:** ~25-31%
- **Files Tested:** Workflow engine, proposal service
- **Test Count:** ~80 tests

### After Plan 260-01 (API Routes)
- **Projected Coverage:** 30-39%
- **Increase:** +5-8 percentage points
- **Cumulative Tests:** ~125 tests

### After Plan 260-02 (Tools)
- **Projected Coverage:** 34-45%
- **Increase:** +4-6 percentage points
- **Cumulative Tests:** ~160 tests

### After Plan 260-03 (Integration Services)
- **Projected Coverage:** 36-49%
- **Increase:** +2-4 percentage points
- **Cumulative Tests:** ~184 tests

### Total Wave 3 Impact
- **Total Coverage Increase:** +11-18 percentage points
- **Total New Tests:** ~104 tests
- **Final Coverage:** 36-49%

## Technical Approach

### Testing Strategy
1. **FastAPI TestClient:** For API route testing with request/response validation
2. **AsyncMock/MagicMock:** For external service mocking (Playwright, APIs)
3. **Database Fixtures:** Isolated test databases with rollback
4. **Governance Mocking:** Permission check simulation
5. **Error Path Testing:** Comprehensive error handling coverage

### Mock Strategy
- **Browser Tool:** Mock Playwright CDP (browser, context, page)
- **Device Tool:** Mock WebSocket communication and device APIs
- **Calendar Tool:** Mock Google Calendar API
- **Integration Services:** Mock external platform APIs (Slack, Discord, etc.)

### Coverage Goals
- **Line Coverage:** >80% for targeted files
- **Branch Coverage:** >70% for critical paths
- **Happy Path:** All success scenarios
- **Error Path:** All failure scenarios
- **Edge Cases:** Boundary conditions and invalid inputs

## Execution Sequence

### Recommended Order
1. **Plan 260-01 (API Routes)** - Highest impact, foundational testing
2. **Plan 260-02 (Tools)** - Medium impact, extensive mocking required
3. **Plan 260-03 (Integration Services)** - Lower impact, specialized testing

### Prerequisites
- Phase 259 completed successfully
- Test infrastructure in place (pytest, coverage tools)
- Mock libraries available (unittest.mock)
- Database fixtures configured

### Dependencies
- All plans depend on Phase 259 completion
- Plans within Wave 3 are independent but sequential execution recommended
- Each plan generates its own coverage report

## Success Criteria

### Coverage Metrics
- [ ] Line coverage increases by ≥11 percentage points
- [ ] Branch coverage increases by ≥8 percentage points
- [ ] All targeted files achieve >70% coverage
- [ ] Overall backend coverage reaches 36-49%

### Test Quality
- [ ] All 104+ tests pass (100% pass rate)
- [ ] No test failures or errors
- [ ] Tests are maintainable and documented
- [ ] Mock strategy is consistent across plans

### Documentation
- [ ] Coverage reports generated (JSON + Markdown)
- [ ] Plan summaries created for each plan
- [ ] Wave 3 summary with recommendations
- [ ] COV-B-04 requirement progress documented

## Risk Mitigation

### Technical Risks
- **Mock Complexity:** Extensive mocking may hide integration bugs
  - *Mitigation:* Document mock assumptions clearly
- **Async Testing:** AsyncMock may not catch all async issues
  - *Mitigation:* Include async-specific test cases
- **Database State:** Test data isolation critical
  - *Mitigation:* Use transaction rollback fixtures

### Coverage Risks
- **Low Impact:** Some files may have minimal execution paths
  - *Mitigation:* Focus on critical business logic
- **External Dependencies:** May not be fully testable
  - *Mitigation:* Mock at appropriate abstraction level

## Output Artifacts

### Test Files
1. `backend/tests/coverage_expansion/test_canvas_routes_coverage.py` (~450 lines)
2. `backend/tests/coverage_expansion/test_agent_routes_coverage.py` (~500 lines)
3. `backend/tests/coverage_expansion/test_workflow_routes_coverage.py` (~400 lines)
4. `backend/tests/coverage_expansion/test_browser_tool_coverage.py` (~550 lines)
5. `backend/tests/coverage_expansion/test_device_tool_coverage.py` (~600 lines)
6. `backend/tests/coverage_expansion/test_calendar_tool_coverage.py` (~400 lines)
7. `backend/tests/coverage_expansion/test_agent_integration_gateway_coverage.py` (~350 lines)
8. `backend/tests/coverage_expansion/test_integration_service_coverage.py` (~300 lines)
9. `backend/tests/coverage_expansion/test_slack_routes_coverage.py` (~350 lines)

### Coverage Reports
1. `tests/coverage_reports/metrics/coverage_260_plan01.json`
2. `tests/coverage_reports/metrics/coverage_260_plan02.json`
3. `tests/coverage_reports/metrics/coverage_260_plan03.json`
4. `tests/coverage_reports/260_wave3_summary.md`

### Summary Documents
1. `.planning/phases/260-coverage-expansion-wave-3/260-01-SUMMARY.md`
2. `.planning/phases/260-coverage-expansion-wave-3/260-02-SUMMARY.md`
3. `.planning/phases/260-coverage-expansion-wave-3/260-03-SUMMARY.md`
4. `.planning/phases/260-coverage-expansion-wave-3/260-WAVE3-SUMMARY.md`

## Next Steps

### Immediate Actions
1. Review and approve all three plan files
2. Set up test environment with required dependencies
3. Execute Plan 260-01 (API Routes)
4. Generate coverage report and review results
5. Proceed to Plans 260-02 and 260-03

### Future Waves
- **Wave 4:** Test remaining services and utilities
- **Wave 5:** Property-based testing for critical business logic
- **Wave 6:** E2E test expansion
- **Final Wave:** Coverage gap analysis and targeted improvements

### 80% Target Strategy
Current trajectory suggests 4-5 more waves needed to reach 80% coverage. Each wave should target:
- High-impact, low-coverage files
- Critical business logic
- Security-sensitive operations
- Integration points

## Conclusion

Phase 260 Wave 3 represents a significant step toward the 80% coverage target. By systematically testing API routes, tools, and integration services, we will increase coverage by 11-18 percentage points while establishing robust testing patterns for future waves.

The comprehensive test suites will:
- Improve code quality and reliability
- Catch regressions early
- Document expected behavior
- Enable safe refactoring
- Support continuous deployment

**Ready to execute when approved.**

---

**Phase 260 Wave 3 Status:** Plans Complete, Ready for Execution
**Total Estimated Duration:** 3.5-4 hours (across all 3 plans)
**Total Test Count:** ~104 new tests
**Expected Coverage Impact:** +11-18 percentage points
