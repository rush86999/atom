# -*- coding: utf-8 -*-
"""A lesson taught in chat must reach the agent that answers the chat.

Live failure this exists for (2026-09-16): the operator taught a used-machinery
pricing rule — "depreciate the new list price to the machine's age; if there is
no current price, fall back to the workbook ladder / a 40-50% margin" — and the
very next turns answered as if it had never been said. The rule WAS stored; it
was stored against one agent while the chat was being served by another, and
retrieval was strictly per-agent:

* the operator cannot know which agent a chat turn routes to, so teaching must
  not depend on that;
* the knowledge itself ("how we price used machines") is workspace truth, not one
  hire's quirk.

Design pinned here: an agent's OWN lessons keep priority, and relevant sibling
lessons fill the remaining slots, labelled so the model can attribute them.
"""
import pytest

from core.student_learning_service import (
    _lesson_in_scope,
    format_lessons_block,
    get_agent_lessons,
)


class _Agent:
    def __init__(self, agent_id, name, workspace=None):
        self.id = agent_id
        self.name = name
        self.workspace_id = workspace
        self.configuration = {}


class _Query:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class _DB:
    def __init__(self, agents):
        self._agents = agents

    def query(self, *a, **k):
        return _Query(self._agents)


def _lesson(text, topic="general"):
    return {"id": text[:6], "kind": "teacher_lesson", "lesson": text, "topic": topic}


@pytest.fixture
def world(monkeypatch):
    """One workspace, two agents: the lesson lives on the OTHER one."""
    sales = _Agent("sales", "Sales Agent", workspace=None)
    chat = _Agent("chat", "Chat Assistant", workspace="default")
    store = {"sales": [_lesson("depreciate the NEW list price to the machine's age",
                              topic="used machine pricing")],
             "chat": [_lesson("always CC the lead on quotes", topic="email")]}
    db = _DB([sales, chat])

    def _permanent(_db, agent_id):
        return list(store.get(str(agent_id), []))

    monkeypatch.setattr(
        "core.student_learning_service._permanent_lessons", _permanent
    )
    return db, store


class TestSiblingRecall:
    def test_own_lessons_only_when_workspace_recall_off(self, world):
        db, _ = world
        got = get_agent_lessons(
            db, "chat", query="used machine pricing", include_workspace=False
        )
        assert [l["lesson"] for l in got] == ["always CC the lead on quotes"]

    def test_sibling_lesson_is_reachable(self, world):
        db, _ = world
        got = get_agent_lessons(db, "chat", query="how do we price a used machine")
        texts = " ".join(l["lesson"] for l in got)
        assert "depreciate the NEW list price" in texts, (
            "a pricing rule taught to another agent must reach this one — the "
            "operator does not choose which agent answers"
        )

    def test_sibling_entries_are_marked_for_attribution(self, world):
        db, _ = world
        got = get_agent_lessons(db, "chat", query="used machine pricing")
        sibling = [l for l in got if "depreciate" in l["lesson"]]
        assert sibling and sibling[0].get("_source_agent_id") == "sales"

    def test_own_lesson_wins_a_relevance_tie(self, world, monkeypatch):
        db, store = world
        store["chat"] = [_lesson("used machine pricing rule of thumb")]
        got = get_agent_lessons(db, "chat", query="used machine pricing rule")
        assert got[0]["lesson"].startswith("used machine pricing rule of thumb")
        assert not got[0].get("_source_agent_id")

    def test_ranking_happens_before_the_limit(self, world):
        """The cap must not discard the highest-scoring sibling.

        The first implementation collected siblings until `limit` and THEN
        ranked, so four unrelated recent lessons displaced the 5-token match on
        "list price for a used machine".
        """
        db, store = world
        store["sales"] = [
            _lesson(f"unrelated recent note number {i}") for i in range(10)
        ] + [_lesson("list price for a used machine is depreciated", topic="pricing")]
        got = get_agent_lessons(
            db, "chat", query="list price for a used machine", limit=3
        )
        assert "depreciated" in got[0]["lesson"], (
            "scoring must run over ALL candidates, not the first `limit`"
        )

    def test_goal_scoped_sibling_lessons_stay_scoped(self, world):
        """Cross-agent recall must not smuggle goal-scoped rules out of scope.

        A lesson taught for ONE deal ("check the FX rate before asking me") is
        noise everywhere else, and that must hold when it is borrowed from a
        sibling agent too.
        """
        db, store = world
        scoped = _lesson("check the FX rate before quoting")
        scoped["scope"] = "goal"
        scoped["goal_id"] = "goal-1"
        store["sales"] = [scoped]

        asserted = _lesson_in_scope(scoped, None) is False
        assert asserted, "the scope predicate itself must exclude an unworked goal"

        # ...and the sibling path must not include it while working no goal
        monkeypatch_free = [l for l in get_agent_lessons(db, "chat", query="FX") 
                            if "FX rate" in str(l.get("lesson") or "")]
        assert monkeypatch_free == [], "goal-scoped sibling lesson leaked into normal work"
        assert _lesson_in_scope(scoped, "goal-1") is True


class TestLessonBlockRendering:
    def test_sibling_lessons_are_labelled(self, world):
        db, _ = world
        got = get_agent_lessons(db, "chat", query="used machine pricing")
        block = format_lessons_block(got)
        assert "DIFFERENT agent in this workspace" in block

    def test_block_is_empty_for_no_lessons(self):
        assert format_lessons_block([]) == ""


class TestMidMessageTeachingCapture:
    """Instructions that arrive mid-message must at least be OFFERED.

    Both previous channels required the message to OPEN with the directive. The
    way people teach while working is to append it to the request that prompted
    it ("open the workbook and show the derivation. use the above formula as a
    backup for pricing a used machine") — so the rule was neither stored NOR
    suggested, and the next turn answered as if it had never been said (live
    2026-09-16).
    """

    def test_mid_message_directive_is_detected(self):
        from core.chat_teaching import detect_mid_message_cue

        msg = (
            "open PRICE VIPUL (6).xlsx and show me the derivation. "
            "use the above formula as a backup for figuring out the list price "
            "from a dealer's used machine."
        )
        clause = detect_mid_message_cue(msg)
        assert clause and "backup" in clause.lower()
        assert "open PRICE VIPUL" not in clause, (
            "the suggestion must be the RULE, not the whole request that carried it"
        )

    @pytest.mark.parametrize(
        "msg",
        [
            "should I always CC the lead on quotes?",
            "what is the list price?",
            "never mind, that is fine",
        ],
    )
    def test_questions_and_chatter_are_not_lessons(self, msg):
        from core.chat_teaching import detect_mid_message_cue

        assert detect_mid_message_cue(msg) is None

    def test_detection_never_writes(self, world):
        """Confirm-first is the lesson-poisoning guard: detection is pure."""
        from core.chat_teaching import detect_mid_message_cue

        db, store = world
        before = {k: list(v) for k, v in store.items()}
        detect_mid_message_cue("always add the Canadian tariff line to quotes.")
        assert store == before, "detection must not write a permanent lesson"


class TestLessonCompleteness:
    """The suggestion must contain the METHOD, not just the announcement.

    The rule is typically stated in one sentence and EXPLAINED in the next ("use
    the above formula as a backup for pricing a used machine. Used machinery
    price is calculated from the new retail price depreciated to the machine's
    age."). Returning only the first sentence suggested a lesson that omitted the
    method entirely (live 2026-09-16).
    """

    MESSAGE = (
        "use the above formula as a backup (secondary option) for figuring out "
        "the list price from a dealer's used machine. Use machinery price is "
        "actually calculated from retail listed of a new one and depreciating as "
        "per market trends until the age of the machine is reached."
    )

    def test_elaboration_is_carried(self):
        from core.chat_teaching import detect_mid_message_cue

        clause = detect_mid_message_cue(self.MESSAGE)
        assert "backup" in clause.lower()
        assert "depreciating" in clause.lower(), (
            "the METHOD sentence must ride along with the announcement"
        )

    def test_a_new_directive_starts_a_new_lesson(self):
        """Two rules in one message must not be merged into one lesson."""
        from core.chat_teaching import detect_mid_message_cue

        clause = detect_mid_message_cue(
            "always CC the lead on quotes. never quote below warehouse cost."
        )
        assert "never quote below" not in clause.lower()

    def test_length_bound_still_applies(self):
        from core.chat_teaching import _MAX_LESSON_CHARS, detect_mid_message_cue

        clause = detect_mid_message_cue("always " + ("word " * 400))
        assert clause is None or len(clause) <= _MAX_LESSON_CHARS
