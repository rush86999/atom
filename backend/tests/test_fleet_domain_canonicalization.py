"""Goal 13 regression: recruitment must resolve display-label domains.

Live evidence (``fleet-live-matched-roster.log`` lines 417–424): the model
returned ``Finance`` and ``Data_Analysis`` for a seeded, in-scope roster whose
``AgentRegistry.category`` values were exactly ``Finance`` and
``Data_Analysis``. Recruitment compared those labels to its lowercase
canonical vocabulary (``AVAILABLE_DOMAINS`` / ``DOMAIN_ALIASES``), filtered
both, matched nothing, and returned ``no_suitable_specialist_available``.

These tests lock the shared normalization and the scope rules the catalog and
matcher must agree on:
  - display labels resolve through ONE synonym table;
  - the catalog only lists canonical domains present in the user's workspace;
  - matching applies the same workspace AND user eligibility;
  - the Goal 13 replay recruits the seeded specialists instead of dropping
    their domain labels.

Every test uses an isolated scratch SQLite file. No live DB/provider/network.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentRegistry, Tenant, Workspace
from core.recruitment_intelligence_service import (
    RecruitmentIntelligenceService,
    RecruitmentPlan,
)
from core.specialist_matcher import (
    SpecialistMatcher,
    canonical_domain,
    normalize_domain_label,
)


TENANT = "tenant-g13"
WORKSPACE = "workspace-g13"
USER = "user-g13"
OTHER_USER = "user-other"
FOREIGN_TENANT = "tenant-other"
FOREIGN_WORKSPACE = "workspace-other"


@pytest.fixture()
def scratch(tmp_path):
    """Isolated SQLite file (never the live dev DB)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'domain.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield engine, Session
    finally:
        engine.dispose()


def _agent(
    agent_id,
    *,
    name,
    category,
    capabilities,
    tenant=TENANT,
    workspace=WORKSPACE,
    user=USER,
    status="intern",
):
    return AgentRegistry(
        id=agent_id,
        name=name,
        display_name=name,
        category=category,
        module_path="core.generic_agent",
        class_name="GenericAgent",
        tenant_id=tenant,
        workspace_id=workspace,
        user_id=user,
        status=status,
        enabled=True,
        capabilities=list(capabilities),
        specialty=capabilities[0],
    )


def _plan(domains, rationale):
    return RecruitmentPlan(
        goal_analysis="diagnose the quarterly revenue shortfall",
        required_domains=list(domains),
        domain_rationale=dict(rationale),
        complexity_estimate="medium",
        estimated_parallelizable=True,
        suggested_specialist_count=2,
    )


def _service(db, llm):
    return RecruitmentIntelligenceService(
        db=db,
        llm=llm,
        specialist_matcher=SpecialistMatcher(db),
        analytics=MagicMock(),
        fleet_service=MagicMock(),
        optimizer=MagicMock(
            get_optimization_parameters=MagicMock(return_value={})),
        governance=MagicMock(
            can_perform_action_async=AsyncMock(
                return_value={"allowed": True})),
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
    )


def _seed_goal13_roster(db):
    """Reproduce the live matched-roster shape with in/out-of-scope decoys."""
    db.add_all([
        Tenant(id=TENANT, name="Goal 13", subdomain="goal13"),
        Tenant(id=FOREIGN_TENANT, name="Other", subdomain="other"),
        Workspace(id=WORKSPACE, name="Goal 13", tenant_id=TENANT),
        Workspace(id=FOREIGN_WORKSPACE, name="Other", tenant_id=FOREIGN_TENANT),
    ])
    db.add_all([
        _agent("spec-finance", name="Finance Analyst",
               category="Finance", capabilities=["finance"]),
        _agent("spec-data_analysis", name="Data_Analysis Analyst",
               category="Data_Analysis", capabilities=["data_analysis"]),
        # Same categories, foreign workspace: must never be catalogued or
        # recruited even though it is a stronger (autonomous) agent.
        _agent("foreign-finance", name="Foreign Finance", category="Finance",
               capabilities=["finance", "budget", "reconciliation"],
               tenant=FOREIGN_TENANT, workspace=FOREIGN_WORKSPACE,
               status="autonomous"),
        # Same workspace, another user: user eligibility must exclude it.
        _agent("other-user-finance", name="Other User Finance",
               category="Finance", capabilities=["finance", "budget"],
               user=OTHER_USER, status="autonomous"),
    ])
    db.commit()


def test_display_labels_resolve_to_canonical_vocabulary():
    assert normalize_domain_label("Data Analysis") == "data_analysis"
    assert canonical_domain("Finance") == "finance"
    assert canonical_domain("Data_Analysis") == "intelligence"
    assert canonical_domain(" financial analysis ") == "finance"
    assert canonical_domain("Business Intelligence") == "intelligence"
    # Unknown labels stay unknown; recruitment must not invent a domain.
    assert canonical_domain("system") is None
    assert canonical_domain("quantum_ledger") is None
    # ``allowed`` is the AVAILABLE_DOMAINS gate.
    assert canonical_domain("Finance", allowed=["intelligence"]) is None


@pytest.mark.asyncio
async def test_analyze_goal_domains_normalizes_model_labels(scratch):
    _engine, Session = scratch
    db = Session()
    try:
        llm = MagicMock()
        llm.generate_structured_response = AsyncMock(return_value=_plan(
            ["Finance", "Data_Analysis", "Quantum_Ledger"],
            {
                "Finance": "budget variance",
                "Data_Analysis": "trend analysis",
                "Quantum_Ledger": "not a real domain",
            },
        ))
        result = await _service(db, llm).analyze_goal_domains(
            "Diagnose the quarterly revenue shortfall", USER)

        assert result.required_domains == ["finance", "intelligence"]
        assert result.suggested_specialist_count == 2
        assert result.domain_rationale == {
            "finance": "budget variance",
            "intelligence": "trend analysis",
        }
    finally:
        db.close()


@pytest.mark.asyncio
async def test_catalog_lists_only_scoped_canonical_domains(scratch):
    _engine, Session = scratch
    db = Session()
    try:
        _seed_goal13_roster(db)
        catalog = _service(db, MagicMock())._build_domain_catalog(USER)

        # Canonical labels, not registry display labels.
        assert "- Finance: 1 specialist(s) available" in catalog
        assert "- Intelligence: 1 specialist(s) available" in catalog
        assert "Data_Analysis" not in catalog
        # Foreign-workspace and other-user agents do not inflate the count.
        assert "- Finance: 3 specialist(s)" not in catalog
    finally:
        db.close()


@pytest.mark.asyncio
async def test_goal13_display_labels_recruit_scoped_specialists(scratch):
    """The exact live failure: Finance + Data_Analysis must match the roster."""
    _engine, Session = scratch
    db = Session()
    try:
        _seed_goal13_roster(db)
        llm = MagicMock()
        llm.generate_structured_response = AsyncMock(return_value=_plan(
            ["Finance", "Data_Analysis"],
            {"Finance": "budget variance", "Data_Analysis": "trend analysis"},
        ))
        svc = _service(db, llm)

        result = await svc.orchestrate_recruitment(
            goal=(
                "Diagnose the quarterly revenue shortfall against the approved "
                "budget for the leadership review and list the highest-impact "
                "corrective actions. Supplied figures: target 240000 USD, "
                "closed 198000 USD, churn 21000 USD, slipped deals 15000 USD."
            ),
            user_id=USER,
            context={},
            max_specialists=2,
            chain_id="chain-g13",
        )

        assert result["success"] is True, result
        assert result["recruitment_plan"]["required_domains"] == [
            "finance", "intelligence"]
        roster = {item["domain"]: item["agent_id"]
                  for item in result["recruitment_roster"]}
        assert roster == {
            "finance": "spec-finance",
            "intelligence": "spec-data_analysis",
        }
        assert "foreign-finance" not in roster.values()
        assert "other-user-finance" not in roster.values()
    finally:
        db.close()


def test_matcher_enforces_workspace_and_user_eligibility(scratch):
    _engine, Session = scratch
    db = Session()
    try:
        _seed_goal13_roster(db)
        matches = SpecialistMatcher(db).find_specialists_for_domains(
            domains=["finance"],
            user_id=USER,
            workspace_id=WORKSPACE,
            limit_per_domain=10,
        )
        assert [m["agent_id"] for m in matches["finance"]] == ["spec-finance"]
    finally:
        db.close()
