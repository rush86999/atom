"""Focused verification for the task-wait browser fixture promotion contract.

The browser task-wait drivers (``scripts/acceptance/browser_agent_job_wait.py``,
shared by ``browser_agent_source_answer.py`` via ``D3._setup_fixture``) create
their fixture agent through public routes under current governance (#831):

1. the fresh unqualified agent must be refused by the qualification gate with
   a structured ``QUALIFICATION_REQUIRED``/409 (captured, never dropped);
2. the documented owner assessment policy is provisioned with one delta — an
   explicit, exact-agent-scoped manual exception — through the audited admin
   settings API into the isolated scratch DB;
3. the SAME public route then promotes the agent and reports
   ``assessment.state=manual_override`` with
   ``candidate_capability_qualified=False`` and no exam receipt.

Real scratch SQLite + real FastAPI routes + real JWT + the REAL production
exception handlers (``core.error_handler.setup_error_handlers``) so refusals
are observed in the exact shape the live API emits: the Atom handlers return
``exc.detail`` directly for dict details, so a 409 body is FLAT
(``error``/``assessment`` at the top level, no ``detail`` key). No model,
provider, browser or live DB. These are fixture-contract controls, not
capability proof.
"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from core.agent_graduation_service import evaluate_qualification_gate
from core.error_handler import setup_error_handlers
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import (
    AgentRegistry,
    GraduationExam,
    PromotionHistory,
    RuntimeSetting,
    Tenant,
    User,
    Workspace,
)
from core.promotion_policy_service import (
    ASSESSMENT_POLICY_KEY,
    AssessmentPolicy,
    get_assessment_policy,
)
from api.admin_runtime_settings_routes import router as admin_settings_router
from api.agent_routes import router as agent_router
from api.board_routes import router as board_router

REPO = Path(__file__).resolve().parents[3]


def _load_driver():
    """Load the task-wait driver by path, the way the source-answer driver
    shares it (a regular backend package would shadow the repo scripts
    namespace)."""
    path = REPO / "scripts" / "acceptance" / "browser_agent_job_wait.py"
    spec = importlib.util.spec_from_file_location(
        "browser_agent_job_wait_fixture_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def driver():
    return _load_driver()


COMPANY, WS_A = "company", "ws-a"
ADMIN = "fixture-admin"


class World:
    """The isolated scratch world: one admin (the role the acceptance
    bootstrap creates) and nothing else — agents are created through the
    public route exactly as the driver does."""

    def __init__(self, tmp_path: Path):
        self.db_path = tmp_path / "taskwait-fixture.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add(Tenant(
                id=COMPANY, name="Company",
                subdomain=f"tw-{uuid.uuid4().hex[:6]}",
                edition="personal", is_active=True))
            db.add(Workspace(id=WS_A, name="A", tenant_id=COMPANY))
            db.add(User(
                id=ADMIN, tenant_id=COMPANY, workspace_id=WS_A,
                email="admin@example.com", first_name="A", last_name="V",
                role="workspace_admin", status="active", is_active=True))
            db.commit()

    def client(self) -> TestClient:
        app = FastAPI()
        # The REAL production handlers: without them TestClient falls back to
        # FastAPI's default {"detail": ...} envelope, which is NOT what the
        # live server emits for dict details (the Atom handlers return
        # exc.detail directly — flat, no "detail" key).
        setup_error_handlers(app)
        app.include_router(agent_router)
        app.include_router(board_router)
        app.include_router(admin_settings_router)

        def override():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override
        token = create_access_token(
            {"sub": ADMIN}, user=self.user())
        return TestClient(
            app, base_url="http://testserver",
            headers={"Authorization": f"Bearer {token}"})

    def user(self) -> User:
        with self.Session() as db:
            return db.get(User, ADMIN)

    def run_db(self):
        return self.Session()


@pytest.fixture
def world(tmp_path, monkeypatch):
    # The strict resolver reads env before the DB row; the fixture provisions
    # through the settings API, so an env value must not shadow it.
    monkeypatch.delenv(ASSESSMENT_POLICY_KEY, raising=False)
    return World(tmp_path)


def test_fixture_refusal_then_scoped_owner_exception_promotes(world, driver):
    client = world.client()
    fixture = driver._setup_fixture(client)
    agent_id = fixture["agent_id"]
    assert agent_id

    # 1. The unqualified promote was refused, with the refusal captured.
    refusal = fixture["qualification_gate_refusal"]
    assert refusal["status"] == 409
    assert refusal["code"] == "QUALIFICATION_REQUIRED"
    assert refusal["gate_allowed"] is False
    assert refusal["gate_state"] == "unresolved_missing"
    assert refusal["review_action_id"] is None

    # 2. The owner exception is scoped to exactly this agent, via the DB row.
    policy_meta = fixture["owner_exception_policy"]
    assert policy_meta["setting"] == ASSESSMENT_POLICY_KEY
    assert policy_meta["source"] == "db"
    assert policy_meta["agent_ids"] == [agent_id]
    assert policy_meta["state"] == "manual_override"
    assert policy_meta["reason_recorded"] is True
    assert policy_meta["tiers_still_required"] == {
        "intern": True, "supervised": True, "autonomous": True}

    # 3. The same route promoted the agent; the exception never claims
    #    capability qualification.
    assert fixture["agent_promote_status"] == 200
    assert fixture["promote_assessment_state"] == "manual_override"
    assert fixture["promote_claims_capability_qualification"] is False
    assert fixture["board_id"]
    assert fixture["column_id"]

    # Durable scratch-DB truth: autonomous agent, one manual promotion with
    # NO exam receipt, the stored policy naming exactly this agent.
    with world.run_db() as db:
        agent = db.get(AgentRegistry, agent_id)
        assert agent.status == "autonomous"
        assert not agent.last_exam_id
        histories = db.query(PromotionHistory).filter(
            PromotionHistory.agent_id == agent_id).all()
        assert len(histories) == 1
        assert histories[0].promotion_type == "manual"
        assert histories[0].exam_id is None
        assert "manual_override" in (histories[0].justification or "")
        assert db.query(func.count(GraduationExam.id)).scalar() == 0
        row = db.get(RuntimeSetting, ASSESSMENT_POLICY_KEY)
        assert row is not None
        stored = row.value_json
        assert stored["default_required"] is True
        assert stored["exceptions"]["manual"]["allowed"] is True
        assert stored["exceptions"]["manual"]["agent_ids"] == [agent_id]
        assert stored["exceptions"]["manual"]["reason"]
        assert stored["exceptions"]["legacy"]["allowed"] is False
        assert stored["exceptions"]["system"]["allowed"] is False
        # The gate still runs and reports the exception state for this agent.
        bundle = get_assessment_policy(db)
        assessment = evaluate_qualification_gate(
            db, agent, "AUTONOMOUS", manual=True)
        assert assessment["allowed"] is True
        assert assessment["state"] == "manual_override"
        assert assessment["candidate_capability_qualified"] is False
        assert assessment["policy_revision"] == bundle["revision"]
        assert assessment["exception"]["agent_ids"] == [agent_id]


def test_unnamed_agent_remains_refused_by_the_gate(world, driver):
    client = world.client()
    fixture = driver._setup_fixture(client)

    # A second, differently-named agent is NOT covered by the exception:
    # the fixture must not have weakened the gate for anyone else.
    created = client.post("/api/agents/custom", json={
        "name": "Wait Acceptance Employee B",
        "description": "Unnamed control for the fixture exception scope.",
        "category": "acceptance",
    })
    assert created.status_code in (200, 201), created.text
    second_id = str(
        (created.json().get("data") or {}).get("agent_id"))
    assert second_id and second_id != fixture["agent_id"]

    refused = client.post(f"/api/agents/{second_id}/promote")
    assert refused.status_code == 409, refused.text
    body = refused.json()
    # The REAL production handler emits exc.detail directly: FLAT body, no
    # wrapping "detail" key. This also proves the driver's bounded projection
    # reads the same flat shape the live API emits.
    assert "detail" not in body
    assert body["error"]["code"] == "QUALIFICATION_REQUIRED"
    assert body["assessment"]["allowed"] is False
    projected = driver._safe_error_body(refused)
    assert projected["detail"]["code"] == "QUALIFICATION_REQUIRED"
    assert projected["assessment"]["allowed"] is False
    with world.run_db() as db:
        assert db.get(AgentRegistry, second_id).status == "student"


def test_owner_exception_policy_validates_strict_and_stays_scoped(driver):
    policy = driver._owner_exception_policy("agent-123")
    model = AssessmentPolicy.model_validate(policy)
    assert model.default_required is True
    assert model.tiers.autonomous is True
    manual = model.exceptions.manual
    assert manual.allowed is True
    assert manual.agent_ids == ["agent-123"]
    assert manual.domains == []
    assert manual.reason.strip()
    # Named agent matches; any other agent never does.
    assert model.scoped_exception(
        "manual", SimpleNamespace(id="agent-123")) is manual
    assert model.scoped_exception(
        "manual", SimpleNamespace(id="not-the-named-agent")) is None


class _GateRefusalResponse:
    """Minimal response shape for the bounded error projection."""
    status_code = 409

    def json(self):
        return {
            "success": False,
            "detail": {
                "success": False,
                "error": {
                    "code": "QUALIFICATION_REQUIRED",
                    "message": "m" * 500,
                },
                "assessment": {
                    "state": "unresolved_missing",
                    "allowed": False,
                    "message": "g" * 400,
                    "review_action_id": None,
                    "next_action": {"code": "unresolved_missing"},
                },
                "verification": {"status": "refused", "effect": "none"},
            },
        }


class _PlainErrorResponse:
    status_code = 404

    def json(self):
        return {"success": False, "detail": "Agent not found: x" * 40}


class _FlatGateRefusalResponse:
    """The REAL production shape: ``core.base_routes.atom_exception_handler``
    and ``core.error_handler.http_exception_handler`` return ``exc.detail``
    directly for dict details — ``error``/``assessment`` at the top level,
    no wrapping ``detail`` key (this is what stopped the browser retry)."""

    status_code = 409

    def json(self):
        return {
            "success": False,
            "error": {
                "code": "QUALIFICATION_REQUIRED",
                "message": "m" * 500,
            },
            "assessment": {
                "state": "unresolved_missing",
                "allowed": False,
                "message": "g" * 400,
                "review_action_id": None,
                "next_action": {"code": "unresolved_missing"},
            },
            "verification": {"status": "refused", "effect": "none"},
        }


def test_safe_error_body_keeps_bounded_gate_assessment(driver):
    body = driver._safe_error_body(_GateRefusalResponse())
    assert body["status"] == 409
    assert body["detail"]["code"] == "QUALIFICATION_REQUIRED"
    assert len(body["detail"]["message"]) == 300
    assert body["assessment"]["state"] == "unresolved_missing"
    assert body["assessment"]["allowed"] is False
    assert len(body["assessment"]["message"]) == 300
    assert body["assessment"]["review_action_id"] is None
    # Unbounded/irrelevant detail is not carried.
    assert "verification" not in body
    assert "next_action" not in (body["assessment"] or {})

    # The flat production shape parses identically.
    flat = driver._safe_error_body(_FlatGateRefusalResponse())
    assert flat["status"] == 409
    assert flat["detail"]["code"] == "QUALIFICATION_REQUIRED"
    assert len(flat["detail"]["message"]) == 300
    assert flat["assessment"]["state"] == "unresolved_missing"
    assert flat["assessment"]["allowed"] is False
    assert len(flat["assessment"]["message"]) == 300
    assert flat["assessment"]["review_action_id"] is None
    assert "verification" not in flat
    assert "next_action" not in (flat["assessment"] or {})

    plain = driver._safe_error_body(_PlainErrorResponse())
    assert plain["status"] == 404
    assert plain["assessment"] is None
    assert len(plain["detail"]) == 300


def test_env_shadowed_policy_write_is_refused(world, driver, monkeypatch):
    client = world.client()
    created = client.post("/api/agents/custom", json={
        "name": "Wait Acceptance Employee C",
        "description": "Env-shadow control.",
        "category": "acceptance",
    })
    assert created.status_code in (200, 201), created.text
    agent_id = str((created.json().get("data") or {}).get("agent_id"))

    monkeypatch.setenv(ASSESSMENT_POLICY_KEY, "{}")
    with pytest.raises(driver.DriverError, match="shadow"):
        driver._apply_owner_exception(client, agent_id)
    with world.run_db() as db:
        assert db.get(RuntimeSetting, ASSESSMENT_POLICY_KEY) is None
