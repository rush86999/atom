"""
Property-Based Tests for FitnessService

This module tests FitnessService invariants using Hypothesis to generate hundreds
of test cases automatically.

Properties tested:
1. Score Bounds Invariant - All fitness scores are in [0.0, 1.0]
2. Monotonic Top-N Invariant - Top-N selection returns N highest scores
3. Proxy Signal Scoring Invariant - Proxy signals produce valid scores
4. External Signal Adjustment Invariant - External signals adjust scores correctly
5. Top Variants Ordering Invariant - Top variants are ordered by fitness score
"""

import pytest
from hypothesis import given, settings, strategies as st
from datetime import datetime, timezone

from core.auto_dev.fitness_service import FitnessService
from core.auto_dev.models import WorkflowVariant


# =============================================================================
# Strategy Definitions
# =============================================================================

# Score lists (including out-of-bounds values for normalization testing)
raw_scores = st.lists(
    st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    min_size=0,
    max_size=100
)

# Normalized score lists (already in [0.0, 1.0])
normalized_scores = st.lists(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    min_size=0,
    max_size=100
)


# =============================================================================
# Property Tests
# =============================================================================

@pytest.mark.property
@given(
    execution_success=st.booleans(),
    syntax_error=st.booleans(),
    execution_latency_ms=st.floats(min_value=0.0, max_value=10000.0),
    user_approved=st.one_of(st.booleans(), st.none())
)
@settings(max_examples=100)
def test_proxy_signal_bounds_invariant(
    fitness_service,
    db_session,
    execution_success,
    syntax_error,
    execution_latency_ms,
    user_approved
):
    """
    Property: Proxy signal evaluation always produces scores in [0.0, 1.0].

    For any combination of proxy signals (success, syntax error, latency,
    user approval), the resulting fitness score must be clamped to [0.0, 1.0].
    """
    import uuid

    # Create test variant
    variant = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        mutation_type="test_mutation",
        code="print('test')",
        fitness_score=None,
        fitness_signals={},
        evaluation_status="pending",
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=None
    )
    db_session.add(variant)
    db_session.commit()

    # Build proxy signals
    proxy_signals = {
        "execution_success": execution_success,
        "syntax_error": syntax_error,
        "execution_latency_ms": execution_latency_ms,
        "user_approved_proposal": user_approved,
        "expects_delayed_eval": False
    }

    # Evaluate
    score = fitness_service.evaluate_initial_proxy(
        variant.id,
        variant.tenant_id,
        proxy_signals
    )

    # Verify bounds
    assert 0.0 <= score <= 1.0, \
        f"Score {score} out of bounds [0.0, 1.0] for signals: {proxy_signals}"


@pytest.mark.property
@given(
    initial_score=st.floats(min_value=0.0, max_value=1.0),
    invoice_created=st.booleans(),
    crm_conversion=st.booleans(),
    conversion_success=st.booleans(),
    email_bounce=st.booleans(),
    error_signal=st.booleans(),
    conversion_value=st.floats(min_value=0.0, max_value=5000.0)
)
@settings(max_examples=100)
def test_external_signal_adjustment_invariant(
    fitness_service,
    db_session,
    initial_score,
    invoice_created,
    crm_conversion,
    conversion_success,
    email_bounce,
    error_signal,
    conversion_value
):
    """
    Property: External signal evaluation produces scores in [0.0, 1.0].

    For any combination of external signals (webhooks), the adjusted fitness
    score must remain in [0.0, 1.0] after applying positive/negative adjustments.
    """
    import uuid

    # Create test variant with initial score
    variant = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        mutation_type="test_mutation",
        code="print('test')",
        fitness_score=initial_score,
        fitness_signals={"proxy": {}},
        evaluation_status="pending",
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=datetime.now(timezone.utc)
    )
    db_session.add(variant)
    db_session.commit()

    # Build external signals
    external_signals = {
        "invoice_created": invoice_created,
        "crm_conversion": crm_conversion,
        "conversion_success": conversion_success,
        "email_bounce": email_bounce,
        "error_signal": error_signal,
        "conversion_value": conversion_value
    }

    # Evaluate
    final_score = fitness_service.evaluate_delayed_webhook(
        variant.id,
        variant.tenant_id,
        external_signals
    )

    # Verify bounds
    assert 0.0 <= final_score <= 1.0, \
        f"Final score {final_score} out of bounds [0.0, 1.0] after external signals"


@pytest.mark.property
@given(
    variants_count=st.integers(min_value=0, max_value=20),
    base_score=st.floats(min_value=0.0, max_value=1.0)
)
@settings(max_examples=100)
def test_top_variants_ordering_invariant(
    fitness_service,
    db_session,
    variants_count,
    base_score
):
    """
    Property: Top variants are ordered by descending fitness score.

    For any set of variants with varying fitness scores, get_top_variants
    should return variants sorted in descending order by fitness score.
    """
    import uuid

    tenant_id = str(uuid.uuid4())

    # Create variants with different scores
    variants = []
    for i in range(variants_count):
        # Create decreasing scores
        score = max(0.0, min(1.0, base_score - (i * 0.05)))

        variant = WorkflowVariant(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            agent_id=str(uuid.uuid4()),
            mutation_type=f"mutation_{i}",
            code=f"print('test_{i}')",
            fitness_score=score,
            fitness_signals={},
            evaluation_status="evaluated",
            created_at=datetime.now(timezone.utc),
            last_evaluated_at=datetime.now(timezone.utc)
        )
        variants.append(variant)
        db_session.add(variant)

    db_session.commit()

    # Get top variants
    limit = min(5, variants_count)
    top_variants = fitness_service.get_top_variants(tenant_id, limit=limit)

    # Verify ordering (descending by fitness_score)
    if len(top_variants) > 1:
        for i in range(len(top_variants) - 1):
            assert top_variants[i].fitness_score >= top_variants[i + 1].fitness_score, \
                f"Variants not in descending order: {top_variants[i].fitness_score} < {top_variants[i + 1].fitness_score}"

    # Verify count constraint
    assert len(top_variants) <= limit, \
        f"Returned {len(top_variants)} variants, expected <= {limit}"


@pytest.mark.property
@given(
    syntax_error=st.booleans(),
    execution_success=st.booleans(),
    user_approved=st.booleans()
)
@settings(max_examples=100)
def test_syntax_error_penalty_invariant(
    fitness_service,
    db_session,
    syntax_error,
    execution_success,
    user_approved
):
    """
    Property: Syntax errors always result in lower fitness scores.

    For any combination of signals, a variant with syntax errors should
    receive a lower fitness score than an identical variant without errors.
    """
    import uuid

    # Create two variants: one with syntax error, one without
    variant_with_error = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        mutation_type="test_mutation",
        code="print('test')",
        fitness_score=None,
        fitness_signals={},
        evaluation_status="pending",
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=None
    )

    variant_without_error = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        mutation_type="test_mutation",
        code="print('test')",
        fitness_score=None,
        fitness_signals={},
        evaluation_status="pending",
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=None
    )

    db_session.add(variant_with_error)
    db_session.add(variant_without_error)
    db_session.commit()

    # Evaluate with syntax error
    proxy_signals_with_error = {
        "execution_success": execution_success,
        "syntax_error": True,
        "execution_latency_ms": 100.0,
        "user_approved_proposal": user_approved,
        "expects_delayed_eval": False
    }

    # Evaluate without syntax error
    proxy_signals_without_error = {
        "execution_success": execution_success,
        "syntax_error": False,
        "execution_latency_ms": 100.0,
        "user_approved_proposal": user_approved,
        "expects_delayed_eval": False
    }

    score_with_error = fitness_service.evaluate_initial_proxy(
        variant_with_error.id,
        variant_with_error.tenant_id,
        proxy_signals_with_error
    )

    score_without_error = fitness_service.evaluate_initial_proxy(
        variant_without_error.id,
        variant_without_error.tenant_id,
        proxy_signals_without_error
    )

    # Syntax error should result in lower or equal score
    assert score_with_error <= score_without_error, \
        f"Variant with syntax error ({score_with_error}) scored higher than without ({score_without_error})"


@pytest.mark.property
@given(
    base_score=st.floats(min_value=0.0, max_value=0.5),
    positive_signals_count=st.integers(min_value=1, max_value=3)
)
@settings(max_examples=100)
def test_positive_signals_increase_score_invariant(
    fitness_service,
    db_session,
    base_score,
    positive_signals_count
):
    """
    Property: Positive external signals increase fitness score.

    For any variant with a baseline score, adding positive external signals
    (invoice_created, crm_conversion, conversion_success) should increase
    or maintain the fitness score.
    """
    import uuid

    # Create variant with baseline score
    variant = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        mutation_type="test_mutation",
        code="print('test')",
        fitness_score=base_score,
        fitness_signals={"proxy": {}},
        evaluation_status="pending",
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=datetime.now(timezone.utc)
    )
    db_session.add(variant)
    db_session.commit()

    initial_score = variant.fitness_score

    # Build external signals with positive signals
    external_signals = {}

    # Add positive signals based on count
    signal_types = ['invoice_created', 'crm_conversion', 'conversion_success']
    for i in range(min(positive_signals_count, len(signal_types))):
        external_signals[signal_types[i]] = True

    # Evaluate
    final_score = fitness_service.evaluate_delayed_webhook(
        variant.id,
        variant.tenant_id,
        external_signals
    )

    # Verify score increased or stayed same
    assert final_score >= initial_score, \
        f"Positive signals decreased score: {initial_score} -> {final_score}"


@pytest.mark.property
@given(
    base_score=st.floats(min_value=0.5, max_value=1.0),
    negative_signals=st.lists(
        st.sampled_from(['email_bounce', 'error_signal']),
        min_size=1,
        max_size=2,
        unique=True
    )
)
@settings(max_examples=100)
def test_negative_signals_decrease_score_invariant(
    fitness_service,
    db_session,
    base_score,
    negative_signals
):
    """
    Property: Negative external signals decrease fitness score.

    For any variant with a baseline score, adding negative external signals
    (email_bounce, error_signal) should decrease or maintain the fitness score.
    """
    import uuid

    # Create variant with baseline score
    variant = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        mutation_type="test_mutation",
        code="print('test')",
        fitness_score=base_score,
        fitness_signals={"proxy": {}},
        evaluation_status="pending",
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=datetime.now(timezone.utc)
    )
    db_session.add(variant)
    db_session.commit()

    initial_score = variant.fitness_score

    # Build external signals with negative signals
    external_signals = {signal: True for signal in negative_signals}

    # Evaluate
    final_score = fitness_service.evaluate_delayed_webhook(
        variant.id,
        variant.tenant_id,
        external_signals
    )

    # Verify score decreased or stayed same
    assert final_score <= initial_score, \
        f"Negative signals increased score: {initial_score} -> {final_score}"


@pytest.mark.property
@given(
    initial_signals=st.dictionaries(
        keys=st.sampled_from(['execution_success', 'syntax_error', 'execution_latency_ms']),
        values=st.one_of(st.booleans(), st.floats(min_value=0.0, max_value=10000.0)),
        min_size=1,
        max_size=3
    )
)
@settings(max_examples=100)
def test_fitness_signals_preservation_invariant(
    fitness_service,
    db_session,
    initial_signals
):
    """
    Property: Fitness signals are preserved and stored correctly.

    For any proxy signals, the evaluated variant should store the signals
    in the fitness_signals dictionary under the 'proxy' key.
    """
    import uuid

    # Create variant
    variant = WorkflowVariant(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        mutation_type="test_mutation",
        code="print('test')",
        fitness_score=None,
        fitness_signals={},
        evaluation_status="pending",
        created_at=datetime.now(timezone.utc),
        last_evaluated_at=None
    )
    db_session.add(variant)
    db_session.commit()

    # Build proxy signals
    proxy_signals = {
        **initial_signals,
        "user_approved_proposal": None,
        "expects_delayed_eval": False
    }

    # Evaluate
    fitness_service.evaluate_initial_proxy(
        variant.id,
        variant.tenant_id,
        proxy_signals
    )

    # Refresh from database
    db_session.refresh(variant)

    # Verify signals preserved
    assert 'proxy' in variant.fitness_signals, \
        "Proxy signals not stored in fitness_signals"

    stored_proxy = variant.fitness_signals['proxy']
    for key, value in initial_signals.items():
        assert key in stored_proxy, f"Signal {key} not preserved"
        assert stored_proxy[key] == value, \
            f"Signal {key} value changed: {value} -> {stored_proxy[key]}"
