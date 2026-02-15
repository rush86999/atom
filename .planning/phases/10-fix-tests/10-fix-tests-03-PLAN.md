---
phase: 10-fix-tests
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/unit/governance/test_agent_graduation_governance.py
  - tests/factories/agent_factory.py
autonomous: true

must_haves:
  truths:
    - Agent factories use correct parameters for AgentRegistry model
    - Graduation governance tests pass without TypeError
    - Tests correctly verify agent promotion and maturity level updates
  artifacts:
    - path: "tests/unit/governance/test_agent_graduation_governance.py"
      provides: "Graduation governance unit tests"
      contains: "TestPermissionMatrixValidation"
    - path: "tests/factories/agent_factory.py"
      provides: "Test data factories for agents"
      contains: "AgentRegistry"
  key_links:
    - from: "tests/factories/agent_factory.py"
      to: "core.models.AgentRegistry"
      via: "factory_boy"
      pattern: "class .*AgentFactory"
---

<objective>
Fix graduation governance test failures due to invalid factory parameters

**Purpose**: 6 graduation governance tests fail because test factories pass `metadata_json={}` parameter to AgentRegistry, but the model doesn't accept this parameter.

**Root Cause**: Factory Boy configurations use outdated AgentRegistry model signature. The `metadata_json` field may have been removed or renamed in the model.

**Output**: All 6 graduation governance tests pass
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/ROADMAP.md
</execution_context>

<context>
@.planning/ROADMAP.md
@backend/core/models.py
@backend/tests/factories/agent_factory.py
@backend/tests/unit/governance/test_agent_graduation_governance.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Identify correct AgentRegistry parameters</name>
  <files>core/models.py</files>
  <action>
Check AgentRegistry model definition to find valid parameters:

1. Search for `class AgentRegistry` in `core/models.py`
2. List all Column and field definitions
3. Identify which fields are writable vs computed
4. Check if `metadata_json` exists under a different name (e.g., `metadata`, `config`)

Command: `grep -A 50 "class AgentRegistry" core/models.py | grep -E "Column|metadata|json"`

Expected output: List of valid field names for AgentRegistry
</action>
  <verify>
# After inspection, the correct field name should be identified
# Common alternatives: metadata, configuration, settings
</verify>
  <done>
Identified valid AgentRegistry field names. Confirmed whether metadata_json exists or needs replacement.
</done>
</task>

<task type="auto">
  <name>Task 2: Fix agent factory configurations</name>
  <files>tests/factories/agent_factory.py</files>
  <action>
Update agent factory classes to use correct parameters:

**If `metadata_json` doesn't exist**:
1. Remove `metadata_json` from all factory class definitions
2. Update factory `Meta.model` if needed
3. Check for any other outdated parameters

**If `metadata_json` was renamed**:
1. Replace `metadata_json` with correct field name
2. Update all factory classes: StudentAgentFactory, InternAgentFactory, etc.

**Classes to check**:
- StudentAgentFactory
- InternAgentFactory
- SupervisedAgentFactory
- AutonomousAgentFactory

**Pattern**: Find and replace `metadata_json` occurrences or remove entirely if not valid.
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend python -c "from tests.factories import StudentAgentFactory; print('Factory imports successfully')" 2>&1
Expected: No ImportError or TypeError
</verify>
  <done>
Agent factory classes use correct AgentRegistry parameters. No `metadata_json` errors.
</done>
</task>

<task type="auto">
  <name>Task 3: Fix test code that uses metadata_json parameter</name>
  <files>tests/unit/governance/test_agent_graduation_governance.py</files>
  <action>
Find and fix test code that directly passes `metadata_json`:

1. Search for `metadata_json` in the test file
2. Remove or replace the parameter in test code
3. Update test assertions if they depend on metadata values

**Tests to fix** (from failures):
- test_promote_agent_updates_maturity_level
- test_promote_with_invalid_maturity_returns_false
- test_promotion_metadata_updated
- test_performance_trend_calculation
- test_promote_agent_updates_timestamp
- test_constitutional_score_with_none_values

**Example fix**:
```python
# Before (broken):
agent = StudentAgentFactory(_session=db_session, metadata_json={})

# After (fixed):
agent = StudentAgentFactory(_session=db_session)
# or if metadata field exists with different name:
agent = StudentAgentFactory(_session=db_session, metadata={})
```
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/unit/governance/test_agent_graduation_governance.py -v 2>&1 | grep -E "passed|failed"
Expected: "28 passed" (all tests, currently 22 passed, 6 failed)
</verify>
  <done>
All 6 graduation governance tests pass. Factory creates valid AgentRegistry instances.
</done>
</task>

</tasks>

<verification>
1. All graduation governance tests pass: `pytest tests/unit/governance/test_agent_graduation_governance.py -v` shows 28/28 passed
2. No `TypeError: 'metadata_json' is an invalid keyword argument for AgentRegistry`
3. Factories create valid agent instances for all maturity levels
</verification>

<success_criteria>
- All 28 graduation governance tests pass (6 were failing, now fixed)
- Factory Boy configurations match current AgentRegistry model schema
- Tests use correct field names when creating test agents
</success_criteria>

<output>
After completion, create `.planning/phases/10-fix-tests/10-fix-tests-03-SUMMARY.md` with:
- Corrected field name (metadata_json → correct_name or removed)
- Number of factories updated
- Final test count (28/28 passed)
</output>
