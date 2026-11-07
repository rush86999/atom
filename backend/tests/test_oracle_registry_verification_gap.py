"""Shared ORACLE registry-verification controls.

The decisive gap was fail-open: a registered durable mutation with no
postcondition verifier returned ``applied`` (with ``oracle_verified=None``),
and a real legacy mutation (``mini_app_set_tests``) was not even classified as
mutating because its registration omitted effects.

These controls join the full ``AssignmentExecutor`` path, use real scratch
SQLite stores, and preserve operation identity through uncertain outcomes.
Only the external/model effect leaf is simulated; the executor, lifecycle,
receipt and oracle consumer are the production implementations.
"""
from __future__ import annotations

import asyncio
import sqlite3
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.action_effects import declares_mutation
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
from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.oracle import (
    OracleResult,
    get_postcondition,
    register_postcondition,
    validate,
)
from core.task_lifecycle import TaskLifecycle, _approval_payload_hash


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/oracle-gap.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runs = GoalRunService(
        workspace_id="ws_gap", tenant_id="tenant_gap",
        session_factory=factory)
    goals = GoalService(
        workspace_id="ws_gap", tenant_id="tenant_gap",
        session_factory=factory)
    lifecycle = TaskLifecycle(runs, goals)
    registry = default_adapter_registry.clone()
    return {
        "tmp": tmp_path,
        "lifecycle": lifecycle,
        "registry": registry,
        "executor": AssignmentExecutor(lifecycle, adapters=registry),
    }


def _effect_db(tmp_path):
    path = tmp_path / "effect.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "create table effects "
            "(value integer, token text, operation_id text)")
    return path


def _rows(path):
    with sqlite3.connect(path) as db:
        return db.execute(
            "select value, token, operation_id from effects").fetchall()


def _create(env, action_name, arguments, *, effect="local",
            approval_required=False):
    step = new_step(
        step_id="act",
        title="Run the registered action",
        operation_type="edit" if effect != "external" else "outbound",
        adapter="action.registry",
        inputs={"action": action_name, "arguments": arguments},
        effect=effect,
        approval_required=approval_required,
        approval_purpose="Apply the controlled action",
    )
    plan = new_assignment(
        objective="Exercise the registered action",
        employee_id="user-1",
        workspace_id="ws_gap",
        tenant_id="tenant_gap",
        teaching_snapshot=new_teaching_snapshot(revision="teach-gap"),
        steps=[step],
        authorized_actions=[
            "retrieve", "calculate", "present", "edit", "outbound"],
        completion_criteria=[],
        budget={"max_steps": 20, "max_attempts_per_step": 3,
                "max_wall_seconds": 600},
    )
    return env["executor"].create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}", plan["objective"],
        assignment=plan)["run_id"]


def _operation(record, step):
    return next(
        item for item in record["operations"]
        if item["operation_id"] == step["operation_id"])


def test_declared_mutation_without_verifier_is_uncertain_and_not_reapplied(
        env, tmp_path):
    path = _effect_db(tmp_path)
    calls = []
    name = f"test.gap.missing.{uuid.uuid4().hex[:8]}"

    async def write(args, context):
        calls.append(context.get("operation_id"))
        with sqlite3.connect(path) as db:
            db.execute(
                "insert into effects values (?, ?, ?)",
                (args["value"], args["token"], context.get("operation_id")))
        return {"success": True, "status": "success",
                "action_result": "applied", "remote_id": "local-missing"}

    action_registry.register(
        name, write, effects=[{"effect": "write", "scope": "local"}])

    run_id = _create(env, name, {"value": 7, "token": "missing"})
    first = asyncio.run(env["executor"].execute(run_id))
    assert first["assignment"]["status"] == "blocked", first
    assignment = env["lifecycle"].get_assignment(run_id)
    step = step_by_id(assignment, "act")
    assert step["status"] == "uncertain", step
    operation = _operation(env["lifecycle"].get_task(run_id), step)
    assert operation["status"] == "uncertain"
    assert operation["needs_reconciliation"] is True
    assert operation["receipt"]["observed_status"] == "uncertain"
    assert operation["receipt"]["oracle_verified"] is False
    assert operation["receipt"]["reconciliation_required"] is True
    assert operation["execution"]["oracle_verified"] is False
    assert "no registered postcondition verifier" in (
        operation["execution"]["oracle_evidence"])
    assert len(calls) == 1
    assert _rows(path) == [(7, "missing", step["operation_id"])]

    # Restart: the uncertain original operation is never dispatched again.
    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    resumed = asyncio.run(restarted.resume(run_id))
    assert resumed["assignment"]["status"] == "blocked", resumed
    assert len(calls) == 1
    assert len(_rows(path)) == 1
    operation = _operation(restarted.lifecycle.get_task(run_id), step)
    assert operation["status"] == "uncertain"


@pytest.mark.parametrize("mode", ["none", "raise", "refute"])
def test_unusable_verifier_is_uncertain_with_receipt(env, tmp_path, mode):
    path = _effect_db(tmp_path)
    calls = []
    name = f"test.gap.{mode}.{uuid.uuid4().hex[:8]}"

    async def write(args, context):
        calls.append(context.get("operation_id"))
        with sqlite3.connect(path) as db:
            db.execute(
                "insert into effects values (?, ?, ?)",
                (args["value"], args["token"], context.get("operation_id")))
        return {"success": True, "action_result": "applied",
                "remote_id": f"local-{mode}"}

    async def verifier(ctx):
        if mode == "none":
            return None
        if mode == "raise":
            raise RuntimeError("readback store unavailable")
        return OracleResult(name, False, "readback disagrees")

    action_registry.register(
        name, write, effects=[{"effect": "write", "scope": "local"}])
    register_postcondition(name)(verifier)

    run_id = _create(env, name, {"value": 3, "token": mode})
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "blocked", result
    step = step_by_id(env["lifecycle"].get_assignment(run_id), "act")
    assert step["status"] == "uncertain", step
    operation = _operation(env["lifecycle"].get_task(run_id), step)
    assert operation["status"] == "uncertain"
    assert operation["receipt"]["oracle_verified"] is False
    assert operation["execution"]["oracle_verified"] is False
    assert len(calls) == 1
    assert len(_rows(path)) == 1
    if mode == "raise":
        assert "errored" in operation["execution"]["oracle_evidence"].lower()
    if mode == "refute":
        assert "readback disagrees" in operation["execution"]["oracle_evidence"]


def test_positive_independent_verdict_applies_with_receipt(env, tmp_path):
    path = _effect_db(tmp_path)
    name = f"test.gap.positive.{uuid.uuid4().hex[:8]}"

    async def write(args, context):
        with sqlite3.connect(path) as db:
            db.execute(
                "insert into effects values (?, ?, ?)",
                (args["value"], args["token"], context.get("operation_id")))
        return {"success": True, "action_result": "applied",
                "remote_id": "local-positive"}

    async def verifier(ctx):
        expected_operation = str(
            ctx.get("_oracle_expected_operation_id") or "")
        rows = _rows(path)
        ok = (
            len(rows) == 1
            and rows[0] == (9, "positive", expected_operation)
        )
        return OracleResult(
            name, ok, f"scratch effect row matches operation "
                      f"{expected_operation[:12]}: {ok}")

    action_registry.register(
        name, write, effects=[{"effect": "write", "scope": "local"}])
    register_postcondition(name)(verifier)

    run_id = _create(env, name, {"value": 9, "token": "positive"})
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    step = step_by_id(env["lifecycle"].get_assignment(run_id), "act")
    assert step["status"] == "applied", step
    operation = _operation(env["lifecycle"].get_task(run_id), step)
    assert operation["status"] == "applied"
    assert operation["receipt"]["observed_status"] == "confirmed"
    assert operation["receipt"]["oracle_verified"] is True
    assert operation["execution"]["oracle_verified"] is True
    assert _rows(path) == [(9, "positive", step["operation_id"])]


def test_read_action_without_verifier_still_applies(env):
    name = f"test.gap.read.{uuid.uuid4().hex[:8]}"

    async def read(args, context):
        return {"success": True, "rows": [{"id": 1}]}

    action_registry.register(name, read, effects=[{"effect": "read"}])
    run_id = _create(env, name, {}, effect="read_only")
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    step = step_by_id(env["lifecycle"].get_assignment(run_id), "act")
    assert step["status"] == "applied", step
    operation = _operation(env["lifecycle"].get_task(run_id), step)
    assert operation["receipt"]["oracle_verified"] is None


def test_full_executor_real_task_create_is_independently_verified(
        env, tmp_path, monkeypatch):
    """Real covered mutation family: tasks.create through the full executor."""
    from contextlib import contextmanager

    import core.database as db_module
    from core.models import AgentRegistry
    from core.models_board import Board, BoardColumn, BoardTask

    engine = create_engine(f"sqlite:///{tmp_path}/board.db")
    for table in (Board.__table__, BoardColumn.__table__,
                  BoardTask.__table__, AgentRegistry.__table__):
        table.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(Board(id="board-1", name="Delivery"))
        db.add(BoardColumn(
            id="column-1", board_id="board-1", name="Backlog", position=0))
        db.commit()

    @contextmanager
    def scratch_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(db_module, "get_db_session", scratch_session)
    run_id = _create(
        env, "tasks.create",
        {"title": "Verified task", "board_id": "board-1",
         "column_id": "column-1"},
        effect="local")
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    step = step_by_id(env["lifecycle"].get_assignment(run_id), "act")
    assert step["status"] == "applied", step
    operation = _operation(env["lifecycle"].get_task(run_id), step)
    assert operation["receipt"]["oracle_verified"] is True
    with Session() as db:
        saved = db.query(BoardTask).filter(
            BoardTask.title == "Verified task").one()
        assert str(saved.board_id) == "board-1"
        assert str(saved.column_id) == "column-1"


def test_full_executor_real_read_action_still_applies(env, tmp_path, monkeypatch):
    """Real read twin: agents.list needs no mutation verifier."""
    from contextlib import contextmanager

    import core.database as db_module
    from core.models import AgentRegistry

    engine = create_engine(f"sqlite:///{tmp_path}/agents.db")
    AgentRegistry.__table__.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scratch_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(db_module, "get_db_session", scratch_session)
    run_id = _create(env, "agents.list", {}, effect="read_only")
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    step = step_by_id(env["lifecycle"].get_assignment(run_id), "act")
    assert step["status"] == "applied", step
    operation = _operation(env["lifecycle"].get_task(run_id), step)
    assert operation["receipt"]["oracle_verified"] is None


def test_plan_output_is_not_treated_as_a_mutation(env, monkeypatch):
    plan = {
        "method": "standard",
        "subtasks": [{"id": "one", "depends_on": []}],
        "execution_groups": [["one"]],
        "cycles": [],
    }
    action = action_registry.get_action("goals.decompose")

    async def handler(args, context):
        return {"success": True, "plan": plan}

    monkeypatch.setattr(action, "handler", handler)
    assert declares_mutation(action) is False
    run_id = _create(env, "goals.decompose", {"goal": "ship it"})
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    step = step_by_id(env["lifecycle"].get_assignment(run_id), "act")
    assert step["status"] == "applied"
    operation = _operation(env["lifecycle"].get_task(run_id), step)
    assert operation["receipt"]["oracle_verified"] is True
    assert operation["receipt"]["observed_status"] == "confirmed"


def test_changed_request_is_refuted_against_the_frozen_authorized_request(
        env, tmp_path):
    path = _effect_db(tmp_path)
    name = f"test.gap.changed.{uuid.uuid4().hex[:8]}"

    async def write(args, context):
        # The handler edits its own dispatch copy and writes a different value.
        # The frozen authorized request must still drive the verdict.
        args["value"] = 999
        with sqlite3.connect(path) as db:
            db.execute(
                "insert into effects values (?, ?, ?)",
                (8, args["token"], context.get("operation_id")))
        return {"success": True, "action_result": "applied",
                "remote_id": "local-changed"}

    async def verifier(ctx):
        expected_operation = str(
            ctx.get("_oracle_expected_operation_id") or "")
        rows = _rows(path)
        ok = len(rows) == 1 and rows[0] == (7, "frozen", expected_operation)
        return OracleResult(
            name, ok, f"frozen request value 7, observed {rows}")

    action_registry.register(
        name, write, effects=[{"effect": "update", "scope": "local"}])
    register_postcondition(name)(verifier)

    run_id = _create(env, name, {"value": 7, "token": "frozen"})
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "blocked", result
    step = step_by_id(env["lifecycle"].get_assignment(run_id), "act")
    assert step["status"] == "uncertain", step
    operation = _operation(env["lifecycle"].get_task(run_id), step)
    assert operation["receipt"]["oracle_verified"] is False
    assert len(_rows(path)) == 1


def test_disabled_oracle_never_certifies_applied(env, tmp_path, monkeypatch):
    path = _effect_db(tmp_path)
    name = f"test.gap.disabled.{uuid.uuid4().hex[:8]}"

    async def write(args, context):
        with sqlite3.connect(path) as db:
            db.execute(
                "insert into effects values (?, ?, ?)",
                (args["value"], args["token"], context.get("operation_id")))
        return {"success": True, "action_result": "applied",
                "remote_id": "local-disabled"}

    async def verifier(ctx):
        return OracleResult(name, True, "would have verified")

    action_registry.register(
        name, write, effects=[{"effect": "write", "scope": "local"}])
    register_postcondition(name)(verifier)
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "false")

    run_id = _create(env, name, {"value": 5, "token": "disabled"})
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "blocked", result
    step = step_by_id(env["lifecycle"].get_assignment(run_id), "act")
    assert step["status"] == "uncertain", step
    operation = _operation(env["lifecycle"].get_task(run_id), step)
    assert operation["receipt"]["oracle_verified"] is False
    assert "disabled" in operation["execution"]["oracle_evidence"].lower()
    assert len(_rows(path)) == 1


def test_lead_probe_declared_write_without_verifier_cannot_claim_applied(
        tmp_path, monkeypatch):
    """The supplied probe, kept post-dispatch: the effect landed, so the only
    truthful outcome is uncertain (never failed-none and never applied)."""
    monkeypatch.setattr(action_registry, "_actions", dict(action_registry._actions))
    path = tmp_path / "probe.db"
    with sqlite3.connect(path) as db:
        db.execute("create table effects (value integer)")

    async def write(args, context):
        with sqlite3.connect(path) as db:
            db.execute("insert into effects values (?)", (args["value"],))
        return {"status": "success", "action_result": "applied",
                "remote_id": "local-effect",
                "verification": {"status": "verified", "verified": True}}

    name = f"lead_probe.unverified_mutation.{uuid.uuid4().hex[:8]}"
    action_registry.register(name, write, effects=[{"effect": "write"}])
    assert get_postcondition(name) is None
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {"value": 7}},
        {"workspace_id": "proof-ws", "tenant_id": "proof-tenant",
         "employee_id": "proof-owner", "run_id": "proof-run",
         "step": {"effect": "local", "operation_id": "proof-op"}}))
    with sqlite3.connect(path) as db:
        assert db.execute("select value from effects").fetchall() == [(7,)]
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False
    assert result["action_result"] == "uncertain"


def test_readonly_twin_without_verifier_still_applies(monkeypatch):
    monkeypatch.setattr(action_registry, "_actions", dict(action_registry._actions))

    async def read(args, context):
        return {"status": "success", "value": 7}

    name = f"lead_probe.read.{uuid.uuid4().hex[:8]}"
    action_registry.register(name, read, effects=[{"effect": "read"}])
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {}}, {"step": {"effect": "read"}}))
    assert result["status"] == "applied", result
    assert result["oracle_verified"] is None


@pytest.mark.parametrize("effects", [[], [{"effect": "unknown_effect"}]])
def test_unqualified_effect_metadata_is_not_an_implicit_read(
        monkeypatch, effects):
    """Empty/unknown metadata cannot evade the verification gate."""
    monkeypatch.setattr(action_registry, "_actions", dict(action_registry._actions))

    async def handler(args, context):
        return {"status": "success", "action_result": "applied",
                "success": True, "remote_id": "unqualified"}

    name = f"lead_probe.unqualified.{uuid.uuid4().hex[:8]}"
    action_registry.register(name, handler, effects=effects)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {}},
        {"workspace_id": "ws", "employee_id": "u1", "tenant_id": "t1",
         "step": {"effect": "local", "operation_id": "op-unqualified"}}))
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False
    assert "no registered postcondition verifier" in result["oracle_evidence"]


def test_registry_declares_effects_and_keeps_uncovered_explicit():
    from core.action_effects import declares_plan_output

    # A plan effect mixed with an unknown declaration is NOT a pure plan/read
    # exemption; it stays unqualified and must not be treated as read proof.
    assert declares_plan_output(
        [{"effect": "plan_produced"}, {"effect": "unknown_effect"}]) is False
    assert declares_plan_output([{"effect": "plan_produced"}]) is True
    assert declares_plan_output([]) is False

    uncovered = {
        action.name for action in action_registry.get_all_definitions()
        if declares_mutation(action)
        and get_postcondition(action.name) is None
    }
    # Every remaining mutation without a verifier is explicitly known. The
    # assignment adapter downgrades all of them to uncertain after dispatch;
    # none can claim independently verified applied success.
    allowed = {
        "shopify_create_article", "shopify_create_blog",
        "shopify_create_fulfillment", "shopify_create_product",
        "mini_app_db_write", "mini_app_install", "mini_app_publish",
        "mini_app_revert_logic", "mini_app_run", "mini_app_scaffold",
        "mini_app_write_logic",
        # Lazy registrations (radio/BPE) are mutations too when loaded.
        "radio.create_thread", "radio.send_message",
        "workspace.commit", "workspace.note",
    }
    assert uncovered <= allowed, sorted(uncovered - allowed)

    mini = action_registry.get_action("mini_app_set_tests")
    assert declares_mutation(mini)
    assert get_postcondition("mini_app_set_tests") is not None
    assert action_registry.get_action("shopify_create_product").effects == [
        {"effect": "create", "scope": "external"}]
    assert declares_mutation(
        action_registry.get_action("goals.create")) is True
    assert declares_mutation(
        action_registry.get_action("goals.decompose")) is False
    assert get_postcondition("goals.decompose") is not None


def test_mini_app_manifest_cas_binds_exact_prior_value(tmp_path):
    """No-peer CAS succeeds for JSON null and empty-object prior states."""
    from core.models import Canvas, MiniApp
    from tools.mini_app_tool import _cas_set_tests_manifest

    engine = create_engine(f"sqlite:///{tmp_path}/cas-null.db")
    for table in (Canvas.__table__, MiniApp.__table__):
        table.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    for index, prior in enumerate([None, {}]):
        with Session() as db:
            canvas = Canvas(
                id=f"cas-canvas-{index}", tenant_id="t1", workspace_id="ws",
                created_by="user-1", name="source",
                canvas_type="mini_app", content={})
            app = MiniApp(
                id=f"cas-app-{index}", tenant_id="t1", workspace_id="ws",
                created_by="user-1", name="app", manifest=prior,
                blueprint_canvas_id=canvas.id, status="draft")
            db.add_all([canvas, app])
            db.commit()
            loaded = db.query(MiniApp).filter(
                MiniApp.id == app.id).one()
            prior_manifest = loaded.manifest
            updated = _cas_set_tests_manifest(
                db, app.id, prior_manifest, False,
                {"tests": [{"name": "x", "expect_state": {"runs": 1}}]})
            db.commit()
            assert updated == 1
        with Session() as db:
            saved = db.query(MiniApp).filter(MiniApp.id == app.id).one()
            assert saved.manifest["tests"][0]["name"] == "x"


def test_mini_app_manifest_cas_peer_change_preserves_peer_state(tmp_path):
    """A peer manifest update after our read makes the CAS write zero-effect."""
    from core.models import Canvas, MiniApp
    from sqlalchemy import select
    from tools.mini_app_tool import _cas_set_tests_manifest

    engine = create_engine(
        f"sqlite:///{tmp_path}/cas-peer.db",
        connect_args={"timeout": 30})
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    for table in (Canvas.__table__, MiniApp.__table__):
        table.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as setup:
        setup.add(Canvas(
            id="peer-canvas", tenant_id="t1", workspace_id="ws",
            created_by="user-1", name="source",
            canvas_type="mini_app", content={}))
        setup.add(MiniApp(
            id="peer-app", tenant_id="t1", workspace_id="ws",
            created_by="user-1", name="app",
            manifest={"peer": "v1", "config": {"theme": "light"}},
            blueprint_canvas_id="peer-canvas", status="draft"))
        setup.commit()

    with Session() as reader:
        app = reader.query(MiniApp).filter(MiniApp.id == "peer-app").one()
        prior = app.manifest
        prior_is_sql_null = bool(reader.execute(
            select(MiniApp.manifest.is_(None))
            .where(MiniApp.id == "peer-app")).scalar())
        # A peer updates the same app after this invocation read it.
        with Session() as peer:
            peer_app = peer.query(MiniApp).filter(
                MiniApp.id == "peer-app").one()
            peer_app.manifest = {
                "peer": "v2", "config": {"theme": "dark"},
                "publish": {"version": "2.0.0"}}
            peer.commit()
        new_manifest = dict(prior)
        new_manifest["tests"] = [{"name": "x", "expect_state": {"runs": 1}}]
        updated = _cas_set_tests_manifest(
            reader, "peer-app", prior, prior_is_sql_null, new_manifest)
        assert updated == 0

    with Session() as db:
        saved = db.query(MiniApp).filter(MiniApp.id == "peer-app").one()
        assert saved.manifest == {
            "peer": "v2", "config": {"theme": "dark"},
            "publish": {"version": "2.0.0"}}


def test_mini_app_set_tests_conflict_is_truthful_no_effect(
        tmp_path, monkeypatch):
    """A zero-row CAS returns proven-not-applied and appends no audit row."""
    from contextlib import contextmanager

    import core.database as db_module
    from core.models import Canvas, CanvasAudit, MiniApp
    from tools import mini_app_tool

    engine = create_engine(f"sqlite:///{tmp_path}/cas-conflict.db")
    for table in (Canvas.__table__, MiniApp.__table__, CanvasAudit.__table__):
        table.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as setup:
        setup.add(Canvas(
            id="conflict-canvas", tenant_id="t1", workspace_id="ws",
            created_by="user-1", name="source",
            canvas_type="mini_app", content={}))
        setup.add(MiniApp(
            id="conflict-app", tenant_id="t1", workspace_id="ws",
            created_by="user-1", name="app", manifest={"peer": "v1"},
            blueprint_canvas_id="conflict-canvas", status="draft"))
        setup.commit()

    @contextmanager
    def scratch_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(db_module, "get_db_session", scratch_session)
    monkeypatch.setattr(
        mini_app_tool, "_cas_set_tests_manifest",
        lambda *args, **kwargs: 0)
    result = asyncio.run(mini_app_tool.mini_app_set_tests(
        {"app_id": "conflict-app",
         "tests": [{"name": "x", "expect_state": {"runs": 1}}]},
        {"user_id": "user-1", "workspace_id": "ws", "tenant_id": "t1",
         "operation_id": "op-conflict"}))
    assert result["success"] is False
    assert result["action_result"] == "proven_not_applied"
    assert result["error_kind"] == "manifest_changed"
    with Session() as db:
        saved = db.query(MiniApp).filter(MiniApp.id == "conflict-app").one()
        assert saved.manifest == {"peer": "v1"}
        assert db.query(CanvasAudit).count() == 0

    # The shared adapter preserves the truthful no-effect conflict rather than
    # turning it into an applied write or an uncertain one.
    from core.assignment_executor import _action_registry_adapter

    dispatched = asyncio.run(_action_registry_adapter(
        {"action": "mini_app_set_tests",
         "arguments": {
             "app_id": "conflict-app",
             "tests": [{"name": "x", "expect_state": {"runs": 1}}]}},
        {"employee_id": "user-1", "workspace_id": "ws", "tenant_id": "t1",
         "step": {"effect": "local", "operation_id": "op-conflict"}}))
    assert dispatched["status"] == "failed", dispatched
    assert dispatched["data"]["action_result"] == "proven_not_applied"


def test_mini_app_set_tests_verifier_binds_exact_tests_and_operation(tmp_path):
    from core.models import Canvas, CanvasAudit, MiniApp

    engine = create_engine(f"sqlite:///{tmp_path}/mini.db")
    for table in (Canvas.__table__, MiniApp.__table__, CanvasAudit.__table__):
        table.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    tests = [{"name": "proof", "expect_state": {"runs": 1}}]
    digest = _approval_payload_hash(tests)
    with Session() as db:
        canvas = Canvas(
            id="canvas-1", tenant_id="tenant-1", workspace_id="ws-1",
            created_by="user-1", name="App source", canvas_type="mini_app",
            content={})
        app = MiniApp(
            id="app-1", tenant_id="tenant-1", workspace_id="ws-1",
            created_by="user-1", name="App", manifest={"tests": tests},
            blueprint_canvas_id=canvas.id, status="draft")
        audit = CanvasAudit(
            id="audit-1", canvas_id=canvas.id, tenant_id="tenant-1",
            action_type="mini_app_set_tests", user_id="user-1",
            canvas_type="mini_app",
            details_json={
                "app_id": app.id, "tests_sha256": digest,
                "operation_id": "op-new", "workspace_id": "ws-1",
                "tenant_id": "tenant-1", "actor_id": "user-1",
            })
        db.add_all([canvas, app, audit])
        db.commit()

        base = {
            "db": db,
            "_oracle_expected_app_id": app.id,
            "_oracle_expected_tests": tests,
            "_oracle_expected_tests_sha256": digest,
            "_oracle_expected_operation_id": "op-new",
            "_oracle_expected_tenant_id": "tenant-1",
            "_oracle_expected_workspace_id": "ws-1",
            "_oracle_expected_actor_id": "user-1",
            "audit_id": audit.id,
        }
        good = asyncio.run(validate("mini_app_set_tests", base))
        assert good is not None and good.verified is True, good

        # An old identical manifest/audit row cannot certify a new operation.
        wrong_operation = {**base, "_oracle_expected_operation_id": "op-other"}
        old = asyncio.run(validate("mini_app_set_tests", wrong_operation))
        assert old is not None and old.verified is False

        changed = {
            **base,
            "_oracle_expected_tests": [{"name": "different"}],
        }
        mismatch = asyncio.run(validate("mini_app_set_tests", changed))
        assert mismatch is not None and mismatch.verified is False

        missing = {**base, "audit_id": "missing"}
        absent = asyncio.run(validate("mini_app_set_tests", missing))
        assert absent is not None and absent.verified is False

        wrong_actor = {**base, "_oracle_expected_actor_id": "other-user"}
        actor = asyncio.run(validate("mini_app_set_tests", wrong_actor))
        assert actor is not None and actor.verified is False

        wrong_app = {**base, "_oracle_expected_app_id": "other-app"}
        app_mismatch = asyncio.run(validate("mini_app_set_tests", wrong_app))
        assert app_mismatch is not None and app_mismatch.verified is False

        wrong_request = {**base, "_oracle_expected_tests_sha256": "a" * 64}
        request = asyncio.run(validate("mini_app_set_tests", wrong_request))
        assert request is not None and request.verified is False
