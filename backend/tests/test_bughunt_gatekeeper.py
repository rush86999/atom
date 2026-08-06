"""
Bug-hunt: gatekeeper / data-taint / blueprint sanitizer security sweep.

TDD red-green hunts for real bugs in the P3 gatekeeper middleware, P4 data
taint tracker, and P5 blueprint sanitizer:

  A. Gatekeeper service-name normalization — admin policy configured under one
     casing/whitespace variant is bypassed by calls under another.
  B. Response field masking is case-sensitive — credential keys with any other
     casing leak through unmasked.
  C. HITL escalation silently swallows intervention_service failures — a
     "paused" mutation with no intervention_id can never be approved.
  D. The HITL-paused path skips the audit record.
  E. rate_limit=0 (block all) is silently ignored by the underlying limiter.
  F. required_scopes config is never enforced.
  G. Taint PII false negatives: emails, phone numbers, IPs not classified.
  H. Credit-card classifier over-tags ANY 13-16 digit number (order IDs,
     timestamps) as restricted, blocking normal outbound flows.
  I. Blueprint sanitizer denylist bypasses: auth_token, apikey, x-api-key,
     private_key, bearer_token, Authorization keys leak on share/fork.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.blueprint_sanitizer import strip_credentials, has_credentials
from core.data_taint_tracker import classify_sensitivity, DataTaintTracker


# ============================================================================
# A. Gatekeeper — service-name normalization (policy bypass)
# ============================================================================

class TestServiceNameNormalization:
    @pytest.mark.asyncio
    async def test_approval_policy_configured_under_mixed_case_is_enforced(self, monkeypatch):
        """An admin configures 'Slack' but dispatch calls use 'slack' — the
        approval policy must still apply (fail-closed, no bypass)."""
        from middleware import governance_middleware as gm

        monkeypatch.setattr(
            gm.governance_middleware,
            "_config",
            {"Slack": {"require_approval_for": ["post_message"]}},
        )

        async def _fake_intervention(*args, **kwargs):
            return {"status": "PAUSED", "action_id": "hitl-1", "requires_approval": True}
        monkeypatch.setattr(
            gm.intervention_service, "request_intervention", _fake_intervention
        )

        result = await gm.governance_middleware.check_action_risk(
            "slack", action="post_message", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is False
        assert result.get("intervention_id") == "hitl-1"

    @pytest.mark.asyncio
    async def test_approval_policy_configured_with_whitespace_is_enforced(self, monkeypatch):
        """Config key ' slack ' must match calls with 'slack'."""
        from middleware import governance_middleware as gm

        monkeypatch.setattr(
            gm.governance_middleware,
            "_config",
            {" slack ": {"require_approval_for": ["post_message"]}},
        )

        async def _fake_intervention(*args, **kwargs):
            return {"status": "PAUSED", "action_id": "hitl-2", "requires_approval": True}
        monkeypatch.setattr(
            gm.intervention_service, "request_intervention", _fake_intervention
        )

        result = await gm.governance_middleware.check_action_risk(
            "slack", action="post_message", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is False

    def test_configure_normalizes_service_name(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("Slack ", {"masked_fields": {"access_token"}})
        assert gk._get("slack", "masked_fields", set()) == {"access_token"}
        assert gk._get("SLACK", "masked_fields", set()) == {"access_token"}


# ============================================================================
# B. Response field masking — case sensitivity
# ============================================================================

class TestMaskingCaseInsensitive:
    def test_mask_matches_key_case_insensitively(self):
        from middleware.governance_middleware import mask_response_fields
        resp = {
            "ACCESS_TOKEN": "leak-1",
            "AccessToken": "leak-2",
            "data": {"accessToken": "leak-3"},
            "public": "ok",
        }
        masked = mask_response_fields(resp, masked_fields={"access_token"})
        assert masked["ACCESS_TOKEN"] == "***"
        assert masked["AccessToken"] == "***"
        assert masked["data"]["accessToken"] == "***"
        assert masked["public"] == "ok"


# ============================================================================
# C+D. HITL escalation failure handling + audit
# ============================================================================

class TestHitlFailureHandling:
    @pytest.mark.asyncio
    async def test_intervention_service_silent_error_fails_closed(self, monkeypatch):
        """request_intervention returns {'status': 'ERROR'} without raising —
        the gatekeeper must NOT report a paused intervention with no
        intervention_id (a phantom pause that can never be approved)."""
        from middleware import governance_middleware as gm

        monkeypatch.setattr(
            gm.governance_middleware,
            "_config",
            {"slack": {"require_approval_for": ["post_message"]}},
        )

        async def _failing_intervention(*args, **kwargs):
            return {"status": "ERROR", "message": "db down"}
        monkeypatch.setattr(
            gm.intervention_service, "request_intervention", _failing_intervention
        )

        result = await gm.governance_middleware.check_action_risk(
            "slack", action="post_message", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is False
        assert result.get("intervention_id") is None
        assert result.get("paused") is not True
        assert "unavailable" in result.get("reason", "").lower() or "failed" in result.get("reason", "").lower()

    @pytest.mark.asyncio
    async def test_paused_mutation_is_audited(self, monkeypatch):
        """Every checked call is audited — including the HITL-paused path."""
        from middleware import governance_middleware as gm

        monkeypatch.setattr(
            gm.governance_middleware,
            "_config",
            {"slack": {"require_approval_for": ["post_message"]}},
        )

        async def _fake_intervention(*args, **kwargs):
            return {"status": "PAUSED", "action_id": "hitl-3", "requires_approval": True}
        monkeypatch.setattr(
            gm.intervention_service, "request_intervention", _fake_intervention
        )

        calls = []
        monkeypatch.setattr(gm.governance_middleware, "_write_audit",
                            lambda **kw: calls.append(kw))
        await gm.governance_middleware.check_action_risk(
            "slack", action="post_message", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert len(calls) == 1
        assert calls[0]["service"] == "slack"
        assert calls[0]["allowed"] is False


# ============================================================================
# E. Rate limit 0 must block everything
# ============================================================================

class TestRateLimitZero:
    @pytest.mark.asyncio
    async def test_configured_rate_limit_zero_blocks_all(self, monkeypatch):
        from middleware import governance_middleware as gm
        monkeypatch.setattr(
            gm.governance_middleware,
            "_config",
            {"svc_block": {"rate_limit": 0}},
        )
        result = await gm.governance_middleware.check_action_risk(
            "svc_block", action="read", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is False
        assert "rate" in result.get("reason", "").lower() or "limit" in result.get("reason", "").lower()


# ============================================================================
# F. required_scopes enforcement
# ============================================================================

class TestRequiredScopes:
    @pytest.mark.asyncio
    async def test_missing_required_scope_blocks(self, monkeypatch):
        """A service with configured required_scopes must fail closed when the
        caller cannot prove the scope."""
        from middleware import governance_middleware as gm
        monkeypatch.setattr(
            gm.governance_middleware,
            "_config",
            {"svc_scope": {"required_scopes": ["billing.write"]}},
        )
        result = await gm.governance_middleware.check_action_risk(
            "svc_scope", action="create", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is False
        assert "scope" in result.get("reason", "").lower()

    @pytest.mark.asyncio
    async def test_present_required_scope_allows(self, monkeypatch):
        from middleware import governance_middleware as gm
        monkeypatch.setattr(
            gm.governance_middleware,
            "_config",
            {"svc_scope": {"required_scopes": ["billing.write"]}},
        )
        result = await gm.governance_middleware.check_action_risk(
            "svc_scope", action="create", params={},
            agent_id="a1", workspace_id="ws1",
            scopes={"billing.write"},
        )
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_no_scope_policy_allows_without_scopes(self, monkeypatch):
        """Unconfigured services are unaffected by the new enforcement."""
        from middleware import governance_middleware as gm
        result = await gm.governance_middleware.check_action_risk(
            "plain_svc", action="read", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is True


# ============================================================================
# G. Taint PII false negatives
# ============================================================================

class TestTaintPiiGaps:
    def test_email_is_restricted(self):
        assert classify_sensitivity("forward this to jane.doe@example.com") == "restricted"

    def test_phone_number_is_restricted(self):
        assert classify_sensitivity("call 415-555-0100 for details") == "restricted"

    def test_ip_address_is_restricted(self):
        assert classify_sensitivity("server at 10.0.2.15 internal") == "restricted"

    def test_pii_in_dict_observe_is_restricted(self):
        tracker = DataTaintTracker(run_id="r")
        tracker.observe({"recipient": "jane@example.com"}, source="d1")
        assert "restricted" in tracker.observed_labels

    def test_luhn_credit_card_still_restricted(self):
        assert classify_sensitivity("card 4111-1111-1111-1111 expires 12/25") == "restricted"


# ============================================================================
# H. Taint over-tagging — numeric IDs are not credit cards
# ============================================================================

class TestTaintOverTagging:
    def test_order_number_not_credit_card(self):
        assert classify_sensitivity("invoice #1234567890123456 for order") == "internal"

    def test_long_timestamp_not_credit_card(self):
        assert classify_sensitivity("generated at 123456789012345") == "internal"

    def test_order_number_does_not_block_outbound(self):
        tracker = DataTaintTracker(run_id="r")
        tracker.observe("invoice #1234567890123456 for order", source="d1")
        decision = tracker.check_outbound(destination="external", service="slack")
        assert decision["allowed"] is True


# ============================================================================
# I. Blueprint sanitizer denylist bypasses
# ============================================================================

class TestBlueprintDenylistBypass:
    def test_strips_token_key_variants(self):
        obj = {
            "auth_token": "1",
            "bot_token": "2",
            "apikey": "3",
            "x-api-key": "4",
            "private_key": "5",
            "bearer_token": "6",
            "Authorization": "7",
        }
        assert strip_credentials(obj) == {}

    def test_has_credentials_detects_variants(self):
        assert has_credentials({"auth_token": "1"}) is True
        assert has_credentials({"apikey": "2"}) is True
        assert has_credentials({"x-api-key": "3"}) is True

    def test_nested_variant_keys_stripped(self):
        obj = {"conn": {"auth_token": "1"}, "items": [{"private_key": "2"}]}
        out = strip_credentials(obj)
        assert out == {"conn": {}, "items": [{}]}

    def test_non_credential_keys_untouched(self):
        obj = {"name": "x", "config": {"timeout": 30}, "url": "https://example.com"}
        assert strip_credentials(obj) == obj
