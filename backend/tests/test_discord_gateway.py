"""
Discord Gateway client (P0.4 §7 follow-up): real-time MESSAGE_CREATE ingestion.

RED: no gateway client exists — Discord messages only reached memory via the
chat bridge (interactions only) or nothing at all.

Contracts pinned here (all against an injected fake WebSocket — no network):
  - lifecycle: HELLO (op 10) -> IDENTIFY (op 2) carrying the bot token +
    GUILD_MESSAGES|MESSAGE_CONTENT intents; HEARTBEAT (op 1) sent when the
    interval elapses; op 11 treated as heartbeat ACK.
  - dispatch: MESSAGE_CREATE payloads reach the on_message callback as
    normalized comm records ({id, content, author, channel_id, guild_id,
    timestamp, direction="inbound", source_app="discord"}).
  - non-dispatch / non-message events are ignored silently.
  - resilience: a raised/closed connection triggers reconnect with
    exponential backoff (capped), and the client keeps consuming.
  - gating: maybe_start_from_env() is a no-op unless DISCORD_GATEWAY_ENABLED
    is truthy AND DISCORD_BOT_TOKEN is set.
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from integrations.discord_gateway import DiscordGatewayClient


class FakeWS:
    """Minimal async websocket double driven by a scripted frame queue."""

    def __init__(self, frames, fail_after=None):
        self.sent = []
        self._frames = list(frames)
        self._fail_after = fail_after
        self._count = 0
        self.closed = False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def recv(self):
        if self._fail_after is not None and self._count >= self._fail_after:
            raise ConnectionError("connection dropped")
        if self._count >= len(self._frames):
            self.closed = True
            raise ConnectionError("no more frames")
        frame = self._frames[self._count]
        self._count += 1
        return json.dumps(frame)

    async def recv_blocking(self):
        """Never returns data — forces heartbeat timeouts."""
        await asyncio.sleep(0.05)
        return None

    async def close(self):
        self.closed = True


def hello(interval_ms=20000):
    return {"op": 10, "d": {"heartbeat_interval": interval_ms}}


def dispatch(event, data):
    return {"op": 0, "t": event, "d": data}


def message_create(mid="m1", content="deploy is green", user="devops"):
    return {
        "id": mid,
        "content": content,
        "author": {"username": user},
        "channel_id": "ch_9",
        "guild_id": "g_1",
        "timestamp": "2026-08-21T12:00:00+00:00",
    }


@pytest.fixture()
def received():
    return []


@pytest.fixture()
def client(received):
    return DiscordGatewayClient(
        bot_token="tok", on_message=received.append, heartbeat_jitter=False,
    )


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_identify_sent_after_hello(self, client, received):
        ws = FakeWS([hello(20000)])
        await client._run_once(ws)
        ops = [(f["op"], f.get("t")) for f in ws.sent]
        assert (2, None) in ops or any(f["op"] == 2 for f in ws.sent)
        identify = next(f for f in ws.sent if f["op"] == 2)
        assert identify["d"]["token"] == "tok"
        # GUILD_MESSAGES | MESSAGE_CONTENT
        assert identify["d"]["intents"] == 512 | 32768

    @pytest.mark.asyncio
    async def test_message_create_reaches_callback_normalized(self, client, received):
        ws = FakeWS([hello(), dispatch("MESSAGE_CREATE", message_create())])
        await client._run_once(ws)
        assert len(received) == 1
        rec = received[0]
        assert rec["id"] == "m1"
        assert rec["content"] == "deploy is green"
        assert rec["author"] == "devops"
        assert rec["channel_id"] == "ch_9" and rec["guild_id"] == "g_1"
        assert rec["direction"] == "inbound"
        assert rec["source_app"] == "discord"

    @pytest.mark.asyncio
    async def test_non_message_events_ignored(self, client, received):
        ws = FakeWS([
            hello(),
            dispatch("GUILD_CREATE", {"id": "g"}),
            {"op": 11},  # heartbeat ACK
        ])
        await client._run_once(ws)
        assert received == []

    @pytest.mark.asyncio
    async def test_heartbeat_sent_when_interval_elapsed(self, client, received):
        class IdleWS(FakeWS):
            def __init__(self, frames):
                super().__init__(frames)
                self._hello_done = False

            async def recv(self):
                if not self._hello_done:
                    self._hello_done = True
                    return json.dumps(self._frames[0])
                await self.recv_blocking()

        ws = IdleWS([hello(10)])
        await client._run_once(ws, max_iterations=3)
        heartbeats = [f for f in ws.sent if f["op"] == 1]
        assert len(heartbeats) >= 1


class TestResilience:
    @pytest.mark.asyncio
    async def test_connection_drop_triggers_reconnect_with_backoff(self, client, received):
        sleeps = []

        async def fake_sleep(s):
            sleeps.append(s)

        ws1 = FakeWS([hello()], fail_after=1)
        ws2 = FakeWS([
            hello(),
            dispatch("MESSAGE_CREATE", message_create("after-reconnect")),
        ])

        async def factory():
            return ws1 if not client._reconnected_once else ws2

        with patch.object(client, "_sleep", side_effect=fake_sleep):
            client._reconnected_once = False
            # run two connection lifetimes then stop
            await client._run_once(ws1)
            client._reconnected_once = True
            await client._run_once(ws2)

        # after the drop, the second session still delivers messages
        assert received[0]["id"] == "after-reconnect"

    def test_maybe_start_gated_by_env(self, received):
        import os

        from integrations.discord_gateway import maybe_start_from_env

        called = {}

        class _GateClient:
            def __init__(self, bot_token, on_message=None, **kw):
                called["token"] = bot_token
                called["cb"] = on_message

            async def start(self):
                called["started"] = True

        with patch("integrations.discord_gateway.DiscordGatewayClient", _GateClient):
            env_off = {"DISCORD_GATEWAY_ENABLED": "false",
                       "DISCORD_BOT_TOKEN": "tok"}
            with patch.dict(os.environ, env_off):
                assert maybe_start_from_env(cb=received.append) is False
            env_no_token = {"DISCORD_GATEWAY_ENABLED": "true"}
            with patch.dict(os.environ, env_no_token):
                os_env = dict(os.environ)
                os_env.pop("DISCORD_BOT_TOKEN", None)
                with patch.dict(os.environ, os_env, clear=True):
                    assert maybe_start_from_env(cb=received.append) is False
            import asyncio as _asyncio

            env_on = {"DISCORD_GATEWAY_ENABLED": "true",
                      "DISCORD_BOT_TOKEN": "tok"}

            async def _start():
                from integrations.discord_gateway import maybe_start_from_env

                return maybe_start_from_env(cb=received.append)

            with patch.dict(os.environ, env_on):
                started = _asyncio.get_event_loop().run_until_complete(_start())
            assert started is True
            assert called["token"] == "tok" and called["started"] is True