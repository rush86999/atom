"""Canvas broadcast channel fan-out contract (2026-09-09).

Every canvas present/update must reach BOTH the plain user channel (the
main chat pane's socket auto-joins it server-side) AND the session-scoped
variant (the /canvas/{id} page's subscription). canvas_tool's six present
emitters used to pick ONE channel — session-scoped when a session existed —
so a live chart/table present during a sessioned chat never reached the
main chat pane without a manual refresh.
"""

import os
os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, MagicMock

import pytest

from tools.canvas_tool import _user_broadcast_channels


class TestUserBroadcastChannels:
    def test_session_scoped_fans_out_to_both(self):
        channels = _user_broadcast_channels("u1", "s1")
        assert channels == ["user:u1", "user:u1:session:s1"]

    def test_no_session_is_user_channel_only(self):
        assert _user_broadcast_channels("u1", None) == ["user:u1"]
        assert _user_broadcast_channels("u1", "") == ["user:u1"]

    def test_no_user_falls_back_to_default(self):
        assert _user_broadcast_channels(None, None) == ["user:default"]
        assert _user_broadcast_channels("", "s1") == ["user:default"]


class TestPresentFansOutToBothChannels:
    """present_chart with a session must broadcast on BOTH channels — the
    regression is channel SELECTIVITY, so assert on the channels the mock
    manager saw."""

    @pytest.mark.asyncio
    async def test_present_chart_broadcasts_both_channels(self, monkeypatch):
        import tools.canvas_tool as ct

        broadcasts = []

        async def _fake_broadcast(channel, message):
            broadcasts.append(channel)

        monkeypatch.setattr(ct.ws_manager, "broadcast", _fake_broadcast)
        # Governance off + no agent lookup: the tool must degrade to a
        # plain present with audit skipped rather than error.
        monkeypatch.setattr(
            ct.FeatureFlags, "should_enforce_governance", lambda *_a, **_k: False
        )

        class _Result:
            success = True
            data = {"data": {"x": [1, 2], "y": [3, 4]}, "title": "t"}

        # Resolve-agent path: system default is enough for the broadcast
        # under test; stub the resolver so no DB is touched.
        class _FakeAgent:
            id = "agent-1"
            name = "Chat Assistant"

        class _FakeResolver:
            def resolve(self, *a, **k):
                return {"agent": _FakeAgent(), "maturity": None}

        monkeypatch.setattr(ct, "AgentContextResolver", lambda *a, **k: _FakeResolver())

        result = await ct.present_chart(
            chart_type="bar",
            title="t",
            data={"x": [1, 2], "y": [3, 4]},
            user_id="u1",
            session_id="s1",
        )
        assert result.get("success") is True
        assert broadcasts == ["user:u1", "user:u1:session:s1"]
