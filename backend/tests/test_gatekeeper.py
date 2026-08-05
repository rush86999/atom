"""
P3 — Gatekeeper Service tests (G3).

Per-service policy shim in front of every outbound integration call: OAuth
token refresh, rate limiting, response field masking, audit logging, mutation
approval (HITL). Fills the real missing ``middleware/governance_middleware.py``
module so the swallowed import at ``universal_integration_service.py:10``
becomes live and ``check_action_risk`` actually runs.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# Module import + live wiring
# ============================================================================

class TestModuleLiveness:
    def test_governance_middleware_importable(self):
        """The previously-swallowed import must resolve cleanly."""
        from middleware.governance_middleware import governance_middleware  # noqa

    def test_universal_integration_service_sees_live_middleware(self):
        """universal_integration_service must import the REAL module now (not None)."""
        import integrations.universal_integration_service as uis
        assert uis.governance_middleware is not None, (
            "governance_middleware is still None — the import at uis.py:10 is "
            "still swallowing an ImportError. The module must now exist."
        )

    def test_check_action_risk_method_exists(self):
        from middleware.governance_middleware import governance_middleware
        assert hasattr(governance_middleware, "check_action_risk")


# ============================================================================
# check_action_risk behaviour
# ============================================================================

class TestCheckActionRisk:
    @pytest.mark.asyncio
    async def test_allowed_by_default(self):
        """An action with no special policy and under rate limit is allowed."""
        from middleware.governance_middleware import governance_middleware
        result = await governance_middleware.check_action_risk(
            "slack", action="post_message", params={"channel": "x"},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_rate_limit_rejection(self, monkeypatch):
        """When the rate limiter says 'limited', the action is blocked."""
        from middleware import governance_middleware as gm

        async def _limited(connector_id, limit=None, window=60):
            return (True, 0)  # limited=True
        monkeypatch.setattr(gm.rate_limiter, "is_rate_limited", _limited)

        result = await gm.governance_middleware.check_action_risk(
            "slack", action="post_message", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is False
        assert "rate" in result.get("reason", "").lower() or "limit" in result.get("reason", "").lower()

    @pytest.mark.asyncio
    async def test_mutation_approval_escalates_to_hitl(self, monkeypatch):
        """A mutation action configured for approval must escalate (pause)."""
        from middleware import governance_middleware as gm

        # Inject a config requiring approval for slack/post_message.
        monkeypatch.setattr(
            gm.governance_middleware,
            "_config",
            {"slack": {"require_approval_for": ["post_message"]}},
        )

        async def _fake_intervention(*args, **kwargs):
            return {"status": "PAUSED", "action_id": "hitl-1", "requires_approval": True}
        monkeypatch.setattr(
            gm.intervention_service, "request_intervention", _fake_intervention
        )

        result = await gm.governance_middleware.check_action_risk(
            "slack", action="post_message", params={"channel": "x"},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is False
        assert result.get("intervention_id") == "hitl-1"
        assert "review" in result.get("reason", "").lower() or "approval" in result.get("reason", "").lower()

    @pytest.mark.asyncio
    async def test_audit_logged_per_call(self, monkeypatch):
        """Each checked action writes an audit record."""
        from middleware import governance_middleware as gm
        calls = []
        monkeypatch.setattr(gm.governance_middleware, "_write_audit",
                            lambda **kw: calls.append(kw))
        await gm.governance_middleware.check_action_risk(
            "slack", action="post_message", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert len(calls) == 1
        assert calls[0]["service"] == "slack"
        assert calls[0]["action"] == "post_message"


# ============================================================================
# Response field masking
# ============================================================================

class TestResponseMasking:
    def test_mask_fields_strips_credentials(self):
        from middleware.governance_middleware import mask_response_fields
        resp = {
            "access_token": "secret",
            "data": {"token": "x", "name": "ok"},
            "public": "visible",
        }
        masked = mask_response_fields(resp, masked_fields={"access_token", "token"})
        assert masked["access_token"] == "***"
        assert masked["data"]["token"] == "***"
        assert masked["data"]["name"] == "ok"
        assert masked["public"] == "visible"

    def test_mask_fields_no_config(self):
        from middleware.governance_middleware import mask_response_fields
        resp = {"access_token": "secret"}
        # No masked_fields -> unchanged.
        assert mask_response_fields(resp, masked_fields=set())["access_token"] == "secret"


# ============================================================================
# Config override
# ============================================================================

class TestConfigOverride:
    def test_configure_changes_behavior(self):
        from middleware.governance_middleware import governance_middleware
        governance_middleware.configure(
            "custom_svc",
            {"masked_fields": {"api_key"}, "require_approval_for": {"delete"}},
        )
        assert governance_middleware._get("custom_svc", "masked_fields", set()) == {"api_key"}
        assert governance_middleware._get("custom_svc", "require_approval_for", set()) == {"delete"}
        # Defaults still apply for unconfigured services.
        assert governance_middleware._get("other_svc", "masked_fields", set()) == set()

    def test_mask_response_uses_provider_config(self):
        from middleware.governance_middleware import governance_middleware
        governance_middleware.configure("svc_x", {"masked_fields": {"secret_field"}})
        masked = governance_middleware.mask_response(
            "svc_x", {"secret_field": "v", "public": "p"}
        )
        assert masked["secret_field"] == "***"
        assert masked["public"] == "p"
