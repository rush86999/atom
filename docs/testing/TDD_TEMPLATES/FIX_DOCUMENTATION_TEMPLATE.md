# Fix Documentation Template (Red-Green-Refactor)

**Purpose**: Template for documenting bug fixes using TDD methodology.

**Version**: 1.0
**Milestone**: v12.0

---

## Fix Documentation Format

### Title

```
[FIX] <Component>: <Brief description of fix>
```

**Example**:
```
[FIX] AgentGovernanceService: Added maturity transition validation to block demotion
```

---

### Template

```markdown
## Fix Documentation

**Component**: <Component Name>
**Bug Report**: <Link to bug report>
**Severity**: <P0/P1/P2/P3>
**Fixed By**: <Developer name>
**Date**: <YYYY-MM-DD>
**Commit**: <Commit hash>

---

## Bug Summary

**Description**:
<Describe the bug in 1-2 sentences>

**Root Cause**:
<Explain why the bug occurred>

**Impact**:
<Who was affected, what broke>

---

## Red Phase (Write Failing Test)

**Test File**: `<path/to/test_file.py>`

**Test Code**:
```python
def test_<behavior>_when_<condition>():
    """
    BUG: <Bug description>

    SCENARIO: <Describe scenario>
    EXPECTED: <Expected behavior>
    ACTUAL: <Actual behavior (bug)>
    """
    # Arrange
    <test setup>

    # Act & Assert
    with pytest.raises(<Error>, match="<message>"):
        <function_call>
```

**Test Result**: ❌ FAILED (as expected)

**Failure Message**:
```
<Error output showing test failure>
```

**Key Insight**:
<What did this test reveal about the bug?>

---

## Green Phase (Write Minimal Fix)

**Implementation File**: `<path/to/implementation_file.py>`

**Minimal Fix**:
```python
def <function>(<params>):
    """<Brief description>."""
    <Minimal code to make test pass>
```

**Test Result**: ✅ PASSED

**Key Insight**:
<Why is this the minimal fix?>

---

## Refactor Phase (Improve Code)

**Refactored Implementation**:
```python
class <Service>:
    def <function>(self, <params>):
        """<Improved description>."""
        <Refactored code>

    def _helper_method(self, <params>):
        """<Helper description>."""
        <Helper logic>
```

**Test Result**: ✅ PASSED (all tests still pass)

**Key Insight**:
<How did refactoring improve code quality?>

---

## Regression Prevention

**Test Added**: `<path/to/test_file.py>`

**Test Coverage**: This test prevents bug from reoccurring by:
1. <How test prevents regression>
2. <What scenarios are covered>
3. <Why this test is effective>

---

## Lessons Learned

**What went well**:
- <Positive outcomes>

**What could be improved**:
- <Areas for improvement>

**Recommendations for future**:
- <How to prevent similar bugs>

---

## Related Changes

**Files Modified**:
- `<path/to/file1.py>`: <Description of changes>
- `<path/to/file2.py>`: <Description of changes>

**Tests Added**:
- `<path/to/test_file.py>`: <Description of test>

**Documentation Updated**:
- `<path/to/docs.md>`: <Description of updates>

---

## Verification

**Full Test Suite**: ✅ PASSED
```bash
pytest tests/ -v
# <number> tests passed
```

**Code Review**: ✅ APPROVED
- Reviewed by: <Reviewer name>
- Approval date: <YYYY-MM-DD>

**Deployment**: ✅ DEPLOYED
- Deployment date: <YYYY-MM-DD>
- Environment: <staging/production>

---

## References

**Bug Report**: <Link>
**Commit**: <Link to commit>
**PR**: <Link to pull request>
**Related Issues**: <Links to related issues>
```

---

## Example Fix Documentation

```markdown
## Fix Documentation

**Component**: AgentGovernanceService
**Bug Report**: [LINK] Agent maturity allows demotion (security risk)
**Severity**: P1 (High)
**Fixed By**: John Doe
**Date**: 2026-04-29
**Commit**: abc123def456

---

## Bug Summary

**Description**:
Agent maturity validation allows demotion from AUTONOMOUS to STUDENT, bypassing graduation requirements and creating security vulnerability.

**Root Cause**:
Missing maturity transition validation in `AgentGovernanceService.update_maturity()`. Function allowed any maturity transition without checking if it was a demotion.

**Impact**:
Agents could be demoted, losing capabilities they were granted. This bypasses graduation criteria and creates security risk (demoted agents might retain some permissions).

---

## Red Phase (Write Failing Test)

**Test File**: `backend/tests/test_agent_governance_service.py`

**Test Code**:
```python
def test_agent_maturity_blocks_demotion():
    """
    BUG: Agent maturity allows demotion from AUTONOMOUS to STUDENT.

    SCENARIO: Demote agent from AUTONOMOUS to STUDENT
    EXPECTED: ValueError raised (demotion not allowed)
    ACTUAL: Demotion succeeds (security risk)
    """
    # Arrange
    agent = AgentRegistry(
        id="test-agent",
        maturity=AgentMaturity.AUTONOMOUS
    )

    with SessionLocal() as db:
        db.add(agent)
        db.commit()

        service = AgentGovernanceService(db)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid maturity transition"):
            service.update_maturity("test-agent", AgentMaturity.STUDENT)
```

**Test Result**: ❌ FAILED (as expected)

**Failure Message**:
```
FAILED - Function: update_maturity() completed without error
Expected: ValueError("Invalid maturity transition")
Actual: No exception raised
```

**Key Insight**:
Test confirmed bug exists - demotion was allowed when it should be blocked.

---

## Green Phase (Write Minimal Fix)

**Implementation File**: `backend/core/agent_governance_service.py`

**Minimal Fix**:
```python
def update_maturity(self, agent_id: str, new_maturity: AgentMaturity):
    """Update agent maturity level."""
    agent = self.db.query(AgentRegistry).filter_by(id=agent_id).first()

    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    # Add validation to block demotion
    maturity_levels = {
        AgentMaturity.STUDENT: 1,
        AgentMaturity.INTERN: 2,
        AgentMaturity.SUPERVISED: 3,
        AgentMaturity.AUTONOMOUS: 4,
    }

    current_level = maturity_levels[agent.maturity]
    new_level = maturity_levels[new_maturity]

    if new_level < current_level:
        raise ValueError(
            f"Invalid maturity transition: {agent.maturity} → {new_maturity}"
        )

    agent.maturity = new_maturity
    self.db.commit()
```

**Test Result**: ✅ PASSED

**Key Insight**:
Maturity levels mapped to integers, allowing comparison. Demotion detected when new level < current level.

---

## Refactor Phase (Improve Code)

**Refactored Implementation**:
```python
class AgentGovernanceService:
    def update_maturity(self, agent_id: str, new_maturity: AgentMaturity):
        """Update agent maturity level with validation."""
        agent = self._get_agent(agent_id)
        self._validate_maturity_transition(agent.maturity, new_maturity)

        agent.maturity = new_maturity
        self.db.commit()

    def _get_agent(self, agent_id: str) -> AgentRegistry:
        """Fetch agent by ID."""
        agent = self.db.query(AgentRegistry).filter_by(id=agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        return agent

    def _validate_maturity_transition(self, current, new):
        """Validate that maturity transition is allowed (no demotion)."""
        if self._is_demotion(current, new):
            raise ValueError(
                f"Invalid maturity transition: {current} → {new}. "
                f"Demotion not allowed (graduation required)."
            )

    def _is_demotion(self, current: AgentMaturity, new: AgentMaturity) -> bool:
        """Check if maturity transition is a demotion."""
        levels = {
            AgentMaturity.STUDENT: 1,
            AgentMaturity.INTERN: 2,
            AgentMaturity.SUPERVISED: 3,
            AgentMaturity.AUTONOMOUS: 4,
        }
        return levels[new] < levels[current]
```

**Test Result**: ✅ PASSED (all tests still pass)

**Key Insight**:
Extracted methods improve testability and reusability. `_is_demotion` can be tested independently.

---

## Regression Prevention

**Test Added**: `backend/tests/test_agent_governance_service.py`

**Test Coverage**: This test prevents bug from reoccurring by:
1. Testing all maturity transitions (including demotion)
2. Ensuring ValueError is raised for demotion
3. Verifying error message is descriptive
4. Testing edge cases (AUTONOMOUS → STUDENT, all demotions)

---

## Lessons Learned

**What went well**:
- TDD approach caught bug early (before production)
- Test clearly documents expected behavior
- Refactoring improved code quality
- Regression test prevents future issues

**What could be improved**:
- Should have added validation when feature was initially implemented
- Maturity transitions should have been designed as state machine from start

**Recommendations for future**:
- All state transitions should have explicit validation
- Security-sensitive features require TDD (no exceptions)
- State machine design prevents invalid transitions

---

## Related Changes

**Files Modified**:
- `backend/core/agent_governance_service.py`: Added maturity transition validation, extracted 3 helper methods

**Tests Added**:
- `backend/tests/test_agent_governance_service.py`: Added `test_agent_maturity_blocks_demotion` test

**Documentation Updated**:
- `docs/AGENT_MATURITY_TRANSITIONS.md`: Documented valid transitions
- `docs/SECURITY_CONSIDERATIONS.md`: Added governance validation section

---

## Verification

**Full Test Suite**: ✅ PASSED
```bash
pytest backend/tests/ -v
# 195 tests passed (100% pass rate)
```

**Code Review**: ✅ APPROVED
- Reviewed by: Jane Smith
- Approval date: 2026-04-29
- Feedback: "Great TDD workflow, clear validation logic"

**Deployment**: ✅ DEPLOYED
- Deployment date: 2026-04-29
- Environment: Production (no issues)

---

## References

**Bug Report**: [LINK] GitHub Issue #1234
**Commit**: [LINK] abc123def456
**PR**: [LINK] Pull Request #567
**Related Issues**: [LINK] Graduation framework design
```

---

## Fix Documentation Checklist

Before documenting fix, verify:

- [ ] Bug summary clearly described
- [ ] Root cause explained
- [ ] Impact stated (who/what affected)
- [ ] Red phase: Failing test included
- [ ] Green phase: Minimal fix shown
- [ ] Refactor phase: Code improvements documented
- [ ] Regression prevention explained
- [ ] Lessons learned included
- [ ] Related changes listed
- [ ] Verification completed (tests pass, review approved, deployed)

---

## Usage

1. **Before Fix**: Create bug report using [Bug Report Template](BUG_REPORT_TEMPLATE.md)
2. **During Fix**: Follow red-green-refactor cycle (document each phase)
3. **After Fix**: Complete this template and commit to repository
4. **Archive**: Store fix documentation in `/docs/testing/FIXES/<year>/<component>/`

---

*Fix Documentation Template created for Atom v12.0*
*Purpose: Document bug fixes using TDD methodology*
