# Requirements: Atom 80% Test Coverage Initiative

**Status:** Draft
**Created:** February 17, 2026
**Goal:** Achieve 80% test coverage across AI-related components

---

## Project Context

**What We're Building:**
Comprehensive test suite for Atom's AI-powered business automation platform, focusing on multi-agent governance, LLM integration, episodic memory, social layer, community skills, local agent, and IM adapters.

**Core Value:**
Critical AI system paths are thoroughly tested and validated before production deployment.

**Current State:**
- 701 test files exist (large but incomplete coverage)
- pytest, pytest-asyncio, pytest-cov, Hypothesis already in use
- Test infrastructure in place (conftest.py, fixtures)
- Coverage baseline unknown (to be measured in Phase 1)

**Constraints:**
- Quality Standard: 80% coverage target (defensible quality bar)
- Focus Area: AI-related components (highest risk and complexity)
- Test Types: Unit (40%), Integration (30%), Property-based (30%)
- Timeline: Flexible - quality matters more than speed
- Priority: Critical paths first (governance, security, AI operations)

---

## Validated Requirements

These are locked and implementation has begun or is complete.

### VR-01: Test Infrastructure Exists
**Status:** ✅ Complete
**Description:** pytest, pytest-asyncio, pytest-cov, Hypothesis configured
**Evidence:** 701 test files, conftest.py with fixtures, property tests in place
**Acceptance Criteria:**
- [x] pytest configured with async support
- [x] pytest-cov generates coverage reports
- [x] Hypothesis property-based testing configured
- [x] Test fixtures available (db_session, test_agent, etc.)

### VR-02: Property-Based Testing Framework
**Status:** ✅ Complete
**Description:** Hypothesis for testing system invariants
**Evidence:** 28 property-based tests mentioned in project context
**Acceptance Criteria:**
- [x] Hypothesis installed and configured
- [x] Property tests for governance invariants
- [x] Property tests for LLM handler invariants
- [x] Property tests for episode segmentation

### VR-03: OpenClaw Integration Features Delivered
**Status:** ✅ Complete
**Description:** 5 major features implemented, need test coverage
**Evidence:** TEST_COVERAGE_PROJECT.md lists delivered features
**Features Delivered:**
- [x] IM adapters (Telegram/WhatsApp)
- [x] Local agent (God Mode)
- [x] Social layer (Moltbook)
- [x] Simplified installer
- [x] Community skills integration

---

## Active Requirements

These are in scope for this initiative. Implementation pending.

### AR-01: Baseline Coverage Measurement
**Priority:** P0 (blocks everything else)
**Phase:** 1 - Foundation
**Description:** Run coverage report to establish baseline, identify gaps in AI components
**Acceptance Criteria:**
- [ ] Coverage report generated: `pytest --cov=core --cov=api --cov=tools --cov-report=html`
- [ ] Baseline coverage percentage documented
- [ ] Gaps identified by module (governance, LLM, memory, agents, social, skills, local agent, IM)
- [ ] Critical paths with <50% coverage flagged
- [ ] Uncovered lines in critical services catalogued
**Rationale:** Can't improve what you don't measure. Baseline required for tracking progress.
**Dependencies:** None
**Estimated:** 0.5 day

### AR-02: Test Infrastructure Standardization
**Priority:** P0 (blocks all testing)
**Phase:** 1 - Foundation
**Description:** Standardize fixtures, Hypothesis settings, test utilities for consistent testing
**Acceptance Criteria:**
- [ ] `conftest.py` standardized with:
  - [ ] `db_session` fixture (temp file-based SQLite, per-test isolation)
  - [ ] `test_agent` fixtures (all maturity levels: STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
  - [ ] `mock_llm_response` fixture (deterministic outputs)
  - [ ] `mock_embedding_vectors` fixture (controlled similarity)
- [ ] `property_tests/conftest.py` with Hypothesis settings (max_examples=200 local, 50 CI)
- [ ] Test utilities (factories, helpers, assertion libraries)
- [ ] All tests use standardized fixtures (no ad-hoc setup)
**Rationale:** Consistent test infrastructure prevents flaky tests and ensures maintainability.
**Dependencies:** None
**Estimated:** 1-2 days

### AR-03: Core Invariants Testing
**Priority:** P0 (safety-critical)
**Phase:** 2 - Core Invariants
**Description:** Property-based tests for governance, LLM, database invariants
**Acceptance Criteria:**
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
**Rationale:** Governance, LLM routing, and database are safety-critical. Invariants must hold.
**Dependencies:** AR-02 (test infrastructure)
**Estimated:** 3-5 days

### AR-04: LLM Integration Coverage
**Priority:** P0 (core AI feature)
**Phase:** 2 - Core Invariants
**Description:** Test multi-provider routing, streaming, token management, error handling
**Acceptance Criteria:**
- [ ] **Multi-provider routing**:
  - [ ] Provider selection based on cost/latency/quality
  - [ ] Fallback on provider failure (OpenAI down → Anthropic)
  - [ ] Rate limit handling (retry with exponential backoff)
  - [ ] Timeout handling (fallback to next provider)
- [ ] **Streaming responses**:
  - [ ] Token-by-token streaming via WebSocket
  - [ ] Stream completion (all tokens delivered)
  - [ ] Stream interruption (client disconnect handled)
- [ ] **Token management**:
  - [ ] Token counting accuracy (±5%)
  - [ ] Cost tracking (total cost per agent, per day)
  - [ ] Token limits enforced (OOM protection)
- [ ] **Error handling**:
  - [ ] API errors logged and handled gracefully
  - [ ] Invalid requests rejected with clear error messages
  - [ ] Retry logic for transient failures
**Rationale:** LLM integration is core to Atom's AI capabilities. Must be reliable.
**Dependencies:** AR-02 (test infrastructure), AR-03 (LLM invariants)
**Estimated:** 3-5 days (combined with AR-03)

### AR-05: Agent Governance Coverage
**Priority:** P0 (safety-critical)
**Phase:** 5 - Agent Layer
**Description:** Test maturity routing, permissions, graduation, context resolution
**Acceptance Criteria:**
- [ ] **Maturity routing**:
  - [ ] All 4 maturity levels tested (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
  - [ ] STUDENT agents blocked from complexity 3-4 actions
  - [ ] INTERN agents require proposals for complexity 2-4 actions
  - [ ] SUPERVISED agents execute under real-time monitoring
  - [ ] AUTONOMOUS agents have full access
- [ ] **Permissions**:
  - [ ] Action complexity matrix enforced (1-4)
  - [ ] Capability checks (canvas, browser, device, local agent)
  - [ ] Permission caching (<1ms lookups)
- [ ] **Graduation framework**:
  - [ ] Readiness score calculation (episodes, interventions, constitutional compliance)
  - [ ] Graduation exam validation (100% constitutional compliance required)
  - [ ] Level transitions (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
- [ ] **Context resolution**:
  - [ ] Agent context resolution with fallback chain
  - [ ] Governance cache hits (>95% hit rate)
**Rationale:** Agent governance is Atom's key differentiator. Must be thoroughly tested.
**Dependencies:** AR-03 (core invariants), AR-06 (memory layer - for graduation exam)
**Estimated:** 4-5 days

### AR-06: Episodic Memory Coverage
**Priority:** P1 (core feature)
**Phase:** 3 - Memory Layer
**Description:** Test segmentation, retrieval, lifecycle, graduation integration
**Acceptance Criteria:**
- [ ] **Segmentation**:
  - [ ] Time-gap segmentation (>2 hours → new episode)
  - [ ] Topic change detection (embedding similarity <0.7 → new episode)
  - [ ] Task completion detection (agent success → episode closed)
- [ ] **Retrieval**:
  - [ ] Temporal retrieval (sorted by time, paginated)
  - [ ] Semantic retrieval (vector similarity, ranked by relevance)
  - [ ] Sequential retrieval (full episode with context)
  - [ ] Contextual retrieval (hybrid query: temporal + semantic)
  - [ ] No duplicates in retrieval results
  - [ ] Retrieval performance (<100ms for semantic search)
- [ ] **Lifecycle**:
  - [ ] Episode decay (old episodes access frequency ↓)
  - [ ] Consolidation (merge similar episodes)
  - [ ] Archival (cold storage to LanceDB)
- [ ] **Graduation integration**:
  - [ ] Episodes used in graduation exam (constitutional compliance validation)
  - [ ] Feedback-linked episodes (positive feedback boosts retrieval)
  - [ ] Canvas-aware episodes (track canvas interactions)
**Rationale:** Episodic memory enables agent learning. Must be reliable and performant.
**Dependencies:** AR-03 (database invariants)
**Estimated:** 3-4 days

### AR-07: Social Layer Coverage
**Priority:** P2 (important feature)
**Phase:** 6 - Social Layer
**Description:** Test post generation, PII redaction, communication, channels
**Acceptance Criteria:**
- [ ] **Post generation**:
  - [ ] GPT-4.1 mini NLG for posts (success rate >95%)
  - [ ] Post length limits (≤280 chars for microblog, ≤5000 for long-form)
  - [ ] Post formatting (markdown, mentions, hashtags)
- [ ] **PII redaction**:
  - [ ] Microsoft Presidio integration (email, phone, SSN, credit card)
  - [ ] Redaction accuracy (>95% PII detected)
  - [ ] False positive rate (<5% legitimate content redacted)
- [ ] **Communication**:
  - [ ] Agent-to-agent messaging (Redis pub/sub)
  - [ ] Message delivery (no lost messages)
  - [ ] Message ordering (FIFO per channel)
- [ ] **Feed management**:
  - [ ] Feed generation (chronological, algorithmic)
  - [ ] Feed pagination (no duplicates, ordered correctly)
  - [ ] Feed filtering (by agent, by topic, by time range)
**Rationale:** Social layer enables multi-agent coordination. Important but not safety-critical.
**Dependencies:** AR-05 (agent layer), AR-06 (memory layer)
**Estimated:** 3-4 days

### AR-08: Community Skills Coverage
**Priority:** P1 (security-critical)
**Phase:** 7 - Skills Layer
**Phase:** 6 - Skills Layer
**Description:** Test parsing, adaptation, sandbox, registry, security scanning
**Acceptance Criteria:**
- [ ] **Parsing**:
  - [ ] SKILL.md YAML frontmatter parsing (lenient, auto-fix)
  - [ ] Metadata extraction (name, version, author, category)
  - [ ] Prompt vs. Python skill detection (automatic)
- [ ] **Adaptation**:
  - [ ] LangChain BaseTool wrapping (for Python skills)
  - [ ] Prompt template rendering (for prompt skills)
  - [ ] Tool parameter validation (required vs. optional)
- [ ] **Sandbox isolation**:
  - [ ] Docker container isolation (no host access)
  - [ ] Resource limits (CPU, memory, timeout)
  - [ ] Network blocking (no external network)
  - [ ] Filesystem isolation (tmpfs only)
- [ ] **Registry workflow**:
  - [ ] Untrusted → Active → Banned transitions
  - [ ] LLM security scanning (malicious code detection)
  - [ ] Skill execution audit logging
- [ ] **Security**:
  - [ ] Fuzz testing for malicious SKILL.md files
  - [ ] Docker escape attempts blocked
  - [ ] Command injection prevention
**Rationale:** Community skills execute untrusted code. Security-critical.
**Dependencies:** AR-05 (agent layer - for governance)
**Estimated:** 4-5 days

### AR-09: Local Agent Coverage
**Priority:** P0 (security-critical)
**Phase:** 8 - Local Agent
**Description:** Test shell execution, directory permissions, command whitelist, security
**Acceptance Criteria:**
- [ ] **Shell execution**:
  - [ ] Command injection prevention (sanitize shell inputs)
  - [ ] Argument sanitization (block ;, |, $(), backticks)
  - [ ] Subprocess execution with timeout (5-min max)
- [ ] **Directory permissions**:
  - [ ] Maturity-based access (AUTONOMOUS only for host mount)
  - [ ] Path traversal prevention (block ../../, absolute paths)
  - [ ] Permission checks (<1ms per check)
- [ ] **Command whitelist**:
  - [ ] Blocked dangerous commands (rm, dd, mkfs, chmod, chown)
  - [ ] AUTONOMOUS gate enforced (STUDENT/INTERN/SUPERVISED blocked)
  - [ ] Whitelist configuration (customizable per environment)
- [ ] **Security**:
  - [ ] Fuzz testing for shell inputs
  - [ ] Host filesystem isolation (containerized execution)
  - [ ] Audit logging (all shell commands logged)
**Rationale:** Local agent can execute arbitrary shell commands. Security-critical.
**Dependencies:** AR-05 (agent governance)
**Estimated:** 3-4 days

### AR-10: IM Adapters Coverage
**Priority:** P2 (integration feature)
**Phase:** 9 - IM Layer
**Description:** Test webhook handling, governance routing, rate limiting, audit logging
**Acceptance Criteria:**
- [ ] **Webhook handling**:
  - [ ] Telegram webhook signature verification
  - [ ] WhatsApp business verification
  - [ ] Webhook replay prevention (idempotency keys)
  - [ ] Webhook parsing (extract message, user, metadata)
- [ ] **Governance routing**:
  - [ ] IM-triggered agent execution respects maturity levels
  - [ ] STUDENT agents blocked from IM-triggered actions
  - [ ] Rate-limited users routed to TRAINING
- [ ] **Rate limiting**:
  - [ ] Per-user rate limits (10 requests/min)
  - [ ] Per-channel rate limits (1000 requests/min)
  - [ ] Rate limit enforcement (429 responses, retry-after header)
- [ ] **Audit logging**:
  - [ ] All webhooks logged (timestamp, source, payload)
  - [ ] Agent execution logged (agent_id, action, result)
  - [ ] Governance decisions logged (allow/deny, reason)
**Rationale:** IM adapters integrate external platforms. Important but not safety-critical.
**Dependencies:** AR-05 (agent governance)
**Estimated:** 2-3 days

### AR-11: Three-Tier LLM Testing Strategy
**Priority:** P1 (quality assurance)
**Phase:** 10 - LLM Validation
**Description:** Unit (mocks) + Integration (real LLM at temperature=0) + E2E (statistical)
**Acceptance Criteria:**
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
**Rationale:** Three-tier strategy balances speed (unit), realism (integration), and coverage (E2E).
**Dependencies:** All previous phases (LLM integration must be working)
**Estimated:** 3-4 days

### AR-12: Property-Based Testing Expansion
**Priority:** P1 (invariant validation)
**Phase:** 2-11 (ongoing)
**Description:** Expand Hypothesis usage for system invariants beyond core
**Acceptance Criteria:**
- [ ] **Memory system invariants** (Phase 3):
  - [ ] Episode retrieval never returns duplicates
  - [ ] Temporal queries always sorted by time
  - [ ] Semantic results ranked by similarity (descending)
- [ ] **Agent system invariants** (Phase 4):
  - [ ] Graduation readiness score in [0.0, 1.0]
  - [ ] Maturity transitions are monotonic (no downgrades)
  - [ ] Intervention rate decreases with maturity
- [ ] **Social layer invariants** (Phase 5):
  - [ ] Feed pagination never returns duplicates
  - [ ] Message ordering is FIFO per channel
  - [ ] PII redaction never leaks protected info
- [ ] **Skills invariants** (Phase 6):
  - [ ] SKILL.md parsing succeeds for valid YAML
  - [ ] Sandboxed skills cannot access host filesystem
  - [ ] Security scanner detects 90% of malicious patterns
- [ ] **Local agent invariants** (Phase 7):
  - [ ] Shell execution timeout enforced (≤5 min)
  - [ ] Command whitelist blocks 100% of dangerous commands
  - [ ] AUTONOMOUS gate enforcement (no bypasses)
**Rationale:** Property-based testing finds edge cases unit tests miss.
**Dependencies:** AR-03 (core invariants)
**Estimated:** Ongoing (integrated into each phase)

### AR-13: Chaos Engineering Tests
**Priority:** P3 (resilience verification)
**Phase:** 11 - Chaos Engineering
**Description:** Test system resilience under failure conditions
**Acceptance Criteria:**
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
**Rationale:** Chaos engineering validates resilience before production.
**Dependencies:** All previous phases (system must be working)
**Estimated:** 3-4 days

### AR-14: Security Test Suite
**Priority:** P0 (security-critical)
**Phase:** 2, 7, 8 (integrated)
**Description:** Fuzz testing, OWASP Top 10, dependency scanning
**Acceptance Criteria:**
- [ ] **Fuzz testing** (integrated into AR-08, AR-09):
  - [ ] Shell input fuzzing (random strings, special characters)
  - [ ] SKILL.md fuzzing (malicious YAML, code injection)
  - [ ] Webhook fuzzing (invalid payloads, signature spoofing)
- [ ] **OWASP Top 10 coverage**:
  - [ ] Injection (SQL, shell, command) - AR-09
  - [ ] Broken authentication - test auth routes
  - [ ] XSS in canvas - test canvas HTML sanitization
  - [ ] CSRF in API routes - test CSRF tokens
  - [ ] Security misconfiguration - test .env handling
- [ ] **Dependency scanning**:
  - [ ] `pip-audit` runs in CI (blocks PRs with vulns)
  - [ ] `bandit` runs in CI (security linting)
  - [ ] `safety check` runs in CI (known vulnerabilities)
**Rationale:** Security testing prevents vulnerabilities in production.
**Dependencies:** AR-03 (core invariants), AR-08 (skills), AR-09 (local agent)
**Estimated:** 2-3 days (integrated into phases)

### AR-15: 80% Coverage Target Achievement
**Priority:** P1 (goal)
**Phase:** 12 - Gap Filling
**Description:** Reach 80% coverage with focus on critical paths
**Acceptance Criteria:**
- [ ] **Overall coverage**: ≥80% line coverage
- [ ] **Per-module coverage targets**:
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
**Rationale:** 80% coverage is the goal, but critical paths need 100%.
**Dependencies:** All previous phases
**Estimated:** 5-7 days

### AR-16: Hybrid Retrieval Implementation
**Priority:** P1 (high value)
**Phase:** 4 - Hybrid Retrieval Enhancement
**Description:** Implement FastEmbed for initial indexing and Sentence Transformers for reranking to improve retrieval quality
**Acceptance Criteria:**
- [ ] **FastEmbed integration**:
  - [ ] FastEmbed model initialization (BAAI/bge-small-en-v1.5, 384-dim vectors)
  - [ ] Batch embedding generation for episode indexing
  - [ ] Fast vector similarity search (<20ms for 10k episodes)
  - [ ] Local-only execution (no API calls, privacy-preserving)
- [ ] **Sentence Transformers reranking**:
  - [ ] Sentence Transformers model integration (BAAI/bge-large-en-v1.5, 1024-dim vectors)
  - [ ] Top-k candidate selection (k=50-100 from FastEmbed results)
  - [ ] Reranking with higher-quality embeddings
  - [ ] Fallback to FastEmbed if reranking fails
- [ ] **Hybrid retrieval pipeline**:
  - [ ] FastEmbed coarse search (retrieve top-k candidates)
  - [ ] Sentence Transformers fine reranking (reorder top-k by relevance)
  - [ ] Unified API for semantic retrieval
  - [ ] Caching strategy (embeddings cached in LanceDB)
- [ ] **Performance targets**:
  - [ ] FastEmbed indexing: <10ms per episode
  - [ ] Coarse search: <20ms for top-100 candidates
  - [ ] Reranking: <150ms for top-50 candidates
  - [ ] Total latency: <200ms end-to-end
**Rationale:** FastEmbed provides fast, local embeddings for initial candidate retrieval. Sentence Transformers provides higher-quality embeddings for reranking top candidates, improving relevance while maintaining performance.
**Dependencies:** Phase 1 (test infrastructure), Phase 2 (database invariants), Phase 3 (memory layer)
**Estimated:** 3-5 days

### AR-17: Retrieval Quality Testing
**Priority:** P1 (high value)
**Phase:** 4 - Hybrid Retrieval Enhancement
**Description:** Property tests for retrieval accuracy, latency, and consistency with FastEmbed and Sentence Transformers
**Acceptance Criteria:**
- [ ] **Quality improvements**:
  - [ ] Recall@10: >90% (FastEmbed alone: ~80%)
  - [ ] NDCG@10: >0.85 (vs. ~0.70 for FastEmbed alone)
  - [ ] Relevance score improvement: >15% boost
- [ ] **Property tests** (AR-12):
  - [ ] Top-k candidates always include best matches (no false negatives)
  - [ ] Reranking never decreases relevance scores (monotonic improvement)
  - [ ] Fallback maintains FastEmbed baseline quality
  - [ ] Embedding consistency (same input → same embedding)
- [ ] **Performance tests**:
  - [ ] End-to-end latency <200ms for semantic retrieval
  - [ ] Coarse search <20ms for top-100 candidates
  - [ ] Reranking <150ms for top-50 candidates
- [ ] **Fallback tests**:
  - [ ] Sentence Transformers failure → FastEmbed fallback
  - [ ] Network timeout → cached embeddings
  - [ ] Model loading error → graceful degradation
**Rationale:** Property tests verify retrieval invariants and ensure quality improvements. Fallback testing ensures system resilience.
**Dependencies:** AR-16 (Hybrid Retrieval Implementation)
**Estimated:** 3-5 days (combined with AR-16)

### AR-18: CI/CD Pipeline Reliability
**Priority:** P0 (blocks deployment)
**Phase:** 13 - CI/CD Pipeline Fixes
**Description:** Ensure all CI/CD checks pass consistently and reliably
**Acceptance Criteria:**
- [ ] **CI stability**:
  - [ ] CI pass rate: 100% (all checks pass consistently)
  - [ ] 20 consecutive successful CI runs
  - [ ] Zero intermittent failures
- [ ] **Failure analysis**:
  - [ ] Identify all flaky tests (inconsistent failures)
  - [ ] Identify timeout issues (tests exceeding limits)
  - [ ] Identify resource constraints (memory, CPU, disk)
  - [ ] Baseline CI metrics documented
- [ ] **Root cause fixes**:
  - [ ] Fix test ordering dependencies (tests run independently)
  - [ ] Fix async race conditions (explicit coordination)
  - [ ] Fix resource leaks (connections, files, threads)
  - [ ] Add retries for transient failures (network, external services)
**Rationale:** CI/CD reliability is critical for deployment confidence. Failing checks block releases and erode trust in test suite.
**Dependencies:** All previous phases (complete test suite required)
**Estimated:** 3-5 days

### AR-19: Test Suite Determinism
**Priority:** P0 (blocks reliability)
**Phase:** 13 - CI/CD Pipeline Fixes
**Description:** Eliminate flaky tests and ensure reproducible results
**Acceptance Criteria:**
- [ ] **Flaky test elimination**:
  - [ ] Flaky test rate: 0% (verified over 10 runs per test)
  - [ ] All tests pass consistently across multiple runs
  - [ ] Test isolation enforced (no shared state between tests)
- [ ] **Determinism improvements**:
  - [ ] Remove time dependencies (use fixed timestamps, fake timers)
  - [ ] Remove randomness from tests (seed random number generators)
  - [ ] Explicit async coordination (no race conditions)
  - [ ] Fixed test execution order (shuffle to detect dependencies)
- [ ] **Verification**:
  - [ ] Run full test suite 10 times consecutively
  - [ ] All 10 runs produce identical results
  - [ ] Document remaining non-determinism (if any)
**Rationale:** Flaky tests erode trust in CI and make it impossible to detect real failures. Deterministic tests ensure reliable CI/CD.
**Dependencies:** AR-18 (CI stability analysis)
**Estimated:** 3-5 days (combined with AR-18)

### AR-20: Pipeline Performance
**Priority:** P1 (optimization)
**Phase:** 13 - CI/CD Pipeline Fixes
**Description:** Optimize CI/CD pipeline for fast feedback
**Acceptance Criteria:**
- [ ] **Execution time**:
  - [ ] Full test suite: <30 minutes (target: 20 minutes)
  - [ ] Unit tests: <5 minutes
  - [ ] Integration tests: <10 minutes
  - [ ] Property tests: <15 minutes
- [ ] **Parallelization**:
  - [ ] pytest-xdist configured (split tests across workers)
  - [ ] Test suite split into chunks (unit, integration, property)
  - [ ] Worker count optimized (based on CI resources)
- [ ] **Caching**:
  - [ ] Docker layer caching ( dependencies, images)
  - [ ] pip package caching (wheelhouse for compiled packages)
  - [ ] Test fixture caching (database snapshots, test data)
  - [ ] Dependency caching (GitHub Actions cache, proper cache keys)
- [ ] **Monitoring**:
  - [ ] CI metrics dashboard (pass rate, execution time trends)
  - [ ] Performance alerting (notify on slowdowns)
  - [ ] Bottleneck identification (track slow tests)
**Rationale:** Fast CI feedback enables rapid iteration. Slow pipelines delay releases and frustrate developers.
**Dependencies:** AR-18 (CI stability analysis)
**Estimated:** 3-5 days (combined with AR-18)

---

## Out of Scope

These are explicitly excluded from this initiative.

### OS-01: E2E UI Testing
**Reason:** Requires Playwright/Cypress, separate tooling, defer to v2
**Alternative:** API-level E2E tests for critical workflows

### OS-02: Load Testing
**Reason:** Performance and scalability testing, defer to v2
**Alternative:** Monitor test execution time, optimize slow tests

### OS-03: Chaos Engineering (Full)
**Reason:** Resilience testing is Phase 10 only, not full chaos engineering practice
**Scope:** Phase 10 covers basic failure injection, not comprehensive chaos engineering

### OS-04: Visual Regression
**Reason:** UI snapshot testing, defer to v2
**Alternative:** Manual UI testing for canvas components

### OS-05: Frontend Component Testing
**Reason:** React components tested separately (if at all)
**Scope:** Backend Python code only (core/, api/, tools/)

---

## Success Criteria

The initiative is successful when:

1. **Coverage**: ≥80% line coverage across AI-related components (AR-15)
2. **Critical Paths**: 100% coverage for agent execution, LLM integration, governance, memory (AR-15)
3. **Test Quality**:
   - [ ] All tests use standardized fixtures (AR-02)
   - [ ] No flaky tests (database isolation, deterministic mocks)
   - [ ] Property tests for all invariants (AR-03, AR-12)
   - [ ] Three-tier LLM testing (AR-11)
4. **Security**: Fuzz testing for user inputs, OWASP Top 10 coverage (AR-14)
5. **Performance**: Test suite runs in <30 minutes (pytest-xdist parallelization)
6. **Maintainability**: Tests are readable, documented, and follow patterns

---

## Requirements Traceability Matrix

| Requirement | Phase | Priority | Dependencies | Estimated |
|-------------|-------|----------|--------------|-----------|
| AR-01: Baseline measurement | 1 | P0 | None | 0.5 day |
| AR-02: Test infrastructure | 1 | P0 | None | 1-2 days |
| AR-03: Core invariants | 2 | P0 | AR-02 | 3-5 days |
| AR-04: LLM integration | 2 | P0 | AR-02, AR-03 | 3-5 days (combined) |
| AR-05: Agent governance | 5 | P0 | AR-03, AR-06 | 4-5 days |
| AR-06: Episodic memory | 3 | P1 | AR-03 | 3-4 days |
| AR-07: Social layer | 6 | P2 | AR-05, AR-06 | 3-4 days |
| AR-08: Community skills | 7 | P1 | AR-05 | 4-5 days |
| AR-09: Local agent | 8 | P0 | AR-05 | 3-4 days |
| AR-10: IM adapters | 9 | P2 | AR-05 | 2-3 days |
| AR-11: Three-tier LLM testing | 10 | P1 | All previous | 3-4 days |
| AR-12: Property-based expansion | 2-11 | P1 | AR-03 | Ongoing |
| AR-13: Chaos engineering | 11 | P3 | All previous | 3-4 days |
| AR-14: Security test suite | 2,7,8 | P0 | AR-03, AR-08, AR-09 | 2-3 days (integrated) |
| AR-15: 80% coverage | 12 | P1 | All previous | 5-7 days |
| **AR-16: Hybrid retrieval implementation** | **4** | **P1** | **AR-02, AR-03, AR-06** | **3-5 days** |
| **AR-17: Retrieval quality testing** | **4** | **P1** | **AR-16** | **3-5 days (combined)** |
| **AR-18: CI/CD pipeline reliability** | **13** | **P0** | **All previous** | **3-5 days** |
| **AR-19: Test suite determinism** | **13** | **P0** | **AR-18** | **3-5 days (combined)** |
| **AR-20: Pipeline performance** | **13** | **P1** | **AR-18** | **3-5 days (combined)** |

**Total Estimated Time:** 43-63 days

---

## Open Questions

1. **DeepEval Integration** (AR-11): Should we use DeepEval or build custom evaluators? DeepEval documentation was unavailable during research (LOW confidence).
2. **RAGAS for Retrieval** (AR-06): Is RAGAS overkill for episodic memory? Custom invariants may be simpler.
3. **Docker-in-Docker CI** (AR-08): Can we run Docker-in-Docker in GitHub Actions for sandbox testing? Security implications?
4. **Coverage Thresholds** (AR-15): Are per-module targets realistic? Should we use diff-cover for new code only?
5. **Test Execution Time**: Will 701+ tests with 80% coverage exceed 30-minute target? Need pytest-xdist.

---

## Definitions

**Critical Path**: Code that handles core AI operations (agent execution, LLM routing, governance checks, memory operations)

**Invariant**: A property that must always hold true (e.g., "confidence scores are in [0.0, 1.0]", "governance cache lookups <10ms")

**Three-tier LLM Testing**:
- Tier 1 (Unit): Mocked LLM responses, fast, deterministic
- Tier 2 (Integration): Real LLM at temperature=0, deterministic-ish, validates integration
- Tier 3 (E2E): Real LLM at temperature=0.7, probabilistic, statistical assertions

**Property-Based Testing**: Hypothesis generates hundreds of test cases to find edge cases

**Maturity Levels**:
- STUDENT: <0.5 confidence, read-only, blocked from automated triggers
- INTERN: 0.5-0.7 confidence, proposals required for actions
- SUPERVISED: 0.7-0.9 confidence, real-time monitoring
- AUTONOMOUS: >0.9 confidence, full autonomy

**Action Complexity**:
- 1 (LOW): Presentations → STUDENT+
- 2 (MODERATE): Streaming → INTERN+
- 3 (HIGH): State changes → SUPERVISED+
- 4 (CRITICAL): Deletions → AUTONOMOUS only

---

*Requirements defined: February 17, 2026*
*Initiative: Atom 80% Test Coverage*
*Next: Create roadmap with 11 phases*
