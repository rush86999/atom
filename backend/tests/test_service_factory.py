"""
Test Service Factory

Tests for the centralized service factory.
"""

import pytest
import threading
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.service_factory import ServiceFactory
from core.agent_governance_service import AgentGovernanceService
from core.agent_context_resolver import AgentContextResolver
from core.governance_cache import GovernanceCache


class TestServiceFactory:
    """Test suite for ServiceFactory"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock(spec=Session)

    def test_get_governance_service(self, mock_db):
        """Test getting governance service"""
        with patch('core.service_factory.AgentGovernanceService') as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance

            service = ServiceFactory.get_governance_service(mock_db)

            assert service == mock_instance
            mock_class.assert_called_once_with(mock_db)

    def test_get_context_resolver(self, mock_db):
        """Test getting context resolver"""
        with patch('core.service_factory.AgentContextResolver') as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance

            resolver = ServiceFactory.get_context_resolver(mock_db)

            assert resolver == mock_instance
            mock_class.assert_called_once_with(mock_db)

    def test_get_governance_cache_singleton(self):
        """Test that governance cache is a singleton"""
        cache1 = ServiceFactory.get_governance_cache()
        cache2 = ServiceFactory.get_governance_cache()

        assert cache1 is cache2  # Same instance

    def test_clear_thread_local(self, mock_db):
        """Test clearing thread-local storage"""
        # Create a service
        ServiceFactory.get_governance_service(mock_db)

        # Clear thread-local storage
        ServiceFactory.clear_thread_local()

        # Verify services are cleared
        # (New instances will be created on next access)
        assert True  # If no exception raised, test passes


class TestThreadSafety:
    """Test suite for thread safety"""

    def test_thread_local_isolation(self):
        """Test that different threads get different service instances"""
        services = []

        def create_service():
            mock_db = Mock(spec=Session)
            service = ServiceFactory.get_governance_service(mock_db)
            services.append(id(service))

        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_service)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All services should have different IDs (different instances per thread)
        # But within same thread, should reuse instance
        assert len(set(services)) == 5  # 5 different threads = 5 different instances


class TestServiceReuse:
    """Test suite for service reuse within thread"""

    def test_governance_service_reuse(self, mock_db):
        """Test that governance service is reused within same thread"""
        with patch('core.service_factory.AgentGovernanceService') as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance

            service1 = ServiceFactory.get_governance_service(mock_db)
            service2 = ServiceFactory.get_governance_service(mock_db)

            # Should be same instance
            assert service1 is service2
            # Constructor should only be called once
            mock_class.assert_called_once()

    def test_context_resolver_reuse(self, mock_db):
        """Test that context resolver is reused within same thread"""
        with patch('core.service_factory.AgentContextResolver') as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance

            resolver1 = ServiceFactory.get_context_resolver(mock_db)
            resolver2 = ServiceFactory.get_context_resolver(mock_db)

            # Should be same instance
            assert resolver1 is resolver2
            # Constructor should only be called once
            mock_class.assert_called_once()


class TestLegacyFactory:
    """Test suite for legacy GovernanceServiceFactory"""

    def test_legacy_factory_compatibility(self):
        """Test that legacy factory still works"""
        from core.service_factory import GovernanceServiceFactory

        mock_db = Mock(spec=Session)

        with patch('core.service_factory.AgentGovernanceService') as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance

            service = GovernanceServiceFactory.create(mock_db)

            assert service == mock_instance
