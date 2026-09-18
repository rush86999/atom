# -*- coding: utf-8 -*-
"""The positive grounding marker (incident closure item 3).

Fabrication accounting places a generation in the denominator only when the
grounding check actually RAN on it — a fabrication verdict, or an explicit
``grounding_ok`` marker. Without the marker the denominator could contain only
fabrications, so the rate would read 100% by construction.

These tests drive the real producer (``record_grounding_pass``) against
scratch persistence and assert the properties that make the marker usable:

* it ANNOTATES the generation's existing outcome row (never a second row);
* it does NOT overwrite the outcome's real quality measurement with the
  marker's placeholder score;
* it never DOWNGRADES an existing fabrication verdict;
* the accounting then counts the generation as evaluated-and-passed.
"""
import json

import pytest


@pytest.fixture()
def scratch_db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.database as database
    from core.models import LLMRoutingFeedback

    engine = create_engine(
        f"sqlite:///{tmp_path / 'g.db'}",
        connect_args={"check_same_thread": False})
    LLMRoutingFeedback.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    yield {"engine": engine, "Session": Session}
    engine.dispose()


def _router(monkeypatch, scratch):
    from core.llm import learning_router_registry as reg
    from core.learning_llm_router import LearningBasedRouter

    router = object.__new__(LearningBasedRouter)
    LearningBasedRouter.__init__(router, scratch["Session"]())
    monkeypatch.setattr(reg, "get_learning_router_instance",
                        lambda *a, **k: router)
    return router


def _rows(scratch, turn, model):
    from core.models import LLMRoutingFeedback

    with scratch["Session"]() as db:
        return (db.query(LLMRoutingFeedback)
                .filter(LLMRoutingFeedback.routing_result_id == turn,
                        LLMRoutingFeedback.model_id == model).all())


def _features(row):
    raw = row.prompt_features
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


MODEL = "openrouter/deepseek/deepseek-v4-flash-0731"


async def _outcome(router, turn):
    from core.learning_llm_router import LearningBasedRouter
    from core.llm.response_quality import assess_response_quality

    await router.record_feedback(LearningBasedRouter.build_feedback(
        routing_result_id=turn, tenant_id="default", model_id=MODEL,
        task_type="question_answering",
        quality=assess_response_quality(content="y" * 400)))


class TestGroundingPassMarker:
    @pytest.mark.asyncio
    async def test_marker_annotates_the_generation_row(self, scratch_db, monkeypatch):
        router = _router(monkeypatch, scratch_db)
        turn = "aaaa1111-bbbb-2222-cccc-333344445555"
        await _outcome(router, turn)

        import core.llm.learning_router_registry as reg
        ok = await reg.record_grounding_pass(
            model_id=MODEL, task_type="question_answering",
            routing_result_id=turn)
        assert ok is True

        rows = _rows(scratch_db, turn, MODEL)
        assert len(rows) == 1, "the marker created a second row for one generation"
        assert _features(rows[0]).get("verdict") == "grounding_ok"

    @pytest.mark.asyncio
    async def test_marker_keeps_the_real_quality_measurement(
            self, scratch_db, monkeypatch):
        router = _router(monkeypatch, scratch_db)
        turn = "bbbb1111-cccc-2222-dddd-333344445555"
        await _outcome(router, turn)
        before = _rows(scratch_db, turn, MODEL)[0].user_satisfaction

        import core.llm.learning_router_registry as reg
        await reg.record_grounding_pass(
            model_id=MODEL, task_type="question_answering",
            routing_result_id=turn)

        after = _rows(scratch_db, turn, MODEL)[0]
        assert after.user_satisfaction == before, (
            "the marker's placeholder score overwrote the outcome's real "
            "quality measurement")
        assert after.quality_satisfied is True

    @pytest.mark.asyncio
    async def test_marker_does_not_downgrade_a_fabrication_verdict(
            self, scratch_db, monkeypatch):
        router = _router(monkeypatch, scratch_db)
        turn = "cccc1111-dddd-2222-eeee-333344445555"
        await _outcome(router, turn)

        import core.llm.learning_router_registry as reg
        await reg.record_fabrication_signal(
            model_id=MODEL, task_type="question_answering",
            unsupported_figures=["8880"], routing_result_id=turn)
        await reg.record_grounding_pass(
            model_id=MODEL, task_type="question_answering",
            routing_result_id=turn)

        row = _rows(scratch_db, turn, MODEL)[0]
        assert _features(row).get("verdict") == "unsupported_figures", (
            "a positive marker overwrote a fabrication verdict — a fabricating "
            "model could whitewash its own record")

    @pytest.mark.asyncio
    async def test_accounting_counts_the_marker_as_evaluated(
            self, scratch_db, monkeypatch):
        from core.llm.fabrication_accounting import account_generations
        from core.models import LLMRoutingFeedback

        router = _router(monkeypatch, scratch_db)
        turn = "dddd1111-eeee-2222-ffff-333344445555"
        await _outcome(router, turn)
        import core.llm.learning_router_registry as reg
        await reg.record_grounding_pass(
            model_id=MODEL, task_type="question_answering",
            routing_result_id=turn)

        with scratch_db["Session"]() as db:
            rows = db.query(LLMRoutingFeedback).all()
            acc = account_generations(rows)
        assert acc.grounded_ok == 1
        assert acc.generations == 1, (
            "a generation whose grounding check passed must be in the "
            "denominator")
        assert acc.rate == 0.0
