"""
Coverage wave 65d — core/telegram, core/provider_auto_discovery,
core/schedule_optimizer, core/trajectory (TDD; zero LLM spend, no network,
no real DB — all deps mocked/faked).

Bugs found & fixed (regression tests included):
  * core/trajectory.py set_final_result: end_time was tz-aware while
    start_time is naive (utcnow) -> duration_ms() raised TypeError on every
    finished trace. Fixed to naive utcnow (matching the module convention).
"""

import asyncio
import builtins
import datetime
import importlib
import json
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.provider_auto_discovery import ProviderAutoDiscovery, get_auto_discovery
from core.schedule_optimizer import (
    ConflictResolution,
    ResolutionSlot,
    ScheduleOptimizer,
    schedule_optimizer,
)
from core.telegram import TelegramAdapter
from core.trajectory import (
    ExecutionTrace,
    TraceStep,
    TraceStepType,
    TrajectoryRecorder,
)


# --------------------------------------------------------------------------
# core/telegram — TelegramAdapter
# --------------------------------------------------------------------------


class TestTelegramInit:
    def test_defaults_from_env(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "envbot")
        monkeypatch.setenv("TELEGRAM_SECRET_TOKEN", "envsecret")
        adapter = TelegramAdapter()
        assert adapter.bot_token == "envbot"
        assert adapter.secret_token == "envsecret"
        assert adapter.api_base == "https://api.telegram.org/botenvbot"

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "envbot")
        monkeypatch.setenv("TELEGRAM_SECRET_TOKEN", "envsecret")
        adapter = TelegramAdapter(bot_token="argbot", secret_token="argsecret")
        assert adapter.bot_token == "argbot"
        assert adapter.secret_token == "argsecret"
        assert adapter.api_base == "https://api.telegram.org/botargbot"

    def test_no_env_no_args(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_SECRET_TOKEN", raising=False)
        adapter = TelegramAdapter()
        assert adapter.bot_token is None
        assert adapter.secret_token is None
        assert adapter.api_base == "https://api.telegram.org/botNone"


class TestTelegramVerifyRequest:
    @pytest.mark.asyncio
    async def test_skips_verification_when_no_secret(self):
        adapter = TelegramAdapter(bot_token="bot")
        request = SimpleNamespace(headers={})
        assert await adapter.verify_request(request, b"body") is True

    @pytest.mark.asyncio
    async def test_verifies_matching_secret(self):
        adapter = TelegramAdapter(bot_token="bot", secret_token="s3cret")
        request = SimpleNamespace(headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"})
        assert await adapter.verify_request(request, b"body") is True

    @pytest.mark.asyncio
    async def test_rejects_mismatched_secret(self):
        adapter = TelegramAdapter(bot_token="bot", secret_token="s3cret")
        request = SimpleNamespace(headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
        assert await adapter.verify_request(request, b"body") is False

    @pytest.mark.asyncio
    async def test_rejects_missing_header(self):
        adapter = TelegramAdapter(bot_token="bot", secret_token="s3cret")
        request = SimpleNamespace(headers={})
        assert await adapter.verify_request(request, b"body") is False


class TestTelegramNormalizePayload:
    def test_non_dict_returns_empty(self):
        assert TelegramAdapter(bot_token="b").normalize_payload("not a dict") == {}
        assert TelegramAdapter(bot_token="b").normalize_payload(None) == {}

    def test_basic_message(self):
        payload = {
            "message": {
                "from": {"id": 42, "username": "alice"},
                "chat": {"id": -100123},
                "text": "hello",
            }
        }
        result = TelegramAdapter(bot_token="b").normalize_payload(payload)
        assert result["platform"] == "telegram"
        assert result["user_id"] == "42"
        assert result["username"] == "alice"
        assert result["channel_id"] == "-100123"
        assert result["content"] == "hello"
        assert result["metadata"] is payload

    def test_voice_message_sets_media(self):
        payload = {
            "message": {
                "from": {"id": 7},
                "chat": {"id": 99},
                "text": "ignored",
                "voice": {"file_id": "FILE123", "duration": 3},
            }
        }
        result = TelegramAdapter(bot_token="b").normalize_payload(payload)
        assert result["content"] == "[Voice Message]"
        assert result["metadata"]["media_id"] == "FILE123"
        assert result["metadata"]["media_type"] == "voice"

    def test_missing_from_and_chat_defaults(self):
        payload = {"message": {"text": "no sender info"}}
        result = TelegramAdapter(bot_token="b").normalize_payload(payload)
        assert result["user_id"] == ""
        assert result["channel_id"] == ""
        assert result["username"] == ""
        assert result["content"] == "no sender info"

    def test_missing_message_key(self):
        result = TelegramAdapter(bot_token="b").normalize_payload({"update_id": 1})
        assert result["user_id"] == ""
        assert result["content"] == ""


class TestTelegramSendMessage:
    def _client_mock(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock()
        response = Mock()
        response.raise_for_status = Mock()
        client.post.return_value = response
        return client, response

    @pytest.mark.asyncio
    async def test_no_token_returns_false(self):
        adapter = TelegramAdapter()
        assert await adapter.send_message("123", "hi") is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        client, response = self._client_mock()
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            assert await adapter.send_message("123", "hello") is True
        client.post.assert_awaited_once()
        _, kwargs = client.post.await_args
        assert kwargs["json"] == {
            "chat_id": "123",
            "text": "hello",
            "parse_mode": "Markdown",
        }
        assert client.post.await_args.args[0] == (
            "https://api.telegram.org/botbot/sendMessage"
        )
        response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_failure_returns_false(self):
        client, _ = self._client_mock()
        client.post.side_effect = RuntimeError("network down")
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            assert await adapter.send_message("123", "hello") is False

    @pytest.mark.asyncio
    async def test_http_error_returns_false(self):
        client, response = self._client_mock()
        response.raise_for_status.side_effect = RuntimeError("400 Bad Request")
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            assert await adapter.send_message("123", "hello") is False


class TestTelegramGetMedia:
    def _client_mock(self, get_file_result=None, download_content=b"\x00\x01"):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        get_file_resp = Mock()
        get_file_resp.json.return_value = get_file_result or {
            "result": {"file_path": "audio/voice.ogg"}
        }
        get_file_resp.raise_for_status = Mock()
        download_resp = Mock()
        download_resp.content = download_content
        download_resp.raise_for_status = Mock()
        client.get = AsyncMock(side_effect=[get_file_resp, download_resp])
        return client, get_file_resp, download_resp

    @pytest.mark.asyncio
    async def test_no_token_returns_none(self):
        adapter = TelegramAdapter()
        assert await adapter.get_media("F1") is None

    @pytest.mark.asyncio
    async def test_download_success(self):
        client, get_file_resp, download_resp = self._client_mock()
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            content = await adapter.get_media("F1")
        assert content == b"\x00\x01"
        assert client.get.await_args_list[0].kwargs["params"] == {"file_id": "F1"}
        assert client.get.await_args_list[1].args[0] == (
            "https://api.telegram.org/file/botbot/audio/voice.ogg"
        )

    @pytest.mark.asyncio
    async def test_missing_file_path_returns_none(self):
        client, _, _ = self._client_mock(get_file_result={"result": {}})
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            assert await adapter.get_media("F1") is None
        assert client.get.await_count == 1

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        client, _, _ = self._client_mock()
        client.get.side_effect = RuntimeError("telegram unreachable")
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            assert await adapter.get_media("F1") is None


class TestTelegramGetUpdates:
    def _client_mock(self, result):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        res = Mock()
        res.json.return_value = {"result": result}
        res.raise_for_status = Mock()
        client.get = AsyncMock(return_value=res)
        return client, res

    @pytest.mark.asyncio
    async def test_no_token_returns_empty(self):
        adapter = TelegramAdapter()
        assert await adapter.get_updates() == []

    @pytest.mark.asyncio
    async def test_success_returns_updates(self):
        client, _ = self._client_mock([{"update_id": 1}, {"update_id": 2}])
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            updates = await adapter.get_updates(limit=25, offset=10, timeout=5)
        assert [u["update_id"] for u in updates] == [1, 2]
        params = client.get.await_args.kwargs["params"]
        assert params == {"limit": 25, "timeout": 5, "offset": 10}

    @pytest.mark.asyncio
    async def test_limit_clamped(self):
        client, _ = self._client_mock([])
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            await adapter.get_updates(limit=500)
        assert client.get.await_args.kwargs["params"]["limit"] == 100
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            await adapter.get_updates(limit=0)
        assert client.get.await_args.kwargs["params"]["limit"] == 1

    @pytest.mark.asyncio
    async def test_offset_omitted_when_none(self):
        client, _ = self._client_mock([])
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            await adapter.get_updates()
        assert "offset" not in client.get.await_args.kwargs["params"]

    @pytest.mark.asyncio
    async def test_missing_result_key_returns_empty(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        res = Mock()
        res.json.return_value = {"ok": True}
        res.raise_for_status = Mock()
        client.get = AsyncMock(return_value=res)
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            assert await adapter.get_updates() == []

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get.side_effect = RuntimeError("timeout")
        with patch("core.telegram.httpx.AsyncClient", return_value=client):
            adapter = TelegramAdapter(bot_token="bot")
            assert await adapter.get_updates(timeout=30) == []


# --------------------------------------------------------------------------
# core/provider_auto_discovery — ProviderAutoDiscovery
# --------------------------------------------------------------------------

_PRICING_OPENAI = {
    "litellm_provider": "openai",
    "supports_cache": True,
    "supports_vision": True,
    "supports_function_calling": True,
    "input_cost_per_token": 0.00001,
    "output_cost_per_token": 0.00002,
    "mode": "vision",
    "description": "gpt-4o",
    "max_tokens": 4096,
    "context_window": 128000,
    "source": "litellm",
}


class TestProviderAutoDiscoveryHelpers:
    def test_extract_provider_from_model(self):
        provider = ProviderAutoDiscovery()._extract_provider_from_model("gpt-4o", _PRICING_OPENAI)
        assert provider == {
            "provider_id": "openai",
            "name": "Openai",
            "litellm_provider": "openai",
            "supports_cache": True,
            "supports_vision": True,
            "supports_tools": True,
            "is_active": True,
        }

    def test_extract_provider_unknown_returns_none(self):
        discovery = ProviderAutoDiscovery()
        assert discovery._extract_provider_from_model("m", {"litellm_provider": "unknown"}) is None
        assert discovery._extract_provider_from_model("m", {}) is None

    def test_extract_provider_defaults(self):
        provider = ProviderAutoDiscovery()._extract_provider_from_model("m", {"litellm_provider": "x"})
        assert provider["supports_cache"] is False
        assert provider["supports_vision"] is False
        assert provider["supports_tools"] is False

    def test_detect_capabilities_chat_default(self):
        caps = ProviderAutoDiscovery()._detect_capabilities("gpt-4o", {"mode": "chat"})
        assert caps == ["chat"]

    def test_detect_capabilities_vision_mode(self):
        caps = ProviderAutoDiscovery()._detect_capabilities("gpt-4o", {"mode": "vision"})
        assert caps == ["vision"]

    def test_detect_capabilities_vision_flag_keeps_chat(self):
        caps = ProviderAutoDiscovery()._detect_capabilities(
            "gpt-4o", {"mode": "chat", "supports_vision": True}
        )
        assert caps == ["chat", "vision"]

    def test_detect_capabilities_tools(self):
        caps = ProviderAutoDiscovery()._detect_capabilities(
            "gpt-4o", {"mode": "chat", "supports_function_calling": True}
        )
        assert caps == ["chat", "tools"]

    def test_detect_capabilities_vision_and_tools(self):
        caps = ProviderAutoDiscovery()._detect_capabilities(
            "gpt-4o", {"mode": "vision", "supports_function_calling": True}
        )
        assert caps == ["vision", "tools"]

    def test_detect_capabilities_lux_specialization(self):
        caps = ProviderAutoDiscovery()._detect_capabilities("lux-1.0", {"mode": "chat"})
        assert caps == ["computer_use", "browser_use"]

    def test_extract_model_from_pricing(self):
        model = ProviderAutoDiscovery()._extract_model_from_pricing("gpt-4o", _PRICING_OPENAI)
        assert model["model_id"] == "gpt-4o"
        assert model["provider_id"] == "openai"
        assert model["name"] == "gpt-4o"
        assert model["description"] == "gpt-4o"
        assert model["input_cost_per_token"] == 0.00001
        assert model["output_cost_per_token"] == 0.00002
        assert model["max_tokens"] == 4096
        assert model["max_input_tokens"] is None
        assert model["context_window"] == 128000
        assert model["mode"] == "vision"
        assert model["capabilities"] == ["vision", "tools"]
        assert model["exclude_from_general_routing"] is True
        assert model["source"] == "litellm"

    def test_extract_model_unknown_returns_none(self):
        discovery = ProviderAutoDiscovery()
        assert discovery._extract_model_from_pricing("m", {"litellm_provider": "unknown"}) is None
        assert discovery._extract_model_from_pricing("m", {}) is None

    def test_extract_model_chat_not_excluded(self):
        model = ProviderAutoDiscovery()._extract_model_from_pricing(
            "deepseek-chat", {"litellm_provider": "deepseek", "mode": "chat"}
        )
        assert model["exclude_from_general_routing"] is False
        assert model["source"] == "litellm"
        assert model["max_input_tokens"] is None
        assert model["context_window"] is None


class TestProviderAutoDiscoverySync:
    def _fixture(self, registry=None, pricing=None):
        fetcher = Mock()
        fetcher.pricing_cache = pricing or {}
        fetcher.refresh_pricing = AsyncMock()
        registry = registry or Mock()
        return fetcher, registry

    @pytest.mark.asyncio
    async def test_sync_providers_dedup_and_counts(self):
        fetcher, registry = self._fixture(
            pricing={
                "gpt-4o": {"litellm_provider": "openai"},
                "gpt-4o-mini": {"litellm_provider": "openai"},
                "claude-3-5-sonnet": {"litellm_provider": "anthropic"},
            }
        )
        discovery = ProviderAutoDiscovery()
        discovery.pricing_fetcher = fetcher
        discovery.registry = registry
        result = await discovery.sync_providers()
        assert result == {"providers_synced": 2, "models_synced": 3}
        fetcher.refresh_pricing.assert_awaited_once_with(force=True)
        assert registry.upsert_provider.call_count == 2
        assert registry.upsert_model.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_providers_skips_unknown_provider(self):
        fetcher, registry = self._fixture(
            pricing={"weird": {"litellm_provider": "unknown"}}
        )
        discovery = ProviderAutoDiscovery()
        discovery.pricing_fetcher = fetcher
        discovery.registry = registry
        result = await discovery.sync_providers()
        assert result == {"providers_synced": 0, "models_synced": 0}
        registry.upsert_provider.assert_not_called()
        registry.upsert_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_providers_provider_upsert_exception_continues(self):
        fetcher, registry = self._fixture(
            pricing={"gpt-4o": {"litellm_provider": "openai"}}
        )
        registry.upsert_provider.side_effect = RuntimeError("db down")
        discovery = ProviderAutoDiscovery()
        discovery.pricing_fetcher = fetcher
        discovery.registry = registry
        result = await discovery.sync_providers()
        assert result["providers_synced"] == 0
        assert result["models_synced"] == 1
        registry.upsert_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_providers_model_upsert_exception_continues(self):
        fetcher, registry = self._fixture(
            pricing={"gpt-4o": {"litellm_provider": "openai"}}
        )
        registry.upsert_model.side_effect = RuntimeError("db down")
        discovery = ProviderAutoDiscovery()
        discovery.pricing_fetcher = fetcher
        discovery.registry = registry
        result = await discovery.sync_providers()
        assert result["providers_synced"] == 1
        assert result["models_synced"] == 0

    @pytest.mark.asyncio
    async def test_sync_single_provider_filters(self):
        fetcher, registry = self._fixture(
            pricing={
                "gpt-4o": {"litellm_provider": "openai"},
                "claude-3-5-sonnet": {"litellm_provider": "anthropic"},
            }
        )
        discovery = ProviderAutoDiscovery()
        discovery.pricing_fetcher = fetcher
        discovery.registry = registry
        result = await discovery.sync_single_provider("openai")
        assert result == {"provider_id": "openai", "models_synced": 1}
        assert registry.upsert_model.call_count == 1

    @pytest.mark.asyncio
    async def test_sync_single_provider_no_match(self):
        fetcher, registry = self._fixture(
            pricing={"claude-3-5-sonnet": {"litellm_provider": "anthropic"}}
        )
        discovery = ProviderAutoDiscovery()
        discovery.pricing_fetcher = fetcher
        discovery.registry = registry
        result = await discovery.sync_single_provider("openai")
        assert result == {"provider_id": "openai", "models_synced": 0}

    @pytest.mark.asyncio
    async def test_sync_single_provider_model_upsert_exception(self):
        fetcher, registry = self._fixture(
            pricing={"gpt-4o": {"litellm_provider": "openai"}}
        )
        registry.upsert_model.side_effect = RuntimeError("db down")
        discovery = ProviderAutoDiscovery()
        discovery.pricing_fetcher = fetcher
        discovery.registry = registry
        result = await discovery.sync_single_provider("openai")
        assert result == {"provider_id": "openai", "models_synced": 0}


class TestProviderAutoDiscoverySingleton:
    def test_get_auto_discovery_singleton(self):
        import core.provider_auto_discovery as pad

        pad._auto_discovery_instance = None
        d1 = get_auto_discovery()
        d2 = get_auto_discovery()
        assert d1 is d2
        assert isinstance(d1, ProviderAutoDiscovery)


# --------------------------------------------------------------------------
# core/schedule_optimizer — ScheduleOptimizer
# --------------------------------------------------------------------------

_T0 = datetime.datetime(2026, 8, 13, 9, 0, 0)


class TestScheduleModels:
    def test_resolution_slot(self):
        slot = ResolutionSlot(start=_T0, end=_T0 + datetime.timedelta(hours=1), reason="r")
        assert slot.start == _T0
        assert slot.end == _T0 + datetime.timedelta(hours=1)
        assert slot.reason == "r"

    def test_conflict_resolution(self):
        cr = ConflictResolution(
            event_id="e1",
            original_start=_T0,
            suggested_start=_T0 + datetime.timedelta(hours=1),
            suggested_end=_T0 + datetime.timedelta(hours=2),
            conflict_event_id="e2",
        )
        assert cr.event_id == "e1"
        assert cr.conflict_event_id == "e2"

    def test_module_singleton(self):
        assert isinstance(schedule_optimizer, ScheduleOptimizer)

    def test_default_buffer(self):
        assert ScheduleOptimizer().buffer_minutes == 15
        assert ScheduleOptimizer(buffer_minutes=30).buffer_minutes == 30
        assert ScheduleOptimizer().cache == {}


class TestFindResolutionSlots:
    @pytest.mark.asyncio
    async def test_no_conflicts_returns_three_slots(self):
        optimizer = ScheduleOptimizer()
        conflicting = {"start": _T0 - datetime.timedelta(hours=1), "end": _T0}
        slots = await optimizer.find_resolution_slots(conflicting, [], lookahead_days=1)
        assert len(slots) == 3
        assert slots[0].start == _T0
        assert slots[0].end == _T0 + datetime.timedelta(hours=1)
        assert slots[0].reason == "First available gap after conflict"
        assert slots[1].start == _T0 + datetime.timedelta(minutes=75)

    @pytest.mark.asyncio
    async def test_conflict_jumps_to_event_end(self):
        optimizer = ScheduleOptimizer()
        conflicting = {"start": _T0 - datetime.timedelta(hours=1), "end": _T0}
        events = [
            {"start": _T0 + datetime.timedelta(minutes=30), "end": _T0 + datetime.timedelta(hours=3)}
        ]
        slots = await optimizer.find_resolution_slots(conflicting, events, lookahead_days=1)
        assert len(slots) == 3
        assert slots[0].start == _T0 + datetime.timedelta(hours=3, minutes=15)

    @pytest.mark.asyncio
    async def test_no_slots_when_search_exhausted(self):
        optimizer = ScheduleOptimizer()
        conflicting = {"start": _T0 - datetime.timedelta(hours=1), "end": _T0}
        events = [
            {"start": _T0, "end": _T0 + datetime.timedelta(days=3)}
        ]
        slots = await optimizer.find_resolution_slots(conflicting, events, lookahead_days=1)
        assert slots == []

    @pytest.mark.asyncio
    async def test_events_unsorted_input(self):
        optimizer = ScheduleOptimizer()
        conflicting = {"start": _T0 - datetime.timedelta(hours=1), "end": _T0}
        events = [
            {"start": _T0 + datetime.timedelta(hours=6), "end": _T0 + datetime.timedelta(hours=7)},
            {"start": _T0 + datetime.timedelta(hours=2), "end": _T0 + datetime.timedelta(hours=3)},
        ]
        slots = await optimizer.find_resolution_slots(conflicting, events, lookahead_days=1)
        assert len(slots) == 3
        assert all(s.start != _T0 + datetime.timedelta(hours=2) for s in slots)


class TestCalculatePriority:
    @pytest.mark.asyncio
    async def test_no_attendees(self):
        assert await ScheduleOptimizer().calculate_priority({}) == 0

    @pytest.mark.asyncio
    async def test_roles_weights(self):
        event = {
            "attendees": [
                {"role": "decision_maker"},
                {"role": "organizer"},
                {"role": "required"},
                {"role": "optional"},
            ]
        }
        assert await ScheduleOptimizer().calculate_priority(event) == 240

    @pytest.mark.asyncio
    async def test_unknown_role_defaults_to_50(self):
        event = {"attendees": [{"role": "observer"}]}
        assert await ScheduleOptimizer().calculate_priority(event) == 50

    @pytest.mark.asyncio
    async def test_non_dict_attendee_counts_as_required(self):
        event = {"attendees": ["just-a-name", {"role": "optional"}]}
        assert await ScheduleOptimizer().calculate_priority(event) == 60


class TestCalculateDensityPenalty:
    @pytest.mark.asyncio
    async def test_no_events_zero(self):
        target_start = _T0 + datetime.timedelta(hours=1)
        assert await ScheduleOptimizer().calculate_density_penalty(
            target_start, target_start + datetime.timedelta(hours=1), []
        ) == 0.0

    @pytest.mark.asyncio
    async def test_back_to_back_before_penalty_30(self):
        target_start = _T0 + datetime.timedelta(hours=1)
        target_end = target_start + datetime.timedelta(hours=1)
        events = [{"start": _T0, "end": target_start}]
        assert await ScheduleOptimizer().calculate_density_penalty(
            target_start, target_end, events
        ) == 30.0

    @pytest.mark.asyncio
    async def test_back_to_back_after_penalty_30(self):
        target_start = _T0 + datetime.timedelta(hours=1)
        target_end = target_start + datetime.timedelta(hours=1)
        events = [{"start": target_end, "end": target_end + datetime.timedelta(hours=1)}]
        assert await ScheduleOptimizer().calculate_density_penalty(
            target_start, target_end, events
        ) == 30.0

    @pytest.mark.asyncio
    async def test_proximity_30_minutes_penalty_15(self):
        target_start = _T0 + datetime.timedelta(hours=1)
        target_end = target_start + datetime.timedelta(hours=1)
        events = [{"start": _T0, "end": _T0 + datetime.timedelta(minutes=30)}]
        assert await ScheduleOptimizer().calculate_density_penalty(
            target_start, target_end, events
        ) == 15.0

    @pytest.mark.asyncio
    async def test_exactly_60_minutes_away_no_penalty(self):
        target_start = _T0 + datetime.timedelta(hours=1)
        target_end = target_start + datetime.timedelta(hours=1)
        events = [{"start": _T0 - datetime.timedelta(hours=1), "end": _T0}]
        assert await ScheduleOptimizer().calculate_density_penalty(
            target_start, target_end, events
        ) == 0.0

    @pytest.mark.asyncio
    async def test_outside_window_no_penalty(self):
        target_start = _T0 + datetime.timedelta(hours=1)
        target_end = target_start + datetime.timedelta(hours=1)
        events = [{"start": _T0 - datetime.timedelta(hours=5), "end": _T0 - datetime.timedelta(hours=4)}]
        assert await ScheduleOptimizer().calculate_density_penalty(
            target_start, target_end, events
        ) == 0.0

    @pytest.mark.asyncio
    async def test_penalty_capped_at_100(self):
        target_start = _T0 + datetime.timedelta(hours=1)
        target_end = target_start + datetime.timedelta(hours=1)
        events = [
            {"start": target_start - datetime.timedelta(seconds=30), "end": target_start},
            {"start": target_start, "end": target_start + datetime.timedelta(seconds=30)},
            {"start": target_end - datetime.timedelta(seconds=30), "end": target_end},
            {"start": target_end, "end": target_end + datetime.timedelta(seconds=30)},
        ]
        assert await ScheduleOptimizer().calculate_density_penalty(
            target_start, target_end, events
        ) == 100.0


class TestDetectAllConflicts:
    @pytest.mark.asyncio
    async def test_no_conflicts(self):
        events = [
            {"start": _T0, "end": _T0 + datetime.timedelta(hours=1), "attendees": []},
            {"start": _T0 + datetime.timedelta(hours=2), "end": _T0 + datetime.timedelta(hours=3), "attendees": []},
        ]
        assert await ScheduleOptimizer().detect_all_conflicts(events) == []

    @pytest.mark.asyncio
    async def test_overlap_detected_with_priorities(self):
        events = [
            {
                "start": _T0,
                "end": _T0 + datetime.timedelta(hours=1),
                "attendees": [{"role": "decision_maker"}],
            },
            {
                "start": _T0 + datetime.timedelta(minutes=30),
                "end": _T0 + datetime.timedelta(hours=2),
                "attendees": [{"role": "required"}],
            },
        ]
        conflicts = await ScheduleOptimizer().detect_all_conflicts(events)
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict["event1"] is events[0]
        assert conflict["event2"] is events[1]
        assert conflict["priority1"] == 100
        assert conflict["priority2"] == 50
        assert conflict["overlap_minutes"] == 30.0

    @pytest.mark.asyncio
    async def test_contained_event_overlap(self):
        events = [
            {
                "start": _T0,
                "end": _T0 + datetime.timedelta(hours=2),
                "attendees": [],
            },
            {
                "start": _T0 + datetime.timedelta(minutes=30),
                "end": _T0 + datetime.timedelta(hours=1),
                "attendees": [],
            },
        ]
        conflicts = await ScheduleOptimizer().detect_all_conflicts(events)
        assert len(conflicts) == 1
        assert conflicts[0]["overlap_minutes"] == 30.0

    @pytest.mark.asyncio
    async def test_non_overlapping_breaks_early(self):
        events = [
            {"start": _T0, "end": _T0 + datetime.timedelta(hours=1), "attendees": []},
            {"start": _T0 + datetime.timedelta(hours=2), "end": _T0 + datetime.timedelta(hours=3), "attendees": []},
            {"start": _T0 + datetime.timedelta(hours=4), "end": _T0 + datetime.timedelta(hours=5), "attendees": []},
        ]
        assert await ScheduleOptimizer().detect_all_conflicts(events) == []


# --------------------------------------------------------------------------
# core/trajectory — TrajectoryRecorder / ExecutionTrace
# --------------------------------------------------------------------------


class TestTraceModels:
    def test_trace_step_type_enum_values(self):
        assert TraceStepType.THOUGHT.value == "thought"
        assert TraceStepType.TOOL_CALL.value == "tool_call"
        assert TraceStepType.TOOL_RESULT.value == "tool_result"
        assert TraceStepType.FINAL_ANSWER.value == "final_answer"
        assert TraceStepType.ERROR.value == "error"

    def test_trace_step_defaults(self):
        step = TraceStep(type=TraceStepType.THOUGHT, content="hi")
        assert step.step_id
        assert isinstance(step.timestamp, datetime.datetime)
        assert step.metadata == {}

    def test_execution_trace_defaults(self):
        trace = ExecutionTrace(user_id="u", request="r")
        assert trace.trace_id
        assert trace.end_time is None
        assert trace.steps == []
        assert trace.final_result is None

    def test_trace_step_metadata_custom(self):
        step = TraceStep(
            type=TraceStepType.TOOL_CALL,
            content="call",
            metadata={"tool": "search", "args": {"q": 1}},
        )
        assert step.metadata["tool"] == "search"


class TestTrajectoryRecorderMethods:
    def test_init_creates_trace(self):
        rec = TrajectoryRecorder("user-1", "what is 2+2?")
        assert rec.trace.user_id == "user-1"
        assert rec.trace.request == "what is 2+2?"
        assert rec.trace.steps == []

    def test_add_thought(self):
        rec = TrajectoryRecorder("u", "r")
        rec.add_thought("thinking hard")
        assert len(rec.trace.steps) == 1
        step = rec.trace.steps[0]
        assert step.type == TraceStepType.THOUGHT
        assert step.content == "thinking hard"

    def test_add_tool_call(self):
        rec = TrajectoryRecorder("u", "r")
        rec.add_tool_call("web_search", {"q": "atom"})
        step = rec.trace.steps[0]
        assert step.type == TraceStepType.TOOL_CALL
        assert step.content == "Calling tool: web_search"
        assert step.metadata == {"tool": "web_search", "args": {"q": "atom"}}

    def test_add_tool_result(self):
        rec = TrajectoryRecorder("u", "r")
        rec.add_tool_result("web_search", {"n": 3})
        step = rec.trace.steps[0]
        assert step.type == TraceStepType.TOOL_RESULT
        assert step.content == "Result from web_search"
        assert step.metadata["result"] == "{'n': 3}"

    def test_add_tool_result_error(self):
        rec = TrajectoryRecorder("u", "r")
        rec.add_tool_result("web_search", "boom", is_error=True)
        assert rec.trace.steps[0].type == TraceStepType.ERROR

    def test_set_final_result(self):
        rec = TrajectoryRecorder("u", "r")
        rec.set_final_result({"answer": 42})
        assert rec.trace.final_result == {"answer": 42}
        assert rec.trace.steps[-1].type == TraceStepType.FINAL_ANSWER
        assert rec.trace.steps[-1].content == "Generated Final Response"
        assert rec.trace.steps[-1].metadata == {"result": {"answer": 42}}
        assert rec.trace.end_time is not None


class TestDurationMs:
    def test_duration_zero_without_end_time(self):
        rec = TrajectoryRecorder("u", "r")
        assert rec.trace.duration_ms() == 0.0

    def test_duration_after_set_final_result(self):
        """Regression: end_time was tz-aware vs naive start_time -> TypeError."""
        rec = TrajectoryRecorder("u", "r")
        rec.set_final_result({"ok": True})
        duration = rec.trace.duration_ms()
        assert duration >= 0.0
        assert isinstance(duration, float)

    def test_duration_manual_end_time(self):
        trace = ExecutionTrace(user_id="u", request="r")
        trace.end_time = trace.start_time + datetime.timedelta(seconds=2)
        assert trace.duration_ms() == 2000.0


# --------------------------------------------------------------------------
# core/trajectory — save() (fake aiofiles: real aiofiles NOT installed here)
# --------------------------------------------------------------------------


class _FakeAioFile:
    def __init__(self, path):
        self.path = path
        self.parts = []

    async def write(self, data):
        self.parts.append(data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("".join(self.parts))
        return False


def _install_fake_aiofiles(monkeypatch):
    import core.trajectory as traj

    fake = types.ModuleType("aiofiles")
    fake.open = lambda path, mode="w": _FakeAioFile(path)
    monkeypatch.setattr(traj, "aiofiles", fake, raising=False)
    monkeypatch.setattr(traj, "AIOFILES_AVAILABLE", True, raising=False)
    return traj


class TestTrajectorySave:
    @pytest.mark.asyncio
    async def test_save_creates_json_file(self, monkeypatch, tmp_path):
        _install_fake_aiofiles(monkeypatch)
        monkeypatch.chdir(tmp_path)
        rec = TrajectoryRecorder("u1", "r1")
        rec.add_thought("t")
        filename = await rec.save("logs/traces")
        assert filename == f"logs/traces/{rec.trace.trace_id}.json"
        assert os.path.exists(filename)
        data = json.load(open(filename))
        assert data["user_id"] == "u1"
        assert data["request"] == "r1"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["content"] == "t"

    @pytest.mark.asyncio
    async def test_save_full_trace_content(self, monkeypatch, tmp_path):
        _install_fake_aiofiles(monkeypatch)
        monkeypatch.chdir(tmp_path)
        rec = TrajectoryRecorder("u2", "r2")
        rec.add_thought("t")
        rec.add_tool_call("search", {"q": "x"})
        rec.add_tool_result("search", "res")
        rec.set_final_result({"answer": "a"})
        filename = await rec.save("logs/traces")
        data = json.load(open(filename))
        assert [s["type"] for s in data["steps"]] == [
            "thought",
            "tool_call",
            "tool_result",
            "final_answer",
        ]
        assert data["final_result"] == {"answer": "a"}
        assert data["end_time"] is not None
        assert "start_time" in data

    @pytest.mark.asyncio
    async def test_save_sanitizes_traversal_directory(self, monkeypatch, tmp_path):
        _install_fake_aiofiles(monkeypatch)
        monkeypatch.chdir(tmp_path)
        rec = TrajectoryRecorder("u", "r")
        filename = await rec.save("../etc/passwd")
        assert filename == f"etc/passwd/{rec.trace.trace_id}.json"
        assert os.path.exists(filename)
        assert not (tmp_path.parent / "etc").exists()

    @pytest.mark.asyncio
    async def test_save_empty_directory_falls_back_to_default(self, monkeypatch, tmp_path):
        _install_fake_aiofiles(monkeypatch)
        monkeypatch.chdir(tmp_path)
        rec = TrajectoryRecorder("u", "r")
        filename = await rec.save("..")
        assert filename == f"logs/traces/{rec.trace.trace_id}.json"
        assert os.path.exists(filename)

    @pytest.mark.asyncio
    async def test_save_sanitizes_trace_id_in_filename(self, monkeypatch, tmp_path):
        _install_fake_aiofiles(monkeypatch)
        monkeypatch.chdir(tmp_path)
        rec = TrajectoryRecorder("u", "r")
        rec.trace.trace_id = "a/../b.json"
        filename = await rec.save("logs/traces")
        assert filename == "logs/traces/abjson.json"
        assert os.path.exists(filename)

    @pytest.mark.asyncio
    async def test_save_empty_trace_id_generates_new(self, monkeypatch, tmp_path):
        _install_fake_aiofiles(monkeypatch)
        monkeypatch.chdir(tmp_path)
        rec = TrajectoryRecorder("u", "r")
        rec.trace.trace_id = "///"
        filename = await rec.save("logs/traces")
        assert filename != "logs/traces/.json"
        assert filename.endswith(".json")
        assert os.path.exists(filename)

    @pytest.mark.asyncio
    async def test_save_skips_makedirs_when_dir_exists(self, monkeypatch, tmp_path):
        _install_fake_aiofiles(monkeypatch)
        monkeypatch.chdir(tmp_path)
        os.makedirs("logs/traces", exist_ok=True)
        rec = TrajectoryRecorder("u", "r")
        filename = await rec.save("logs/traces")
        assert os.path.exists(filename)

    @pytest.mark.asyncio
    async def test_save_non_serializable_metadata_raises(self, monkeypatch, tmp_path):
        _install_fake_aiofiles(monkeypatch)
        monkeypatch.chdir(tmp_path)

        class _Weird:
            pass

        rec = TrajectoryRecorder("u", "r")
        rec.add_tool_call("search", {"query": _Weird()})
        with pytest.raises(TypeError):
            await rec.save("logs/traces")

    def test_save_raises_import_error_when_aiofiles_unavailable(self, monkeypatch):
        import core.trajectory as traj

        monkeypatch.setattr(traj, "AIOFILES_AVAILABLE", False)
        rec = traj.TrajectoryRecorder("u", "r")
        with pytest.raises(ImportError, match="aiofiles"):
            asyncio.run(rec.save("logs/traces"))


class TestTrajectoryAiofilesDetection:
    def test_import_with_aiofiles_sets_flag(self, monkeypatch):
        import core.trajectory as traj

        fake_mod = types.ModuleType("aiofiles")
        monkeypatch.setitem(sys.modules, "aiofiles", fake_mod)
        reloaded = importlib.reload(traj)
        assert reloaded.AIOFILES_AVAILABLE is True

    def test_import_without_aiofiles_sets_flag_false(self, monkeypatch):
        import core.trajectory as traj

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "aiofiles":
                raise ImportError("no aiofiles here")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        reloaded = importlib.reload(traj)
        assert reloaded.AIOFILES_AVAILABLE is False

    def test_restore_module_state(self):
        import core.trajectory as traj

        reloaded = importlib.reload(traj)
        try:
            import aiofiles  # noqa: F401

            expected = True
        except ImportError:
            expected = False
        assert reloaded.AIOFILES_AVAILABLE is expected
