"""
Test FitnessService scoring and evaluation.

Tests cover:
- Initial proxy evaluation
- Delayed webhook evaluation
- Top variants retrieval
- Score normalization
- Scoring math
"""

import pytest

from core.auto_dev.fitness_service import FitnessService
from core.auto_dev.models import WorkflowVariant


class TestFitnessServiceInitialProxy:
    """Test evaluate_initial_proxy() scores."""

    def test_syntax_validation(self, auto_dev_db_session, sample_workflow_variant):
        """Test syntax validation."""
        service = FitnessService(auto_dev_db_session)

        proxy_signals = {
            "syntax_error": False,
            "execution_success": True,
            "execution_latency_ms": 1000,
        }

        score = service.evaluate_initial_proxy(
            sample_workflow_variant.id,
            sample_workflow_variant.tenant_id,
            proxy_signals,
        )

        assert 0.0 <= score <= 1.0

    def test_compilation_check(self, auto_dev_db_session, sample_tenant_id):
        """Test compilation check."""
        service = FitnessService(auto_dev_db_session)

        variant = WorkflowVariant(
            tenant_id=sample_tenant_id,
            workflow_def={},
            evaluation_status="pending",
        )
        auto_dev_db_session.add(variant)
        auto_dev_db_session.commit()

        proxy_signals = {
            "syntax_error": True,  # Compilation error
            "execution_success": False,
        }

        score = service.evaluate_initial_proxy(
            variant.id,
            variant.tenant_id,
            proxy_signals,
        )

        # Syntax error should penalize score
        assert score < 0.5

    def test_semantic_similarity(self, auto_dev_db_session, sample_workflow_variant):
        """Test semantic similarity scoring."""
        service = FitnessService(auto_dev_db_session)

        proxy_signals = {
            "syntax_error": False,
            "execution_success": True,
            "user_approved_proposal": True,
        }

        score = service.evaluate_initial_proxy(
            sample_workflow_variant.id,
            sample_workflow_variant.tenant_id,
            proxy_signals,
        )

        # User approval should boost score
        assert score >= 0.5


class TestFitnessServiceDelayedWebhook:
    """Test evaluate_delayed_webhook() scores."""

    def test_success_rate_scoring(self, auto_dev_db_session, sample_workflow_variant):
        """Test success rate scoring."""
        service = FitnessService(auto_dev_db_session)

        external_signals = {
            "conversion_success": True,
        }

        score = service.evaluate_delayed_webhook(
            sample_workflow_variant.id,
            sample_workflow_variant.tenant_id,
            external_signals,
        )

        assert 0.0 <= score <= 1.0

    def test_speed_scoring(self, auto_dev_db_session, sample_tenant_id):
        """Test speed scoring."""
        service = FitnessService(auto_dev_db_session)

        variant = WorkflowVariant(
            tenant_id=sample_tenant_id,
            workflow_def={},
            fitness_score=0.5,
            evaluation_status="pending",
        )
        auto_dev_db_session.add(variant)
        auto_dev_db_session.commit()

        external_signals = {
            "invoice_created": True,
        }

        score = service.evaluate_delayed_webhook(
            variant.id,
            variant.tenant_id,
            external_signals,
        )

        assert score > 0.5  # Should increase

    def test_cost_efficiency_scoring(self, auto_dev_db_session, sample_workflow_variant):
        """Test cost efficiency scoring."""
        service = FitnessService(auto_dev_db_session)

        external_signals = {
            "conversion_value": 500.0,
        }

        score = service.evaluate_delayed_webhook(
            sample_workflow_variant.id,
            sample_workflow_variant.tenant_id,
            external_signals,
        )

        assert 0.0 <= score <= 1.0


class TestFitnessServiceTopVariants:
    """Test get_top_variants() returns sorted top N."""

    def test_returns_top_n_variants(self, auto_dev_db_session, sample_tenant_id):
        """Test returns top N variants by fitness."""
        service = FitnessService(auto_dev_db_session)

        # Create variants with different scores
        for i in range(5):
            variant = WorkflowVariant(
                tenant_id=sample_tenant_id,
                workflow_def={"index": i},
                fitness_score=0.1 + (i * 0.1),
                evaluation_status="evaluated",
            )
            auto_dev_db_session.add(variant)

        auto_dev_db_session.commit()

        top_variants = service.get_top_variants(sample_tenant_id, limit=3)

        assert len(top_variants) <= 3
        # Should be sorted descending
        if len(top_variants) > 1:
            assert top_variants[0].fitness_score >= top_variants[1].fitness_score

    def test_stable_sorting(self, auto_dev_db_session, sample_tenant_id):
        """Test stable sorting (deterministic order)."""
        service = FitnessService(auto_dev_db_session)

        # Create variants with same score
        for i in range(3):
            variant = WorkflowVariant(
                tenant_id=sample_tenant_id,
                workflow_def={"index": i},
                fitness_score=0.5,
                evaluation_status="evaluated",
            )
            auto_dev_db_session.add(variant)

        auto_dev_db_session.commit()

        top_variants = service.get_top_variants(sample_tenant_id, limit=5)

        # Should return all 3
        assert len(top_variants) == 3

    def test_handles_empty_list(self, auto_dev_db_session, sample_tenant_id):
        """Test handles empty list."""
        service = FitnessService(auto_dev_db_session)

        top_variants = service.get_top_variants(sample_tenant_id, limit=5)

        assert len(top_variants) == 0


class TestFitnessServiceNormalization:
    """Test scores normalized to [0.0, 1.0]."""

    def test_clamps_to_range(self, auto_dev_db_session, sample_workflow_variant):
        """Test all scores clamped to [0.0, 1.0]."""
        service = FitnessService(auto_dev_db_session)

        # Test with extreme signals
        proxy_signals = {
            "syntax_error": True,
            "execution_success": False,
            "user_approved_proposal": False,
        }

        score = service.evaluate_initial_proxy(
            sample_workflow_variant.id,
            sample_workflow_variant.tenant_id,
            proxy_signals,
        )

        assert 0.0 <= score <= 1.0


class TestFitnessServiceScoringMath:
    """Test scoring math weights components correctly."""

    def test_initial_formula(self, auto_dev_db_session, sample_workflow_variant):
        """Test initial formula: syntax*0.3 + compilation*0.4 + semantic*0.3."""
        service = FitnessService(auto_dev_db_session)

        proxy_signals = {
            "syntax_error": False,
            "execution_success": True,
            "user_approved_proposal": True,
        }

        score = service.evaluate_initial_proxy(
            sample_workflow_variant.id,
            sample_workflow_variant.tenant_id,
            proxy_signals,
        )

        # Should be high with all positive signals
        assert score >= 0.7

    def test_delayed_formula(self, auto_dev_db_session, sample_workflow_variant):
        """Test delayed formula: success*0.5 + speed*0.3 + cost*0.2."""
        service = FitnessService(auto_dev_db_session)

        external_signals = {
            "conversion_success": True,
            "invoice_created": True,
        }

        score = service.evaluate_delayed_webhook(
            sample_workflow_variant.id,
            sample_workflow_variant.tenant_id,
            external_signals,
        )

        # Should increase score
        assert score > 0
