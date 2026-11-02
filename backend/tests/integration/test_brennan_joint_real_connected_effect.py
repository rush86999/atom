"""Real connected-handler assignment control.

Uses the actual registered `connected.books.create_estimate` handler (not a
substitute action) with a controlled provider that records acceptance and then
loses the response.  The assignment must become uncertain, the dependent
Outlook draft must stay blocked, restart/resume must add no provider effect,
and reconciliation must settle the original operation.
"""
from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.assignment_executor import AssignmentExecutor
from core.assignment_plan import new_assignment, new_step
from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.task_lifecycle import TaskLifecycle
from core.assignment_plan import new_teaching_snapshot
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.assignment_executor import default_adapter_registry


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/assignment.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runs = GoalRunService(
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=factory)
    goals = GoalService(
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=factory)
    lifecycle = TaskLifecycle(runs, goals)
    registry = default_adapter_registry.clone()
    return {
        "tmp": tmp_path,
        "factory": factory,
        "lifecycle": lifecycle,
        "executor": AssignmentExecutor(lifecycle, adapters=registry),
        "registry": registry,
    }


def _estimate_data():
    return {
        "customer_id": "customer-1",
        "reference_number": "RFQ-REAL-1",
        "date": "2026-11-01",
        "currency_code": "USD",
        "total": "200.00",
        "sub_total": "200.00",
        "tax_total": "0.00",
        "line_items": [{"item_id": "A", "quantity": "2", "rate": "100.00",
                        "account_id": "acct-1"}],
    }


def _steps():
    estimate = new_step(
        step_id="estimate",
        title="Create the authorized estimate",
        operation_type="outbound",
        adapter="action.registry",
        inputs={
            "action": "connected.books.create_estimate",
            "arguments": {
                "organization_id": "org-1",
                "estimate_data": _estimate_data(),
                "authority_reference": "grant-real-1",
                "operation_id": "op-real-1",
            },
        },
        effect="external",
        approval_required=True,
        approval_purpose="Create the quote estimate",
    )
    draft = new_step(
        step_id="email-draft",
        title="Create the Outlook draft",
        operation_type="outbound",
        adapter="action.registry",
        depends_on=["estimate"],
        inputs={
            "action": "connected.outlook.create_draft",
            "arguments": {
                "to": ["buyer@example.invalid"],
                "subject": "Quote RFQ-REAL-1",
                "body": "Quoted total: 200.00 USD",
                "operation_id": "op-real-draft-1",
            },
        },
        effect="external",
        approval_required=True,
        approval_purpose="Create the Outlook draft",
    )
    return [estimate, draft]


def _create(env):
    plan = new_assignment(
        objective="Create an authorized estimate and Outlook draft",
        steps=_steps(),
        authorized_actions=["outbound"],
        teaching_snapshot=new_teaching_snapshot(revision="untrained"),
        employee_id="user-1",
        workspace_id="ws_assign",
        tenant_id="tenant_assign",
        budget={"max_steps": 20, "max_attempts_per_step": 3,
                "max_wall_seconds": 600},
    )
    return env["executor"].create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}",
        "Create an authorized estimate and Outlook draft",
        assignment=plan,
    )["run_id"]


def test_real_connected_estimate_uncertainty_blocks_draft_and_reconciles(
        env, monkeypatch):
    from core import connected_actions as actions

    calls = {"estimate": 0, "readback": 0, "draft": 0}

    class FakeBooks:
        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_estimates_page(self, token, org, page=1, per_page=200):
            return [], {"has_more": False}

        async def create_estimate(self, token, org, data):
            calls["estimate"] += 1
            # The provider records acceptance, then the connection is lost
            # before the caller can read the response.
            raise httpx.ReadError("connection reset after acceptance")

        async def get_estimate(self, token, org, estimate_id):  # pragma: no cover
            calls["readback"] += 1
            raise AssertionError("no readback without a remote id")

    class FakeOutlook:
        def __init__(self):
            self.sent = False

        async def _get_access_token(self, user_id):
            return "token"

        async def create_draft_email(self, **kwargs):
            calls["draft"] += 1
            self.draft = kwargs
            return {"id": "draft-real-1", "subject": kwargs["subject"]}

        async def get_email_by_id(self, user_id, email_id, token=None):
            payload = getattr(self, "draft", {}) or {}
            return {
                "id": email_id,
                "subject": payload.get("subject", ""),
                "body": {"content": payload.get("body", "")},
                "to_recipients": [
                    {"emailAddress": {"address": item}}
                    for item in (payload.get("to_recipients") or [])
                ],
                "cc_recipients": [
                    {"emailAddress": {"address": item}}
                    for item in (payload.get("cc_recipients") or [])
                ],
                "bcc_recipients": [
                    {"emailAddress": {"address": item}}
                    for item in (payload.get("bcc_recipients") or [])
                ],
            }

        async def send_email(self, *args, **kwargs):  # pragma: no cover
            self.sent = True
            raise AssertionError("draft must not send")

    async def fake_books(ids):
        return FakeBooks()

    outlook = FakeOutlook()
    monkeypatch.setattr(actions, "_books_service", fake_books)
    monkeypatch.setattr(
        "integrations.outlook_service.OutlookService",
        lambda *a, **k: outlook)

    run_id = _create(env)
    first = asyncio.run(env["executor"].execute(run_id))
    assignment = first["assignment"]
    estimate_step = next(step for step in assignment["steps"]
                         if step["step_id"] == "estimate")
    assert estimate_step["status"] == "awaiting_approval"
    assert calls["estimate"] == 0

    approved = env["executor"].approve_step(
        run_id, "estimate", approved_by="owner", note="bounded estimate")
    assert approved["status"] in ("approved", "already_applied")
    after = asyncio.run(env["executor"].execute(run_id))["assignment"]
    estimate_step = next(step for step in after["steps"]
                         if step["step_id"] == "estimate")
    draft_step = next(step for step in after["steps"]
                      if step["step_id"] == "email-draft")
    assert estimate_step["status"] == "uncertain", estimate_step
    assert draft_step["status"] != "applied"
    assert calls["estimate"] == 1
    assert calls["draft"] == 0

    # Restart with a new executor over the same durable lifecycle.
    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    asyncio.run(restarted.execute(run_id))
    assert calls["estimate"] == 1
    assert calls["draft"] == 0

    # Reconcile the original operation and continue the dependent draft.
    env["executor"].reconcile_step(
        run_id, "estimate", "applied",
        evidence="controlled provider accepted the estimate",
        evidence_ref="controlled-readback:estimate:RFQ-REAL-1")
    after_reconcile = asyncio.run(env["executor"].execute(run_id))["assignment"]
    draft_step = next(step for step in after_reconcile["steps"]
                      if step["step_id"] == "email-draft")
    assert draft_step["status"] == "awaiting_approval", draft_step
    approved_draft = env["executor"].approve_step(
        run_id, "email-draft", approved_by="owner",
        note="bounded Outlook draft")
    assert approved_draft["status"] in ("approved", "already_applied")
    final = asyncio.run(env["executor"].execute(run_id))["assignment"]
    draft_step = next(step for step in final["steps"]
                      if step["step_id"] == "email-draft")
    assert draft_step["status"] == "applied", {
        "status": draft_step.get("status"),
        "failure": draft_step.get("failure"),
        "result": draft_step.get("result"),
    }
    assert calls["estimate"] == 1
    assert calls["draft"] == 1
    assert outlook.sent is False


def test_post_dispatch_serialization_overflow_is_uncertain_and_reconciles(
        env, monkeypatch):
    from core.action_registry import action_registry

    calls = []
    huge = {
        "status": "success", "action_result": "applied",
        "remote_id": "remote-big",
        "content": "x" * 1_700_000,
        "other": "y" * 1_700_000,
        "rows": [{"v": "x" * 72} for _ in range(10000)],
    }

    async def huge_update(args, context):
        calls.append(dict(args))
        return dict(huge)

    name = f"test.serialization.executor.{uuid.uuid4().hex[:8]}"
    action_registry.register(
        name, huge_update, effects=[{"effect": "create"}])
    create = new_step(
        step_id="create", title="Create the oversized commercial record",
        operation_type="outbound", adapter="action.registry",
        inputs={"action": name, "arguments": {}},
        effect="external", approval_required=True,
        approval_purpose="Create the record",
    )
    draft = new_step(
        step_id="email-draft", title="Prepare the customer email",
        operation_type="outbound", adapter="email.draft",
        depends_on=["create"],
        inputs={"to": ["buyer@example.invalid"],
                "subject": "Quote", "body": "Quoted total"},
        effect="local",
    )
    plan = new_assignment(
        objective="Create and draft with an oversized provider result",
        steps=[create, draft], authorized_actions=["outbound", "edit"],
        employee_id="user-1", workspace_id="ws_assign",
        tenant_id="tenant_assign",
        budget={"max_steps": 20, "max_attempts_per_step": 3,
                "max_wall_seconds": 600},
    )
    run_id = env["executor"].create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}", plan["objective"],
        assignment=plan)["run_id"]

    asyncio.run(env["executor"].execute(run_id))
    env["executor"].approve_step(
        run_id, "create", approved_by="owner", note="bounded create")
    after = asyncio.run(env["executor"].execute(run_id))["assignment"]
    create_step = next(step for step in after["steps"]
                       if step["step_id"] == "create")
    draft_step = next(step for step in after["steps"]
                      if step["step_id"] == "email-draft")
    assert create_step["status"] == "uncertain"
    assert draft_step["status"] == "pending"
    assert len(calls) == 1
    record = env["lifecycle"].get_task(run_id)
    operation = next(
        item for item in record["operations"]
        if item["operation_id"] == create_step["operation_id"])
    assert operation["status"] == "uncertain"
    assert operation["receipt"]["remote_identity"]["remote_id"] == "remote-big"

    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    resumed = asyncio.run(restarted.execute(run_id))["assignment"]
    assert resumed["status"] == "blocked"
    assert len(calls) == 1

    restarted.reconcile_step(
        run_id, "create", "applied",
        evidence="provider readback shows remote-big",
        evidence_ref="remote-big")
    completed = asyncio.run(restarted.execute(run_id))["assignment"]
    draft_step = next(step for step in completed["steps"]
                      if step["step_id"] == "email-draft")
    assert draft_step["status"] == "applied"
    assert len(calls) == 1


def test_oracle_failure_after_real_create_stays_uncertain_and_never_recreates(
        env, monkeypatch):
    """A dispatched effect with no usable oracle verdict is uncertain.

    The real registered estimate handler performs one successful provider
    create. The oracle then raises, so the executor must preserve the remote
    identity, block the dependent draft, and never dispatch a second create
    across restart. Reconciliation settles the ORIGINAL operation and only
    then may the dependent draft proceed.
    """
    from core import connected_actions as actions
    import core.oracle as oracle_module

    calls = {"estimate": 0, "readback": 0, "draft": 0}

    class FakeBooks:
        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_estimates_page(self, token, org, page=1, per_page=200):
            return [], {"has_more": False}

        async def create_estimate(self, token, org, data):
            calls["estimate"] += 1
            return {"estimate_id": "est-oracle-failed"}

        async def get_estimate(self, token, org, estimate_id):
            calls["readback"] += 1
            return {
                "estimate_id": estimate_id,
                "customer_id": "customer-1",
                "reference_number": "RFQ-REAL-1",
                "date": "2026-11-01",
                "currency_code": "USD",
                "total": "200.00",
                "sub_total": "200.00",
                "tax_total": "0.00",
                "line_items": [{
                    "item_id": "A", "quantity": "2", "rate": "100.00",
                    "account_id": "acct-1",
                }],
            }

    class FakeOutlook:
        def __init__(self):
            self.sent = False
            self.draft = None

        async def _get_access_token(self, user_id):
            return "token"

        async def create_draft_email(self, **kwargs):
            calls["draft"] += 1
            self.draft = kwargs
            return {"id": "draft-after-reconcile", "subject": kwargs["subject"]}

        async def get_email_by_id(self, user_id, email_id, token=None):
            payload = self.draft or {}
            return {
                "id": email_id,
                "subject": payload.get("subject", ""),
                "body": {"content": payload.get("body", "")},
                "to_recipients": [
                    {"emailAddress": {"address": item}}
                    for item in (payload.get("to_recipients") or [])
                ],
                "cc_recipients": [
                    {"emailAddress": {"address": item}}
                    for item in (payload.get("cc_recipients") or [])
                ],
                "bcc_recipients": [
                    {"emailAddress": {"address": item}}
                    for item in (payload.get("bcc_recipients") or [])
                ],
            }

        async def send_email(self, *args, **kwargs):  # pragma: no cover
            self.sent = True
            raise AssertionError("draft must not send")

    async def fake_books(ids):
        return FakeBooks()

    outlook = FakeOutlook()
    monkeypatch.setattr(actions, "_books_service", fake_books)
    monkeypatch.setattr(
        "integrations.outlook_service.OutlookService",
        lambda *a, **k: outlook)

    real_validate = oracle_module.validate

    async def flaky_validate(action, context=None):
        if str(action).endswith("books.create_estimate"):
            raise RuntimeError("oracle transport unavailable")
        return await real_validate(action, context)

    monkeypatch.setattr(oracle_module, "validate", flaky_validate)

    run_id = _create(env)
    asyncio.run(env["executor"].execute(run_id))
    approved = env["executor"].approve_step(
        run_id, "estimate", approved_by="owner", note="bounded estimate")
    assert approved["status"] in ("approved", "already_applied")
    after = asyncio.run(env["executor"].execute(run_id))["assignment"]
    estimate_step = next(step for step in after["steps"]
                         if step["step_id"] == "estimate")
    draft_step = next(step for step in after["steps"]
                      if step["step_id"] == "email-draft")
    assert estimate_step["status"] == "uncertain", estimate_step
    assert draft_step["status"] != "applied"
    assert calls == {"estimate": 1, "readback": 1, "draft": 0}

    record = env["lifecycle"].get_task(run_id)
    operation = next(
        item for item in record["operations"]
        if item["operation_id"] == estimate_step["operation_id"])
    assert operation["status"] == "uncertain"
    assert operation["receipt"]["remote_identity"]["remote_id"] == (
        "est-oracle-failed")
    assert operation["receipt"]["reconciliation_required"] is True

    fresh_runs = GoalRunService(
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=env["factory"])
    fresh_goals = GoalService(
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=env["factory"])
    restarted = AssignmentExecutor(
        TaskLifecycle(fresh_runs, fresh_goals), adapters=env["registry"])
    resumed = asyncio.run(restarted.execute(run_id))["assignment"]
    assert resumed["status"] == "blocked"
    assert calls == {"estimate": 1, "readback": 1, "draft": 0}

    restarted.reconcile_step(
        run_id, "estimate", "applied",
        evidence="readback shows est-oracle-failed",
        evidence_ref="remote:est-oracle-failed")
    awaiting = asyncio.run(restarted.execute(run_id))["assignment"]
    draft_step = next(step for step in awaiting["steps"]
                      if step["step_id"] == "email-draft")
    assert draft_step["status"] == "awaiting_approval", draft_step
    approved_draft = restarted.approve_step(
        run_id, "email-draft", approved_by="owner",
        note="bounded Outlook draft")
    assert approved_draft["status"] in ("approved", "already_applied")
    final = asyncio.run(restarted.execute(run_id))["assignment"]
    draft_step = next(step for step in final["steps"]
                      if step["step_id"] == "email-draft")
    assert draft_step["status"] == "applied", draft_step
    assert calls == {"estimate": 1, "readback": 1, "draft": 1}
    assert outlook.sent is False
