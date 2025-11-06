"""
Slack Integration Test Suite
Comprehensive testing for Slack integration components
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import httpx

# Import modules to test
from integrations.slack_service_unified import (
    SlackUnifiedService,
    SlackError,
    SlackAPIError,
    SlackRateLimitError,
    SlackNetworkError,
    SlackHTTPError,
    SlackServiceError
)

from integrations.slack_events import SlackEventHandler, create_slack_event_handler
from integrations.slack_routes import slack_bp


class TestSlackUnifiedService:
    """Test Slack Unified Service"""
    
    @pytest.fixture
    def service_config(self):
        return {
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'signing_secret': 'test_signing_secret',
            'redirect_uri': 'http://localhost:3000/callback',
            'cache_ttl': 300
        }
    
    @pytest.fixture
    def service(self, service_config):
        return SlackUnifiedService(service_config)
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, service_config):
        """Test service initialization"""
        service = SlackUnifiedService(service_config)
        
        assert service.client_id == service_config['client_id']
        assert service.client_secret == service_config['client_secret']
        assert service.signing_secret == service_config['signing_secret']
        assert service.api_base_url == 'https://slack.com/api'
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, service):
        """Test successful API request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'ok': True, 'data': 'test_data'}
        mock_response.headers = {}
        
        service.client.request = AsyncMock(return_value=mock_response)
        
        result = await service.make_request('GET', 'test')
        
        assert result['ok'] is True
        assert result['data'] == 'test_data'
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_make_request_api_error(self, service):
        """Test API error response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'ok': False, 'error': 'test_error'}
        mock_response.headers = {}
        
        service.client.request = AsyncMock(return_value=mock_response)
        
        with pytest.raises(SlackAPIError) as exc_info:
            await service.make_request('GET', 'test')
        
        assert 'test_error' in str(exc_info.value)
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_make_request_rate_limit(self, service):
        """Test rate limiting response"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        mock_response.text = 'Rate limited'
        
        service.client.request = AsyncMock(return_value=mock_response)
        
        with pytest.raises(SlackRateLimitError) as exc_info:
            await service.make_request('GET', 'test')
        
        assert exc_info.value.retry_after == 60
        assert 'Rate limited' in str(exc_info.value)
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_make_request_network_error(self, service):
        """Test network error"""
        service.client.request = AsyncMock(side_effect=httpx.RequestError("Network error"))
        
        with pytest.raises(SlackNetworkError) as exc_info:
            await service.make_request('GET', 'test')
        
        assert 'Network error' in str(exc_info.value)
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_get_oauth_url(self, service):
        """Test OAuth URL generation"""
        user_id = 'test_user'
        scopes = ['channels:read', 'users:read']
        state = 'test_state'
        
        with patch('secrets.token_urlsafe', return_value=state):
            url = await service.get_oauth_url(user_id, scopes, state)
        
        assert 'slack.com/oauth/v2/authorize' in url
        assert 'client_id=test_client_id' in url
        assert 'channels:read' in url
        assert 'users:read' in url
        assert f'state={state}' in url
        assert f'user={user_id}' in url
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token(self, service):
        """Test code exchange for token"""
        code = 'test_code'
        state = 'test_state'
        
        mock_response_data = {
            'ok': True,
            'access_token': 'test_access_token',
            'token_type': 'Bearer',
            'scope': 'channels:read',
            'bot_user_id': 'U1234567890',
            'team': {'id': 'T1234567890', 'name': 'Test Team'},
            'enterprise': {'id': 'E1234567890', 'name': 'Test Enterprise'},
            'authed_user': {'id': 'U1234567890'},
            'expires_in': 3600,
            'refresh_token': 'test_refresh_token'
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.headers = {}
        
        service.client.request = AsyncMock(return_value=mock_response)
        
        result = await service.exchange_code_for_token(code, state)
        
        assert result['access_token'] == 'test_access_token'
        assert result['team_id'] == 'T1234567890'
        assert result['team_name'] == 'Test Team'
        assert result['enterprise_id'] == 'E1234567890'
        assert result['enterprise_name'] == 'Test Enterprise'
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_verify_webhook_signature(self, service):
        """Test webhook signature verification"""
        body = b'{"type": "url_verification", "challenge": "test_challenge"}'
        timestamp = str(int(datetime.now().timestamp()))
        
        # Create correct signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        import hmac
        import hashlib
        signature = 'v0=' + hmac.new(
            service.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Test valid signature
        result = await service.verify_webhook_signature(body, timestamp, signature)
        assert result is True
        
        # Test invalid signature
        invalid_signature = 'v0=invalid_signature'
        result = await service.verify_webhook_signature(body, timestamp, invalid_signature)
        assert result is False
        
        # Test old timestamp
        old_timestamp = str(int(datetime.now().timestamp()) - 400)  # 400 seconds ago
        result = await service.verify_webhook_signature(body, old_timestamp, signature)
        assert result is False
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_test_connection(self, service):
        """Test connection test"""
        token = 'test_token'
        
        mock_response_data = {
            'ok': True,
            'user_id': 'U1234567890',
            'user': 'testuser',
            'team_id': 'T1234567890',
            'team': 'Test Team',
            'bot_id': 'B1234567890',
            'url': 'https://testteam.slack.com/',
            'response_metadata': {}
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.headers = {}
        
        service.client.request = AsyncMock(return_value=mock_response)
        
        result = await service.test_connection(token)
        
        assert result['connected'] is True
        assert result['user_id'] == 'U1234567890'
        assert result['team_id'] == 'T1234567890'
        assert result['team'] == 'Test Team'
        
        await service.close()


class TestSlackEventHandler:
    """Test Slack Event Handler"""
    
    @pytest.fixture
    def signing_secret(self):
        return 'test_signing_secret'
    
    @pytest.fixture
    def event_handler(self, signing_secret):
        return SlackEventHandler(signing_secret)
    
    def test_event_handler_initialization(self, signing_secret):
        """Test event handler initialization"""
        handler = SlackEventHandler(signing_secret)
        
        assert handler.signing_secret == signing_secret
        assert 'url_verification' in handler.event_handlers
        assert 'event_callback' in handler.event_handlers
        assert handler.stats['events_received'] == 0
        
        # Test factory function
        with patch.dict('os.environ', {'SLACK_SIGNING_SECRET': signing_secret}):
            factory_handler = create_slack_event_handler()
            assert factory_handler is not None
            assert factory_handler.signing_secret == signing_secret
    
    def test_verify_request_success(self, event_handler):
        """Test successful request verification"""
        mock_request = Mock()
        mock_request.headers = {
            'X-Slack-Request-Timestamp': str(int(datetime.now().timestamp())),
            'X-Slack-Signature': 'v0=test_signature'
        }
        mock_request.get_data.return_value = b'test_body'
        
        with patch('hmac.compare_digest', return_value=True):
            result = event_handler.verify_request(mock_request)
            assert result is True
    
    def test_verify_request_invalid_timestamp(self, event_handler):
        """Test request verification with invalid timestamp"""
        mock_request = Mock()
        old_timestamp = str(int(datetime.now().timestamp()) - 400)  # 400 seconds ago
        mock_request.headers = {
            'X-Slack-Request-Timestamp': old_timestamp,
            'X-Slack-Signature': 'v0=test_signature'
        }
        mock_request.get_data.return_value = b'test_body'
        
        result = event_handler.verify_request(mock_request)
        assert result is False
    
    def test_verify_request_invalid_signature(self, event_handler):
        """Test request verification with invalid signature"""
        mock_request = Mock()
        mock_request.headers = {
            'X-Slack-Request-Timestamp': str(int(datetime.now().timestamp())),
            'X-Slack-Signature': 'v0=invalid_signature'
        }
        mock_request.get_data.return_value = b'test_body'
        
        with patch('hmac.compare_digest', return_value=False):
            result = event_handler.verify_request(mock_request)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_handle_url_verification(self, event_handler):
        """Test URL verification event"""
        event_data = {
            'type': 'url_verification',
            'challenge': 'test_challenge'
        }
        
        result = await event_handler.handle_event(event_data)
        
        assert result['challenge'] == 'test_challenge'
        assert event_handler.stats['events_received'] == 1
        assert event_handler.stats['events_processed'] == 1
    
    @pytest.mark.asyncio
    async def test_handle_event_callback_message(self, event_handler):
        """Test message event callback"""
        event_data = {
            'type': 'event_callback',
            'event': {
                'type': 'message',
                'user': 'U1234567890',
                'text': 'Hello world',
                'channel': 'C1234567890',
                'ts': '1234567890.123456'
            }
        }
        
        result = await event_handler.handle_event(event_data)
        
        assert result['status'] == 'processed'
        assert result['event'] == 'message'
        assert 'data' in result
        
        message_data = result['data']
        assert message_data['channel'] == 'C1234567890'
        assert message_data['user'] == 'U1234567890'
        assert message_data['text'] == 'Hello world'
        
        assert event_handler.stats['events_received'] == 1
        assert event_handler.stats['events_processed'] == 1
    
    @pytest.mark.asyncio
    async def test_handle_unknown_event_type(self, event_handler):
        """Test handling unknown event type"""
        event_data = {
            'type': 'unknown_event',
            'data': 'test'
        }
        
        result = await event_handler.handle_event(event_data)
        
        assert result['status'] == 'ignored'
        assert result['reason'] == 'Unknown event type'
        
        assert event_handler.stats['events_received'] == 1
        assert event_handler.stats['events_failed'] == 1
    
    @pytest.mark.asyncio
    async def test_handle_event_error(self, event_handler):
        """Test handling event with error"""
        event_data = {
            'type': 'event_callback',
            'event': None  # This will cause an error
        }
        
        result = await event_handler.handle_event(event_data)
        
        assert result['status'] == 'error'
        assert 'message' in result
        
        assert event_handler.stats['events_received'] == 1
        assert event_handler.stats['events_failed'] == 1
    
    def test_register_handler(self, event_handler):
        """Test registering custom handler"""
        async def custom_handler(event):
            return {'status': 'custom', 'event': event}
        
        event_handler.register_handler('custom_event', custom_handler)
        
        assert 'custom_event' in event_handler.event_handlers
        assert event_handler.event_handlers['custom_event'] == custom_handler
    
    def test_get_statistics(self, event_handler):
        """Test getting statistics"""
        # Update some stats
        event_handler.stats['events_received'] = 10
        event_handler.stats['events_processed'] = 8
        event_handler.stats['events_failed'] = 2
        
        stats = event_handler.get_statistics()
        
        assert stats['events_received'] == 10
        assert stats['events_processed'] == 8
        assert stats['events_failed'] == 2
        assert stats['success_rate'] == 80.0
        assert 'url_verification' in stats['registered_handlers']


class TestSlackRoutes:
    """Test Slack Integration Routes"""
    
    @pytest.fixture
    def app(self):
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(slack_bp)
        return app
    
    @pytest.fixture
    def client(self, app):
        return app.test_client()
    
    def test_health_check_success(self, client):
        """Test successful health check"""
        with patch('integrations.slack_routes.slack_enhanced_service.get_service_info') as mock_get_info:
            mock_get_info.return_value = {
                'version': '1.0.0',
                'capabilities': ['test_capability']
            }
            
            response = client.post('/api/integrations/slack/health')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'healthy'
            assert data['service'] == 'slack_integration'
            assert data['version'] == '1.0.0'
            assert 'test_capability' in data['capabilities']
    
    def test_health_check_failure(self, client):
        """Test health check failure"""
        with patch('integrations.slack_routes.slack_enhanced_service.get_service_info') as mock_get_info:
            mock_get_info.side_effect = Exception("Service error")
            
            response = client.post('/api/integrations/slack/health')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'unhealthy'
            assert 'Service error' in data['error']
    
    def test_get_workspaces_success(self, client):
        """Test successful workspaces retrieval"""
        mock_workspace = Mock()
        mock_workspace.to_dict.return_value = {
            'id': 'T1234567890',
            'name': 'Test Workspace',
            'domain': 'test'
        }
        
        with patch('integrations.slack_routes.slack_enhanced_service.get_workspaces') as mock_get_workspaces:
            mock_get_workspaces.return_value = [mock_workspace]
            
            response = client.post(
                '/api/integrations/slack/workspaces',
                json={'user_id': 'test_user'},
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert len(data['workspaces']) == 1
            assert data['workspaces'][0]['id'] == 'T1234567890'
            assert data['workspaces'][0]['name'] == 'Test Workspace'
    
    def test_get_workspaces_missing_user_id(self, client):
        """Test workspaces retrieval without user_id"""
        response = client.post(
            '/api/integrations/slack/workspaces',
            json={},
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        # Should default to 'default-user'
    
    def test_get_channels_success(self, client):
        """Test successful channels retrieval"""
        mock_channel = Mock()
        mock_channel.to_dict.return_value = {
            'id': 'C1234567890',
            'name': 'general',
            'is_private': False,
            'is_archived': False
        }
        mock_channel.is_archived = False
        
        with patch('integrations.slack_routes.slack_enhanced_service.get_channels') as mock_get_channels:
            mock_get_channels.return_value = [mock_channel]
            
            response = client.post(
                '/api/integrations/slack/channels',
                json={
                    'user_id': 'test_user',
                    'workspace_id': 'T1234567890',
                    'include_private': False,
                    'include_archived': False,
                    'limit': 100
                },
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert len(data['channels']) == 1
            assert data['channels'][0]['id'] == 'C1234567890'
    
    def test_get_channels_missing_workspace_id(self, client):
        """Test channels retrieval without workspace_id"""
        response = client.post(
            '/api/integrations/slack/channels',
            json={'user_id': 'test_user'},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert 'workspace_id is required' in data['error']
    
    def test_send_message_success(self, client):
        """Test successful message sending"""
        mock_message = Mock()
        mock_message.to_dict.return_value = {
            'id': '1234567890.123456',
            'text': 'Hello from ATOM',
            'channel': 'C1234567890',
            'user': 'U1234567890'
        }
        
        with patch('integrations.slack_routes.slack_enhanced_service.send_message') as mock_send:
            mock_send.return_value = mock_message
            
            response = client.post(
                '/api/integrations/slack/messages/send',
                json={
                    'user_id': 'test_user',
                    'workspace_id': 'T1234567890',
                    'channel_id': 'C1234567890',
                    'text': 'Hello from ATOM'
                },
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['message']['text'] == 'Hello from ATOM'
    
    def test_send_message_missing_required_fields(self, client):
        """Test message sending with missing required fields"""
        response = client.post(
            '/api/integrations/slack/messages/send',
            json={'user_id': 'test_user'},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert 'workspace_id and channel_id and text are required' in data['error']
    
    def test_search_messages_success(self, client):
        """Test successful message search"""
        mock_result = Mock()
        mock_result.to_dict.return_value = {
            'id': '1234567890.123456',
            'text': 'Search result',
            'channel': 'C1234567890'
        }
        
        with patch('integrations.slack_routes.slack_enhanced_service.search_messages') as mock_search:
            mock_search.return_value = {
                'messages': [mock_result],
                'paging': {},
                'total': 1,
                'search_filters': {}
            }
            
            response = client.post(
                '/api/integrations/slack/search',
                json={
                    'user_id': 'test_user',
                    'workspace_id': 'T1234567890',
                    'query': 'search term',
                    'count': 50
                },
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert len(data['messages']) == 1
            assert data['messages'][0]['text'] == 'Search result'
    
    def test_search_messages_missing_query(self, client):
        """Test message search without query"""
        response = client.post(
            '/api/integrations/slack/search',
            json={'user_id': 'test_user', 'workspace_id': 'T1234567890'},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert 'workspace_id and query are required' in data['error']
    
    def test_handle_webhook_events(self, client):
        """Test webhook event handling"""
        response = client.post(
            '/api/integrations/slack/events',
            json={
                'type': 'url_verification',
                'challenge': 'test_challenge'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['challenge'] == 'test_challenge'


# Integration tests
@pytest.mark.integration
class TestSlackIntegrationE2E:
    """End-to-end integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_oauth_flow(self):
        """Test complete OAuth flow from start to finish"""
        # This would test the entire OAuth flow using real Slack API
        # Mark with @pytest.mark.integration and use real credentials for testing
        pass
    
    @pytest.mark.asyncio
    async def test_full_data_ingestion_pipeline(self):
        """Test complete data ingestion pipeline"""
        # This would test the entire pipeline from Slack API to database
        pass
    
    @pytest.mark.asyncio
    async def test_realtime_event_processing(self):
        """Test real-time event processing"""
        # This would test webhook handling and event processing
        pass


# Performance tests
@pytest.mark.performance
class TestSlackIntegrationPerformance:
    """Performance tests for Slack integration"""
    
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self):
        """Test handling concurrent API requests"""
        # Test multiple simultaneous API calls
        pass
    
    @pytest.mark.asyncio
    async def test_large_dataset_processing(self):
        """Test processing large datasets"""
        # Test handling of large message/channel/file datasets
        pass
    
    @pytest.mark.asyncio
    async def test_memory_usage_during_ingestion(self):
        """Test memory usage during data ingestion"""
        # Monitor memory usage during large data ingestion
        pass


# Fixtures for common test data
@pytest.fixture
def mock_slack_workspace():
    return {
        'id': 'T1234567890',
        'name': 'Test Workspace',
        'domain': 'test-workspace',
        'url': 'https://test-workspace.slack.com',
        'icon': {'image_34': 'https://.../icon.png'},
        'enterprise_id': 'E1234567890',
        'enterprise_name': 'Test Enterprise'
    }


@pytest.fixture
def mock_slack_channel():
    return {
        'id': 'C1234567890',
        'name': 'general',
        'display_name': 'general',
        'purpose': {'value': 'Company-wide announcements'},
        'topic': {'value': 'Company updates'},
        'is_private': False,
        'is_archived': False,
        'is_general': True,
        'is_shared': False,
        'num_members': 50,
        'created': 1609459200
    }


@pytest.fixture
def mock_slack_user():
    return {
        'id': 'U1234567890',
        'name': 'testuser',
        'real_name': 'Test User',
        'display_name': 'Test User',
        'profile': {
            'email': 'test@example.com',
            'image_24': 'https://.../avatar.png'
        },
        'is_bot': False,
        'is_admin': False,
        'is_owner': False,
        'presence': 'active'
    }


@pytest.fixture
def mock_slack_message():
    return {
        'id': '1234567890.123456',
        'text': 'Hello world',
        'user': 'U1234567890',
        'channel': 'C1234567890',
        'team': 'T1234567890',
        'ts': '1234567890.123456',
        'type': 'message',
        'reactions': [{'name': 'thumbsup', 'count': 2}],
        'files': [],
        'pinned_to': [],
        'reply_count': 0
    }


# Test runner configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )


if __name__ == "__main__":
    # Run tests with specific markers
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-m", "not integration and not performance"
    ])