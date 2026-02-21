# Phase 62 Redesign Summary

**Date:** February 21, 2026
**Status:** Planning Complete - Ready for Execution

## Executive Summary

Phase 62 was redesigned based on research findings that identified why the original 11 plans failed to improve coverage despite creating 567 tests. The redesign uses a research-backed 6-week sprint approach focused on fixing execution blockers first, then writing integration tests with real DB/API (not mocks), and finally setting up quality gates.

## Original Phase 62 Failure Analysis

### What Went Wrong

| Issue | Impact | Evidence |
|-------|--------|----------|
| Import errors | 92 tests couldn't execute | test_core_services_batch.py has wrong imports |
| Unregistered routes | 50 tests returned 404 | workspace_routes, token_routes, etc. not in main_api_app.py |
| Wrong coverage threshold | CI never enforced | fail_under=80.0 when actual coverage is 17.12% |
| Heavy mocking | Tests passed but didn't cover real code | Mocked workflow_engine, not real execution |
| No incremental validation | Issues found after 4 months | Coverage only measured at end |

### Root Cause

Phase 62 focused on **test count** (567 tests) instead of **coverage percentage** gained. Tests were written without verifying they ran or covered production code.

## Redesign Approach

### Research-Backed Principles (from 62-RESEARCH.md)

1. **Fix Execution Blockers First** - Import errors, missing routes must be fixed before writing new tests
2. **Integration Tests Over Mocked Unit Tests** - Real DB/API exercises 2-3x more code
3. **Daily Coverage Measurement** - Measure coverage after EACH test file, not after 4 months
4. **Realistic Thresholds** - Start with 25%, increment by 5% per sprint
5. **Focus on Coverage Percentage** - Not test count (aim for +10% per sprint)

### 6-Week Sprint Plan

| Week | Plan(s) | Focus | Target Coverage |
|------|---------|-------|-----------------|
| 1 | 62-13, 62-14 | Fix blockers (imports, routes, config) | 25-35% |
| 2-3 | 62-15, 62-16 | Integration tests (critical paths) | 40-50% |
| 4-5 | 62-17, 62-18 | Unit tests (pure logic), tools/integrations | 50-60% |
| 6 | 62-19 | Quality gates, CI/CD, pre-commit | 60-65% |

## New Plans Overview

### Plan 62-13: Fix Test Execution Blockers (Wave 1)

**Objective:** Fix import errors, configuration problems, test discovery issues

**Tasks:**
1. Update coverage config (fail_under=25, --cov-branch)
2. Fix import errors in batch test files
3. Verify test discovery (pytest collects 700+ tests)

**Coverage Target:** 25-30%

**Dependencies:** None

### Plan 62-14: Register Missing API Routes (Wave 2)

**Objective:** Register missing routes in main_api_app.py

**Tasks:**
1. Identify 5 missing routes (workspace, token, marketing, operational, user_activity)
2. Register routes in main_api_app.py
3. Verify tests return real responses (not 404)

**Coverage Target:** 30-35%

**Dependencies:** 62-13

### Plan 62-15: Integration Tests for Critical Paths (Wave 3)

**Objective:** Write integration tests for high-impact files

**Tasks:**
1. Create workflow_engine integration tests (real DB)
2. Create agent_endpoints integration tests (TestClient)
3. Create byok_handler integration tests (respx HTTP mocking)

**Coverage Target:** 40-45%

**Dependencies:** 62-13, 62-14

### Plan 62-16: Integration Tests for Medium-Impact Files (Wave 3)

**Objective:** Write integration tests for medium-priority modules

**Tasks:**
1. Create episode memory integration tests
2. Create governance integration tests
3. Create workspace integration tests

**Coverage Target:** 45-50%

**Dependencies:** 62-13, 62-14

### Plan 62-17: Unit Tests for Pure Logic (Wave 4)

**Objective:** Write unit tests for algorithms and validators

**Tasks:**
1. Create governance_cache unit tests (with Hypothesis)
2. Create episode algorithms unit tests (parametrized)
3. Create validator unit tests (parametrized)

**Coverage Target:** 50-55%

**Dependencies:** 62-15, 62-16

### Plan 62-18: Integration Tests for Tools/External (Wave 4)

**Objective:** Write integration tests for tools and external services

**Tasks:**
1. Create canvas tool integration tests
2. Create browser tool integration tests
3. Create Slack/Discord integration tests (respx)

**Coverage Target:** 55-60%

**Dependencies:** 62-15, 62-16

### Plan 62-19: Quality Gates and CI/CD Enforcement (Wave 5)

**Objective:** Set up CI/CD quality gates and pre-commit hooks

**Tasks:**
1. Update GitHub Actions workflow (cov-fail-under=55)
2. Create pre-commit configuration
3. Validate quality gates (TQ-01 through TQ-05)

**Coverage Target:** 60-65%

**Dependencies:** 62-17, 62-18

## Wave Structure for Parallel Execution

| Wave | Plans | Can Run In Parallel |
|------|-------|---------------------|
| 1 | 62-13 | No (must fix blockers first) |
| 2 | 62-14 | After 62-13 completes |
| 3 | 62-15, 62-16 | Yes (different modules) |
| 4 | 62-17, 62-18 | Yes (different scopes) |
| 5 | 62-19 | After 62-17, 62-18 complete |

## Must-Haves Derived from Research

Each plan includes these must-haves based on research findings:

1. **Daily Coverage Measurement** - Run coverage after EACH test file
2. **Integration Tests First** - Use real DB/API, not mocks
3. **Test Real Code** - No mock.patch on handler methods
4. **Parametrize for Edge Cases** - Use @pytest.mark.parametrize
5. **Hypothesis for Invariants** - Property-based tests where applicable
6. **Branch Coverage** - Always use --cov-branch
7. **Realistic Thresholds** - Start at 25%, increment gradually

## Quality Gates (TQ-01 through TQ-05)

From 62-RESEARCH.md, quality standards to validate:

- **TQ-01 (Independence):** Tests run in random order (pytest-xdist)
- **TQ-02 (Pass Rate):** 98%+ across 3 runs
- **TQ-03 (Performance):** Full suite <60 minutes
- **TQ-04 (Determinism):** Same results across runs
- **TQ-05 (Coverage Quality):** Branch coverage enabled, behavior-based tests

## Risk-Based Coverage Strategy

Instead of blanket 80% coverage, target:

| Priority | Modules | Target Coverage |
|----------|---------|-----------------|
| P0 (Critical) | workflow_engine, byok_handler, governance | 90%+ |
| P1 (High) | episode services, integrations, API routes | 70-80% |
| P2 (Medium) | Tools, utilities | 50-60% |
| P3 (Low) | Config, logging | 30-40% |

**Expected Result:** 60-65% overall coverage, 80%+ business confidence on critical paths

## Files Modified by Redesign

| Plan | Files Modified |
|------|----------------|
| 62-13 | .coveragerc, pytest.ini, test_core_services_batch.py, conftest.py |
| 62-14 | main_api_app.py, test_workspace_routes.py, test_token_routes.py, etc. |
| 62-15 | test_workflow_engine_integration.py, test_agent_endpoints_integration.py, test_byok_handler_integration.py |
| 62-16 | test_episode_memory_integration.py, test_governance_integration.py, test_workspace_integration.py |
| 62-17 | test_governance_cache_unit.py, test_episode_algorithms_unit.py, test_validators_unit.py |
| 62-18 | test_tools_integration.py, test_browser_tool_integration.py, test_integrations_external.py |
| 62-19 | .github/workflows/test.yml, .pre-commit-config.yaml, test_quality_gates.py |

## Success Criteria

After executing all 7 redesign plans (62-13 through 62-19):

- [ ] Overall coverage 60-65% (from 17.12% baseline)
- [ ] All 700+ tests can execute without errors
- [ ] Import errors fixed (92 tests now run)
- [ ] API routes registered (50 tests return real responses)
- [ ] Integration tests use real DB/TestClient (not mocks)
- [ ] Unit tests use parametrize and Hypothesis
- [ ] CI/CD enforces coverage threshold (55%)
- [ ] Pre-commit hooks run coverage check
- [ ] All quality gates validated (TQ-01 through TQ-05)
- [ ] Branch coverage enabled
- [ ] HTML coverage report generated

## Next Steps

1. Execute Plan 62-13 (Fix Test Execution Blockers)
2. Verify coverage increases to 25-30%
3. Execute remaining plans in wave order
4. Measure coverage daily
5. Adjust plans based on actual coverage gains

## References

- Research: `.planning/phases/62-test-coverage-80pct/62-RESEARCH.md`
- Verification: `.planning/phases/62-test-coverage-80pct/62-VERIFICATION.md`
- Plans: `.planning/phases/62-test-coverage-80pct/62-{13-19}-PLAN.md`
