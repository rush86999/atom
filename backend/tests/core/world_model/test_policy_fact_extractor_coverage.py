"""
Coverage-driven tests for PolicyFactExtractor (currently 0% -> target 70%+)

Target file: core/policy_fact_extractor.py (~89 statements)

Focus areas from coverage gap analysis:
- Extractor initialization (lines 30-39)
- Document extraction (lines 40-67)
- Global registry (lines 70-89)
- Pydantic models (lines 17-28)
"""

import pytest
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from core.policy_fact_extractor import (
    PolicyFactExtractor,
    ExtractedFact,
    ExtractionResult,
    get_policy_fact_extractor,
    _extractors
)


class TestExtractedFactModel:
    """Coverage for ExtractedFact Pydantic model (lines 17-22)"""

    def test_extracted_fact_basic_creation(self):
        """Test basic ExtractedFact creation"""
        fact = ExtractedFact(fact="Expenses over $100 need approval")
        assert fact.fact == "Expenses over $100 need approval"
        assert fact.domain is None
        assert fact.confidence == 0.8

    def test_extracted_fact_with_domain(self):
        """Test ExtractedFact with domain"""
        fact = ExtractedFact(
            fact="Invoices over $5000 need VP approval",
            domain="finance"
        )
        assert fact.domain == "finance"

    def test_extracted_fact_with_custom_confidence(self):
        """Test ExtractedFact with custom confidence"""
        fact = ExtractedFact(
            fact="Travel expenses within 30 days",
            confidence=0.95
        )
        assert fact.confidence == 0.95

    def test_extracted_fact_all_fields(self):
        """Test ExtractedFact with all fields"""
        fact = ExtractedFact(
            fact="Software purchases over $1000 need IT review",
            domain="procurement",
            confidence=0.9
        )
        assert fact.fact == "Software purchases over $1000 need IT review"
        assert fact.domain == "procurement"
        assert fact.confidence == 0.9


class TestExtractionResultModel:
    """Coverage for ExtractionResult Pydantic model (lines 24-28)"""

    def test_extraction_result_basic(self):
        """Test ExtractionResult with empty facts"""
        result = ExtractionResult(facts=[], extraction_time=0.5)
        assert result.facts == []
        assert result.extraction_time == 0.5

    def test_extraction_result_with_facts(self):
        """Test ExtractionResult with facts"""
        facts = [
            ExtractedFact(fact="Rule 1", confidence=0.9),
            ExtractedFact(fact="Rule 2", confidence=0.8)
        ]
        result = ExtractionResult(facts=facts, extraction_time=1.2)
        assert len(result.facts) == 2
        assert result.extraction_time == 1.2

    def test_extraction_result_serialization(self):
        """Test ExtractionResult can be serialized to dict"""
        facts = [ExtractedFact(fact="Test fact")]
        result = ExtractionResult(facts=facts, extraction_time=0.1)
        data = result.model_dump()
        assert "facts" in data
        assert "extraction_time" in data


class TestPolicyFactExtractorInitialization:
    """Coverage for PolicyFactExtractor initialization (lines 30-39)"""

    def test_extractor_initialization_default_workspace(self):
        """Test extractor initialization with default workspace"""
        extractor = PolicyFactExtractor()
        assert extractor.workspace_id == "default"

    def test_extractor_initialization_custom_workspace(self):
        """Test extractor initialization with custom workspace"""
        extractor = PolicyFactExtractor(workspace_id="test-workspace")
        assert extractor.workspace_id == "test-workspace"

    def test_extractor_initialization_with_id(self):
        """Test extractor initialization with specific ID"""
        extractor = PolicyFactExtractor(workspace_id="workspace-123")
        assert extractor.workspace_id == "workspace-123"


class TestExtractFactsFromDocument:
    """Coverage for extract_facts_from_document method (lines 40-67)"""

    @pytest.mark.asyncio
    async def test_extract_facts_returns_empty_result(self):
        """Test extraction returns empty result (stub implementation)"""
        extractor = PolicyFactExtractor()
        result = await extractor.extract_facts_from_document(
            document_path="/path/to/document.pdf",
            user_id="user-123"
        )
        assert isinstance(result, ExtractionResult)
        assert result.facts == []
        assert result.extraction_time >= 0

    @pytest.mark.asyncio
    async def test_extract_facts_measures_time(self):
        """Test extraction measures elapsed time"""
        extractor = PolicyFactExtractor()
        result = await extractor.extract_facts_from_document(
            document_path="/path/to/policy.pdf",
            user_id="user-456"
        )
        # Should have some measurement
        assert result.extraction_time >= 0
        assert result.extraction_time < 1.0  # Should be very fast (stub)

    @pytest.mark.asyncio
    async def test_extract_facts_with_different_paths(self):
        """Test extraction with various document paths"""
        extractor = PolicyFactExtractor()
        paths = [
            "/path/to/policy.pdf",
            "/path/to/document.docx",
            "/path/to/file.txt",
            "relative/path/document.pdf"
        ]

        for path in paths:
            result = await extractor.extract_facts_from_document(
                document_path=path,
                user_id="test-user"
            )
            assert isinstance(result, ExtractionResult)

    @pytest.mark.asyncio
    async def test_extract_facts_with_different_users(self):
        """Test extraction with different user IDs"""
        extractor = PolicyFactExtractor()
        users = ["user-1", "user-2", "admin-user"]

        for user_id in users:
            result = await extractor.extract_facts_from_document(
                document_path="/test.pdf",
                user_id=user_id
            )
            assert isinstance(result, ExtractionResult)

    @pytest.mark.asyncio
    async def test_extract_facts_logs_warning(self):
        """Test extraction logs warning about unimplemented feature"""
        extractor = PolicyFactExtractor()
        with patch("core.policy_fact_extractor.logger") as mock_logger:
            result = await extractor.extract_facts_from_document(
                document_path="/test.pdf",
                user_id="user-123"
            )
            # Should log warning about unimplemented feature
            mock_logger.warning.assert_called_once()
            call_args = str(mock_logger.warning.call_args)
            assert "not implemented" in call_args.lower()


class TestGlobalExtractorRegistry:
    """Coverage for global registry functions (lines 70-89)"""

    def test_get_extractor_creates_new_instance(self):
        """Test get_policy_fact_extractor creates new instance"""
        # Clear registry first
        _extractors.clear()

        extractor = get_policy_fact_extractor("test-workspace")
        assert isinstance(extractor, PolicyFactExtractor)
        assert extractor.workspace_id == "test-workspace"
        assert "test-workspace" in _extractors

    def test_get_extractor_reuses_existing_instance(self):
        """Test get_policy_fact_extractor reuses existing instance"""
        # Clear registry first
        _extractors.clear()

        extractor1 = get_policy_fact_extractor("reuse-workspace")
        extractor2 = get_policy_fact_extractor("reuse-workspace")

        # Should be the same instance
        assert extractor1 is extractor2
        assert len(_extractors) == 1

    def test_get_extractor_default_workspace(self):
        """Test get_policy_fact_extractor with default workspace"""
        # Clear registry first
        _extractors.clear()

        extractor = get_policy_fact_extractor()
        assert isinstance(extractor, PolicyFactExtractor)
        assert extractor.workspace_id == "default"
        assert "default" in _extractors

    def test_get_extractor_multiple_workspaces(self):
        """Test get_policy_fact_extractor with multiple workspaces"""
        # Clear registry first
        _extractors.clear()

        extractor1 = get_policy_fact_extractor("workspace-1")
        extractor2 = get_policy_fact_extractor("workspace-2")
        extractor3 = get_policy_fact_extractor("workspace-3")

        # Should be different instances
        assert extractor1 is not extractor2
        assert extractor2 is not extractor3

        # All should be in registry
        assert len(_extractors) == 3
        assert "workspace-1" in _extractors
        assert "workspace-2" in _extractors
        assert "workspace-3" in _extractors

    def test_get_extractor_logs_creation(self):
        """Test get_policy_fact_extractor logs creation"""
        # Clear registry first
        _extractors.clear()

        with patch("core.policy_fact_extractor.logger") as mock_logger:
            extractor = get_policy_fact_extractor("log-test")
            # Should log creation
            mock_logger.info.assert_called_once()
            call_args = str(mock_logger.info.call_args)
            assert "log-test" in call_args
            assert "created" in call_args.lower()


class TestEdgeCases:
    """Coverage for edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_extract_facts_empty_path(self):
        """Test extraction with empty document path"""
        extractor = PolicyFactExtractor()
        result = await extractor.extract_facts_from_document(
            document_path="",
            user_id="user-123"
        )
        assert isinstance(result, ExtractionResult)

    @pytest.mark.asyncio
    async def test_extract_facts_special_chars_in_path(self):
        """Test extraction with special characters in path"""
        extractor = PolicyFactExtractor()
        special_paths = [
            "/path/to/document with spaces.pdf",
            "/path/to/document-with-dashes.pdf",
            "/path/to/document_with_underscores.pdf"
        ]

        for path in special_paths:
            result = await extractor.extract_facts_from_document(
                document_path=path,
                user_id="user-123"
            )
            assert isinstance(result, ExtractionResult)

    @pytest.mark.asyncio
    async def test_extract_facts_empty_user_id(self):
        """Test extraction with empty user ID"""
        extractor = PolicyFactExtractor()
        result = await extractor.extract_facts_from_document(
            document_path="/test.pdf",
            user_id=""
        )
        assert isinstance(result, ExtractionResult)

    def test_extractor_workspace_id_none(self):
        """Test extractor with None as workspace_id"""
        # This should work - None is a valid value
        extractor = PolicyFactExtractor(workspace_id=None)
        assert extractor.workspace_id is None

    def test_extracted_fact_edge_cases(self):
        """Test ExtractedFact with edge case values"""
        # Empty fact string
        fact = ExtractedFact(fact="")
        assert fact.fact == ""

        # Zero confidence
        fact = ExtractedFact(fact="test", confidence=0.0)
        assert fact.confidence == 0.0

        # Maximum confidence
        fact = ExtractedFact(fact="test", confidence=1.0)
        assert fact.confidence == 1.0

    def test_extraction_result_negative_time(self):
        """Test ExtractionResult with zero time (not negative in practice)"""
        result = ExtractionResult(facts=[], extraction_time=0.0)
        assert result.extraction_time == 0.0

    def test_global_registry_clear_between_tests(self):
        """Test that registry can be cleared between tests"""
        # Add some extractors
        get_policy_fact_extractor("test-1")
        get_policy_fact_extractor("test-2")
        assert len(_extractors) >= 2

        # Clear
        _extractors.clear()
        assert len(_extractors) == 0

        # Can create new ones after clearing
        get_policy_fact_extractor("test-3")
        assert len(_extractors) == 1


class TestModelValidation:
    """Coverage for Pydantic model validation"""

    def test_extracted_fact_validation(self):
        """Test ExtractedFact validates confidence is float"""
        # Pydantic should convert int to float
        fact = ExtractedFact(fact="test", confidence=80)
        assert isinstance(fact.confidence, float)
        assert fact.confidence == 80.0

    def test_extraction_result_validation(self):
        """Test ExtractionResult validates extraction_time is float"""
        # Pydantic should convert int to float
        result = ExtractionResult(facts=[], extraction_time=1)
        assert isinstance(result.extraction_time, float)
        assert result.extraction_time == 1.0

    def test_extracted_fact_optional_domain(self):
        """Test ExtractedFact domain is optional"""
        fact = ExtractedFact(fact="test")
        assert fact.domain is None

        fact_with_domain = ExtractedFact(fact="test", domain="finance")
        assert fact_with_domain.domain == "finance"


class TestAsyncBehavior:
    """Coverage for async method behavior"""

    @pytest.mark.asyncio
    async def test_extract_facts_is_coroutine(self):
        """Test that extract_facts_from_document is async"""
        extractor = PolicyFactExtractor()
        result = await extractor.extract_facts_from_document(
            document_path="/test.pdf",
            user_id="user-123"
        )
        assert isinstance(result, ExtractionResult)

    @pytest.mark.asyncio
    async def test_multiple_consecutive_extractions(self):
        """Test multiple consecutive extraction calls"""
        extractor = PolicyFactExtractor()
        results = []

        for i in range(3):
            result = await extractor.extract_facts_from_document(
                document_path=f"/test{i}.pdf",
                user_id="user-123"
            )
            results.append(result)

        assert len(results) == 3
        assert all(isinstance(r, ExtractionResult) for r in results)


class TestWorkspaceIsolation:
    """Coverage for workspace isolation through extractor instances"""

    def test_different_workspaces_have_different_extractors(self):
        """Test that different workspaces get different extractor instances"""
        # Clear registry
        _extractors.clear()

        extractor1 = get_policy_fact_extractor("workspace-1")
        extractor2 = get_policy_fact_extractor("workspace-2")

        assert extractor1.workspace_id != extractor2.workspace_id
        assert extractor1 is not extractor2

    @pytest.mark.asyncio
    async def test_extractor_workspace_attribute_persistence(self):
        """Test that workspace_id persists on extractor instance"""
        extractor = PolicyFactExtractor(workspace_id="persistent-workspace")

        # workspace_id should persist
        assert extractor.workspace_id == "persistent-workspace"

        # Even after extraction
        await extractor.extract_facts_from_document("/test.pdf", "user-123")
        assert extractor.workspace_id == "persistent-workspace"
