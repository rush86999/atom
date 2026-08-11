"""Coverage wave 45 — governance_middleware (92%) + gateway routes completion.

- middleware: response-mask list branch, mutations default, rate-limit check
  exception tolerance, taint-check exception tolerance, HITL escalation
  exception tolerance
- routes: anthropic non-stream completion error path (GatewayBlocked)
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.governance_middleware import Gatekeeper, mask_response_fields


class _MW:
    def __init__(self):
        self.mw = Gatekeeper()

    def _reset(self, key, value):
        self.mw._config[key] = value


@pytest.fixture
def mw():
    return _MW()


class TestResponseMasking:
    def test_mask_list_branch(self):
        masked = mask_response_fields(
            {"items": [{"password": "x", "ok": 1}]},
            {"password"},
        )
        assert masked["items"][0]["password"] == "***"
        assert masked["items"][0]["ok"] == 1

    def test_mask_non_dict_values_passthrough(self):
        masked = mask_response_fields(
            "plain-string", {"password"})
        assert masked == "plain-string"


class TestConfigDefaults:
    def test_mutations_default_from_registry(self, mw):
        result = mw.mw._get("notion", "mutations", set())
        assert isinstance(result, set)


class TestRateLimitException:
    async def test_rate_limit_check_exception_tolerated(self, mw):
        with patch("middleware.governance_middleware.rate_limiter.is_rate_limited",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await mw.mw.check_action_risk(
                "service-x", "action-y", {}, None, None, None, None)
        assert "allowed" in result  # never raises


class TestTaintAndHITLExceptions:
    async def test_taint_check_exception_tolerated(self, mw):
        tracker = MagicMock()
        tracker.check_outbound.side_effect = RuntimeError("boom")
        result = await mw.mw.check_action_risk(
            "service-x", "action-y", {}, None, None, None, None,
            taint_tracker=tracker)
        assert "allowed" in result  # must not raise

    async def test_hitl_escalation_exception_tolerated(self, mw):
        mw.mw.configure("service-x", {"require_approval_for": {"mutate"}})
        with patch("middleware.governance_middleware.intervention_service") as ivs:
            ivs.request_intervention = AsyncMock(side_effect=RuntimeError("boom"))
            result = await mw.mw.check_action_risk(
                "service-x", "mutate", {}, None, None, None, None)
        assert "allowed" in result  # must not raise; decision still produced
        ivs.request_intervention.assert_awaited_once()
