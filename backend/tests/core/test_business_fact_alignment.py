"""Business-fact write→read alignment (data-journey trace, agent leg).

Documented invariant (integration_ontology_bridge docstring): business-fact
rows must keep **top-level doc_id == metadata["id"]** so ``get_business_fact``
lookups work. The R84 bridge honors it — the two legacy world-model paths did
not:

B-1. ``record_business_fact`` (the ``save_business_fact`` tool path) passed
     NO doc_id → LanceDB auto-generated a *timestamp* top-level id while
     metadata carried the BusinessFact uuid. ``get_business_fact(fact.id)``
     filters on the TOP-LEVEL id → agent-saved truths were permanently
     unfindable by their own handle.
B-2. ``update_fact_verification`` found the row by metadata.id but RE-ADDED
     the corrected version without a doc_id → a second mis-aligned timestamp
     row plus an untracked stale duplicate (append-only store).
"""
from datetime import datetime, timezone

import pytest


class FakeFactStore:
    """LanceDB-handler double keyed by TOP-LEVEL row id."""

    def __init__(self):
        self.rows = {}  # top-level id -> {"text", "metadata"}

    def search(self, table_name=None, query="", limit=100, **k):
        return [
            {"id": rid, "text": r["text"], "metadata": r["metadata"]}
            for rid, r in list(self.rows.items())[:limit]
        ]

    def get_document_by_id(self, table_name, doc_id):
        row = self.rows.get(doc_id)
        return dict(row, id=doc_id) if row else None

    def delete_documents_by_id(self, table_name, doc_id):
        return self.rows.pop(doc_id, None) is not None or True

    def add_document(self, table_name=None, text="", source="", metadata=None,
                     user_id="test", doc_id=None, **k):
        if doc_id is None:
            doc_id = str(datetime.now(timezone.utc).timestamp())
        self.rows[doc_id] = {"text": text, "metadata": metadata or {}}
        return True

    def get_table(self, table_name):
        if table_name != "business_facts":
            return None
        return _FakeFactsTable(self.rows)


class _FakeFactsTable:
    """Minimal lance-table double: search().where("id == 'x'").limit(1)."""

    def __init__(self, rows):
        self._rows = rows
        self._expr = None

    def search(self):
        return self

    def where(self, expr):
        self._expr = expr
        return self

    def limit(self, n):
        return self

    def to_pandas(self):
        import pandas as pd

        rid = ""
        if self._expr and "'" in self._expr:
            rid = self._expr.split("'", 2)[1]
        row = self._rows.get(rid)
        recs = [dict(row, id=rid)] if row else []
        return pd.DataFrame(recs)


@pytest.fixture
def world_model():
    from core.agent_world_model import WorldModelService

    svc = WorldModelService(workspace_id="ws-align")
    svc.db = FakeFactStore()
    return svc


def _fact(fid="truth-1"):
    from core.agent_world_model import BusinessFact

    return BusinessFact(
        id=fid,
        fact="Invoices over $500 need VP approval",
        citations=["policy.pdf:p4"],
        reason="Finance policy",
        source_agent_id="agent-9",
        created_at=datetime.now(timezone.utc),
        last_verified=datetime.now(timezone.utc),
        verification_status="verified",
        metadata={"source": "handbook"},
    )


@pytest.mark.asyncio
async def test_saved_fact_is_findable_by_its_handle(world_model):
    """Roundtrip: save_business_fact → get_business_fact(fact.id) must hit."""
    fact = _fact()
    assert await world_model.record_business_fact(fact) is True

    row = world_model.db.rows.get(fact.id)
    assert row is not None, (
        "writer must stamp top-level doc_id == BusinessFact.id "
        "(get_business_fact filters on the top-level id)"
    )
    fetched = await world_model.get_business_fact(fact.id)
    assert fetched is not None
    assert fetched.fact == fact.fact


@pytest.mark.asyncio
async def test_verification_update_keeps_alignment_and_drops_duplicate(world_model):
    """update_fact_verification: aligned replace — no stale duplicate, same
    top-level id, status updated."""
    fact = _fact()
    await world_model.record_business_fact(fact)

    ok = await world_model.update_fact_verification(fact.id, "outdated")
    assert ok is True

    matching = [rid for rid, r in world_model.db.rows.items()
                if r["metadata"].get("id") == fact.id]
    assert matching == [fact.id], (
        f"replace must stay aligned and leave exactly one row: {matching}"
    )
    assert world_model.db.rows[fact.id]["metadata"]["verification_status"] == "outdated"


@pytest.mark.asyncio
async def test_bridge_written_facts_still_verifiable(world_model):
    """Bridge-written rows (intfact:* with content_hash) remain updatable."""
    from core.integration_ontology_bridge import fact_content_hash

    fid = "intfact:crm:L-1"
    text = "Fact: crm lead 'Acme'\nCitations: crm:L-1\nReason: sync\nStatus: unverified"
    world_model.db.rows[fid] = {
        "text": text,
        "metadata": {
            "id": fid, "fact": "crm lead 'Acme'", "content_hash":
                fact_content_hash(text),
            "verification_status": "unverified",
        },
    }

    ok = await world_model.update_fact_verification(fid, "verified")
    assert ok is True
    assert world_model.db.rows[fid]["metadata"]["verification_status"] == "verified"


# ---------------------------------------------------------------------------
# Same family: experiences must be findable by their own handle
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_record_experience_stamps_doc_id(world_model):
    """record_experience must stamp doc_id == experience.id so
    _get_experience_by_id's direct lookup (and the feedback lifecycle built
    on it) can address the row without relying on a bounded scan fallback."""
    from core.agent_world_model import AgentExperience

    exp = AgentExperience(
        id="exp-9",
        agent_id="agent-1",
        task_type="reconciliation",
        input_summary="Reconcile SKU-123",
        outcome="Success",
        learnings="clean run",
        agent_role="finance",
        timestamp=datetime.now(timezone.utc),
    )
    assert await world_model.record_experience(exp) is True

    assert "exp-9" in world_model.db.rows, (
        "experience row must be stored under its own id"
    )
    row = await world_model._get_experience_by_id("exp-9")
    assert row is not None and row["id"] == "exp-9"
