"""Playbook draft editing + retrieval shape (Playbook Journey P1).

- PlaybookService.update: draft-only in-place edits ("edit steps first" in
  the review queue); approved/missing rows return None (the route maps a
  non-draft hit to 409).
- get_relevant: includes the playbook id so the co-editor result can carry
  matched_playbooks the UI can render as a chip (P3 transparency).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import Playbook
from core.playbook_service import PlaybookService

TABLES = [Playbook.__table__]


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def svc(db):
    return PlaybookService(db, tenant_id="default")


def test_update_edits_a_draft(db, svc):
    row = svc.create("Draft rule", steps=["step one"], source="learned",
                     approval_state="draft", trigger_keywords=["stock"])
    updated = svc.update(row.id, steps=["step one", "step two"],
                         trigger_keywords=["stock", "inventory"])
    assert updated is not None
    assert updated.steps == ["step one", "step two"]
    assert updated.trigger_keywords == ["stock", "inventory"]
    assert svc.get(row.id).steps == ["step one", "step two"]


def test_update_refuses_approved_playbooks(db, svc):
    row = svc.create("Active process", steps=["s"], source="authored",
                     approval_state="approved")
    assert svc.update(row.id, steps=["hacked"]) is None
    assert svc.get(row.id).steps == ["s"]


def test_update_missing_returns_none(db, svc):
    assert svc.update("nope", steps=["s"]) is None


def test_get_relevant_includes_id_for_ui_deep_link(db, svc):
    svc.create("Quote process", steps=["check price list"], source="authored",
               approval_state="approved", trigger_keywords=["quote"])
    hits = svc.get_relevant("please update the quote with the new total",
                            canvas_type="email")
    assert len(hits) == 1
    assert hits[0]["id"]
    assert hits[0]["name"] == "Quote process"


def test_get_relevant_respects_off_mode(db, svc, monkeypatch):
    svc.create("Quote process", steps=["s"], source="authored",
               approval_state="approved", trigger_keywords=["quote"])
    monkeypatch.setattr("core.playbook_service.playbook_mode", lambda: "off")
    assert svc.get_relevant("quote it") == []
