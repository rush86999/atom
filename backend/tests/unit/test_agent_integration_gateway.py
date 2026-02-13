"""
Unit tests for AgentIntegrationGateway

Tests cover:
- Gateway initialization
- Integration registration
- Agent routing
- Transformation layer
- Integration with external systems (Slack, Asana, etc.)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import Dict, Any, List

from core.agent_integration_gateway import (
    AgentIntegrationGateway,
    ActionType,
    agent_integration_gateway
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_registry():
    """Mock service registry"""
    registry = MagicMock()
    registry.get_service = MagicMock()
    registry.register_service = MagicMock()
    return registry


@pytest.fixture
def mock_integration_clients():
    """Mock integration clients"""
    clients = {
        "slack": AsyncMock(),
        "asana": AsyncMock(),
        "jira": AsyncMock(),
        "notion": AsyncMock()
    }
    return clients


@pytest.fixture
def sample_gateway_config():
    """Sample gateway configuration"""
    return {
        "max_retries": 3,
        "timeout": 30,
        "enabled_integrations": ["slack", "asana", "jira"]
    }


@pytest.fixture
def gateway_instance():
    """Create AgentIntegrationGateway instance"""
    return AgentIntegrationGateway()


# =============================================================================
# TEST CLASS: GatewayInit
# =============================================================================

class TestGatewayInit:
    """Tests for AgentIntegrationGateway initialization"""

    def test_gateway_init(self, gateway_instance):
        """Verify gateway initializes with correct defaults"""
        assert gateway_instance.services is not None
        assert isinstance(gateway_instance.services, dict)
        assert len(gateway_instance.services) > 0

    def test_gateway_has_required_services(self, gateway_instance):
        """Verify gateway has all required services"""
        required_services = ["slack", "asana", "meta", "whatsapp", "shopify"]

        for service in required_services:
            assert service in gateway_instance.services

    def test_gateway_singleton_instance(self):
        """Verify global gateway instance exists"""
        from core.agent_integration_gateway import agent_integration_gateway

        assert agent_integration_gateway is not None
        assert isinstance(agent_integration_gateway, AgentIntegrationGateway)


# =============================================================================
# TEST CLASS: IntegrationRegistration
# =============================================================================

class TestIntegrationRegistration:
    """Tests for integration registration and management"""

    def test_slack_service_registered(self, gateway_instance):
        """Verify Slack service is registered"""
        assert "slack" in gateway_instance.services
        assert gateway_instance.services["slack"] is not None

    def test_asana_service_registered(self, gateway_instance):
        """Verify Asana service is registered"""
        assert "asana" in gateway_instance.services

    def test_shopify_service_registered(self, gateway_instance):
        """Verify Shopify service is registered"""
        assert "shopify" in gateway_instance.services

    def test_meta_service_registered(self, gateway_instance):
        """Verify Meta service is registered"""
        assert "meta" in gateway_instance.services

    def test_ecommerce_service_registered(self, gateway_instance):
        """Verify Ecommerce service is registered"""
        assert "ecommerce" in gateway_instance.services

    def test_marketing_service_registered(self, gateway_instance):
        """Verify Marketing service is registered"""
        assert "marketing" in gateway_instance.services

    def test_all_expected_integrations(self, gateway_instance):
        """Verify all expected integrations are present"""
        expected = [
            "meta", "ecommerce", "marketing", "whatsapp", "docs",
            "shopify", "discord", "teams", "telegram", "google_chat",
            "slack", "openclaw"
        ]

        for integration in expected:
            assert integration in gateway_instance.services


# =============================================================================
# TEST CLASS: AgentRouting
# =============================================================================

class TestAgentRouting:
    """Tests for agent request routing to integrations"""

    @pytest.mark.asyncio
    async def test_execute_action_send_message_slack(self, gateway_instance):
        """Verify send_message action routes to Slack"""
        with patch.object(gateway_instance, '_handle_send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "success"}

            result = await gateway_instance.execute_action(
                ActionType.SEND_MESSAGE,
                "slack",
                {"recipient_id": "channel_123", "content": "Hello"}
            )

            assert result["status"] == "success"
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_action_send_message_whatsapp(self, gateway_instance):
        """Verify send_message action routes to WhatsApp"""
        with patch.object(gateway_instance, '_handle_send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "success"}

            result = await gateway_instance.execute_action(
                ActionType.SEND_MESSAGE,
                "whatsapp",
                {"recipient_id": "+1234567890", "content": "Test"}
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_action_update_record(self, gateway_instance):
        """Verify update_record action routes correctly"""
        with patch.object(gateway_instance, '_handle_update_record', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = {"status": "success"}

            result = await gateway_instance.execute_action(
                ActionType.UPDATE_RECORD,
                "shopify",
                {"record_id": "product_123", "data": {"price": 99.99}}
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_action_fetch_insights(self, gateway_instance):
        """Verify fetch_insights action routes correctly"""
        with patch.object(gateway_instance, '_handle_fetch_insights', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"status": "success", "data": []}

            result = await gateway_instance.execute_action(
                ActionType.FETCH_INSIGHTS,
                "meta",
                {"account_id": "act_123"}
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_action_unsupported_type(self, gateway_instance):
        """Verify unsupported action type returns error"""
        result = await gateway_instance.execute_action(
            ActionType.SYNC_DATA,  # Not implemented
            "slack",
            {}
        )

        assert result["status"] == "error"


# =============================================================================
# TEST CLASS: TransformationLayer
# =============================================================================

class TestTransformationLayer:
    """Tests for data transformation between agent and integration formats"""

    @pytest.mark.asyncio
    async def test_handle_send_message_slack_transform(self, gateway_instance):
        """Verify Slack message transformation"""
        with patch('integrations.slack_enhanced_service.slack_enhanced_service') as mock_slack:
            mock_slack.send_message = AsyncMock(return_value={"ok": True})

            result = await gateway_instance._handle_send_message(
                "slack",
                {
                    "recipient_id": "C12345",
                    "content": "Test message",
                    "workspace_id": "workspace_123"
                }
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_handle_send_message_meta_transform(self, gateway_instance):
        """Verify Meta message transformation"""
        with patch('integrations.meta_business_service.meta_business_service') as mock_meta:
            mock_meta.send_message = AsyncMock(return_value=True)

            result = await gateway_instance._handle_send_message(
                "meta",
                {
                    "recipient_id": "user_123",
                    "content": "Test",
                    "platform": "messenger"
                }
            )

            assert result["status"] == "success" or result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_handle_update_record_ecommerce_transform(self, gateway_instance):
        """Verify ecommerce record update transformation"""
        with patch('integrations.ecommerce_unified_service.ecommerce_service') as mock_ecom:
            mock_ecom.update_inventory = AsyncMock()

            result = await gateway_instance._handle_update_record(
                "amazon",
                {
                    "record_id": "product_123",
                    "data": {"quantity": 100}
                }
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_handle_fetch_logic_transform(self, gateway_instance):
        """Verify logic fetching transformation"""
        result = await gateway_instance._handle_fetch_logic(
            "docs",
            {
                "query": "business rules",
                "workspace_id": "workspace_123"
            }
        )

        assert result["status"] == "success"
        assert "logic" in result


# =============================================================================
# TEST CLASS: ShopifyLifecycleActions
# =============================================================================

class TestShopifyActions:
    """Tests for Shopify-specific lifecycle actions"""

    @pytest.mark.asyncio
    async def test_shopify_get_customers(self, gateway_instance):
        """Verify Shopify get customers action"""
        with patch.object(gateway_instance, '_handle_shopify_customers', new_callable=AsyncMock) as mock_customers:
            mock_customers.return_value = {
                "status": "success",
                "data": [{"id": 1, "email": "test@example.com"}]
            }

            result = await gateway_instance.execute_action(
                ActionType.SHOPIFY_GET_CUSTOMERS,
                "shopify",
                {
                    "access_token": "token",
                    "shop": "test.myshopify.com"
                }
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_shopify_get_orders(self, gateway_instance):
        """Verify Shopify get orders action"""
        with patch.object(gateway_instance, '_handle_shopify_orders', new_callable=AsyncMock) as mock_orders:
            mock_orders.return_value = {
                "status": "success",
                "data": [{"id": 1, "total": "100.00"}]
            }

            result = await gateway_instance.execute_action(
                ActionType.SHOPIFY_GET_ORDERS,
                "shopify",
                {
                    "access_token": "token",
                    "shop": "test.myshopify.com"
                }
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_shopify_get_products(self, gateway_instance):
        """Verify Shopify get products action"""
        with patch.object(gateway_instance, '_handle_shopify_products', new_callable=AsyncMock) as mock_products:
            mock_products.return_value = {
                "status": "success",
                "data": [{"id": 1, "title": "Test Product"}]
            }

            result = await gateway_instance.execute_action(
                ActionType.SHOPIFY_GET_PRODUCTS,
                "shopify",
                {
                    "access_token": "token",
                    "shop": "test.myshopify.com"
                }
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_shopify_create_fulfillment(self, gateway_instance):
        """Verify Shopify create fulfillment action"""
        with patch.object(gateway_instance, '_handle_shopify_fulfillment', new_callable=AsyncMock) as mock_fulfill:
            mock_fulfill.return_value = {"status": "success", "data": {}}

            result = await gateway_instance.execute_action(
                ActionType.SHOPIFY_CREATE_FULFILLMENT,
                "shopify",
                {
                    "access_token": "token",
                    "shop": "test.myshopify.com",
                    "order_id": "123",
                    "location_id": "loc_1"
                }
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_shopify_get_analytics(self, gateway_instance):
        """Verify Shopify get analytics action"""
        with patch.object(gateway_instance, '_handle_shopify_analytics', new_callable=AsyncMock) as mock_analytics:
            mock_analytics.return_value = {
                "status": "success",
                "data": {"total_sales": 1000}
            }

            result = await gateway_instance.execute_action(
                ActionType.SHOPIFY_GET_ANALYTICS,
                "shopify",
                {
                    "access_token": "token",
                    "shop": "test.myshopify.com"
                }
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_shopify_manage_inventory(self, gateway_instance):
        """Verify Shopify manage inventory action"""
        with patch.object(gateway_instance, '_handle_shopify_inventory', new_callable=AsyncMock) as mock_inv:
            mock_inv.return_value = {
                "status": "success",
                "inventory": [],
                "locations": []
            }

            result = await gateway_instance.execute_action(
                ActionType.SHOPIFY_MANAGE_INVENTORY,
                "shopify",
                {
                    "access_token": "token",
                    "shop": "test.myshopify.com"
                }
            )

            assert result["status"] == "success"


# =============================================================================
# TEST CLASS: FormulaActions
# =============================================================================

class TestFormulaActions:
    """Tests for formula memory access and execution"""

    @pytest.mark.asyncio
    async def test_fetch_formulas(self, gateway_instance):
        """Verify formula fetching action"""
        with patch.object(gateway_instance, '_handle_fetch_formulas', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "status": "success",
                "formulas": [
                    {
                        "id": "formula_1",
                        "name": "Test Formula",
                        "expression": "x + y"
                    }
                ]
            }

            result = await gateway_instance.execute_action(
                ActionType.FETCH_FORMULAS,
                "docs",
                {
                    "query": "math formulas",
                    "domain": "finance",
                    "limit": 5
                }
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_apply_formula(self, gateway_instance):
        """Verify formula execution action"""
        with patch.object(gateway_instance, '_handle_apply_formula', new_callable=AsyncMock) as mock_apply:
            mock_apply.return_value = {
                "status": "success",
                "result": 42
            }

            result = await gateway_instance.execute_action(
                ActionType.APPLY_FORMULA,
                "docs",
                {
                    "formula_id": "formula_1",
                    "inputs": {"x": 40, "y": 2},
                    "agent_id": "agent_123"
                }
            )

            assert result["status"] == "success"


# =============================================================================
# TEST CLASS: ActionTypeEnum
# =============================================================================

class TestActionTypeEnum:
    """Tests for ActionType enum values"""

    def test_action_type_send_message(self):
        """Verify SEND_MESSAGE action type"""
        assert ActionType.SEND_MESSAGE.value == "send_message"

    def test_action_type_update_record(self):
        """Verify UPDATE_RECORD action type"""
        assert ActionType.UPDATE_RECORD.value == "update_record"

    def test_action_type_fetch_insights(self):
        """Verify FETCH_INSIGHTS action type"""
        assert ActionType.FETCH_INSIGHTS.value == "fetch_insights"

    def test_action_type_shopify_actions(self):
        """Verify Shopify action types"""
        assert ActionType.SHOPIFY_GET_CUSTOMERS.value == "shopify_get_customers"
        assert ActionType.SHOPIFY_GET_ORDERS.value == "shopify_get_orders"
        assert ActionType.SHOPIFY_GET_PRODUCTS.value == "shopify_get_products"


# =============================================================================
# ADDITIONAL TESTS
# =============================================================================

class TestGatewayEdgeCases:
    """Tests for edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_execute_action_exception_handling(self, gateway_instance):
        """Verify exceptions are handled gracefully"""
        result = await gateway_instance.execute_action(
            ActionType.SEND_MESSAGE,
            "nonexistent_platform",
            {}
        )

        # Should return error status, not raise exception
        assert "status" in result

    @pytest.mark.asyncio
    async def test_handle_send_message_fallback(self, gateway_instance):
        """Verify fallback handler for unknown platforms"""
        result = await gateway_instance._handle_send_message(
            "unknown_platform",
            {"recipient_id": "123", "content": "Test"}
        )

        # Should return success with note about legacy handler
        assert "status" in result

    @pytest.mark.asyncio
    async def test_formula_memory_not_configured(self, gateway_instance):
        """Verify behavior when formula memory is not configured"""
        with patch.object(gateway_instance, '_handle_fetch_formulas', new_callable=AsyncMock) as mock_fetch:
            # Simulate formula memory not available
            mock_fetch.return_value = {
                "status": "error",
                "message": "Formula memory not available"
            }

            result = await gateway_instance.execute_action(
                ActionType.FETCH_FORMULAS,
                "docs",
                {"query": "test"}
            )

            assert result["status"] == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
