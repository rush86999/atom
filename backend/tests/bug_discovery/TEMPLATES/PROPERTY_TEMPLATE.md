# Property-Based Test: [Invariant Name]

## Purpose

Validate invariant: [invariant statement] for [target module/function]

**What this test validates:**
- Invariant holds for all valid inputs (not just hand-picked examples)
- Edge cases discovered through automatic test generation
- Counterexample shrinking to minimal failing case

**Target:**
- Module: `backend/core/[module].py`
- Function: `[function_name]`
- Input type: `[strings, integers, lists, JSON, etc.]`

## Dependencies

**Required Libraries:**
```bash
pip install hypothesis==6.92.0
```

**Target Module:**
- `backend/core/[module].py` - [description of target]
- `backend/api/[routes].py` - [description of target API]

**Hypothesis Strategies:**
- `hypothesis.strategies.text()` - String generation
- `hypothesis.strategies.integers()` - Integer generation
- `hypothesis.strategies.lists()` - List generation
- `hypothesis.strategies.dictionaries()` - Dictionary generation
- `hypothesis.strategies.builds()` - Custom object generation

## Invariant (Document Before Writing Test)

**CRITICAL: Document invariant FIRST, then write test.**

**Property:** [What must be true for all inputs]

Example invariants:
- "Workflow serialization is lossless for all step lists"
- "Agent execution is idempotent for all agent IDs"
- "JSON round-trip preserves data for all valid JSON objects"
- "Episode segmentation produces contiguous time segments for all message lists"

**Domain:** [Input space: strings, integers, lists, JSON objects, etc.]

**Preconditions:** [Required conditions for invariant to hold]

Example:
- Input must be valid UTF-8 string
- List must contain 0-100 items
- JSON must conform to schema

**Postconditions:** [What must be true after operation]

Example:
- Output list has same length as input
- All IDs in output are valid UUIDs
- Timestamps are monotonically increasing

**Example Invariant Documentation:**
```python
"""
Invariant: Workflow serialization is lossless for all step lists.

Property:
- For any list of workflow steps, serializing and deserializing
  produces an equivalent workflow with the same steps.

Domain:
- Input: List of workflow steps (dict with 'action', 'params', 'order')
- Size: 0-100 steps per workflow
- Actions: 'create_agent', 'execute_workflow', 'present_canvas'

Preconditions:
- All steps have valid 'action' field
- All steps have 'order' field (integer, 0-1000)
- 'params' is a dict (can be empty)

Postconditions:
- Deserialized workflow has same number of steps as input
- All steps are present in same order
- All step fields are preserved (action, params, order)
"""
```

## Setup

**Hypothesis settings configuration:**
```python
from hypothesis import given, settings, strategies as st
from tests.property_tests.conftest import DEFAULT_PROFILE, CI_PROFILE

# Use CI profile for faster tests (50 examples, 5s deadline)
# Use local profile for thorough testing (200 examples, 30s deadline)

# Settings profiles defined in tests/property_tests/conftest.py:
# - CI_PROFILE: max_examples=50, deadline=5s (fast for PR checks)
# - DEFAULT_PROFILE: max_examples=200, deadline=30s (thorough for local)

# Example: Use CI profile for fast tests
@settings(CI_PROFILE)

# Example: Use default profile for thorough tests
@settings(DEFAULT_PROFILE)

# Custom settings
@settings(
    max_examples=100,
    deadline=timedelta(seconds=10),
    phases=[Phase.generate]  # Skip reuse phase for faster tests
)
```

**Import strategies:**
```python
from hypothesis import strategies as st

# Common strategies
st.text()  # Random strings (unicode, min_size=0)
st.integers(min_value=0, max_value=100)  # Bounded integers
st.lists(st.integers(), min_size=0, max_size=100)  # Lists
st.dictionaries(st.text(), st.integers())  # Dicts
st.builds(MyModel, id=st.uuid4(), name=st.text())  # Custom objects
```

## Test Procedure

**Step 1: Define invariant (BEFORE writing test)**
```python
# Document invariant in docstring
def test_workflow_serialization_roundtrip(steps):
    """
    Test that workflow serialization is lossless.

    Invariant: Serializing and deserializing a workflow produces
    an equivalent workflow with the same steps.

    Strategy:
    - Generate random workflow steps (0-100 steps)
    - Each step has: action, params, order
    - Actions from: create_agent, execute_workflow, present_canvas

    Expected:
    - Deserialized workflow has same steps as input
    - All fields preserved (action, params, order)
    - Steps in same order
    """
```

**Step 2: Write test with @given decorator**
```python
import pytest
from hypothesis import given, settings, strategies as st
from tests.property_tests.conftest import DEFAULT_PROFILE
from backend.core.workflow_engine import WorkflowDefinition

@pytest.mark.property
@given(st.lists(
    st.fixed_dictionaries({
        'action': st.sampled_from(['create_agent', 'execute_workflow', 'present_canvas']),
        'params': st.dictionaries(st.text(), st.text()),
        'order': st.integers(min_value=0, max_value=1000)
    }),
    min_size=0,
    max_size=100
))
@settings(DEFAULT_PROFILE)
def test_workflow_serialization_roundtrip(steps):
    """
    Test that workflow serialization is lossless for all step lists.

    Invariant: For any list of workflow steps, serializing and deserializing
    produces an equivalent workflow with the same steps.

    Strategy: Generate 0-100 workflow steps with random actions, params, order.

    Expected: All steps preserved in same order.
    """
    # Arrange: Create workflow from generated steps
    workflow = WorkflowDefinition(name="test", steps=steps)

    # Act: Serialize and deserialize
    serialized = workflow.serialize()
    deserialized = WorkflowDefinition.deserialize(serialized)

    # Assert: Invariant holds
    assert len(deserialized.steps) == len(steps), \
        f"Step count mismatch: {len(deserialized.steps)} != {len(steps)}"

    for i, (original, recovered) in enumerate(zip(steps, deserialized.steps)):
        assert recovered['action'] == original['action'], \
            f"Step {i}: action mismatch ({recovered['action']} != {original['action']})"
        assert recovered['order'] == original['order'], \
            f"Step {i}: order mismatch ({recovered['order']} != {original['order']})"
        assert recovered['params'] == original['params'], \
            f"Step {i}: params mismatch ({recovered['params']} != {original['params']})"
```

**Step 3: Run test and verify**
```bash
# Run property test
pytest backend/tests/property_tests/test_workflow_properties.py::test_workflow_serialization_roundtrip -v

# Hypothesis will:
# 1. Generate 100+ random examples (by default)
# 2. Shrink counterexample to minimal case (if invariant violated)
# 3. Print minimal failing input (for bug filing)

# Example output on failure:
# Falsifying example:
# test_workflow_serialization_roundtrip(
#     steps=[
#         {'action': 'create_agent', 'params': {}, 'order': 0},
#         {'action': 'execute_workflow', 'params': {'name': ''}, 'order': 1}
#     ]
# )
# Shrunk from 53 steps to 2 steps in 0.05s
```

**Step 4: Handle invariant violations**
```python
# If test fails, Hypothesis provides minimal counterexample
# Example: Steps with empty 'name' param cause serialization error

# Fix bug or refine invariant
# Option 1: Fix bug in serialization logic
# Option 2: Add precondition: 'name' must be non-empty
# Option 3: Update invariant to handle empty names correctly

# Example: Add precondition to strategy
@given(st.lists(
    st.fixed_dictionaries({
        'action': st.sampled_from(['create_agent', 'execute_workflow', 'present_canvas']),
        'params': st.dictionaries(
            st.text(min_size=1, max_size=10),  # Non-empty keys
            st.text(min_size=1)  # Non-empty values (precondition)
        ),
        'order': st.integers(min_value=0, max_value=1000)
    }),
    min_size=0,
    max_size=100
))
@settings(DEFAULT_PROFILE)
def test_workflow_serialization_roundtrip_with_preconditions(steps):
    """
    Test that workflow serialization is lossless for all step lists.

    Invariant: For any list of workflow steps with non-empty params,
    serializing and deserializing produces an equivalent workflow.

    Precondition: All param keys and values must be non-empty strings.
    """
    # ... same test logic
```

## Expected Behavior

**Invariant holds (test passes):**
- All generated examples satisfy invariant
- Hypothesis runs 100-200 examples (depending on profile)
- No counterexamples found
- Test completes in <30s (per TQ-03)

**Invariant violated (test fails):**
- Hypothesis finds counterexample
- Automatically shrinks to minimal failing case
- Prints minimal input that violates invariant
- Provides reproduction script

**Example failure output:**
```python
# ==================== FAILURES ====================
# ____________________ test_workflow_serialization_roundtrip ____________________
#
# Falsifying example:
# test_workflow_serialization_roundtrip(
#     steps=[
#         {'action': 'execute_workflow', 'params': {'name': ''}, 'order': 0}
#     ]
# )
# Shrunk from 47 steps to 1 step in 0.03s
#
# assert 1 == 0
#  +  where 1 = len([{'action': 'execute_workflow', 'params': {}, 'order': 0}])
#  +  and   0 = len([])
#
# Step 0: params mismatch ({'name': ''} != {})
```

**Hypothesis shrinking process:**
1. Find first failing example (may be complex: 53 steps)
2. Simplify example (remove steps, reduce values)
3. Find minimal counterexample (2 steps → 1 step)
4. Report minimal failing case for debugging

## Bug Filing

**Automatic bug filing on invariant violation:**
```python
from tests.bug_discovery.bug_filing_service import BugFilingService

@pytest.mark.property
@given(st.lists(st.integers(), min_size=0, max_size=100))
@settings(DEFAULT_PROFILE)
def test_[invariant_name](inputs):
    """
    Test that [invariant] holds for all [inputs].

    Invariant: [statement]
    Strategy: [strategy description]

    Fails on: [known counterexample]
    """
    try:
        # Test logic
        result = [function_under_test](inputs)
        assert [invariant_check](result), f"Invariant violated: {result}"

    except AssertionError as e:
        # File bug with counterexample
        BugFilingService.file_bug(
            test_name=f"test_{[invariant_name]}_violation",
            error_message=f"Invariant violation: {str(e)}",
            metadata={
                "test_type": "property",
                "invariant": "[invariant_name]",
                "counterexample": str(inputs),
                "shrunk_input": str(inputs),  # Hypothesis already shrunk
                "hypothesis_examples": 100,  # Number of examples run
                "strategy": "st.lists(st.integers(), min_size=0, max_size=100)"
            },
            expected_behavior=f"Invariant should hold: {[invariant_statement]}",
            actual_behavior=f"Invariant violated for input: {inputs}"
        )
        raise  # Re-raise to fail test
```

**Manual bug filing (if not automatic):**
```bash
# Bug title: [Bug] Invariant violation: [Invariant Name]

# Bug body:
## Bug Description

Property-based test discovered invariant violation in [function_name].

## Invariant

**Statement:** [invariant statement]

**Domain:** [input space]

**Preconditions:** [required conditions]

## Counterexample

```python
# Minimal failing input (shrunk by Hypothesis)
inputs = [paste counterexample from test output]

# Reproducer
from backend.core.[module] import [function_name]
result = [function_name](inputs)
# Expected: [expected behavior]
# Actual: [actual behavior]
```

## Steps to Reproduce

1. Run property test: `pytest backend/tests/property_tests/test_[module]_properties.py::test_[invariant_name] -v`
2. Hypothesis finds counterexample after N examples
3. Counterexample shrunk to minimal case: [paste input]
4. Invariant violated: [description of violation]

## Shrinking Process

- Original failing example: [N] steps/items
- Shrunk to: [M] steps/items (minimal case)
- Shrinking time: [seconds]

## Hypothesis Output

```
[paste Hypothesis output with counterexample]
```

## Expected Behavior

Invariant should hold: [invariant statement]

For input: [counterexample], expected: [expected result]

## Actual Behavior

Invariant violated: [description of violation]

For input: [counterexample], actual: [actual result]

## Test Context

- **Test:** `test_[invariant_name]`
- **Hypothesis examples run:** [N]
- **Strategy:** [Hypothesis strategy used]
- **Settings:** [max_examples, deadline]
- **Platform:** [output of `uname -a`]
- **Python:** [output of `python --version`]
```

## TQ Compliance

**TQ-01 (Test Independence):**
- Each test generates fresh inputs (Hypothesis @given decorator)
- No shared state between property tests
- Each invariant tested independently

**TQ-02 (Pass Rate):**
- Property tests have 100% pass rate (invariant violations = real bugs)
- Same input always produces same output (deterministic target function)
- No flaky tests (Hypothesis provides reproducible examples)

**TQ-03 (Performance):**
- Hypothesis settings enforce deadline (30s default)
- CI profile: 50 examples, 5s deadline (fast for PR checks)
- Default profile: 200 examples, 30s deadline (thorough for local)

**TQ-04 (Determinism):**
- Same input produces same output (deterministic target function required)
- Hypothesis uses fixed random seed (reproducible examples)
- Counterexamples are reproducible (same test run = same failure)

**TQ-05 (Coverage Quality):**
- Tests invariant (observable behavior), not implementation
- Hypothesis explores input space systematically (edge cases discovered)
- Property-based: tests general property, not specific examples

## pytest.ini Marker

Add to `backend/pytest.ini`:
```ini
[pytest]
markers =
    property: Property-based tests (Hypothesis, slow, thorough)
```

Run only property tests:
```bash
pytest backend/tests/property_tests/ -v -m property
```

Skip property tests in fast CI:
```bash
pytest backend/tests/ -v -m "not property"
```

## Invariant-First Thinking

**Process:**
1. **Document invariant first** (before writing test)
2. Write test that validates invariant
3. Run test to discover counterexamples
4. Fix bugs or refine invariant (add preconditions)
5. Re-run test to verify fix

**Why invariant-first?**
- Forces clarity about what must be true
- Prevents implementation-driven tests
- Catches edge cases early
- Makes tests maintainable (invariant is documentation)

**Bad example (not invariant-first):**
```python
# BAD: Test specific examples, no invariant documented
def test_workflow_serialization():
    workflow = Workflow(steps=[{'action': 'create_agent'}])
    serialized = workflow.serialize()
    deserialized = Workflow.deserialize(serialized)
    assert deserialized.steps == workflow.steps
```

**Good example (invariant-first):**
```python
# GOOD: Invariant documented, tested for all inputs
@given(st.lists(st.builds(WorkflowStep)))
@settings(DEFAULT_PROFILE)
def test_workflow_serialization_roundtrip(steps):
    """
    Test that workflow serialization is lossless for all step lists.

    Invariant: For any list of workflow steps, serializing and
    deserializing produces an equivalent workflow.
    """
    workflow = Workflow(steps=steps)
    serialized = workflow.serialize()
    deserialized = Workflow.deserialize(serialized)
    assert deserialized.steps == workflow.steps
```

## See Also

- [Hypothesis Documentation](https://hypothesis.readthedocs.io)
- [Property-Based Testing](https://hypothesis.works/articles/what-is-property-based-testing/)
- `backend/docs/TEST_QUALITY_STANDARDS.md` - TQ-01 through TQ-05
- `backend/tests/bug_discovery/TEMPLATES/README.md` - Template usage guide
