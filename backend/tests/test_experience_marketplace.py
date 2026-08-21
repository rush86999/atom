"""Experience Marketplace — signed, sanitized lesson packs + reputation.

Covers the pack service (docs/architecture/EXPERIENCE_MARKETPLACE.md):
- sanitizer: role tokens, PII redaction, bucketing, leak scan
- export: sensitivity gate, ceiling+destination, signing, audit, delta cursor
- canvas lessons (feature #7 summaries from EpisodeSegment.canvas_context)
- import: verify-before-parse, idempotent apply, tombstones, ontology
  raised-never-lowered + no stub edges, credential fail-closed
- reputation: tier from verified steps, cards
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import org_sharing_crypto
from core.experience_marketplace.sanitizer import (
    RoleRegistry,
    bucket_value,
    guess_kind,
    redact_pii,
    sanitize_text,
    scan_for_leak,
)
from core.experience_marketplace.pack_service import (
    ExperiencePackService,
    PackError,
    _read_cursor,
)
from core.ingestion_profile_service import canonical_payload, payload_hash
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
    Skill.__table__,
    OrgPublicKey.__table__,
]

NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(tmp_path / "org_sharing_key"))
    monkeypatch.setenv("ATOM_EXPERIENCE_MARKETPLACE_ENABLED", "true")


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Tenant(id="tenant-1", name="t1", subdomain="t1"))
    session.add(Workspace(id="ws-1", name="w1", tenant_id="tenant-1"))
    session.commit()
    yield session
    session.close()


def add_agent(db, agent_id="agent-1", workspace_id="ws-1"):
    db.add(AgentRegistry(id=agent_id, name="Test Agent", type="personal",
                         category="Operations", module_path="core.agents.queen_agent",
                         class_name="QueenAgent", workspace_id=workspace_id, status="active"))
    db.commit()
    return agent_id


def add_execution(db, agent_id="agent-1", workspace_id="ws-1"):
    execution = AgentExecution(id=str(uuid4()), agent_id=agent_id, tenant_id="tenant-1",
                               workspace_id=workspace_id, status="completed")
    db.add(execution)
    db.commit()
    return execution.id


def add_episode(db, agent_id="agent-1", episode_id=None, outcome="success",
                task="Consolidate Acme Corp revenue reports", rating=5, feedback=0.8,
                efficiency=1.2, sensitivity="internal", updated_at=None,
                topics=None, metadata_json=None):
    ep = AgentEpisode(
        id=episode_id or f"ep-{abs(hash(task)) % 10**6}",
        agent_id=agent_id, tenant_id="tenant-1", workspace_id="ws-1",
        task_description=task, maturity_at_time="intern", outcome=outcome,
        success=outcome == "success", supervisor_rating=rating,
        aggregate_feedback_score=feedback, step_efficiency=efficiency,
        confidence_score=0.9, metadata_json=metadata_json or {"sensitivity": sensitivity},
        topics=topics or ["finance_reporting"],
        updated_at=updated_at or NOW, created_at=NOW,
    )
    db.add(ep)
    db.commit()
    return ep


def add_steps(db, execution_id, verified_count=3, unverified=1):
    steps = []
    for i in range(verified_count):
        steps.append(AgentReasoningStep(
            execution_id=execution_id, step_number=i, step_type="action",
            thought="think", action={"tool": "tool"}, observation="ok",
            verified="verified", confidence=1.0,
        ))
    for i in range(unverified):
        steps.append(AgentReasoningStep(
            execution_id=execution_id, step_number=100 + i, step_type="action",
            thought="think", action={"tool": "tool"}, observation="ok",
            verified="unverified", confidence=0.5,
        ))
    db.add_all(steps)
    db.commit()


def add_segment(db, episode_id, canvas_type="sheets", summary=None, created_at=None,
                verification="verified", critical=None):
    seg = EpisodeSegment(
        id=f"seg-{episode_id}-{canvas_type}",
        episode_id=episode_id, segment_type="canvas_update", sequence_order=0,
        content="content", content_summary="summary", source_type="canvas",
        canvas_context={
            "canvas_type": canvas_type,
            "presentation_summary": summary or "Agent presented revenue table on sheets canvas",
            "summary_verification": verification,
            "summary_source": "llm",
            "summary_richness": 0.85,
            "visual_elements": ["table", "chart"],
            "user_interaction": "user approved",
            "critical_data_points": critical or {"revenue": 4200, "workflow_id": "wf-secret-1"},
            "outcome": "success",
        },
        created_at=created_at or NOW,
    )
    db.add(seg)
    db.commit()
    return seg


def add_graph(db, node_names, edges=None):
    nodes = {}
    for name, ntype in node_names:
        node = GraphNode(workspace_id="ws-1", tenant_id="tenant-1", name=name,
                         type=ntype, description=f"node about {name}", sensitivity="internal")
        db.add(node)
        db.flush()
        nodes[(name, ntype)] = node.id
    for (s, st, t, tt, rel) in (edges or []):
        db.add(GraphEdge(workspace_id="ws-1", tenant_id="tenant-1",
                         source_node_id=nodes[(s, st)], target_node_id=nodes[(t, tt)],
                         relationship_type=rel, properties={"weight": 1.0}))
    db.commit()
    return nodes


class TestSanitizer:
    def test_role_tokens_deterministic_and_persisted(self, db):
        reg = RoleRegistry(db, "ws-1")
        assert reg.token_for("Acme Corp", "company") == reg.token_for("Acme Corp", "company")
        assert reg.token_for("Acme Corp", "company") == "company_001"
        assert reg.token_for("Globex", "company") == "company_002"
        assert db.query(ExperienceRoleRegistry).count() == 2

    def test_sanitize_text_replaces_entities_and_redacts_pii(self, db):
        reg = RoleRegistry(db, "ws-1")
        reg.token_for("Acme Corp", "company")
        out = sanitize_text(
            "Acme Corp emailed alice@acme.com at +1 (415) 555-0132 https://acme.io/sales",
            reg,
        )
        assert "Acme Corp" not in out and "company_001" in out
        assert "alice" not in out and "<email>" in out
        assert "415" not in out and "<phone>" in out
        assert "https" not in out and "<url>" in out

    def test_bucket_value_never_verbatim(self):
        assert bucket_value(4200, "amount") == "amount:[1K,10K]"
        assert bucket_value(150, "count") == "count:[100,1K]"
        assert bucket_value(90, "duration") == "duration:[1m,10m]"
        assert bucket_value(0.8, "ratio") == "ratio:0.8"
        assert bucket_value("2026-08-20", "date") == "date:2026-Q3"
        weird = bucket_value("wf-secret-1", "identity")
        assert weird.startswith("identity:") and len(weird) < 20

    def test_guess_kind_identity_keys(self):
        assert guess_kind("workflow_id") == "identity"
        assert guess_kind("revenue") == "amount"
        assert guess_kind("row_count") == "count"
        assert guess_kind("duration_seconds") == "duration"

    def test_redact_pii(self):
        out = redact_pii("reach jane@doe.org or 555-123-4567")
        assert "jane" not in out and "<email>" in out and "<phone>" in out

    def test_scan_for_leak(self):
        assert scan_for_leak(["ok company_001 token"], ["Acme Corp"]) == []
        assert scan_for_leak(["Acme Corp still here"], ["Acme Corp"]) == ["Acme Corp"]


class TestExport:
    async def test_full_export_sanitized_and_signed(self, key_file, db):
        add_agent(db)
        ep = add_episode(db, task="Consolidate Acme Corp revenue reports")
        exec_id = add_execution(db)
        ep.execution_id = exec_id
        add_steps(db, exec_id, verified_count=3)
        db.commit()
        add_segment(db, ep.id)
        add_graph(db, [("Acme Corp", "company"), ("Rishi", "person")],
                  edges=[("Acme Corp", "company", "Rishi", "person", "reports_to")])
        db.add(Skill(id="sk-1", name="BudgetMerge", description="merge budgets",
                     version="1.0.0", type="function", is_public=True, is_approved=True,
                     tags=["finance"], category="finance", input_schema={}, config={}))
        db.commit()

        env = ExperiencePackService().export_pack(db, "ws-1", "agent-1")

        payload = env["payload"]
        assert env["kind"] == "atom_experience_pack"
        sections = payload["sections"]

        # patterns: lesson text tokenized, no proprietary identity survives
        pattern = sections["patterns"][0]
        assert pattern["kind"] == "pattern"
        assert "Acme" not in pattern["payload"]["lesson"]
        assert "outcome: success" in pattern["payload"]["lesson"]
        assert pattern["payload"]["verified_step_count"] == 3
        assert pattern["payload"]["supervisor_rating"] == 5
        assert pattern["payload"]["conditions"] == {}

        # canvas lessons: identity keys dropped, amounts bucketed
        lesson = sections["canvas_lessons"][0]
        assert lesson["payload"]["canvas_type"] == "sheets"
        assert lesson["payload"]["summary_verification"] == "verified"
        assert "wf-secret" not in str(lesson["payload"]["critical_data_points"])
        assert lesson["payload"]["critical_data_points"]["revenue"] == "amount:[1K,10K]"
        assert "table" in lesson["payload"]["visual_elements"]

        # ontology: tokens, no real names
        tokens = {n["role"] for n in sections["ontology"]["nodes"]}
        assert all("Acme" not in t and "Rishi" not in t for t in tokens)
        assert sections["ontology"]["edges"][0]["relationship_type"] == "reports_to"
        assert sections["ontology"]["edges_skipped_unresolved"] == 0

        # skills: public marketplace skills only
        assert sections["skills"][0]["payload"]["name"] == "BudgetMerge"

        # signed + audited
        assert env["signature"]
        db_exp = db.query(ExperienceExport).one()
        assert db_exp.agent_id == "agent-1"
        assert db_exp.item_count == 6
        assert db_exp.excluded_by_sensitivity == {}
        assert org_sharing_crypto.verify_payload(db, canonical_payload(env["payload"]),
                                                 env["signature"], "ws-1")

    async def test_sensitivity_gate_default_excludes_high(self, key_file, db):
        add_agent(db)
        add_episode(db, task="conf task", outcome="success",
                    metadata_json={"sensitivity": "confidential"})
        add_episode(db, task="restr task", outcome="failure",
                    metadata_json={"sensitivity": "restricted"})
        env = ExperiencePackService().export_pack(db, "ws-1", "agent-1")
        assert env["excluded_by_sensitivity"] == {"confidential": 1, "restricted": 1}
        assert env["payload"]["sections"]["patterns"] == []

    async def test_raised_ceiling_requires_destination(self, key_file, db):
        add_agent(db)
        add_episode(db, task="conf task", outcome="success",
                    metadata_json={"sensitivity": "confidential"})
        add_episode(db, task="secret task", outcome="success",
                    metadata_json={"sensitivity": "restricted"})
        with pytest.raises(PackError):
            ExperiencePackService().export_pack(
                db, "ws-1", "agent-1", sensitivity_ceiling="confidential")
        env = ExperiencePackService().export_pack(
            db, "ws-1", "agent-1", sensitivity_ceiling="confidential",
            destination="portfolio-co")
        assert env["excluded_by_sensitivity"] == {"restricted": 1}
        assert len(env["payload"]["sections"]["patterns"]) == 1
        export = db.query(ExperienceExport).one()
        assert export.destination == "portfolio-co"
        assert export.sensitivity_ceiling == "confidential"

    async def test_invalid_ceiling_and_unknown_section(self, key_file, db):
        add_agent(db)
        svc = ExperiencePackService()
        with pytest.raises(PackError):
            svc.export_pack(db, "ws-1", "agent-1", sensitivity_ceiling="wild")
        with pytest.raises(PackError):
            svc.export_pack(db, "ws-1", "agent-1", include=["chat_logs"])

    async def test_delta_cursor_and_repeat_export(self, key_file, db):
        add_agent(db)
        add_episode(db, task="early task", updated_at=NOW - timedelta(days=2))
        svc = ExperiencePackService()
        env1 = svc.export_pack(db, "ws-1", "agent-1")
        cursor = env1["payload"]["cursor"]["updated_at"]
        assert cursor and env1["payload"]["delta"] is False

        add_episode(db, task="later task", updated_at=NOW + timedelta(hours=1))
        env2 = svc.export_pack(db, "ws-1", "agent-1", since=cursor)
        assert env2["payload"]["delta"] is True
        lessons = env2["payload"]["sections"]["patterns"]
        assert len(lessons) == 1 and "later task" in lessons[0]["payload"]["lesson"]

    async def test_leak_scan_aborts_export(self, key_file, db):
        add_agent(db)
        # Identity registered in the registry (from ontology)…
        add_graph(db, [("Acme Corp", "company")])
        # …but appearing in the episode text in a different case, so the
        # exact-case token replacement misses it → post-assembly scan aborts.
        add_episode(db, task="Consolidate ACME CORP revenue reports")
        with pytest.raises(PackError):
            ExperiencePackService().export_pack(db, "ws-1", "agent-1")

    async def test_flag_disabled_refuses(self, db):
        svc = ExperiencePackService()
        with pytest.raises(PackError):
            svc.export_pack(db, "ws-1", "agent-1")
        with pytest.raises(PackError):
            svc.reputation_for_agent(db, "ws-1", "agent-1")

    async def test_canvas_lessons_dedupe_and_flagged_kept(self, key_file, db):
        add_agent(db)
        ep = add_episode(db, task="canvas task")
        add_segment(db, ep.id)
        add_segment(db, ep.id, canvas_type="terminal",
                    summary="Agent ran deployment check in terminal", verification="flagged",
                    critical={"exit_code": 0, "command": "deploy --prod"})
        env = ExperiencePackService().export_pack(db, "ws-1", "agent-1")
        lessons = env["payload"]["sections"]["canvas_lessons"]
        assert len(lessons) == 2
        by_type = {l["payload"]["canvas_type"]: l for l in lessons}
        assert by_type["terminal"]["payload"]["summary_verification"] == "flagged"
        # command is an identity — dropped from critical data
        assert "deploy" not in str(by_type["terminal"]["payload"]["critical_data_points"])


class TestImport:
    async def _export(self, db):
        return ExperiencePackService().export_pack(db, "ws-1", "agent-1")

    async def test_import_applies_idempotently(self, key_file, db):
        add_agent(db)
        ep = add_episode(db, task="Consolidate Acme Corp revenue reports")
        exec_id = add_execution(db)
        ep.execution_id = exec_id
        db.commit()
        add_segment(db, ep.id)
        add_graph(db, [("Acme Corp", "company"), ("Rishi", "person")],
                  edges=[("Acme Corp", "company", "Rishi", "person", "reports_to")])
        env = await self._export(db)

        svc = ExperiencePackService()
        first = await svc.import_pack(db, env, workspace_id="ws-1")
        assert first["applied"] == 2
        assert first["nodes"] == 2 and first["edges"] == 1 and first["edges_skipped"] == 0

        items = db.query(ExperienceItem).all()
        assert len(items) == 2
        assert {i.kind for i in items} == {"pattern", "canvas_lesson"}

        second = await svc.import_pack(db, env, workspace_id="ws-1")
        assert second["applied"] == 0 and second["skipped"] == 2
        assert db.query(ExperienceImport).count() == 2

        # ontology: import creates token-named rows; the workspace's own graph
        # (real names) is the source's data and stays untouched
        roles = [n["role"] for n in env["payload"]["sections"]["ontology"]["nodes"]]
        imported = db.query(GraphNode).filter(
            GraphNode.workspace_id == "ws-1", GraphNode.name.in_(roles)
        ).all()
        assert len(imported) == 2
        assert all("Acme" not in n.name and "Rishi" not in n.name for n in imported)
        assert db.query(GraphNode).filter(GraphNode.workspace_id == "ws-1").count() == 4

    async def test_import_rejects_tampered_and_unverified(self, key_file, db):
        add_agent(db)
        add_episode(db, task="do a thing")
        env = await self._export(db)

        bad = dict(env)
        bad["payload"]["sections"]["patterns"][0]["payload"]["lesson"] = "tampered"
        with pytest.raises(PackError):
            await ExperiencePackService().import_pack(db, bad, workspace_id="ws-1")
        audit = db.query(ExperienceImport).one()
        assert audit.signature_valid is False
        assert audit.failure_reason == "signature_verification_failed"

        unver = dict(env)
        unver["signature"] = "AAAA"
        with pytest.raises(PackError):
            await ExperiencePackService().import_pack(db, unver, workspace_id="ws-1")

    async def test_import_credential_fail_closed(self, key_file, db, monkeypatch):
        import core.blueprint_sanitizer as sanitizer
        monkeypatch.setattr(sanitizer, "strip_credentials", lambda obj: obj)
        add_agent(db)
        evil = {
            "kind": "atom_experience_pack",
            "payload": {
                "pack_version": 1,
                "source_agent_id": "agent-1",
                "sensitivity_ceiling": "public",
                "sections": {"patterns": [{
                    "item_id": "ep:evil:1", "kind": "pattern", "sensitivity": "public",
                    "payload": {"lesson": "take over", "api_key": "sk-evil123", "password": "p"},
                }]},
            },
        }
        sig, pub = org_sharing_crypto.sign_payload(canonical_payload(evil["payload"]))
        evil["payload_hash"] = payload_hash(evil["payload"])
        evil["signature"] = sig
        evil["signed_by"] = pub
        with pytest.raises(PackError):
            await ExperiencePackService().import_pack(db, evil, workspace_id="ws-1")
        assert db.query(ExperienceImport).one().failure_reason == "credential_shaped_data"
        assert db.query(ExperienceItem).count() == 0

    async def test_import_tombstones_and_bad_kind(self, key_file, db):
        add_agent(db)
        add_episode(db, task="task one")
        env = await self._export(db)
        await ExperiencePackService().import_pack(db, env, workspace_id="ws-1")
        victim = db.query(ExperienceItem).filter(ExperienceItem.kind == "pattern").first()
        env["payload"]["sections"]["patterns_tombstones"] = [{"item_id": victim.item_id}]
        env["payload_hash"] = payload_hash(env["payload"])
        env["signature"] = org_sharing_crypto.sign_payload(
            canonical_payload(env["payload"]))[0]
        result = await ExperiencePackService().import_pack(db, env, workspace_id="ws-1")
        assert result["tombstones"] == 1
        db.refresh(victim)
        assert victim.superseded_at is not None

        with pytest.raises(PackError):
            await ExperiencePackService().import_pack(
                db, {"kind": "not-a-pack", "payload": {"pack_version": 1}}, workspace_id="ws-1")

    async def test_import_ontology_no_stub_edges(self, key_file, db):
        add_agent(db)
        add_graph(db, [("Acme Corp", "company"), ("Rishi", "person"), ("John", "person")],
                  edges=[("Acme Corp", "company", "Rishi", "person", "reports_to"),
                         ("Acme Corp", "company", "John", "person", "collaborates_with")])
        env = await self._export(db)

        # Raise one node's sensitivity so the edge to it is dropped at export.
        john = db.query(GraphNode).filter(GraphNode.name == "John").first()
        john.sensitivity = "confidential"
        db.commit()

        env2 = await self._export(db)
        onto = env2["payload"]["sections"]["ontology"]
        assert onto["edges_skipped_unresolved"] == 1
        assert len(onto["edges"]) == 1

        result = await ExperiencePackService().import_pack(db, env2, workspace_id="ws-1")
        assert result["nodes"] == 2 and result["edges"] == 1 and result["edges_skipped"] == 0
        roles = [n["role"] for n in onto["nodes"]]
        token_ids = [row.id for row in db.query(GraphNode).filter(
            GraphNode.workspace_id == "ws-1", GraphNode.name.in_(roles)).all()]
        imported_edges = db.query(GraphEdge).filter(
            GraphEdge.workspace_id == "ws-1",
            GraphEdge.source_node_id.in_(token_ids),
        ).all()
        assert len(imported_edges) == 1  # no stub, no dangling target
        assert db.query(GraphEdge).filter(
            GraphEdge.workspace_id == "ws-1").count() == 3  # workspace's own graph intact

    async def test_import_reapply_raises_never_lowers_and_upsert(self, key_file, db):
        add_agent(db)
        ep = add_episode(db, task="task one")
        env = await self._export(db)
        await ExperiencePackService().import_pack(db, env, workspace_id="ws-1")

        # Modify payload (same item, changed lesson) → update, not duplicate.
        env2 = dict(env)
        pattern = env2["payload"]["sections"]["patterns"][0]
        pattern["payload"]["lesson"] = pattern["payload"]["lesson"] + " (rev 2)"
        sig, pub = org_sharing_crypto.sign_payload(canonical_payload(env2["payload"]))
        env2["payload_hash"] = payload_hash(env2["payload"])
        env2["signature"] = sig
        result = await ExperiencePackService().import_pack(db, env2, workspace_id="ws-1")
        assert result["applied"] == 1 and result["skipped"] == 0
        rows = db.query(ExperienceItem).filter(ExperienceItem.kind == "pattern").all()
        assert len(rows) == 1
        assert "rev 2" in rows[0].payload["lesson"]


class TestReputation:
    async def test_tiers_from_verified_steps(self, key_file, db):
        add_agent(db, agent_id="intern")
        ep = add_episode(db, agent_id="intern", task="t1")
        exec_id = add_execution(db, agent_id="intern")
        ep.execution_id = exec_id
        db.commit()
        add_steps(db, exec_id, verified_count=7)
        add_episode(db, agent_id="intern", task="t2", outcome="failure", rating=2, feedback=-0.5)

        card = ExperiencePackService().reputation_for_agent(db, "ws-1", "intern")
        assert card["maturity"] == "INTERN"
        assert card["episodes_total"] == 2
        assert card["verified_execution_count"] == 7
        assert card["success_rate"] == 0.5
        assert card["outcome_breakdown"] == {"success": 1, "failure": 1}
        assert card["export_count"] == 0

    async def test_autonomous_tier(self, key_file, db):
        add_agent(db, agent_id="auto")
        ep = add_episode(db, agent_id="auto", task="t")
        exec_id = add_execution(db, agent_id="auto")
        ep.execution_id = exec_id
        db.commit()
        add_steps(db, exec_id, verified_count=60)
        card = ExperiencePackService().reputation_for_agent(db, "ws-1", "auto")
        assert card["maturity"] == "AUTONOMOUS"

    async def test_unknown_agent_raises(self, key_file, db):
        with pytest.raises(PackError):
            ExperiencePackService().reputation_for_agent(db, "ws-1", "ghost")

    async def test_cursor_persisted_on_delta_import(self, key_file, db):
        add_agent(db)
        add_episode(db, task="delta task")
        env = ExperiencePackService().export_pack(db, "ws-1", "agent-1")
        env["payload"]["delta"] = True
        env["payload"]["cursor"] = {"updated_at": "2026-08-20T00:00:00+00:00"}
        sig, pub = org_sharing_crypto.sign_payload(canonical_payload(env["payload"]))
        env["payload_hash"] = payload_hash(env["payload"])
        env["signature"] = sig
        await ExperiencePackService().import_pack(db, env, workspace_id="ws-1")
        assert _read_cursor(db, "ws-1") == {"updated_at": "2026-08-20T00:00:00+00:00"}