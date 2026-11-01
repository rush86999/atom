"""Approval must be an atomic compare-and-swap, not a stale-object commit.

The verifier's reproduction: session A loaded revision 1, session B committed
revision 2, then A approved its stale assessment. That accepted the old
assessment and overwrote the newer canvas content. These controls pin the
transaction boundary.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from core.database import Base
from core.models import Canvas


@pytest.fixture()
def store(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'atom.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    setup = Session()
    canvas = Canvas(
        id="canvas_concurrency_1", tenant_id="default", workspace_id="ws-1",
        created_by="user-1", name="Concurrency", canvas_type="sheet",
        content={}, status="active",
    )
    setup.add(canvas)
    setup.commit()
    yield Session, canvas
    setup.close()
    engine.dispose()


@pytest.fixture()
def user():
    return SimpleNamespace(
        id="user-1", workspace_id="ws-1", tenant_id="default",
        role="workspace_admin",
    )


def _manifest():
    return {
        "schema_version": 1,
        "base_component": "table",
        "operations": [
            "read", "select", "calculate", "assess", "edit", "export", "bind",
        ],
        "data_binding": {
            "subject_field": "Ref", "measure_field": "Amount",
            "status_field": "Status",
        },
        "editable_fields": ["Amount", "Status"],
        "teaching_binding": {"agent_id": "agent-1", "scope_id": "task-1"},
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "task_policy": (
            "Approve Amount >= 100 when Status is Open. Review 50-99. "
            "Deny below 50 or Closed."
        ),
        "outputs": ["xlsx"],
        "required_approvals": [],
    }


def _prepare(db, canvas, user):
    from core.canvas_capability_service import bind_dataset, set_manifest

    set_manifest(db, canvas, user, _manifest())
    bind_dataset(
        db, canvas, user,
        ["Ref", "Amount", "Status", "Note"],
        [
            ["R-1", 120, "Open", "alpha"],
            ["R-2", 75, "Open", "beta"],
            ["R-3", 20, "Closed", "gamma"],
            ["R-4", 95, "Open", "delta"],
        ],
        source={"file_name": "concurrency.csv", "sha256": "fixture-sha"},
    )


_FAKE = {}


def _fake_review(monkeypatch):
    from core import review_result

    async def fake_generate(llm, **kwargs):
        rev = _FAKE["revision"]
        assessments = [
            {
                "subject_id": subject,
                "decision": decision,
                "basis": ["fixture"],
                "evidence_ids": [f"ev:{subject}:{row}"],
                "policy_ids": [f"policy:{rev}"],
                "unresolved_requirements": [],
            }
            for subject, decision, row in (
                ("R-1", "APPROVE", 2), ("R-2", "REVIEW", 3),
                ("R-3", "DENY", 4), ("R-4", "REVIEW", 5),
            )
        ]
        return "```review_result\n" + json.dumps(
            {"assessments": assessments}) + "\n```"

    monkeypatch.setenv("ATOM_REVIEW_MODEL", "deepseek-flash")
    monkeypatch.setattr(review_result, "generate_structured_review", fake_generate)


def _assess(db, canvas, user):
    from core.canvas_capability_service import (
        assess_operation, get_manifest, policy_revision,
    )

    _FAKE["revision"] = policy_revision(get_manifest(canvas))
    return asyncio.run(assess_operation(
        db, canvas, user, "all rows", llm_service=object()))


def test_two_session_interleaving_refuses_stale_approval(store, user, monkeypatch):
    """Verifier's exact defect: stale session approval must not overwrite."""
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, current_revision, edit_operation,
        get_dataset,
    )

    Session, _ = store
    session_a = Session()
    session_b = Session()
    try:
        canvas_a = session_a.query(Canvas).first()
        _prepare(session_a, canvas_a, user)
        _fake_review(monkeypatch)
        assessment = _assess(session_a, canvas_a, user)
        assert current_revision(canvas_a) == 1

        # Session B commits a newer revision while A holds revision 1.
        canvas_b = session_b.query(Canvas).first()
        edit_operation(
            session_b, canvas_b, user,
            [{"row": 2, "column": "Amount", "value": 130}],
            expected_revision=1,
        )
        session_b.commit()
        assert current_revision(canvas_b) == 2

        with pytest.raises(CapabilityError) as exc:
            approve_assessment(
                session_a, canvas_a, user, assessment["execution_id"])
        assert exc.value.code in {"stale_assessment", "assessment_conflict"}

        # The newer work must be preserved, not overwritten by the stale copy.
        session_a.expire_all()
        fresh = session_a.query(Canvas).first()
        assert current_revision(fresh) == 2
        rows = get_dataset(fresh)["rows"]
        assert rows[0][1] == 130
    finally:
        session_a.close()
        session_b.close()


def test_conditional_update_matches_zero_rows_after_concurrent_write(
        store, user, monkeypatch):
    """The CAS predicate itself: observed revision 1 vs current 2."""
    from core.canvas_capability_service import (
        _cas_update_assessment_content, current_revision, edit_operation,
    )

    Session, _ = store
    session_a = Session()
    session_b = Session()
    try:
        canvas_a = session_a.query(Canvas).first()
        _prepare(session_a, canvas_a, user)
        _fake_review(monkeypatch)
        assessment = _assess(session_a, canvas_a, user)
        assert current_revision(canvas_a) == 1

        canvas_b = session_b.query(Canvas).first()
        edit_operation(
            session_b, canvas_b, user,
            [{"row": 2, "column": "Amount", "value": 130}],
            expected_revision=1,
        )
        session_b.commit()

        wrote = _cas_update_assessment_content(
            session_a, canvas_a,
            observed_revision=1,
            execution_id=assessment["execution_id"],
            observed_assessment_revision=1,
            new_content={"stale": True},
        )
        assert wrote is False
        session_a.rollback()

        session_a.expire_all()
        fresh = session_a.query(Canvas).first()
        assert current_revision(fresh) == 2
        assert (fresh.content or {}).get("stale") is None
    finally:
        session_a.close()
        session_b.close()


def test_reassessment_between_review_and_approval_requires_fresh_review(
        store, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, _canvas_content, approve_assessment,
    )

    Session, _ = store
    session_a = Session()
    session_b = Session()
    try:
        canvas_a = session_a.query(Canvas).first()
        _prepare(session_a, canvas_a, user)
        _fake_review(monkeypatch)
        first = _assess(session_a, canvas_a, user)

        # Another session re-assesses before the human approves the first one.
        canvas_b = session_b.query(Canvas).first()
        second = _assess(session_b, canvas_b, user)
        assert second["execution_id"] != first["execution_id"]

        with pytest.raises(CapabilityError) as exc:
            approve_assessment(
                session_a, canvas_a, user, first["execution_id"])
        assert exc.value.code == "stale_assessment"
        assert exc.value.extra["current_execution_id"] == second["execution_id"]

        session_a.expire_all()
        fresh = session_a.query(Canvas).first()
        stored = _canvas_content(fresh)["assessment_review"]
        assert stored["execution_id"] == second["execution_id"]
    finally:
        session_a.close()
        session_b.close()


def test_stale_session_consumption_is_refused_after_canvas_change(
        store, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, decisions_operation, edit_operation,
    )

    Session, _ = store
    session_a = Session()
    session_b = Session()
    try:
        canvas_a = session_a.query(Canvas).first()
        _prepare(session_a, canvas_a, user)
        _fake_review(monkeypatch)
        assessment = _assess(session_a, canvas_a, user)
        approve_assessment(
            session_a, canvas_a, user, assessment["execution_id"])
        assert decisions_operation(canvas_a, db=session_a)[
            "success"] is True

        canvas_b = session_b.query(Canvas).first()
        edit_operation(
            session_b, canvas_b, user,
            [{"row": 3, "column": "Amount", "value": 80}],
            expected_revision=1,
        )
        session_b.commit()

        with pytest.raises(CapabilityError) as exc:
            decisions_operation(canvas_a, db=session_a)
        assert exc.value.code == "review_required"
        assert exc.value.extra["authorization"]["state"] == "stale_assessment"
    finally:
        session_a.close()
        session_b.close()


def test_unchanged_approval_survives_reload(store, user, monkeypatch):
    from core.canvas_capability_service import approve_assessment, decisions_operation

    Session, _ = store
    session_a = Session()
    try:
        canvas_a = session_a.query(Canvas).first()
        _prepare(session_a, canvas_a, user)
        _fake_review(monkeypatch)
        assessment = _assess(session_a, canvas_a, user)
        approve_assessment(
            session_a, canvas_a, user, assessment["execution_id"])
        expected = decisions_operation(canvas_a, db=session_a)[
            "decisions"]
    finally:
        session_a.close()

    fresh_session = Session()
    try:
        reloaded = fresh_session.query(Canvas).first()
        decisions = decisions_operation(reloaded, db=fresh_session)
        assert decisions["decisions"] == expected
        assert decisions["authorization"]["state"] == "authorized"
    finally:
        fresh_session.close()


def test_two_simultaneous_approvals_produce_one_transition(store, user, monkeypatch):
    """Both attempt the same observed token; exactly one CAS wins."""
    from core.canvas_capability_service import (
        _cas_update_assessment_content, current_assessment_revision,
    )

    Session, _ = store
    session_a = Session()
    session_b = Session()
    try:
        canvas_a = session_a.query(Canvas).first()
        _prepare(session_a, canvas_a, user)
        _fake_review(monkeypatch)
        assessment = _assess(session_a, canvas_a, user)
        observed = current_assessment_revision(canvas_a)

        first = _cas_update_assessment_content(
            session_a, canvas_a,
            observed_revision=1,
            execution_id=assessment["execution_id"],
            observed_assessment_revision=observed,
            new_content={"winner": "a"},
        )
        session_a.commit()

        second = _cas_update_assessment_content(
            session_b, canvas_b := session_b.query(Canvas).first(),
            observed_revision=1,
            execution_id=assessment["execution_id"],
            observed_assessment_revision=observed,
            new_content={"winner": "b"},
        )
        session_b.rollback()

        assert first is True
        assert second is False
        session_b.expire_all()
        content = (session_b.query(Canvas).first().content or {})
        assert content.get("winner") == "a"
    finally:
        session_a.close()
        session_b.close()


def test_repeat_approval_is_idempotent(store, user, monkeypatch):
    from core.canvas_capability_service import (
        approve_assessment, current_assessment_revision,
    )

    Session, _ = store
    session_a = Session()
    try:
        canvas_a = session_a.query(Canvas).first()
        _prepare(session_a, canvas_a, user)
        _fake_review(monkeypatch)
        assessment = _assess(session_a, canvas_a, user)
        first = approve_assessment(
            session_a, canvas_a, user, assessment["execution_id"])
        assert first.get("idempotent") is not True
        token = current_assessment_revision(canvas_a)

        second = approve_assessment(
            session_a, canvas_a, user, assessment["execution_id"])
        assert second.get("idempotent") is True
        assert current_assessment_revision(canvas_a) == token
    finally:
        session_a.close()
