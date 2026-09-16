# -*- coding: utf-8 -*-
"""Generation-level fabrication accounting (review item 3).

The defect this pins: one GENERATION can produce several ROWS. The outcome row
is written when ``generate_completion`` returns; a corrective fabrication
verdict is written later, when the figure-grounding / verification guard runs
on the ASSEMBLED reply. Dividing ``fabrication rows / all rows`` mixed those
two units, so a correction inflated the denominator:

    one fabricated generation among four evaluated generations -> 1/5 = 0.20,
    below the 0.25 bench threshold -> a fabricating model stayed in the
    candidate list.

The rate is now ``fabricated generations / evaluated generations``, with the
identities defined in ``core.llm.fabrication_accounting``:

    turn=routing_result_id · attempt=(turn, model) · generation=one attempt's
    output · verdict=the corrective stamp on that generation.

Primary and fallback attempts remain DISTINCT generations; repeated
corrections are idempotent; and historical rows with no provenance stay
explicitly UNKNOWN rather than being counted as clean.

The durable half of this suite asserts DATABASE CONTENTS and restart
behaviour, not persistence-call counts.
"""
import json
import os

import pytest


# ---------------------------------------------------------------------------
# Pure accounting
# ---------------------------------------------------------------------------

from core.llm.fabrication_accounting import (  # noqa: E402
    AVAILABILITY_VERDICTS,
    FABRICATION_SCORE_CEILING,
    FABRICATION_VERDICTS,
    account_generations,
    coerce_features,
    verdict_of,
)


def _row(row_id, turn, model="m1", score=0.9, features=None):
    """A feedback row shaped like the queried columns."""
    return (row_id, turn, model, score, features)


class TestGenerationIdentity:
    def test_one_fabrication_among_four_generations_is_one_quarter(self):
        """THE regression: the corrective row must not become a 5th
        generation. 4 evaluated generations, 1 fabricated -> 0.25, not 0.20."""
        rows = [
            _row("r1", "turn-1", score=0.9),
            _row("r2", "turn-2", score=0.9),
            _row("r3", "turn-3", score=0.9),
            # The generation's own outcome row...
            _row("r4", "turn-4", score=0.9),
            # ...and the corrective verdict the guard wrote for it afterwards.
            _row("r5", "turn-4", score=0.1,
                 features={"verdict": "unsupported_figures"}),
        ]
        acc = account_generations(rows)
        assert acc.rows == 5
        assert acc.generations == 4, "a corrective row created a 5th generation"
        assert acc.fabricated == 1
        assert acc.rate == pytest.approx(0.25)

    def test_repeated_corrections_are_idempotent(self):
        rows = [
            _row("r1", "turn-1", score=0.1,
                 features={"verdict": "unsupported_figures"}),
            _row("r2", "turn-1", score=0.1,
                 features={"verdict": "unsupported_figures"}),
            _row("r3", "turn-1", score=0.1,
                 features={"verdict": "unsupported_figures"}),
        ]
        acc = account_generations(rows)
        assert acc.generations == 1
        assert acc.fabricated == 1
        assert acc.duplicate_rows == 2

    def test_primary_and_fallback_attempts_are_distinct_generations(self):
        """A turn that fell back produced TWO real attempts; neither may be
        dropped or merged."""
        rows = [
            _row("r1", "turn-1", model="primary", score=0.9),
            _row("r2", "turn-1", model="fallback", score=0.9),
        ]
        acc = account_generations(rows)
        assert acc.generations == 2, "a fallback attempt was merged away"
        assert acc.clean == 2

    def test_fabricated_fallback_does_not_condemn_the_primary(self):
        rows = [
            _row("r1", "turn-1", model="primary", score=0.9),
            _row("r2", "turn-1", model="fallback", score=0.1,
                 features={"verdict": "ungrounded_claims"}),
        ]
        acc = account_generations(rows)
        assert acc.generations == 2
        assert acc.fabricated == 1

    def test_rows_without_a_turn_id_do_not_merge(self):
        """Legacy rows with no routing id must not collapse into each other."""
        rows = [
            _row("a", None, score=0.9),
            _row("b", None, score=0.9),
            _row("c", "", score=0.1,
                 features={"verdict": "unsupported_figures"}),
        ]
        acc = account_generations(rows)
        assert acc.generations == 3
        assert acc.fabricated == 1

    def test_orm_style_rows_and_dicts_are_accepted(self):
        from types import SimpleNamespace

        rows = [
            SimpleNamespace(id="1", routing_result_id="t1", model_id="m",
                            user_satisfaction=0.9, prompt_features=None),
            {"id": "2", "routing_result_id": "t1", "model_id": "m",
             "user_satisfaction": 0.1,
             "prompt_features": {"verdict": "unsupported_figures"}},
        ]
        acc = account_generations(rows)
        assert acc.generations == 1
        assert acc.fabricated == 1


class TestUnknownIsNotClean:
    def test_low_score_without_provenance_is_unknown(self):
        """0.0/0.1 is where provider exceptions, empty completions and
        fabrications all land — without provenance it is UNKNOWN, never
        clean."""
        acc = account_generations([_row("r1", "t1", score=0.0)])
        assert acc.generations == 0
        assert acc.unknown == 1
        assert acc.clean == 0
        assert acc.rate is None

    def test_missing_score_is_unknown(self):
        acc = account_generations([_row("r1", "t1", score=None)])
        assert acc.unknown == 1 and acc.generations == 0

    def test_score_above_the_band_is_clean(self):
        acc = account_generations(
            [_row("r1", "t1", score=FABRICATION_SCORE_CEILING + 0.01)])
        assert acc.clean == 1 and acc.generations == 1

    def test_unrecognised_verdict_is_unknown_not_clean(self):
        acc = account_generations(
            [_row("r1", "t1", score=0.9, features={"verdict": "looks_fine"})])
        assert acc.clean == 0
        assert acc.unknown == 1

    def test_availability_verdicts_are_excluded_from_both_terms(self):
        rows = [
            _row("r1", "t1", score=0.3, features={"verdict": "timeout"}),
            _row("r2", "t2", score=0.9),
        ]
        acc = account_generations(rows)
        assert acc.availability == 1
        assert acc.generations == 1 and acc.clean == 1
        assert acc.rate == 0.0

    def test_fabrication_outranks_a_companion_availability_verdict(self):
        rows = [
            _row("r1", "t1", score=0.3, features={"verdict": "timeout"}),
            _row("r2", "t1", score=0.1,
                 features={"verdict": "unsupported_figures"}),
        ]
        acc = account_generations(rows)
        assert acc.fabricated == 1
        assert acc.availability == 0

    def test_clean_row_wins_over_a_companion_availability_row(self):
        rows = [
            _row("r1", "t1", score=0.3, features={"verdict": "timeout"}),
            _row("r2", "t1", score=0.9),
        ]
        acc = account_generations(rows)
        assert acc.clean == 1 and acc.generations == 1

    def test_rate_is_none_when_nothing_was_evaluated(self):
        acc = account_generations([])
        assert acc.rate is None
        assert acc.as_dict()["rate"] is None


class TestMalformedMetadataIsolation:
    @pytest.mark.parametrize("payload", [
        "[1, 2, 3]",       # JSON array
        '{"verdict": ',    # truncated JSON
        "not json at all",  # garbage
        '"a string"',      # JSON scalar
        [1, 2],            # a Python list straight from the column
        42,
        True,
    ])
    def test_malformed_payload_is_a_row_property(self, payload):
        features, malformed = coerce_features(payload)
        assert features == {}
        assert malformed is True

    @pytest.mark.parametrize("payload", [None, "", "   ", {}, "null"])
    def test_absent_payload_is_not_malformed(self, payload):
        """``null`` is how a JSON column stores "no features" — the live table
        holds 67 of them. It is ABSENT, not corrupt; counting it as malformed
        would report two thirds of production history as damaged metadata."""
        features, malformed = coerce_features(payload)
        assert features == {}
        assert malformed is False

    def test_non_string_verdict_is_not_coerced(self):
        verdict, malformed = verdict_of({"verdict": ["unsupported_figures"]})
        assert verdict is None
        assert malformed is True

    def test_one_malformed_row_does_not_hide_the_others(self):
        """A single bad row must not turn the model's check into 'no
        fabrication found'."""
        rows = [
            _row("r0", "t0", score=0.9, features={"verdict": ["bogus"]}),
            _row("r1", "t1", score=0.1,
                 features={"verdict": "unsupported_figures"}),
            _row("r2", "t2", score=0.1,
                 features={"verdict": "unsupported_figures"}),
            _row("r3", "t3", score=0.1,
                 features={"verdict": "ungrounded_claims"}),
        ]
        acc = account_generations(rows)
        assert acc.malformed_rows == 1
        assert acc.fabricated == 3
        assert acc.generations == 3
        assert acc.rate == 1.0

    def test_unreadable_row_object_is_counted_not_raised(self):
        class Hostile:
            @property
            def routing_result_id(self):
                raise RuntimeError("column exploded")

        acc = account_generations([Hostile()])
        assert acc.malformed_rows == 1
        assert acc.unknown == 1

    def test_malformed_rows_are_reported_in_the_dict(self):
        acc = account_generations([_row("r0", "t0", features="[1,2]")])
        snapshot = acc.as_dict()
        assert snapshot["malformed_rows"] == 1
        assert snapshot["unknown"] == 1


# ---------------------------------------------------------------------------
# The bench, against a real (scratch) database
# ---------------------------------------------------------------------------

@pytest.fixture()
def scratch_feedback_db(tmp_path, monkeypatch):
    """Point core.database.SessionLocal at a scratch SQLite file.

    Durable on purpose: the point is to assert database CONTENTS and that a
    fresh process (fresh router, fresh session, fresh bench cache) reads the
    same verdicts back.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.database as database
    from core.models import LLMRoutingFeedback

    db_path = tmp_path / "feedback.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    LLMRoutingFeedback.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    yield {"engine": engine, "Session": Session, "path": db_path}
    engine.dispose()


def _writer():
    """A router instance able to persist a feedback row."""
    from core.learning_llm_router import LearningBasedRouter

    return LearningBasedRouter.__new__(LearningBasedRouter)


def _feedback(turn, model="openai/m1", score=0.9, task="question_answering"):
    from core.learning_llm_router import RoutingFeedback

    return RoutingFeedback(
        routing_result_id=turn,
        tenant_id="default",
        task_type=task,
        model_id=model,
        success=True,
        quality_satisfied=score > FABRICATION_SCORE_CEILING,
        cost_within_budget=True,
        user_satisfaction=score,
        actual_cost=0.0,
        actual_latency_ms=10.0,
    )


def _read_rows(scratch):
    from core.models import LLMRoutingFeedback

    with scratch["Session"]() as db:
        return [
            (r.id, r.routing_result_id, r.model_id,
             r.user_satisfaction, r.prompt_features)
            for r in db.query(LLMRoutingFeedback)
            .order_by(LLMRoutingFeedback.created_at.asc()).all()
        ]


def _bench_stub(monkeypatch, min_events=1, rate=0.25):
    """A BYOKHandler without __init__, so the bench runs on real class
    settings plus the scratch DB."""
    from core.llm.byok_handler import BYOKHandler

    monkeypatch.setattr(BYOKHandler, "_FAB_BENCH_MIN_EVENTS", min_events)
    monkeypatch.setattr(BYOKHandler, "_FAB_BENCH_RATE", rate)
    monkeypatch.setenv("ATOM_FABRICATION_BENCH", "1")
    return BYOKHandler.__new__(BYOKHandler)


class TestBenchUsesGenerationsNotRows:
    def test_correction_annotates_the_generation_row(
            self, scratch_feedback_db, monkeypatch):
        """The verdict JOINs the generation's own row: 4 generations stay 4
        rows, and the fabricated one carries the provenance."""
        writer = _writer()
        for turn in ("t1", "t2", "t3", "t4"):
            writer._persist_feedback(_feedback(turn), {"quality": 0.9})

        writer._persist_feedback(
            _feedback("t4", score=0.1),
            {"verdict": "unsupported_figures"})

        rows = _read_rows(scratch_feedback_db)
        assert len(rows) == 4, (
            "the corrective verdict added a row — one generation is being "
            "counted as two")
        by_turn = {r[1]: r for r in rows}
        stored = by_turn["t4"][4]
        if isinstance(stored, str):
            stored = json.loads(stored)
        assert stored.get("verdict") == "unsupported_figures", (
            "the outcome row kept no provenance, so the bench cannot tell a "
            "fabrication from an outage")
        # The other three keep their real outcome rows untouched.
        for turn in ("t1", "t2", "t3"):
            other = by_turn[turn][4]
            if isinstance(other, str):
                other = json.loads(other)
            assert not (other or {}).get("verdict")

    def test_repeated_correction_does_not_duplicate(
            self, scratch_feedback_db, monkeypatch):
        writer = _writer()
        writer._persist_feedback(_feedback("t1"), {"quality": 0.9})
        for _ in range(3):
            writer._persist_feedback(
                _feedback("t1", score=0.1),
                {"verdict": "unsupported_figures"})
        assert len(_read_rows(scratch_feedback_db)) == 1

    def test_bench_fires_on_one_fabrication_in_four_generations(
            self, scratch_feedback_db, monkeypatch):
        """Turns at 0.25 must bench. Under the old row-based denominator this
        was 1/5 = 0.20 and the model stayed in the candidate list."""
        writer = _writer()
        for turn in ("t1", "t2", "t3", "t4"):
            writer._persist_feedback(_feedback(turn), {"quality": 0.9})
        writer._persist_feedback(
            _feedback("t4", score=0.1),
            {"verdict": "unsupported_figures"})

        handler = _bench_stub(monkeypatch)
        assert handler._fabrication_benched("openai", "m1") is True

    def test_bench_is_durable_across_a_restart(
            self, scratch_feedback_db, monkeypatch):
        """A fresh bench object (fresh cache, fresh session) must reach the
        same verdict from the database alone."""
        writer = _writer()
        for turn in ("t1", "t2", "t3", "t4"):
            writer._persist_feedback(_feedback(turn), {"quality": 0.9})
        writer._persist_feedback(
            _feedback("t4", score=0.1),
            {"verdict": "unsupported_figures"})

        before = _bench_stub(monkeypatch)
        assert before._fabrication_benched("openai", "m1") is True
        after = _bench_stub(monkeypatch)          # simulated restart
        assert after._fab_bench_cache == {}
        assert after._fabrication_benched("openai", "m1") is True

    def test_one_malformed_row_does_not_fail_the_bench_open(
            self, scratch_feedback_db, monkeypatch):
        """The old implementation json.loads'ed a list payload, raised
        AttributeError out of the per-row helper, and the outer except turned
        the WHOLE model's check into 'not benched'."""
        from core.models import LLMRoutingFeedback

        writer = _writer()
        with scratch_feedback_db["Session"]() as db:
            db.add(LLMRoutingFeedback(
                id="bad", routing_result_id="t0", tenant_id="default",
                task_type="question_answering", model_id="openai/m1",
                success=True, quality_satisfied=False, cost_within_budget=True,
                user_satisfaction=0.9, prompt_features=[1, 2, 3],
            ))
        for turn in ("t1", "t2", "t3"):
            writer._persist_feedback(
                _feedback(turn, score=0.1),
                {"verdict": "unsupported_figures"})

        handler = _bench_stub(monkeypatch, min_events=3, rate=0.25)
        assert handler._fabrication_benched("openai", "m1") is True, (
            "a malformed row made the whole model check fail open")

    def test_health_rows_do_not_bench_a_model(self, scratch_feedback_db,
                                              monkeypatch):
        """Timeouts are availability, not fabrication: benching for them
        punished outage victims as liars."""
        writer = _writer()
        for turn in ("t1", "t2", "t3"):
            writer._persist_feedback(
                _feedback(turn, score=0.3), {"verdict": "timeout"})
        handler = _bench_stub(monkeypatch, min_events=1, rate=0.25)
        assert handler._fabrication_benched("openai", "m1") is False

    def test_unprovenanced_history_cannot_bench_or_exonerate(
            self, scratch_feedback_db, monkeypatch):
        """Legacy rows with no verdict: not clean, not fabricated, and the
        rate stays undefined for them."""
        writer = _writer()
        for turn in ("t1", "t2", "t3"):
            writer._persist_feedback(_feedback(turn, score=0.1), None)
        rows = _read_rows(scratch_feedback_db)
        acc = account_generations(rows)
        assert acc.generations == 0
        assert acc.unknown == 3
        assert acc.rate is None
        handler = _bench_stub(monkeypatch, min_events=1, rate=0.25)
        assert handler._fabrication_benched("openai", "m1") is False

    def test_primary_and_fallback_rows_both_count(
            self, scratch_feedback_db, monkeypatch):
        writer = _writer()
        writer._persist_feedback(
            _feedback("t1", model="openai/primary"), {"quality": 0.9})
        writer._persist_feedback(
            _feedback("t1", model="openai/fallback", score=0.1),
            {"verdict": "unsupported_figures"})
        rows = _read_rows(scratch_feedback_db)
        assert len(rows) == 2
        acc = account_generations(rows)
        assert acc.generations == 2 and acc.fabricated == 1
