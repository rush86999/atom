"""
Anti-laundering tests for AtomMetaAgent.teach_student (R86c).

atom_main may share KNOWLEDGE with anyone, but teaching transfers PROVEN
domain judgment: it teaches business-role students only after earning
super-mentor status on that domain's ledger. System/Meta students remain
directly teachable.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import AgentRegistry, AgentStatus, DomainExperienceLedger


def _make_student(db, category="Sales"):
    agent = AgentRegistry(
        id=f"stu-{uuid.uuid4().hex[:8]}",
        name="Sales Student", category=category, description="t",
        module_path="core.generic_agent", class_name="GenericAgent",
        status=AgentStatus.STUDENT.value, confidence_score=0.1,
        configuration={}, capabilities=None,
        workspace_id="default", tenant_id="default",
    )
    db.add(agent)
    db.commit()
    return agent


def _make_meta(db):
    meta = AgentRegistry(
        id="atom_main", name="Atom", category="Meta", description="meta",
        module_path="core.atom_meta_agent", class_name="AtomMetaAgent",
        status=AgentStatus.AUTONOMOUS.value, confidence_score=1.0,
        configuration={}, workspace_id="default", tenant_id="default",
    )
    db.add(meta)
    db.commit()
    return meta


def _seed_ledger(db, domain, wins):
    for _ in range(wins):
        db.add(DomainExperienceLedger(
            agent_id="atom_main", domain=domain,
            outcome="success", task_summary="verified domain work",
        ))
    db.commit()


def _meta_agent(db):
    """Bare AtomMetaAgent-shaped object — only teach_student's collaborators
    are exercised, so skip the heavy __init__ (LLM, world model, etc.)."""
    from core.atom_meta_agent import AtomMetaAgent
    with patch.object(AtomMetaAgent, "__init__", lambda self: None):
        agent = AtomMetaAgent()
    agent.workspace_id = "default"
    agent.tenant_id = "default"
    return agent


def _gov(allowed=True):
    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(return_value={"allowed": allowed})
    return gov


class TestTeachStudentLaunderingGuard:
    @pytest.mark.asyncio
    async def test_unearned_domain_teaching_rejected(self, db_session, monkeypatch):
        monkeypatch.delenv("ATOM_SUPERMENTOR_MIN_DOMAIN_WINS", raising=False)
        _make_meta(db_session)
        sales_student = _make_student(db_session)  # no ledger wins in sales

        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=_gov()):
            result = await _meta_agent(db_session).teach_student(
                sales_student.id, "always qualify leads first", db=db_session,
            )

        assert result["status"] == "error"
        assert result.get("laundering_guard") is True
        assert "earned mentorship" in result["reason"]
        db_session.refresh(sales_student)
        assert not sales_student.configuration.get("learning", {}).get("log")

    @pytest.mark.asyncio
    async def test_earned_domain_teaching_allowed(self, db_session, monkeypatch):
        monkeypatch.setenv("ATOM_SUPERMENTOR_MIN_DOMAIN_WINS", "3")
        _make_meta(db_session)
        _seed_ledger(db_session, "sales", wins=3)
        sales_student = _make_student(db_session)

        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=_gov()):
            result = await _meta_agent(db_session).teach_student(
                sales_student.id, "always qualify leads first", topic="leads",
                db=db_session,
            )

        assert result["status"] == "ok", result
        db_session.refresh(sales_student)
        entry = sales_student.configuration["learning"]["log"][0]
        assert entry["teacher_agent_id"] == "atom_main"

    @pytest.mark.asyncio
    async def test_wrong_domain_wins_do_not_qualify(self, db_session, monkeypatch):
        monkeypatch.delenv("ATOM_SUPERMENTOR_MIN_DOMAIN_WINS", raising=False)
        _make_meta(db_session)
        _seed_ledger(db_session, "finance", wins=10)  # rich finance record only
        sales_student = _make_student(db_session, category="Sales")

        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=_gov()):
            result = await _meta_agent(db_session).teach_student(
                sales_student.id, "always qualify leads first", db=db_session,
            )

        assert result["status"] == "error"
        assert result.get("laundering_guard") is True

    @pytest.mark.asyncio
    async def test_system_student_directly_teachable(self, db_session, monkeypatch):
        monkeypatch.delenv("ATOM_SUPERMENTOR_MIN_DOMAIN_WINS", raising=False)
        _make_meta(db_session)
        system_student = _make_student(db_session, category="system")

        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=_gov()):
            result = await _meta_agent(db_session).teach_student(
                system_student.id, "platform conventions", db=db_session,
            )

        assert result["status"] == "ok", result

    @pytest.mark.asyncio
    async def test_governance_denial_still_blocks_everything(self, db_session):
        _make_meta(db_session)
        system_student = _make_student(db_session, category="system")

        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=_gov(allowed=False)):
            result = await _meta_agent(db_session).teach_student(
                system_student.id, "anything", db=db_session,
            )

        assert result["status"] == "error"
        assert "Teaching not permitted" in result["reason"]
