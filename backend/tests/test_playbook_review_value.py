"""The Training tab's playbook review queue must be readable by the human
doing the teaching.

Regression context (Sep 4, 2026): sleep-time drafts were named after the
pattern fingerprint ("[identity] recurring correction on 4c1986b1…") with
the same text as their only step, and every 6h maintenance cycle bumped the
version even though nothing changed — the supervisor's queue showed cards
like "learned v211 seen 211× needs review recurring correction on
4c1986b1…", which taught them nothing. These tests pin: human-readable
rule + occurrence count, no version inflation on identical re-runs, and
retirement of the legacy fingerprint-text drafts.
"""
import pytest

from core.exchange_memory_maintenance import _draft_playbooks
from core.models import Base, Canvas, IncidentEval, Playbook
from core.playbook_service import PlaybookService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, expire_on_commit=False)
    s = Sess()
    try:
        yield s
    finally:
        s.close()
    eng.dispose()


def _incident(canvas_id="c-abc", taxonomy="identity", value="Mark",
              occurrences=8, kind="excludes", **kw):
    return IncidentEval(
        tenant_id="default",
        canvas_id=canvas_id,
        canvas_type="email",
        taxonomy=taxonomy,
        instruction=f"canvas_id={canvas_id}; supervisor corrected the hire's draft",
        context_snapshot={},
        expected_property={"kind": kind, "value": value},
        source="correction",
        fingerprint=f"sha1:{canvas_id}|{taxonomy}|{value}",
        occurrences=occurrences,
        **kw,
    )


def test_draft_card_carries_human_readable_rule(db, monkeypatch):
    monkeypatch.setattr("core.playbook_service.playbook_mode", lambda: "auto")
    db.add(Canvas(id="c-abc", tenant_id="default", name="Re: Bandsaw quote",
                  created_by="u-1"))
    db.add(_incident())
    db.commit()

    summary = _draft_playbooks(db)
    assert summary["drafted"] == 1

    row = db.query(Playbook).filter(Playbook.source == "learned").first()
    assert row.name == '[identity] Never include "Mark"'
    assert row.steps == ['Never include \u201cMark\u201d in drafts of this kind '
                         '\u2014 the supervisor removed it in recurring corrections.']
    assert "From 8 recurring supervisor corrections" in row.description
    assert "Re: Bandsaw quote" in row.description
    assert "4c1986b1" not in row.name and "c-abc" not in row.name


def test_identical_rerun_does_not_inflate_version(db, monkeypatch):
    """The 6h cycle re-sees the same pattern forever; the version is a
    CONTENT version and must not become a fake 'seen N×' counter."""
    monkeypatch.setattr("core.playbook_service.playbook_mode", lambda: "auto")
    db.add(_incident())
    db.commit()

    _draft_playbooks(db)
    first = db.query(Playbook).filter(Playbook.source == "learned").first()
    assert first.version == 1

    _draft_playbooks(db)
    _draft_playbooks(db)
    db.refresh(first)
    assert first.version == 1

    # A REAL rule change refreshes content and bumps exactly once.
    inc = db.query(IncidentEval).first()
    inc.expected_property = {"kind": "includes", "value": "delivery date"}
    db.commit()
    summary = _draft_playbooks(db)
    db.refresh(first)
    assert summary["updated"] == 1
    assert first.version == 2
    assert first.steps == ['Include \u201cdelivery date\u201d in drafts of this '
                           'kind before they go out.']


def test_legacy_fingerprint_text_drafts_are_retired(db, monkeypatch):
    """The old '… recurring correction on <uuid>…' drafts taught the reviewer
    nothing — the sweep moves them out of 'needs review'."""
    monkeypatch.setattr("core.playbook_service.playbook_mode", lambda: "auto")
    db.add(Playbook(
        tenant_id="default", workspace_id=None,
        name="[identity] recurring correction on 4c1986b1\u2026",
        description="Auto-drafted from recurring supervisor corrections "
                    "(sleep-time). Review, edit, then approve.",
        steps=["[identity] recurring correction on 4c1986b1\u2026"],
        source="learned", approval_state="draft", version=211,
    ))
    db.commit()

    _draft_playbooks(db)
    legacy = db.query(Playbook).filter(
        Playbook.name.like("%recurring correction on %")).first()
    assert legacy.approval_state == "retired"


def test_draft_from_pattern_custom_content(db):
    """steps/description overrides land on the created draft (defaults keep
    the legacy pattern-text behavior pinned in test_installation_adaptation)."""
    svc = PlaybookService(db, tenant_id="default")
    row = svc.draft_from_pattern(
        "[tone] Never include \u201csorry\u201d",
        trigger_canvas_type="email",
        steps=["Never apologize on the company's behalf."],
        description="From 4 recurring corrections.",
    )
    assert row.steps == ["Never apologize on the company's behalf."]
    assert row.description == "From 4 recurring corrections."
    assert row.version == 1
