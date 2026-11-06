"""Agent 3 independent probes for merged PR682 execution-scope freezing.

Independent review of the owner-merged #682 workflow approval-scope repair at
main ``3925cf359`` (runtime source ``068abd57a``, merge ``49d45c7f3``,
scheduled join #684 ``78d2e0ca8``). Adds only the cases the merged controls
do not cover:

1. the direct public execute route must discard a client-supplied
   ``_atom_execution_scope`` (the merged suite covers the schedule route
   only) — the durable execution and the governance approval must carry the
   authenticated caller's scope;
2. the pure helper contract: client key discarded before the authoritative
   scope is set, empty/whitespace scope is not invented, and resume inputs
   are stripped.

Reuses the merged suite's real public surfaces, real durable state manager,
real governance service and real ``_execute_step`` database leaf unchanged.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from core.database import get_db_session
from core.execution_state_manager import ExecutionStateManager
from core.models import HITLAction, WorkflowExecution
from core.workflow_engine import (
    EXECUTION_SCOPE_KEY,
    WorkflowEngine,
    freeze_execution_scope,
    strip_execution_scope,
)

from tests.test_workflow_public_approval_flow import (
    _app,
    _pending,
    _wait_status,
    public_world,
)


@pytest.mark.asyncio
async def test_execute_route_discards_client_supplied_scope(public_world):
    """A caller cannot smuggle a foreign execution scope through
    ``POST /workflows/{id}/execute`` input_data: the durable execution and
    the governance-created approval carry the authenticated caller's scope.

    The route's lone dict body parameter IS the input_data (FastAPI does not
    embed it), so the client key arrives at the top level where the freeze
    must discard it before setting the caller's authoritative scope."""
    state_manager = ExecutionStateManager()
    transport = httpx.ASGITransport(app=_app(public_world))
    with patch.object(WorkflowEngine, "_notify_workflow_paused",
                      new=lambda *a, **k: None):
        async with httpx.AsyncClient(
                transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/workflows/{public_world['workflow_id']}/execute",
                json={
                    "x": 1,
                    EXECUTION_SCOPE_KEY: {
                        "workspace_id": "workspace-foreign",
                        "tenant_id": "tenant-foreign",
                    },
                })
            assert response.status_code == 200, response.text
            execution_id = response.json()["execution_id"]

            paused = await _wait_status(state_manager, execution_id, "PAUSED")
            assert paused["steps"]["s1"]["status"] == "PAUSED"

            with get_db_session() as db:
                row = db.query(WorkflowExecution).filter(
                    WorkflowExecution.execution_id == execution_id).first()
                assert row is not None
                durable = row.input_data
                if isinstance(durable, str):
                    durable = json.loads(durable or "{}")
                assert durable["x"] == 1
                assert durable[EXECUTION_SCOPE_KEY] == {
                    "workspace_id": public_world["workspace_id"],
                    "tenant_id": public_world["tenant_id"],
                }

            # The approval is waiting in the caller's own scope — a smuggled
            # foreign scope would have moved the row out of this queue.
            pending = await _pending(client)
            assert len(pending) == 1, pending
            with get_db_session() as db:
                approval = db.query(HITLAction).filter(
                    HITLAction.id == pending[0]["id"]).first()
                assert approval.tenant_id == public_world["tenant_id"]
                assert approval.workspace_id == public_world["workspace_id"]


def test_freeze_and_strip_helpers_discard_client_key_and_invent_nothing():
    foreign = {
        "workspace_id": "workspace-foreign",
        "tenant_id": "tenant-foreign",
    }
    frozen = freeze_execution_scope(
        {"x": 1, EXECUTION_SCOPE_KEY: foreign},
        workspace_id="ws-real", tenant_id=None)
    assert frozen["x"] == 1
    assert frozen[EXECUTION_SCOPE_KEY] == {"workspace_id": "ws-real"}

    # Missing or whitespace-only scope values are not invented.
    assert freeze_execution_scope(None, workspace_id="  ") == {}
    assert freeze_execution_scope({"x": 1}) == {"x": 1}

    # Resume inputs are stripped of the reserved key.
    assert strip_execution_scope(
        {"x": 1, EXECUTION_SCOPE_KEY: foreign}) == {"x": 1}
    assert strip_execution_scope(None) == {}
