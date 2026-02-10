# Project Research Summary

**Project:** Atom Test Coverage Initiative
**Domain:** Comprehensive Testing Systems for Python/FastAPI/React Native
**Researched:** February 10, 2026
**Confidence:** HIGH

## Executive Summary

Atom is an AI-powered business automation platform requiring a comprehensive testing initiative to achieve 80% code coverage within 1-2 weeks. The platform combines a Python/FastAPI backend with multi-agent governance, episodic memory systems, and React Native mobile apps. Industry best practices for 2026 emphasize property-based testing, critical path prioritization, and risk-based testing strategies over brute-force coverage accumulation.

Research indicates that pytest with Hypothesis for property-based testing is the industry-standard approach for Python/FastAPI codebases. The recommended architecture follows a test pyramid pattern: 40% unit tests, 40% property-based tests (using Hypothesis), 15% integration tests, and 5% E2E tests. The key differentiator for Atom is governance-specific testing—validating agent maturity levels, confidence scores, and action complexity matrix invariants—which is unique to this multi-agent system.

Critical risks include coverage churn (writing junk tests to hit 80% targets), weak property tests that don't verify meaningful invariants, and integration test state contamination causing flaky tests. Mitigation requires establishing quality thresholds before measuring coverage, documenting invariants explicitly before implementing property tests, and enforcing parallel execution from day one to catch state sharing issues early.

## Key Findings

### Recommended Stack

**Core technologies:**
- **pytest 7.4+**: Test framework with async support — industry standard for Python, provides fixtures, markers, and discovery
- **Hypothesis 6.92+**: Property-based testing library — finds edge cases unit tests miss through random input generation
- **pytest-cov**: Coverage reporting — generates HTML/JSON/terminal reports, enables 80% threshold enforcement
- **pytest-asyncio**: Async test support — required for FastAPI endpoints, WebSocket testing, background task coordination
- **pytest-xdist**: Parallel test execution — reduces CI time from hours to minutes, exposes state sharing bugs
- **factory_boy**: Test data generation — prevents brittle hardcoded fixtures, enables isolated test data creation
- **fakeredis**: Redis mocking — faster than real Redis for testing WebSocket/caching scenarios

**Version requirements:** Python 3.11+ (matching production), pytest 7.4+ (asyncio_mode = auto), Hypothesis 6.92+ (conservative strategy for CI).

### Expected Features

**Must have (table stakes):**
- **Test Coverage Metrics** — 80% threshold is industry standard before code review approval
- **Unit Tests** — foundation of testing strategy, verify components in isolation
- **Property-Based Tests** — modern best practice, verify invariants across random inputs
- **Integration Tests** — required to verify component interactions (governance, episodic memory)
- **CI/CD Integration** — tests must run automatically in pipeline, configured in pytest.ini
- **Test Discovery & Organization** — pytest discovers tests by pattern, markers enable categorization
- **Async Test Support** — required for FastAPI, configured as `asyncio_mode = auto`
- **Coverage Reports** — HTML, terminal, and JSON reports track progress toward 80% goal

**Should have (competitive):**
- **Property-Based Testing Framework** — 108 files already exist, catches edge cases unit tests miss (10x-100x more test cases)
- **Critical Path Prioritization** — P0/P1/P2/P3 markers enable focusing on governance, security, episodic memory first
- **Risk-Based Testing** — domain markers (financial, security, api, database, workflow, episode, agent) for targeted coverage
- **Governance-Specific Testing** — UNIQUE to Atom, validates agent maturity levels, confidence scores, action complexity matrix
- **Coverage by Domain** — track coverage for critical subsystems (governance, security, episodes) separately
- **Test Protection Mechanisms** — PROPERTY_TEST_GUARDIAN.md prevents AI/automation from modifying critical invariant tests

**Defer (v2+):**
- **100% Coverage Goal** — diminishing returns, focus on 80% critical paths instead
- **E2E Tests for All Workflows** — too slow/fragile for 2-week sprint, integration tests for critical workflows only
- **Mutation Testing** — very slow (10x-100x runtime), run nightly/weekly not in PR checks
- **Chaos Engineering** — resilience testing, requires production infrastructure
- **Fuzzy Testing** — security-focused, high false positive rate, defer to post-sprint

### Architecture Approach

**Recommended structure:** Test pyramid with property-based layer. Bottom layer: unit tests (fast, example-based). Middle layer: property tests (medium speed, exhaustive invariant verification). Top layer: integration/E2E tests (slow, realistic workflows). This pattern provides fast feedback while maintaining comprehensive coverage.

**Major components:**
1. **Unit Tests** — test individual functions/classes in isolation using pytest + pytest-mock (<0.1s each)
2. **Property Tests** — verify invariants hold for all inputs using Hypothesis with custom strategies (<1s each)
3. **Integration Tests** — test module interactions with real dependencies using database fixtures (<5s each)
4. **E2E Tests** — test complete workflows through API using TestClient/Playwright (<30s each, 5% of pyramid)
5. **Coverage System** — track code coverage using pytest-cov with JSON/HTML/terminal reports
6. **Test Fixtures** — provide reusable test data using pytest fixtures (conftest.py) with appropriate scoping
7. **Test Infrastructure** — CI/CD integration (GitHub Actions), parallel execution (pytest-xdist), test data factories

**Key architectural patterns:** Test pyramid with property-based layer, fixture hierarchy with scoping (session/module/function), strategy-based property testing, layered mock strategy (only mock external dependencies), coverage-driven test development.

### Critical Pitfalls

1. **Coverage Churn Under Timeline Pressure** — teams write low-value tests to hit 80% targets, creating false confidence. Prevention: set quality thresholds (assertion density), require test review focusing on "what bugs does this catch?", ban trivial tests (assert True, assert not None), timebox properly (80% quality coverage in 4 weeks > 80% junk coverage in 1 week).

2. **Property-Based Testing Without Meaningful Invariants** — teams test obvious truths (x + y == y + x) rather than domain invariants, missing bug-finding value. Prevention: identify invariants first (list 3-5 domain invariants per module), reference established property patterns (roundtrip, inductive), focus on critical paths (governance, episodic memory), require bug-finding evidence in docstrings.

3. **Integration Test State Contamination** — shared database state/file systems cause intermittent failures, destroying confidence. Prevention: transaction rollback pattern (never commit in tests), test-scoped fixtures (scope="function"), parallel execution from day one (pytest-xdist -n auto), unique test data (f"test_agent_{uuid4()}"), explicit cleanup in finally blocks.

4. **Async Test Race Conditions** — improper async patterns lead to tests that fail randomly due to timing issues. Prevention: use pytest-asyncio with auto-mode, explicit async coordination (asyncio.Event, asyncio.Queue), await background tasks (poll for completion status), WebSocket testing with receive_json(timeout=5), ban time.sleep() in tests.

5. **React Native Testing Platform Neglect** — tests written for iOS only, assuming Android behavior is identical. Prevention: test both platforms from day one in CI, platform-specific fixtures (@pytest.fixture(params=["ios", "android"])), mock native modules correctly (Expo), file path abstraction (RNFS.DocumentDirectoryPath), permission testing for both platforms.

6. **Test Data Fragility** — tests depend on hardcoded fixtures (agent_id="test-agent-123") that become invalid as code evolves. Prevention: factory pattern (factory_boy) for dynamic test data creation, test data isolation (each test creates own data), minimal assumptions (only assume database schema), fixture versioning with schema tags, mock external APIs.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation & Strategy
**Rationale:** Must establish testing infrastructure and quality standards before writing tests to prevent coverage churn and test data fragility. Without factories and quality gates, teams will write brittle junk tests.

**Delivers:** Test infrastructure (pytest-xdist, pytest-asyncio, factory_boy), quality gates (assertion density metric, critical path coverage), dual-platform CI for mobile, documented invariants for property tests.

**Addresses:** Test Coverage Metrics, Test Discovery & Organization, Async Test Support, Coverage Reports, Test Data Factories

**Avoids:** Coverage churn under timeline pressure, test data fragility

**Duration:** 2-3 days

### Phase 2: Core Property Tests
**Rationale:** Property-based testing is Atom's strongest differentiator but requires identifying meaningful invariants first. Governance, episodic memory, and agent coordination have complex state transitions best verified through property tests.

**Delivers:** Property tests for governance invariants (maturity, permissions, cache performance), episodic memory invariants (segmentation, retrieval, lifecycle), agent coordination invariants (multi-agent, view orchestration), fuzzy tests with error contracts.

**Uses:** Hypothesis 6.92+, custom strategies for domain objects, pytest markers for categorization

**Implements:** Strategy-based property testing pattern, invariant documentation, bug-finding evidence in docstrings

**Duration:** 4-5 days

**Research flag:** Medium confidence on invariant identification—requires domain knowledge from senior developers to identify governance/episodic memory invariants correctly.

### Phase 3: Integration Tests
**Rationale:** After establishing infrastructure and property tests, validate component interactions. Must enforce parallel execution during test writing to catch state sharing issues early.

**Delivers:** Integration tests for API contracts (FastAPI endpoints, request/response validation), database transactions (rollback, isolation, consistency), async coordination (WebSocket, background tasks, agent execution), external service mocking (LLM providers, Slack, GitHub).

**Implements:** Transaction rollback pattern, test-scoped fixtures, explicit async coordination, parallel execution verification

**Avoids:** Integration test state contamination, async test race conditions

**Duration:** 3-4 days

**Research flag:** Low confidence—well-documented patterns for FastAPI integration testing, pytest-asyncio integration is standard.

### Phase 4: Mobile Tests
**Rationale:** React Native testing requires platform-specific approaches. Set up dual-platform CI from day one to catch platform differences early.

**Delivers:** React Native component testing (iOS + Android), device capabilities (Camera, Location, Notifications), platform-specific permissions (biometric, file system), mobile workflow testing (offline, sync, background).

**Implements:** Platform-specific fixtures, native module mocking, file path abstraction, permission testing for both platforms

**Avoids:** React Native testing platform neglect

**Duration:** 2-3 days

**Research flag:** Medium confidence—React Native testing is platform-specific, less documentation than backend testing. May need deeper research on Expo mock modules and platform-specific permission testing.

### Phase 5: Coverage & Validation
**Rationale:** After implementing test types, achieve 80% coverage on critical paths (governance, security, episodic memory) and validate overall coverage target.

**Delivers:** 80% coverage on governance domain (core/governance_service.py, agent_context_resolver.py, governance_cache.py), 80% coverage on security domain (auth/, crypto/, tools_security/), 80% coverage on episodic memory domain (episode_*.py services), overall 80% coverage across backend/, coverage trending setup.

**Implements:** Coverage-driven test development, domain-specific coverage reports, coverage trend tracking

**Duration:** 2-3 days

**Research flag:** Low confidence—coverage reporting is well-documented, pytest-cov provides standard interfaces.

### Phase Ordering Rationale

- **Foundation first:** Cannot write quality tests without infrastructure (factories, parallel execution, quality gates). Skipping this leads to coverage churn (Pitfall #1) and test data fragility (Pitfall #7).
- **Property tests before integration:** Property tests require different mindset (invariant identification). Writing them after integration tests leads to weak properties (Pitfall #2).
- **Integration tests third:** Requires solid foundation (fixtures) and validates real behavior. Must enforce parallel execution to avoid state contamination (Pitfall #3).
- **Mobile tests fourth:** Platform-specific testing is isolated from backend, can be done in parallel with Phase 2-3 if resources allow. Depends on foundation (dual-platform CI) but not on backend tests.
- **Coverage validation last:** Cannot achieve meaningful coverage without quality tests. Coverage metrics are the output, not the goal.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 2 (Core Property Tests):** Medium confidence on invariant identification. Governance/episodic memory invariants require domain knowledge. May need workshops with senior developers to document invariants before implementation.
- **Phase 4 (Mobile Tests):** Medium confidence on React Native testing patterns. Platform-specific testing has less documentation than backend. Expo mock modules may need investigation.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Foundation & Strategy):** High confidence. pytest-xdist, pytest-asyncio, factory_boy are well-documented with standard patterns.
- **Phase 3 (Integration Tests):** High confidence. FastAPI testing strategies, pytest-asyncio integration, transaction rollback patterns are established best practices.
- **Phase 5 (Coverage & Validation):** High confidence. pytest-cov provides standard interfaces for coverage reporting, well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified against official docs (pytest 7.4+, Hypothesis 6.92+, pytest-asyncio, pytest-cov). Python 3.11+ matches production. |
| Features | MEDIUM | Table stakes (80% coverage, unit tests, integration tests) verified from multiple 2026 testing best practice sources. Differentiators (property-based testing, governance-specific testing) inferred from existing codebase analysis. |
| Architecture | HIGH | Test pyramid pattern, fixture hierarchy, property-based testing strategies verified from official pytest/Hypothesis documentation and FastAPI testing guides. |
| Pitfalls | HIGH | All 7 critical pitfalls documented with prevention strategies, verified from official docs (Hypothesis, React Native testing) and 2026 research on property-based testing challenges. |

**Overall confidence:** HIGH

- Stack and architecture backed by official documentation (pytest, Hypothesis, FastAPI, React Native)
- Pitfalls supported by 2026 academic research on property-based testing challenges
- Features moderate confidence due to reliance on industry best practices (not official docs) for some differentiators
- Missing STACK.md research file, but stack inferred from existing codebase and verified against official docs

### Gaps to Address

- **Missing STACK.md research file:** Stack recommendations inferred from existing codebase (pytest.ini, test infrastructure) and verified against official docs. No dedicated stack research was conducted by the parallel agents.
- **Invariant identification for property tests:** Requires domain knowledge from senior developers to identify governance/episodic memory invariants. Plan: Hold workshop during Phase 2 planning to document invariants before implementation.
- **React Native platform-specific testing:** Less documentation than backend testing. Expo mock modules may require investigation during Phase 4 planning. Mitigation: Set up dual-platform CI early to expose platform differences through testing.
- **Test data factory implementation:** factory_boy recommended but not yet implemented. Need to define factory schemas for AgentRegistry, Episode, CanvasAudit models during Phase 1.

## Sources

### Primary (HIGH confidence)
- **[Testing - React Native](https://reactnative.dev/docs/testing-overview)** — Official React Native testing strategies, updated Jan 16, 2026
- **[Using Hypothesis and Schemathesis to Test FastAPI](https://testdriven.io/blog/fastapi-hypothesis/)** — Comprehensive property-based testing guide for FastAPI
- **[Getting Started With Property-Based Testing in Python With Hypothesis](https://semaphore.io/blog/property-based-testing-python-hypothesis-pytest)** — Detailed Hypothesis implementation tutorial
- **[An Empirical Evaluation of Property-Based Testing in Python](https://dl.acm.org/doi/10.1145/3764068)** — ACM OOPSLA 2025 research on property-based testing challenges
- **[Common Pitfalls of Integration Testing in Java](https://www.atomicjar.com/2023/11/common-pitfalls-of-integration-testing-in-java/)** — Database state isolation, test data management (applicable to Python/FastAPI)
- **[The Fuzzing Book - Reducing Failure-Inducing Inputs](https://www.fuzzingbook.org/html/Reducer.html)** — Fuzzing techniques and minimizing failure cases

### Secondary (MEDIUM confidence)
- **[Software Testing Best Practices for 2026 - N-iX](https://www.n-ix.com/software-testing-best-practices/)** — Risk-based testing, automation, metrics (January 18, 2026)
- **[Zero to 92% Test Coverage: A Week-Long Journey - Medium](https://medium.com/@jaivalsuthar/building-a-comprehensive-testing-suite-a-week-long-journey-to-92-coverage-1a9f5df8c4e0)** — Direct relevance to achieving high coverage in one week
- **[How to Write an Effective Test Coverage Plan - QA Wolf](https://www.qawolf.com/blog/how-to-write-an-effective-test-coverage-plan)** — Prioritize automation by impact
- **[Testing Strategies: pytest, fixtures, and mocking best practices](https://dasroot.net/posts/2026/01/testing-strategies-pytest-fixtures-mocking/)** — January 22, 2026
- **[How to Use pytest with Mocking - OneUptime](https://oneuptime.com/blog/post/2026-02-02-pytest-mocking/view)** — February 2, 2026
- **[Mastering Pytest: Advanced Fixtures, Parameterization, and Mocking](https://medium.com/@abhayda/mastering-pytest-advanced-fixtures-parameterization-and-mocking-explained-108a7a2ab82d)** — February 8, 2025
- **[FastAPI Best Practices](https://auth0.com/blog/fastapi-best-practices/)** — Auth0's FastAPI testing guide
- **[6 Common React Native mistakes I still see in production apps](https://medium.com/@eduardofelipi/6-common-react-native-mistakes-i-still-see-in-production-apps-01bd81260628)** — Medium, Jan 2, 2026

### Tertiary (LOW confidence)
- **[Hypothesis: Property-Based Testing for Python](https://news.ycombinator.com/item?id=45818562)** — Hacker News community discussion
- **[Integration test fails intermittently when CI builds run concurrently](https://www.reddit.com/r/softwaretesting/comments/1on5qee/integration_test_fails_intermittently_when_ci/)** — Reddit real-world example
- **[The argument against clearing the database between tests](https://calpaterson.com/against-database-teardown.html)** — Alternative viewpoint on database state management

### Codebase Analysis (HIGH confidence)
- `/Users/rushiparikh/projects/atom/backend/pytest.ini` — Pytest configuration with markers, coverage, Hypothesis settings
- `/Users/rushiparikh/projects/atom/backend/tests/property_tests/README.md` — Property-based testing documentation (108 files, ~3,699 tests)
- `/Users/rushiparikh/projects/atom/backend/tests/property_tests/database/test_database_invariants.py` — Example property-based tests (49 test functions, 808 lines)
- `/Users/rushiparikh/projects/atom/.planning/PROJECT.md` — Project requirements and current state

---
*Research completed: February 10, 2026*
*Ready for roadmap: yes*
