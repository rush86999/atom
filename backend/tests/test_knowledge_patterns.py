"""WikiSkill W2+W3+W4 — the knowledge pattern store (the wiki layer).

Pins: fingerprint dedup grows patterns instead of stacking rows, the
maintainer samples a BALANCED set of failing and passing traces, distills
both failure modes AND success strategies (LLM path + deterministic
fallback), renders the evolver index, and the runtime memory assembler
never gains a raw-wiki leg (W4).
"""
import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.knowledge_pattern_service import (
    distill_from_traces,
    pattern_fingerprint,
    pattern_index,
    recent_patterns,
    sample_traces,
    upsert_pattern,
)
from core.models import AgentEpisode, KnowledgePattern

TABLES = [KnowledgePattern.__table__, AgentEpisode.__table__]
TENANT = "t1"
NOW = datetime.now(timezone.utc)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add_episode(db, episode_id, *, success=True, rating=None,
                task="Consolidate revenue reports", tool_errors=None,
                created_at=None):
    meta = {}
    if tool_errors:
        meta["tool_errors"] = tool_errors
    db.add(AgentEpisode(
        id=episode_id, agent_id="a1", tenant_id=TENANT, workspace_id="ws-1",
        task_description=task, success=success,
        outcome="success" if success else "failure",
        supervisor_rating=rating, metadata_json=meta,
        maturity_at_time="intern",
        created_at=created_at or NOW, updated_at=created_at or NOW,
    ))
    db.commit()


# ── upsert: the wiki grows, it never stacks ─────────────────────────────────

def test_upsert_creates_then_bumps(db):
    row1, created1 = upsert_pattern(
        db, tenant_id=TENANT, name="outlook search 400", kind="failure_mode",
        root_cause="query string contains @ unencoded", workaround="url-encode",
        evidence_id="ep-1")
    row2, created2 = upsert_pattern(
        db, tenant_id=TENANT, name="outlook search 400", kind="failure_mode",
        root_cause="query string contains @ unencoded", workaround="url-encode",
        evidence_id="ep-2")
    assert created1 is True and created2 is False
    assert row1.id == row2.id
    assert row2.occurrence_count == 2
    assert row2.evidence_ids == ["ep-1", "ep-2"]
    assert row2.fingerprint == pattern_fingerprint(TENANT, "failure_mode",
                                                   "outlook search 400")


def test_upsert_caps_evidence(db):
    for i in range(30):
        upsert_pattern(db, tenant_id=TENANT, name="p", kind="failure_mode",
                       evidence_id=f"ep-{i}")
    row, _ = upsert_pattern(db, tenant_id=TENANT, name="p", kind="failure_mode",
                            evidence_id="ep-30")
    assert len(row.evidence_ids) <= 20


def test_upsert_rejects_empty_name(db):
    with pytest.raises(ValueError):
        upsert_pattern(db, tenant_id=TENANT, name="  ", kind="failure_mode")


# ── balanced sampling (W3) ──────────────────────────────────────────────────

def test_sample_traces_is_balanced_failing_plus_passing(db):
    for i in range(7):
        add_episode(db, f"fail-{i}", success=False,
                    tool_errors=[{"signature": "outlook.search_emails",
                                  "error": "400 bad query"}])
    for i in range(5):
        add_episode(db, f"pass-{i}", success=True, rating=5)
    add_episode(db, "rated-low", success=True, rating=2)  # must NOT count

    sample = sample_traces(db, TENANT)
    assert len(sample["failing"]) == 5     # paper cap: ≤5 failing
    assert len(sample["passing"]) == 3     # paper cap: ≤3 passing
    assert all(t["episode_id"] != "rated-low" for t in sample["passing"])
    assert sample["failing"][0]["error"].startswith("outlook.search_emails")


# ── the maintainer ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deterministic_distill_uses_both_trace_kinds(db):
    add_episode(db, "fail-1", success=False,
                tool_errors=[{"signature": "outlook.search_emails",
                              "error": "400: character '@' is not valid"}])
    add_episode(db, "pass-1", success=True, rating=5,
                task="Quarterly revenue consolidation")

    summary = await distill_from_traces(db, TENANT, workspace_id="ws-1",
                                        llm_service=None)
    assert summary["created"] == 2
    kinds = {p.kind for p in recent_patterns(db, TENANT, consumer="evolver")}
    assert kinds == {"failure_mode", "success_strategy"}
    failure = [p for p in recent_patterns(db, TENANT, consumer="evolver") if p.kind == "failure_mode"][0]
    assert "outlook" in failure.name or "@" in failure.root_cause
    assert failure.evidence_ids == ["fail-1"]


@pytest.mark.asyncio
async def test_llm_distill_creates_curated_patterns(db):
    add_episode(db, "fail-1", success=False)
    add_episode(db, "pass-1", success=True, rating=5)

    llm = AsyncMock()
    llm.generate_completion = AsyncMock(return_value={"content":
        '{"patterns": ['
        '{"name": "Unencoded emails in OData filters", "kind": "failure_mode", '
        ' "root_cause": "@ breaks the filter", "workaround": "url-encode", "evidence": "fail-1"},'
        '{"name": "Lead with the summary row", "kind": "success_strategy", '
        ' "root_cause": "rated 5/5 on reports", "workaround": "", "evidence": "pass-1"}]}'
    })
    summary = await distill_from_traces(db, TENANT, llm_service=llm)
    assert summary["mode"] == "llm"
    assert summary["created"] == 2
    names = {p.name for p in recent_patterns(db, TENANT, consumer="evolver")}
    assert "Unencoded emails in OData filters" in names


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_deterministic(db):
    add_episode(db, "fail-1", success=False,
                tool_errors=[{"signature": "zoho.list", "error": "401 unauthorized"}])

    llm = AsyncMock()
    llm.generate_completion = AsyncMock(side_effect=RuntimeError("provider down"))
    summary = await distill_from_traces(db, TENANT, llm_service=llm)
    assert summary["created"] >= 1  # the wiki still grows offline


@pytest.mark.asyncio
async def test_idempotent_distill_bumps_not_stacks(db):
    add_episode(db, "fail-1", success=False,
                tool_errors=[{"signature": "zoho.list", "error": "401"}])
    await distill_from_traces(db, TENANT, llm_service=None)
    await distill_from_traces(db, TENANT, llm_service=None)
    rows = recent_patterns(db, TENANT, consumer="evolver")
    assert len(rows) == 1
    assert rows[0].occurrence_count == 2


# ── the index (wiki/index.md analog) ────────────────────────────────────────

def test_pattern_index_renders_catalog(db):
    upsert_pattern(db, tenant_id=TENANT, name="outlook 400",
                   kind="failure_mode", root_cause="unencoded @", )
    upsert_pattern(db, tenant_id=TENANT, name="summary first",
                   kind="success_strategy", root_cause="rated 5/5")
    index = pattern_index(db, TENANT, consumer="evolver")
    assert "[failure_mode]" in index and "[success_strategy]" in index
    assert "outlook 400" in index
    # other tenants don't leak in
    assert "t2" not in index


def test_pattern_index_empty_when_no_wiki(db):
    assert pattern_index(db, TENANT, consumer="evolver") == ""


# ── W4: the runtime agent never reads the raw wiki ──────────────────────────

# Every module that assembles a RUNTIME prompt for the inference agent. The
# paper's ablation: inference-time wiki access measurably HURTS (63.7→60.9) —
# knowledge reaches the runtime only compiled into approved lessons/playbooks.
# The wiki layer is readable by the OFFLINE skill proposers exclusively.
_RUNTIME_PROMPT_MODULES = (
    "core.memory_context_assembler",
    "core.generic_agent",
    "integrations.chat_orchestrator",
    "core.chat_canvas_editor",
    "core.chat_tool_planner",
    "core.verify_panel",
)

_WIKI_MARKERS = (
    "knowledge_pattern_service",
    "KnowledgePattern",
    "skill_impact_ledger",
    "SkillImpactEntry",
)


@pytest.mark.parametrize("module_name", _RUNTIME_PROMPT_MODULES)
def test_runtime_prompt_modules_have_no_wiki_access(module_name):
    """Pin the import graph of EVERY runtime prompt-assembly path: no wiki
    table or service may be imported into turn-time context."""
    import importlib
    import inspect

    module = importlib.import_module(module_name)
    src = inspect.getsource(module)
    for marker in _WIKI_MARKERS:
        assert marker not in src, (
            f"{module_name} references wiki-layer symbol {marker!r} — "
            "WikiSkill W4 forbids runtime wiki access"
        )


def test_wiki_reads_require_evolver_consumer(db):
    """The read path refuses unlabeled or runtime consumers BY CONSTRUCTION,
    not by convention."""
    from core.knowledge_pattern_service import (
        RuntimeWikiAccessError,
        pattern_index,
        recent_patterns,
    )

    upsert_pattern(db, tenant_id=TENANT, name="guarded pattern",
                   kind="failure_mode", root_cause="rc")

    with pytest.raises(RuntimeWikiAccessError):
        pattern_index(db, TENANT)                      # unlabeled
    with pytest.raises(RuntimeWikiAccessError):
        pattern_index(db, TENANT, consumer="runtime")  # explicit runtime
    with pytest.raises(RuntimeWikiAccessError):
        recent_patterns(db, TENANT)
    with pytest.raises(RuntimeWikiAccessError):
        recent_patterns(db, TENANT, consumer="chat")

    # the offline skill proposer is the only sanctioned reader
    assert "guarded pattern" in pattern_index(db, TENANT, consumer="evolver")


@pytest.mark.asyncio
async def test_proposer_prompts_carry_the_wiki_index(db):
    """The paper's Skill Proposer reads the wiki index (two-step retrieval:
    index first, patterns on demand). Both evolvers render it."""
    upsert_pattern(db, tenant_id=TENANT, name="Unencoded @ in OData filters",
                   kind="failure_mode", root_cause="@ breaks the filter",
                   workaround="url-encode the query")

    from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
    from core.auto_dev.memento_engine import MementoEngine

    llm = AsyncMock()
    llm.generate_completion = AsyncMock(return_value={"content": "def f():\n    pass"})

    memento = MementoEngine(db=db, llm_service=llm)
    await memento.propose_code_change({
        "task_description": "search emails", "error_trace": "",
        "tenant_id": TENANT,
    })
    memento_prompt = llm.generate_completion.await_args.kwargs["messages"][1]["content"]
    assert "KNOWLEDGE PATTERN INDEX" in memento_prompt
    assert "Unencoded @ in OData filters" in memento_prompt

    llm.generate_completion.reset_mock()
    llm.generate_completion = AsyncMock(return_value={"content": "def g():\n    return 1"})
    alpha = AlphaEvolverEngine(db=db, llm_service=llm)
    await alpha.propose_code_change({
        "base_code": "def g():\n    return 0",
        "mutation_prompt": "be faster",
        "tenant_id": TENANT,
    })
    alpha_prompt = llm.generate_completion.await_args.kwargs["messages"][1]["content"]
    assert "KNOWLEDGE PATTERN INDEX" in alpha_prompt
    assert "url-encode the query" in alpha_prompt
