"""
Tests for Slack and Asana endpoint additions.

Tests the new Slack add_reaction and Asana create_project endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import services
try:
    from integrations.slack_service_unified import SlackUnifiedService
    from integrations.asana_service import AsanaService
except ImportError:
    from backend.integrations.slack_service_unified import SlackUnifiedService
    from backend.integrations.asana_service import AsanaService


class TestSlackAddReaction:
    """Test suite for Slack add_reaction endpoint"""

    @pytest.mark.asyncio
    async def test_add_reaction_success(self):
        """Test successful reaction addition"""
        # Arrange
        slack_service = SlackUnifiedService()

        # Mock the make_request method
        slack_service.make_request = AsyncMock(
            return_value={"ok": True}
        )

        # Act
        result = await slack_service.add_reaction(
            token="xoxb-test-token",
            channel_id="C1234567890",
            timestamp="1234567890.123456",
            reaction="thumbsup"
        )

        # Assert
        assert result["ok"] is True
        slack_service.make_request.assert_called_once()

        # Verify the call parameters
        call_args = slack_service.make_request.call_args
        assert call_args[0][0] == "POST"  # method
        assert call_args[0][1] == "reactions.add"  # endpoint
        assert call_args[1]["data"]["channel"] == "C1234567890"
        assert call_args[1]["data"]["timestamp"] == "1234567890.123456"
        assert call_args[1]["data"]["name"] == "thumbsup"

    @pytest.mark.asyncio
    async def test_add_reaction_with_colons(self):
        """Test reaction with colon syntax (:thumbsup:)"""
        # Arrange
        slack_service = SlackUnifiedService()
        slack_service.make_request = AsyncMock(return_value={"ok": True})

        # Act
        result = await slack_service.add_reaction(
            token="xoxb-test-token",
            channel_id="C1234567890",
            timestamp="1234567890.123456",
            reaction=":thumbsup:"
        )

        # Assert - colons should be stripped
        call_args = slack_service.make_request.call_args
        assert call_args[1]["data"]["name"] == "thumbsup"  # No colons
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_add_reaction_various_emojis(self):
        """Test adding various reaction types"""
        # Arrange
        slack_service = SlackUnifiedService()
        slack_service.make_request = AsyncMock(return_value={"ok": True})

        reactions = [
            "thumbsup",
            "white_check_mark",
            "eyes",
            "rocket",
            "celebrate"
        ]

        for reaction in reactions:
            # Act
            result = await slack_service.add_reaction(
                token="xoxb-test-token",
                channel_id="C1234567890",
                timestamp="1234567890.123456",
                reaction=reaction
            )

            # Assert
            assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_add_reaction_failure(self):
        """Test error handling when add_reaction fails"""
        # Arrange
        slack_service = SlackUnifiedService()
        slack_service.make_request = AsyncMock(
            side_effect=Exception("Invalid channel")
        )

        # Act & Assert
        from integrations.slack_service_unified import SlackServiceError

        with pytest.raises(SlackServiceError) as exc_info:
            await slack_service.add_reaction(
                token="xoxb-test-token",
                channel_id="invalid_channel",
                timestamp="1234567890.123456",
                reaction="thumbsup"
            )

        assert "Failed to add reaction" in str(exc_info.value)


class TestAsanaCreateProject:
    """Test suite for Asana create_project endpoint"""

    @pytest.mark.asyncio
    async def test_create_project_minimum_fields(self):
        """Test creating project with minimum required fields"""
        # Arrange
        asana_service = AsanaService()

        # Mock _make_request
        asana_service._make_request = MagicMock(
            return_value={
                "data": {
                    "gid": "123456789",
                    "name": "Test Project",
                    "created_at": "2026-02-05T00:00:00.000Z",
                    "modified_at": "2026-02-05T00:00:00.000Z",
                    "workspace": {"gid": "987654321"}
                }
            }
        )

        # Act
        result = await asana_service.create_project(
            access_token="test-token",
            workspace_gid="987654321",
            name="Test Project"
        )

        # Assert
        assert result["ok"] is True
        assert result["project"]["gid"] == "123456789"
        assert result["project"]["name"] == "Test Project"

        # Verify the call
        call_args = asana_service._make_request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/projects"
        assert call_args[1]["data"]["workspace"] == "987654321"
        assert call_args[1]["data"]["name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_create_project_with_notes(self):
        """Test creating project with description"""
        # Arrange
        asana_service = AsanaService()
        asana_service._make_request = MagicMock(
            return_value={
                "data": {
                    "gid": "123456789",
                    "name": "Marketing Campaign",
                    "notes": "Q1 marketing initiatives",
                    "created_at": "2026-02-05T00:00:00.000Z",
                    "workspace": {"gid": "987654321"}
                }
            }
        )

        # Act
        result = await asana_service.create_project(
            access_token="test-token",
            workspace_gid="987654321",
            name="Marketing Campaign",
            notes="Q1 marketing initiatives"
        )

        # Assert
        assert result["ok"] is True
        assert result["project"]["notes"] == "Q1 marketing initiatives"
        call_args = asana_service._make_request.call_args
        assert call_args[1]["data"]["notes"] == "Q1 marketing initiatives"

    @pytest.mark.asyncio
    async def test_create_project_with_team(self):
        """Test creating team project"""
        # Arrange
        asana_service = AsanaService()
        asana_service._make_request = MagicMock(
            return_value={
                "data": {
                    "gid": "123456789",
                    "name": "Team Project",
                    "created_at": "2026-02-05T00:00:00.000Z",
                    "workspace": {"gid": "987654321"},
                    "team": {"gid": "555555555"}
                }
            }
        )

        # Act
        result = await asana_service.create_project(
            access_token="test-token",
            workspace_gid="987654321",
            name="Team Project",
            team_gid="555555555"
        )

        # Assert
        assert result["ok"] is True
        assert result["project"]["team_gid"] == "555555555"

    @pytest.mark.asyncio
    async def test_create_project_with_color(self):
        """Test creating project with color"""
        # Arrange
        asana_service = AsanaService()
        asana_service._make_request = MagicMock(
            return_value={
                "data": {
                    "gid": "123456789",
                    "name": "Colored Project",
                    "color": "light-green",
                    "created_at": "2026-02-05T00:00:00.000Z",
                    "workspace": {"gid": "987654321"}
                }
            }
        )

        # Act
        result = await asana_service.create_project(
            access_token="test-token",
            workspace_gid="987654321",
            name="Colored Project",
            color="light-green"
        )

        # Assert
        assert result["ok"] is True
        assert result["project"]["color"] == "light-green"

    @pytest.mark.asyncio
    async def test_create_project_with_additional_fields(self):
        """Test creating project with additional kwargs"""
        # Arrange
        asana_service = AsanaService()
        asana_service._make_request = MagicMock(
            return_value={
                "data": {
                    "gid": "123456789",
                    "name": "Complex Project",
                    "created_at": "2026-02-05T00:00:00.000Z",
                    "workspace": {"gid": "987654321"}
                }
            }
        )

        # Act
        result = await asana_service.create_project(
            access_token="test-token",
            workspace_gid="987654321",
            name="Complex Project",
            due_on="2026-12-31",
            public=True,
            avatar="https://example.com/avatar.png"
        )

        # Assert
        assert result["ok"] is True
        call_args = asana_service._make_request.call_args
        assert call_args[1]["data"]["due_on"] == "2026-12-31"
        assert call_args[1]["data"]["public"] is True
        assert call_args[1]["data"]["avatar"] == "https://example.com/avatar.png"

    @pytest.mark.asyncio
    async def test_create_project_failure(self):
        """Test error handling when create_project fails"""
        # Arrange
        asana_service = AsanaService()
        asana_service._make_request = MagicMock(
            side_effect=Exception("Invalid workspace")
        )

        # Act
        result = await asana_service.create_project(
            access_token="test-token",
            workspace_gid="invalid",
            name="Test Project"
        )

        # Assert
        assert result["ok"] is False
        assert "error" in result


class TestIntegrationScenarios:
    """Integration tests for Slack and Asana endpoints"""

    @pytest.mark.asyncio
    async def test_slack_react_then_asana_create_project(self):
        """Test workflow: React to Slack message, then create Asana project"""
        # Arrange
        slack_service = SlackUnifiedService()
        asana_service = AsanaService()

        slack_service.make_request = AsyncMock(return_value={"ok": True})
        asana_service._make_request = MagicMock(
            return_value={
                "data": {
                    "gid": "123456789",
                    "name": "New Project",
                    "created_at": "2026-02-05T00:00:00.000Z",
                    "workspace": {"gid": "987654321"}
                }
            }
        )

        # Act - React to Slack message
        slack_result = await slack_service.add_reaction(
            token="xoxb-test",
            channel_id="C123",
            timestamp="1234567890.123456",
            reaction="white_check_mark"
        )

        # Create Asana project
        asana_result = await asana_service.create_project(
            access_token="test-token",
            workspace_gid="987654321",
            name="New Project",
            notes="Created after Slack approval"
        )

        # Assert
        assert slack_result["ok"] is True
        assert asana_result["ok"] is True
        assert asana_result["project"]["name"] == "New Project"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
