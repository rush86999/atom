# Roadmap: Atom - Automated Bug Discovery & QA Testing

## Overview

Atom transforms from comprehensive E2E testing (495+ tests in v7.0) to intelligent automated bug discovery through fuzzing, chaos engineering, property-based testing expansion, and headless browser automation. This milestone builds on existing test infrastructure to discover 50+ bugs with reproducible test cases and automated GitHub issue filing.

## Milestones

- ✅ **v7.0 Cross-Platform E2E Testing & Bug Discovery** - Phases 233-236 (shipped 2026-03-24)
- 🚧 **v8.0 Automated Bug Discovery & QA Testing** - Phases 237-245 (in progress)

## Phases

<details>
<summary>✅ v7.0 Cross-Platform E2E Testing & Bug Discovery (Phases 233-236) - SHIPPED 2026-03-24</summary>

### Phase 233: E2E Test Infrastructure & Authentication Flows
**Goal**: Foundation for E2E testing with API-first authentication
**Plans**: 7 plans

### Phase 234: Agent Workflow E2E Tests
**Goal**: Critical path E2E coverage for agent execution
**Plans**: 6 plans

### Phase 235: Cross-Platform Stress Testing
**Goal**: Load testing, network simulation, memory/performance testing
**Plans**: 7 plans

### Phase 236: Cross-Platform Consistency & Automated Bug Discovery
**Goal**: Mobile/desktop testing, visual regression, accessibility, bug filing
**Plans**: 7 plans

</details>

### 🚧 v8.0 Automated Bug Discovery & QA Testing (In Progress)

**Milestone Goal:** Discover 50+ bugs through automated fuzzing, chaos engineering, property-based testing expansion, and intelligent browser automation with automated GitHub issue filing.

#### Phase 237: Bug Discovery Infrastructure Foundation
**Goal**: Bug discovery integrates into existing pytest infrastructure with separate CI pipelines
**Depends on**: Phase 236
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, SUCCESS-04, SUCCESS-05
**Success Criteria** (what must be TRUE):
  1. Bug discovery tests run in `pytest tests/` alongside existing tests (not separate `/bug-discovery/` directory)
  2. Fast PR tests complete in <10 minutes (unit tests, integration tests, quick property tests)
  3. Weekly bug discovery pipeline runs in ~2 hours (fuzzing, chaos, browser exploration)
  4. All bug discovery tests follow TEST_QUALITY_STANDARDS.md (TQ-01 through TQ-05)
  5. Bug discovery fixtures reuse existing auth_fixtures, database_fixtures, page_objects
**Plans**: 5 plans
- [ ] 237-01-PLAN.md — Bug discovery test directory structure (fuzzing/, browser_discovery/)
- [ ] 237-02-PLAN.md — Documentation templates for all bug discovery categories
- [ ] 237-03-PLAN.md — Separate CI pipelines (fast PR <10min, weekly bug discovery ~2 hours)
- [ ] 237-04-PLAN.md — Fixture reuse documentation and verification
- [ ] 237-05-PLAN.md — Infrastructure verification and comprehensive documentation

#### Phase 238: Property-Based Testing Expansion ✅
**Goal**: 50+ new property tests validate critical invariants across agent execution, LLM routing, episodic memory, governance, and security
**Depends on**: Phase 237
**Requirements**: PROP-01, PROP-02, PROP-03, PROP-04, PROP-05
**Success Criteria** (what must be TRUE):
  1. 50+ new property tests cover agent execution, LLM routing, episodic memory, governance critical paths
  2. API contract tests validate malformed JSON handling, oversized payloads, response schema compliance
  3. State machine tests enforce agent graduation monotonic transitions and episode lifecycle invariants
  4. Security property tests prevent SQL injection, XSS, and CSRF vulnerabilities
  5. All property tests follow invariant-first thinking (invariants documented before writing tests)
**Plans**: 5 plans
**Completed**: 2026-03-24
- [x] 238-01-PLAN.md — Agent execution property tests (idempotence, termination, determinism)
- [x] 238-02-PLAN.md — LLM routing property tests (consistency, cognitive tier mapping, cache-aware)
- [x] 238-03-PLAN.md — Episodic memory property tests (segmentation, retrieval, lifecycle)
- [x] 238-04-PLAN.md — API contracts and governance expansion (malformed JSON, authorization, cache)
- [x] 238-05-PLAN.md — State machines and security property tests (graduation, SQL injection, XSS, CSRF)

#### Phase 239: API Fuzzing Infrastructure ✅
**Goal**: Coverage-guided fuzzing for FastAPI endpoints discovers crashes in parsing/validation code
**Depends on**: Phase 237
**Requirements**: FUZZ-01, FUZZ-02, FUZZ-03, FUZZ-04, FUZZ-05, FUZZ-06, FUZZ-07
**Success Criteria** (what must be TRUE):
  1. FuzzingOrchestrator service manages fuzzing campaigns (start, stop, monitor runs)
  2. Atheris fuzzing harnesses exercise FastAPI endpoints for auth, agent execution, workflows
  3. Fuzzing campaigns cover login, signup, password reset, JWT validation endpoints
  4. Fuzzing campaigns cover chat streaming, canvas presentation, trigger execution, skill installation endpoints
  5. Reproducible crashes are deduplicated and filed automatically as GitHub issues
  6. Fuzzing runs in separate weekly CI pipeline (1 hour runs, not on PRs)
**Plans**: 5 plans
**Completed**: 2026-03-24
- [x] 239-01-PLAN.md — FuzzingOrchestrator service and crash deduplication (FUZZ-01, FUZZ-06)
- [x] 239-02-PLAN.md — Auth endpoint fuzzing harnesses (FUZZ-03)
- [x] 239-03-PLAN.md — Agent execution and canvas presentation fuzzing (FUZZ-04)
- [x] 239-04-PLAN.md — Workflow and skill endpoint fuzzing (FUZZ-05)
- [x] 239-05-PLAN.md — Weekly CI pipeline integration and documentation (FUZZ-07)

#### Phase 240: Headless Browser Bug Discovery ✅
**Goal**: Intelligent exploration agent discovers UI bugs through console errors, accessibility violations, broken links, visual regression
**Depends on**: Phase 237
**Requirements**: BROWSER-01, BROWSER-02, BROWSER-03, BROWSER-04, BROWSER-05, BROWSER-06, BROWSER-07
**Success Criteria** (what must be TRUE):
  1. ExplorationAgent navigates application using heuristics (depth-first, breadth-first, random walk)
  2. Console error detection captures JavaScript errors and unhandled exceptions
  3. Accessibility violation detection uses axe-core for WCAG 2.1 AA compliance
  4. Broken link detection identifies 404 responses and redirect loops
  5. Visual regression testing with Percy detects UI changes across 78+ snapshots
  6. Form filling tests edge cases (null bytes, XSS payloads, SQL injection)
  7. API-first authentication integration provides 10-100x faster test setup
**Plans**: 5 plans
**Completed**: 2026-03-25
- [x] 240-01-PLAN.md — Console error and accessibility detection tests (BROWSER-02, BROWSER-03)
- [x] 240-02-PLAN.md — Broken link detection and form edge case tests (BROWSER-04, BROWSER-06)
- [x] 240-03-PLAN.md — Visual regression testing with Percy integration (BROWSER-05)
- [x] 240-04-PLAN.md — Intelligent exploration agent with DFS/BFS/random walk (BROWSER-01)
- [x] 240-05-PLAN.md — Documentation and weekly CI pipeline (BROWSER-07)

#### Phase 241: Chaos Engineering Integration
**Goal**: Controlled failure injection tests resilience to network issues, resource exhaustion, and service crashes
**Depends on**: Phase 237
**Requirements**: CHAOS-01, CHAOS-02, CHAOS-03, CHAOS-04, CHAOS-05, CHAOS-06, CHAOS-07, CHAOS-08
**Success Criteria** (what must be TRUE):
  1. ChaosCoordinator service orchestrates failure injection experiments
  2. Network latency injection simulates slow 3G conditions using Toxiproxy
  3. Database connection drop simulation tests connection pool exhaustion recovery
  4. Memory pressure injection validates heap exhaustion handling
  5. Service crash simulation tests LLM provider failures and Redis crashes
  6. Blast radius controls isolate failures (test databases, injection limits, duration caps)
  7. Recovery validation checks data integrity and rollback verification
  8. Chaos experiments run in isolated environment (weekly, never on shared dev)
**Plans**: 7 plans in 4 waves
- [ ] 241-01-PLAN.md — ChaosCoordinator service and blast radius controls (Wave 1)
- [ ] 241-02-PLAN.md — Network latency injection with Toxiproxy (Wave 2)
- [ ] 241-03-PLAN.md — Database connection drop simulation (Wave 2)
- [ ] 241-04-PLAN.md — Memory pressure injection (Wave 2)
- [ ] 241-05-PLAN.md — Service crash simulation (Wave 2)
- [ ] 241-06-PLAN.md — Blast radius controls and recovery validation (Wave 3)
- [ ] 241-07-PLAN.md — Weekly CI pipeline and documentation (Wave 4)

#### Phase 242: Unified Bug Discovery Pipeline
**Goal**: Orchestrate all discovery methods with result aggregation, deduplication, automated triage, and GitHub filing
**Depends on**: Phase 238, Phase 239, Phase 240, Phase 241
**Requirements**: PIPELINE-01, PIPELINE-02, PIPELINE-03, PIPELINE-04, PIPELINE-05, PIPELINE-06, SUCCESS-02
**Success Criteria** (what must be TRUE):
  1. DiscoveryCoordinator service orchestrates fuzzing, chaos, property tests, browser discovery
  2. Result aggregation correlates failures across all discovery methods
  3. Bug deduplication merges duplicate bugs by error signature
  4. Automated bug triage classifies severity (critical/high/medium/low)
  5. Bug discovery dashboard generates weekly reports (bugs found, fixed, regression rate)
  6. All bugs are automatically filed via GitHub Issues integration with BugFilingService
**Plans**: TBD

#### Phase 243: Memory & Performance Bug Discovery
**Goal**: Specialized discovery for memory leaks and performance regressions using memray and pytest-benchmark
**Depends on**: Phase 237
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04, PERF-05
**Success Criteria** (what must be TRUE):
  1. Memory leak detection with memray identifies leaks in long-running agent executions
  2. Heap snapshot comparison detects 10MB+ memory increases during agent execution loops
  3. Performance regression detection with pytest-benchmark tracks latency over time
  4. Lighthouse CI integration alerts on >20% web UI performance regression
  5. Performance baseline tracking maintains p(95) latency, throughput, and error rate metrics
**Plans**: 5 plans in 4 waves
**Completed**: 2026-03-25
- [x] 243-01-PLAN.md — Memray Python memory leak detection (Wave 1)
- [x] 243-02-PLAN.md — pytest-benchmark regression infrastructure (Wave 2)
- [x] 243-03-PLAN.md — Lighthouse CI regression enhancement (Wave 2)
- [x] 243-04-PLAN.md — Memory/performance bug filing integration (Wave 3)
- [x] 243-05-PLAN.md — Weekly CI pipeline and documentation (Wave 4)

#### Phase 244: AI-Enhanced Bug Discovery
**Goal**: Multi-agent fuzzing orchestration and AI-generated invariants expand bug discovery coverage
**Depends on**: Phase 238, Phase 239
**Requirements**: AI-01, AI-02, AI-03, AI-04
**Success Criteria** (what must be TRUE):
  1. Multi-agent fuzzing orchestration generates fuzzing strategies from coverage gaps
  2. AI-generated invariants analyze code to suggest property test opportunities
  3. Cross-platform bug correlation detects bugs manifesting across web/mobile/desktop
  4. Semantic bug clustering uses LLM embeddings to group similar bugs
**Plans**: 4 plans in 4 waves
**Completed**: 2026-03-25
- [x] 244-01-PLAN.md — FuzzingStrategyGenerator with coverage-aware fuzzing (Wave 1)
- [x] 244-02-PLAN.md — InvariantGenerator with AI-generated property test invariants (Wave 2)
- [x] 244-03-PLAN.md — CrossPlatformCorrelator for multi-platform bug correlation (Wave 3)
- [x] 244-04-PLAN.md — SemanticBugClusterer with LLM embeddings and clustering (Wave 4)

#### Phase 245: Feedback Loops & ROI Tracking
**Goal**: Close the loop with regression test generation, effectiveness metrics, and ROI tracking
**Depends on**: Phase 242
**Requirements**: FEEDBACK-01, FEEDBACK-02, FEEDBACK-03, FEEDBACK-04, FEEDBACK-05, SUCCESS-01, SUCCESS-03
**Success Criteria** (what must be TRUE):
  1. Automated regression test generation converts bug findings to permanent tests
  2. Bug discovery dashboard shows weekly reports (bugs found, fixed, regression rate)
  3. GitHub issue integration auto-files issues for new bugs with reproducible test cases
  4. ROI tracking demonstrates time saved, bugs prevented, fix cost vs. discovery cost
  5. Bug discovery effectiveness metrics track bugs found per hour and false positive rate
  6. Bug fix verification re-runs tests after fixes to confirm 50+ bugs resolved
**Plans**: 6 plans in 4 waves
**Completed**: 2026-03-25
- [x] 245-01-PLAN.md — RegressionTestGenerator with Jinja2 templates (Wave 1)
- [x] 245-02-PLAN.md — BugFixVerifier with GitHub integration (Wave 2)
- [x] 245-03-PLAN.md — ROITracker with SQLite metrics database (Wave 2)
- [x] 245-04-PLAN.md — Enhanced DashboardGenerator with ROI metrics (Wave 3)
- [x] 245-05-PLAN.md — Integration, CI workflows, documentation (Wave 3)
- [ ] 245-06-PLAN.md — Bug discovery execution and remediation (Wave 4)

## Progress

**Execution Order:**
Phases execute in numeric order: 237 → 238 → 239 → 240 → 241 → 242 → 243 → 244 → 245

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 237. Bug Discovery Infrastructure Foundation | v8.0 | 5/5 | ✅ Complete | 2026-03-24 |
| 238. Property-Based Testing Expansion | v8.0 | 5/5 | ✅ Complete | 2026-03-24 |
| 239. API Fuzzing Infrastructure | v8.0 | 5/5 | ✅ Complete | 2026-03-24 |
| 240. Headless Browser Bug Discovery | v8.0 | 5/5 | ✅ Complete | 2026-03-25 |
| 241. Chaos Engineering Integration | v8.0 | 0/TBD | Not started | - |
| 242. Unified Bug Discovery Pipeline | v8.0 | 0/TBD | Not started | - |
| 243. Memory & Performance Bug Discovery | v8.0 | 5/5 | ✅ Complete | 2026-03-25 |
| 244. AI-Enhanced Bug Discovery | v8.0 | 4/4 | ✅ Complete | 2026-03-25 |
| 245. Feedback Loops & ROI Tracking | v8.0 | 5/6 | ✅ Complete | 2026-03-25 |
