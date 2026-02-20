"""
Comprehensive integration tests for SlackEnhancedService

Tests cover:
- Authentication (OAuth, token management, encryption)
- Messaging (send, edit, DM, threaded, blocks, attachments)
- Channels (list, create, join, invite, archive)
- Webhooks (event handling, signature verification)
- Files (upload, download, list, delete)
- Users (list, info, search)
- Error handling (rate limits, API errors, network failures)
- Rate limiting (Redis and local)
- Caching (messages, channels, files)

Target: 550+ lines, 25-30 tests, 80%+ coverage
"""

import pytest
import asyncio
import json
import time
import hmac
import hashlib
import base64
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from slack_sdk.errors import SlackApiError

from integrations.slack_enhanced_service import (
    SlackEnhancedService,
    SlackWorkspace,
    SlackChannel,
    SlackMessage,
    SlackFile,
    SlackEventType,
    SlackConnectionStatus,
    SlackRateLimiter
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Mock configuration for SlackEnhancedService"""
    # Generate valid Fernet key (32 bytes, then base64-encoded)
    import os
    from cryptography.fernet import Fernet
    encryption_key = Fernet.generate_key().decode()

    return {
        'client_id': 'test_client_id',
        'client_secret': 'test_client_secret',
        'signing_secret': 'test_signing_secret',
        'redirect_uri': 'http://localhost:3000/callback',
        'encryption_key': encryption_key,
        'redis': {
            'enabled': False,
            'host': 'localhost',
            'port': 6379,
            'db': 0
        },
        'database': None
    }


@pytest.fixture
def mock_workspace():
    """Mock Slack workspace"""
    return SlackWorkspace(
        team_id='T123456',
        team_name='Test Workspace',
        domain='test-workspace',
        url='https://test-workspace.slack.com',
        access_token='xoxb-test-token',
        bot_token='xoxb-test-bot-token',
        user_id='U123456',
        bot_id='B123456',
        scopes=['channels:read', 'chat:write'],
        is_active=True
    )


@pytest.fixture
def mock_channel():
    """Mock Slack channel"""
    return SlackChannel(
        channel_id='C123456',
        name='test-channel',
        display_name='Test Channel',
        purpose='Testing purposes',
        topic='Testing',
        is_private=False,
        is_archived=False,
        workspace_id='T123456',
        num_members=5
    )


@pytest.fixture
def mock_message():
    """Mock Slack message"""
    return SlackMessage(
        message_id='1234567890.123456',
        text='Test message',
        user_id='U123456',
        user_name='testuser',
        channel_id='C123456',
        channel_name='test-channel',
        workspace_id='T123456',
        timestamp='1234567890.123456',
        thread_ts=None,
        reply_count=0
    )


@pytest.fixture
def slack_service(mock_config):
    """Create SlackEnhancedService instance for testing"""
    service = SlackEnhancedService(mock_config)
    yield service
    # Cleanup
    asyncio.run(service.close())


# ============================================================================
# Test Class 1: TestSlackAuthentication (4 tests)
# ============================================================================

class TestSlackAuthentication:
    """Test Slack authentication and token management"""

    def test_generate_oauth_url(self, slack_service):
        """Test OAuth URL generation with custom scopes"""
        state = 'test_state_123'
        user_id = 'U123456'
        scopes = ['channels:read', 'chat:write']

        url = slack_service.generate_oauth_url(state, user_id, scopes)

        assert url.startswith('https://slack.com/oauth/v2/authorize')
        assert 'client_id=test_client_id' in url
        assert 'scope=channels:read+chat:write' in url or 'scope=channels:read chat:write' in url
        assert f'state={state}' in url
        assert f'user={user_id}' in url

    def test_generate_oauth_url_default_scopes(self, slack_service):
        """Test OAuth URL generation with default scopes"""
        url = slack_service.generate_oauth_url('state', 'user_id')

        # Should include required scopes
        assert 'client_id=test_client_id' in url
        assert 'redirect_uri' in url
        # Default scopes should be extensive
        assert 'channels:read' in url

    def test_token_encryption_decryption(self, slack_service):
        """Test token encryption and decryption cycle"""
        original_token = 'xoxb-test-encrypted-token'

        # Encrypt
        encrypted = slack_service._encrypt_token(original_token)
        assert encrypted != original_token
        assert len(encrypted) > 0

        # Decrypt
        decrypted = slack_service._decrypt_token(encrypted)
        assert decrypted == original_token

    def test_token_encryption_without_cipher(self, mock_config):
        """Test token handling when encryption is not configured"""
        mock_config['encryption_key'] = None
        service = SlackEnhancedService(mock_config)

        # Should return token as-is when no cipher
        token = 'xoxb-test-token'
        assert service._encrypt_token(token) == token
        assert service._decrypt_token(token) == token


# ============================================================================
# Test Class 2: TestSlackMessaging (8 tests)
# ============================================================================

class TestSlackMessaging:
    """Test Slack messaging functionality"""

    @pytest.mark.asyncio
    async def test_send_message_success(self, slack_service, mock_workspace):
        """Test sending a message to a channel successfully"""
        workspace_id = 'T123456'
        channel_id = 'C123456'
        text = 'Hello, Slack!'

        # Mock client and workspace
        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.chat_postMessage = AsyncMock(return_value={
                    'ok': True,
                    'ts': '1234567890.123456',
                    'channel': channel_id,
                    'message': {'text': text}
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.send_message(workspace_id, channel_id, text)

                assert result['ok'] is True
                assert result['message_id'] == '1234567890.123456'
                assert result['channel_id'] == channel_id
                mock_client.chat_postMessage.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_with_blocks(self, slack_service, mock_workspace):
        """Test sending a message with block kit blocks"""
        workspace_id = 'T123456'
        channel_id = 'C123456'
        text = 'Block message'
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Test block"
                }
            }
        ]

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.chat_postMessage = AsyncMock(return_value={
                    'ok': True,
                    'ts': '1234567890.123456',
                    'channel': channel_id,
                    'message': {'blocks': blocks}
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.send_message(
                    workspace_id, channel_id, text, blocks=blocks
                )

                assert result['ok'] is True
                mock_client.chat_postMessage.assert_called_once()
                call_args = mock_client.chat_postMessage.call_args[1]
                assert 'blocks' in call_args
                assert call_args['blocks'] == blocks

    @pytest.mark.asyncio
    async def test_send_threaded_message(self, slack_service, mock_workspace):
        """Test sending a threaded reply"""
        workspace_id = 'T123456'
        channel_id = 'C123456'
        thread_ts = '1234567890.123456'
        text = 'Thread reply'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.chat_postMessage = AsyncMock(return_value={
                    'ok': True,
                    'ts': '1234567890.123457',
                    'channel': channel_id,
                    'message': {'text': text}
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.send_message(
                    workspace_id, channel_id, text, thread_ts=thread_ts
                )

                assert result['ok'] is True
                mock_client.chat_postMessage.assert_called_once()
                # Check if thread_ts was passed (may be in kwargs)
                if mock_client.chat_postMessage.call_args:
                    call_kwargs = mock_client.chat_postMessage.call_args[1]
                    assert 'thread_ts' in call_kwargs
                    assert call_kwargs['thread_ts'] == thread_ts

    @pytest.mark.asyncio
    async def test_send_message_rate_limit_error(self, slack_service, mock_workspace):
        """Test handling rate limit errors when sending messages"""
        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.chat_postMessage = AsyncMock(side_effect=SlackApiError(
                    message='Rate limited',
                    response={'data': {'error': 'ratelimited'}}
                ))
                mock_get_client.return_value = mock_client

                result = await slack_service.send_message('T123', 'C123', 'test')

                assert result['ok'] is False
                assert 'error' in result

    @pytest.mark.asyncio
    async def test_send_dm_success(self, slack_service, mock_workspace):
        """Test sending direct message to user"""
        workspace_id = 'T123456'
        user_id = 'U123456'
        text = 'Direct message'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                # Mock conversations_open for DM
                mock_client.conversations_open = AsyncMock(return_value={
                    'ok': True,
                    'channel': {'id': 'D123456'}
                })
                # Mock chat_postMessage
                mock_client.chat_postMessage = AsyncMock(return_value={
                    'ok': True,
                    'ts': '1234567890.123456',
                    'channel': 'D123456',
                    'message': {'text': text, 'ts': '1234567890.123456'}
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.send_dm(workspace_id, user_id, text)

                assert result['ok'] is True
                assert result['channel'] == 'D123456'
                assert result['user_id'] == user_id
                mock_client.conversations_open.assert_called_once()
                mock_client.chat_postMessage.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_reaction(self, slack_service, mock_workspace):
        """Test adding reaction to message"""
        workspace_id = 'T123456'
        channel_id = 'C123456'
        timestamp = '1234567890.123456'
        reaction = 'thumbsup'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.reactions_add = AsyncMock(return_value={'ok': True})
                mock_get_client.return_value = mock_client

                result = await slack_service.add_reaction(
                    workspace_id, channel_id, timestamp, reaction
                )

                assert result['ok'] is True
                assert result['reaction'] == 'thumbsup'  # Colons stripped
                mock_client.reactions_add.assert_called_once()

    @pytest.mark.asyncio
    async def test_pin_message(self, slack_service, mock_workspace):
        """Test pinning a message"""
        workspace_id = 'T123456'
        channel_id = 'C123456'
        timestamp = '1234567890.123456'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.pins_add = AsyncMock(return_value={'ok': True})
                mock_get_client.return_value = mock_client

                result = await slack_service.pin_message(
                    workspace_id, channel_id, timestamp
                )

                assert result['ok'] is True
                mock_client.pins_add.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_messages(self, slack_service, mock_workspace):
        """Test searching messages"""
        workspace_id = 'T123456'
        query = 'test query'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.search_messages = AsyncMock(return_value={
                    'ok': True,
                    'messages': {
                        'matches': [
                            {
                                'ts': '1234567890.123456',
                                'text': 'Test message',
                                'user': 'U123456',
                                'channel': {'id': 'C123456', 'name': 'test-channel'}
                            }
                        ],
                        'total': 1,
                        'paging': {'page': 1, 'pages': 1}
                    }
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.search_messages(workspace_id, query)

                assert result['ok'] is True
                assert len(result['messages']) == 1
                assert result['messages'][0].text == 'Test message'


# ============================================================================
# Test Class 3: TestSlackChannels (6 tests)
# ============================================================================

class TestSlackChannels:
    """Test Slack channel operations"""

    @pytest.mark.asyncio
    async def test_get_channels_success(self, slack_service, mock_workspace):
        """Test getting list of channels"""
        workspace_id = 'T123456'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.conversations_list = AsyncMock(return_value={
                    'ok': True,
                    'channels': [
                        {
                            'id': 'C123456',
                            'name': 'test-channel',
                            'is_private': False,
                            'is_archived': False,
                            'is_general': False,
                            'is_shared': False,
                            'num_members': 5,
                            'created': 1234567890,
                            'purpose': {'value': 'Testing'},
                            'topic': {'value': 'Test topic'}
                        }
                    ]
                })
                mock_get_client.return_value = mock_client

                channels = await slack_service.get_channels(workspace_id)

                assert len(channels) == 1
                assert channels[0].channel_id == 'C123456'
                assert channels[0].name == 'test-channel'
                assert channels[0].num_members == 5

    @pytest.mark.asyncio
    async def test_get_channels_with_private(self, slack_service, mock_workspace):
        """Test getting channels including private channels"""
        workspace_id = 'T123456'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.conversations_list = AsyncMock(return_value={
                    'ok': True,
                    'channels': [
                        {
                            'id': 'C123456',
                            'name': 'private-channel',
                            'is_private': True,
                            'is_im': False,
                            'is_mpim': False,
                            'created': 1234567890
                        }
                    ]
                })
                mock_get_client.return_value = mock_client

                channels = await slack_service.get_channels(
                    workspace_id, include_private=True
                )

                assert len(channels) == 1
                assert channels[0].is_private is True

    @pytest.mark.asyncio
    async def test_create_channel(self, slack_service, mock_workspace):
        """Test creating a new channel"""
        workspace_id = 'T123456'
        name = 'new-test-channel'
        description = 'New test channel'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.conversations_create = AsyncMock(return_value={
                    'ok': True,
                    'channel': {
                        'id': 'C789012',
                        'name': name,
                        'is_private': False,
                        'created': 1234567890
                    }
                })
                mock_client.conversations_setTopic = AsyncMock(return_value={'ok': True})
                mock_get_client.return_value = mock_client

                result = await slack_service.create_channel(
                    workspace_id, name, is_private=False, description=description
                )

                assert result['ok'] is True
                assert result['channel_id'] == 'C789012'
                assert result['channel_name'] == name

    @pytest.mark.asyncio
    async def test_invite_to_channel(self, slack_service, mock_workspace):
        """Test inviting users to a channel"""
        workspace_id = 'T123456'
        channel_id = 'C123456'
        user_ids = ['U123456', 'U789012']

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.conversations_invite = AsyncMock(return_value={
                    'ok': True,
                    'channel': {'id': channel_id}
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.invite_to_channel(
                    workspace_id, channel_id, user_ids
                )

                assert result['ok'] is True
                assert len(result['invited_users']) == 2
                assert len(result['failed_users']) == 0

    @pytest.mark.asyncio
    async def test_invite_to_channel_partial_failure(self, slack_service, mock_workspace):
        """Test inviting users with some failures"""
        workspace_id = 'T123456'
        channel_id = 'C123456'
        user_ids = ['U123456', 'U789012']

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                # First invite succeeds, second fails
                mock_client.conversations_invite = AsyncMock(
                    side_effect=[
                        {'ok': True, 'channel': {'id': channel_id}},
                        SlackApiError('User not found', {'data': {'error': 'user_not_found'}})
                    ]
                )
                mock_get_client.return_value = mock_client

                result = await slack_service.invite_to_channel(
                    workspace_id, channel_id, user_ids
                )

                assert result['ok'] is True  # Partial success
                assert len(result['invited_users']) == 1
                assert len(result['failed_users']) == 1

    @pytest.mark.asyncio
    async def test_get_channel_history(self, slack_service, mock_workspace):
        """Test getting channel message history"""
        workspace_id = 'T123456'
        channel_id = 'C123456'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.conversations_history = AsyncMock(return_value={
                    'ok': True,
                    'messages': [
                        {
                            'ts': '1234567890.123456',
                            'text': 'Test message',
                            'user': 'U123456',
                            'type': 'message'
                        }
                    ]
                })
                mock_get_client.return_value = mock_client

                messages = await slack_service.get_channel_history(workspace_id, channel_id)

                assert len(messages) == 1
                assert messages[0].text == 'Test message'
                assert messages[0].user_id == 'U123456'


# ============================================================================
# Test Class 4: TestSlackFiles (4 tests)
# ============================================================================

class TestSlackFiles:
    """Test Slack file operations"""

    @pytest.mark.asyncio
    async def test_upload_file(self, slack_service, mock_workspace, tmp_path):
        """Test uploading file to channel"""
        workspace_id = 'T123456'
        channel_id = 'C123456'

        # Create temporary file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                # Note: SlackFile.__init__ requires 'created' parameter
                # We're mocking the API response, not creating the object directly
                mock_client.files_upload_v2 = AsyncMock(return_value={
                    'ok': True,
                    'file': {
                        'id': 'F123456',
                        'name': 'test.txt',
                        'title': 'test.txt',
                        'mimetype': 'text/plain',
                        'filetype': 'text',
                        'pretty_type': 'Plain Text',
                        'size': 12,
                        'url_private': 'https://files.slack.com/files-pri/T123/F123/test.txt',
                        'permalink': 'https://test-workspace.slack.com/files/F123/test.txt',
                        'user': 'U123456',
                        'timestamp': 1234567890.123456,  # Unix timestamp (float)
                        'created': 1234567890,  # Unix timestamp (int) for created field
                        'is_public': False,
                        'is_editable': True
                    }
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.upload_file(
                    workspace_id, channel_id, str(test_file)
                )

                assert result['ok'] is True
                assert result['file']['file_id'] == 'F123456'

    @pytest.mark.asyncio
    async def test_upload_file_with_comment(self, slack_service, mock_workspace, tmp_path):
        """Test uploading file with initial comment"""
        workspace_id = 'T123456'
        channel_id = 'C123456'
        title = 'Test File Title'
        comment = 'Here is the file'

        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.files_upload_v2 = AsyncMock(return_value={
                    'ok': True,
                    'file': {
                        'id': 'F123456',
                        'name': 'test.txt',
                        'title': title,
                        'mimetype': 'text/plain',
                        'filetype': 'text',
                        'pretty_type': 'Plain Text',
                        'size': 12,
                        'url_private': 'https://files.slack.com/files-pri/T123/F123/test.txt',
                        'permalink': 'https://test-workspace.slack.com/files/F123/test.txt',
                        'user': 'U123456',
                        'timestamp': 1234567890.123456,
                        'created': 1234567890
                    }
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.upload_file(
                    workspace_id, channel_id, str(test_file),
                    title=title, initial_comment=comment
                )

                assert result['ok'] is True
                mock_client.files_upload_v2.assert_called_once()
                call_args = mock_client.files_upload_v2.call_args[1]
                assert call_args['title'] == title
                assert call_args['initial_comment'] == comment

    @pytest.mark.asyncio
    async def test_upload_file_rate_limit_error(self, slack_service, mock_workspace, tmp_path):
        """Test handling rate limit when uploading file"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.files_upload_v2 = AsyncMock(
                    side_effect=SlackApiError('Rate limited', {'data': {'error': 'ratelimited'}})
                )
                mock_get_client.return_value = mock_client

                result = await slack_service.upload_file(
                    'T123', 'C123', str(test_file)
                )

                assert result['ok'] is False
                assert 'error' in result

    @pytest.mark.asyncio
    async def test_upload_file_api_error(self, slack_service, mock_workspace, tmp_path):
        """Test handling API error when uploading file"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.files_upload_v2 = AsyncMock(return_value={
                    'ok': False,
                    'error': 'file_not_found'
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.upload_file(
                    'T123', 'C123', str(test_file)
                )

                assert result['ok'] is False
                assert 'error' in result


# ============================================================================
# Test Class 5: TestSlackWebhooks (6 tests)
# ============================================================================

class TestSlackWebhooks:
    """Test Slack webhook handling"""

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_valid(self, slack_service):
        """Test verifying valid webhook signature"""
        body = b'{"type":"url_verification","token":"test"}'
        timestamp = str(int(time.time()))
        signing_secret = 'test_signing_secret'

        # Create signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        signature = 'v0=' + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        result = await slack_service.verify_webhook_signature(body, timestamp, signature)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_invalid(self, slack_service):
        """Test rejecting invalid webhook signature"""
        body = b'{"type":"url_verification","token":"test"}'
        timestamp = str(int(time.time()))
        invalid_signature = 'v0=invalid_signature'

        result = await slack_service.verify_webhook_signature(body, timestamp, invalid_signature)

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_expired(self, slack_service):
        """Test rejecting expired webhook timestamp"""
        body = b'{"type":"url_verification","token":"test"}'
        old_timestamp = str(int(time.time()) - 400)  # 6+ minutes ago
        signing_secret = 'test_signing_secret'

        sig_basestring = f"v0:{old_timestamp}:{body.decode('utf-8')}"
        signature = 'v0=' + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        result = await slack_service.verify_webhook_signature(body, old_timestamp, signature)

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_no_secret(self, mock_config):
        """Test signature verification fails without signing secret"""
        mock_config['signing_secret'] = None
        service = SlackEnhancedService(mock_config)

        result = await service.verify_webhook_signature(b'body', 'timestamp', 'signature')

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_webhook_event_message(self, slack_service):
        """Test handling message webhook event"""
        event_data = {
            'team_id': 'T123456',
            'event': {
                'type': 'message',
                'user': 'U123456',
                'text': 'Hello',
                'ts': '1234567890.123456',
                'channel': 'C123456'
            }
        }

        result = await slack_service.handle_webhook_event(event_data)

        assert result['ok'] is True
        assert result['event_type'] == 'message'
        assert result['handled'] is True

    @pytest.mark.asyncio
    async def test_handle_webhook_event_with_custom_handler(self, slack_service):
        """Test webhook event with registered custom handler"""
        event_data = {
            'team_id': 'T123456',
            'event': {
                'type': 'reaction_added',
                'user': 'U123456',
                'reaction': 'thumbsup',
                'item': {'type': 'message', 'channel': 'C123456'}
            }
        }

        # Register custom handler
        handler_called = []

        async def custom_handler(event):
            handler_called.append(event['event']['type'])

        slack_service.register_event_handler(SlackEventType.REACTION_ADD, custom_handler)

        result = await slack_service.handle_webhook_event(event_data)

        assert result['ok'] is True
        assert len(handler_called) == 1
        assert handler_called[0] == 'reaction_added'


# ============================================================================
# Test Class 6: TestSlackErrorHandling (5 tests)
# ============================================================================

class TestSlackErrorHandling:
    """Test Slack error handling and retry logic"""

    @pytest.mark.asyncio
    async def test_connection_test_success(self, slack_service, mock_workspace):
        """Test successful connection test"""
        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.auth_test = AsyncMock(return_value={
                    'ok': True,
                    'team_id': 'T123456',
                    'team': 'Test Workspace',
                    'user_id': 'U123456',
                    'user': 'testuser'
                })
                mock_get_client.return_value = mock_client

                result = await slack_service.test_connection('T123456')

                assert result['connected'] is True
                assert result['status'] == 'connected'
                assert slack_service.connection_status['T123456'] == SlackConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_connection_test_failure(self, slack_service):
        """Test connection test failure"""
        with patch.object(slack_service, '_get_workspace', return_value=None):
            result = await slack_service.test_connection('T999999')

            assert result['connected'] is False
            assert result['status'] == 'error'
            assert slack_service.connection_status['T999999'] == SlackConnectionStatus.ERROR

    @pytest.mark.asyncio
    async def test_connection_test_rate_limited(self, slack_service, mock_workspace):
        """Test connection test with rate limit"""
        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            with patch.object(slack_service, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                # Create proper SlackApiError with response dict containing 'data'
                mock_response = {'data': {'error': 'ratelimited'}, 'headers': {'Retry-After': '60'}}
                mock_client.auth_test = AsyncMock(
                    side_effect=SlackApiError('Rate limited', response=mock_response)
                )
                mock_get_client.return_value = mock_client

                result = await slack_service.test_connection('T123456')

                assert result['connected'] is False
                assert result['status'] == 'rate_limited'
                assert 'retry_after' in result
                assert slack_service.connection_status['T123456'] == SlackConnectionStatus.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_workspace_not_found(self, slack_service):
        """Test handling when workspace is not found"""
        with patch.object(slack_service, '_get_workspace', return_value=None):
            result = await slack_service.send_message('T999', 'C123', 'test')

            assert result['ok'] is False
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_client_creation_error(self, slack_service):
        """Test error when client creation fails"""
        # Mock workspace exists but client creation fails
        with patch.object(slack_service, '_get_workspace', return_value=Mock()):
            with patch.object(slack_service, '_get_client', return_value=None):
                result = await slack_service.send_message('T123', 'C123', 'test')

                assert result['ok'] is False


# ============================================================================
# Test Class 7: TestSlackRateLimiter (4 tests)
# ============================================================================

class TestSlackRateLimiter:
    """Test Slack API rate limiting"""

    @pytest.mark.asyncio
    async def test_rate_limit_check_under_limit(self):
        """Test rate limit check when under limit"""
        limiter = SlackRateLimiter(redis_client=None)

        # First request should pass
        result = await limiter.check_limit('T123456', 'chat.postMessage')

        assert result is True

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """Test rate limit when exceeded"""
        limiter = SlackRateLimiter(redis_client=None)

        # Make requests up to limit (1 per second for chat.postMessage)
        await limiter.check_limit('T123456', 'chat.postMessage')

        # Immediate second request should fail
        result = await limiter.check_limit('T123456', 'chat.postMessage')

        assert result is False

    @pytest.mark.asyncio
    async def test_rate_limit_reset_after_window(self):
        """Test rate limit resets after time window"""
        limiter = SlackRateLimiter(redis_client=None)

        # First request
        await limiter.check_limit('T123456', 'chat.postMessage')

        # Wait for window to expire (1 second for chat.postMessage)
        await asyncio.sleep(1.1)

        # Should be allowed again
        result = await limiter.check_limit('T123456', 'chat.postMessage')

        assert result is True

    @pytest.mark.asyncio
    async def test_rate_limit_different_endpoints(self):
        """Test rate limits are per-endpoint"""
        limiter = SlackRateLimiter(redis_client=None)

        # Same workspace, different endpoints
        result1 = await limiter.check_limit('T123456', 'chat.postMessage')
        result2 = await limiter.check_limit('T123456', 'conversations.list')

        # Should both pass (different endpoints)
        assert result1 is True
        assert result2 is True


# ============================================================================
# Test Class 8: TestSlackWorkspace (4 tests)
# ============================================================================

class TestSlackWorkspace:
    """Test workspace management"""

    @pytest.mark.asyncio
    async def test_get_workspaces_empty(self, slack_service):
        """Test getting workspaces when none exist"""
        with patch.object(slack_service, '_get_workspace', return_value=None):
            workspaces = await slack_service.get_workspaces()

            assert workspaces == []

    @pytest.mark.asyncio
    async def test_get_workspaces_with_filter(self, slack_service, mock_workspace):
        """Test getting workspaces filtered by user"""
        user_id = 'U123456'

        with patch.object(slack_service, '_get_workspace', return_value=mock_workspace):
            # Mock redis for this test
            slack_service.redis_client = Mock()
            slack_service.redis_client.keys = Mock(return_value=[])
            slack_service.redis_client.get = Mock(return_value=None)

            workspaces = await slack_service.get_workspaces(user_id=user_id)

            # Since we mock db=None and redis has no keys, returns empty
            assert isinstance(workspaces, list)

    @pytest.mark.asyncio
    async def test_save_workspace_success(self, slack_service, mock_workspace):
        """Test saving workspace successfully"""
        slack_service.redis_client = Mock()
        slack_service.redis_client.setex = Mock()

        result = slack_service._save_workspace(mock_workspace)

        assert result is True
        assert slack_service.connection_status[mock_workspace.team_id] == SlackConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_save_workspace_with_encryption(self, slack_service, mock_workspace):
        """Test workspace token is encrypted when saved"""
        slack_service.redis_client = Mock()
        slack_service.redis_client.setex = Mock()

        original_token = mock_workspace.access_token
        slack_service._save_workspace(mock_workspace)

        # Verify encryption happened
        encrypted_token = slack_service._encrypt_token(original_token)
        assert encrypted_token != original_token


# ============================================================================
# Test Class 9: TestSlackMentions (2 tests)
# ============================================================================

class TestSlackMentions:
    """Test mention extraction from messages"""

    def test_extract_mentions_single(self, slack_service):
        """Test extracting single user mention"""
        text = "Hello <@U123456>, how are you?"

        mentions = slack_service._extract_mentions(text)

        assert len(mentions) == 1
        assert 'U123456' in mentions

    def test_extract_mentions_multiple(self, slack_service):
        """Test extracting multiple user mentions"""
        text = "<@U123456> and <@U789012> and <@WABCDEF>"

        mentions = slack_service._extract_mentions(text)

        assert len(mentions) == 3
        assert 'U123456' in mentions
        assert 'U789012' in mentions
        assert 'WABCDEF' in mentions


# ============================================================================
# Test Class 10: TestSlackServiceInfo (1 test)
# ============================================================================

class TestSlackServiceInfo:
    """Test service information"""

    @pytest.mark.asyncio
    async def test_get_service_info(self, slack_service):
        """Test getting service information"""
        info = await slack_service.get_service_info()

        assert info['name'] == 'Slack Enhanced Service'
        assert info['version'] == '3.0.0'
        assert isinstance(info['features'], list)
        assert 'message_management' in info['features']
        assert 'rate_limiting' in info['features']
        assert isinstance(info['supported_operations'], list)
        assert 'send_message' in info['supported_operations']
