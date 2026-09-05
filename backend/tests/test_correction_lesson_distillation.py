"""Correction distillation: supervisor fixes the draft on the canvas → the
hire learns a REAL rule immediately, no send required.

Regression context (Sep 4, 2026): canvas corrections journaled a raw JSON
dump as the "lesson" ("Supervisor corrected my work — follow the corrected
version's content and style: {\"type\": \"canvas_edit\", \"content\":
{\"to\": …"). Nothing usable reached the work-time lesson list or the
Training panel, so the hire only visibly advanced when an email was
sent+approved — the supervisor's on-canvas teaching was write-only until
they pushed the send button. These tests pin the distilled path, the
no-LLM fallback, and the unteachable-diff skip.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.student_learning_service import (
    CorrectionLesson,
    distill_and_journal_correction,
    raw_correction_gist,
)


def _fresh_engine(tmp_path, name):
    from core.models import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine(f"sqlite:///{tmp_path}/{name}.db")
    Base.metadata.create_all(bind=eng)
    return eng, sessionmaker(bind=eng, expire_on_commit=False)


def _seed_agent(session, agent_id):
    from core.models import AgentRegistry

    agent = AgentRegistry(id=agent_id, name="Hire", category="business",
                          module_path="core.test", class_name="T",
                          status="student", tenant_id="default")
    session.add(agent)
    session.commit()
    return agent


def _learning_log(session, agent_id):
    from core.models import AgentRegistry

    agent = session.query(AgentRegistry).filter(
        AgentRegistry.id == agent_id).first()
    config = agent.configuration if isinstance(agent.configuration, dict) else {}
    learning = config.get("learning") or {}
    return learning.get("log") or []


BEFORE = {"to": "jschulz@blumetric.ca", "cc": "", "subject": "Re: quote", "body": "<p>Hi</p>"}
AFTER = {"to": "jschulz@blumetric.ca", "cc": "vipul@brennan.ca", "subject": "Re: quote", "body": "<p>Hi</p>"}
LESSON = "Always CC vipul@brennan.ca on customer quote emails."


@pytest.mark.asyncio
async def test_distilled_correction_journals_real_lesson(tmp_path):
    """Happy path: the diff becomes ONE imperative rule in the learning
    log — the lesson the editor planner and the Training panel consume."""
    eng, Sess = _fresh_engine(tmp_path, "distill1")
    llm = AsyncMock()
    llm.generate_structured_response = AsyncMock(
        return_value=CorrectionLesson(teachable=True, lesson=LESSON))

    with patch("core.student_learning_service._correction_llm", return_value=llm), \
         patch("core.database.SessionLocal", Sess):
        with Sess() as s:
            _seed_agent(s, "hire-1")
        result = await distill_and_journal_correction(
            "hire-1", BEFORE, AFTER, canvas_id="c-1", canvas_type="email")

    assert result["status"] == "distilled"
    with Sess() as s:
        log = _learning_log(s, "hire-1")
        assert len(log) == 1
        entry = log[0]
        assert entry["source"] == "observation"
        assert entry["observation_type"] == "human_correction"
        assert entry["summary"] == LESSON          # the rule, not JSON
        assert entry["details"]["distilled"] is True
        assert entry["details"]["canvas_id"] == "c-1"
    eng.dispose()


@pytest.mark.asyncio
async def test_llm_unavailable_falls_back_to_raw_gist(tmp_path):
    """No provider configured (or the call fails): the legacy raw-diff gist
    is journaled — learning is never LOST, only less readable."""
    eng, Sess = _fresh_engine(tmp_path, "distill2")

    with patch("core.student_learning_service._correction_llm", return_value=None), \
         patch("core.database.SessionLocal", Sess):
        with Sess() as s:
            _seed_agent(s, "hire-2")
        result = await distill_and_journal_correction(
            "hire-2", BEFORE, AFTER, canvas_id="c-2", canvas_type="email")

    assert result["status"] == "fallback"
    with Sess() as s:
        log = _learning_log(s, "hire-2")
        assert len(log) == 1
        assert log[0]["summary"].startswith(
            "Supervisor corrected my work — follow the corrected "
            "version's content and style:")
        assert log[0]["details"]["distilled"] is False
    eng.dispose()


@pytest.mark.asyncio
async def test_unteachable_diff_skips_the_journal(tmp_path):
    """Pure formatting / no-op diffs must not crowd the bounded work-time
    lesson list with junk — the LLM judged them unteachable."""
    eng, Sess = _fresh_engine(tmp_path, "distill3")
    llm = AsyncMock()
    llm.generate_structured_response = AsyncMock(
        return_value=CorrectionLesson(teachable=False, lesson=""))

    with patch("core.student_learning_service._correction_llm", return_value=llm), \
         patch("core.database.SessionLocal", Sess):
        with Sess() as s:
            _seed_agent(s, "hire-3")
        result = await distill_and_journal_correction(
            "hire-3", BEFORE, BEFORE, canvas_id="c-3", canvas_type="email")

    assert result["status"] == "not_teachable"
    with Sess() as s:
        assert _learning_log(s, "hire-3") == []
    eng.dispose()


@pytest.mark.asyncio
async def test_record_correction_schedules_distillation_when_loop_running(tmp_path):
    """Live wiring: inside a running loop (the API route), record_user_
   _correction schedules the background distiller instead of journaling
    the raw gist inline — an LLM call must never sit inside the PUT."""
    import contextlib
    from core.models import CanvasContext
    from services.canvas_context_service import CanvasContextService

    eng, Sess = _fresh_engine(tmp_path, "distill4")
    distilled = AsyncMock(return_value={"status": "distilled"})

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    with patch("core.database.get_db_session", side_effect=lambda: db_session()), \
         patch("core.student_learning_service.distill_and_journal_correction", distilled):
        with Sess() as s:
            _seed_agent(s, "hire-4")
            s.add(CanvasContext(canvas_id="c-4", tenant_id="default",
                                canvas_type="email", user_id="u-1",
                                agent_id="hire-4", current_state={}))
            s.commit()
        service = CanvasContextService(Sess(), tenant_id="default")
        service.record_user_correction(
            canvas_id="c-4", user_id="u-1",
            original_action={"type": "canvas_edit", "content": BEFORE, "author": "agent"},
            corrected_action={"type": "canvas_edit", "content": AFTER, "author": "supervisor"},
            context_info="test",
        )
        await asyncio.sleep(0)  # let the scheduled task run

    distilled.assert_awaited_once()
    args, kwargs = distilled.await_args
    assert kwargs.get("canvas_id") == "c-4"
    assert kwargs.get("canvas_type") == "email"
    eng.dispose()


def test_raw_correction_gist_matches_legacy_text():
    """The fallback path must stay byte-compatible with the pre-distillation
    journal text (consumers/tests key on its prefix)."""
    gist = raw_correction_gist({"fixed": True})
    assert gist.startswith(
        "Supervisor corrected my work — follow the corrected "
        "version's content and style:")
    assert '"fixed": true' in gist.lower() or "'fixed': true" in gist.lower() or "fixed" in gist
