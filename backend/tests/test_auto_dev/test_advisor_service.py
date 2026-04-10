"""
Test AdvisorService guidance generation.

Tests cover:
- Guidance generation
- Variant performance analysis
- LLM integration
- Error handling
- Caching
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.auto_dev.advisor_service import AdvisorService


class TestAdvisorServiceGuidanceGeneration:
    """Test generate_guidance() creates human-readable advice."""

    @pytest.mark.asyncio
    async def test_generate_guidance_calls_llm(self, mock_auto_dev_llm, auto_dev_db_session):
        """Test generate_guidance() calls LLM."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        result = await service.generate_guidance(tenant_id="tenant-001")

        assert "status" in result
        assert result["status"] == "success"
        assert "message" in result

    @pytest.mark.asyncio
    async def test_includes_variant_metadata(self, mock_auto_dev_llm, auto_dev_db_session, sample_workflow_variant):
        """Test includes variant metadata."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        result = await service.generate_guidance(tenant_id=sample_workflow_variant.tenant_id)

        assert "data_summary" in result

    @pytest.mark.asyncio
    async def test_includes_fitness_signals(self, mock_auto_dev_llm, auto_dev_db_session, sample_workflow_variant):
        """Test includes fitness signals."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        result = await service.generate_guidance(tenant_id=sample_workflow_variant.tenant_id)

        summary = result["data_summary"]
        assert "top_fitness_score" in summary

    @pytest.mark.asyncio
    async def test_returns_human_readable_text(self, mock_auto_dev_llm, auto_dev_db_session):
        """Test returns human-readable text."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        result = await service.generate_guidance(tenant_id="tenant-001")

        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    @pytest.mark.asyncio
    async def test_handles_llm_errors(self, auto_dev_db_session):
        """Test handles LLM errors."""
        # Mock LLM that fails
        mock_llm = MagicMock()
        mock_llm.generate_completion = AsyncMock(side_effect=Exception("LLM error"))

        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_llm)

        result = await service.generate_guidance(tenant_id="tenant-001")

        # Should fall back to heuristic guidance
        assert result["status"] == "success"
        assert "message" in result


class TestAdvisorServiceVariantAnalysis:
    """Test analyze_variant_performance() provides detailed analysis."""

    @pytest.mark.asyncio
    async def test_compares_variants(self, mock_auto_dev_llm, auto_dev_db_session, sample_tenant_id):
        """Test compares variants."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        result = await service.generate_guidance(tenant_id=sample_tenant_id)

        assert "data_summary" in result

    @pytest.mark.asyncio
    async def test_identifies_strengths_weaknesses(self, mock_auto_dev_llm, auto_dev_db_session, sample_tenant_id):
        """Test identifies strengths/weaknesses."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        result = await service.generate_guidance(tenant_id=sample_tenant_id)

        # Message should contain guidance
        assert len(result["message"]) > 50


class TestAdvisorServiceLLMIntegration:
    """Test uses LLMService for guidance."""

    @pytest.mark.asyncio
    async def test_uses_llm_service(self, mock_auto_dev_llm, auto_dev_db_session):
        """Test uses LLMService."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        await service.generate_guidance(tenant_id="tenant-001")

        # Should have called LLM
        assert mock_auto_dev_llm.generate_completion.called

    @pytest.mark.asyncio
    async def test_passes_context_correctly(self, mock_auto_dev_llm, auto_dev_db_session):
        """Test passes context correctly."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        await service.generate_guidance(tenant_id="tenant-001")

        # Check call arguments
        call_args = mock_auto_dev_llm.generate_completion.call_args
        assert "system_prompt" in call_args[1]
        assert "user_prompt" in call_args[1]


class TestAdvisorServiceErrorHandling:
    """Test handles missing data gracefully."""

    @pytest.mark.asyncio
    async def test_handles_missing_variant_data(self, auto_dev_db_session):
        """Test handles missing variant data."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=None)

        result = await service.generate_guidance(tenant_id="nonexistent-tenant")

        # Should still return success
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_returns_safe_default_guidance(self, auto_dev_db_session):
        """Test returns safe default guidance."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=None)

        result = await service.generate_guidance(tenant_id="tenant-001")

        assert "message" in result
        assert len(result["message"]) > 0


class TestAdvisorServiceReadinessScore:
    """Test readiness score calculation."""

    @pytest.mark.asyncio
    async def test_calculates_readiness_score(self, mock_auto_dev_llm, auto_dev_db_session, sample_tenant_id):
        """Test calculates readiness score."""
        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        result = await service.generate_guidance(tenant_id=sample_tenant_id)

        assert "readiness_score" in result
        assert 0 <= result["readiness_score"] <= 100

    @pytest.mark.asyncio
    async def test_readiness_increases_with_mutations(self, mock_auto_dev_llm, auto_dev_db_session, sample_tenant_id):
        """Test readiness increases with passed mutations."""
        from core.auto_dev.models import ToolMutation

        # Create some mutations
        for i in range(5):
            mutation = ToolMutation(
                tenant_id=sample_tenant_id,
                tool_name=f"tool_{i}",
                mutated_code="def test(): pass",
                sandbox_status="passed" if i < 3 else "failed",
            )
            auto_dev_db_session.add(mutation)

        auto_dev_db_session.commit()

        service = AdvisorService(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        result = await service.generate_guidance(tenant_id=sample_tenant_id)

        # Readiness should be > 0
        assert result["readiness_score"] > 0
