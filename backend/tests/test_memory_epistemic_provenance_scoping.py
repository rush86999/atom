"""
Source-attribution memory hardening (re-ranked per external critique):

P1 — actor provenance (comm store):
  - _normalize_message stamps metadata["actor_type"] ("external" for inbound,
    "employee" for outbound) and carries actor_id.
  - derive_actor() maps a stored record to (actor_type, actor_id).
  - search_communications(direction=…) filters on the existing column.
    Auditable who-said-what using existing columns — no schema surgery.

P2 — source-attribution policy + epistemic axis (turn facts):
  - TurnFact.epistemic_type ∈ {stated, inferred} (how we know: a source said
    it vs the agent concluded it). Prompt classifies; invalid/missing →
    stated. HONESTLY SCOPED: schema/prompt addition only — recall ordering
    prefers stated over inferred at equal recency (survey §7.3: source
    attribution outranks confidence); NO SOTA claim without an eval.
  - TurnFact.sensitivity ∈ P4 taint vocabulary (public/internal/confidential/
    restricted), default internal — enables downstream taint alignment;
    enforcement is a separate change.

DEFERRED (until fleet routing ships): role-scoped visibility tiers.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import TurnFact


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _fact(db, *, fact_text="the customer renews March 1", epistemic="stated",
          category="exact_value", confidence=0.9):
    row = TurnFact(
        workspace_id="ws-1",
        extraction_source="turn",
        fact_text=fact_text,
        category=category,
        confidence=confidence,
        content_hash=f"hash-{fact_text}-{epistemic}",
        status="active",
        epistemic_type=epistemic,
    )
    db.add(row)
    db.commit()
    return row


# ============================================================================
# Gap 1 — epistemic typing
# ============================================================================

class TestEpistemicTyping:
    def test_model_default_is_stated(self, db):
        row = TurnFact(workspace_id="ws-1", extraction_source="turn",
                       fact_text="x", category="exact_value", confidence=0.9,
                       content_hash="h-default")
        db.add(row)
        db.commit()
        assert row.epistemic_type == "stated"

    def test_extraction_prompt_classifies_epistemic_origin(self):
        from core.turn_fact_extractor import TurnFactExtractor

        prompt = TurnFactExtractor.EXTRACTION_PROMPT
        assert "stated" in prompt and "inferred" in prompt
        # the output contract must carry the field
        assert '"epistemic"' in prompt or "`epistemic`" in prompt

    @pytest.mark.asyncio
    async def test_parser_honors_inferred_and_defaults_invalid(self):
        from core.turn_fact_extractor import TurnFactExtractor

        svc = TurnFactExtractor.__new__(TurnFactExtractor)
        svc.workspace_id = "ws-1"
        svc.tenant_id = "t-1"
        svc.llm = MagicMock()
        svc.llm.generate = AsyncMock(return_value=(
            '[{"fact": "customer renews March 1", "category": "exact_value", '
            '"epistemic": "stated", "confidence": 0.9},'
            '{"fact": "customer seems price-sensitive", "category": "implicit_pref", '
            '"epistemic": "inferred", "confidence": 0.6},'
            '{"fact": "bogus without field", "category": "decision_reason", '
            '"epistemic": "banana", "confidence": 0.7}]'
        ))
        svc._recent_hashes = set()
        rows = []
        with patch.object(
            svc, "_persist_one",
            side_effect=lambda **kw: (rows.append(kw), kw)[1],
        ):
            await svc._extract(
                text="customer said they renew March 1; seems price-sensitive",
                extraction_source="turn",
                execution_id=None, reasoning_step_id=None,
                episode_id=None, session_id=None, user_id=None,
            )
        epistemics = sorted(r["epistemic_type"] for r in rows)
        assert epistemics == ["inferred", "stated", "stated"]  # banana → stated

    def test_recall_filters_by_epistemic_type(self, db):
        _fact(db, fact_text="stated fact", epistemic="stated")
        _fact(db, fact_text="inferred guess", epistemic="inferred")

        from core.turn_fact_extractor import get_active_facts_for_prompt

        all_rows = get_active_facts_for_prompt(db, "ws-1")
        assert len(all_rows) == 2
        only_stated = get_active_facts_for_prompt(db, "ws-1", epistemic_type="stated")
        assert [r.fact_text for r in only_stated] == ["stated fact"]

    def test_source_attribution_ordering_prefers_stated(self, db):
        """Survey §7.3: user-statement attribution outranks confidence.
        Equal-recency facts surface stated before inferred (tertiary key)."""
        # inferred is NEWER and higher-confidence — still ranks after stated
        newer_inferred = TurnFact(
            workspace_id="ws-1", extraction_source="turn",
            fact_text="inferred guess", category="implicit_pref",
            confidence=0.95, content_hash="h-inf",
            status="active", epistemic_type="inferred",
        )
        older_stated = TurnFact(
            workspace_id="ws-1", extraction_source="turn",
            fact_text="customer stated the SLA", category="exact_value",
            confidence=0.6, content_hash="h-st",
            status="active", epistemic_type="stated",
        )
        db.add_all([newer_inferred])
        db.commit()
        import time
        time.sleep(0.02)
        db.add(older_stated)
        db.commit()
        from core.turn_fact_extractor import get_active_facts_for_prompt

        rows = get_active_facts_for_prompt(
            db, "ws-1", prioritize_stated=True,
        )
        assert [r.epistemic_type for r in rows] == ["stated", "inferred"]
        # default behavior unchanged (recency first)
        rows_default = get_active_facts_for_prompt(db, "ws-1")
        assert rows_default[0].fact_text == "inferred guess"

    def test_sensitivity_column_p4_vocabulary(self, db):
        row = TurnFact(workspace_id="ws-1", extraction_source="turn",
                       fact_text="z", category="exact_value", confidence=0.9,
                       content_hash="h-sens")
        db.add(row)
        db.commit()
        assert row.sensitivity == "internal"  # P4 default

        row2 = TurnFact(workspace_id="ws-1", extraction_source="turn",
                        fact_text="w", category="exact_value", confidence=0.9,
                        content_hash="h-sens2", sensitivity="confidential")
        db.add(row2)
        db.commit()
        assert row2.sensitivity == "confidential"

    def test_sensitivity_carried_through_persist(self):
        from core.turn_fact_extractor import TurnFactExtractor

        svc = TurnFactExtractor(workspace_id="ws-1", tenant_id="default")
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            sess = MagicMock()
            sess.bind = None
            sess.query.return_value.filter.return_value.first.return_value = None
            sl.return_value.__enter__ = lambda s: sess
            sl.return_value.__exit__ = lambda s, *a: False
            row = svc._persist_one(
                fact_text="payroll figures for Q3",
                category="exact_value",
                domain="finance",
                confidence=0.8,
                tags=None,
                extraction_source="turn",
                execution_id=None, reasoning_step_id=None,
                episode_id=None, session_id=None, user_id=None,
                sensitivity="restricted",
            )
        assert row is not None
        assert row.sensitivity == "restricted"
        assert row.epistemic_type == "stated"  # default


# ============================================================================
# Gap 3 — role-scoped visibility
# ============================================================================

# ============================================================================
# Gap 2 — actor provenance in the comm store
# ============================================================================

def _pipe():
    from integrations.atom_communication_ingestion_pipeline import (
        CommunicationIngestionPipeline,
    )

    return CommunicationIngestionPipeline(MagicMock())


class TestActorProvenance:
    def test_inbound_whatsapp_is_external_actor(self):
        pipe = _pipe()
        rec = pipe._normalize_message("whatsapp", {
            "id": "wa1", "direction": "inbound", "from": "+15551234567",
            "text": "Need the invoice resent please",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        assert rec["metadata"]["actor_type"] == "external"
        assert rec["metadata"]["actor_id"] == "+15551234567"

    def test_outbound_email_is_employee_actor(self):
        pipe = _pipe()
        rec = pipe._normalize_message("gmail", {
            "id": "gm1", "from": "me@atom.dev", "to": "client@acme.com",
            "subject": "Re: invoice", "body": "Resending the invoice now",
            "direction": "outbound",
        })
        assert rec["metadata"]["actor_type"] == "employee"
        assert rec["metadata"]["actor_id"] == "me@atom.dev"

    def test_direction_field_overrides_heuristic(self):
        pipe = _pipe()
        rec = pipe._normalize_message("whatsapp", {
            "id": "wa2", "direction": "outbound", "from": "+15559999999",
            "text": "Here is your invoice", "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        assert rec["metadata"]["actor_type"] == "employee"

    def test_derive_actor_from_stored_record(self):
        from integrations.atom_communication_ingestion_pipeline import derive_actor

        stored = {"direction": "inbound", "sender": "ops@acme.com"}
        assert derive_actor(stored) == ("external", "ops@acme.com")
        assert derive_actor({"direction": "outbound", "sender": "me@atom.dev"}) == (
            "employee",
            "me@atom.dev",
        )
        # unknown direction → conservative external attribution
        assert derive_actor({})[0] == "external"

    def test_search_communications_filters_by_direction(self, tmp_path):
        from integrations.atom_communication_ingestion_pipeline import (
            LanceDBMemoryManager,
        )

        pipe = LanceDBMemoryManager(db_path=str(tmp_path / "mem"))
        table = MagicMock()
        builder = MagicMock()
        table.search.return_value = builder
        builder.vector.return_value = builder
        builder.text.return_value = builder
        builder.limit.return_value = builder
        builder.where.return_value = builder
        builder.to_pandas.return_value.to_dict.return_value = []
        pipe.connections_table = table
        pipe.generate_embedding = MagicMock(return_value=[0.0] * 4)
        pipe.search_communications("invoice", direction="inbound")
        where_clauses = [c.args[0] for c in builder.where.call_args_list]
        assert any("direction" in w and "inbound" in w for w in where_clauses)