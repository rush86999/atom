"""Coverage wave 57 — core/llm/byok_handler.py section C: generate_response paths.

Trial gate, no-client (agentic demo + plain), budget gate, and the happy path
with a mocked client (system prompt, vision payload, cache recording, usage
tracking). Uses the make_handler helper from section A.
"""
import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.llm.byok_handler import AwaitableResult, BYOKHandler

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


class TestGenerateResponseGates:
    async def test_trial_restricted(self):
        h = make_handler(clients={"openai": 1})
        with patch.object(h, "_is_trial_restricted", return_value=True):
            result = await h.generate_response("hello")
        assert "Trial Expired" in result

    async def test_no_clients_agentic_demo(self):
        h = make_handler(clients={})
        result = await h.generate_response("analyze the market", task_type="agentic")
        parsed = json.loads(result)
        assert parsed["action"] == "perform_market_analysis"

    async def test_no_clients_agentic_done(self):
        h = make_handler(clients={})
        result = await h.generate_response("something random", task_type="agentic")
        parsed = json.loads(result)
        assert parsed["action"] == "DONE"

    async def test_no_clients_plain(self):
        h = make_handler(clients={})
        result = await h.generate_response("hello", task_type="chat")
        assert "not initialized" in result

    async def test_budget_exceeded(self):
        h = make_handler(clients={"openai": 1})
        with patch("core.llm.byok_handler.llm_usage_tracker") as ut:
            ut.is_budget_exceeded.return_value = True
            result = await h.generate_response("hello")
        assert "BUDGET EXCEEDED" in result


class TestGenerateResponseHappyPath:
    async def test_plain_prompt(self):
        h = make_handler(clients={"openai": 1, "deepseek": 1})
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
            result = await h.generate_response("hello world")
        assert result == "hi there"
        assert h._last_used_model == "gpt-4o"
        assert h._last_used_provider == "openai"
        client.chat.completions.create.assert_called_once()

    async def test_no_eligible_providers(self):
        h = make_handler(clients={"openai": 1})
        with patch.object(h, "get_ranked_providers", return_value=AwaitableResult([])), \
             patch.object(h, "_is_trial_restricted", return_value=False), \
             patch("core.llm.byok_handler.llm_usage_tracker") as ut, \
             patch("core.llm.byok_handler.get_db_session") as gds:
            ut.is_budget_exceeded.return_value = False
            db = MagicMock()
            db.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            gds.return_value = db
            result = await h.generate_response("hello")
        assert "No eligible LLM providers" in result


class TestVisionAndFallback:
    async def test_vision_payload_with_coordinated_description(self):
        h = make_handler(clients={"openai": 1})
        client = Mock()
        client.chat.completions.create.return_value = _chat_response("vision answer")
        h.clients["openai"] = client
        with patch.object(h, "get_ranked_providers",
                          return_value=AwaitableResult([("openai", "gpt-4o")])), \
             patch.object(h, "_is_trial_restricted", return_value=False), \
             patch.object(h, "_get_coordinated_vision_description",
                          new=AsyncMock(return_value="coordinated context")), \
             patch("core.llm.byok_handler.llm_usage_tracker") as ut, \
             patch("core.llm.byok_handler.get_db_session") as gds:
            ut.is_budget_exceeded.return_value = False
            db = MagicMock()
            db.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            gds.return_value = db
            result = await h.generate_response(
                "what is this", image_payload="data:image/png;base64,AAAA")
        assert result == "vision answer"
        _, kwargs = client.chat.completions.create.call_args
        # multimodal content blocks sent
        assert isinstance(kwargs["messages"][-1]["content"], list)

    async def test_provider_fallback_on_first_failure(self):
        h = make_handler(clients={"openai": 1, "deepseek": 1})
        bad = Mock()
        bad.chat.completions.create.side_effect = RuntimeError("boom")
        good = Mock()
        good.chat.completions.create.return_value = _chat_response("recovered")
        h.clients["openai"] = bad
        h.clients["deepseek"] = good
        with patch.object(h, "get_ranked_providers",
                          return_value=AwaitableResult([
                              ("openai", "gpt-4o"),
                              ("deepseek", "deepseek-chat"),
                          ])), \
             patch.object(h, "_is_trial_restricted", return_value=False), \
             patch("core.llm.byok_handler.llm_usage_tracker") as ut, \
             patch("core.llm.byok_handler.get_db_session") as gds:
            ut.is_budget_exceeded.return_value = False
            db = MagicMock()
            db.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            gds.return_value = db
            result = await h.generate_response("hello")
        assert result == "recovered"
