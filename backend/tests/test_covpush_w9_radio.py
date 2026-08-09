# -*- coding: utf-8 -*-
"""Coverage wave 9 — Agent Radio thin layer (radio_config, radio_guard).

Pushes core/agent_radio/radio_config.py (81% -> 100%) and
core/agent_radio/radio_guard.py (95% -> 100%). No source changes expected;
these are pure-function coverage of fail-safe defaults and guard branches.
"""

import os
import pytest

from core.agent_radio import radio_config
from core.agent_radio.radio_guard import (
    budget_allows_send,
    check_send_policy,
    inbox_pending_messages,
    interrupt_worth_it,
)
from core.models import AgentThread, LateralMessage


# ---------------------------------------------------------------------------
# radio_config
# ---------------------------------------------------------------------------

class TestRadioConfigEnvBool:
    def test_default_when_unset(self):
        os.environ.pop("ATOM_RADIO_TEST_BOOL", None)
        assert radio_config._env_bool("ATOM_RADIO_TEST_BOOL", True) is True
        assert radio_config._env_bool("ATOM_RADIO_TEST_BOOL", False) is False

    @pytest.mark.parametrize("raw", ["1", "true", "True", "TRUE", "yes", "on", " ON ", "1 ", "true "])
    def test_truthy_values(self, raw):
        os.environ["ATOM_RADIO_TEST_BOOL"] = raw
        assert radio_config._env_bool("ATOM_RADIO_TEST_BOOL", False) is True

    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", "anything", ""])
    def test_falsy_values(self, raw):
        os.environ["ATOM_RADIO_TEST_BOOL"] = raw
        assert radio_config._env_bool("ATOM_RADIO_TEST_BOOL", True) is False

    def test_empty_string_is_falsy(self):
        os.environ["ATOM_RADIO_TEST_BOOL"] = "  "
        assert radio_config._env_bool("ATOM_RADIO_TEST_BOOL", True) is False


class TestRadioConfigSetters:
    def test_master_switch_default_and_override(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_ENABLED", raising=False)
        assert radio_config.radio_enabled() is True
        monkeypatch.setenv("ATOM_RADIO_ENABLED", "false")
        assert radio_config.radio_enabled() is False
        monkeypatch.setenv("ATOM_RADIO_ENABLED", "true")
        assert radio_config.radio_enabled() is True

    def test_inbox_cap_default_and_override(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_INBOX_CAP", raising=False)
        assert radio_config.inbox_cap() == 10
        monkeypatch.setenv("ATOM_RADIO_INBOX_CAP", "42")
        assert radio_config.inbox_cap() == 42

    def test_backlog_ttl_default_and_override(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_BACKLOG_TTL_MIN", raising=False)
        assert radio_config.backlog_ttl_minutes() == 30
        monkeypatch.setenv("ATOM_RADIO_BACKLOG_TTL_MIN", "7")
        assert radio_config.backlog_ttl_minutes() == 7

    def test_team_budget_default_and_override(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_TEAM_BUDGET_USD", raising=False)
        assert radio_config.team_budget_usd() == 0.20
        monkeypatch.setenv("ATOM_RADIO_TEAM_BUDGET_USD", "1.5")
        assert radio_config.team_budget_usd() == 1.5

    def test_wait_timeout_default_and_override(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_WAIT_TIMEOUT_SECONDS", raising=False)
        assert radio_config.wait_timeout_seconds() == 30
        monkeypatch.setenv("ATOM_RADIO_WAIT_TIMEOUT_SECONDS", "5")
        assert radio_config.wait_timeout_seconds() == 5

    def test_breakpoint_gate_default_and_override(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_BREAKPOINT_GATE", raising=False)
        assert radio_config.breakpoint_gate_enabled() is True
        monkeypatch.setenv("ATOM_RADIO_BREAKPOINT_GATE", "false")
        assert radio_config.breakpoint_gate_enabled() is False


class TestRadioConfigStrings:
    def test_env_str_unset_returns_none(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_TEST_STR", raising=False)
        assert radio_config._env_str("ATOM_RADIO_TEST_STR") is None

    def test_env_str_value_stripped(self, monkeypatch):
        monkeypatch.setenv("ATOM_RADIO_TEST_STR", "  hello world  ")
        assert radio_config._env_str("ATOM_RADIO_TEST_STR") == "hello world"

    def test_thread_override_chain_id_reserved(self):
        assert radio_config.thread_override_chain_id("th-1") is None


# ---------------------------------------------------------------------------
# radio_guard
# ---------------------------------------------------------------------------

def make_thread(member_ids=None, created_by=None, status="open", metadata=None):
    t = AgentThread(
        id="th-1",
        name="t",
        status=status,
        created_by_agent_id=created_by or "agent-a",
        member_agent_ids=member_ids or ["agent-a", "agent-b"],
        metadata_json=metadata,
    )
    return t


def make_message(mentions, content="hello", metadata=None):
    return LateralMessage(
        id="m-1",
        thread_id="th-1",
        from_agent_id="agent-a",
        mentions=mentions or [],
        content=content,
        metadata_json=metadata,
    )


class TestCheckSendPolicy:
    def test_allowed_mention_send(self):
        t = make_thread()
        assert check_send_policy(t, "agent-a", ["agent-b"], None, "hello") is None

    def test_allowed_to_agent_send(self):
        t = make_thread()
        assert check_send_policy(t, "agent-a", None, "agent-b", "hello") is None

    def test_mention_deduplicated_with_to_agent(self):
        t = make_thread()
        # to_agent_id + mention of the same agent -> single recipient, allowed
        assert check_send_policy(t, "agent-a", ["agent-b", "agent-b"], "agent-b", "hi") is None

    def test_no_recipients_rejected(self):
        t = make_thread()
        msg = check_send_policy(t, "agent-a", [], None, "hello")
        assert "mention" in msg

    def test_only_self_mention_rejected(self):
        t = make_thread()
        msg = check_send_policy(t, "agent-a", ["agent-a"], None, "hello")
        assert msg is not None

    def test_empty_content_rejected(self):
        t = make_thread()
        assert check_send_policy(t, "agent-a", ["agent-b"], None, "   ") is not None

    def test_oversized_content_rejected(self):
        t = make_thread()
        msg = check_send_policy(t, "agent-a", ["agent-b"], None, "x" * 8001)
        assert "8000" in msg

    def test_closed_thread_rejected(self):
        t = make_thread(status="closed")
        assert check_send_policy(t, "agent-a", ["agent-b"], None, "hello") is not None

    def test_none_thread_rejected(self):
        assert check_send_policy(None, "agent-a", ["agent-b"], None, "hello") is not None

    def test_non_member_sender_rejected(self):
        t = make_thread(member_ids=["agent-b", "agent-c"], created_by="agent-z")
        assert check_send_policy(t, "agent-a", ["agent-b"], None, "hello") is not None

    def test_creator_not_in_roster_allowed(self):
        t = make_thread(member_ids=["agent-b"], created_by="agent-a")
        assert check_send_policy(t, "agent-a", ["agent-b"], None, "hello") is None


class TestBudgetAllowsSend:
    def test_none_thread_rejected(self):
        assert budget_allows_send(None, 0.1) is False

    def test_within_budget(self):
        t = make_thread(metadata={"used_budget_usd": 0.10})
        assert budget_allows_send(t, 0.05) is True

    def test_at_budget_exactly(self):
        t = make_thread(metadata={"used_budget_usd": 0.10})
        assert budget_allows_send(t, 0.10) is True

    def test_over_budget(self):
        t = make_thread(metadata={"used_budget_usd": 0.10})
        assert budget_allows_send(t, 0.11) is False

    def test_negative_cost_clamped_to_zero(self):
        t = make_thread(metadata={"used_budget_usd": 0.19})
        assert budget_allows_send(t, -5.0) is True

    def test_corrupt_budget_metadata_falls_back_to_zero(self):
        # metadata_json used_budget_usd is a non-numeric string -> float() raises
        t = make_thread(metadata={"used_budget_usd": "not-a-number"})
        assert budget_allows_send(t, 0.05) is True

    def test_corrupt_budget_metadata_typeerror(self):
        t = make_thread(metadata={"used_budget_usd": {"nested": True}})
        assert budget_allows_send(t, 0.05) is True


class TestInboxPendingMessages:
    def _msgs(self):
        return [
            make_message(["agent-b"]),
            make_message(["agent-b"], metadata={"read_by": ["agent-b"]}),
            make_message(["agent-c"]),
            make_message(["agent-b", "agent-c"]),
        ]

    def test_filters_to_unread_mentions(self):
        pending = inbox_pending_messages(self._msgs(), "agent-b")
        ids = [m.id for m in pending]
        assert len(ids) == 2  # read one excluded, non-mention excluded

    def test_cap_applied(self, monkeypatch):
        monkeypatch.setenv("ATOM_RADIO_INBOX_CAP", "1")
        pending = inbox_pending_messages(self._msgs(), "agent-b")
        assert len(pending) == 1

    def test_no_messages(self):
        assert inbox_pending_messages([], "agent-b") == []


class TestInterruptWorthIt:
    def test_not_mentioned_false(self):
        assert interrupt_worth_it(make_message(["agent-c"]), "agent-b") is False

    def test_empty_content_false(self):
        assert interrupt_worth_it(make_message(["agent-b"], content="   "), "agent-b") is False

    def test_high_priority_true(self):
        m = make_message(["agent-b"], metadata={"priority": "high"})
        assert interrupt_worth_it(m, "agent-b") is True

    def test_urgent_priority_true(self):
        m = make_message(["agent-b"], metadata={"priority": "urgent"})
        assert interrupt_worth_it(m, "agent-b") is True

    def test_response_marker_true(self):
        m = make_message(["agent-b"], metadata={"is_response": True})
        assert interrupt_worth_it(m, "agent-b") is True

    def test_plain_message_false(self):
        assert interrupt_worth_it(make_message(["agent-b"]), "agent-b") is False
