# Atom Test Coverage Initiative - Roadmap

**Project**: Atom AI-Powered Business Automation Platform
**Initiative**: Test Coverage Improvement & Quality Assurance
**Current Coverage**: 74.6% actual line coverage (as of 2026-03-22)
**Target Coverage**: 80% (v5.5 milestone goal)

---

## Current Milestone: v5.5 Fix Test Failures and Push Backend Coverage to 80%

**Goal**: Fix remaining test failures and expand backend coverage from 74.6% to 80%

**Started**: 2026-03-22
**Status**: PLANNING

**Strategy**: Fix test failures first → Expand coverage → Quality gates enforcement

---

## Phases

- [ ] **Phase 220: Fix Industry Workflow Test Failures** - Fix 10 failing tests in industry workflow endpoints
- [ ] **Phase 221: Fix 2FA Routes Test Errors** - Resolve 24 test errors in 2FA routes
- [ ] **Phase 222: Core Services Coverage Expansion** - Push core services coverage to 80%
- [ ] **Phase 223: API Routes Coverage Expansion** - Push API routes coverage to 80%
- [ ] **Phase 224: Tools & Integration Coverage** - Push tools and integration coverage to 80%
- [ ] **Phase 225: Coverage Verification & Reports** - Generate coverage reports and verify 80% target
- [ ] **Phase 226: Quality Gates Enforcement** - Ensure 98% pass rate and re-enable CI/CD

---

## Phase Details

### Phase 220: Fix Industry Workflow Test Failures

**Goal**: All industry workflow tests pass with 0 failures

**Depends on**: Nothing (first phase)

**Requirements**: FAIL-01, FAIL-02, FAIL-03, FAIL-04

**Success Criteria** (what must be TRUE):
1. All 10 industry workflow tests pass (0 failures)
2. Duplicate test file `test_industry_workflow_endpoints.py` removed from tests/api/services/
3. Template ID mismatches fixed (using real template IDs like "healthcare_patient_onboarding")
4. ROI request validation fixed (template_id removed from request body)

**Plans**: 1 plan
- [x] 220-01-PLAN.md — Fix failing tests by removing duplicate file, fixing ROI validation, and updating template IDs ✅ COMPLETE (2026-03-22)

---

### Phase 221: Fix 2FA Routes Test Errors

**Goal**: All 2FA routes tests execute without errors

**Depends on**: Phase 220

**Requirements**: FAIL-05, FAIL-06

**Success Criteria** (what must be TRUE):
1. All 24 2FA routes test errors resolved
2. 2FA test fixtures and dependencies properly configured
3. 2FA tests execute successfully without import or fixture errors
4. No regressions in previously passing tests

**Plans**: TBD

---

### Phase 222: Core Services Coverage Expansion

**Goal**: Core services achieve 80% test coverage

**Depends on**: Phase 221

**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04

**Success Criteria** (what must be TRUE):
1. Token storage service coverage >= 80% (currently has gaps at line 17)
2. Error handler decorator coverage >= 80% (gaps at line 74)
3. Structured logger coverage >= 80% (gaps at lines 112, 187)
4. API routes base coverage >= 80% (gaps at line 54)

**Plans**: TBD

---

### Phase 223: API Routes Coverage Expansion

**Goal**: API routes achieve 80% test coverage

**Depends on**: Phase 222

**Requirements**: API-01, API-02, API-03, API-04

**Success Criteria** (what must be TRUE):
1. Episode routes coverage >= 80% (gaps at line 305)
2. Auto-install routes coverage >= 80% (gaps at lines 25, 32)
3. Admin routes coverage >= 80% (gaps at lines 99, 1065)
4. Composition routes coverage >= 80% (gaps at line 35)

**Plans**: TBD

---

### Phase 224: Tools & Integration Coverage

**Goal**: Tools and integration services achieve 80% test coverage with property-based tests

**Depends on**: Phase 223

**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, QUAL-03

**Success Criteria** (what must be TRUE):
1. Canvas tool coverage >= 80%
2. Browser automation tool coverage >= 80%
3. Device capabilities tool coverage >= 80%
4. Agent governance service coverage >= 80%
5. LLM routing and BYOK handler coverage >= 80%
6. Property-based tests added for critical invariants (Hypothesis tests)

**Plans**: TBD

---

### Phase 225: Coverage Verification & Reports

**Goal**: Verify 80% backend coverage achieved and generate comprehensive reports

**Depends on**: Phase 224

**Requirements**: QUAL-01, QUAL-04

**Success Criteria** (what must be TRUE):
1. Backend actual line coverage >= 80% (up from 74.6%)
2. Coverage report generated (HTML + JSON formats)
3. Coverage gaps identified and documented
4. All critical system paths have >= 80% coverage

**Plans**: TBD

---

### Phase 226: Quality Gates Enforcement

**Goal**: Ensure 98% test pass rate and re-enable CI/CD workflows

**Depends on**: Phase 225

**Requirements**: FAIL-07, QUAL-02, QUAL-05

**Success Criteria** (what must be TRUE):
1. Overall test pass rate >= 98% (currently 90.6%)
2. All tests passing with no failures or errors
3. CI/CD workflows re-enabled after 80% target achieved
4. Quality gates operational (pre-commit, CI, trend tracking)

**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 220. Fix Industry Workflow Test Failures | 0/1 | Planning | - |
| 221. Fix 2FA Routes Test Errors | 0/0 | Not started | - |
| 222. Core Services Coverage Expansion | 0/0 | Not started | - |
| 223. API Routes Coverage Expansion | 0/0 | Not started | - |
| 224. Tools & Integration Coverage | 0/0 | Not started | - |
| 225. Coverage Verification & Reports | 0/0 | Not started | - |
| 226. Quality Gates Enforcement | 0/0 | Not started | - |

---

## Dependencies

**Phase 220** → **Phase 221** → **Phase 222** → **Phase 223** → **Phase 224** → **Phase 225** → **Phase 226**

- Phase 220 must complete before 221 (test failures block progress)
- Phase 221 must complete before 222 (all tests must pass before coverage expansion)
- Phase 222 must complete before 223 (core services foundation first)
- Phase 223 must complete before 224 (API routes before tools/integration)
- Phase 224 must complete before 225 (coverage complete before verification)
- Phase 225 must complete before 226 (verification before quality gates)

---

## Coverage Metrics

### Baseline (2026-03-22)
- **Overall Coverage**: 74.6% actual line coverage
- **Test Pass Rate**: 90.6% (483 passing, 14 failing, 36 errors)
- **Total Tests**: 1,489 test files

### Milestone Targets
- **Phase 220**: 0 test failures (industry workflow)
- **Phase 221**: 0 test errors (2FA routes)
- **Phase 222**: Core services >= 80%
- **Phase 223**: API routes >= 80%
- **Phase 224**: Tools & integration >= 80%
- **Phase 225**: Overall >= 80%
- **Phase 226**: 98%+ pass rate, CI/CD re-enabled

### Ultimate Goal
- **Overall Coverage**: 80% actual line coverage
- **Test Pass Rate**: 98%+ (targeting 100%)
- **Quality Gates**: All operational

---

## Testing Strategy

### Test Failure Resolution (Phases 220-221)
- Fix failing tests by analyzing root causes
- Remove duplicate test files
- Fix test fixtures and dependencies
- Validate test assertions match API behavior

### Coverage Expansion (Phases 222-224)
- Target specific coverage gaps identified in baseline
- Add unit tests for uncovered code paths
- Add integration tests for endpoint validation
- Add property-based tests for invariants (Hypothesis)

### Quality Enforcement (Phases 225-226)
- Generate comprehensive coverage reports (HTML + JSON)
- Verify 80% target achieved across all modules
- Ensure 98%+ pass rate maintained
- Re-enable CI/CD workflows with quality gates

---

## Notes

### Key Insights
1. **Test failures must be fixed first** - Can't expand coverage with failing tests
2. **Actual line coverage matters** - 74.6% is real baseline, not estimates
3. **Progressive approach** - Fix failures → Core services → API routes → Tools → Verify → Quality gates
4. **Property-based testing** - Add Hypothesis tests for critical invariants during Phase 224

### Risks
1. **Test failures may be complex** - Industry workflow and 2FA tests may have deep issues
2. **Coverage gaps may be large** - 5.4 percentage points to target (74.6% → 80%)
3. **Test suite size** - 1,489 test files require careful navigation
4. **Timeline pressure** - Aggressive execution required

### Opportunities
1. **Clear target** - 80% is well-defined milestone
2. **Structured approach** - Phases build on each other
3. **Quality gates ready** - Infrastructure from v5.4 available
4. **Comprehensive requirements** - 24 requirements provide complete coverage scope

---

*Last Updated: 2026-03-22*
*Next Action: Execute Phase 220 - Fix Industry Workflow Test Failures*
*Milestone: v5.5 Fix Test Failures and Push Backend Coverage to 80%*
