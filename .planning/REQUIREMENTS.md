# Requirements: Atom Test Coverage Initiative

**Defined:** 2026-02-10 (v1), 2026-02-18 (v2.0)
**Core Value:** Critical system paths are thoroughly tested and validated before production deployment

## v1 Requirements (COMPLETE)

All v1 requirements were completed in Milestone v1.0 (200/203 plans).

---

## v2.0 Requirements

Requirements for completing all 55 remaining phases to achieve 80% test coverage and integrate Community Skills feature.

### Community Skills Integration

**Table stakes:** SKILL.md parsing, Docker sandbox execution, security scanning, governance workflow

- [ ] **SKILLS-01**: Atom can parse OpenClaw SKILL.md files with YAML frontmatter and natural language/Python instructions
- [ ] **SKILLS-02**: Skills are wrapped as Atom BaseTool classes with proper Pydantic validation
- [ ] **SKILLS-03**: Imported skills run in isolated Docker sandbox ("atom-sandbox-python") to prevent governance bypass
- [ ] **SKILLS-04**: Sandbox cannot access host filesystem or network (only controlled Atom API)
- [ ] **SKILLS-05**: Users can import skills via GitHub URL (e.g., from VoltAgent/awesome-openclaw-skills)
- [ ] **SKILLS-06**: Imported skills are tagged as "Untrusted" until LLM security scan approves them
- [ ] **SKILLS-07**: GovernanceService reviews skill code for malicious patterns before promoting to "Active"
- [ ] **SKILLS-08**: AUTONOMOUS agents can use Active skills; STUDENT/INTERN/SUPERVISED require approval
- [ ] **SKILLS-09**: All skill executions are logged to audit trail with skill metadata
- [ ] **SKILLS-10**: Skills registry UI shows all imported skills with status (Untrusted/Active/Banned)

**Differentiators:** LLM semantic analysis, episodic memory integration, graduation tracking

- [ ] **SKILLS-11**: SkillSecurityScanner uses GPT-4 for semantic analysis of obfuscated threats
- [ ] **SKILLS-12**: Skill executions create EpisodeSegments for learning and retrieval
- [ ] **SKILLS-13**: Skill usage metrics count toward agent graduation readiness scores
- [ ] **SKILLS-14**: Skill diversity bonus (up to +5%) for agents using varied skills

### Test Failure Fixes

**Table stakes:** All tests passing, stable baseline, quality metrics met

- [ ] **TEST-01**: Fix Hypothesis TypeError in property tests (10 modules with st.just/st.sampled_from issues)
- [ ] **TEST-02**: Fix proposal service test failures (6 tests with incorrect mock targets)
- [ ] **TEST-03**: Verify 98%+ test pass rate (TQ-02: run full suite 3 times, <2% failures allowed)
- [ ] **TEST-04**: Fix graduation governance test failures (3 tests with metadata_json factory parameter issue)
- [ ] **TEST-05**: Verify test suite performance <60 minutes (TQ-03: full suite execution time)
- [ ] **TEST-06**: Fix agent task cancellation flaky tests (test_unregister_task, test_register_task, test_get_all_running_agents)
- [ ] **TEST-07**: Fix security config and governance runtime flaky tests (test_default_secret_key_in_development, test_agent_governance_gating)
- [ ] **TEST-08**: Verify zero flaky tests (TQ-04: 3 consecutive runs with identical results)

**Differentiators:** Root cause fixes, not just symptom patches

- [ ] **TEST-09**: All test fixes include regression tests to prevent recurrence
- [ ] **TEST-10**: Test failures documented with root cause analysis in commit messages

### Coverage Push - Tier 1 Files

**Table stakes:** Achieve 28% overall coverage by testing highest-impact files

- [ ] **COV-01**: core/models.py (2351 lines) reaches 50% coverage (+1,176 lines)
- [ ] **COV-02**: core/workflow_engine.py (1163 lines) reaches 50% coverage (+582 lines)
- [ ] **COV-03**: core/atom_agent_endpoints.py (736 lines) reaches 50% coverage (+368 lines)
- [ ] **COV-04**: core/workflow_analytics_engine.py (593 lines) reaches 50% coverage (+297 lines)
- [ ] **COV-05**: core/llm/byok_handler.py (549 lines) reaches 50% coverage (+275 lines)
- [ ] **COV-06**: core/workflow_debugger.py (527 lines) reaches 50% coverage (+264 lines)

**Differentiators:** Property tests for stateful logic, integration tests for API endpoints

- [ ] **COV-07**: Property tests verify workflow_engine stateful invariants (execution order, rollback)
- [ ] **COV-08**: Property tests verify byok_handler provider fallback invariants
- [ ] **COV-09**: Integration tests verify atom_agent_endpoints API contracts
- [ ] **COV-10**: Unit tests verify models.py ORM relationships and cascades

### Agent Layer Testing

**Table stakes:** Comprehensive governance, graduation, execution coverage

- [ ] **AGENT-01**: 4x4 maturity/complexity matrix tests (STUDENT/INTERN/SUPERVISED/AUTONOMOUS × Low/Moderate/High/Critical)
- [ ] **AGENT-02**: Action complexity validation (60+ actions across all complexity levels)
- [ ] **AGENT-03**: Governance cache performance tests (<1ms cached, <50ms uncached)
- [ ] **AGENT-04**: Graduation readiness scoring tests (episode counts, intervention rates, constitutional scores)
- [ ] **AGENT-05**: Graduation exam execution tests (validate promotion readiness)
- [ ] **AGENT-06**: Trigger interceptor routing tests (STUDENT → training, INTERN → proposal, SUPERVISED → supervision)
- [ ] **AGENT-07**: Agent execution orchestration tests (coordination, state management, error recovery)
- [ ] **AGENT-08**: Agent-to-agent communication tests (message passing, coordination invariants)

**Differentiators:** Property-based invariants, end-to-end workflows

- [ ] **AGENT-09**: Property tests verify agent maturity never decreases without explicit promotion
- [ ] **AGENT-10**: Property tests verify governance decisions are deterministic (same inputs → same routing)
- [ ] **AGENT-11**: Integration tests verify agent execution → episodic memory → graduation feedback loop

### Memory Layer Verification

**Table stakes:** Episodic memory coverage with property-based invariants

- [ ] **MEM-01**: Segmentation tests verify time-gap detection (>30min threshold)
- [ ] **MEM-02**: Segmentation tests verify topic change detection (similarity <0.75)
- [ ] **MEM-03**: Segmentation tests verify task completion boundaries
- [ ] **MEM-04**: Retrieval tests verify temporal queries are sorted by time (AR-12 invariant)
- [ ] **MEM-05**: Retrieval tests verify semantic queries are ranked by similarity (AR-12 invariant)
- [ ] **MEM-06**: Retrieval tests verify sequential queries return full episodes (no duplicates)
- [ ] **MEM-07**: Retrieval tests verify contextual queries use hybrid search (temporal + semantic)
- [ ] **MEM-08**: Lifecycle tests verify decay (90-day threshold, 180-day archival)
- [ ] **MEM-09**: Lifecycle tests verify consolidation (similarity-based merging)
- [ ] **MEM-10**: Graduation tests verify episode count thresholds (10/25/50)
- [ ] **MEM-11**: Graduation tests verify intervention rate thresholds (50%/20%/0%)
- [ ] **MEM-12**: Graduation tests verify constitutional score thresholds (0.70/0.85/0.95)

**Differentiators:** Performance SLAs, canvas/feedback integration

- [ ] **MEM-13**: Performance tests verify episode creation <5s
- [ ] **MEM-14**: Performance tests verify temporal retrieval <10ms
- [ ] **MEM-15**: Performance tests verify semantic retrieval <100ms
- [ ] **MEM-16**: Canvas-aware episodes track all canvas interactions (present, submit, close, update, execute)
- [ ] **MEM-17**: Feedback-linked episodes aggregate user feedback scores for retrieval weighting

### Platform Coverage Completion

**Table stakes:** Mobile and desktop test coverage completion

- [ ] **PLAT-01**: Resolve Expo SDK 50 + Jest compatibility issue (mobile auth tests can run)
- [ ] **PLAT-02**: Complete DeviceContext tests for React Native (iOS + Android platforms)
- [ ] **PLAT-03**: Platform-specific permissions tests (iOS vs Android differences documented)
- [ ] **PLAT-04**: Desktop coverage completion with cargo-tarpaulin (80% coverage target)
- [ ] **PLAT-05**: Desktop CI/CD integration for automated test execution

**Differentiators:** Dual-platform CI, real device testing

- [ ] **PLAT-06**: Dual-platform CI (iOS + Android) to catch platform differences early
- [ ] **PLAT-07**: Real device testing infrastructure (not just simulators)

### Coverage & Quality Validation

**Table stakes:** 80% coverage achieved, test quality validated

- [ ] **QUAL-01**: Governance domain achieves 80% coverage (agent_governance_service.py, governance_cache.py, trigger_interceptor.py)
- [ ] **QUAL-02**: Security domain achieves 80% coverage (auth/, crypto/, validation/)
- [ ] **QUAL-03**: Episodic memory domain achieves 80% coverage (segmentation, retrieval, lifecycle, graduation)
- [ ] **QUAL-04**: Core backend achieves 80% coverage (backend/core/, backend/api/, backend/tools/)
- [ ] **QUAL-05**: Test suite executes in parallel with zero shared state
- [ ] **QUAL-06**: Test suite has zero flaky tests (3 consecutive runs with identical results)
- [ ] **QUAL-07**: Full test suite completes in <5 minutes

**Differentiators:** Quality gates, trending documentation

- [ ] **QUAL-08**: Assertion density quality gate enforced (70%+ assertion density)
- [ ] **QUAL-09**: Coverage trending setup tracks coverage.json over time
- [ ] **QUAL-10**: Comprehensive test documentation (TEST_STANDARDS.md, INVARIANTS.md)

### Documentation Updates

**Table stakes:** All documentation reflects v2.0 features

- [ ] **DOCS-01**: README.md updated with Community Skills and test coverage achievements
- [ ] **DOCS-02**: CANVAS_IMPLEMENTATION_COMPLETE.md updated with Phase 20-23 features
- [ ] **DOCS-03**: EPISODIC_MEMORY_IMPLEMENTATION.md updated with canvas/feedback integration
- [ ] **DOCS-04**: COMMUNITY_SKILLS.md verified for production status
- [ ] **DOCS-05**: AGENT_GRADUATION_GUIDE.md updated with latest criteria (including skill metrics)
- [ ] **DOCS-06**: INSTALLATION.md verified for Personal/Enterprise editions

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| E2E UI testing with Playwright/Cypress | Separate tooling needed, defer to v3.0 |
| Load testing and performance benchmarks | Performance tests beyond coverage, defer to v3.0 |
| Chaos engineering and resilience testing | Requires production infrastructure, defer to v3.0 |
| Visual regression testing with snapshot comparison | UI snapshot testing, defer to v3.0 |
| 100% code coverage goal | Diminishing returns, 80% critical paths is industry standard |

---

## Traceability

*Populated during roadmap creation*

| Requirement | Phase | Status |
|-------------|-------|--------|
| SKILLS-01 through SKILLS-14 | Phase 14 | Pending |
| TEST-01 through TEST-10 | Phase 10 | Pending |
| COV-01 through COV-10 | Phase 12 | Pending |
| AGENT-01 through AGENT-11 | Phase 17 | Pending |
| MEM-01 through MEM-17 | Phase 3 | Pending |
| PLAT-01 through PLAT-07 | Phase 4, 5 | Pending |
| QUAL-01 through QUAL-10 | Phase 5 | Pending |
| DOCS-01 through DOCS-06 | Phase 24 | Pending |

**Coverage:**
- v2.0 requirements: 73 total
- Mapped to phases: 73 (Phase 3, 10, 12, 14, 17, plus gap closures)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-18 for Milestone v2.0*
