"""Never-autonomous task baskets: real service/API coverage.

Run with the isolated scratch DB (never the live dev DB):

    TESTING=1 PYTEST_VERSION=ci PYTHON_DOTENV_DISABLED=1 \
    DATABASE_URL=sqlite:////tmp/atom_never_rules_test.db \
    /private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python -m pytest \
      tests/test_never_autonomous_rules.py -q

Covers: no-policy baseline, each dimension + combinations, near-neighbour
nonmatches, mature/graduated agents, per-execution approval, missing
metadata, stale edits, cross-user/scope isolation, persistence/readback and
the final MCP fail-closed guard.
"""
from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core import autonomy_policy as ap
from core.agent_governance_service import AgentGovernanceService
from core.auth import get_current_user
from core.database import get_db
from core.models import AgentRegistry, Base
from core.task_classification import (
    TASK_PROFILE_CONTEXT_KEY,
    build_task_profile,
)

MATCHED_TEXT = (
    "Perform an advanced security audit and vulnerability review of the "
    "finance invoice architecture, debug the python api endpoint and "
    "reconcile accounting records"
)
NEAR_MATCH_TEXT = (
    "Write a short marketing blog article and summarize the campaign notes"
)
FINANCE_TEXT = "Reconcile the finance invoice billing expense and accounting records"
CODE_TEXT = "Debug and refactor the python function api endpoint module"


@pytest.fixture()
def store(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'atom_never.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    try:
        yield Session, db
    finally:
        db.close()
        engine.dispose()


def _agent(db, agent_id="hire-1", user_id="u1", status="autonomous"):
    db.add(AgentRegistry(
        id=agent_id,
        name=agent_id,
        category="Operations",
        role="agent",
        type="personal",
        capabilities=[],
        module_path="operations.test",
        class_name="TestAgent",
        user_id=user_id,
        status=status,
        confidence_score=0.95,
        configuration={},
    ))
    db.commit()


def _allow_gate(monkeypatch, status="autonomous"):
    monkeypatch.setattr(
        ap, "maturity_check",
        lambda *a, **k: {
            "known": True, "maturity_level": status,
            "required": "intern", "ok": True, "reason": None})
    monkeypatch.setattr(
        ap, "trust_check",
        lambda *a, **k: {"ok": True, "trust": 0.9, "threshold": 0.6})
    monkeypatch.setattr(ap, "autonomy_cycle", lambda *a, **k: None)
    monkeypatch.setattr(
        ap, "trust_calibration_check",
        lambda *a, **k: {"ok": True, "enabled": False, "resolved": None})
    monkeypatch.setattr(
        ap, "revocation_check",
        lambda *a, **k: {"ok": True, "applicable": False, "revoked": False})


# ---------------------------------------------------------------------------
# Baseline + classification mapping
# ---------------------------------------------------------------------------

def test_no_rules_keeps_existing_behavior(store, monkeypatch):
    _Session, db = store
    _agent(db)
    _allow_gate(monkeypatch)
    profile = build_task_profile(MATCHED_TEXT, user_id="u1")
    gate = ap.gate_for_topic(
        db, "u1", "canvas_edit", "hire-1", task_profile=profile)
    assert gate["outcome"] == ap.OUTCOME_EXECUTE
    assert gate["never_autonomous"]["applicable"] is False
    assert gate["never_autonomous"]["matched"] is False


def test_canonical_classification_mapping():
    profile = build_task_profile(MATCHED_TEXT, user_id="u1")
    assert profile.difficulty == "advanced"
    assert profile.category == "code"
    assert profile.domain == "finance"
    assert profile.source == "server"

    finance = build_task_profile(FINANCE_TEXT, user_id="u1")
    assert finance.category == "extraction"
    assert finance.domain == "finance"

    code = build_task_profile(CODE_TEXT, user_id="u1")
    assert code.category == "code"
    assert code.difficulty in ("complex", "advanced")


# ---------------------------------------------------------------------------
# Matching: each dimension, combinations, near-neighbour nonmatch
# ---------------------------------------------------------------------------

def test_match_each_dimension_and_combination(store):
    Session, db = store
    profile = build_task_profile(MATCHED_TEXT, user_id="u1")

    for match in (
        {"difficulty": ["advanced"]},
        {"category": ["code"]},
        {"domain": ["finance"]},
        {"difficulty": ["advanced"], "category": ["code"]},
        {"difficulty": ["advanced"], "category": ["code"],
         "domain": ["finance"]},
        {"category": ["planning", "code"], "domain": ["sales", "finance"]},
    ):
        rule = ap.create_never_rule(
            db, "u1", name="rule", match=match)
        decision = ap.evaluate_never_autonomous(db, "u1", profile)
        assert decision["outcome"] == ap.NEVER_OUTCOME_REVIEW, match
        assert rule["id"] in decision["rule_ids"]
        ap.delete_never_rule(db, "u1", rule["id"])


def test_near_neighbour_nonmatch_is_unaffected(store):
    Session, db = store
    ap.create_never_rule(
        db, "u1", name="finance advanced",
        match={"difficulty": ["advanced"], "domain": ["finance"]})
    near = build_task_profile(NEAR_MATCH_TEXT, user_id="u1")
    decision = ap.evaluate_never_autonomous(db, "u1", near)
    assert decision["outcome"] == ap.NEVER_OUTCOME_UNAFFECTED
    assert decision["matched"] is False

    # A present, contradicted dimension proves a nonmatch even if another
    # dimension happens to match: ALL specified dimensions must match.
    finance_only = build_task_profile(FINANCE_TEXT, user_id="u1")
    assert finance_only.domain == "finance"
    contradiction = ap.create_never_rule(
        db, "u1", name="finance but advanced code",
        match={"difficulty": ["advanced"], "category": ["code"],
               "domain": ["finance"]})
    decision = ap.evaluate_never_autonomous(db, "u1", finance_only)
    # difficulty=simple contradicts advanced -> nonmatch
    assert decision["outcome"] == ap.NEVER_OUTCOME_UNAFFECTED
    ap.delete_never_rule(db, "u1", contradiction["id"])


# ---------------------------------------------------------------------------
# Mature/graduated + independent of mutable agent.category
# ---------------------------------------------------------------------------

def test_graduation_and_category_cannot_bypass(store, monkeypatch):
    Session, db = store
    _agent(db, status="supervised")
    _allow_gate(monkeypatch, status="autonomous")
    ap.create_never_rule(
        db, "u1", name="finance advanced",
        match={"difficulty": ["advanced"], "domain": ["finance"]})
    profile = build_task_profile(MATCHED_TEXT, user_id="u1")

    # Career graduation / trust / capability changes do not waive the rule.
    db.query(AgentRegistry).filter(AgentRegistry.id == "hire-1").update({
        "status": "autonomous",
        "confidence_score": 0.99,
        "configuration": {"capability_maturities": {"canvas_edit": "autonomous"}},
        "category": "Finance",
    })
    db.commit()
    gate = ap.gate_for_topic(
        db, "u1", "canvas_edit", "hire-1", task_profile=profile)
    assert gate["outcome"] == ap.OUTCOME_PROPOSE
    assert gate["maturity"]["ok"] is True
    assert gate["never_autonomous"]["matched"] is True
    assert "Never-autonomous" in gate["reason"]


@pytest.mark.asyncio
async def test_governance_forces_review_before_effect(store, monkeypatch):
    Session, db = store
    _agent(db, status="autonomous")
    ap.create_never_rule(
        db, "u1", name="finance advanced",
        match={"difficulty": ["advanced"], "domain": ["finance"]})
    profile = build_task_profile(MATCHED_TEXT, user_id="u1")

    gov = AgentGovernanceService(db, workspace_id="default", tenant_id=None)
    monkeypatch.setattr(
        gov, "_check_budget_async",
        AsyncMock(return_value={"allowed": True}))
    decision = await gov.can_perform_action_async(
        "hire-1", "update_canvas", task_profile=profile)
    assert decision["requires_human_approval"] is True
    assert decision["never_autonomous"]["matched"] is True
    assert "Never-autonomous" in decision["reason"]

    # Same agent/action without a never policy is unchanged.
    ap.delete_never_rule(db, "u1", ap.list_never_rules(db, "u1")[0]["id"])
    clean = await gov.can_perform_action_async(
        "hire-1", "update_canvas", task_profile=profile)
    assert clean["requires_human_approval"] is False
    assert clean["never_autonomous"]["applicable"] is False


# ---------------------------------------------------------------------------
# Per-execution approval is not a blanket waiver
# ---------------------------------------------------------------------------

def test_approval_clearance_is_per_execution(store):
    Session, db = store
    ap.create_never_rule(
        db, "u1", name="finance advanced",
        match={"difficulty": ["advanced"], "domain": ["finance"]})
    profile = build_task_profile(MATCHED_TEXT, user_id="u1")
    decision = ap.evaluate_never_autonomous(db, "u1", profile)
    assert decision["outcome"] == ap.NEVER_OUTCOME_REVIEW

    approved_context = {}
    ap.grant_never_autonomous_clearance(approved_context, decision)
    assert ap.has_never_autonomous_clearance(approved_context) is True

    # A different execution has no clearance and re-evaluates to review.
    other_context = {}
    assert ap.has_never_autonomous_clearance(other_context) is False
    assert ap.evaluate_never_autonomous(
        db, "u1", profile)["outcome"] == ap.NEVER_OUTCOME_REVIEW
    # The rule is untouched by the approval.
    rules = ap.list_never_rules(db, "u1")
    assert len(rules) == 1 and rules[0]["enabled"] is True

    # A blanket-ish clearance for the OLD rule does not cover a NEW rule
    # added after the human decision. The fresh evaluation's rule ids must be
    # a subset of what was approved.
    ap.create_never_rule(
        db, "u1", name="also code", match={"category": ["code"]})
    fresh = ap.evaluate_never_autonomous(db, "u1", profile)
    assert fresh["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert ap.has_never_autonomous_clearance(
        approved_context, required_rule_ids=fresh["rule_ids"]) is False
    assert ap.has_never_autonomous_clearance(
        approved_context, required_rule_ids=decision["rule_ids"]) is True


# ---------------------------------------------------------------------------
# Missing / untrusted metadata fails closed
# ---------------------------------------------------------------------------

def test_missing_metadata_forces_review(store):
    Session, db = store
    ap.create_never_rule(
        db, "u1", name="finance advanced",
        match={"difficulty": ["advanced"], "domain": ["finance"]})

    no_profile = ap.evaluate_never_autonomous(db, "u1", None)
    assert no_profile["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert no_profile["potential"] is True
    assert no_profile["metadata_state"] == "missing"

    untrusted = ap.evaluate_never_autonomous(
        db, "u1", {"difficulty": "advanced", "domain": "finance"})
    assert untrusted["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert untrusted["metadata_state"] == "untrusted"

    # Partial profile: rule constrains a missing dimension -> review.
    partial = build_task_profile(FINANCE_TEXT, user_id="u1")  # no difficulty? present
    assert partial.difficulty is not None
    # Remove one dimension through a normal profile with no domain.
    no_domain = build_task_profile("Debug the python api endpoint", user_id="u1")
    assert no_domain.domain is None
    adomain_rule = ap.create_never_rule(
        db, "u1", name="domain only", match={"domain": ["finance"]})
    decision = ap.evaluate_never_autonomous(db, "u1", no_domain)
    assert decision["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert decision["potential"] is True
    ap.delete_never_rule(db, "u1", adomain_rule["id"])


# ---------------------------------------------------------------------------
# Stale edits / revision / invalid bodies
# ---------------------------------------------------------------------------

def test_stale_rule_edits_are_visible_immediately(store):
    Session, db = store
    rule = ap.create_never_rule(
        db, "u1", name="finance advanced",
        match={"difficulty": ["advanced"], "domain": ["finance"]})
    profile = build_task_profile(MATCHED_TEXT, user_id="u1")
    assert ap.evaluate_never_autonomous(
        db, "u1", profile)["outcome"] == ap.NEVER_OUTCOME_REVIEW

    ap.update_never_rule(
        db, "u1", rule["id"], name="disabled",
        match={"difficulty": ["advanced"], "domain": ["finance"]},
        enabled=False)
    assert ap.evaluate_never_autonomous(
        db, "u1", profile)["outcome"] == ap.NEVER_OUTCOME_UNAFFECTED

    with pytest.raises(ap.NeverRuleConflict):
        ap.update_never_rule(
            db, "u1", rule["id"], name="stale",
            match={"domain": ["finance"]}, expected_revision=1)

    with pytest.raises(ap.NeverRuleValidationError):
        ap.create_never_rule(
            db, "u1", name="bad", match={"difficulty": ["impossible"]})
    with pytest.raises(ap.NeverRuleValidationError):
        ap.create_never_rule(db, "u1", name="empty", match={})


# ---------------------------------------------------------------------------
# Cross-user / cross-scope isolation + persistence
# ---------------------------------------------------------------------------

def test_cross_user_and_scope_isolation(store):
    Session, db = store
    profile_u1 = build_task_profile(MATCHED_TEXT, user_id="u1")
    ap.create_never_rule(
        db, "u1", name="u1 rule", match={"domain": ["finance"]})

    # Another user is unaffected by u1's rule.
    assert ap.evaluate_never_autonomous(
        db, "u2", profile_u1)["outcome"] == ap.NEVER_OUTCOME_UNAFFECTED

    # Workspace narrowing: a rule created for workspace A does not match the
    # same user's task in workspace B, but NULL/default scope does.
    ws_rule = ap.create_never_rule(
        db, "u1", name="workspace A",
        match={"domain": ["finance"]},
        workspace_id="ws-a", tenant_id="tenant-a")
    in_a = ap.evaluate_never_autonomous(
        db, "u1", profile_u1, workspace_id="ws-a", tenant_id="tenant-a")
    in_b = ap.evaluate_never_autonomous(
        db, "u1", profile_u1, workspace_id="ws-b", tenant_id="tenant-a")
    assert in_a["outcome"] == ap.NEVER_OUTCOME_REVIEW
    # The default-scope rule still applies in B; that is intentional
    # Personal-first semantics (NULL is not "no owner", it is default scope).
    assert in_b["outcome"] == ap.NEVER_OUTCOME_REVIEW
    ap.delete_never_rule(db, "u1", ws_rule["id"])
    ap.delete_never_rule(
        db, "u1", ap.list_never_rules(db, "u1")[0]["id"])
    only_null = ap.create_never_rule(
        db, "u1", name="default", match={"domain": ["finance"]})
    assert ap.evaluate_never_autonomous(
        db, "u1", profile_u1, workspace_id="ws-b",
        tenant_id="tenant-a")["outcome"] == ap.NEVER_OUTCOME_REVIEW
    ap.delete_never_rule(db, "u1", only_null["id"])


def test_durable_readback_after_new_session(store):
    Session, db = store
    rule = ap.create_never_rule(
        db, "u1", name="persisted", match={"domain": ["finance"]})
    db.close()

    fresh = Session()
    try:
        rules = ap.list_never_rules(fresh, "u1")
        assert len(rules) == 1
        assert rules[0]["id"] == rule["id"]
        profile = build_task_profile(MATCHED_TEXT, user_id="u1")
        assert ap.evaluate_never_autonomous(
            fresh, "u1", profile)["rule_ids"] == [rule["id"]]
        # Cross-user cannot see/mutate it.
        assert ap.list_never_rules(fresh, "u2") == []
        with pytest.raises(ap.NeverRuleNotFound):
            ap.update_never_rule(
                fresh, "u2", rule["id"], name="hijack",
                match={"domain": ["finance"]})
    finally:
        fresh.close()


# ---------------------------------------------------------------------------
# HTTP contract
# ---------------------------------------------------------------------------

def _http_app(db):
    from api.autonomy_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    return app


def _user(uid="u1", workspace_id=None, tenant_id=None):
    return SimpleNamespace(
        id=uid, workspace_id=workspace_id, tenant_id=tenant_id)


def test_http_crud_scope_and_contract(store):
    Session, db = store
    app = _http_app(db)
    app.dependency_overrides[get_current_user] = lambda: _user("u1")
    client = TestClient(app)

    empty = client.get("/api/autonomy/never-rules")
    assert empty.status_code == 200
    assert empty.json()["rules"] == []

    created = client.post(
        "/api/autonomy/never-rules",
        json={
            "name": "Finance advanced",
            "enabled": True,
            "match": {"difficulty": ["advanced"], "domain": ["Finance"]},
        },
    )
    assert created.status_code == 201
    rule = created.json()["rule"]
    assert rule["match"]["domain"] == ["finance"]
    assert rule["scope"]["user_id"] == "u1"

    listed = client.get("/api/autonomy/never-rules").json()
    assert listed["count"] == 1
    assert listed["dimensions"]["difficulty"] == [
        "simple", "moderate", "complex", "advanced"]

    # 409 top-level contract on stale revision.
    conflict = client.put(
        f"/api/autonomy/never-rules/{rule['id']}",
        json={
            "name": "updated",
            "enabled": False,
            "match": {"domain": ["finance"]},
            "expected_revision": 999,
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "rule_revision_conflict"
    assert conflict.json()["current_revision"] == 1

    updated = client.put(
        f"/api/autonomy/never-rules/{rule['id']}",
        json={
            "name": "updated",
            "enabled": False,
            "match": {"domain": ["finance"]},
            "expected_revision": 1,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["rule"]["enabled"] is False
    assert updated.json()["rule"]["revision"] == 2

    invalid = client.post(
        "/api/autonomy/never-rules",
        json={"name": "bad", "match": {"difficulty": ["impossible"]}},
    )
    assert invalid.status_code == 400

    # Different authenticated user cannot mutate or delete u1's rule.
    app.dependency_overrides[get_current_user] = lambda: _user("u2")
    other_client = TestClient(app)
    assert other_client.put(
        f"/api/autonomy/never-rules/{rule['id']}",
        json={"name": "hijack", "match": {"domain": ["finance"]}},
    ).status_code == 404
    assert other_client.delete(
        f"/api/autonomy/never-rules/{rule['id']}").status_code == 404
    assert other_client.get("/api/autonomy/never-rules").json()["count"] == 0

    app.dependency_overrides[get_current_user] = lambda: _user("u1")
    deleted = client.delete(f"/api/autonomy/never-rules/{rule['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get("/api/autonomy/never-rules").json()["count"] == 0


# ---------------------------------------------------------------------------
# Final shared-dispatch guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_guard_blocks_matched_task_before_handler(store):
    Session, db = store
    ap.create_never_rule(
        db, "u1", name="finance advanced",
        match={"difficulty": ["advanced"], "domain": ["finance"]})
    profile = build_task_profile(MATCHED_TEXT, user_id="u1")

    @contextlib.contextmanager
    def _session():
        yield db

    from core import action_registry as registry_module
    from integrations import mcp_service as mcp_module

    with patch("core.database.get_db_session", _session), patch.object(
        registry_module.action_registry, "get_action",
        return_value=object(),
    ), patch.object(
        registry_module.action_registry, "execute_action",
        new=AsyncMock(return_value={"ok": True}),
    ):
        context = {
            "user_id": "u1",
            TASK_PROFILE_CONTEXT_KEY: profile,
        }
        blocked = await mcp_module.mcp_service.call_tool(
            "arbitrary_effect", {"x": 1}, context)
        assert blocked["blocked_by"] == "never_autonomous"
        assert blocked["requires_human_approval"] is True
        assert blocked["never_autonomous"]["matched"] is True

        # Missing trusted metadata, with the owner's rules configured, is
        # also fail-closed rather than a silent skip.
        missing = await mcp_module.mcp_service.call_tool(
            "arbitrary_effect", {"x": 1}, {"user_id": "u1"})
        assert missing["blocked_by"] == "never_autonomous"
        assert missing["never_autonomous"]["metadata_state"] == "missing"

        # Server-issued clearance represents the specific human approval.
        ap.grant_never_autonomous_clearance(
            context,
            ap.evaluate_never_autonomous(db, "u1", profile),
        )
        allowed = await mcp_module.mcp_service.call_tool(
            "arbitrary_effect", {"x": 1}, context)
        assert allowed == {"ok": True}
