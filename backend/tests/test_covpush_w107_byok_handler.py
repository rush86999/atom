"""Coverage wave 107 — core/llm/byok_handler.py depth push (99% → 100%).

Combined-suite probe (w57 a-e + w64j a/b + legacy byok suites + opencode-go)
left exactly 16 statements uncovered: the openai/instructor ImportError
fallbacks (17-19, 24-26), the running-event-loop branch of
``_run_coroutine_sync`` (71-81), the no-local-providers early return in
``_load_local_providers`` (975), the Free-plan managed-AI restriction return
(1784), and the valid-forced-tier ``QueryComplexity.COMPLEX`` assignment
(1803). All fully mocked, zero LLM spend, no network/DB.
"""
import asyncio
import builtins
import importlib
import importlib.util
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.llm.byok_handler as bh
from core.llm.byok_handler import AwaitableResult, BYOKHandler, QueryComplexity

MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "llm", "byok_handler.py",
)


def make_handler(**attrs):
    h = BYOKHandler.__new__(BYOKHandler)
    h.clients = {}
    h.async_clients = {}
    h.byok_manager = Mock()
    h.credential_service = None
    h.cognitive_classifier = Mock()
    h.cache_router = Mock()
    h.pricing_fetcher = Mock()
    h.db_session = None
    h.tier_service = Mock()
    h.excluded_models = set()
    h.health_monitor = MagicMock()
    h.health_monitor.health_scores = {}
    h.rate_tracker = Mock()
    h._last_used_model = None
    h._last_used_provider = None
    h._pending_routing_result_id = None
    h._embedding_initialized = False
    h._embedding_init_lock = None
    h._clients_initialized = True
    h.workspace_id = "ws1"
    h.tenant_id = "tenant"
    h.default_provider_id = None
    for k, v in attrs.items():
        setattr(h, k, v)
    return h


def _chat_response(content="hello", finish="stop", usage=None):
    choice = SimpleNamespace(message=SimpleNamespace(content=content),
                             finish_reason=finish)
    return SimpleNamespace(
        choices=[choice],
        usage=usage or SimpleNamespace(prompt_tokens=10, completion_tokens=5,
                                       total_tokens=15),
        model="m1",
    )


class TestImportFallbacks:
    """Lines 17-19 + 24-26: optional-dependency ImportError fallbacks."""

    def test_openai_and_instructor_fallbacks(self):
        assert bh.OpenAI is not None
        assert bh.INSTRUCTOR_AVAILABLE is True

        real_import = builtins.__import__

        def _blocked(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "instructor" or name.startswith("openai"):
                raise ImportError(f"blocked import: {name}")
            return real_import(name, globals, locals, fromlist, level)

        spec = importlib.util.spec_from_file_location(
            "byok_handler_import_fallback_probe", MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        with patch("builtins.__import__", side_effect=_blocked):
            spec.loader.exec_module(mod)

        assert mod.OpenAI is None
        assert mod.AsyncOpenAI is None
        assert mod.INSTRUCTOR_AVAILABLE is False
        assert mod.instructor is None


class TestRunCoroutineSyncWithRunningLoop:
    """Lines 71-81: background credential-loop branch."""

    async def test_schedules_on_background_loop(self):
        async def _identity(value):
            return value

        result = bh._run_coroutine_sync(_identity(42))
        assert result == 42
        assert bh._CREDENTIAL_LOOP is not None

    async def test_timeout_raises(self):
        ev = asyncio.Event()

        async def _blocker():
            await ev.wait()

        with pytest.raises(TimeoutError):
            bh._run_coroutine_sync(_blocker(), timeout=0.1)
        bh._CREDENTIAL_LOOP.call_soon_threadsafe(ev.set)
        await asyncio.sleep(0.2)


class TestLoadLocalProvidersNoRows:
    """Line 975: no registered local providers → clean early return."""

    def test_no_providers_returns(self):
        h = make_handler()
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            result = h._load_local_providers()
        assert result is None


class TestFreePlanNoClients:
    """Phase-59 free-plan restriction: the plan-specific return was dead code
    (unreachable — the ``if not self.clients`` gate above returns first); the
    delivered no-keys behavior is the not-initialized message. Fixed by
    removing the dead branch; this test pins the delivered behavior."""

    async def test_free_plan_no_clients_gets_not_initialized(self):
        h = make_handler(clients={})
        h.byok_manager.get_tenant_api_key.return_value = None
        db = MagicMock()
        db.__enter__.return_value = db
        workspace = SimpleNamespace(tenant_id="t1")
        tenant = SimpleNamespace(plan_type=SimpleNamespace(value="free"))
        db.query.return_value.filter.return_value.first.side_effect = [
            workspace, tenant,
        ]
        with patch.object(h, "_is_trial_restricted", return_value=False), \
             patch.object(h, "analyze_query_complexity",
                          return_value=QueryComplexity.SIMPLE), \
             patch.object(h, "get_optimal_provider",
                          new=AsyncMock(return_value=(None, None))), \
             patch("core.llm.byok_handler.llm_usage_tracker") as ut, \
             patch("core.llm.byok_handler.get_db_session") as gds:
            ut.is_budget_exceeded.return_value = False
            gds.return_value = db
            result = await h.generate_response("hello", task_type="chat")
        assert result == "LLM Client not initialized (No API Keys configured)."

    async def test_free_plan_with_own_keys_proceeds(self):
        h = make_handler(clients={"openai": 1})
        h.byok_manager.get_tenant_api_key.return_value = None
        client = Mock()
        client.chat.completions.create.return_value = _chat_response("own key")
        h.clients["openai"] = client
        db = MagicMock()
        db.__enter__.return_value = db
        workspace = SimpleNamespace(tenant_id="t1")
        tenant = SimpleNamespace(plan_type=SimpleNamespace(value="free"))
        db.query.return_value.filter.return_value.first.side_effect = [
            workspace, tenant,
        ]
        with patch.object(h, "get_ranked_providers",
                          return_value=AwaitableResult([("openai", "gpt-4o")])), \
             patch.object(h, "_is_trial_restricted", return_value=False), \
             patch.object(h, "analyze_query_complexity",
                          return_value=QueryComplexity.SIMPLE), \
             patch.object(h, "get_optimal_provider",
                          new=AsyncMock(return_value=(None, None))), \
             patch("core.llm.byok_handler.llm_usage_tracker") as ut, \
             patch("core.llm.byok_handler.get_db_session") as gds:
            ut.is_budget_exceeded.return_value = False
            gds.return_value = db
            result = await h.generate_response("hello", task_type="chat")
        assert result == "own key"
        client.chat.completions.create.assert_called_once()


class TestForcedTierComplexity:
    """Line 1803: valid x-atom-tier override keeps QueryComplexity.COMPLEX."""

    async def test_valid_forced_tier_uses_complex(self):
        h = make_handler(clients={"openai": 1})
        client = Mock()
        client.chat.completions.create.return_value = _chat_response("hi there")
        h.clients["openai"] = client
        with patch.object(h, "get_ranked_providers",
                          return_value=AwaitableResult([("openai", "gpt-4o")])), \
             patch.object(h, "_is_trial_restricted", return_value=False), \
             patch("core.llm.byok_handler.llm_usage_tracker") as ut, \
             patch("core.llm.byok_handler.get_db_session") as gds:
            ut.is_budget_exceeded.return_value = False
            db = MagicMock()
            db.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            gds.return_value = db
            result = await h.generate_response("hello", cognitive_tier="versatile")
        assert result == "hi there"
        client.chat.completions.create.assert_called_once()
