"""ORCH-01 complete approval-binding matrix.

Each case starts from a real durable ``HITLAction`` created by the production
checkpoint consumer, removes or contradicts exactly one binding field through
the existing reviewed modification path, and then resumes through a fresh
orchestrator. No malformed review may release the controlled effect.
"""
from __future__ import annotations

import asyncio

import pytest

from core.intervention_service import intervention_service
from tests.test_orch01_real_checkpoint_contract import (
    APPROVER_ID,
    _approval_step,
    _compiled,
    _execute,
    _orchestrator,
    _row_for_execution,
    governance_pending,
    real_db,
)


@pytest.mark.parametrize(
    "changed_field",
    [
        "execution_id",
        "workflow_id",
        "definition_id",
        "definition_digest",
        "step_id",
        "guarded_step",
        "guarded_digest",
        "input_digest",
        "workspace_id",
        "tenant_id",
    ],
)
@pytest.mark.parametrize("change", ["missing", "wrong"])
def test_server_required_review_rejects_partial_or_contradictory_identity(
        real_db, governance_pending, changed_field, change):
    compiled = _compiled()
    effects = []
    execution_id = f"exec-review-binding-{changed_field}-{change}"
    orch, definition = _orchestrator(compiled, effects)
    _execute(orch, definition, execution_id, {"amount": 100})
    row = _row_for_execution(real_db, execution_id)
    assert row and row.status == "pending"

    params = dict(row.params)
    if change == "wrong":
        params[changed_field] = "wrong-reviewed-identity"
    else:
        params.pop(changed_field, None)
    approved = asyncio.run(intervention_service.approve_intervention(
        row.id, APPROVER_ID, modified_params=params))
    assert approved["success"] is True, approved

    fresh, _ = _orchestrator(compiled, effects)
    result = asyncio.run(fresh.resume_workflow(
        execution_id, _approval_step(compiled)["step_id"]))
    assert effects == [], (changed_field, effects, result.results)
