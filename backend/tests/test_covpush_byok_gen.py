"""
Coverage-push tests for core.llm.byok_handler generation paths (tests-only).

Covers generate_response, chat_completion, and stream_completion with mocked
clients — the largest previously-untested surface.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.llm.byok_handler import (
    AllProvidersFailedError,
    BYOKHandler,
    GatewayBlockedError,
    QueryComplexity,
)

pytestmark = pytest.mark.asyncio


def make_handler():
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


def usage_mock(prompt=10, completion=5):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def response_mock(content="hello world", finish="stop", usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content),
                                 finish_reason=finish)],
        usage=usage,
    )


def ctx_mock(db):
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        yield db

    return ctx


def patch_session(db):
    return patch("core.llm.byok_handler.get_db_session", ctx_mock(db))


def pro_tenant_db():
    """DB mock returning a workspace + non-free tenant (structured path)."""
    workspace = SimpleNamespace(tenant_id="t-2")
    tenant = SimpleNamespace(plan_type="pro")
    db = Mock()
    firsts = iter([workspace, tenant])

    def fake_query(model):
        q = Mock()
        q.filter.return_value.first.side_effect = lambda: next(firsts, None)
        return q

    db.query.side_effect = fake_query
    return db


def standard_patches(handler, options, usage=None, content="hello world", cost=0.001):
    client = Mock()
    client.chat.completions.create = Mock(return_value=response_mock(content, usage=usage or usage_mock()))
    handler.clients = {"openai": client, "deepseek": Mock()}
    handler.async_clients = {}
    handler.get_ranked_providers = AsyncMock(return_value=options)
    handler._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
    handler._is_trial_restricted = Mock(return_value=False)
    fetcher = Mock()
    fetcher.estimate_cost = Mock(return_value=cost)
    handler.cache_router = Mock()
    handler.cache_router.record_cache_outcome = Mock()
    usage_tracker = Mock()
    usage_tracker.is_budget_exceeded = Mock(return_value=False)
    return client, fetcher, usage_tracker


class TestGenerateResponse:
    async def test_trial_restricted(self):
        h = make_handler()
        h._is_trial_restricted = Mock(return_value=True)
        assert "Trial Expired" in await h.generate_response("hi")

    async def test_no_clients_agentic_demo_market(self):
        h = make_handler()
        h.clients = {}
        out = await h.generate_response("Can you check my inbox and analyze", task_type="agentic")
        assert json.loads(out)["action"] == "perform_market_analysis"

    async def test_no_clients_agentic_demo_done(self):
        h = make_handler()
        h.clients = {}
        out = await h.generate_response("do something", task_type="agentic")
        assert json.loads(out)["action"] == "DONE"

    async def test_no_clients_plain(self):
        h = make_handler()
        h.clients = {}
        assert "not initialized" in await h.generate_response("hi")

    async def test_budget_exceeded(self):
        h = make_handler()
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(return_value=True)
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            out = await h.generate_response("hi")
        assert "BUDGET EXCEEDED" in out

    async def test_success_path(self):
        h = make_handler()
        client, fetcher, tracker = standard_patches(
            h, [("openai", "gpt-4o")], usage=usage_mock(10, 5))
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch_session(db), patch(
            "core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher
        ), patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            out = await h.generate_response("hello", task_type="chat")
        assert out == "hello world"
        assert h._last_used_model == "gpt-4o"
        assert h._last_used_provider == "openai"
        tracker.record.assert_called_once()
        client.chat.completions.create.assert_called_once()

    async def test_success_with_image_payload(self):
        h = make_handler()
        client, fetcher, tracker = standard_patches(
            h, [("openai", "gpt-4o")], usage=usage_mock(), content="vision ok")
        h._model_supports_vision = Mock(return_value=True)
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch_session(db):
            out = await h.generate_response("look", image_payload="http://img/x.png")
        assert out == "vision ok"

    async def test_vision_coordinated(self):
        h = make_handler()
        client, fetcher, tracker = standard_patches(
            h, [("openai", "gpt-4o")], usage=usage_mock(), content="coordinated")
        h._model_supports_vision = Mock(return_value=False)
        h._get_coordinated_vision_description = AsyncMock(return_value="visual description")
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch_session(db):
            out = await h.generate_response("click", image_payload="data:image")
        assert out == "coordinated"

    async def test_tenant_key_flips_to_byok(self):
        h = make_handler()
        client, fetcher, tracker = standard_patches(h, [("openai", "gpt-4o")])
        workspace = SimpleNamespace(tenant_id="t-2")
        tenant = SimpleNamespace(plan_type="pro")
        db = Mock()
        firsts = iter([workspace, tenant])

        def fake_query(model):
            q = Mock()
            q.filter.return_value.first.side_effect = lambda: next(firsts, None)
            return q

        db.query.side_effect = fake_query
        h.byok_manager.get_tenant_api_key = Mock(return_value="tenant-key")
        with patch_session(db), patch(
            "core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher
        ), patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            out = await h.generate_response("hi", task_type="chat")
        assert out == "hello world"

    async def test_no_eligible_providers(self):
        h = make_handler()
        standard_patches(h, [])
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch_session(db):
            out = await h.generate_response("hi")
        assert "No eligible LLM providers" in out

    async def test_all_providers_fail_apology(self):
        h = make_handler()
        client, fetcher, tracker = standard_patches(h, [("openai", "gpt-4o")])
        client.chat.completions.create = Mock(side_effect=RuntimeError("api down"))
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch_session(db):
            out = await h.generate_response("hi")
        assert "I'm sorry" in out
        h.health_monitor.record_call.assert_called()

    async def test_self_heal_retry_success(self):
        h = make_handler()
        client, fetcher, tracker = standard_patches(h, [("openai", "gpt-4o")])
        client.chat.completions.create = Mock(side_effect=[
            RuntimeError("400 unsupported param"),
            response_mock("healed answer", usage=usage_mock()),
        ])
        healer = Mock()
        healer.heal = Mock(return_value=SimpleNamespace(
            patched_kwargs={"model": "gpt-4o", "messages": [], "temperature": 0.7},
            rule="drop_param", patched_keys=["max_tokens"]))
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch_session(db), patch(
            "core.llm.routing.request_healer.get_request_healer", return_value=healer
        ):
            out = await h.generate_response("hi")
        assert out == "healed answer"
        assert client.chat.completions.create.call_count == 2

    async def test_self_heal_retry_fails_then_apology(self):
        h = make_handler()
        client, fetcher, tracker = standard_patches(h, [("openai", "gpt-4o")])
        client.chat.completions.create = Mock(side_effect=[
            RuntimeError("400 bad"), RuntimeError("400 still bad")])
        healer = Mock()
        healer.heal = Mock(return_value=SimpleNamespace(
            patched_kwargs={"model": "m"}, rule="r", patched_keys=[]))
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch_session(db), patch(
            "core.llm.routing.request_healer.get_request_healer", return_value=healer
        ):
            out = await h.generate_response("hi")
        assert "I'm sorry" in out

    async def test_cognitive_tier_override_invalid(self):
        h = make_handler()
        client, fetcher, tracker = standard_patches(
            h, [("openai", "gpt-4o")], usage=usage_mock(), content="tier ok")
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch_session(db), patch(
            "core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher
        ), patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            out = await h.generate_response("hi", cognitive_tier="bogus")
        assert out == "tier ok"

    async def test_outer_exception_returns_apology(self):
        h = make_handler()
        standard_patches(h, [("openai", "gpt-4o")])
        with patch("core.llm.byok_handler.get_db_session", side_effect=RuntimeError("boom")):
            out = await h.generate_response("hi")
        assert "I'm sorry, an error occurred" in out


class TestChatCompletion:
    async def test_no_clients(self):
        h = make_handler()
        h.clients = {}
        h.async_clients = {}
        with pytest.raises(ValueError, match="No available providers"):
            await h.chat_completion([], "m", "openai")

    async def test_budget_exceeded_blocks(self):
        h = make_handler()
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(return_value=True)
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            with pytest.raises(GatewayBlockedError):
                await h.chat_completion([], "m", "openai")

    async def test_budget_tracker_fail_closed(self):
        h = make_handler()
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(side_effect=RuntimeError("db down"))
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            with pytest.raises(GatewayBlockedError) as exc:
                await h.chat_completion([], "m", "openai")
        assert exc.value.reason == "budget_check_failed"

    async def test_trial_expired_blocks(self):
        h = make_handler()
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(return_value=False)
        tracker.is_trial_expired = Mock(return_value=False)
        tracker.is_trial_expired = Mock(return_value=True)
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            with pytest.raises(GatewayBlockedError) as exc:
                await h.chat_completion([], "m", "openai")
        assert exc.value.reason == "trial_expired"

    async def test_no_fallback_order(self):
        h = make_handler()
        h._get_provider_fallback_order = Mock(return_value=[])
        with pytest.raises(ValueError, match="No available providers for completion"):
            await h.chat_completion([], "m", "openai")

    async def test_success(self):
        h = make_handler()
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="answer"),
                                     finish_reason="stop")],
            usage=usage_mock(5, 3)))
        h.async_clients = {"openai": client}
        h.clients = {"openai": client}
        fetcher = Mock()
        fetcher.estimate_cost = Mock(return_value=0.01)
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(return_value=False)
        tracker.is_trial_expired = Mock(return_value=False)
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), patch(
            "core.llm.byok_handler.llm_usage_tracker", tracker
        ):
            result = await h.chat_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o", "openai", extra_kwargs={"top_p": 0.5})
        assert result["choices"][0]["message"]["content"] == "answer"
        assert result["usage"]["prompt_tokens"] == 5
        assert result["provider"] == "openai"
        tracker.record.assert_called_once()

    async def test_fallback_skip_unsupported_model(self):
        h = make_handler()
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="a"), finish_reason="stop")],
            usage=None))
        h.async_clients = {"openai": client}
        h.clients = {"openai": client, "anthropic": Mock()}
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(return_value=False)
        tracker.is_trial_expired = Mock(return_value=False)
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            result = await h.chat_completion([{"role": "user", "content": "hi"}],
                                             "claude-3", "openai")
        assert result["provider"] == "openai"

    async def test_heal_retry_success(self):
        h = make_handler()
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(side_effect=[
            RuntimeError("400 param"),
            SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="healed"), finish_reason="stop")],
                usage=None)])
        h.async_clients = {"openai": client}
        h.clients = {"openai": client}
        healer = Mock()
        healer.heal = Mock(return_value=SimpleNamespace(
            patched_kwargs={"model": "m"}, rule="r", patched_keys=["k"]))
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(return_value=False)
        tracker.is_trial_expired = Mock(return_value=False)
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker), patch(
            "core.llm.routing.request_healer.get_request_healer", return_value=healer
        ):
            result = await h.chat_completion([{"role": "user", "content": "hi"}], "m", "openai")
        assert result["choices"][0]["message"]["content"] == "healed"

    async def test_all_providers_failed(self):
        h = make_handler()
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError("down"))
        h.async_clients = {"openai": client}
        h.clients = {"openai": client}
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(return_value=False)
        tracker.is_trial_expired = Mock(return_value=False)
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            with pytest.raises(AllProvidersFailedError):
                await h.chat_completion([{"role": "user", "content": "hi"}], "m", "openai")

    async def test_no_client_for_provider(self):
        h = make_handler()
        h.async_clients = {"deepseek": AsyncMock()}
        h.clients = {"deepseek": Mock()}
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(return_value=False)
        tracker.is_trial_expired = Mock(return_value=False)
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            with pytest.raises(AllProvidersFailedError):
                await h.chat_completion([], "m", "openai")


class TestStreamCompletion:
    def _chunks(self, *texts):
        async def gen():
            for t in texts:
                yield SimpleNamespace(
                    choices=[SimpleNamespace(
                        delta=SimpleNamespace(content=t), finish_reason=None)])
            yield SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=None), finish_reason="stop")])
        return gen()

    async def test_no_clients(self):
        h = make_handler()
        h.clients = {}
        h.async_clients = {}
        with pytest.raises(ValueError, match="Streaming unavailable"):
            async for _ in h.stream_completion([], "m", "openai"):
                pass

    async def test_no_fallback_order(self):
        h = make_handler()
        h._get_provider_fallback_order = Mock(return_value=[])
        with pytest.raises(ValueError, match="No available providers for streaming"):
            async for _ in h.stream_completion([], "m", "openai"):
                pass

    async def test_stream_success(self):
        h = make_handler()
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=self._chunks("hel", "lo"))
        h.async_clients = {"openai": client}
        h.clients = {"openai": client}
        h._stash_decision_features = Mock(return_value=None)
        tokens = []
        async for token in h.stream_completion(
            [{"role": "user", "content": "hi"}], "gpt-4o", "openai"
        ):
            tokens.append(token)
        assert "".join(tokens) == "hello"
        h.health_monitor.record_call.assert_called()

    async def test_stream_fallback_to_second_provider(self):
        h = make_handler()
        bad = AsyncMock()
        bad.chat.completions.create = AsyncMock(side_effect=RuntimeError("down"))
        good = AsyncMock()
        good.chat.completions.create = AsyncMock(return_value=self._chunks("ok"))
        h.async_clients = {"openai": bad, "deepseek": good}
        h.clients = {"openai": bad, "deepseek": good}
        h._stash_decision_features = Mock(return_value=None)
        tokens = []
        async for token in h.stream_completion(
            [{"role": "user", "content": "hi"}], "deepseek-chat", "openai"
        ):
            tokens.append(token)
        assert "".join(tokens) == "ok"

    async def test_stream_governance_tracking(self):
        h = make_handler()
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=self._chunks("x"))
        h.async_clients = {"openai": client}
        h.clients = {"openai": client}
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        h._stash_decision_features = Mock(return_value=None)
        with patch("core.agent_governance_service.AgentGovernanceService") as gov_cls:
            gov_cls.return_value.record_outcome = AsyncMock()
            tokens = []
            async for token in h.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o", "openai",
                agent_id="agent-1", db=db, task_type="chat"
            ):
                tokens.append(token)
        assert "".join(tokens) == "x"
        db.add.assert_called()
        gov_cls.return_value.record_outcome.assert_awaited_once()


class TestStructuredResponse:
    async def test_trial_restricted(self):
        h = make_handler()
        h._is_trial_restricted = Mock(return_value=True)
        assert await h.generate_structured_response("p", "sys", dict) is None

    async def test_no_clients(self):
        h = make_handler()
        h.clients = {}
        assert await h.generate_structured_response("p", "sys", dict) is None

    async def test_instructor_unavailable(self):
        h = make_handler()
        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", False):
            assert await h.generate_structured_response("p", "sys", dict) is None

    async def test_free_tier_managed_blocked(self):
        h = make_handler()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch_session(db):
            assert await h.generate_structured_response("p", "sys", dict) is None

    async def test_success(self):
        h = make_handler()
        result = SimpleNamespace(
            _raw_response=SimpleNamespace(usage=usage_mock(3, 2), finish_reason="stop"))
        instructor_client = Mock()
        instructor_client.chat.completions.create = Mock(return_value=result)
        h.clients = {"openai": Mock()}
        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), patch(
            "core.llm.byok_handler.instructor"
        ) as instr, patch("core.hallucination_config.is_moa_enabled", return_value=False):
            instr.from_openai = Mock(return_value=instructor_client)
            h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
            with patch_session(pro_tenant_db()):
                out = await h.generate_structured_response("p", "sys", dict)
        assert out is result
        instr.from_openai.assert_called_once()

    async def test_success_with_truncation(self):
        h = make_handler()
        result = SimpleNamespace(_raw_response=SimpleNamespace(usage=None, finish_reason="stop"))
        instructor_client = Mock()
        instructor_client.chat.completions.create = Mock(return_value=result)
        h.clients = {"openai": Mock()}
        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), patch(
            "core.llm.byok_handler.instructor"
        ) as instr, patch("core.hallucination_config.is_moa_enabled", return_value=False):
            instr.from_openai = Mock(return_value=instructor_client)
            h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
            h.get_context_window = Mock(return_value=100)
            with patch_session(pro_tenant_db()), patch(
                "core.turn_fact_queue.get_extraction_queue",
                side_effect=RuntimeError("no queue")):
                out = await h.generate_structured_response("z" * 5000, "sys", dict)
        assert out is result

    async def test_schema_error_cascades(self):
        h = make_handler()
        from pydantic import ValidationError

        class Model:
            pass

        def failing_create(*args, **kwargs):
            if not getattr(failing_create, "cascaded", False):
                failing_create.cascaded = True
                raise ValidationError.from_exception_data("x", [])
            return SimpleNamespace(_raw_response=SimpleNamespace(usage=None, finish_reason="stop"))

        instructor_client = Mock()
        instructor_client.chat.completions.create = Mock(side_effect=failing_create)
        h.clients = {"openai": Mock()}
        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), patch(
            "core.llm.byok_handler.instructor"
        ) as instr, patch("core.hallucination_config.is_moa_enabled", return_value=False), \
             patch("core.hallucination_config.is_frontier_model", return_value=False), \
             patch("core.hallucination_config.get_frontier_model_for_provider",
                   return_value="gpt-5"):
            instr.from_openai = Mock(return_value=instructor_client)
            h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
            with patch_session(pro_tenant_db()):
                out = await h.generate_structured_response("p", "sys", dict, cascade=True)
        assert out is not None

    async def test_all_fail_returns_none(self):
        h = make_handler()
        instructor_client = Mock()
        instructor_client.chat.completions.create = Mock(side_effect=RuntimeError("down"))
        h.clients = {"openai": Mock()}
        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), patch(
            "core.llm.byok_handler.instructor"
        ) as instr, patch("core.hallucination_config.is_moa_enabled", return_value=False):
            instr.from_openai = Mock(return_value=instructor_client)
            h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
            with patch_session(pro_tenant_db()):
                out = await h.generate_structured_response("p", "sys", dict)
        assert out is None

    async def test_moa_dispatch(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.generate_structured_moa = AsyncMock(return_value="moa-result")
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "m1"), ("deepseek", "m2")])
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.COMPLEX)
        with patch("core.hallucination_config.is_moa_enabled", return_value=True):
            with patch_session(pro_tenant_db()):
                out = await h.generate_structured_response("p", "sys", dict)
        assert out == "moa-result"

    async def test_moa_not_eligible_simple(self):
        h = make_handler()
        result = SimpleNamespace(_raw_response=SimpleNamespace(usage=None, finish_reason="stop"))
        instructor_client = Mock()
        instructor_client.chat.completions.create = Mock(return_value=result)
        h.clients = {"openai": Mock()}
        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), patch(
            "core.llm.byok_handler.instructor"
        ) as instr, patch("core.hallucination_config.is_moa_enabled", return_value=True):
            instr.from_openai = Mock(return_value=instructor_client)
            h.get_ranked_providers = AsyncMock(return_value=[("openai", "m1"), ("deepseek", "m2")])
            with patch_session(pro_tenant_db()):
                out = await h.generate_structured_response("hi", "sys", dict)
        assert out is result


class TestMoaHelpers:
    def test_moa_eligible(self, ):
        h = make_handler()
        assert h._moa_eligible(QueryComplexity.COMPLEX, None) is True
        assert h._moa_eligible(QueryComplexity.ADVANCED, None) is True
        assert h._moa_eligible(QueryComplexity.SIMPLE, "code") is True
        assert h._moa_eligible(QueryComplexity.SIMPLE, None) is False

    def test_render_sample(self):
        sample = SimpleNamespace(model_dump=lambda: {"a": 1})
        assert BYOKHandler._render_sample(sample) == '{"a": 1}'
        sample2 = SimpleNamespace(dict=lambda: {"b": 2})
        assert BYOKHandler._render_sample(sample2) == '{"b": 2}'
        assert BYOKHandler._render_sample("plain") == "plain"
        broken = SimpleNamespace(model_dump=lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert BYOKHandler._render_sample(broken) == str(broken)

    def test_build_moa_aggregator_prompt(self):
        h = make_handler()
        prompt = h._build_moa_aggregator_prompt("q", ["a", "b"])
        assert "[CANDIDATE ANSWER 1]" in prompt
        assert "[USER REQUEST]:\nq" in prompt

    async def test_generate_structured_moa_single_valid(self):
        h = make_handler()
        with patch("core.hallucination_config.get_moa_samples", return_value=3):
            h.generate_structured_response = AsyncMock(side_effect=[None, "sample2"])
            out = await h.generate_structured_moa(
                "p", "s", dict, 0.2, None, None, None,
                [("a", "m1"), ("b", "m2")], "free", True, QueryComplexity.COMPLEX, False)
        assert out == "sample2"

    async def test_generate_structured_moa_no_valid(self):
        h = make_handler()
        with patch("core.hallucination_config.get_moa_samples", return_value=2):
            h.generate_structured_response = AsyncMock(return_value=None)
            out = await h.generate_structured_moa(
                "p", "s", dict, 0.2, None, None, None,
                [("a", "m1"), ("b", "m2")], "free", True, QueryComplexity.COMPLEX, False)
        assert out is None

    async def test_generate_structured_moa_aggregator_fallback(self):
        h = make_handler()
        with patch("core.hallucination_config.get_moa_samples", return_value=2), patch(
            "core.llm.self_consistency_voter.SelfConsistencyVoter.is_irreversible",
            return_value=True):
            h.generate_structured_response = AsyncMock(side_effect=["s1", "s2", None])
            out = await h.generate_structured_moa(
                "p", "s", dict, 0.2, None, None, None,
                [("a", "m1"), ("b", "m2")], "free", True, QueryComplexity.COMPLEX, False)
        assert out == "s1"
