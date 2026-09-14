"""Train an agent from chat — /teach command, detected cues, and the
confirm-first suggestion path (canvas co-editor chat AND regular chat).

The chat surfaces had no teaching channel at all: /teach existed only as the
canvas Training tab's form, and a message like "always CC the lead" was
ordinary conversation. These tests lock the channel's contract:

* explicit ``/teach <rule>`` saves through the SAME composite the API uses and
  answers deterministically (never via the reply model),
* a detected cue only SUGGESTS (lessons are permanent prompt instructions —
  human-gated writes) and never touches the learning log on its own,
* no attached agent → the reply asks for one and lists the options,
* ordinary conversation is left completely alone.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.chat_teaching import (
    detect_teaching_cue,
    list_teachable_agents,
    parse_teach_command,
    suggest_lesson,
    teach_from_chat,
)
from core.models import AgentRegistry


def _make_agent(db_session, *, status="student", name="Learner", confidence=0.1):
    agent = AgentRegistry(
        id=f"teach-{uuid.uuid4().hex[:8]}",
        name=name, category="Finance", description="t",
        module_path="core.generic_agent", class_name="GenericAgent",
        status=status, confidence_score=confidence, configuration={},
        capabilities=["send_email"],
        workspace_id="default", tenant_id="default",
    )
    db_session.add(agent)
    db_session.commit()
    return agent


def _log(agent: AgentRegistry):
    return ((agent.configuration or {}).get("learning") or {}).get("log") or []


# ---------------------------------------------------------------------------
# Detection (the conservative gate)
# ---------------------------------------------------------------------------

class TestTeachCommandParsing:
    def test_parses_the_rule_after_the_command(self):
        assert parse_teach_command("/teach Always CC the lead on quotes") == \
            "Always CC the lead on quotes"

    @pytest.mark.parametrize("message", [
        "/teach: Always CC the lead",
        "/TEACH Always CC the lead",
        "  /teach   Always CC the lead  ",
        "/teach - Always CC the lead",
    ])
    def test_tolerates_spacing_case_and_separators(self, message):
        assert parse_teach_command(message) == "Always CC the lead"

    def test_bare_command_is_a_usage_request_not_a_lesson(self):
        assert parse_teach_command("/teach") == ""

    @pytest.mark.parametrize("message", [
        "teach me about quotes",           # no slash
        "/teacher of the year",            # different word
        "please /teach later",             # not at the start
        "hello there",
    ])
    def test_only_the_command_at_the_start_counts(self, message):
        assert parse_teach_command(message) is None


class TestDetectedTeachingCue:
    @pytest.mark.parametrize("message", [
        "Always CC the lead on quotes",
        "Never send a quote without the ROI table",
        "From now on, price the enterprise tier at 20% off",
        "Going forward, use the shorter subject line",
        "Remember that our refund window is 30 days",
        "Keep in mind that Northline prefers email",
        "Make sure you always attach the signed PDF",
        "When the lead is in the EU, always add VAT",
    ])
    def test_directives_are_detected(self, message):
        assert detect_teaching_cue(message)

    def test_soft_lead_ins_are_stripped_from_the_stored_rule(self):
        # The wrapper is conversational; the rule is the substance.
        assert detect_teaching_cue(
            "Remember that our refund window is 30 days"
        ) == "our refund window is 30 days"

    @pytest.mark.parametrize("message", [
        "I always wonder whether this works",     # cue not at the start
        "Do you always cc the lead?",             # a question
        "Never mind, use the other one",          # conversational opener
        "Always happy to help!",
        "always",                                 # too short to be a rule
        "Can you check the totals for me?",
    ])
    def test_ordinary_conversation_is_not_training(self, message):
        assert detect_teaching_cue(message) is None


# ---------------------------------------------------------------------------
# Service level (delivery + target resolution)
# ---------------------------------------------------------------------------

class TestTeachFromChat:
    def test_explicit_command_saves_a_permanent_lesson(self, db_session):
        agent = _make_agent(db_session)

        notice = teach_from_chat(
            db_session, agent_id=agent.id,
            lesson="Always CC the lead on quotes",
        )

        assert notice["status"] == "saved"
        assert notice["agent"]["id"] == agent.id
        assert notice["teaching_point_id"]
        assert notice["lesson"] == "Always CC the lead on quotes"
        assert agent.name in notice["message"]
        db_session.refresh(agent)
        assert _log(agent)[0]["lesson"] == "Always CC the lead on quotes"
        assert _log(agent)[0]["source"] == "teacher"

    def test_graduated_agent_learns_as_standing_guidance(self, db_session):
        """Teaching is the guidance channel, not a STUDENT privilege — a
        supervised hire's lesson must land too (no confidence nudge)."""
        agent = _make_agent(db_session, status="supervised", confidence=0.8)

        notice = teach_from_chat(
            db_session, agent_id=agent.id, lesson="Always verify vendor totals",
        )

        assert notice["status"] == "saved"
        assert notice["mode"] == "standing_guidance"
        db_session.refresh(agent)
        assert _log(agent)[-1]["lesson"] == "Always verify vendor totals"
        assert agent.confidence_score == pytest.approx(0.8)

    def test_repeating_a_lesson_is_reported_as_a_duplicate(self, db_session):
        agent = _make_agent(db_session, status="intern")

        first = teach_from_chat(db_session, agent_id=agent.id, lesson="Use the house tone")
        second = teach_from_chat(db_session, agent_id=agent.id, lesson="Use the house tone")

        assert first["status"] == "saved"
        assert second["status"] == "duplicate"
        db_session.refresh(agent)
        assert len([e for e in _log(agent) if e.get("lesson") == "Use the house tone"]) == 1

    def test_repeating_a_lesson_to_a_student_does_not_stack(self, db_session):
        """Regression (found live): the standing journal deduped, but the
        STUDENT pedagogy path did not — so /teach twice stacked two identical
        entries and the bounded work-time block rendered the same instruction
        twice, spending a lesson slot on a duplicate."""
        agent = _make_agent(db_session)  # STUDENT

        first = teach_from_chat(db_session, agent_id=agent.id, lesson="Always CC the lead")
        second = teach_from_chat(db_session, agent_id=agent.id, lesson="Always CC the lead")

        assert first["status"] == "saved"
        assert second["status"] == "duplicate"
        db_session.refresh(agent)
        assert len([e for e in _log(agent) if e.get("lesson") == "Always CC the lead"]) == 1

    def test_bare_command_asks_what_to_teach(self, db_session):
        notice = teach_from_chat(db_session, agent_id=None, lesson="")
        assert notice["status"] == "empty"
        assert "/teach" in notice["message"]

    def test_no_agent_lists_the_pickable_agents(self, db_session):
        agent = _make_agent(db_session, name="Sales Assistant")

        notice = teach_from_chat(
            db_session, agent_id=None, lesson="Always CC the lead on quotes",
        )

        assert notice["status"] == "needs_agent"
        ids = [a["id"] for a in notice["agents"]]
        assert agent.id in ids
        # The user must be able to act on the list, not just be told off.
        assert notice["lesson"] == "Always CC the lead on quotes"

    def test_unknown_agent_falls_back_to_the_picker(self, db_session):
        _make_agent(db_session, name="Sales Assistant")
        notice = teach_from_chat(
            db_session, agent_id="does-not-exist", lesson="Always CC the lead",
        )
        assert notice["status"] == "needs_agent"
        assert notice["agents"]

    def test_canvas_id_is_snapshotted_onto_the_lesson(self, db_session):
        from core.models import Canvas

        agent = _make_agent(db_session)
        canvas = Canvas(
            id=f"cv-{uuid.uuid4().hex[:8]}", name="Quote draft",
            canvas_type="email", content={"body": "Hi"},
            tenant_id="default", created_by="user-1", workspace_id="default",
        )
        db_session.add(canvas)
        db_session.commit()

        notice = teach_from_chat(
            db_session, agent_id=agent.id,
            lesson="Always CC the lead on quotes", canvas_id=canvas.id,
        )

        assert notice["status"] == "saved"
        db_session.refresh(agent)
        entry = [e for e in _log(agent) if e.get("lesson")][-1]
        assert entry["canvas"]["canvas_id"] == canvas.id

    def test_teach_never_raises_on_a_broken_agent_id(self, db_session):
        notice = teach_from_chat(db_session, agent_id=object(), lesson="Always be nice")
        assert notice["status"] == "needs_agent"

    def test_agent_list_is_bounded(self, db_session):
        for i in range(12):
            _make_agent(db_session, name=f"Agent {i}")
        agents = list_teachable_agents(db_session, limit=5)
        assert len(agents) == 5


class TestLessonSuggestion:
    def test_suggestion_does_not_write_anything(self, db_session):
        agent = _make_agent(db_session)

        notice = suggest_lesson(
            db_session, agent_id=agent.id, lesson="Always CC the lead on quotes",
        )

        assert notice["status"] == "suggested"
        assert notice["agent"]["name"] == agent.name
        db_session.refresh(agent)
        assert _log(agent) == []          # confirm-first: nothing saved yet

    def test_no_suggestion_without_an_agent(self, db_session):
        # With no target there is nothing to confirm — the card would be noise.
        assert suggest_lesson(db_session, agent_id=None, lesson="Always CC") is None


# ---------------------------------------------------------------------------
# Route level: POST /api/chat/message
# ---------------------------------------------------------------------------

@pytest.fixture
def chat_client(db_session: Session, monkeypatch):
    """The real chat router with the orchestrator's session bookkeeping
    stubbed (the teach path must not reach the reply model at all)."""
    import core.auth as auth_mod
    from core.database import get_db
    from integrations import chat_routes as cr

    monkeypatch.setattr(
        cr.chat_orchestrator, "_get_or_create_session",
        lambda user_id, session_id, context=None: {"id": session_id, "history": []},
    )
    monkeypatch.setattr(cr.chat_orchestrator, "_update_session", lambda *a, **k: None)

    app = FastAPI()
    app.include_router(cr.router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    user = type("User", (), {
        "id": "user-1", "email": "u@example.com",
        "workspace_id": "default", "tenant_id": "default", "role": "member",
    })()
    app.dependency_overrides[auth_mod.get_current_user] = lambda: user

    client = TestClient(app, raise_server_exceptions=False)
    yield client, cr
    app.dependency_overrides.clear()


def _post(client, message, **extra):
    return client.post("/api/chat/message", json={
        "message": message, "user_id": "user-1", **extra,
    })


class TestTeachCommandOverChat:
    def test_command_saves_and_confirms_without_calling_the_model(
        self, chat_client, db_session
    ):
        client, cr = chat_client
        agent = _make_agent(db_session)
        # If the reply leg runs at all, this blows up — teaching is deterministic.
        cr.chat_orchestrator.process_chat_message = AsyncMock(
            side_effect=AssertionError("the reply model must not run for /teach")
        )

        resp = _post(client, "/teach Always CC the lead on quotes", agent_id=agent.id)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["intent"] == "teaching"
        notice = body["metadata"]["teaching"]
        assert notice["status"] == "saved"
        assert notice["agent"]["id"] == agent.id
        db_session.refresh(agent)
        assert _log(agent)[0]["lesson"] == "Always CC the lead on quotes"

    def test_command_without_an_agent_returns_the_pick_list(self, chat_client, db_session):
        client, _ = chat_client
        _make_agent(db_session, name="Sales Assistant")

        resp = _post(client, "/teach Always CC the lead on quotes")

        assert resp.status_code == 200, resp.text
        notice = resp.json()["metadata"]["teaching"]
        assert notice["status"] == "needs_agent"
        assert notice["agents"]

    def test_canvas_turn_teaches_the_canvases_own_agent(self, chat_client, db_session):
        """The canvas side-chat posts context.agent_id — a /teach there must
        land on the attached hire with no extra plumbing."""
        client, _ = chat_client
        agent = _make_agent(db_session)

        resp = _post(
            client, "/teach Keep the closing friendly", agent_id=agent.id,
            context={"canvas_id": "cv-1", "canvas_type": "email", "agent_id": agent.id},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["metadata"]["teaching"]["status"] == "saved"
        db_session.refresh(agent)
        assert _log(agent)[0]["lesson"] == "Keep the closing friendly"


class TestDetectedCueOverChat:
    def test_cue_attaches_a_suggestion_and_saves_nothing(self, chat_client, db_session):
        client, cr = chat_client
        agent = _make_agent(db_session)
        cr.chat_orchestrator.process_chat_message = AsyncMock(return_value={
            "success": True, "message": "Sure — here's the draft.",
            "session_id": "s-1", "data": {"actions": []},
        })

        resp = _post(client, "Always CC the lead on quotes", agent_id=agent.id)

        assert resp.status_code == 200, resp.text
        notice = resp.json()["metadata"]["teaching"]
        assert notice["status"] == "suggested"
        assert notice["lesson"] == "Always CC the lead on quotes"
        assert resp.json()["message"] == "Sure — here's the draft."
        # Confirm-first: the detected cue alone must not write a lesson.
        db_session.refresh(agent)
        assert _log(agent) == []

    def test_ordinary_message_gets_no_teaching_metadata(self, chat_client, db_session):
        client, cr = chat_client
        _make_agent(db_session)
        cr.chat_orchestrator.process_chat_message = AsyncMock(return_value={
            "success": True, "message": "Here's the answer.",
            "session_id": "s-1", "data": {},
        })

        resp = _post(client, "What's the status of the Northline deal?", agent_id="x")

        assert resp.status_code == 200, resp.text
        assert "teaching" not in (resp.json().get("metadata") or {})

    def test_suggestion_is_not_offered_when_no_agent_is_attached(self, chat_client, db_session):
        client, cr = chat_client
        cr.chat_orchestrator.process_chat_message = AsyncMock(return_value={
            "success": True, "message": "ok", "session_id": "s-1", "data": {},
        })

        resp = _post(client, "Always CC the lead on quotes")

        assert resp.status_code == 200, resp.text
        assert "teaching" not in (resp.json().get("metadata") or {})


class TestTeachingPointHandleRoundTrip:
    """The handle a teaching surface hands back must be the handle removal
    resolves — that is what makes the chat card's inline Undo possible."""

    def test_handle_from_delivery_deletes_the_lesson(self, db_session):
        from core.student_learning_service import (
            deliver_teacher_lesson,
            delete_teaching_point,
            get_agent_lessons,
        )

        agent = _make_agent(db_session)
        delivery = deliver_teacher_lesson(db_session, agent.id, "Always CC the lead")

        point_id = delivery["entry"]["id"]
        assert point_id

        removed = delete_teaching_point(db_session, agent.id, point_id)
        assert removed.get("status") == "ok"
        assert get_agent_lessons(db_session, agent.id) == []


class TestTeachGoalContextOverChat:
    """Explicit goal context (chat opened from a run) beats inference — and
    must not pay for an LLM call at all."""

    def _goal_and_run(self, db_session, agent_id):
        from core.models import GoalObjective, GoalRun
        goal = GoalObjective(
            id="goal-chat-1", tenant_id="default", workspace_id="default",
            title="Prepare a quote for the Acme lead", status="active",
        )
        run = GoalRun(
            id="run-chat-1", tenant_id="default", workspace_id="default",
            goal_id="goal-chat-1", agent_id=agent_id, status="active",
        )
        db_session.add_all([goal, run])
        db_session.commit()

    def test_run_context_scopes_the_lesson_to_its_goal(
        self, chat_client, db_session, monkeypatch
    ):
        import core.chat_teaching as ct

        client, _ = chat_client
        agent = _make_agent(db_session)
        self._goal_and_run(db_session, agent.id)

        # Inference must not even be consulted when the run is known.
        async def _must_not_run(*a, **k):
            raise AssertionError("inference must not run for explicit context")
        monkeypatch.setattr(ct, "infer_lesson_goal", _must_not_run)

        resp = _post(
            client, "/teach Use the Q3 price book", agent_id=agent.id,
            context={"goal_run_id": "run-chat-1", "agent_id": agent.id},
        )

        assert resp.status_code == 200, resp.text
        notice = resp.json()["metadata"]["teaching"]
        assert notice["status"] == "saved"
        assert notice["scope"] == "goal"
        assert notice["goal_id"] == "goal-chat-1"
        assert notice["goal_title"] == "Prepare a quote for the Acme lead"
        assert notice["goal_inferred"] is False

        # The lesson is goal-scoped: invisible to ordinary work.
        from core.student_learning_service import get_agent_lessons
        assert get_agent_lessons(db_session, agent.id) == []

    def test_an_unknown_run_falls_back_to_inference(
        self, chat_client, db_session, monkeypatch
    ):
        import core.chat_teaching as ct

        client, _ = chat_client
        agent = _make_agent(db_session)
        # A LIVE goal for this agent, so inference has candidates (with none,
        # the route skips the call entirely — no goals, no cost).
        self._goal_and_run(db_session, agent.id)
        called = {"n": 0}

        async def _infer(llm_service, *, lesson, candidates, **kw):
            called["n"] += 1
            return None
        monkeypatch.setattr(ct, "infer_lesson_goal", _infer)

        resp = _post(
            client, "/teach Always CC the lead", agent_id=agent.id,
            context={"goal_run_id": "run-does-not-exist"},
        )

        assert resp.status_code == 200, resp.text
        notice = resp.json()["metadata"]["teaching"]
        assert notice["scope"] == "global"
        assert notice["status"] == "saved"
        # Inference was consulted (and returned nothing) — the run id was junk.
        assert called["n"] == 1

    def test_no_live_goals_skips_inference_entirely(
        self, chat_client, db_session, monkeypatch
    ):
        """An agent with nothing in flight must not pay for a model call."""
        import core.chat_teaching as ct

        client, _ = chat_client
        agent = _make_agent(db_session)

        async def _must_not_run(*a, **k):
            raise AssertionError("inference must not run without candidates")
        monkeypatch.setattr(ct, "infer_lesson_goal", _must_not_run)

        resp = _post(client, "/teach Always CC the lead", agent_id=agent.id)

        assert resp.status_code == 200, resp.text
        assert resp.json()["metadata"]["teaching"]["scope"] == "global"
