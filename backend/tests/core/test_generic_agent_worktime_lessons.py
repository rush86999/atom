"""Work-time application of taught lessons in the GenericAgent runtime.

Lessons taught via /teach (and observed human corrections) are PERMANENT
training. The retrieval + formatting logic lives in
core/student_learning_service.py (covered there); these tests pin the
agent-runtime glue: the lessons recalled into ``memory`` must actually reach
the ReAct system prompt on every task execution — for any agent, at any
maturity tier.
"""

import os
os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import AgentRegistry
from core.generic_agent import GenericAgent, ReActStep
from core.student_learning_service import format_lessons_block


def _agent_model(**cfg_overrides):
    config = {
        "system_prompt": "You are Test Agent.",
        "tools": "*",
        "max_steps": 3,
        **cfg_overrides,
    }
    return AgentRegistry(
        id="agent-lessons-1", name="Test Agent",
        type="assistant", module_path="agents.assistant", class_name="AssistantAgent",
        category="general", configuration=config,
    )


def _build_agent(model):
    with patch("core.generic_agent.WorldModelService"), \
         patch("core.generic_agent.ReflectionService"), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service"), \
         patch("core.generic_agent.LLMService"):
        return GenericAgent(model)


def _stub_llm_surface(agent):
    """Make the collaborative services _react_step touches awaitable/no-op."""
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
    agent.llm = MagicMock()
    agent.llm.generate_structured = AsyncMock(
        return_value=ReActStep(thought="thinking", final_answer="done"))
    return agent


_TAUGHT = [{
    "source": "teacher", "teacher_agent_id": "atom_main", "topic": "tone",
    "lesson": "Address the client as Dr. Reyes, never by first name",
    "learned_at": "2026-08-01T00:00:00+00:00",
}]


@pytest.mark.asyncio
async def test_react_prompt_includes_taught_lessons():
    agent = _stub_llm_surface(_build_agent(_agent_model()))

    memory = {"lessons": _TAUGHT}
    step = await agent._react_step("draft the client update email", memory, "")

    assert step.final_answer == "done"
    # lessons render into the MEMORY CONTEXT section of the turn prompt
    user_prompt = agent.llm.generate_structured.call_args.kwargs["prompt"]
    assert "TRAINING LESSONS" in user_prompt
    assert "Dr. Reyes" in user_prompt


@pytest.mark.asyncio
async def test_react_prompt_without_lessons_stays_clean():
    agent = _stub_llm_surface(_build_agent(_agent_model()))

    await agent._react_step("a task with no lessons", {}, "")

    user_prompt = agent.llm.generate_structured.call_args.kwargs["prompt"]
    assert "TRAINING LESSONS" not in user_prompt


@pytest.mark.asyncio
async def test_react_prompt_lessons_render_survives_failure():
    """A broken renderer must never break the ReAct step (same fault isolation
    as every other memory section)."""
    agent = _stub_llm_surface(_build_agent(_agent_model()))

    with patch("core.student_learning_service.format_lessons_block",
               side_effect=RuntimeError("boom")):
        step = await agent._react_step("task", {"lessons": _TAUGHT}, "")

    assert step.final_answer == "done"


def test_format_block_shared_with_runtime():
    """The runtime renders lessons with the same permanence framing as every
    other work-time surface (chat assembler, canvas edit planner)."""
    block = format_lessons_block(_TAUGHT)
    assert block.startswith("TRAINING LESSONS — PERMANENT INSTRUCTIONS")
    assert "[tone]" in block
