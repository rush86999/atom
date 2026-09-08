"""Computer use with gpt-6-astra — end-to-end wiring tests (Sept 2026).

Pins the chain that lets the computer-use loop actually run on astra:

1. Capability inference: astra is vision+tools capable in the pricing cache
   (bare id AND litellm composite id), so vision/required-tools routing
   keeps it as a candidate instead of silently dropping it.
2. Routing: task_type="computer_use" classifies ADVANCED (which carries the
   frontier-reserved gate's difficulty signal) and requires tool support;
   the gate itself survives composite catalog ids.
3. LLM layer: embedded image content-parts are lifted into image_payload so
   vision routing sees them; the transcript's final user turn is sent exactly
   once (no duplication); explicit max_tokens reaches the provider request.
4. LuxModel loop: screenshot -> ONE action decision -> execute -> fresh
   screenshot, with governance hard-stop, step budget, three-failure abort,
   coordinate clamping, and JPEG-downscaled payloads (cost control).
"""

import os
os.environ["TESTING"] = "1"

import base64
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers (adapted from tests/test_covpush_byok_gen.py and
# tests/test_bpc_frontier_reserved_gate.py)
# ---------------------------------------------------------------------------


def _make_handler():
    from core.llm.byok_handler import BYOKHandler

    with patch("core.llm.byok_handler.get_byok_manager", return_value=Mock()), \
         patch("core.llm.byok_handler.llm_usage_tracker",
               Mock(is_budget_exceeded=Mock(return_value=False),
                    is_trial_expired=Mock(return_value=False),
                    record=Mock())):
        h = BYOKHandler(workspace_id="ws-1", tenant_id="t-1")
    h.rate_tracker = Mock()
    h.health_monitor = Mock()
    h.health_monitor.health_scores = {}
    h.health_monitor.record_call = Mock()
    h._is_trial_restricted = Mock(return_value=False)
    return h


def _response_mock(content="ok"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content),
                                 finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def _standard_patches(handler, options):
    client = Mock()
    client.chat.completions.create = Mock(return_value=_response_mock())
    handler.clients = {"openai": client}
    handler.async_clients = {}
    handler.get_ranked_providers = AsyncMock(return_value=options)
    handler._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
    handler._is_trial_restricted = Mock(return_value=False)
    fetcher = Mock()
    fetcher.estimate_cost = Mock(return_value=0.001)
    handler.cache_router = Mock()
    handler.cache_router.record_cache_outcome = Mock()
    tracker = Mock()
    tracker.is_budget_exceeded = Mock(return_value=False)
    return client, fetcher, tracker


def _null_db():
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.all.return_value = []
    return db


def _session_ctx(db):
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        yield db

    return ctx


# ---------------------------------------------------------------------------
# 1. Capability inference
# ---------------------------------------------------------------------------


class TestAstraCapabilityInference:
    @pytest.mark.parametrize("model_id", ["gpt-6-astra", "openai/gpt-6-astra"])
    @pytest.mark.parametrize("mode", ["chat", "reasoning"])
    def test_vision_and_tools(self, model_id, mode):
        from core.dynamic_pricing_fetcher import DynamicPricingFetcher

        fetcher = DynamicPricingFetcher()
        caps = fetcher._infer_capabilities({
            model_id: {
                "input_cost_per_token": 0.00001,
                "output_cost_per_token": 0.00005,
                "max_tokens": 128000,
                "max_input_tokens": 1050000,
                "litellm_provider": "openai",
                "mode": mode,
                "source": "litellm",
            }
        })
        assert caps[model_id]["supports_vision"] is True, (model_id, mode)
        # mode=="reasoning" must NOT zero tool support for the gpt-6 family —
        # that would lock astra out of agentic/computer_use routing.
        assert caps[model_id]["supports_tools"] is True, (model_id, mode)

    def test_computer_use_capability_score(self):
        from core.benchmarks import get_capability_score

        assert get_capability_score("gpt-6-astra", "computer_use") == 97

    def test_learning_router_spec_has_vision(self):
        from core.learning_llm_router import LearningBasedRouter, ModelCapability

        router = LearningBasedRouter(db=Mock())
        spec = router._model_registry["gpt-6-astra"]
        assert ModelCapability.VISION in spec.capabilities


# ---------------------------------------------------------------------------
# 2. Routing
# ---------------------------------------------------------------------------


class TestComputerUseRouting:
    def test_complexity_advanced_even_for_trivial_prompt(self):
        h = _make_handler()
        assert h.analyze_query_complexity(
            "open calculator", task_type="computer_use"
        ).name == "ADVANCED"

    def test_requires_tools_predicate(self):
        from core.llm.byok_handler import _task_requires_tools

        assert _task_requires_tools(None, "computer_use") is True
        assert _task_requires_tools("agent-1", None) is True
        assert _task_requires_tools(None, "chat") is False

    def test_frontier_gate_survives_composite_ids(self):
        """Litellm catalogs key astra as openai/gpt-6-astra — the exact-key
        gate lookup used to miss it, letting the flagship escape the
        frontier-reserved floor entirely."""
        from core.llm.byok_handler import BYOKHandler, QueryComplexity

        h = _make_handler()
        h.clients = {"openai": MagicMock()}
        h.env_key_providers = {"openai"}
        h.rate_tracker.get_headroom = MagicMock(return_value=1.0)
        h.rate_tracker.get_model_headroom = MagicMock(return_value=1.0)
        h.rate_tracker.get_model_weight = MagicMock(return_value=1.0)
        h.rate_tracker.get_max_context = MagicMock(return_value=None)
        h.cache_router.calculate_effective_cost = MagicMock(
            side_effect=lambda model, provider, estimated_tokens, turn_index=0, **kw: 30.0 / 1e6
        )
        h.excluded_models = set()

        fetcher = MagicMock()
        fetcher.pricing_cache = {
            "openai/gpt-6-astra": {
                "litellm_provider": "openai",
                "input_cost_per_token": 5e-6,
                "output_cost_per_token": 25e-6,
                "max_input_tokens": 1_000_000,
            },
        }

        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=fetcher,
        ), patch("core.llm.byok_handler.get_db_session",
                 _session_ctx(_null_db())), \
             patch("core.database.get_db_session", _session_ctx(_null_db())):
            below = list(h.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=False))
            top = list(h.get_ranked_providers(
                QueryComplexity.ADVANCED, is_managed_service=False))

        assert "openai/gpt-6-astra" not in [m for _, m in below]
        assert "openai/gpt-6-astra" in [m for _, m in top]

    def test_computer_use_task_passes_tools_requirement(self):
        """generate_response must rank with requires_tools for computer_use
        turns (tool-blind candidates can't serve the action-JSON loop)."""
        import asyncio

        h = _make_handler()
        client, fetcher, tracker = _standard_patches(h, [("openai", "gpt-6-astra")])
        h._model_supports_vision = Mock(return_value=True)
        with patch("core.llm.byok_handler.get_db_session",
                   _session_ctx(_null_db())), patch(
                "core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            out = asyncio.run(h.generate_response("click the button",
                                                  task_type="computer_use"))
        assert out == "ok"
        rank_kwargs = h.get_ranked_providers.call_args.kwargs
        assert rank_kwargs.get("requires_tools") is True


# ---------------------------------------------------------------------------
# 3. LLM layer — generate_completion multimodal + max_tokens
# ---------------------------------------------------------------------------


class TestGenerateCompletionMultimodal:
    def _service(self):
        from core.llm_service import LLMService

        svc = SimpleNamespace()
        svc._workspace_id = "ws-1"
        svc._resolve_governance_model = lambda ws, model, **kw: model
        handler = AsyncMock()
        handler.generate_response = AsyncMock(return_value="answer")
        handler._last_used_model = "gpt-6-astra"
        handler._last_used_provider = "openai"
        handler._last_reasoning = None
        svc._get_handler = lambda **kw: handler
        svc._token_counter = MagicMock()
        svc._token_counter.count_tokens = MagicMock(return_value=5)
        svc._context_validator = MagicMock()
        svc._context_validator.estimate_request_tokens = MagicMock(return_value=5)
        svc.estimate_tokens = MagicMock(return_value=5)
        svc.get_provider = MagicMock(return_value=MagicMock(value="openai"))
        return svc, handler

    def _run(self, svc, **call_kwargs):
        import asyncio
        from core.llm_service import LLMService

        return asyncio.run(
            LLMService.generate_completion(svc, **call_kwargs)
        )

    def test_embedded_image_lifted_to_image_payload(self):
        svc, handler = self._service()
        img_b64 = base64.b64encode(b"fakepng").decode()
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "what is on screen?"},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            ],
        }]
        result = self._run(svc, messages=messages, model="gpt-6-astra")
        assert result["success"] is True
        kwargs = handler.generate_response.call_args.kwargs
        # Vision routing contract: raw base64 in image_payload (data: prefix
        # stripped — the handler re-wraps), not an embedded content part.
        assert kwargs["image_payload"] == img_b64
        # Prompt extraction sees TEXT, not the content-part list.
        assert kwargs["prompt"] == "what is on screen?"
        # The normalized message carries plain text content.
        assert kwargs["messages"][0]["content"] == "what is on screen?"

    def test_explicit_image_payload_wins(self):
        svc, handler = self._service()
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "describe"},
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64,embedded"}},
            ],
        }]
        self._run(svc, messages=messages, image_payload="explicitraw")
        assert handler.generate_response.call_args.kwargs["image_payload"] == "explicitraw"

    def test_max_tokens_forwarded_only_when_explicit(self):
        svc, handler = self._service()
        self._run(svc, messages=[{"role": "user", "content": "hi"}],
                  max_tokens=1234)
        assert handler.generate_response.call_args.kwargs["max_tokens"] == 1234

        svc2, handler2 = self._service()
        self._run(svc2, messages=[{"role": "user", "content": "hi"}])
        assert "max_tokens" not in handler2.generate_response.call_args.kwargs


# ---------------------------------------------------------------------------
# 3b. generate_response request assembly
# ---------------------------------------------------------------------------


class TestGenerateResponseAssembly:
    def _drive(self, **call_kwargs):
        import asyncio

        h = _make_handler()
        client, fetcher, tracker = _standard_patches(h, [("openai", "gpt-4o")])
        h._model_supports_vision = Mock(return_value=True)
        with patch("core.llm.byok_handler.get_db_session",
                   _session_ctx(_null_db())), patch(
                "core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            out = asyncio.run(h.generate_response(**call_kwargs))
        create_kwargs = client.chat.completions.create.call_args.kwargs
        return h, out, create_kwargs

    def test_image_attaches_to_last_user_message_no_duplication(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "look at this"},
        ]
        _, out, kw = self._drive(prompt="look at this", messages=messages,
                                 image_payload="rawb64")
        assert out == "ok"
        sent = kw["messages"]
        # Exactly one user turn, carrying text + image parts — previously the
        # prompt text was appended AGAIN as a second user message.
        user_msgs = [m for m in sent if m["role"] == "user"]
        assert len(user_msgs) == 1
        content = user_msgs[-1]["content"]
        assert isinstance(content, list)
        texts = [p["text"] for p in content if p["type"] == "text"]
        imgs = [p for p in content if p["type"] == "image_url"]
        assert texts == ["look at this"]
        assert len(imgs) == 1
        assert imgs[0]["image_url"]["url"] == "data:image/jpeg;base64,rawb64"

    def test_data_url_payload_not_double_wrapped(self):
        messages = [{"role": "user", "content": "x"}]
        _, _, kw = self._drive(prompt="x", messages=messages,
                               image_payload="data:image/png;base64,AAA")
        imgs = [p for m in kw["messages"] if m["role"] == "user"
                for p in (m["content"] if isinstance(m["content"], list) else [])
                if p["type"] == "image_url"]
        assert imgs[0]["image_url"]["url"] == "data:image/png;base64,AAA"

    def test_text_turn_not_duplicated(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
        ]
        _, _, kw = self._drive(prompt="hello", messages=messages)
        user_texts = [m["content"] for m in kw["messages"] if m["role"] == "user"]
        assert user_texts == ["hello"]

    def test_fallback_attempt_does_not_stack_images(self):
        """A failed first provider must not leave a second image glued onto
        the transcript for the retry — each attempt starts from the pristine
        caller transcript."""
        import asyncio

        h = _make_handler()
        client, fetcher, tracker = _standard_patches(
            h, [("openai", "gpt-4o"), ("deepseek", "deepseek-v3.2")])
        h._model_supports_vision = Mock(return_value=True)
        responses = [
            Exception("400 bad"),   # first provider attempt fails
            _response_mock("retry ok"),
        ]
        client.chat.completions.create = Mock(side_effect=responses)
        h.clients["deepseek"] = client  # same stub client, second provider

        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "look"},
        ]
        with patch("core.llm.byok_handler.get_db_session",
                   _session_ctx(_null_db())), patch(
                "core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            out = asyncio.run(h.generate_response(
                prompt="look", messages=messages, image_payload="rawb64"))

        assert out == "retry ok"
        assert client.chat.completions.create.call_count == 2
        second_messages = client.chat.completions.create.call_args_list[1].kwargs["messages"]
        imgs = [p for m in second_messages if m["role"] == "user"
                for p in (m["content"] if isinstance(m["content"], list) else [])
                if p["type"] == "image_url"]
        assert len(imgs) == 1  # exactly one image, not stacked

    def test_max_tokens_forwarded_to_provider(self):
        from core.llm.byok_handler import _DEFAULT_COMPLETION_MAX_TOKENS

        _, _, kw = self._drive(prompt="hi", max_tokens=777)
        assert kw["max_tokens"] == 777
        _, _, kw2 = self._drive(prompt="hi")
        assert kw2["max_tokens"] == _DEFAULT_COMPLETION_MAX_TOKENS


# ---------------------------------------------------------------------------
# 4. LuxModel agentic loop
# ---------------------------------------------------------------------------


def _decision(action_type, params=None, done=False, confidence=0.9):
    payload = {
        "reasoning": "test", "done": done, "summary": "finished" if done else "",
    }
    if action_type and not done:
        payload["action"] = {
            "action_type": action_type,
            "parameters": params or {},
            "confidence": confidence,
        }
    return json.dumps(payload)


@pytest.fixture
def lux():
    with patch("ai.lux_model.LLM_SERVICE_AVAILABLE", True), \
         patch("ai.lux_model.LLMService", MagicMock()), \
         patch("ai.lux_model.PYAUTOGUI_AVAILABLE", True), \
         patch("ai.lux_model.pyautogui", MagicMock()) as pygui:
        from ai.lux_model import LuxModel

        model = LuxModel(tenant_id="t-1")
        model.llm_service = AsyncMock()
        model.capture_screen = AsyncMock(return_value=None)
        model.screen_width = 1920
        model.screen_height = 1080
        model._pygui = pygui
        yield model


def _png(max_edge=3000):
    from PIL import Image

    img = Image.new("RGB", (max_edge, max_edge // 2), (30, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestRunTaskLoop:
    def test_default_model_is_astra(self, lux):
        assert lux.model_config["model"] == "gpt-6-astra"

    def test_happy_path_click_then_done(self, lux):
        lux.llm_service.generate_completion = AsyncMock(side_effect=[
            {"success": True, "content": _decision("click", {"coordinates": [100, 200]})},
            {"success": True, "content": _decision(None, done=True)},
        ])
        result = asyncio_run(lux.run_task("click the login button"))
        assert result["done"] is True
        assert result["steps"] == 1
        assert result["actions"][0]["success"] is True
        assert result["actions"][0]["action_type"] == "click"
        lux._pygui.click.assert_called_once_with(100, 200)

        call = lux.llm_service.generate_completion.call_args.kwargs
        assert call["task_type"] == "computer_use"
        assert call["model"] == "gpt-6-astra"
        assert call["max_tokens"] == 4096

    def test_screenshot_downscaled_jpeg_payload(self, lux):
        from PIL import Image

        lux.capture_screen = AsyncMock(return_value=Image.new("RGB", (3000, 1500), "red"))
        lux.llm_service.generate_completion = AsyncMock(return_value={
            "success": True, "content": _decision(None, done=True)})
        asyncio_run(lux.run_task("do nothing"))
        payload = lux.llm_service.generate_completion.call_args.kwargs["image_payload"]
        assert not payload.startswith("data:")  # raw base64 contract
        decoded = Image.open(io.BytesIO(base64.b64decode(payload)))
        assert decoded.format == "JPEG"
        assert max(decoded.size) <= 1568

    def test_governance_blocks_hard_stop(self, lux):
        lux.governance_callback = AsyncMock(return_value=False)
        lux.llm_service.generate_completion = AsyncMock(return_value={
            "success": True, "content": _decision("click", {"coordinates": [1, 1]})})
        result = asyncio_run(lux.run_task("delete everything"))
        assert result["success"] is False
        assert "governance" in result["error"].lower()
        assert result["actions"][0]["blocked_by_governance"] is True
        lux._pygui.click.assert_not_called()

    def test_step_budget_respected(self, lux):
        lux.llm_service.generate_completion = AsyncMock(return_value={
            "success": True, "content": _decision("click", {"coordinates": [5, 5]})})
        result = asyncio_run(lux.run_task("never done", max_steps=3,
                                          step_settle_seconds=0))
        assert result["steps"] == 3
        assert result["done"] is False

    def test_three_consecutive_failures_abort(self, lux):
        lux._pygui.click = MagicMock(side_effect=RuntimeError("nope"))
        lux.llm_service.generate_completion = AsyncMock(return_value={
            "success": True, "content": _decision("click", {"coordinates": [5, 5]})})
        result = asyncio_run(lux.run_task("failing", max_steps=10,
                                          step_settle_seconds=0))
        assert result["steps"] == 3
        assert all(a["success"] is False for a in result["actions"])

    def test_coordinates_clamped_to_screen(self, lux):
        lux.llm_service.generate_completion = AsyncMock(side_effect=[
            {"success": True, "content": _decision("click", {"coordinates": [5000, -5]})},
            {"success": True, "content": _decision(None, done=True)},
        ])
        asyncio_run(lux.run_task("click far away"))
        lux._pygui.click.assert_called_once_with(1919, 0)

    def test_execute_command_delegates_to_run_task(self, lux):
        lux.run_task = AsyncMock(return_value={"success": True})
        asyncio_run(lux.execute_command("open notes"))
        lux.run_task.assert_awaited_once_with("open notes")

    def test_interpret_command_compat_actions_list(self, lux):
        """browser_engine/agent.py consumes interpret_command's multi-action
        list — that contract must keep working."""
        lux.llm_service.generate_completion = AsyncMock(return_value={
            "success": True,
            "content": json.dumps({"actions": [
                {"action_type": "type", "parameters": {"text": "hello"}},
            ]}),
        })
        actions = asyncio_run(lux.interpret_command("type hello", screenshot=None))
        assert len(actions) == 1
        assert actions[0].action_type.value == "type"


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 5. Config + registry
# ---------------------------------------------------------------------------


class TestConfigAndRegistry:
    def test_default_and_env_override_model(self, monkeypatch):
        from core.lux_config import lux_config

        assert lux_config.get_computer_use_model() == "gpt-6-astra"
        monkeypatch.setenv("ATOM_COMPUTER_USE_MODEL", "claude-3-5-sonnet-20241022")
        assert lux_config.get_computer_use_model() == "claude-3-5-sonnet-20241022"

    def test_max_steps_env(self, monkeypatch):
        from core.lux_config import lux_config

        monkeypatch.setenv("ATOM_COMPUTER_USE_MAX_STEPS", "2")
        assert lux_config.get_max_steps() == 2
        monkeypatch.setenv("ATOM_COMPUTER_USE_MAX_STEPS", "bogus")
        assert lux_config.get_max_steps() == lux_config.DEFAULT_MAX_STEPS

    def test_registry_registers_astra_with_computer_use(self):
        from core.llm.registry.service import LLMRegistryService

        service = LLMRegistryService.__new__(LLMRegistryService)
        service.db = Mock()

        upserted = SimpleNamespace(
            capabilities=["vision", "tools", "computer_use", "agentic"],
            sync_capabilities=Mock(),
        )
        service.upsert_model = Mock(return_value=upserted)
        service.register_lux_model = Mock(return_value=None)

        registered = service.register_computer_use_models("tenant-1")

        assert upserted in registered
        data = service.upsert_model.call_args.args[1]
        assert data["model_name"] == "gpt-6-astra"
        assert "computer_use" in data["capabilities"]
