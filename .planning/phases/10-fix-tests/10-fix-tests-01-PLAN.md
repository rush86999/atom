---
phase: 10-fix-tests
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/property_tests/analytics/test_analytics_invariants.py
  - tests/property_tests/api/test_api_contracts.py
  - tests/property_tests/caching/test_caching_invariants.py
  - tests/property_tests/contracts/test_action_complexity.py
  - tests/property_tests/data_validation/test_data_validation_invariants.py
  - tests/property_tests/episodes/test_error_guidance_invariants.py
  - tests/property_tests/governance/test_governance_cache_invariants.py
  - tests/property_tests/input_validation/test_input_validation_invariants.py
  - tests/property_tests/temporal/test_temporal_invariants.py
  - tests/property_tests/tools/test_tool_governance_invariants.py
autonomous: true

must_haves:
  truths:
    - Property tests collect successfully during full test suite collection (no ERROR messages)
    - st.just() and st.sampled_from() work correctly in all property tests when pytest symbol table is large
    - All 10 property test modules can be imported and collected by pytest with 10,000+ other tests
    - Property tests run with Hypothesis 6.151.5 without AttributeError during full suite collection
  artifacts:
    - path: "tests/property_tests/analytics/test_analytics_invariants.py"
      provides: "Analytics property tests"
      contains: "st.just"
    - path: "tests/property_tests/episodes/test_error_guidance_invariants.py"
      provides: "Error guidance property tests"
      contains: "st.one_of"
    - path: "tests/property_tests/governance/test_governance_cache_invariants.py"
      provides: "Governance cache property tests"
      contains: "st.sampled_from"
  key_links:
    - from: "tests/property_tests"
      to: "hypothesis.strategies"
      via: "import strategies as st"
      pattern: "from hypothesis import strategies as st"
---

<objective>
Fix Hypothesis TypeError in property tests during full test suite collection

**Purpose**: 10 property test modules fail during collection with `AttributeError: 'JustStrategy' object has no attribute '_transformations'` when collected as part of the full test suite (10,000+ tests). Tests pass individually but fail during full collection due to pytest symbol table conflicts with Hypothesis internals.

**Root Cause**: When pytest collects 10,000+ tests, its symbol table becomes very large. Hypothesis's st.just(), st.sampled_from(), and st.one_of() strategies trigger isinstance() checks that fail against Hypothesis 6.151.5's internal JustStrategy class when the symbol table is bloated. The tests pass individually (smaller symbol table) but fail during full collection.

**Output**: All property tests collect successfully as part of full test suite
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/ROADMAP.md
</execution_context>

<context>
@.planning/ROADMAP.md
@backend/tests/property_tests/episodes/test_error_guidance_invariants.py
@backend/tests/property_tests/governance/test_governance_cache_invariants.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix Hypothesis st.just() strategy issues in property tests</name>
  <files>tests/property_tests/analytics/test_analytics_invariants.py</files>
  <files>tests/property_tests/api/test_api_contracts.py</files>
  <files>tests/property_tests/caching/test_caching_invariants.py</files>
  <files>tests/property_tests/contracts/test_action_complexity.py</files>
  <files>tests/property_tests/data_validation/test_data_validation_invariants.py</files>
  <files>tests/property_tests/episodes/test_error_guidance_invariants.py</files>
  <files>tests/property_tests/governance/test_governance_cache_invariants.py</files>
  <files>tests/property_tests/input_validation/test_input_validation_invariants.py</files>
  <files>tests/property_tests/temporal/test_temporal_invariants.py</files>
  <files>tests/property_tests/tools/test_tool_governance_invariants.py</files>
  <action>
Fix Hypothesis compatibility issue in all 10 property test files. The issue occurs when pytest's symbol table is large (10,000+ tests). Hypothesis's st.just() and st.one_of() trigger isinstance() checks that fail against Hypothesis 6.151.5's internal JustStrategy class.

**Problem patterns to fix:**

1. **st.one_of() with multiple st.just() calls** - This triggers isinstance() failures:
   ```python
   # BROKEN:
   st.one_of(st.just(''), st.just('   '), st.just(None))

   # FIXED: Use st.sampled_from() instead:
   st.sampled_from(['', '   ', None])
   # OR use st.none() + st.text():
   st.one_of(st.none(), st.text())
   ```

2. **st.sampled_from() with single value** - Inefficient but triggers same issue:
   ```python
   # BROKEN:
   st.sampled_from(['hit'])
   st.sampled_from([timezone.utc])
   st.sampled_from(['http://example.com'])

   # FIXED: Use st.just() directly:
   st.just('hit')
   st.just(timezone.utc)
   st.just('http://example.com')
   ```

3. **st.tuples() with st.just() first element** - May trigger issue:
   ```python
   # Check if this pattern causes issues, if so restructure:
   st.tuples(st.just("value"), st.other_strategy())
   ```

**Files with known issues** (from collection errors):
- test_error_guidance_invariants.py: Has st.one_of() with st.just() pattern
- test_governance_cache_invariants.py: Has st.sampled_from() with single values
- test_input_validation_invariants.py: Has st.just() with SQL string
- test_temporal_invariants.py: Has st.just(timezone.utc)
- test_tool_governance_invariants.py: Has st.sampled_from() with URLs
- test_api_contracts.py: May have similar patterns
- test_caching_invariants.py: May have similar patterns
- test_data_validation_invariants.py: May have similar patterns

**Verification**: After fixes, run full suite collection to verify no errors.
</action>
  <verify>
# Test individual collection first (should pass):
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/property_tests/analytics/test_analytics_invariants.py --collect-only -q 2>&1 | grep -E "collected|ERROR"
Expected: "31 tests collected" (no ERROR)

# Then test full suite collection:
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ --collect-only -q 2>&1 | grep -E "collected|errors collected"
Expected: "10176 tests collected" with "0 errors collected" (not "10 errors")
</verify>
  <done>
Property tests collect successfully during full test suite collection. `pytest tests/ --collect-only` shows 10176 tests collected with 0 errors.
</done>
</task>

<task type="auto">
  <name>Task 2: Verify property tests run successfully after fixes</name>
  <files>tests/property_tests/</files>
  <action>
Run a sample of property tests to verify they execute correctly:

1. Run error guidance invariants test (had the st.one_of issue)
2. Run governance cache invariants test (had st.sampled_from single value issue)
3. Run input validation invariants test (had st.just with SQL injection pattern)

Command: `pytest tests/property_tests/episodes/test_error_guidance_invariants.py tests/property_tests/governance/test_governance_cache_invariants.py tests/property_tests/input_validation/test_input_validation_invariants.py -v --tb=short`

Expected: Tests run and pass (or fail with test assertions, not Hypothesis errors)
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/property_tests/episodes/test_error_guidance_invariants.py tests/property_tests/governance/test_governance_cache_invariants.py -v --tb=short 2>&1 | tail -20
Expected: No "AttributeError: 'JustStrategy' object has no attribute '_transformations'" errors
</verify>
  <done>
Sample property tests execute without Hypothesis collection errors. Tests may pass or fail based on assertions, but not due to Hypothesis library compatibility.
</done>
</task>

</tasks>

<verification>
1. All property tests collect successfully: `pytest tests/property_tests/ --collect-only` returns 0 errors
2. No `AttributeError: 'JustStrategy' object has no attribute '_transformations'` in test output
3. At least 3 property test files run successfully (not just collect)
</verification>

<success_criteria>
- Property tests collect without Hypothesis TypeErrors (0 errors during collection)
- All 10 property test modules can be imported
- Sample property tests execute to completion (pass or fail on assertions, not Hypothesis errors)
</success_criteria>

<output>
After completion, create `.planning/phases/10-fix-tests/10-fix-tests-01-SUMMARY.md` with:
- Number of files modified
- Specific patterns replaced (before/after)
- Collection results (before: 10 errors, after: 0 errors)
</output>
