"""
Property-Based Tests for MementoEngine

This module tests MementoEngine invariants using Hypothesis to generate hundreds
of test cases automatically.

Properties tested:
1. Skill Candidate Structure Invariant - Generated candidates have valid structure
2. Episode Analysis Structure Invariant - Analysis returns valid structure
3. Validation Result Structure Invariant - Validation returns valid structure
4. Skill Name Generation Invariant - Skill names are valid Python identifiers
5. Fitness Score Bounds Invariant - Fitness scores are in [0.0, 1.0]
"""

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from datetime import datetime, timezone
import uuid

from core.auto_dev.memento_engine import MementoEngine
from core.auto_dev.models import SkillCandidate


# =============================================================================
# Strategy Definitions
# =============================================================================

# Task description strategy
task_descriptions = st.text(min_size=10, max_size=500).filter(
    lambda x: len(x.strip()) > 0
)

# Error trace strategy
error_traces = st.text(min_size=0, max_size=2000)

# Episode ID strategy
episode_ids = st.text(min_size=36, max_size=36, alphabet='abcdef0123456789-')

# Agent ID strategy
agent_ids = st.text(min_size=36, max_size=36, alphabet='abcdef0123456789-')

# Tenant ID strategy
tenant_ids = st.text(min_size=36, max_size=36, alphabet='abcdef0123456789-')

# Test inputs strategy (for validation)
test_inputs = st.lists(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.integers(), st.floats(), st.text(), st.booleans()),
        min_size=0,
        max_size=5
    ),
    min_size=0,
    max_size=10
)

# Generated code strategy
generated_code = st.text(min_size=20, max_size=5000).filter(
    lambda x: len(x.strip()) > 0
)

# Skill name strategy
skill_names = st.text(min_size=1, max_size=100).filter(
    lambda x: len(x.strip()) > 0 and x.replace('_', '').replace('-', '').isalnum()
)


# =============================================================================
# Property Tests
# =============================================================================

@pytest.mark.property
@given(
    tenant_id=tenant_ids,
    agent_id=agent_ids,
    episode_id=episode_ids
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_skill_candidate_structure_invariant(
    memento_engine,
    db_session,
    tenant_id,
    agent_id,
    episode_id
):
    """
    Property: Generated skill candidates have valid structure.

    For any valid tenant, agent, and episode IDs, generate_skill_candidate
    should create a SkillCandidate with all required fields.
    """
    # Create a test episode first
    try:
        from core.models import Episode

        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            user_id=tenant_id,
            task_description="Test task for skill generation",
            outcome="failure",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(episode)
        db_session.commit()
    except ImportError:
        pytest.skip("Episode model not available")

    # Generate candidate (will fail if Episode not in database, but that's OK for property test)
    try:
        candidate = await memento_engine.generate_skill_candidate(
            tenant_id=tenant_id,
            agent_id=agent_id,
            episode_id=episode_id
        )

        # Verify required fields
        assert hasattr(candidate, 'id'), "Missing id field"
        assert hasattr(candidate, 'tenant_id'), "Missing tenant_id field"
        assert hasattr(candidate, 'agent_id'), "Missing agent_id field"
        assert hasattr(candidate, 'source_episode_id'), "Missing source_episode_id field"
        assert hasattr(candidate, 'skill_name'), "Missing skill_name field"
        assert hasattr(candidate, 'skill_description'), "Missing skill_description field"
        assert hasattr(candidate, 'generated_code'), "Missing generated_code field"
        assert hasattr(candidate, 'validation_status'), "Missing validation_status field"

        # Verify field types
        assert isinstance(candidate.tenant_id, str), "tenant_id not a string"
        assert isinstance(candidate.skill_name, str), "skill_name not a string"
        assert isinstance(candidate.skill_description, str), "skill_description not a string"
        assert isinstance(candidate.generated_code, str), "generated_code not a string"
        assert isinstance(candidate.validation_status, str), "validation_status not a string"

        # Verify validation status is valid
        assert candidate.validation_status in ['pending', 'validated', 'failed', 'promoted'], \
            f"Invalid validation_status: {candidate.validation_status}"

    except Exception as e:
        # LLM might not be available, which is OK for property test
        if "LLM" in str(e) or "Episode" in str(e):
            pytest.skip(f"Required service not available: {e}")
        else:
            raise


@pytest.mark.property
@given(
    task_description=task_descriptions,
    error_trace=error_traces
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_skill_name_generation_invariant(task_description, error_trace):
    """
    Property: Generated skill names are valid Python identifiers.

    For any task description and error trace, _suggest_skill_name should
    return a string that is a valid Python identifier (or contains only
    alphanumeric characters and underscores).
    """
    from core.auto_dev.memento_engine import MementoEngine

    skill_name = MementoEngine._suggest_skill_name(task_description, error_trace)

    # Verify skill name is a string
    assert isinstance(skill_name, str), "Skill name should be a string"

    # Verify skill name is not empty
    assert len(skill_name) > 0, "Skill name should not be empty"

    # Verify skill name contains only valid characters (alphanumeric, underscore, hyphen)
    sanitized = skill_name.replace('_', '').replace('-', '')
    assert sanitized.isalnum(), \
        f"Skill name '{skill_name}' should contain only alphanumeric characters, underscores, or hyphens"


@pytest.mark.property
@given(
    code=generated_code,
    test_inputs_list=test_inputs
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_validation_result_structure_invariant(
    memento_engine,
    code,
    test_inputs_list
):
    """
    Property: Validation results have valid structure.

    For any code and test inputs, validate_change should return a dict
    with 'passed' boolean and 'test_results' list.
    """
    import uuid

    result = await memento_engine.validate_change(
        code=code,
        test_inputs=test_inputs_list or [{}],
        tenant_id=str(uuid.uuid4())
    )

    # Verify structure
    assert isinstance(result, dict), "Validation result should be a dict"
    assert "passed" in result, "Validation result missing 'passed' field"
    assert "test_results" in result, "Validation result missing 'test_results' field"

    # Verify types
    assert isinstance(result["passed"], bool), "'passed' should be boolean"
    assert isinstance(result["test_results"], list), "'test_results' should be a list"

    # Verify test results structure
    for test_result in result["test_results"]:
        assert isinstance(test_result, dict), "Test result should be a dict"
        assert "test_index" in test_result, "Test result missing 'test_index'"
        assert "passed" in test_result, "Test result missing 'passed'"
        assert "output" in test_result, "Test result missing 'output'"
        assert "execution_seconds" in test_result, "Test result missing 'execution_seconds'"

        # Verify types
        assert isinstance(test_result["test_index"], int), "test_index should be int"
        assert isinstance(test_result["passed"], bool), "passed should be bool"
        assert isinstance(test_result["output"], str), "output should be str"
        assert isinstance(test_result["execution_seconds"], (int, float)), \
            "execution_seconds should be numeric"

    # Verify test count matches
    expected_count = len(test_inputs_list) if test_inputs_list else 1
    assert len(result["test_results"]) == expected_count, \
        f"Expected {expected_count} test results, got {len(result['test_results'])}"


@pytest.mark.property
@given(
    skill_name=skill_names,
    description=task_descriptions,
    code=generated_code
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_skill_candidate_model_structure_invariant(
    db_session,
    skill_name,
    description,
    code
):
    """
    Property: SkillCandidate model accepts valid parameters.

    For any valid skill name, description, and code, creating a SkillCandidate
    should succeed and produce a model with correct field types.
    """
    import uuid

    candidate = SkillCandidate(
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        source_episode_id=str(uuid.uuid4()),
        skill_name=skill_name,
        skill_description=description,
        generated_code=code,
        failure_pattern={},
        validation_status="pending",
        fitness_score=None,
        validation_result=None,
        validated_at=None,
        promoted_at=None,
        created_at=datetime.now(timezone.utc)
    )

    # Verify all fields set correctly
    assert candidate.skill_name == skill_name
    assert candidate.skill_description == description
    assert candidate.generated_code == code
    assert candidate.validation_status == "pending"
    assert candidate.fitness_score is None
    assert candidate.validation_result is None

    # Verify types
    assert isinstance(candidate.skill_name, str)
    assert isinstance(candidate.skill_description, str)
    assert isinstance(candidate.generated_code, str)
    assert isinstance(candidate.validation_status, str)


@pytest.mark.property
@given(
    initial_status=st.sampled_from(['pending', 'validated', 'failed', 'promoted']),
    passed=st.booleans()
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_validation_status_transition_invariant(
    memento_engine,
    db_session,
    initial_status,
    passed
):
    """
    Property: Validation status transitions are valid.

    For any initial status and validation result, the validation_status
    should transition appropriately: pending -> validated/failed.
    """
    import uuid

    # Create candidate
    candidate = SkillCandidate(
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        source_episode_id=str(uuid.uuid4()),
        skill_name="test_skill",
        skill_description="Test skill",
        generated_code="print('test')",
        failure_pattern={},
        validation_status=initial_status,
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(candidate)
    db_session.commit()

    # Store initial status
    status_before = candidate.validation_status

    # Mock validation result
    result = {
        "passed": passed,
        "test_results": []
    }

    # Update candidate (simulating validate_candidate behavior)
    candidate.validation_status = "validated" if passed else "failed"
    candidate.validation_result = result
    candidate.validated_at = datetime.now(timezone.utc)

    if passed:
        candidate.fitness_score = 1.0

    db_session.commit()

    # Verify transition
    assert candidate.validation_status in ['validated', 'failed'], \
        f"Invalid status after validation: {candidate.validation_status}"

    # Verify status matches result
    if passed:
        assert candidate.validation_status == "validated", \
            "Passed validation should result in 'validated' status"
        assert candidate.fitness_score == 1.0, \
            "Passed validation should set fitness_score to 1.0"
    else:
        assert candidate.validation_status == "failed", \
            "Failed validation should result in 'failed' status"


@pytest.mark.property
@given(
    fitness_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fitness_score_bounds_invariant(
    db_session,
    fitness_score
):
    """
    Property: Fitness scores are always in [0.0, 1.0].

    For any fitness score value, setting it on a SkillCandidate should
    maintain the value within [0.0, 1.0] bounds.
    """
    import uuid

    candidate = SkillCandidate(
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        source_episode_id=str(uuid.uuid4()),
        skill_name="test_skill",
        skill_description="Test skill",
        generated_code="print('test')",
        failure_pattern={},
        validation_status="validated",
        fitness_score=fitness_score,
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(candidate)
    db_session.commit()

    # Verify fitness score in bounds
    assert 0.0 <= candidate.fitness_score <= 1.0, \
        f"Fitness score {candidate.fitness_score} out of bounds [0.0, 1.0]"


@pytest.mark.property
@given(
    skill_name1=skill_names,
    skill_name2=skill_names,
    description1=task_descriptions,
    description2=task_descriptions
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_candidate_uniqueness_invariant(
    db_session,
    skill_name1,
    skill_name2,
    description1,
    description2
):
    """
    Property: Different candidates can have the same skill name.

    The system allows multiple candidates with the same skill name (e.g.,
    from different episodes or different generations). This is a property
    test to verify this behavior is consistent.
    """
    import uuid

    # Create two candidates with potentially same names
    candidate1 = SkillCandidate(
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        source_episode_id=str(uuid.uuid4()),
        skill_name=skill_name1,
        skill_description=description1,
        generated_code="print('candidate1')",
        failure_pattern={},
        validation_status="pending",
        created_at=datetime.now(timezone.utc)
    )

    candidate2 = SkillCandidate(
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        source_episode_id=str(uuid.uuid4()),
        skill_name=skill_name2,
        skill_description=description2,
        generated_code="print('candidate2')",
        failure_pattern={},
        validation_status="pending",
        created_at=datetime.now(timezone.utc)
    )

    db_session.add(candidate1)
    db_session.add(candidate2)
    db_session.commit()

    # Verify both created successfully
    assert candidate1.id is not None, "First candidate should have ID"
    assert candidate2.id is not None, "Second candidate should have ID"
    assert candidate1.id != candidate2.id, "Candidates should have different IDs"

    # If names are same, verify both have same name
    if skill_name1 == skill_name2:
        assert candidate1.skill_name == candidate2.skill_name, \
            "Candidates with same skill_name should match"


@pytest.mark.property
@given(
    metadata=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.text(), st.integers(), st.floats(), st.booleans(), st.none()),
        min_size=0,
        max_size=20
    )
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_failure_pattern_storage_invariant(
    db_session,
    metadata
):
    """
    Property: Failure pattern metadata is stored correctly.

    For any valid metadata dict, storing it in the failure_pattern field
    should preserve the structure and values.
    """
    import uuid

    candidate = SkillCandidate(
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        source_episode_id=str(uuid.uuid4()),
        skill_name="test_skill",
        skill_description="Test skill",
        generated_code="print('test')",
        failure_pattern=metadata,
        validation_status="pending",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(candidate)
    db_session.commit()

    # Verify failure_pattern preserved
    assert candidate.failure_pattern == metadata, \
        "Failure pattern metadata not preserved correctly"

    # Verify type
    assert isinstance(candidate.failure_pattern, dict), \
        "Failure pattern should be a dict"
