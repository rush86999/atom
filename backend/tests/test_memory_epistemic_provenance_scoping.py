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

# ============================================================================
# Write-path governance — poisoning tripwire
# ============================================================================

class TestPoisoningTripwire:
    @pytest.fixture(autouse=True)
    def _reset_poison_state(self):
        from core import turn_fact_extractor as tfe

        tfe._poison_state.clear()
        tfe._poison_quarantined.clear()
        yield
        tfe._poison_state.clear()
        tfe._poison_quarantined.clear()

    def _svc(self):
        from core.turn_fact_extractor import TurnFactExtractor

        return TurnFactExtractor(workspace_id="ws-1", tenant_id="default")

    @pytest.mark.asyncio
    async def test_repeated_supersessions_quarantine_the_source(self, db):
        """5 supersessions within the window -> subsequent writes quarantined."""
        import uuid as _uuid

        from core.turn_fact_extractor import TurnFactExtractor
        from core import turn_fact_extractor as tfe

        # Unique workspace per run: the store persists across runs (real dev
        # DB) and stale same-text rows would absorb the escalation chain.
        svc = TurnFactExtractor(
            workspace_id=f"ws-poison-{_uuid.uuid4().hex[:8]}", tenant_id="default"
        )
        # Poisoning vector: the SAME fact restated with escalating
        # confidence — each write clears the >+0.1 supersede margin against
        # the current active row (0.2 -> 0.35 -> ... -> 0.95, five
        # supersessions = the tripwire limit).
        kwargs = dict(
            category="exact_value", domain="general",
            tags=None, extraction_source="turn", execution_id=None,
            reasoning_step_id=None, episode_id=None, session_id=None,
            user_id="suspicious-user",
        )
        base = "the agreed SLA is seven days"
        ladder = [0.2, 0.35, 0.5, 0.65, 0.8, 0.95]
        svc._persist_one(fact_text=base, confidence=ladder[0], **{
            k: v for k, v in kwargs.items() if k != "confidence"
        })
        for i, conf in enumerate(ladder[1:]):
            row = svc._persist_one(
                fact_text=base, confidence=conf,
                **{k: v for k, v in kwargs.items() if k != "confidence"},
                _skip_antithrash=True,
            )
            assert row is not None, f"revision {i} did not persist"

        assert "suspicious-user:noexec:nosess" in tfe._poison_quarantined

        # next NEW write from this source lands quarantined, not active
        q = svc._persist_one(
            fact_text="totally new fact from a shady source", confidence=0.9,
            **{k: v for k, v in kwargs.items() if k != "confidence"},
            _skip_antithrash=True,
        )
        assert q is not None and q.status == "quarantined"

    def test_quarantined_rows_excluded_from_recall(self, db):
        db.add(TurnFact(workspace_id="ws-1", extraction_source="turn",
                        fact_text="poisoned claim", category="exact_value",
                        confidence=0.99, content_hash="h-poison",
                        status="quarantined"))
        db.add(TurnFact(workspace_id="ws-1", extraction_source="turn",
                        fact_text="legit claim", category="exact_value",
                        confidence=0.9, content_hash="h-legit",
                        status="active"))
        db.commit()
        from core.turn_fact_extractor import get_active_facts_for_prompt

        rows = get_active_facts_for_prompt(db, "ws-1")
        texts = {r.fact_text for r in rows}
        assert "legit claim" in texts and "poisoned claim" not in texts

    @pytest.mark.asyncio
    async def test_kill_switch_disables_tripwire(self, db):
        from core import turn_fact_extractor as tfe

        svc = self._svc()
        kwargs = dict(
            category="exact_value", domain="general", confidence=0.99,
            tags=None, extraction_source="turn", execution_id=None,
            reasoning_step_id=None, episode_id=None, session_id=None,
            user_id="suspicious-user",
        )
        base = "the contracted vendor is Acme Corp"
        svc._persist_one(fact_text=base, **kwargs)
        with patch.dict("os.environ", {"ATOM_MEMORY_POISON_TRIPWIRE": "false"}):
            for i in range(tfe._POISON_SUPERSEDE_LIMIT + 2):
                svc._persist_one(
                    fact_text=f"{base} revision {i + 2}", **kwargs,
                    _skip_antithrash=True,
                )
        assert not tfe._poison_quarantined, "kill switch must disable quarantine"

    @pytest.mark.asyncio
    async def test_normal_single_supersession_does_not_trigger(self):
        from core import turn_fact_extractor as tfe

        svc = self._svc()
        kwargs = dict(
            category="exact_value", domain="general", confidence=0.99,
            tags=None, extraction_source="turn", execution_id=None,
            reasoning_step_id=None, episode_id=None, session_id=None,
            user_id="normal-user",
        )
        svc._persist_one(fact_text="budget approved at fifty K", **kwargs)
        row = svc._persist_one(
            fact_text="budget approved at sixty K", **kwargs, _skip_antithrash=True,
        )
        assert row is not None and row.status == "active"
        assert not tfe._poison_quarantined

# ============================================================================
# Recall-time sensitivity enforcement (P4 alignment)
# ============================================================================

class TestSensitivityCeiling:
    def _seed_sensitivity_spread(self, db):
        for text, sens in [
            ("public roadmap note", "public"),
            ("internal process note", "internal"),
            ("confidential salary band", "confidential"),
            ("restricted payroll export", "restricted"),
        ]:
            db.add(TurnFact(workspace_id="ws-1", extraction_source="turn",
                            fact_text=text, category="exact_value",
                            confidence=0.9, content_hash=f"h-{sens}",
                            status="active", sensitivity=sens))
        db.commit()

    def test_ceiling_excludes_above_rank(self, db):
        self._seed_sensitivity_spread(db)
        from core.turn_fact_extractor import get_active_facts_for_prompt

        rows = get_active_facts_for_prompt(db, "ws-1", max_sensitivity="internal")
        texts = {r.fact_text for r in rows}
        assert "public roadmap note" in texts
        assert "internal process note" in texts
        assert "confidential salary band" not in texts
        assert "restricted payroll export" not in texts

    def test_confidential_ceiling_keeps_confidential(self, db):
        self._seed_sensitivity_spread(db)
        from core.turn_fact_extractor import get_active_facts_for_prompt

        rows = get_active_facts_for_prompt(db, "ws-1", max_sensitivity="confidential")
        texts = {r.fact_text for r in rows}
        assert "confidential salary band" in texts
        assert "restricted payroll export" not in texts

    def test_no_ceiling_is_legacy_all_rows(self, db):
        self._seed_sensitivity_spread(db)
        from core.turn_fact_extractor import get_active_facts_for_prompt

        assert len(get_active_facts_for_prompt(db, "ws-1")) == 4

    def test_unknown_sensitivity_treated_as_restricted(self, db):
        db.add(TurnFact(workspace_id="ws-1", extraction_source="turn",
                        fact_text="mystery classification", category="exact_value",
                        confidence=0.9, content_hash="h-mystery",
                        status="active", sensitivity="banana"))
        db.commit()
        from core.turn_fact_extractor import get_active_facts_for_prompt

        rows = get_active_facts_for_prompt(db, "ws-1", max_sensitivity="confidential")
        assert rows == []  # conservative: unknown excluded under strict ceilings
        rows_all = get_active_facts_for_prompt(db, "ws-1")
        assert len(rows_all) == 1  # legacy view keeps it

    def test_ceiling_composes_with_prioritize_stated(self, db):
        db.add(TurnFact(workspace_id="ws-1", extraction_source="turn",
                        fact_text="inferred low-sensitivity guess",
                        category="implicit_pref", confidence=0.95,
                        content_hash="h-comp-inf", status="active",
                        epistemic_type="inferred", sensitivity="internal"))
        db.commit()
        import time
        time.sleep(0.02)
        db.add(TurnFact(workspace_id="ws-1", extraction_source="turn",
                        fact_text="stated confidential commitment",
                        category="exact_value", confidence=0.6,
                        content_hash="h-comp-st", status="active",
                        epistemic_type="stated", sensitivity="confidential"))
        db.add(TurnFact(workspace_id="ws-1", extraction_source="turn",
                        fact_text="stated restricted secret",
                        category="exact_value", confidence=0.6,
                        content_hash="h-comp-res", status="active",
                        epistemic_type="stated", sensitivity="restricted"))
        db.commit()
        from core.turn_fact_extractor import get_active_facts_for_prompt

        rows = get_active_facts_for_prompt(
            db, "ws-1", max_sensitivity="confidential", prioritize_stated=True,
        )
        # restricted dropped entirely; stated still ranks before inferred
        assert [r.fact_text for r in rows] == [
            "stated confidential commitment",
            "inferred low-sensitivity guess",
        ]

    @pytest.mark.asyncio
    async def test_prefetch_respects_ceiling(self, db):
        """Tier-2 hydration applies the same ceiling."""
        self._seed_sensitivity_spread(db)
        from core import turn_fact_extractor as tfe

        ids = [r.id for r in db.query(TurnFact).filter(
            TurnFact.workspace_id == "ws-1").all()]
        fake_search = MagicMock(return_value=ids)
        sess_ctx = MagicMock()
        sess_ctx.__enter__.return_value = db
        sess_ctx.__exit__.return_value = False
        with patch("core.turn_fact_extractor.SessionLocal",
                   return_value=sess_ctx), \
             patch("core.turn_fact_vector_store.search_relevant_fact_ids",
                   side_effect=fake_search):
            tfe.TURN_FACT_VECTOR_RECALL_ENABLED = True
            try:
                rows = tfe.prefetch_relevant_facts(
                    "ws-1", "what are the notes?", max_sensitivity="internal",
                )
            finally:
                tfe.TURN_FACT_VECTOR_RECALL_ENABLED = False
        texts = {r.fact_text for r in rows}
        assert "restricted payroll export" not in texts
        assert "internal process note" in texts