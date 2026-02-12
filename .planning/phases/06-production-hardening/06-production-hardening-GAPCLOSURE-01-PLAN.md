---
phase: 06-production-hardening
plan: GAPCLOSURE-01
type: execute
gap_closure: true
wave: 1
depends_on: []
files_modified:
  - backend/tests/property_tests/analytics/test_analytics_invariants.py
  - backend/tests/property_tests/api/test_api_contracts.py
  - backend/tests/property_tests/contracts/test_action_complexity.py
  - backend/tests/property_tests/conftest.py
  - backend/tests/property_tests/database/test_database_invariants.py
  - backend/requirements.txt
  - backend/tests/COLLECTION_ERROR_INVESTIGATION.md
autonomous: true

must_haves:
  truths:
    - "Full test suite executes without blocking errors"
    - "Property test TypeErrors are resolved"
    - "Test data generation strategies are compatible with Hypothesis 6.151.5"
    - "Import paths for test fixtures are correct"
    - "Optional dependencies are documented or installed"
  artifacts:
    - path: "backend/tests/property_tests/conftest.py"
      provides: "Custom Hypothesis strategies compatible with current version"
    - path: "backend/requirements.txt"
      provides: "Documented optional dependencies (flask, mark, marko)"
    - path: "backend/tests/COLLECTION_ERROR_INVESTIGATION.md"
      provides: "Updated investigation with resolution details"
  key_links:
    - from: "pytest tests/property_tests/ -v"
      to: "zero TypeErrors during collection"
      via: "Hypothesis strategy fixes"
      pattern: "TypeError.*isinstance"
    - from: "hypothesis>=6.92.0,<7.0.0"
      to: "requirements.txt"
      via: "version constraint"
      pattern: "hypothesis"
---

<objective>
Fix property test TypeErrors causing 12,982 test failures (23.5%) by resolving Hypothesis version compatibility issues, correcting test data generation strategies, and fixing import paths for test fixtures.

**Purpose:** Gap 1 addresses the P0 blocking issue where property tests fail with TypeError during collection. The root cause is Hypothesis framework compatibility - either version mismatch or incorrect strategy usage (e.g., `st.one_of()` with incorrect types, `isinstance()` arg 2 errors). This gap closure plan will systematically identify and fix all TypeError issues in property tests.

**Output:**
- Fixed property test files with compatible Hypothesis strategies
- Updated conftest.py with corrected custom strategies
- Documented optional dependencies in requirements.txt
- Zero TypeErrors during test collection
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/06-production-hardening/06-RESEARCH.md
@.planning/phases/06-production-hardening/06-production-hardening-VERIFICATION.md
@/Users/rushiparikh/projects/atom/backend/tests/COLLECTION_ERROR_INVESTIGATION.md
@/Users/rushiparikh/projects/atom/backend/tests/property_tests/conftest.py
</context>

<tasks>

<task type="auto">
  <name>Identify All Property Test TypeErrors</name>
  <files>backend/tests/property_tests</files>
  <action>
Run property test collection to catalog all TypeError issues:

1. From backend directory, run: `pytest tests/property_tests/ -v --collect-only 2>&1 | grep -A 5 TypeError | tee tests/property_tests_typeerror_catalog.txt`

2. Parse the catalog and categorize errors by type:
   - **isinstance() arg 2 errors**: Usually from st.one_of() with incorrect types
   - **Module import errors**: Missing fixtures or incorrect import paths
   - **Strategy composition errors**: Incorrect use of st.lists(), st.dictionaries(), etc.
   - **Custom strategy errors**: Issues in conftest.py custom strategies

3. Create a spreadsheet-like categorization:
   ```markdown
   | File | Line | Error Type | Affected Strategy | Fix Approach |
   |------|------|------------|-------------------|--------------|
   | test_analytics_invariants.py | 28 | isinstance arg 2 | st.one_of() | Fix type union |
   | test_api_contracts.py | 40 | isinstance arg 2 | st.one_of() | Fix type union |
   | ...
   ```

4. Identify patterns - if most errors are the same type, prioritize fixing the root cause pattern first
  </action>
  <verify>File exists at backend/tests/property_tests_typeerror_catalog.txt containing all TypeError errors with file, line, error type, and affected strategy</verify>
  <done>All property test TypeErrors catalogued by type, location, and affected Hypothesis strategy</done>
</task>

<task type="auto">
  <name>Fix Hypothesis Strategy Type Errors</name>
  <files>backend/tests/property_tests/analytics/test_analytics_invariants.py</files>
  <action>
Fix isinstance() arg 2 errors caused by incorrect Hypothesis strategy usage:

**Root Cause Pattern:** `st.one_of()` with incompatible types causes TypeError during collection. In Hypothesis 6.x, `st.one_of()` requires all strategies to produce compatible types or be wrapped properly.

**Common Fixes:**

1. **st.one_of() with scalar and container types:**
   ```python
   # WRONG - causes isinstance arg 2 error:
   metric_value=st.one_of(
       st.integers(min_value=-1000000, max_value=1000000),
       st.floats(min_value=-1000000.0, max_value=1000000.0)
   )

   # CORRECT - use st.one_of() with compatible scalar types:
   metric_value=st.one_of(
       st.integers(min_value=-1000000, max_value=1000000),
       st.floats(min_value=-1000000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
   )
   ```

2. **Nested st.one_of() in dictionaries:**
   ```python
   # WRONG - nested one_of with incompatible dict structures:
   data=st.one_of(
       st.none(),
       st.dictionaries(
           st.text(),
           st.one_of(st.text(), st.integers(), st.lists())  # Error here
       )
   )

   # CORRECT - use st.one_of() for values with compatible output:
   data=st.one_of(
       st.none(),
       st.dictionaries(
           st.text(min_size=1, max_size=50),
           st.one_of(
               st.text(min_size=1, max_size=100),
               st.integers(min_value=0, max_value=10000),
               st.floats(min_value=0.0, max_value=10000.0),
               st.lists(st.integers(min_value=0, max_value=100))
           )
       )
   )
   ```

3. **Fix each file identified in Task 1:**
   - test_analytics_invariants.py (lines 28-31, 88, etc.)
   - test_api_contracts.py (lines 35-48, 84-92, etc.)
   - test_action_complexity.py (check all @given decorators)
   - Any other files from the TypeError catalog

4. Verify each fix by running: `pytest tests/property_tests/[file] -v --collect-only`

**Pattern:** Most errors are from `st.one_of()` where inner strategies produce incompatible types. Hypothesis tries to validate with isinstance() but the second argument is not a valid type or tuple of types.
  </action>
  <verify>All identified property test files show zero TypeErrors during collection: pytest tests/property_tests/[file] -v --collect-only</verify>
  <done>All isinstance() arg 2 errors resolved in property test files</done>
</task>

<task type="auto">
  <name>Fix Import Paths for Test Fixtures</name>
  <files>backend/tests/property_tests/conftest.py</files>
  <action>
Fix import errors in security and integration test fixtures:

1. **Review conftest.py imports:**
   - Verify all core.models imports are correct
   - Verify main_api_app import path is correct
   - Check for any circular import issues

2. **Fix common import patterns:**
   ```python
   # If import error exists for api.atom_agent_endpoints:
   # WRONG (causes ModuleNotFoundError):
   from api.atom_agent_endpoints import app

   # CORRECT:
   from main_api_app import app

   # For missing fixtures in security tests:
   # WRONG (fixture not found):
   from tests.security.conftest import secure_client

   # CORRECT - create fixture locally or use proper path:
   from tests.conftest import client  # or create fixture in conftest.py
   ```

3. **Add missing imports to conftest.py:**
   - If security tests need specific fixtures, add them to the property_tests conftest
   - Ensure all models used by tests are imported

4. **Document fixture access:** Create a comment block in conftest.py explaining:
   - Which fixtures are available
   - How to add new fixtures
   - Common patterns for database/agent fixtures

5. Run collection to verify: `pytest tests/property_tests/ -v --collect-only`
  </action>
  <verify>pytest tests/property_tests/ -v --collect-only shows zero ImportError or ModuleNotFoundError for test fixtures</verify>
  <done>All fixture import paths corrected, zero import errors during collection</done>
</task>

<task type="auto">
  <name>Document Optional Dependencies</name>
  <files>backend/requirements.txt</files>
  <action>
Document or install optional dependencies (flask, mark, marko) that cause import errors:

1. **Review import errors in test logs:**
   - Identify which files require flask, mark, or marko
   - Determine if these tests are critical or optional

2. **For each optional dependency:**

   **Option A - Install if tests are critical:**
   ```bash
   # Add to requirements.txt:
   flask>=3.0.0,<4.0.0  # Required for test_github_oauth_server.py
   marko>=1.0.0,<2.0.0  # Required for markdown rendering tests
   ```

   **Option B - Document as optional if tests are non-critical:**
   ```bash
   # Add to requirements-dev.txt:
   # Optional dependencies for specific test scenarios
   flask>=3.0.0,<4.0.0  # Optional: GitHub OAuth server tests
   marko>=1.0.0,<2.0.0  # Optional: Markdown rendering tests
   ```

   **Option C - Mark tests as skip if dependency missing:**
   ```python
   # In test file:
   import pytest

   try:
       import flask
       HAS_FLASK = True
   except ImportError:
       HAS_FLASK = False

   @pytest.mark.skipif(not HAS_FLASK, reason="flask not installed")
   def test_github_oauth():
       ...
   ```

3. **Create requirements-dev-optional.txt** for truly optional dependencies:
   ```txt
   # Optional test dependencies - not required for core test suite
   # Install with: pip install -r requirements-dev-optional.txt

   flask>=3.0.0,<4.0.0  # GitHub OAuth server tests (test_github_oauth_server.py)
   marko>=1.0.0,<2.0.0  # Markdown rendering tests
   # Add other optional dependencies as discovered
   ```

4. **Update README.md** with documentation on optional dependencies

5. **Re-run full property test collection:** `pytest tests/property_tests/ -v --collect-only`
  </action>
  <verify>requirements.txt or requirements-dev-optional.txt documents flask, mark, marko; tests either import successfully or are properly marked with @pytest.mark.skipif</verify>
  <done>All optional dependencies documented in requirements files, tests handle missing dependencies gracefully</done>
</task>

<task type="auto">
  <name>Verify All Property Tests Collect Successfully</name>
  <files>backend/tests/property_tests</files>
  <action>
Run comprehensive verification of all property test collection:

1. **Run full property test collection:**
   ```bash
   cd backend && pytest tests/property_tests/ -v --collect-only 2>&1 | tee tests/property_tests_collection_final.txt
   ```

2. **Verify zero errors:**
   - Check for "TypeError" in output - should be zero
   - Check for "ImportError" in output - should be zero
   - Check for "ModuleNotFoundError" in output - should be zero
   - Count collected tests - should match or exceed previous count

3. **Run a subset of property tests to verify execution:**
   ```bash
   # Run analytics tests (sample of fixed files):
   pytest tests/property_tests/analytics/test_analytics_invariants.py -v

   # Run API contract tests:
   pytest tests/property_tests/api/test_api_contracts.py -v

   # Run database invariants:
   pytest tests/property_tests/database/test_database_invariants.py::test_transaction_atomicity -v
   ```

4. **Document results in COLLECTION_ERROR_INVESTIGATION.md:**
   ```markdown
   ## Gap Closure Resolution (2026-02-12)

   ### TypeErrors Fixed
   - Fixed N isinstance() arg 2 errors in property tests
   - Files modified: [...]
   - Root cause: st.one_of() with incompatible types

   ### Import Errors Fixed
   - Fixed N import path errors in test fixtures
   - Files modified: conftest.py

   ### Optional Dependencies
   - Documented flask, mark, marko as optional
   - Tests skip gracefully when dependencies missing

   ### Verification
   - Collection errors: 0 (was 17)
   - Tests collected: N (was N)
   - Property tests collectable: 100%
   ```

5. **If any errors remain, iterate back to relevant task**
  </action>
  <verify>pytest tests/property_tests/ -v --collect-only completes with zero TypeError, ImportError, or ModuleNotFoundError; all tests successfully collected</verify>
  <done>All property tests collect successfully with zero errors; COLLECTION_ERROR_INVESTIGATION.md updated with resolution details</done>
</task>

</tasks>

<verification>
Run `pytest tests/property_tests/ -v --collect-only` to verify zero collection errors. Run `pytest tests/property_tests/analytics/test_analytics_invariants.py -v` and `pytest tests/property_tests/api/test_api_contracts.py -v` to verify actual test execution. Check COLLECTION_ERROR_INVESTIGATION.md for resolution documentation.
</verification>

<success_criteria>
1. pytest tests/property_tests/ -v --collect-only completes with zero TypeError
2. pytest tests/property_tests/ -v --collect-only completes with zero ImportError
3. All property tests successfully collected (same or greater count than before)
4. At least one property test file executes successfully (e.g., test_analytics_invariants.py)
5. Optional dependencies documented in requirements.txt or requirements-dev-optional.txt
6. COLLECTION_ERROR_INVESTIGATION.md updated with resolution details
</success_criteria>

<output>
After completion, create `.planning/phases/06-production-hardening/06-production-hardening-GAPCLOSURE-01-SUMMARY.md` with:
- Number of TypeError issues resolved
- Files modified with strategy fixes
- Optional dependencies documented
- Collection error count before/after (target: 0 errors)
- Sample test execution results
</output>
