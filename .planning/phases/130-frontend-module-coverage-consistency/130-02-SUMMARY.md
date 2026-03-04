---
phase: 130-frontend-module-coverage-consistency
plan: 02
subsystem: frontend-coverage
tags: [coverage-analysis, per-module-thresholds, test-inventory, roadmap]

# Dependency graph
requires:
  - phase: 130-frontend-module-coverage-consistency
    plan: 01
    provides: baseline metrics and coverage audit
provides:
  - Per-module coverage threshold configuration in jest.config.js
  - Coverage gap analysis script with priority classification
  - Test inventory for 613 files below threshold
  - Coverage improvement roadmap for Waves 3-5
affects: [frontend-testing, ci-cd, coverage-tracking]

# Tech tracking
tech-stack:
  added: [coverage-gaps.js script, per-module jest thresholds]
  patterns: ["graduated rollout strategy (70-90% thresholds by module type)"]

key-files:
  created:
    - frontend-nextjs/scripts/coverage-gaps.js
    - .planning/phases/130-frontend-module-coverage-consistency/130-02-GAPS.md
  modified:
    - frontend-nextjs/jest.config.js

key-decisions:
  - "Graduated thresholds: lib 90%, hooks 85%, canvas 85%, ui 80%, integrations 70%, pages 80%"
  - "Global floor at 75% (ramp to 80% by end of Phase 130)"
  - "Parallel execution: Waves 3-4 concurrent, Wave 5 sequential (25-week timeline)"
  - "Priority classification: CRITICAL <50%, HIGH 50-70%, MEDIUM 70-80%"
  - "Canvas Components (73%) as testing pattern reference for other modules"

patterns-established:
  - "Pattern: Threshold-aware gap detection with module-level aggregation"
  - "Pattern: Test inventory categorizes by effort (unit/integration/smoke) and wave allocation"
  - "Pattern: Coverage roadmap with parallel execution and risk mitigation"

# Metrics
duration: 3min
completed: 2026-03-04
---

# Phase 130: Frontend Module Coverage Consistency - Plan 02 Summary

**Coverage gap analysis with per-module thresholds, test inventory for 613 files, and coverage improvement roadmap for Waves 3-5**

## Performance

- **Duration:** 3 minutes
- **Started:** 2026-03-04T00:18:47Z
- **Completed:** 2026-03-04T00:22:00Z
- **Tasks:** 5
- **Files created:** 2
- **Files modified:** 1

## Accomplishments

- **Coverage gap analysis script** created with threshold-aware detection and priority classification (CRITICAL/HIGH/MEDIUM)
- **Per-module coverage thresholds** configured in jest.config.js with graduated rollout strategy
- **130-02-GAPS.md** generated with comprehensive gap analysis, test inventory, and roadmap
- **613 files below threshold** identified and categorized by module type
- **Test inventory** created with 1,201 estimated test suites and effort breakdown
- **Coverage improvement roadmap** defined for Waves 3-5 with parallel execution strategy

## Task Commits

Each task was committed atomically:

1. **Task 1: Create coverage gap analysis script** - `a1e12a356` (feat)
2. **Task 2: Configure per-module coverage thresholds** - `96cbba5e9` (feat)
3. **Task 3: Generate gap analysis report** - `19c0c990a` (feat)
4. **Task 4: Create test inventory** - `6bcabca50` (feat)
5. **Task 5: Create coverage improvement roadmap** - `1abf9839b` (feat)

**Plan metadata:** 5 tasks, 3 minutes execution time

## Files Created

### Created
- `frontend-nextjs/scripts/coverage-gaps.js` (213 lines)
  - Threshold-aware gap detection with module-level aggregation
  - Priority classification: CRITICAL (<50%), HIGH (50-70%), MEDIUM (70-80%)
  - Three output formats: JSON, Markdown, console
  - Module-level coverage summary with gap calculation

- `.planning/phases/130-frontend-module-coverage-consistency/130-02-GAPS.md` (586 lines)
  - Coverage gap analysis with 613 files below threshold
  - Module-level coverage breakdown (7 modules)
  - Critical gaps list (top 50 files at 0% coverage)
  - High priority gaps (6 files at 50-70% coverage)
  - Test inventory for 487 files with effort estimates
  - Coverage improvement roadmap for Waves 3-5

### Modified
- `frontend-nextjs/jest.config.js` (+44 lines)
  - Global floor: 75% (branches, functions, lines, statements)
  - lib/**/*.{ts,tsx}: 90% (utilities are testable, critical infrastructure)
  - hooks/**/*.{ts,tsx}: 85% (custom hooks, testable with renderHook)
  - components/canvas/**/*.{ts,tsx}: 85% (maintain existing good coverage)
  - components/ui/**/*.{ts,tsx}: 80% (base UI components)
  - components/integrations/**/*.{ts,tsx}: 70% (external deps, complex)
  - pages/**/*.{ts,tsx}: 80% (Next.js pages)

## Coverage Gap Analysis Results

### Module-Level Coverage (Current State)

| Module | Files | Coverage | Threshold | Gap | Status |
|--------|-------|----------|-----------|-----|--------|
| Integration Components | 17 | 0% | 70% | 70% | FAIL |
| Next.js Pages | 386 | 0% | 80% | 80% | FAIL |
| Other | 174 | 1% | 80% | 79% | FAIL |
| React Hooks | 25 | 15% | 85% | 70% | FAIL |
| UI Components | 29 | 31% | 80% | 49% | FAIL |
| Utility Libraries | 18 | 44% | 90% | 46% | FAIL |
| Canvas Components | 12 | 73% | 85% | 12% | FAIL |

**Total Files Below Threshold:** 613
**Priority Breakdown:** 603 CRITICAL, 6 HIGH, 4 MEDIUM

### Critical Gaps (Top 20)

1. **AsanaIntegration.tsx**: 0% (142 uncovered lines)
2. **AzureIntegration.tsx**: 0% (178 uncovered lines)
3. **BoxIntegration.tsx**: 0% (260 uncovered lines)
4. **FreshdeskIntegration.tsx**: 0% (130 uncovered lines)
5. **GitHubIntegration.tsx**: 0% (112 uncovered lines)
6. **GoogleWorkspaceIntegration.tsx**: 0% (168 uncovered lines)
7. **JiraIntegration.tsx**: 0% (158 uncovered lines)
8. **JiraOAuthFlow.tsx**: 0% (120 uncovered lines)
9. **Microsoft365Integration.tsx**: 0% (245 uncovered lines)
10. **NotionIntegration.tsx**: 0% (161 uncovered lines)
11. **OutlookIntegration.tsx**: 0% (148 uncovered lines)
12. **SlackIntegration.tsx**: 0% (147 uncovered lines)
13. **ZoomIntegration.tsx**: 0% (186 uncovered lines)
14. **WorkflowAutomation.tsx**: 0% (290 uncovered lines)
15. **Dashboard.tsx**: 0% (64 uncovered lines)
16. **CommunicationHub.tsx**: 0% (6 uncovered lines)
17. **TaskManagement.tsx**: 0% (80 uncovered lines)
18. **ZendeskIntegration.tsx**: 0% (234 uncovered lines)
19. **TeamsIntegration.tsx**: 0% (263 uncovered lines)
20. **TrelloIntegration.tsx**: 0% (180 uncovered lines)

## Test Inventory

### Effort Summary

| Module | Files | Avg Test Suites/File | Total Test Suites | Estimated Hours |
|--------|-------|---------------------|-------------------|-----------------|
| Integration Components | 17 | 3.5 | 60 | 120-180 |
| Next.js Pages | 386 | 2.5 | 965 | 1,930-2,895 |
| React Hooks | 25 | 2.5 | 63 | 126-189 |
| Utility Libraries | 18 | 2.5 | 45 | 90-135 |
| UI Components | 29 | 1.5 | 44 | 88-132 |
| Canvas Components | 12 | 2 | 24 | 48-72 |
| **TOTAL** | **487** | **2.4** | **1,201** | **2,402-3,603** |

### Test Type Categories

1. **Integration Component Tests** (17 files, 60 test suites)
   - OAuth flow authentication, API integration, loading/error states
   - MSW mocking required for external services
   - Estimated: 120-180 hours

2. **Next.js Page Tests** (386 files, 965 test suites)
   - Smoke tests + integration tests for routes
   - Priority pages: dashboard, analytics, automations, calendar
   - Estimated: 1,930-2,895 hours

3. **React Hook Tests** (25 files, 63 test suites)
   - Unit tests with @testing-library/react-hooks
   - Critical hooks: useCognitiveTier, useFileUpload, useLive*
   - Estimated: 126-189 hours

4. **Utility Library Tests** (18 files, 45 test suites)
   - Unit tests for pure functions
   - Critical utilities: auth.ts, logger.ts, graphqlClient.ts
   - Estimated: 90-135 hours

5. **UI Component Tests** (29 files, 44 test suites)
   - Integration tests for user interactions
   - Low priority (mostly shadcn/ui components)
   - Estimated: 88-132 hours

6. **Canvas Component Tests** (12 files, 24 test suites)
   - Integration tests for visualizations
   - Best coverage (73%) - use as reference
   - Estimated: 48-72 hours

## Coverage Improvement Roadmap

### Wave 3 (Plan 130-03): Integration Components
- **Scope:** 17 integration components
- **Target:** 70% coverage
- **Estimated:** 60 test suites, 120-180 hours
- **Duration:** 3-4 weeks
- **Parallel:** Can run concurrent with Wave 4

### Wave 4 (Plan 130-04): Core Features
- **Scope:** 10 high-value pages + 10 critical hooks
- **Target:** 80-85% coverage
- **Estimated:** 500+ test suites, 1,000+ hours
- **Duration:** 20+ weeks
- **Parallel:** Can run concurrent with Wave 3

### Wave 5 (Plan 130-05): Threshold Enforcement
- **Scope:** Remaining 376 pages + utilities + UI components
- **Target:** Enforce all thresholds globally
- **Estimated:** 600+ test suites, 1,200+ hours
- **Duration:** 24+ weeks
- **Sequential:** Must run after Waves 3-4

### Parallel Execution Strategy

**Option B: Partial Parallel (Recommended)**
- Wave 3 + Wave 4 (parallel) → Wave 5 (sequential)
- Duration: ~25 weeks (6 months)
- Resources: 2 testers
- Risk: Medium (merge conflicts, test interference)

**Coverage Trajectory:**
- Current: 4.87% global
- Wave 3: +10% (15% global)
- Wave 4: +35% (50% global)
- Wave 5: +30% (80% global)

## Decisions Made

- **Graduated thresholds:** Module-specific thresholds based on testability and criticality (70-90%)
- **Global floor:** 75% initially, ramp to 80% by end of Phase 130
- **Parallel execution:** Waves 3-4 concurrent to reduce timeline from 50 weeks to 25 weeks
- **Priority classification:** CRITICAL (<50%), HIGH (50-70%), MEDIUM (70-80%) for gap prioritization
- **Canvas reference:** Use Canvas Components (73% coverage) as testing pattern for other modules

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**Issue 1: Module detection logic not working for absolute paths**
- **Found during:** Task 3 (gap analysis report generation)
- **Issue:** Script using `filepath.split('/')[1]` didn't correctly categorize files into modules
- **Fix:** Updated to use relative paths and threshold names as module keys
- **Files modified:** scripts/coverage-gaps.js
- **Commit:** 19c0c990a

## Verification Results

All verification steps passed:

1. ✅ **scripts/coverage-gaps.js exists** - 213 lines, executable
2. ✅ **Script generates console output** - Priority breakdown shown correctly
3. ✅ **Script generates markdown report** - Valid markdown with tables
4. ✅ **Script generates JSON output** - Valid JSON format
5. ✅ **Per-module thresholds configured** - All 6 module categories in jest.config.js
6. ✅ **130-02-GAPS.md exists** - 586 lines with complete analysis
7. ✅ **Test inventory included** - 487 files categorized with effort estimates
8. ✅ **Roadmap defined** - Waves 3-5 scope with dependencies and parallel execution

## Coverage Metrics

**Current State (from 130-01):**
- Overall: 4.87% (1,052/21,592 lines)
- Total Files: 661
- Files Below Threshold: 613 (92.9%)
- Largest Gap: Next.js Pages (80% gap)
- Smallest Gap: Canvas Components (12% gap)

**Target State (end of Phase 130):**
- Overall: 80% global coverage
- Module-specific: 70-90% by module type
- Test Suites: 1,201 estimated
- Duration: 25 weeks (with 2 testers parallel)

## Next Phase Readiness

✅ **Coverage gap analysis complete** - All 613 files categorized and prioritized

**Ready for:**
- Phase 130 Plan 03: Integration component tests (Wave 3)
- Phase 130 Plan 04: Core feature tests (Wave 4, parallel with 130-03)
- Phase 130 Plan 05: Threshold enforcement (Wave 5)

**Recommendations for follow-up:**
1. Start Wave 3 (130-03) with 17 integration components (Slack, Asana, GitHub, etc.)
2. Start Wave 4 (130-04) in parallel with high-value pages and hooks
3. Set up MSW (Mock Service Worker) for OAuth provider mocking
4. Establish test patterns from Canvas Components (73% coverage reference)
5. Configure CI threshold enforcement for Wave 5

---

*Phase: 130-frontend-module-coverage-consistency*
*Plan: 02*
*Completed: 2026-03-04*
