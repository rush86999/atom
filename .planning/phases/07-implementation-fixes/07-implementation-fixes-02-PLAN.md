---
phase: 07-implementation-fixes
plan: 02
subsystem: test-collection-fixes
type: execute
wave: 3
depends_on:
  - pytest_xdist_test_isolation_research.md
files_modified:
  - backend/tests/test_performance_baseline.py
  - backend/tests/integration/test_auth_flows.py
  - backend/tests/integration/episodes/test_episode_lifecycle_lancedb.py
  - backend/tests/property_tests/episodes/test_episode_segmentation_invariants.py
  - backend/tests/property_tests/episodes/test_agent_graduation_invariants.py
  - backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py
  - backend/tests/property_tests/database/test_database_invariants.py
  - backend/tests/property_tests/state/test_state_invariants.py
  - backend/tests/property_tests/events/test_event_invariants.py
  - backend/tests/property_tests/files/test_file_invariants.py
  - backend/tests/unit/episodes/test_episode_segmentation_service.py
  - backend/pytest.ini
  - backend/tests/PERFORMANCE_BASELINE.md
autonomous: true

must_haves:
  truths:
    - "All 17 collection errors are fixed or tests renamed to .broken"
    - "pytest tests/ --collect-only shows 0 errors and 7324+ items collected"
    - "All 7,324 tests can be collected and run successfully"
    - "pytest-xdist parallel execution works with -n auto flag"
    - "TypeError root cause investigated and documented"
    - "Rollback strategy defined for unfixable tests"
  artifacts:
    - path: "backend/tests/test_performance_baseline.py"
      provides: "Fixed pytest marker reference or renamed to .broken"
    - path: "backend/tests/integration/test_auth_flows.py"
      provides: "Fixed import path from api.atom_agent_endpoints to correct module"
    - path: "backend/tests/integration/episodes/test_episode_lifecycle_lancedb.py"
      provides: "Fixed syntax error in fixture name (spaces not allowed)"
    - path: "backend/tests/property_tests/episodes/test_episode_segmentation_invariants.py"
      provides: "Added missing 'example' import from hypothesis"
    - path: "backend/tests/property_tests/episodes/test_agent_graduation_invariants.py"
      provides: "Added missing 'example' import from hypothesis"
    - path: "backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py"
      provides: "Added missing 'example' import from hypothesis"
    - path: "backend/tests/property_tests/database/test_database_invariants.py"
      provides: "Fixed TypeError or missing imports from hypothesis"
    - path: "backend/tests/property_tests/state/test_state_invariants.py"
      provides: "Fixed TypeError or missing imports from hypothesis"
    - path: "backend/tests/property_tests/events/test_event_invariants.py"
      provides: "Fixed TypeError or missing imports from hypothesis"
    - path: "backend/tests/property_tests/files/test_file_invariants.py"
      provides: "Fixed TypeError or missing imports from hypothesis"
    - path: "backend/tests/unit/episodes/test_episode_segmentation_service.py"
      provides: "Fixed async/await syntax error (await outside async function)"
    - path: "backend/pytest.ini"
      provides: "Added 'fast' marker configuration if needed"
    - path: "backend/tests/coverage_reports/metrics/performance_baseline.json"
      provides: "Updated with parallel execution baseline metrics"
    - path: "backend/tests/PERFORMANCE_BASELINE.md"
      provides: "Documented parallel execution performance baseline"
  key_links:
    - from: "pytest.ini"
      to: "test_performance_baseline.py"
      via: "Marker configuration allows test to run"
    - from: "All property tests"
      to: "pytest-xdist execution"
      via: "Fixed imports allow collection and parallel execution"
    - from: "TypeError investigation"
      to: "All property tests"
      via: "Root cause analysis guides comprehensive fix strategy"

---

<objective>
Fix all 17 collection errors blocking test execution, enabling all 7,324 tests to be collected and run successfully with pytest-xdist parallel execution.

**Purpose:** Phase 6 research identified that the reported low test pass rate was caused by collection/import errors, not runtime isolation failures. This plan fixes all collection errors to unblock test execution.

**Key Changes from Previous Plan:**
- Wave changed from 1 to 3 for parallel execution of independent fixes
- Added TypeError investigation task to understand root cause in property tests
- Added tasks for remaining 10 property test collection errors
- Split full test suite verification into smaller subset runs with timeouts
- Added rollback strategy (.broken criteria for unfixable tests)
- Added PERFORMANCE_BASELINE.md documentation task
- Added dependency on pytest_xdist_test_isolation_research.md

**Success Criteria:**
1. All 17 collection errors fixed or tests renamed to .broken
2. `pytest tests/ --collect-only` shows "collected 7324+ items, 0 errors"
3. TypeError root cause investigated and documented
4. All tests run with `pytest tests/ -n auto` (with timeout handling)
5. Performance baseline documented in PERFORMANCE_BASELINE.md
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/STATE.md
@.planning/ROADMAP.md
@backend/tests/pytest_xdist_test_isolation_research.md
</execution_context>

<context>
From pytest_xdist_test_isolation_research.md:

**Finding:** The Atom codebase does NOT have significant pytest-xdist test isolation issues. Tests pass successfully with parallel execution. The reported 23% pass rate (130/566 tests) was caused by **collection/import errors**, not runtime isolation failures.

**Current State:**
- **7,324 tests collected** (not 566 as initially reported)
- **17 collection errors** during test discovery
- **0 runtime isolation failures** detected

**Collection Errors (17 total):**

1. **test_performance_baseline.py** - Missing 'fast' marker in pytest.ini
   - Error: `'fast' not found in markers configuration option`
   - Fix: Add 'fast' marker to pytest.ini OR rename to .broken

2. **test_auth_flows.py** - ModuleNotFoundError
   - Error: `ModuleNotFoundError: No module named 'api.atom_agent_endpoints'`
   - Fix: Update import to correct module path (core.atom_agent_endpoints)

3. **test_episode_lifecycle_lancedb.py** - SyntaxError
   - Error: `SyntaxError: expected '('` at line 89
   - Cause: `def episodes_with varying_ages(` - spaces not allowed in function name
   - Fix: Change to `def episodes_with_varying_ages(`

4. **test_episode_segmentation_invariants.py** - NameError
   - Error: `NameError: name 'example' is not defined` at line 33
   - Cause: `@example` decorator used without importing from hypothesis
   - Fix: Add `from hypothesis import example` to imports

5. **test_agent_graduation_invariants.py** - NameError
   - Error: `NameError: name 'example' is not defined` at line 55
   - Cause: `@example` decorator used without importing from hypothesis
   - Fix: Add `from hypothesis import example` to imports

6. **test_episode_retrieval_invariants.py** - NameError
   - Error: `NameError: name 'example' is not defined` at line 39
   - Cause: `@example` decorator used without importing from hypothesis
   - Fix: Add `from hypothesis import example` to imports

7. **test_episode_segmentation_service.py** (unit test) - SyntaxError
   - Error: `SyntaxError: 'await' outside async function` at line 758
   - Cause: `await` used in non-async function
   - Fix: Make function async or remove await

**Remaining 10 Property Test Errors (Likely Hypothesis-related):**

8. **test_database_invariants.py** - TypeError or NameError
   - Error: `TypeError: isinstance... arg 2 must be a type or tuple of types`
   - Or: `NameError: name 'example' is not defined`
   - Fix: Investigate root cause, add missing imports, fix isinstance calls

9. **test_state_invariants.py** - TypeError or NameError
   - Error: Similar to database invariants
   - Fix: Investigate root cause, add missing imports

10. **test_event_invariants.py** - TypeError or NameError
    - Error: Similar to database invariants
    - Fix: Investigate root cause, add missing imports

11. **test_file_invariants.py** - TypeError or NameError
    - Error: Similar to database invariants
    - Fix: Investigate root cause, add missing imports

**Additional Property Test Files (6 more):**
- Additional property test files in backend/tests/property_tests/ directory
- Expected to have similar Hypothesis import or TypeError issues

**Rollback Strategy:**
If a test cannot be fixed within reasonable time (15 minutes investigation + 15 minutes fix):
1. Rename file from `test_*.py` to `test_*.py.broken`
2. Document reason for .broken status in file header
3. Create GitHub issue tracking the broken test
4. Update summary document with .broken files list
</context>

<tasks>

<task type="auto">
  <name>Fix pytest.ini marker configuration for test_performance_baseline.py</name>
  <files>backend/pytest.ini, backend/tests/test_performance_baseline.py</files>
  <action>
    Check if test_performance_baseline.py uses @pytest.mark.fast decorator
    If yes: Add "fast: Fast tests (<0.1s)" to markers section in pytest.ini
    If no: Rename test_performance_baseline.py to test_performance_baseline.py.broken
    Verify fix with: pytest backend/tests/test_performance_baseline.py --collect-only
    Commit: "fix(tests): Add fast marker to pytest.ini or rename performance baseline test"
  </action>
  <verify>
    pytest backend/tests/test_performance_baseline.py --collect-only succeeds
    No marker-related errors in output
  </verify>
  <done>
    Fixed marker configuration OR renamed to .broken
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Fix import path in test_auth_flows.py</name>
  <files>backend/tests/integration/test_auth_flows.py</files>
  <action>
    Read test_auth_flows.py line 23 where error occurs
    Identify correct import path for atom_agent_endpoints
    Change from: from api.atom_agent_endpoints import app
    Change to: from core.atom_agent_endpoints import app (or correct path)
    Verify fix with: pytest backend/tests/integration/test_auth_flows.py --collect-only
    Commit: "fix(tests): Correct import path in test_auth_flows.py"
  </action>
  <verify>
    pytest backend/tests/integration/test_auth_flows.py --collect-only succeeds
    No ModuleNotFoundError in output
  </verify>
  <done>
    Import path corrected
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Fix syntax error in test_episode_lifecycle_lancedb.py fixture name</name>
  <files>backend/tests/integration/episodes/test_episode_lifecycle_lancedb.py</files>
  <action>
    Read line 89 of test_episode_lifecycle_lancedb.py
    Change: def episodes_with varying_ages(
    To: def episodes_with_varying_ages(
    Update all references to this fixture name
    Verify fix with: pytest backend/tests/integration/episodes/test_episode_lifecycle_lancedb.py --collect-only
    Commit: "fix(tests): Fix fixture name syntax error in episode_lifecycle_lancedb"
  </action>
  <verify>
    pytest backend/tests/integration/episodes/test_episode_lifecycle_lancedb.py --collect-only succeeds
    No SyntaxError in output
  </verify>
  <done>
    Fixture name corrected (no spaces)
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Add missing hypothesis import to test_episode_segmentation_invariants.py</name>
  <files>backend/tests/property_tests/episodes/test_episode_segmentation_invariants.py</files>
  <action>
    Read line 16-20 (imports section)
    Add: from hypothesis import example
    Verify fix with: pytest backend/tests/property_tests/episodes/test_episode_segmentation_invariants.py --collect-only
    Commit: "fix(tests): Add missing example import from hypothesis"
  </action>
  <verify>
    pytest backend/tests/property_tests/episodes/test_episode_segmentation_invariants.py --collect-only succeeds
    No NameError for 'example' in output
  </verify>
  <done>
    Added 'from hypothesis import example' to imports
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Add missing hypothesis import to test_agent_graduation_invariants.py</name>
  <files>backend/tests/property_tests/episodes/test_agent_graduation_invariants.py</files>
  <action>
    Read imports section
    Add: from hypothesis import example
    Verify fix with: pytest backend/tests/property_tests/episodes/test_agent_graduation_invariants.py --collect-only
    Commit: "fix(tests): Add missing example import from hypothesis"
  </action>
  <verify>
    pytest backend/tests/property_tests/episodes/test_agent_graduation_invariants.py --collect-only succeeds
    No NameError for 'example' in output
  </verify>
  <done>
    Added 'from hypothesis import example' to imports
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Add missing hypothesis import to test_episode_retrieval_invariants.py</name>
  <files>backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py</files>
  <action>
    Read imports section
    Add: from hypothesis import example
    Verify fix with: pytest backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py --collect-only
    Commit: "fix(tests): Add missing example import from hypothesis"
  </action>
  <verify>
    pytest backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py --collect-only succeeds
    No NameError for 'example' in output
  </verify>
  <done>
    Added 'from hypothesis import example' to imports
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Fix async/await syntax error in test_episode_segmentation_service.py</name>
  <files>backend/tests/unit/episodes/test_episode_segmentation_service.py</files>
  <action>
    Read line 758 area where SyntaxError occurs
    Identify if function should be async or if await should be removed
    If function calls async code, add async def before function definition
    If function doesn't need async, remove await keyword
    Verify fix with: pytest backend/tests/unit/episodes/test_episode_segmentation_service.py --collect-only
    Commit: "fix(tests): Fix async/await syntax in episode_segmentation_service unit test"
  </action>
  <verify>
    pytest backend/tests/unit/episodes/test_episode_segmentation_service.py --collect-only succeeds
    No SyntaxError in output
  </verify>
  <done>
    async/await syntax corrected
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Investigate TypeError root cause in property tests</name>
  <files>backend/tests/property_tests/</files>
  <action>
    Run collection on all property tests to identify TypeError messages:
    PYTHONPATH=backend pytest backend/tests/property_tests/ --collect-only 2>&1 | grep -A 5 TypeError
    Read each failing file to understand the TypeError pattern
    Check if errors are from isinstance() calls with incorrect arguments
    Check if errors are from missing Hypothesis imports (example, given, settings)
    Document findings in COLLECTION_ERROR_INVESTIGATION.md
    Commit: "docs(tests): Document TypeError root cause analysis"
  </action>
  <verify>
    All TypeError messages documented
    Root cause identified (isinstance issue vs import issue vs other)
    Investigation document created
  </verify>
  <done>
    TypeError root cause documented
    Fix strategy determined for all remaining property tests
  </done>
</task>

<task type="auto">
  <name>Fix TypeError/imports in test_database_invariants.py</name>
  <files>backend/tests/property_tests/database/test_database_invariants.py</files>
  <action>
    Read file and identify error type (TypeError vs NameError)
    If TypeError: Fix isinstance() calls or other type-related issues
    If NameError: Add missing Hypothesis imports (example, given, settings, etc.)
    Verify fix with: pytest backend/tests/property_tests/database/test_database_invariants.py --collect-only
    If unfixable in 15 minutes, rename to .broken and document reason
    Commit: "fix(tests): Fix TypeError/imports in test_database_invariants.py"
  </action>
  <verify>
    pytest backend/tests/property_tests/database/test_database_invariants.py --collect-only succeeds
    No TypeError or NameError in output
  </verify>
  <done>
    TypeError/imports fixed OR renamed to .broken
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Fix TypeError/imports in test_state_invariants.py</name>
  <files>backend/tests/property_tests/state/test_state_invariants.py</files>
  <action>
    Read file and identify error type (TypeError vs NameError)
    If TypeError: Fix isinstance() calls or other type-related issues
    If NameError: Add missing Hypothesis imports (example, given, settings, etc.)
    Verify fix with: pytest backend/tests/property_tests/state/test_state_invariants.py --collect-only
    If unfixable in 15 minutes, rename to .broken and document reason
    Commit: "fix(tests): Fix TypeError/imports in test_state_invariants.py"
  </action>
  <verify>
    pytest backend/tests/property_tests/state/test_state_invariants.py --collect-only succeeds
    No TypeError or NameError in output
  </verify>
  <done>
    TypeError/imports fixed OR renamed to .broken
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Fix TypeError/imports in test_event_invariants.py</name>
  <files>backend/tests/property_tests/events/test_event_invariants.py</files>
  <action>
    Read file and identify error type (TypeError vs NameError)
    If TypeError: Fix isinstance() calls or other type-related issues
    If NameError: Add missing Hypothesis imports (example, given, settings, etc.)
    Verify fix with: pytest backend/tests/property_tests/events/test_event_invariants.py --collect-only
    If unfixable in 15 minutes, rename to .broken and document reason
    Commit: "fix(tests): Fix TypeError/imports in test_event_invariants.py"
  </action>
  <verify>
    pytest backend/tests/property_tests/events/test_event_invariants.py --collect-only succeeds
    No TypeError or NameError in output
  </verify>
  <done>
    TypeError/imports fixed OR renamed to .broken
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Fix TypeError/imports in test_file_invariants.py</name>
  <files>backend/tests/property_tests/files/test_file_invariants.py</files>
  <action>
    Read file and identify error type (TypeError vs NameError)
    If TypeError: Fix isinstance() calls or other type-related issues
    If NameError: Add missing Hypothesis imports (example, given, settings, etc.)
    Verify fix with: pytest backend/tests/property_tests/files/test_file_invariants.py --collect-only
    If unfixable in 15 minutes, rename to .broken and document reason
    Commit: "fix(tests): Fix TypeError/imports in test_file_invariants.py"
  </action>
  <verify>
    pytest backend/tests/property_tests/files/test_file_invariants.py --collect-only succeeds
    No TypeError or NameError in output
  </verify>
  <done>
    TypeError/imports fixed OR renamed to .broken
    Test collects without errors
  </done>
</task>

<task type="auto">
  <name>Fix remaining property test collection errors (batch fix)</name>
  <files>backend/tests/property_tests/</files>
  <action>
    Run full property test collection to find remaining errors:
    PYTHONPATH=backend pytest backend/tests/property_tests/ --collect-only 2>&1 | tee /tmp/property_errors.log
    For each remaining error:
    1. Read the file and identify error type
    2. Apply appropriate fix (add import, fix syntax, rename to .broken)
    3. Verify individual file collects successfully
    Stop after 30 minutes or when all errors fixed
    Commit: "fix(tests): Fix remaining property test collection errors (batch)"
  </action>
  <verify>
    All property test files collect without errors OR are renamed to .broken
    Document any .broken files with reasons
  </verify>
  <done>
    All property test errors addressed
    Summary of fixes and .broken files created
  </done>
</task>

<task type="auto">
  <name>Verify episode property tests collection (subset check)</name>
  <files>backend/tests/property_tests/episodes/</files>
  <action>
    Run collection on episode property tests only:
    PYTHONPATH=backend pytest backend/tests/property_tests/episodes/ --collect-only
    Verify expected test count (20+ tests per file)
    Check for 0 errors in output
    Document test count for subset
    Commit: "docs(tests): Document episode property tests collection count"
  </action>
  <verify>
    Output shows "collected XXX items, 0 errors"
    No ERROR lines in output
    Test count matches expected (60+ items for 3 files)
  </verify>
  <done>
    Episode property tests verified
    Collection count documented
  </done>
</task>

<task type="auto">
  <name>Verify integration tests collection (subset check)</name>
  <files>backend/tests/integration/</files>
  <action>
    Run collection on integration tests only:
    PYTHONPATH=backend pytest backend/tests/integration/ --collect-only
    Verify test_auth_flows.py and test_episode_lifecycle_lancedb.py collect
    Check for 0 errors in output
    Document test count for subset
    Commit: "docs(tests): Document integration tests collection count"
  </action>
  <verify>
    Output shows "collected XXX items, 0 errors"
    No ERROR lines in output
    test_auth_flows.py appears in collected items
  </verify>
  <done>
    Integration tests verified
    Collection count documented
  </done>
</task>

<task type="auto">
  <name>Verify all collection errors fixed with full test collection</name>
  <files>backend/tests/</files>
  <depends_on>["Fix TypeError/imports in test_database_invariants.py", "Fix TypeError/imports in test_state_invariants.py", "Fix TypeError/imports in test_event_invariants.py", "Fix TypeError/imports in test_file_invariants.py", "Fix remaining property test collection errors (batch fix)"]</depends_on>
  <action>
    Run full collection: PYTHONPATH=backend pytest backend/tests/ --collect-only
    Check for "collected 7324+ items" (exact count may vary)
    Verify "0 errors" in output
    Document any remaining issues
    Create summary of fixed errors in COLLECTION_FIXES_SUMMARY.md
    List any .broken files with reasons
    Commit: "docs(tests): Document collection error fixes summary"
  </action>
  <verify>
    pytest backend/tests/ --collect-only shows "collected 7324+ items, 0 errors" (exact count acceptable)
    No ERROR lines in output
    COLLECTION_FIXES_SUMMARY.md created with all fixes documented
  </verify>
  <done>
    All 17 collection errors fixed or documented as .broken
    Full test suite collects successfully with 7324+ items
    Summary document created
  </done>
</task>

<task type="auto">
  <name>Run unit tests subset with pytest-xdist (verification)</name>
  <files>backend/tests/unit/</files>
  <depends_on>["Verify all collection errors fixed with full test collection"]</depends_on>
  <action>
    Run unit tests with parallel execution:
    PYTHONPATH=backend pytest backend/tests/unit/ -n auto --tb=short -v
    Record pass/fail counts
    Record execution time
    Check for collection errors (should be 0)
    Commit: "test(perf): Verify unit tests with pytest-xdist"
  </action>
  <verify>
    Tests run with parallel execution
    No collection errors
    Execution time recorded
  </verify>
  <done>
    Unit tests verified with -n auto
    Baseline metrics recorded
  </done>
</task>

<task type="auto">
  <name>Run property tests subset with pytest-xdist (verification)</name>
  <files>backend/tests/property_tests/</files>
  <depends_on>["Verify all collection errors fixed with full test collection"]</depends_on>
  <action>
    Run property tests with parallel execution (10 min timeout):
    PYTHONPATH=backend pytest backend/tests/property_tests/ -n auto --tb=short -v --timeout=600
    Record pass/fail counts
    Record execution time
    Check for collection errors (should be 0)
    Commit: "test(perf): Verify property tests with pytest-xdist"
  </action>
  <verify>
    Tests run with parallel execution
    No collection errors
    Execution time recorded
  </verify>
  <done>
    Property tests verified with -n auto
    Baseline metrics recorded
  </done>
</task>

<task type="auto">
  <name>Create PERFORMANCE_BASELINE.md documentation</name>
  <files>backend/tests/PERFORMANCE_BASELINE.md</files>
  <depends_on>["Run unit tests subset with pytest-xdist (verification)", "Run property tests subset with pytest-xdist (verification)"]</depends_on>
  <action>
    Create PERFORMANCE_BASELINE.md with:
    1. Test suite overview (total count: 7324+ tests)
    2. Parallel execution configuration (-n auto)
    3. Baseline execution times by test type (unit, integration, property)
    4. Known .broken tests with reasons
    5. Performance optimization recommendations
    6. Hardware/environment context for baseline
    Commit: "docs(tests): Add performance baseline documentation"
  </action>
  <verify>
    PERFORMANCE_BASELINE.md exists
    Contains test count (7324+)
    Contains execution time baselines
    Lists any .broken tests
  </verify>
  <done>
    Performance baseline documented
    Reference for future performance comparisons created
  </done>
</task>

<task type="auto">
  <name>Run full test suite sample with pytest-xdist (final verification)</name>
  <files>backend/tests/</files>
  <depends_on>["Create PERFORMANCE_BASELINE.md documentation"]</depends_on>
  <action>
    Run full test suite with timeout (30 min):
    PYTHONPATH=backend pytest backend/tests/ -n auto --tb=short --timeout=1800 --maxfail=10
    If timeout occurs: Note subset completed and move to summary
    Monitor test execution
    Record pass/fail counts (may be partial if timeout)
    Record execution time
    Update performance_baseline.json with results
    Note: Full 7324 tests may take 30+ minutes
    Commit: "test(perf): Update performance baseline with pytest-xdist results"
  </action>
  <verify>
    Tests run with parallel execution OR timeout reached
    No collection errors
    Performance baseline updated with actual results
    Summary includes whether full suite completed or partial
  </verify>
  <done>
    Full test suite executed with -n auto (or partial with timeout)
    Pass rate documented
    Execution time baseline established
    Timeout handled gracefully if occurred
  </done>
</task>

</tasks>

<verification>
Overall verification steps:
1. Run TypeError investigation: PYTHONPATH=backend pytest backend/tests/property_tests/ --collect-only 2>&1 | grep -A 5 TypeError
   Expected: All TypeError messages documented with root cause
2. Run subset collection checks:
   - Episode property tests: PYTHONPATH=backend pytest backend/tests/property_tests/episodes/ --collect-only
     Expected: "collected 60+ items, 0 errors"
   - Integration tests: PYTHONPATH=backend pytest backend/tests/integration/ --collect-only
     Expected: "collected XXX items, 0 errors", no ModuleNotFoundError
3. Run full collection check: PYTHONPATH=backend pytest backend/tests/ --collect-only
   Expected: "collected 7324+ items, 0 errors" (exact count acceptable)
4. Run parallel execution subsets (with timeouts):
   - Unit tests: PYTHONPATH=backend pytest backend/tests/unit/ -n auto --tb=short
     Expected: No collection errors, execution time recorded
   - Property tests: PYTHONPATH=backend pytest backend/tests/property_tests/ -n auto --timeout=600
     Expected: No collection errors, execution time recorded
5. Verify specific fixes:
   - test_performance_baseline.py collects OR renamed to .broken
   - test_auth_flows.py collects without ModuleNotFoundError
   - test_episode_lifecycle_lancedb.py collects without SyntaxError
   - All episode property tests collect without NameError for 'example'
   - All database/state/event/file property tests collect without TypeError or NameError
   - test_episode_segmentation_service.py collects without async SyntaxError
6. Check PERFORMANCE_BASELINE.md created with:
   - Total test count (7324+)
   - Execution time baselines by test type
   - List of any .broken tests with reasons
7. Verify no regression in test isolation (tests still pass)
8. Verify rollback strategy applied: any unfixable tests renamed to .broken with documentation
</verification>

<success_criteria>
- [ ] All 17 collection errors fixed or tests renamed to .broken
- [ ] `pytest tests/ --collect-only` shows "collected 7324+ items, 0 errors" (exact count acceptable)
- [ ] TypeError root cause investigated and documented in COLLECTION_ERROR_INVESTIGATION.md
- [ ] All tests run with `pytest tests/ -n auto` (or subset with timeout)
- [ ] Performance baseline documented in PERFORMANCE_BASELINE.md
- [ ] Full test collection count documented (7,324+ tests)
- [ ] No SyntaxError, NameError, ModuleNotFoundError, or marker errors
- [ ] COLLECTION_FIXES_SUMMARY.md created describing all fixes
- [ ] Git commits for each fix with atomic changes
- [ ] Rollback strategy applied: unfixable tests renamed to .broken with reasons
- [ ] TypeError in property tests fixed or tests renamed to .broken
- [ ] PERFORMANCE_BASELINE.md contains execution time baselines by test type
- [ ] Depends on pytest_xdist_test_isolation_research.md completion acknowledged
</success_criteria>
