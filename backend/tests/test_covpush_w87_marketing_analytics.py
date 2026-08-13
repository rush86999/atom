# -*- coding: utf-8 -*-
"""Coverage wave 87 — core/marketing_analytics (standalone, zero LLM spend,
no network).

- generate_narrative_report: no AI service → static report; AI present WITH
  the optional ai_enhanced_service module → dict output (content key, or
  str(dict) fallback when content absent) and string output passthrough; AI
  present but the module is ABSENT (this repo) → graceful static fallback
  instead of ModuleNotFoundError (BUG 87-4).
- get_budget_advice: no AI → static advice; AI + module present → dict/str
  output handling; AI + module absent → graceful fallback.
"""
from contextlib import ExitStack
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.marketing_analytics import PlainEnglishReporter


def _run(coro):
    import asyncio
    return asyncio.run(coro)


@contextmanager
def _ai_surface():
    """Simulate integrations.ai_enhanced_service being importable: the guarded
    module-level import in marketing_analytics picks these up."""
    with ExitStack() as stack:
        for p in [
            patch("core.marketing_analytics.AIRequest",
                  MagicMock(side_effect=lambda **kw: SimpleNamespace(**kw))),
            patch("core.marketing_analytics.AIModelType",
                  MagicMock(GPT_4O="gpt-4o")),
            patch("core.marketing_analytics.AIServiceType",
                  MagicMock(OPENAI="openai")),
            patch("core.marketing_analytics.AITaskType",
                  MagicMock(CONTENT_GENERATION="content")),
        ]:
            stack.enter_context(p)
        yield


class TestGenerateNarrativeReport:
    def test_no_ai_service_returns_static_report(self):
        result = _run(PlainEnglishReporter().generate_narrative_report({"leads": 5}))
        assert "Google and Facebook" in result

    def test_ai_service_without_module_falls_back(self):
        """BUG 87-4 regression: injected AI service + absent optional module
        must fall back to the static report, not raise ModuleNotFoundError."""
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(output_data={}))
        with patch("core.marketing_analytics.AIRequest", None):
            result = _run(
                PlainEnglishReporter(ai_service=ai).generate_narrative_report({})
            )
        assert "Google and Facebook" in result
        ai.process_ai_request.assert_not_called()

    def test_ai_dict_output_with_content(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={"content": "Calls up 20%"})
        )
        with _ai_surface():
            result = _run(
                PlainEnglishReporter(ai_service=ai).generate_narrative_report({})
            )
        assert result == "Calls up 20%"
        request = ai.process_ai_request.await_args.args[0]
        assert request.task_type == "content"

    def test_ai_dict_output_without_content_uses_str(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={"other": "value"})
        )
        with _ai_surface():
            result = _run(
                PlainEnglishReporter(ai_service=ai).generate_narrative_report({})
            )
        assert "other" in result

    def test_ai_string_output_passthrough(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data="Plain sentence report")
        )
        with _ai_surface():
            result = _run(
                PlainEnglishReporter(ai_service=ai).generate_narrative_report({})
            )
        assert result == "Plain sentence report"


class TestGetBudgetAdvice:
    def test_no_ai_service_returns_static_advice(self):
        result = _run(PlainEnglishReporter().get_budget_advice({"google": {}}))
        assert "Google Search" in result

    def test_ai_service_without_module_falls_back(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(output_data={}))
        with patch("core.marketing_analytics.AIRequest", None):
            result = _run(
                PlainEnglishReporter(ai_service=ai).get_budget_advice({})
            )
        assert "Google Search" in result
        ai.process_ai_request.assert_not_called()

    def test_ai_dict_output_with_content(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={"content": "Shift budget"})
        )
        with _ai_surface():
            result = _run(
                PlainEnglishReporter(ai_service=ai).get_budget_advice({"fb": {}})
            )
        assert result == "Shift budget"

    def test_ai_dict_output_without_content_uses_str(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={"why": "x"})
        )
        with _ai_surface():
            result = _run(
                PlainEnglishReporter(ai_service=ai).get_budget_advice({})
            )
        assert "why" in result

    def test_ai_string_output_passthrough(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data="More money to Meta")
        )
        with _ai_surface():
            result = _run(
                PlainEnglishReporter(ai_service=ai).get_budget_advice({})
            )
        assert result == "More money to Meta"
