"""
Coverage wave 65b — schema_aware_sql_generator, fusion_router,
resource_reasoning, execution_recovery (TDD, standalone, zero LLM spend).

Covers:
- SchemaAwareSQLGenerator: prompt building (descriptions / types / context),
  SQL extraction (fenced / plain / semicolon / empty), mandatory workspace
  filter injection (WHERE / ORDER BY / GROUP BY / LIMIT / OFFSET / HAVING /
  none, quote escaping, sqlparse failures), LLM error and empty-response
  paths.
- fusion_router: eligibility gate (every condition + batch-task lockdown),
  judge prompt, N parallel samples, quality pre-rank + dominant-candidate
  judge skip, quality-assessment failure fallback, judge success/failure/
  empty/timeout paths, all-samples-fail, partial sample failure.
- ResourceReasoningEngine: optimal assignee scoring (required-skills branch,
  fallback keyword match, multi-word skills, load weighting, bias penalty
  incl. zero/negative bias), empty candidates, owned-session close; burnout
  risk (unknown user, load/overdue thresholds, boundary cases, metrics).
- execution_recovery: workflow + agent sweep, invalid/stale context and
  metadata JSON branches, dict metadata passthrough, idempotency, disabled
  flag, exception rollback path.

No real DB writes: every test uses a fresh in-memory SQLite engine; the
fusion router and SQL generator LLM dependencies are mocked. The real
atom_dev.db is never touched.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(os.getcwd())

import service_delivery.models  # noqa: F401  (registers ProjectTask & friends)
from service_delivery.models import Milestone, Project, ProjectTask

import core.models  # noqa: F401  (registers User, executions, ...)
from core.database import Base
from core.execution_recovery import (
    _CRASH_ERROR_MESSAGE,
    _recover_agent_executions,
    _recover_workflow_executions,
    reconcile_orphaned_executions,
)
from core.llm.fusion_router import (
    FUSION_ENABLED,
    _build_judge_prompt,
    is_fusion_eligible,
    run_fusion,
)
from core.models import (
    AgentExecution,
    ExecutionStatus,
    User,
    Workspace,
    WorkflowExecution,
    WorkflowExecutionStatus,
)
from core.resource_reasoning import ResourceReasoningEngine
from core.schema_aware_sql_generator import SchemaAwareSQLGenerator

import core.execution_recovery as er_mod
import core.resource_reasoning as rr_mod


# ============================================================================
# Shared fixtures / helpers
# ============================================================================


@pytest.fixture
def db_factory():
    """Fresh in-memory SQLite session factory per test (no real DB writes)."""
    configure_mappers()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


def _add_workspace(db, ws_id="ws1"):
    db.add(Workspace(id=ws_id, name=f"Workspace {ws_id}"))
    return ws_id


def _add_project(db, ws_id="ws1", project_id="p1", milestone_id="m1"):
    db.add(Project(id=project_id, workspace_id=ws_id, name="Project 1"))
    db.add(Milestone(id=milestone_id, workspace_id=ws_id, project_id=project_id, name="M1"))
    return project_id, milestone_id


def _add_user(db, uid, first="Alice", last="Expert", skills=None, status="active"):
    """Create a user. ``skills`` is NOT a mapped column on User (the model
    column is commented out) — rows loaded from the DB never carry it, so
    tests exercise the module's graceful getattr fallback. Skill-matching
    branches are covered via fake sessions with SimpleNamespace users."""
    user = User(
        id=uid,
        email=f"{uid}@corp.com",
        first_name=first,
        last_name=last,
        role="member",
        status=status,
    )
    if skills is not None:
        user.skills = skills
    db.add(user)
    return user


def _add_task(
    db,
    task_id,
    assigned_to,
    status="in_progress",
    ws_id="ws1",
    project_id="p1",
    milestone_id="m1",
    due=None,
    name=None,
):
    task = ProjectTask(
        id=task_id,
        workspace_id=ws_id,
        project_id=project_id,
        milestone_id=milestone_id,
        name=name or f"Task {task_id}",
        status=status,
        assigned_to=assigned_to,
        due_date=due,
    )
    db.add(task)
    return task


class _FakeAnalytics:
    """Stand-in for WorkforceAnalyticsService with a per-test bias map."""

    bias: dict = {}

    def __init__(self, db_session=None):
        self.db_session = db_session

    def get_user_bias_profile(self, user_id, workspace_id):
        return {"adjustment_multiplier": _FakeAnalytics.bias.get(user_id, 1.0)}


def _right_value(bin_expr):
    """Extract the literal value from a SQLAlchemy BinaryExpression."""
    right = getattr(bin_expr, "right", None)
    return getattr(right, "value", right)


class _FakeQuery:
    """Query stub supporting the filter/all/count/first chain used by
    ResourceReasoningEngine (no DB, deterministic)."""

    def __init__(self, session, model):
        self._session = session
        self._model = model

    def filter(self, *args):
        for a in args:
            left = getattr(a, "left", None)
            if left is not None and getattr(left, "name", None) == "assigned_to":
                self._session._last_assigned = _right_value(a)
        return self

    def all(self):
        if self._model is User:
            return list(self._session._users)
        return []

    def count(self):
        uid = getattr(self._session, "_last_assigned", None)
        return self._session._load_counts.get(uid, 0)

    def first(self):
        return self._session._users[0] if self._session._users else None


class _FakeSession:
    """Session stub: query() returns _FakeQuery; close() recorded."""

    def __init__(self, users, load_counts=None):
        self._users = users
        self._load_counts = load_counts or {}
        self._last_assigned = None
        self.closed = False

    def query(self, model):
        return _FakeQuery(self, model)

    def close(self):
        self.closed = True


def _skill_user(uid, skills):
    return SimpleNamespace(
        id=uid, first_name=uid, last_name="X", skills=skills, status="active"
    )


class _FakeLLM:
    """Async LLM double with call recording and optional error injection."""

    def __init__(self, result="", error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def _fusion_handler(responses):
    """Build a handler whose generate_response pops the response list
    (exceptions propagate); always returns the last entry beyond the list."""
    handler = MagicMock()
    calls = []

    async def _generate(**kwargs):
        calls.append(kwargs)
        idx = min(len(calls) - 1, len(responses) - 1)
        item = responses[idx]
        if isinstance(item, Exception):
            raise item
        return item

    handler.generate_response = _generate
    return handler, calls


# ============================================================================
# SchemaAwareSQLGenerator
# ============================================================================


class TestSchemaAwareGenerateSQL:
    def test_happy_path_appends_workspace_filter(self):
        llm = _FakeLLM(result="SELECT id FROM tasks")
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="ws_1", llm_service=llm)
        sql = asyncio.run(gen.generate_sql("lead", "Find leads", {"properties": {}}))
        assert sql == "SELECT id FROM tasks WHERE workspace_id = 'ws_1'"
        call = llm.calls[0]
        assert call["temperature"] == 0.0
        assert call["max_tokens"] == 500
        assert "Table: lead" in call["prompt"]
        assert "Find leads" in call["prompt"]
        assert "SELECT queries only" in call["system_instruction"]

    def test_injects_filter_into_existing_where_clause(self):
        llm = _FakeLLM(result="SELECT * FROM t WHERE active = 1")
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=llm)
        sql = asyncio.run(gen.generate_sql("t", "q", {"properties": {}}))
        assert sql == "SELECT * FROM t WHERE workspace_id = 'w' AND active = 1"

    @pytest.mark.parametrize(
        "clause", ["GROUP BY x", "ORDER BY x", "LIMIT 10", "OFFSET 5", "HAVING count(*) > 1"]
    )
    def test_inserts_filter_before_trailing_clause(self, clause):
        llm = _FakeLLM(result=f"SELECT * FROM t {clause}")
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=llm)
        sql = asyncio.run(gen.generate_sql("t", "q", {"properties": {}}))
        # The filter is inserted at the clause boundary (keeps the whitespace
        # that the trailing-clause regex matched — hence the double space).
        assert sql == f"SELECT * FROM t WHERE workspace_id = 'w'  {clause}"

    def test_lowercase_where_is_still_recognized(self):
        llm = _FakeLLM(result="select * from t where active = 1")
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=llm)
        sql = asyncio.run(gen.generate_sql("t", "q", {"properties": {}}))
        assert sql == "select * from t WHERE workspace_id = 'w' AND active = 1"

    def test_escapes_single_quotes_in_workspace_id(self):
        llm = _FakeLLM(result="SELECT * FROM t")
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="O'Reilly", llm_service=llm)
        sql = asyncio.run(gen.generate_sql("t", "q", {"properties": {}}))
        assert "workspace_id = 'O''Reilly'" in sql

    def test_llm_error_raises_value_error(self):
        llm = _FakeLLM(result="", error=RuntimeError("provider down"))
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=llm)
        with pytest.raises(ValueError, match="Failed to generate SQL"):
            asyncio.run(gen.generate_sql("t", "q", {"properties": {}}))

    def test_empty_response_raises_value_error(self):
        llm = _FakeLLM(result="")
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=llm)
        with pytest.raises(ValueError, match="did not generate a valid SQL query"):
            asyncio.run(gen.generate_sql("t", "q", {"properties": {}}))

    def test_non_sql_response_raises_value_error(self):
        llm = _FakeLLM(result="I cannot help with that.")
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=llm)
        with pytest.raises(ValueError, match="did not generate a valid SQL query"):
            asyncio.run(gen.generate_sql("t", "q", {"properties": {}}))

    def test_additional_context_is_injected_into_prompt(self):
        llm = _FakeLLM(result="SELECT 1")
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=llm)
        asyncio.run(
            gen.generate_sql("t", "q", {"properties": {}}, additional_context="ctx info")
        )
        assert "Knowledge Graph Context:\nctx info" in llm.calls[0]["prompt"]


class TestSchemaAwareBuildPrompt:
    def test_fields_with_descriptions_and_context(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        schema = {
            "properties": {
                "name": {"type": "string", "description": "Full name"},
                "age": {"type": "integer", "description": ""},
            }
        }
        prompt = gen._build_schema_aware_prompt(schema, "person", "Who is 30?", "extra")
        assert "Table: person" in prompt
        assert "- name (string): Full name" in prompt
        assert "- age (integer)" in prompt
        assert "System fields (always available): id, workspace_id" in prompt
        assert "Knowledge Graph Context:\nextra" in prompt
        assert "Who is 30?" in prompt

    def test_missing_type_defaults_to_unknown(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        prompt = gen._build_schema_aware_prompt(
            {"properties": {"weird": {"description": "no type"}}}, "t", "q"
        )
        assert "- weird (unknown): no type" in prompt

    def test_empty_properties_and_no_context(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        prompt = gen._build_schema_aware_prompt({"properties": {}}, "t", "q")
        assert "Available fields:\n" in prompt
        assert "Knowledge Graph Context" not in prompt

    def test_default_additional_context_argument(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        prompt = gen._build_schema_aware_prompt({"properties": {}}, "t", "q")
        assert prompt.rstrip().endswith("A:")


class TestSchemaAwareInjectWorkspaceFilter:
    def test_parse_failure_falls_back_to_append(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        with patch("core.schema_aware_sql_generator.sqlparse.parse", side_effect=Exception("boom")):
            sql = gen._inject_workspace_filter("SELECT 1", "w")
        assert sql == "SELECT 1 AND workspace_id = 'w'"

    def test_empty_parse_result_falls_back_to_append(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        with patch("core.schema_aware_sql_generator.sqlparse.parse", return_value=[]):
            sql = gen._inject_workspace_filter("SELECT 1", "w")
        assert sql == "SELECT 1 AND workspace_id = 'w'"

    def test_only_first_where_clause_is_replaced(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        sql = gen._inject_workspace_filter("SELECT * FROM t WHERE a=1 WHERE b=2", "w")
        assert sql == "SELECT * FROM t WHERE workspace_id = 'w' AND a=1 WHERE b=2"

    def test_no_clause_appends_at_end(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        assert gen._inject_workspace_filter("SELECT * FROM t", "w") == (
            "SELECT * FROM t WHERE workspace_id = 'w'"
        )

    def test_workspace_id_is_stringified(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id=42, llm_service=_FakeLLM())
        sql = gen._inject_workspace_filter("SELECT * FROM t", 42)
        assert sql == "SELECT * FROM t WHERE workspace_id = '42'"


class TestSchemaAwareExtractSQL:
    def test_none_and_empty_response(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        assert gen._extract_sql_from_llm_response("") == ""
        assert gen._extract_sql_from_llm_response(None) == ""

    def test_fenced_sql_block(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        sql = gen._extract_sql_from_llm_response("Here:\n```sql\nSELECT * FROM t;\n```")
        assert sql == "SELECT * FROM t;"

    def test_generic_fenced_block_with_select(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        sql = gen._extract_sql_from_llm_response("```\nSELECT 1\n```")
        assert sql == "SELECT 1"

    def test_generic_fenced_block_without_select_returns_empty(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        assert gen._extract_sql_from_llm_response("```\njust prose\n```") == ""

    def test_plain_select_with_trailing_semicolon_stripped(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        sql = gen._extract_sql_from_llm_response("SELECT a, b FROM t WHERE x = 1;")
        assert sql == "SELECT a, b FROM t WHERE x = 1"

    def test_plain_select_without_semicolon(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        assert gen._extract_sql_from_llm_response("SELECT 1") == "SELECT 1"

    def test_no_sql_returns_empty(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        assert gen._extract_sql_from_llm_response("no sql anywhere here") == ""

    def test_whitespace_response_is_stripped_first(self):
        gen = SchemaAwareSQLGenerator(db=None, workspace_id="w", llm_service=_FakeLLM())
        sql = gen._extract_sql_from_llm_response("  \nSELECT 2\n  ")
        assert sql == "SELECT 2"


# ============================================================================
# Fusion router
# ============================================================================


class TestFusionEligibility:
    def test_eligible_when_all_conditions_met(self):
        assert is_fusion_eligible("fusion", "complex", "chat", 3) is True

    @pytest.mark.parametrize("strategy", ["auto", "balanced", None, ""])
    def test_not_eligible_without_fusion_strategy(self, strategy):
        assert is_fusion_eligible(strategy, "complex", "chat", 3) is False

    @pytest.mark.parametrize("tier", ["standard", "versatile", "heavy", "micro", None])
    def test_not_eligible_below_complex_tier(self, tier):
        assert is_fusion_eligible("fusion", tier, "chat", 3) is False

    @pytest.mark.parametrize("task", ["agentic", "extraction", "pdf_ocr", "EXTRACTION"])
    def test_not_eligible_for_batch_task_types(self, task):
        assert is_fusion_eligible("fusion", "complex", task, 3) is False

    def test_eligible_when_task_type_none(self):
        assert is_fusion_eligible("fusion", "complex", None, 2) is True

    def test_not_eligible_with_insufficient_candidates(self):
        assert is_fusion_eligible("fusion", "complex", "chat", 1) is False
        assert is_fusion_eligible("fusion", "complex", "chat", 0) is False

    def test_not_eligible_when_disabled(self, monkeypatch):
        monkeypatch.setattr("core.llm.fusion_router.FUSION_ENABLED", False)
        assert is_fusion_eligible("fusion", "complex", "chat", 3) is False


class TestFusionJudgePrompt:
    def test_includes_all_candidates_and_question(self):
        prompt = _build_judge_prompt("What is 2+2?", ["4", "Four"])
        assert "What is 2+2?" in prompt
        assert "2 candidate answers" in prompt
        assert "--- Candidate 1 ---\n4" in prompt
        assert "--- Candidate 2 ---\nFour" in prompt
        assert "Synthesize the best possible answer" in prompt

    def test_single_candidate(self):
        prompt = _build_judge_prompt("Q", ["only"])
        assert "1 candidate answers" in prompt
        assert "--- Candidate 1 ---" in prompt
        assert "Candidate 2" not in prompt


class TestFusionRunFusion:
    @pytest.mark.asyncio
    async def test_judge_synthesis_returns_result(self):
        handler, calls = _fusion_handler([
            "sample A", "sample B", "sample C", "synthesized answer",
        ])
        result, meta = await run_fusion(
            handler=handler,
            prompt="Best approach?",
            system_instruction="be helpful",
            options=[("openai", "gpt-4o"), ("anthropic", "claude"), ("deepseek", "deepseek-v4")],
            temperature=0.7,
            task_type="chat",
            agent_id=None,
            chain_id=None,
            turn_index=0,
        )
        assert result == "synthesized answer"
        assert meta["fusion"] is True
        assert meta["samples"] == 3
        assert meta["judge_skipped"] is False
        assert meta["best_provider"] == "openai"
        assert meta["best_model"] == "gpt-4o"
        assert len(calls) == 4
        assert calls[-1]["temperature"] == 0.3
        assert "synthesis judge" in calls[-1]["system_instruction"]

    @pytest.mark.asyncio
    async def test_raises_when_all_samples_fail(self):
        handler, _ = _fusion_handler([RuntimeError("down"), RuntimeError("down")])
        with pytest.raises(RuntimeError, match="All fusion samples failed"):
            await run_fusion(
                handler=handler, prompt="p", system_instruction="s",
                options=[("a", "1"), ("b", "2")], temperature=0.7, task_type="chat",
                agent_id=None, chain_id=None, turn_index=0,
            )

    @pytest.mark.asyncio
    async def test_raises_when_all_samples_empty(self):
        handler, _ = _fusion_handler(["", "", ""])
        with pytest.raises(RuntimeError, match="All fusion samples failed"):
            await run_fusion(
                handler=handler, prompt="p", system_instruction="s",
                options=[("a", "1"), ("b", "2"), ("c", "3")], temperature=0.7,
                task_type="chat", agent_id=None, chain_id=None, turn_index=0,
            )

    @pytest.mark.asyncio
    async def test_partial_sample_failure_uses_surviving_sample(self):
        handler, calls = _fusion_handler([RuntimeError("a down"), "survivor", "judge answer"])
        result, meta = await run_fusion(
            handler=handler, prompt="p", system_instruction="s",
            options=[("a", "1"), ("b", "2")], temperature=0.7, task_type="chat",
            agent_id=None, chain_id=None, turn_index=0,
        )
        assert result == "judge answer"
        assert meta["samples"] == 1
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_judge_failure_falls_back_to_best_candidate(self):
        handler, _ = _fusion_handler(["answer one", "answer two", RuntimeError("judge down")])
        result, meta = await run_fusion(
            handler=handler, prompt="p", system_instruction="s",
            options=[("a", "1"), ("b", "2")], temperature=0.7, task_type="chat",
            agent_id=None, chain_id=None, turn_index=0,
        )
        assert meta["judge_failed"] is True
        assert meta["judge_skipped"] is True
        assert result in ("answer one", "answer two")

    @pytest.mark.asyncio
    async def test_empty_judge_result_falls_back(self):
        handler, _ = _fusion_handler(["candidate a", "candidate b", ""])
        result, meta = await run_fusion(
            handler=handler, prompt="p", system_instruction="s",
            options=[("a", "1"), ("b", "2")], temperature=0.7, task_type="chat",
            agent_id=None, chain_id=None, turn_index=0,
        )
        assert meta["judge_failed"] is True
        assert result in ("candidate a", "candidate b")

    @pytest.mark.asyncio
    async def test_dominant_candidate_skips_judge(self):
        handler, calls = _fusion_handler(["clear winner", "weak second"])
        with patch(
            "core.llm.response_quality.assess_response_quality",
            side_effect=[0.9, 0.3],
        ):
            result, meta = await run_fusion(
                handler=handler, prompt="p", system_instruction="s",
                options=[("a", "1"), ("b", "2")], temperature=0.7, task_type="chat",
                agent_id=None, chain_id=None, turn_index=0,
            )
        assert result == "clear winner"
        assert meta["judge_skipped"] is True
        assert meta["best_provider"] == "a"
        assert len(calls) == 2  # no judge call

    @pytest.mark.asyncio
    async def test_second_candidate_high_keeps_judge(self):
        handler, calls = _fusion_handler(["answer x", "answer y", "judge out"])
        with patch(
            "core.llm.response_quality.assess_response_quality",
            side_effect=[0.9, 0.85, 0.3],
        ):
            result, meta = await run_fusion(
                handler=handler, prompt="p", system_instruction="s",
                options=[("a", "1"), ("b", "2"), ("c", "3")], temperature=0.7,
                task_type="chat", agent_id=None, chain_id=None, turn_index=0,
            )
        assert result == "judge out"
        assert meta["judge_skipped"] is False
        assert len(calls) == 4

    @pytest.mark.asyncio
    async def test_quality_scoring_failure_falls_back_to_constant(self):
        handler, _ = _fusion_handler(["answer x", "answer y", "judge out"])
        with patch(
            "core.llm.response_quality.assess_response_quality",
            side_effect=RuntimeError("scorer down"),
        ):
            result, meta = await run_fusion(
                handler=handler, prompt="p", system_instruction="s",
                options=[("a", "1"), ("b", "2")], temperature=0.7, task_type="chat",
                agent_id=None, chain_id=None, turn_index=0,
            )
        assert result == "judge out"
        assert meta["judge_skipped"] is False

    @pytest.mark.asyncio
    async def test_sample_count_capped_by_options_length(self, monkeypatch):
        monkeypatch.setattr("core.llm.fusion_router.FUSION_SAMPLE_COUNT", 5)
        handler, calls = _fusion_handler(["one", "two", "judge"])
        result, meta = await run_fusion(
            handler=handler, prompt="p", system_instruction="s",
            options=[("a", "1"), ("b", "2")], temperature=0.7, task_type="chat",
            agent_id=None, chain_id=None, turn_index=0,
        )
        assert meta["samples"] == 2
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_sample_count_limits_specs(self, monkeypatch):
        monkeypatch.setattr("core.llm.fusion_router.FUSION_SAMPLE_COUNT", 2)
        handler, calls = _fusion_handler(["s1", "s2", "judge"])
        result, meta = await run_fusion(
            handler=handler, prompt="p", system_instruction="s",
            options=[("a", "1"), ("b", "2"), ("c", "3"), ("d", "4")],
            temperature=0.7, task_type="chat", agent_id=None, chain_id=None,
            turn_index=0,
        )
        assert meta["samples"] == 2
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_single_sample_still_judges(self, monkeypatch):
        monkeypatch.setattr("core.llm.fusion_router.FUSION_SAMPLE_COUNT", 1)
        handler, calls = _fusion_handler(["only one", "judge"])
        result, meta = await run_fusion(
            handler=handler, prompt="p", system_instruction="s",
            options=[("a", "1"), ("b", "2")], temperature=0.7, task_type="chat",
            agent_id=None, chain_id=None, turn_index=0,
        )
        assert result == "judge"
        assert meta["best_provider"] == "a"


# ============================================================================
# ResourceReasoningEngine
# ============================================================================


class TestResourceReasoningConstructor:
    def test_stores_db_and_knowledge_manager(self):
        engine = ResourceReasoningEngine(db_session="session")
        assert engine.db == "session"
        assert engine.knowledge_manager is not None

    def test_default_db_is_none(self):
        engine = ResourceReasoningEngine()
        assert engine.db is None


class TestResourceReasoningOptimalAssignee:
    """Real in-memory DB tests: users loaded from rows have NO skills column,
    exercising the graceful fallback. Skill-matching branches are covered by
    the fake-session tests further down."""

    def test_no_users_returns_empty_suggestion(self, db_factory):
        db = db_factory()
        engine = ResourceReasoningEngine(db_session=db)
        result = asyncio.run(engine.get_optimal_assignee("ws1", "Any task"))
        assert result["suggested_user"] is None
        assert result["alternatives"] == []

    def test_picks_lower_load_user_when_skills_equal(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u_free")
        _add_user(db, "u_busy")
        for i in range(3):
            _add_task(db, f"t{i}", "u_busy")
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        result = asyncio.run(engine.get_optimal_assignee("ws1", "Python task"))
        assert result["suggested_user"]["user_id"] == "u_free"
        assert result["suggested_user"]["load"] == 0

    def test_user_without_skills_keeps_base_score(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1")
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        result = asyncio.run(engine.get_optimal_assignee("ws1", "Anything"))
        assert result["suggested_user"]["skill_score"] == 0.5

    def test_bias_penalty_prefers_faster_user(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u_slow")
        _add_user(db, "u_fast")
        db.commit()
        _FakeAnalytics.bias = {"u_slow": 2.0, "u_fast": 0.5}
        with patch("core.resource_reasoning.WorkforceAnalyticsService", _FakeAnalytics):
            engine = ResourceReasoningEngine(db_session=db)
            result = asyncio.run(engine.get_optimal_assignee("ws1", "Python task"))
        assert result["suggested_user"]["user_id"] == "u_fast"
        assert result["suggested_user"]["bias_factor"] == 0.5

    def test_zero_bias_factor_uses_default_penalty(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1")
        db.commit()
        _FakeAnalytics.bias = {"u1": 0.0}
        with patch("core.resource_reasoning.WorkforceAnalyticsService", _FakeAnalytics):
            engine = ResourceReasoningEngine(db_session=db)
            result = asyncio.run(engine.get_optimal_assignee("ws1", "Python task"))
        assert result["suggested_user"]["composite_score"] == 0.5

    def test_negative_bias_factor_uses_default_penalty(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1")
        db.commit()
        _FakeAnalytics.bias = {"u1": -1.0}
        with patch("core.resource_reasoning.WorkforceAnalyticsService", _FakeAnalytics):
            engine = ResourceReasoningEngine(db_session=db)
            result = asyncio.run(engine.get_optimal_assignee("ws1", "Python task"))
        assert result["suggested_user"]["composite_score"] == 0.5

    def test_alternatives_exclude_suggested_and_cap_at_two(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        for i in range(4):
            _add_user(db, f"u{i}")
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        result = asyncio.run(engine.get_optimal_assignee("ws1", "Python task"))
        assert result["suggested_user"]["user_id"] == "u0"
        assert len(result["alternatives"]) == 2
        assert all(a["user_id"] != "u0" for a in result["alternatives"])

    def test_single_candidate_has_no_alternatives(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1")
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        result = asyncio.run(engine.get_optimal_assignee("ws1", "Python task"))
        assert result["suggested_user"]["user_id"] == "u1"
        assert result["alternatives"] == []

    def test_inactive_users_excluded(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u_active", status="active")
        _add_user(db, "u_gone", status="disabled")
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        result = asyncio.run(engine.get_optimal_assignee("ws1", "Python task"))
        assert result["suggested_user"]["user_id"] == "u_active"

    def test_owned_session_is_closed(self, monkeypatch):
        session = MagicMock()
        user = SimpleNamespace(
            id="u1", first_name="A", last_name="B", skills="python", status="active"
        )
        session.query.return_value.filter.return_value.all.return_value = [user]
        session.query.return_value.filter.return_value.count.return_value = 0
        monkeypatch.setattr(rr_mod, "get_db_session", lambda: session)
        with patch("core.resource_reasoning.WorkforceAnalyticsService", _FakeAnalytics):
            engine = ResourceReasoningEngine()
            result = asyncio.run(engine.get_optimal_assignee("ws1", "Python task"))
        assert result["suggested_user"]["user_id"] == "u1"
        session.close.assert_called_once()


class TestResourceReasoningSkillMatching:
    """Skill-matching branches via a deterministic fake session (no DB)."""

    def _suggest(self, users, task_name, description=None, load_counts=None):
        session = _FakeSession(users, load_counts)
        with patch("core.resource_reasoning.WorkforceAnalyticsService", _FakeAnalytics):
            engine = ResourceReasoningEngine(db_session=session)
            result = asyncio.run(
                engine.get_optimal_assignee("ws1", task_name, description)
            )
        return result

    def test_required_skills_full_match_scores_1(self):
        result = self._suggest(
            [_skill_user("u1", "python, sql")],
            "Build ETL",
            "required skills: python, sql.",
        )
        assert result["suggested_user"]["skill_score"] == 1.0

    def test_required_skills_partial_match(self):
        result = self._suggest(
            [_skill_user("u1", "python")],
            "Build ETL",
            "required skills: python, sql.",
        )
        assert result["suggested_user"]["skill_score"] == 0.75

    def test_required_skills_no_match_keeps_base_score(self):
        result = self._suggest(
            [_skill_user("u1", "java")],
            "Build ETL",
            "required skills: python, sql.",
        )
        assert result["suggested_user"]["skill_score"] == 0.5

    def test_required_skills_case_insensitive(self):
        result = self._suggest(
            [_skill_user("u1", "PYTHON")],
            "Build ETL",
            "REQUIRED SKILLS: Python.",
        )
        assert result["suggested_user"]["skill_score"] == 1.0

    def test_required_skills_semicolon_separated(self):
        result = self._suggest(
            [_skill_user("u1", "python, sql")],
            "Build ETL",
            "required skills: python; sql.",
        )
        assert result["suggested_user"]["skill_score"] == 1.0

    def test_required_skills_without_period(self):
        result = self._suggest(
            [_skill_user("u1", "python")],
            "Build ETL",
            "required skills: python",
        )
        assert result["suggested_user"]["skill_score"] == 1.0

    def test_fallback_keyword_match_boosts_to_0_9(self):
        result = self._suggest([_skill_user("u1", "python")], "Write a Python script")
        assert result["suggested_user"]["skill_score"] == 0.9

    def test_multi_word_skill_keyword_match(self):
        result = self._suggest(
            [_skill_user("u1", "data science, sql")], "Data Science model"
        )
        assert result["suggested_user"]["skill_score"] == 0.9

    def test_higher_skill_match_wins_over_base_score(self):
        result = self._suggest(
            [
                _skill_user("u_matched", "python"),
                _skill_user("u_unmatched", "java"),
            ],
            "Python script",
        )
        assert result["suggested_user"]["user_id"] == "u_matched"

    def test_skill_score_weighted_by_fraction_of_requirements(self):
        result = self._suggest(
            [
                _skill_user("u_full", "python, sql, docker"),
                _skill_user("u_one_of_three", "python"),
            ],
            "Build ETL",
            "required skills: python, sql, docker.",
        )
        assert result["suggested_user"]["user_id"] == "u_full"
        assert result["suggested_user"]["skill_score"] == 1.0
        alt = result["alternatives"][0]
        assert alt["user_id"] == "u_one_of_three"
        assert alt["skill_score"] == pytest.approx(0.5 + (1 / 3) * 0.5)

    def test_load_counts_affect_composite_even_with_skills(self):
        users = [
            _skill_user("u_free", "python"),
            _skill_user("u_busy", "python"),
        ]
        result = self._suggest(
            users, "Python task", load_counts={"u_busy": 3, "u_free": 0}
        )
        assert result["suggested_user"]["user_id"] == "u_free"
        assert result["suggested_user"]["load"] == 0


class TestResourceReasoningBurnout:
    def test_unknown_user_returns_unknown(self, db_factory):
        db = db_factory()
        engine = ResourceReasoningEngine(db_session=db)
        assert engine.assess_burnout_risk("missing") == {"risk": "unknown"}

    def test_low_risk_with_no_load_or_overdue(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1", skills="python")
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        risk = engine.assess_burnout_risk("u1")
        assert risk["risk_level"] == "low"
        assert risk["reasons"] == []
        assert risk["metrics"] == {"active_tasks": 0, "overdue_tasks": 0}

    def test_high_load_raises_to_medium(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1", skills="python")
        for i in range(9):
            _add_task(db, f"t{i}", "u1", status="in_progress")
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        risk = engine.assess_burnout_risk("u1")
        assert risk["risk_level"] == "medium"
        assert "high_active_load" in risk["reasons"]
        assert risk["metrics"]["active_tasks"] == 9

    def test_overdue_tasks_raise_to_medium(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1", skills="python")
        past = datetime.now(timezone.utc) - timedelta(days=5)
        for i in range(4):
            _add_task(db, f"t{i}", "u1", status="pending", due=past)
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        risk = engine.assess_burnout_risk("u1")
        assert risk["risk_level"] == "medium"
        assert "multiple_overdue_tasks" in risk["reasons"]
        assert "high_active_load" not in risk["reasons"]

    def test_high_load_plus_overdue_raises_to_high(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1", skills="python")
        past = datetime.now(timezone.utc) - timedelta(days=5)
        for i in range(9):
            _add_task(db, f"t{i}", "u1", status="in_progress")
        for i in range(4):
            _add_task(db, f"o{i}", "u1", status="pending", due=past)
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        risk = engine.assess_burnout_risk("u1")
        assert risk["risk_level"] == "high"
        assert set(risk["reasons"]) == {"high_active_load", "multiple_overdue_tasks"}

    def test_load_boundary_of_8_stays_low(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1", skills="python")
        for i in range(8):
            _add_task(db, f"t{i}", "u1", status="in_progress")
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        assert engine.assess_burnout_risk("u1")["risk_level"] == "low"

    def test_overdue_boundary_of_3_stays_low(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1", skills="python")
        past = datetime.now(timezone.utc) - timedelta(days=5)
        for i in range(3):
            _add_task(db, f"t{i}", "u1", status="pending", due=past)
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        assert engine.assess_burnout_risk("u1")["risk_level"] == "low"

    def test_completed_overdue_tasks_not_counted(self, db_factory):
        db = db_factory()
        _add_workspace(db)
        _add_project(db)
        _add_user(db, "u1", skills="python")
        past = datetime.now(timezone.utc) - timedelta(days=5)
        for i in range(6):
            _add_task(db, f"t{i}", "u1", status="completed", due=past)
        db.commit()
        engine = ResourceReasoningEngine(db_session=db)
        risk = engine.assess_burnout_risk("u1")
        assert risk["risk_level"] == "low"
        assert risk["metrics"]["overdue_tasks"] == 0

    def test_owned_session_is_closed_for_unknown_user(self, monkeypatch):
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        monkeypatch.setattr(rr_mod, "get_db_session", lambda: session)
        engine = ResourceReasoningEngine()
        assert engine.assess_burnout_risk("nobody") == {"risk": "unknown"}
        session.close.assert_called_once()


# ============================================================================
# Execution recovery
# ============================================================================


def _make_workflow_exec(db, status=WorkflowExecutionStatus.RUNNING.value, context="{}"):
    row = WorkflowExecution(
        execution_id=str(uuid.uuid4()),
        workflow_id="wf_test",
        status=status,
        input_data="{}",
        steps="{}",
        outputs="{}",
        context=context,
        version=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_agent_exec(db, status=ExecutionStatus.RUNNING.value, metadata_json=None):
    row = AgentExecution(
        id=str(uuid.uuid4()),
        agent_id="atom_main",
        status=status,
        input_summary="test",
        triggered_by="manual",
        metadata_json=metadata_json,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestExecutionRecoveryWorkflow:
    def test_recovers_running_workflow(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        orphan = _make_workflow_exec(db)
        result = reconcile_orphaned_executions()
        assert result["workflow_recovered"] == 1
        assert result["agent_recovered"] == 0
        db.refresh(orphan)
        assert orphan.status == WorkflowExecutionStatus.FAILED.value
        assert orphan.error == _CRASH_ERROR_MESSAGE
        assert orphan.completed_at is not None
        ctx = json.loads(orphan.context)
        assert ctx["recovery"]["crashed"] is True
        # SQLite round-trips datetimes without tzinfo, so compare the local
        # part only.
        assert ctx["recovery"]["recovered_at"].startswith(
            orphan.completed_at.isoformat().split("+")[0]
        )

    def test_invalid_context_json_is_still_stamped(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        orphan = _make_workflow_exec(db, context="{broken json")
        result = reconcile_orphaned_executions()
        assert result["workflow_recovered"] == 1
        db.refresh(orphan)
        ctx = json.loads(orphan.context)
        assert ctx["recovery"]["crashed"] is True

    def test_none_context_is_still_stamped(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        orphan = _make_workflow_exec(db, context=None)
        reconcile_orphaned_executions()
        db.refresh(orphan)
        ctx = json.loads(orphan.context)
        assert ctx["recovery"]["crashed"] is True

    def test_does_not_touch_terminal_workflows(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        done = _make_workflow_exec(db, status=WorkflowExecutionStatus.COMPLETED.value)
        failed = _make_workflow_exec(db, status=WorkflowExecutionStatus.FAILED.value)
        result = reconcile_orphaned_executions()
        assert result["workflow_recovered"] == 0
        db.refresh(done)
        db.refresh(failed)
        assert done.status == WorkflowExecutionStatus.COMPLETED.value
        assert failed.status == WorkflowExecutionStatus.FAILED.value


class TestExecutionRecoveryAgent:
    def test_recovers_running_agent(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        orphan = _make_agent_exec(db, metadata_json=None)
        result = reconcile_orphaned_executions()
        assert result["agent_recovered"] == 1
        db.refresh(orphan)
        assert orphan.status == ExecutionStatus.FAILED.value
        assert orphan.error_message == _CRASH_ERROR_MESSAGE
        assert orphan.completed_at is not None
        assert orphan.metadata_json["recovery"]["crashed"] is True

    def test_dict_metadata_is_preserved_and_marked(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        orphan = _make_agent_exec(db, metadata_json={"foo": "bar"})
        reconcile_orphaned_executions()
        db.refresh(orphan)
        meta = orphan.metadata_json
        assert meta["foo"] == "bar"
        assert meta["recovery"]["crashed"] is True

    def test_string_metadata_json_falls_back_to_empty(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        orphan = _make_agent_exec(db, metadata_json="hello")
        reconcile_orphaned_executions()
        db.refresh(orphan)
        assert orphan.metadata_json["recovery"]["crashed"] is True

    def test_scalar_metadata_json_falls_back_to_empty(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        orphan = _make_agent_exec(db, metadata_json=5)
        reconcile_orphaned_executions()
        db.refresh(orphan)
        assert orphan.metadata_json["recovery"]["crashed"] is True

    def test_does_not_touch_terminal_agents(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        done = _make_agent_exec(db, status=ExecutionStatus.COMPLETED.value)
        result = reconcile_orphaned_executions()
        assert result["agent_recovered"] == 0
        db.refresh(done)
        assert done.status == ExecutionStatus.COMPLETED.value


class TestExecutionRecoveryReconcile:
    def test_counts_both_types(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        monkeypatch.setattr(er_mod, "RECOVERY_ENABLED", True)
        _make_workflow_exec(db)
        _make_workflow_exec(db)
        _make_agent_exec(db)
        result = reconcile_orphaned_executions()
        assert result == {"workflow_recovered": 2, "agent_recovered": 1, "enabled": True}

    def test_idempotent_second_run(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        monkeypatch.setattr(er_mod, "RECOVERY_ENABLED", True)
        _make_workflow_exec(db)
        _make_agent_exec(db)
        assert reconcile_orphaned_executions()["workflow_recovered"] == 1
        second = reconcile_orphaned_executions()
        assert second["workflow_recovered"] == 0
        assert second["agent_recovered"] == 0
        assert second["enabled"] is True

    def test_no_orphans_reports_zero(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        monkeypatch.setattr(er_mod, "RECOVERY_ENABLED", True)
        result = reconcile_orphaned_executions()
        assert result == {"workflow_recovered": 0, "agent_recovered": 0, "enabled": True}

    def test_disabled_flag_is_noop(self, db_factory, monkeypatch):
        factory = db_factory
        db = factory()
        monkeypatch.setattr(er_mod, "SessionLocal", factory)
        monkeypatch.setattr(er_mod, "RECOVERY_ENABLED", False)
        orphan = _make_workflow_exec(db)
        result = reconcile_orphaned_executions()
        assert result == {"workflow_recovered": 0, "agent_recovered": 0, "enabled": False}
        db.refresh(orphan)
        assert orphan.status == WorkflowExecutionStatus.RUNNING.value

    def test_sweep_exception_rolls_back_and_reports_error(self, monkeypatch):
        fake_session = MagicMock()
        SessionLocal = MagicMock(return_value=fake_session)
        monkeypatch.setattr(er_mod, "SessionLocal", SessionLocal)
        monkeypatch.setattr(er_mod, "RECOVERY_ENABLED", True)
        monkeypatch.setattr(
            er_mod, "_recover_workflow_executions",
            MagicMock(side_effect=RuntimeError("sweep boom")),
        )
        monkeypatch.setattr(er_mod, "_recover_agent_executions", MagicMock(return_value=0))
        result = reconcile_orphaned_executions()
        assert result["enabled"] is True
        assert result["workflow_recovered"] == 0
        assert "sweep boom" in result["error"]
        fake_session.rollback.assert_called_once()
        fake_session.close.assert_called_once()

    def test_recovery_error_message_constant(self):
        assert _CRASH_ERROR_MESSAGE == "Process restarted while execution was running (crashed)"

    def test_module_defaults(self):
        assert isinstance(er_mod.RECOVERY_ENABLED, bool)
        assert isinstance(FUSION_ENABLED, bool)


class TestExecutionRecoveryHelpers:
    def test_recover_workflow_helper_direct_call(self, db_factory):
        db = db_factory()
        orphan = _make_workflow_exec(db)
        assert _recover_workflow_executions(db) == 1
        # The helper mutates in place; the caller commits.
        assert orphan.status == WorkflowExecutionStatus.FAILED.value
        assert orphan.error == _CRASH_ERROR_MESSAGE

    def test_recover_agent_helper_direct_call(self, db_factory):
        db = db_factory()
        orphan = _make_agent_exec(db)
        assert _recover_agent_executions(db) == 1
        assert orphan.status == ExecutionStatus.FAILED.value
        assert orphan.error_message == _CRASH_ERROR_MESSAGE
