# -*- coding: utf-8 -*-
"""Correction lifecycle, end to end through the REAL feedback entry point.

Audit closure item 2. The generation-level accounting module fixed the
row-count arithmetic, but the persistence path it reads was never exercised
end to end. Two hazards are named in the closure brief and reproduced here:

1. ``LearningBasedRouter.record_feedback`` recovers the stashed decision
   features for a ``routing_result_id`` and assigns them to
   ``feedback._prompt_features``. ``consume_decision`` does NOT delete the
   stash, so a corrective verdict that rides on ``_prompt_features`` can be
   REPLACED by the decision features — the verdict never reaches the row, and
   ``_persist_feedback`` (which only annotates when it can see a verdict)
   inserts a SECOND row for the same generation instead.

2. Even when the annotation does land, the update path rewrites
   ``prompt_features`` only, leaving ``user_satisfaction`` /
   ``quality_satisfied`` at the pre-correction outcome values. The stored row
   then contradicts itself, and in-memory learning has already been fed a
   second, contradictory event — so a restart changes what the router believes.

These tests drive ``record_feedback`` / ``record_fabrication_signal`` — the
real entry points — against scratch persistence, never ``_persist_feedback``
alone.
"""
import json

import pytest


@pytest.fixture()
def scratch_db(tmp_path, monkeypatch):
    """Point the app's session factory at a scratch SQLite file."""
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


def _rows(scratch, turn, model):
    from core.models import LLMRoutingFeedback

    with scratch["Session"]() as db:
        return (
            db.query(LLMRoutingFeedback)
            .filter(LLMRoutingFeedback.routing_result_id == turn,
                    LLMRoutingFeedback.model_id == model)
            .all()
        )


def _fresh_router(monkeypatch, scratch):
    """A real LearningBasedRouter wired to the scratch session."""
    from core.llm import learning_router_registry as reg
    from core.learning_llm_router import LearningBasedRouter

    router = LearningBasedRouter(db=scratch["Session"]())
    monkeypatch.setattr(reg, "get_learning_router_instance",
                        lambda *a, **k: router)
    return router


async def _write_outcome(router, turn, model, content="x" * 400):
    from core.llm.response_quality import assess_response_quality
    from core.learning_llm_router import LearningBasedRouter

    fb = LearningBasedRouter.build_feedback(
        routing_result_id=turn,
        tenant_id="default",
        model_id=model,
        task_type="question_answering",
        quality=assess_response_quality(content=content),
    )
    await router.record_feedback(fb)


MODEL = "openrouter/z-ai/glm-5.3-flash"


class TestCorrectionSurvivesFeatureRecovery:
    @pytest.mark.asyncio
    async def test_verdict_is_not_clobbered_by_the_decision_stash(
            self, scratch_db, monkeypatch):
        """The stash deliberately outlives one feedback call, so the verdict
        must not ride on a field record_feedback overwrites."""
        router = _fresh_router(monkeypatch, scratch_db)
        turn = router.stash_decision(
            {"log_tokens": 8.0, "task_general": 1.0})
        await _write_outcome(router, turn, MODEL)

        import core.llm.learning_router_registry as reg
        ok = await reg.record_fabrication_signal(
            model_id=MODEL, task_type="question_answering",
            unsupported_figures=["8880"], routing_result_id=turn)
        assert ok is True

        rows = _rows(scratch_db, turn, MODEL)
        assert len(rows) == 1, (
            "the corrective verdict was lost and a second row inserted for "
            "the same generation")
        stored = rows[0].prompt_features
        stored = json.loads(stored) if isinstance(stored, str) else (stored or {})
        assert stored.get("verdict") == "unsupported_figures", (
            "the stored row carries no fabrication verdict — the stash "
            "recovery overwrote _prompt_features")

    @pytest.mark.asyncio
    async def test_annotation_lands_when_no_decision_was_stashed(
            self, scratch_db, monkeypatch):
        """Control: without a stashed decision the same flow annotates."""
        router = _fresh_router(monkeypatch, scratch_db)
        turn = "11111111-2222-3333-4444-555555555555"
        await _write_outcome(router, turn, MODEL)

        import core.llm.learning_router_registry as reg
        await reg.record_fabrication_signal(
            model_id=MODEL, task_type="question_answering",
            unsupported_figures=["8880"], routing_result_id=turn)

        rows = _rows(scratch_db, turn, MODEL)
        assert len(rows) == 1
        stored = rows[0].prompt_features
        stored = json.loads(stored) if isinstance(stored, str) else (stored or {})
        assert stored.get("verdict") == "unsupported_figures"

    @pytest.mark.asyncio
    async def test_repeated_corrections_stay_one_row(self, scratch_db, monkeypatch):
        router = _fresh_router(monkeypatch, scratch_db)
        turn = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        await _write_outcome(router, turn, MODEL)

        import core.llm.learning_router_registry as reg
        for _ in range(3):
            await reg.record_fabrication_signal(
                model_id=MODEL, task_type="question_answering",
                unsupported_figures=["8880"], routing_result_id=turn)

        assert len(_rows(scratch_db, turn, MODEL)) == 1


class TestCorrectedRowIsInternallyConsistent:
    @pytest.mark.asyncio
    async def test_quality_fields_agree_with_the_verdict(
            self, scratch_db, monkeypatch):
        """A row that says verified=True, score=0.8 AND verdict=fabrication is
        self-contradictory: every reader picks whichever half suits it."""
        router = _fresh_router(monkeypatch, scratch_db)
        turn = "99999999-8888-7777-6666-555555555555"
        await _write_outcome(router, turn, MODEL)

        import core.llm.learning_router_registry as reg
        await reg.record_fabrication_signal(
            model_id=MODEL, task_type="question_answering",
            unsupported_figures=["8880"], routing_result_id=turn)

        row = _rows(scratch_db, turn, MODEL)[0]
        stored = row.prompt_features
        stored = json.loads(stored) if isinstance(stored, str) else (stored or {})
        assert stored.get("verdict") == "unsupported_figures"
        assert row.quality_satisfied is False, (
            "stored quality_satisfied still claims the fabricated reply was "
            "satisfactory")
        assert (row.user_satisfaction or 0) <= 0.15, (
            "stored satisfaction still carries the pre-correction score")


class TestRestartConsistency:
    @pytest.mark.asyncio
    async def test_learning_matches_persistence_before_and_after_restart(
            self, scratch_db, monkeypatch):
        """In-memory learning and the persisted row must tell the same story,
        or a restart silently changes the router's opinion of the model."""
        router = _fresh_router(monkeypatch, scratch_db)
        turn = "abcdefab-1234-5678-9abc-def012345678"
        await _write_outcome(router, turn, MODEL)

        import core.llm.learning_router_registry as reg
        await reg.record_fabrication_signal(
            model_id=MODEL, task_type="question_answering",
            unsupported_figures=["8880"], routing_result_id=turn)

        key = "default:question_answering"
        events = [f for f in router._preference_data.get(key, [])
                  if f.routing_result_id == turn]
        assert events, "in-memory learning recorded nothing for this turn"
        worst = min(f.user_satisfaction or 1.0 for f in events)
        row = _rows(scratch_db, turn, MODEL)[0]
        assert (row.user_satisfaction or 0) <= worst + 1e-9, (
            "in-memory learning believes the generation scored "
            f"{worst} while the persisted row says {row.user_satisfaction}; "
            "a restart would flip the router's view")


class TestFallbackGenerations:
    @pytest.mark.asyncio
    async def test_fallback_and_primary_are_separate_generations(
            self, scratch_db, monkeypatch):
        router = _fresh_router(monkeypatch, scratch_db)
        turn = "fedcba98-7654-3210-fedc-ba9876543210"
        await _write_outcome(router, turn, MODEL)
        await _write_outcome(router, turn, "openrouter/qwen/qwen3.8-flash")

        rows = _rows(scratch_db, turn, MODEL)
        other = _rows(scratch_db, turn, "openrouter/qwen/qwen3.8-flash")
        assert len(rows) == 1 and len(other) == 1, (
            "a fallback attempt must keep its own generation row")

        import core.llm.learning_router_registry as reg
        await reg.record_fabrication_signal(
            model_id="openrouter/qwen/qwen3.8-flash",
            task_type="question_answering",
            unsupported_figures=["8880"], routing_result_id=turn)
        # the primary is untouched
        primary = _rows(scratch_db, turn, MODEL)[0]
        stored = primary.prompt_features
        stored = json.loads(stored) if isinstance(stored, str) else (stored or {})
        assert stored.get("verdict") is None
