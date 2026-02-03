"""
Test suite for newly implemented integration features
Tests the communication ingestion pipeline, OAuth context manager, and enterprise services
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest


class TestCommunicationIngestionPipeline:
    """Test communication ingestion pipeline implementations"""

    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance"""
        from integrations.atom_communication_ingestion_pipeline import (
            CommunicationIngestionPipeline,
            LanceDBMemoryManager,
        )
        memory_manager = LanceDBMemoryManager()
        pipeline = CommunicationIngestionPipeline(memory_manager)
        return pipeline

    @pytest.mark.asyncio
    async def test_fetch_whatsapp_messages(self, pipeline):
        """Test WhatsApp message fetching"""
        # Mock the integration service
        with patch('integrations.atom_communication_ingestion_pipeline.whatsapp_integration_service') as mock_service:
            mock_service.get_messages = AsyncMock(return_value=[
                {
                    "id": "msg1",
                    "from": "1234567890",
                    "to": "9876543210",
                    "content": "Test message",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ])

            messages = await pipeline._fetch_whatsapp_messages(None)

            assert isinstance(messages, list)
            # Verify service was called
            mock_service.get_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_whatsapp_messages_service_unavailable(self, pipeline):
        """Test WhatsApp fetching when service unavailable"""
        with patch('integrations.atom_communication_ingestion_pipeline.whatsapp_integration_service', side_effect=ImportError()):
            messages = await pipeline._fetch_whatsapp_messages(None)
            assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_teams_messages(self, pipeline):
        """Test Microsoft Teams message fetching"""
        with patch('integrations.atom_communication_ingestion_pipeline.token_storage') as mock_storage:
            # Mock token storage
            mock_storage.get_token = Mock(return_value={
                "access_token": "test_token"
            })

            # Mock httpx client
            with patch('integrations.atom_communication_ingestion_pipeline.httpx.AsyncClient') as mock_client_class:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"value": []}

                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                messages = await pipeline._fetch_teams_messages(None)

                assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_fetch_teams_messages_no_token(self, pipeline):
        """Test Teams fetching without token"""
        with patch('integrations.atom_communication_ingestion_pipeline.token_storage') as mock_storage:
            mock_storage.get_token = Mock(return_value=None)

            messages = await pipeline._fetch_teams_messages(None)

            assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_outlook_messages(self, pipeline):
        """Test Outlook message fetching"""
        with patch('integrations.atom_communication_ingestion_pipeline.token_storage') as mock_storage:
            mock_storage.get_token = Mock(return_value={
                "access_token": "test_token"
            })

            with patch('integrations.atom_communication_ingestion_pipeline.httpx.AsyncClient') as mock_client_class:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"value": []}

                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                messages = await pipeline._fetch_outlook_messages(None)

                assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_fetch_email_messages_imap(self, pipeline):
        """Test IMAP email fetching"""
        with patch.dict('os.environ', {
            'IMAP_SERVER': 'imap.test.com',
            'IMAP_USER': 'test@test.com',
            'IMAP_PASSWORD': 'password'
        }):
            # Mock IMAP operations
            with patch('integrations.atom_communication_ingestion_pipeline.imaplib.IMAP4_SSL') as mock_imap:
                mock_mail = Mock()
                mock_imap.return_value = mock_mail
                mock_mail.login.return_value = None
                mock_mail.select.return_value = None
                mock_mail.search.return_value = ('OK', [b''])
                mock_mail.fetch.return_value = []
                mock_mail.close.return_value = None
                mock_mail.logout.return_value = None

                messages = await pipeline._fetch_email_messages(None)

                assert isinstance(messages, list)
                # Verify IMAP connection was attempted
                mock_imap.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_gmail_messages(self, pipeline):
        """Test Gmail message fetching"""
        with patch('integrations.atom_communication_ingestion_pipeline.GmailService') as mock_gmail_class:
            mock_service = AsyncMock()
            mock_service.authenticate = AsyncMock(return_value=True)
            mock_service.get_messages = AsyncMock(return_value=[])
            mock_gmail_class.return_value = mock_service

            messages = await pipeline._fetch_gmail_messages(None)

            assert isinstance(messages, list)
            mock_service.authenticate.assert_called_once()


class TestOAuthUserContext:
    """Test OAuth user context manager"""

    @pytest.fixture
    def context(self):
        """Create OAuth user context"""
        from core.oauth_user_context import OAuthUserContext
        return OAuthUserContext("user123", "google")

    def test_context_initialization(self, context):
        """Test context initialization"""
        assert context.user_id == "user123"
        assert context.provider == "google"
        assert context._token_data is None

    @pytest.mark.asyncio
    async def test_get_access_token_success(self, context):
        """Test getting access token successfully"""
        with patch('core.oauth_user_context.ConnectionService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_connection = AsyncMock(return_value={
                "access_token": "test_token",
                "expires_at": (datetime.now().timestamp() + 3600)
            })
            mock_service_class.return_value = mock_service

            token = await context.get_access_token()

            assert token == "test_token"
            assert context._token_data is not None

    @pytest.mark.asyncio
    async def test_get_access_token_no_connection(self, context):
        """Test getting access token when no connection exists"""
        with patch('core.oauth_user_context.ConnectionService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_connection = AsyncMock(return_value=None)
            mock_service_class.return_value = mock_service

            token = await context.get_access_token()

            assert token is None

    def test_is_token_expired_with_expiry(self, context):
        """Test token expiration check"""
        # Token expired
        expired_connection = {
            "expires_at": (datetime.now().timestamp() - 100)
        }
        assert context._is_token_expired(expired_connection) is True

        # Token valid
        valid_connection = {
            "expires_at": (datetime.now().timestamp() + 3600)
        }
        assert context._is_token_expired(valid_connection) is False

        # No expiry
        no_expiry_connection = {}
        assert context._is_token_expired(no_expiry_connection) is False

    def test_is_authenticated(self, context):
        """Test authentication check"""
        assert context.is_authenticated() is False

        context._token_data = {"access_token": "test"}
        assert context.is_authenticated() is True


class TestSlackConfig:
    """Test Slack configuration updates"""

    @pytest.fixture
    def config_manager(self):
        """Create config manager"""
        from integrations.slack_config import SlackConfigManager, SlackIntegrationConfig
        config = SlackIntegrationConfig()
        manager = SlackConfigManager()
        return manager

    def test_update_api_config(self, config_manager):
        """Test updating API configuration"""
        updates = {
            "client_id": "new_client_id",
            "bot_token": "new_bot_token"
        }

        config_manager.update_config(updates)

        assert config_manager.config.api.client_id == "new_client_id"
        assert config_manager.config.api.bot_token == "new_bot_token"

    def test_update_feature_flags(self, config_manager):
        """Test updating feature flags"""
        updates = {
            "enable_events": True,
            "enable_workflows": False
        }

        config_manager.update_config(updates)

        assert config_manager.config.features.enable_events is True
        assert config_manager.config.features.enable_workflows is False

    def test_update_rate_limits(self, config_manager):
        """Test updating rate limits"""
        updates = {
            "tier_1_limit": 200,
            "tier_2_limit": 100
        }

        config_manager.update_config(updates)

        assert config_manager.config.rate_limits.tier_1_limit == 200
        assert config_manager.config.rate_limits.tier_2_limit == 100

    def test_update_cache_config(self, config_manager):
        """Test updating cache configuration"""
        updates = {
            "cache_enabled": True,
            "cache_ttl": 300
        }

        config_manager.update_config(updates)

        assert config_manager.config.cache.enabled is True
        assert config_manager.config.cache.ttl == 300


class TestGoogleServices:
    """Test Google services without dummy classes"""

    def test_google_calendar_imports_available(self):
        """Test that Google Calendar service handles missing imports gracefully"""
        from integrations.google_calendar_service import GOOGLE_APIS_AVAILABLE

        # Test that the flag is set based on actual availability
        assert isinstance(GOOGLE_APIS_AVAILABLE, bool)

    def test_gmail_imports_available(self):
        """Test that Gmail service handles missing imports gracefully"""
        from integrations.gmail_service import GOOGLE_APIS_AVAILABLE

        # Test that the flag is set based on actual availability
        assert isinstance(GOOGLE_APIS_AVAILABLE, bool)


class TestEnterpriseUnifiedService:
    """Test enterprise unified service implementations"""

    @pytest.fixture
    def service(self):
        """Create enterprise service"""
        from integrations.atom_enterprise_unified_service import enterprise_unified_service
        return enterprise_unified_service

    @pytest.mark.asyncio
    async def test_initialize_enterprise_services(self, service):
        """Test enterprise services initialization"""
        # This should not raise an error
        await service._initialize_enterprise_services()

    @pytest.mark.asyncio
    async def test_setup_workflow_security(self, service):
        """Test workflow security setup"""
        # This should not raise an error
        await service._setup_workflow_security_integration()

    @pytest.mark.asyncio
    async def test_setup_compliance_automation(self, service):
        """Test compliance automation setup"""
        # This should not raise an error
        await service._setup_compliance_automation()

    @pytest.mark.asyncio
    async def test_setup_ai_automation(self, service):
        """Test AI automation setup"""
        # This should not raise an error
        await service._setup_ai_powered_automation()

    @pytest.mark.asyncio
    async def test_start_monitoring(self, service):
        """Test enterprise monitoring startup"""
        # This should not raise an error
        await service._start_enterprise_monitoring()


class TestEnterpriseSecurityService:
    """Test enterprise security service implementations"""

    @pytest.fixture
    def security_service(self):
        """Create security service"""
        from integrations.atom_enterprise_security_service import enterprise_security_service
        return security_service

    @pytest.mark.asyncio
    async def test_initialize_encryption(self, security_service):
        """Test encryption initialization"""
        await security_service._initialize_encryption()
        assert hasattr(security_service, 'encryption_config')

    @pytest.mark.asyncio
    async def test_load_security_policies(self, security_service):
        """Test security policies loading"""
        await security_service._load_security_policies()
        assert hasattr(security_service, 'security_policies')

    @pytest.mark.asyncio
    async def test_initialize_threat_detection(self, security_service):
        """Test threat detection initialization"""
        await security_service._initialize_threat_detection()
        assert hasattr(security_service, 'threat_detection_config')

    @pytest.mark.asyncio
    async def test_start_security_monitoring(self, security_service):
        """Test security monitoring startup"""
        await security_service._start_security_monitoring()
        assert security_service.monitoring_active is True

    @pytest.mark.asyncio
    async def test_initialize_compliance_monitoring(self, security_service):
        """Test compliance monitoring initialization"""
        await security_service._initialize_compliance_monitoring()
        assert hasattr(security_service, 'compliance_monitoring')


class TestAIIntegration:
    """Test AI integration implementations"""

    @pytest.fixture
    def ai_integration(self):
        """Create AI integration"""
        from integrations.atom_ai_integration import atom_ai_integration
        return ai_integration

    @pytest.mark.asyncio
    async def test_update_search_index(self, ai_integration):
        """Test search index update"""
        # This should not raise an error
        await ai_integration.update_search_index()

    @pytest.mark.asyncio
    async def test_load_search_index(self, ai_integration):
        """Test search index loading"""
        # This should not raise an error
        await ai_integration._load_search_index()
        assert hasattr(ai_integration, 'search_index')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
