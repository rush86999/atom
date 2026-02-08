#!/usr/bin/env python3
"""
Test Suite for Slack Workflow Actions
Tests SlackEnhancedService methods and workflow engine integration
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, AsyncMock, patch
import uuid

# Import Slack workflow components
from integrations.slack_enhanced_service import (
    SlackEnhancedService,
    SlackWorkspace
)
from integrations.slack_workflow_engine import (
    WorkflowExecutionEngine,
    WorkflowDefinition,
    WorkflowTrigger,
    WorkflowTriggerType,
    WorkflowAction,
    WorkflowActionType,
    WorkflowActionParameter,
    WorkflowExecution,
    WorkflowExecutionStatus,
    WorkflowExecutionPriority,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def slack_service():
    """Create Slack enhanced service instance"""
    config = {
        'client_id': 'test_client_id',
        'client_secret': 'test_client_secret',
        'redirect_uri': 'http://localhost:8000/oauth/callback',
        'signing_secret': 'test_signing_secret',
    }
    return SlackEnhancedService(config)


@pytest.fixture
def workflow_engine():
    """Create workflow engine instance"""
    config = {
        'max_concurrent_executions': 5,
        'execution_timeout': 300,
        'retry_attempts': 3,
        'retry_delay': 5,
        'slack': {
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
        }
    }
    return WorkflowExecutionEngine(config)


@pytest.fixture
def mock_workspace():
    """Create mock workspace"""
    return SlackWorkspace(
        team_id='T123456',
        team_name='Test Workspace',
        domain='test-workspace',
        url='https://test-workspace.slack.com',
        access_token='xoxb-test-token',
        bot_id='B123456',
    )


@pytest.fixture
def sample_trigger_data():
    """Create sample trigger data"""
    return {
        'type': 'message',
        'workspace_id': 'T123456',
        'channel_id': 'C123456',
        'user_id': 'U123456',
        'text': 'Test message',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# SlackEnhancedService Method Tests
# ============================================================================

class TestSlackEnhancedServiceMethods:
    """Test SlackEnhancedService new methods"""

    @pytest.mark.asyncio
    async def test_add_reaction_success(self, slack_service, mock_workspace):
        """Test successful reaction addition"""
        # Mock the client and rate limiter
        mock_client = AsyncMock()
        mock_client.reactions_add = AsyncMock(return_value={'ok': True})

        with patch.object(slack_service, '_get_client', return_value=mock_client), \
             patch.object(slack_service.rate_limiter, 'check_limit', return_value=True):

            result = await slack_service.add_reaction(
                workspace_id='T123456',
                channel_id='C123456',
                timestamp='1234567890.123456',
                reaction='thumbsup'
            )

        assert result['ok'] is True
        assert result['reaction'] == 'thumbsup'
        assert result['channel'] == 'C123456'
        assert result['message'] == 'Reaction added successfully'
        mock_client.reactions_add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_reaction_with_colons(self, slack_service):
        """Test reaction with colons is handled correctly"""
        mock_client = AsyncMock()
        mock_client.reactions_add = AsyncMock(return_value={'ok': True})

        with patch.object(slack_service, '_get_client', return_value=mock_client), \
             patch.object(slack_service.rate_limiter, 'check_limit', return_value=True):

            result = await slack_service.add_reaction(
                workspace_id='T123456',
                channel_id='C123456',
                timestamp='1234567890.123456',
                reaction=':thumbsup:'  # With colons
            )

        assert result['ok'] is True
        assert result['reaction'] == 'thumbsup'  # Colons stripped
        # Verify the API was called with stripped reaction
        mock_client.reactions_add.assert_called_once_with(
            channel='C123456',
            timestamp='1234567890.123456',
            name='thumbsup'
        )

    @pytest.mark.asyncio
    async def test_add_reaction_rate_limited(self, slack_service):
        """Test reaction addition when rate limited"""
        with patch.object(slack_service.rate_limiter, 'check_limit', return_value=False):
            result = await slack_service.add_reaction(
                workspace_id='T123456',
                channel_id='C123456',
                timestamp='1234567890.123456',
                reaction='thumbsup'
            )

        assert result['ok'] is False
        assert 'Rate limit' in result['error']

    @pytest.mark.asyncio
    async def test_send_dm_success(self, slack_service):
        """Test successful DM sending"""
        mock_client = AsyncMock()
        mock_client.conversations_open = AsyncMock(return_value={
            'ok': True,
            'channel': {'id': 'D123456'}
        })
        mock_client.chat_postMessage = AsyncMock(return_value={
            'ok': True,
            'message': {'ts': '1234567890.123456'}
        })

        with patch.object(slack_service, '_get_client', return_value=mock_client), \
             patch.object(slack_service.rate_limiter, 'check_limit', return_value=True):

            result = await slack_service.send_dm(
                workspace_id='T123456',
                user_id='U123456',
                text='Test DM message'
            )

        assert result['ok'] is True
        assert result['user_id'] == 'U123456'
        assert result['channel'] == 'D123456'
        assert result['message_id'] == '1234567890.123456'

    @pytest.mark.asyncio
    async def test_send_dm_with_blocks(self, slack_service):
        """Test DM with block kit blocks"""
        mock_client = AsyncMock()
        mock_client.conversations_open = AsyncMock(return_value={
            'ok': True,
            'channel': {'id': 'D123456'}
        })
        mock_client.chat_postMessage = AsyncMock(return_value={
            'ok': True,
            'message': {'ts': '1234567890.123456'}
        })

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Test block"
                }
            }
        ]

        with patch.object(slack_service, '_get_client', return_value=mock_client), \
             patch.object(slack_service.rate_limiter, 'check_limit', return_value=True):

            result = await slack_service.send_dm(
                workspace_id='T123456',
                user_id='U123456',
                text='Fallback text',
                blocks=blocks
            )

        assert result['ok'] is True
        # Verify blocks were passed
        call_args = mock_client.chat_postMessage.call_args
        assert 'blocks' in call_args.kwargs
        assert call_args.kwargs['blocks'] == blocks

    @pytest.mark.asyncio
    async def test_create_channel_success(self, slack_service):
        """Test successful channel creation"""
        mock_client = AsyncMock()
        mock_client.conversations_create = AsyncMock(return_value={
            'ok': True,
            'channel': {
                'id': 'C123456',
                'name': 'test-channel',
                'is_private': False,
                'created': 1234567890
            }
        })
        mock_client.conversations_setTopic = AsyncMock(return_value={'ok': True})

        with patch.object(slack_service, '_get_client', return_value=mock_client), \
             patch.object(slack_service.rate_limiter, 'check_limit', return_value=True):

            result = await slack_service.create_channel(
                workspace_id='T123456',
                name='test-channel',
                is_private=False,
                description='Test channel description'
            )

        assert result['ok'] is True
        assert result['channel_id'] == 'C123456'
        assert result['channel_name'] == 'test-channel'
        assert result['is_private'] is False

    @pytest.mark.asyncio
    async def test_invite_to_channel_success(self, slack_service):
        """Test successful user invitation to channel"""
        mock_client = AsyncMock()
        mock_client.conversations_invite = AsyncMock(return_value={'ok': True})

        with patch.object(slack_service, '_get_client', return_value=mock_client):

            result = await slack_service.invite_to_channel(
                workspace_id='T123456',
                channel_id='C123456',
                user_ids=['U123456', 'U789012']
            )

        assert result['ok'] is True
        assert result['invited_users'] == ['U123456', 'U789012']
        assert len(result['failed_users']) == 0

    @pytest.mark.asyncio
    async def test_invite_to_channel_partial_failure(self, slack_service):
        """Test channel invitation with some failures"""
        mock_client = AsyncMock()

        # First call succeeds, second fails
        call_count = [0]

        async def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {'ok': True}
            else:
                raise Exception("User not in workspace")

        mock_client.conversations_invite = AsyncMock(side_effect=side_effect)

        with patch.object(slack_service, '_get_client', return_value=mock_client):

            result = await slack_service.invite_to_channel(
                workspace_id='T123456',
                channel_id='C123456',
                user_ids=['U123456', 'U789012']
            )

        assert result['ok'] is True  # Overall success since at least one succeeded
        assert len(result['invited_users']) == 1
        assert len(result['failed_users']) == 1

    @pytest.mark.asyncio
    async def test_pin_message_success(self, slack_service):
        """Test successful message pinning"""
        mock_client = AsyncMock()
        mock_client.pins_add = AsyncMock(return_value={'ok': True})

        with patch.object(slack_service, '_get_client', return_value=mock_client), \
             patch.object(slack_service.rate_limiter, 'check_limit', return_value=True):

            result = await slack_service.pin_message(
                workspace_id='T123456',
                channel_id='C123456',
                timestamp='1234567890.123456'
            )

        assert result['ok'] is True
        assert result['channel'] == 'C123456'
        assert result['message'] == 'Message pinned successfully'


# ============================================================================
# Workflow Engine Integration Tests
# ============================================================================

class TestWorkflowEngineIntegration:
    """Test workflow engine integration with Slack service"""

    @pytest.mark.asyncio
    async def test_handle_send_message_with_real_service(self, workflow_engine, sample_trigger_data):
        """Test send_message action uses real Slack service"""
        mock_client = AsyncMock()
        mock_client.chat_postMessage = AsyncMock(return_value={
            'ok': True,
            'message': {'ts': '1234567890.123456'}
        })

        # Mock the Slack service
        mock_slack_service = AsyncMock()
        mock_slack_service.send_message = AsyncMock(return_value={
            'ok': True,
            'timestamp': '1234567890.123456',
            'message_id': 'msg123'
        })

        workflow_engine.slack_service = mock_slack_service

        # Create execution and action
        execution = WorkflowExecution(
            id='exec123',
            workflow_id='wf123',
            trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data=sample_trigger_data,
            status=WorkflowExecutionStatus.RUNNING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc)
        )

        action = WorkflowAction(
            id='action1',
            type=WorkflowActionType.SEND_MESSAGE,
            parameters={
                'channel': WorkflowActionParameter(
                    name='channel',
                    value='C123456',
                    required=True
                ),
                'message': WorkflowActionParameter(
                    name='message',
                    value='Test message',
                    required=True
                )
            }
        )

        result = await workflow_engine._handle_send_message(execution, action)

        assert result['ok'] is True
        assert result['channel'] == 'C123456'
        assert result['method'] == 'slack_api'
        mock_slack_service.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_send_message_fallback_to_mock(self, workflow_engine, sample_trigger_data):
        """Test send_message falls back to mock when service unavailable"""
        # No Slack service available
        workflow_engine.slack_service = None

        execution = WorkflowExecution(
            id='exec123',
            workflow_id='wf123',
            trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data=sample_trigger_data,
            status=WorkflowExecutionStatus.RUNNING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc)
        )

        action = WorkflowAction(
            id='action1',
            type=WorkflowActionType.SEND_MESSAGE,
            parameters={
                'channel': WorkflowActionParameter(
                    name='channel',
                    value='C123456',
                    required=True
                ),
                'message': WorkflowActionParameter(
                    name='message',
                    value='Test message',
                    required=True
                )
            }
        )

        result = await workflow_engine._handle_send_message(execution, action)

        assert result['channel'] == 'C123456'
        assert result['message'] == 'Test message'
        assert result['method'] == 'mock'
        assert 'message_id' in result

    @pytest.mark.asyncio
    async def test_handle_add_reaction_integration(self, workflow_engine, sample_trigger_data):
        """Test add_reaction action integration"""
        mock_slack_service = AsyncMock()
        mock_slack_service.add_reaction = AsyncMock(return_value={
            'ok': True,
            'reaction': 'thumbsup',
            'channel': 'C123456'
        })

        workflow_engine.slack_service = mock_slack_service

        execution = WorkflowExecution(
            id='exec123',
            workflow_id='wf123',
            trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data=sample_trigger_data,
            status=WorkflowExecutionStatus.RUNNING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc)
        )

        action = WorkflowAction(
            id='action1',
            type=WorkflowActionType.ADD_REACTION,
            parameters={
                'channel': WorkflowActionParameter(
                    name='channel',
                    value='C123456',
                    required=True
                ),
                'message_ts': WorkflowActionParameter(
                    name='message_ts',
                    value='1234567890.123456',
                    required=True
                ),
                'emoji': WorkflowActionParameter(
                    name='emoji',
                    value='thumbsup',
                    required=True
                )
            }
        )

        result = await workflow_engine._handle_add_reaction(execution, action)

        assert result['ok'] is True
        assert result['method'] == 'slack_api'
        mock_slack_service.add_reaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_create_channel_integration(self, workflow_engine, sample_trigger_data):
        """Test create_channel action integration"""
        mock_slack_service = AsyncMock()
        mock_slack_service.create_channel = AsyncMock(return_value={
            'ok': True,
            'channel_id': 'C789012',
            'channel_name': 'new-channel',
            'is_private': False
        })

        workflow_engine.slack_service = mock_slack_service

        execution = WorkflowExecution(
            id='exec123',
            workflow_id='wf123',
            trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data=sample_trigger_data,
            status=WorkflowExecutionStatus.RUNNING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc)
        )

        action = WorkflowAction(
            id='action1',
            type=WorkflowActionType.CREATE_CHANNEL,
            parameters={
                'name': WorkflowActionParameter(
                    name='name',
                    value='new-channel',
                    required=True
                ),
                'private': WorkflowActionParameter(
                    name='private',
                    value=False,
                    required=True
                )
            }
        )

        result = await workflow_engine._handle_create_channel(execution, action)

        assert result['ok'] is True
        assert result['method'] == 'slack_api'
        assert result['channel_id'] == 'C789012'

    @pytest.mark.asyncio
    async def test_handle_invite_to_channel_integration(self, workflow_engine, sample_trigger_data):
        """Test invite_user action integration"""
        mock_slack_service = AsyncMock()
        mock_slack_service.invite_to_channel = AsyncMock(return_value={
            'ok': True,
            'invited_users': ['U123456', 'U789012'],
            'failed_users': []
        })

        workflow_engine.slack_service = mock_slack_service

        execution = WorkflowExecution(
            id='exec123',
            workflow_id='wf123',
            trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data=sample_trigger_data,
            status=WorkflowExecutionStatus.RUNNING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc)
        )

        action = WorkflowAction(
            id='action1',
            type=WorkflowActionType.INVITE_USER,
            parameters={
                'channel': WorkflowActionParameter(
                    name='channel',
                    value='C123456',
                    required=True
                ),
                'user_ids': WorkflowActionParameter(
                    name='user_ids',
                    value=['U123456', 'U789012'],
                    required=True
                )
            }
        )

        result = await workflow_engine._handle_invite_user(execution, action)

        assert result['ok'] is True
        assert result['method'] == 'slack_api'
        assert result['invited_users'] == ['U123456', 'U789012']

    @pytest.mark.asyncio
    async def test_handle_pin_message_integration(self, workflow_engine, sample_trigger_data):
        """Test pin_message action integration"""
        mock_slack_service = AsyncMock()
        mock_slack_service.pin_message = AsyncMock(return_value={
            'ok': True,
            'channel': 'C123456',
            'message_ts': '1234567890.123456'
        })

        workflow_engine.slack_service = mock_slack_service

        execution = WorkflowExecution(
            id='exec123',
            workflow_id='wf123',
            trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data=sample_trigger_data,
            status=WorkflowExecutionStatus.RUNNING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc)
        )

        action = WorkflowAction(
            id='action1',
            type=WorkflowActionType.PIN_MESSAGE,
            parameters={
                'channel': WorkflowActionParameter(
                    name='channel',
                    value='C123456',
                    required=True
                ),
                'message_ts': WorkflowActionParameter(
                    name='message_ts',
                    value='1234567890.123456',
                    required=True
                )
            }
        )

        result = await workflow_engine._handle_pin_message(execution, action)

        assert result['ok'] is True
        assert result['method'] == 'slack_api'


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestSlackActionsErrorHandling:
    """Test error handling in Slack actions"""

    @pytest.mark.asyncio
    async def test_slack_service_unavailable_graceful_fallback(self, workflow_engine, sample_trigger_data):
        """Test graceful fallback when Slack service is unavailable"""
        # Simulate service failure
        mock_slack_service = AsyncMock()
        mock_slack_service.send_message = AsyncMock(side_effect=Exception("Service unavailable"))

        workflow_engine.slack_service = mock_slack_service

        execution = WorkflowExecution(
            id='exec123',
            workflow_id='wf123',
            trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data=sample_trigger_data,
            status=WorkflowExecutionStatus.RUNNING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc)
        )

        action = WorkflowAction(
            id='action1',
            type=WorkflowActionType.SEND_MESSAGE,
            parameters={
                'channel': WorkflowActionParameter(
                    name='channel',
                    value='C123456',
                    required=True
                ),
                'message': WorkflowActionParameter(
                    name='message',
                    value='Test message',
                    required=True
                )
            }
        )

        result = await workflow_engine._handle_send_message(execution, action)

        # Should fall back to mock
        assert result['method'] == 'mock'
        assert 'message_id' in result

    @pytest.mark.asyncio
    async def test_invalid_user_ids_list_conversion(self, workflow_engine, sample_trigger_data):
        """Test string user_ids is converted to list"""
        mock_slack_service = AsyncMock()
        mock_slack_service.invite_to_channel = AsyncMock(return_value={
            'ok': True,
            'invited_users': ['U123456'],
            'failed_users': []
        })

        workflow_engine.slack_service = mock_slack_service

        execution = WorkflowExecution(
            id='exec123',
            workflow_id='wf123',
            trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data=sample_trigger_data,
            status=WorkflowExecutionStatus.RUNNING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc)
        )

        # Pass string instead of list
        action = WorkflowAction(
            id='action1',
            type=WorkflowActionType.INVITE_USER,
            parameters={
                'channel': WorkflowActionParameter(
                    name='channel',
                    value='C123456',
                    required=True
                ),
                'user_ids': WorkflowActionParameter(
                    name='user_ids',
                    value='U123456',  # String instead of list
                    required=True
                )
            }
        )

        result = await workflow_engine._handle_invite_user(execution, action)

        # Should convert string to list
        assert result['ok'] is True
        mock_slack_service.invite_to_channel.assert_called_once()
        # Verify it was called with a list
        call_args = mock_slack_service.invite_to_channel.call_args
        assert isinstance(call_args[0][2], list)  # user_ids should be a list


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
