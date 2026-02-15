---
phase: 10-fix-tests
plan: 07
type: execute
wave: 1
depends_on:
  - phase: 10-fix-tests
    plan: 06
    provides: Fixed agent task cancellation tests
files_modified:
  - tests/test_security_config.py
  - tests/test_agent_governance_runtime.py
  - tests/conftest.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "test_default_secret_key_in_development passes without RERUN loops (environment isolated)"
    - "test_agent_governance_gating completes without continuous RERUN (external dependencies mocked)"
    - "Security config tests use monkeypatch for environment variable isolation"
    - "Governance runtime tests mock BYOK client and governance cache"
  artifacts:
    - path: "tests/test_security_config.py"
      provides: "Isolated security configuration tests"
      min_lines: 150
    - path: "tests/test_agent_governance_runtime.py"
      provides: "Mocked governance runtime tests"
      min_lines: 80
    - path: "tests/conftest.py"
      provides: "Environment isolation fixture"
      exports: ["isolated_environment"]
  key_links:
    - from: "tests/test_security_config.py"
      to: "os.environ"
      via: "monkeypatch fixture"
      pattern: "monkeypatch.setenv|monkeypatch.delenv"
    - from: "tests/test_agent_governance_runtime.py"
      to: "core.llm.byok_handler"
      via: "AsyncMock patches"
      pattern: "patch.object.*BYOK|AsyncMock.*return_value"
    - from: "tests/test_agent_governance_runtime.py"
      to: "core/governance_cache.py"
      via: "Mock patches"
      pattern: "patch.*governance_cache"
---

<objective>
Fix remaining flaky tests: test_default_secret_key_in_development (environment isolation) and test_agent_governance_gating (external dependency mocking).

**Purpose:** These tests fail due to shared global state:
1. test_default_secret_key_in_development: Environment variable pollution between test runs
2. test_agent_governance_gating: External service dependencies (BYOK client, governance cache) not mocked

**Root Causes (from Plan 05 analysis):**
1. SecurityConfig reads os.environ at import time and caches values
2. Tests use `patch.dict(os.environ, ...)` but config instance is already cached
3. BYOK client initialization happens during module import (slow, non-deterministic)
4. No fixture to reset config cache between tests

**Output:**
- Fixed test_security_config.py with proper environment isolation
- Fixed test_agent_governance_runtime.py with mocked external dependencies
- Environment isolation fixture for tests that modify os.environ
- All 2 flaky tests passing without RERUN loops
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/10-fix-tests/10-fix-tests-05-SUMMARY.md
@.planning/phases/10-fix-tests/10-fix-tests-VERIFICATION.md

# Flaky Test Evidence (from Plan 05)

**test_default_secret_key_in_development:**
```
tests/test_security_config.py::TestSecurityConfig::test_default_secret_key_in_development RERUN [  0%]
tests/test_security_config.py::TestSecurityConfig::test_default_secret_key_in_development RERUN [  0%]
tests/test_security_config.py::TestSecurityConfig::test_default_secret_key_in_development RERUN [  0%]
tests/test_security_config.py::TestSecurityConfig::test_default_secret_key_in_development RERUN [  0%]
tests/test_security_config.py::TestSecurityConfig::test_default_secret_key_in_development FAILED [  0%]
```

**test_agent_governance_gating:**
```
tests/test_agent_governance_runtime.py::test_agent_governance_gating RERUN [  0%]
2026-02-15 14:39:15 [    INFO] Initialized BYOK client for openai
2026-02-15 14:39:15 [    INFO] Initialized BYOK client for deepseek
... (repeats indefinitely)
```

# Current Implementation Issues

**File: core/config.py**
- SecurityConfig reads os.environ in __post_init__
- Global `config = ATOMConfig.from_env()` created at import time
- `get_config()` returns cached global instance
- No reset/clear mechanism for config cache

**File: tests/test_security_config.py**
- Uses `patch.dict(os.environ, {...}, clear=False)` which doesn't affect cached config
- Tests create new SecurityConfig() instances but don't reset module-level config
- No fixture to ensure clean environment per test

**File: tests/test_agent_governance_runtime.py**
- Imports GenericAgent which triggers BYOK initialization
- BYOK client connects to external services (slow, may timeout)
- No mocks for governance cache or database state
- Database cleanup in finally block (may not execute if test times out)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix test_default_secret_key_in_development with monkeypatch fixture</name>
  <files>tests/test_security_config.py</files>
  <action>
    Replace patch.dict() usage with pytest's monkeypatch fixture for proper environment isolation.

    Changes to test_default_secret_key_in_development:
    1. Change method signature to accept `monkeypatch` fixture:
       ```python
       def test_default_secret_key_in_development(self, monkeypatch):
       ```
    2. Replace `with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=False):` with:
       ```python
       monkeypatch.setenv('ENVIRONMENT', 'development')
       monkeypatch.delenv('SECRET_KEY', raising=False)
       ```
    3. Remove `with patch.dict(...):` indentation (run at method level)
    4. Keep assertions unchanged: verify secret_key is not None and len > 20

    Also update test_automatic_key_generation_in_development:
    1. Change signature to accept `monkeypatch` fixture
    2. Replace patch.dict with monkeypatch.setenv/delenv
    3. Remove try/finally for SECRET_KEY restoration (monkeypatch auto-restores)
    4. Keep test logic and assertions unchanged

    DO NOT:
    - Change test assertions or what they verify
    - Modify other tests in the file (only fix the 2 environment-related tests)
    - Add new test cases
  </action>
  <verify>
    Run: `PYTHONPATH=. pytest tests/test_security_config.py::TestSecurityConfig::test_default_secret_key_in_development -v`
    Expected: Test passes without RERUN messages
  </verify>
  <done>
    test_default_secret_key_in_development and test_automatic_key_generation_in_development use monkeypatch for environment isolation
  </done>
</task>

<task type="auto">
  <name>Task 2: Add environment isolation fixture to conftest.py</name>
  <files>tests/conftest.py</files>
  <action>
    Add an autouse fixture that saves/restores critical environment variables to prevent pollution between tests.

    Implementation:
    1. Import `os` at top (already present)
    2. Add list of critical env vars to track:
       ```python
       _CRITICAL_ENV_VARS = ['SECRET_KEY', 'ENVIRONMENT', 'DATABASE_URL', 'ALLOW_DEV_TEMP_USERS']
       ```
    3. Add fixture after reset_agent_task_registry:
       ```python
       @pytest.fixture(autouse=True)
       def isolate_environment():
           """Isolate environment variables between tests."""
           # Save critical env vars
           saved = {}
           for var in _CRITICAL_ENV_VARS:
               if var in os.environ:
                   saved[var] = os.environ[var]

           yield

           # Restore saved env vars, delete ones that weren't set before
           for var in _CRITICAL_ENV_VARS:
               if var in saved:
                   os.environ[var] = saved[var]
               else:
                   os.environ.pop(var, None)
       ```
    4. Add docstring: prevents test pollution from environment modifications

    DO NOT:
    - Clear entire os.environ (breaks Python runtime)
    - Modify existing fixtures
    - Add vars not related to config/security
  </action>
  <verify>
    Run: `PYTHONPATH=. pytest tests/test_security_config.py -v -k "secret"`
    Expected: All secret key tests pass, no environment leakage errors
  </verify>
  <done>
    tests/conftest.py has autouse fixture that saves/restores critical environment variables
  </done>
</task>

<task type="auto">
  <name>Task 3: Mock BYOK client and governance cache in test_agent_governance_runtime.py</name>
  <files>tests/test_agent_governance_runtime.py</files>
  <action>
    Mock external dependencies (BYOK client, governance cache) to prevent slow initialization and non-deterministic behavior.

    Implementation for test_agent_governance_gating:
    1. Add imports at top:
       ```python
       from unittest.mock import patch, AsyncMock, MagicMock
       from core.governance_cache import GovernanceCache
       ```

    2. Patch BYOK client initialization to prevent real connections:
       ```python
       @patch('core.llm.byok_handler.initialize_byok_clients', return_value=None)
       @patch('core.governance_cache.GovernanceCache.get_instance')
       @pytest.mark.asyncio
       async def test_agent_governance_gating(mock_governance_cache, mock_byok_init):
           # Setup mock cache
           mock_cache_instance = MagicMock()
           mock_cache_instance.check_governance.return_value = {
               'allowed': False,
               'reason': 'Agent lacks maturity level for this action'
           }
           mock_governance_cache.return_value = mock_cache_instance

           db = SessionLocal()
           try:
               # ... rest of test unchanged ...
    ```

    3. Remove any direct BYOK client imports or initialization calls
    4. Keep test logic unchanged (still verifies governance gating behavior)

    For test_agent_learning_progression:
    1. Apply same BYOK and governance cache patches
    2. Keep existing LLM mock (agent.llm.generate_response = AsyncMock(...))
    3. Keep database cleanup logic in finally block

    DO NOT:
    - Change test assertions or what they verify
    - Remove database test data cleanup (finally block)
    - Mock the database (use real SessionLocal for integration testing)
  </action>
  <verify>
    Run: `PYTHONPATH=. pytest tests/test_agent_governance_runtime.py -v --tb=short`
    Expected: Both tests pass, no "Initialized BYOK client" log messages, no RERUN loops
  </verify>
  <done>
    test_agent_governance_gating and test_agent_learning_progression use mocked BYOK and governance cache
  </done>
</task>

</tasks>

<verification>
After completion, verify:

1. Run test_security_config.py in isolation:
   ```bash
   PYTHONPATH=. pytest tests/test_security_config.py -v --tb=short
   ```
   Expected: All tests pass, no RERUN messages for environment tests

2. Run test_agent_governance_runtime.py in isolation:
   ```bash
   PYTHONPATH=. pytest tests/test_agent_governance_runtime.py -v --tb=short
   ```
   Expected: Both tests pass, no BYOK initialization logs, no continuous RERUN

3. Run all previously flaky tests together:
   ```bash
   PYTHONPATH=. pytest tests/test_agent_cancellation.py tests/test_security_config.py tests/test_agent_governance_runtime.py -v --tb=short
   ```
   Expected: All 19 tests pass, no RERUN messages, tests complete in <30 seconds

4. Run tests 3 times to verify no flakiness:
   ```bash
   for i in 1 2 3; do PYTHONPATH=. pytest tests/test_security_config.py::TestSecurityConfig::test_default_secret_key_in_development tests/test_agent_governance_runtime.py::test_agent_governance_gating -q; done
   ```
   Expected: Identical pass count (2 passed) for all 3 runs
</verification>

<success_criteria>
1. test_default_secret_key_in_development passes without RERUN loops
2. test_agent_governance_gating completes without continuous RERUN
3. Tests pass consistently across 3 consecutive runs (0 variance)
4. No BYOK client initialization log messages during test runs
5. Environment isolation fixture saves/restores critical env vars
</success_criteria>

<output>
After completion, create `.planning/phases/10-fix-tests/10-fix-tests-07-SUMMARY.md`

Include:
- Flaky tests fixed (test_default_secret_key_in_development, test_agent_governance_gating)
- Number of RERUN loops eliminated (target: 0)
- Test execution time improvement (target: <30 seconds for 19 tests)
- Files modified with commit references
</output>
