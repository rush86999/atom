---
phase: 07-implementation-fixes
plan: 01
subsystem: test-execution
type: execute
wave: 1
depends_on: []
files_modified:
  - mobile/src/contexts/AuthContext.tsx
  - mobile/src/contexts/DeviceContext.tsx
  - backend/core/notification_service.py
  - tests/integration/test_auth_flows.py
  - tests/property_tests/database/test_database_atomicity.py
autonomous: true

must_haves:
  truths:
    - "Expo SDK 50 + Jest compatibility issue is fully resolved"
    - "notificationService.ts destructuring errors are fixed"
    - "All incomplete mobile implementations are completed or stubbed"
    - "Desktop integration issues are resolved"
  artifacts:
    - path: "mobile/src/contexts/AuthContext.tsx"
      provides: "EXPO_PUBLIC_API_URL pattern fixed, tests can run"
    - path: "mobile/src/contexts/DeviceContext.tsx"
      provides: "EXPO_PUBLIC_API_URL pattern fixed, tests can run"
    - path: "backend/core/notification_service.py"
      provides: "Fixed destructuring errors, proper error handling"
    - path: "tests/integration/test_auth_flows.py"
      provides: "Integration tests validate notification service fixes"
    - path: "tests/property_tests/database/test_database_atomicity.py"
      provides: "P1 regression tests for financial data integrity"
    - path: "tests/test_p1_regression.py"
      provides: "P1 regression test suite"
    - path: "backend/tests/coverage_reports/metrics/bug_triage_report.md"
      provides: "Updated with P1 bug fixes marked as resolved"
    - path: "backend/tests/test_isolation_validation.py"
      provides: "Assertion density improvements documented"
    - path: "backend/tests/coverage_reports/metrics/performance_baseline.json"
      provides: "Performance baseline updated with test results"
    - path: "backend/pytest.ini"
      provides: "Coverage warnings removed, pytest configuration clean"
    - path: "backend/venv/requirements.txt"
      provides: "Missing dependencies documented and added (flask, freezegun, responses)"
    - path: "frontend-nextjs/src-tauri/venv/requirements.txt"
      provides: "Desktop integration test requirements documented"
  key_links:
    - from: "mobile/src/contexts/AuthContext.tsx"
      to: "tests/integration/test_auth_flows.py"
      via: "Notification service fixes validated"
    - from: "tests/test_p1_regression.py"
      to: "bug_triage_report.md"
      via: "P1 bugs marked as RESOLVED"
    - from: "pytest.ini"
      to: "performance_baseline.json"
      via: "Clean pytest configuration speeds up tests"

---

<objective>
Fix Expo SDK 50 + Jest compatibility issue, notificationService.ts destructuring errors, and complete mobile implementations to prepare codebase for production.

**Purpose:** Phase 6 discovered several incomplete implementations and bugs that need fixing before production deployment. This plan addresses the highest priority issues systematically.

</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/STATE.md
@.planning/ROADMAP.md
</execution_context>

<context>
Phase 6 requirements from ROADMAP.md lines 140-146:
- FIX-01: Expo SDK 50 + Jest compatibility issue (RESOLVED) - mobile auth tests can run
- FIX-02: Service implementation bugs fixed (notificationService.ts destructuring errors)
- FIX-03, 04, 05: Incomplete mobile implementations completed or stubbed
- FIX-06: Desktop integration issues resolved
- FIX-07: Coverage configuration warnings resolved
</context>

<tasks>

<task type="auto">
  <name>Fix Expo SDK 50 + Jest Compatibility Issue</name>
  <files>mobile/src/contexts/AuthContext.tsx, mobile/src/contexts/DeviceContext.tsx, tests/integration/test_auth_flows.py</files>
  <action>
    Verify EXPO_PUBLIC_API_URL pattern is consistently used (Constants.expoConfig?.extra?.apiUrl) in both context files
    Update any test files that reference process.env.EXPO_PUBLIC_API_URL to use Constants.expoConfig pattern
    Add integration tests for auth context with EXPO_PUBLIC_API_URL pattern
    Run mobile test suite to verify no expo/virtual/env errors
  Document the fix in plan SUMMARY.md
  Commit changes atomically
  </action>
  <verify>
    AuthContext.tsx and DeviceContext.tsx use EXPO_PUBLIC_API_URL pattern consistently
    Integration tests pass without expo/virtual/env import errors
    Plan SUMMARY.md created with fix documented
  </done>
  <done>
    EXPO_PUBLIC_API_URL pattern fixed, tests can run, integration tests pass
  Plan SUMMARY.md created with fix documented
  </done>
</task>

<task type="auto">
  <name>Fix notificationService.ts Destructuring Errors</name>
  <files>backend/core/notification_service.py, tests/integration/test_auth_flows.py</files>
  <action>
    Fix line 158 destructuring error in notificationService.ts
    Update error handling to properly check if getExpoPushTokenAsync() returns {data} not {status}
    Add unit tests for notification service error handling
    Document the fix in plan SUMMARY.md
    Commit changes atomically
  </action>
  <verify>
    notification_service.py correctly handles getExpoPushTokenAsync response structure
    Unit tests for notification service pass
  </verify>
  <done>
    Plan SUMMARY.md created with fix documented
  </done>
</task>

<task type="auto">
  <name>Complete and Stub Mobile Implementations</name>
  <files>mobile/src/services/, mobile/src/contexts/, tests/integration/</files>
  <action>
    For each incomplete implementation found in bug triage report:
      Create or update implementation file to add proper functionality
    Add unit tests for the implementation
    Document what was stubbed and what's now implemented
    Commit changes atomically
    For notification_service fixes: add tests/integration/test_notification_service.py
    For auth context: update tests/integration/test_auth_flows.py
    For other services: create test files as needed
    Document all changes in plan SUMMARY.md
  </action>
  <verify>
    All incomplete implementations identified in bug triage report are now complete or stubbed
    Mobile implementations achieved 80% coverage target
  </verify>
  <done>
    Plan SUMMARY.md created with fix documented
  </done>
</task>

<task type="auto">
  <name>Resolve Desktop Integration Issues</name>
  <files>frontend-nextjs/src-tauri/, backend/tests/integration/</files>
  <action>
    Desktop integration issues were already resolved in Phase 6 Plan 04
    Verify resolution is still in place
    Document the resolution in plan SUMMARY.md
    Create summary of Phase 7 Plan 01
    Commit changes atomically
  </action>
  <verify>
    Desktop integration tests pass
    All desktop integration issues resolved
  </verify>
  <done>
    Plan SUMMARY.md created with resolution documented
  </done>
</task>

<task type="auto">
  <name>Clean Coverage Configuration and Final Verification</name>
  <files>backend/pytest.ini, backend/venv/requirements.txt, frontend-nextjs/src-tauri/venv/requirements.txt</files>
  <action>
    Remove deprecated pytest options from pytest.ini (--cov-fail-under, --cov-branch, [run] precision, partial_branches)
    Run full test suite to generate fresh coverage data without deprecated warnings
    Update performance_baseline.json with new metrics
    Verify coverage is trending correctly
    Document final results in plan SUMMARY.md
    Commit changes atomically
  </action>
  <verify>
    pytest.ini clean, no deprecated warnings
    Performance baseline updated with accurate test data
    Coverage trending works without warnings
  </verify>
  <done>
    Plan SUMMARY.md created with final Phase 7 completion
  </done>
</task>

</tasks>

<verification>
Overall verification steps:
1. Run mobile test suite: `cd mobile && npm test -- --coverage`
2. Run backend property tests: `PYTHONPATH=. python -m pytest tests/property_tests/ -v`
3. Run integration tests: `PYTHONPATH=. python -m pytest tests/integration/ -v`
4. Verify EXPO_PUBLIC_API_URL pattern fixed (no expo/virtual/env errors)
5. Verify notification service destructuring errors fixed
6. Verify all incomplete mobile implementations completed or stubbed
7. Verify desktop integration issues resolved (tests pass)
8. Verify pytest.ini clean, no deprecated warnings
9. Check performance_baseline.json shows updated execution time
10. Verify coverage trending configured correctly
</verification>

<success_criteria>
- [ ] All EXPO_PUBLIC_API_URL patterns fixed (Constants.expoConfig pattern)
- [ ] All notificationService.ts destructuring errors fixed
- [ ] All incomplete mobile implementations completed or stubbed
- [ ] All desktop integration issues resolved
- [ ] Coverage configuration clean, no deprecated warnings
- [ ] Test infrastructure P0/P1 bugs documented (no production P0 bugs found)
- [ ] Performance baseline updated with fresh test data
- [ ] Coverage trending configured correctly
- [ ] Full test suite executes without blocking errors
- [ ] Bug triage report updated with Phase 7 fixes
- [ ] Test infrastructure stable and performant
- [ ] Production codebase ready for deployment
- [ ] Documentation complete (test guides, bug triage, coverage trending, performance baselines)
</success_criteria>