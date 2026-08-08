"""
Bug-hunt tests for comms integration services (R84 wave).

TDD RED->GREEN for real bugs found while reading:
  integrations/slack_enhanced_service.py
  integrations/slack_analytics_engine.py
  integrations/discord_enhanced_service.py
  integrations/discord_analytics_engine.py
  integrations/google_chat_analytics_engine.py
  integrations/teams_enhanced_service.py
  integrations/chat_orchestrator.py
"""
import asyncio
import importlib
import inspect
import json
import subprocess
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.slack_enhanced_service import (
    SlackEnhancedService,
    SlackWorkspace,
    SlackMessage,
)
from integrations.discord_enhanced_service import (
    DiscordEnhancedService,
    DiscordMessage,
    DiscordGuild,
    DiscordChannelType,
)
from integrations.slack_analytics_engine import SlackAnalyticsEngine
from integrations.discord_analytics_engine import (
    DiscordAnalyticsEngine,
    DiscordAnalyticsMetric,
    DiscordAnalyticsTimeRange,
    DiscordAnalyticsGranularity,
)
from integrations.google_chat_analytics_engine import (
    GoogleChatAnalyticsEngine,
    GoogleChatAnalyticsMetric,
    GoogleChatAnalyticsTimeRange,
    GoogleChatAnalyticsGranularity,
)
from integrations import chat_orchestrator as co

BACKEND = "/Users/rushiparikh/projects/atom/backend"


def _teams_module():
    """Lazily import teams_enhanced_service (module was unimportable before fix)."""
    return importlib.import_module("integrations.teams_enhanced_service")


# ============================================================================
# slack_enhanced_service
# ============================================================================

class TestSlackFullSync:
    """B1: full_sync passes 2 positional args to 1-arg sync_to_postgres_cache."""

    async def test_full_sync_calls_postgres_cache_with_single_arg(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        with patch.object(svc, "sync_to_postgres_cache", new=AsyncMock(return_value={"success": True, "metrics_synced": 3})) as sync:
            result = await svc.full_sync("T1", "T1")
            assert sync.call_count == 1
            args = sync.call_args[0]
            assert args == ("T1",), f"expected single (workspace_id,) arg, got {args}"
            assert result["postgres_cache"] == {"success": True, "metrics_synced": 3}


class TestSlackDuplicateMethods:
    """B2: duplicate get_capabilities/health_check definitions (merge residue)."""

    def test_no_duplicate_health_check_definition(self):
        source = inspect.getsource(SlackEnhancedService)
        assert source.count("def health_check") == 1
        assert source.count("def get_capabilities") == 1


class TestSlackBotTokenBinding:
    """B3: exchange_code_for_tokens binds bot_token to the bot USER ID."""

    async def test_exchange_code_binds_bot_token_and_bot_id(self):
        svc = SlackEnhancedService(tenant_id="default", config={})

        async def fake_post(url, data=None, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.text = "{}"
            resp.json = lambda: {
                "ok": True,
                "team": {"id": "T1", "name": "Test", "domain": "test"},
                "enterprise": {},
                "authed_user": {"id": "U1"},
                "access_token": "xoxb-real-bot-token",
                "bot_user_id": "B123",
                "scope": "channels:read,chat:write",
            }
            return resp

        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(side_effect=fake_post))
            )
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch.object(svc, "_save_workspace", return_value=True) as save:
                result = await svc.exchange_code_for_tokens("code", "state")
                assert result["ok"] is True
                workspace = save.call_args[0][0]
                # bot_token must be the actual bot token, not the bot user id
                assert workspace.bot_token == "xoxb-real-bot-token"
                assert workspace.bot_id == "B123"


# ============================================================================
# slack_analytics_engine
# ============================================================================

class TestSlackAnalyticsImportOrder:
    """B11: module must import when VADER is present but TextBlob is missing."""

    def test_import_with_partial_optional_deps(self):
        code = (
            "import sys\n"
            "import types\n"
            "mod = types.ModuleType('vaderSentiment')\n"
            "sa = types.ModuleType('vaderSentiment.vaderSentiment')\n"
            "sa.SentimentIntensityAnalyzer = lambda: None\n"
            "sys.modules['vaderSentiment'] = mod\n"
            "sys.modules['vaderSentiment.vaderSentiment'] = sa\n"
            "try:\n"
            "    import textblob\n"
            "except ImportError:\n"
            "    pass\n"
            "import integrations.slack_analytics_engine as m\n"
            "print('IMPORT_OK')\n"
        )
        # Ensure textblob is not importable: run in subprocess with a poisoned import
        env_code = code.replace(
            "import textblob\n", "raise ImportError('textblob blocked')\n"
        )
        # Simpler: patch builtins to fail textblob import
        full = (
            "import sys, types\n"
            "import builtins\n"
            "_orig_import = builtins.__import__\n"
            "def _blocked(name, *a, **k):\n"
            "    if name == 'textblob' or name.startswith('textblob.'):\n"
            "        raise ImportError('blocked')\n"
            "    return _orig_import(name, *a, **k)\n"
            "builtins.__import__ = _blocked\n"
            "mod = types.ModuleType('vaderSentiment')\n"
            "sa = types.ModuleType('vaderSentiment.vaderSentiment')\n"
            "sa.SentimentIntensityAnalyzer = lambda: None\n"
            "sys.modules['vaderSentiment'] = mod\n"
            "sys.modules['vaderSentiment.vaderSentiment'] = sa\n"
            "import integrations.slack_analytics_engine as m\n"
            "print('IMPORT_OK')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", full],
            cwd=BACKEND,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": BACKEND, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        assert "IMPORT_OK" in proc.stdout, f"import failed: {proc.stderr[-2000:]}"


# ============================================================================
# discord_enhanced_service
# ============================================================================

class TestDiscordMessageConstruction:
    """B4: DiscordMessage.__post_init__ referenced missing self.author."""

    def test_discord_message_constructs(self):
        msg = DiscordMessage(
            message_id="1",
            content="hello",
            channel_id="c1",
            guild_id="g1",
            guild_name="Guild",
            user_id="u1",
            user_name="User",
            user_discriminator="0001",
            timestamp="2026-01-01T00:00:00Z",
            member={"user": {"bot": True}},
        )
        assert msg.message_id == "1"

    async def test_get_channel_messages_returns_messages(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        client = MagicMock()
        msg = MagicMock()
        msg.id = "m1"
        msg.content = "hi"
        msg.channel_id = "c1"
        msg.timestamp = "2026-01-01T00:00:00Z"
        msg.author = {"id": "u1", "username": "n", "discriminator": "0000", "bot": False}
        msg.member = {}
        msg.attachments = []
        msg.embeds = []
        msg.reactions = []
        msg.components = []
        msg.message_snapshots = []
        msg.stickers = []
        msg.edited_timestamp = None
        msg.mention_everyone = False
        msg.mentions = []
        msg.mention_roles = []
        msg.mention_channels = []
        msg.pinned = False
        msg.webhook_id = None
        msg.type = 0
        msg.referenced_message = None
        msg.interaction = None
        msg.application_id = None
        msg.activity = None
        msg.application = None
        msg.flags = 0
        msg.message_data = {}
        msg.get = lambda key, default=None: getattr(msg, key, default)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [msg.__dict__]
        client.get = AsyncMock(return_value=resp)
        svc.session = client
        with patch.object(svc, "_get_guild_by_id", return_value=DiscordGuild(
            guild_id="g1", name="G", owner_id="o", owner_name="o"
        )):
            messages = await svc.get_channel_messages("g1", "c1")
            assert len(messages) == 1
            assert messages[0].user_id == "u1"


class TestDiscordGuildPermissions:
    """B5: exchange_code_for_tokens passed permissions= kwarg DiscordGuild lacked."""

    def test_discord_guild_accepts_permissions(self):
        guild = DiscordGuild(
            guild_id="1", name="n", owner_id="o", owner_name="o",
            permissions="0x00000008",
        )
        assert guild.permissions == "0x00000008"


class TestDiscordExecuteOperation:
    """B6: execute_operation('send_message') returned a placeholder success."""

    async def test_execute_operation_send_message_delegates(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        with patch.object(svc, "send_message", new=AsyncMock(return_value={"ok": True, "message_id": "m1"})) as send:
            result = await svc.execute_operation(
                "send_message",
                {"guild_id": "g1", "channel_id": "c1", "content": "hi"},
            )
            send.assert_awaited_once_with(
                guild_id="g1", channel_id="c1", content="hi",
                embed=None, components=None, tts=False,
            )
            assert result["success"] is True


# ============================================================================
# discord_analytics_engine / google_chat_analytics_engine
# ============================================================================

class TestLLMKwargNames:
    """B12: engines pass system_prompt= to generate_structured (real kwarg is
    system_instruction) — LLM path always fell back before the fix."""

    def _signature_checking_llm(self, result):
        llm = MagicMock()
        llm.generate_structured = AsyncMock()

        async def _fake(prompt, response_model, **kwargs):
            assert "system_prompt" not in kwargs, "invalid kwarg system_prompt passed"
            assert "system_instruction" in kwargs, "expected system_instruction kwarg"
            return result

        llm.generate_structured.side_effect = _fake
        return llm

    async def test_discord_sentiment_uses_system_instruction(self):
        from integrations.discord_analytics_engine import LLMSentiment

        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        llm = self._signature_checking_llm(
            LLMSentiment(score=0.5, label="positive", confidence=0.9)
        )
        with patch("integrations.discord_analytics_engine.get_llm_service", return_value=llm):
            result = await engine._analyze_sentiment("This is a wonderful positive message here")
        assert result["score"] == 0.5

    async def test_google_sentiment_uses_system_instruction(self):
        from integrations.google_chat_analytics_engine import LLMSentiment

        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        llm = self._signature_checking_llm(
            LLMSentiment(score=-0.5, label="negative", confidence=0.8)
        )
        with patch("integrations.google_chat_analytics_engine.get_llm_service", return_value=llm):
            result = await engine._analyze_sentiment("This is a terrible horrible message here")
        assert result["score"] == -0.5

    async def test_google_topics_uses_system_instruction(self):
        from integrations.google_chat_analytics_engine import LLMTopics

        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        llm = self._signature_checking_llm(
            LLMTopics(topics=["pricing", "launch"], confidence=0.7)
        )
        with patch("integrations.google_chat_analytics_engine.get_llm_service", return_value=llm):
            result = await engine._extract_topics(["talk about pricing and launch plans"])
        assert result["topics"] == ["pricing", "launch"]


# ============================================================================
# teams_enhanced_service
# ============================================================================

class TestTeamsModuleImport:
    """B7: module imported phantom packages (msal, azure.mgmt.teams, azure.graph)."""

    def test_module_imports_cleanly(self):
        mod = _teams_module()
        assert hasattr(mod, "TeamsEnhancedService")


class TestTeamsMessageDataclass:
    """B7b: TeamsMessage dataclass had a default field before required fields."""

    def test_teams_message_constructs(self):
        mod = _teams_module()
        msg = mod.TeamsMessage(
            message_id="1",
            text="hi",
            user_id="u1",
            user_name="n",
            user_email="e",
            channel_id="c1",
            workspace_id="w1",
            tenant_id="t1",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert msg.text == "hi"


class TestTeamsGetChannelMessages:
    """B10: TeamsMessage constructed without required workspace_id."""

    async def test_get_channel_messages_builds_messages(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        client = MagicMock()
        msg = MagicMock()
        msg.id = "m1"
        msg.body.content = "hi"
        msg.created_datetime = "2026-01-01T00:00:00Z"
        msg.last_modified_datetime = None
        msg.reply_to_id = None
        msg.message_type = "message"
        msg.importance = "normal"
        msg.subject = None
        msg.summary = None
        msg.attachments = []
        msg.mentions = []
        msg.localized = {}
        msg.etag = None
        msg.channel_identity = {}
        msg.additional_data = {}
        frm = MagicMock()
        frm.additional_data = {"user": {"id": "u1", "displayName": "n", "emailAddress": "e"}}
        setattr(msg, "from", frm)
        client.teams["w1"].channels["c1"].messages.get = AsyncMock(
            return_value=MagicMock(value=[msg])
        )
        svc._get_graph_client = MagicMock(return_value=client)
        messages = await svc.get_channel_messages("w1", "c1")
        assert len(messages) == 1
        assert messages[0].user_id == "u1"

    async def test_search_messages_builds_messages(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        client = MagicMock()
        client._default_headers = {"Authorization": "Bearer tok"}
        svc._get_graph_client = MagicMock(return_value=client)
        hit = {
            "resource": {
                "id": "m1",
                "body": {"content": "hi"},
                "from": {"id": "u1", "displayName": "n", "emailAddress": "e"},
                "channelIdentity": {"channelId": "c1"},
                "createdDateTime": "2026-01-01T00:00:00Z",
                "lastModifiedDateTime": None,
                "replyToId": None,
                "messageType": "message",
                "importance": "normal",
                "subject": None,
                "summary": None,
                "attachments": [],
                "mentions": [],
                "files": [],
                "etag": None,
                "participantCount": 2,
            },
            "score": 0.9,
        }
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "value": [{"hitsContainers": [{"hits": [hit], "total": 1}]}]
        }

        async def fake_post(url, headers=None, json=None):
            return resp

        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(side_effect=fake_post)))
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.search_messages("w1", "hello")
        assert result["ok"] is True
        assert len(result["messages"]) == 1
        assert result["messages"][0].workspace_id == "w1"


class TestTeamsFilterCombination:
    """B9: passing both latest and oldest dropped the latest filter."""

    async def test_get_channel_messages_keeps_both_filters(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        client = MagicMock()
        client.teams["w1"].channels["c1"].messages.get = AsyncMock(
            return_value=MagicMock(value=[])
        )
        svc._get_graph_client = MagicMock(return_value=client)
        await svc.get_channel_messages("w1", "c1", latest="L", oldest="O")
        kwargs = client.teams["w1"].channels["c1"].messages.get.call_args[1]
        flt = kwargs.get("$filter", "")
        assert "createdDateTime lt L" in flt, f"latest filter missing: {flt}"
        assert "createdDateTime gt O" in flt, f"oldest filter missing: {flt}"


# ============================================================================
# chat_orchestrator
# ============================================================================

class TestFinanceHandler:
    """B13: _handle_finance_request referenced unimported accounting classes."""

    async def test_finance_handler_runs_check_overdue(self):
        settings = MagicMock()
        settings.is_accounting_enabled.return_value = True
        assistant = MagicMock()
        assistant.process_query = AsyncMock(
            return_value={"intent": "check_overdue", "answer": "base answer"}
        )
        collection = MagicMock()
        collection.check_overdue_invoices = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch.object(co, "get_automation_settings", return_value=settings), \
             patch.object(co, "AccountingAssistant", return_value=assistant), \
             patch.object(co, "CollectionAgent", return_value=collection), \
             patch.object(co, "SessionLocal", return_value=db):
            orchestrator = co.ChatOrchestrator()
            orchestrator.ai_engines = {}
            result = await orchestrator._handle_finance_request(
                "check overdue invoices", {}, {"id": "s1"}, {"workspace_id": "w1"}
            )
        assert result["success"] is True
        assert "overdue invoices" in result["message"]

    async def test_finance_handler_runs_aging(self):
        settings = MagicMock()
        settings.is_accounting_enabled.return_value = True
        assistant = MagicMock()
        assistant.process_query = AsyncMock(return_value={"intent": "get_aging", "answer": "a"})
        collection = MagicMock()
        collection.generate_aging_report.return_value = {"aging": []}
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch.object(co, "get_automation_settings", return_value=settings), \
             patch.object(co, "AccountingAssistant", return_value=assistant), \
             patch.object(co, "CollectionAgent", return_value=collection), \
             patch.object(co, "SessionLocal", return_value=db):
            orchestrator = co.ChatOrchestrator()
            orchestrator.ai_engines = {}
            result = await orchestrator._handle_finance_request(
                "aging report", {}, {"id": "s1"}, {"workspace_id": "w1"}
            )
        assert result["success"] is True
        assert "aging" in result["message"]

    async def test_finance_handler_disabled_settings(self):
        settings = MagicMock()
        settings.is_accounting_enabled.return_value = False
        with patch.object(co, "get_automation_settings", return_value=settings):
            orchestrator = co.ChatOrchestrator()
            result = await orchestrator._handle_finance_request(
                "payroll", {}, {"id": "s1"}, {"workspace_id": "w1"}
            )
        assert result["success"] is False
        assert "disabled" in result["message"]


class TestCRMHandler:
    """B14: _handle_crm_request crashed when get_automation_settings is None."""

    async def test_crm_handler_with_none_settings(self):
        orchestrator = co.ChatOrchestrator()
        with patch.object(co, "get_automation_settings", None):
            result = await orchestrator._handle_crm_request(
                "show pipeline", {}, {"id": "s1"}, {"workspace_id": "w1"}
            )
        assert result["success"] is False
        assert "disabled" in result["message"]
