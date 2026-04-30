# Bug Report Template (TDD Version)

**Purpose**: Template for reporting bugs with reproducible test cases.

**Version**: 1.0
**Milestone**: v12.0

---

## Bug Report Format

### Title

```
[BUG] <Component>: <Brief description of bug>
```

**Example**:
```
[BUG] AgentGovernanceService: Agent maturity allows demotion from AUTONOMOUS to STUDENT
```

---

### Template

```markdown
## Bug Description

**Component**: <Component Name>
**Severity**: <P0: Critical / P1: High / P2: Medium / P3: Low>
**Impact**: <What breaks, who is affected>

**Current Behavior**:
<Describe what is currently happening>

**Expected Behavior**:
<Describe what should happen>

**Steps to Reproduce**:
1. <Step 1>
2. <Step 2>
3. <Step 3>

**Reproducible Test**:
<Write failing test that reproduces bug>

**Environment**:
- Backend/Frontend: <Python/TypeScript version>
- Database: <PostgreSQL/SQLite version>
- Browser: <Chrome/Firefox/Safari version>

**Attachments**:
- Screenshots: <if applicable>
- Logs: <if applicable>
- Error messages: <if applicable>
```

---

## Example Bug Report

```markdown
## Bug Description

**Component**: AgentGovernanceService
**Severity**: P1 (High)
**Impact**: Security vulnerability - agents can be demoted bypassing graduation requirements

**Current Behavior**:
Agent maturity allows demotion from AUTONOMOUS to STUDENT, bypassing graduation criteria. This creates security risk as demoted agents lose capabilities they were granted.

**Expected Behavior**:
Agent maturity should only allow progression (STUDENT → INTERN → SUPERVISED → AUTONOMOUS). Demotion should be blocked with ValueError.

**Steps to Reproduce**:
1. Create agent with AUTONOMOUS maturity
2. Call `update_maturity(agent_id, AgentMaturity.STUDENT)`
3. Observe: Maturity updated to STUDENT (demotion succeeded)
4. Expected: ValueError raised (demotion blocked)

**Reproducible Test**:
```python
# backend/tests/test_agent_governance_service.py

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

**Environment**:
- Backend: Python 3.11
- Database: PostgreSQL 14
- Atom Version: v12.0

**Attachments**:
- Error message: None (no error raised, this is the bug)
- Logs: N/A

**Root Cause**:
Missing maturity transition validation in `AgentGovernanceService.update_maturity()`

**Related Issues**:
- GitHub Issue: #1234
- Jira Ticket: ATOM-5678
```

---

## Severity Guidelines

### P0: Critical
- System down (production outage)
- Data loss or corruption
- Security vulnerability (exploitable)
- **SLA**: Fix within 24 hours

### P1: High
- Major feature broken
- Significant performance degradation
- Security vulnerability (theoretical)
- **SLA**: Fix within 1 week

### P2: Medium
- Minor feature broken
- Workaround available
- UX issue (not critical)
- **SLA**: Fix within 2 weeks

### P3: Low
- Cosmetic issue
- Nice-to-have improvement
- No user impact
- **SLA**: Fix when convenient

---

## Bug Report Checklist

Before submitting bug report, verify:

- [ ] Title is descriptive (includes component and brief description)
- [ ] Severity assigned correctly (P0-P3)
- [ ] Impact clearly stated (who/what affected)
- [ ] Current behavior described (what's happening)
- [ ] Expected behavior described (what should happen)
- [ ] Steps to reproduce provided (numbered list)
- [ ] Reproducible test included (failing test that demonstrates bug)
- [ ] Environment specified (versions, browser, database)
- [ ] Attachments included (screenshots, logs, error messages)

---

## TDD Bug Fix Workflow

After bug report is filed:

1. **RED Phase**: Confirm failing test reproduces bug
   ```bash
   pytest tests/test_<bug>.py -v  # Should FAIL
   ```

2. **GREEN Phase**: Implement minimal fix
   ```bash
   pytest tests/test_<bug>.py -v  # Should PASS
   ```

3. **REFACTOR Phase**: Improve code while tests pass
   ```bash
   pytest tests/test_<bug>.py -v  # Should still PASS
   ```

4. **REGRESSION TEST**: Ensure bug doesn't reoccur
   ```bash
   pytest tests/ -v  # Full test suite passes
   ```

5. **DOCUMENTATION**: Update bug report with fix details
   - Add "Fix" section with explanation
   - Link to commit/PR
   - Close bug report as fixed

---

*Bug Report Template created for Atom v12.0*
*Purpose: Standardize bug reports with reproducible tests*
