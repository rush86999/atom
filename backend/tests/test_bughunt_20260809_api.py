# -*- coding: utf-8 -*-
"""
Bug-hunt wave 2026-08-09 — api/feedback_enhanced.py, api/analytics_dashboard_routes.py,
integrations/line_routes.py, api/canvas_docs_routes.py (TDD RED->GREEN).

Bugs (all reproduced RED before the minimal source fix):
1.  feedback_enhanced POST /api/feedback/submit stores the client-supplied
    body ``user_id`` into AgentFeedback.user_id -> any user can attribute
    feedback to anyone (RLHF data poisoning / audit forgery).
2.  analytics_dashboard_routes GET /api/analytics/patterns/{user_id} returns
    another user's behavioral communication patterns (most active hours,
    avg response time, message-type preferences) with no ownership check
    (cross-user IDOR on behavioral PII).
3.  integrations/line_routes POST /api/line/webhook FAILS OPEN: an invalid or
    missing X-Line-Signature only logs a warning and the event is still
    processed; plain ``!=`` comparison (timing oracle); empty
    LINE_CHANNEL_SECRET default lets an attacker forge the HMAC trivially.
4.  canvas_docs_routes GET /{canvas_id}/versions, POST /{canvas_id}/restore
    and GET /{canvas_id}/toc skip the ``_get_owned_docs_canvas_or_error``
    gate every sibling endpoint enforces (cross-user read + cross-user
    mutation of document content), and restore_version attributes the audit
    row to the client-supplied body ``user_id`` (forgery).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from core.models import AgentFeedback, AgentRegistry, CanvasAudit, Tenant, User

TABLES = [
    "tenants", "users", "agent_registry", "agent_feedback", "canvas_audit",
]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Base.metadata.tables[n] for n in TABLES if n in Base.metadata.tables],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant(db):
    if not db.query(Tenant).filter(Tenant.id == "t1").first():
        db.add(Tenant(id="t1", name="T", subdomain="t-default"))
    db.flush()


def _seed_user(db, user_id="user-1", email=None):
    _seed_tenant(db)
    if db.query(User).filter(User.id == user_id).first():
        return
    db.add(User(
        id=user_id, tenant_id="t1",
        email=email or f"{user_id}@x.com",
        first_name="A", last_name="B", hashed_password="pw",
        role="member", status="active",
    ))
    db.commit()


def _app_for(router_module, db, user_id="user-1", extra_overrides=None):
    app = FastAPI()
    app.include_router(router_module.router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    def override_user():
        return SimpleNamespace(id=user_id, role="member", is_admin=False)

    from core.auth import get_current_user as auth_current_user
    app.dependency_overrides[auth_current_user] = override_user
    for dep in (extra_overrides or {}):
        app.dependency_overrides[dep] = extra_overrides[dep]
    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# 1. api/feedback_enhanced.py — body user_id impersonation
# =============================================================================

class TestFeedbackEnhancedImpersonation:
    def test_submit_feedback_ignores_body_user_id(self, db_session):
        from api import feedback_enhanced

        _seed_user(db_session, "user-1", "u1@x.com")
        _seed_user(db_session, "user-victim", "victim@x.com")
        agent = AgentRegistry(
            id="agent-1", name="Test Agent", description="d", category="Operations",
            role="agent", module_path="operations.automations.inventory",
            class_name="InventoryAgent", status="active",
        )
        db_session.add(agent)
        db_session.commit()

        client = _app_for(feedback_enhanced, db_session, user_id="user-1")
        resp = client.post("/api/feedback/submit", json={
            "agent_id": "agent-1",
            "user_id": "user-victim",  # attacker tries to attribute to victim
            "thumbs_up_down": True,
        })
        assert resp.status_code == 200, resp.text

        row = db_session.query(AgentFeedback).first()
        assert row is not None
        assert row.user_id == "user-1", (
            f"feedback attributed to body-supplied user_id {row.user_id!r}, "
            "not the token identity"
        )


# =============================================================================
# 2. api/analytics_dashboard_routes.py — patterns/{user_id} IDOR
# =============================================================================

class TestAnalyticsPatternsIDOR:
    def test_foreign_user_patterns_403(self, db_session):
        from api import analytics_dashboard_routes
        from core.predictive_insights import (
            CommunicationPattern,
            get_predictive_insights_engine,
        )

        _seed_user(db_session, "user-1", "u1@x.com")
        engine = get_predictive_insights_engine()
        engine.user_patterns["victim-99"] = CommunicationPattern(
            user_id="victim-99",
            most_active_hours=[9, 10],
            most_active_platform="slack",
            avg_response_time=42.0,
            response_probability_by_hour={9: 0.8},
            preferred_message_types=["text"],
        )
        try:
            client = _app_for(analytics_dashboard_routes, db_session, user_id="user-1")
            resp = client.get("/api/analytics/patterns/victim-99")
            assert resp.status_code == 403, (
                f"cross-user pattern read returned {resp.status_code}: {resp.text}"
            )
        finally:
            engine.user_patterns.pop("victim-99", None)

    def test_own_patterns_200(self, db_session):
        from api import analytics_dashboard_routes
        from core.predictive_insights import (
            CommunicationPattern,
            get_predictive_insights_engine,
        )

        _seed_user(db_session, "user-1", "u1@x.com")
        engine = get_predictive_insights_engine()
        engine.user_patterns["user-1"] = CommunicationPattern(
            user_id="user-1",
            most_active_hours=[9],
            most_active_platform="email",
            avg_response_time=10.0,
            response_probability_by_hour={9: 0.5},
            preferred_message_types=["text"],
        )
        try:
            client = _app_for(analytics_dashboard_routes, db_session, user_id="user-1")
            resp = client.get("/api/analytics/patterns/user-1")
            assert resp.status_code == 200, resp.text
        finally:
            engine.user_patterns.pop("user-1", None)


# =============================================================================
# 3. integrations/line_routes.py — fail-open webhook
# =============================================================================

class TestLineWebhookFailClosed:
    def test_missing_signature_401(self, db_session, monkeypatch):
        from integrations import line_routes

        monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
        client = _app_for(line_routes, db_session, user_id="user-1")
        resp = client.post("/api/line/webhook", json={"events": []})
        assert resp.status_code == 401, (
            f"unsigned webhook accepted with {resp.status_code}: {resp.text}"
        )

    def test_bad_signature_401(self, db_session, monkeypatch):
        from integrations import line_routes

        monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
        client = _app_for(line_routes, db_session, user_id="user-1")
        resp = client.post(
            "/api/line/webhook",
            json={"events": []},
            headers={"X-Line-Signature": "deadbeef"},
        )
        assert resp.status_code == 401, (
            f"webhook with wrong signature accepted: {resp.status_code}: {resp.text}"
        )

    def test_unconfigured_secret_503(self, db_session, monkeypatch):
        from integrations import line_routes

        monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
        client = _app_for(line_routes, db_session, user_id="user-1")
        resp = client.post(
            "/api/line/webhook",
            json={"events": []},
            headers={"X-Line-Signature": "whatever"},
        )
        assert resp.status_code in (401, 503), (
            f"unconfigured webhook not fail-closed: {resp.status_code}"
        )

    def test_valid_signature_200(self, db_session, monkeypatch):
        from integrations import line_routes

        monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
        body = b'{"events": []}'
        digest = hmac.new(b"test-secret", body, hashlib.sha256).digest()
        sig = base64.b64encode(digest).decode()
        client = _app_for(line_routes, db_session, user_id="user-1")
        resp = client.post(
            "/api/line/webhook",
            content=body,
            headers={"X-Line-Signature": sig},
        )
        assert resp.status_code == 200, resp.text


# =============================================================================
# 4. api/canvas_docs_routes.py — missing ownership gate + user_id forgery
# =============================================================================

def _seed_docs_canvas(db, canvas_id="cv-1", owner="victim-99", versions=None):
    """Create the earliest CanvasAudit row for a docs canvas (owner marker)."""
    if versions is None:
        versions = [{
            "version_id": "v1",
            "content": "secret document",
            "author": owner,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "changes": "initial",
        }]
    db.add(CanvasAudit(
        id=f"audit-{canvas_id}",
        tenant_id="t1",
        user_id=owner,
        canvas_id=canvas_id,
        action_type="create",
        canvas_type="docs",
        details_json={"content": "secret document", "versions": versions},
    ))
    db.commit()


class TestCanvasDocsIDOR:
    def test_versions_foreign_canvas_403(self, db_session):
        from api import canvas_docs_routes

        _seed_user(db_session, "user-1", "u1@x.com")
        _seed_user(db_session, "victim-99", "v@x.com")
        _seed_docs_canvas(db_session, "cv-1", "victim-99")

        client = _app_for(canvas_docs_routes, db_session, user_id="user-1")
        resp = client.get("/api/canvas/docs/cv-1/versions")
        assert resp.status_code == 403, (
            f"foreign canvas versions readable: {resp.status_code}: {resp.text}"
        )

    def test_toc_foreign_canvas_403(self, db_session):
        from api import canvas_docs_routes

        _seed_user(db_session, "user-1", "u1@x.com")
        _seed_user(db_session, "victim-99", "v@x.com")
        _seed_docs_canvas(db_session, "cv-1", "victim-99")

        client = _app_for(canvas_docs_routes, db_session, user_id="user-1")
        resp = client.get("/api/canvas/docs/cv-1/toc")
        assert resp.status_code == 403, (
            f"foreign canvas toc readable: {resp.status_code}: {resp.text}"
        )

    def test_restore_foreign_canvas_403(self, db_session):
        from api import canvas_docs_routes

        _seed_user(db_session, "user-1", "u1@x.com")
        _seed_user(db_session, "victim-99", "v@x.com")
        _seed_docs_canvas(db_session, "cv-1", "victim-99")

        client = _app_for(canvas_docs_routes, db_session, user_id="user-1")
        resp = client.post("/api/canvas/docs/cv-1/restore", json={
            "user_id": "victim-99",
            "version_id": "v1",
        })
        assert resp.status_code == 403, (
            f"foreign canvas restorable: {resp.status_code}: {resp.text}"
        )

    def test_restore_attributes_to_token_user(self, db_session):
        from api import canvas_docs_routes

        _seed_user(db_session, "user-1", "u1@x.com")
        _seed_docs_canvas(db_session, "cv-1", "user-1")

        client = _app_for(canvas_docs_routes, db_session, user_id="user-1")
        resp = client.post("/api/canvas/docs/cv-1/restore", json={
            "user_id": "attacker-other",  # forged attribution attempt
            "version_id": "v1",
        })
        assert resp.status_code == 200, resp.text

        restore_row = (
            db_session.query(CanvasAudit)
            .filter(CanvasAudit.action_type == "restore_version")
            .first()
        )
        assert restore_row is not None
        assert restore_row.user_id == "user-1", (
            f"restore audit attributed to body user_id {restore_row.user_id!r}, "
            "not the token identity"
        )
