"""radio_guard tests — attention + cost governance (deterministic policies).

Covers: mention-first send policy, content size bounds, membership/access,
per-thread budget accounting, inbox cap, and interrupt-worthiness heuristics.
These are pure-function checks over in-memory model instances (no DB needed).
"""

from __future__ import annotations

from types import SimpleNamespace

from core.agent_radio import radio_guard


def _thread(members=("a", "b"), status="open", used=0.0):
    """Build a minimal stand-in for an AgentThread ORM row."""
    return SimpleNamespace(
        member_agent_ids=list(members),
        created_by_agent_id=members[0],
        status=status,
        metadata_json={"used_budget_usd": used},
    )


def _msg(mentions=(), content="hi", read_by=(), priority=None, is_response=False):
    meta = {"read_by": list(read_by)}
    if priority is not None:
        meta["priority"] = priority
    meta["is_response"] = is_response
    return SimpleNamespace(mentions=list(mentions), content=content, metadata_json=meta)


class TestSendPolicy:
    def test_allows_mentioned_send(self):
        assert radio_guard.check_send_policy(_thread(), "a", ["b"], None, "evidence") is None

    def test_rejects_broadcast(self):
        err = radio_guard.check_send_policy(_thread(), "a", [], None, "hi all")
        assert err is not None and "mention" in err.lower()

    def test_to_agent_counts_as_mention(self):
        assert radio_guard.check_send_policy(_thread(), "a", None, "b", "dm") is None

    def test_rejects_self_only_mention(self):
        err = radio_guard.check_send_policy(_thread(), "a", ["a"], None, "note")
        assert err is not None

    def test_rejects_empty_content(self):
        err = radio_guard.check_send_policy(_thread(), "a", ["b"], None, "   ")
        assert err is not None and "empty" in err.lower()

    def test_rejects_oversized_content(self):
        err = radio_guard.check_send_policy(_thread(), "a", ["b"], None, "x" * 8001)
        assert err is not None and "8000" in err

    def test_rejects_closed_thread(self):
        err = radio_guard.check_send_policy(_thread(status="closed"), "a", ["b"], None, "x")
        assert err is not None and "closed" in err.lower()

    def test_rejects_non_member(self):
        err = radio_guard.check_send_policy(_thread(), "intruder", ["b"], None, "x")
        assert err is not None and "member" in err.lower()


class TestBudget:
    def test_allows_within_budget(self):
        assert radio_guard.budget_allows_send(_thread(used=0.0), cost_usd=0.19) is True

    def test_blocks_over_budget(self):
        assert radio_guard.budget_allows_send(_thread(used=0.19), cost_usd=0.05) is False

    def test_zero_cost_always_allowed_if_under_cap(self):
        assert radio_guard.budget_allows_send(_thread(used=0.0), cost_usd=0.0) is True

    def test_missing_thread_denies(self):
        assert radio_guard.budget_allows_send(None) is False


class TestInboxCap:
    def test_caps_pending_list(self, monkeypatch):
        monkeypatch.setattr("core.agent_radio.radio_config.inbox_cap", lambda: 2)
        msgs = [_msg(mentions=["me"], read_by=[]) for _ in range(5)]
        out = radio_guard.inbox_pending_messages(msgs, "me")
        assert len(out) == 2

    def test_excludes_read_messages(self):
        msgs = [
            _msg(mentions=["me"], read_by=[]),
            _msg(mentions=["me"], read_by=["me"]),  # already read
        ]
        out = radio_guard.inbox_pending_messages(msgs, "me")
        assert len(out) == 1

    def test_excludes_unmentioned(self):
        msgs = [_msg(mentions=["other"]), _msg(mentions=["me"])]
        out = radio_guard.inbox_pending_messages(msgs, "me")
        assert len(out) == 1


class TestInterruptWorthiness:
    def test_unmentioned_never_interrupts(self):
        assert radio_guard.interrupt_worth_it(_msg(mentions=["other"]), "me") is False

    def test_empty_content_never_interrupts(self):
        assert radio_guard.interrupt_worth_it(_msg(mentions=["me"], content=""), "me") is False

    def test_high_priority_interrupts(self):
        assert radio_guard.interrupt_worth_it(
            _msg(mentions=["me"], priority="high"), "me"
        ) is True

    def test_response_message_interrupts(self):
        assert radio_guard.interrupt_worth_it(
            _msg(mentions=["me"], is_response=True), "me"
        ) is True

    def test_plain_mention_does_not_interrupt(self):
        # Conservative: ordinary mentions surface in the next drain, not as interrupts.
        assert radio_guard.interrupt_worth_it(_msg(mentions=["me"]), "me") is False
