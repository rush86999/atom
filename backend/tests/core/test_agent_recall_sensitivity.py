"""Agent-consumption leg: recall must respect the prompt sensitivity ceiling.

Traced journey gap (2026-08-25 data-journey trace, agent leg):

The turn-fact layer defines ``prompt_sensitivity_ceiling()`` — default
"confidential", documented as "restricted data never enters prompts" (P4
alignment), env ``ATOM_MEMORY_PROMPT_SENSITIVITY_CEILING`` — but:

A-G1. **GenericAgent ignored it**: its Tier-2 vector prefetch AND Tier-1 SQL
   fallback passed no ``max_sensitivity``, while the meta-agent enforced the
   ceiling at both of its call sites. Specialty agents leaked
   restricted-classified durable facts into their prompts.
A-G2. **World-model legs never had it**: ``get_relevant_business_facts`` and
   ``_recall_general_knowledge`` return any semantically-matching row —
   restricted-classified business facts and knowledge flow into EVERY
   agent's prompt (meta + specialty).

Design (research-validated): retrieval-time pre-filtering, not post-filtering
— restricted rows must never become prompt candidates. Legacy rows WITHOUT a
sensitivity stamp pass as "internal" (R83 pre-classification data must not
vanish from recall); present-but-invalid values fail closed.
"""
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest


# ---------------------------------------------------------------------------
# A-G1. GenericAgent durable-fact recall enforces the ceiling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generic_agent_vector_leg_passes_ceiling(monkeypatch):
    from core import generic_agent as ga

    captured: dict = {}

    def fake_prefetch(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        "core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", True
    )
    monkeypatch.setattr(
        "core.turn_fact_extractor.prefetch_relevant_facts", fake_prefetch
    )

    facts = await ga.GenericAgent._recall_durable_facts(
        "quarterly revenue question", workspace_id="ws1"
    )

    assert facts == []
    assert captured.get("max_sensitivity") is not None, (
        "GenericAgent Tier-2 recall must pass the prompt sensitivity ceiling"
    )
    assert captured.get("workspace_id") == "ws1"


@pytest.mark.asyncio
async def test_generic_agent_sql_fallback_passes_ceiling(monkeypatch):
    from core import generic_agent as ga
    from core.models import TurnFact

    captured: dict = {}

    class FakeDB:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        "core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", False
    )

    fact = TurnFact(workspace_id="ws1", fact_text="internal note", category="fact")
    import contextlib

    @contextlib.contextmanager
    def fake_session_local():
        yield FakeDB()

    monkeypatch.setattr(ga, "SessionLocal", fake_session_local)
    monkeypatch.setattr(
        "core.turn_fact_extractor.get_active_facts_for_prompt",
        lambda *a, **k: (captured.update(k), [fact])[1],
    )

    facts = await ga.GenericAgent._recall_durable_facts(
        "anything", workspace_id="ws1"
    )

    assert len(facts) == 1
    assert captured.get("max_sensitivity") is not None, (
        "Tier-1 SQL fallback must also pass the ceiling"
    )


# ---------------------------------------------------------------------------
# A-G2. World-model recall legs respect the ceiling
# ---------------------------------------------------------------------------
@pytest.fixture
def world_model():
    from core.agent_world_model import WorldModelService

    svc = WorldModelService(workspace_id="test-ws")
    yield svc
    # restore env if a test overrode it via monkeypatch — handled by fixture args


@pytest.mark.asyncio
async def test_business_facts_recall_filters_restricted(world_model):
    """restricted > confidential(ceiling) → excluded; internal → kept."""
    rows = [
        {"id": "f-int", "text": "Fact: internal thing", "metadata": {
            "id": "intfact:crm:1", "fact": "internal thing",
            "sensitivity": "internal", "verification_status": "unverified",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        {"id": "f-res", "text": "Fact: ssns of everyone", "metadata": {
            "id": "intfact:hr:2", "fact": "ssns of everyone",
            "sensitivity": "restricted",
            "verification_status": "unverified",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
    ]
    world_model.db = Mock()
    world_model.db.search.return_value = rows

    facts = await world_model.get_relevant_business_facts("ssn query", limit=5)

    ids = [f.id for f in facts]
    assert ids == ["intfact:crm:1"], (
        f"restricted fact must be filtered from prompt recall: {ids}"
    )


@pytest.mark.asyncio
async def test_business_facts_legacy_rows_without_stamp_survive(world_model):
    """Pre-R83 rows carry no sensitivity key — fail OPEN as 'internal'."""
    rows = [
        {"id": "f-old", "text": "Fact: old row", "metadata": {
            "id": "legacy:1", "fact": "old row",
            "verification_status": "unverified",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
    ]
    world_model.db = Mock()
    world_model.db.search.return_value = rows

    facts = await world_model.get_relevant_business_facts("old", limit=5)

    assert [f.id for f in facts] == ["legacy:1"]


@pytest.mark.asyncio
async def test_business_facts_ceiling_disable_switch(world_model, monkeypatch):
    """ATOM_MEMORY_PROMPT_SENSITIVITY_CEILING=none → no filtering (kill switch)."""
    monkeypatch.setenv("ATOM_MEMORY_PROMPT_SENSITIVITY_CEILING", "none")
    rows = [
        {"id": "f-res", "text": "Fact: secret", "metadata": {
            "id": "intfact:x:9", "fact": "secret",
            "sensitivity": "restricted",
            "verification_status": "unverified",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
    ]
    world_model.db = Mock()
    world_model.db.search.return_value = rows

    facts = await world_model.get_relevant_business_facts("secret", limit=5)

    assert [f.id for f in facts] == ["intfact:x:9"]


@pytest.mark.asyncio
async def test_general_knowledge_recall_filters_restricted(world_model):
    """Role-aware knowledge recall must skip above-ceiling vector rows."""
    hits = [
        {"id": "k-ok", "score": 0.1, "metadata": {"file_name": "a.pdf",
                                                   "sensitivity": "internal"}},
        {"id": "k-res", "score": 0.05, "metadata": {"file_name": "b.pdf",
                                                     "sensitivity": "restricted"}},
        # legacy row without a stamp — must survive
        {"id": "k-old", "score": 0.2, "metadata": {"file_name": "c.pdf"}},
    ]
    world_model.db = Mock()
    world_model.db.search.return_value = hits

    results = world_model._recall_general_knowledge(
        world_model.db, "payroll audit", None, 5
    )

    ids = {r["id"] for r in results}
    assert "k-res" not in ids, "restricted knowledge must not reach prompts"
    assert {"k-ok", "k-old"} <= ids
