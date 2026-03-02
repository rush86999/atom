# Phase 118 Coverage Analysis: Canvas Tool

**Generated:** 2026-03-01T22:58:00Z
**File:** tools/canvas_tool.py (1360 lines)
**Baseline:** 82% coverage
**Target:** 60%+ coverage

## Summary
- **Current Coverage:** 82%
- **Target Coverage:** 60%
- **Coverage Gap:** 0% (exceeds target by 22%)
- **Total Missing Lines:** 74

## Missing Lines by Function

### present_chart (lines 93-250)
**Purpose:** Send chart to frontend canvas
**Complexity:** Medium - Governance, WebSocket, audit tracking
**Missing lines:** 142-143, 322-324 (6 lines)
**Tests needed:**
  - Governance denial handling
  - Agent execution lifecycle
  - Audit entry creation
  - Error handling and rollback

### present_markdown (lines 327-447)
**Purpose:** Send markdown content to canvas
**Complexity:** Low-Medium
**Missing lines:** 370-371, 391 (3 lines)
**Tests needed:**
  - Markdown presentation success
  - Audit entry with metadata
  - Execution completion

### present_form (lines 450-574)
**Purpose:** Present form to user
**Complexity:** Medium
**Missing lines:** 496-497, 517 (3 lines)
**Tests needed:**
  - Form schema handling
  - Canvas ID generation
  - Governance checks

### update_canvas (lines 577-747)
**Purpose:** Update existing canvas
**Complexity:** Medium
**Missing lines:** 644-645, 725-747 (25 lines)
**Tests needed:**
  - Canvas update success
  - Update with agent_id
  - Error rollback

### present_to_canvas (lines 750-857)
**Purpose:** Generic wrapper for canvas presentation
**Complexity:** Low - Routing logic
**Missing lines:** None (covered)
**Tests needed:**
  - None - routing logic fully covered

### canvas_execute_javascript (lines 891-1111)
**Purpose:** Execute JavaScript in canvas (AUTONOMOUS only)
**Complexity:** High - Security validation, governance
**Missing lines:** 886-888, 1025, 1068-1075, 1089-1111 (22 lines)
**Tests needed:**
  - AUTONOMOUS requirement enforcement
  - Dangerous pattern blocking
  - JavaScript audit trail
  - Security validation

### present_specialized_canvas (lines 1114-1359)
**Purpose:** Present specialized canvas types
**Complexity:** Medium-High - Type validation, governance
**Missing lines:** 1337-1359 (23 lines)
**Tests needed:**
  - Type validation
  - Component validation
  - Layout validation
  - Maturity requirement checks

### close_canvas (lines 860-888)
**Purpose:** Close canvas for user
**Complexity:** Low
**Missing lines:** None (covered)
**Tests needed:**
  - None - close logic fully covered

## Gap-Filling Priority

### Priority 1: High-Use Functions (LOW PRIORITY - already 82%)
1. **present_chart** - Core presentation function (82% covered, only 6 missing lines)
2. **update_canvas** - Dynamic content updates (74 missing lines, large error handler)
3. **present_to_canvas** - Generic routing (100% covered, no work needed)

### Priority 2: Security Functions (MEDIUM PRIORITY - 22 lines missing)
1. **canvas_execute_javascript** - AUTONOMOUS enforcement (22 missing lines)
2. **present_specialized_canvas** - Type validation (23 missing lines)

### Priority 3: Supporting Functions (LOW PRIORITY - already covered)
1. **present_form** - Form handling (82% covered, only 3 missing lines)
2. **present_markdown** - Content presentation (82% covered, only 3 missing lines)
3. **close_canvas** - Cleanup (100% covered, no work needed)

## Test Strategy Notes
- Current 82% coverage already exceeds 60% target by 22%
- 2 failing tests need fixing: `test_validate_canvas_schema`, `test_governance_block_handling`
- Focus on fixing 2 failing tests first
- Priority 2 functions (security) are most important for completeness
- update_canvas error handler (lines 725-747) is large but low priority (error logging)
- canvas_execute_javascript security validation is high value (22 lines, AUTONOMOUS enforcement)
- present_specialized_canvas validation is high value (23 lines, type safety)

## Estimated Tests Needed
- **Fix failing tests:** 2 tests (validate_layout mock, governance block assertion)
- **Priority 2 (Security):** 3-4 tests (~25 lines coverage)
  - canvas_execute_javascript: AUTONOMOUS enforcement, dangerous patterns, audit trail
  - present_specialized_canvas: Type validation, component validation, layout validation
- **Priority 1 (High-Use):** 0 tests (already 82%, exceeds target)
- **Priority 3 (Supporting):** 0 tests (already covered)
- **Total:** 5-6 tests to reach 90%+ coverage

## Key Insight
**canvas_tool.py already exceeds 60% target at 82% coverage.** Plan 03 should focus on:
1. Fixing 2 failing tests
2. Adding 3-4 security-focused tests for high-value functions
3. Target: 90%+ coverage (realistic with 5-6 tests)
