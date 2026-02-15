---
phase: 10-fix-tests
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/unit/governance/test_proposal_service.py
autonomous: true

must_haves:
  truths:
    - Proposal service tests mock correct function names from browser_tool and canvas_tool
    - All 5 failing proposal service tests pass
    - Tests correctly verify execute_proposed_action behavior
  artifacts:
    - path: "tests/unit/governance/test_proposal_service.py"
      provides: "Proposal service unit tests"
      contains: "TestActionExecution"
  key_links:
    - from: "tests/unit/governance/test_proposal_service.py"
      to: "tools/browser_tool"
      via: "mock patch"
      pattern: "patch\\('tools\\.browser_tool\\."
---

<objective>
Fix proposal service test failures due to incorrect mock targets

**Purpose**: 5 proposal service tests fail because they mock non-existent functions (`execute_browser_automation`, `execute_canvas_presentation`, `execute_workflow_action`, `execute_agent_action`). The actual functions in these modules have different names.

**Root Cause**: Tests were written assuming function names that don't exist in the actual implementations. Need to update mock targets to match real function names.

**Output**: All 5 proposal service tests pass with correct mocks
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/ROADMAP.md
</execution_context>

<context>
@.planning/ROADMAP.md
@backend/tools/browser_tool.py
@backend/tools/canvas_tool.py
@backend/core/workflow_engine.py
@backend/tests/unit/governance/test_proposal_service.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix browser action test mock target</name>
  <files>tests/unit/governance/test_proposal_service.py</files>
  <action>
Fix `test_execute_browser_action` (around line 742):

**Current (broken)**:
```python
with patch('tools.browser_tool.execute_browser_automation', new=AsyncMock(...))
```

**Problem**: `execute_browser_automation` doesn't exist in `tools/browser_tool.py`

**Available functions** (from grep of browser_tool.py):
- `browser_create_session`
- `browser_navigate`
- `browser_screenshot`
- `browser_fill_form`
- `browser_click`
- `browser_close_session`
- etc.

**Solution**: The test should mock at the proposal_service import location, not directly at browser_tool. Check how `proposal_service.py` imports and calls browser functions:

1. Read `core/proposal_service.py` to find the actual import and function call
2. Update the mock to target the correct location
3. If the function is called differently, update both the mock and test expectations

**Alternative**: If the proposal service doesn't directly call browser_tool but uses an orchestration layer, mock that layer instead.
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/unit/governance/test_proposal_service.py::TestActionExecution::test_execute_browser_action -v 2>&1 | grep -E "PASSED|FAILED"
Expected: "PASSED"
</verify>
  <done>
test_execute_browser_action passes with correct mock target.
</done>
</task>

<task type="auto">
  <name>Task 2: Fix integration, workflow, and agent action test mocks</name>
  <files>tests/unit/governance/test_proposal_service.py</files>
  <action>
Fix the remaining 4 failing tests with same approach:

1. **test_execute_integration_action** - Mock the correct integration execution function
   - Check how proposal_service executes integration actions
   - Mock at the correct import location

2. **test_execute_workflow_action** - Mock the correct workflow execution function
   - Check how proposal_service executes workflow actions
   - Functions available: `workflow_engine.execute_workflow()` or similar

3. **test_execute_agent_action** - Mock the correct agent execution function
   - Check how proposal_service executes agent actions
   - Likely uses `agent_governance_service` or similar

4. **test_format_proposal_outcome_approved** - Check proposal outcome formatting
   - May need to verify the actual method name and signature
   - Update test assertions to match real behavior

**For each test**:
1. Read `core/proposal_service.py` to find how actions are executed
2. Identify the actual function being called
3. Update mock target to use correct import path
4. Update return value if needed to match actual function signature
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/unit/governance/test_proposal_service.py::TestActionExecution -v 2>&1 | grep -E "passed|failed"
Expected: "4 passed" (all TestActionExecution tests)
</verify>
  <done>
All 4 action execution tests pass with correct mock targets.
</done>
</task>

<task type="auto">
  <name>Task 3: Fix test_format_proposal_outcome_approved</name>
  <files>tests/unit/governance/test_proposal_service.py</files>
  <action>
Fix `test_format_proposal_outcome_approved` test:

**Issue**: The test expects a specific method name or format that may not match implementation.

**Steps**:
1. Read the test to understand expected behavior
2. Check actual implementation in `proposal_service.py`
3. Update test to match actual method signature and return value
4. Ensure assertions verify correct formatting

**Common issues**:
- Method renamed: `format_proposal_outcome` → `format_outcome` or similar
- Return format differs: expects dict but returns object, or vice versa
- Missing field: test checks for field that doesn't exist
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/unit/governance/test_proposal_service.py::TestEpisodeCreation::test_format_proposal_outcome_approved -v 2>&1 | grep -E "PASSED|FAILED"
Expected: "PASSED"
</verify>
  <done>
test_format_proposal_outcome_approved passes with correct assertions.
</done>
</task>

</tasks>

<verification>
1. All 5 proposal service tests pass: `pytest tests/unit/governance/test_proposal_service.py -v` shows 40/40 passed
2. No `AttributeError` or `TypeError` related to missing functions
3. Tests verify actual behavior of proposal_service, not stub implementations
</verification>

<success_criteria>
- All 40 proposal service tests pass (5 were failing, now fixed)
- Mock targets use correct function names from actual implementations
- Tests maintain their original intent (verifying proposal execution behavior)
</success_criteria>

<output>
After completion, create `.planning/phases/10-fix-tests/10-fix-tests-02-SUMMARY.md` with:
- List of corrected mock targets (old → new)
- Final test count (40/40 passed)
</output>
