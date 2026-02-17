# Pitfalls Research: AI/LLM Testing for Atom Platform

**Domain:** AI/LLM Testing for Multi-Agent Platform
**Researched:** February 16, 2026
**Confidence:** MEDIUM (based on codebase analysis, existing testing patterns, and AI testing knowledge)

---

## Executive Summary

AI/LLM testing projects commonly fail by treating LLM applications like traditional software. The key pitfalls specific to AI systems: **over-mocking LLM responses**, **ignoring non-determinism**, **testing only happy paths**, **coverage vanity** (100% of trivial code, 0% of critical paths), and **missing governance-dependent behavior**.

For Atom's 80% test coverage initiative, the most critical pitfalls are:
1. **Over-mocking LLM responses** → tests pass but production breaks
2. **Flaky tests from non-determinism** → CI becomes unreliable
3. **Ignoring maturity-dependent behavior** → governance violations in production
4. **Testing only happy paths** → failure modes untested
5. **Coverage vanity** → high coverage, low actual protection

---

## Critical Pitfalls

### Pitfall 1: Over-Mocking LLM Responses

**What goes wrong:**
Tests mock LLM responses with static, perfect outputs. All tests pass, but production fails because:
- Mocks don't match actual LLM behavior (formatting, edge cases, API changes)
- Tests never validate prompt engineering quality
- LLM provider changes break production (tests stay green)
- Integration issues (rate limits, timeouts, tokens) never tested

**Why it happens:**
- Mocking is faster (no API calls, no costs)
- Mocks are deterministic (no flaky tests)
- Developers want to avoid API rate limits during CI
- Mocks are easier to control than probabilistic outputs

**Consequences:**
- False confidence in system reliability
- Production issues that tests never caught
- Prompt engineering regressions
- LLM provider API changes cause outages

**How to avoid:**
1. **Three-tier testing strategy**:
   - **Unit tests**: Mock LLM responses (fast, deterministic)
   - **Integration tests**: Use real LLM with `temperature=0` (deterministic-ish)
   - **E2E tests**: Sample real LLM outputs (probabilistic, use statistical assertions)

2. **Use evaluation datasets**, not fixed mocks:
   ```python
   # BAD: Static mock
   mock_llm.return_value = "Perfect response every time"

   # GOOD: Evaluation dataset with real LLM outputs
   EVALUATION_DATASET = [
       {"input": "What's the weather?", "output_variants": [...]},
       {"input": "Summarize this doc", "output_variants": [...]}
   ]
   ```

3. **Version prompts and test against regression**:
   ```python
   def test_prompt_regression():
       response = call_llm(prompt_v1, input)
       assert semantic_similarity(response, expected) > 0.85
   ```

4. **Golden dataset testing**: Maintain a dataset of real LLM responses, test semantic similarity

**Warning signs:**
- All LLM tests use `@patch` or `Mock()`
- Test suite has 100% pass rate but production has frequent LLM issues
- No tests call actual LLM APIs
- Prompt changes never require test updates

**Phase to address:**
- **Phase 01**: Establish three-tier testing strategy with golden dataset
- **Phase 03**: Add LLM integration tests with temperature=0
- **Phase 05**: Add statistical E2E tests for probabilistic outputs

---

### Pitfall 2: Flaky Tests from Non-Deterministic AI Behavior

**What goes wrong:**
LLM tests fail intermittently due to:
- Same input produces different outputs (temperature > 0)
- Race conditions in async agent execution
- Network latency affecting streaming responses
- Rate limiting in external APIs
- Database state not isolated between tests

**Why it happens:**
- LLMs are inherently probabilistic
- Async code introduces timing variability
- External services (Slack, Asana, GitHub) have rate limits
- Tests don't properly isolate database state

**Consequences:**
- CI becomes unreliable (tests fail randomly)
- Developers lose trust in test suite
- Flaky tests get disabled or ignored
- Real bugs get masked by "known flakiness"

**How to avoid:**
1. **Control randomness explicitly**:
   ```python
   # For unit/integration tests, force determinism
   response = call_llm(prompt, temperature=0.0, seed=42)

   # For E2E tests, use statistical assertions
   results = [call_llm(prompt) for _ in range(10)]
   assert mean(passing(results)) > 0.8  # 80% pass rate acceptable
   ```

2. **Isolate database state per test**:
   ```python
   @pytest.fixture(scope="function")
   def db_session():
       # Use temp file-based SQLite, not :memory: (see conftest.py)
       ...
   ```

3. **Mock external services with realistic rate limits**:
   ```python
   # Don't mock all responses
   # Mock with realistic delays and rate limits
   mock_slack = MockSlackService(
       rate_limit=100,  # requests per minute
       latency_ms=(50, 200)  # realistic jitter
   )
   ```

4. **Use Hypothesis for property-based tests** (already in place):
   ```python
   @given(confidence=st.floats(min_value=0.0, max_value=1.0))
   @settings(max_examples=200)
   def test_confidence_bounds(confidence):
       assert 0.0 <= confidence <= 1.0
   ```

5. **Mark flaky tests explicitly**:
   ```python
   @pytest.mark.flaky(max_runs=3, min_passes=1)
   def test_probabilistic_llm_output():
       # Accept 1/3 pass rate for highly non-deterministic tests
   ```

**Warning signs:**
- CI fails randomly with same commit
- Developers retry tests until they pass
- Tests pass locally but fail in CI
- "It works on my machine" is common excuse

**Phase to address:**
- **Phase 01**: Fix database isolation (already done in property tests conftest.py)
- **Phase 02**: Add explicit randomness controls (temperature=0, seeds)
- **Phase 04**: Mock external services with realistic behavior
- **Phase 05**: Add statistical testing for truly non-deterministic behaviors

---

### Pitfall 3: Ignoring Maturity-Dependent Agent Behavior

**What goes wrong:**
Tests create agents with one maturity level (usually AUTONOMOUS) and never validate:
- STUDENT agents blocked from dangerous actions
- INTERN agents require approval for state changes
- SUPERVISED agents run under real-time supervision
- Maturity transitions follow graduation rules

**Why it happens:**
- Easier to test with AUTONOMOUS agents (no governance friction)
- Tests focus on "does it work?" not "who can do it?"
- Governance logic is boring compared to agent behavior
- Developers forget agents have different permission levels

**Consequences:**
- STUDENT agents perform destructive actions in production
- Governance bypass vulnerabilities
- Privilege escalation attacks
- Graduation framework never tested

**How to avoid:**
1. **Test all maturity levels for critical actions**:
   ```python
   @pytest.mark.parametrize("maturity", [
       AgentStatus.STUDENT,
       AgentStatus.INTERN,
       AgentStatus.SUPERVISED,
       AgentStatus.AUTONOMOUS
   ])
   def test_delete_action_maturity_gated(maturity):
       agent = create_agent(maturity)
       result = agent.execute("delete", resource_id="x")

       if maturity == AgentStatus.STUDENT:
           assert result["allowed"] == False
       elif maturity == AgentStatus.AUTONOMOUS:
           assert result["allowed"] == True
   ```

2. **Property-based testing for governance** (already implemented):
   - `tests/property_tests/agent_governance/test_governance_invariants.py`
   - Tests all maturity levels against all action types
   - Uses Hypothesis to generate random maturity/action combinations

3. **Test graduation scenarios**:
   ```python
   def test_student_to_intern_graduation():
       agent = create_student_agent()
       # Execute 10 safe actions
       for _ in range(10):
           agent.execute("read", resource_id="x")

       # Verify graduation criteria met
       assert agent.can_graduate_to("INTERN") == True
   ```

4. **Test governance bypass attempts**:
   ```python
   def test_governance_cannot_be_bypassed():
       student_agent = create_student_agent()

       # Try direct execution (bypassing governance)
       with pytest.raises(PermissionError):
           student_agent._unsafe_execute("delete", resource_id="x")
   ```

**Warning signs:**
- All test agents are AUTONOMOUS
- No tests check for "permission denied" or "governance blocked"
- Graduation framework has no tests
- Property tests fail with "maturity level X shouldn't allow action Y"

**Phase to address:**
- **Phase 01**: Audit all tests for maturity level diversity
- **Phase 02**: Add maturity-parametrized tests for all critical actions
- **Phase 04**: Test graduation framework end-to-end
- **Phase 05**: Security audit for governance bypass

---

### Pitfall 4: Testing Only Happy Paths (Not Failure Modes)

**What goes wrong:**
Tests only validate "everything works correctly":
- LLM returns valid response
- Database queries succeed
- External APIs are available
- Agents have required permissions

**Why it happens:**
- Happy paths are easy to test
- Error handling is tedious to set up
- Tests written during development when everything works
- "I'll add error tests later" (never happens)

**Consequences:**
- Production errors crash system instead of graceful degradation
- Error messages are unhelpful
- Users see stack traces instead of friendly errors
- Recovery paths never tested

**How to avoid:**
1. **Test failure modes for every critical path**:
   ```python
   def test_llm_timeout_handling():
       with patch('llm.call', side_effect=TimeoutError):
           response = agent.execute("analyze", data={...})
           assert response["status"] == "timeout"
           assert response["retry_after"] is not None

   def test_llm_rate_limit_handling():
       with patch('llm.call', side_effect=RateLimitError):
           response = agent.execute("analyze", data={...})
           assert response["status"] == "rate_limited"
           assert response["retry_after"] > 0
   ```

2. **Test graceful degradation**:
   ```python
   def test_agent_degrades_gracefully_when_llm_unavailable():
       agent = create_agent()

       with patch('agent.llm', side_effect=ConnectionError):
           result = agent.process(request)

           # Should use cached response or fallback
           assert result["source"] in ["cache", "fallback", "error"]
           assert result["error"] is not None
   ```

3. **Test external service failures**:
   ```python
   @pytest.mark.parametrize("failure", [
       "timeout", "rate_limit", "auth_error", "server_error"
   ])
   def test_slack_integration_handles_failures(failure):
       slack_mock = MockSlackService(failure_mode=failure)
       result = workflow.execute_step("send_slack_message", slack_mock)

       assert result["success"] == False
       assert result["retryable"] is not None
       assert result["error_code"] is not None
   ```

4. **Test governance rejection paths**:
   ```python
   def test_student_agent_rejected_from_critical_action():
       student = create_student_agent()
       result = student.execute("delete_user", user_id="x")

       assert result["allowed"] == False
       assert "STUDENT" in result["reason"]
       assert result["suggestion"] == "Upgrade agent maturity"
   ```

**Warning signs:**
- Test suite has >90% pass rate with no failure tests
- No tests use `side_effect=Exception`
- Error handling code added but never tested
- "We'll test error handling in production"

**Phase to address:**
- **Phase 02**: Add failure mode tests for all critical paths
- **Phase 03**: Add external service failure tests
- **Phase 04**: Add graceful degradation tests
- **Phase 05**: Chaos engineering (inject failures in production-like environment)

---

### Pitfall 5: Coverage Vanity (100% of Trivial Code, 0% of Critical Paths)

**What goes wrong:**
Test coverage metrics show 80-90%, but critical paths are untested:
- Data models have 100% coverage (simple getters/setters)
- Agent execution logic has 20% coverage (complex async flows)
- LLM integration has 10% coverage (hard to test)
- Governance checks have 50% coverage (boring to test)

**Why it happens:**
- Coverage metrics reward easy tests (models, DTOs, utils)
- Complex code (async, LLM, multi-agent) is hard to test
- Developers chase coverage numbers, not protection
- "80% coverage" sounds good but hides gaps

**Consequences:**
- High coverage metric, low actual protection
- Critical bugs in production despite "good" coverage
- False sense of security
- Wasted effort testing trivial code

**How to avoid:**
1. **Focus on critical path coverage, not overall percentage**:
   ```python
   # Define critical paths (code, not files)
   CRITICAL_PATHS = [
       "core/agent_governance_service.py:can_perform_action",
       "core/llm/byok_handler.py:call_llm",
       "tools/browser_tool.py:execute",
       "core/episode_segmentation_service.py:segment_episode"
   ]

   # Require 90% coverage for CRITICAL_PATHS only
   # Allow 50% for utility code
   ```

2. **Use coverage targets per module type**:
   - **Core services** (governance, LLM, episodic memory): 90%
   - **Tools** (browser, device, canvas): 80%
   - **API routes**: 70%
   - **Models/DTOs**: 50% (lots of boilerplate)
   - **Utils/helpers**: 60%

3. **Track "business logic coverage" separately**:
   ```python
   # Use pytest markers to identify business logic tests
   @pytest.mark.business_logic
   def test_agent_governance_blocks_dangerous_actions():
       ...

   # Require 100% of business logic paths covered
   # Don't care about utils/models coverage
   ```

4. **Manual audit of uncovered lines**:
   ```bash
   # Generate coverage report
   pytest --cov=core --cov-report=html

   # Manually review htmlcov/index.html
   # Focus on:
   # - Red lines in critical services
   # - Yellow lines in governance logic
   # - Ignore red lines in models/utils
   ```

5. **Use pytest markers to prioritize test gaps**:
   ```python
   @pytest.mark.coverage_gap(module="governance", priority="high")
   def test_graduation_validation():
       # Test uncovered graduation logic
   ```

**Warning signs:**
- Coverage report shows 80% but production has frequent bugs
- Most tests are for models, DTOs, and utils
- Critical services (governance, LLM) have low coverage
- "We hit our coverage target!" but system feels fragile

**Phase to address:**
- **Phase 01**: Audit coverage by module type, identify critical gaps
- **Phase 02**: Prioritize testing high-risk, low-coverage areas
- **Phase 03**: Establish per-module coverage targets
- **Phase 05**: Continuous coverage gap analysis in CI

---

## Moderate Pitfalls

### Pitfall 6: Property-Based Tests with Wrong Invariants

**What goes wrong:**
Property-based tests (Hypothesis) verify invariants that are:
- Too specific to current implementation (brittle)
- Trivially true (confidence_score >= 0)
- Not actually required (artificial constraints)
- Conflict with business requirements

**Why it happens:**
- Property-based testing is new to many developers
- Easy to pick "obvious" invariants that aren't meaningful
- Hard to identify genuine system invariants
- Pressure to add property tests without deep thought

**Consequences:**
- Tests give false confidence
- Refactoring becomes impossible (invariants too specific)
- Tests fail when requirements change (invariants were wrong)

**How to avoid:**
1. **Focus on business-critical invariants** (already done well):
   - Agent maturity hierarchy (STUDENT < INTERN < SUPERVISED < AUTONOMOUS)
   - Confidence score bounds [0.0, 1.0]
   - Governance decisions are deterministic for same inputs
   - Action complexity matrix enforcement

2. **Avoid implementation-specific invariants**:
   ```python
   # BAD: Tests internal cache structure
   def test_cache_has_exact_keys():
       assert cache._data.keys() == {"governance", "maturity"}

   # GOOD: Tests cache behavior
   def test_cache_returns_same_decision_for_same_key():
       decision1 = cache.get("agent_1", "delete")
       decision2 = cache.get("agent_1", "delete")
       assert decision1 == decision2
   ```

3. **Review invariants quarterly** with business stakeholders:
   - "Is this invariant actually required?"
   - "Has this invariant changed since we defined it?"
   - "Are we missing critical invariants?"

**Warning signs:**
- Property tests fail after refactoring (even if behavior is correct)
- Invariants reference internal implementation details (_private methods)
- Developers want to delete property tests

**Phase to address:**
- **Phase 03**: Audit existing property tests for implementation specificity
- **Phase 04**: Business stakeholder review of invariants
- **Phase 05**: Add missing critical invariants

---

### Pitfall 7: Integration Tests Too Slow/Brittle

**What goes wrong:**
Integration tests:
- Take hours to run (test real LLMs, databases, APIs)
- Fail due to external issues (Slack API down, network flaky)
- Require complex setup (test accounts, OAuth tokens)
- Unreliable in CI (random failures)

**Why it happens:**
- Easy to write integration tests (just call real services)
- No mocking required (appears simpler)
- "Real tests are better than mocks"
- No thought given to test isolation

**Consequences:**
- Developers stop running tests locally (too slow)
- CI takes hours, slowing development
- Tests disabled due to flakiness
- Fast feedback lost

**How to avoid:**
1. **Test pyramid: 70% unit, 20% integration, 10% E2E**:
   - Unit tests: No external services, <100ms each
   - Integration tests: Mock external services, <1s each
   - E2E tests: Real services, <10s each, run in separate CI job

2. **Use Testcontainers for databases** (already done with temp SQLite):
   ```python
   # Fast, isolated databases per test
   @pytest.fixture
   def db_session():
       # Temp file-based SQLite (see conftest.py)
       ...
   ```

3. **Mock external APIs in integration tests**:
   ```python
   # Use realistic mocks, not real APIs
   @pytest.fixture
   def mock_slack_api():
       with patch('integrations.slack.SlackClient') as mock:
           mock.send_message.return_value = {"ok": True, "ts": "12345"}
           yield mock
   ```

4. **Run slow tests separately**:
   ```bash
   # Fast tests (run on every commit)
   pytest tests/unit/ tests/property_tests/ -m "not slow"

   # Integration tests (run on merge to main)
   pytest tests/integration/ -m "integration"

   # E2E tests (run nightly)
   pytest tests/e2e/ -m "slow"
   ```

5. **Use pytest markers** to categorize tests:
   ```python
   @pytest.mark.unit
   def test_governance_logic():
       ...

   @pytest.mark.integration
   @pytest.mark.slow
   def test_slack_api_integration():
       ...

   @pytest.mark.e2e
   @pytest.mark.slow
   def test_full_workflow_execution():
       ...
   ```

**Warning signs:**
- Test suite takes >30 minutes to run
- Developers skip tests locally
- CI pipeline frequently fails due to external issues
- "We'll just fix that test later" (it gets disabled)

**Phase to address:**
- **Phase 02**: Categorize tests by speed (unit/integration/e2e)
- **Phase 03**: Move slow tests to separate CI job
- **Phase 04**: Add realistic mocks for external services
- **Phase 05**: Optimize test parallelization

---

## Minor Pitfalls

### Pitfall 8: Not Testing Security Boundaries

**What goes wrong:**
Security-critical paths untested:
- Shell injection in local agent execution
- Docker sandbox escape in community skills
- Webhook spoofing in IM adapters
- SQL injection in database queries
- XSS in canvas presentations

**Why it happens:**
- Security tests are niche (require security expertise)
- "Security is handled by framework"
- Hard to test without security knowledge
- Pressure to ship features, not find vulnerabilities

**Consequences:**
- Security vulnerabilities in production
- Data breaches, privilege escalation
- Compliance failures (HIPAA, SOC2)
- Customer churn due to security incidents

**How to avoid:**
1. **Security test suite** (see `tests/security/`):
   ```python
   def test_shell_command_injection_blocked():
       student_agent = create_student_agent()

       with pytest.raises(PermissionError):
           student_agent.execute("shell", command="rm -rf /")

   def test_docker_sandbox_cannot_escape():
       skill = create_community_skill("malicious_skill")
       result = skill.execute("escape_sandbox")

       assert result["success"] == False
       assert "sandbox" in result["error"].lower()
   ```

2. **Fuzz testing for user inputs**:
   ```python
   from hypothesis import given, strategies as st

   @given(user_input=st.text())
   def test_shell_input_sanitized(user_input):
       agent = create_agent()
       result = agent.execute("shell", command=user_input)

       # Should reject or sanitize all shell inputs
       assert ";" not in result["command"]
       assert "|" not in result["command"]
       assert "$(" not in result["command"]
   ```

3. **OWASP Top 10 test coverage**:
   - Injection (SQL, shell, command)
   - Broken authentication
   - XSS in canvas/webhook payloads
   - CSRF in API routes
   - Security misconfiguration

4. **Dependency scanning**:
   ```bash
   # Run security scans in CI
   pip-audit
   bandit -r core/
   safety check
   ```

**Warning signs:**
- No `tests/security/` directory
- No fuzz testing for user inputs
- Security audits find vulnerabilities
- "We'll test security later" (never happens)

**Phase to address:**
- **Phase 02**: Add security test suite for high-risk areas
- **Phase 04**: Fuzz testing for all user inputs
- **Phase 05**: Third-party security audit

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| **Mock all LLM calls** | Fast tests, no API costs | Missed integration issues, prompt regression | Never - use three-tier testing |
| **Test only AUTONOMOUS agents** | Fewer test cases | Governance violations in production | Never - test all maturity levels |
| **Skip error path testing** | Faster test writing | Crashes in production | Never - test failure modes |
| **Chase overall coverage %** | Good metrics | Critical paths untested | Never - use critical path coverage |
| **Ignore flaky tests** | Tests appear to pass | Unreliable CI, ignored failures | Never - fix or mark as flaky |
| **Use real external APIs in tests** | Realistic tests | Slow, flaky, expensive | Only in separate E2E suite |
| **Test database with :memory:** | Fast tests | Connection isolation issues | Never - use temp file-based DB (already done) |
| **Hard-coded test data** | Simple tests | Edge cases missed | For simple smoke tests only |
| **Skip property tests** | Faster test writing | Invariant violations | Never - property tests critical for governance |
| **Ignore coverage gaps in complex code** | Hit coverage targets faster | Bugs in production | Never - prioritize complex code coverage |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **LLM Providers** (OpenAI, Anthropic) | Mock all responses, test only happy path | Three-tier testing: unit (mocks) + integration (temperature=0) + E2E (statistical) |
| **Database** (SQLite, PostgreSQL) | Use `:memory:` (connection isolation issues) | Use temp file-based SQLite (see `tests/property_tests/conftest.py`) |
| **External APIs** (Slack, Asana, GitHub) | Call real APIs in CI (slow, flaky, expensive) | Mock with realistic behavior, E2E tests in separate job |
| **Browser Automation** (Playwright) | Skip browser tests (too complex) | Use Dockerized Playwright, mock CDP where possible |
| **WebSocket** (real-time communication) | Don't test async message flows | Use `pytest-asyncio` + TestWebSocket client |
| **LanceDB** (vector database) | Skip vector search tests | Use temp LanceDB instance, test with real embeddings |
| **OAuth** (Slack, Asana, GitHub) | Hard-coded tokens in tests | Mock OAuth flows, test token validation logic only |
| **File Storage** (local, S3) | Don't test file operations | Use temp directories, mock S3 for unit tests |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Tests hit real LLM APIs** | CI takes hours, API costs high | Mock LLM responses in 90% of tests | Immediately - every test run is slow/expensive |
| **Database not isolated between tests** | Tests pass locally, fail in CI | Use temp file-based DB per test (already done) | At 100+ tests, race conditions emerge |
| **No test parallelization** | CI takes 30+ minutes | Use `pytest-xdist` to parallelize | At 500+ tests, CI becomes unusable |
| **External API calls in tests** | Flaky tests, rate limits | Mock all external APIs in unit/integration tests | Immediately - external services are unreliable |
| **Property tests with too many examples** | Test suite takes hours | Use `max_examples=50` in CI, 200 locally | At 10+ property tests |
| **E2E tests run on every commit** | Feedback loop too slow | Run E2E tests on merge to main, not every PR | At 5+ E2E tests |
| **No test prioritization** | Critical bugs caught late | Run high-priority tests first (pytest-ordering) | At 1000+ tests, slowest tests block feedback |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Test credentials in codebase** | Credential leakage, account takeover | Use environment variables, never commit secrets |
| **Shell injection not tested** | RCE via agent commands | Fuzz test all shell inputs, block dangerous commands |
| **Docker sandbox escape not tested** | Community skills escape sandbox | Try to escape sandbox in tests, verify blocked |
| **Webhook spoofing not tested** | Fake events from malicious actors | Test webhook signature validation |
| **SQL injection not tested** | Database breach | Fuzz test all database inputs, use parameterized queries |
| **XSS in canvas not tested** | User sessions hijacked | Test canvas HTML sanitization, CSP headers |
| **Authentication bypass not tested** | Unauthorized access | Test all routes require auth, test token validation |
| **Governance bypass not tested** | Privilege escalation | Test all maturity levels, try to bypass governance |

---

## "Looks Done But Isn't" Checklist

- [ ] **LLM Integration**: Often missing real API calls — verify integration tests call actual LLMs (with temperature=0)
- [ ] **Governance Testing**: Often missing maturity level diversity — verify tests cover STUDENT/INTERN/SUPERVISED/AUTONOMOUS
- [ ] **Error Handling**: Often missing failure modes — verify every critical path has error tests
- [ ] **Property Tests**: Often testing trivial invariants — verify invariants are business-critical
- [ ] **Security**: Often missing input validation — verify fuzz testing for user inputs
- [ ] **Performance**: Often missing load testing — verify tests don't become CI bottleneck
- [ ] **E2E Tests**: Often running on every commit — verify E2E tests run in separate job
- [ ] **Coverage**: Often missing critical paths — manually audit htmlcov/ for red lines in critical services
- [ ] **Async Testing**: Often missing proper async test patterns — verify use of `pytest-asyncio`
- [ ] **Database Isolation**: Often using `:memory:` SQLite — verify temp file-based DB (see conftest.py)

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Over-mocked LLM tests** | MEDIUM (1-2 weeks) | 1. Add integration tests with real LLM (temperature=0) <br> 2. Create golden dataset of real responses <br> 3. Add semantic similarity assertions |
| **Flaky tests from non-determinism** | LOW (1 week) | 1. Add explicit randomness controls (temperature=0, seeds) <br> 2. Fix database isolation (use temp file DB) <br> 3. Mark truly flaky tests with `@pytest.mark.flaky` |
| **Missing maturity testing** | HIGH (2-3 weeks) | 1. Parametrize all critical tests by maturity level <br> 2. Add governance bypass attempts <br> 3. Test graduation framework |
| **Only happy paths tested** | MEDIUM (2 weeks) | 1. Add failure mode tests for all critical paths <br> 2. Test external service failures <br> 3. Test graceful degradation |
| **Coverage vanity** | MEDIUM (1-2 weeks) | 1. Audit coverage by module type <br> 2. Focus on critical path coverage <br> 3. Use per-module coverage targets |
| **Property tests with wrong invariants** | MEDIUM (1 week) | 1. Review invariants with business stakeholders <br> 2. Remove implementation-specific invariants <br> 3. Add missing critical invariants |
| **Integration tests too slow** | HIGH (2-3 weeks) | 1. Categorize tests by speed (unit/integration/e2e) <br> 2. Mock external APIs in integration tests <br> 3. Move slow tests to separate CI job |
| **Security boundaries not tested** | HIGH (3-4 weeks) | 1. Add security test suite (tests/security/) <br> 2. Fuzz test all user inputs <br> 3. Run dependency scanning in CI <br> 4. Third-party security audit |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **Over-mocking LLM responses** | Phase 01 (three-tier strategy) | Integration tests call real LLMs, golden dataset exists |
| **Flaky tests from non-determinism** | Phase 01 (database isolation) | All tests use temp file DB, explicit randomness controls |
| **Ignoring maturity-dependent behavior** | Phase 01 (maturity-parametrized tests) | All critical tests have maturity parameter |
| **Testing only happy paths** | Phase 02 (failure mode tests) | Every critical path has error test |
| **Coverage vanity** | Phase 01 (critical path audit) | Per-module coverage targets, critical path coverage tracked |
| **Property tests with wrong invariants** | Phase 03 (invariant review) | Business stakeholder review, no implementation-specific invariants |
| **Integration tests too slow** | Phase 02 (test categorization) | Tests marked by speed, slow tests in separate CI job |
| **Security boundaries not tested** | Phase 02 (security test suite) | Fuzz testing for user inputs, dependency scanning in CI |

---

## Sources

**Confidence: MEDIUM** - Based on codebase analysis, existing testing patterns (property tests, API testing guide), and general AI/LLM testing knowledge. Web search was not functional during research, so findings are based on:
- Codebase analysis (existing test patterns, property tests, API testing guide)
- Known AI/LLM testing challenges (non-determinism, mocking, coverage vanity)
- Atom platform architecture (multi-agent governance, maturity levels, LLM integration)
- Industry best practices (three-tier testing, property-based testing, security testing)

**Key Resources:**
- `tests/property_tests/README.md` - Property-based testing patterns (HIGH confidence)
- `tests/property_tests/conftest.py` - Database isolation patterns (HIGH confidence)
- `tests/property_tests/agent_governance/test_governance_invariants.py` - Governance testing patterns (HIGH confidence)
- `docs/API_TESTING_GUIDE.md` - API testing best practices (HIGH confidence)
- `docs/CODE_QUALITY_STANDARDS.md` - Testing standards and patterns (HIGH confidence)
- `docs/INCOMPLETE_IMPLEMENTATIONS.md` - Test coverage tracking (HIGH confidence)

**Missing External Verification:**
Due to web search tool limitations, could not verify against:
- Current LLM testing best practices (2025-2026)
- Industry case studies on AI testing failures
- Hypothesis library latest documentation
- Property-based testing patterns for AI systems

**Recommendations:**
- Phase 1 should include external research validation
- Review AI testing conference papers (NeurIPS, ICML)
- Check LangSmith, DeepEval, Promptfoo documentation for current patterns

---

*Pitfalls research for: AI/LLM Testing for Multi-Agent Platform*
*Researched: February 16, 2026*
*Next Review: After Phase 1 completion*
