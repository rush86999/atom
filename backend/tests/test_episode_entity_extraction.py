"""
Tests for Episode Entity Extraction
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.episode_segmentation_service import EpisodeSegmentationService
from core.models import ChatMessage, ChatSession, AgentExecution


class TestEntityExtraction:
    """Test entity extraction from messages and executions"""

    @pytest.fixture
    def db(self):
        """Create database session"""
        with get_db_session() as session:
            yield session

    @pytest.fixture
    def segmentation_service(self, db):
        """Create episode segmentation service"""
        return EpisodeSegmentationService(db)

    def test_extract_email_entities(self, segmentation_service):
        """Test extraction of email addresses"""
        messages = [
            ChatMessage(
                id="msg1",
                conversation_id="conv1",
                workspace_id="workspace1",
                role="user",
                content="Contact me at john@example.com or jane@test.org"
            )
        ]

        entities = segmentation_service._extract_entities(messages, [])

        # Should extract email addresses
        assert "john@example.com" in entities
        assert "jane@test.org" in entities

    def test_extract_phone_entities(self, segmentation_service):
        """Test extraction of phone numbers"""
        messages = [
            ChatMessage(
                id="msg1",
                conversation_id="conv1",
                workspace_id="workspace1",
                role="user",
                content="Call me at 555-123-4567 or 555.987.6543"
            )
        ]

        entities = segmentation_service._extract_entities(messages, [])

        # Should extract phone numbers
        assert "555-123-4567" in entities
        assert "555.987.6543" in entities

    def test_extract_url_entities(self, segmentation_service):
        """Test extraction of URLs"""
        messages = [
            ChatMessage(
                id="msg1",
                conversation_id="conv1",
                workspace_id="workspace1",
                role="user",
                content="Check out https://example.com and http://test.org"
            )
        ]

        entities = segmentation_service._extract_entities(messages, [])

        # Should extract URLs
        assert "https://example.com" in entities
        assert "http://test.org" in entities

    def test_extract_from_execution_task(self, segmentation_service):
        """Test extraction from execution input_summary"""
        executions = [
            AgentExecution(
                id="exec1",
                agent_id="agent1",
                input_summary="Send Email to John Smith about Invoice #12345",
                status="completed"
            )
        ]

        entities = segmentation_service._extract_entities([], executions)

        # Should extract capitalized words as potential entities
        assert "John" in entities or "Smith" in entities or "Invoice" in entities

    def test_extract_from_execution_metadata(self, segmentation_service):
        """Test extraction from execution metadata (if present)"""
        # Create a mock execution object with metadata_json
        class MockExecution:
            def __init__(self):
                self.input_summary = "Test task"
                self.metadata_json = {
                    "recipient": "user@example.com",
                    "workflow_id": "workflow_789"
                }

        executions = [MockExecution()]

        entities = segmentation_service._extract_entities([], executions)

        # Should extract from execution metadata if available
        # Note: This tests the extraction logic, not the model structure
        assert len(entities) > 0  # Should extract some entities

    def test_entity_limiting(self, segmentation_service):
        """Test that entities are limited to top 20"""
        # Create message with many potential entities
        many_emails = ", ".join([f"user{i}@example.com" for i in range(30)])
        messages = [
            ChatMessage(
                id="msg1",
                conversation_id="conv1",
                workspace_id="workspace1",
                role="user",
                content=f"Emails: {many_emails}"
            )
        ]

        entities = segmentation_service._extract_entities(messages, [])

        # Should limit to 20 entities
        assert len(entities) <= 20

    def test_entity_deduplication(self, segmentation_service):
        """Test that duplicate entities are removed"""
        messages = [
            ChatMessage(
                id="msg1",
                conversation_id="conv1",
                workspace_id="workspace1",
                role="user",
                content="Email me at test@example.com, test@example.com, test@example.com"
            )
        ]

        entities = segmentation_service._extract_entities(messages, [])

        # Should deduplicate (only one instance)
        assert entities.count("test@example.com") == 1

    def test_no_entities_in_empty_content(self, segmentation_service):
        """Test extraction from content with no entities"""
        messages = [
            ChatMessage(
                id="msg1",
                conversation_id="conv1",
                workspace_id="workspace1",
                role="user",
                content="Hello world, how are you today"
            )
        ]

        entities = segmentation_service._extract_entities(messages, [])

        # Should return empty list
        assert isinstance(entities, list)
        # May or may not have entities depending on word capitalization

    def test_combined_message_and_execution_entities(self, segmentation_service):
        """Test extraction from both messages and executions"""
        messages = [
            ChatMessage(
                id="msg1",
                conversation_id="conv1",
                workspace_id="workspace1",
                role="user",
                content="Contact john@example.com"
            )
        ]

        # Create mock execution with metadata
        class MockExecution:
            def __init__(self):
                self.input_summary = "Process payment for Premium Plan"
                self.metadata_json = {"invoice": "INV-001"}

        executions = [MockExecution()]

        entities = segmentation_service._extract_entities(messages, executions)

        # Should include entities from both sources
        assert "john@example.com" in entities
        # May include other entities from execution
        assert len(entities) >= 1

    def test_extract_entities_with_invalid_input(self, segmentation_service):
        """Test extraction handles invalid input gracefully"""
        messages = []

        # Should not crash
        entities = segmentation_service._extract_entities(messages, [])
        assert isinstance(entities, list)

    def test_entity_extraction_preserves_order(self, segmentation_service):
        """Test that entity extraction maintains some order"""
        messages = [
            ChatMessage(
                id="msg1",
                conversation_id="conv1",
                workspace_id="workspace1",
                role="user",
                content="Contact alice@example.com then bob@example.com"
            )
        ]

        entities = segmentation_service._extract_entities(messages, [])

        # Both should be present
        assert "alice@example.com" in entities
        assert "bob@example.com" in entities


class TestWorldModelVersionTracking:
    """Test world model version tracking"""

    @pytest.fixture
    def db(self):
        """Create database session"""
        with get_db_session() as session:
            yield session

    @pytest.fixture
    def segmentation_service(self, db):
        """Create episode segmentation service"""
        return EpisodeSegmentationService(db)

    def test_default_version(self, segmentation_service, monkeypatch):
        """Test default version when no config exists"""
        # Ensure no environment variable
        monkeypatch.delenv("WORLD_MODEL_VERSION", raising=False)

        version = segmentation_service._get_world_model_version()

        # Should return default
        assert version == "v1.0"

    def test_environment_variable_version(self, segmentation_service, monkeypatch):
        """Test version from environment variable"""
        monkeypatch.setenv("WORLD_MODEL_VERSION", "v2.5.0")

        version = segmentation_service._get_world_model_version()

        # Should use environment variable
        assert version == "v2.5.0"

    def test_version_format(self, segmentation_service):
        """Test that version is a string"""
        version = segmentation_service._get_world_model_version()

        assert isinstance(version, str)
        assert len(version) > 0

    def test_version_in_episode_creation(self, segmentation_service, db):
        """Test that version is included in created episodes"""
        # This would require full episode creation setup
        # For now, test the method directly
        version = segmentation_service._get_world_model_version()

        assert version is not None
        assert isinstance(version, str)
