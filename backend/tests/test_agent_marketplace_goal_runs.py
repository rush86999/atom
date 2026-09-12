"""Agent marketplace × goal runs (2026-09-12).

Selling an agent sells its VERIFIED goal-run track record: packaging
(``package_agent_for_sale``) computes the listing's verified_record from
GoalRun rows — the publisher cannot author any of it — ships the runtime
guidance buyers already get (golden paths from achieved runs, correction
heuristics) plus the approved playbooks the buyer's ``goal_runs.start``
seeds plans from. Installs seed evidence-honest confidence (tier stays
intern — trust is re-earned locally), and a managed agent's finished runs
report usage back to the listing.

Pattern: service-level on the conftest scratch DB (get_db_session routed
to the test session), same as test_canvas_version_tools.
"""

import asyncio
import os
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("TESTING", "1")

import core.database as db_mod
from core.agent_marketplace_service import AgentMarketplaceService
from core.goals.goal_run_service import GoalRunService
from core.models import (
    AgentRegistry,
    AgentTemplate,
    GoalObjective,
    GoalRun,
    GraphNode,
    Playbook,
    User,
    UserRole,
)

WS = "ws-mkt"


@pytest.fixture(autouse=True)
def patched_session(db_session):
    original = db_mod.get_db_session

    @contextmanager
    def _test_session():
        yield db_session

    db_mod.get_db_session = _test_session
    try:
        yield db_session
    finally:
        db_mod.get_db_session = original


@pytest.fixture(autouse=True)
def silence_side_effects(monkeypatch):
    monkeypatch.setattr(
        "core.goals.goal_run_notifications.schedule_notification",
        lambda coro: coro.close() if hasattr(coro, "close") else None)

    async def _noop_outcome(service, run, outcome):
        return None

    monkeypatch.setattr(
        "core.goals.goal_run_learning.record_run_outcome", _noop_outcome)
    # Hermetic by default: the usage tracker opens its OWN session
    # (module-level import — unaffected by patched_session).
    monkeypatch.setattr(
        "core.marketplace_usage_tracker.MarketplaceUsageTracker.track_usage",
        staticmethod(lambda **kw: None))


def _run(env, **kw) -> GoalRun:
    row = GoalRun(
        workspace_id=kw.pop("workspace_id", WS), tenant_id="default",
        status=kw.pop("status", "active"), **kw)
    env.add(row)
    return row


@pytest.fixture
def env(db_session):
    db_session.add(User(
        id="u-seller", email="seller@example.com", first_name="Sel",
        last_name="Ler", role=UserRole.MEMBER.value, status="active"))
    for gid in ("g-achieved", "g-failed", "g-cancelled", "g-any"):
        db_session.add(GoalObjective(
            id=gid, workspace_id=WS, tenant_id="default",
            title=f"Goal {gid}", status="active"))
    db_session.add(AgentRegistry(
        id="agent-quota", name="Quota Agent", category="Sales",
        specialty="sales", module_path="agents.sales",
        class_name="SalesAgent", status="supervised",
        user_id="u-seller", workspace_id=WS,
        configuration={"system_prompt": "You are Quota Agent."}))
    # The workspace KNOWS its customer — packaging must not leak the name.
    db_session.add(GraphNode(
        workspace_id=WS, tenant_id="default", name="WFS Ltd",
        type="company"))
    db_session.add(Playbook(
        tenant_id="default", workspace_id=WS, name="Quote process",
        description="How we quote", trigger_canvas_type="email",
        trigger_keywords=["quote"], approval_state="approved",
        steps=["Research the lead", "Draft the quote", "Human review",
               "Send and follow up"]))
    db_session.add(Playbook(
        tenant_id="default", workspace_id=WS, name="Draft never ships",
        approval_state="draft", steps=["secret draft step"]))
    db_session.commit()

    # The track record being sold: 2 achieved, 1 failed, 1 cancelled.
    achieved_plan = [
        {"id": "s1", "kind": "canvas_work", "title": "Research WFS Ltd"},
        {"id": "s2", "kind": "canvas_work", "title": "Draft quote for WFS Ltd"},
        {"id": "s3", "kind": "human_checkpoint", "title": "Review"},
    ]
    for _ in range(2):
        _run(db_session, agent_id="agent-quota", status="achieved",
             supervision_mode="shadow", role="sales", goal_id="g-achieved",
             plan=achieved_plan, steps_executed=3, human_interventions=1,
             decision_log=[
                 {"kind": "decision", "decision": "ADVANCE", "rationale": "r"},
                 {"kind": "override", "decision": "REPLAN",
                  "rationale": "always verify the customer's legal name "
                               "at companies-house@example.com first"},
             ])
    _run(db_session, agent_id="agent-quota", status="failed",
         supervision_mode="shadow", role="sales", goal_id="g-failed",
         plan=[], steps_executed=2, human_interventions=0,
         decision_log=[{"kind": "decision", "decision": "ADVANCE"}])
    _run(db_session, agent_id="agent-quota", status="cancelled",
         supervision_mode="autonomous", role="sales", goal_id="g-cancelled",
         plan=[], steps_executed=0, human_interventions=0, decision_log=[])
    db_session.commit()
    return db_session


def _svc(env, saas=None):
    return AgentMarketplaceService(
        env, saas_client=saas or MagicMock())


# ------------------------------------------------------------- packaging

class TestPackaging:

    def test_listing_carries_the_verified_record(self, env):
        out = _svc(env).package_agent_for_sale("agent-quota", price=0)
        assert out["success"] is True, out
        record = out["verified_record"]
        assert record["runs"] == {"achieved": 2, "failed": 1,
                                  "cancelled": 1, "active": 0, "total": 4}
        assert record["achieved_rate"] == round(2 / 3, 3)
        assert record["steps_executed"] == 8        # 3+3+2
        assert record["human_interventions"] == 2   # 1+1
        assert record["decisions"] == 3
        assert record["supervision_modes"] == ["autonomous", "shadow"]
        assert record["maturity_at_publish"] == "supervised"

        template = env.query(AgentTemplate).filter(
            AgentTemplate.id == out["template_id"]).one()
        assert template.verified_record == record
        assert template.is_public and template.is_active

    def test_guidance_and_playbooks_ride_along(self, env):
        out = _svc(env).package_agent_for_sale("agent-quota")
        template = env.query(AgentTemplate).filter(
            AgentTemplate.id == out["template_id"]).one()
        bundle = template.anonymized_memory_bundle
        # golden paths: only from ACHIEVED runs (step titles sanitized —
        # the entity-name assertion lives in the leak test below)
        assert len(bundle["golden_paths"]) == 2
        joined = " ".join(bundle["golden_paths"][0]["sequence"])
        assert "Research" in joined and "Draft quote" in joined
        # heuristics: the supervisor's override correction
        assert len(bundle["heuristics"]) == 2
        assert bundle["heuristics"][0]["error_type"] == "goal-run correction"
        # playbooks: approved only — drafts never ship
        playbooks = template.configuration["playbooks"]
        assert [p["name"] for p in playbooks] == ["Quote process"]
        assert playbooks[0]["steps"] == [
            "Research the lead", "Draft the quote", "Human review",
            "Send and follow up"]

    def test_entity_names_and_pii_never_ship(self, env):
        out = _svc(env).package_agent_for_sale("agent-quota")
        template = env.query(AgentTemplate).filter(
            AgentTemplate.id == out["template_id"]).one()
        payload = str(template.anonymized_memory_bundle) + str(
            template.configuration)
        assert "WFS Ltd" not in payload          # graph-known entity tokenized
        assert "companies-house@example.com" not in payload  # PII redacted

    def test_paid_listing_needs_a_verified_achieved_run(self, env):
        svc = _svc(env)
        # agent-quota HAS achieved runs — paid is allowed
        assert svc.package_agent_for_sale("agent-quota", price=9)["success"]
        env.add(AgentRegistry(
            id="agent-fresh", name="Fresh Agent", category="Sales",
            module_path="agents.sales", class_name="FreshAgent",
            status="student", user_id="u-seller", workspace_id=WS))
        env.commit()
        out = svc.package_agent_for_sale("agent-fresh", price=5)
        assert out["success"] is False
        assert "achieved" in out["error"]
        # free listings are always allowed
        assert svc.package_agent_for_sale("agent-fresh", price=0)["success"]

    def test_managed_installs_cannot_be_republished(self, env):
        env.add(AgentRegistry(
            id="agent-copy", name="Copy", category="Sales",
            module_path="core.generic_agent", class_name="GenericAgent",
            status="intern", user_id="u-seller", workspace_id=WS,
            configuration={"marketplace_managed": True,
                           "template_id": "tmpl-x"}))
        env.commit()
        out = _svc(env).package_agent_for_sale("agent-copy")
        assert out["success"] is False

    def test_sale_readiness_is_advisory(self, env):
        out = _svc(env).sale_readiness("agent-quota")
        assert out["success"] is True
        assert out["evidence"]["runs"]["achieved"] == 2
        assert out["paid_listing_blockers"] == []
        assert out["guidance"]["playbooks"] == 1


# --------------------------------------------------------------- install

class TestEvidenceHonestInstall:

    def test_local_install_seeds_from_the_record(self, env):
        published = _svc(env).package_agent_for_sale("agent-quota", price=19)
        # SaaS unreachable → the LOCAL listing serves the install
        saas = MagicMock()
        saas.get_agent_template_sync.return_value = None
        svc = AgentMarketplaceService(env, saas_client=saas)

        out = svc.install_agent(published["template_id"],
                                tenant_id="t-buyer", user_id="u-buyer")
        assert out["success"] is True, out
        # evidence-honest: intern tier, but confidence above the flat 0.55
        # (2 achieved × 0.03 + 8 steps × 0.001) and capped inside the band
        agent = env.query(AgentRegistry).filter(
            AgentRegistry.id == out["agent_id"]).one()
        assert agent.status == "intern"
        assert agent.confidence_score == pytest.approx(0.618, abs=1e-6)
        seed = agent.configuration["seed_evidence"]
        assert seed["source_template_id"] == published["template_id"]
        assert seed["verified_record"]["runs"]["achieved"] == 2
        assert out["verified_record"]["runs"]["achieved"] == 2
        assert out["playbooks_installed"] == 1

        # the buyer's goal_runs.start finds the shipped playbook
        buyer_pb = env.query(Playbook).filter(
            Playbook.tenant_id == "t-buyer").all()
        assert [p.name for p in buyer_pb] == ["Quote process"]
        assert buyer_pb[0].approval_state == "approved"
        assert buyer_pb[0].origin_ids == [
            "marketplace:" + published["template_id"]]

        # idempotent: a second install does not duplicate playbooks
        again = svc.install_agent(published["template_id"],
                                  tenant_id="t-buyer", user_id="u-buyer2")
        assert again["success"] is True
        assert again["playbooks_installed"] == 0
        assert env.query(Playbook).filter(
            Playbook.tenant_id == "t-buyer").count() == 1


# ------------------------------------------------- run outcomes → listing

class TestRunOutcomesFeedTheListing:

    def test_terminal_run_reports_usage_for_managed_agents(self, env,
                                                           monkeypatch):
        calls = []
        monkeypatch.setattr(
            "core.marketplace_usage_tracker.MarketplaceUsageTracker"
            ".track_usage",
            staticmethod(lambda **kw: calls.append(kw)))

        env.add(AgentRegistry(
            id="agent-managed", name="Managed", category="Sales",
            module_path="core.generic_agent", class_name="GenericAgent",
            status="intern", workspace_id=WS,
            configuration={"marketplace_managed": True,
                           "template_id": "tmpl-managed"}))
        svc = GoalRunService(workspace_id=WS, tenant_id="default")
        run = svc.create_run("g-any", agent_id="agent-managed", role="sales")
        svc.transition(run["id"], "active")
        svc.transition(run["id"], "achieved")

        assert calls == [{"item_type": "agent",
                          "item_id": "tmpl-managed", "success": True}]
        # a plain (non-managed) agent's run reports nothing
        calls.clear()
        plain = svc.create_run("g-any", agent_id="agent-quota", role="sales")
        svc.transition(plain["id"], "cancelled")
        assert calls == []


# --------------------------------------------------------------- routes

class TestRoutes:
    """The HTTP boundary (pattern from test_goal_journey_gaps)."""

    def _client(self, env, user_id):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.agent_marketplace_routes import router
        from core.auth import get_current_user
        from core.database import get_db as _get_db
        from unittest.mock import Mock

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: Mock(id=user_id)
        app.dependency_overrides[_get_db] = lambda: env
        return TestClient(app)

    def test_owner_publishes_and_listing_is_buyer_safe(self, env):
        client = self._client(env, "u-seller")
        ready = client.get("/api/agent-marketplace/agents/agent-quota/sale-readiness")
        assert ready.status_code == 200
        assert ready.json()["evidence"]["runs"]["achieved"] == 2

        pub = client.post("/api/agent-marketplace/agents/agent-quota/publish",
                          json={"price": 12.0})
        assert pub.status_code == 200, pub.text
        template_id = pub.json()["template_id"]

        listing = client.get(f"/api/agent-marketplace/templates/{template_id}")
        assert listing.status_code == 200
        body = listing.json()
        assert body["verified_record"]["runs"]["achieved"] == 2
        assert body["guidance"]["playbooks"] == 1
        assert body["price"] == 12.0
        # buyer-safe: no manifest, no memory bundle
        assert "configuration" not in body and "anonymized_memory_bundle" not in body

    def test_non_owner_cannot_publish(self, env):
        env.add(User(
            id="u-other", email="other@example.com", first_name="Oth",
            last_name="Er", role=UserRole.MEMBER.value, status="active"))
        env.commit()
        client = self._client(env, "u-other")
        resp = client.post("/api/agent-marketplace/agents/agent-quota/publish",
                           json={"price": 0})
        assert resp.status_code == 403

    def test_paid_gate_maps_to_409(self, env):
        env.add(AgentRegistry(
            id="agent-fresh", name="Fresh Agent", category="Sales",
            module_path="agents.sales", class_name="FreshAgent",
            status="student", user_id="u-seller", workspace_id=WS))
        env.commit()
        client = self._client(env, "u-seller")
        resp = client.post("/api/agent-marketplace/agents/agent-fresh/publish",
                           json={"price": 5})
        assert resp.status_code == 409
        assert "achieved" in resp.json()["detail"]
