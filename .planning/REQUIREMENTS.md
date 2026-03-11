# Requirements: Atom Backend 80% Coverage Initiative

**Defined:** 2026-03-11
**Core Value:** Critical system paths are thoroughly tested and validated before production deployment

## v5.4 Requirements

Requirements for Backend 80% Coverage milestone. Each maps to roadmap phases.

### Coverage Infrastructure & Measurement

- [ ] **COV-01**: Team can measure actual line coverage (not service-level estimates) across entire backend using coverage.py JSON output
- [ ] **COV-02**: Team can measure branch coverage with `--cov-branch` flag enabled in pytest configuration
- [ ] **COV-03**: Team can enforce progressive coverage thresholds (70% → 75% → 80%) via quality gates with emergency bypass mechanism
- [ ] **COV-04**: Team can generate coverage gap analysis identifying untested code prioritized by business impact (critical → moderate → low)
- [ ] **COV-05**: Team can generate test stub files for uncovered code using automated gap-driven tooling

### Core Services Testing

- [ ] **CORE-01**: Team can test agent governance service (maturity routing, permission checks, cache validation) at 80%+ line coverage
- [ ] **CORE-02**: Team can test LLM service (provider routing, cognitive tier classification, streaming, cache) at 80%+ line coverage
- [ ] **CORE-03**: Team can test episodic memory services (segmentation, retrieval modes, lifecycle) at 80%+ line coverage
- [ ] **CORE-04**: Team can test governance invariants using property-based tests (Hypothesis) - cache consistency, maturity rules, permission checks
- [ ] **CORE-05**: Team can test maturity matrix (4 levels × 4 complexities) using parametrized tests covering all agent behaviors

### API & Database Layer

- [ ] **API-01**: Team can test FastAPI endpoints (agent chat, canvas, browser, device, auth) at 75%+ line coverage using TestClient
- [ ] **API-02**: Team can test database models (CRUD operations, relationships, foreign keys, cascades) at 80%+ line coverage using SQLite temp DBs
- [ ] **API-03**: Team can test API contracts using Schemathesis for OpenAPI spec validation
- [ ] **API-04**: Team can test complex model relationships (many-to-many, self-referential, polymorphic) with proper session isolation
- [ ] **API-05**: Team can test error paths (401 unauthorized, 500 server errors, constraint violations) for all endpoints

### Tools & Integrations

- [ ] **TOOL-01**: Team can test browser automation tool (Playwright CDP, session management, screenshot capture) at 75%+ line coverage
- [ ] **TOOL-02**: Team can test device capabilities tool (camera, location, notifications, shell access) at 75%+ line coverage
- [ ] **TOOL-03**: Team can test LanceDB integration (vector search, semantic similarity, batch operations) at 70%+ line coverage with deterministic mocks
- [ ] **TOOL-04**: Team can test WebSocket connections (async streaming, connection lifecycle, error handling) using AsyncMock patterns
- [ ] **TOOL-05**: Team can test HTTP clients (LLM providers, external APIs) using responses library with proper error handling

### Gap Closure & Quality

- [ ] **GAP-01**: Team can audit coverage exclusions (`# pragma: no cover`) and remove outdated or unnecessary exclusions
- [ ] **GAP-02**: Team can write tests for error paths (network failures, timeouts, malformed responses) systematically across all services
- [ ] **GAP-03**: Team can write tests for edge cases (boundary conditions, invalid inputs, state transitions) across all services
- [ ] **GAP-04**: Team can fix flaky tests (timing issues, race conditions, async coordination) by addressing root causes not just adding retries
- [ ] **GAP-05**: Team can achieve 80% overall line coverage and 70%+ branch coverage across entire backend codebase

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Performance Testing
- **PERF-01**: Team can measure test execution time and identify slow tests (>1s) for optimization
- **PERF-02**: Team can run full test suite in parallel with pytest-xdist in <30 minutes

### Mutation Testing
- **MUT-01**: Team can validate test quality using mutation testing (mutmut or pymut) to verify branch coverage effectiveness

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| E2E Testing | Backend-focused milestone; E2E handled in Phase 148 (cross-platform orchestration) |
| Load Testing | Performance testing separate concern; use existing monitoring.py metrics instead |
| Fuzz Testing | Security testing separate initiative; property-based testing for invariants instead |
| New Feature Development | This milestone focuses on testing existing features, not building new capabilities |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| COV-01 | Phase 163 | Pending |
| COV-02 | Phase 163 | Pending |
| COV-03 | Phase 163 | Pending |
| COV-04 | Phase 164 | Pending |
| COV-05 | Phase 164 | Pending |
| CORE-01 | Phase 165 | Pending |
| CORE-02 | Phase 165 | Pending |
| CORE-03 | Phase 166 | Pending |
| CORE-04 | Phase 165 | Pending |
| CORE-05 | Phase 165 | Pending |
| API-01 | Phase 167 | Pending |
| API-02 | Phase 168 | Pending |
| API-03 | Phase 167 | Pending |
| API-04 | Phase 168 | Pending |
| API-05 | Phase 167 | Pending |
| TOOL-01 | Phase 169 | Pending |
| TOOL-02 | Phase 169 | Pending |
| TOOL-03 | Phase 170 | Pending |
| TOOL-04 | Phase 170 | Pending |
| TOOL-05 | Phase 170 | Pending |
| GAP-01 | Phase 171 | Pending |
| GAP-02 | Phase 171 | Pending |
| GAP-03 | Phase 171 | Pending |
| GAP-04 | Phase 171 | Pending |
| GAP-05 | Phase 171 | Pending |

**Coverage:**
- v5.4 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after initial definition*
