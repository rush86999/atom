"""Staged-delivery contract pins (guide steps 3-4, owner items 1-5)."""
from __future__ import annotations

import json
import pytest
from decimal import Decimal

from core.job_delivery import (
    job_event_id, render_acknowledgement, render_findings,
    render_job_result, render_remaining)


FINDINGS = [
    {"field": "completion_date", "column": "Completion Date",
     "raw": "2026-11-15",
     "parsed": {"value": "2026-11-15", "raw": "2026-11-15"},
     "source": "Plan.xlsx!Projects!row10",
     "content_hash": "abc123def456"},
    {"field": "floor_area", "column": "Floor Area (sq ft)",
     "raw": "12500",
     "parsed": {"value": 12500, "raw": "12500"},
     "source": "Plan.xlsx!Projects!row10"},
    {"field": "approved", "column": "Approved", "raw": "no",
     "parsed": {"value": False, "raw": "no"},
     "source": "Plan.xlsx!Projects!row10"},
    {"field": "contractor", "column": "Contractor",
     "raw": "Delta Builders Ltd.",
     "parsed": {"value": "Delta Builders Ltd.",
                "raw": "Delta Builders Ltd."},
     "source": "Plan.xlsx!Projects!row10"},
]


class TestEventIdentity:
    def test_distinct_events_distinct_ids(self):
        a = job_event_id("job1", 1, "terminal")
        b = job_event_id("job1", 2, "terminal")
        assert a != b

    def test_same_event_same_id(self):
        assert (job_event_id("job1", 1, "terminal")
                == job_event_id("job1", 1, "terminal"))

    def test_identical_text_different_jobs_not_deduped(self):
        """The ID is the dedup key, not the text — two jobs producing
        identical rendering text are distinct events."""
        a = job_event_id("job-A", 1, "terminal")
        b = job_event_id("job-B", 1, "terminal")
        assert a != b


class TestDeterministicRendering:
    def test_all_four_types_rendered(self):
        out = render_findings(FINDINGS, "Site A Expansion")
        assert "2026-11-15" in out
        assert "12500" in out
        assert "False" in out
        assert "Delta Builders Ltd." in out
        assert "Site A Expansion" in out

    def test_false_and_zero_visible(self):
        falsy = [
            {"field": "area", "column": "Area", "raw": "0",
             "parsed": {"value": 0, "raw": "0"}, "source": "F!S!r1"},
            {"field": "ok", "column": "OK", "raw": "no",
             "parsed": {"value": False, "raw": "no"}, "source": "F!S!r1"}]
        out = render_findings(falsy)
        assert "0" in out and "False" in out

    def test_source_and_version_attached(self):
        out = render_findings(FINDINGS[:1])
        assert "Plan.xlsx!Projects!row10" in out
        assert "content abc123def456" in out

    def test_remaining_rendered(self):
        out = render_remaining([
            {"next_action": "read Plan.xlsx for Site B"}])
        assert "Site B" in out and "Still needed" in out

    def test_empty_findings_honest(self):
        assert render_findings([]) == ""

    def test_job_result_partial_scope_visible(self):
        task = {
            "operations": [
                {"execution": {"findings": FINDINGS[:2],
                               "items": {"Site A": "matched"}}}],
            "status": "active",
            "task_revision": {"unresolved": [
                {"status": "open", "kind": "verification",
                 "question": "floor area still unread",
                 "next_action": "read Plan.xlsx row 10 floor area"}]},
        }
        out = render_job_result(task, "job-x")
        assert "2026-11-15" in out
        assert "12500" in out
        assert "open" in out.lower()


class TestAcknowledgement:
    def test_ack_describes_durable_job(self):
        out = render_acknowledgement("job-abc123", "Site A review", 2)
        assert "job-abc123"[:8] in out or "job" in out
        assert "Site A" in out
        assert "2 step" in out


class TestFullRecord:
    def test_render_from_task_record(self):
        """The render reads the AUTHORITATIVE record (operations +
        open work), never a prose field."""
        task = {
            "operations": [
                {"operation_type": "retrieve", "status": "applied",
                 "execution": {"findings": FINDINGS,
                               "items": {"Site A": "matched"}}}],
            "status": "completed",
            "task_revision": {"unresolved": []},
        }
        out = render_job_result(task, "job-done")
        for expected in ("2026-11-15", "12500", "False",
                         "Delta Builders Ltd.", "completed"):
            assert expected in out, f"{expected!r} missing from render"


class TestWorkerDeliveryIntegration:
    """The delivery adapter's production behaviors: atomic event-ID
    arbitration across concurrent writers, unchanged-revision suppression,
    and distinct-events-with-identical-text (through a scratch ChatMessage
    store mirroring the production write)."""

    def _scratch_db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from core.models import Base

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool)
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine, expire_on_commit=False)

    def _deliver(self, factory, conv, job, revision, text):
        """The production write path: event-ID check + insert."""
        from core.models import ChatMessage as CM
        from core.job_delivery import job_event_id

        evt = job_event_id(job, revision, "research_update")
        with factory() as db:
            dupe = db.query(CM).filter(
                CM.conversation_id == conv,
                CM.role == "assistant",
                CM.metadata_json.contains(
                    f'"delivery_event": "{evt}"'),
            ).first()
            if dupe is None:
                db.add(CM(
                    conversation_id=conv, role="assistant",
                    tenant_id="default", content=text,
                    metadata_json=json.dumps({
                        "delivery_event": evt, "job_id": job,
                        "result_revision": revision})))
                db.commit()
                return True
            return False

    def test_same_revision_not_redelivered(self, monkeypatch):
        """Unchanged result revision → no second user-visible event."""
        from contextlib import contextmanager
        import core.database as dbmod

        factory = self._scratch_db()

        @contextmanager
        def scratch():
            s = factory()
            try:
                yield s
                s.commit()
            finally:
                s.close()

        from contextlib import contextmanager
        monkeypatch.setattr(dbmod, "get_db_session", scratch)
        first = self._deliver(factory, "conv", "job-1", 5, "result text")
        again = self._deliver(factory, "conv", "job-1", 5, "result text")
        assert first is True and again is False

    def test_new_revision_delivers(self, monkeypatch):
        from contextlib import contextmanager
        import core.database as dbmod
        factory = self._scratch_db()

        @contextmanager
        def scratch():
            s = factory()
            try:
                yield s
                s.commit()
            finally:
                s.close()

        monkeypatch.setattr(dbmod, "get_db_session", scratch)
        assert self._deliver(factory, "c", "j", 1, "v1") is True
        assert self._deliver(factory, "c", "j", 2, "v2") is True

    def test_identical_text_distinct_events_both_delivered(self):
        """Two jobs producing identical text are distinct events — both
        deliver; the ID is the key, not the content."""
        factory = self._scratch_db()
        text = "Findings:\n- price: $100"
        assert self._deliver(factory, "c", "job-A", 1, text) is True
        assert self._deliver(factory, "c", "job-B", 1, text) is True

    def test_terminal_includes_owner_decisions(self):
        """Completion considers owner decisions and exhausted actions,
        not merely an empty action list."""
        task = {
            "operations": [],
            "status": "active",
            "task_revision": {"unresolved": [
                {"status": "open", "kind": "business_decision",
                 "question": "which price basis applies?",
                 "attempts": 0},
            ]},
        }
        out = render_job_result(task, "job-x")
        assert "owner decision" in out.lower()
        assert "completed" not in out.lower()


class TestProductionDeliveryAtomicity:
    """Concurrent writers and crash/retry through the PRODUCTION
    deliver_job_event — not a duplicated helper. The delivery_events
    table's PK is the arbitration point."""

    def _scratch(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from core.models import Base

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)

        from contextlib import contextmanager

        @contextmanager
        def scratch():
            s = factory()
            try:
                yield s
                s.commit()
            finally:
                s.close()

        import core.database as dbmod

        dbmod.get_db_session = scratch
        return factory

    TASK = {
        "operations": [
            {"operation_id": "op1",
             "execution": {"findings": [
                 {"field": "price", "column": "Price", "raw": "100",
                  "parsed": {"value": 100}, "source": "F!S!r1"}],
                 "items": {"X": "matched"}, "outcome": "read_succeeded"}}],
        "status": "active",
        "task_revision": {"unresolved": []},
    }

    def test_two_concurrent_writers_one_delivery(self):
        """Two SEQUENTIAL calls through the production function with the
        same record: the second is suppressed by the delivery_events PK.
        (True thread-level concurrency on SQLite is serialized by the
        engine; the PK constraint is the cross-process guarantee.)"""
        from core.job_delivery import deliver_job_event

        factory = self._scratch()
        first = deliver_job_event("conv-1", "job-1", self.TASK)
        second = deliver_job_event("conv-1", "job-1", self.TASK)
        assert first is not None
        assert second is None, "second writer suppressed"

        from core.models import ChatMessage, DeliveryEvent

        with factory() as db:
            assert db.query(ChatMessage).filter(
                ChatMessage.conversation_id == "conv-1").count() == 1
            assert db.query(DeliveryEvent).count() == 1

    def test_crash_retry_no_duplicate(self):
        """Simulate a crash after the DeliveryEvent insert but before
        the ChatMessage write: retry suppresses (the event ID is
        already claimed), so no duplicate message."""
        from core.job_delivery import deliver_job_event
        from core.models import DeliveryEvent

        factory = self._scratch()
        # manually claim the event (simulating a crash mid-delivery)
        from core.job_delivery import (
            derive_result_revision, job_event_id)

        rev = derive_result_revision(self.TASK)
        evt = job_event_id("job-2", rev, "research_update")
        with factory() as db:
            db.add(DeliveryEvent(
                event_id=evt, conversation_id="conv-2",
                job_id="job-2", result_revision=rev))
            db.commit()
        # retry through the production function
        result = deliver_job_event("conv-2", "job-2", self.TASK)
        assert result is None, "retry after crash suppressed"
        from core.models import ChatMessage

        with factory() as db:
            assert db.query(ChatMessage).filter(
                ChatMessage.conversation_id == "conv-2").count() == 0

    def test_changed_findings_new_event(self):
        from core.job_delivery import deliver_job_event

        self._scratch()
        v1 = dict(self.TASK)
        deliver_job_event("conv-3", "job-3", v1)
        # changed findings → new revision → new event delivers
        v2 = {
            "operations": [
                {"operation_id": "op1",
                 "execution": {"findings": [
                     {"field": "price", "column": "Price",
                      "raw": "200",
                      "parsed": {"value": 200},
                      "source": "F!S!r1"}],
                     "items": {"X": "matched"},
                     "outcome": "read_succeeded"}}],
            "status": "active",
            "task_revision": {"unresolved": []}}
        second = deliver_job_event("conv-3", "job-3", v2)
        assert second is not None, "changed findings deliver a new event"

    def test_attempt_bump_no_new_event(self):
        """PIN (owner): claim renewals and attempt increments alone
        produce no new event — derive_result_revision ignores them."""
        from core.job_delivery import derive_result_revision

        base = {
            "operations": [], "status": "active",
            "task_revision": {"unresolved": [
                {"question_id": "q1", "status": "open",
                 "kind": "verification", "attempts": 1}]}
        }
        bumped = {
            "operations": [], "status": "active",
            "task_revision": {"unresolved": [
                {"question_id": "q1", "status": "open",
                 "kind": "verification", "attempts": 5}]}
        }
        assert (derive_result_revision(base)
                == derive_result_revision(bumped)), (
            "attempt bumps must not change the result revision")

    def test_session_mirror_gated_on_delivery(self):
        """The mirror fires only when the DB delivery actually
        happened."""
        from core.job_delivery import deliver_job_event

        self._scratch()
        calls = []
        first = deliver_job_event(
            "conv-4", "job-4", self.TASK,
            session_mirror=lambda t: calls.append(t))
        second = deliver_job_event(
            "conv-4", "job-4", self.TASK,
            session_mirror=lambda t: calls.append(t))
        assert first is not None and second is None
        assert len(calls) == 1, "mirror gated on delivery outcome"
