"""Mini-app integrations rename (mcp_servers → integrations) + alias tests.

WS1 contract: ``integrations`` is the preferred field; ``mcp_servers`` is a
deprecated alias that still works. The field routes through
ExternalIntegrationService (NOT MCP), so the name now reflects reality.
"""
import pytest


class TestManifestFieldNames:
    def test_integrations_accepted(self):
        from core.mini_app_service import validate_manifest
        validate_manifest({
            "declared_scopes": ["*"],
            "integrations": [{"service": "notion", "action": "search", "params": {"q": "x"}}],
        })

    def test_mcp_servers_still_accepted_as_alias(self):
        from core.mini_app_service import validate_manifest
        # Legacy alias must still validate (backward-compat)
        validate_manifest({
            "declared_scopes": ["*"],
            "mcp_servers": [{"service": "notion", "action": "search", "params": {}}],
        })

    def test_bad_integrations_shape_rejected(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "integrations": [{"service": ""}]})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "integrations": "notalist"})

    def test_integrations_takes_precedence_over_mcp_servers(self):
        """If both are present, integrations wins (mcp_servers ignored)."""
        from core.mini_app_service import validate_manifest
        # both present — integrations is valid, mcp_servers is invalid shape;
        # validation should pass using integrations (ignoring the bad alias)
        validate_manifest({
            "declared_scopes": ["*"],
            "integrations": [],
            "mcp_servers": [{"service": ""}],  # would fail if validated
        })


class TestInjectorReadsIntegrations:
    @pytest.mark.asyncio
    async def test_inject_reads_integrations_field(self, monkeypatch):
        from core.mini_app_service import _inject_integration_sources

        class FakeExt:
            async def execute_integration_action(self, integration_id, action_id, params, credentials):
                return type("R", (), {"data": {"ok": True}})()

        monkeypatch.setattr(
            "core.external_integration_service.ExternalIntegrationService", FakeExt
        )
        out = await _inject_integration_sources(
            {"integrations": [{"service": "notion", "action": "search", "params": {}}]},
            "t1", "w1", "ag1",
        )
        assert out == {"notion": {"ok": True}}

    @pytest.mark.asyncio
    async def test_inject_falls_back_to_mcp_servers(self, monkeypatch):
        from core.mini_app_service import _inject_integration_sources

        class FakeExt:
            async def execute_integration_action(self, integration_id, action_id, params, credentials):
                return {"data": {"pages": []}}

        monkeypatch.setattr(
            "core.external_integration_service.ExternalIntegrationService", FakeExt
        )
        # No 'integrations' key → falls back to legacy 'mcp_servers'
        out = await _inject_integration_sources(
            {"mcp_servers": [{"service": "slack", "action": "list", "params": {}}]},
            "t1", "w1", "ag1",
        )
        assert out == {"slack": {"pages": []}}
