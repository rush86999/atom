# Property-Based Test Protection Mechanism

## Purpose
This directory contains property-based tests that verify CRITICAL SYSTEM INVARIANTS.
These tests are PROTECTED from modification by implementation AI/automation.

## Protection Rules

### Files Under Protection
All files in `tests/property_tests/` are PROTECTED and MUST NOT be modified by:
- Implementation AI agents
- Automated refactoring tools
- Code generation scripts
- ANY automation that doesn't explicitly understand invariant testing

### What Changes Are Allowed
Only HUMAN engineers with explicit authorization may modify these tests to:
1. Fix test bugs (not implementation bugs)
2. Add new invariants
3. Improve test clarity
4. Update documentation

### Modification Detection
Changes to protected files will trigger:
1. Pre-commit hook validation
2. CI/CD pipeline failure
3. Notification to engineering lead

## Allowed Modifications by Implementation AI

Implementation AI MAY:
- Modify files in `tests/` (regular unit tests)
- Modify files in `tests/integration/`
- Modify implementation code in `core/`, `api/`, etc.

Implementation AI MUST NOT:
- Modify files in `tests/property_tests/`
- Modify this protection marker file
- Attempt to bypass or disable protection checks

## File Structure

```
tests/property_tests/
├── __init__.py                          # Package documentation
├── conftest.py                          # Shared fixtures
├── README.md                            # This file
│
├── invariants/                          # Core invariant tests
│   ├── __init__.py
│   ├── test_governance_invariants.py    # Governance state invariants
│   ├── test_cache_invariants.py         # Cache consistency invariants
│   ├── test_confidence_invariants.py    # Confidence score bounds
│   └── test_maturity_invariants.py      # Maturity level transitions
│
├── interfaces/                          # API contract tests
│   ├── __init__.py
│   ├── test_governance_service.py       # AgentGovernanceService contracts
│   └── test_context_resolver.py         # AgentContextResolver contracts
│
├── contracts/                           # Business rule contracts
│   ├── __init__.py
│   └── test_action_complexity.py        # Action complexity matrix
│
└── models/                              # Data model invariants
    ├── __init__.py
    └── (future tests for model invariants)
```

## Invariants Tested

### Critical System Invariants

1. **Confidence Score Bounds**: All confidence scores MUST be in [0.0, 1.0]
2. **Maturity Hierarchy**: Agents never regress in maturity level
3. **Action Complexity Matrix**: STUDENT can't do CRITICAL actions
4. **Cache Idempotency**: Cache returns same decision for same key within TTL
5. **Audit Trail Completeness**: Every state change is logged
6. **API Response Format**: Standardized error handling
7. **Episode Immutability**: Memory integrity
8. **Fallback Chain Completeness**: Resolver never crashes

### Why These Invariants Matter

| Invariant | Safety Impact | Test Location |
|-----------|---------------|---------------|
| Confidence ∈ [0.0, 1.0] | AI decision safety | `test_confidence_invariants.py` |
| Maturity is monotonic | Prevents privilege regression | `test_maturity_invariants.py` |
| Action complexity enforced | STUDENT can't do CRITICAL actions | `test_action_complexity.py` |
| Cache idempotency within TTL | Consistent governance decisions | `test_cache_invariants.py` |
| Governance never crashes | System reliability | `test_governance_invariants.py` |

## How These Tests Differ from Unit Tests

### Unit Tests
- Test specific code paths
- Use fixed inputs
- Can be adapted to implementation
- Example: "Test that `can_perform_action` returns False when agent is STUDENT and action is delete"

### Property-Based Tests (These Tests)
- Test system properties and invariants
- Use random generated inputs
- Must remain implementation-agnostic
- Example: "Test that `can_perform_action` ALWAYS returns a dict with required fields for ANY agent and action"

## Running the Tests

```bash
# Run all property-based tests
pytest tests/property_tests/ -v

# Run only invariant tests
pytest tests/property_tests/invariants/ -v -m invariant

# Run with many examples (stress testing)
pytest tests/property_tests/invariants/ -v --hypothesis-max-examples=10000

# Run with coverage
pytest tests/property_tests/ --cov=core --cov-report=html

# CI mode (faster, fewer examples)
pytest tests/property_tests/ -v --hypothesis-max-examples=50
```

## Writing New Property-Based Tests

When adding new invariant tests:

1. **Test Observable Behaviors**: Only test public APIs, not implementation details
2. **Use Hypothesis Strategists**: Generate random inputs using `@given` decorator
3. **Verify Invariants**: Test properties that MUST always be true
4. **Keep Tests Independent**: Each test should verify one invariant
5. **Use Descriptive Names**: Test names should clearly state the invariant

Example:

```python
@given(
    confidence_score=st.floats(min_value=0.0, max_value=1.0)
)
@settings(max_examples=200)
def test_confidence_never_exceeds_bounds(
    self, db_session: Session, confidence_score: float
):
    """
    INVARIANT: Confidence scores MUST always be in [0.0, 1.0].

    This is safety-critical for AI decision-making.
    """
    # Arrange
    agent = AgentRegistry(
        confidence_score=confidence_score,
        ...
    )
    db_session.add(agent)
    db_session.commit()

    # Assert: Verify invariant
    assert 0.0 <= agent.confidence_score <= 1.0
```

## Pre-Commit Hook

A pre-commit hook warns when protected files are modified:

```bash
#!/bin/bash
# .git/hooks/pre-commit-property-tests

PROTECTED_DIR="tests/property_tests"

if git diff --cached --name-only | grep -q "^$PROTECTED_DIR/"; then
    echo "⚠️  WARNING: Property-based tests have been modified!"
    echo "Please confirm with engineering lead before proceeding."
    # Interactive prompt for confirmation
fi
```

## Verification

Run: `make verify-property-tests` to verify integrity (if make target is configured).

## Contact

For questions about these tests or to request modifications, contact:
- Engineering Lead
- Architecture Team

---

**Remember**: These tests protect the system from implementation changes that break critical invariants. They are the last line of defense against regressions.
