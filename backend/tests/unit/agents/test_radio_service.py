"""Agent Radio service tests — DB layer (AgentThread / LateralMessage).

Covers: thread creation, mention-first policy, per-recipient delivery
(read_by), budget governance, access control, and the passive inbox drain
text that the agent loops consume.
"""

import pytest
from unittest.mock import patch

from core.agent_radio import radio_service
from core.agent_radio.radio_config import ATOM_RADIO_ENABLED  # noqa: F401 (flag sanity)
from core.agent_radio.radio_service import (
    RadioAccessError,
    RadioBudgetExceeded,
    RadioPolicyError,
    create_thread,
    close_thread,
    get_pending_mentions,
    get_thread_snapshot,
    mark_read,
    send_message,
)
from core.models import AgentThread, LateralMessage


@pytest.fixture()
def thread(db_session):
    return create_thread(
        db_session,
        name="algo-team",
        created_by_agent_id="agent_a",
        member_agent_ids=["agent_b", "agent_c"],
    )


class TestCreateThread:
    def test_creator_is_always_a_member(self, db_session):
        t = create_thread(db_session, name="t", created_by_agent_id="agent_a",
                          member_agent_ids=["agent_b"])
        assert t.member_agent_ids == ["agent_a", "agent_b"]
        assert t.status == "open"
        assert t.metadata_json.get("used_budget_usd") == 0.0

    def test_persisted(self, db_session, thread):
        assert db_session.query(AgentThread).count() == 1
        assert thread.chain_id is None


class TestSendMentionFirst:
    def test_broadcast_rejected(self, db_session, thread):
        with pytest.raises(RadioPolicyError):
            send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                         content="hello everyone")

    def test_to_agent_implicitly_mentions(self, db_session, thread):
        m = send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                         content="for you", to_agent_id="agent_b")
        assert m.mentions == ["agent_b"]

    def test_own_mentions_stripped(self, db_session, thread):
        m = send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                         content="self note", mention_agent_ids=["agent_a", "agent_b"])
        assert m.mentions == ["agent_b"]

    def test_send_persists(self, db_session, thread):
        m = send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                         content="evidence found", mention_agent_ids=["agent_b"])
        assert isinstance(m.id, str)
        assert m.delivered is False
        assert (m.metadata_json or {}).get("read_by") == []


class TestPendingMentions:
    def test_pending_only_for_mentioned(self, db_session, thread):
        send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                     content="for b", mention_agent_ids=["agent_b"])
        send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                     content="for c", mention_agent_ids=["agent_c"])
        pending_b = get_pending_mentions(db_session, thread.id, "agent_b")
        pending_c = get_pending_mentions(db_session, thread.id, "agent_c")
        assert len(pending_b) == 1 and pending_b[0].content == "for b"
        assert len(pending_c) == 1 and pending_c[0].content == "for c"

    def test_own_messages_not_pending(self, db_session, thread):
        send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                     content="note to self-ish", mention_agent_ids=["agent_a", "agent_b"])
        assert get_pending_mentions(db_session, thread.id, "agent_a") == []

    def test_mark_read_removes_pending(self, db_session, thread):
        m = send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                         content="read me", mention_agent_ids=["agent_b", "agent_c"])
        mark_read(db_session, m, "agent_b")
        assert len(get_pending_mentions(db_session, thread.id, "agent_b")) == 0
        # But agent_c still has it pending (per-recipient delivery).
        assert len(get_pending_mentions(db_session, thread.id, "agent_c")) == 1
        mark_read(db_session, m, "agent_c")
        db_session.refresh(m)
        assert m.delivered is True  # all mentioned recipients have read

    def test_snapshot_counts_unread(self, db_session, thread):
        send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                     content="snap", mention_agent_ids=["agent_b"])
        snap = get_thread_snapshot(db_session, thread.id, "agent_b")
        assert snap["found"] is True
        assert snap["unread_mentions"] == 1
        assert snap["messages"][-1]["content"] == "snap"
        assert snap["member_agent_ids"] == ["agent_a", "agent_b", "agent_c"]

    def test_snapshot_missing_thread(self, db_session):
        snap = get_thread_snapshot(db_session, "nope", "agent_x")
        assert snap["found"] is False


class TestAccessAndBudget:
    def test_non_member_send_denied(self, db_session, thread):
        with pytest.raises(RadioAccessError):
            send_message(db_session, thread_id=thread.id, from_agent_id="intruder",
                         content="hi", mention_agent_ids=["agent_b"])

    def test_closed_thread_denied(self, db_session, thread):
        close_thread(db_session, thread.id)
        with pytest.raises(RadioAccessError):
            send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                         content="too late", mention_agent_ids=["agent_b"])

    def test_budget_exhaustion(self, db_session, thread, monkeypatch):
        monkeypatch.setattr("core.agent_radio.radio_config.team_budget_usd", lambda: 0.10)
        send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                     content="pricey", mention_agent_ids=["agent_b"], cost_usd=0.10)
        with pytest.raises(RadioBudgetExceeded):
            send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                         content="over", mention_agent_ids=["agent_b"], cost_usd=0.01)

    def test_budget_accumulates_on_thread(self, db_session, thread):
        send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                     content="a", mention_agent_ids=["agent_b"], cost_usd=0.05)
        send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                     content="b", mention_agent_ids=["agent_b"], cost_usd=0.03)
        db_session.refresh(thread)
        assert thread.metadata_json["used_budget_usd"] == 0.08


class TestInboxDrainText:
    def _patch_session_cm(self, monkeypatch, db_session):
        """Make get_db_session() return a CM that yields the live test session.

        ``inbox_drain_text`` uses ``with get_db_session() as db:`` — returning the
        raw session would let ``__exit__`` detach/close it. We yield without
        closing so the fixture stays usable across both drain calls.
        """
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield db_session

        monkeypatch.setattr("core.database.get_db_session", _cm)

    def test_drain_injects_mention_lines(self, db_session, thread, monkeypatch):
        send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                     content="server-side logs required", mention_agent_ids=["agent_b"])
        self._patch_session_cm(monkeypatch, db_session)
        text = radio_service.inbox_drain_text("agent_b", thread.id)
        assert "RADIO INBOX" in text
        assert "server-side logs required" in text
        # Idempotent: the mention was surfaced once.
        assert radio_service.inbox_drain_text("agent_b", thread.id) == ""

    def test_drain_auto_thread_resolution(self, db_session, thread, monkeypatch):
        send_message(db_session, thread_id=thread.id, from_agent_id="agent_a",
                     content="look here", mention_agent_ids=["agent_c"])
        self._patch_session_cm(monkeypatch, db_session)
        text = radio_service.inbox_drain_text("agent_c")
        assert "look here" in text

    def test_drain_never_raises(self, db_session, thread):
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("core.agent_radio.radio_config.radio_enabled",
                            lambda: False)
        assert radio_service.inbox_drain_text("agent_b", thread.id) == ""
        monkeypatch.undo()