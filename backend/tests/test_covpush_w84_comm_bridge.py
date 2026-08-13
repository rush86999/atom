# -*- coding: utf-8 -*-
"""Coverage wave 84 — core/universal_communication_bridge (standalone; real
in-memory SQLite for CommunicationChannel/UnifiedMessage, adapter classes
mocked so no network/deps are touched).

- get_adapter: known platform → adapter instance; unknown → None + warning.
- receive_message: unknown platform, falsy normalized payload, interactive
  callback routing (dispatcher patched; sender_id/user_id and action_id/value
  fallbacks), standard inbound on a NEW channel (channel + message created,
  metrics updated) and an EXISTING channel (no duplicate, count increments),
  exception → rollback + None.
- send_message: unknown platform → False, adapter failure → False, adapter
  raise → False, success → outbound UnifiedMessage recorded (direction/
  status/agent_id/metadata) + kwargs passthrough.
- _record_outbound: channel present vs absent (no crash).
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import CommunicationChannel, UnifiedMessage
from core.universal_communication_bridge import UniversalCommunicationBridge


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def bridge(db):
    return UniversalCommunicationBridge(db)


class _FakeAdapter:
    """Minimal stand-in for a PlatformAdapter subclass."""

    def __init__(self, normalize_result=None, send_result=True, send_kwargs=None):
        self._normalize_result = normalize_result
        self._send_result = send_result
        self._send_kwargs = send_kwargs
        self.normalize_payload = MagicMock(return_value=normalize_result)
        self.send_message = AsyncMock(return_value=send_result)

    @classmethod
    def for_bridge(cls, **kwargs):
        return cls(**kwargs)


def _patch_adapters(bridge, adapter_map):
    """Replace bridge.ADAPTERS with a dict of fake adapter CLASSES."""
    patcher = patch.object(UniversalCommunicationBridge, "ADAPTERS", adapter_map)
    patcher.start()
    return patcher


# ============================================================================
# get_adapter
# ============================================================================

class TestGetAdapter:
    def test_known_platform(self, bridge):
        fake_cls = type("Fake", (), {"__init__": lambda self: None})
        with patch.object(UniversalCommunicationBridge, "ADAPTERS", {"slack": fake_cls}):
            adapter = bridge.get_adapter("slack")
        assert isinstance(adapter, fake_cls)

    def test_unknown_platform(self, bridge, caplog):
        assert bridge.get_adapter("telegram") is None
        assert "No adapter found for platform: telegram" in caplog.text


# ============================================================================
# _parse_timestamp
# ============================================================================

class TestParseTimestamp:
    def test_none(self, bridge):
        assert bridge._parse_timestamp(None) is None

    def test_datetime_passthrough(self, bridge):
        dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
        assert bridge._parse_timestamp(dt) == dt

    def test_naive_datetime_gets_utc(self, bridge):
        parsed = bridge._parse_timestamp(datetime(2026, 8, 1))
        assert parsed == datetime(2026, 8, 1, tzinfo=timezone.utc)

    def test_iso_string_with_z(self, bridge):
        parsed = bridge._parse_timestamp("2026-08-01T00:00:00Z")
        assert parsed == datetime(2026, 8, 1, tzinfo=timezone.utc)

    def test_iso_string_naive_gets_utc(self, bridge):
        parsed = bridge._parse_timestamp("2026-08-01T00:00:00")
        assert parsed == datetime(2026, 8, 1, tzinfo=timezone.utc)

    def test_iso_string_with_offset(self, bridge):
        parsed = bridge._parse_timestamp("2026-08-01T02:00:00+02:00")
        assert parsed == datetime(2026, 8, 1, tzinfo=timezone.utc)

    def test_epoch_seconds(self, bridge):
        parsed = bridge._parse_timestamp(1700000000.0)
        assert parsed == datetime.fromtimestamp(1700000000.0, tz=timezone.utc)

    def test_epoch_int(self, bridge):
        parsed = bridge._parse_timestamp(1700000000)
        assert parsed == datetime.fromtimestamp(1700000000, tz=timezone.utc)

    def test_epoch_overflow(self, bridge):
        assert bridge._parse_timestamp(10 ** 100) is None

    def test_epoch_negative_too_far(self, bridge):
        assert bridge._parse_timestamp(-10 ** 100) is None

    def test_garbage_string(self, bridge):
        assert bridge._parse_timestamp("not-a-date") is None

    def test_other_types(self, bridge):
        assert bridge._parse_timestamp(["list"]) is None
        assert bridge._parse_timestamp(True) is None


# ============================================================================
# receive_message
# ============================================================================

class TestReceiveMessage:
    async def test_unknown_platform_returns_none(self, bridge):
        with patch.object(UniversalCommunicationBridge, "ADAPTERS", {}):
            result = await bridge.receive_message("t1", "telegram", {"a": 1}, b"raw")
        assert result is None

    async def test_falsy_normalized_returns_none(self, bridge):
        adapter = _FakeAdapter(normalize_result=None)
        with patch.object(UniversalCommunicationBridge, "ADAPTERS", {"slack": type("F", (), {"__init__": lambda self: None})}), \
                patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter):
            result = await bridge.receive_message("t1", "slack", {"a": 1})
        assert result is None

    async def test_interaction_routes_to_dispatcher(self, bridge):
        adapter = _FakeAdapter(normalize_result={
            "is_interaction": True,
            "sender_id": "u1",
            "action_id": "approve_proposal:1",
            "content": "x",
        })
        dispatcher = MagicMock()
        dispatcher.dispatch_action = AsyncMock(return_value={"success": True})
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter), \
                patch("core.universal_communication_bridge.get_messaging_action_dispatcher",
                      return_value=dispatcher):
            result = await bridge.receive_message("t1", "slack", {})
        assert result == {"type": "interaction",
                          "result": {"success": True},
                          "normalized": adapter._normalize_result}
        dispatcher.dispatch_action.assert_awaited_once_with(
            platform="slack", tenant_id="t1", user_id="u1",
            action_id="approve_proposal:1", payload=adapter._normalize_result)

    async def test_interaction_uses_user_id_and_value_fallbacks(self, bridge):
        adapter = _FakeAdapter(normalize_result={
            "type": "interaction",
            "user_id": "u2",
            "value": "feedback_thumbs",
        })
        dispatcher = MagicMock()
        dispatcher.dispatch_action = AsyncMock(return_value={"success": True})
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter), \
                patch("core.universal_communication_bridge.get_messaging_action_dispatcher",
                      return_value=dispatcher):
            result = await bridge.receive_message("t1", "slack", {})
        assert result["type"] == "interaction"
        dispatcher.dispatch_action.assert_awaited_once_with(
            platform="slack", tenant_id="t1", user_id="u2",
            action_id="feedback_thumbs", payload=adapter._normalize_result)

    async def test_standard_message_creates_channel_and_message(self, db, bridge):
        adapter = _FakeAdapter(normalize_result={
            "sender_id": "s1",
            "content": "Hello there " * 5,
            "channel_id": "c1",
            "metadata": {"channel_name": "General", "message_id": "m1",
                         "sender_name": "Sam", "timestamp": "2026-08-01T00:00:00Z"},
        })
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter):
            result = await bridge.receive_message("t1", "slack", {})
        assert result["type"] == "message"
        assert result["normalized"] == adapter._normalize_result

        channel = db.query(CommunicationChannel).filter_by(channel_id="c1").first()
        assert channel is not None
        assert channel.tenant_id == "t1"
        assert channel.platform == "slack"
        assert channel.channel_name == "General"
        assert channel.is_active is True
        assert channel.message_count == 1
        assert channel.last_message_at is not None

        msg = db.query(UnifiedMessage).first()
        assert msg.direction == "inbound"
        assert msg.status == "pending"
        assert msg.platform == "slack"
        assert msg.sender_id == "s1"
        assert msg.sender_name == "Sam"
        assert msg.platform_message_id == "m1"
        assert msg.content == "Hello there " * 5
        assert msg.metadata_json == {"channel_name": "General", "message_id": "m1",
                                     "sender_name": "Sam", "timestamp": "2026-08-01T00:00:00Z"}
        assert msg.platform_timestamp == datetime(2026, 8, 1)
        assert result["message_id"] == msg.id

    async def test_standard_message_existing_channel(self, db, bridge):
        channel = CommunicationChannel(
            tenant_id="t1", platform="slack", channel_id="c1",
            channel_name="Existing", is_active=True)
        db.add(channel)
        db.commit()
        adapter = _FakeAdapter(normalize_result={
            "sender_id": "s1", "content": "Hi", "channel_id": "c1", "metadata": {}})
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter):
            result = await bridge.receive_message("t1", "slack", {})
        assert result["type"] == "message"
        assert db.query(CommunicationChannel).count() == 1
        db.refresh(channel)
        assert channel.message_count == 1
        assert channel.channel_name == "Existing"

    async def test_default_channel_name_and_channel_id_fallback(self, db, bridge):
        adapter = _FakeAdapter(normalize_result={
            "sender_id": "s1", "content": "Hi", "metadata": {}})
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter):
            result = await bridge.receive_message("t1", "whatsapp", {})
        assert result["type"] == "message"
        channel = db.query(CommunicationChannel).first()
        assert channel.channel_id == "s1"
        assert channel.channel_name == "Whatsapp Channel"

    async def test_exception_rolls_back(self, db, bridge):
        adapter = _FakeAdapter()
        adapter.normalize_payload.side_effect = RuntimeError("boom")
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter):
            result = await bridge.receive_message("t1", "slack", {})
        assert result is None
        assert db.query(CommunicationChannel).count() == 0


# ============================================================================
# send_message
# ============================================================================

class TestSendMessage:
    async def test_unknown_platform_returns_false(self, bridge):
        with patch.object(UniversalCommunicationBridge, "ADAPTERS", {}):
            result = await bridge.send_message("t1", "telegram", "c1", "hi")
        assert result is False

    async def test_success_records_outbound(self, db, bridge):
        channel = CommunicationChannel(
            tenant_id="t1", platform="slack", channel_id="c1",
            channel_name="General", is_active=True)
        db.add(channel)
        db.commit()
        adapter = _FakeAdapter(send_result=True)
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter):
            result = await bridge.send_message("t1", "slack", "c1", "Hey there",
                                         agent_id="agent-1", metadata={"foo": "bar"})
        assert result is True
        adapter.send_message.assert_awaited_once_with("c1", "Hey there", foo="bar")
        msg = db.query(UnifiedMessage).first()
        assert msg is not None
        assert msg.direction == "outbound"
        assert msg.status == "processed"
        assert msg.agent_id == "agent-1"
        assert msg.sender_id == "agent"
        assert msg.content == "Hey there"
        assert msg.metadata_json == {"foo": "bar"}

    async def test_adapter_false_returns_false(self, db, bridge):
        adapter = _FakeAdapter(send_result=False)
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter):
            result = await bridge.send_message("t1", "slack", "c1", "hi")
        assert result is False
        assert db.query(UnifiedMessage).count() == 0

    async def test_adapter_raises_returns_false(self, db, bridge):
        adapter = _FakeAdapter()
        adapter.send_message = AsyncMock(side_effect=RuntimeError("network"))
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter):
            result = await bridge.send_message("t1", "slack", "c1", "hi")
        assert result is False
        assert db.query(UnifiedMessage).count() == 0

    async def test_success_without_existing_channel_no_record(self, db, bridge):
        adapter = _FakeAdapter(send_result=True)
        with patch.object(UniversalCommunicationBridge, "get_adapter", return_value=adapter):
            result = await bridge.send_message("t1", "slack", "ghost-channel", "hi")
        assert result is True
        assert db.query(UnifiedMessage).count() == 0


# ============================================================================
# _record_outbound (unit)
# ============================================================================

class TestRecordOutbound:
    def test_with_channel(self, db, bridge):
        channel = CommunicationChannel(
            tenant_id="t1", platform="slack", channel_id="c1",
            channel_name="General", is_active=True)
        db.add(channel)
        db.commit()
        bridge._record_outbound("t1", "slack", "c1", "content", "agent-9", {"k": "v"})
        msg = db.query(UnifiedMessage).first()
        assert msg is not None
        assert msg.direction == "outbound"
        assert msg.status == "processed"
        assert msg.agent_id == "agent-9"

    def test_without_channel_no_crash(self, db, bridge):
        bridge._record_outbound("t1", "slack", "missing", "content", None, None)
        assert db.query(UnifiedMessage).count() == 0
