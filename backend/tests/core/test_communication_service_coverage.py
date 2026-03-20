"""
Comprehensive tests for CommunicationService

Target: 60%+ coverage for core/communication_service.py (145 lines)
Focus: Message handling, adapter management, slash commands, voice processing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.communication_service import CommunicationService, communication_service
from core.models import User, UserIdentity, AgentExecution


# ========================================================================
# Fixtures
# ========================================================================


@pytest.fixture
def mock_user(db_session):
    """Create a mock user for testing."""
    user = User(
        id="test-user-123",
        email="test@example.com",
        full_name="Test User",
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_user_identity(db_session, mock_user):
    """Create a mock user identity for testing."""
    identity = UserIdentity(
        id="test-identity-123",
        user_id=mock_user.id,
        provider="slack",
        provider_user_id="U123456",
        raw_data={"team": "T12345"}
    )
    db_session.add(identity)
    db_session.commit()
    db_session.refresh(identity)
    return identity


@pytest.fixture
def communication_svc():
    """Get CommunicationService instance."""
    return CommunicationService()


@pytest.fixture
def mock_background_tasks():
    """Mock FastAPI BackgroundTasks."""
    tasks = MagicMock()
    tasks.add_task = MagicMock()
    return tasks


# ========================================================================
# TestCommunicationService: Service Initialization and Configuration
# ========================================================================


class TestCommunicationService:
    """Test communication service initialization and configuration."""

    def test_service_initialization(self, communication_svc):
        """Test service initializes with all adapters registered."""
        assert "slack" in communication_svc._adapters
        assert "discord" in communication_svc._adapters
        assert "whatsapp" in communication_svc._adapters
        assert "telegram" in communication_svc._adapters
        assert "email" in communication_svc._adapters
        assert "sms" in communication_svc._adapters
        assert "generic" in communication_svc._adapters

    def test_register_adapter(self, communication_svc):
        """Test registering a new adapter."""
        mock_adapter = MagicMock()
        communication_svc.register_adapter("test_adapter", mock_adapter)
        assert "test_adapter" in communication_svc._adapters
        assert communication_svc._adapters["test_adapter"] == mock_adapter

    def test_get_adapter_existing(self, communication_svc):
        """Test getting an existing adapter."""
        adapter = communication_svc.get_adapter("slack")
        assert adapter is not None
        assert adapter.__class__.__name__ == "SlackAdapter"

    def test_get_adapter_fallback_to_generic(self, communication_svc):
        """Test getting non-existent adapter falls back to generic."""
        adapter = communication_svc.get_adapter("nonexistent")
        assert adapter is not None
        assert adapter.__class__.__name__ == "GenericAdapter"

    def test_singleton_instance(self):
        """Test communication_service is a singleton."""
        from core.communication_service import communication_service as svc1
        from core.communication_service import communication_service as svc2
        assert svc1 is svc2


# ========================================================================
# TestMessageDelivery: Message Creation and Delivery
# ========================================================================


class TestMessageDelivery:
    """Test message creation, validation, and delivery."""

    @pytest.mark.asyncio
    async def test_handle_incoming_message_success(self, communication_svc, mock_user_identity, mock_background_tasks):
        """Test successful message handling with valid payload."""
        payload = {
            "sender_id": "U123456",
            "content": "Hello Atom",
            "channel_id": "C123456",
            "metadata": {}
        }

        with patch('core.communication_service.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user_identity
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            result = await communication_svc.handle_incoming_message(
                source="slack",
                payload=payload,
                background_tasks=mock_background_tasks
            )

            assert result["status"] in ["processing", "command_executed"]
            assert "message" in result

    @pytest.mark.asyncio
    async def test_handle_incoming_message_empty_content(self, communication_svc, mock_background_tasks):
        """Test message with empty content is ignored."""
        payload = {
            "sender_id": "U123456",
            "content": "",
            "channel_id": "C123456"
        }

        result = await communication_svc.handle_incoming_message(
            source="slack",
            payload=payload,
            background_tasks=mock_background_tasks
        )

        assert result["status"] == "ignored"
        assert result["reason"] == "empty_content"

    @pytest.mark.asyncio
    async def test_handle_incoming_message_no_identity(self, communication_svc, mock_background_tasks):
        """Test message from unknown identity is rejected."""
        payload = {
            "sender_id": "UNKNOWN_USER",
            "content": "Hello",
            "channel_id": "C123456"
        }

        with patch('core.communication_service.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            result = await communication_svc.handle_incoming_message(
                source="slack",
                payload=payload,
                background_tasks=mock_background_tasks
            )

            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_send_message_success(self, communication_svc):
        """Test sending message successfully."""
        with patch.object(communication_svc, 'get_adapter') as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_adapter.send_message.return_value = True
            mock_get_adapter.return_value = mock_adapter

            with patch('core.communication_service.notification_manager') as mock_notify:
                mock_notify.broadcast = AsyncMock()

                await communication_svc.send_message(
                    target_source="slack",
                    target_id="C123456",
                    message="Test message",
                    workspace_id="default"
                )

                mock_adapter.send_message.assert_called_once()
                mock_notify.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_failure(self, communication_svc):
        """Test handling send message failure."""
        with patch.object(communication_svc, 'get_adapter') as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_adapter.send_message.return_value = False
            mock_get_adapter.return_value = mock_adapter

            with patch('core.communication_service.notification_manager') as mock_notify:
                mock_notify.broadcast = AsyncMock()

                # Should not raise exception, just log error
                await communication_svc.send_message(
                    target_source="slack",
                    target_id="C123456",
                    message="Test message",
                    workspace_id="default"
                )

    @pytest.mark.asyncio
    async def test_background_task_scheduled(self, communication_svc, mock_user_identity, mock_background_tasks):
        """Test that agent processing is scheduled as background task."""
        payload = {
            "sender_id": "U123456",
            "content": "Tell me about the weather",
            "channel_id": "C123456"
        }

        with patch('core.communication_service.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_identity = mock_user_identity
            mock_identity.user = mock_user_identity.user
            mock_db.query.return_value.filter.return_value.first.return_value = mock_identity
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            await communication_svc.handle_incoming_message(
                source="slack",
                payload=payload,
                background_tasks=mock_background_tasks
            )

            # Verify background task was added
            assert mock_background_tasks.add_task.called


# ========================================================================
# TestNotificationChannels: Slash Commands and Special Handlers
# ========================================================================


class TestNotificationChannels:
    """Test slash commands, channel selection, and special handlers."""

    @pytest.mark.asyncio
    async def test_slash_command_agents_list(self, communication_svc, mock_user, mock_background_tasks):
        """Test /agents command lists available agents."""
        with patch('core.communication_service.SpecialtyAgentTemplate') as mock_templates:
            mock_templates.TEMPLATES = {
                "finance": {"name": "Finance Agent", "description": "Handles finance tasks"}
            }

            with patch.object(communication_svc, 'send_message', new_callable=AsyncMock) as mock_send:
                result = await communication_svc._handle_slash_commands(
                    command="/agents",
                    user=mock_user,
                    workspace_id="default",
                    source="slack",
                    channel_id="C123456",
                    background_tasks=mock_background_tasks
                )

                assert result is True
                mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_slash_command_workflow_trigger(self, communication_svc, mock_user, mock_background_tasks):
        """Test /workflow command triggers workflow."""
        with patch.object(communication_svc, 'send_message', new_callable=AsyncMock) as mock_send:
            result = await communication_svc._handle_slash_commands(
                command="/workflow wf-123",
                user=mock_user,
                workspace_id="default",
                source="slack",
                channel_id="C123456",
                background_tasks=mock_background_tasks
            )

            assert result is True
            # Verify both send_message and background task scheduled
            mock_send.assert_called_once()
            assert mock_background_tasks.add_task.called

    @pytest.mark.asyncio
    async def test_slash_command_run(self, communication_svc, mock_user, mock_background_tasks):
        """Test /run command executes agent."""
        result = await communication_svc._handle_slash_commands(
            command="/run summarize the report",
            user=mock_user,
            workspace_id="default",
            source="slack",
            channel_id="C123456",
            background_tasks=mock_background_tasks
        )

        assert result is True
        assert mock_background_tasks.add_task.called

    @pytest.mark.asyncio
    async def test_unknown_command_not_handled(self, communication_svc, mock_user, mock_background_tasks):
        """Test unknown command returns False."""
        result = await communication_svc._handle_slash_commands(
            command="/unknown command",
            user=mock_user,
            workspace_id="default",
            source="slack",
            channel_id="C123456",
            background_tasks=mock_background_tasks
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_slash_command_without_args(self, communication_svc, mock_user, mock_background_tasks):
        """Test slash commands missing arguments."""
        # /workflow without args
        result = await communication_svc._handle_slash_commands(
            command="/workflow",
            user=mock_user,
            workspace_id="default",
            source="slack",
            channel_id="C123456",
            background_tasks=mock_background_tasks
        )
        assert result is False


# ========================================================================
# TestVoiceProcessing: Voice Message Handling
# ========================================================================


class TestVoiceProcessing:
    """Test voice message transcription and processing."""

    @pytest.mark.asyncio
    async def test_voice_transcription_success(self, communication_svc, mock_user):
        """Test successful voice transcription."""
        metadata = {
            "media_id": "audio-123",
            "media_type": "audio"
        }

        with patch('core.communication_service.get_voice_service') as mock_get_voice:
            mock_voice_svc = AsyncMock()
            mock_transcription = MagicMock()
            mock_transcription.text = "Transcribed text"
            mock_voice_svc.transcribe_audio.return_value = mock_transcription
            mock_get_voice.return_value = mock_voice_svc

            with patch.object(communication_svc, 'get_adapter') as mock_get_adapter:
                mock_adapter = AsyncMock()
                mock_adapter.get_media.return_value = b"fake_audio_bytes"
                mock_get_adapter.return_value = mock_adapter

                with patch('core.communication_service.handle_manual_trigger', new_callable=AsyncMock) as mock_trigger:
                    mock_trigger.return_value = {"final_output": "Response"}

                    with patch.object(communication_svc, 'send_message', new_callable=AsyncMock):
                        await communication_svc._process_and_reply(
                            user=mock_user,
                            workspace_id="default",
                            request="Original text",
                            source="telegram",
                            channel_id="C123456",
                            metadata=metadata
                        )

                        mock_voice_svc.transcribe_audio.assert_called_once()

    @pytest.mark.asyncio
    async def test_voice_transcription_fallback(self, communication_svc, mock_user):
        """Test fallback to text when voice transcription fails."""
        metadata = {
            "media_id": "audio-123",
            "media_type": "audio"
        }

        with patch.object(communication_svc, 'get_adapter') as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_adapter.get_media.side_effect = Exception("Transcription failed")
            mock_get_adapter.return_value = mock_adapter

            with patch('core.communication_service.handle_manual_trigger', new_callable=AsyncMock) as mock_trigger:
                # Should use original text
                mock_trigger.return_value = {"final_output": "Response"}

                with patch.object(communication_svc, 'send_message', new_callable=AsyncMock):
                    await communication_svc._process_and_reply(
                        user=mock_user,
                        workspace_id="default",
                        request="Original text",
                        source="telegram",
                        channel_id="C123456",
                        metadata=metadata
                    )

            # Verify original request was used
            call_args = mock_trigger.call_args
            assert call_args[1]['request'] == "Original text"

    @pytest.mark.asyncio
    async def test_no_media_metadata(self, communication_svc, mock_user):
        """Test processing without media metadata."""
        with patch('core.communication_service.handle_manual_trigger', new_callable=AsyncMock) as mock_trigger:
            mock_trigger.return_value = {"final_output": "Response"}

            with patch.object(communication_svc, 'send_message', new_callable=AsyncMock):
                await communication_svc._process_and_reply(
                    user=mock_user,
                    workspace_id="default",
                    request="Text message",
                    source="slack",
                    channel_id="C123456",
                    metadata=None
                )

                # Should use text directly
                call_args = mock_trigger.call_args
                assert call_args[1]['request'] == "Text message"


# ========================================================================
# TestCommunicationErrors: Error Handling
# ========================================================================


class TestCommunicationErrors:
    """Test error handling in communication service."""

    @pytest.mark.asyncio
    async def test_process_and_reply_exception_handling(self, communication_svc, mock_user):
        """Test exception handling in _process_and_reply."""
        with patch('core.communication_service.handle_manual_trigger', new_callable=AsyncMock) as mock_trigger:
            mock_trigger.side_effect = Exception("Processing failed")

            with patch.object(communication_svc, 'send_message', new_callable=AsyncMock) as mock_send:
                await communication_svc._process_and_reply(
                    user=mock_user,
                    workspace_id="default",
                    request="Test",
                    source="slack",
                    channel_id="C123456"
                )

                # Should send error message
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                assert "error" in call_args[1]['message'].lower()

    @pytest.mark.asyncio
    async def test_response_extraction_fallbacks(self, communication_svc, mock_user):
        """Test various response format extractions."""
        test_cases = [
            {"final_output": "Direct output"},
            {"response": "Response field"},
            {"output": "Output field"},
            {"actions_executed": [{"thought": "Action 1"}]},
            "Plain string response"
        ]

        with patch('core.communication_service.handle_manual_trigger', new_callable=AsyncMock) as mock_trigger:
            with patch.object(communication_svc, 'send_message', new_callable=AsyncMock):
                for response in test_cases:
                    mock_trigger.reset_mock()
                    mock_trigger.return_value = response

                    await communication_svc._process_and_reply(
                        user=mock_user,
                        workspace_id="default",
                        request="Test",
                        source="slack",
                        channel_id="C123456"
                    )

                    # Should not raise exception
                    assert communication_svc.send_message.called

    @pytest.mark.asyncio
    async def test_database_error_handling(self, communication_svc, mock_background_tasks):
        """Test handling of database errors during user resolution."""
        payload = {
            "sender_id": "U123456",
            "content": "Hello",
            "channel_id": "C123456"
        }

        with patch('core.communication_service.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.side_effect = Exception("Database connection failed")
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            result = await communication_svc.handle_incoming_message(
                source="slack",
                payload=payload,
                background_tasks=mock_background_tasks
            )

            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_workspace_resolution(self, communication_svc, mock_user_identity):
        """Test workspace resolution from user."""
        payload = {
            "sender_id": "U123456",
            "content": "Hello",
            "channel_id": "C123456"
        }

        with patch('core.communication_service.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_identity = mock_user_identity
            # Mock user with workspaces
            mock_user = MagicMock()
            mock_user.workspaces = [MagicMock(id="workspace-123")]
            mock_identity.user = mock_user
            mock_db.query.return_value.filter.return_value.first.return_value = mock_identity
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            mock_background_tasks = MagicMock()
            mock_background_tasks.add_task = MagicMock()

            await communication_svc.handle_incoming_message(
                source="slack",
                payload=payload,
                background_tasks=mock_background_tasks
            )

            # Should use first workspace
            assert mock_background_tasks.add_task.called
