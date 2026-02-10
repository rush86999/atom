# Pitfalls Research

**Domain:** Comprehensive Testing Initiative for Python/FastAPI/React Native Codebase
**Researched:** February 10, 2026
**Confidence:** HIGH

---

## Critical Pitfalls

### Pitfall 1: Coverage Churn Under Timeline Pressure

**What goes wrong:**
Teams rush to hit 80% coverage targets by writing low-value tests that exercise code without verifying behavior. Tests become "coverage checks" rather than "quality assurances." The resulting test suite has high coverage metrics but misses real bugs, creating a false sense of security.

**Why it happens:**
- Timeline pressure forces compromise on test quality
- Coverage metrics are easily gamified (assert True, trivial tests)
- 80% coverage in 1-2 weeks incentivizes quantity over quality
- Writing meaningful tests takes 3-5x longer than writing coverage tests

**Consequences:**
- High coverage (80%+) but production bugs still slip through
- Tests catch regressions but not logic errors or edge cases
- False confidence leads to reduced manual testing
- Technical debt: tests must be rewritten later for actual value
- Coverage targets become organizational theater rather than quality gates

**How to avoid:**
1. **Set quality thresholds, not just coverage:** Require 80% coverage AND 70% assertion quality (measured by assertion complexity)
2. **Test categorization:** Track "critical path coverage" vs. "overall coverage" - governance, episodic memory, agent execution need >90%
3. **Review test assertions:** Require test review focusing on "what bugs does this catch?" not "does it pass?"
4. **Ban trivial tests:** Prohibit tests with single assert True or assert not None
5. **Timebox properly:** 80% quality coverage in 4 weeks > 80% junk coverage in 1 week

**Warning signs:**
- Tests with single-line assertions (assert result is not None)
- Test files with 100% coverage but <10 assertions per 100 lines
- Developers commenting "this test is just for coverage"
- Rapid coverage growth (>10% per day) without corresponding architecture changes
- Tests passing but bugs appearing in previously tested areas

**Phase to address:**
**Phase 1: Foundation & Strategy** - Establish testing quality standards before writing tests. Define what "good test" means before measuring coverage.

---

### Pitfall 2: Property-Based Testing Without Meaningful Invariants

**What goes wrong:**
Teams adopt property-based testing (Hypothesis) but write properties that test obvious truths or implementation details rather than meaningful invariants. Tests generate hundreds of examples but catch no bugs because the properties are too weak or miss the point.

**Why it happens:**
- Property-based testing requires different mindset than example-based testing
- Identifying good invariants is significantly harder than writing test cases
- Difficulty determining "what is invariant here?" leads to trivial properties (x + y == y + x)
- Hypothesis examples show "@given(integers())" but finding domain-specific properties is undocumented
- Pressure to add "fancy tests" leads to surface-level adoption

**Consequences:**
- Property tests become expensive assertion checks (calling functions 100x with random data to verify nothing crashes)
- False confidence: "we have property tests" but they don't verify system invariants
- Slow test suites (100 examples per test) without bug-finding value
- Property tests abandoned as "not useful" when the issue was weak properties
- Missed opportunity: property-based testing is exceptionally powerful for governance, episodic memory, multi-agent coordination

**How to avoid:**
1. **Identify invariants first:** Before writing property tests, list 3-5 domain invariants per module (e.g., "Agent maturity never decreases without explicit promotion")
2. **Reference patterns:** Use established property patterns (roundtrip: serialize → deserialize → equals, inductive: f(x, f(y)) == f(f(x), y))
3. **Test critical paths:** Focus property tests on governance checks, episodic memory retrieval, agent graduation - areas with complex state transitions
4. **Require bug-finding evidence:** Each property test must include "example bug this would have caught" in docstring
5. **Pair programming:** Write properties with senior developers who understand domain invariants

**Warning signs:**
- Properties testing commutativity (a + b == b + a) or associativity without domain relevance
- Property tests with no @assume or .filter() (should reject invalid inputs)
- Properties that never fail after 200+ examples (likely too weak)
- Properties testing implementation details (e.g., "function returns in <5ms") rather than behavior
- Developers struggle to explain "what invariant does this verify?"

**Phase to address:**
**Phase 2: Core Property Tests** - Dedicate time to invariant identification before implementation. Require documented invariants for governance, episodic memory, agent coordination before writing tests.

---

### Pitfall 3: Integration Test State Contamination

**What goes wrong:**
Integration tests share database state, file systems, or external service mocks, causing tests to fail intermittently when run concurrently or in random order. Test flakiness destroys confidence, leading to "flake retry" scripts or entire test suites being ignored.

**Why it happens:**
- FastAPI tests share SQLAlchemy sessions without proper isolation
- Database rollback/commit strategies inconsistent across tests
- File operations (canvas exports, episode backups) write to shared paths
- WebSocket connections not properly torn down between tests
- pytest-xdist parallel execution exposes state sharing
- Test data cleanup in finally blocks is incomplete or missing

**Consequences:**
- Tests pass locally but fail in CI (parallel execution exposes issues)
- "Flaky test retry" logic added to CI (hides real problems)
- Developers stop trusting integration tests → run less frequently
- Critical bugs slip through because "test probably just flaked"
- Time wasted debugging false failures (90% of integration test failures are state issues)
- Production incidents from integration tests being disabled

**How to avoid:**
1. **Transaction rollback pattern:** Wrap each test in transaction, rollback at end (never commit)
2. **Test-scoped fixtures:** Use `@pytest.fixture(scope="function")` for database, WebSocket, file system
3. **Parallel execution from day one:** Run tests with `pytest-xdist -n auto` during development to catch state sharing early
4. **Unique test data:** Generate unique IDs (e.g., f"test_agent_{uuid4()}") instead of hardcoded fixtures
5. **Explicit cleanup:** Always use try/finally with explicit cleanup, never rely on pytest teardown order
6. **State validation:** Assert initial state at test start (fail fast if previous test contaminated state)

**Warning signs:**
- Tests fail when run with `pytest-xdist -n 4` but pass with `pytest`
- Tests fail intermittently with "Database locked" or "File exists" errors
- Developers run tests serially during development but CI runs parallel
- `@pytest.mark.skipif` used to disable flaky tests instead of fixing
- Tests rely on execution order (test_001_, test_002_ naming)

**Phase to address:**
**Phase 3: Integration Tests** - Enforce parallel execution during test writing. Block merging tests that fail under parallel execution. Make test isolation a first-class requirement.

---

### Pitfall 4: Async Test Race Conditions

**What goes wrong:**
FastAPI async endpoints tested with improper async patterns lead to tests that pass 90% of the time but fail randomly due to timing issues. Async waits, WebSocket message ordering, and background task completion are not properly awaited.

**Why it happens:**
- `async def` test functions without `pytest-asyncio` configured
- WebSocket tests not awaiting message reception before asserting
- Background tasks (agent execution, episode segmentation) not given time to complete
- No explicit synchronization primitives (Event, Queue) used in tests
- Tests relying on `time.sleep(1)` instead of proper async coordination
- FastAPI TestClient used synchronously for async endpoints

**Consequences:**
- "Works on my machine" syndrome: tests pass locally, fail in CI (timing differences)
- False negatives: actual async bugs dismissed as "test flake"
- Increased test execution time (excessive sleep() calls to avoid races)
- Tests that "usually pass" leading to developers ignoring failures
- Race conditions in production (async coordination bugs not caught in tests)

**How to avoid:**
1. **Use pytest-asyncio:** All async tests must use `@pytest.mark.asyncio` with auto-mode configured
2. **Explicit async coordination:** Use `asyncio.Event`, `asyncio.Queue` for synchronization, never `time.sleep()`
3. **Await background tasks:** For agent execution, episode segmentation, poll for completion status before asserting
4. **WebSocket testing:** Use `websocket_client.receive_json(timeout=5)` with proper error handling
5. **Test timeout annotations:** Add `@pytest.mark.timeout(30)` to fail slow tests early (hides async issues)
6. **Async fixture scoping:** Use `@pytest_asyncio.fixture(scope="function")` for async resources

**Warning signs:**
- Tests with `time.sleep()` calls (indicates improper async coordination)
- Tests that fail 1 in 10 runs with "awaited but never completed"
- Tests passing when run singly but failing in suites (async resource contention)
- WebSocket tests with `await asyncio.sleep(0.1)` between send/receive
- Background task tests assuming completion without explicit check

**Phase to address:**
**Phase 3: Integration Tests** - Require all async tests to use pytest-asyncio with explicit coordination. Ban time.sleep() in tests. Use race detection tools (pytest-race) during development.

---

### Pitfall 5: React Native Testing Platform Neglect

**What goes wrong:**
React Native tests written for iOS only, assuming Android behavior is identical. Platform-specific APIs (permissions, file paths, native modules) cause tests to pass on one platform but fail or crash on the other.

**Why it happens:**
- Development happens on one platform (typically iOS simulator)
- Android testing requires separate emulator setup (slower, more friction)
- Assumption that "React Native abstracts platform differences"
- Platform-specific code (Camera, Location, Notifications) not mocked correctly
- File paths different between platforms (/var/mobile/ vs /data/data/)
- Native modules (Expo) have different async behavior on Android

**Consequences:**
- iOS tests pass, Android crashes in production (permission prompts, file access)
- Android-specific bugs caught late (after iOS release)
- Platform-specific workarounds in production code (if platform == 'ios'...)
- Inconsistent user experience between platforms
- Release delays when Android testing reveals fundamental issues
- User reviews mentioning "works on iPhone but broken on Android"

**How to avoid:**
1. **Test both platforms from day one:** Run tests on iOS simulator AND Android emulator in CI
2. **Platform-specific fixtures:** Create `@pytest.fixture(params=["ios", "android"])` for platform-dependent tests
3. **Mock native modules correctly:** Use Expo mock modules that simulate platform differences
4. **File path abstraction:** Use `RNFS.DocumentDirectoryPath` instead of hardcoded paths
5. **Permission testing:** Test permission flows (Camera, Location) with platform-specific prompts
6. **Platform matrix in CI:** Require tests passing on both platforms before merge

**Warning signs:**
- CI only runs tests on one platform
- Tests use `Platform.OS === 'ios'` assumptions in test code
- Device permission tests commented out for Android
- File path tests fail on Android with "ENOENT: no such file or directory"
- Native module tests mocked identically for both platforms

**Phase to address:**
**Phase 4: Mobile Tests** - Set up dual-platform CI pipeline from day one. Block merges that only pass on one platform. Create platform-specific test fixtures for permissions, file system, native modules.

---

### Pitfall 6: Fuzzy Testing Without Oracle

**What goes wrong:**
Fuzzy testing (Hypothesis, fuzzing) applied to complex functions without defining expected behavior. Tests crash applications or find edge cases but don't indicate whether the behavior is correct, leading to "found a bug... or is it?" uncertainty.

**Why it happens:**
- Fuzzing generates invalid inputs (negative lengths, empty strings) that crash functions
- No "oracle" defined: is crashing on invalid input a bug or expected?
- Error handling paths not tested, so fuzzing finds unhandled exceptions
- Complex systems (agent governance, episodic memory) have undefined behavior for edge cases
- Focus on "what breaks" rather than "what should happen"

**Consequences:**
- Fuzzing finds 100s of "bugs" that are actually expected edge cases
- Time wasted investigating non-issues (is null agent ID a bug or test artifact?)
- Fuzzing abandoned as "too noisy"
- Real bugs (actual error handling failures) lost in noise
- No clear path from fuzzing result → fix

**How to avoid:**
1. **Define error contracts:** Specify what inputs are invalid and what error should be raised
2. **Use @assume in Hypothesis:** Pre-filter invalid inputs so tests only exercise valid edge cases
3. **Error oracle tests:** Separate tests for "invalid input raises specific exception"
4. **Fuzz core functions first:** Apply fuzzing to stateless functions (LLM routing, governance checks) before complex stateful systems
5. **Baseline known bugs:** Use fuzzing to find specific bug classes (SQL injection, XSS) not random crashes
6. **Property-based oracles:** Combine fuzzing with property checks (output format, invariants preserved)

**Warning signs:**
- Fuzzing tests finding "AttributeError: None" on 50% of runs (too weak preconditions)
- No @assume or .filter() in @given strategies (testing invalid inputs)
- Tests catching all exceptions (try/except pass) to avoid failures
- Fuzzing results not reviewed because "too many false positives"
- Undefined behavior: "what should happen when agent_id is empty string?"

**Phase to address:**
**Phase 2: Core Property Tests** - Define input/output contracts before fuzzing. Create separate fuzzing suite for error handling vs. invariant preservation. Require fuzzing findings reviewed weekly.

---

### Pitfall 7: Test Data Fragility

**What goes wrong:**
Tests depend on specific data states (agent with ID 123 exists, episode with training_data flag) that become invalid as code evolves. Tests fail not because behavior changed, but because test data assumptions no longer hold.

**Why it happens:**
- Hardcoded fixtures (agent_id="test-agent-123") referenced across multiple tests
- Test data not isolated (tests assume database state from other tests)
- Database migrations invalidate assumptions (column renamed, enum changed)
- Test fixtures not updated when models change (AgentRegistry.maturity field added)
- Assumptions about external data (Slack API returns specific response format)

**Consequences:**
- Tests fail after unrelated code changes (false failures)
- Time wasted updating test data instead of tests
- Developers "comment out" failing tests to unblock CI
- Test suite becomes maintenance burden rather than safety net
- Tests deleted rather than fixed (loss of coverage)

**How to avoid:**
1. **Factory pattern:** Use factory_boy or similar to create test data dynamically, not hardcoded fixtures
2. **Test data isolation:** Each test creates its own data (never depends on pre-existing state)
3. **Minimal assumptions:** Tests should only assume database schema, not specific data
4. **Fixture versioning:** Tag fixtures with schema version, fail fast if assumptions outdated
5. **Database migration testing:** Run tests after each migration to catch broken assumptions early
6. **External data mocking:** Mock external APIs (Slack, GitHub) instead of relying on live data

**Warning signs:**
- Multiple tests referencing identical hardcoded IDs (agent_id="test-agent-123")
- Tests fail after model changes with "column does not exist" or "no such attribute"
- Test fixtures file >500 lines (accumulated hardcoded data)
- Developers keep "test data setup spreadsheet" to remember which test uses which data
- Tests using `@pytest.mark.skipif(reason="test data outdated")`

**Phase to address:**
**Phase 1: Foundation & Strategy** - Implement test data factories during test infrastructure setup. Enforce test data isolation in test reviews. Require all tests to create own data.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| **Skip async coordination** | Tests pass in 1 day vs 3 days | Random failures, lost bugs, reduced confidence | NEVER - async requires proper coordination |
| **Hardcoded test data** | Tests written in 30 min vs 2 hours | Brittle tests, maintenance burden | Only for smoke tests, replaced with factories in Phase 1 |
| **Test only iOS** | Mobile tests complete in 1 week vs 2 | Android bugs in production, platform divergence | Only for MVP hotfix, followed by Android tests within 1 week |
| **Weak property tests** | Property tests written in 2 hours vs 8 hours | False confidence, wasted test execution time | NEVER - weak properties worse than no properties |
| **Coverage over quality** | Hit 80% in 1 week vs 3 weeks | High coverage but low bug detection, rewrites | NEVER - quality thresholds prevent this |
| **Shared state between tests** | Tests written faster | Flaky tests, parallel execution fails | Only for integration tests with explicit transaction isolation |
| **Mock external services** | Tests run without dependencies | Tests don't catch integration issues | Acceptable if mocks mirror real service contracts |
| **time.sleep() in tests** | Async tests pass without complexity | Slow tests, intermittent failures | Only as temporary marker, must be replaced within 1 day |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Database (PostgreSQL)** | Tests assume committed data persists between tests | Use transaction rollback, never commit in tests |
| **WebSocket (FastAPI)** | Not awaiting message reception before asserting | Use `receive_json(timeout=5)` with error handling |
| **External APIs (Slack, GitHub)** | Assuming live API available in tests | Mock responses with realistic contracts, use VCR for recorded interactions |
| **File System (canvas exports)** | Writing to `/tmp/` and assuming cleanup | Use `tmp_path` fixture with automatic cleanup |
| **Redis (caching)** | Shared Redis instance causes test interference | Use separate Redis database per test (SELECT different DB) |
| **LLM Providers (OpenAI, Anthropic)** | Calling live APIs in tests (slow, expensive) | Mock streaming responses, use recorded fixtures |
| **React Native Permissions** | Assuming permission prompt behavior identical iOS/Android | Test both platforms with platform-specific mocks |
| **Browser Automation (Playwright)** | Not closing browser contexts, memory leaks | Use `@pytest.fixture` with explicit teardown in finally block |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **No test parallelization** | Test suite takes 30+ minutes, developers skip running locally | Use pytest-xdist from day one, design tests for parallel execution | 100+ integration tests |
| **Property tests with 1000 examples** | Test suite takes 1+ hour, developers disable property tests | Start with 50 examples, increase only if bug-finding justifies it | 20+ property test files |
| **Database not reset between tests** | Tests accumulate 10k+ rows, slow queries | Transaction rollback or TRUNCATE per test | 50+ tests touching database |
| **Synchronous async tests** | Tests sleep() to avoid races, 5x slower | Proper async coordination with Event/Queue | Any async endpoints |
| **No test prioritization** | Critical tests (governance) run after slow tests (UI) | Test ordering: smoke → critical → comprehensive, use pytest markers | 200+ tests |
| **Live API calls in tests** | Tests timeout on network issues, 10s+ per test | Mock external services, use VCR for contract testing | Any external API dependency |
| **Heavy fixtures (full DB dump)** | Each test spends 5s loading fixtures | Use minimal per-test fixtures, lazy loading | 50+ tests |

**Scale thresholds for Atom (current codebase size):**
- Current: 200+ test files, integration tests already showing slowdown
- Break point: 500+ tests without parallelization → CI takes >30 minutes
- Governance tests: 30+ test files, must be fast (<5 min total) for rapid iteration

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Tests using production credentials** | Accidental production data modification | Environment variable checks, fail fast if PROD=true in tests |
| **Hardcoded API keys in test fixtures** | Keys leaked in git history | Use .env.test, exclude from git, rotate keys if committed |
| **Tests bypassing authentication** | Authentication bugs not caught | Test auth flows explicitly, use test users with proper permissions |
| **Mocking security checks** | Governance bypass vulnerabilities not tested | Test security boundaries with valid/invalid permissions |
| **SQL injection in test data** | Tests themselves vulnerable | Use parameterized queries even in test data setup |
| **Agent privilege escalation tests missing** | STUDENT agents accessing AUTONOMOUS features | Property tests for maturity invariants (maturity never decreases without explicit promotion) |
| **Episode access control not tested** | User A accessing User B's episodic memories | Integration tests for multi-tenant isolation |
| **Canvas XSS not tested** | Malicious canvas components executing JS | Fuzzy tests for canvas component security, sanitize inputs |

---

## UX Pitfalls

Common user experience mistakes in testing initiatives.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **Slow feedback loops** | Developers wait 30+ min for test results, context switching | Parallel test execution, prioritize smoke tests (<2 min feedback) |
| **Flaky tests not fixed** | Developers ignore test failures, "probably just flaky" | Zero tolerance for flakiness, block merges until fixed |
| **Tests as black boxes** | Developers don't know what tests check, fear changing code | Descriptive test names, docstrings explain "what bug this catches" |
| **Coverage reports not actionable** | "82% coverage" but no guidance on what's missing | Coverage reports annotated with "critical path coverage" vs. "overall" |
| **Test failures hard to debug** | Generic assertion errors, no context | Use pytest plugins (pytest-icdiff), rich assertions, detailed error messages |
| **Mobile tests only on CI** | Mobile developers can't run tests locally, slow iteration | Mobile tests runnable on local simulator/emulator, documented setup |
| **Property test failures not explained** | "Hypothesis found counterexample" but no reproduction steps | Include shrinking output, minimal failing example in test docstring |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Coverage reports**: Often missing branch coverage → verify with `pytest --cov-branch` (line coverage hides gaps in conditionals)
- [ ] **Async tests**: Often missing proper cleanup → verify WebSocket connections closed, database sessions rolled back in finally blocks
- [ ] **Property tests**: Often missing meaningful invariants → verify each property test has documented invariants in docstring
- [ ] **Integration tests**: Often missing parallel execution verification → verify tests pass with `pytest-xdist -n auto`
- [ ] **Mobile tests**: Often missing Android verification → verify CI runs both iOS and Android simulators
- [ ] **Fuzzy tests**: Often missing error contracts → verify invalid inputs raise specific exceptions, not random crashes
- [ ] **Test data**: Often missing isolation verification → verify each test creates own data, no shared fixtures
- [ ] **Governance tests**: Often missing maturity boundary checks → verify STUDENT/INTERN/SUPERVISED/AUTONOMOUS transitions tested
- [ ] **Episodic memory tests**: Often missing lifecycle verification → verify episodes decay, consolidate, archive as expected
- [ ] **Performance tests**: Often missing baseline assertions → verify governance cache <1ms, agent resolution <50ms with pytest-benchmark

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Coverage churn (junk tests)** | HIGH (2-4 weeks rewrite) | 1. Audit all tests for assertion quality (reject trivial assertions). 2. Delete tests with <1 assertion per 20 lines. 3. Require documented "bugs this catches" for surviving tests. 4. Rebuild test suite with quality gates. |
| **Weak property tests** | MEDIUM (1-2 weeks) | 1. Identify properties with no failures after 200 examples. 2. Delete or strengthen with domain invariants. 3. Run failing examples through codebase to confirm bug detection. 4. Document invariant in test docstring. |
| **Flaky integration tests** | MEDIUM (1 week per 10 tests) | 1. Identify failing test with `pytest-xdist -n auto` to expose state sharing. 2. Add transaction wrappers around database operations. 3. Ensure unique IDs for all test data. 4. Verify cleanup in finally blocks. |
| **Async test race conditions** | MEDIUM (3-5 days) | 1. Replace all `time.sleep()` with `asyncio.Event` coordination. 2. Add explicit awaits for background tasks. 3. Use pytest-asyncio with proper fixture scoping. 4. Add timeout markers to catch hanging tests. |
| **Platform-specific mobile bugs** | HIGH (2-3 weeks) | 1. Set up dual-platform CI (iOS + Android). 2. Identify platform-specific failures (file paths, permissions). 3. Create platform-agnostic abstractions. 4. Add platform-specific fixtures. |
| **Fuzzy testing noise** | LOW (3-5 days) | 1. Review all fuzzing findings, categorize as "bug" vs. "expected". 2. Add input validation with @assume to filter invalid inputs. 3. Separate error oracle tests from invariant tests. 4. Document expected error contracts. |
| **Test data fragility** | HIGH (2-3 weeks) | 1. Implement factory_boy or similar for test data creation. 2. Replace hardcoded fixtures with factory calls. 3. Ensure each test creates own data. 4. Add schema migration testing to catch outdated assumptions. |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **Coverage churn under timeline pressure** | Phase 1: Foundation & Strategy | Coverage reports include assertion quality metric (assertions per 100 lines) |
| **Weak property tests** | Phase 2: Core Property Tests | Each property test has documented invariant, has found at least 1 bug |
| **Integration test state contamination** | Phase 3: Integration Tests | All tests pass with `pytest-xdist -n auto`, no shared fixtures |
| **Async test race conditions** | Phase 3: Integration Tests | Zero `time.sleep()` calls, all async tests use pytest-asyncio with explicit coordination |
| **React Native platform neglect** | Phase 4: Mobile Tests | CI pipeline runs both iOS and Android, platform-specific fixtures in place |
| **Fuzzy testing without oracle** | Phase 2: Core Property Tests | Error contracts documented, fuzzing findings reviewed weekly, categorized as bug/expected |
| **Test data fragility** | Phase 1: Foundation & Strategy | Factory pattern implemented, all tests create own data, zero hardcoded IDs |

**Phase-specific testing standards:**

**Phase 1: Foundation & Strategy**
- Establish test infrastructure (pytest, pytest-xdist, pytest-asyncio, factory_boy)
- Define quality gates (assertion density, critical path coverage)
- Set up dual-platform CI for mobile
- Document invariants for property tests

**Phase 2: Core Property Tests**
- Governance invariants (maturity, permissions, cache performance)
- Episodic memory invariants (segmentation, retrieval, lifecycle)
- Agent coordination invariants (multi-agent, view orchestration)
- Fuzzy tests with error contracts

**Phase 3: Integration Tests**
- API contracts (FastAPI endpoints, request/response validation)
- Database transactions (rollback, isolation, consistency)
- Async coordination (WebSocket, background tasks, agent execution)
- External service mocking (LLM providers, Slack, GitHub)

**Phase 4: Mobile Tests**
- React Native component testing (iOS + Android)
- Device capabilities (Camera, Location, Notifications)
- Platform-specific permissions (biometric, file system)
- Mobile workflow testing (offline, sync, background)

---

## Sources

### High Confidence (Official Documentation & Research)

- **[Using Hypothesis and Schemathesis to Test FastAPI](https://testdriven.io/blog/fastapi-hypothesis/)** (TestDriven.io) - Comprehensive guide on property-based testing for FastAPI with Hypothesis and Schemathesis
- **[Testing - React Native](https://reactnative.dev/docs/testing-overview)** (Official React Native Documentation, Updated Jan 16, 2026) - Official testing strategies for React Native including integration testing approaches
- **[Getting Started With Property-Based Testing in Python With Hypothesis](https://semaphore.io/blog/property-based-testing-python-hypothesis-pytest)** (Semaphore) - Detailed tutorial on implementing property-based testing with Hypothesis
- **[Let Hypothesis Break Your Python Code Before Your Users Do](https://towardsdatascience.com/let-hypothesis-break-your-python-code-before-your-users-do/)** (Towards Data Science) - Practical guide on using Hypothesis for property-based testing
- **[An Empirical Evaluation of Property-Based Testing in Python](https://dl.acm.org/doi/10.1145/3764068)** (ACM OOPSLA 2025) - Academic research identifying five challenges developers face when using property-based testing
- **[Common Pitfalls of Integration Testing in Java](https://www.atomicjar.com/2023/11/common-pitfalls-of-integration-testing-in-java/)** (AtomicJar) - Database state isolation, test data management, parallel execution challenges (applicable to Python/FastAPI)
- **[The Fuzzing Book - Reducing Failure-Inducing Inputs](https://www.fuzzingbook.org/html/Reducer.html)** - Comprehensive guide on fuzzing techniques and minimizing failure cases
- **[The Human Side of Fuzzing: Challenges Faced by Developers](https://dl.acm.org/doi/10.1145/3611668)** (ACM) - Research on bad fuzzing targets, test code issues, and implementation challenges

### Medium Confidence (Industry Articles & Blog Posts)

- **[Why high testing coverage doesn't guarantee code quality](https://www.linkedin.com/posts/alexander-chiou_techcareergrowth-softwareengineering-growthtips-activity-7388967814415458305-TT3H)** (Alexander Chiou, LinkedIn) - Discusses how 80%+ coverage requirements often lead to worst code due to coverage gaming
- **[6 Common React Native mistakes I still see in production apps](https://medium.com/@eduardofelipi/6-common-react-native-mistakes-i-still-see-in-production-apps-01bd81260628)** (Medium, Jan 2, 2026) - Testing-related issues including incomplete test coverage and platform differences
- **[React Native's 7 Deadliest Mistakes in 2026](https://yunsoft.com/blog/react-native-7-deadliest-mistakes-2026)** (Yunsoft, Jan 23, 2026) - Mentions testing issues like only testing login functionality and shipping incomplete test coverage
- **[Is fuzzing Python code worth it? Yes!](https://medium.com/cognite/is-fuzzing-python-code-worth-it-yes-862f2a9cb086)** (Cognite Medium) - Discusses value of Python fuzzing and common bugs found (AttributeErrors, out-of-bounds access)
- **[Integration Testing: Avoid Common Mistakes in 2025](https://testquality.com/integration-testing-common-mistakes-pitfalls/)** (TestQuality) - Integration testing pitfalls including test isolation and database state management
- **[FastAPI Testing Strategies to Raise Quality](https://blog.greeden.me/en/2025/11/04/fastapi-testing-strategies-to-raise-quality-pytest-testclient-httpx-dependency-overrides-db-rollbacks-mocks-contract-tests-and-load-testing/)** (Greeden.me, Nov 4, 2025) - Comprehensive FastAPI testing strategies including property-based testing and common pitfalls

### Low Confidence (Community Discussions & Forums)

- **[Hypothesis: Property-Based Testing for Python](https://news.ycombinator.com/item?id=45818562)** (Hacker News Discussion) - Community discussion noting "the property/specification needs to be quite simple compared to the implementation"
- **[Integration test fails intermittently when CI builds run concurrently](https://www.reddit.com/r/softwaretesting/comments/1on5qee/integration_test_fails_intermittently_when_ci/)** (Reddit) - Real-world example of test isolation issues causing CI failures
- **[The argument against clearing the database between tests](https://calpaterson.com/against-database-teardown.html)** - Alternative viewpoint on database state management (useful for understanding tradeoffs)

### Additional Sources Cited in Research

- **[Guide to Common Errors in Python Automated Testing](https://www.oreateai.com/blog/guide-to-common-errors-in-python-automated-testing-analysis-and-avoidance)** (January 7, 2026) - Common pitfalls in Python automated testing processes
- **[Top 10 Testing Mistakes QA Engineers Must Avoid](https://www.qabash.com/top-10-testing-mistakes-qa/)** - Inadequate test planning, insufficient coverage, ignoring automation
- **[Mastering Integration Testing: Tools, Techniques, and Common Pitfalls](https://www.linkedin.com/pulse/mastering-integration-testing-tools-techniques-common-pitfalls-cf79c)** (LinkedIn) - Integration testing challenges and best practices

---

*Pitfalls research for: Comprehensive Testing Initiative (Python/FastAPI/React Native)*
*Researched: February 10, 2026*
*Confidence: HIGH*
