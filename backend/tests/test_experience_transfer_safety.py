"""WikiSkill W6 — negative-transfer guard for the experience marketplace.

Pins: exported packs carry the source agent's model provenance; imports
land QUARANTINED (validation_state=pending) so a weak-model skill can never
silently degrade a stronger agent (arXiv:2608.27454: 4B skills dropped a
large model's score 50.5%→18.1%); advisory kinds auto-activate on a clean
incident-eval replay while skills wait for explicit human review;
list_active_items never returns quarantined or rejected rows.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.experience_marketplace.pack_service import ExperiencePackService
from core.experience_marketplace.transfer_safety import (
    activate_item,
    auto_validate_import,
    list_active_items,
    pending_items,
    reject_item,
    validate_pending_imports,
)
from core.models import (
    AgentEpisode,
    AgentExecution,
    AgentReasoningStep,
    AgentRegistry,
    Base,
    EpisodeSegment,
    ExperienceExport,
    ExperienceImport,
    ExperienceItem,
    ExperienceRoleRegistry,
    GraphEdge,
    GraphNode,
    IngestionSettings,
    IncidentEval,
    OrgPublicKey,
    Skill,
    Tenant,
    Workspace,
)

TABLES = [
    Tenant.__table__,
    Workspace.__table__,
    AgentRegistry.__table__,
    AgentExecution.__table__,
    AgentEpisode.__table__,
    AgentReasoningStep.__table__,
    EpisodeSegment.__table__,
    ExperienceItem.__table__,
    ExperienceRoleRegistry.__table__,
    ExperienceExport.__table__,
    ExperienceImport.__table__,
    GraphNode.__table__,
    GraphEdge.__table__,
    IngestionSettings.__table__,
    IncidentEval.__table__,
    Skill.__table__,
    OrgPublicKey.__table__,
]

NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(tmp_path / "org_sharing_key"))
    monkeypatch.setenv("ATOM_EXPERIENCE_MARKETPLACE_ENABLED", "true")


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine)()
    session.add(Tenant(id="tenant-1", name="t1", subdomain="t1"))
    session.add(Workspace(id="ws-1", name="w1", tenant_id="tenant-1"))
    session.commit()
    yield session
    session.close()


def add_agent(db, model="qwen-3.5-4B"):
    db.add(AgentRegistry(
        id="agent-1", name="Test Agent", type="personal", category="Operations",
        module_path="core.agents.queen_agent", class_name="QueenAgent",
        workspace_id="ws-1", status="active", configuration={"model": model},
    ))
    db.commit()


def add_episode(db, episode_id, *, task, success):
    db.add(AgentEpisode(
        id=episode_id, agent_id="agent-1", tenant_id="tenant-1",
        workspace_id="ws-1", task_description=task, success=success,
        outcome="success" if success else "failure", supervisor_rating=5,
        metadata_json={"sensitivity": "internal"},
        maturity_at_time="intern",
        topics=["reports"], created_at=NOW, updated_at=NOW,
    ))
    db.commit()


async def _export_pack(db):
    add_episode(db, "ep-1", task="Consolidate revenue reports", success=True)
    add_episode(db, "ep-2", task="Draft budget forecast", success=False)
    return ExperiencePackService().export_pack(db, "ws-1", "agent-1")


# ── provenance + quarantine at import ───────────────────────────────────────

@pytest.mark.asyncio
async def test_import_stamps_provenance_and_quarantines(key_file, db):
    add_agent(db, model="qwen-3.5-4B")
    env = await _export_pack(db)
    assert env["payload"]["source_model"] == "qwen-3.5-4B"

    result = await ExperiencePackService().import_pack(db, env, workspace_id="ws-1")
    assert result["applied"] >= 1

    items = db.query(ExperienceItem).all()
    assert items
    for item in items:
        assert item.validation_state == "pending"   # quarantined, NOT active
        assert item.source_model == "qwen-3.5-4B"

    # the consumer surface sees nothing until validation
    assert list_active_items(db, "ws-1") == []
    assert len(pending_items(db, "ws-1")) == len(items)


# ── auto-validation: advisory kinds activate on a clean replay ──────────────

@pytest.mark.asyncio
async def test_clean_replay_activates_advisory_kinds_holds_skills(
        key_file, db, monkeypatch):
    add_agent(db)
    add_episode(db, "ep-1", task="Consolidate revenue reports", success=True)
    # a public marketplace skill rides in the pack's "skills" section —
    # the paper's catastrophic negative-transfer class
    db.add(Skill(id="sk-1", name="BudgetMerge", description="merge budgets",
                 version="1.0.0", type="function", is_public=True,
                 is_approved=True, tags=["finance"], category="finance",
                 input_schema={}, config={}))
    db.commit()
    env = ExperiencePackService().export_pack(db, "ws-1", "agent-1")
    await ExperiencePackService().import_pack(db, env, workspace_id="ws-1")

    # empty IncidentEval corpus → replay clean (ran=0, failed=0)
    out = await auto_validate_import(db, "ws-1", "tenant-1")
    states = {i.kind: i.validation_state for i in db.query(ExperienceItem).all()}
    assert states.get("pattern") == "active"
    assert states.get("skill") == "pending"   # waits for explicit human review
    assert out["activated"] >= 1 and out["held"] >= 1
    active = list_active_items(db, "ws-1")
    assert {i.kind for i in active} == {"pattern"}


@pytest.mark.asyncio
async def test_failing_replay_holds_everything(key_file, db, monkeypatch):
    add_agent(db)
    env = await _export_pack(db)
    await ExperiencePackService().import_pack(db, env, workspace_id="ws-1")

    async def failing_replay(db, tenant_id="default", limit=20,
                             llm_service=None, eval_ids=None):
        return {"ran": 2, "passed": 1, "failed": 1, "skipped": 0, "results": []}

    monkeypatch.setattr("core.incident_eval_runner.run_evals", failing_replay)
    out = await auto_validate_import(db, "ws-1", "tenant-1")
    assert out["activated"] == 0
    assert out["held"] >= 1
    assert "incident_evals_failing" in out["reason"]
    assert list_active_items(db, "ws-1") == []


# ── explicit human review for skills ────────────────────────────────────────

@pytest.mark.asyncio
async def test_explicit_activate_and_reject(key_file, db):
    add_agent(db)
    env = await _export_pack(db)
    await ExperiencePackService().import_pack(db, env, workspace_id="ws-1")
    item = db.query(ExperienceItem).first()

    assert activate_item(db, "ws-1", item.id) is True
    assert len(list_active_items(db, "ws-1")) == 1

    assert reject_item(db, "ws-1", item.id) is True
    assert list_active_items(db, "ws-1") == []     # rejected never consumable
    assert activate_item(db, "ws-1", "missing-id") is False


# ── changed content re-quarantines; unchanged stays put ─────────────────────

@pytest.mark.asyncio
async def test_reimport_same_content_keeps_state_changed_requarantines(
        key_file, db):
    add_agent(db)
    env = await _export_pack(db)
    svc = ExperiencePackService()
    await svc.import_pack(db, env, workspace_id="ws-1")
    await auto_validate_import(db, "ws-1", "tenant-1")
    item = db.query(ExperienceItem).filter_by(kind="pattern").first()
    assert item.validation_state == "active"

    # identical re-import: applied=0, state untouched
    second = await svc.import_pack(db, env, workspace_id="ws-1")
    assert second["applied"] == 0
    db.expire_all()
    assert db.query(ExperienceItem).filter_by(kind="pattern").first() \
        .validation_state == "active"

    # source episode changed → content hash changes → back to quarantine
    ep = db.query(AgentEpisode).filter_by(id="ep-1").first()
    ep.task_description = "Consolidate revenue reports v2 (revised)"
    db.commit()
    env2 = ExperiencePackService().export_pack(db, "ws-1", "agent-1")
    third = await svc.import_pack(db, env2, workspace_id="ws-1")
    assert third["applied"] >= 1
    db.expire_all()
    assert db.query(ExperienceItem).filter_by(kind="pattern").first() \
        .validation_state == "pending"


# ── maintenance-loop entry ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_pending_imports_sweeps_cohorts(key_file, db):
    add_agent(db)
    env = await _export_pack(db)
    await ExperiencePackService().import_pack(db, env, workspace_id="ws-1")

    results = await validate_pending_imports(db)
    assert len(results) == 1
    assert results[0]["workspace_id"] == "ws-1"
    assert results[0]["activated"] >= 1
