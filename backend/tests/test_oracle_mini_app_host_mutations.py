"""Independent proof for the six supported mini-app host mutations.

These controls exercise the real registered consumer (``action.registry`` /
``_action_registry_adapter``) and the real ``AssignmentExecutor`` against a
scratch SQLite store. No guest microVM, provider, model or live account is
used: ``mini_app_run`` and every Shopify write remain out of scope.

For each action the producer appends a receipt in the SAME transaction as its
host effect. The verifier re-reads the authoritative store in a FRESH session
and requires the executor-owned operation id, the frozen authorized-request
digest and the exact material (ids/versions/digests). Negatives cover a wrong
operation, a changed request, a missing receipt, stale authoritative material
and a dirty caller identity map.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from core.action_registry import action_registry
from core.assignment_executor import (
    AssignmentExecutor,
    _action_registry_adapter,
    default_adapter_registry,
)
from core.assignment_plan import (
    new_assignment,
    new_step,
    new_teaching_snapshot,
    step_by_id,
)
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import (
    Base,
    Canvas,
    CanvasAudit,
    CanvasLogic,
    CanvasRecord,
    CanvasState,
    MiniApp,
    MiniAppInstallation,
    User,
)
from core.oracle import get_postcondition, validate
from core.task_lifecycle import TaskLifecycle, _approval_payload_hash

USER = "user-1"
TENANT = "tenant-1"
WORKSPACE = "ws-1"
SOURCE = "state = dict(state or {})\nstate['runs'] = state.get('runs', 0) + 1\n"


@pytest.fixture()
def host(tmp_path, monkeypatch):
    """Scratch store shared by the mini-app writers and the assignment state."""
    engine = create_engine(
        f"sqlite:///{tmp_path}/mini-host-proofs.db",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scratch_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr("core.database.get_db_session", scratch_session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.engine", engine)

    with Session() as db:
        db.add(User(
            id=USER, tenant_id=TENANT, workspace_id=WORKSPACE,
            email="host-proof@example.com", hashed_password="x",
            first_name="Host", last_name="Proof", role="member",
            status="active", is_active=True))
        db.commit()

    runs = GoalRunService(
        workspace_id=WORKSPACE, tenant_id=TENANT, session_factory=Session)
    goals = GoalService(
        workspace_id=WORKSPACE, tenant_id=TENANT, session_factory=Session)
    lifecycle = TaskLifecycle(runs, goals)
    executor = AssignmentExecutor(
        lifecycle, adapters=default_adapter_registry.clone())
    return SimpleNamespace(
        engine=engine, Session=Session, lifecycle=lifecycle,
        executor=executor, session=scratch_session)


def _context(operation: str, *, actor: str = USER, tenant: str = TENANT,
             workspace: str = WORKSPACE, tier: str = "autonomous") -> dict:
    return {
        "employee_id": actor,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "tier": tier,
        "step": {"effect": "local", "operation_id": operation},
    }


def _adapter(action: str, arguments: dict, operation: str, **kwargs) -> dict:
    result = asyncio.run(_action_registry_adapter(
        {"action": action, "arguments": arguments},
        _context(operation, **kwargs)))
    if result.get("status") == "applied":
        payload = dict(result.get("data") or {})
        payload["_adapter_status"] = "applied"
        return payload
    return {
        "success": False,
        "_adapter_status": result.get("status"),
        **result,
    }


def _run_executor(host, action: str, arguments: dict) -> SimpleNamespace:
    """Dispatch one action through the real AssignmentExecutor."""
    step = new_step(
        step_id="act", title=f"Run {action}", operation_type="edit",
        adapter="action.registry",
        inputs={"action": action, "arguments": arguments},
        effect="local", approval_required=False,
        approval_purpose=f"Apply {action}")
    plan = new_assignment(
        objective=f"Prove {action}", employee_id=USER,
        workspace_id=WORKSPACE, tenant_id=TENANT,
        teaching_snapshot=new_teaching_snapshot(revision="teach-host-flow"),
        steps=[step],
        authorized_actions=["retrieve", "calculate", "present", "edit"],
        completion_criteria=[], budget={
            "max_steps": 20, "max_attempts_per_step": 3,
            "max_wall_seconds": 600})
    run_id = host.executor.create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}", plan["objective"],
        assignment=plan)["run_id"]
    outcome = asyncio.run(host.executor.execute(run_id))
    assignment = host.lifecycle.get_assignment(run_id)
    record = host.lifecycle.get_task(run_id)
    step = step_by_id(assignment, "act")
    operation = next(
        item for item in record["operations"]
        if item["operation_id"] == step["operation_id"])
    return SimpleNamespace(
        run_id=run_id, outcome=outcome, step=step, operation=operation,
        data=(operation.get("execution") or {}).get("data") or {})


def _receipt(db, receipt_id: str):
    return db.query(CanvasAudit).filter(CanvasAudit.id == receipt_id).first()


def _request_digest(arguments: dict) -> str:
    return _approval_payload_hash(arguments)


def _scaffold_ctx(data: dict, arguments: dict, operation: str, **kwargs) -> dict:
    return {
        "app_id": data["app_id"],
        "canvas_id": data["canvas_id"],
        "audit_id": data["audit_id"],
        "_oracle_expected_operation_id": operation,
        "_oracle_expected_request_sha256": _request_digest(arguments),
        "_oracle_expected_tenant_id": kwargs.get("tenant", TENANT),
        "_oracle_expected_workspace_id": kwargs.get("workspace", WORKSPACE),
        "_oracle_expected_actor_id": kwargs.get("actor", USER),
        "_oracle_expected_mini_app_name": arguments.get("name"),
        "_oracle_expected_mini_app_declared_scopes": list(
            arguments.get("declared_scopes") or []),
        "_oracle_expected_mini_app_dependencies": list(
            arguments.get("dependencies") or []),
        "_oracle_expected_mini_app_spec": dict(arguments.get("spec") or {}),
    }


def _app_ctx(action: str, data: dict, arguments: dict, operation: str,
             **kwargs) -> dict:
    ctx = {
        "app_id": data.get("app_id"),
        "canvas_id": data.get("canvas_id"),
        "audit_id": data.get("audit_id"),
        "_oracle_expected_app_id": arguments.get("app_id") or data.get("app_id"),
        "_oracle_expected_operation_id": operation,
        "_oracle_expected_request_sha256": _request_digest(arguments),
        "_oracle_expected_tenant_id": kwargs.get("tenant", TENANT),
        "_oracle_expected_workspace_id": kwargs.get("workspace", WORKSPACE),
        "_oracle_expected_actor_id": kwargs.get("actor", USER),
    }
    if action == "mini_app_write_logic":
        from core.mini_app_service import logic_source_sha256

        ctx["_oracle_expected_mini_app_source_sha256"] = logic_source_sha256(
            arguments.get("source"))
    if action == "mini_app_revert_logic":
        ctx["_oracle_expected_mini_app_version"] = str(
            arguments.get("version"))
    return ctx


def _db_ctx(data: dict, arguments: dict, operation: str, **kwargs) -> dict:
    return {
        "canvas_id": data.get("canvas_id") or arguments.get("canvas_id"),
        "audit_id": data.get("audit_id"),
        "_oracle_expected_canvas_id": arguments.get("canvas_id"),
        "_oracle_expected_operation_id": operation,
        "_oracle_expected_request_sha256": _request_digest(arguments),
        "_oracle_expected_tenant_id": kwargs.get("tenant", TENANT),
        "_oracle_expected_workspace_id": kwargs.get("workspace", WORKSPACE),
        "_oracle_expected_actor_id": kwargs.get("actor", USER),
        "_oracle_expected_db_op": arguments.get("op"),
        "_oracle_expected_db_series": arguments.get("series"),
        "_oracle_expected_db_data": arguments.get("data"),
        "_oracle_expected_db_record_id": str(
            arguments.get("record_id") or ""),
        "_oracle_expected_db_append_id": str(arguments.get("id") or ""),
        "_oracle_expected_db_filter": arguments.get("filter") or {},
    }


def _seed_published_app(host, *, name="Host proof", public=False) -> dict:
    """Scaffold + write + publish directly, returning the ids/material."""
    arguments = {
        "name": name,
        "declared_scopes": ["canvas_render"],
        "dependencies": [],
    }
    data = _adapter("mini_app_scaffold", arguments, "op-scaffold")
    assert data["success"] is True, data
    write_args = {"app_id": data["app_id"], "source": SOURCE}
    write = _adapter("mini_app_write_logic", write_args, "op-write")
    assert write["success"] is True, write

    from core.mini_app_service import prepare_runtime

    original = prepare_runtime
    try:
        import core.mini_app_service as service

        service.prepare_runtime = lambda app, db, commit=True: None
        pub_args = {"app_id": data["app_id"]}
        published = _adapter("mini_app_publish", pub_args, "op-publish")
    finally:
        service.prepare_runtime = original
    assert published["success"] is True, published
    return {
        "app_id": data["app_id"],
        "canvas_id": data["canvas_id"],
        "publish": published,
        "published": published,
        "arguments": arguments,
    }


# ---------------------------------------------------------------------------
# Positives through the real AssignmentExecutor
# ---------------------------------------------------------------------------
def test_supported_host_flow_is_independently_verified(host):
    from core import mini_app_service

    original = mini_app_service.prepare_runtime
    mini_app_service.prepare_runtime = lambda app, db, commit=True: None
    try:
        scaffold = _run_executor(host, "mini_app_scaffold", {
            "name": "Executor proof", "declared_scopes": ["canvas_render"],
            "dependencies": []})
        assert scaffold.step["status"] == "applied", scaffold.outcome
        assert scaffold.operation["execution"]["oracle_verified"] is True

        write = _run_executor(host, "mini_app_write_logic", {
            "app_id": scaffold.data["app_id"], "source": SOURCE})
        assert write.step["status"] == "applied", (
            write.outcome, write.operation)
        assert write.operation["execution"]["oracle_verified"] is True

        publish = _run_executor(host, "mini_app_publish", {
            "app_id": scaffold.data["app_id"]})
        assert publish.step["status"] == "applied", publish.outcome
        assert publish.operation["execution"]["oracle_verified"] is True

        install = _run_executor(host, "mini_app_install", {
            "app_id": scaffold.data["app_id"]})
        assert install.step["status"] == "applied", install.outcome
        assert install.operation["execution"]["oracle_verified"] is True

        revert = _run_executor(host, "mini_app_revert_logic", {
            "app_id": scaffold.data["app_id"],
            "version": write.data["version"]})
        assert revert.step["status"] == "applied", revert.outcome
        assert revert.operation["execution"]["oracle_verified"] is True

        with host.session() as db:
            app = db.query(MiniApp).filter(
                MiniApp.id == scaffold.data["app_id"]).one()
            assert app.status == "published"
            for run in (scaffold, write, publish, install, revert):
                audit = _receipt(db, run.data["audit_id"])
                assert audit is not None, run.step
                assert audit.details_json["operation_id"] == (
                    run.step["operation_id"])
                assert audit.details_json["request_sha256"]
    finally:
        mini_app_service.prepare_runtime = original


def test_same_operation_is_not_dispatched_twice(host):
    scaffold = _run_executor(host, "mini_app_scaffold", {
        "name": "No second app"})
    assert scaffold.step["status"] == "applied", scaffold.outcome
    with host.session() as db:
        before_apps = db.query(MiniApp).count()
        before_audits = db.query(CanvasAudit).filter(
            CanvasAudit.action_type == "mini_app_scaffold").count()
    # Re-running the SAME persisted operation must not dispatch the producer
    # again (that would create a second app and a second receipt).
    resumed = asyncio.run(host.executor.execute(scaffold.run_id))
    assert resumed["assignment"]["status"] in {"applied", "completed"}, resumed
    with host.session() as db:
        assert db.query(MiniApp).count() == before_apps == 1
        assert db.query(CanvasAudit).filter(
            CanvasAudit.action_type == "mini_app_scaffold").count() == (
                before_audits)


# ---------------------------------------------------------------------------
# Twins: each supported action
# ---------------------------------------------------------------------------
def test_scaffold_receipt_twins(host):
    arguments = {
        "name": "Scaffold twins", "declared_scopes": ["canvas_render"],
        "dependencies": [],
    }
    data = _adapter("mini_app_scaffold", arguments, "op-scaffold-twins")
    assert data["success"] is True, data
    ctx = _scaffold_ctx(data, arguments, "op-scaffold-twins")
    with host.session() as db:
        ctx["db"] = db
        good = asyncio.run(validate("mini_app_scaffold", ctx))
        assert good is not None and good.verified is True, good
        assert asyncio.run(validate(
            "mini_app_scaffold",
            {**ctx, "_oracle_expected_operation_id": "other"})).verified is False
        assert asyncio.run(validate(
            "mini_app_scaffold",
            {**ctx, "_oracle_expected_request_sha256": "a" * 64})
        ).verified is False
        db.query(CanvasAudit).filter(
            CanvasAudit.id == data["audit_id"]).delete()
        db.commit()
        assert asyncio.run(validate(
            "mini_app_scaffold", ctx)).verified is False


def test_scaffold_stale_or_dirty_state_is_refuted(host):
    arguments = {"name": "Scaffold stale"}
    data = _adapter("mini_app_scaffold", arguments, "op-scaffold-stale")
    ctx = _scaffold_ctx(data, arguments, "op-scaffold-stale")
    with host.session() as db:
        app = db.query(MiniApp).filter(MiniApp.id == data["app_id"]).one()
        app.name = "peer changed"
        db.commit()
        ctx["db"] = db
        assert asyncio.run(validate("mini_app_scaffold", ctx)).verified is False

    # A dirty caller session that "fixes" the tampered row must not certify it:
    # verification opens its own session and sees the authoritative peer value.
    with host.session() as dirty:
        app = dirty.query(MiniApp).filter(MiniApp.id == data["app_id"]).one()
        app.name = "Scaffold stale"
        ctx["db"] = dirty
        assert asyncio.run(validate("mini_app_scaffold", ctx)).verified is False


def test_logic_write_receipt_twins(host):
    scaf = _adapter("mini_app_scaffold", {"name": "Logic twins"}, "op-scaf")
    arguments = {"app_id": scaf["app_id"], "source": SOURCE}
    data = _adapter("mini_app_write_logic", arguments, "op-logic-twins")
    assert data["success"] is True, data
    ctx = _app_ctx("mini_app_write_logic", data, arguments, "op-logic-twins")
    with host.session() as db:
        ctx["db"] = db
        good = asyncio.run(validate("mini_app_write_logic", ctx))
        assert good is not None and good.verified is True, good
        assert asyncio.run(validate(
            "mini_app_write_logic",
            {**ctx, "_oracle_expected_mini_app_source_sha256": "b" * 64})
        ).verified is False
        assert asyncio.run(validate(
            "mini_app_write_logic",
            {**ctx, "_oracle_expected_operation_id": "other"})).verified is False
        db.query(CanvasAudit).filter(
            CanvasAudit.id == data["audit_id"]).delete()
        db.commit()
        assert asyncio.run(validate("mini_app_write_logic", ctx)).verified is False


def test_logic_write_stale_source_is_refuted(host):
    scaf = _adapter("mini_app_scaffold", {"name": "Logic stale"}, "op-scaf2")
    arguments = {"app_id": scaf["app_id"], "source": SOURCE}
    data = _adapter("mini_app_write_logic", arguments, "op-logic-stale")
    ctx = _app_ctx("mini_app_write_logic", data, arguments, "op-logic-stale")
    with host.session() as db:
        debug = db.query(CanvasAudit).filter(
            CanvasAudit.id == data["audit_id"]).one()
        canvas_id = debug.canvas_id
        from core.canvas_logic_service import CanvasLogicService

        CanvasLogicService(db).save_logic(
            canvas_id=canvas_id, source="state = {'tampered': True}\n",
            created_by="peer")
        ctx["db"] = db
        assert asyncio.run(validate("mini_app_write_logic", ctx)).verified is False


def test_publish_receipt_twins(host):
    seeded = _seed_published_app(host, name="Publish twins")
    arguments = {"app_id": seeded["app_id"]}
    data = seeded["publish"]
    ctx = _app_ctx("mini_app_publish", data, arguments, "op-publish")
    with host.session() as db:
        ctx["db"] = db
        good = asyncio.run(validate("mini_app_publish", ctx))
        assert good is not None and good.verified is True, good
        assert asyncio.run(validate(
            "mini_app_publish",
            {**ctx, "_oracle_expected_operation_id": "other"})).verified is False
        assert asyncio.run(validate(
            "mini_app_publish",
            {**ctx, "_oracle_expected_request_sha256": "c" * 64})
        ).verified is False
        db.query(CanvasAudit).filter(
            CanvasAudit.id == data["audit_id"]).delete()
        db.commit()
        assert asyncio.run(validate("mini_app_publish", ctx)).verified is False


def test_publish_stale_version_is_refuted(host):
    seeded = _seed_published_app(host, name="Publish stale")
    arguments = {"app_id": seeded["app_id"]}
    ctx = _app_ctx(
        "mini_app_publish", seeded["publish"], arguments, "op-publish")
    with host.session() as db:
        db.execute(update(MiniApp).where(
            MiniApp.id == seeded["app_id"]).values(version="9.9.9"))
        db.commit()
        ctx["db"] = db
        assert asyncio.run(validate("mini_app_publish", ctx)).verified is False


def test_install_receipt_twins(host):
    seeded = _seed_published_app(host, name="Install twins")
    arguments = {"app_id": seeded["app_id"]}
    data = _adapter("mini_app_install", arguments, "op-install")
    assert data["success"] is True, data
    ctx = _app_ctx("mini_app_install", data, arguments, "op-install")
    with host.session() as db:
        ctx["db"] = db
        good = asyncio.run(validate("mini_app_install", ctx))
        assert good is not None and good.verified is True, good
        assert asyncio.run(validate(
            "mini_app_install",
            {**ctx, "_oracle_expected_operation_id": "other"})).verified is False
        assert asyncio.run(validate(
            "mini_app_install",
            {**ctx, "_oracle_expected_request_sha256": "d" * 64})
        ).verified is False
        db.query(CanvasAudit).filter(
            CanvasAudit.id == data["audit_id"]).delete()
        db.commit()
        assert asyncio.run(validate("mini_app_install", ctx)).verified is False


def test_install_stale_instance_is_refuted(host):
    seeded = _seed_published_app(host, name="Install stale")
    arguments = {"app_id": seeded["app_id"]}
    data = _adapter("mini_app_install", arguments, "op-install-stale")
    ctx = _app_ctx("mini_app_install", data, arguments, "op-install-stale")
    with host.session() as db:
        db.execute(update(MiniAppInstallation).where(
            MiniAppInstallation.canvas_id == data["canvas_id"]
        ).values(installed_version="0.0.0"))
        db.commit()
        ctx["db"] = db
        assert asyncio.run(validate("mini_app_install", ctx)).verified is False


def test_install_allows_different_instance_owner(host):
    from core.models import User as UserModel

    seeded = _seed_published_app(host, name="Shared install")
    with host.session() as db:
        app = db.query(MiniApp).filter(MiniApp.id == seeded["app_id"]).one()
        app.is_public = True
        app.is_approved = True
        db.add(UserModel(
            id="user-2", tenant_id="tenant-2", workspace_id="ws-2",
            email="installer@example.com", hashed_password="x",
            first_name="In", last_name="Staller", role="member",
            status="active", is_active=True))
        db.commit()

    arguments = {"app_id": seeded["app_id"]}
    data = _adapter(
        "mini_app_install", arguments, "op-install-shared",
        actor="user-2", tenant="tenant-2", workspace="ws-2")
    assert data["success"] is True, data
    ctx = _app_ctx(
        "mini_app_install", data, arguments, "op-install-shared",
        actor="user-2", tenant="tenant-2", workspace="ws-2")
    with host.session() as db:
        ctx["db"] = db
        result = asyncio.run(validate("mini_app_install", ctx))
        assert result is not None and result.verified is True, result
        canvas = db.query(Canvas).filter(Canvas.id == data["canvas_id"]).one()
        assert str(canvas.created_by) == "user-2"
        installation = db.query(MiniAppInstallation).filter(
            MiniAppInstallation.canvas_id == data["canvas_id"]).one()
        assert str(installation.installed_by) == "user-2"
        assert installation.source == "marketplace"


def test_revert_receipt_twins(host):
    scaf = _adapter("mini_app_scaffold", {"name": "Revert twins"}, "op-scaf3")
    v1 = _adapter(
        "mini_app_write_logic", {"app_id": scaf["app_id"], "source": SOURCE},
        "op-write-v1")
    _adapter(
        "mini_app_write_logic",
        {"app_id": scaf["app_id"], "source": "state = {'v': 2}\n"},
        "op-write-v2")
    arguments = {"app_id": scaf["app_id"], "version": v1["version"]}
    data = _adapter("mini_app_revert_logic", arguments, "op-revert")
    assert data["success"] is True, data
    ctx = _app_ctx("mini_app_revert_logic", data, arguments, "op-revert")
    with host.session() as db:
        ctx["db"] = db
        good = asyncio.run(validate("mini_app_revert_logic", ctx))
        assert good is not None and good.verified is True, good
        assert asyncio.run(validate(
            "mini_app_revert_logic",
            {**ctx, "_oracle_expected_mini_app_version": "999"})
        ).verified is False
        assert asyncio.run(validate(
            "mini_app_revert_logic",
            {**ctx, "_oracle_expected_operation_id": "other"})).verified is False
        db.query(CanvasAudit).filter(
            CanvasAudit.id == data["audit_id"]).delete()
        db.commit()
        assert asyncio.run(validate("mini_app_revert_logic", ctx)).verified is False


def test_db_write_receipt_twins(host):
    seeded = _seed_published_app(host, name="Record twins")
    instance = _adapter(
        "mini_app_install", {"app_id": seeded["app_id"]}, "op-install-rec")
    assert instance["success"] is True, instance
    arguments = {
        "canvas_id": instance["canvas_id"], "op": "append",
        "series": "ledger", "data": {"amount": 5, "note": "first"},
    }
    data = _adapter("mini_app_db_write", arguments, "op-db-append")
    assert data["success"] is True, data
    ctx = _db_ctx(data, arguments, "op-db-append")
    with host.session() as db:
        ctx["db"] = db
        good = asyncio.run(validate("mini_app_db_write", ctx))
        assert good is not None and good.verified is True, good
        assert asyncio.run(validate(
            "mini_app_db_write",
            {**ctx, "_oracle_expected_operation_id": "other"})).verified is False
        assert asyncio.run(validate(
            "mini_app_db_write",
            {**ctx, "_oracle_expected_request_sha256": "e" * 64})
        ).verified is False
        row = db.query(CanvasRecord).filter(
            CanvasRecord.canvas_id == instance["canvas_id"]).one()
        row.data = {"amount": 999}
        db.commit()
        ctx["db"] = db
        assert asyncio.run(validate("mini_app_db_write", ctx)).verified is False


def test_db_write_missing_receipt_and_wrong_target(host):
    seeded = _seed_published_app(host, name="Record target")
    instance = _adapter(
        "mini_app_install", {"app_id": seeded["app_id"]}, "op-install-target")
    arguments = {
        "canvas_id": instance["canvas_id"], "op": "append",
        "series": "ledger", "data": {"amount": 1},
    }
    data = _adapter("mini_app_db_write", arguments, "op-db-target")
    ctx = _db_ctx(data, arguments, "op-db-target")
    with host.session() as db:
        ctx["db"] = db
        assert asyncio.run(validate(
            "mini_app_db_write",
            {**ctx, "_oracle_expected_canvas_id": "other-canvas"})
        ).verified is False
        db.query(CanvasAudit).filter(
            CanvasAudit.id == data["audit_id"]).delete()
        db.commit()
        assert asyncio.run(validate("mini_app_db_write", ctx)).verified is False


def test_db_write_update_binds_prior_material(host):
    seeded = _seed_published_app(host, name="Record update")
    instance = _adapter(
        "mini_app_install", {"app_id": seeded["app_id"]}, "op-install-upd")
    append = _adapter("mini_app_db_write", {
        "canvas_id": instance["canvas_id"], "op": "append",
        "series": "ledger", "data": {"amount": 2, "state": "new"},
    }, "op-append-upd")
    arguments = {
        "canvas_id": instance["canvas_id"], "op": "update",
        "series": "ledger", "record_id": append["id"],
        "data": {"amount": 3},
    }
    data = _adapter("mini_app_db_write", arguments, "op-db-update")
    assert data["success"] is True, data
    ctx = _db_ctx(data, arguments, "op-db-update")
    with host.session() as db:
        ctx["db"] = db
        assert asyncio.run(validate("mini_app_db_write", ctx)).verified is True
        db.execute(update(CanvasRecord).where(
            CanvasRecord.id == append["id"]).values(data={"amount": 99}))
        db.commit()
        ctx["db"] = db
        assert asyncio.run(validate("mini_app_db_write", ctx)).verified is False


# ---------------------------------------------------------------------------
# Zero-effect guarded DML: no receipt and peer state preserved
# ---------------------------------------------------------------------------
def test_stale_publish_is_proven_not_applied_and_writes_no_receipt(host):
    from core.mini_app_service import publish

    seeded = _seed_published_app(host, name="Publish conflict")
    with host.session() as stale:
        app = stale.query(MiniApp).filter(
            MiniApp.id == seeded["app_id"]).one()
        with host.session() as peer:
            peer_app = peer.query(MiniApp).filter(
                MiniApp.id == seeded["app_id"]).one()
            peer_app.manifest = {**peer_app.manifest, "peer": "changed"}
            peer.commit()
        with host.session() as before:
            count = before.query(CanvasAudit).filter(
                CanvasAudit.action_type == "mini_app_publish").count()
        result = publish(app, stale, operation_id="op-publish-stale")
        assert result["success"] is False
        assert result["action_result"] == "proven_not_applied"
        with host.session() as db:
            assert db.query(CanvasAudit).filter(
                CanvasAudit.action_type == "mini_app_publish").count() == count
            saved = db.query(MiniApp).filter(
                MiniApp.id == seeded["app_id"]).one()
            assert saved.manifest["peer"] == "changed"


@pytest.mark.parametrize("peer_changes_language", [False, True])
def test_logic_cas_binds_prior_language(
        host, peer_changes_language):
    """A same-source peer language change is never silently overwritten."""
    from sqlalchemy import event

    from core.canvas_logic_service import CanvasLogicService, LogicConflict

    with host.session() as db:
        db.add(CanvasLogic(
            id="cas-logic", canvas_id="cas-canvas",
            source="old", language="python"))
        db.commit()
    changed = []

    def _after_read(conn, cursor, statement, parameters, context,
                    executemany):
        if (peer_changes_language and not changed
                and statement.lstrip().startswith("SELECT")
                and "FROM canvas_logic" in statement):
            changed.append(True)
            with host.session() as peer:
                row = peer.query(CanvasLogic).filter(
                    CanvasLogic.id == "cas-logic").one()
                row.language = "javascript"
                peer.commit()

    event.listen(host.engine, "after_cursor_execute", _after_read)
    refused = False
    try:
        with host.session() as db:
            try:
                CanvasLogicService(db).save_logic(
                    canvas_id="cas-canvas", source="new", language="python",
                    require_cas=True)
            except LogicConflict:
                refused = True
    finally:
        event.remove(host.engine, "after_cursor_execute", _after_read)
    with host.session() as db:
        row = db.query(CanvasLogic).filter(
            CanvasLogic.id == "cas-logic").one()
        saved = (row.source, row.language)
    if peer_changes_language:
        assert refused is True and saved == ("old", "javascript"), saved
    else:
        assert refused is False and saved == ("new", "python"), saved


@pytest.mark.parametrize("initial_image", [None, "retained-rootfs.img"])
def test_publish_precondition_failure_does_not_commit_preparation(
        host, initial_image):
    """Missing blueprint must not leave an already-committed image clear."""
    from core.mini_app_service import publish

    with host.session() as db:
        db.add(MiniApp(
            id=f"publish-atomic-{initial_image}", tenant_id=TENANT,
            created_by=USER, name="Atomic publish",
            blueprint_canvas_id="missing-source",
            manifest={"dependencies": []}, runtime_image=initial_image))
        db.commit()
        app = db.query(MiniApp).filter(
            MiniApp.id == f"publish-atomic-{initial_image}").one()
        with pytest.raises(ValueError, match="Blueprint canvas"):
            publish(
                app, db, operation_id="publish-op",
                request_sha256="exact-request", actor_id=USER)
        db.rollback()
    with host.session() as db:
        actual = db.query(MiniApp).filter(
            MiniApp.id == f"publish-atomic-{initial_image}").one().runtime_image
    assert actual == initial_image, actual


def test_stale_record_write_raises_conflict_and_preserves_peer(host):
    from core.mini_app_db_service import RecordConflict, _guarded_update_record

    seeded = _seed_published_app(host, name="Record conflict")
    instance = _adapter(
        "mini_app_install", {"app_id": seeded["app_id"]}, "op-install-conf")
    append = _adapter("mini_app_db_write", {
        "canvas_id": instance["canvas_id"], "op": "append",
        "series": "ledger", "data": {"amount": 1},
    }, "op-append-conf")
    with host.session() as stale:
        stale_row = stale.query(CanvasRecord).filter(
            CanvasRecord.id == append["id"]).one()
        assert stale_row.data == {"amount": 1}
        with host.session() as peer:
            peer_row = peer.query(CanvasRecord).filter(
                CanvasRecord.id == append["id"]).one()
            peer_row.data = {"amount": 2}
            peer.commit()
        # The guarded DML binds the prior payload read by THIS invocation; the
        # peer's committed change makes the write zero-effect.
        with pytest.raises(RecordConflict):
            _guarded_update_record(
                stale, stale_row, {"amount": 3}, commit=False)
        with host.session() as db:
            row = db.query(CanvasRecord).filter(
                CanvasRecord.id == append["id"]).one()
            assert row.data == {"amount": 2}


# ---------------------------------------------------------------------------
# Registry coverage snapshot (bounded: six newly covered actions)
# ---------------------------------------------------------------------------
def test_registered_host_mutations_have_verifiers():
    for name in (
            "mini_app_scaffold", "mini_app_write_logic", "mini_app_publish",
            "mini_app_install", "mini_app_db_write",
            "mini_app_revert_logic"):
        action = action_registry.get_action(name)
        assert action is not None, name
        assert get_postcondition(name) is not None, name
