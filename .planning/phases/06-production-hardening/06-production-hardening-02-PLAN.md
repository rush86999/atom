---
phase: 06-production-hardening
plan: 02
type: execute
wave: 2
depends_on: [06-production-hardening-01]
files_modified:
  - backend/core/agent_governance_service.py
  - backend/core/episode_segmentation_service.py
  - backend/core/episode_retrieval_service.py
  - backend/core/models.py
  - backend/api/atom_agent_endpoints.py
  - backend/tests/coverage_reports/metrics/bug_triage_report.md
autonomous: true

must_haves:
  truths:
    - "All P0 (critical) bugs are fixed with regression tests"
    - "P0 fixes are verified with passing tests"
    - "Bug triage report updated with fix status"
    - "No new P0 bugs introduced by fixes"
  artifacts:
    - path: "backend/core/agent_governance_service.py"
      provides: "Agent governance with P0 bug fixes"
    - path: "backend/core/episode_segmentation_service.py"
      provides: "Episode segmentation with P0 bug fixes"
    - path: "backend/core/episode_retrieval_service.py"
      provides: "Episode retrieval with P0 bug fixes"
    - path: "backend/core/models.py"
      provides: "Database models with P0 constraint fixes"
    - path: "backend/api/atom_agent_endpoints.py"
      provides: "API endpoints with P0 security fixes"
    - path: "backend/tests/coverage_reports/metrics/bug_triage_report.md"
      provides: "Updated bug status after P0 fixes"
  key_links:
    - from: "06-production-hardening-01-PLAN.md"
      to: "06-production-hardening-02-PLAN.md"
      via: "bug_triage_report.md"
      pattern: "P0.*Critical"
    - from: "bug_triage_report.md"
      to: "backend/core/*.py"
      via: "P0 bug fixes"
      pattern: "fix.*P0|P0.*resolved"
    - from: "backend/tests"
      to: "backend/core/*.py"
      via: "regression tests"
      pattern: "test_p0_*|regression"
---

<objective>
Fix all P0 (critical) bugs discovered in Plan 01 with regression tests, verify fixes pass, and update bug triage report.

**Purpose:** P0 bugs represent security vulnerabilities, data loss/corruption, and cost leaks that must be fixed within 24 hours. This plan addresses the highest-priority issues to prevent production failures and security incidents.

**Output:**
- Fixed P0 bugs in core service files
- Regression tests preventing future P0 bugs
- Updated bug_triage_report.md with fix status
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/06-production-hardening/06-RESEARCH.md
@.planning/phases/06-production-hardening/06-production-hardening-01-SUMMARY.md
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Bug triage from Plan 01
@/Users/rushiparikh/projects/atom/backend/tests/coverage_reports/metrics/bug_triage_report.md
</context>

<tasks>

<task type="auto">
  <name>Fix P0 Security Vulnerabilities</name>
  <files>backend/core/agent_governance_service.py, backend/core/models.py, backend/api/atom_agent_endpoints.py</files>
  <action>
Fix P0 security bugs identified in bug_triage_report.md:

Common P0 security patterns from RESEARCH.md:
1. **JWT validation bypass** - Ensure tokens are properly validated with signature verification
2. **Authorization bypass** - Verify maturity/permission matrix is enforced before action execution
3. **Input validation failures** - Add OWASP Top 10 payload validation for all user inputs
4. **Canvas JavaScript security** - Ensure AUTONOMOUS-only enforcement for JS execution
5. **SQL injection prevention** - Verify parameterized queries only (no string concatenation)

For each P0 security bug:
1. Add regression test BEFORE fixing:
   ```python
   def test_p0_security_<bug_name>_regression(self):
       """
       Regression test for P0 security bug: <description>.

       VALIDATED_BUG: Discovered Phase 6 Plan 01
       Fix: <commit_hash>
       """
       # Test that the vulnerability is prevented
       with pytest.raises(SecurityError):
           vulnerable_operation()
   ```

2. Fix the vulnerability in source code
3. Verify test passes with fix
4. Document fix in bug_triage_report.md:
   - Add "Fixed:" section with commit hash
   - Mark status as RESOLVED

**DO NOT**: Make security exceptions or bypasses for convenience
  </action>
  <verify>For each P0 security bug: (1) Regression test added and passing, (2) Source code fix implemented, (3) Bug triage report marked RESOLVED with commit hash</verify>
  <done>All P0 security vulnerabilities fixed with regression tests preventing recurrence, bug_triage_report.md updated with fix status and commit hashes</done>
</task>

<task type="auto">
  <name>Fix P0 Data Loss/Corruption Bugs</name>
  <files>backend/core/episode_segmentation_service.py, backend/core/episode_retrieval_service.py, backend/core/models.py</files>
  <action>
Fix P0 data integrity bugs identified in bug_triage_report.md:

Common P0 data loss patterns from INVARIANTS.md:
1. **Database atomicity violations** - Ensure transactions are all-or-nothing with proper try/except
2. **Transaction rollback failures** - Verify rollback actually restores state (deep copy issue)
3. **Episode data loss** - Ensure segmentation boundaries preserve all data
4. **Foreign key violations** - Validate child records reference existing parents
5. **Constraint violations** - Ensure CHECK constraints are enforced (balance >= 0, etc.)

For each P0 data loss bug:
1. Add regression test BEFORE fixing:
   ```python
   def test_p0_data_loss_<bug_name>_regression(self, db_session):
       """
       Regression test for P0 data loss bug: <description>.

       VALIDATED_BUG: Discovered Phase 6 Plan 01
       Fix: <commit_hash>
       """
       # Test that data loss cannot occur
       # ... test scenario that previously caused loss
       assert data_integrity_preserved
   ```

2. Fix the data loss issue in source code
3. Verify test passes with fix
4. Document fix in bug_triage_report.md

For database-related issues:
- Use explicit transaction boundaries: `with db_session.begin():`
- Add proper error handling: `try: ... except: db_session.rollback()`
- Verify foreign key constraints in schema
  </action>
  <verify>For each P0 data loss bug: (1) Regression test added and passing, (2) Database transaction code fixed with proper atomicity, (3) Bug triage report marked RESOLVED</verify>
  <done>All P0 data loss/corruption bugs fixed with regression tests, database transaction integrity verified, bug_triage_report.md updated with fix status</done>
</task>

<task type="auto">
  <name>Fix P0 Cost Leaks and Resource Exhaustion</name>
  <files>backend/core/agent_governance_service.py, backend/api/atom_agent_endpoints.py</files>
  <action>
Fix P0 cost leak bugs identified in bug_triage_report.md:

Common P0 cost leak patterns from RESEARCH.md:
1. **Unbounded API calls** - Add pagination limits and timeout controls
2. **Infinite loops** - Ensure all loops have exit conditions
3. **Missing rate limits** - Add throttling for external service calls
4. **Resource not released** - Verify proper cleanup (connections, file handles)
5. **Retry storms** - Ensure exponential backoff with max retries

For each P0 cost leak bug:
1. Add regression test BEFORE fixing:
   ```python
   def test_p0_cost_leak_<bug_name>_regression(self):
       """
       Regression test for P0 cost leak bug: <description>.

       VALIDATED_BUG: Discovered Phase 6 Plan 01
       Fix: <commit_hash>
       """
       # Test that resource is bounded
       # ... test scenario that previously leaked
       assert operations_completed < max_limit
   ```

2. Fix the resource leak in source code
3. Verify test passes with fix
4. Document fix in bug_triage_report.md

For API-related issues:
- Add timeout parameters to all HTTP calls
- Use context managers for resources: `with ...`
- Add circuit breakers for external dependencies
  </action>
  <verify>For each P0 cost leak bug: (1) Regression test added and passing, (2) Resource limits implemented with timeouts and cleanup, (3) Bug triage report marked RESOLVED</verify>
  <done>All P0 cost leak/resource exhaustion bugs fixed with regression tests, resource limits properly implemented, bug_triage_report.md updated with fix status</done>
</task>

</tasks>

<verification>
1. Run regression tests: `pytest tests/test_p0_*_regression.py -v` - all should pass
2. Run full test suite: `pytest tests/ -v -n auto` - P0 bug tests should pass
3. Verify bug_triage_report.md has all P0 bugs marked as RESOLVED with commit hashes
4. Check no new P0 bugs introduced: `pytest tests/ -v | grep -i "fail"` should show zero P0 failures
</verification>

<success_criteria>
1. All P0 bugs from bug_triage_report.md are fixed
2. Each P0 bug has a regression test that passes
3. Full test suite passes without P0 failures
4. Bug triage report updated with fix status (RESOLVED) and commit hashes
5. No new P0 bugs introduced by fixes
</success_criteria>

<output>
After completion, create `.planning/phases/06-production-hardening/06-production-hardening-02-SUMMARY.md` with:
- P0 bugs fixed count
- Regression tests added
- Commits/fixes applied
- Updated bug triage status
</output>
