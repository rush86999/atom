"""Coverage wave 11d — streaming governance/AgentExecution path, vision
coordination, context-window/truncation helpers, trial gate, decision stash.
"""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import BYOKHandler


def _make_handler():
    with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.get_db_session"):
        handler = BYOKHandler(workspace_id="default", tenant_id="default")
    handler.clients = {"openai": MagicMock()}
    handler.async_clients = {"openai": MagicMock()}
    handler.health_monitor = MagicMock()
    handler.health_monitor.health_scores = {}
    handler.byok_manager.is_configured = MagicMock(return_value=False)
    handler.byok_manager.get_api_key = MagicMock(return_value=None)
    return handler


def _chunk(delta_text):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            delta=SimpleNamespace(content=delta_text),
            finish_reason=None,
        )]
    )


class _AsyncGenClient:
    def __init__(self, chunks, error=None):
        self._chunks = chunks
        self._error = error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        if self._error:
            raise self._error
        for c in self._chunks:
            yield c


# =========================================================================== #
# Streaming governance path (agent_id + db -> AgentExecution lifecycle)
# =========================================================================== #
class TestStreamGovernance:
    @pytest.mark.asyncio
    async def test_execution_record_lifecycle(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler()
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=_AsyncGenClient([_chunk("hi")]).chat.completions.create
        )
        db = MagicMock()
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False), \
             patch(
                 "core.agent_governance_service.AgentGovernanceService",
             ) as m_gov:
            tokens = [t async for t in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o-mini", "openai",
                agent_id="a-1", db=db,
            )]
        assert "".join(tokens) == "hi"
        # execution record created + committed; completion marks it done
        assert db.add.called and db.commit.called
        exec_obj = db.add.call_args.args[0]
        assert exec_obj.agent_id == "a-1"
        assert exec_obj.status == "completed"
        m_gov.assert_called()

    @pytest.mark.asyncio
    async def test_governance_disabled_skips_execution_record(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler()
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=_AsyncGenClient([_chunk("hi")]).chat.completions.create
        )
        db = MagicMock()
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False), \
             patch.dict(os.environ, {"STREAMING_GOVERNANCE_ENABLED": "false"}):
            tokens = [t async for t in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o-mini", "openai",
                agent_id="a-1", db=db,
            )]
        assert "".join(tokens) == "hi"
        assert not db.add.called  # no execution record without governance

    @pytest.mark.asyncio
    async def test_tracking_error_does_not_break_stream(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler()
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=_AsyncGenClient([_chunk("hi")]).chat.completions.create
        )
        db = MagicMock()
        db.commit.side_effect = [None, RuntimeError("db down")]
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            tokens = [t async for t in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o-mini", "openai",
                agent_id="a-1", db=db,
            )]
        assert "".join(tokens) == "hi"  # tokens still flow despite tracking error


# =========================================================================== #
# Vision coordination (generate_response)
# =========================================================================== #
class TestVisionCoordination:
    async def _run_generate(self, handler, **kw):
        from core.llm.byok_handler import llm_usage_tracker

        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            return await handler.generate_response(
                "What is in this image?", task_type="chat", **kw
            )

    @pytest.mark.asyncio
    async def test_non_vision_primary_gets_coordinated_description(self):
        handler = _make_handler()
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o-mini")]
        )
        handler.get_optimal_provider = AsyncMock(return_value=("openai", "gpt-4o-mini"))
        handler._rerank_with_learning = AsyncMock(
            side_effect=lambda opts, *a, **k: opts
        )
        handler._model_supports_vision = MagicMock(return_value=False)
        handler._get_coordinated_vision_description = AsyncMock(
            return_value="The image shows a red car on a highway."
        )
        handler.clients["openai"].chat.completions.create = MagicMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="ok"),
                    finish_reason="stop",
                )],
                usage=None,
            )
        )
        result = await self._run_generate(
            handler, image_payload="base64data=="
        )
        assert result == "ok"
        # coordinated description was used and the image payload cleared
        handler._get_coordinated_vision_description.assert_awaited_once()
        sent = handler.clients["openai"].chat.completions.create.call_args.kwargs["messages"]
        assert "[VISUAL CONTEXT ANALYSIS]" in sent[1]["content"]
        assert "red car" in sent[1]["content"]

    @pytest.mark.asyncio
    async def test_vision_model_gets_image_message(self):
        handler = _make_handler()
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o")]
        )
        handler.get_optimal_provider = AsyncMock(return_value=("openai", "gpt-4o"))
        handler._rerank_with_learning = AsyncMock(
            side_effect=lambda opts, *a, **k: opts
        )
        handler._model_supports_vision = MagicMock(return_value=True)
        handler.clients["openai"].chat.completions.create = MagicMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="ok"),
                    finish_reason="stop",
                )],
                usage=None,
            )
        )
        result = await self._run_generate(
            handler, image_payload="https://example.com/img.png"
        )
        assert result == "ok"
        sent = handler.clients["openai"].chat.completions.create.call_args.kwargs["messages"]
        assert sent[1]["content"][1]["type"] == "image_url"
        assert sent[1]["content"][1]["image_url"]["url"] == "https://example.com/img.png"


# =========================================================================== #
# Context window + truncation helpers
# =========================================================================== #
class TestContextHelpers:
    def test_get_context_window_pricing_hit(self):
        handler = _make_handler()
        fetcher = MagicMock()
        fetcher.get_model_price.return_value = {"max_input_tokens": 99999}
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_context_window("my-model") == 99999

    def test_get_context_window_defaults(self):
        handler = _make_handler()
        fetcher = MagicMock()
        fetcher.get_model_price.return_value = None
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_context_window("gpt-4o") == 128000
            assert handler.get_context_window("claude-3-sonnet") == 200000
            assert handler.get_context_window("deepseek-chat") == 32768
            assert handler.get_context_window("unknown-model") == 4096

    def test_get_context_window_error(self):
        handler = _make_handler()
        fetcher = MagicMock()
        fetcher.get_model_price.side_effect = RuntimeError("boom")
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_context_window("gpt-4o-mini") == 128000

    def test_truncate_short_text_unchanged(self):
        handler = _make_handler()
        text = "short prompt"
        assert handler.truncate_to_context(text, "gpt-4o") == text

    def test_truncate_long_text_preserves_head_tail(self):
        handler = _make_handler()
        fetcher = MagicMock()
        fetcher.get_model_price.return_value = {"max_input_tokens": 4000}
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            long = "A" * 200000 + "MIDDLE" + "B" * 200000
            out = handler.truncate_to_context(long, "gpt-4o-mini", reserve_tokens=1000)
        assert len(out) < len(long)
        assert out.startswith("A" * 2000)
        assert out.endswith("B" * 2000)
        assert "MIDDLE" not in out
        assert "Content truncated" in out


# =========================================================================== #
# Model capability helpers
# =========================================================================== #
class TestModelCapabilities:
    def test_model_supports_tools(self):
        handler = _make_handler()
        handler.pricing_fetcher = MagicMock()
        handler.pricing_fetcher.get_model_capabilities.return_value = {
            "supports_tools": True
        }
        assert handler._model_supports_tools("gpt-4o") is True
        handler.pricing_fetcher.get_model_capabilities.return_value = {
            "supports_tools": False
        }
        assert handler._model_supports_tools("gpt-4o") is False
        handler.pricing_fetcher.get_model_capabilities.return_value = {}
        assert handler._model_supports_tools("gpt-4o") is False  # unknown -> no

    def test_model_supports_vision(self):
        handler = _make_handler()
        handler.pricing_fetcher = MagicMock()
        handler.pricing_fetcher.get_model_capabilities.return_value = {
            "supports_vision": True
        }
        assert handler._model_supports_vision("gpt-4o") is True
        handler.pricing_fetcher.get_model_capabilities.return_value = {
            "supports_vision": False
        }
        assert handler._model_supports_vision("gpt-4o") is False


# =========================================================================== #
# Trial gate
# =========================================================================== #
class TestTrialRestricted:
    def _handler(self):
        handler = _make_handler()
        return handler

    @staticmethod
    def _ctx(session):
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False
        return ctx

    def test_trial_not_ended(self):
        handler = self._handler()
        session = MagicMock()
        workspace = SimpleNamespace(trial_ended=False)
        session.query.return_value.filter.return_value.first.return_value = workspace
        with patch("core.llm.byok_handler.get_db_session", return_value=self._ctx(session)):
            assert handler._is_trial_restricted() is False

    def test_trial_ended(self):
        handler = self._handler()
        session = MagicMock()
        workspace = SimpleNamespace(trial_ended=True)
        session.query.return_value.filter.return_value.first.return_value = workspace
        with patch("core.llm.byok_handler.get_db_session", return_value=self._ctx(session)):
            assert handler._is_trial_restricted() is True

    def test_db_error_fails_open(self):
        handler = self._handler()
        with patch(
            "core.llm.byok_handler.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            assert handler._is_trial_restricted() is False


# =========================================================================== #
# Decision stash
# =========================================================================== #
class TestStashDecisionFeatures:
    def test_flag_off_returns_none(self):
        handler = _make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "false"}):
            assert handler._stash_decision_features("hi", "chat") is None

    def test_router_unavailable_returns_none(self):
        handler = _make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=None,
             ):
            assert handler._stash_decision_features("hi", "chat") is None

    def test_stashes_decision(self):
        handler = _make_handler()
        router = MagicMock()
        router.stash_decision = MagicMock(return_value="dec-xyz")
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ):
            decision_id = handler._stash_decision_features("hi", "chat")
        assert decision_id == "dec-xyz"
