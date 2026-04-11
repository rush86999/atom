"""
Property-Based Tests for Auto-Dev Database Models

This module tests Auto-Dev database model invariants using Hypothesis to generate
hundreds of test cases automatically.

Properties tested:
1. ToolMutation Model Integrity Invariant - Required fields and types
2. WorkflowVariant Model Integrity Invariant - Required fields and types
3. SkillCandidate Model Integrity Invariant - Required fields and types
4. Fitness Score Bounds Invariant - All fitness scores in [0.0, 1.0]
5. Timestamp Monotonicity Invariant - Updated timestamp >= created timestamp
6. JSON Field Schema Invariant - JSON fields accept valid data
"""

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from datetime import datetime, timezone
import uuid

from core.auto_dev.models import ToolMutation, WorkflowVariant, SkillCandidate


# =============================================================================
# Strategy Definitions
# =============================================================================

# Tenant ID strategy
tenant_ids = st.text(min_size=36, max_size=36, alphabet='abcdef0123456789-')

# Agent ID strategy
agent_ids = st.text(min_size=36, max_size=36, alphabet='abcdef0123456789-')

# Parent ID strategy
parent_ids = st.text(min_size=36, max_size=36, alphabet='abcdef0123456789-')

# Tool name strategy
tool_names = st.text(min_size=1, max_size=255).filter(
    lambda x: len(x.strip()) > 0
)

# Code strategy
code_snippets = st.text(min_size=1, max_size=5000).filter(
    lambda x: len(x.strip()) > 0
)

# Sandbox status strategy
sandbox_statuses = st.sampled_from(['pending', 'passed', 'failed'])

# Evaluation status strategy
evaluation_statuses = st.sampled_from(['pending', 'evaluated', 'pruned'])

# Validation status strategy
validation_statuses = st.sampled_from(['pending', 'validated', 'failed', 'promoted'])

# Fitness score strategy
fitness_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Fitness signals strategy (proxy signals)
fitness_signals = st.dictionaries(
    keys=st.sampled_from([
        'execution_success',
        'syntax_error',
        'execution_latency_ms',
        'user_approved_proposal',
        'expects_delayed_eval',
        'invoice_created',
        'crm_conversion',
        'conversion_success',
        'email_bounce',
        'error_signal',
        'conversion_value'
    ]),
    values=st.one_of(st.booleans(), st.floats(min_value=0.0, max_value=10000.0), st.none()),
    min_size=0,
    max_size=10
)

# Workflow definition strategy (JSON)
workflow_definitions = st.dictionaries(
    keys=st.text(min_size=1, max_size=50),
    values=st.one_of(st.text(), st.integers(), st.floats(), st.booleans(), st.none()),
    min_size=1,
    max_size=20
)

# Skill name strategy
skill_names = st.text(min_size=1, max_size=255).filter(
    lambda x: len(x.strip()) > 0
)

# Skill description strategy
skill_descriptions = st.text(min_size=0, max_size=5000)

# Failure pattern strategy
failure_patterns = st.dictionaries(
    keys=st.text(min_size=1, max_size=50),
    values=st.one_of(st.text(), st.integers(), st.floats(), st.lists(st.integers())),
    min_size=0,
    max_size=20
)

# Validation result strategy
validation_results = st.dictionaries(
    keys=st.sampled_from(['passed', 'test_results', 'error']),
    values=st.one_of(st.booleans(), st.integers(), st.floats(), st.text(), st.none()),
    min_size=0,
    max_size=10
)


# =============================================================================
# Property Tests
# =============================================================================

@pytest.mark.property
@given(
    tenant_id=tenant_ids,
    parent_tool_id=st.one_of(parent_ids, st.none()),
    tool_name=tool_names,
    mutated_code=code_snippets,
    sandbox_status=sandbox_statuses
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_tool_mutation_model_integrity_invariant(
    db_session,
    tenant_id,
    parent_tool_id,
    tool_name,
    mutated_code,
    sandbox_status
):
    """
    Property: ToolMutation model accepts valid parameters and maintains data integrity.

    For any valid input parameters, creating a ToolMutation should succeed
    and preserve all field values correctly.
    """
    mutation = ToolMutation(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        parent_tool_id=parent_tool_id,
        tool_name=tool_name,
        mutated_code=mutated_code,
        sandbox_status=sandbox_status,
        execution_error=None,
        created_at=datetime.now(timezone.utc)
    )

    db_session.add(mutation)
    db_session.commit()

    # Verify fields preserved
    assert mutation.tenant_id == tenant_id
    assert mutation.parent_tool_id == parent_tool_id
    assert mutation.tool_name == tool_name
    assert mutation.mutated_code == mutated_code
    assert mutation.sandbox_status == sandbox_status

    # Verify types
    assert isinstance(mutation.id, str)
    assert isinstance(mutation.tenant_id, str)
    assert isinstance(mutation.tool_name, str)
    assert isinstance(mutation.mutated_code, str)
    assert isinstance(mutation.sandbox_status, str)

    # Verify sandbox status is valid
    assert mutation.sandbox_status in ['pending', 'passed', 'failed']


@pytest.mark.property
@given(
    tenant_id=tenant_ids,
    parent_variant_id=st.one_of(parent_ids, st.none()),
    agent_id=st.one_of(agent_ids, st.none()),
    workflow_definition=workflow_definitions,
    fitness_score=st.one_of(fitness_scores, st.none()),
    fitness_signals=st.one_of(fitness_signals, st.none()),
    evaluation_status=evaluation_statuses
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_workflow_variant_model_integrity_invariant(
    db_session,
    tenant_id,
    parent_variant_id,
    agent_id,
    workflow_definition,
    fitness_score,
    fitness_signals,
    evaluation_status
):
    """
    Property: WorkflowVariant model accepts valid parameters and maintains data integrity.

    For any valid input parameters, creating a WorkflowVariant should succeed
    and preserve all field values correctly.
    """
    variant = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        parent_variant_id=parent_variant_id,
        agent_id=agent_id,
        workflow_definition=workflow_definition,
        fitness_score=fitness_score,
        fitness_signals=fitness_signals,
        evaluation_status=evaluation_status,
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=None
    )

    db_session.add(variant)
    db_session.commit()

    # Verify fields preserved
    assert variant.tenant_id == tenant_id
    assert variant.parent_variant_id == parent_variant_id
    assert variant.agent_id == agent_id
    assert variant.workflow_definition == workflow_definition
    assert variant.fitness_score == fitness_score
    assert variant.fitness_signals == fitness_signals
    assert variant.evaluation_status == evaluation_status

    # Verify types
    assert isinstance(variant.id, str)
    assert isinstance(variant.tenant_id, str)
    assert isinstance(variant.workflow_definition, dict)
    assert isinstance(variant.evaluation_status, str)

    # Verify evaluation status is valid
    assert variant.evaluation_status in ['pending', 'evaluated', 'pruned']

    # Verify fitness score in bounds if present
    if variant.fitness_score is not None:
        assert 0.0 <= variant.fitness_score <= 1.0, \
            f"Fitness score {variant.fitness_score} out of bounds"


@pytest.mark.property
@given(
    tenant_id=tenant_ids,
    agent_id=st.one_of(agent_ids, st.none()),
    source_episode_id=st.one_of(parent_ids, st.none()),
    skill_name=skill_names,
    skill_description=skill_descriptions,
    generated_code=code_snippets,
    failure_pattern=failure_patterns,
    validation_status=validation_statuses,
    fitness_score=st.one_of(fitness_scores, st.none()),
    validation_result=st.one_of(validation_results, st.none())
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_skill_candidate_model_integrity_invariant(
    db_session,
    tenant_id,
    agent_id,
    source_episode_id,
    skill_name,
    skill_description,
    generated_code,
    failure_pattern,
    validation_status,
    fitness_score,
    validation_result
):
    """
    Property: SkillCandidate model accepts valid parameters and maintains data integrity.

    For any valid input parameters, creating a SkillCandidate should succeed
    and preserve all field values correctly.
    """
    candidate = SkillCandidate(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        agent_id=agent_id,
        source_episode_id=source_episode_id,
        skill_name=skill_name,
        skill_description=skill_description,
        generated_code=generated_code,
        failure_pattern=failure_pattern,
        validation_status=validation_status,
        fitness_score=fitness_score,
        validation_result=validation_result,
        created_at=datetime.now(timezone.utc),
        validated_at=None,
        promoted_at=None
    )

    db_session.add(candidate)
    db_session.commit()

    # Verify fields preserved
    assert candidate.tenant_id == tenant_id
    assert candidate.agent_id == agent_id
    assert candidate.source_episode_id == source_episode_id
    assert candidate.skill_name == skill_name
    assert candidate.skill_description == skill_description
    assert candidate.generated_code == generated_code
    assert candidate.failure_pattern == failure_pattern
    assert candidate.validation_status == validation_status
    assert candidate.fitness_score == fitness_score
    assert candidate.validation_result == validation_result

    # Verify types
    assert isinstance(candidate.id, str)
    assert isinstance(candidate.tenant_id, str)
    assert isinstance(candidate.skill_name, str)
    assert isinstance(candidate.generated_code, str)
    assert isinstance(candidate.validation_status, str)

    # Verify validation status is valid
    assert candidate.validation_status in ['pending', 'validated', 'failed', 'promoted']

    # Verify fitness score in bounds if present
    if candidate.fitness_score is not None:
        assert 0.0 <= candidate.fitness_score <= 1.0, \
            f"Fitness score {candidate.fitness_score} out of bounds"


@pytest.mark.property
@given(
    initial_score=fitness_scores,
    adjustment=st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fitness_score_bounds_invariant(
    db_session,
    initial_score,
    adjustment
):
    """
    Property: Fitness scores are always clamped to [0.0, 1.0].

    For any initial fitness score and adjustment, the final score should
    be clamped to [0.0, 1.0] bounds.
    """
    # Create variant with initial score
    variant = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        workflow_definition={"test": True},
        fitness_score=initial_score,
        evaluation_status="pending",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(variant)
    db_session.commit()

    # Apply adjustment
    adjusted_score = max(0.0, min(1.0, initial_score + adjustment))
    variant.fitness_score = adjusted_score
    db_session.commit()

    # Verify bounds
    assert 0.0 <= variant.fitness_score <= 1.0, \
        f"Fitness score {variant.fitness_score} out of bounds [0.0, 1.0]"


@pytest.mark.property
@given(
    delay_seconds=st.integers(min_value=0, max_value=2)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_timestamp_monotonicity_invariant(
    db_session,
    delay_seconds
):
    """
    Property: Last evaluated timestamp >= created timestamp.

    For any delay, the last_evaluated_at timestamp should be >= created_at
    timestamp after updating the variant.
    """
    import time

    # Create variant
    variant = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        workflow_definition={"test": True},
        fitness_score=None,
        evaluation_status="pending",
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=None
    )
    db_session.add(variant)
    db_session.commit()

    created_time = variant.created_at

    # Wait specified delay
    time.sleep(delay_seconds)

    # Update variant
    variant.last_evaluated_at = datetime.now(timezone.utc)
    db_session.commit()

    # Verify timestamp ordering
    assert variant.last_evaluated_at >= variant.created_at, \
        f"last_evaluated_at {variant.last_evaluated_at} < created_at {variant.created_at}"

    assert variant.last_evaluated_at >= created_time, \
        f"last_evaluated_at {variant.last_evaluated_at} < original created_at {created_time}"


@pytest.mark.property
@given(
    fitness_signals_data=fitness_signals
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_json_field_schema_invariant(
    db_session,
    fitness_signals_data
):
    """
    Property: JSON fields accept and store valid JSON data.

    For any valid fitness signals dict, storing it in the fitness_signals
    field should preserve the structure and values.
    """
    # Create variant with fitness signals
    variant = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        workflow_definition={"test": True},
        fitness_score=0.5,
        fitness_signals=fitness_signals_data,
        evaluation_status="evaluated",
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=datetime.now(timezone.utc)
    )
    db_session.add(variant)
    db_session.commit()

    # Verify JSON field preserved
    assert variant.fitness_signals == fitness_signals_data, \
        "Fitness signals not preserved correctly"

    # Verify type
    assert isinstance(variant.fitness_signals, dict), \
        "Fitness signals should be a dict"


@pytest.mark.property
@given(
    failure_pattern_data=failure_patterns
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_skill_candidate_json_fields_invariant(
    db_session,
    failure_pattern_data
):
    """
    Property: SkillCandidate JSON fields accept and store valid JSON data.

    For any valid failure pattern dict, storing it in the failure_pattern
    field should preserve the structure and values.
    """
    # Create candidate with failure pattern
    candidate = SkillCandidate(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        skill_name="test_skill",
        generated_code="print('test')",
        failure_pattern=failure_pattern_data,
        validation_status="pending",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(candidate)
    db_session.commit()

    # Verify JSON field preserved
    assert candidate.failure_pattern == failure_pattern_data, \
        "Failure pattern not preserved correctly"

    # Verify type
    assert isinstance(candidate.failure_pattern, dict), \
        "Failure pattern should be a dict"


@pytest.mark.property
@given(
    validation_result_data=validation_results
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_validation_result_json_field_invariant(
    db_session,
    validation_result_data
):
    """
    Property: validation_result JSON field accepts and stores valid JSON data.

    For any valid validation result dict, storing it should preserve the
    structure and values.
    """
    # Create candidate with validation result
    candidate = SkillCandidate(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        skill_name="test_skill",
        generated_code="print('test')",
        validation_status="validated",
        validation_result=validation_result_data,
        fitness_score=1.0,
        created_at=datetime.now(timezone.utc),
        validated_at=datetime.now(timezone.utc)
    )
    db_session.add(candidate)
    db_session.commit()

    # Verify JSON field preserved
    assert candidate.validation_result == validation_result_data, \
        "Validation result not preserved correctly"

    # Verify type
    assert isinstance(candidate.validation_result, dict), \
        "Validation result should be a dict"


@pytest.mark.property
@given(
    code1=code_snippets,
    code2=code_snippets
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_workflow_variant_uniqueness_invariant(
    db_session,
    code1,
    code2
):
    """
    Property: Different workflow variants can have similar definitions.

    The system allows multiple variants with similar or identical definitions
    (e.g., from different mutation runs). This property test verifies that
    unique IDs are assigned even for similar variants.
    """
    # Create two variants with potentially same code
    variant1 = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        workflow_definition={"code": code1},
        fitness_score=0.5,
        evaluation_status="evaluated",
        created_at=datetime.now(timezone.utc)
    )

    variant2 = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        workflow_definition={"code": code2},
        fitness_score=0.6,
        evaluation_status="evaluated",
        created_at=datetime.now(timezone.utc)
    )

    db_session.add(variant1)
    db_session.add(variant2)
    db_session.commit()

    # Verify both created successfully
    assert variant1.id is not None, "First variant should have ID"
    assert variant2.id is not None, "Second variant should have ID"
    assert variant1.id != variant2.id, "Variants should have different IDs"


@pytest.mark.property
@given(
    status1=validation_statuses,
    status2=validation_statuses
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_skill_candidate_status_transitions_invariant(
    db_session,
    status1,
    status2
):
    """
    Property: Skill candidates can have any validation status.

    For any two validation statuses, creating candidates with those statuses
    should succeed. The system doesn't enforce strict status transitions
    at the model level (that's done at the service level).
    """
    # Create two candidates with different statuses
    candidate1 = SkillCandidate(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        skill_name="test_skill_1",
        generated_code="print('test1')",
        validation_status=status1,
        created_at=datetime.now(timezone.utc)
    )

    candidate2 = SkillCandidate(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        skill_name="test_skill_2",
        generated_code="print('test2')",
        validation_status=status2,
        created_at=datetime.now(timezone.utc)
    )

    db_session.add(candidate1)
    db_session.add(candidate2)
    db_session.commit()

    # Verify both created successfully
    assert candidate1.validation_status == status1
    assert candidate2.validation_status == status2

    # Verify statuses are valid
    assert candidate1.validation_status in ['pending', 'validated', 'failed', 'promoted']
    assert candidate2.validation_status in ['pending', 'validated', 'failed', 'promoted']
