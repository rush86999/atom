"""Deterministic same-second restore ordering and no-change controls.

Real SQLAlchemy SQLite rows with explicit opaque ids, real restore/read tools,
no random-UUID tie ordering. Covers contentless latest event rows and a
fresh child-process readback.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import core.database as db_mod
import core.models  # noqa: F401
from core.database import Base
from core.models import CanvasAudit, Tenant, User, UserStatus


AT = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)


def _row(row_id, canvas_id, tenant_id, user_id, action, details, at, canvas_type="docs"):
    return CanvasAudit(
        id=row_id,
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        user_id=user_id,
        action_type=action,
        canvas_type=canvas_type,
        details_json=details,
        created_at=at,
    )


@pytest.fixture()
def env(tmp_path):
    db_path = tmp_path / "restore_ordering.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    tenant = Tenant(
        id="restore-tenant", name="Restore", subdomain="restore-tests",
        edition="personal", is_active=True)
    user = User(
        id="restore-owner", email="restore-owner@example.invalid",
        hashed_password="h", first_name="Restore", last_name="Owner",
        role="member", status=UserStatus.ACTIVE.value, is_active=True,
        tenant_id="restore-tenant")
    foreign = User(
        id="restore-foreign", email="restore-foreign@example.invalid",
        hashed_password="h", first_name="Restore", last_name="Foreign",
        role="member", status=UserStatus.ACTIVE.value, is_active=True,
        tenant_id="restore-tenant")
    db.add_all([tenant, user, foreign])
    db.commit()

    original = db_mod.get_db_session

    @contextmanager
    def _session():
        yield db

    db_mod.get_db_session = _session
    try:
        yield SimpleNamespace(
            db=db, Session=Session, engine=engine, path=str(db_path),
            user=user, foreign=foreign,
        )
    finally:
        db_mod.get_db_session = original
        db.close()
        engine.dispose()


def _restore(user_id, canvas_id, audit_id):
    from tools.canvas_crud_tool import restore_canvas_version
    return asyncio.run(restore_canvas_version(user_id, canvas_id, audit_id))


def _read(user_id, canvas_id):
    from tools.canvas_crud_tool import read_canvas
    return asyncio.run(read_canvas(user_id, canvas_id))


def test_same_second_tie_restore_appends_after_authoritative_bad_edit(env):
    good = _row("a-000-good", "cv-tie", "restore-tenant", env.user.id, "present",
                {"title": "good", "content": "good draft"}, AT)
    bad = _row("a-999-bad", "cv-tie", "restore-tenant", env.user.id, "update",
               {"title": "bad", "content": "bad edit"}, AT)
    env.db.add(good)
    env.db.commit()
    env.db.add(bad)
    env.db.commit()

    current = _read(env.user.id, "cv-tie")
    assert current["success"] is True
    assert current["content"] == "bad edit", current

    before = env.db.query(CanvasAudit).filter(CanvasAudit.canvas_id == "cv-tie").count()
    result = _restore(env.user.id, "cv-tie", good.id)
    assert result["success"] is True, result
    after = env.db.query(CanvasAudit).filter(CanvasAudit.canvas_id == "cv-tie").count()
    assert after == before + 1, result

    fresh = _read(env.user.id, "cv-tie")
    assert fresh["success"] is True
    assert fresh["content"] == "good draft", fresh
    latest = (
        env.db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == "cv-tie")
        .order_by(CanvasAudit.created_at.desc(), CanvasAudit.id.desc())
        .first()
    )
    assert fresh["audit_id"] == latest.id, fresh
    assert fresh["created_at"], fresh
    assert fresh["revision_audit_id"] == latest.id, fresh

    # Fresh child process reads the same durable rows.
    script = (
        "import json, sqlite3, sys\n"
        "c = sqlite3.connect(sys.argv[1])\n"
        "rows = c.execute('select id, details_json from canvas_audit where canvas_id=? "
        "order by created_at desc, id desc', (sys.argv[2],)).fetchall()\n"
        "print(json.dumps({'count': len(rows), 'latest_id': rows[0][0], "
        "'latest_details': rows[0][1]}))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, env.path, "cv-tie"],
        capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout.strip().splitlines()[-1])
    assert summary["count"] == after
    assert "good draft" in summary["latest_details"]


def test_contentless_latest_and_genuine_nochange_append_nothing(env):
    good = _row("a-000-good", "cv-nochange", "restore-tenant", env.user.id, "present",
                {"title": "good", "content": "good draft"}, AT)
    event = _row("a-999-event", "cv-nochange", "restore-tenant", env.user.id, "email_send",
                 {"to": "a@b.invalid"}, AT + timedelta(seconds=1), canvas_type="email")
    env.db.add(good)
    env.db.commit()
    env.db.add(event)
    env.db.commit()

    current = _read(env.user.id, "cv-nochange")
    assert current["success"] is True
    assert current["content"] == "good draft", current

    before = env.db.query(CanvasAudit).filter(CanvasAudit.canvas_id == "cv-nochange").count()
    result = _restore(env.user.id, "cv-nochange", good.id)
    assert result["success"] is True, result
    assert result.get("no_change") is True, result
    after = env.db.query(CanvasAudit).filter(CanvasAudit.canvas_id == "cv-nochange").count()
    assert after == before, result


def test_event_only_row_between_versions_restore_is_append_only(env):
    good = _row("a-000-good", "cv-event-between", "restore-tenant", env.user.id, "present",
                {"title": "good", "content": "good draft"}, AT)
    event = _row("a-500-event", "cv-event-between", "restore-tenant", env.user.id, "email_send",
                 {"to": "a@b.invalid"}, AT + timedelta(seconds=1), canvas_type="email")
    bad = _row("a-999-bad", "cv-event-between", "restore-tenant", env.user.id, "update",
               {"title": "bad", "content": "bad edit"}, AT + timedelta(seconds=2))
    env.db.add_all([good, event, bad])
    env.db.commit()

    result = _restore(env.user.id, "cv-event-between", good.id)
    assert result["success"] is True, result
    fresh = _read(env.user.id, "cv-event-between")
    assert fresh["content"] == "good draft", fresh
    latest = (
        env.db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == "cv-event-between")
        .order_by(CanvasAudit.created_at.desc(), CanvasAudit.id.desc())
        .first()
    )
    assert latest.details_json["restored_from"]["audit_id"] == good.id


def test_foreign_restore_refused_zero_effect(env):
    good = _row("a-000-good", "cv-foreign", "restore-tenant", env.user.id, "present",
                {"title": "good", "content": "good draft"}, AT)
    env.db.add(good)
    env.db.commit()
    before = env.db.query(CanvasAudit).filter(CanvasAudit.canvas_id == "cv-foreign").count()
    result = _restore(env.foreign.id, "cv-foreign", good.id)
    assert result["success"] is False, result
    after = env.db.query(CanvasAudit).filter(CanvasAudit.canvas_id == "cv-foreign").count()
    assert after == before


def test_equal_body_different_title_restores_requested_title(env):
    old = _row("a-old", "root-title", "restore-tenant", env.user.id, "present",
               {"title": "Reviewed title", "content": "same body"}, AT)
    current = _row("z-new", "root-title", "restore-tenant", env.user.id, "update",
                   {"title": "Accidental title", "content": "same body"},
                   AT + timedelta(seconds=1))
    env.db.add_all([old, current])
    env.db.commit()

    result = _restore(env.user.id, "root-title", old.id)
    visible = _read(env.user.id, "root-title")
    assert result["success"] is True, result
    assert result.get("no_change") is not True, result
    assert visible["title"] == "Reviewed title", visible
    assert env.db.query(CanvasAudit).filter_by(canvas_id="root-title").count() == 3


def test_tied_contentless_event_cannot_false_nochange(env):
    old = _row("a-old", "root-event-tie", "restore-tenant", env.user.id, "present",
               {"title": "Old", "content": "older body"}, AT)
    requested = _row("b-new", "root-event-tie", "restore-tenant", env.user.id, "update",
                     {"title": "New", "content": "requested body"},
                     AT + timedelta(seconds=1))
    event = _row("z-event", "root-event-tie", "restore-tenant", env.user.id, "email_send",
                 {"to": "recipient@example.invalid"},
                 AT + timedelta(seconds=1), canvas_type="email")
    env.db.add_all([old, requested, event])
    env.db.commit()

    assert _read(env.user.id, "root-event-tie")["content"] == "requested body"
    result = _restore(env.user.id, "root-event-tie", requested.id)
    visible = _read(env.user.id, "root-event-tie")
    assert result["success"] is True, result
    assert visible["content"] == "requested body", visible


def test_genuine_current_body_and_title_nochange_zero_effect(env):
    old = _row("a-old", "root-nochange", "restore-tenant", env.user.id, "present",
               {"title": "Current", "content": "current body"}, AT)
    current = _row("z-new", "root-nochange", "restore-tenant", env.user.id, "update",
                   {"title": "Current", "content": "current body"},
                   AT + timedelta(seconds=1))
    env.db.add_all([old, current])
    env.db.commit()
    before = env.db.query(CanvasAudit).filter_by(canvas_id="root-nochange").count()
    result = _restore(env.user.id, "root-nochange", old.id)
    after = env.db.query(CanvasAudit).filter_by(canvas_id="root-nochange").count()
    assert result["success"] is True, result
    assert result.get("no_change") is True, result
    assert after == before


def test_explicit_empty_title_is_restored_not_dropped(env):
    old = _row("a-old", "root-empty-title", "restore-tenant", env.user.id, "present",
               {"title": "", "content": "same body"}, AT)
    current = _row("z-new", "root-empty-title", "restore-tenant", env.user.id, "update",
                   {"title": "Accidental title", "content": "same body"},
                   AT + timedelta(seconds=1))
    env.db.add_all([old, current])
    env.db.commit()
    result = _restore(env.user.id, "root-empty-title", old.id)
    visible = _read(env.user.id, "root-empty-title")
    assert result["success"] is True, result
    assert result.get("no_change") is not True, result
    assert visible["title"] == "", visible


def test_body_behind_more_than_fifty_event_stamps_is_still_visible(env):
    good = _row("a-good", "root-long-events", "restore-tenant", env.user.id, "present",
                {"title": "Good", "content": "good body"}, AT)
    bad = _row("b-bad", "root-long-events", "restore-tenant", env.user.id, "update",
               {"title": "Bad", "content": "bad body"}, AT + timedelta(seconds=1))
    env.db.add_all([good, bad])
    for index in range(60):
        env.db.add(_row(
            f"e-{index:03d}", "root-long-events", "restore-tenant", env.user.id,
            "email_send", {"to": "a@b.invalid"},
            AT + timedelta(seconds=2 + index), canvas_type="email"))
    env.db.commit()

    assert _read(env.user.id, "root-long-events")["content"] == "bad body"
    result = _restore(env.user.id, "root-long-events", good.id)
    fresh = _read(env.user.id, "root-long-events")
    assert result["success"] is True, result
    assert fresh["content"] == "good body", fresh


def test_repeat_restore_after_success_is_nochange_without_second_row(env):
    old = _row("a-old", "root-repeat", "restore-tenant", env.user.id, "present",
               {"title": "Old", "content": "old body"}, AT)
    current = _row("z-new", "root-repeat", "restore-tenant", env.user.id, "update",
                   {"title": "New", "content": "new body"},
                   AT + timedelta(seconds=1))
    env.db.add_all([old, current])
    env.db.commit()

    first = _restore(env.user.id, "root-repeat", old.id)
    assert first["success"] is True, first
    after_first = env.db.query(CanvasAudit).filter_by(canvas_id="root-repeat").count()
    second = _restore(env.user.id, "root-repeat", old.id)
    after_second = env.db.query(CanvasAudit).filter_by(canvas_id="root-repeat").count()
    assert second["success"] is True, second
    assert second.get("no_change") is True, second
    assert after_second == after_first


def test_ordinary_read_reports_actual_body_audit_id_and_timestamp(env):
    body = _row("a-body", "root-provenance", "restore-tenant", env.user.id, "present",
                {"title": "Body", "content": "body text"}, AT)
    env.db.add(body)
    env.db.commit()

    read = _read(env.user.id, "root-provenance")
    assert read["success"] is True, read
    assert read["content"] == "body text", read
    assert read["audit_id"] == "a-body", read
    assert read["revision_audit_id"] == "a-body", read
    assert read["created_at"], read


@pytest.mark.parametrize("body", ["", 0, [], {}], ids=["empty-string", "zero", "empty-list", "empty-dict"])
def test_falsy_body_is_preserved_and_provenanced(env, body):
    row = _row(f"a-falsy-{type(body).__name__}", "root-falsy", "restore-tenant",
               env.user.id, "present", {"title": "Falsy", "content": body}, AT)
    env.db.add(row)
    env.db.commit()
    read = _read(env.user.id, "root-falsy")
    assert read["success"] is True, read
    assert read["content"] == body, read
    assert read["audit_id"] == row.id, read
    assert read["created_at"], read


def test_latest_submit_event_with_body_does_not_hide_older_content(env):
    body = _row("a-body", "root-submit-event", "restore-tenant", env.user.id,
                "present", {"title": "Body", "content": "actual body"}, AT)
    submit = _row("z-submit", "root-submit-event", "restore-tenant", env.user.id,
                  "submit", {"data": {"form": "submission"}}, AT + timedelta(seconds=1))
    env.db.add_all([body, submit])
    env.db.commit()

    read = _read(env.user.id, "root-submit-event")
    assert read["success"] is True, read
    assert read["content"] == "actual body", read
    assert read["audit_id"] == body.id, read
    assert read["revision_audit_id"] == submit.id, read
