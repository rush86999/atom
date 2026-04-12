# Phase 260: Coverage Expansion Wave 3

**Status:** 🚧 Active
**Started:** 2026-04-12
**Milestone:** v10.0 Quality & Stability (Continued)

---

## Overview

Phase 260 continues coverage expansion work toward the 80% backend coverage target. This wave focuses on API routes and tools coverage, targeting high-impact endpoints and integration tools.

---

## Goals

1. **Add traditional unit/integration tests** for API routes
2. **Add tests for tools coverage** (browser, device, integration services)
3. **Increase coverage measurably** from ~13% baseline
4. **Target critical API endpoints** and tool integrations

---

## Target Areas (from Gap Analysis)

### Priority 1: API Routes
- `backend/api/canvas_routes.py` - Canvas presentation endpoints
- `backend/api/agent_routes.py` - Agent management endpoints
- `backend/api/workflow_template_routes.py` - Workflow template endpoints
- **Estimated:** ~45 tests needed (15 per file)
- **Expected impact:** +5-8 percentage points
- **Plan:** 260-01-PLAN.md ✅

### Priority 2: Tools
- `backend/tools/browser_tool.py` - Browser automation (CDP)
- `backend/tools/device_tool.py` - Device capabilities
- `backend/tools/calendar_tool.py` - Calendar integration
- **Estimated:** ~35 tests needed (12+12+11)
- **Expected impact:** +4-6 percentage points
- **Plan:** 260-02-PLAN.md ✅

### Priority 3: Integration Services
- `backend/core/agent_integration_gateway.py` - External platform routing
- `backend/core/integration_service.py` - Integration lifecycle
- `backend/integrations/slack_routes.py` - Slack API endpoints
- **Estimated:** ~24 tests needed (8 per file)
- **Expected impact:** +2-4 percentage points
- **Plan:** 260-03-PLAN.md ✅

**Total Estimated Tests:** ~104 tests
**Expected Coverage Increase:** +11-18 percentage points
**Target After Wave 3:** 36-49% coverage (up from 25-31%)

---

## Plans

### Plan 260-01: Test API Routes (Canvas, Agents, Workflows)
**Status:** ✅ Plan Complete, Ready to Execute
**Duration:** 60-75 minutes
**Dependencies:** Phase 259 (Wave 2 complete)
**Plan File:** 260-01-PLAN.md

**Target Files:**
- `api/canvas_routes.py` - Canvas CRUD operations
- `api/agent_routes.py` - Agent lifecycle management
- `api/workflow_template_routes.py` - Workflow template endpoints

**Tests to Create:**
- Canvas routes: ~15 tests covering CRUD, submission, state management
- Agent routes: ~15 tests covering creation, updates, deletion, queries
- Workflow routes: ~15 tests covering execution, state, history

**Expected Impact:** +5-8 percentage points

### Plan 260-02: Test Tools (Browser, Device, Calendar)
**Status:** ✅ Plan Complete, Ready to Execute
**Duration:** 75-90 minutes
**Dependencies:** Phase 260-01
**Plan File:** 260-02-PLAN.md

**Target Files:**
- `tools/browser_tool.py` - Browser automation via CDP
- `tools/device_tool.py` - Device capabilities (camera, location, etc.)
- `tools/calendar_tool.py` - Calendar event management

**Tests to Create:**
- Browser tool: ~12 tests covering navigation, screenshots, form filling
- Device tool: ~12 tests covering permissions, capabilities, governance
- Calendar tool: ~11 tests covering events, conflicts, CRUD operations

**Expected Impact:** +4-6 percentage points

### Plan 260-03: Test Integration Services
**Status:** ✅ Plan Complete, Ready to Execute
**Duration:** 60-75 minutes
**Dependencies:** Phase 260-02
**Plan File:** 260-03-PLAN.md

**Target Files:**
- `core/agent_integration_gateway.py` - External platform routing
- `core/integration_service.py` - Integration lifecycle
- `integrations/slack_routes.py` - Slack API endpoints

**Tests to Create:**
- Agent Integration Gateway: ~8 tests covering routing, actions, errors
- Integration Service: ~8 tests covering lifecycle, validation, health
- Slack Routes: ~8 tests covering OAuth, webhooks, events

**Expected Impact:** +2-4 percentage points

---

## Success Criteria

### Phase Complete When:
- [ ] All 3 plans complete (260-01, 260-02, 260-03)
- [ ] ~104 new tests created
- [ ] Coverage increased by at least +11 percentage points
- [ ] All API routes have >70% coverage
- [ ] All tools have >70% coverage
- [ ] All integration services have >70% coverage
- [ ] Coverage report generated showing progress

### Wave 3 Targets:
- **Minimum:** +11 percentage points (to 36% coverage)
- **Target:** +15 percentage points (to 40% coverage)
- **Stretch:** +18 percentage points (to 49% coverage)

---

## Progress Tracking

**Current Coverage:** ~25-31% (after Phase 259 Wave 2)
**Wave 3 Target:** 36-49% coverage
**Gap to 80%:** ~31-44 percentage points remaining

**Estimated Total Tests:** ~104 tests
**Estimated Duration:** 3.5-4 hours

---

## Notes

**Test Strategy:**
- FastAPI TestClient for API route testing
- Extensive mocking of external dependencies (Playwright, device APIs, Google Calendar, Slack)
- AsyncMock for async function testing
- Database fixtures with transaction rollback
- Governance permission mocking

**Quality Gates:**
- All new tests must pass (100% pass rate)
- Coverage must increase measurably per plan
- No regressions in existing tests
- Mock strategy documented

**Documentation:**
- Comprehensive plan files with test code examples
- Coverage reports (JSON + Markdown) for each plan
- Wave 3 summary with recommendations
- PHASE.md updated with progress

**Next Steps After Wave 3:**
- Execute all three plans sequentially
- Generate coverage reports after each plan
- Create Wave 3 summary document
- Update ROADMAP.md with progress
- Plan Wave 4 based on remaining gaps

---

**Phase Owner:** Development Team
**Start Date:** 2026-04-12
**Completion Target:** 2026-04-12
