"""AdvisorService canonical completion contract.

The service must use the real ``LLMService.generate_completion(messages, ...)``
surface, accept only typed successful text as model advice, and label every
failure/empty/malformed result as the declared heuristic fallback. The double
below exposes ONLY the canonical method: a regression to
``system_prompt``/``user_prompt`` or ``generate_response`` fails immediately.
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auto_dev.advisor_service import AdvisorService
from core.auto_dev.models import ToolMutation, WorkflowVariant
from core.database import Base


class CanonicalOnlyLLM:
    def __init__(self, result=None, *, error=None):
        self.result = result
        self.error = error
        self.calls: list[dict] = []

    async def generate_completion(self, messages, model="auto",
                                  temperature=0.7, max_tokens=None,
                                  workspace_id=None, tenant_id=None):
        self.calls.append({
            "messages": messages, "model": model,
            "temperature": temperature, "max_tokens": max_tokens,
            "workspace_id": workspace_id, "tenant_id": tenant_id,
        })
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'advisor-contract.db'}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    session.add(ToolMutation(
        tenant_id="tenant-1", tool_name="tool", mutated_code="code",
        sandbox_status="passed"))
    session.add(WorkflowVariant(
        tenant_id="tenant-1", workflow_definition={}, fitness_score=0.8,
        evaluation_status="evaluated"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _run(db, llm):
    return asyncio.run(
        AdvisorService(db, llm_service=llm).generate_guidance(
            tenant_id="tenant-1"))


def test_canonical_success_is_model_advice_with_full_messages_and_scope(db):
    llm = CanonicalOnlyLLM(
        {"success": True, "content": "  MODEL ADVICE  ",
         "text": "MODEL ADVICE"})
    assert not hasattr(llm, "generate_response")

    result = _run(db, llm)

    assert result["message"] == "MODEL ADVICE"
    assert result["guidance_source"] == "model"
    assert "fallback_reason" not in result
    call = llm.calls[0]
    assert call["temperature"] == 0.5
    assert call["tenant_id"] == "tenant-1"
    assert [m["role"] for m in call["messages"]] == ["system", "user"]
    assert "tenant-1" in call["messages"][1]["content"]
    assert "system_prompt" not in call
    assert "user_prompt" not in call


def test_typed_failure_falls_back_and_is_labelled(db):
    llm = CanonicalOnlyLLM({
        "success": False, "content": "", "text": "",
        "failure": {"reason": "policy_blocked", "message": "blocked"}})

    result = _run(db, llm)

    assert "Strong results" in result["message"]
    assert result["guidance_source"] == "heuristic_fallback"
    assert result["fallback_reason"] == "policy_blocked"


def test_empty_generation_falls_back(db):
    llm = CanonicalOnlyLLM({"success": True, "content": "   "})
    result = _run(db, llm)
    assert result["guidance_source"] == "heuristic_fallback"
    assert result["fallback_reason"] == "empty_generation"


def test_non_string_content_is_never_stringified_into_advice(db):
    llm = CanonicalOnlyLLM(
        {"success": True, "content": {"error": "not an answer"}})
    result = _run(db, llm)
    assert result["guidance_source"] == "heuristic_fallback"
    assert result["fallback_reason"] == "invalid_completion_content"
    assert "not an answer" not in result["message"]


def test_exception_falls_back_without_a_second_attempt(db):
    llm = CanonicalOnlyLLM(error=RuntimeError("transport down"))
    result = _run(db, llm)
    assert result["guidance_source"] == "heuristic_fallback"
    assert result["fallback_reason"] == "llm_call_failed"
    assert len(llm.calls) == 1


def test_no_llm_is_declared_heuristic_fallback(db, monkeypatch):
    monkeypatch.setattr(
        "core.auto_dev.advisor_service.AdvisorService._get_llm_service",
        lambda self: None)
    result = _run(db, None)
    assert result["guidance_source"] == "heuristic_fallback"
    assert result["fallback_reason"] == "no_llm"
    assert "Strong results" in result["message"]


def test_no_data_is_not_model_or_heuristic_advice(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        result = asyncio.run(
            AdvisorService(session).generate_guidance(tenant_id="empty"))
    engine.dispose()
    assert result["guidance_source"] == "no_data"
    assert "No evolutionary data" in result["message"]
