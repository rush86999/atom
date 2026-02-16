---
phase: 10-fix-tests
plan: 04
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/unit/governance/test_agent_graduation_governance.py
  - tests/factories/agent_factory.py
autonomous: true

must_haves:
  truths:
    - Agent factories use correct parameters for AgentRegistry model (configuration field, not metadata_json)
    - Graduation governance tests pass without TypeError or flaky reruns
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

**Purpose**: 3 graduation governance tests fail with flaky reruns because test factories pass `metadata_json={}` parameter to AgentRegistry, but the model uses `configuration` field instead. Additionally, tests may be timing-dependent causing flaky behavior.

**Actual failures** (from test run with 3 reruns):
1. test_promote_agent_updates_maturity_level - flaky, fails on reruns
2. test_promote_with_invalid_maturity_returns_false - flaky, fails on reruns
3. test_promotion_metadata_updated - flaky, fails on reruns

**Root Cause**: Factory Boy configurations use `metadata_json={}` parameter but AgentRegistry model has `configuration` field (JSON). This causes test instability and flaky behavior.

**Output**: All 3 graduation governance tests pass consistently (no flaky reruns)
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
  <name>Task 1: Verify AgentRegistry model fields and identify issue</name>
  <files>core/models.py</files>
  <action>
Check AgentRegistry model definition to confirm field names:

1. Read `class AgentRegistry` in `core/models.py` (around line 562)
2. List all JSON/Column fields
3. Confirm: The model has `configuration` JSON field, NOT `metadata_json`

Expected findings:
- `configuration = Column(JSON, default={})` exists
- `metadata_json` does NOT exist
- `schedule_config = Column(JSON, default={})` exists

The tests pass `metadata_json={}` to factories but the model doesn't have this field.
</action>
  <verify>
grep -A 30 "class AgentRegistry" /Users/rushiparikh/projects/atom/backend/core/models.py | grep -E "Column|JSON|configuration"
Expected output should show `configuration` as JSON field, no `metadata_json`
</verify>
  <done>
Confirmed: AgentRegistry has `configuration` field, not `metadata_json`.
</done>
</task>

<task type="auto">
  <name>Task 2: Fix agent factory configurations</name>
  <files>tests/factories/agent_factory.py</files>
  <action>
Update agent factory classes to remove invalid `metadata_json` parameter:

**Problem**: Factories pass `metadata_json={}` but AgentRegistry doesn't have this field.

**Fix**: Remove `metadata_json` from all agent factory classes:
- StudentAgentFactory
- InternAgentFactory
- SupervisedAgentFactory
- AutonomousAgentFactory

**Action**:
1. Find all occurrences of `metadata_json` in agent_factory.py
2. Remove the parameter from factory class definitions
3. If factories need default configuration, use `configuration={}` instead (matches AgentRegistry model)

**Example**:
```python
# Before (broken):
class StudentAgentFactory(BaseFactory):
    class Meta:
        model = AgentRegistry
    metadata_json = {}

# After (fixed):
class StudentAgentFactory(BaseFactory):
    class Meta:
        model = AgentRegistry
    # Remove metadata_json entirely or use:
    configuration = {}  # This matches the actual model field
```
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend python -c "from tests.factories import StudentAgentFactory; print('Factory OK')" 2>&1
Expected: "Factory OK" with no TypeError about invalid keyword argument
</verify>
  <done>
Agent factory classes use correct AgentRegistry parameters. No `metadata_json` errors.
</done>
</task>

<task type="auto">
  <name>Task 3: Fix test code that uses metadata_json parameter</name>
  <files>tests/unit/governance/test_agent_graduation_governance.py</files>
  <action>
Find and remove `metadata_json={}` from test code:

1. Search for `metadata_json` in test_agent_graduation_governance.py
2. Remove the parameter from all factory calls
3. Don't replace with `configuration={}` unless tests specifically need it

**Tests to fix** (from flaky failures):
- Line 248: `test_promote_agent_updates_maturity_level` has `metadata_json={}`
- Line 282: `test_promote_with_invalid_maturity_returns_false` has `metadata_json={}`
- Line 296: `test_promotion_metadata_updated` has `metadata_json={}`

**Fix**:
```python
# Before:
agent = StudentAgentFactory(_session=db_session, metadata_json={})

# After:
agent = StudentAgentFactory(_session=db_session)
```

The flaky behavior (reruns) likely comes from pytest rerunfailures plugin detecting test instability caused by the invalid parameter.
</action>
  <verify>
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/unit/governance/test_agent_graduation_governance.py::TestPermissionMatrixValidation -v 2>&1 | grep -E "passed|failed|RERUN"
Expected: "10 passed" with 0 RERUN indicators (all tests pass consistently)
</verify>
  <done>
All 3 graduation governance tests pass consistently without flaky reruns. No `metadata_json` in test code.
</done>
</task>

</tasks>

<verification>
1. All graduation governance tests pass: `pytest tests/unit/governance/test_agent_graduation_governance.py -v` shows 28/28 passed
2. No flaky reruns (RERUN markers in output)
3. No `TypeError: 'metadata_json' is an invalid keyword argument for AgentRegistry`
4. Factories create valid agent instances for all maturity levels
</verification>

<success_criteria>
- All 28 graduation governance tests pass (3 were failing/flaky, now fixed)
- Factory Boy configurations match current AgentRegistry model schema
- Tests run consistently without rerunfailures plugin triggering
</success_criteria>

<output>
After completion, create `.planning/phases/10-fix-tests/10-fix-tests-04-SUMMARY.md` with:
- Fixed parameter (metadata_json removed from factories and tests)
- Number of factories updated
- Final test count (28/28 passed, no flaky behavior)
</output>
