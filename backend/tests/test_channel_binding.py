"""
Round 72 — Workstream I: channel-binding fix (cross-channel context leak).

Covers:
- universal_webhook_bridge binds session_id to channel/thread (sender on two
  channels of one platform gets distinct sessions).
- Reply routing still targets the source channel (outgoing side unchanged).
- ChatSessionManager.create_session persists channel_id/thread_id (DB path).
- ChatSession model round-trips the new columns.
- Alembic migration is guarded + idempotent on SQLite.
"""
import importlib
import importlib.util
from contextlib import contextmanager
import pathlib
import site
import sys
from unittest.mock import AsyncMock, patch

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.models import ChatSession, Base

_MIGRATION_FILE = str(
    pathlib.Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "20260802_add_chat_session_channel.py"
)


@contextmanager
def _real_alembic():
    """Temporarily expose the installed alembic (the local backend/alembic
    package shadows it under PYTHONPATH) and load the migration module fresh."""
    site_packages = next(
        sp for sp in site.getsitepackages()
        if (pathlib.Path(sp) / "alembic" / "migration.py").exists()
    )
    sys.path.insert(0, site_packages)
    for name in [n for n in sys.modules if n == "alembic" or n.startswith("alembic.")]:
        del sys.modules[name]
    importlib.invalidate_caches()
    try:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        spec = importlib.util.spec_from_file_location("_channel_migration", _MIGRATION_FILE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield MigrationContext, Operations, mod
    finally:
        sys.path.pop(0)
        for name in [n for n in sys.modules if n == "_channel_migration"]:
            del sys.modules[name]
        # Reload the local shadowing package so later imports keep working.
        for name in [n for n in sys.modules if n == "alembic" or n.startswith("alembic.")]:
            del sys.modules[name]
        importlib.invalidate_caches()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeOrchestrator:
    """Records the session_id/context the bridge would pass to ChatOrchestrator."""

    def __init__(self, response=None):
        self.calls = []
        self.response = response or {"message": ""}

    async def process_chat_message(self, message, session_id, user_id, context):
        self.calls.append(
            {"message": message, "session_id": session_id, "user_id": user_id, "context": context}
        )
        return self.response


def _slack_payload(channel: str, ts: str, thread_ts=None, user: str = "U1") -> dict:
    payload = {"type": "message", "user": user, "channel": channel, "text": "hello", "ts": ts}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    return payload


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Bridge session-id binding
# ---------------------------------------------------------------------------

class TestBridgeSessionBinding:
    def _bridge_with_fake(self, fake):
        from integrations.universal_webhook_bridge import UniversalWebhookBridge
        bridge = UniversalWebhookBridge()
        bridge._orchestrator = fake
        return bridge

    def test_same_sender_two_channels_get_distinct_sessions(self):
        fake = FakeOrchestrator()
        bridge = self._bridge_with_fake(fake)

        asyncio_run(bridge.process_incoming_message("slack", _slack_payload("C_A", "1")))
        asyncio_run(bridge.process_incoming_message("slack", _slack_payload("C_B", "2")))

        assert len(fake.calls) == 2
        session_a = fake.calls[0]["session_id"]
        session_b = fake.calls[1]["session_id"]
        assert session_a != session_b
        assert "C_A" in session_a
        assert "C_B" in session_b
        # Same sender, but distinct contexts must also carry their channel.
        assert fake.calls[0]["context"]["channel_id"] == "C_A"
        assert fake.calls[1]["context"]["channel_id"] == "C_B"

    def test_thread_scoped_sessions_are_distinct(self):
        fake = FakeOrchestrator()
        bridge = self._bridge_with_fake(fake)

        asyncio_run(bridge.process_incoming_message(
            "slack", _slack_payload("C_A", "1", thread_ts="t1")))
        asyncio_run(bridge.process_incoming_message(
            "slack", _slack_payload("C_A", "2", thread_ts="t2")))

        assert len(fake.calls) == 2
        assert fake.calls[0]["session_id"] != fake.calls[1]["session_id"]
        assert fake.calls[0]["context"]["thread_id"] == "t1"
        assert fake.calls[1]["context"]["thread_id"] == "t2"

    def test_same_channel_reuses_same_session(self):
        fake = FakeOrchestrator()
        bridge = self._bridge_with_fake(fake)

        asyncio_run(bridge.process_incoming_message("slack", _slack_payload("C_A", "1")))
        asyncio_run(bridge.process_incoming_message("slack", _slack_payload("C_A", "2")))

        assert fake.calls[0]["session_id"] == fake.calls[1]["session_id"]

    def test_reply_routing_still_targets_source_channel(self):
        """Outgoing routing is unchanged — replies go to the source channel."""
        fake = FakeOrchestrator(response={"message": "hi"})
        bridge = self._bridge_with_fake(fake)

        with patch(
            "core.agent_integration_gateway.agent_integration_gateway.execute_action",
            new=AsyncMock(return_value={"success": True}),
        ) as mock_execute:
            result = asyncio_run(bridge.process_incoming_message(
                "slack", _slack_payload("C_A", "1")))

        assert result["status"] == "success"
        _, platform, send_params = mock_execute.call_args.args
        assert platform == "slack"
        assert send_params["channel"] == "C_A"


# ---------------------------------------------------------------------------
# ChatSession model + ChatSessionManager persistence
# ---------------------------------------------------------------------------

def _make_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[ChatSession.__table__])
    Session = sessionmaker(bind=engine)
    return Session()


class TestChatSessionPersistence:
    def test_model_roundtrips_channel_and_thread(self):
        db = _make_session()
        db.add(ChatSession(
            id="s1", user_id="u1", channel_id="C_A", thread_id="t1", message_count=0
        ))
        db.commit()
        row = db.query(ChatSession).filter(ChatSession.id == "s1").first()
        assert row.channel_id == "C_A"
        assert row.thread_id == "t1"

    def test_create_session_persists_channel_and_thread(self, monkeypatch):
        db = _make_session()
        from core import chat_session_manager as csm

        @contextmanager
        def fake_get_db_session():
            yield db

        manager = csm.ChatSessionManager.__new__(csm.ChatSessionManager)
        manager.use_db = True
        manager.persistence_mode = "STRICT_DB"
        manager.sessions_file = "/tmp/never_used.json"

        monkeypatch.setattr(csm, "get_db_session", fake_get_db_session)

        sid = manager.create_session(
            user_id="u1", session_id="s1", channel_id="C_A", thread_id="t1"
        )
        assert sid == "s1"

        row = db.query(ChatSession).filter(ChatSession.id == "s1").first()
        assert row is not None
        assert row.channel_id == "C_A"
        assert row.thread_id == "t1"


# ---------------------------------------------------------------------------
# ChatOrchestrator session binding
# ---------------------------------------------------------------------------

class TestOrchestratorSessionBinding:
    def _orchestrator(self):
        from integrations.chat_orchestrator import ChatOrchestrator
        orch = ChatOrchestrator.__new__(ChatOrchestrator)
        orch.conversation_sessions = {}
        orch.session_manager = None
        return orch

    def test_sessions_carry_channel_and_thread(self):
        orch = self._orchestrator()
        session = orch._get_or_create_session(
            "u1", "s1", {"channel_id": "C_A", "thread_id": "t1"}
        )
        assert session["channel_id"] == "C_A"
        assert session["thread_id"] == "t1"

    def test_context_fallback_to_recipient_id(self):
        """The bridge passes recipient_id for channels not in context['channel_id']."""
        orch = self._orchestrator()
        session = orch._get_or_create_session("u1", "s1", {"recipient_id": "C_B"})
        assert session["channel_id"] == "C_B"


# ---------------------------------------------------------------------------
# Alembic migration (guarded + idempotent on SQLite)
# ---------------------------------------------------------------------------

class TestMigration:
    def test_upgrade_adds_columns_and_is_idempotent(self):
        engine = create_engine("sqlite://")
        with _real_alembic() as (MigrationContext, Operations, mod):
            with engine.begin() as conn:
                conn.execute(text(
                    "CREATE TABLE chat_sessions "
                    "(id VARCHAR PRIMARY KEY, user_id VARCHAR NOT NULL)"
                ))
                context = MigrationContext.configure(conn)
                with Operations.context(context):
                    mod.upgrade()

            cols = [c["name"] for c in sa.inspect(engine).get_columns("chat_sessions")]
            assert "channel_id" in cols
            assert "thread_id" in cols

            # Second run must skip (column already exists) without error.
            with engine.begin() as conn:
                context = MigrationContext.configure(conn)
                with Operations.context(context):
                    mod.upgrade()

            cols = [c["name"] for c in sa.inspect(engine).get_columns("chat_sessions")]
            assert "channel_id" in cols

    def test_skip_when_table_absent(self):
        engine = create_engine("sqlite://")
        with _real_alembic() as (MigrationContext, Operations, mod):
            with engine.begin() as conn:
                context = MigrationContext.configure(conn)
                with Operations.context(context):
                    mod.upgrade()  # no chat_sessions table -> no-op, no error
