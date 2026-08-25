"""RED tests — data-ingestion `agent_id` is a memory-scoping beneficiary,
NOT a governance actor.

Round 80s added `?agent_id=` to POST /api/data-ingestion/sync/{id} and
/enable-sync meaning "tag ingested records FOR this employee's memory". But
the generic @require_governance decorator treats ANY agent_id as the ACTING
agent — so a human admin seeding their STUDENT employee's memory gets 403
"Agent not authorized for this action / required INTERN": the exact journey
the parameter was built for is impossible from the UI.

Fix under test: `require_governance(..., agent_id_is_scope=True)` opts a route
out of query/body actor extraction — only genuine agent channels
(`request.state.agent_id`, `X-Agent-ID` header) still count as actors. All
other governed routes keep today's behavior unchanged.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from core.api_governance import extract_agent_id, require_governance


def _http_request(query="agent_id=student-agent", agent_header=None):
    """A REAL Starlette Request (the decorator isinstance-checks)."""
    headers = [(b"x-agent-id", agent_header.encode())] if agent_header else []
    return Request(scope={
        "type": "http",
        "method": "POST",
        "path": "/api/data-ingestion/sync/zoho",
        "query_string": query.encode() if query else b"",
        "headers": headers,
    })


class _StubRequest:
    """Duck-typed request for extract_agent_id unit tests: real attribute
    semantics so hasattr() probes behave like Starlette's."""

    def __init__(self, query=None, headers=None, state_agent=None):
        self.query_params = query or {}
        self.headers = headers or {}
        if state_agent is not None:
            self.state = SimpleNamespace(agent_id=state_agent)
        else:
            # No agent_id attribute at all (mirrors a plain user request)
            self.state = SimpleNamespace(user_id="user-1")


# ---------------------------------------------------------------------------
# extract_agent_id semantics
# ---------------------------------------------------------------------------

def test_query_agent_id_still_default_actor_source():
    """Regression: existing routes keep query-param actor extraction."""
    req = _StubRequest(query={"agent_id": "agt-1"})
    assert extract_agent_id(req) == "agt-1"


def test_scope_mode_ignores_query_param():
    req = _StubRequest(query={"agent_id": "agt-1"})
    assert extract_agent_id(req, include_query_body=False) is None


def test_scope_mode_still_honors_header_and_state():
    assert extract_agent_id(
        _StubRequest(state_agent="agt-state"), include_query_body=False
    ) == "agt-state"
    assert extract_agent_id(
        _StubRequest(query={"agent_id": "agt-1"}, headers={"X-Agent-ID": "agt-header"}),
        include_query_body=False,
    ) == "agt-header"


# ---------------------------------------------------------------------------
# Decorator opt-out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scoped_route_does_not_gate_on_beneficiary_maturity():
    """RED: STUDENT beneficiary must not 403 a human-triggered sync."""
    calls = []

    @require_governance(
        action_complexity=2,
        action_name="trigger_sync",
        feature="data_ingestion",
        agent_id_is_scope=True,
    )
    async def route(request=None, db=None, agent_id=None):
        calls.append(agent_id)
        return {"ok": True}

    request = _http_request()

    with patch("core.api_governance.perform_governance_check",
               new=AsyncMock()) as gov_check:
        result = await route(request=request, db=MagicMock(),
                             agent_id="student-agent")

    assert result == {"ok": True}
    assert calls == ["student-agent"]
    gov_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_scoped_route_still_gates_genuine_agent_actor():
    """An agent-channel caller (header) on a scope-mode route is still gated."""

    @require_governance(
        action_complexity=2,
        action_name="trigger_sync",
        feature="data_ingestion",
        agent_id_is_scope=True,
    )
    async def route(request=None, db=None):
        return {"ok": True}

    request = _http_request(agent_header="student-agent")

    with patch("core.api_governance.FeatureFlags.should_enforce_governance",
               return_value=True), \
         patch("core.api_governance.AgentContextResolver") as resolver_cls, \
         patch("core.api_governance.AgentGovernanceService") as gov_cls, \
         patch("core.api_governance.FeatureFlags.is_emergency_bypass_active",
               return_value=False):
        resolver_cls.return_value.resolve_agent_for_request = AsyncMock(
            return_value=(SimpleNamespace(id="student-agent",
                                          maturity_level="STUDENT"), {})
        )
        gov_cls.return_value.can_perform_action_async = AsyncMock(
            return_value={"allowed": False}
        )
        with pytest.raises(HTTPException) as exc:
            await route(request=request, db=MagicMock())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_default_decorator_unchanged_query_param_gates():
    """Regression: without the opt-out, query ?agent_id= still gates."""

    @require_governance(action_complexity=2, action_name="trigger_sync")
    async def route(request=None, db=None):
        return {"ok": True}

    request = _http_request()

    with patch("core.api_governance.FeatureFlags.should_enforce_governance",
               return_value=True), \
         patch("core.api_governance.AgentContextResolver") as resolver_cls, \
         patch("core.api_governance.AgentGovernanceService") as gov_cls, \
         patch("core.api_governance.FeatureFlags.is_emergency_bypass_active",
               return_value=False):
        resolver_cls.return_value.resolve_agent_for_request = AsyncMock(
            return_value=(SimpleNamespace(id="student-agent",
                                          maturity_level="STUDENT"), {})
        )
        gov_cls.return_value.can_perform_action_async = AsyncMock(
            return_value={"allowed": False}
        )
        with pytest.raises(HTTPException) as exc:
            await route(request=request, db=MagicMock())
    assert exc.value.status_code == 403
