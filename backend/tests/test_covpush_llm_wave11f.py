"""Coverage wave 11f — provider-model heuristic, tool-pair sanitizer, query
complexity, optimal-provider wrapper (TDD)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import BYOKHandler, QueryComplexity


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


# =========================================================================== #
# _provider_serves_model heuristic
# =========================================================================== #
class TestProviderServesModel:
    def test_local_providers_always_serve(self):
        handler = _make_handler()
        assert handler._provider_serves_model("ollama", "anything") is True
        assert handler._provider_serves_model("local_p1", "my-model") is True
        assert handler._provider_serves_model("vllm", "x") is True

    def test_gateway_providers_always_serve(self):
        handler = _make_handler()
        assert handler._provider_serves_model("opencode-go", "deepseek-v4-flash") is True
        assert handler._provider_serves_model("openrouter", "claude-sonnet") is True

    def test_family_prefix_match(self):
        handler = _make_handler()
        assert handler._provider_serves_model("openai", "gpt-4o") is True
        assert handler._provider_serves_model("anthropic", "claude-sonnet") is True
        assert handler._provider_serves_model("deepseek", "deepseek-chat") is True
        assert handler._provider_serves_model("qwen", "qwen-plus") is True
        assert handler._provider_serves_model("moonshot", "kimi-k2") is True
        assert handler._provider_serves_model("glm", "chatglm-turbo") is True

    def test_family_prefix_mismatch(self):
        handler = _make_handler()
        assert handler._provider_serves_model("openai", "claude-sonnet") is False
        assert handler._provider_serves_model("anthropic", "gpt-4o") is False

    def test_substring_fallback(self):
        handler = _make_handler()
        assert handler._provider_serves_model("xai", "grok-xai-beta") is True

    def test_empty_model(self):
        handler = _make_handler()
        assert handler._provider_serves_model("openai", "") is True


# =========================================================================== #
# sanitize_tool_pairs
# =========================================================================== #
class TestSanitizeToolPairs:
    def test_tool_without_preceding_tool_calls_gets_stub(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "tool", "tool_call_id": "t1", "content": "result"},
        ]
        out = BYOKHandler.sanitize_tool_pairs(messages)
        assert out[1]["role"] == "assistant"
        assert out[1]["tool_calls"][0]["id"] == "t1"
        assert out[1]["tool_calls"][0]["function"]["name"] == "_truncated_tool_call"
        assert out[2]["role"] == "tool"

    def test_tool_with_preceding_tool_calls_passthrough(self):
        messages = [
            {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]},
            {"role": "tool", "tool_call_id": "t1", "content": "result"},
        ]
        out = BYOKHandler.sanitize_tool_pairs(messages)
        assert len(out) == 2
        assert out[1]["role"] == "tool"

    def test_trailing_tool_calls_without_content_dropped(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "t9"}]},
        ]
        out = BYOKHandler.sanitize_tool_pairs(messages)
        assert len(out) == 1
        assert out[0]["role"] == "user"

    def test_trailing_tool_calls_with_content_kept(self):
        messages = [
            {"role": "assistant", "content": "thinking...", "tool_calls": [{"id": "t9"}]},
        ]
        out = BYOKHandler.sanitize_tool_pairs(messages)
        assert len(out) == 1

    def test_empty_messages(self):
        assert BYOKHandler.sanitize_tool_pairs([]) == []


# =========================================================================== #
# analyze_query_complexity
# =========================================================================== #
class TestAnalyzeQueryComplexity:
    def _analyze(self, prompt, task_type=None):
        handler = _make_handler()
        return handler.analyze_query_complexity(prompt, task_type)

    def test_simple_greeting(self):
        assert self._analyze("hello") == QueryComplexity.SIMPLE

    def test_long_prompt_scores_higher(self):
        # 10000 chars -> 2500 tokens -> +3 base; "simple" -2 -> score 1 -> MODERATE
        assert self._analyze("hello " * 2000) == QueryComplexity.MODERATE

    def test_code_block_and_keywords(self):
        code = "```python\ndef foo(x):\n    return x\n``` debug the import error"
        tier = self._analyze(code)
        assert tier in (QueryComplexity.COMPLEX, QueryComplexity.ADVANCED)

    def test_technical_math(self):
        assert self._analyze("calculate the integral of x^2") == QueryComplexity.COMPLEX

    def test_advanced_security(self):
        assert self._analyze("perform a security audit of the authentication flow") == QueryComplexity.ADVANCED

    def test_task_type_bias(self):
        assert self._analyze("write it", task_type="code") == QueryComplexity.COMPLEX
        assert self._analyze("hello there", task_type="chat") == QueryComplexity.SIMPLE

    def test_empty_prompt(self):
        assert self._analyze("") == QueryComplexity.SIMPLE


# =========================================================================== #
# get_optimal_provider
# =========================================================================== #
class TestGetOptimalProvider:
    @pytest.mark.asyncio
    async def test_returns_top_ranked(self):
        handler = _make_handler()
        handler.get_ranked_providers = MagicMock(
            return_value=[("deepseek", "deepseek-chat"), ("openai", "gpt-4o-mini")]
        )
        provider, model = await handler.get_optimal_provider(
            QueryComplexity.SIMPLE, "chat", True
        )
        assert provider == "deepseek"
        assert model == "deepseek-chat"

    @pytest.mark.asyncio
    async def test_empty_falls_back(self):
        handler = _make_handler()
        handler.get_ranked_providers = MagicMock(return_value=[])
        provider, model = await handler.get_optimal_provider(
            QueryComplexity.SIMPLE, "chat", True
        )
        # falls back to the first configured client + its default model
        assert provider == "openai"
        assert model == "gpt-4o-mini"
