# -*- coding: utf-8 -*-
"""Coverage wave 73 — core/api_governance (decorator + helpers).

This module was never imported by any existing test file (0% baseline).
Covers: ActionComplexity.get_required_maturity mapping, require_governance
wrapper branches (request/http_request lookup, missing request/db skip,
emergency bypass, user-initiated passthrough, agent-gated enforcement),
extract_agent_id sources (state/query/header/body), perform_governance_check
(feature-flag off, 404 agent, INTERN proposal 202, STUDENT 403, default 403,
success, 500 fallback), convenience decorators and the testing helper.

Fully mocked (FeatureFlags, AgentContextResolver, AgentGovernanceService,
core.auth.get_current_user_from_request, ProposalService). Zero LLM spend,
no network, no real DB.
"""
import pytest
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, Request, status
from starlette.requests import Request as StarletteRequest

from core.api_governance import (
    ActionComplexity,
    check_governance_for_testing,
    extract_agent_id,
    perform_governance_check,
    require_browser_governance,
    require_canvas_governance,
    require_device_governance,
    require_financial_governance,
    require_governance,
)


class _State:
    """Request-state stand-in: missing attributes raise AttributeError (like
    starlette's State) instead of auto-creating MagicMock attrs."""

    def __init__(self, **values):
        self._values = values

    def __getattr__(self, name):
        if name in self._values:
            return self._values[name]
        raise AttributeError(name)


def make_starlette_request(**state_overrides):
    """Real starlette Request with mutable state (exercises the `request`
    kwarg branch of the wrapper). Missing state attrs raise AttributeError,
    matching production behavior."""
    request = StarletteRequest(
        scope={
            "type": "http",
            "method": "POST",
            "path": "/api/test",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 5555),
        }
    )
    for key, value in state_overrides.items():
        setattr(request.state, key, value)
    return request


def make_mock_request(agent_id=None, query=None, headers=None, body=None):
    """Plain mock request exercising the `http_request` kwarg branch."""
    request = MagicMock()
    request.state = _State(agent_id=agent_id) if agent_id else _State()
    request.query_params.get = lambda k: (query or {}).get(k)
    request.headers.get = lambda k, default=None: (headers or {}).get(k, default)
    request._json = body
    request.path_params = {"canvas_id": "canvas-9"}
    request.url.path = "/api/test"
    request.method = "POST"
    return request


# ============================================================================
# ActionComplexity
# ============================================================================

class TestActionComplexity:
    @pytest.mark.parametrize("complexity,expected", [
        (1, "STUDENT"), (2, "INTERN"), (3, "SUPERVISED"), (4, "AUTONOMOUS"),
        (0, "AUTONOMOUS"), (99, "AUTONOMOUS"),
    ])
    def test_get_required_maturity(self, complexity, expected):
        assert ActionComplexity.get_required_maturity(complexity) == expected

    def test_constants(self):
        assert ActionComplexity.LOW == 1
        assert ActionComplexity.MODERATE == 2
        assert ActionComplexity.HIGH == 3
        assert ActionComplexity.CRITICAL == 4


# ============================================================================
# require_governance wrapper branches
# ============================================================================

class TestRequireGovernanceWrapper:
    @pytest.mark.asyncio
    async def test_missing_request_and_db_skips_check(self):
        called = []

        @require_governance(action_complexity=3, action_name="act")
        async def handler():
            called.append(True)
            return "ok"

        assert await handler() == "ok"
        assert called == [True]

    @pytest.mark.asyncio
    async def test_http_request_kwarg_is_used(self):
        """Endpoint params named `http_request` were silently skipped before
        Round 37; the wrapper must honor them."""
        request = make_mock_request(agent_id="agent-1")
        db = MagicMock()
        called = []

        @require_governance(action_complexity=2, action_name="act")
        async def handler(http_request, db):
            called.append((http_request, db))
            return "ok"

        with patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            result = await handler(http_request=request, db=db)

        assert result == "ok"
        check.assert_awaited_once()
        assert called == [(request, db)]

    @pytest.mark.asyncio
    async def test_emergency_bypass_skips_check(self):
        request = make_starlette_request(agent_id="agent-1")
        db = MagicMock()

        @require_governance(action_complexity=4, action_name="act")
        async def handler(request, db):
            return "ran"

        with patch(
            "core.api_governance.FeatureFlags.is_emergency_bypass_active",
            return_value=True,
        ), patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            result = await handler(request=request, db=db)

        assert result == "ran"
        check.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_agent_user_initiated_proceeds(self):
        request = make_starlette_request()
        db = MagicMock()

        @require_governance(action_complexity=2, action_name="act")
        async def handler(request, db):
            return "user-ok"

        with patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            result = await handler(request=request, db=db)

        assert result == "user-ok"
        check.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_agent_not_user_initiated_still_proceeds(self):
        """No agent_id + allow_user_initiated=False has no denial branch in
        the wrapper (documented behavior) — the handler still runs."""
        request = make_starlette_request()
        db = MagicMock()

        @require_governance(action_complexity=2, action_name="act", allow_user_initiated=False)
        async def handler(request, db):
            return "ok"

        with patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            result = await handler(request=request, db=db)

        assert result == "ok"
        check.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_agent_gated_check_passes_through(self):
        request = make_starlette_request(agent_id="agent-1")
        db = MagicMock()

        @require_governance(action_complexity=3, action_name="custom_action", feature="browser")
        async def handler(request, db):
            return "agent-ok"

        with patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            result = await handler(request=request, db=db)

        assert result == "agent-ok"
        check.assert_awaited_once()
        kwargs = check.await_args.kwargs
        assert kwargs["db"] is db
        assert kwargs["agent_id"] == "agent-1"
        assert kwargs["action_complexity"] == 3
        assert kwargs["action_name"] == "custom_action"
        assert kwargs["feature"] == "browser"

    @pytest.mark.asyncio
    async def test_default_action_name_is_function_name(self):
        request = make_starlette_request(agent_id="agent-1")
        db = MagicMock()

        @require_governance(action_complexity=1)
        async def my_route_handler(request, db):
            return "ok"

        with patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            await my_route_handler(request=request, db=db)

        assert check.await_args.kwargs["action_name"] == "my_route_handler"
        assert check.await_args.kwargs["feature"] is None


# ============================================================================
# extract_agent_id
# ============================================================================

class TestExtractAgentId:
    def test_from_state(self):
        request = make_starlette_request(agent_id="state-agent")
        assert extract_agent_id(request) == "state-agent"

    def test_from_query_params(self):
        request = make_mock_request(agent_id=None, query={"agent_id": "query-agent"})
        assert extract_agent_id(request) == "query-agent"

    def test_from_header(self):
        request = make_mock_request(agent_id=None, headers={"X-Agent-ID": "header-agent"})
        assert extract_agent_id(request) == "header-agent"

    def test_from_body_json(self):
        request = make_mock_request(agent_id=None, body={"agent_id": "body-agent"})
        assert extract_agent_id(request) == "body-agent"

    def test_body_exception_swallowed(self):
        class _BodyRaisingRequest(MagicMock):
            @property
            def _json(self):
                raise RuntimeError("unserializable")

        request = _BodyRaisingRequest()
        request.state = _State()
        request.query_params.get = lambda k: None
        request.headers.get = lambda k, default=None: None
        assert extract_agent_id(request) is None

    def test_no_agent_returns_none(self):
        request = make_mock_request(agent_id=None)
        assert extract_agent_id(request) is None


# ============================================================================
# perform_governance_check
# ============================================================================

def patch_governance_deps(agent, governance_result):
    resolver_cls = MagicMock()
    resolver = resolver_cls.return_value
    agent_obj = agent if agent is not None else None

    async def resolve(**kwargs):
        if agent_obj is None:
            return None, None
        return agent_obj, "by_request"

    resolver.resolve_agent_for_request = resolve

    gov_cls = MagicMock()
    gov_cls.return_value.can_perform_action.return_value = governance_result

    return [
        patch("core.api_governance.AgentContextResolver", resolver_cls),
        patch("core.api_governance.AgentGovernanceService", gov_cls),
    ]


@contextmanager
def governed(agent, result, extra_patches=()):
    """Enter all governance dependency patches + extras via ExitStack."""
    with ExitStack() as stack:
        for p in patch_governance_deps(agent, result):
            stack.enter_context(p)
        for p in extra_patches:
            stack.enter_context(p)
        yield


class TestPerformGovernanceCheck:
    @pytest.mark.asyncio
    async def test_feature_flag_disabled_returns_early(self):
        request = make_mock_request(agent_id="agent-1")
        with patch(
            "core.api_governance.FeatureFlags.should_enforce_governance",
            return_value=False,
        ), patch("core.api_governance.AgentContextResolver") as resolver:
            result = await perform_governance_check(
                db=MagicMock(), agent_id="agent-1", request=request,
                action_complexity=3, action_name="act", feature="browser",
            )
        assert result is None
        resolver.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_not_found_404(self):
        request = make_mock_request(agent_id="ghost")
        agent = MagicMock()
        agent.maturity_level = "AUTONOMOUS"
        with governed(agent=None, result=None):
            with pytest.raises(HTTPException) as excinfo:
                await perform_governance_check(
                    db=MagicMock(), agent_id="ghost", request=request,
                    action_complexity=2, action_name="act",
                )
        assert excinfo.value.status_code == 404

    @pytest.mark.asyncio
    async def test_user_id_from_request_state_threaded_to_resolver(self):
        """The phantom `get_current_user_from_request` import (which never
        existed in core.auth) previously ImportError'd every agent-gated
        request into a 500. The fixed path reads request.state.user_id and
        passes it to the resolver."""
        request = make_starlette_request(agent_id="agent-1", user_id="user-42")
        agent = MagicMock()
        agent.id = "agent-1"
        agent.maturity_level = "AUTONOMOUS"
        captured = {}

        async def resolve(**kwargs):
            captured.update(kwargs)
            return agent, "by_request"

        resolver_cls = MagicMock()
        resolver_cls.return_value.resolve_agent_for_request = resolve
        gov_cls = MagicMock()
        gov_cls.return_value.can_perform_action.return_value = {"allowed": True}

        with patch("core.api_governance.AgentContextResolver", resolver_cls), patch(
            "core.api_governance.AgentGovernanceService", gov_cls
        ):
            result = await perform_governance_check(
                db=MagicMock(), agent_id="agent-1", request=request,
                action_complexity=1, action_name="read",
            )
        assert result is None
        assert captured["user_id"] == "user-42"
        assert captured["requested_agent_id"] == "agent-1"

    @pytest.mark.asyncio
    async def test_missing_state_user_id_degrades_to_none(self):
        request = make_mock_request(agent_id="agent-1")
        agent = MagicMock()
        agent.id = "agent-1"
        agent.maturity_level = "AUTONOMOUS"
        captured = {}

        async def resolve(**kwargs):
            captured.update(kwargs)
            return agent, "by_request"

        resolver_cls = MagicMock()
        resolver_cls.return_value.resolve_agent_for_request = resolve
        gov_cls = MagicMock()
        gov_cls.return_value.can_perform_action.return_value = {"allowed": True}

        with patch("core.api_governance.AgentContextResolver", resolver_cls), patch(
            "core.api_governance.AgentGovernanceService", gov_cls
        ):
            result = await perform_governance_check(
                db=MagicMock(), agent_id="agent-1", request=request,
                action_complexity=1, action_name="read",
            )
        assert result is None
        assert captured["user_id"] is None

    @pytest.mark.asyncio
    async def test_intern_denied_creates_proposal_202(self):
        request = make_mock_request(agent_id="agent-1")
        agent = MagicMock()
        agent.id = "agent-1"
        agent.maturity_level = "INTERN"
        proposal = MagicMock()
        proposal.id = "proposal-77"
        proposal_cls = MagicMock(return_value=MagicMock(
            create_action_proposal=AsyncMock(return_value=proposal),
        ))

        with governed(agent, {"allowed": False}), patch(
            "core.proposal_service.ProposalService", proposal_cls
        ):
            with pytest.raises(HTTPException) as excinfo:
                await perform_governance_check(
                    db=MagicMock(), agent_id="agent-1", request=request,
                    action_complexity=2, action_name="submit",
                )

        assert excinfo.value.status_code == 202
        detail = excinfo.value.detail
        assert detail["proposal_id"] == "proposal-77"
        assert detail["required_maturity"] == "INTERN"

    @pytest.mark.asyncio
    async def test_student_denied_403(self):
        request = make_mock_request(agent_id="agent-1")
        agent = MagicMock()
        agent.id = "agent-1"
        agent.maturity_level = "STUDENT"

        with governed(agent, {"allowed": False}):
            with pytest.raises(HTTPException) as excinfo:
                await perform_governance_check(
                    db=MagicMock(), agent_id="agent-1", request=request,
                    action_complexity=2, action_name="submit",
                )

        assert excinfo.value.status_code == 403
        assert "STUDENT agents cannot perform" in excinfo.value.detail["message"]

    @pytest.mark.asyncio
    async def test_other_maturity_denied_403_default(self):
        request = make_mock_request(agent_id="agent-1")
        agent = MagicMock()
        agent.id = "agent-1"
        agent.maturity_level = "SUPERVISED"

        with governed(agent, {"allowed": False}):
            with pytest.raises(HTTPException) as excinfo:
                await perform_governance_check(
                    db=MagicMock(), agent_id="agent-1", request=request,
                    action_complexity=4, action_name="delete",
                )

        assert excinfo.value.status_code == 403
        assert excinfo.value.detail["message"] == "Agent not authorized for this action"

    @pytest.mark.asyncio
    async def test_allowed_passes(self):
        request = make_mock_request(agent_id="agent-1")
        agent = MagicMock()
        agent.id = "agent-1"
        agent.maturity_level = "AUTONOMOUS"

        with governed(agent, {"allowed": True}):
            result = await perform_governance_check(
                db=MagicMock(), agent_id="agent-1", request=request,
                action_complexity=4, action_name="delete",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_unexpected_exception_500(self):
        request = make_mock_request(agent_id="agent-1")
        resolver_cls = MagicMock()
        resolver_cls.return_value.resolve_agent_for_request = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        with patch("core.api_governance.AgentContextResolver", resolver_cls), patch(
            "core.api_governance.AgentGovernanceService", MagicMock()
        ):
            with pytest.raises(HTTPException) as excinfo:
                await perform_governance_check(
                    db=MagicMock(), agent_id="agent-1", request=request,
                    action_complexity=2, action_name="act",
                )
        assert excinfo.value.status_code == 500
        assert excinfo.value.detail == "Internal error"


# ============================================================================
# Convenience decorators + testing helper
# ============================================================================

class TestConvenienceDecorators:
    @pytest.mark.asyncio
    async def test_browser_governance(self):
        @require_browser_governance(action_complexity=ActionComplexity.HIGH)
        async def handler(request, db):
            return "browser"

        request = make_starlette_request(agent_id="agent-1")
        with patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            assert await handler(request=request, db=MagicMock()) == "browser"
        assert check.await_args.kwargs["feature"] == "browser"
        assert check.await_args.kwargs["action_name"] == "browser_automation"

    @pytest.mark.asyncio
    async def test_canvas_governance(self):
        @require_canvas_governance()
        async def handler(request, db):
            return "canvas"

        request = make_starlette_request(agent_id="agent-1")
        with patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            assert await handler(request=request, db=MagicMock()) == "canvas"
        assert check.await_args.kwargs["feature"] == "canvas"
        assert check.await_args.kwargs["action_name"] == "canvas_presentation"

    @pytest.mark.asyncio
    async def test_device_governance(self):
        @require_device_governance()
        async def handler(request, db):
            return "device"

        request = make_starlette_request(agent_id="agent-1")
        with patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            assert await handler(request=request, db=MagicMock()) == "device"
        assert check.await_args.kwargs["feature"] == "device"

    @pytest.mark.asyncio
    async def test_financial_governance(self):
        @require_financial_governance()
        async def handler(request, db):
            return "finance"

        request = make_starlette_request(agent_id="agent-1")
        with patch("core.api_governance.perform_governance_check", new_callable=AsyncMock) as check:
            assert await handler(request=request, db=MagicMock()) == "finance"
        assert check.await_args.kwargs["feature"] == "financial"
        assert check.await_args.kwargs["action_complexity"] == 4


class TestCheckGovernanceForTesting:
    @pytest.mark.asyncio
    async def test_success(self):
        gov_cls = MagicMock()
        gov_cls.return_value.can_perform_action.return_value = {"allowed": True}
        with patch("core.api_governance.AgentGovernanceService", gov_cls):
            result = await check_governance_for_testing(
                db=MagicMock(), agent_id="agent-1", action_complexity=2
            )
        assert result == {"allowed": True}
        gov_cls.return_value.can_perform_action.assert_called_once_with(
            agent_id="agent-1", action_complexity=2, action_name="test_action"
        )

    @pytest.mark.asyncio
    async def test_exception_returns_failure_dict(self):
        gov_cls = MagicMock()
        gov_cls.side_effect = RuntimeError("broken")
        with patch("core.api_governance.AgentGovernanceService", gov_cls):
            result = await check_governance_for_testing(
                db=MagicMock(), agent_id="agent-1", action_complexity=2
            )
        assert result["allowed"] is False
        assert "broken" in result["error"]
