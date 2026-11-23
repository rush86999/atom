import asyncio
from dataclasses import fields
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core import autonomy_policy
from core.models import ActionAutonomyRule, HITLAction
from core.task_classification import build_workflow_task_profile
from core.execution_state_manager import ExecutionStateManager
from core.workflow_engine import WorkflowEngine
from core.workflow_event_admission import (
    EventAdmissionReceipt, ReservationResult, WorkflowEvent, WorkflowEventAdmissionCoordinator,
)
from test_workflow_event_reservation import event_db


@pytest.mark.parametrize("legacy_author", [None, "synthetic-former-author", "user-a"])
@pytest.mark.parametrize("through_worker", [False, True])
def test_event_owner_saved_rule_pauses_before_any_action(event_db, monkeypatch, tmp_path, legacy_author, through_worker):
    source, event_type = "mail", "message.created"
    payload = {"topic": "invoice", "message_id": "synthetic"}
    condition = "${input.event.payload.topic} == 'invoice'"
    action = "forward_email"
    db_engine = create_engine(f"sqlite:///{tmp_path / 'policy.db'}")
    for table in (ActionAutonomyRule.__table__, HITLAction.__table__):
        table.create(db_engine)
    monkeypatch.setattr("core.workflow_engine.get_db_session", lambda: Session(db_engine))
    classified_owners = []
    def classify(material):
        result = build_workflow_task_profile(material)
        classified_owners.append(result.owner_user_id)
        return result
    monkeypatch.setattr("core.task_classification.build_workflow_task_profile", classify)
    if through_worker:
        from core.models import User
        from core import workflow_event_worker
        User.__table__.create(db_engine)
        with Session(db_engine) as db:
            db.add(User(id="user-a", email="synthetic@example.invalid", first_name="Synthetic",
                        last_name="Owner", role="member", status="active", is_active=True,
                        tenant_id="tenant-a", workspace_id="workspace-a"))
            db.commit()
        monkeypatch.setattr(workflow_event_worker, "_open_db", lambda: Session(db_engine))
    approval = Mock(return_value="synthetic-review")
    monkeypatch.setattr("core.workflow_engine.ServiceFactory.get_governance_service",
                        lambda *args, **kwargs: Mock(request_approval=approval))
    async def verify():
        identity = {"tenant_id": "tenant-a", "workspace_id": "workspace-a", "user_id": "user-a"}
        manager = ExecutionStateManager()
        event = WorkflowEvent(tenant_id="tenant-a", workspace_id="workspace-a", owner_id="user-a",
                              connection_id="synthetic-connection", source=source, event_type=event_type,
                              provider_event_id="synthetic-event", payload=payload)
        workflow = {"id": "synthetic-workflow", "enabled": True, "description": "Write a customer support response about an invoice",
                    "tenant_id": "tenant-a", "workspace_id": "workspace-a",
                    "event_subscriptions": [{
                        "id": "synthetic-sub", "enabled": True, "description": "Write a customer support response about an invoice",
                        "connection_id": event.connection_id, "source": source, "event_type": event_type,
                    }],
                    "nodes": [
                        {"id": "trigger", "type": "trigger", "config": {
                            "service": "synthetic", "action": "start",
                        }},
                        {"id": "effect", "type": "action", "config": {
                            "service": "synthetic", "action": action,
                            "parameters": {"destination": "saved-recipient", "record": "${input.event.payload}"},
                        }},
                    ],
                    "connections": [{"source": "trigger", "target": "effect", "condition": condition}]}

        if legacy_author is not None:
            workflow["created_by"] = legacy_author
        profile = build_workflow_task_profile(workflow)
        match = {key: [value] for key, value in profile.as_dict().items()
                 if key in ("difficulty", "category", "domain") and value is not None}
        assert match
        with Session(db_engine) as db:
            autonomy_policy.create_never_rule(
                db, identity["user_id"], name="Review these events", match=match,
                tenant_id=identity["tenant_id"], workspace_id=identity["workspace_id"],
            )
            correct = autonomy_policy.evaluate_task_admission(
                db, profile, user_id=identity["user_id"],
                tenant_id=identity["tenant_id"], workspace_id=identity["workspace_id"],
            )
            assert correct["outcome"] == "review"

        def receipt(state):
            data = state["context"]["_atom_event_admission"]
            properties = {f.name: data[f.name] for f in fields(EventAdmissionReceipt)
                          if f.name != "input_data"}
            return EventAdmissionReceipt(**properties, input_data=state["input_data"])

        async def lookup(key):
            state = await manager.get_execution_state(key.event_id)
            return receipt(state) if state else None

        async def reserve(candidate):
            state, created = await manager.reserve_event_execution(
                candidate.workflow_id, dict(candidate.input_data),
                execution_id=candidate.event_id, identity=identity,
                admission=candidate.admission_context,
            )
            return ReservationResult(receipt(state), created=created)

        coordinator = WorkflowEventAdmissionCoordinator(lookup, reserve)
        admitted = await coordinator.admit(event, workflow)
        state = await manager.get_execution_state(admitted.event_id)
        engine = WorkflowEngine()
        engine.state_manager = manager
        engine._publish_orchestration_event = Mock()
        engine._execute_step = AsyncMock(return_value={"status": "success", "result": {"ok": True}})
        monkeypatch.setattr("core.workflow_engine.get_connection_manager", lambda: AsyncMock())

        async def preflight(execution_id, state, workflow):
            return True

        if through_worker:
            import json
            from core import workflow_endpoints
            catalog = tmp_path / "workflows.json"
            catalog.write_text(json.dumps([workflow]))
            monkeypatch.setattr(workflow_endpoints, "WORKFLOWS_FILE", str(catalog))
            assert await workflow_event_worker.process_pending_event_executions_once(engine=engine) == 1
        else:
            assert await engine.launch_reserved_event_execution(admitted.event_id, state, preflight)
        await asyncio.gather(*list(engine._background_tasks))
        persisted = await manager.get_execution_state(admitted.event_id)
        assert persisted["status"] == "PAUSED"
        engine._execute_step.assert_not_awaited()
        approval.assert_called_once()
        assert approval.call_args.kwargs["user_id"] == identity["user_id"]
        assert classified_owners == [identity["user_id"]]
        assert workflow.get("created_by") == legacy_author

    asyncio.run(asyncio.wait_for(verify(), timeout=20))


@pytest.mark.parametrize("execution_id", ["manual_one", "scheduled_one"])
def test_non_event_policy_owner_does_not_override_author(execution_id):
    assert WorkflowEngine._reserved_event_policy_owner(
        execution_id, {"id": "wf", "created_by": "author"}, {}) is None


@pytest.mark.parametrize("mutation", ["missing_owner", "missing_tenant", "missing_workspace", "wrong_execution", "wrong_workflow", "missing_receipt"])
def test_incomplete_event_owner_is_not_default_authority(mutation):
    from core.execution_state_manager import EXECUTION_SCOPE_KEY
    state = {"input_data": {EXECUTION_SCOPE_KEY: {
        "user_id": "owner", "tenant_id": "tenant", "workspace_id": "workspace"}},
        "context": {"_atom_event_admission": {
            "execution_id": "evt_one", "workflow_id": "wf"}}}
    if mutation.startswith("missing_") and mutation != "missing_receipt":
        key = {"missing_owner": "user_id", "missing_tenant": "tenant_id", "missing_workspace": "workspace_id"}[mutation]
        state["input_data"][EXECUTION_SCOPE_KEY].pop(key)
    elif mutation == "missing_receipt":
        state["context"].clear()
    else:
        state["context"]["_atom_event_admission"]["execution_id" if mutation == "wrong_execution" else "workflow_id"] = "other"
    with pytest.raises(ValueError):
        WorkflowEngine._reserved_event_policy_owner("evt_one", {"id": "wf"}, state)
