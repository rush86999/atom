"""Canvas ORIGIN provenance: hydration from the create-audit row and its
journey into the prompts.

Live incident (2026-09-02, canvas da27bb76…): the panel session started
empty, so "why was the draft written this way then?" got an honest "I don't
know who originally wrote that language" — even though the origin thread
(aca15165…) was recorded in the canvas_audit create row, one query away.
The create row's session_id is now hydrated into context['canvas_provenance'].
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.chat_canvas_editor import _provenance_section
from core.models import Base, CanvasAudit, ChatMessage

CANVAS_ID = "da27bb76-3f37-4f15-9f40-16c61b37b595"
ORIGIN_SESSION = "aca15165-d9e1-4011-85a9-b3b0f060ab4f"
PANEL_SESSION = "ca7c4e26-1b98-45b0-a42c-886b47d7010e"


@pytest.fixture()
def db_session():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, expire_on_commit=False)
    session = Sess()
    try:
        yield session
    finally:
        session.close()
        eng.dispose()
        os.unlink(path)


class _SessionCtx:
    """`with get_db_session() as db` shim over an existing test session."""

    def __init__(self, s):
        self._s = s

    def __enter__(self):
        return self._s

    def __exit__(self, *exc):
        return False


def _seed_origin(db_session):
    db_session.add(CanvasAudit(
        canvas_id=CANVAS_ID, tenant_id="default",
        action_type="create", session_id=ORIGIN_SESSION,
    ))
    t0 = datetime(2026, 9, 2, 2, 13, 0)
    rows = [
        ("user", "we were talking about mark kellam. why blumetric?"),
        ("assistant", "You're right — my mistake. Let me focus on Mark Kellam."),
        ("user", "generate the draft"),
        ("assistant", "Based on the email thread, Mark Kellam is from WFS Ltd. "
                      "Here is the draft…"),
    ]
    for i, (role, content) in enumerate(rows):
        db_session.add(ChatMessage(
            conversation_id=ORIGIN_SESSION, tenant_id="default",
            role=role, content=content, created_at=t0 + timedelta(minutes=i),
        ))
    db_session.commit()


def _monkey_db(monkeypatch, db_session):
    import core.database as core_db
    monkeypatch.setattr(
        core_db, "get_db_session", lambda: _SessionCtx(db_session))


def test_hydrates_origin_messages_from_create_audit_row(db_session, monkeypatch):
    _seed_origin(db_session)
    _monkey_db(monkeypatch, db_session)

    from integrations.chat_routes import _canvas_provenance_context

    prov = _canvas_provenance_context(CANVAS_ID, PANEL_SESSION)
    assert prov is not None
    assert prov["session_id"] == ORIGIN_SESSION
    roles = [m["role"] for m in prov["messages"]]
    # chronological, both roles carried
    assert roles == ["user", "assistant", "user", "assistant"]
    assert "mark kellam" in prov["messages"][0]["content"]


def test_skips_when_canvas_was_created_in_this_session(db_session, monkeypatch):
    _seed_origin(db_session)
    _monkey_db(monkeypatch, db_session)

    from integrations.chat_routes import _canvas_provenance_context

    # the panel session IS the origin session — the live transcript
    # already carries it; duplicating it would double-count prompt space
    assert _canvas_provenance_context(CANVAS_ID, ORIGIN_SESSION) is None


def test_skips_without_a_create_audit_row(db_session, monkeypatch):
    _monkey_db(monkeypatch, db_session)

    from integrations.chat_routes import _canvas_provenance_context

    assert _canvas_provenance_context("no-such-canvas", PANEL_SESSION) is None


def test_skips_when_origin_conversation_is_empty(db_session, monkeypatch):
    db_session.add(CanvasAudit(
        canvas_id=CANVAS_ID, tenant_id="default",
        action_type="create", session_id="ghost-session",
    ))
    db_session.commit()
    _monkey_db(monkeypatch, db_session)

    from integrations.chat_routes import _canvas_provenance_context

    assert _canvas_provenance_context(CANVAS_ID, PANEL_SESSION) is None


# ───────────────── prompt-side shaping ─────────────────

def test_provenance_section_labels_and_bounds():
    prov = {
        "session_id": ORIGIN_SESSION,
        "messages": [
            {"role": "user", "content": "generate the draft"},
            {"role": "assistant", "content": "x" * 2000},
        ],
    }
    section = _provenance_section(prov)
    assert section.startswith("DRAFT ORIGIN")
    assert "NOT" in section and "evidence" in section
    assert "generate the draft" in section
    # assistant line bounded to 600 chars + trim marker
    assert "…(trimmed)" in section
    assert len(section) < 1200


def test_provenance_section_empty_safe():
    assert _provenance_section(None) == ""
    assert _provenance_section({"messages": []}) == ""
    assert _provenance_section({"messages": [{"role": "user", "content": " "}]}) == ""
