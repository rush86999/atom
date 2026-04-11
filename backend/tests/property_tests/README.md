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
├── auto_dev/                            # Auto-Dev component tests (Phase 291)
│   ├── conftest.py                      # Auto-Dev specific fixtures and strategies
│   ├── test_event_bus_properties.py     # EventBus invariants (7 tests, 350 examples)
│   ├── test_fitness_service_properties.py # FitnessService invariants (7 tests, 700 examples)
│   ├── test_capability_gate_properties.py # CapabilityGate invariants (11 tests, 1100 examples)
│   ├── test_container_sandbox_properties.py # ContainerSandbox invariants (10 tests, 500 examples)
│   ├── test_memento_engine_properties.py # MementoEngine invariants (8 tests, 700 examples)
│   └── test_database_properties.py      # Database model invariants (10 tests, 950 examples)
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

# Run only Auto-Dev property tests
pytest tests/property_tests/auto_dev/ -v

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

## Auto-Dev Property Tests (Phase 291)

### Overview

Auto-Dev property tests verify invariants across 6 core components using Hypothesis to generate 4,300+ test examples automatically.

### Components Tested

#### 1. EventBus (`test_event_bus_properties.py`)
**7 property tests, 350 examples**

Tests the in-memory event bus for Auto-Dev lifecycle events:
- Subscriber Delivery Invariant - All subscribers receive events
- Exception Isolation Invariant - Subscriber exceptions don't affect others
- No Duplicate Delivery Invariant - Each event delivered once per subscriber
- Handler Count Invariant - Handler count matches registrations
- Clear Removes All Handlers - Clear() removes all registered handlers
- TaskEvent/SkillExecutionEvent Structure Invariants - Events maintain correct structure

#### 2. FitnessService (`test_fitness_service_properties.py`)
**7 property tests, 700 examples**

Tests fitness evaluation for workflow variants:
- Proxy Signal Bounds Invariant - Scores always in [0.0, 1.0]
- External Signal Adjustment Invariant - External signals keep scores in [0.0, 1.0]
- Top Variants Ordering Invariant - Top variants sorted by descending fitness
- Syntax Error Penalty Invariant - Syntax errors result in lower scores
- Positive/Negative Signal Invariants - Signals adjust scores correctly
- Fitness Signals Preservation Invariant - Signals stored correctly in database

#### 3. CapabilityGate (`test_capability_gate_properties.py`)
**11 property tests, 1100 examples**

Tests maturity-based feature gating:
- is_at_least Reflexivity/Transitivity Invariants - Maturity comparison properties
- Gate Consistency Invariant - Same capability request returns same result
- Unknown Capability Defaults to Student - Unknown capabilities default to STUDENT
- Workspace Toggle Invariant - Workspace settings override maturity requirements
- Capability Gates Defined Invariant - All capabilities map to valid maturity levels
- Maturity Hierarchy Ordering Invariant - Maturity hierarchy correctly ordered
- Daily Limits Configuration Invariant - Daily limits configurable via workspace settings

#### 4. ContainerSandbox (`test_container_sandbox_properties.py`)
**10 property tests, 500 examples**

Tests Docker-based sandbox for code execution:
- Execution Result Structure Invariant - All executions return valid structure
- Timeout Enforcement Invariant - Executions respect timeout limits
- Error Containment Invariant - Container crashes don't affect host system
- Output Type Invariant - All outputs are strings
- Execution Time Measurement Invariant - Execution times are non-negative floats
- Syntax Error Handling Invariant - Syntax errors caught and reported properly
- Input Parameter Injection Invariant - Input parameters injected as _INPUT_PARAMS
- Memory/Network Configuration Invariants - Limits configurable via constructor
- Docker Availability Detection Invariant - Docker detection is consistent

**Note:** All ContainerSandbox tests require Docker (`@pytest.mark.docker_required`).

#### 5. MementoEngine (`test_memento_engine_properties.py`)
**8 property tests, 700 examples**

Tests skill generation from failed episodes:
- Skill Candidate Structure Invariant - Generated candidates have valid structure
- Skill Name Generation Invariant - Skill names are valid Python identifiers
- Validation Result Structure Invariant - Validation returns valid structure
- SkillCandidate Model Structure Invariant - Model accepts valid parameters
- Validation Status Transition Invariant - Status transitions are valid
- Fitness Score Bounds Invariant - Fitness scores in [0.0, 1.0]
- Candidate Uniqueness Invariant - Different candidates can have same name
- Failure Pattern Storage Invariant - Failure pattern metadata stored correctly

#### 6. Database Models (`test_database_properties.py`)
**10 property tests, 950 examples**

Tests SQLAlchemy model integrity:
- ToolMutation/WorkflowVariant/SkillCandidate Model Integrity Invariants
- Fitness Score Bounds Invariant - Scores clamped to [0.0, 1.0]
- Timestamp Monotonicity Invariant - Updated timestamp >= created timestamp
- JSON Field Schema Invariants - JSON fields accept valid data
- Uniqueness Invariants - Different records have unique IDs

### Running Auto-Dev Property Tests

```bash
# Run all Auto-Dev property tests
pytest tests/property_tests/auto_dev/ -v

# Run specific component
pytest tests/property_tests/auto_dev/test_event_bus_properties.py -v

# Skip Docker-dependent tests
pytest tests/property_tests/auto_dev/ -v -m "not docker_required"

# Run with Hypothesis settings
pytest tests/property_tests/auto_dev/ -v --hypothesis-seed=42
```

### Hypothesis Strategies for Auto-Dev

Custom strategies defined in `auto_dev/conftest.py`:

- `fitness_scores` - Lists of floats in [0.0, 1.0]
- `maturity_levels` - One of ['student', 'intern', 'supervised', 'autonomous']
- `event_data` - Dictionaries with random keys/values
- `capabilities` - Valid capability names
- `proxy_signals` - Execution success, syntax error, latency, approval
- `external_signals` - Webhook signals (invoice_created, crm_conversion, etc.)
- `workspace_settings` - Nested dictionaries for workspace configuration

### Performance

- **Per test:** 50-100 examples (configurable via `@settings(max_examples=...)`)
- **Total examples:** 4,300+ examples across 53 tests
- **Typical runtime:** 2-3 minutes on modern hardware

## References

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing](https://hypothesis.works/articles/what-is-property-based-testing/)
- Atom Platform CLAUDE.md for architecture details
- [Auto-Dev Architecture](../../../docs/AUTO_DEV_ARCHITECTURE.md)
- [Phase 291 Plan](../../../.planning/phases/291-property-based-testing/)

## Support

For questions or issues:
- Engineering Lead
- Architecture Team
- Check `PROPERTY_TEST_GUARDIAN.md` for protection guidelines
