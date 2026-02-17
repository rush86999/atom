# Roadmap: Atom 80% Test Coverage Initiative

**Created:** February 17, 2026
**Goal:** 80% test coverage across AI-related components
**Estimated:** 35-50 days
**Phases:** 11

---

## Phase Overview

| Phase | Name | Goal | Plans | Est. |
|-------|------|------|-------|------|
| 1 | Foundation & Infrastructure | Establish test infrastructure, baseline measurement, and quality standards | 2 | 1.5-2.5 days |
| 2 | Core Invariants | Property-based tests for governance, LLM, database, and security | 3 | 3-5 days |
| 3 | Memory Layer | Episodic memory coverage (segmentation, retrieval, lifecycle, graduation) | 2 | 3-4 days |
| 4 | Agent Layer | Agent governance, maturity routing, permissions, graduation, execution | 3 | 4-5 days |
| 5 | Social Layer | Social feed, PII redaction, communication, channels | 2 | 3-4 days |
| 6 | Skills Layer | Community skills parsing, adaptation, sandbox, registry, security | 3 | 4-5 days |
| 7 | Local Agent | Shell execution, directory permissions, command whitelist, security | 2 | 3-4 days |
| 8 | IM Layer | Webhook handling, governance routing, rate limiting, audit logging | 2 | 2-3 days |
| 9 | LLM Validation | Three-tier LLM testing (unit, integration, E2E) | 2 | 3-4 days |
| 10 | Chaos Engineering | Failure injection and resilience testing | 2 | 3-4 days |
| 11 | Gap Filling | Reach 80% coverage across all AI components | 3 | 5-7 days |

**Total:** 11 phases, 29 plans, 35-50 days estimated

---

## Phase 1: Foundation & Infrastructure

**Goal:** Establish test infrastructure, measure baseline coverage, and standardize testing practices

**Plans:**
- Plan 1-1: Baseline Coverage Measurement - Run coverage report, identify gaps, document baseline
- Plan 1-2: Test Infrastructure Standardization - Standardize fixtures, Hypothesis settings, test utilities

**Requirements:**
- AR-01: Baseline Coverage Measurement - Run coverage report to establish baseline, identify gaps in AI components
- AR-02: Test Infrastructure Standardization - Standardize fixtures, Hypothesis settings, test utilities for consistent testing

**Dependencies:** None (foundation phase)

**Estimated:** 1.5-2.5 days

**Deliverables:**
- [ ] Coverage report generated (HTML, JSON, terminal) showing baseline metrics
- [ ] Baseline coverage percentage documented by module
- [ ] Gaps identified in AI components (governance, LLM, memory, agents, social, skills, local agent, IM)
- [ ] Critical paths with <50% coverage flagged
- [ ] Uncovered lines in critical services catalogued
- [ ] `conftest.py` standardized with:
  - [ ] `db_session` fixture (temp file-based SQLite, per-test isolation)
  - [ ] `test_agent` fixtures (all maturity levels: STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
  - [ ] `mock_llm_response` fixture (deterministic outputs)
  - [ ] `mock_embedding_vectors` fixture (controlled similarity)
- [ ] `property_tests/conftest.py` with Hypothesis settings (max_examples=200 local, 50 CI)
- [ ] Test utilities (factories, helpers, assertion libraries)
- [ ] All tests use standardized fixtures (no ad-hoc setup)

**Success Criteria:**
- [ ] Coverage report generated with baseline metrics documented
- [ ] Gaps identified by module with critical paths flagged
- [ ] Standardized fixtures in place (db_session, test_agent, mock_llm_response, mock_embedding_vectors)
- [ ] Hypothesis settings configured (max_examples=200 local, 50 CI)
- [ ] Test utilities available (factories, helpers, assertion libraries)
- [ ] All new tests use standardized fixtures

**Pitfalls Addressed:**
- Coverage churn under timeline pressure (Pitfall #1) - Quality standards established before measuring coverage
- Test data fragility (Pitfall #7) - Standardized fixtures prevent hardcoded data

---

## Phase 2: Core Invariants

**Goal:** Property-based tests for governance, LLM, database, and security invariants

**Plans:**
- Plan 2-1: Governance Invariants - Agent maturity, permissions, confidence scores, cache performance
- Plan 2-2: LLM Invariants - Multi-provider routing, token counting, cost calculation, streaming
- Plan 2-3: Database & Security Invariants - Atomicity, constraints, fuzz testing, OWASP Top 10

**Requirements:**
- AR-03: Core Invariants Testing - Property-based tests for governance, LLM, database invariants
- AR-04: LLM Integration Coverage - Test multi-provider routing, streaming, token management, error handling
- AR-14: Security Test Suite - Fuzz testing, OWASP Top 10, dependency scanning (integrated into Phase 2)

**Dependencies:** Phase 1 (test infrastructure)

**Estimated:** 3-5 days

**Deliverables:**
- [ ] **Governance invariants** (property_tests/governance/):
  - [ ] Confidence score bounds [0.0, 1.0]
  - [ ] Maturity routing (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
  - [ ] Action complexity enforcement (1-4 matrix)
  - [ ] Governance cache performance (<10ms lookups)
  - [ ] Maturity checks (STUDENT blocked from complexity 4)
- [ ] **LLM invariants** (property_tests/llm/):
  - [ ] Provider fallback (OpenAI → Anthropic → DeepSeek → Gemini)
  - [ ] Token counting accuracy (±5% of actual)
  - [ ] Cost calculation (no negative costs, realistic per-token rates)
  - [ ] Streaming response completion (all tokens delivered)
- [ ] **Database invariants** (property_tests/database/):
  - [ ] Atomicity (transactions all-or-nothing)
  - [ ] Foreign key constraints (no orphaned records)
  - [ ] Unique constraints (no duplicate agent IDs, episode IDs)
  - [ ] Cascade deletions (agent deletion → executions deleted)
- [ ] **Security tests** (integrated):
  - [ ] Fuzz testing for governance inputs
  - [ ] OWASP Top 10 coverage (injection, broken authentication, XSS, CSRF, security misconfiguration)
  - [ ] Dependency scanning (pip-audit, bandit, safety check)
- [ ] Multi-provider routing tests (provider selection, fallback, rate limits, timeouts)
- [ ] Streaming response tests (token-by-token streaming, completion, interruption)
- [ ] Token management tests (counting accuracy, cost tracking, limits enforced)
- [ ] Error handling tests (API errors, invalid requests, retry logic)

**Success Criteria:**
- [ ] All governance invariants tested with documented bug findings
- [ ] All LLM invariants tested with streaming validation
- [ ] All database invariants tested with ACID properties verified
- [ ] Security tests cover fuzz testing and OWASP Top 10
- [ ] Dependency scanning integrated in CI (pip-audit, bandit, safety check)
- [ ] Property tests have documented invariants in docstrings

**Pitfalls Addressed:**
- Weak property tests (Pitfall #2) - Invariants identified before implementation
- Fuzzy testing without oracle (Pitfall #6) - Error contracts defined before fuzzing

---

## Phase 3: Memory Layer

**Goal:** Episodic memory coverage (segmentation, retrieval, lifecycle, graduation integration)

**Plans:**
- Plan 3-1: Episode Segmentation & Retrieval - Test time-gap segmentation, topic change, temporal/semantic/sequential retrieval
- Plan 3-2: Episode Lifecycle & Graduation - Test decay, consolidation, archival, graduation integration

**Requirements:**
- AR-06: Episodic Memory Coverage - Test segmentation, retrieval, lifecycle, graduation integration
- AR-12: Property-Based Testing Expansion (Memory System) - Episode retrieval never returns duplicates, temporal queries sorted, semantic results ranked

**Dependencies:** Phase 1 (test infrastructure), Phase 2 (database invariants)

**Estimated:** 3-4 days

**Deliverables:**
- [ ] **Segmentation tests**:
  - [ ] Time-gap segmentation (>2 hours → new episode)
  - [ ] Topic change detection (embedding similarity <0.7 → new episode)
  - [ ] Task completion detection (agent success → episode closed)
- [ ] **Retrieval tests**:
  - [ ] Temporal retrieval (sorted by time, paginated)
  - [ ] Semantic retrieval (vector similarity, ranked by relevance)
  - [ ] Sequential retrieval (full episode with context)
  - [ ] Contextual retrieval (hybrid query: temporal + semantic)
  - [ ] No duplicates in retrieval results
  - [ ] Retrieval performance (<100ms for semantic search)
- [ ] **Lifecycle tests**:
  - [ ] Episode decay (old episodes access frequency ↓)
  - [ ] Consolidation (merge similar episodes)
  - [ ] Archival (cold storage to LanceDB)
- [ ] **Graduation integration tests**:
  - [ ] Episodes used in graduation exam (constitutional compliance validation)
  - [ ] Feedback-linked episodes (positive feedback boosts retrieval)
  - [ ] Canvas-aware episodes (track canvas interactions)
- [ ] **Property tests** (AR-12):
  - [ ] Episode retrieval never returns duplicates
  - [ ] Temporal queries always sorted by time
  - [ ] Semantic results ranked by similarity (descending)

**Success Criteria:**
- [ ] All segmentation triggers tested (time gap, topic change, task completion)
- [ ] All retrieval modes tested (temporal, semantic, sequential, contextual)
- [ ] All lifecycle operations tested (decay, consolidation, archival)
- [ ] Graduation integration tested (constitutional compliance, feedback-linked, canvas-aware)
- [ ] Property tests verify memory invariants (no duplicates, sorted, ranked)
- [ ] Retrieval performance <100ms for semantic search

**Pitfalls Addressed:**
- Integration test state contamination (Pitfall #3) - Transaction rollback pattern
- Async test race conditions (Pitfall #4) - Explicit async coordination

---

## Phase 4: Agent Layer

**Goal:** Agent governance, maturity routing, permissions, graduation, execution, and coordination

**Plans:**
- Plan 4-1: Agent Governance & Maturity Routing - Test all maturity levels, action complexity matrix, permission checks
- Plan 4-2: Agent Graduation & Context Resolution - Test readiness scoring, graduation exam, context resolution
- Plan 4-3: Agent Execution & Coordination - Test agent execution orchestration, agent-to-agent communication

**Requirements:**
- AR-05: Agent Governance Coverage - Test maturity routing, permissions, graduation, context resolution
- AR-12: Property-Based Testing Expansion (Agent System) - Graduation readiness score in [0.0, 1.0], maturity transitions monotonic, intervention rate decreases

**Dependencies:** Phase 2 (core invariants), Phase 3 (memory layer - for graduation exam)

**Estimated:** 4-5 days

**Deliverables:**
- [ ] **Maturity routing tests**:
  - [ ] All 4 maturity levels tested (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
  - [ ] STUDENT agents blocked from complexity 3-4 actions
  - [ ] INTERN agents require proposals for complexity 2-4 actions
  - [ ] SUPERVISED agents execute under real-time monitoring
  - [ ] AUTONOMOUS agents have full access
- [ ] **Permissions tests**:
  - [ ] Action complexity matrix enforced (1-4)
  - [ ] Capability checks (canvas, browser, device, local agent)
  - [ ] Permission caching (<1ms lookups)
- [ ] **Graduation framework tests**:
  - [ ] Readiness score calculation (episodes, interventions, constitutional compliance)
  - [ ] Graduation exam validation (100% constitutional compliance required)
  - [ ] Level transitions (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
- [ ] **Context resolution tests**:
  - [ ] Agent context resolution with fallback chain
  - [ ] Governance cache hits (>95% hit rate)
- [ ] **Agent execution tests**:
  - [ ] Agent execution orchestration
  - [ ] Error handling and recovery
  - [ ] Audit logging
- [ ] **Agent coordination tests**:
  - [ ] Agent-to-agent messaging
  - [ ] Event bus communication
- [ ] **Property tests** (AR-12):
  - [ ] Graduation readiness score in [0.0, 1.0]
  - [ ] Maturity transitions are monotonic (no downgrades)
  - [ ] Intervention rate decreases with maturity

**Success Criteria:**
- [ ] All maturity levels tested with all action complexity combinations
- [ ] All capability checks tested (canvas, browser, device, local agent)
- [ ] Graduation framework tested (readiness scoring, exam, transitions)
- [ ] Context resolution tested with fallback chain and cache hits
- [ ] Agent execution tested with error handling and audit logging
- [ ] Agent coordination tested with event bus communication
- [ ] Property tests verify agent invariants

**Pitfalls Addressed:**
- Integration test state contamination (Pitfall #3) - Transaction rollback pattern
- Async test race conditions (Pitfall #4) - Explicit async coordination

---

## Phase 5: Social Layer

**Goal:** Social feed, PII redaction, communication, and channels

**Plans:**
- Plan 5-1: Post Generation & PII Redaction - Test GPT-4.1 mini NLG, Microsoft Presidio integration
- Plan 5-2: Communication & Feed Management - Test agent-to-agent messaging, Redis pub/sub, feed generation

**Requirements:**
- AR-07: Social Layer Coverage - Test post generation, PII redaction, communication, channels
- AR-12: Property-Based Testing Expansion (Social Layer) - Feed pagination never returns duplicates, message ordering FIFO, PII redaction never leaks

**Dependencies:** Phase 4 (agent layer), Phase 3 (memory layer)

**Estimated:** 3-4 days

**Deliverables:**
- [ ] **Post generation tests**:
  - [ ] GPT-4.1 mini NLG for posts (success rate >95%)
  - [ ] Post length limits (≤280 chars for microblog, ≤5000 for long-form)
  - [ ] Post formatting (markdown, mentions, hashtags)
- [ ] **PII redaction tests**:
  - [ ] Microsoft Presidio integration (email, phone, SSN, credit card)
  - [ ] Redaction accuracy (>95% PII detected)
  - [ ] False positive rate (<5% legitimate content redacted)
- [ ] **Communication tests**:
  - [ ] Agent-to-agent messaging (Redis pub/sub)
  - [ ] Message delivery (no lost messages)
  - [ ] Message ordering (FIFO per channel)
- [ ] **Feed management tests**:
  - [ ] Feed generation (chronological, algorithmic)
  - [ ] Feed pagination (no duplicates, ordered correctly)
  - [ ] Feed filtering (by agent, by topic, by time range)
- [ ] **Property tests** (AR-12):
  - [ ] Feed pagination never returns duplicates
  - [ ] Message ordering is FIFO per channel
  - [ ] PII redaction never leaks protected info

**Success Criteria:**
- [ ] Post generation tested with GPT-4.1 mini NLG (>95% success rate)
- [ ] PII redaction tested with Microsoft Presidio (>95% detection, <5% false positives)
- [ ] Communication tested with Redis pub/sub (no lost messages, FIFO ordering)
- [ ] Feed management tested (generation, pagination, filtering)
- [ ] Property tests verify social invariants

**Pitfalls Addressed:**
- Integration test state contamination (Pitfall #3) - Transaction rollback pattern
- Async test race conditions (Pitfall #4) - Explicit async coordination for Redis pub/sub

---

## Phase 6: Skills Layer

**Goal:** Community skills parsing, adaptation, sandbox, registry, and security

**Plans:**
- Plan 6-1: Skill Parsing & Adaptation - Test SKILL.md parsing, LangChain BaseTool wrapping
- Plan 6-2: Skill Sandbox & Security - Test Docker isolation, fuzz testing, security scanning
- Plan 6-3: Skill Registry & Execution - Test Untrusted → Active → Banned transitions, audit logging

**Requirements:**
- AR-08: Community Skills Coverage - Test parsing, adaptation, sandbox, registry, security scanning
- AR-12: Property-Based Testing Expansion (Skills) - SKILL.md parsing succeeds for valid YAML, sandboxed skills cannot access host, security scanner detects 90% of malicious patterns
- AR-14: Security Test Suite (Skills) - Fuzz testing for SKILL.md files, Docker escape attempts blocked, command injection prevention

**Dependencies:** Phase 4 (agent layer - for governance)

**Estimated:** 4-5 days

**Deliverables:**
- [ ] **Parsing tests**:
  - [ ] SKILL.md YAML frontmatter parsing (lenient, auto-fix)
  - [ ] Metadata extraction (name, version, author, category)
  - [ ] Prompt vs. Python skill detection (automatic)
- [ ] **Adaptation tests**:
  - [ ] LangChain BaseTool wrapping (for Python skills)
  - [ ] Prompt template rendering (for prompt skills)
  - [ ] Tool parameter validation (required vs. optional)
- [ ] **Sandbox isolation tests**:
  - [ ] Docker container isolation (no host access)
  - [ ] Resource limits (CPU, memory, timeout)
  - [ ] Network blocking (no external network)
  - [ ] Filesystem isolation (tmpfs only)
- [ ] **Registry workflow tests**:
  - [ ] Untrusted → Active → Banned transitions
  - [ ] LLM security scanning (malicious code detection)
  - [ ] Skill execution audit logging
- [ ] **Security tests**:
  - [ ] Fuzz testing for malicious SKILL.md files
  - [ ] Docker escape attempts blocked
  - [ ] Command injection prevention
- [ ] **Property tests** (AR-12):
  - [ ] SKILL.md parsing succeeds for valid YAML
  - [ ] Sandboxed skills cannot access host filesystem
  - [ ] Security scanner detects 90% of malicious patterns

**Success Criteria:**
- [ ] SKILL.md parsing tested with lenient YAML frontmatter
- [ ] Skill adaptation tested with LangChain BaseTool and prompt templates
- [ ] Sandbox isolation tested with Docker (no host access, resource limits, network blocking, filesystem isolation)
- [ ] Registry workflow tested (Untrusted → Active → Banned transitions)
- [ ] Security tests cover fuzzing, Docker escape, command injection
- [ ] Property tests verify skill invariants

**Pitfalls Addressed:**
- Security mistakes (PITFALLS.md) - Comprehensive security testing for untrusted code
- Integration test state contamination (Pitfall #3) - Container isolation prevents state sharing

---

## Phase 7: Local Agent

**Goal:** Shell execution, directory permissions, command whitelist, and security

**Plans:**
- Plan 7-1: Shell Execution & Command Whitelist - Test command injection prevention, argument sanitization, timeout enforcement
- Plan 7-2: Directory Permissions & Security - Test maturity-based access, path traversal prevention, fuzz testing

**Requirements:**
- AR-09: Local Agent Coverage - Test shell execution, directory permissions, command whitelist, security
- AR-12: Property-Based Testing Expansion (Local Agent) - Shell execution timeout enforced (≤5 min), command whitelist blocks 100% of dangerous commands, AUTONOMOUS gate enforcement
- AR-14: Security Test Suite (Local Agent) - Fuzz testing for shell inputs, host filesystem isolation, audit logging

**Dependencies:** Phase 4 (agent governance)

**Estimated:** 3-4 days

**Deliverables:**
- [ ] **Shell execution tests**:
  - [ ] Command injection prevention (sanitize shell inputs)
  - [ ] Argument sanitization (block ;, |, $(), backticks)
  - [ ] Subprocess execution with timeout (5-min max)
- [ ] **Directory permissions tests**:
  - [ ] Maturity-based access (AUTONOMOUS only for host mount)
  - [ ] Path traversal prevention (block ../../, absolute paths)
  - [ ] Permission checks (<1ms per check)
- [ ] **Command whitelist tests**:
  - [ ] Blocked dangerous commands (rm, dd, mkfs, chmod, chown)
  - [ ] AUTONOMOUS gate enforced (STUDENT/INTERN/SUPERVISED blocked)
  - [ ] Whitelist configuration (customizable per environment)
- [ ] **Security tests**:
  - [ ] Fuzz testing for shell inputs
  - [ ] Host filesystem isolation (containerized execution)
  - [ ] Audit logging (all shell commands logged)
- [ ] **Property tests** (AR-12):
  - [ ] Shell execution timeout enforced (≤5 min)
  - [ ] Command whitelist blocks 100% of dangerous commands
  - [ ] AUTONOMOUS gate enforcement (no bypasses)

**Success Criteria:**
- [ ] Shell execution tested with command injection prevention
- [ ] Directory permissions tested with maturity-based access and path traversal prevention
- [ ] Command whitelist tested with dangerous commands blocked and AUTONOMOUS gate
- [ ] Security tests cover fuzzing, filesystem isolation, audit logging
- [ ] Property tests verify local agent invariants

**Pitfalls Addressed:**
- Security mistakes (PITFALLS.md) - Comprehensive security testing for shell execution
- Integration test state contamination (Pitfall #3) - Container isolation prevents state sharing

---

## Phase 8: IM Layer

**Goal:** Webhook handling, governance routing, rate limiting, and audit logging

**Plans:**
- Plan 8-1: Webhook Handling - Test Telegram/WhatsApp signature verification, parsing, replay prevention
- Plan 8-2: Governance Routing & Rate Limiting - Test IM-triggered agent execution, rate limits, audit logging

**Requirements:**
- AR-10: IM Adapters Coverage - Test webhook handling, governance routing, rate limiting, audit logging

**Dependencies:** Phase 4 (agent governance)

**Estimated:** 2-3 days

**Deliverables:**
- [ ] **Webhook handling tests**:
  - [ ] Telegram webhook signature verification
  - [ ] WhatsApp business verification
  - [ ] Webhook replay prevention (idempotency keys)
  - [ ] Webhook parsing (extract message, user, metadata)
- [ ] **Governance routing tests**:
  - [ ] IM-triggered agent execution respects maturity levels
  - [ ] STUDENT agents blocked from IM-triggered actions
  - [ ] Rate-limited users routed to TRAINING
- [ ] **Rate limiting tests**:
  - [ ] Per-user rate limits (10 requests/min)
  - [ ] Per-channel rate limits (1000 requests/min)
  - [ ] Rate limit enforcement (429 responses, retry-after header)
- [ ] **Audit logging tests**:
  - [ ] All webhooks logged (timestamp, source, payload)
  - [ ] Agent execution logged (agent_id, action, result)
  - [ ] Governance decisions logged (allow/deny, reason)

**Success Criteria:**
- [ ] Webhook handling tested with signature verification and replay prevention
- [ ] Governance routing tested with maturity level enforcement
- [ ] Rate limiting tested with per-user and per-channel limits
- [ ] Audit logging tested for all webhook operations

**Pitfalls Addressed:**
- Integration test state contamination (Pitfall #3) - Transaction rollback pattern
- Async test race conditions (Pitfall #4) - Explicit async coordination for webhooks

---

## Phase 9: LLM Validation

**Goal:** Three-tier LLM testing (unit, integration, E2E)

**Plans:**
- Plan 9-1: LLM Unit & Integration Tests - Mocked responses, real LLM at temperature=0, DeepEval metrics
- Plan 9-2: LLM E2E Tests - Real LLM at temperature=0.7, statistical assertions, golden dataset

**Requirements:**
- AR-11: Three-Tier LLM Testing Strategy - Unit (mocks) + Integration (real LLM at temperature=0) + E2E (statistical)

**Dependencies:** All previous phases (LLM integration must be working)

**Estimated:** 3-4 days

**Deliverables:**
- [ ] **Unit tests (70% of LLM tests)**:
  - [ ] Mocked LLM responses (deterministic, fast)
  - [ ] Test prompt construction, error handling, retry logic
  - [ ] No real API calls
- [ ] **Integration tests (20% of LLM tests)**:
  - [ ] Real LLM calls with `temperature=0` (deterministic-ish)
  - [ ] DeepEval metrics (faithfulness, relevance, hallucination)
  - [ ] Semantic similarity assertions (>0.85 for known queries)
- [ ] **E2E tests (10% of LLM tests)**:
  - [ ] Real LLM calls with `temperature=0.7` (probabilistic)
  - [ ] Statistical assertions (pass rate >95% for 100 samples)
  - [ ] Golden dataset of expected responses

**Success Criteria:**
- [ ] Unit tests cover prompt construction, error handling, retry logic with mocked responses
- [ ] Integration tests use real LLM at temperature=0 with DeepEval metrics
- [ ] E2E tests use real LLM at temperature=0.7 with statistical assertions
- [ ] Three-tier distribution: 70% unit, 20% integration, 10% E2E

**Pitfalls Addressed:**
- Async test race conditions (Pitfall #4) - Explicit async coordination for LLM calls

---

## Phase 10: Chaos Engineering

**Goal:** Test system resilience under failure conditions

**Plans:**
- Plan 10-1: LLM & Database Failures - Test provider timeouts, connection loss, query timeouts, deadlocks
- Plan 10-2: Redis & Network Failures - Test pub/sub failures, cache misses, network partitions

**Requirements:**
- AR-13: Chaos Engineering Tests - Test system resilience under failure conditions

**Dependencies:** All previous phases (system must be working)

**Estimated:** 3-4 days

**Deliverables:**
- [ ] **LLM provider failures**:
  - [ ] OpenAI timeout → fallback to Anthropic
  - [ ] All providers down → graceful degradation
  - [ ] Rate limit handling (exponential backoff)
- [ ] **Database failures**:
  - [ ] Connection loss → retry → succeed
  - [ ] Query timeout → fallback to cache
  - [ ] Deadlock detection → retry with backoff
- [ ] **Redis failures**:
  - [ ] Pub/sub failure → in-memory fallback
  - [ ] Cache miss → cache repopulation
- [ ] **Network partitions**:
  - [ ] Partial outage (50% nodes down) → degraded service
  - [ ] Total outage → cached responses only

**Success Criteria:**
- [ ] LLM provider failures tested with fallback and graceful degradation
- [ ] Database failures tested with retry and fallback to cache
- [ ] Redis failures tested with in-memory fallback and cache repopulation
- [ ] Network partitions tested with degraded service and cached responses

**Pitfalls Addressed:**
- Integration test state contamination (Pitfall #3) - Failure isolation
- Async test race conditions (Pitfall #4) - Explicit async coordination for failure scenarios

---

## Phase 11: Gap Filling

**Goal:** Reach 80% coverage across all AI components

**Plans:**
- Plan 11-1: Coverage Analysis & Prioritization - Identify remaining gaps, prioritize critical paths
- Plan 11-2: Targeted Test Development - Fill coverage gaps in high-priority areas
- Plan 11-3: Final Validation & Documentation - Verify 80% coverage, update documentation

**Requirements:**
- AR-15: 80% Coverage Target Achievement - Reach 80% coverage with focus on critical paths

**Dependencies:** All previous phases

**Estimated:** 5-7 days

**Deliverables:**
- [ ] **Coverage analysis**:
  - [ ] Overall coverage: ≥80% line coverage
  - [ ] Per-module coverage targets:
    - [ ] Core services (governance, LLM, memory, agents): ≥90%
    - [ ] Tools (browser, device, canvas): ≥80%
    - [ ] API routes: ≥70%
    - [ ] Models/DTOs: ≥50%
    - [ ] Security modules (auth, local agent, skills): 100%
- [ ] **Critical path coverage**:
  - [ ] Agent execution flow: 100%
  - [ ] LLM integration flow: 100%
  - [ ] Governance checks: 100%
  - [ ] Memory operations: 100%
- [ ] **Manual audit**:
  - [ ] Review htmlcov/ for red lines in critical services
  - [ ] Write targeted tests for uncovered critical paths
  - [ ] Document acceptable gaps (e.g., error handlers for edge cases)

**Success Criteria:**
- [ ] Overall coverage ≥80% line coverage
- [ ] Per-module coverage targets met (core services ≥90%, tools ≥80%, API routes ≥70%, models/DTOs ≥50%, security modules 100%)
- [ ] Critical paths 100% covered (agent execution, LLM integration, governance checks, memory operations)
- [ ] Manual audit completed with documented gaps

**Pitfalls Addressed:**
- Coverage churn under timeline pressure (Pitfall #1) - Quality over quantity
- Performance traps (PITFALLS.md) - Test suite <30 minutes with pytest-xdist

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Coverage churn under timeline pressure** | High | High | Phase 1 establishes quality gates. Test review focuses on "what bugs does this catch?" |
| **Weak property tests** | Medium | High | Phase 2 requires invariant identification before implementation. Documented bug findings required. |
| **Integration test state contamination** | High | High | Phase 1 enforces standardized fixtures with transaction rollback. Parallel execution from day one. |
| **Async test race conditions** | Medium | High | Phase 1 configures pytest-asyncio with auto-mode. Explicit async coordination required. |
| **Test data fragility** | Medium | Medium | Phase 1 implements standardized fixtures. No hardcoded IDs. |
| **DeepEval integration uncertainty** | Medium | Medium | Open Question OQ-1: Research DeepEval or build custom evaluators. |
| **Docker-in-Docker CI challenges** | Medium | Medium | Open Question OQ-3: Validate Docker-in-Docker in GitHub Actions. |
| **Test execution time exceeds 30 minutes** | Medium | Medium | Open Question OQ-5: Use pytest-xdist for parallelization. |

---

## Definition of Done

A phase is **DONE** when:
- [ ] All plans complete
- [ ] All requirements met
- [ ] All tests passing
- [ ] Coverage increased
- [ ] Documentation updated
- [ ] Zero flaky tests
- [ ] Parallel execution verified

The initiative is **COMPLETE** when:
- [ ] 80% coverage achieved across all AI components
- [ ] All 15 requirements met
- [ ] Critical paths 100% covered (governance, security, episodic memory, LLM integration)
- [ ] Test suite stable (<1% flaky)
- [ ] Security tests passing (fuzzing, OWASP Top 10, dependency scanning)
- [ ] Test suite executes in <30 minutes (pytest-xdist parallelization)
- [ ] Tests are readable, documented, and follow patterns
- [ ] Documentation updated (test suite README, coverage guide)

---

## Execution Guidelines

### Phase Dependencies
- **Phase 1** must complete first (foundation for all other phases)
- **Phase 2** must complete before Phase 3-10 (property test mindset)
- **Phase 3-10** can execute in parallel after Phase 2 (independent domains)
- **Phase 11** must complete last (gap filling requires all other phases)

### Quality Standards
- **Assertion density:** >1 assertion per 20 lines of test code
- **Critical path coverage:** 100% for governance, security, episodic memory, LLM integration
- **Overall coverage:** 80% across all AI components
- **Test execution time:** <30 minutes with pytest-xdist parallelization
- **Flaky test tolerance:** 0% (zero tolerance for flakiness)

### Test Review Criteria
When reviewing tests, ask:
1. **What bugs does this test catch?** (Every test must have a clear purpose)
2. **Is this testing behavior or implementation?** (Test public APIs, not private methods)
3. **Would this test catch a real bug?** (No trivial assertions like `assert True`)
4. **Is this test isolated?** (No shared state, uses standardized fixtures)
5. **Is this test reproducible?** (Passes with parallel execution, no timing dependencies)

### Coverage Prioritization
1. **P0 (Critical):** Governance, security, episodic memory, LLM integration, local agent (100% coverage)
2. **P1 (High):** Agent system, community skills, social layer, three-tier LLM testing (≥90% coverage)
3. **P2 (Medium):** IM adapters, tools, API routes (≥80% coverage)
4. **P3 (Low):** Models/DTOs, utilities (≥50% coverage)

### Timeline Management
- **Week 1:** Phase 1-2 (Foundation + Core Invariants)
- **Week 2:** Phase 3-6 (Memory, Agent, Social, Skills layers)
- **Week 3:** Phase 7-10 (Local Agent, IM, LLM, Chaos)
- **Week 4:** Phase 11 (Gap Filling + Final Validation)

**Flexibility:** If a phase takes longer than estimated, adjust timeline. Quality matters more than speed.

---

## Open Questions

1. **DeepEval Integration** (AR-11): Should we use DeepEval or build custom evaluators? DeepEval documentation was unavailable during research (LOW confidence).
2. **RAGAS for Retrieval** (AR-06): Is RAGAS overkill for episodic memory? Custom invariants may be simpler.
3. **Docker-in-Docker CI** (AR-08): Can we run Docker-in-Docker in GitHub Actions for sandbox testing? Security implications?
4. **Coverage Thresholds** (AR-15): Are per-module targets realistic? Should we use diff-cover for new code only?
5. **Test Execution Time**: Will 701+ tests with 80% coverage exceed 30-minute target? Need pytest-xdist.

---

*Roadmap created: February 17, 2026*
*Based on requirements: AR-01 through AR-15*
*Estimated: 35-50 days, 11 phases, 29 plans*
*Next: Begin Phase 1 (Foundation & Infrastructure)*
