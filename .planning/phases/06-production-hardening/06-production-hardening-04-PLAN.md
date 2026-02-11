---
phase: 06-production-hardening
plan: 04
type: execute
wave: 4
depends_on: [06-production-hardening-01]
files_modified:
  - backend/core/agent_governance_service.py
  - backend/core/episode_segmentation_service.py
  - backend/core/episode_retrieval_service.py
  - backend/core/governance_cache.py
  - backend/api/atom_agent_endpoints.py
  - backend/tools/canvas_tool.py
  - backend/tests/coverage_reports/metrics/bug_triage_report.md
autonomous: true

must_haves:
  truths:
    - "All P1 (high-priority) bugs are fixed with regression tests"
    - "P1 fixes are verified with passing tests"
    - "Bug triage report updated with P1 fix status"
    - "No new P1 bugs introduced by fixes"
  artifacts:
    - path: "backend/core/agent_governance_service.py"
      provides: "Agent governance with P1 bug fixes"
    - path: "backend/core/episode_segmentation_service.py"
      provides: "Episode segmentation with P1 bug fixes"
    - path: "backend/core/episode_retrieval_service.py"
      provides: "Episode retrieval with P1 bug fixes"
    - path: "backend/core/governance_cache.py"
      provides: "Cache layer with P1 bug fixes"
    - path: "backend/api/atom_agent_endpoints.py"
      provides: "API endpoints with P1 bug fixes"
    - path: "backend/tools/canvas_tool.py"
      provides: "Canvas tool with P1 bug fixes"
    - path: "backend/tests/coverage_reports/metrics/bug_triage_report.md"
      provides: "Updated bug status after P1 fixes"
  key_links:
    - from: "06-production-hardening-01-PLAN.md"
      to: "06-production-hardening-04-PLAN.md"
      via: "bug_triage_report.md"
      pattern: "P1.*High"
    - from: "bug_triage_report.md"
      to: "backend/core/*.py"
      via: "P1 bug fixes"
      pattern: "fix.*P1|P1.*resolved"
    - from: "backend/tests"
      to: "backend/core/*.py"
      via: "regression tests"
      pattern: "test_p1_*|regression"
---

<objective>
Fix all P1 (high-priority) bugs discovered in Plan 01, focusing on system crashes, financial incorrectness, and data integrity issues with 72-hour SLA.

**Purpose:** P1 bugs represent high-priority issues that can cause system crashes, financial errors, and data integrity problems. These must be fixed within 72 hours to prevent significant operational impact while following P0 critical fixes.

**Output:**
- Fixed P1 bugs in core service files
- Regression tests preventing future P1 bugs
- Updated bug_triage_report.md with P1 fix status
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/06-production-hardening/06-RESEARCH.md
@.planning/phases/06-production-hardening/06-production-hardening-01-SUMMARY.md
@.planning/phases/06-production-hardening/06-production-hardening-02-SUMMARY.md
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Bug triage from Plan 01
@/Users/rushiparikh/projects/atom/backend/tests/coverage_reports/metrics/bug_triage_report.md

# Prioritized fixes from Plan 02
@/Users/rushiparikh/projects/atom/.planning/phases/06-production-hardening/06-production-hardening-02-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Fix P1 System Crash Bugs</name>
  <files>backend/core/agent_governance_service.py, backend/core/governance_cache.py, backend/api/atom_agent_endpoints.py</files>
  <action>
Fix P1 system crash bugs identified in bug_triage_report.md:

Common P1 crash patterns from RESEARCH.md:
1. **Unhandled exceptions** - Add try/except with proper error handling
2. **OOM errors** - Fix memory leaks, add pagination limits
3. **Null pointer dereferences** - Add None checks before access
4. **Stack overflow** - Fix infinite recursion, add depth limits
5. **Resource exhaustion** - Add proper cleanup in finally blocks

For each P1 crash bug:
1. Add regression test BEFORE fixing:
   ```python
   def test_p1_crash_<bug_name>_regression(self):
       """
       Regression test for P1 crash bug: <description>.

       VALIDATED_BUG: Discovered Phase 6 Plan 01
       Fix: <commit_hash>
       """
       # Test that crash condition is handled
       with pytest.raises(<ExpectedException>):
           crash_causing_operation()
   ```

2. Fix the crash in source code with proper error handling:
   ```python
   # GOOD - Handle potential crash
   try:
       risky_operation()
   except (SpecificException, AnotherException) as e:
       logger.error(f"Operation failed: {e}")
       raise <AppropriateError>(str(e)) from e
   ```

3. Verify test passes with fix
4. Document fix in bug_triage_report.md with "RESOLVED" status

For cache-related crashes:
- Add bounds checking on cache size
- Implement proper cache eviction policies
- Add cache hit/miss metrics
  </action>
  <verify>For each P1 crash bug: (1) Regression test added and passing, (2) Exception handling added with specific catches, (3) Bug triage report marked RESOLVED</verify>
  <done>All P1 system crash bugs fixed with regression tests, proper error handling implemented, bug_triage_report.md updated with fix status</done>
</task>

<task type="auto">
  <name>Fix P1 Financial/Data Integrity Bugs</name>
  <files>backend/core/models.py, backend/core/episode_segmentation_service.py, backend/core/episode_retrieval_service.py</files>
  <action>
Fix P1 financial and data integrity bugs identified in bug_triage_report.md:

Common P1 integrity patterns from INVARIANTS.md:
1. **Incorrect calculations** - Fix arithmetic/logic errors in business logic
2. **Off-by-one errors** - Fix boundary conditions (< vs <=)
3. **Type coercion bugs** - Ensure proper type handling
4. **Transaction integrity** - Verify database constraints enforced
5. **Episode data consistency** - Ensure segments properly linked

For each P1 integrity bug:
1. Add regression test BEFORE fixing:
   ```python
   def test_p1_integrity_<bug_name>_regression(self, db_session):
       """
       Regression test for P1 integrity bug: <description>.

       VALIDATED_BUG: Discovered Phase 6 Plan 01
       Fix: <commit_hash>
       """
       # Test that integrity is maintained
       result = business_logic_operation()
       assert result == expected_value, f"Integrity violation: {result} != {expected}"
   ```

2. Fix the integrity issue in source code:
   ```python
   # GOOD - Explicit boundary checks
   if value < boundary:  # Exclusive boundary
       process(value)
   # NOT: if value <= boundary:  # Off-by-one

   # GOOD - Explicit type handling
   result = int(string_value) if string_value.isdigit() else default_value
   # NOT: result = int(string_value)  # May crash
   ```

3. Verify test passes with fix
4. Document fix in bug_triage_report.md

For database integrity issues:
- Verify CHECK constraints in schema
- Add explicit validation before database operations
- Use transactions for multi-step operations
  </action>
  <verify>For each P1 integrity bug: (1) Regression test added and passing, (2) Logic/boundary errors fixed, (3) Bug triage report marked RESOLVED</verify>
  <done>All P1 financial/data integrity bugs fixed with regression tests, proper validation implemented, bug_triage_report.md updated with fix status</done>
</task>

</tasks>

<verification>
1. Run regression tests: `pytest tests/test_p1_*_regression.py -v` - all should pass
2. Run full test suite: `pytest tests/ -v -n auto` - P1 bug tests should pass
3. Verify bug_triage_report.md has all P1 bugs marked as RESOLVED with commit hashes
4. Check no new P1 bugs introduced: `pytest tests/ -v | grep -i "fail"` should show zero P1 failures
</verification>

<success_criteria>
1. All P1 bugs from bug_triage_report.md are fixed
2. Each P1 bug has a regression test that passes
3. Full test suite passes without P1 failures
4. Bug triage report updated with fix status (RESOLVED) and commit hashes
5. No new P1 bugs introduced by fixes
</success_criteria>

<output>
After completion, create `.planning/phases/06-production-hardening/06-production-hardening-04-SUMMARY.md` with:
- P1 bugs fixed count
- Regression tests added
- Commits/fixes applied
- Updated bug triage status
</output>
