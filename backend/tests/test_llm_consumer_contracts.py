"""Typed-completion contracts for adjacent LLMService facade consumers.

These consumers previously called a nonexistent
``LLMService.generate_response``. The canonical facade is
``generate_completion``: full OpenAI-style ``messages`` plus scoped
``workspace_id``/``tenant_id``, returning a typed mapping.

The doubles below deliberately expose ONLY ``generate_completion`` so a
regression to the legacy method fails immediately. They also verify that
provider/policy failures and non-string content are never published as model
answers, while previously declared deterministic/template fallbacks remain.
"""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("TESTING", "1")

import pytest

from core.blueprint_healer import BlueprintHealer
from core.canvas_presentation_summary import CanvasPresentationSummaryService
from core.group_reflection_service import (
    DomainProfileRegistry,
    GroupReflectionService,
)
from core.llm.completion_outcome import completion_text_outcome
from core.social_post_generator import SocialPostGenerator


def _ok(text):
    return {"success": True, "content": text, "text": text}


def _failure(reason="policy_blocked", message="provider unavailable"):
    return {
        "success": False,
        "content": "",
        "text": "",
        "error": message,
        "failure": {"reason": reason, "message": message},
    }


class _CanonicalLLM:
    """Fake canonical facade with NO ``generate_response`` attribute."""

    def __init__(self, result=None, *, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def generate_completion(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def _blueprint():
    return {
        "name": "ResearchArchitecture",
        "nodes": [{"id": "n1", "type": "tool", "name": "search"}],
    }


def _reflection_pool():
    return {
        "agent_count": 1,
        "trace_count": 2,
        "tool_patterns": [],
        "task_log_excerpts": [],
        "successful_patches": [],
        "evolving_requirements": [],
        "_domain_profile": DomainProfileRegistry.resolve("engineering"),
        "_category": "engineering",
    }


def _tracker():
    return SimpleNamespace(
        operation_type="workflow_execute",
        status="completed",
        what_explanation="reconciled invoices",
        why_explanation="monthly close",
        next_steps="notify finance",
    )


def _agent():
    return SimpleNamespace(
        name="Finance Agent", workspace_id="ws-finance", tenant_id="t-finance")


def _canvas_service(llm):
    with patch(
            "core.service_factory.ServiceFactory.get_llm_service",
            return_value=llm):
        return CanvasPresentationSummaryService(db=MagicMock())


def _reflection_service(llm):
    with patch(
            "core.service_factory.ServiceFactory.get_llm_service",
            return_value=llm):
        return GroupReflectionService(MagicMock())


def test_completion_text_outcome_rejects_typed_failures_and_nonstrings():
    assert completion_text_outcome(_ok("  answer  ")) == ("answer", None)
    assert completion_text_outcome(
        {"success": True, "text": "legacy"}) == ("legacy", None)
    for bad in ({"error": "not an answer"}, ["x"], True, 7, 1.5):
        text, failure = completion_text_outcome(
            {"success": True, "content": bad})
        assert text is None
        assert failure["reason"] == "invalid_completion_content"
    typed = {"reason": "provider_down", "message": "unavailable"}
    assert completion_text_outcome(
        {"success": False, "failure": typed}) == (None, typed)
    assert completion_text_outcome(
        {"success": True, "content": "  "})[1]["reason"] == "empty_generation"
    assert completion_text_outcome(None)[1]["reason"] == (
        "invalid_completion_result")


def test_canonical_llm_service_exposes_completion_not_generate_response():
    """The adjacent consumers must target the real facade method."""
    from core.llm_service import LLMService

    assert hasattr(LLMService, "generate_completion")
    assert not hasattr(LLMService, "generate_response")


def test_blueprint_healer_uses_canonical_completion_and_keeps_full_context():
    llm = _CanonicalLLM(_ok(
        '```json\n[{"id": "n2", "type": "tool", "name": "retry"}]\n```'))
    healer = BlueprintHealer(MagicMock(), llm)

    healed = asyncio.run(healer.heal_blueprint(
        _blueprint(), "n1", "schema unknown", tenant_id="t-42"))

    assert healed["status"] == "healed"
    assert healed["nodes"] == [
        {"id": "n2", "type": "tool", "name": "retry"}]
    assert not hasattr(llm, "generate_response")
    call = llm.calls[0]
    assert call["tenant_id"] == "t-42"
    assert len(call["messages"]) == 2
    assert "schema unknown" in call["messages"][1]["content"]


def test_blueprint_healer_failure_and_nonstring_never_mark_healed():
    original = _blueprint()
    for result in (
            _failure("budget_denied"),
            {"success": True, "content": {"error": "not text"}},
            None):
        llm = _CanonicalLLM(result)
        healer = BlueprintHealer(MagicMock(), llm)
        healed = asyncio.run(healer.heal_blueprint(
            original, "n1", "err", tenant_id="t1"))
        assert healed is original
        assert healed.get("status") != "healed"


def test_blueprint_directive_failure_uses_declared_template_not_error():
    llm = _CanonicalLLM(_failure("provider_down", "raw provider error"))
    healer = BlueprintHealer(MagicMock(), llm)

    directive = asyncio.run(healer.summarize_healing_as_directive(
        {"name": "n1", "type": "tool"}, [], "boom", tenant_id="t1"))

    assert directive == "Improve architectural robustness for the failing node type."
    assert "raw provider error" not in directive
    assert len(llm.calls[0]["messages"]) == 2


def test_canvas_summary_success_uses_full_messages_and_scope():
    llm = _CanonicalLLM(_ok("  The user is reconciling invoices.  "))
    service = _canvas_service(llm)

    result = asyncio.run(service.generate_presentation_summary(
        "c1", "sheets", {"rows": 10}, tenant_id="t1", use_cache=False))

    assert result == "The user is reconciling invoices."
    assert not hasattr(llm, "generate_response")
    call = llm.calls[0]
    assert call["tenant_id"] == "t1"
    assert call["max_tokens"] == 150
    assert len(call["messages"]) == 2
    assert "Analyze this spreadsheet canvas" in (
        call["messages"][1]["content"])


def test_canvas_summary_failure_uses_declared_fallback_not_error_text():
    llm = _CanonicalLLM(_failure("provider_unavailable", "raw provider error"))
    service = _canvas_service(llm)

    result = asyncio.run(service.generate_presentation_summary(
        "c1", "terminal", {"pwd": "/tmp"}, tenant_id="t1", use_cache=False))

    assert result == "Terminal canvas with 1 state elements"
    assert "raw provider error" not in result

    empty_llm = _CanonicalLLM({"success": True, "content": ""})
    empty_service = _canvas_service(empty_llm)
    assert asyncio.run(empty_service.generate_presentation_summary(
        "c1", "sheets", {}, tenant_id="t1", use_cache=False)) == ""


def test_reflection_success_uses_canonical_completion_and_tenant_scope():
    llm = _CanonicalLLM(_ok(
        "1. Add error handling\n2. Improve caching\n3. Fix race condition"))
    service = _reflection_service(llm)

    directives = asyncio.run(service.reflect_and_generate_directives(
        _reflection_pool(), tenant_id="t-1", max_directives=2))

    assert directives == ["Add error handling", "Improve caching"]
    assert not hasattr(llm, "generate_response")
    call = llm.calls[0]
    assert call["tenant_id"] == "t-1"
    assert len(call["messages"]) == 2


def test_reflection_failure_or_nonstring_never_becomes_verified_directive():
    original = _reflection_pool()
    for result in (
            _failure("policy_blocked", "raw provider error"),
            {"success": True, "content": {"error": "not text"}}):
        service = _reflection_service(_CanonicalLLM(result))
        directives = asyncio.run(service.reflect_and_generate_directives(
            original, tenant_id="t1"))
        profile = DomainProfileRegistry.resolve("engineering")
        assert directives == [
            "Maintain current behavior while investigating "
            f"{profile.failure_label}."]
        assert all("raw provider error" not in item for item in directives)

    empty_service = _reflection_service(
        _CanonicalLLM({"success": True, "content": ""}))
    assert asyncio.run(empty_service.reflect_and_generate_directives(
        original, tenant_id="t1")) == []


def test_social_post_success_preserves_scope_and_full_messages():
    llm = _CanonicalLLM(_ok("Just finished the report!"))
    generator = SocialPostGenerator()
    with patch.object(SocialPostGenerator, "llm_service", llm):
        post = asyncio.run(generator.generate_from_operation(
            _tracker(), _agent()))

    assert post == "Just finished the report!"
    assert not hasattr(llm, "generate_response")
    call = llm.calls[0]
    assert call["workspace_id"] == "ws-finance"
    assert call["tenant_id"] == "t-finance"
    assert call["temperature"] == 0.7
    assert len(call["messages"]) == 2
    assert "reconciled invoices" in call["messages"][1]["content"]


@pytest.mark.parametrize("result", [
    _failure("provider_down", "raw provider error"),
    {"success": True, "content": {"error": "not text"}},
])
def test_social_post_failure_or_nonstring_uses_template_not_error(result):
    llm = _CanonicalLLM(result)
    generator = SocialPostGenerator()
    with patch.object(SocialPostGenerator, "llm_service", llm):
        post = asyncio.run(generator.generate_from_operation(
            _tracker(), _agent()))

    assert "workflow_execute" in post
    assert "raw provider error" not in post
    assert "error" not in post.lower()


def test_episode_context_forwards_workspace_and_tenant_to_canonical_call():
    llm = _CanonicalLLM(_ok("post with context"))
    generator = SocialPostGenerator()
    with patch.object(SocialPostGenerator, "llm_service", llm):
        post = asyncio.run(generator._generate_with_llm_and_context(
            {"operation_type": "etl", "what_explanation": "loaded data"},
            "Similar to past experiences: prior ETL",
            workspace_id="ws-1", tenant_id="t-1"))

    assert post == "post with context"
    call = llm.calls[0]
    assert call["workspace_id"] == "ws-1"
    assert call["tenant_id"] == "t-1"
    assert len(call["messages"]) == 2
    assert "Similar to past experiences" in call["messages"][1]["content"]


def test_episode_context_failure_uses_template_not_error_text():
    llm = _CanonicalLLM(_failure("provider_down", "raw provider error"))
    generator = SocialPostGenerator()
    with patch.object(SocialPostGenerator, "llm_service", llm):
        post = asyncio.run(generator._generate_with_llm_and_context(
            {"operation_type": "workflow_execute", "status": "completed",
             "what_explanation": "x"}, "ctx",
            workspace_id="ws-1", tenant_id="t-1"))

    assert "workflow_execute" in post
    assert "raw provider error" not in post
