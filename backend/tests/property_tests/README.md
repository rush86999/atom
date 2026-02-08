# Property-Based Tests for Atom Platform

This directory contains property-based tests that verify **critical system invariants** using the Hypothesis library.

## What are Property-Based Tests?

Property-based tests verify that a system maintains certain invariants across **many random inputs**, rather than testing specific code paths with fixed inputs like traditional unit tests.

### Key Differences

| Aspect | Unit Tests | Property-Based Tests |
|--------|-----------|---------------------|
| **Inputs** | Fixed, hand-picked | Random, generated |
| **Scope** | Specific code paths | System invariants/properties |
| **Adaptation** | Can be adapted to implementation | Must remain implementation-agnostic |
| **Failure Mode** | Shows what broke | Shows a counterexample to invariant |
| **Examples** | "Test that STUDENT can't delete" | "Test that ANY agent returns valid decision structure" |

## Directory Structure

```
property_tests/
├── __init__.py                          # Package documentation
├── conftest.py                          # Shared fixtures for all property tests
├── README.md                            # This file
│
├── invariants/                          # Core invariant tests
│   ├── test_governance_invariants.py    # Governance decisions always valid
│   ├── test_cache_invariants.py         # Cache consistency
│   ├── test_confidence_invariants.py    # Confidence score bounds [0.0, 1.0]
│   └── test_maturity_invariants.py      # Maturity transitions
│
├── interfaces/                          # API contract tests
│   ├── test_governance_service.py       # AgentGovernanceService contracts
│   └── test_context_resolver.py         # AgentContextResolver contracts
│
├── contracts/                           # Business rule tests
│   └── test_action_complexity.py        # Action complexity matrix enforcement
│
└── models/                              # Data model tests (future)
    └── (model invariant tests)
```

## Running the Tests

### Basic Usage

```bash
# Run all property-based tests
pytest tests/property_tests/ -v

# Run only invariant tests
pytest tests/property_tests/invariants/ -v

# Run only interface tests
pytest tests/property_tests/interfaces/ -v

# Run only business rule tests
pytest tests/property_tests/contracts/ -v
```

### Advanced Options

```bash
# Run with many examples (stress testing)
pytest tests/property_tests/invariants/test_confidence_invariants.py -v \
  --hypothesis-max-examples=10000

# Run with coverage
pytest tests/property_tests/ --cov=core --cov-report=html

# CI mode (faster, fewer examples)
pytest tests/property_tests/ -v --hypothesis-max-examples=50

# Run specific test
pytest tests/property_tests/invariants/test_governance_invariants.py::TestGovernanceInvariants::test_governance_decision_has_required_fields -v

# Verbose output with Hypothesis statistics
pytest tests/property_tests/ -v -s
```

## Key Invariants Tested

### 1. Confidence Score Bounds
- **Invariant**: All confidence scores must stay in [0.0, 1.0]
- **Why**: Safety-critical for AI decision-making
- **Test**: `test_confidence_invariants.py`

### 2. Maturity Hierarchy
- **Invariant**: Agents never regress in maturity level
- **Why**: Prevents privilege escalation attacks
- **Test**: `test_maturity_invariants.py`

### 3. Action Complexity Matrix
- **Invariant**: STUDENT can't perform CRITICAL (complexity 4) actions
- **Why**: Prevents unauthorized destructive operations
- **Test**: `test_action_complexity.py`

### 4. Cache Idempotency
- **Invariant**: Cache returns same decision for same key within TTL
- **Why**: Ensures consistent governance decisions
- **Test**: `test_cache_invariants.py`

### 5. API Response Format
- **Invariant**: All governance decisions have required fields
- **Why**: API consumers rely on this structure
- **Test**: `test_governance_invariants.py`

## Example Test

Here's an example property-based test that verifies confidence scores never exceed bounds:

```python
from hypothesis import given, settings
from hypothesis import strategies as st

@given(
    confidence_score=st.floats(
        min_value=0.0,
        max_value=1.0,
        allow_nan=False,
        allow_infinity=False
    )
)
@settings(max_examples=200)
def test_confidence_score_never_exceeds_bounds(
    self, db_session: Session, confidence_score: float
):
    """
    INVARIANT: Confidence scores MUST always be in [0.0, 1.0].

    This is safety-critical for AI decision-making.
    """
    # Arrange: Create agent with random confidence score
    agent = AgentRegistry(
        name="TestAgent",
        category="test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.INTERN.value,
        confidence_score=confidence_score,
        capabilities=["test_capability"],
    )
    db_session.add(agent)
    db_session.commit()

    # Assert: Verify invariant holds
    assert 0.0 <= agent.confidence_score <= 1.0
```

This test will run **200 times** with different randomly generated confidence scores, ensuring the invariant holds across all cases.

## Protection Mechanism

These tests are **PROTECTED** from modification by implementation AI/automation. See:
- `tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md` for full details
- Pre-commit hook warns about modifications to protected files

## Writing New Property-Based Tests

When adding new tests:

1. **Test Observable Behaviors**: Only test public APIs, not implementation details
2. **Use Hypothesis Strategists**: Generate random inputs using `@given` decorator
3. **Verify Invariants**: Test properties that MUST always be true
4. **Keep Tests Independent**: Each test should verify one invariant
5. **Use Descriptive Names**: Test names should clearly state the invariant

### Hypothesis Strategies

Common strategies for generating test data:

```python
from hypothesis import strategies as st

# Text
st.text(min_size=1, max_size=50)
st.text(min_size=1, max_size=50).filter(lambda x: x.strip())  # Non-empty

# Integers
st.integers(min_value=0, max_value=100)

# Floats
st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Booleans
st.booleans()

# Sample from list
st.sampled_from([AgentStatus.STUDENT, AgentStatus.INTERN, ...])

# Dates
st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 12, 31))
```

## Troubleshooting

### Test Fails with "Falsified Example"

Hypothesis found a counterexample to your invariant. This means:
- The invariant you're testing is NOT always true
- Hypothesis will show you the specific input that breaks it

**Action**: Either fix the implementation or update the invariant if it was incorrect.

### Tests are Slow

Property-based tests can be slow with many examples. Solutions:
- Reduce `max_examples` in `@settings` decorator
- Use `--hypothesis-max-examples` flag for CI
- Run specific test files instead of entire suite

### "Database is locked" Errors

Each test creates a fresh in-memory database. If you see errors:
- Ensure `db_session` fixture is used (not creating sessions manually)
- Check for concurrent access in tests

## References

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing](https://hypothesis.works/articles/what-is-property-based-testing/)
- Atom Platform CLAUDE.md for architecture details

## Support

For questions or issues:
- Engineering Lead
- Architecture Team
- Check `PROPERTY_TEST_GUARDIAN.md` for protection guidelines
