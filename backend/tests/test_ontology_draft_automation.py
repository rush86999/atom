"""Ontology draft promotion automation tests.

Covers the consent-gated loop in ``core/ontology/ontology_draft_automation``
mirroring fleet/stage-router/trust-calibration semantics:

- off mode: pass is a no-op, no ledger rows
- auto + evidence: promotion applies immediately (ledger state ``applied``)
- evidence floors: age, usage, evolution (since last decision), samples
- revocation is ALWAYS automatic when a previously-applied type loses its
  evidence (zero usage, no new evolution, stale)
- approve mode queues; admin approve applies, reject marks rejected
- notify mode records + notifies once (cooldown), never activates
- manual decisions (PATCH is_active stamps) are never overridden
- system types are never in scope
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from core.models import (
    EntityTypeDefinition,
    EntityTypeVersionHistory,
    GraphNode,
    OntologyDraftAction,
)

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"name": {"type": "string"}},
}


@pytest.fixture
def odb():
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    for t in (
        EntityTypeDefinition.__table__,
        EntityTypeVersionHistory.__table__,
        GraphNode.__table__,
        OntologyDraftAction.__table__,
    ):
        t.create(engine)
    return sessionmaker(bind=engine)()


@pytest.fixture
def fresh(monkeypatch):
    """Automation module keeps module-level config; reset per test."""
    import core.ontology.ontology_draft_automation as auto

    monkeypatch.setattr(auto, "_mode", None)
    monkeypatch.setattr(auto, "_interval_min", None)
    monkeypatch.setattr(auto, "_last_pass_monotonic", 0.0)
    monkeypatch.setattr(auto, "_notified_keys", {})
    monkeypatch.setattr(auto, "_last_pass_result", None)
    return auto


def _draft(odb, tenant="t1", slug="ws1_crm_crm_leads", version=1, meta=None,
           age_days=5, active=False, system=False):
    now = datetime.now(timezone.utc)
    d = EntityTypeDefinition(
        id=f"et-{slug}",
        tenant_id=tenant,
        slug=slug,
        display_name=slug.replace("_", " ").title(),
        json_schema=SCHEMA,
        is_active=active,
        is_system=system,
        version=version,
        metadata_json=meta or {},
        created_at=now - timedelta(days=age_days),
        updated_at=now - timedelta(days=age_days),
    )
    odb.add(d)
    odb.commit()
    return d


def _nodes(odb, type_, n, tenant="t1", workspace="ws1"):
    for i in range(n):
        odb.add(GraphNode(
            id=f"{type_}-{i}", tenant_id=tenant, workspace_id=workspace,
            name=f"node-{i}", type=type_,
        ))
    odb.commit()


def _manual(odb, draft, is_active, by="user:1", age_min=0):
    meta = dict(draft.metadata_json or {})
    meta.setdefault("manual_decisions", []).append({
        "is_active": is_active,
        "at": (datetime.now(timezone.utc) - timedelta(minutes=age_min)).isoformat(),
        "by": by,
    })
    draft.metadata_json = meta
    odb.commit()


class TestConsentModes:
    def test_off_mode_noop(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "off")
        _draft(odb, age_days=10)
        _nodes(odb, "crm_leads", 5)

        out = fresh.run_automation_pass(odb, force=True)
        assert out["ran"] is False
        assert odb.query(OntologyDraftAction).count() == 0

    def test_auto_promotes_on_usage_evidence(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto")
        draft = _draft(odb, slug="ws1_crm_crm_leads", age_days=5)
        _nodes(odb, "crm_leads", 3)  # suffix match: ws1_crm_crm_leads → crm_leads

        out = fresh.run_automation_pass(odb, force=True)
        assert out["ran"] and len(out["promoted"]) == 1
        row = odb.query(OntologyDraftAction).first()
        assert row.state == "applied" and row.verdict == "promote"
        assert row.evidence_json["node_count"] == 3
        assert "crm_leads" in row.evidence_json["matching_labels"]

        odb.expire_all()
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is True

    def test_auto_promotes_on_recurring_evolution(self, odb, fresh, monkeypatch):
        """version>=2 (discovered twice with different shapes) is evidence
        even with zero graph nodes."""
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto")
        draft = _draft(odb, slug="evolved_type", version=2, age_days=5)
        odb.add(EntityTypeVersionHistory(
            id="vh-1", tenant_id="t1", entity_type_id=draft.id, version=1,
            json_schema=SCHEMA, display_name="Evolved", schema_hash="h1",
        ))
        odb.commit()

        out = fresh.run_automation_pass(odb, force=True)
        assert len(out["promoted"]) == 1
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is True

    def test_young_draft_never_promotes(self, odb, fresh, monkeypatch):
        """One ingestion burst is not a recurring type."""
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto")
        _draft(odb, slug="ws1_crm_crm_leads", age_days=0)
        _nodes(odb, "crm_leads", 10)

        out = fresh.run_automation_pass(odb, force=True)
        assert out["promoted"] == []
        assert any("age" in " ".join(h["reasons"]) for h in out["held"])
        assert odb.query(EntityTypeDefinition).first().is_active is False

    def test_approve_mode_queues_and_admin_applies(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "approve")
        draft = _draft(odb, slug="ws1_crm_crm_leads", age_days=5)
        _nodes(odb, "crm_leads", 3)

        out = fresh.run_automation_pass(odb, force=True)
        assert len(out["queued"]) == 1
        row = odb.query(OntologyDraftAction).first()
        assert row.state == "approval"
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is False

        assert fresh.approve_action(odb, row.id) is True
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is True
        assert odb.query(OntologyDraftAction).first().state == "applied"

    def test_reject_marks_rejected_and_apply_refused(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "approve")
        draft = _draft(odb, slug="ws1_crm_crm_leads", age_days=5)
        _nodes(odb, "crm_leads", 3)

        out = fresh.run_automation_pass(odb, force=True)
        row = odb.query(OntologyDraftAction).first()
        assert row.state == "approval"
        assert fresh.reject_action(odb, row.id) is True
        assert fresh.approve_action(odb, row.id) is False
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is False

    def test_notify_mode_records_and_cooldowns(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "notify")
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_NOTIFY_COOLDOWN_HOURS", "24")
        _draft(odb, slug="ws1_crm_crm_leads", age_days=5)
        _nodes(odb, "crm_leads", 3)
        notified = []
        monkeypatch.setattr(fresh, "_notify", lambda t, m: notified.append(t))

        out1 = fresh.run_automation_pass(odb, force=True)
        out2 = fresh.run_automation_pass(odb, force=True)

        assert out1["notified"] and out2["notified"] == []
        assert len(notified) == 1  # cooldown dedupes
        row = odb.query(OntologyDraftAction).first()
        assert row.state == "notified"
        assert odb.query(EntityTypeDefinition).first().is_active is False


class TestAutomaticRevocation:
    def test_stale_unused_type_revokes_automatically(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto")
        draft = _draft(odb, slug="ws1_crm_crm_leads", age_days=30)
        _nodes(odb, "crm_leads", 3)

        out = fresh.run_automation_pass(odb, force=True)
        assert len(out["promoted"]) == 1
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is True

        # Evidence evaporates: nodes deleted, schema unchanged, stale.
        odb.query(GraphNode).delete()
        odb.commit()
        out2 = fresh.run_automation_pass(odb, force=True)
        assert len(out2["revoked"]) == 1
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is False
        states = [r.state for r in odb.query(OntologyDraftAction)
                  .order_by(OntologyDraftAction.id).all()]
        assert states == ["applied", "revoked"]

    def test_revocation_is_automatic_in_approve_mode_too(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "approve")
        draft = _draft(odb, slug="ws1_crm_crm_leads", age_days=30)
        _nodes(odb, "crm_leads", 3)
        fresh.run_automation_pass(odb, force=True)
        row = odb.query(OntologyDraftAction).first()
        fresh.approve_action(odb, row.id)
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is True

        odb.query(GraphNode).delete()
        odb.commit()
        out = fresh.run_automation_pass(odb, force=True)
        # Revocation never waits for consent — no approval row was created.
        assert len(out["revoked"]) == 1
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is False

    def test_revoked_type_needs_new_evolution_to_return(self, odb, fresh, monkeypatch):
        """A revoked type's stale evolution signal must not re-promote it."""
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto")
        _draft(odb, slug="evolved_type", version=1, age_days=30)
        # Usage-only promotion: version 1 + nodes.
        _nodes(odb, "evolved_type", 3)
        fresh.run_automation_pass(odb, force=True)
        odb.expire_all()
        assert odb.query(EntityTypeDefinition).filter_by(id="et-evolved_type").first().is_active is True

        odb.query(GraphNode).delete()
        odb.commit()
        out = fresh.run_automation_pass(odb, force=True)
        assert len(out["revoked"]) == 1
        # No new evolution since the revoke decision: version still 1.
        out2 = fresh.run_automation_pass(odb, force=True)
        assert out2["promoted"] == []
        odb.expire_all()
        assert odb.query(EntityTypeDefinition).filter_by(id="et-evolved_type").first().is_active is False

        # Discovery sees the type again with a new shape: version 2 → re-promote.
        d = odb.query(EntityTypeDefinition).filter_by(id="et-evolved_type").first()
        d.version = 2
        odb.commit()
        out3 = fresh.run_automation_pass(odb, force=True)
        assert len(out3["promoted"]) == 1
        odb.expire_all()
        assert odb.query(EntityTypeDefinition).filter_by(id="et-evolved_type").first().is_active is True


class TestManualDecisionsNeverOverridden:
    def test_manual_retirement_shelves_promotion(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto")
        draft = _draft(odb, slug="ws1_crm_crm_leads", age_days=5)
        _manual(odb, draft, is_active=False)
        _nodes(odb, "crm_leads", 10)

        out = fresh.run_automation_pass(odb, force=True)
        assert out["manual_held"] == ["ws1_crm_crm_leads"]
        assert odb.query(OntologyDraftAction).count() == 0
        assert odb.query(EntityTypeDefinition).first().is_active is False

    def test_manual_promotion_defers_automation_revoke(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto")
        draft = _draft(odb, slug="ws1_crm_crm_leads", age_days=30)
        _nodes(odb, "crm_leads", 3)
        fresh.run_automation_pass(odb, force=True)  # automated promotion
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is True

        # Human explicitly signed off on it AFTER the automation acted.
        d = odb.query(EntityTypeDefinition).filter_by(id=draft.id).first()
        _manual(odb, d, is_active=True)
        odb.query(GraphNode).delete()
        odb.commit()

        out = fresh.run_automation_pass(odb, force=True)
        assert out["revoked"] == []  # human decision newer than automation wins
        assert odb.query(EntityTypeDefinition).filter_by(id=draft.id).first().is_active is True


class TestScopeAndCensus:
    def test_system_types_never_in_scope(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto")
        _draft(odb, slug="SystemDraft", system=True, age_days=30)
        _nodes(odb, "systemdraft", 10)

        out = fresh.run_automation_pass(odb, force=True)
        assert out["drafts_scanned"] == 0
        census = fresh.census(odb)
        assert census["drafts_total"] == 0

    def test_census_reports_state(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "approve")
        _draft(odb, slug="ws1_crm_crm_leads", age_days=5)
        _nodes(odb, "crm_leads", 3)
        _draft(odb, slug="ws1_crm_crm_prospects", age_days=5)  # no evidence

        census = fresh.census(odb)
        assert census["drafts_total"] == 2
        assert census["drafts_eligible"] == 1
        assert census["eligible_slugs"] == ["ws1_crm_crm_leads"]

    def test_sample_count_floor_applies_when_present(self, odb, fresh, monkeypatch):
        monkeypatch.setenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto")
        draft = _draft(odb, slug="llm_found_type", age_days=5,
                       meta={"sample_count": 1})
        _nodes(odb, "llm_found_type", 5)

        out = fresh.run_automation_pass(odb, force=True)
        assert out["promoted"] == []  # samples 1 < 3 floor
        d = odb.query(EntityTypeDefinition).filter_by(id=draft.id).first()
        d.metadata_json = {**dict(d.metadata_json or {}), "sample_count": 3}
        odb.commit()
        out2 = fresh.run_automation_pass(odb, force=True)
        assert len(out2["promoted"]) == 1


class TestRoutesAndStamping:
    @pytest.mark.asyncio
    async def test_invalid_mode_rejected(self):
        from fastapi import HTTPException

        import backend.api.ontology_draft_routes as routes

        with pytest.raises(HTTPException) as exc:
            await routes.set_automation(mode="bogus")
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_manual_decision_stamped_on_patch(self, odb, monkeypatch):
        import backend.api.entity_type_routes as routes
        from core.entity_type_service import EntityTypeService

        svc = EntityTypeService(db=odb)
        created = svc.create_entity_type(
            tenant_id="ws1", slug="ws1_crm_crm_leads",
            display_name="Crm Leads", json_schema=SCHEMA, is_active=False,
        )
        with patch.object(routes, "get_entity_type_service", return_value=svc):
            await routes.update_entity_type(
                workspace_id="ws1",
                entity_type_id=str(created.id),
                request=routes.EntityTypeUpdate(is_active=True),
                current_user=SimpleAdmin(),
            )
        refreshed = svc.get_entity_type("ws1", entity_type_id=str(created.id))
        assert refreshed.is_active is True
        decisions = refreshed.metadata_json["manual_decisions"]
        assert decisions[-1]["is_active"] is True
        assert decisions[-1]["by"] == "user:u1"


class SimpleAdmin:
    id = "u1"
    role = "team_lead"
