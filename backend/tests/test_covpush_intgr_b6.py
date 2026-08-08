"""Coverage push for integrations wave B - batch 6 (discord/google_chat/pdf)."""
import asyncio
import base64
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ============================================================================
# atom_discord_integration
# ============================================================================


class TestDiscordIntegration:
    def _svc(self, **kw):
        from integrations.atom_discord_integration import AtomDiscordIntegration
        cfg = {"atom_memory_service": MagicMock(), "atom_search_service": MagicMock(),
               "atom_workflow_service": MagicMock(), "atom_ingestion_pipeline": MagicMock()}
        cfg.update(kw)
        return AtomDiscordIntegration(cfg)

    def _guild(self):
        from integrations.discord_enhanced_service import DiscordGuild
        return DiscordGuild(
            guild_id="g1", name="Server", owner_id="o1", owner_name="Owner",
            member_count=10, channel_count=3, icon_url="", description="d",
            is_connected=True, features=[], premium_tier=0, verification_level=0,
            roles_count=0, emojis_count=0, created_at=datetime.now(timezone.utc),
            region="us", integration_data={},
        )

    async def test_initialize(self):
        svc = self._svc()
        svc.discord_service = MagicMock()
        with patch.object(svc, "_start_integration_workers", AsyncMock()), \
             patch.object(svc, "_initialize_unified_data", AsyncMock()), \
             patch.object(svc, "_setup_cross_platform_handlers", AsyncMock()):
            assert await svc.initialize() is True
        svc2 = self._svc()
        assert await svc2.initialize() is False  # no discord service

    async def test_get_unified_workspaces(self):
        from integrations.discord_enhanced_service import DiscordGuild
        svc = self._svc()
        guild = self._guild()
        svc.discord_service = MagicMock()
        svc.discord_service.get_guilds = AsyncMock(return_value=[guild])
        ws = await svc.get_unified_workspaces("u1")
        assert len(ws) == 1
        assert ws[0]["id"] == "discord_g1"
        assert ws[0]["capabilities"]["messaging"] is True
        svc.discord_service.get_guilds = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.get_unified_workspaces("u1") == []

    async def test_get_unified_channels(self):
        from integrations.discord_enhanced_service import DiscordChannel
        svc = self._svc()
        svc.discord_service = MagicMock()
        channel = DiscordChannel(
            channel_id="c1", name="general", type=__import__("integrations.discord_enhanced_service", fromlist=["DiscordChannelType"]).DiscordChannelType.TEXT,
            guild_id="g1", guild_name="Server", topic="t", is_archived=False,
            member_count=5, message_count=10, last_modified_at="2024-01-01",
            is_private=False, is_text=True, is_voice=False, is_stage=False, is_news=False,
            is_thread=False, position=0, parent_id=None, permissions=[], rate_limit_per_user=0,
            nsfw=False, bitrate=0, user_limit=0, default_auto_archive_duration=0, flags=0,
            permission_overwrites=[], last_pin_timestamp=None, rtc_region=None,
            integration_data={},
        )
        import integrations.atom_discord_integration as mod
        from integrations.discord_enhanced_service import DiscordGuild as RealGuild
        svc.discord_service.get_guild_channels = AsyncMock(return_value=[channel])
        with patch.object(mod, "DiscordGuild", RealGuild):
            ch = await svc.get_unified_channels("discord_g1", "u1")
        assert len(ch) == 1
        assert ch[0]["type"] == "guild-text"
        assert await svc.get_unified_channels("slack_w1", "u1") == []
        # unknown platform -> []
        assert await svc.get_unified_channels("zz", "u1") == []
        svc.discord_service.get_guild_channels = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.get_unified_channels("discord_g1", "u1") == []

    async def test_send_unified_message(self):
        svc = self._svc()
        svc.discord_service = MagicMock()
        svc.discord_service.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        svc._store_message_in_memory = AsyncMock()
        svc._index_message_in_search = AsyncMock()
        svc._trigger_workflows = AsyncMock()
        result = await svc.send_unified_message("w1", "discord_c1", "hi")
        assert result["ok"] is True
        svc.discord_service.send_message = AsyncMock(return_value={"ok": False, "error": "e"})
        result = await svc.send_unified_message("w1", "discord_c1", "hi")
        assert result["ok"] is False
        result = await svc.send_unified_message("w1", "slack_c1", "hi")
        assert result["ok"] is False
        svc.discord_service.send_message = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.send_unified_message("w1", "discord_c1", "hi")
        assert result["ok"] is False

    async def test_get_unified_messages(self):
        svc = self._svc()
        svc.discord_service = MagicMock()
        msg = MagicMock()
        msg.message_id = "m1"
        msg.content = "hi"
        msg.html_content = "hi"
        msg.platform = "discord"
        msg.workspace_id = "w1"
        msg.channel_id = "c1"
        msg.user_id = "u1"
        msg.user_name = "B"
        msg.user_display_name = "B"
        msg.user_avatar = ""
        msg.timestamp = "t"
        msg.thread_id = None
        msg.reply_to_id = None
        msg.message_type = "default"
        msg.is_edited = False
        msg.is_pinned = False
        msg.is_bot = False
        msg.is_webhook = False
        msg.reactions = []
        msg.attachments = []
        msg.embeds = []
        msg.mentions = []
        msg.files = []
        msg.integration_data = {}
        msg.metadata = {}
        svc.discord_service.get_channel_messages = AsyncMock(return_value=[msg])
        messages = await svc.get_unified_messages("w1", "discord_c1")
        assert len(messages) == 1
        assert messages[0]["id"] == "discord_m1"
        assert messages[0]["metadata"]["has_thread"] is False
        assert await svc.get_unified_messages("w1", "slack_c1") == []
        svc.discord_service.get_channel_messages = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.get_unified_messages("w1", "discord_c1") == []

    async def test_unified_search_and_workflow(self):
        svc = self._svc()
        svc.discord_service = MagicMock()
        svc.discord_service.search_messages = AsyncMock(return_value={"ok": True, "results": []})
        results = await svc.unified_search("q", "w1", "c1")
        assert results == []
        results = await svc.unified_search("q", "w1", "discord_c1", {"limit": 10, "before": "b", "after": "a"})
        assert svc.discord_service.search_messages.called
        results = await svc.unified_search("q", "w1", "slack_c1")
        svc.discord_service.search_messages = AsyncMock(return_value={"ok": False})
        results = await svc.unified_search("q", "w1", "discord_c1")
        assert results == []
        svc.discord_service.search_messages = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.unified_search("q", "w1", "discord_c1") == []
        svc.atom_workflow.create_workflow = AsyncMock(return_value={"ok": True})
        result = await svc.create_unified_workflow({"name": "w"})
        assert result["ok"] is True
        svc.atom_workflow.create_workflow = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.create_unified_workflow({"name": "w"})
        assert result["ok"] is False
        svc.atom_workflow = None
        result = await svc.create_unified_workflow({"name": "w"})
        assert result["ok"] is False
        svc.atom_workflow = MagicMock()
        svc.atom_workflow.create_workflow = AsyncMock(return_value={"ok": True})
        result = await svc.create_unified_workflow({"name": "w"})
        assert result["ok"] is True

    async def test_get_unified_analytics(self):
        svc = self._svc()
        llm = MagicMock()
        llm.chat_completion = AsyncMock(return_value=json.dumps({"x": 1}))
        svc.llm_service = llm
        result = await svc.get_unified_analytics("orders", "30d", "w1")
        assert result["metric"] == "orders"
        llm.chat_completion = AsyncMock(return_value="text")
        result = await svc.get_unified_analytics("orders", "30d", "w1")
        assert result["metric"] == "orders"
        llm.chat_completion = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.get_unified_analytics("orders", "30d", "w1")
        assert result["metric"] == "orders"

    async def test_workers_and_setup(self):
        svc = self._svc()
        svc.discord_service = MagicMock()
        svc.atom_memory.query = AsyncMock(return_value=[])
        await svc._initialize_unified_data()
        svc.atom_memory.query = AsyncMock(side_effect=RuntimeError("x"))
        await svc._initialize_unified_data()
        import integrations.atom_discord_integration as mod
        ET = MagicMock()
        ET.MESSAGE_CREATE = "MESSAGE_CREATE"
        ET.GUILD_CREATE = "GUILD_CREATE"
        ET.VOICE_STATE_UPDATE = "VOICE_STATE_UPDATE"
        svc.discord_service.event_handlers = {
            "MESSAGE_CREATE": [], "GUILD_CREATE": [], "VOICE_STATE_UPDATE": [],
        }
        with patch.object(mod, "DiscordEventType", ET):
            await svc._setup_cross_platform_handlers()
        assert len(svc.discord_service.event_handlers["MESSAGE_CREATE"]) == 1
        await svc._start_integration_workers()
        await asyncio.sleep(0.01)
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await svc._discord_message_ingestion_worker()
            with pytest.raises(asyncio.CancelledError):
                await svc._discord_event_processing_worker()
            with pytest.raises(asyncio.CancelledError):
                await svc._unified_search_indexing_worker()

    async def test_converters(self):
        svc = self._svc()
        assert svc._convert_discord_message_type(0) == "default"
        assert svc._convert_discord_message_type(999) == "unknown"
        assert svc._convert_discord_reactions([{"emoji": {"name": "x"}, "count": 2, "me": True}])[0]["emoji"] == "x"
        assert svc._convert_discord_reactions([]) == []
        att = svc._convert_discord_attachments([{"id": 1, "filename": "f", "url": "u"}])
        assert att[0]["type"] == "discord_attachment"
        men = svc._convert_discord_mentions([{"id": 1, "username": "u"}])
        assert men[0]["platform"] == "Discord"
        emb = svc._convert_discord_embeds([{"title": "t"}])
        assert emb[0]["fields"] == []
        import integrations.atom_discord_integration as mod
        with patch.object(mod, "DiscordGuild", MagicMock()):
            assert svc._get_guild_by_id("g1") is not None
        assert svc._get_guild_by_id("g1") is None

    async def test_memory_search_workflow_helpers(self):
        svc = self._svc()
        await svc._store_message_in_memory({"message_id": "m1"}, "discord")
        assert svc.atom_memory.store.called
        svc.atom_memory.store = AsyncMock(side_effect=RuntimeError("x"))
        await svc._store_message_in_memory({"message_id": "m1"}, "discord")
        svc2 = self._svc()
        svc2.atom_memory = None
        await svc2._store_message_in_memory({"message_id": "m1"}, "discord")
        svc3 = self._svc()
        svc3.atom_search.index = AsyncMock()
        await svc3._index_message_in_search({"message_id": "m1"}, "discord")
        assert svc3.atom_search.index.called
        svc3.atom_search.index = AsyncMock(side_effect=RuntimeError("x"))
        await svc3._index_message_in_search({"message_id": "m1"}, "discord")
        svc4 = self._svc()
        svc4.atom_search = None
        await svc4._index_message_in_search({"message_id": "m1"}, "discord")
        svc5 = self._svc()
        svc5.atom_workflow.trigger_workflows = AsyncMock()
        await svc5._trigger_workflows({"a": 1}, "evt")
        svc5.atom_workflow.trigger_workflows = AsyncMock(side_effect=RuntimeError("x"))
        await svc5._trigger_workflows({"a": 1}, "evt")
        svc6 = self._svc()
        svc6.atom_workflow = None
        await svc6._trigger_workflows({"a": 1}, "evt")

    async def test_cross_platform_handlers(self):
        svc = self._svc()
        svc._store_message_in_memory = AsyncMock()
        svc._index_message_in_search = AsyncMock()
        svc._trigger_workflows = AsyncMock()
        svc._update_workspace_cross_platform = AsyncMock()
        svc._update_voice_state_cross_platform = AsyncMock()
        await svc._handle_discord_message_cross_platform({"a": 1})
        await svc._handle_discord_guild_event_cross_platform({"a": 1})
        await svc._handle_discord_voice_event_cross_platform({"a": 1})
        svc._store_message_in_memory = AsyncMock(side_effect=RuntimeError("x"))
        svc._index_message_in_search = AsyncMock(side_effect=RuntimeError("x"))
        svc._trigger_workflows = AsyncMock(side_effect=RuntimeError("x"))
        svc._update_workspace_cross_platform = AsyncMock(side_effect=RuntimeError("x"))
        svc._update_voice_state_cross_platform = AsyncMock(side_effect=RuntimeError("x"))
        await svc._handle_discord_message_cross_platform({"a": 1})
        await svc._handle_discord_guild_event_cross_platform({"a": 1})
        await svc._handle_discord_voice_event_cross_platform({"a": 1})

    async def test_workspace_sync(self):
        import integrations.atom_discord_integration as mod
        svc = self._svc(database=MagicMock())
        ws = MagicMock()
        ws.id = "uw1"
        svc.workspace_sync = MagicMock()
        svc.db = MagicMock()
        svc.db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(mod, "UnifiedWorkspace", MagicMock()):
            svc.workspace_sync.create_unified_workspace.return_value = ws
        svc.workspace_sync.create_unified_workspace.return_value = ws
        svc.workspace_sync.propagate_change = AsyncMock()
        await svc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G", "type": "GUILD_UPDATE"}, "discord")
        await svc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G", "type": "GUILD_MEMBER_ADD"}, "discord")
        await svc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G", "type": "GUILD_MEMBER_REMOVE"}, "discord")
        await svc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G", "type": "GUILD_ROLE_UPDATE"}, "discord")
        await svc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G", "type": "GUILD_CHANNEL_CREATE"}, "discord")
        await svc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G", "type": "GUILD_CHANNEL_DELETE"}, "discord")
        await svc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G", "type": "OTHER"}, "discord")
        # voice state
        uw = MagicMock()
        uw.voice_states = {}
        svc.db = MagicMock()
        svc.db.query.return_value.filter.return_value.first.return_value = uw
        with patch.object(mod, "UnifiedWorkspace", MagicMock()):
            await svc._update_voice_state_cross_platform({"user_id": "u1", "guild_id": "g1", "channel_id": "c1", "state": "joined"}, "discord")
        assert uw.voice_states
        svc.db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(mod, "UnifiedWorkspace", MagicMock()):
            await svc._update_voice_state_cross_platform({"user_id": "u1", "guild_id": "g1"}, "discord")
        await svc._check_voice_state_conflicts(uw, "u1", "discord", "joined")
        await svc._check_voice_state_conflicts(MagicMock(voice_states={"u1_discord": {"channel_id": "c1"}}), "u1", "discord", "joined")
        svc.workspace_sync = None
        await svc._update_workspace_cross_platform({"guild_id": "g1"}, "discord")
        await svc._update_voice_state_cross_platform({"guild_id": "g1"}, "discord")

    async def test_get_or_create_unified_workspace(self):
        import integrations.atom_discord_integration as mod
        svc = self._svc()
        svc.db = None
        svc.workspace_sync = MagicMock()
        assert await svc._get_or_create_unified_workspace("g1", "G") is None
        uw = MagicMock()
        uw.id = "uw1"
        svc.workspace_sync.create_unified_workspace.return_value = uw
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc.db = db
        with patch.object(mod, "UnifiedWorkspace", MagicMock()):
            result = await svc._get_or_create_unified_workspace("g1", "G")
            assert result.id == "uw1"
            db.query.return_value.filter.return_value.first.return_value = uw
            result = await svc._get_or_create_unified_workspace("g1", "G")
            assert result.id == "uw1"
            db.query.side_effect = RuntimeError("x")
            assert await svc._get_or_create_unified_workspace("g1", "G") is None


class TestDiscordGaps:
    def _svc(self):
        from integrations.atom_discord_integration import AtomDiscordIntegration
        return AtomDiscordIntegration({
            "atom_memory_service": MagicMock(), "atom_search_service": MagicMock(),
            "atom_workflow_service": MagicMock(), "atom_ingestion_pipeline": MagicMock()})

    async def test_voice_conflict_detection(self):
        svc = self._svc()
        uw = MagicMock()
        uw.voice_states = {
            "u1_discord": {"platform": "discord", "state": "joined", "channel_id": "c1"},
            "u1_slack": {"platform": "slack", "state": "joined", "channel_id": "c2"},
            "u1_teams": {"platform": "teams", "state": "left"},
            "u2_slack": {"platform": "slack", "state": "joined"},
        }
        uw.metadata = {}
        await svc._check_voice_state_conflicts(uw, "u1", "discord", "joined")
        assert uw.metadata["voice_conflicts"]
        await svc._check_voice_state_conflicts(uw, "u1", "discord", "left")  # inactive
        await svc._check_voice_state_conflicts(uw, "u1", "slack", "joined")  # no conflict
        uw.metadata = None
        with patch("integrations.atom_discord_integration.logger"):
            await svc._check_voice_state_conflicts(uw, "u1", "discord", "joined")

    async def test_worker_exception_branches(self):
        svc = self._svc()
        with patch("asyncio.sleep", side_effect=RuntimeError("x")):
            with patch("integrations.atom_discord_integration.logger"):
                with pytest.raises(RuntimeError):
                    await svc._discord_message_ingestion_worker()
                with pytest.raises(RuntimeError):
                    await svc._discord_event_processing_worker()
                with pytest.raises(RuntimeError):
                    await svc._unified_search_indexing_worker()

    async def test_search_indexing_worker_body(self):
        svc = self._svc()
        svc.atom_memory.query = AsyncMock(return_value=[{"id": "m1"}])
        svc._index_message_in_search = AsyncMock()
        svc.atom_memory.update = AsyncMock()
        with patch("asyncio.sleep", side_effect=RuntimeError("x")):
            with patch("integrations.atom_discord_integration.logger"):
                with pytest.raises(RuntimeError):
                    await svc._unified_search_indexing_worker()
        assert svc.atom_memory.update.called
        svc.atom_memory.query = AsyncMock(side_effect=RuntimeError("x"))
        with patch("asyncio.sleep", side_effect=RuntimeError("x")):
            with patch("integrations.atom_discord_integration.logger"):
                with pytest.raises(RuntimeError):
                    await svc._unified_search_indexing_worker()

    async def test_voice_state_full_path(self):
        import integrations.atom_discord_integration as mod
        svc = self._svc()
        uw = MagicMock()
        uw.voice_states = {}
        uw.metadata = {}
        svc.db = MagicMock()
        svc.db.query.return_value.filter.return_value.first.return_value = uw
        svc.workspace_sync = MagicMock()
        with patch.object(mod, "UnifiedWorkspace", MagicMock()):
            await svc._update_voice_state_cross_platform(
                {"user_id": "u1", "guild_id": "g1", "channel_id": "c1", "state": "joined"}, "discord")
        assert "u1_discord" in uw.voice_states
        await svc._check_voice_state_conflicts(uw, "u1", "discord", "joined")

    async def test_workspace_sync_init(self):
        from integrations.atom_discord_integration import AtomDiscordIntegration
        svc = AtomDiscordIntegration({"database": MagicMock()})
        assert svc.workspace_sync is not None

    async def test_workspace_update_except(self):
        import integrations.atom_discord_integration as mod
        svc = self._svc()
        svc.workspace_sync = MagicMock()
        svc.workspace_sync.create_unified_workspace.side_effect = RuntimeError("x")
        svc.db = MagicMock()
        svc.db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(mod, "UnifiedWorkspace", MagicMock()):
            with patch("integrations.atom_discord_integration.logger"):
                await svc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G"}, "discord")

    async def test_import_block(self):
        import integrations.atom_discord_integration as mod
        assert mod.UnifiedWorkspace is not None  # moved out of optional try

    async def test_channel_workspace_excepts(self):
        import integrations.atom_discord_integration as mod
        svc = self._svc()
        svc.discord_service = MagicMock()
        svc.discord_service.get_guilds = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.get_unified_workspaces("u1") == []
        svc.discord_service.get_guild_channels = AsyncMock(side_effect=RuntimeError("x"))
        from integrations.discord_enhanced_service import DiscordGuild as RealGuild
        with patch.object(mod, "DiscordGuild", RealGuild):
            assert await svc.get_unified_channels("discord_g1", "u1") == []


class TestDiscordGaps2:
    def _svc(self):
        from integrations.atom_discord_integration import AtomDiscordIntegration
        return AtomDiscordIntegration({
            "atom_memory_service": MagicMock(), "atom_search_service": MagicMock(),
            "atom_workflow_service": MagicMock(), "atom_ingestion_pipeline": MagicMock()})

    async def test_import_error_fallback_lines(self):
        import integrations.atom_discord_integration as mod
        assert mod.discord_enhanced_service is None
        assert mod.discord_analytics_engine is None
        assert mod.DiscordEventType is None

    async def test_create_workflow_discord_involved(self):
        svc = self._svc()
        svc.atom_workflow = MagicMock()
        svc.atom_workflow.create_workflow = AsyncMock(return_value={"ok": True})
        result = await svc.create_unified_workflow({
            "triggers": [{"platform": "discord"}], "actions": [{"platform": "slack"}],
            "name": "wf",
        })
        assert result["ok"] is True
        result = await svc.create_unified_workflow({
            "triggers": [{"platform": "slack", "event": "discord_event"}],
            "actions": [{"action": "discord_action"}],
        })
        assert result["ok"] is True

    async def test_analytics_with_discord_analytics(self):
        svc = self._svc()
        svc.discord_analytics = MagicMock()
        point = MagicMock()
        point.timestamp = datetime.now(timezone.utc)
        point.value = 1
        point.dimensions = {}
        point.metadata = {}
        svc.discord_analytics.get_analytics = AsyncMock(return_value=[point])
        result = await svc.get_unified_analytics("orders", "30d", "discord_w1")
        assert result["metric"] == "orders"
        assert result["total_points"] == 1
        svc.discord_analytics.get_analytics = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.get_unified_analytics("orders", "30d", "discord_w1")
        assert result["ok"] is False
        svc.discord_analytics = None
        result = await svc.get_unified_analytics("orders", "30d", "w1")
        assert result["total_points"] == 0

    async def test_workspace_update_and_voice_excepts(self):
        import integrations.atom_discord_integration as mod
        svc = self._svc()
        svc.workspace_sync = MagicMock()
        svc.workspace_sync.propagate_change = AsyncMock(side_effect=RuntimeError("x"))
        svc.db = MagicMock()
        svc.db.query.return_value.filter.return_value.first.return_value = MagicMock(id="uw")
        with patch.object(mod, "UnifiedWorkspace", MagicMock()):
            with patch("integrations.atom_discord_integration.logger"):
                await svc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G"}, "discord")
        uw = MagicMock()
        uw.voice_states = {}
        svc.db = MagicMock()
        svc.db.query.return_value.filter.return_value.first.return_value = uw
        vs = MagicMock()
        vs.__setitem__ = MagicMock(side_effect=RuntimeError("x"))
        uw.voice_states = vs
        with patch.object(mod, "UnifiedWorkspace", MagicMock()):
            with patch("integrations.atom_discord_integration.logger"):
                await svc._update_voice_state_cross_platform(
                    {"user_id": "u1", "guild_id": "g1", "channel_id": "c1", "state": "joined"}, "discord")
        # _update_voice_state_cross_platform outer except via broken workspace
        svc.db.query.return_value.filter.return_value.first.side_effect = RuntimeError("x")
        with patch.object(mod, "UnifiedWorkspace", MagicMock()):
            with patch("integrations.atom_discord_integration.logger"):
                await svc._update_voice_state_cross_platform({"guild_id": "g1"}, "discord")

    async def test_initialize_except_branch(self):
        import integrations.atom_discord_integration as mod
        svc = self._svc()
        svc.discord_service = MagicMock()
        with patch.object(svc, "_start_integration_workers", AsyncMock(side_effect=RuntimeError("x"))):
            with patch("integrations.atom_discord_integration.logger"):
                assert await svc.initialize() is False

    async def test_workspace_sync_init_failure(self):
        from integrations.atom_discord_integration import AtomDiscordIntegration
        import integrations.workspace_sync_service as wss
        with patch.object(wss, "WorkspaceSyncService", side_effect=RuntimeError("x")):
            svc = AtomDiscordIntegration({"database": MagicMock()})
        assert svc.workspace_sync is None


# ============================================================================
# google_chat_enhanced_service
# ============================================================================


class TestGoogleChat:
    def _svc(self, **kw):
        from integrations.google_chat_enhanced_service import GoogleChatEnhancedService
        cfg = {"client_id": "cid", "client_secret": "sec", "redirect_uri": "https://cb",
               "encryption_key": base64.urlsafe_b64encode(b"a" * 32).decode()}
        cfg.update(kw)
        return GoogleChatEnhancedService(tenant_id="t1", config=cfg)

    def _space(self, **kw):
        from integrations.google_chat_enhanced_service import GoogleChatSpace
        base = dict(
            space_id="spaces/AAA", name="Space", display_name="Space", type="SPACE",
            description="d", space_threading_state="THREADING_ENABLED", space_type="SPACE",
            space_uri="https://chat.google.com/space/1", space_permission_level="COLLABORATOR",
            space_admins=["u1"], created_at=datetime.now(timezone.utc),
            last_modified_at="2024-01-01", single_user_bot_dm=False, threaded=True,
            member_count=2, message_count=5, files_count=0, is_archived=False, is_active=True,
            external_user_permission="UNKNOWN", access_token="tok", refresh_token="rt",
            scopes=["s"], user_id="u1", tenant_id="t1", integration_data={},
        )
        base.update(kw)
        return GoogleChatSpace(**base)

    async def test_init_and_oauth_flow(self):
        svc = self._svc()
        assert svc.cipher is not None
        assert svc.oauth_flow is not None
        assert len(svc.required_scopes) == 9
        import integrations.google_chat_enhanced_service as mod
        with patch.object(mod.Flow, "from_client_config", side_effect=RuntimeError("x")):
            svc2 = self._svc(client_id=None)
        assert svc2.oauth_flow is None

    async def test_token_encryption(self):
        svc = self._svc()
        enc = svc._encrypt_token("secret")
        assert svc._decrypt_token(enc) == "secret"
        svc3 = self._svc(encryption_key=None)
        with pytest.raises(RuntimeError):
            svc3._encrypt_token("secret")
        assert svc3._decrypt_token("plain") == "plain"

    async def test_rate_limiter(self):
        from integrations.google_chat_enhanced_service import GoogleChatRateLimiter
        rl = GoogleChatRateLimiter()
        assert await rl.check_limit("s1", "messages_send") is True
        for _ in range(150):
            await rl.check_limit("s1", "messages_send")
        assert await rl.check_limit("s1", "messages_send") is False
        # unknown endpoint limit + reset window
        rl.local_limits["gc_rate:s2:x"] = {"count": 0, "reset": time.time() - 10}
        assert await rl.check_limit("s2", "x") is True
        # redis path
        redis = MagicMock()
        redis.get.return_value = "1000"
        rl2 = GoogleChatRateLimiter(redis)
        assert await rl2.check_limit("s1", "messages_send") is False
        redis.get.return_value = None
        rl3 = GoogleChatRateLimiter(redis)
        assert await rl3.check_limit("s1", "messages_send") is True
        assert redis.pipeline().incr.called

    async def test_user_space_get_save(self):
        svc = self._svc()
        svc.redis_client = MagicMock()
        space = self._space()
        assert svc._save_user_space(space) is True
        assert svc.connection_status["spaces/AAA"].value == "connected"
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = None
        svc2 = self._svc(database=db)
        assert svc2._get_user_space("u1") is None
        db.execute.side_effect = RuntimeError("x")
        assert svc2._get_user_space("u1") is None
        assert svc2._get_user_space_by_id("spaces/AAA") is None
        redis = MagicMock()
        redis.get.return_value = json.dumps(self._space().__dict__, default=str)
        svc3 = self._svc()
        svc3.redis_client = redis
        got = svc3._get_user_space("u1")
        assert got is not None

    async def test_get_chat_service(self):
        svc = self._svc()
        assert svc._get_chat_service("u1") is None  # no space
        svc.chat_services["u1"] = "cached"
        assert svc._get_chat_service("u1") == "cached"
        db = MagicMock()
        row = self._space()
        db.execute.return_value.fetchone.return_value = row.__dict__
        svc2 = self._svc(database=db)
        with patch("integrations.google_chat_enhanced_service.build") as build, \
             patch("integrations.google_chat_enhanced_service.Credentials") as creds:
            svc2._get_chat_service("u1")
            build.assert_called()
            creds.assert_called()
        svc3 = self._svc(database=MagicMock())
        svc3.db.execute.return_value.fetchone.return_value = row.__dict__
        with patch("integrations.google_chat_enhanced_service.build", side_effect=RuntimeError("x")), \
             patch("integrations.google_chat_enhanced_service.Credentials"):
            assert svc3._get_chat_service("u1") is None

    async def test_generate_oauth_url(self):
        svc = self._svc()
        url = svc.generate_oauth_url("state1", "u1")
        assert "accounts.google.com" in url
        url2 = svc.generate_oauth_url("state1", "u1", ["scope1"])
        assert url2
        svc.oauth_flow = None
        with pytest.raises(Exception):
            svc.generate_oauth_url("state1", "u1")

    async def test_exchange_code_for_tokens(self):
        svc = self._svc()
        creds = MagicMock()
        creds.token = "tok"
        creds.refresh_token = "rt"
        creds.scopes = ["s"]
        creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        svc.oauth_flow = MagicMock()
        svc.oauth_flow.credentials = creds
        userinfo = MagicMock()
        userinfo.userinfo.return_value.get.return_value.execute.return_value = {"id": "u1"}
        chat = MagicMock()
        chat.spaces.return_value.list.return_value.execute.return_value = {
            "spaces": [{
                "name": "spaces/AAA", "displayName": "S", "type": "SPACE",
                "spaceThreadingState": "THREADING_ENABLED", "spaceType": "SPACE",
                "spaceUri": "u", "spacePermissionLevel": "P", "createTime": "2024-01-01T00:00:00Z",
            }]}
        svc.redis_client = MagicMock()
        with patch("integrations.google_chat_enhanced_service.build") as build:
            build.side_effect = [userinfo, chat]
            result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is True
        assert len(result["spaces"]) == 1
        # no spaces
        chat.spaces.return_value.list.return_value.execute.return_value = {"spaces": []}
        with patch("integrations.google_chat_enhanced_service.build") as build:
            build.side_effect = [userinfo, chat]
            result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False
        # failure path
        svc.oauth_flow.fetch_token.side_effect = RuntimeError("x")
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False
        svc.oauth_flow = None
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False

    async def test_test_connection(self):
        svc = self._svc()
        result = await svc.test_connection("spaces/AAA")
        assert result["connected"] is False  # no space -> error
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = self._space().__dict__
        svc2 = self._svc(database=db)
        svc2.chat_services["u1"] = MagicMock()
        svc2.chat_services["u1"].spaces.return_value.get.return_value.execute.return_value = {
            "name": "spaces/AAA", "displayName": "S", "type": "SPACE",
            "spaceThreadingState": "THREADING_ENABLED"}
        result = await svc2.test_connection("spaces/AAA")
        assert result["connected"] is True
        svc2.chat_services["u1"].spaces.return_value.get.return_value.execute.return_value = None
        result = await svc2.test_connection("spaces/AAA")
        assert result["connected"] is False
        svc2.chat_services["u1"].spaces.return_value.get.return_value.execute.side_effect = RuntimeError("x")
        result = await svc2.test_connection("spaces/AAA")
        assert result["connected"] is False

    async def test_get_spaces(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [self._space().__dict__]
        svc = self._svc(database=db)
        spaces = await svc.get_spaces("u1")
        assert len(spaces) == 1
        spaces = await svc.get_spaces()
        assert len(spaces) == 1
        db.execute.side_effect = RuntimeError("x")
        assert await svc.get_spaces() == []
        redis = MagicMock()
        redis.keys.return_value = ["gc_space_user:u1"]
        redis.get.return_value = json.dumps(self._space().__dict__, default=str)
        svc2 = self._svc()
        svc2.redis_client = redis
        spaces = await svc2.get_spaces("u1")
        assert len(spaces) == 1
        redis.keys.return_value = []
        assert await svc2.get_spaces() == []


class TestGoogleChatMessages:
    def _svc(self):
        from integrations.google_chat_enhanced_service import GoogleChatEnhancedService
        cfg = {"client_id": "cid", "client_secret": "sec", "redirect_uri": "https://cb",
               "encryption_key": base64.urlsafe_b64encode(b"a" * 32).decode()}
        svc = GoogleChatEnhancedService(tenant_id="t1", config=cfg)
        db = MagicMock()
        row = TestGoogleChat()._space()
        db.execute.return_value.fetchone.return_value = row.__dict__
        svc.db = db
        return svc

    def _chat(self, svc):
        chat = MagicMock()
        msg = MagicMock()
        msg.execute.return_value = {
            "name": "spaces/AAA/messages/1", "text": "hi", "createTime": "2024-01-01T00:00:00Z",
            "thread": {"name": "spaces/AAA/threads/1"}, "sender": {"name": "users/u1", "displayName": "U"},
        }
        chat.spaces.return_value.messages.return_value.create.return_value = msg
        chat.spaces.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{
                "name": "spaces/AAA/messages/1", "text": "hi", "formattedText": "hi",
                "createTime": "2024-01-01T00:00:00Z", "lastModifiedTime": "2024-01-02T00:00:00Z",
                "sender": {"name": "users/u1", "displayName": "U", "email": "e@e.com"},
                "thread": {"name": "spaces/AAA/threads/1"},
            }],
            "nextPageToken": "tok",
        }
        return chat

    async def test_send_message(self):
        svc = self._svc()
        chat = self._chat(svc)
        svc.chat_services["u1"] = chat
        result = await svc.send_message("spaces/AAA", "hello")
        assert result["ok"] is True
        assert result["message_id"] == "spaces/AAA/messages/1"
        result = await svc.send_message("spaces/AAA", "hello", thread_id="t1", message_format="MARKDOWN")
        assert result["ok"] is True
        chat.spaces.return_value.messages.return_value.create.return_value.execute.return_value = None
        result = await svc.send_message("spaces/AAA", "hello")
        assert result["ok"] is False
        chat.spaces.return_value.messages.return_value.create.return_value.execute.side_effect = RuntimeError("x")
        result = await svc.send_message("spaces/AAA", "hello")
        assert result["ok"] is False
        # rate limited
        from integrations.google_chat_enhanced_service import GoogleChatRateLimiter
        svc.rate_limiter = GoogleChatRateLimiter()
        for _ in range(110):
            await svc.rate_limiter.check_limit("spaces/AAA", "messages_send")
        result = await svc.send_message("spaces/AAA", "hello")
        assert result["ok"] is False

    async def test_get_space_messages(self):
        svc = self._svc()
        chat = self._chat(svc)
        svc.chat_services["u1"] = chat
        messages = await svc.get_space_messages("spaces/AAA", limit=5)
        assert len(messages) == 1
        assert messages[0].text == "hi"
        chat.spaces.return_value.messages.return_value.list.return_value.execute.return_value = None
        assert await svc.get_space_messages("spaces/AAA") == []
        chat.spaces.return_value.messages.return_value.list.return_value.execute.side_effect = RuntimeError("x")
        assert await svc.get_space_messages("spaces/AAA") == []
        # cached fallback
        redis = MagicMock()
        svc.redis_client = redis
        redis.get.return_value = json.dumps([messages[0].__dict__], default=str)
        cached = await svc.get_space_messages("spaces/AAA")
        assert len(cached) == 1
        chat.spaces.return_value.messages.return_value.list.return_value.execute.side_effect = None
        chat.spaces.return_value.messages.return_value.list.return_value.execute.return_value = {"messages": []}
        assert await svc.get_space_messages("spaces/AAA") == []
        # rate limit
        from integrations.google_chat_enhanced_service import GoogleChatRateLimiter
        svc.rate_limiter = GoogleChatRateLimiter()
        for _ in range(1005):
            await svc.rate_limiter.check_limit("spaces/AAA", "messages_list")
        redis.get.return_value = None
        assert await svc.get_space_messages("spaces/AAA") == []

    async def test_search_messages(self):
        svc = self._svc()
        chat = self._chat(svc)
        svc.chat_services["u1"] = chat
        result = await svc.search_messages("spaces/AAA", "hi")
        assert result["ok"] is True
        assert result["total"] == 1
        chat.spaces.return_value.messages.return_value.list.return_value.execute.return_value = None
        result = await svc.search_messages("spaces/AAA", "hi")
        assert result["ok"] is True and result["total"] == 0
        chat.spaces.return_value.messages.return_value.list.return_value.execute.side_effect = RuntimeError("x")
        result = await svc.search_messages("spaces/AAA", "hi")
        assert result["ok"] is False

    async def test_service_info_capabilities_health(self):
        svc = self._svc()
        info = await svc.get_service_info()
        assert info["name"] == "Google Chat Enhanced Service"
        caps = svc.get_capabilities()
        assert len(caps["operations"]) == 3
        h = svc.health_check()
        assert h["healthy"] is True
        svc2 = TestGoogleChat()._svc(client_id=None, client_secret=None)
        h2 = svc2.health_check()
        assert h2["healthy"] is False

    async def test_execute_operation(self):
        svc = self._svc()
        svc.send_message = AsyncMock(return_value={"ok": True})
        result = await svc.execute_operation("send_message", {"space_id": "s", "text": "hi"})
        assert result["success"] is True
        svc.get_space_messages = AsyncMock(return_value=[])
        result = await svc.execute_operation("get_space_messages", {"space_id": "s"})
        assert result["success"] is True
        svc.search_messages = AsyncMock(return_value={"ok": True})
        result = await svc.execute_operation("search_messages", {"space_id": "s", "query": "q"})
        assert result["success"] is True
        result = await svc.execute_operation("bogus", {})
        assert result["success"] is False
        result = await svc.execute_operation("send_message", {"space_id": "s", "text": "hi"}, context={"tenant_id": "other"})
        assert result["success"] is False
        svc.send_message = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.execute_operation("send_message", {"space_id": "s", "text": "hi"})
        assert result["success"] is False

    async def test_close(self):
        svc = self._svc()
        redis = MagicMock()
        svc.redis_client = redis
        svc.chat_services["u1"] = MagicMock()
        await svc.close()
        assert svc.chat_services == {}
        assert redis.close.called

    async def test_get_user_space_by_id_redis(self):
        from integrations.google_chat_enhanced_service import GoogleChatEnhancedService
        cfg = {"client_id": "cid", "client_secret": "sec", "redirect_uri": "https://cb",
               "encryption_key": base64.urlsafe_b64encode(b"a" * 32).decode()}
        svc = GoogleChatEnhancedService(tenant_id="t1", config=cfg)
        redis = MagicMock()
        redis.get.return_value = json.dumps(TestGoogleChat()._space().__dict__, default=str)
        svc.redis_client = redis
        got = svc._get_user_space_by_id("spaces/AAA")
        assert got is not None
        redis.get.return_value = None
        assert svc._get_user_space_by_id("spaces/AAA") is None
        redis.get.side_effect = RuntimeError("x")
        assert svc._get_user_space_by_id("spaces/AAA") is None

    async def test_get_spaces_redis_filter(self):
        from integrations.google_chat_enhanced_service import GoogleChatEnhancedService
        cfg = {"client_id": "cid", "client_secret": "sec", "redirect_uri": "https://cb",
               "encryption_key": base64.urlsafe_b64encode(b"a" * 32).decode()}
        svc = GoogleChatEnhancedService(tenant_id="t1", config=cfg)
        redis = MagicMock()
        redis.keys.return_value = ["gc_space_user:u1", "gc_space_user:u2"]
        redis.get.return_value = json.dumps(TestGoogleChat()._space().__dict__, default=str)
        svc.redis_client = redis
        spaces = await svc.get_spaces("u1")
        assert len(spaces) == 2
        spaces = await svc.get_spaces()
        assert len(spaces) == 2
        redis.get.return_value = None
        assert await svc.get_spaces() == []
        redis.keys.side_effect = RuntimeError("x")
        assert await svc.get_spaces() == []

    async def test_dataclasses_post_init(self):
        import integrations.google_chat_enhanced_service as mod
        space = mod.GoogleChatSpace(
            space_id="s", name="N", display_name="N", type="T", description="d",
            space_threading_state="T", space_type="S", space_uri="u", space_permission_level="P",
            space_admins=[], created_at=datetime.now(timezone.utc), last_modified_at="t",
            single_user_bot_dm=False, threaded=False, member_count=0, message_count=0,
            files_count=0, is_archived=False, is_active=True, external_user_permission="U",
            access_token="t", refresh_token="r", scopes=[], user_id="u", tenant_id="t",
            integration_data={})
        assert space.created_at.tzinfo is not None
        space2 = mod.GoogleChatSpace(
            space_id="s2", name="N", display_name="N", type="T", description="d",
            space_threading_state="T", space_type="S", space_uri="u", space_permission_level="P",
            space_admins=None, created_at=None, last_modified_at="t",
            single_user_bot_dm=False, threaded=False, member_count=0, message_count=0,
            files_count=0, is_archived=False, is_active=True, external_user_permission="U",
            access_token="t", refresh_token="r", scopes=None, user_id="u", tenant_id="t",
            integration_data=None)
        assert space2.created_at is not None
        assert space2.scopes == []
        msg = mod.GoogleChatMessage(
            message_id="m", text="t", formatted_text="t", user_id="u", user_name="N",
            user_email="e", space_id="s", thread_id=None, timestamp="t",
            created_at=datetime.now(timezone.utc), message_type="MESSAGE", card_v2=[],
            annotations=[], attachment=[], sender_type="HUMAN", integration_data={},
        )
        assert msg.created_at.tzinfo is not None
        msg2 = mod.GoogleChatMessage(
            message_id="m2", text="t", formatted_text="t", user_id="u", user_name="N",
            user_email="e", space_id="s", thread_id=None, timestamp="t",
            created_at=None, message_type="MESSAGE", card_v2=None,
            annotations=None, attachment=None, sender_type="HUMAN", integration_data=None,
        )
        assert msg2.created_at is not None
        f = mod.GoogleChatFile(file_id="f", name="n", display_name="n", mime_type="m",
                               file_type="t", size=1, user_id="u", user_name="U",
                               user_email="e", space_id="s", timestamp="t",
                               created_at=datetime.now(timezone.utc), integration_data={})
        assert f.created_at is not None
        f2 = mod.GoogleChatFile(file_id="f2", name="n", display_name="n", mime_type="m",
                                file_type="t", size=1, user_id="u", user_name="U",
                                user_email="e", space_id="s", timestamp="t",
                                created_at=None, integration_data=None)
        assert f2.created_at is not None
