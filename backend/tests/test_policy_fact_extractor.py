"""
Policy Fact Extractor Tests

Tests for PolicyFactExtractor stub implementation.
Coverage target: 60%+ for core/policy_fact_extractor.py

Tests cover:
- PolicyFactExtractor.__init__: Default and custom workspace_id
- extract_facts_from_document: Stub behavior validation
- get_policy_fact_extractor: Registry singleton pattern

Reference: Phase 181-05 Plan - Policy Fact Extractor coverage
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import time

from core.policy_fact_extractor import (
    PolicyFactExtractor,
    ExtractionResult,
    ExtractedFact,
    get_policy_fact_extractor
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def clear_extractor_registry():
    """Clear the global extractor registry before each test."""
    from core.policy_fact_extractor import _extractors
    _extractors.clear()
    yield
    _extractors.clear()


@pytest.fixture
def sample_extractor(clear_extractor_registry):
    """Create a sample PolicyFactExtractor for testing."""
    return PolicyFactExtractor(workspace_id="test_workspace")


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Create a temporary PDF file path for testing."""
    pdf_file = tmp_path / "test_policy.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")
    return str(pdf_file)


@pytest.fixture
def sample_txt_path(tmp_path):
    """Create a temporary TXT file path for testing."""
    txt_file = tmp_path / "test_policy.txt"
    txt_file.write_text("Sample policy content")
    return str(txt_file)


# ============================================================================
# TEST CLASS: PolicyFactExtractorInit
# ============================================================================

class TestPolicyFactExtractorInit:
    """Tests for PolicyFactExtractor initialization."""

    def test_init_default_workspace(self, clear_extractor_registry):
        """
        GIVEN PolicyFactExtractor class
        WHEN initialized without arguments
        THEN use "default" workspace_id
        """
        extractor = PolicyFactExtractor()
        assert extractor.workspace_id == "default"

    def test_init_custom_workspace(self, clear_extractor_registry):
        """
        GIVEN PolicyFactExtractor class
        WHEN initialized with workspace_id parameter
        THEN use the provided workspace_id
        """
        extractor = PolicyFactExtractor(workspace_id="custom_workspace")
        assert extractor.workspace_id == "custom_workspace"

    def test_extractor_registry_returns_same_instance(self, clear_extractor_registry):
        """
        GIVEN get_policy_fact_extractor function
        WHEN called twice with same workspace_id
        THEN return the same PolicyFactExtractor instance (singleton pattern)
        """
        extractor1 = get_policy_fact_extractor(workspace_id="test_ws")
        extractor2 = get_policy_fact_extractor(workspace_id="test_ws")

        assert extractor1 is extractor2
        assert extractor1.workspace_id == "test_ws"
        assert extractor2.workspace_id == "test_ws"


# ============================================================================
# TEST CLASS: ExtractFactsFromDocument
# ============================================================================

class TestExtractFactsFromDocument:
    """Tests for extract_facts_from_document method."""

    @pytest.mark.asyncio
    async def test_extract_facts_returns_empty_list(self, sample_extractor):
        """
        GIVEN PolicyFactExtractor instance (stub implementation)
        WHEN extract_facts_from_document is called
        THEN return ExtractionResult with empty facts list
        """
        result = await sample_extractor.extract_facts_from_document(
            document_path="/fake/path.pdf",
            user_id="user_123"
        )

        assert isinstance(result, ExtractionResult)
        assert result.facts == []
        assert len(result.facts) == 0

    @pytest.mark.asyncio
    async def test_extract_facts_returns_zero_extraction_time(self, sample_extractor):
        """
        GIVEN PolicyFactExtractor instance (stub implementation)
        WHEN extract_facts_from_document is called
        THEN return ExtractionResult with extraction_time >= 0.0
        """
        result = await sample_extractor.extract_facts_from_document(
            document_path="/fake/path.pdf",
            user_id="user_123"
        )

        assert isinstance(result, ExtractionResult)
        assert result.extraction_time >= 0.0
        assert isinstance(result.extraction_time, float)

    @pytest.mark.asyncio
    async def test_extract_facts_with_nonexistent_file(self, sample_extractor):
        """
        GIVEN PolicyFactExtractor instance (stub implementation)
        WHEN extract_facts_from_document is called with non-existent file path
        THEN return ExtractionResult without crashing (stub doesn't validate file existence)
        """
        # Stub implementation doesn't check file existence
        result = await sample_extractor.extract_facts_from_document(
            document_path="/nonexistent/path/to/file.pdf",
            user_id="user_123"
        )

        assert isinstance(result, ExtractionResult)
        assert result.facts == []

    @pytest.mark.asyncio
    async def test_extract_facts_with_pdf_file(self, sample_extractor, sample_pdf_path):
        """
        GIVEN PolicyFactExtractor instance and a PDF file path
        WHEN extract_facts_from_document is called with .pdf extension
        THEN method executes without error (stub returns empty result)
        """
        result = await sample_extractor.extract_facts_from_document(
            document_path=sample_pdf_path,
            user_id="user_123"
        )

        assert isinstance(result, ExtractionResult)
        assert result.facts == []

    @pytest.mark.asyncio
    async def test_extract_facts_with_txt_file(self, sample_extractor, sample_txt_path):
        """
        GIVEN PolicyFactExtractor instance and a TXT file path
        WHEN extract_facts_from_document is called with .txt extension
        THEN method executes without error (stub returns empty result)
        """
        result = await sample_extractor.extract_facts_from_document(
            document_path=sample_txt_path,
            user_id="user_123"
        )

        assert isinstance(result, ExtractionResult)
        assert result.facts == []

    @pytest.mark.asyncio
    async def test_extract_facts_logs_warning(self, sample_extractor):
        """
        GIVEN PolicyFactExtractor instance (stub implementation)
        WHEN extract_facts_from_document is called
        THEN logger.warning is called with "not implemented" message
        """
        with patch('core.policy_fact_extractor.logger') as mock_logger:
            await sample_extractor.extract_facts_from_document(
                document_path="/fake/path.pdf",
                user_id="user_123"
            )

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            assert "not implemented" in mock_logger.warning.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_extract_facts_returns_extraction_result_object(self, sample_extractor):
        """
        GIVEN PolicyFactExtractor instance (stub implementation)
        WHEN extract_facts_from_document is called
        THEN return proper ExtractionResult object with correct attributes
        """
        result = await sample_extractor.extract_facts_from_document(
            document_path="/fake/path.pdf",
            user_id="user_123"
        )

        # Verify it's an ExtractionResult
        assert isinstance(result, ExtractionResult)

        # Verify it has the correct attributes
        assert hasattr(result, 'facts')
        assert hasattr(result, 'extraction_time')

        # Verify facts is a list
        assert isinstance(result.facts, list)

        # Verify extraction_time is a float
        assert isinstance(result.extraction_time, float)


# ============================================================================
# ADDITIONAL TESTS FOR REGISTRY
# ============================================================================

class TestExtractorRegistry:
    """Additional tests for the extractor registry pattern."""

    def test_different_workspace_ids_create_different_extractors(self, clear_extractor_registry):
        """
        GIVEN get_policy_fact_extractor function
        WHEN called with different workspace_ids
        THEN return different PolicyFactExtractor instances
        """
        extractor1 = get_policy_fact_extractor(workspace_id="workspace_a")
        extractor2 = get_policy_fact_extractor(workspace_id="workspace_b")

        assert extractor1 is not extractor2
        assert extractor1.workspace_id == "workspace_a"
        assert extractor2.workspace_id == "workspace_b"

    def test_get_extractor_creates_new_instance_on_first_call(self, clear_extractor_registry):
        """
        GIVEN get_policy_fact_extractor function
        WHEN called for the first time with a workspace_id
        THEN create and return a new PolicyFactExtractor instance
        """
        from core.policy_fact_extractor import _extractors

        # Verify registry is empty
        assert len(_extractors) == 0

        # Get extractor
        extractor = get_policy_fact_extractor(workspace_id="new_workspace")

        # Verify it was created and added to registry
        assert len(_extractors) == 1
        assert "new_workspace" in _extractors
        assert extractor.workspace_id == "new_workspace"

    def test_get_extractor_reuses_existing_instance(self, clear_extractor_registry):
        """
        GIVEN get_policy_fact_extractor function with existing extractor in registry
        WHEN called again with same workspace_id
        THEN return existing instance without creating new one
        """
        from core.policy_fact_extractor import _extractors

        # Create first extractor
        extractor1 = get_policy_fact_extractor(workspace_id="reuse_workspace")
        initial_registry_size = len(_extractors)

        # Get same extractor again
        extractor2 = get_policy_fact_extractor(workspace_id="reuse_workspace")

        # Verify registry size didn't change
        assert len(_extractors) == initial_registry_size
        assert extractor1 is extractor2
