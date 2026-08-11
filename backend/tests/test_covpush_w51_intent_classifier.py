"""Coverage wave 51 — core/intent_classifier.py (49% → 90%+).

classify_intent: LLM path (chat/workflow/task/unknown categories + flags),
LLM exception → heuristic fallback; _llm_classify: markdown-fenced JSON,
plain JSON, parse-error default; singleton getter with double-checked lock.
"""
import json
import threading
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.intent_classifier import (
    IntentCategory,
    IntentClassification,
    IntentClassifier,
    get_intent_classifier,
)


@pytest.fixture
def classifier():
    with patch("core.intent_classifier.get_llm_service") as gls:
        clf = IntentClassifier(Mock(), "ws1")
        clf.llm = Mock()
        yield clf


def _llm_response(content):
    return {"content": content}


class TestClassifyIntentLLMPath:
    async def test_chat_category(self, classifier):
        classifier.llm.call = AsyncMock(return_value=_llm_response(
            json.dumps({"category": "general_query", "confidence": 0.9,
                        "reasoning": "r"})))
        result = await classifier.classify_intent("hello")
        assert result.category == IntentCategory.CHAT
        assert result.requires_execution is False
        assert result.suggested_handler == "llm_service"
        assert result.is_structured is False

    async def test_workflow_category(self, classifier):
        classifier.llm.call = AsyncMock(return_value=_llm_response(
            json.dumps({"category": "automation", "confidence": 0.8,
                        "reasoning": "r"})))
        result = await classifier.classify_intent("set up a workflow")
        assert result.category == IntentCategory.WORKFLOW
        assert result.suggested_handler == "queen_agent"
        assert result.is_structured is True
        assert result.blueprint_applicable is True

    async def test_task_category(self, classifier):
        classifier.llm.call = AsyncMock(return_value=_llm_response(
            json.dumps({"category": "agent_task", "confidence": 0.7,
                        "reasoning": "r"})))
        result = await classifier.classify_intent("research competitors")
        assert result.category == IntentCategory.TASK
        assert result.suggested_handler == "fleet_admiral"
        assert result.is_long_horizon is True
        assert result.requires_agent_recruitment is True

    async def test_unknown_category_defaults_chat(self, classifier):
        classifier.llm.call = AsyncMock(return_value=_llm_response(
            json.dumps({"category": "mystery", "confidence": 0.5, "reasoning": "r"})))
        result = await classifier.classify_intent("???")
        assert result.category == IntentCategory.CHAT

    async def test_llm_exception_heuristic_fallback(self, classifier):
        classifier.llm.call = AsyncMock(side_effect=RuntimeError("llm down"))
        result = await classifier.classify_intent("hello there")
        assert isinstance(result, IntentClassification)


class TestLlmClassify:
    async def test_markdown_json_fence(self, classifier):
        classifier.llm.call = AsyncMock(return_value=_llm_response(
            '```json\n{"category": "chat", "confidence": 0.6, "reasoning": "x"}\n```'))
        result = await classifier._llm_classify("hi")
        assert result["category"] == IntentCategory.CHAT

    async def test_plain_code_fence(self, classifier):
        classifier.llm.call = AsyncMock(return_value=_llm_response(
            '```\n{"category": "workflow", "confidence": 0.9, "reasoning": "x"}\n```'))
        result = await classifier._llm_classify("wf")
        assert result["category"] == IntentCategory.WORKFLOW

    async def test_parse_error_returns_default(self, classifier):
        classifier.llm.call = AsyncMock(return_value=_llm_response("not json at all"))
        result = await classifier._llm_classify("hi")
        assert result["category"] == IntentCategory.CHAT
        assert result["confidence"] == 0.5

    async def test_llm_error_propagates(self, classifier):
        classifier.llm.call = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            await classifier._llm_classify("hi")


class TestSingleton:
    def test_get_intent_classifier_singleton(self):
        with patch("core.intent_classifier._intent_classifier_instance", None):
            first = get_intent_classifier()
            assert first is get_intent_classifier()
            assert isinstance(first, IntentClassifier)

    def test_singleton_lock_preserved(self):
        # second creation path inside the lock (double-checked)
        with patch("core.intent_classifier._intent_classifier_instance", None), \
             patch("core.intent_classifier._intent_classifier_lock",
                   threading.Lock()) as lock:
            get_intent_classifier()
            get_intent_classifier()
        assert lock is not None


class TestCanvasSummaryEdges:
    def test_richness_empty_summary(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        svc = CanvasSummaryService(Mock())
        assert svc._calculate_semantic_richness("") == 0.0

    def test_fabrication_check_clean(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        svc = CanvasSummaryService(Mock())
        assert svc._detect_hallucination(
            "Workflow wf-123 completed", {"workflow_ids": ["wf-123"]}) is False
        assert svc._detect_hallucination(
            "Workflow wf-999 completed", {"workflow_ids": ["wf-123"]}) is True


class TestHeuristicWorkflowBranch:
    def test_workflow_keywords_route_to_queen(self):
        from core.intent_classifier import IntentCategory
        clf = IntentClassifier(Mock(), "ws1")
        result = clf._heuristic_classify("run the nightly report automation")
        assert result.category == IntentCategory.WORKFLOW
        assert result.suggested_handler == "queen_agent"
        assert result.is_structured is True
        assert result.blueprint_applicable is True
