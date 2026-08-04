"""Regression tests: DataIntelligenceEngine must thread the caller's
user context through to UniversalIntegrationService.execute.

Previously ``_get_platform_data`` called ``execute`` with no context, so
``user_id`` was always empty and ``execute`` raised
``ValueError("user_id required for non-system agents")``. The broad
``except`` swallowed it and returned ``[]`` — meaning connected
integrations (salesforce/jira/asana/...) never synced into the
Intelligence dashboards, and ``/api/intelligence/refresh`` reported
``platforms_synced=0`` even when tokens were configured.
"""
from unittest.mock import patch

from ai.data_intelligence import DataIntelligenceEngine, PlatformType


async def test_get_platform_data_threads_user_context_to_integration_service():
    engine = DataIntelligenceEngine()
    captured = {}

    async def fake_execute(service, action, params, context=None):
        captured["service"] = service
        captured["action"] = action
        captured["params"] = params
        captured["context"] = context
        return {"status": "success", "result": []}

    with patch("integrations.universal_integration_service.UniversalIntegrationService") as mock_cls:
        mock_cls.return_value.execute = fake_execute
        result = await engine._get_platform_data(
            PlatformType.SALESFORCE,
            {"user_id": "user-123", "workspace_id": "default", "tenant_id": "default"},
        )

    assert captured["service"] == "salesforce"
    assert captured["action"] == "list"
    # The caller's user identity must reach the integration service, otherwise
    # it cannot resolve the per-user OAuth token.
    assert captured["context"].get("user_id") == "user-123"
    assert captured["context"].get("workspace_id") == "default"
    assert captured["context"].get("tenant_id") == "default"
    assert result == []


async def test_get_platform_data_without_user_context_degrades_to_empty():
    engine = DataIntelligenceEngine()
    captured = {}

    async def fake_execute(service, action, params, context=None):
        captured["context"] = context
        raise ValueError("user_id required for non-system agents")

    with patch("integrations.universal_integration_service.UniversalIntegrationService") as mock_cls:
        mock_cls.return_value.execute = fake_execute
        # Must not propagate; the broad guard in _get_platform_data returns [].
        result = await engine._get_platform_data(PlatformType.JIRA, {"agent_id": "sys-agent"})

    assert result == []
