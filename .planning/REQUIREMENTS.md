# Requirements: Atom Test Coverage Initiative

**Defined:** 2026-03-22
**Core Value:** Critical system paths are thoroughly tested and validated before production deployment

## v1 Requirements

Requirements for v5.5 milestone: Fix test failures and push backend coverage from 74.6% to 80%.

### Test Failure Resolution

- [ ] **FAIL-01**: All industry workflow tests pass (0 failures)
- [ ] **FAIL-02**: Duplicate test file removed (test_industry_workflow_endpoints.py in tests/api/services/)
- [ ] **FAIL-03**: Template ID mismatches fixed (use real template IDs like "healthcare_patient_onboarding")
- [ ] **FAIL-04**: ROI request validation fixed (remove template_id from request body)
- [ ] **FAIL-05**: All 2FA routes test errors resolved (24 errors fixed)
- [ ] **FAIL-06**: 2FA test fixtures and dependencies properly configured
- [ ] **FAIL-07**: Overall test pass rate >= 98% (currently 90.6%)

### Core Services Coverage Expansion

- [ ] **CORE-01**: Token storage service coverage >= 80% (currently has gaps at line 17)
- [ ] **CORE-02**: Error handler decorator coverage >= 80% (gaps at line 74)
- [ ] **CORE-03**: Structured logger coverage >= 80% (gaps at lines 112, 187)
- [ ] **CORE-04**: API routes base coverage >= 80% (gaps at line 54)

### API Routes Coverage Expansion

- [ ] **API-01**: Episode routes coverage >= 80% (gaps at line 305)
- [ ] **API-02**: Auto-install routes coverage >= 80% (gaps at lines 25, 32)
- [ ] **API-03**: Admin routes coverage >= 80% (gaps at lines 99, 1065)
- [ ] **API-04**: Composition routes coverage >= 80% (gaps at line 35)

### Tools & Integration Coverage

- [ ] **TOOL-01**: Canvas tool coverage >= 80%
- [ ] **TOOL-02**: Browser automation tool coverage >= 80%
- [ ] **TOOL-03**: Device capabilities tool coverage >= 80%
- [ ] **TOOL-04**: Agent governance service coverage >= 80%
- [ ] **TOOL-05**: LLM routing and BYOK handler coverage >= 80%

### Quality Gates & Infrastructure

- [ ] **QUAL-01**: Backend actual line coverage >= 80% (up from 74.6%)
- [ ] **QUAL-02**: All tests passing with >= 98% pass rate
- [ ] **QUAL-03**: Property-based tests added for critical invariants (Hypothesis)
- [ ] **QUAL-04**: Coverage report generated and verified (HTML + JSON)
- [ ] **QUAL-05**: CI/CD workflows re-enabled after 80% target achieved

## v2 Requirements

Deferred to future milestone. Not in current v5.5 scope.

### Frontend Coverage
- **FRONT-01**: Next.js frontend coverage >= 80%
- **FRONT-02**: React components coverage >= 80%
- **FRONT-03**: State management coverage >= 80%

### Mobile Coverage
- **MOBILE-01**: React Native coverage >= 80%
- **MOBILE-02**: Platform-specific coverage (iOS/Android) >= 70%

### Desktop Coverage
- **DESK-01**: Tauri desktop coverage >= 80%
- **DESK-02**: Rust backend coverage >= 70%

## Out of Scope

| Feature | Reason |
|---------|--------|
| New feature development | This milestone focuses on testing existing features, not building new ones |
| Production deployment | Infrastructure setup and deployment automation (separate initiative) |
| Frontend testing | Deferred to v6.0 (backend focus for v5.5) |
| Mobile testing | Deferred to v6.0 (backend focus for v5.5) |
| Desktop testing | Deferred to v6.0 (backend focus for v5.5) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FAIL-01 | Phase 220 | Pending |
| FAIL-02 | Phase 220 | Pending |
| FAIL-03 | Phase 220 | Pending |
| FAIL-04 | Phase 220 | Pending |
| FAIL-05 | Phase 221 | Pending |
| FAIL-06 | Phase 221 | Pending |
| FAIL-07 | Phase 226 | Pending |
| CORE-01 | Phase 222 | Pending |
| CORE-02 | Phase 222 | Pending |
| CORE-03 | Phase 222 | Pending |
| CORE-04 | Phase 222 | Pending |
| API-01 | Phase 223 | Pending |
| API-02 | Phase 223 | Pending |
| API-03 | Phase 223 | Pending |
| API-04 | Phase 223 | Pending |
| TOOL-01 | Phase 224 | Pending |
| TOOL-02 | Phase 224 | Pending |
| TOOL-03 | Phase 224 | Pending |
| TOOL-04 | Phase 224 | Pending |
| TOOL-05 | Phase 224 | Pending |
| QUAL-01 | Phase 225 | Pending |
| QUAL-02 | Phase 226 | Pending |
| QUAL-03 | Phase 224 | Pending |
| QUAL-04 | Phase 225 | Pending |
| QUAL-05 | Phase 226 | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-22 after initial definition*
