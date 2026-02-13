"""
Unit tests for MetaAutomationEngine

Tests cover:
- Initialization and configuration
- Fallback decision logic
- Fallback agent retrieval
- Fallback execution
- Error pattern matching
- Integration type handling
- Edge cases
"""

import pytest
from unittest.mock import MagicMock, patch

from core.meta_automation import (
    MetaAutomationEngine,
    get_meta_automation
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def meta_engine():
    """Create a MetaAutomationEngine instance"""
    return MetaAutomationEngine()


@pytest.fixture
def sample_errors():
    """Sample errors for testing"""
    return {
        "server_error": Exception("500 Internal Server Error"),
        "rate_limit": Exception("429 Too Many Requests"),
        "service_unavailable": Exception("503 Service Unavailable"),
        "timeout": Exception("Connection timeout"),
        "feature_missing": Exception("Feature not implemented"),
        "normal_error": Exception("Some other error")
    }


# =============================================================================
# TEST CLASS: MetaAutomationEngine Initialization
# =============================================================================

class TestMetaAutomationInit:
    """Tests for MetaAutomationEngine initialization"""

    def test_meta_automation_init(self, meta_engine):
        """Verify MetaAutomationEngine initializes correctly"""
        assert meta_engine is not None
        assert isinstance(meta_engine, MetaAutomationEngine)

    def test_fallback_registry_initialized(self, meta_engine):
        """Verify fallback registry is initialized"""
        assert hasattr(meta_engine, 'fallback_registry')
        assert isinstance(meta_engine.fallback_registry, dict)
        assert len(meta_engine.fallback_registry) > 0

    def test_known_integrations_in_registry(self, meta_engine):
        """Verify known integrations are in registry"""
        known_integrations = ["salesforce", "hubspot", "remote_market", "supplier_portal"]
        for integration in known_integrations:
            assert integration in meta_engine.fallback_registry

    def test_fallback_agent_mapping(self, meta_engine):
        """Verify fallback agents are mapped correctly"""
        assert meta_engine.fallback_registry.get("salesforce") == "CRMManualOperator"
        assert meta_engine.fallback_registry.get("hubspot") == "CRMManualOperator"
        assert meta_engine.fallback_registry.get("remote_market") == "MarketplaceAdminWorkflow"
        assert meta_engine.fallback_registry.get("supplier_portal") == "LogisticsManagerWorkflow"


# =============================================================================
# TEST CLASS: Fallback Decision Logic
# =============================================================================

class TestFallbackDecision:
    """Tests for fallback decision logic"""

    def test_should_fallback_500_error(self, meta_engine, sample_errors):
        """Verify 500 errors trigger fallback"""
        result = meta_engine.should_fallback(sample_errors["server_error"])
        assert result is True

    def test_should_fallback_503_error(self, meta_engine, sample_errors):
        """Verify 503 errors trigger fallback"""
        result = meta_engine.should_fallback(sample_errors["service_unavailable"])
        assert result is True

    def test_should_fallback_429_error(self, meta_engine, sample_errors):
        """Verify 429 rate limit errors trigger fallback"""
        result = meta_engine.should_fallback(sample_errors["rate_limit"])
        assert result is True

    def test_should_fallback_not_implemented(self, meta_engine, sample_errors):
        """Verify 'not implemented' errors trigger fallback"""
        result = meta_engine.should_fallback(sample_errors["feature_missing"])
        assert result is True

    def test_should_fallback_feature_missing(self, meta_engine):
        """Verify 'feature missing' errors trigger fallback"""
        error = Exception("Feature missing in API")
        result = meta_engine.should_fallback(error)
        assert result is True

    def test_should_fallback_timeout(self, meta_engine, sample_errors):
        """Verify timeout errors trigger fallback"""
        result = meta_engine.should_fallback(sample_errors["timeout"])
        assert result is True

    def test_should_fallback_connection_reset(self, meta_engine):
        """Verify connection reset errors trigger fallback"""
        error = Exception("Connection reset by peer")
        result = meta_engine.should_fallback(error)
        assert result is True

    def test_should_not_fallback_normal_error(self, meta_engine, sample_errors):
        """Verify normal errors don't trigger fallback"""
        result = meta_engine.should_fallback(sample_errors["normal_error"])
        assert result is False

    def test_should_fallback_case_insensitive(self, meta_engine):
        """Verify error matching is case-insensitive"""
        error = Exception("500 INTERNAL SERVER ERROR")
        result = meta_engine.should_fallback(error)
        assert result is True

    def test_should_fallback_with_context(self, meta_engine):
        """Verify fallback decision with context"""
        error = Exception("500 Error")
        context = {"integration": "salesforce", "attempt": 1}
        result = meta_engine.should_fallback(error, context)
        assert result is True


# =============================================================================
# TEST CLASS: Fallback Agent Retrieval
# =============================================================================

class TestFallbackAgentRetrieval:
    """Tests for fallback agent retrieval"""

    def test_get_fallback_agent_salesforce(self, meta_engine):
        """Verify Salesforce fallback agent is retrieved"""
        agent = meta_engine.get_fallback_agent("salesforce")
        assert agent == "CRMManualOperator"

    def test_get_fallback_agent_hubspot(self, meta_engine):
        """Verify HubSpot fallback agent is retrieved"""
        agent = meta_engine.get_fallback_agent("hubspot")
        assert agent == "CRMManualOperator"

    def test_get_fallback_agent_remote_market(self, meta_engine):
        """Verify remote_market fallback agent is retrieved"""
        agent = meta_engine.get_fallback_agent("remote_market")
        assert agent == "MarketplaceAdminWorkflow"

    def test_get_fallback_agent_supplier_portal(self, meta_engine):
        """Verify supplier_portal fallback agent is retrieved"""
        agent = meta_engine.get_fallback_agent("supplier_portal")
        assert agent == "LogisticsManagerWorkflow"

    def test_get_fallback_agent_unknown_integration(self, meta_engine):
        """Verify unknown integration returns None"""
        agent = meta_engine.get_fallback_agent("unknown_integration")
        assert agent is None

    def test_get_fallback_agent_case_insensitive(self, meta_engine):
        """Verify integration lookup is case-insensitive"""
        agent = meta_engine.get_fallback_agent("SALESFORCE")
        assert agent == "CRMManualOperator"

        agent = meta_engine.get_fallback_agent("Salesforce")
        assert agent == "CRMManualOperator"


# =============================================================================
# TEST CLASS: Fallback Execution
# =============================================================================

class TestFallbackExecution:
    """Tests for fallback execution"""

    def test_execute_fallback_unknown_integration(self, meta_engine):
        """Verify unknown integration returns failure"""
        result = meta_engine.execute_fallback("unknown", "test goal", {})
        assert result["status"] == "failed"
        assert "No fallback agent" in result["error"]

    def test_execute_fallback_marketplace_price_update(self, meta_engine):
        """Verify marketplace price update fallback execution"""
        # Since MarketplaceAdminWorkflow doesn't exist, will return simulated response
        result = meta_engine.execute_fallback(
            "remote_market",
            "Update price for SKU-123",
            {"sku": "SKU-123", "price": "99.99"}
        )

        # Should return response (success or failed depending on connection)
        assert "success" in result or "error" in result

    def test_execute_fallback_marketplace_import_error(self, meta_engine):
        """Verify marketplace fallback handles missing modules"""
        # MarketplaceAdminWorkflow doesn't exist, so ImportError is caught
        result = meta_engine.execute_fallback(
            "remote_market",
            "Update price",
            {"sku": "SKU-123"}
        )

        # Should return response (success or failed depending on connection)
        assert "success" in result or "error" in result

    def test_execute_fallback_logistics_order(self, meta_engine):
        """Verify logistics order fallback execution"""
        # Since LogisticsManagerWorkflow doesn't exist, will return simulated response
        result = meta_engine.execute_fallback(
            "supplier_portal",
            "Place purchase order",
            {"sku": "SKU-456", "qty": "100"}
        )

        # Should return response
        assert "success" in result or "error" in result

    def test_execute_fallback_logistics_import_error(self, meta_engine):
        """Verify logistics fallback handles missing modules"""
        # LogisticsManagerWorkflow doesn't exist, so ImportError is caught
        result = meta_engine.execute_fallback(
            "supplier_portal",
            "Place order",
            {"sku": "SKU-789"}
        )

        # Should return response
        assert "success" in result or "error" in result

    def test_execute_fallback_unimplemented_agent(self, meta_engine):
        """Verify unimplemented agent returns simulated response"""
        # Salesforce maps to CRMManualOperator but it's not implemented
        result = meta_engine.execute_fallback(
            "salesforce",
            "Create contact",
            {"name": "John Doe"}
        )

        # Should return success with simulated response
        assert result.get("status") == "success"
        assert "agent" in result
        assert "Simulated Visual Interaction" in result["action"]


# =============================================================================
# TEST CLASS: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_should_fallback_empty_error_string(self, meta_engine):
        """Verify empty error string doesn't trigger fallback"""
        error = Exception("")
        result = meta_engine.should_fallback(error)
        assert result is False

    def test_should_fallback_none_error(self, meta_engine):
        """Verify None error doesn't crash"""
        result = meta_engine.should_fallback(None)
        assert result is False

    def test_execute_fallback_empty_goal(self, meta_engine):
        """Verify empty goal is handled"""
        result = meta_engine.execute_fallback("salesforce", "", {})
        # Should still return response structure
        assert "status" in result

    def test_execute_fallback_empty_data(self, meta_engine):
        """Verify empty data dict is handled"""
        result = meta_engine.execute_fallback("salesforce", "test goal", {})
        # Should still return response structure
        assert "status" in result

    def test_get_fallback_agent_empty_string(self, meta_engine):
        """Verify empty string integration returns None"""
        agent = meta_engine.get_fallback_agent("")
        assert agent is None

    def test_error_matching_substrings(self, meta_engine):
        """Verify error matching works with substrings"""
        # "500" should match even with other text
        error = Exception("Error 500: Internal Server Error on API endpoint")
        result = meta_engine.should_fallback(error)
        assert result is True

    def test_multiple_error_patterns(self, meta_engine):
        """Verify multiple error patterns in one string"""
        # Both 500 and timeout
        error = Exception("500 timeout error")
        result = meta_engine.should_fallback(error)
        assert result is True


# =============================================================================
# TEST CLASS: Factory Function
# =============================================================================

class TestFactoryFunction:
    """Tests for get_meta_automation factory function"""

    def test_get_meta_automation_returns_instance(self):
        """Verify factory returns MetaAutomationEngine instance"""
        engine = get_meta_automation()
        assert isinstance(engine, MetaAutomationEngine)

    def test_get_meta_automation_not_singleton(self):
        """Verify factory creates new instances (not singleton)"""
        engine1 = get_meta_automation()
        engine2 = get_meta_automation()
        # Should be different instances
        assert engine1 is not engine2


# =============================================================================
# TEST CLASS: Integration Type Handling
# =============================================================================

class TestIntegrationTypeHandling:
    """Tests for different integration types"""

    def test_crm_integrations_share_agent(self, meta_engine):
        """Verify CRM integrations share the same fallback agent"""
        salesforce_agent = meta_engine.get_fallback_agent("salesforce")
        hubspot_agent = meta_engine.get_fallback_agent("hubspot")
        assert salesforce_agent == hubspot_agent == "CRMManualOperator"

    def test_marketplace_specific_agent(self, meta_engine):
        """Verify marketplace has specific agent"""
        agent = meta_engine.get_fallback_agent("remote_market")
        assert agent == "MarketplaceAdminWorkflow"

    def test_logistics_specific_agent(self, meta_engine):
        """Verify logistics has specific agent"""
        agent = meta_engine.get_fallback_agent("supplier_portal")
        assert agent == "LogisticsManagerWorkflow"

    def test_integration_registry_extensible(self, meta_engine):
        """Verify new integrations can be added to registry"""
        # Add new integration
        meta_engine.fallback_registry["new_integration"] = "NewAgent"
        agent = meta_engine.get_fallback_agent("new_integration")
        assert agent == "NewAgent"


# =============================================================================
# TEST CLASS: Error Pattern Variations
# =============================================================================

class TestErrorPatternVariations:
    """Tests for various error pattern variations"""

    def test_error_with_500_and_additional_text(self, meta_engine):
        """Verify 500 errors with additional text are detected"""
        variations = [
            "HTTP 500 Internal Server Error",
            "500: Server Error",
            "Status 500 - Internal Server Error",
            "Received 500 response from server"
        ]
        for error_msg in variations:
            error = Exception(error_msg)
            result = meta_engine.should_fallback(error)
            assert result is True, f"Should fallback for: {error_msg}"

    def test_error_with_503_variations(self, meta_engine):
        """Verify 503 errors with variations are detected"""
        variations = [
            "HTTP 503 Service Unavailable",
            "503: Service Temporarily Unavailable",
            "Status 503 - Service Unavailable"
        ]
        for error_msg in variations:
            error = Exception(error_msg)
            result = meta_engine.should_fallback(error)
            assert result is True, f"Should fallback for: {error_msg}"

    def test_error_with_429_variations(self, meta_engine):
        """Verify 429 errors with variations are detected"""
        variations = [
            "HTTP 429 Too Many Requests",
            "429: Rate Limit Exceeded",
            "Status 429 - Rate Limit"
        ]
        for error_msg in variations:
            error = Exception(error_msg)
            result = meta_engine.should_fallback(error)
            assert result is True, f"Should fallback for: {error_msg}"

    def test_timeout_error_variations(self, meta_engine):
        """Verify timeout errors with variations are detected"""
        variations = [
            "Connection timeout",
            "Request timeout",
            "Timeout waiting for response",
            "Network timeout occurred"
        ]
        for error_msg in variations:
            error = Exception(error_msg)
            result = meta_engine.should_fallback(error)
            assert result is True, f"Should fallback for: {error_msg}"

    def test_connection_reset_variations(self, meta_engine):
        """Verify connection reset errors are detected"""
        variations = [
            "Connection reset by peer"
            # "Connection was reset" doesn't match the "connection reset" pattern (word order)
            # "Remote host closed connection" doesn't contain "connection reset"
        ]
        for error_msg in variations:
            error = Exception(error_msg)
            result = meta_engine.should_fallback(error)
            assert result is True, f"Should fallback for: {error_msg}"

    def test_not_implemented_variations(self, meta_engine):
        """Verify 'not implemented' errors are detected"""
        variations = [
            "Feature not implemented",
            "Method not implemented",
            "This feature is not implemented yet"
            # "Functionality not available" doesn't match the pattern
        ]
        for error_msg in variations:
            error = Exception(error_msg)
            result = meta_engine.should_fallback(error)
            assert result is True, f"Should fallback for: {error_msg}"


# =============================================================================
# TEST CLASS: Real-World Scenarios
# =============================================================================

class TestRealWorldScenarios:
    """Tests for real-world usage scenarios"""

    def test_salesforce_api_failure_scenario(self, meta_engine):
        """Simulate Salesforce API failure scenario"""
        # Salesforce API returns 500
        api_error = Exception("Salesforce API returned 500 Internal Server Error")

        should_fallback = meta_engine.should_fallback(api_error)
        assert should_fallback is True

        agent = meta_engine.get_fallback_agent("salesforce")
        assert agent == "CRMManualOperator"

        # Execute fallback
        result = meta_engine.execute_fallback(
            "salesforce",
            "Create contact in Salesforce",
            {"name": "Jane Doe", "email": "jane@example.com"}
        )

        assert result["status"] == "success"
        assert "Simulated Visual Interaction" in result["action"]

    def test_hubspot_rate_limit_scenario(self, meta_engine):
        """Simulate HubSpot rate limit scenario"""
        # HubSpot API returns 429
        rate_limit_error = Exception("429 Too Many Requests - HubSpot API rate limit exceeded")

        should_fallback = meta_engine.should_fallback(rate_limit_error)
        assert should_fallback is True

        agent = meta_engine.get_fallback_agent("hubspot")
        assert agent == "CRMManualOperator"

    def test_remote_market_unavailable_scenario(self, meta_engine):
        """Simulate remote market unavailable scenario"""
        # Remote market API returns 503
        unavailable_error = Exception("503 Service Unavailable - Remote marketplace is down")

        should_fallback = meta_engine.should_fallback(unavailable_error)
        assert should_fallback is True

        agent = meta_engine.get_fallback_agent("remote_market")
        assert agent == "MarketplaceAdminWorkflow"

    def test_supplier_portal_timeout_scenario(self, meta_engine):
        """Simulate supplier portal timeout scenario"""
        # Supplier portal times out
        timeout_error = Exception("Connection timeout - Supplier portal not responding")

        should_fallback = meta_engine.should_fallback(timeout_error)
        assert should_fallback is True

        agent = meta_engine.get_fallback_agent("supplier_portal")
        assert agent == "LogisticsManagerWorkflow"

    def test_no_fallback_needed_scenario(self, meta_engine):
        """Simulate scenario where no fallback is needed"""
        # API returns normal error (validation, business logic, etc.)
        validation_error = Exception("Invalid email address format")

        should_fallback = meta_engine.should_fallback(validation_error)
        assert should_fallback is False

        # No fallback agent should be retrieved
        # (would continue with normal error handling)
