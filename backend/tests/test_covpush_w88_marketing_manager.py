# -*- coding: utf-8 -*-
"""Coverage wave 88 — core/marketing_manager (53 stmts, never wave-tested).

- LeadScoringService: no-AI fallback dict (score 50 / MEDIUM), AI path with
  integrations.ai_enhanced_service faked via sys.modules (the real module
  does not exist in this repo) — request shape (task type, model, service,
  input prompt contains lead JSON + history) and output_data passthrough.
- AIMarketingManager: constructor wires GMBAutomation + LeadScoringService,
  perform_daily_marketing_checklist returns the expected tasks dict.

No LLM spend / no network / AI surface fully faked.
"""
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock

from core.marketing_manager import AIMarketingManager, LeadScoringService


class _FakeTaskType:
    CONVERSATION_ANALYSIS = "conversation_analysis"


class _FakeModelType:
    GPT_4O = "gpt-4o"


class _FakeServiceType:
    OPENAI = "openai"


class _FakeAIRequest:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _fake_ai_enhanced_module():
    mod = types.ModuleType("integrations.ai_enhanced_service")
    mod.AITaskType = _FakeTaskType
    mod.AIModelType = _FakeModelType
    mod.AIServiceType = _FakeServiceType
    mod.AIRequest = _FakeAIRequest
    return mod


class TestLeadScoringWithoutAI:
    def test_fallback_score(self):
        result = asyncio_run(LeadScoringService().calculate_score(
            {"email": "x@y.z"}, ["visited pricing"]
        ))
        assert result == {"score": 50, "priority": "MEDIUM", "rationale": "Manual review recommended."}


class TestLeadScoringWithAI:
    def test_ai_path_returns_output_data(self, monkeypatch):
        monkeypatch.setitem(
            sys.modules, "integrations.ai_enhanced_service", _fake_ai_enhanced_module()
        )
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=MagicMock(output_data={"score": 88, "priority": "HIGH", "rationale": "hot lead"})
        )
        result = asyncio_run(LeadScoringService(ai_service=ai).calculate_score(
            {"email": "a@b.c", "budget": 5000}, ["visited pricing page", "started signup"]
        ))
        assert result == {"score": 88, "priority": "HIGH", "rationale": "hot lead"}
        request = ai.process_ai_request.await_args.args[0]
        assert isinstance(request, _FakeAIRequest)
        assert request.task_type == _FakeTaskType.CONVERSATION_ANALYSIS
        assert request.model_type == _FakeModelType.GPT_4O
        assert request.service_type == _FakeServiceType.OPENAI
        assert request.request_id.startswith("score_")
        assert json.dumps({"email": "a@b.c", "budget": 5000}) in request.input_data
        assert "started signup" in request.input_data


class TestAIMarketingManager:
    def test_constructor_wires_services(self):
        manager = AIMarketingManager(ai_service="fake-ai", db_session="fake-db")
        assert manager.ai == "fake-ai"
        assert manager.db == "fake-db"
        assert manager.gmb.ai == "fake-ai"
        assert manager.lead_scoring.ai == "fake-ai"

    def test_constructor_without_deps(self):
        manager = AIMarketingManager()
        assert manager.ai is None
        assert manager.db is None
        assert manager.gmb is not None
        assert manager.lead_scoring is not None

    def test_perform_daily_marketing_checklist(self):
        manager = AIMarketingManager()
        result = asyncio_run(manager.perform_daily_marketing_checklist("ws-1"))
        assert result == {"status": "success", "tasks_completed": ["gmb_check", "lead_scan"]}


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
