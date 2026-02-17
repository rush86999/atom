# Research Summary: Atom 80% Test Coverage Initiative

**Domain:** Python AI System Testing (LLM Apps, Multi-Agent Systems, Episodic Memory)
**Researched:** February 17, 2026
**Overall Confidence:** MEDIUM-HIGH

---

## Executive Summary

The Atom 80% test coverage initiative requires a fundamentally different testing approach than traditional software due to the non-deterministic nature of LLM outputs, the complexity of multi-agent governance, and the emergent properties of episodic memory systems. Research across three dimensions—testing stack, architecture patterns, and common pitfalls—reveals that achieving 80% coverage demands balancing **deterministic property-based testing** (40% of tests) for system invariants, **integration testing** (30%) for component interactions, **LLM-specific validation** (20%) for prompt/response quality, and **chaos engineering** (10%) for resilience verification.

The recommended technology stack leverages Atom's existing infrastructure (pytest, pytest-asyncio, pytest-cov, Hypothesis) while adding AI-specific evaluation frameworks (DeepEval for LLM metrics, Promptfoo for red-teaming, RAGAS for retrieval quality). **Critical finding**: Avoid LangSmith for testing—use DeepEval and Promptfoo instead to prevent vendor lock-in and maintain local-first, pytest-compatible testing. The architecture must organize tests by layer (LLM, agents, memory, social, skills, local agent, IM adapters) with clear boundaries between unit, property-based, integration, and E2E tests.

The most critical pitfalls to avoid are **over-mocking LLM responses** (tests pass but production breaks), **flaky tests from non-determinism** (CI becomes unreliable), **ignoring maturity-dependent behavior** (governance violations), **testing only happy paths** (failure modes untested), and **coverage vanity** (high coverage numbers but low actual protection). These pitfalls are addressed through a three-tier testing strategy: unit tests with mocked LLMs (fast), integration tests with real LLMs using `temperature=0` (deterministic-ish), and E2E tests with statistical assertions for probabilistic behaviors.

For roadmap planning, the research suggests an **11-phase build order** starting with foundation (test infrastructure), then core invariants (governance, LLM, database), followed by memory/agent/social layers, skills/security testing, LLM validation, and finally chaos engineering and gap filling. **Phase ordering rationale**: Foundation blocks everything; core invariants are safety-critical; memory/agent/social layers depend on core invariants; skills/local agent are security-critical; LLM validation requires working LLM integration; chaos engineering requires complete system; gap filling is final polish.

---

## Key Findings

**Stack:** Use pytest + pytest-asyncio + pytest-cov + pytest-mock + pytest-xdist (already in use), add DeepEval (LLM metrics), Promptfoo (red-teaming), RAGAS (retrieval quality), faker (test data), factory_boy (test objects), responses (HTTP mocking), freezegun (time freezing). **NO LangSmith for testing** (vendor lock-in, not pytest-native, requires cloud account).

**Architecture:** Four-layer test pyramid with property-based testing (40% for invariants), unit tests (40% for isolated logic), integration tests (15% for component interactions), and E2E tests (5% for critical journeys). AI-specific layers: LLM validation (prompt quality, semantics, safety), agent governance (maturity levels, graduation), memory system (episodes, retrieval, lifecycle), social layer (agent communication, feeds), skills (parsing, sandbox isolation), local agent (shell security, file access), IM adapters (webhooks, rate limiting).

**Critical Pitfall:** **Over-mocking LLM responses** leads to false confidence—tests pass but production breaks because mocks don't match actual LLM behavior, prompt engineering regressions never caught, and LLM provider API changes cause outages. **Solution**: Three-tier testing strategy (unit mocks + integration with real LLM at temperature=0 + E2E with statistical assertions), golden dataset of real LLM responses, semantic similarity assertions instead of exact string matching.

---

## Implications for Roadmap

Based on research, suggested phase structure:

### 1. **Foundation (Test Infrastructure)** - Establishes fixtures, Hypothesis settings, test utilities
   - **Addresses**: PITFALLS.md Pitfall 2 (flaky tests from non-determinism) via database isolation, ARCHITECTURE.md Phase 1 foundation patterns
   - **Avoids**: PITFALLS.md Pitfall 7 (brittle integration tests) by fixing database isolation first
   - **Estimated**: 1-2 days
   - **Key deliverables**: `conftest.py` with db_session fixture (temp file-based SQLite), test_agent fixtures (all maturity levels), mock_llm_response fixtures, Hypothesis settings (max_examples=200 local, 50 CI)

### 2. **Core Invariants (Governance, LLM, Database)** - Safety-critical system invariants
   - **Addresses**: PITFALLS.md Pitfall 3 (ignoring maturity-dependent behavior), PITFALLS.md Pitfall 6 (property tests with wrong invariants), ARCHITECTURE.md Phase 2 patterns
   - **Avoids**: PITFALLS.md Pitfall 5 (coverage vanity) by focusing on business-critical invariants first
   - **Estimated**: 3-5 days
   - **Key deliverables**: Property tests for governance cache (<10ms lookups), maturity routing (STUDENT→INTERN→SUPERVISED→AUTONOMOUS), confidence score bounds [0.0, 1.0], LLM provider fallback, database atomicity/transactions

### 3. **Memory Layer Tests** - Episode segmentation, retrieval, lifecycle
   - **Addresses**: ARCHITECTURE.md Phase 3 (memory layer depends on database), STACK.md freezegun for time-based testing, RAGAS for retrieval quality
   - **Avoids**: PITFALLS.md Pitfall 4 (testing only happy paths) by adding failure mode tests for retrieval
   - **Estimated**: 3-4 days
   - **Key deliverables**: Property tests for time-gap segmentation, retrieval invariants (temporal, semantic, sequential), lifecycle (decay, consolidation, archival), integration tests for episode creation → retrieval

### 4. **Agent Layer Tests** - Governance, graduation, triggers, supervision
   - **Addresses**: PITFALLS.md Pitfall 3 (ignoring maturity-dependent behavior), ARCHITECTURE.md Phase 4 (agents depend on governance+memory)
   - **Avoids**: PITFALLS.md Pitfall 5 (coverage vanity) by testing all maturity levels for critical actions
   - **Estimated**: 4-5 days
   - **Key deliverables**: Property tests for maturity-parametrized actions, graduation readiness scores, trigger interceptor (STUDENT blocking), supervision intervention tracking, integration tests for graduation exam with episodic memory

### 5. **Social Layer Tests** - Agent communication, feeds, Redis pub/sub
   - **Addresses**: ARCHITECTURE.md Phase 5 (social depends on agents+memory), multi-agent coordination patterns
   - **Avoids**: PITFALLS.md Pitfall 7 (slow integration tests) by using FakeRedis for unit tests
   - **Estimated**: 3-4 days
   - **Key deliverables**: Property tests for message structure invariants, feed generation (ordering, pagination), Redis pub/sub (channel subscriptions), integration tests for multi-agent task distribution

### 6. **Skills Layer Tests** - Parsing, adaptation, sandbox isolation, registry
   - **Addresses**: PITFALLS.md Pitfall 8 (not testing security boundaries), ARCHITECTURE.md Docker container isolation testing
   - **Avoids**: PITFALLS.md "security handled by framework" assumption
   - **Estimated**: 4-5 days
   - **Key deliverables**: Property tests for SKILL.md parsing invariants, BaseTool wrapping, sandbox isolation (Docker security flags), registry workflow (Untrusted→Active→Banned), fuzz testing for malicious skills

### 7. **Local Agent Tests** - Shell security, file access, command whitelist
   - **Addresses**: PITFALLS.md Pitfall 8 (security boundaries), ARCHITECTURE.md Phase 7 (local agent is security-critical)
   - **Avoids**: PITFALLS.md "test later" mentality for security
   - **Estimated**: 3-4 days
   - **Key deliverables**: Property tests for shell command injection prevention, file access boundary checks, command whitelist enforcement, AUTONOMOUS-only gate, fuzz testing for user inputs

### 8. **IM Layer Tests** - Webhook handling, rate limiting, integrations
   - **Addresses**: ARCHITECTURE.md Phase 8 (IM depends on agents), STACK.md responses library for HTTP mocking
   - **Avoids**: PITFALLS.md Pitfall 4 (only happy paths) by testing webhook failures, rate limit violations
   - **Estimated**: 2-3 days
   - **Key deliverables**: Property tests for webhook signature validation, replay prevention, rate limiting thresholds, integration tests for Slack/Teams/Discord routing

### 9. **LLM Validation Tests** - Prompt quality, response semantics, safety, cost
   - **Addresses**: PITFALLS.md Pitfall 1 (over-mocking LLM responses) via three-tier strategy, STACK.md DeepEval for metrics, Promptfoo for red-teaming
   - **Avoids**: PITFALLS.md "all tests mock LLM" anti-pattern
   - **Estimated**: 3-4 days
   - **Key deliverables**: Integration tests with real LLM (temperature=0), DeepEval metrics (faithfulness, relevance, hallucination), Promptfoo red-teaming (adversarial inputs), semantic similarity assertions, golden dataset

### 10. **Chaos Engineering Tests** - Failure injection, resilience verification
   - **Addresses**: PITFALLS.md Pitfall 4 (failure modes), ARCHITECTURE.md Phase 10 (chaos requires complete system)
   - **Avoids**: PITFALLS.md "we'll test error handling in production" assumption
   - **Estimated**: 3-4 days
   - **Key deliverables**: LLM timeout/rate limit fallback tests, database connection loss recovery, Redis pub/sub degradation, network partition handling, resource exhaustion scenarios

### 11. **Coverage Analysis & Gap Filling** - Reach 80% coverage target
   - **Addresses**: PITFALLS.md Pitfall 5 (coverage vanity) via critical path auditing, ARCHITECTURE.md Phase 11 (gap filling)
   - **Avoids**: PITFALLS.md "chase overall coverage %" anti-pattern by focusing on critical paths
   - **Estimated**: 5-7 days
   - **Key deliverables**: Per-module coverage targets (core 90%, tools 80%, API 70%, models 50%), critical path coverage tracking, manual audit of htmlcov/ for red lines in critical services, targeted tests for uncovered code

**Phase ordering rationale:**
- **Foundation first** because db_session and test_agent fixtures are dependencies for all subsequent tests
- **Core invariants second** because governance/LLM/database are safety-critical and block all other layers
- **Memory layer third** because episodes are used by agents, social layer, and graduation framework
- **Agent layer fourth** because agents depend on governance and memory, and are used by social/skills/IM layers
- **Social layer fifth** because it depends on agents and memory (for feed episodes)
- **Skills layer sixth** because skills depend on agents (governance) and are security-critical
- **Local agent seventh** because it depends on governance and is security-critical (AUTONOMOUS gate)
- **IM layer eighth** because it depends on agents and has moderate complexity
- **LLM validation ninth** because it requires working LLM integration from all previous layers
- **Chaos engineering tenth** because it requires complete working system to test resilience
- **Gap filling eleventh** because only after all tests written can we identify true gaps

**Research flags for phases:**
- **Phase 1 (Foundation)**: Likely needs deeper research on SQLite temp file pattern vs. :memory: (current conftest.py uses temp file, but verify no connection isolation issues)
- **Phase 9 (LLM Validation)**: Likely needs deeper research on DeepEval integration (webReader failed during research, LOW confidence on API patterns)
- **Phase 6 (Skills)**: Likely needs deeper research on Docker-in-Docker testing in CI (security implications, performance)
- **Phase 10 (Chaos)**: Likely needs deeper research on chaos testing patterns for AI systems (standard patterns may not apply to LLM failures)
- **Phases 2-8**: Standard patterns, unlikely to need research (HIGH confidence on pytest/Hypothesis patterns)

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | **MEDIUM-HIGH** | pytest/Hypothesis/faker/responses/freezegun are HIGH confidence (standard tools, official docs). DeepEval is LOW confidence (webReader failed). Promptfoo is MEDIUM confidence (official docs fetched). RAGAS is LOW confidence (WebSearch failed). Overall MEDIUM-HIGH because core stack (pytest, Hypothesis) is solid, AI-specific tools need verification during Phase 1. |
| **Features** | **N/A** | FEATURES.md does not exist. Feature landscape inferred from ARCHITECTURE.md layer breakdown and codebase analysis (701 test files, existing property tests). Should capture feature requirements during roadmap creation. |
| **Architecture** | **HIGH** | Based on existing Atom infrastructure (tests/property_tests/ with conftest.py, README.md) and established AI testing patterns (Hypothesis docs, pytest docs, LLM testing academic paper). Four-layer test pyramid is well-documented. 11-phase build order is logical but may need adjustment during roadmap planning. |
| **Pitfalls** | **MEDIUM-HIGH** | Based on codebase analysis (existing test patterns, API testing guide), AI testing knowledge (non-determinism, mocking challenges), and industry best practices. Web search was not functional during research, so could not verify against 2025/2026 LLM testing case studies. Confidence is MEDIUM-HIGH because pitfalls are well-understood in AI testing community, but Atom-specific context may reveal unique issues. |

**Overall confidence: MEDIUM-HIGH** — Stack and architecture are solid (HIGH confidence), pitfalls are well-identified (MEDIUM-HIGH confidence), gaps exist in AI-specific tools (DeepEval, RAGAS) and external verification (no web search). Phase 1 should include external research validation for DeepEval integration and chaos testing patterns.

---

## Gaps to Address

**Research Gaps (inconclusive findings):**
1. **DeepEval integration patterns** — webReader failed to fetch documentation, LOW confidence on API usage, metric thresholds (faithfulness, relevance, hallucination), and pytest integration patterns. **Phase 9 will need research spike** on DeepEval setup, golden dataset creation, and semantic similarity thresholds.
2. **RAGAS for episodic memory retrieval** — WebSearch failed, no verification of RAGAS API, LOW confidence on integration with LanceDB, context precision/recall metrics, and pytest compatibility. **Phase 3 (memory layer) should evaluate RAGAS vs. custom retrieval metrics**.
3. **Chaos testing for AI systems** — Standard chaos engineering patterns (databases, Redis) are HIGH confidence, but AI-specific chaos (LLM provider failures, prompt injection attacks, non-deterministic cascades) may need research. **Phase 10 should include research spike** on AI-specific chaos patterns.
4. **LangSmith vs. DeepEval/Promptfoo trade-offs** — STACK.md recommends avoiding LangSmith for testing (vendor lock-in, cloud dependency), but no direct comparison of features. **Phase 1 should evaluate** if LangSmith Evaluation provides unique capabilities worth the lock-in.

**Topics needing phase-specific research later:**
1. **Phase 1 (Foundation)**: Verify SQLite temp file pattern vs. :memory: — current conftest.py uses temp file to avoid connection isolation issues, but research should confirm this is best practice for pytest-asyncio + SQLAlchemy 2.0.
2. **Phase 3 (Memory)**: RAGAS integration vs. custom retrieval metrics — RAGAS may be overkill if episodic memory retrieval is simple vector search. Consider custom invariants (e.g., "episodes sorted by relevance", "no duplicates in results").
3. **Phase 6 (Skills)**: Docker-in-Docker testing in CI — security implications of running Docker containers in GitHub Actions, performance impact, alternative approaches (mocked Docker for unit tests, real Docker for integration tests only).
4. **Phase 9 (LLM Validation)**: DeepEval setup, golden dataset creation, semantic similarity thresholds — need to define what "good enough" looks like (e.g., similarity >0.85, faithfulness >0.7). May need to tune thresholds based on real LLM outputs.
5. **Phase 10 (Chaos)**: AI-specific chaos patterns — LLM provider cascades (OpenAI down → Anthropic down → local fallback), prompt injection resilience (adversarial inputs rejected gracefully), non-deterministic failure propagation (LLM hallucination → agent action → memory corruption).

**Missing research file:**
- **FEATURES.md** does not exist — Feature landscape should be captured during roadmap creation (e.g., which agent capabilities need testing, which LLM providers to support, which IM integrations to test). Current inference from ARCHITECTURE.md layers (LLM, agents, memory, social, skills, local agent, IM adapters) may be incomplete.

**Verification gaps:**
- No web search during research (tool was not functional) — could not verify against 2025/2026 LLM testing best practices, industry case studies, or Hypothesis library latest documentation.
- DeepEval and RAGAS documentation could not be fetched (network errors) — LOW confidence on these tools, may need to switch alternatives (e.g., custom evaluators, LangSmith Evaluation if vendor lock-in is acceptable).
- No verification of Promptfoo red-teaming patterns (official docs fetched but not tested) — MEDIUM confidence, should test Promptfoo CLI during Phase 9.

**Recommendation for roadmap:**
- Include **research spikes** in Phase 1 (DeepEval evaluation), Phase 3 (RAGAS evaluation), Phase 6 (Docker-in-Docker CI patterns), Phase 9 (LLM validation thresholds), Phase 10 (AI-specific chaos patterns).
- Create **FEATURES.md** during roadmap planning to capture feature landscape (e.g., "test all 4 maturity levels for 12 action types", "test 5 LLM providers", "test 3 IM adapters").
- Consider **external validation** of research findings (review LangChain testing concepts, check AI testing conference papers from NeurIPS/ICML 2025).

---

## Synthesis of Research Files

### From STACK.md
- **Technology stack**: pytest 8.0+, pytest-asyncio 0.23+, pytest-cov 5.0+, pytest-mock 3.14+, pytest-xdist 3.6+, Hypothesis 6.100+, faker 30.0+, factory_boy 3.3+, responses 0.25+, freezegun 1.5+ (all already in use or straightforward additions)
- **AI-specific tools**: DeepEval 1.0+ (LLM metrics), Promptfoo 0.80+ (red-teaming), RAGAS 0.1+ (retrieval quality) — LOW/MEDIUM confidence, need verification
- **Avoid**: LangSmith for testing (vendor lock-in, not pytest-native), unittest.TestCase (verbose, no fixtures), nose2 (deprecated), vcrpy (brittle for LLM), LangChain test harness (framework lock-in)
- **Install command**: All tools pip-installable, no complex dependencies
- **Key pattern**: Three-tier LLM testing (unit mocks + integration with temperature=0 + E2E with statistical assertions)

### From ARCHITECTURE.md
- **Test pyramid**: 40% unit tests, 40% property-based tests (Hypothesis), 15% integration tests, 5% E2E tests
- **AI-specific layers**: LLM validation (20% of AI tests), chaos engineering (10% of AI tests)
- **Project structure**: `tests/property_tests/` organized by layer (llm/, agents/, memory/, social/, skills/, local_agent/, im_layer/, governance/, api/, database/, security/, performance/)
- **Architectural patterns**: Deterministic LLM mocking, property-based invariant testing, semantic similarity testing, episode-based memory testing, multi-agent coordination testing, chaos engineering
- **Build order**: 11 phases from foundation to gap filling, with clear dependencies (foundation → core invariants → memory → agents → social → skills → local agent → IM → LLM validation → chaos → gap filling)
- **Anti-patterns**: Exact string matching for LLM outputs, testing implementation details, ignoring test data cleanup, mocking everything, property tests without invariants

### From PITFALLS.md
- **5 critical pitfalls**: (1) Over-mocking LLM responses → false confidence, (2) Flaky tests from non-determinism → unreliable CI, (3) Ignoring maturity-dependent behavior → governance violations, (4) Testing only happy paths → failure modes untested, (5) Coverage vanity → high coverage, low protection
- **3 moderate pitfalls**: (6) Property tests with wrong invariants (too specific, trivial, or not required), (7) Integration tests too slow/brittle (real APIs in CI, no categorization by speed)
- **Minor pitfall**: (8) Not testing security boundaries (shell injection, Docker escape, webhook spoofing, SQL injection, XSS)
- **Technical debt patterns**: Table of shortcuts vs. long-term costs (e.g., "mock all LLM calls" = fast tests but missed integration issues, NEVER acceptable)
- **Pitfall-to-phase mapping**: Each pitfall maps to prevention phase(s) and verification criteria (e.g., over-mocking LLM prevented in Phase 1, verified by integration tests calling real LLMs)

---

## Next Steps for Roadmap Creation

1. **Create FEATURES.md** to capture feature landscape:
   - Agent capabilities to test (12 action types × 4 maturity levels = 48 combinations?)
   - LLM providers to support (OpenAI, Anthropic, DeepSeek, Gemini — test provider fallback?)
   - IM integrations to test (Slack, Teams, Discord — webhook handling, rate limiting)
   - Memory system features (temporal/semantic/sequential retrieval, lifecycle, consolidation)
   - Social layer features (agent communication, feeds, pub/sub, coordination)
   - Skills features (parsing, adaptation, sandbox isolation, registry workflow)
   - Local agent features (shell security, file access, command whitelist, AUTONOMOUS gate)

2. **Review and validate research findings**:
   - Fetch DeepEval documentation (network failed during research)
   - Fetch RAGAS documentation (web search failed)
   - Review LangSmith Evaluation trade-offs (is vendor lock-in acceptable for LLM validation?)
   - Check 2025/2026 LLM testing best practices (conference papers, case studies)

3. **Refine 11-phase structure** based on feature landscape:
   - Are 11 phases too granular? Consider merging phases (e.g., social + IM layers, skills + local agent)
   - Are phase estimates realistic? (Foundation 1-2 days, Core Invariants 3-5 days, etc.)
   - What is parallelizable? (e.g., skills, local agent, IM layers could be done in parallel if team size allows)

4. **Define success criteria per phase**:
   - Coverage targets (e.g., Phase 2: governance/LLM/database ≥90%)
   - Test counts (e.g., Phase 2: 50 property tests for governance invariants)
   - Performance targets (e.g., Phase 2: property tests <10s each)
   - Quality gates (e.g., all phases must pass pytest, mypy, coverage checks)

5. **Plan research spikes**:
   - Phase 1: DeepEval evaluation (1 day)
   - Phase 3: RAGAS evaluation (0.5 day)
   - Phase 6: Docker-in-Docker CI patterns (0.5 day)
   - Phase 9: LLM validation thresholds (0.5 day)
   - Phase 10: AI-specific chaos patterns (0.5 day)

---

*Research summary synthesized from STACK.md, ARCHITECTURE.md, and PITFALLS.md*
*Date: February 17, 2026*
*Confidence: MEDIUM-HIGH*
*Next step: Create FEATURES.md and begin roadmap planning*
