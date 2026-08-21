"""RED tests — Round 80e: @require_governance kwarg drift (audit §4 item 5).

`perform_governance_check` called `AgentGovernanceService.can_perform_action(
agent_id=…, action_complexity=…, action_name=…)` — but the service signature
is `(agent_id, action_type, require_approval=False, chain_id=None)`. The
unexpected kwargs raised TypeError on EVERY governed request; the decorator's
broad `except Exception` converted it to a 500 "Internal error". Routes only
worked when their feature flag disabled governance entirely (early return),
i.e. governance has been silently OFF for every wrapped route.

Fix under test: the async decorator path uses the service's own guidance —
`await can_perform_action_async(agent_id=…, action_type=action_name)` — which
also enforces spend budgets (the reason the async variant exists).

Covers: happy-path allowed, STUDENT blocked 403, INTERN 202 proposal,
paused-agent denial, and the flag-disabled early return.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.api_governance import perform_governance_check
from core.models import AgentRegistry


def _agent(maturity="AUTONOMOUS", status="ACTIVE"):
    agent = MagicMock(spec=AgentRegistry)
    agent.id = "agent-1"
    agent.maturity_level = maturity
    agent.status = status
    return agent


def _request():
    req = MagicMock()
    req.state = MagicMock()
    req.state.user_id = "user-1"
    req.url.path = "/api/data-ingestion/sync/zoho"
    req.method = "POST"
    req.path_params = {}
    req.headers = {}
    req.query_params = {}
    return req


@pytest.fixture
def governed_env():
    """Patch resolver + governance service; feature flag ON."""
    with patch("core.api_governance.FeatureFlags.should_enforce_governance",
               return_value=True), \
         patch("core.api_governance.AgentContextResolver") as resolver_cls, \
         patch("core.api_governance.AgentGovernanceService") as gov_cls:
        resolver = resolver_cls.return_value
        resolver.resolve_agent_for_request = AsyncMock(return_value=(_agent(), "default"))
        governance = gov_cls.return_value
        governance.can_perform_action_async = AsyncMock(
            return_value={"allowed": True})
        yield resolver, governance


@pytest.mark.asyncio
async def test_allowed_agent_passes_without_typeerror(governed_env):
    """RED: the drifted kwargs raised TypeError -> 500. GREEN: decision flows."""
    resolver, governance = governed_env
    governance.can_perform_action_async = AsyncMock(
        return_value={"allowed": True, "reason": "ok"})

    # must not raise
    await perform_governance_check(
        db=MagicMock(), agent_id="agent-1", request=_request(),
        action_complexity=2, action_name="trigger_sync", feature="data_ingestion",
    )
    governance.can_perform_action_async.assert_awaited_once_with(
        agent_id="agent-1", action_type="trigger_sync")


@pytest.mark.asyncio
async def test_student_agent_blocked_403(governed_env):
    resolver, governance = governed_env
    resolver.resolve_agent_for_request = AsyncMock(
        return_value=(_agent(maturity="STUDENT"), "default"))
    # the real service denies complexity > 1 for STUDENT agents
    governance.can_perform_action_async = AsyncMock(
        return_value={"allowed": False, "reason": "STUDENT agents are read-only"})

    with pytest.raises(HTTPException) as exc:
        await perform_governance_check(
            db=MagicMock(), agent_id="agent-1", request=_request(),
            action_complexity=2, action_name="trigger_sync")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_intern_agent_gets_202_proposal(governed_env):
    resolver, governance = governed_env
    resolver.resolve_agent_for_request = AsyncMock(
        return_value=(_agent(maturity="INTERN"), "default"))
    # the real service routes INTERN complexity>1 to human approval
    governance.can_perform_action_async = AsyncMock(
        return_value={"allowed": False, "requires_human_approval": True,
                      "reason": "INTERN requires approval"})

    proposal = MagicMock()
    proposal.id = "prop-1"
    with patch("core.proposal_service.ProposalService") as ps_cls:
        ps_cls.return_value.create_action_proposal = AsyncMock(return_value=proposal)
        with pytest.raises(HTTPException) as exc:
            await perform_governance_check(
                db=MagicMock(), agent_id="agent-1", request=_request(),
                action_complexity=2, action_name="trigger_sync")
    assert exc.value.status_code == 202
    assert exc.value.detail["proposal_id"] == "prop-1"


@pytest.mark.asyncio
async def test_paused_agent_denied_by_service(governed_env):
    resolver, governance = governed_env
    resolver.resolve_agent_for_request = AsyncMock(
        return_value=(_agent(status="PAUSED"), "default"))
    governance.can_perform_action_async = AsyncMock(
        return_value={"allowed": False, "reason": "Agent is PAUSED"})

    with pytest.raises(HTTPException) as exc:
        await perform_governance_check(
            db=MagicMock(), agent_id="agent-1", request=_request(),
            action_complexity=2, action_name="trigger_sync")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_feature_flag_disabled_short_circuits(governed_env):
    """Flag off -> no governance call at all (existing behavior, pinned)."""
    resolver, governance = governed_env
    with patch("core.api_governance.FeatureFlags.should_enforce_governance",
               return_value=False):
        await perform_governance_check(
            db=MagicMock(), agent_id="agent-1", request=_request(),
            action_complexity=2, action_name="trigger_sync", feature="data_ingestion")
    governance.can_perform_action_async.assert_not_awaited()
