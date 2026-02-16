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
    - Proposal service tests mock correct function names from actual implementations
    - All 6 failing proposal service tests pass (4 action execution + 2 episode creation)
    - Tests correctly verify proposal approval and action execution behavior
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

**Purpose**: 6 proposal service tests fail because they mock non-existent functions or mock at wrong import locations. The tests mock functions like `execute_browser_automation`, `execute_workflow_action`, etc. that don't exist or aren't called directly by proposal_service.py.

**Actual failures** (from test run):
1. test_execute_browser_action - mocks wrong function
2. test_execute_integration_action - mocks wrong function
3. test_execute_workflow_action - mocks wrong function
4. test_execute_agent_action - mocks wrong function
5. test_extract_proposal_topics - NLP function issue
6. test_format_proposal_outcome_approved - method signature issue

**Root Cause**: Tests were written assuming function names that don't match actual implementations or mock at wrong import path.

**Output**: All 6 proposal service tests pass (40/40 total)
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
  <name>Task 1: Fix action execution test mocks (4 tests)</name>
  <files>tests/unit/governance/test_proposal_service.py</files>
  <action>
Fix all 4 failing action execution tests. These tests mock functions that don't exist or are called differently:

**Test failures:**
1. `test_execute_browser_action` - mocks `tools.browser_tool.execute_browser_automation` (doesn't exist)
2. `test_execute_integration_action` - mocks non-existent integration function
3. `test_execute_workflow_action` - mocks non-existent workflow function
4. `test_execute_agent_action` - mocks non-existent agent function

**Root cause**: Tests patch at `tools.browser_tool.execute_browser_automation` but proposal_service.py doesn't directly import/execute these functions.

**Fix approach:**

1. **Read proposal_service.py** to find actual import and execution pattern:
   - Search for `browser_automate`, `integration_connect`, `workflow_trigger`, `agent_execute`
   - Find what the service actually calls when approving proposals
   - Check if it uses a dispatcher, orchestrator, or direct imports

2. **Update mock targets** to match actual code:
   - If proposal_service imports: `from tools.browser_tool import browser_navigate`
   - Mock at: `core.proposal_service.browser_navigate` (where it's imported)
   - NOT at: `tools.browser_tool.browser_navigate` (source module)

3. **Alternative approaches:**
   - If action execution is complex, mock the entire action executor object
   - Use `patch.object(proposal_service, 'action_executor')` if applicable
   - Mock the proposal approval result directly if execution is external

**Commands to run:**
```bash
# Find actual imports in proposal_service.py
grep -n "browser_tool\|integration\|workflow\|agent" core/proposal_service.py

# Find actual action execution code
grep -n "execute_action\|approve_proposal" core/proposal_service.py
```
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/unit/governance/test_proposal_service.py::TestActionExecution -v 2>&1 | grep -E "passed|failed"
Expected: "6 passed" (all TestActionExecution tests including canvas action)
</verify>
  <done>
All 4 action execution tests pass with correct mock targets matching actual proposal_service.py imports.
</done>
</task>

<task type="auto">
  <name>Task 2: Fix episode creation tests (2 tests)</name>
  <files>tests/unit/governance/test_proposal_service.py</files>
  <action>
Fix the 2 failing episode creation tests:

**Test failures:**
1. `test_extract_proposal_topics` - NLP topic extraction issue
2. `test_format_proposal_outcome_approved` - Proposal outcome formatting issue

**For test_extract_proposal_topics:**
- Check if proposal_service actually calls NLP for topic extraction
- May need to mock the NLP service if it's external
- Verify test expectations match actual implementation behavior

**For test_format_proposal_outcome_approved:**
- Check actual method name in proposal_service.py
- May be `format_proposal_outcome` vs `format_outcome` vs different name
- Verify return format (dict vs object, field names)
- Update assertions to match actual behavior

**Debug commands:**
```bash
# Find topic extraction code
grep -n "extract.*topic\|topic.*extract" core/proposal_service.py

# Find outcome formatting code
grep -n "format.*outcome\|outcome.*format" core/proposal_service.py
```
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/unit/governance/test_proposal_service.py::TestEpisodeCreation::test_extract_proposal_topics tests/unit/governance/test_proposal_service.py::TestEpisodeCreation::test_format_proposal_outcome_approved -v 2>&1 | grep -E "PASSED|FAILED"
Expected: "2 passed"
</verify>
  <done>
Both episode creation tests pass with correct method names and assertions.
</done>
</task>

</tasks>

<verification>
1. All 6 failing tests pass: `pytest tests/unit/governance/test_proposal_service.py -v` shows 40/40 passed
2. No `AttributeError` or `TypeError` related to missing functions
3. Tests verify actual behavior of proposal_service, not stub implementations
</verification>

<success_criteria>
- All 40 proposal service tests pass (6 were failing: 4 action execution + 2 episode creation)
- Mock targets use correct import paths matching proposal_service.py
- Tests maintain their original intent (verifying proposal approval and execution)
</success_criteria>

<output>
After completion, create `.planning/phases/10-fix-tests/10-fix-tests-02-SUMMARY.md` with:
- List of corrected mock targets (old → new)
- Fixed method signatures
- Final test count (40/40 passed)
</output>
