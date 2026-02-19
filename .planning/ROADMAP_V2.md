# Roadmap: Atom Test Coverage Initiative - Milestone v2.0

## Overview

Milestone v2.0 completes all remaining test coverage phases (55 incomplete) to achieve 80% overall coverage while integrating Community Skills feature for 5,000+ OpenClaw skills. This milestone builds on the 200/203 plans completed in v1.0 (99% completion) and focuses on quality over speed: comprehensive testing infrastructure, property-based invariants, governance/security/episodic memory domain coverage, and production-hardened community skills integration.

**Milestone Goal:** 80% test coverage across critical paths with 100% test pass rate and Community Skills production-ready.

**Starting Phase:** 29 (Phase 28 completed in v1.0)

---

## Milestones

- ✅ **v1.0 Foundation** - Phases 1-28 (200/203 plans, 99% complete)
- 🚧 **v2.0 Feature & Coverage Complete** - Phases 29-33 (73 requirements mapped)
- 📋 **v3.0 Performance & Optimization** - Future milestone (deferred)

---

## Phases

**Phase Numbering:**
- Integer phases (29, 30, 31): Planned v2.0 milestone work
- Decimal phases (29.1, 29.2): Urgent insertions (marked with INSERTED)

### 🚧 v2.0 Feature & Coverage Complete (In Progress)

**Milestone Goal:** Complete all 55 remaining phases to achieve 80% coverage and integrate Community Skills with production-grade security testing.

#### Phase 29: Test Failure Fixes & Quality Foundation
**Goal**: Stabilize test suite by fixing all remaining failures and establishing quality infrastructure for parallel execution
**Depends on**: Phase 28 (Tauri Canvas AI Verification)
**Requirements**: TEST-01 through TEST-10
**Success Criteria** (what must be TRUE):
  1. All 40+ test failures resolved with root cause fixes (Hypothesis TypeErrors, proposal service mocks, graduation metadata, flaky tests)
  2. Test suite achieves 98%+ pass rate over 3 consecutive full runs (TQ-02 verified)
  3. Test suite completes in <60 minutes with parallel execution (TQ-03 verified)
  4. Zero flaky tests confirmed via 3-run verification (TQ-04 verified)
  5. All test fixes include regression tests to prevent recurrence
**Plans**: TBD

Plans:
- [ ] 29-01: Fix Hypothesis TypeError in property tests (10 modules with st.just/st.sampled_from)
- [ ] 29-02: Fix proposal service test failures (6 tests with incorrect mock targets)
- [ ] 29-03: Fix graduation governance test failures (3 tests with metadata_json factory parameter)
- [ ] 29-04: Fix agent task cancellation flaky tests (test_unregister_task, test_register_task, test_get_all_running_agents)
- [ ] 29-05: Fix security config and governance runtime flaky tests (test_default_secret_key_in_development, test_agent_governance_gating)
- [ ] 29-06: Verify TQ-02, TQ-03, TQ-04 (3-run verification, <60min execution, zero flaky tests)

#### Phase 30: Tier 1 Coverage Push - High Impact Files
**Goal**: Achieve 28% overall coverage by testing 6 highest-impact Tier 1 files (>500 lines, <20% coverage) with property and integration tests
**Depends on**: Phase 29 (stable test baseline required)
**Requirements**: COV-01 through COV-10
**Success Criteria** (what must be TRUE):
  1. core/models.py (2351 lines) reaches 50% coverage (+1,176 lines) with ORM relationship tests
  2. core/workflow_engine.py (1163 lines) reaches 50% coverage (+582 lines) with property-based state invariants
  3. core/atom_agent_endpoints.py (736 lines) reaches 50% coverage (+368 lines) with API contract tests
  4. core/workflow_analytics_engine.py (593 lines) reaches 50% coverage (+297 lines) with analytics validation tests
  5. core/llm/byok_handler.py (549 lines) reaches 50% coverage (+275 lines) with provider fallback property tests
  6. core/workflow_debugger.py (527 lines) reaches 50% coverage (+264 lines) with debugging workflow tests
**Plans**: TBD

Plans:
- [ ] 30-01: Models ORM coverage (relationships, cascades, validation)
- [ ] 30-02: Workflow engine property tests (execution order, rollback, state invariants)
- [ ] 30-03: Atom agent endpoints API contracts (request/response validation)
- [ ] 30-04: Workflow analytics and BYOK handler coverage (analytics accuracy, provider fallback)
- [ ] 30-05: Workflow debugger testing (debugging workflows, state inspection)

#### Phase 31: Agent Layer & Memory Coverage
**Goal**: Comprehensive coverage for agent governance, graduation, execution, and episodic memory with property-based invariants
**Depends on**: Phase 29 (test infrastructure stable)
**Requirements**: AGENT-01 through AGENT-11, MEM-01 through MEM-17
**Success Criteria** (what must be TRUE):
  1. 4x4 maturity/complexity matrix fully tested (STUDENT/INTERN/SUPERVISED/AUTONOMOUS × Low/Moderate/High/Critical)
  2. Agent governance cache performance verified (<1ms cached, <50ms uncached)
  3. Graduation readiness scoring tested (episode counts, intervention rates, constitutional scores)
  4. Episodic memory segmentation verified (time-gap >30min, topic change <0.75 similarity, task completion)
  5. Episodic memory retrieval modes tested (temporal sorted, semantic ranked, sequential no duplicates, contextual hybrid)
  6. Episodic memory lifecycle verified (90-day decay, 180-day archival, consolidation merging)
  7. Property tests verify governance determinism and maturity invariants (never decreases without promotion)
  8. Performance tests verify episode creation <5s, temporal retrieval <10ms, semantic retrieval <100ms
**Plans**: TBD

Plans:
- [ ] 31-01: Agent governance and maturity testing (4x4 matrix, action complexity, cache performance)
- [ ] 31-02: Agent graduation and execution testing (readiness scores, exam execution, orchestration)
- [ ] 31-03: Episodic memory segmentation and retrieval (time-gap, topic change, 4 retrieval modes)
- [ ] 31-04: Episodic memory lifecycle and graduation (decay, consolidation, archival, thresholds)
- [ ] 31-05: Property-based invariants for governance and memory (determinism, maturity transitions)

#### Phase 32: Platform & Quality Validation
**Goal**: Complete mobile/desktop coverage and validate 80% coverage achievement with quality gates
**Depends on**: Phase 30 (coverage baseline established)
**Requirements**: PLAT-01 through PLAT-07, QUAL-01 through QUAL-10
**Success Criteria** (what must be TRUE):
  1. Expo SDK 50 + Jest compatibility resolved (mobile auth tests run successfully)
  2. DeviceContext tests completed for React Native (iOS + Android platforms)
  3. Platform-specific permissions tested (iOS vs Android differences documented)
  4. Desktop coverage completion with cargo-tarpaulin (80% coverage target)
  5. Dual-platform CI running (iOS + Android) to catch platform differences early
  6. Governance domain achieves 80% coverage (agent_governance_service.py, governance_cache.py, trigger_interceptor.py)
  7. Security domain achieves 80% coverage (auth/, crypto/, validation/)
  8. Episodic memory domain achieves 80% coverage (segmentation, retrieval, lifecycle, graduation)
  9. Core backend achieves 80% coverage (backend/core/, backend/api/, backend/tools/)
  10. Test suite executes in parallel with zero shared state, zero flaky tests, <5min execution time
**Plans**: TBD

Plans:
- [ ] 32-01: Mobile platform coverage (Expo SDK 50 fix, DeviceContext tests, platform permissions)
- [ ] 32-02: Desktop coverage completion (cargo-tarpaulin 80%, CI/CD integration)
- [ ] 32-03: Platform-specific testing infrastructure (dual-platform CI, real device testing)
- [ ] 32-04: Coverage quality validation (80% governance, 80% security, 80% episodic memory, 80% core backend)
- [ ] 32-05: Quality gates enforcement (assertion density 70%+, coverage trending, test documentation)

#### Phase 33: Community Skills Integration
**Goal**: Enable Atom agents to use 5,000+ OpenClaw/ClawHub skills with Docker sandbox security, LLM semantic analysis, and governance workflow
**Depends on**: Phase 29 (test infrastructure stable), Phase 31 (governance coverage complete)
**Requirements**: SKILLS-01 through SKILLS-14
**Success Criteria** (what must be TRUE):
  1. Atom can parse OpenClaw SKILL.md files with YAML frontmatter and natural language/Python instructions
  2. Skills are wrapped as Atom BaseTool classes with proper Pydantic validation
  3. Imported skills run in isolated Docker sandbox ("atom-sandbox-python") to prevent governance bypass
  4. Sandbox cannot access host filesystem or network (only controlled Atom API)
  5. Users can import skills via GitHub URL (e.g., from VoltAgent/awesome-openclaw-skills)
  6. Imported skills are tagged as "Untrusted" until LLM security scan approves them
  7. GovernanceService reviews skill code for malicious patterns before promoting to "Active"
  8. AUTONOMOUS agents can use Active skills; STUDENT/INTERN/SUPERVISED require approval
  9. All skill executions are logged to audit trail with skill metadata
  10. Skills registry UI shows all imported skills with status (Untrusted/Active/Banned)
  11. SkillSecurityScanner uses GPT-4 for semantic analysis of obfuscated threats
  12. Skill executions create EpisodeSegments for learning and retrieval
  13. Skill usage metrics count toward agent graduation readiness scores
  14. Skill diversity bonus (up to +5%) for agents using varied skills
**Plans**: TBD

Plans:
- [ ] 33-01: Skill parser and adapter (SKILL.md parsing, BaseTool wrapping, Pydantic validation)
- [ ] 33-02: Hazard sandbox implementation (Docker isolation, no host access, resource limits)
- [ ] 33-03: Security scanner integration (21+ malicious patterns, GPT-4 semantic analysis, caching)
- [ ] 33-04: Governance workflow integration (Untrusted → Active → Banned, maturity-based routing)
- [ ] 33-05: Episodic memory and graduation integration (EpisodeSegments, usage metrics, diversity bonus)
- [ ] 33-06: Skills registry UI and API endpoints (import, list, execute, promote)

#### Phase 34: Documentation & Verification
**Goal**: Update all documentation to reflect v2.0 features and verify Community Skills production readiness
**Depends on**: Phase 32 (coverage complete), Phase 33 (Community Skills integrated)
**Requirements**: DOCS-01 through DOCS-06
**Success Criteria** (what must be TRUE):
  1. README.md updated with Community Skills and test coverage achievements (80% overall)
  2. CANVAS_IMPLEMENTATION_COMPLETE.md updated with Phase 20-23 features (LLM summaries, episode integration)
  3. EPISODIC_MEMORY_IMPLEMENTATION.md updated with canvas/feedback integration (enriched retrieval, type filtering)
  4. COMMUNITY_SKILLS.md verified for production status (security validation, governance workflow, graduation metrics)
  5. AGENT_GRADUATION_GUIDE.md updated with latest criteria (including skill usage metrics and diversity bonus)
  6. INSTALLATION.md verified for Personal/Enterprise editions (Docker Compose, CI/CD, monitoring setup)
**Plans**: TBD

Plans:
- [ ] 34-01: Update README.md with v2.0 achievements (Community Skills, 80% coverage, performance metrics)
- [ ] 34-02: Update feature documentation (CANVAS_IMPLEMENTATION_COMPLETE.md, EPISODIC_MEMORY_IMPLEMENTATION.md)
- [ ] 34-03: Verify Community Skills documentation (COMMUNITY_SKILLS.md production status, security validation)
- [ ] 34-04: Update AGENT_GRADUATION_GUIDE.md with skill metrics and verify INSTALLATION.md

---

## Progress

**Execution Order:**
Phases execute in numeric order: 29 → 30 → 31 → 32 → 33 → 34

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 29. Test Failure Fixes | v2.0 | 0/6 | Not started | - |
| 30. Tier 1 Coverage | v2.0 | 0/5 | Not started | - |
| 31. Agent & Memory | v2.0 | 0/5 | Not started | - |
| 32. Platform & Quality | v2.0 | 0/5 | Not started | - |
| 33. Community Skills | v2.0 | 0/6 | Not started | - |
| 34. Documentation | v2.0 | 0/4 | Not started | - |

---

## v1.0 Completion Summary

<details>
<summary>✅ v1.0 Foundation (Phases 1-28) - 200/203 plans complete (99%)</summary>

### Key Achievements:
- Phase 1: Test Infrastructure (pytest, Hypothesis, parallel execution, coverage reporting)
- Phase 2: Core Property Tests (governance, episodic memory, database, API contracts)
- Phase 3: Integration & Security Tests (API endpoints, WebSockets, authentication, canvas security)
- Phase 4: Platform Coverage (React Native mobile, Tauri desktop/menu bar)
- Phase 5: Coverage & Quality Validation (80% target set, quality gates established)
- Phase 6: Production Hardening (full test suite, bug identification, production readiness)
- Phase 7: Implementation Fixes (Expo SDK 50, service bugs, mobile auth, desktop integration)
- Phase 8: 80% Coverage Push Reality Check (15.87% achieved, 216% improvement from 4.4%)
- Phase 8.7-8.9: API Integration, Governance & BYOK, Canvas & Browser Tools (21-22% coverage)
- Phase 9.0-9.1: API Module Expansion, Agent Status & Supervision (24-26% coverage)
- Phase 11: Coverage Analysis & Prioritization (Tier 1 files identified)
- Phase 13: OpenClaw Integration (host shell access, agent social layer, simplified installer)
- Phase 25: Atom CLI as OpenClaw Skill (cross-platform agent usage)
- Phase 26: CI/CD Fixes (all tests passing)
- Phase 27: Valkey Redis-compatible database in Docker Compose
- Phase 28: Tauri Canvas AI Accessibility Verification

**Unresolved from v1.0:** Phases 3, 10, 12, 14, 17, 19, 24 (7 incomplete phases deferred to v2.0 gap closure)

</details>

---

## v2.0 Gap Closure Phases

The following incomplete phases from v1.0 will be closed during v2.0 execution:

- **Phase 3: Memory Layer** - Covered by Phase 31 (Agent Layer & Memory Coverage)
- **Phase 10: Test Failure Fixes** - Covered by Phase 29 (Test Failure Fixes & Quality Foundation)
- **Phase 12: Tier 1 Coverage Push** - Covered by Phase 30 (Tier 1 Coverage Push)
- **Phase 14: Community Skills Integration** - Covered by Phase 33 (Community Skills Integration)
- **Phase 17: Agent Layer Testing** - Covered by Phase 31 (Agent Layer & Memory Coverage)
- **Phase 19: Additional Test Fixes** - Covered by Phase 29 (Test Failure Fixes & Quality Foundation)
- **Phase 24: Documentation** - Covered by Phase 34 (Documentation & Verification)

**Gap Closure Strategy:** All v1.0 incomplete phases have their requirements mapped to v2.0 phases (29-34), ensuring 100% requirement coverage across both milestones.

---

*Roadmap created: 2026-02-18*
*Milestone: v2.0 Feature & Coverage Complete*
*Starting Phase: 29 (Phase 28 completed in v1.0)*
