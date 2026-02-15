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
    - Property tests collect successfully with no TypeError from Hypothesis
    - st.just() and st.sampled_from() work correctly in all property tests
    - All 10 property test modules can be imported and collected by pytest
    - Property tests run with Hypothesis 6.151.5 without AttributeError
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
Fix Hypothesis TypeError in property tests that prevents test collection

**Purpose**: 10 property test modules fail during collection with `AttributeError: 'JustStrategy' object has no attribute '_transformations'`. This is a Hypothesis version compatibility issue with st.just() and st.sampled_from() usage.

**Root Cause**: Hypothesis 6.151.5 changed internal implementation. The pattern `st.sampled_from(['single_value'])` creates a SampledFromStrategy wrapping a JustStrategy, but the check `isinstance(value, type)` fails because JustStrategy no longer has `_transformations` attribute.

**Output**: All property tests collect and run successfully
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
  <name>Task 1: Fix st.just() and st.sampled_from() usage in property tests</name>
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
Fix Hypothesis compatibility issue in all 10 property test files:

1. **Replace `st.sampled_from(['single_value'])` with `st.just('single_value')`**
   - When sampling from a list with one element, use st.just() directly
   - Example: `st.sampled_from(['hit'])` → `st.just('hit')`
   - Example: `st.sampled_from([timezone.utc])` → `st.just(timezone.utc)`

2. **Replace `st.one_of(st.just(''), st.just('   '), st.just(None))` with proper strategy**
   - Use `st.one_of(st.none(), st.text())` or `st.text(min_size=0)` instead
   - The error happens with st.just() inside st.one_of()

3. **For `st.tuples(st.just(...), ...)` patterns**:
   - Replace with direct value strategies where possible
   - Example: `st.tuples(st.just("hit"), st.text(...))` → `st.tuples(st.just("hit"), st.text(...))`
   - If the first value is constant, consider a composite strategy

**Files to modify** (check each for problematic patterns):
- test_error_guidance_invariants.py: Line ~56 has `st.one_of(st.just(''), st.just('   '), st.just(None))`
- test_governance_cache_invariants.py: Multiple `st.sampled_from(['single_value'])` patterns
- test_input_validation_invariants.py: `st.just("' OR '1'='1")` pattern
- test_temporal_invariants.py: `st.just(timezone.utc)` pattern
- test_tool_governance_invariants.py: `st.sampled_from(['http://example.com'])` pattern
- Other files: Check for similar patterns

**Verification pattern**: After fix, running `pytest tests/property_tests/ --collect-only` should show 0 errors.
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/property_tests/ --collect-only -q 2>&1 | grep -E "errors collected|ERROR"
Expected: "0 errors collected" or no ERROR output
</verify>
  <done>
Property tests collect successfully with no Hypothesis TypeErrors. `pytest tests/property_tests/ --collect-only` completes without errors.
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
