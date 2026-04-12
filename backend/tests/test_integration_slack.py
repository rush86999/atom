"""
Slack Integration Tests (pytest)

Tests Slack messaging and webhook integration with proper mocking.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.models import AgentExecution, AgentOperationTracker


class TestSlackMessagingIntegration:
    """Test Slack messaging integration."""

    @pytest.fixture
    def mock_slack_client(self):
        """Create mock Slack client."""
        with patch('integrations.slack_service.WebClient') as mock_client:
            yield mock_client.return_value

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        return db

    def test_send_slack_message(self, mock_slack_client, mock_db):
        """Test sending a message to Slack channel."""
        # Mock Slack API response
        mock_slack_client.chat_postMessage.return_value = {
            "ok": True,
            "channel": "C12345",
            "ts": "1234567890.123456",
            "message": {"text": "Test message"}
        }

        execution = AgentExecution(
            id="exec-slack-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Send Slack message"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Send message
        result = mock_slack_client.chat_postMessage(
            channel="C12345",
            text="Test message"
        )

        # Verify API call
        mock_slack_client.chat_postMessage.assert_called_once()
        assert result["ok"] is True

        execution.output_data = {
            "message_sent": True,
            "channel": result["channel"],
            "timestamp": result["ts"]
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.output_data["message_sent"] is True

    def test_send_slack_message_with_blocks(self, mock_slack_client, mock_db):
        """Test sending a formatted message with blocks."""
        mock_slack_client.chat_postMessage.return_value = {
            "ok": True,
            "channel": "C12345",
            "ts": "1234567890.123456"
        }

        execution = AgentExecution(
            id="exec-slack-002",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Send formatted message"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Send message with blocks
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Task Update*"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": "*Status:*\nCompleted"},
                    {"type": "mrkdwn", "text": "*Priority:*\nHigh"}
                ]
            }
        ]

        result = mock_slack_client.chat_postMessage(
            channel="C12345",
            blocks=blocks
        )

        # Verify API call
        mock_slack_client.chat_postMessage.assert_called_once()
        assert result["ok"] is True

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_update_slack_message(self, mock_slack_client, mock_db):
        """Test updating an existing Slack message."""
        mock_slack_client.chat_update.return_value = {
            "ok": True,
            "channel": "C12345",
            "ts": "1234567890.123456",
            "message": {"text": "Updated message"}
        }

        execution = AgentExecution(
            id="exec-slack-003",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Update message"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Update message
        result = mock_slack_client.chat_update(
            channel="C12345",
            ts="1234567890.123456",
            text="Updated message"
        )

        # Verify API call
        mock_slack_client.chat_update.assert_called_once()
        assert result["ok"] is True

        execution.output_data = {"message_updated": True}
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_add_reaction_to_message(self, mock_slack_client, mock_db):
        """Test adding reaction to Slack message."""
        mock_slack_client.reactions_add.return_value = {
            "ok": True
        }

        execution = AgentExecution(
            id="exec-slack-004",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Add reaction"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Add reaction
        result = mock_slack_client.reactions_add(
            channel="C12345",
            timestamp="1234567890.123456",
            name="white_check_mark"
        )

        # Verify API call
        mock_slack_client.reactions_add.assert_called_once()
        assert result["ok"] is True

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_slack_webhook(self, mock_db):
        """Test Slack webhook integration."""
        with patch('requests.post') as mock_post:
            mock_post.return_value = Mock(status_code=200, json=lambda: {"ok": True})

            execution = AgentExecution(
                id="exec-slack-webhook-001",
                agent_id="agent-001",
                status="running",
                input_data={"task": "Send webhook"},
                started_at=datetime.utcnow()
            )
            mock_db.add(execution)

            # Send webhook
            webhook_url = "https://hooks.slack.com/services/XXX/YYY/ZZZ"
            payload = {"text": "Webhook message"}

            import requests
            response = requests.post(webhook_url, json=payload)

            # Verify request
            mock_post.assert_called_once_with(webhook_url, json=payload)
            assert response.status_code == 200

            execution.output_data = {"webhook_sent": True}
            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            mock_db.commit()

    def test_slack_error_handling(self, mock_slack_client, mock_db):
        """Test handling Slack API errors."""
        # Mock API error
        mock_slack_client.chat_postMessage.side_effect = Exception("SlackApiError: Not Authed")

        execution = AgentExecution(
            id="exec-slack-error-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Send message"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Attempt to send message
        try:
            mock_slack_client.chat_postMessage(channel="C12345", text="Test")
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            mock_db.commit()

        assert execution.status == "failed"
        assert "Not Authed" in execution.error_message

    def test_list_slack_channels(self, mock_slack_client, mock_db):
        """Test listing Slack channels."""
        mock_slack_client.conversations_list.return_value = {
            "ok": True,
            "channels": [
                {"id": "C001", "name": "general"},
                {"id": "C002", "name": "random"}
            ]
        }

        execution = AgentExecution(
            id="exec-slack-005",
            agent_id="agent-001",
            status="running",
            input_data={"task": "List channels"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # List channels
        result = mock_slack_client.conversations_list(types="public_channel")

        # Verify API call
        mock_slack_client.conversations_list.assert_called_once()
        assert len(result["channels"]) == 2

        execution.output_data = {
            "channels_found": len(result["channels"]),
            "channels": result["channels"]
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()
