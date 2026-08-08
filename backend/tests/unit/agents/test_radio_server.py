"""Agent Radio server tests — async relay (wakeups, bounded waits, ping-pong).

These prove the harness works: messages published for mentioned agents wake
their bounded `wait_for_mention` across `asyncio.create_task` agents, timeouts
never hang, and the drain covers queue/DB both sides.
"""

import asyncio

import pytest

from core.agent_radio import radio_service
from core.agent_radio.radio_server import (
    get_radio_server,
    reset_radio_server,
)


@pytest.fixture(autouse=True)
def _reset_relay():
    reset_radio_server()
    yield
    reset_radio_server()


@pytest.fixture()
def thread(db_session):
    return radio_service.create_thread(
        db_session,
        name="ping-pong",
        created_by_agent_id="agent_a",
        member_agent_ids=["agent_b"],
    )


class TestWaitForMention:
    async def test_blocks_until_mention(self, db_session, thread):
        server = get_radio_server()
        waiter = asyncio.create_task(
            server.wait_for_mention(thread.id, "agent_a", timeout=5, db=db_session)
        )
        await asyncio.sleep(0.05)
        msg = radio_service.send_message(
            db_session, thread_id=thread.id, from_agent_id="agent_b",
            content="pong", mention_agent_ids=["agent_a"])
        await server.publish(msg)
        message = await waiter
        assert message is not None
        assert message.content == "pong"
        assert message.id == msg.id

    async def test_times_out_without_mention(self, db_session, thread):
        server = get_radio_server()
        result = await server.wait_for_mention(thread.id, "nobody", timeout=0.1, db=db_session)
        assert result is None

    async def test_timeout_is_capped_by_config(self, db_session, thread, monkeypatch):
        monkeypatch.setattr("core.agent_radio.radio_config.wait_timeout_seconds",
                            lambda: 1)
        server = get_radio_server()
        # Requested 30s but config caps at 1s — must return promptly.
        loop = asyncio.get_event_loop()
        start = loop.time()
        await server.wait_for_mention(thread.id, "nobody", timeout=30, db=db_session)
        assert loop.time() - start < 5

    async def test_drains_pending_before_waiting(self, db_session, thread):
        radio_service.send_message(
            db_session, thread_id=thread.id, from_agent_id="agent_b",
            content="already waiting", mention_agent_ids=["agent_a"])
        server = get_radio_server()
        message = await server.wait_for_mention(thread.id, "agent_a", timeout=0.1, db=db_session)
        assert message is not None and message.content == "already waiting"

    async def test_never_raises(self, db_session):
        server = get_radio_server()
        result = await server.wait_for_mention("missing-thread", "agent_x",
                                               timeout=0.1, db=db_session)
        assert result is None


class TestPublishLifecycles:
    async def test_publish_does_not_raise_without_listener(self, db_session, thread):
        msg = radio_service.send_message(
            db_session, thread_id=thread.id, from_agent_id="agent_b",
            content="x", mention_agent_ids=["agent_a"])
        server = get_radio_server()
        await server.publish(msg)  # nobody listening — must be a no-op