"""Coverage push (W44) — LLM gateway service + wire formats to >=90%.

Direct unit coverage of ``core/llm/gateway/gateway_service.py`` and
``core/llm/gateway/wire_formats.py`` — the pure translators get direct
calls; the service gets a mocked BYOKHandler (mirroring
``tests/test_bughunt_gateway.py`` harness conventions). No real LLM/network
calls anywhere.
"""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.llm.byok_handler import (
    AllProvidersFailedError,
    GatewayBlockedError,
    NoProvidersConfiguredError,
)
from core.llm.cognitive_tier_system import CognitiveTier
from core.llm.gateway.auth import GatewayIdentity
from core.llm.gateway.gateway_service import GatewayService


def _identity():
    return GatewayIdentity(
        user_id="u-1",
        tenant_id="t-1",
        workspace_id="ws-1",
        auth_method="api_key",
        api_key_id="key-1",
    )


def _fake_handler(**overrides):
    handler = MagicMock()
    handler.analyze_query_complexity.return_value = "simple"
    handler.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
    handler.get_ranked_providers.return_value = [("openai", "gpt-4o-mini")]
    handler._provider_serves_model.return_value = False
    handler._rerank_with_learning = AsyncMock(
        return_value=[("anthropic", "claude-3-5-sonnet")]
    )
    handler.async_clients = {"openai": object(), "anthropic": object()}
    handler.clients = {}
    handler.byok_manager = SimpleNamespace(
        providers={"openai": SimpleNamespace(model="gpt-4o-mini")}
    )
    for k, v in overrides.items():
        setattr(handler, k, v)
    return handler


def _service_harness(handler):
    with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
        return GatewayService(_identity(), MagicMock())


# --------------------------------------------------------------------------- #
# wire_formats: prompt_from_messages
# --------------------------------------------------------------------------- #
class TestPromptFromMessages:
    def test_empty_messages_returns_default(self):
        from core.llm.gateway.wire_formats import prompt_from_messages

        assert prompt_from_messages([], default="d") == "d"

    def test_non_dict_messages_skipped(self):
        from core.llm.gateway.wire_formats import prompt_from_messages

        assert prompt_from_messages([{"role": "user", "content": "ok"}, "nope"]) == "ok"

    def test_user_message_with_none_content_skipped(self):
        from core.llm.gateway.wire_formats import prompt_from_messages

        msgs = [{"role": "user", "content": None}, {"role": "assistant", "content": "x"}]
        assert prompt_from_messages(msgs, default="d") == "d"

    def test_content_list_mixed_parts(self):
        from core.llm.gateway.wire_formats import prompt_from_messages

        msgs = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "hi"},
                {"type": "image", "text": "img"},
                " world ",
                {"type": "text", "text": "  "},
            ],
        }]
        assert prompt_from_messages(msgs) == "hi img world"

    def test_non_string_content_coerced(self):
        from core.llm.gateway.wire_formats import prompt_from_messages

        assert prompt_from_messages([{"role": "user", "content": 42}]) == "42"


# --------------------------------------------------------------------------- #
# wire_formats: _content_block_to_openai (private, direct unit calls)
# --------------------------------------------------------------------------- #
class TestContentBlockToOpenai:
    def test_text_block_overwrites_str_content(self):
        from core.llm.gateway.wire_formats import _content_block_to_openai

        msg = {"role": "user", "content": "old"}
        _content_block_to_openai({"type": "text", "text": "new"}, msg)
        assert msg["content"] == "new"

    def test_text_block_appended_to_list_content(self):
        from core.llm.gateway.wire_formats import _content_block_to_openai

        msg = {"role": "user", "content": []}
        _content_block_to_openai({"type": "text", "text": "new"}, msg)
        assert msg["content"] == [{"type": "text", "text": "new"}]

    def test_image_base64_source(self):
        from core.llm.gateway.wire_formats import _content_block_to_openai

        msg = {"role": "user", "content": []}
        _content_block_to_openai(
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}},
            msg,
        )
        assert msg["content"] == [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}}
        ]

    def test_image_url_source(self):
        from core.llm.gateway.wire_formats import _content_block_to_openai

        msg = {"role": "user", "content": []}
        _content_block_to_openai(
            {"type": "image", "source": {"type": "url", "url": "https://x/img.png"}}, msg
        )
        assert msg["content"] == [{"type": "image_url", "image_url": {"url": "https://x/img.png"}}]

    def test_tool_use_block_preserved_as_text(self):
        from core.llm.gateway.wire_formats import _content_block_to_openai

        msg = {"role": "user", "content": []}
        _content_block_to_openai({"type": "tool_use", "text": "t"}, msg)
        assert msg["content"] == [{"type": "text", "text": "t"}]

    def test_thinking_block_without_text_dropped(self):
        from core.llm.gateway.wire_formats import _content_block_to_openai

        msg = {"role": "user", "content": []}
        _content_block_to_openai({"type": "thinking"}, msg)
        assert msg["content"] == []

    def test_unknown_block_with_content_preserved(self):
        from core.llm.gateway.wire_formats import _content_block_to_openai

        msg = {"role": "user", "content": []}
        _content_block_to_openai({"type": "redacted_thinking", "content": "red"}, msg)
        assert msg["content"] == [{"type": "text", "text": "red"}]


# --------------------------------------------------------------------------- #
# wire_formats: anthropic_request_to_openai
# --------------------------------------------------------------------------- #
class TestAnthropicRequestToOpenai:
    def test_system_string(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai({
            "system": "Be brief",
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert out["messages"][0] == {"role": "system", "content": "Be brief"}

    def test_system_content_list(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai({
            "system": [{"type": "text", "text": "be"}, " brief", {"type": "other"}],
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert out["messages"][0] == {"role": "system", "content": "be brief"}

    def test_assistant_list_content(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai({
            "messages": [{"role": "assistant", "content": [{"type": "text", "text": "hi"}]}]
        })
        assert out["messages"][0]["role"] == "assistant"
        assert out["messages"][0]["content"] == [{"type": "text", "text": "hi"}]

    def test_model_and_stop_sequences_passed_through(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai({
            "model": "claude-3-5-sonnet",
            "stop_sequences": ["STOP"],
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert out["model"] == "claude-3-5-sonnet"
        assert out["stop"] == ["STOP"]

    def test_unknown_role_list_content_copied_verbatim(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        original = ["x", {"type": "text", "text": "y"}]
        payload = {"messages": [{"role": "other", "content": original}]}
        out = anthropic_request_to_openai(payload)
        assert out["messages"][0]["role"] == "other"
        assert out["messages"][0]["content"] == original
        assert out["messages"][0]["content"] is not original

    def test_unknown_role_empty_list_content_becomes_empty_string(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai({"messages": [{"role": "other", "content": []}]})
        assert out["messages"][0]["content"] == ""

    def test_non_dict_blocks_become_text(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai(
            {"messages": [{"role": "user", "content": ["raw"]}]}
        )
        assert out["messages"][0]["content"] == [{"type": "text", "text": "raw"}]

    def test_empty_content_list_becomes_empty_string(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai(
            {"messages": [{"role": "user", "content": [{"type": "thinking"}]}]}
        )
        assert out["messages"][0]["content"] == ""

    def test_none_content_becomes_empty_string(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai({"messages": [{"role": "user", "content": None}]})
        assert out["messages"][0]["content"] == ""

    def test_top_p_zero_preserved(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai({
            "top_p": 0.0,
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert out["top_p"] == 0.0

    def test_absent_optional_fields_not_set(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai({"messages": [{"role": "user", "content": "hi"}]})
        assert "model" not in out
        assert "stop" not in out
        assert out["temperature"] == 0.7
        assert out["max_tokens"] == 1000

    def test_empty_stop_sequences_omitted(self):
        from core.llm.gateway.wire_formats import anthropic_request_to_openai

        out = anthropic_request_to_openai({
            "stop_sequences": [],
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert "stop" not in out


# --------------------------------------------------------------------------- #
# wire_formats: openai_response_to_anthropic + maps
# --------------------------------------------------------------------------- #
class TestOpenAIResponseToAnthropic:
    def test_multipart_content_joined(self):
        from core.llm.gateway.wire_formats import openai_response_to_anthropic

        resp = {
            "model": "gpt-4o",
            "created": 123456,
            "choices": [{
                "message": {
                    "content": [
                        {"type": "text", "text": "a"},
                        {"content": "b"},
                        "c",
                    ]
                },
                "finish_reason": "function_call",
            }],
        }
        msg = openai_response_to_anthropic(resp)
        assert msg["content"] == [{"type": "text", "text": "abc"}]
        assert msg["stop_reason"] == "tool_use"
        assert msg["created"] == 123456
        assert msg["usage"] == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def test_no_choices_and_explicit_stop_reason(self):
        from core.llm.gateway.wire_formats import openai_response_to_anthropic

        msg = openai_response_to_anthropic({"model": "m"}, stop_reason="max_tokens")
        assert msg["content"] == [{"type": "text", "text": ""}]
        assert msg["stop_reason"] == "max_tokens"
        assert msg["usage"]["input_tokens"] == 0

    def test_no_created_uses_clock(self):
        from core.llm.gateway.wire_formats import openai_response_to_anthropic

        before = int(time.time())
        msg = openai_response_to_anthropic(
            {"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]}
        )
        assert before <= msg["created"] <= int(time.time()) + 1

    def test_unknown_stop_reason_passthrough(self):
        from core.llm.gateway.wire_formats import map_stop_reason

        assert map_stop_reason("weird_reason") == "weird_reason"
        assert map_stop_reason("stop") == "end_turn"

    def test_error_type_map(self):
        from core.llm.gateway.wire_formats import map_error_type

        assert map_error_type(400) == "invalid_request_error"
        assert map_error_type(401) == "authentication_error"
        assert map_error_type(403) == "permission_error"
        assert map_error_type(404) == "not_found_error"
        assert map_error_type(422) == "invalid_request_error"
        assert map_error_type(429) == "rate_limit_error"
        assert map_error_type(500) == "api_error"
        assert map_error_type(502) == "api_error"
        assert map_error_type(503) == "overloaded_error"
        assert map_error_type(504) == "api_error"
        assert map_error_type(418) == "api_error"


# --------------------------------------------------------------------------- #
# gateway_service: _resolve_route
# --------------------------------------------------------------------------- #
class TestResolveRoute:
    async def test_forced_tier_uses_cognitive_tier(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            [{"role": "user", "content": "hi"}], "auto", {"x-atom-tier": "micro"}
        )
        assert provider == "openai"
        assert model == "gpt-4o-mini"
        handler.get_ranked_providers.assert_called_once_with(
            "simple", "chat", prefer_cost=True, cognitive_tier=CognitiveTier.MICRO
        )

    async def test_invalid_tier_falls_back_to_absolute(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        with patch(
            "core.llm.gateway.gateway_service.parse_routing_overrides",
            return_value={"tier": "bogus"},
        ):
            provider, model = await service._resolve_route(
                [{"role": "user", "content": "hi"}], "auto"
            )
        assert provider == "openai"
        assert model == "gpt-4o-mini"
        handler.get_ranked_providers.assert_not_called()

    async def test_no_providers_config_reraises(self):
        handler = _fake_handler()
        handler.get_ranked_providers.side_effect = NoProvidersConfiguredError()
        service = _service_harness(handler)
        with pytest.raises(NoProvidersConfiguredError):
            await service._resolve_route([{"role": "user", "content": "hi"}], "auto")

    async def test_generic_routing_error_falls_back(self):
        handler = _fake_handler()
        handler.get_ranked_providers.side_effect = RuntimeError("boom")
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            [{"role": "user", "content": "hi"}], "auto"
        )
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    async def test_forced_intent_reranks_with_learning(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        with patch(
            "core.llm.gateway.gateway_service.parse_routing_overrides",
            return_value={"intent": "code"},
        ):
            provider, model = await service._resolve_route(
                [{"role": "user", "content": "hi"}], "auto"
            )
        assert provider == "anthropic"
        assert model == "claude-3-5-sonnet"
        handler._rerank_with_learning.assert_awaited_once()

    async def test_forced_model_header_wins_with_provider_resolution(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            [{"role": "user", "content": "hi"}], "gpt-4o", {"x-atom-model": "deepseek-chat"}
        )
        assert model == "deepseek-chat"
        assert provider == "openai"


# --------------------------------------------------------------------------- #
# gateway_service: _optimal / _absolute_fallback / _resolve_provider_for_model
# --------------------------------------------------------------------------- #
class TestRoutingFallbacks:
    def test_optimal_success(self):
        service = _service_harness(_fake_handler())
        assert service._optimal() == ("openai", "gpt-4o-mini")

    def test_optimal_generic_error_falls_back(self):
        handler = _fake_handler()
        handler.get_optimal_provider.side_effect = RuntimeError("boom")
        service = _service_harness(handler)
        assert service._optimal() == ("openai", "gpt-4o-mini")

    def test_optimal_no_providers_reraises(self):
        handler = _fake_handler()
        handler.get_optimal_provider.side_effect = NoProvidersConfiguredError()
        service = _service_harness(handler)
        with pytest.raises(NoProvidersConfiguredError):
            service._optimal()

    def test_absolute_fallback_uses_configured_model(self):
        service = _service_harness(_fake_handler())
        assert service._absolute_fallback() == ("openai", "gpt-4o-mini")

    def test_absolute_fallback_missing_model_uses_default(self):
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(
            providers={"openai": SimpleNamespace(model=None)}
        )
        service = _service_harness(handler)
        assert service._absolute_fallback() == ("openai", "gpt-4o-mini")

    def test_absolute_fallback_provider_lookup_error_uses_default(self):
        handler = _fake_handler()
        providers = MagicMock()
        providers.get.side_effect = RuntimeError("boom")
        handler.byok_manager = SimpleNamespace(providers=providers)
        service = _service_harness(handler)
        assert service._absolute_fallback() == ("openai", "gpt-4o-mini")

    def test_absolute_fallback_no_clients_raises(self):
        handler = _fake_handler()
        handler.async_clients = {}
        handler.clients = {}
        service = _service_harness(handler)
        with pytest.raises(NoProvidersConfiguredError):
            service._absolute_fallback()

    def test_resolve_provider_for_model_no_server(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        assert service._resolve_provider_for_model("openai", "gpt-4o") == ("openai", "gpt-4o")

    def test_resolve_provider_for_model_reroutes_to_server(self):
        handler = _fake_handler()
        handler._provider_serves_model.side_effect = lambda pid, m: pid == "anthropic"
        service = _service_harness(handler)
        assert service._resolve_provider_for_model("openai", "claude-x") == ("anthropic", "claude-x")


# --------------------------------------------------------------------------- #
# gateway_service: list_models / _models_for_provider
# --------------------------------------------------------------------------- #
class TestListModels:
    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_list_models_dedupes(self, get_models):
        get_models.side_effect = lambda db, pid: ["gpt-4o", "gpt-4o"] if pid == "openai" else ["claude-x"]
        service = _service_harness(_fake_handler())
        body = service.list_models()
        assert body["object"] == "list"
        assert [m["id"] for m in body["data"]] == ["gpt-4o", "claude-x"]

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_list_models_empty_falls_back_to_provider_ids(self, get_models):
        get_models.return_value = []
        service = _service_harness(_fake_handler())
        body = service.list_models()
        assert [m["id"] for m in body["data"]] == ["openai", "anthropic"]

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_list_models_uses_sync_clients_when_async_empty(self, get_models):
        get_models.return_value = []
        handler = _fake_handler()
        handler.async_clients = {}
        handler.clients = {"openai": object()}
        service = _service_harness(handler)
        body = service.list_models()
        assert [m["id"] for m in body["data"]] == ["openai"]

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_models_for_provider_registry_success(self, get_models):
        get_models.return_value = ["gpt-4o"]
        service = _service_harness(_fake_handler())
        assert service._models_for_provider("openai") == ["gpt-4o"]

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_models_for_provider_registry_failure_falls_back_to_config(self, get_models):
        get_models.side_effect = RuntimeError("registry down")
        service = _service_harness(_fake_handler())
        assert service._models_for_provider("openai") == ["gpt-4o-mini"]

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_models_for_provider_no_config_returns_empty(self, get_models):
        get_models.side_effect = ImportError("no registry")
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(providers={})
        service = _service_harness(handler)
        assert service._models_for_provider("openai") == []


# --------------------------------------------------------------------------- #
# gateway_service: map_gateway_error / _error_body / helpers
# --------------------------------------------------------------------------- #
class TestMapGatewayError:
    def test_no_providers_error(self):
        service = _service_harness(_fake_handler())
        body = service.map_gateway_error(NoProvidersConfiguredError())
        assert body["_status"] == 503
        assert body["error"]["code"] == "no_llm_provider"
        assert body["error"]["recovery_url"] == "/settings/ai"

    def test_no_providers_error_custom_recovery_url(self):
        service = _service_harness(_fake_handler())
        exc = NoProvidersConfiguredError(recovery_url="/custom")
        body = service.map_gateway_error(exc)
        assert body["error"]["recovery_url"] == "/custom"

    def test_gateway_blocked_error(self):
        service = _service_harness(_fake_handler())
        body = service.map_gateway_error(
            GatewayBlockedError(reason="trial_expired", message="Trial expired")
        )
        assert body["_status"] == 429
        assert body["error"]["code"] == "trial_expired"
        assert "recovery_url" not in body["error"]

    def test_all_providers_failed(self):
        service = _service_harness(_fake_handler())
        body = service.map_gateway_error(AllProvidersFailedError("boom"))
        assert body["_status"] == 502
        assert body["error"]["code"] == "all_providers_failed"

    def test_http_exception(self):
        service = _service_harness(_fake_handler())
        body = service.map_gateway_error(HTTPException(status_code=418, detail="teapot"))
        assert body["_status"] == 418
        assert body["error"]["message"] == "teapot"
        assert body["error"]["code"] == "gateway_error"

    def test_value_error(self):
        service = _service_harness(_fake_handler())
        body = service.map_gateway_error(ValueError("nope"))
        assert body["_status"] == 400
        assert body["error"]["code"] == "invalid_request"

    def test_generic_error(self):
        service = _service_harness(_fake_handler())
        body = service.map_gateway_error(RuntimeError("secret detail"))
        assert body["_status"] == 500
        assert body["error"]["code"] == "internal_error"
        assert "secret detail" not in str(body)

    def test_anthropic_shaped_body(self):
        service = _service_harness(_fake_handler())
        body = service.map_gateway_error(
            AllProvidersFailedError("boom"), anthropic=True
        )
        assert body["_status"] == 502
        assert body["type"] == "error"
        assert body["error"]["type"] == "api_error"


class TestGatewayHelpers:
    def test_parse_tier_valid(self):
        import core.llm.gateway.gateway_service as gs

        assert gs._parse_tier("micro") == CognitiveTier.MICRO

    def test_parse_tier_invalid(self):
        import core.llm.gateway.gateway_service as gs

        assert gs._parse_tier("quantum") is None

    def test_get_gateway_enabled(self):
        import core.llm.gateway.gateway_service as gs

        assert gs.get_gateway_enabled() == gs.GATEWAY_ENABLED

    def test_require_gateway_enabled_when_on(self):
        import core.llm.gateway.gateway_service as gs

        gs.require_gateway_enabled()

    def test_require_gateway_enabled_when_off(self):
        import core.llm.gateway.gateway_service as gs

        with patch("core.llm.gateway.gateway_service.gateway_enabled", return_value=False):
            with pytest.raises(HTTPException) as ei:
                gs.require_gateway_enabled()
            assert ei.value.status_code == 404

    def test_get_user_or_none(self):
        import core.llm.gateway.gateway_service as gs

        user = MagicMock()
        identity = GatewayIdentity(
            user_id="u-1", tenant_id="t-1", workspace_id="w", auth_method="api_key", user=user
        )
        assert gs.get_user_or_none(identity) is user
