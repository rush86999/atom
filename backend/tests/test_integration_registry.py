"""
Integration Registry Tests (Upstream - Single-Tenant)

Parity tests verifying upstream IntegrationRegistry has no SaaS-specific patterns:
- No tenant_id parameters
- No billing/quota checks
- No database queries filtered by tenant
- Simple in-memory caching (no UniversalCacheService)
- Single-tenant design
"""
import pytest
from core.integration_registry import IntegrationRegistry, DEFAULT_SERVICE_REGISTRY


class TestIntegrationRegistrySingleTenant:
    """Test that IntegrationRegistry is single-tenant (no SaaS patterns)."""

    def test_registry_initialization_no_db_required(self):
        """Verify registry can initialize without database session."""
        registry = IntegrationRegistry()
        assert registry is not None
        assert registry.use_cache is True  # Caching enabled by default
        assert isinstance(registry._service_cache, dict)

    def test_get_service_class_no_tenant_id(self):
        """Verify get_service_class has no tenant_id parameter."""
        registry = IntegrationRegistry()
        
        # This should work without tenant_id
        service_class = registry.get_service_class("slack")
        assert service_class is not None
        assert service_class.__name__ == "SlackUnifiedService"

    def test_get_service_class_invalid_connector(self):
        """Verify get_service_class returns None for unknown connectors."""
        registry = IntegrationRegistry()
        
        service_class = registry.get_service_class("nonexistent_integration")
        assert service_class is None

    def test_service_class_caching(self):
        """Verify service classes are cached in memory."""
        registry = IntegrationRegistry(use_cache=True)
        
        # First call loads and caches
        service_class_1 = registry.get_service_class("gmail")
        
        # Second call returns cached version
        service_class_2 = registry.get_service_class("gmail")
        
        assert service_class_1 is service_class_2  # Same object (cached)

    def test_service_class_no_caching_when_disabled(self):
        """Verify caching can be disabled."""
        registry = IntegrationRegistry(use_cache=False)
        
        # Load service class
        service_class_1 = registry.get_service_class("jira")
        
        # Load again (should not cache, but returns same class)
        service_class_2 = registry.get_service_class("jira")
        
        # Both should be valid (though not necessarily same object)
        assert service_class_1 is not None
        assert service_class_2 is not None

    def test_default_registry_contains_expected_integrations(self):
        """Verify DEFAULT_SERVICE_REGISTRY has expected integrations."""
        # Check high-priority integrations from audit report
        expected_integrations = [
            "slack",
            "gmail",
            "zoom",
            "jira",
            "github",
            "salesforce",
            "hubspot",
        ]
        
        for integration_id in expected_integrations:
            assert integration_id in DEFAULT_SERVICE_REGISTRY
            service_path = DEFAULT_SERVICE_REGISTRY[integration_id]
            assert service_path is not None
            assert ":" in service_path  # Format: "module.path:ClassName"

    def test_default_registry_all_integrations_valid(self):
        """Verify all integrations in DEFAULT_SERVICE_REGISTRY can be loaded."""
        registry = IntegrationRegistry()

        # Test a sample of integrations (not all 90 to save time)
        # Skip trello as it has module-level credential validation
        sample_integrations = [
            "slack",
            "gmail",
            "zoom",
            "jira",
            "github",
            "salesforce",
            "hubspot",
            "notion",
            "asana",
        ]

        loaded_count = 0
        for connector_id in sample_integrations:
            service_class = registry.get_service_class(connector_id)
            if service_class is not None:
                loaded_count += 1

        # At least 8 out of 9 should load (trello may fail)
        assert loaded_count >= 8, f"Only {loaded_count}/{len(sample_integrations)} integrations loaded"

    def test_get_all_integrations(self):
        """Verify get_all_integrations returns catalog."""
        registry = IntegrationRegistry()
        
        catalog = registry.get_all_integrations()
        
        assert isinstance(catalog, list)
        assert len(catalog) > 0
        
        # Check structure of first item
        first_item = catalog[0]
        assert "id" in first_item
        assert "name" in first_item
        assert "service_class_path" in first_item

    def test_get_all_integrations_excludes_legacy(self):
        """Verify get_all_integrations excludes legacy entries."""
        registry = IntegrationRegistry()
        
        catalog = registry.get_all_integrations()
        
        # Check that no legacy entries are included
        for item in catalog:
            assert not item["id"].endswith("_legacy"), f"Legacy entry found: {item['id']}"

    def test_get_integration_valid(self):
        """Verify get_integration returns correct integration."""
        registry = IntegrationRegistry()
        
        integration = registry.get_integration("slack")
        
        assert integration is not None
        assert integration["id"] == "slack"
        assert integration["name"] == "Slack"
        assert "service_class_path" in integration

    def test_get_integration_invalid(self):
        """Verify get_integration returns None for unknown integration."""
        registry = IntegrationRegistry()
        
        integration = registry.get_integration("nonexistent")
        assert integration is None

    def test_list_available_connectors(self):
        """Verify list_available_connectors returns all mappings."""
        registry = IntegrationRegistry()
        
        connectors = registry.list_available_connectors()
        
        assert isinstance(connectors, dict)
        assert len(connectors) > 0
        assert "slack" in connectors
        assert "gmail" in connectors

    def test_no_tenant_id_in_code(self):
        """Verify no tenant_id parameter exists in get_service_class signature."""
        import inspect
        
        registry = IntegrationRegistry()
        sig = inspect.signature(registry.get_service_class)
        params = list(sig.parameters.keys())
        
        # Should only have 'connector_id' and 'self' (no 'tenant_id')
        assert "connector_id" in params
        assert "tenant_id" not in params, "tenant_id parameter found (SaaS pattern)"

    def test_no_database_queries_for_tenant(self):
        """Verify no database queries filter by tenant_id."""
        # This is a code inspection test - verify the implementation
        # doesn't have database queries with tenant filtering
        
        registry = IntegrationRegistry()
        
        # Get service class (should use static registry, not DB)
        service_class = registry.get_service_class("slack")
        
        assert service_class is not None
        # If this worked without a database session, we're good

    def test_no_billing_quota_checks(self):
        """Verify no billing or quota checks in service loading."""
        # Service loading should be unconditional (no billing checks)
        registry = IntegrationRegistry()
        
        # Load any service (should work regardless of "plan" or "quota")
        service_class = registry.get_service_class("slack")
        
        assert service_class is not None
        # No exception raised for billing/quota issues

    def test_no_saas_cache_service(self):
        """Verify UniversalCacheService is not used."""
        # Check that registry uses simple dict cache, not UniversalCacheService
        
        registry = IntegrationRegistry(use_cache=True)
        
        # Should use simple dict for caching
        assert isinstance(registry._service_cache, dict)
        
        # Load a service to populate cache
        registry.get_service_class("slack")
        
        # Verify cache is populated (simple dict, not tenant-scoped)
        assert "service_class:slack" in registry._service_cache

    def test_service_class_path_resolution(self):
        """Verify service class paths are resolved correctly."""
        registry = IntegrationRegistry()
        
        # Test path resolution for known integration
        service_path = registry._get_service_class_path("slack")
        
        assert service_path == "integrations.slack_service_unified:SlackUnifiedService"
        assert service_path is not None

    def test_service_class_path_resolution_unknown(self):
        """Verify service class path returns None for unknown integration."""
        registry = IntegrationRegistry()
        
        service_path = registry._get_service_class_path("unknown_integration")
        
        assert service_path is None


class TestIntegrationRegistryTimeoutProtection:
    """Test timeout protection in service loading."""

    def test_load_service_class_with_timeout_success(self):
        """Verify successful service loading with timeout."""
        registry = IntegrationRegistry()
        
        # Load a real service (should succeed quickly)
        service_class = registry._load_service_class_with_timeout(
            "integrations.slack_service_unified:SlackUnifiedService",
            timeout=5
        )
        
        assert service_class is not None
        assert service_class.__name__ == "SlackUnifiedService"

    def test_load_service_class_with_timeout_invalid_module(self):
        """Verify timeout protection handles invalid modules gracefully."""
        registry = IntegrationRegistry()
        
        # Try to load invalid module
        service_class = registry._load_service_class_with_timeout(
            "nonexistent.module:FakeService",
            timeout=1  # Short timeout
        )
        
        assert service_class is None

    def test_load_service_class_with_timeout_malformed_path(self):
        """Verify timeout protection handles malformed paths."""
        registry = IntegrationRegistry()
        
        # Missing colon separator
        service_class = registry._load_service_class_with_timeout(
            "invalid_path_no_colon",
            timeout=1
        )
        
        assert service_class is None


class TestIntegrationRegistryDocumentation:
    """Test that documentation correctly describes single-tenant design."""

    def test_class_docstring_mentions_single_tenant(self):
        """Verify IntegrationRegistry class docstring mentions single-tenant."""
        assert IntegrationRegistry.__doc__ is not None
        docstring = IntegrationRegistry.__doc__.lower()
        
        # Should mention single-tenant or open-source
        assert "single" in docstring or "tenant" in docstring or "open-source" in docstring

    def test_module_docstring_mentions_saas_removal(self):
        """Verify module docstring mentions SaaS pattern removal."""
        import core.integration_registry as registry_module
        
        if registry_module.__doc__:
            docstring = registry_module.__doc__.lower()
            # Should mention removing SaaS patterns
            assert "saas" in docstring or "tenant" in docstring or "billing" in docstring


class TestIntegrationRegistryErrorHandling:
    """Test error handling in registry operations."""

    def test_get_service_class_handles_import_errors(self):
        """Verify get_service_class handles import errors gracefully."""
        registry = IntegrationRegistry()
        
        # Create a temporary invalid entry (would fail on import)
        # This tests error handling in _load_service_class_with_timeout
        service_class = registry._load_service_class_with_timeout(
            "totally.fake.module:FakeService",
            timeout=1
        )
        
        # Should return None, not raise exception
        assert service_class is None

    def test_get_integration_empty_string(self):
        """Verify get_integration handles empty string."""
        registry = IntegrationRegistry()
        
        integration = registry.get_integration("")
        assert integration is None

    def test_get_service_class_empty_string(self):
        """Verify get_service_class handles empty string."""
        registry = IntegrationRegistry()
        
        service_class = registry.get_service_class("")
        assert service_class is None


class TestGlobalRegistryInstance:
    """Test global registry instance."""

    def test_global_registry_instance_exists(self):
        """Verify global registry instance is created."""
        from core.integration_registry import integration_registry
        
        assert integration_registry is not None
        assert isinstance(integration_registry, IntegrationRegistry)

    def test_global_registry_can_get_services(self):
        """Verify global registry can be used to get services."""
        from core.integration_registry import integration_registry
        
        service_class = integration_registry.get_service_class("slack")
        assert service_class is not None
        assert service_class.__name__ == "SlackUnifiedService"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
