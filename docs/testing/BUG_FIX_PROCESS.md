# Bug Fix Process

**Last Updated:** 2026-04-12
**Status:** Production Ready

---

## Overview

This document describes the standardized bug fix process at Atom, following Test-Driven Development (TDD) principles. All bug fixes must follow the red-green-refactor cycle to ensure quality and prevent regressions.

---

## Philosophy

**Why TDD for Bug Fixes?**

1. **Prevents Regression:** Failing tests ensure bugs don't reoccur
2. **Documents Intent:** Tests explain what the code should do
3. **Enables Refactoring:** Safe code improvements with test safety net
4. **Catches Root Causes:** Tests often reveal deeper issues

**Core Principle:** *Never fix a bug without a test that fails before the fix and passes after.*

---

## The Bug Fix Workflow

### Phase 1: Red (Write Failing Test)

**Goal:** Reproduce the bug with a failing test.

**Steps:**

1. **Understand the Bug**
   - Read bug report carefully
   - Reproduce the bug manually
   - Identify the affected component
   - Understand expected vs. actual behavior

2. **Write a Minimal Test Case**
   ```python
   # Example: Bug - Agent maturity validation not working
   def test_agent_maturity_validation_blocks_demotion():
       """AUTONOMOUS agents cannot be demoted to STUDENT."""
       agent = AgentRegistry(
           id="test-auto",
           maturity=AgentMaturity.AUTONOMOUS
       )
       service = AgentGovernanceService(db_session)

       # This should fail but currently doesn't (BUG)
       with pytest.raises(ValueError, match="Invalid maturity transition"):
           service.update_maturity("test-auto", AgentMaturity.STUDENT)
   ```

3. **Verify Test Fails**
   ```bash
   pytest tests/test_bug_fix.py -v
   # Expected: FAILED (test identifies the bug)
   ```

4. **Commit Failing Test**
   ```bash
   git add tests/test_bug_fix.py
   git commit -m "test: add failing test for maturity validation bug"
   ```

**Success Criteria:**
- [ ] Test reproduces the bug
- [ ] Test fails with clear error message
- [ ] Test name describes the bug
- [ ] Test is isolated and independent

---

### Phase 2: Green (Make Test Pass)

**Goal:** Fix the bug with minimal code changes.

**Steps:**

1. **Identify Root Cause**
   - Use debugger or print statements
   - Trace code execution
   - Find where expected behavior diverges
   - Don't just patch symptoms

2. **Write Minimal Fix**
   ```python
   # Example fix in agent_governance_service.py
   def update_maturity(self, agent_id: str, new_maturity: AgentMaturity):
       agent = self.get_agent(agent_id)
       if not agent:
           raise ValueError(f"Agent {agent_id} not found")

       # FIX: Add validation to prevent demotion
       if self._is_demotion(agent.maturity, new_maturity):
           raise ValueError(
               f"Invalid maturity transition: "
               f"{agent.maturity} → {new_maturity}"
           )

       agent.maturity = new_maturity
       self.db.commit()
       return agent
   ```

3. **Run Test**
   ```bash
   pytest tests/test_bug_fix.py -v
   # Expected: PASSED (fix works)
   ```

4. **Run Full Test Suite**
   ```bash
   pytest tests/ -v
   # Ensure no regressions
   ```

5. **Commit Fix**
   ```bash
   git add core/agent_governance_service.py
   git commit -m "fix: validate maturity transitions to prevent demotion"
   ```

**Success Criteria:**
- [ ] Test passes
- [ ] Full test suite passes (no regressions)
- [ ] Fix is minimal and focused
- [ ] Fix addresses root cause

---

### Phase 3: Refactor (Improve Code)

**Goal:** Improve code quality while maintaining behavior.

**Steps:**

1. **Look for Code Smells**
   - Duplicate code
   - Long methods
   - Complex conditionals
   - Poor naming

2. **Refactor with Test Safety Net**
   ```python
   # Extract validation logic
   def _is_demotion(self, current: AgentMaturity, new: AgentMaturity) -> bool:
       """Check if transition is a demotion."""
       maturity_levels = {
           AgentMaturity.STUDENT: 1,
           AgentMaturity.INTERN: 2,
           AgentMaturity.SUPERVISED: 3,
           AgentMaturity.AUTONOMOUS: 4
       }
       return maturity_levels[new] < maturity_levels[current]
   ```

3. **Verify Tests Still Pass**
   ```bash
   pytest tests/test_bug_fix.py tests/test_governance.py -v
   ```

4. **Commit Refactoring**
   ```bash
   git add core/agent_governance_service.py
   git commit -m "refactor: extract maturity level comparison logic"
   ```

**Success Criteria:**
- [ ] All tests still pass
- [ ] Code is cleaner and more maintainable
- [ ] No behavior changes
- [ ] Better code organization

---

## Common Bug Fix Patterns

### Pattern 1: Input Validation Bug

**Symptom:** Invalid data causes crashes or wrong behavior.

**Test:**
```python
def test_invalid_input_raises_error():
    with pytest.raises(ValueError):
        process_agent_id(None)  # Should reject None
```

**Fix:**
```python
def process_agent_id(agent_id: str):
    if not agent_id:
        raise ValueError("agent_id cannot be None or empty")
    # ... rest of logic
```

### Pattern 2: Edge Case Bug

**Symptom:** Code fails on boundary conditions (empty, zero, negative).

**Test:**
```python
def test_empty_list_handling():
    result = get_top_agents([])  # Empty input
    assert result == []  # Should handle gracefully
```

**Fix:**
```python
def get_top_agents(agents):
    if not agents:
        return []  # Handle edge case
    # ... rest of logic
```

### Pattern 3: State Mutation Bug

**Symptom:** Unexpected side effects modify shared state.

**Test:**
```python
def test_no_state_mutation():
    original = {"key": "value"}
    process_dict(original)
    assert original == {"key": "value"}  # Should not change
```

**Fix:**
```python
def process_dict(data):
    copy = data.copy()  # Don't mutate input
    # ... work with copy
```

### Pattern 4: Integration Bug

**Symptom:** Components don't work together correctly.

**Test:**
```python
def test_workflow_execution_integration():
    agent = create_test_agent()
    workflow = create_test_workflow()

    result = execute_workflow(workflow.id, agent.id)

    assert result.status == "completed"
    assert agent.maturity == AgentMaturity.AUTONOMOUS
```

**Fix:**
```python
def execute_workflow(workflow_id, agent_id):
    # Fix integration issue between components
    workflow = get_workflow(workflow_id)
    agent = get_agent(agent_id)

    # Ensure proper state synchronization
    if not agent.can_execute(workflow):
        raise PermissionError(...)

    # ... rest of logic
```

---

## Bug Fix Checklist

### Before Starting
- [ ] Bug report is clear and reproducible
- [ ] Affected component identified
- [ ] Expected behavior understood
- [ ] Related tests reviewed

### During Fix
- [ ] Failing test written (Red phase)
- [ ] Test committed before fix
- [ ] Minimal fix implemented (Green phase)
- [ ] Full test suite passes
- [ ] Code refactored if needed (Refactor phase)
- [ ] All tests still pass

### After Fix
- [ ] Bug verified as fixed
- [ ] No regressions introduced
- [ ] Documentation updated (if needed)
- [ ] PR created with clear description
- [ ] Code review completed
- [ ] Tests pass in CI/CD

---

## Integration with Quality Gates

**Automated Enforcement:**

1. **Test Pass Rate Gate:** All tests must pass (100%)
2. **Coverage Gate:** Coverage must not decrease
3. **Build Gate:** Build fails if any test fails

**Workflow:**
```
Push → Quality Gate → 100% Pass Required → Merge Allowed
                      ↓
                   Any Failure → Block Merge
```

---

## Examples

### Example 1: Fixing Governance Bug

**Bug:** STUDENT agents can execute HIGH complexity actions.

**Red Phase:**
```python
def test_student_blocked_from_high_complexity():
    student = AgentRegistry(id="student", maturity=AgentMaturity.STUDENT)
    service = AgentGovernanceService(db)

    result = service.check_permission(student, "execute_workflow", complexity=3)

    assert result.granted == False  # Currently fails (BUG)
```

**Green Phase:**
```python
# Fix in agent_governance_service.py
def check_permission(self, agent, action, complexity=1):
    if agent.maturity == AgentMaturity.STUDENT and complexity > 1:
        return PermissionResult(granted=False, reason="STUDENT not allowed")
    # ... rest of logic
```

**Refactor Phase:**
```python
# Extract maturity level mapping
MATURITY_LEVELS = {
    AgentMaturity.STUDENT: 1,
    AgentMaturity.INTERN: 2,
    AgentMaturity.SUPERVISED: 3,
    AgentMaturity.AUTONOMOUS: 4
}

def _check_complexity_allowed(self, maturity, complexity):
    return MATURITY_LEVELS[maturity] >= complexity
```

### Example 2: Fixing Coverage Regression

**Bug:** Coverage decreased from 75% to 73% after refactor.

**Red Phase:**
```python
def test_new_function_is_covered():
    result = new_function("test")
    assert result == "expected"  # Currently uncovered
```

**Green Phase:**
```python
# Add test to cover new function
# Coverage increases back to 75%
```

---

## Troubleshooting

### Issue: Test Won't Fail

**Possible Causes:**
- Test not actually testing the bug
- Bug already fixed elsewhere
- Test setup incorrect

**Solutions:**
- Add debug print to verify test path
- Check test isolation
- Verify bug reproduction steps

### Issue: Fix Breaks Other Tests

**Possible Causes:**
- Fix too broad
- Shared state mutation
- Test dependency

**Solutions:**
- Narrow fix scope
- Use test fixtures for isolation
- Check for test coupling

### Issue: Can't Reproduce Bug

**Possible Causes:**
- Environment-specific bug
- Race condition
- Incomplete bug report

**Solutions:**
- Add more context to bug report
- Check logs and traces
- Use debugger to trace execution

---

## Best Practices

1. **Test First, Always**
   - Never write code without a failing test
   - Commit test before fix
   - Keep tests independent

2. **Fix Root Causes**
   - Don't patch symptoms
   - Understand why bug occurred
   - Prevent similar bugs

3. **Keep Fixes Small**
   - One fix per commit
   - Minimal code changes
   - Easy to review and revert

4. **Maintain Coverage**
   - Never decrease coverage
   - Add tests for new code
   - Cover edge cases

5. **Document Decisions**
   - Why bug occurred
   - Why fix approach chosen
   - Lessons learned

---

## Related Documentation

- **TDD Workflow:** `docs/TDD_WORKFLOW.md`
- **Testing Guide:** `TESTING.md`
- **Quality Gates:** `.github/workflows/quality-gate.yml`
- **Quality Dashboard:** `docs/QUALITY_DASHBOARD.md`

---

**Bug Fix Process Version:** 1.0
**Last Updated:** 2026-04-12
**Maintained By:** Development Team
