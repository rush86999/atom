"""The normal governed TASK route must persist its exact execution parent.

Regression for the producer-side gap behind an interrupted live fleet whose
``DelegationChain.root_execution_id`` was NULL: the governed TASK branch created
a durable ``AgentExecution`` and then called ``initialize_fleet`` without ever
passing that id, so crash recovery had no parent-to-chain binding to follow.
The routing audit UUID is not a substitute -- the link must be the exact
persisted ``AgentExecution.id``.

Everything runs on a per-test scratch SQLite file. The recovery step runs in a
FRESH python process against that same scratch file, so the binding is proven
durable rather than an in-memory side effect of the test process.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

os.environ["TESTING"] = "1"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.atom_meta_agent as ama
from core.database import Base
from core.fleet_admiral import TaskAnalysis
from core.intent_classifier import (
    IntentCategory as RouteIntentCategory,
    IntentClassification as RouteIntent,
)
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    ChainLink,
    DelegationChain,
    ExecutionStatus,
    Tenant,
    Workspace,
)
from core.recruitment_intelligence_service import RecruitmentPlan

TENANT = "tenant-ops"
WORKSPACE = "ws-ops"
OTHER_TENANT = "tenant-other"
OTHER_WORKSPACE = "ws-other"
USER = "user-ops"
RUN_EXECUTION_ID = "925ddba9-d989-4db9-9e2c-fd03ea272023"


def _task_analysis() -> TaskAnalysis:
    return TaskAnalysis(
        complexity="medium",
        required_capabilities=["operations"],
        estimated_duration="30 minutes",
        specialist_count=1,
        reasoning="one operations specialist",
    )


def _recruitment_plan() -> RecruitmentPlan:
    return RecruitmentPlan(
        goal_analysis="office-work checklist",
        required_domains=["operations"],
        domain_rationale={"operations": "draft the checklist"},
        complexity_estimate="medium",
        estimated_parallelizable=False,
        suggested_specialist_count=1,
    )


def _llm():
    async def structured(**kwargs):
        model = kwargs.get("response_model")
        if model is TaskAnalysis:
            return _task_analysis()
        if model is RecruitmentPlan:
            return _recruitment_plan()
        raise AssertionError(f"unexpected response_model {model!r}")

    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(side_effect=structured)
    return llm


@pytest.fixture()
def scratch(tmp_path):
    """Isolated SQLite file (never the live dev DB)."""
    db_path = tmp_path / "fleet-root-execution.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add_all([
            Tenant(id=TENANT, name="Ops", subdomain="ops"),
            Tenant(id=OTHER_TENANT, name="Other", subdomain="other"),
            Workspace(id=WORKSPACE, name="Ops", tenant_id=TENANT),
            Workspace(id=OTHER_WORKSPACE, name="Other", tenant_id=OTHER_TENANT),
        ])
        db.add(AgentRegistry(
            id="atom_main", name="Atom", display_name="Atom",
            category="system", module_path="core.atom_meta_agent",
            class_name="AtomMetaAgent", tenant_id=TENANT,
            workspace_id=WORKSPACE, status=AgentStatus.AUTONOMOUS.value,
            enabled=True, capabilities=["operations"], specialty="operations",
            user_id=USER))
        db.add(AgentRegistry(
            id="ops-1", name="Ops Specialist", display_name="Ops Specialist",
            category="operations", module_path="core.generic_agent",
            class_name="GenericAgent", tenant_id=TENANT,
            workspace_id=WORKSPACE, status=AgentStatus.AUTONOMOUS.value,
            enabled=True, capabilities=["operations"], specialty="operations",
            user_id=USER))
        db.commit()
    try:
        yield db_path, engine, Session
    finally:
        engine.dispose()


def _owner():
    # A real instance (not a proxy) so the governed wrapper binds its class
    # methods normally; only heavyweight __init__ services are bypassed.
    owner = object.__new__(ama.AtomMetaAgent)
    owner.workspace_id = WORKSPACE
    owner.tenant_id = TENANT
    owner.llm = _llm()
    # The governed wrapper is exercised; only its allow/deny answer is stubbed.
    owner._check_governance = AsyncMock(return_value=(True, None))
    return owner


def _task_intent() -> RouteIntent:
    return RouteIntent(
        category=RouteIntentCategory.TASK,
        confidence=0.8,
        reasoning="fleet-eligible one-off task",
        requires_execution=True,
        suggested_handler="fleet_admiral",
        is_structured=False,
        is_long_horizon=True,
        requires_agent_recruitment=True,
    )


async def _governed_task(owner, request: str, execution_id=None):
    return await owner.route_with_governance(
        request,
        _task_intent(),
        USER,
        agent_id="atom_main",
        execution_id=execution_id,
    )


def _persisted_chain(Session, chain_id: str) -> DelegationChain:
    with Session() as db:
        return db.query(DelegationChain).filter(
            DelegationChain.id == chain_id).one()


@pytest.mark.asyncio
async def test_normal_governed_task_route_persists_exact_execution_id(
        scratch, monkeypatch):
    _db_path, _engine, Session = scratch
    monkeypatch.setattr(ama, "SessionLocal", Session)

    with Session() as db:
        db.add(AgentExecution(
            id=RUN_EXECUTION_ID,
            agent_id="atom_main",
            tenant_id=TENANT,
            workspace_id=WORKSPACE,
            status=ExecutionStatus.RUNNING.value,
            input_summary="draft an operations checklist",
        ))
        db.commit()

    result = await _governed_task(
        _owner(),
        "Draft an operations checklist for the office cabinet",
        execution_id=RUN_EXECUTION_ID,
    )
    assert result["route"] == "TASK", result

    with Session() as db:
        execution = db.query(AgentExecution).filter(
            AgentExecution.id == RUN_EXECUTION_ID).one()
        chain = db.query(DelegationChain).filter(
            DelegationChain.id == result["chain_id"]).one()
        links = db.query(ChainLink).filter(
            ChainLink.chain_id == chain.id).all()

    # Exact persisted id, including the dashed spelling. A routing/audit UUID
    # or a dash-normalized variant does not satisfy crash recovery's equality.
    assert chain.root_execution_id == execution.id == RUN_EXECUTION_ID
    assert chain.tenant_id == execution.tenant_id == TENANT
    assert chain.metadata_json["workspace_id"] == execution.workspace_id
    assert [link.child_agent_id for link in links] == ["ops-1"]


@pytest.mark.asyncio
async def test_legacy_caller_without_execution_id_still_works(
        scratch, monkeypatch):
    _db_path, _engine, Session = scratch
    monkeypatch.setattr(ama, "SessionLocal", Session)

    result = await _governed_task(
        _owner(),
        "Draft an operations checklist for the office cabinet",
    )
    assert result["route"] == "TASK", result

    chain = _persisted_chain(Session, result["chain_id"])
    assert chain.root_execution_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "other_tenant, other_workspace",
    [
        (OTHER_TENANT, WORKSPACE),
        (TENANT, OTHER_WORKSPACE),
    ],
    ids=["tenant", "workspace"],
)
async def test_foreign_scope_execution_is_not_linked(
        scratch, monkeypatch, other_tenant, other_workspace):
    _db_path, _engine, Session = scratch
    monkeypatch.setattr(ama, "SessionLocal", Session)

    foreign_id = f"foreign-{other_tenant}-{other_workspace}"
    with Session() as db:
        db.add(AgentExecution(
            id=foreign_id,
            agent_id="atom_main",
            tenant_id=other_tenant,
            workspace_id=other_workspace,
            status=ExecutionStatus.RUNNING.value,
            input_summary="someone else's run",
        ))
        db.commit()

    result = await _governed_task(
        _owner(),
        "Draft an operations checklist for the office cabinet",
        execution_id=foreign_id,
    )
    assert result["route"] == "TASK", result

    chain = _persisted_chain(Session, result["chain_id"])
    assert chain.root_execution_id is None


def test_persisted_link_survives_fresh_process_recovery(scratch, monkeypatch):
    """Crash recovery in a NEW process sees the exact producer-written link.

    The producer link is only useful if recovery ACTS on it: the chain and every
    link still waiting on the dead root must be failed, not left ``active`` /
    ``pending`` as a fleet no worker can advance.
    """
    db_path, _engine, Session = scratch
    monkeypatch.setattr(ama, "SessionLocal", Session)

    with Session() as db:
        db.add(AgentExecution(
            id=RUN_EXECUTION_ID,
            agent_id="atom_main",
            tenant_id=TENANT,
            workspace_id=WORKSPACE,
            status=ExecutionStatus.RUNNING.value,
            input_summary="draft an operations checklist",
        ))
        db.commit()

    result = asyncio.run(_governed_task(
        _owner(),
        "Draft an operations checklist for the office cabinet",
        execution_id=RUN_EXECUTION_ID,
    ))
    chain_id = result["chain_id"]

    # Pre-restart snapshot. The chain is live and its recruited links are
    # non-terminal, so a later ``failed`` is recovery's verdict rather than a
    # status the producer route already wrote. Recovery preserves terminal
    # links (their work really happened), so only the unfinished ones may move.
    with Session() as db:
        chain = db.query(DelegationChain).filter(
            DelegationChain.id == chain_id).one()
        links = db.query(ChainLink).filter(
            ChainLink.chain_id == chain_id).all()
        assert chain.status == "active"
        terminal_before = {
            link.id: link.status for link in links
            if link.status in ("completed", "failed", "cancelled", "canceled",
                               "skipped")
        }
        unfinished_link_ids = {
            link.id for link in links if link.id not in terminal_before
        }
        assert unfinished_link_ids, "fixture must leave a live link to recover"

    # A real dead owner on this host: let a child exit and use its pid.
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    with Session() as db:
        execution = db.query(AgentExecution).filter(
            AgentExecution.id == RUN_EXECUTION_ID).one()
        execution.metadata_json = {
            "owner": {
                "pid": dead.pid,
                "token": "dead-owner-token",
                "host": socket.gethostname(),
            }
        }
        db.commit()

    backend_dir = Path(__file__).resolve().parents[1]
    script = (
        "import json\n"
        "from core.execution_recovery import reconcile_orphaned_executions\n"
        "print(json.dumps(reconcile_orphaned_executions()))\n"
    )
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["ENVIRONMENT"] = "development"
    env["TESTING"] = "0"
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("PYTEST_VERSION", None)
    env.pop("ATOM_MOCK_DATABASE", None)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(backend_dir), env.get("PYTHONPATH", "")])

    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(backend_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stderr
    recovered = json.loads(proc.stdout.strip().splitlines()[-1])
    assert recovered["agent_recovered"] == 1, recovered

    with Session() as db:
        execution = db.query(AgentExecution).filter(
            AgentExecution.id == RUN_EXECUTION_ID).one()
        chain = db.query(DelegationChain).filter(
            DelegationChain.id == chain_id).one()
        links = {
            link.id: link for link in db.query(ChainLink).filter(
                ChainLink.chain_id == chain_id).all()
        }
        assert execution.status == ExecutionStatus.FAILED.value
        # Fresh-process recovery can only find the fleet if the producer wrote
        # the exact parent id; recompute/removal would break this equality.
        assert chain.root_execution_id == execution.id

        # The sweep followed that link: the chain and its unfinished links are
        # now failed, with a recovery marker naming the dead root. Asserting
        # only the id would pass while the fleet still reported itself live.
        assert recovered["fleet_chains_recovered"] == 1, recovered
        assert recovered["fleet_links_reconciled"] == len(
            unfinished_link_ids), recovered
        assert chain.status == "failed"
        assert chain.completed_at is not None
        assert chain.metadata_json["recovery"]["crashed"] is True
        assert (chain.metadata_json["recovery"]["root_execution_id"]
                == RUN_EXECUTION_ID)
        for link_id in unfinished_link_ids:
            link = links[link_id]
            assert link.status == "failed", (link_id, link.status)
            assert link.completed_at is not None
            assert "crashed" in (link.error_message or "").lower()
        # Completed/skipped work is preserved rather than rewritten.
        for link_id, status in terminal_before.items():
            assert links[link_id].status == status
