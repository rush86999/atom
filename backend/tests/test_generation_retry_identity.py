# -*- coding: utf-8 -*-
"""Retry identity in generation accounting (incident closure item 3).

``(routing_result_id, model_id)`` is the accounting identity of a generation.
A turn that REGENERATES with the same model reuses the routing decision, so
both outputs carried the same pair and were MERGED into one generation — which
can hide the second output's fabrication entirely (it lands on a generation
already counted, or not counted at all).

The rule these tests pin: a SECOND outcome row for the same (turn, model) is a
distinct output and must get its own generation id, while a repeated
correction for one output stays idempotent.
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
        f"sqlite:///{tmp_path / 'retry.db'}",
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


def _all_rows(scratch):
    from core.models import LLMRoutingFeedback

    with scratch["Session"]() as db:
        return db.query(LLMRoutingFeedback).all()


async def _outcome(router, turn, model):
    from core.learning_llm_router import LearningBasedRouter
    from core.llm.response_quality import assess_response_quality

    fb = LearningBasedRouter.build_feedback(
        routing_result_id=turn, tenant_id="default", model_id=model,
        task_type="question_answering",
        quality=assess_response_quality(content="z" * 400))
    await router.record_feedback(fb)
    return fb


MODEL = "openrouter/z-ai/glm-5.3-flash"


class TestSameModelRetriesAreDistinctGenerations:
    @pytest.mark.asyncio
    async def test_second_outcome_for_same_turn_is_a_new_generation(
            self, scratch_db, monkeypatch):
        router = _router(monkeypatch, scratch_db)
        turn = "retry-0001"
        await _outcome(router, turn, MODEL)
        await _outcome(router, turn, MODEL)

        rows = _all_rows(scratch_db)
        assert len(rows) == 2, "the retry overwrote or was merged away"
        ids = sorted(r.routing_result_id for r in rows)
        assert len(set(ids)) == 2, (
            "both outputs kept the same generation id — accounting would "
            f"merge them: {ids}")

    @pytest.mark.asyncio
    async def test_accounting_counts_both_retry_generations(
            self, scratch_db, monkeypatch):
        from core.llm.fabrication_accounting import account_generations

        router = _router(monkeypatch, scratch_db)
        turn = "retry-0002"
        await _outcome(router, turn, MODEL)
        await _outcome(router, turn, MODEL)
        acc = account_generations(_all_rows(scratch_db))
        assert acc.rows == 2
        assert acc.duplicate_rows == 0, (
            "the retry was collapsed into the first generation")
        # Neither is grounded, so neither is in the denominator — but they are
        # two distinct generations, not one.
        assert acc.unevaluated == 2

    @pytest.mark.asyncio
    async def test_a_fabrication_on_the_retry_is_counted_separately(
            self, scratch_db, monkeypatch):
        """The failure this prevents: the retry fabricates, the first attempt
        did not, and the pair collapses so the fabrication is invisible."""
        from core.llm.fabrication_accounting import account_generations

        router = _router(monkeypatch, scratch_db)
        turn = "retry-0003"
        first = await _outcome(router, turn, MODEL)
        retry = await _outcome(router, turn, MODEL)

        import core.llm.learning_router_registry as reg
        # The verdict names the RETRY's own id, which the handler publishes
        # after persistence re-keyed it.
        ok = await reg.record_fabrication_signal(
            model_id=MODEL, task_type="question_answering",
            unsupported_figures=["8880"],
            routing_result_id=retry.routing_result_id)
        assert ok is True

        rows = _all_rows(scratch_db)
        assert len(rows) == 2, "the verdict added a third row"
        by_id = {r.routing_result_id: r for r in rows}
        stored = by_id[retry.routing_result_id].prompt_features
        stored = json.loads(stored) if isinstance(stored, str) else (stored or {})
        assert stored.get("verdict") == "unsupported_figures", (
            "the verdict did not land on the retry's own row")
        first_feats = by_id[first.routing_result_id].prompt_features
        first_feats = (json.loads(first_feats)
                       if isinstance(first_feats, str) else (first_feats or {}))
        assert first_feats.get("verdict") is None, (
            "the retry's fabrication was attributed to the first attempt")

        acc = account_generations(rows)
        assert acc.generations == 1 and acc.fabricated == 1

    @pytest.mark.asyncio
    async def test_repeated_correction_for_one_output_stays_idempotent(
            self, scratch_db, monkeypatch):
        router = _router(monkeypatch, scratch_db)
        turn = "retry-0004"
        await _outcome(router, turn, MODEL)

        import core.llm.learning_router_registry as reg
        for _ in range(3):
            await reg.record_fabrication_signal(
                model_id=MODEL, task_type="question_answering",
                unsupported_figures=["8880"], routing_result_id=turn)
        assert len(_all_rows(scratch_db)) == 1
