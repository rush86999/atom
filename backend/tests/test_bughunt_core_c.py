# -*- coding: utf-8 -*-
"""Bug-hunt tests (TDD RED->GREEN) for core modules (wave core_c).

Covers:
- core/autonomous_supervisor_service.py  (phantom attrs on AgentProposal)
- core/agent_marketplace_service.py       (PG-only .astext on SQLite; missing NOT NULL columns)
- core/chat_process_manager.py            (lists bound to Text columns -> ProgrammingError)
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base


@pytest.fixture()
def db():
    """In-memory SQLite with the full schema (AgentRegistry deletes cascade
    through many relationship backrefs, so a partial schema is not enough)."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


# ============================================================================
# BUG 1: autonomous_supervisor_service.approve_proposal writes review data to
# phantom columns (`execution_result`, `completed_at` do not exist on the
# AgentProposal model) -> the review + completion timestamp are silently lost.
# ============================================================================


class TestApproveProposalPersistsReview:
    async def test_approve_proposal_persists_review_and_executed_at(self, db):
        from core.models import AgentProposal

        proposal = AgentProposal(
            id="prop-1",
            tenant_id="t-1",
            user_id="u-1",
            agent_id="a-1",
            proposal_type="action",
            proposal_data={},
            status="pending_approval",
        )
        db.add(proposal)
        db.commit()

        from core.autonomous_supervisor_service import (
            AutonomousSupervisorService,
            ProposalReview,
        )

        review = ProposalReview(
            approved=True,
            confidence_score=0.93,
            risk_level="medium",
            reasoning="looks fine",
            suggested_modifications=["a"],
        )
        service = AutonomousSupervisorService(db)
        ok = await service.approve_proposal("prop-1", "sup-1", review)
        assert ok is True

        db.expire_all()
        stored = db.query(AgentProposal).filter(AgentProposal.id == "prop-1").first()
        assert stored.status == "executed"
        # The review must be persisted (supervision_metadata), not dropped.
        assert stored.supervision_metadata is not None
        assert stored.supervision_metadata["review"]["approved"] is True
        assert stored.supervision_metadata["supervisor_id"] == "sup-1"
        # The completion timestamp must be persisted (executed_at).
        assert stored.executed_at is not None


# ============================================================================
# BUG 2: agent_marketplace_service.uninstall_agent uses PG-only
# `.astext` on a JSON column -> AttributeError on SQLite (default DB).
# ============================================================================


class TestUninstallAgentSqlite:
    def _seed(self, db, agent_id="ag-1", tpl_id="tpl-1", tenant_id="ten-1"):
        from core.models import (
            AgentInstallation,
            AgentRegistry,
            AgentSkill,
            OperationErrorResolution,
        )

        db.add(
            AgentRegistry(
                id=agent_id,
                name="Marketplace Agent",
                category="General",
                role="agent",
                type="marketplace",
                module_path="core.generic_agent",
                class_name="GenericAgent",
                user_id="u-1",
                tenant_id=tenant_id,
                status="intern",
                configuration={},
            )
        )
        db.add(
            AgentInstallation(
                id="inst-1",
                tenant_id=tenant_id,
                template_id=tpl_id,
                instantiated_agent_id=agent_id,
                installed_version="1.0.0",
                is_active=True,
            )
        )
        db.add(
            AgentSkill(
                agent_id=agent_id,
                skill_id="sk-1",
                enabled=True,
            )
        )
        db.add(
            OperationErrorResolution(
                id="res-1",
                tenant_id=tenant_id,
                error_type="err",
                resolution_attempted="retry",
                success=True,
                resolution_metadata={"source_template_id": tpl_id},
            )
        )
        db.add(
            OperationErrorResolution(
                id="res-2",
                tenant_id=tenant_id,
                error_type="err2",
                resolution_attempted="retry",
                success=True,
                resolution_metadata={"source_template_id": "other-tpl"},
            )
        )
        db.commit()

    def test_uninstall_agent_cleanup_works_on_sqlite(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService
        from core.models import OperationErrorResolution

        self._seed(db)
        saas = MagicMock()
        saas.install_agent_sync = MagicMock()
        service = AgentMarketplaceService(db, saas_client=saas)

        with patch("core.marketplace_usage_tracker.get_db_session"):
            result = service.uninstall_agent("ten-1", "ag-1")

        assert result["success"] is True
        # Memory + skills + installation + agent rows must be gone.
        assert (
            db.query(OperationErrorResolution)
            .filter(OperationErrorResolution.id == "res-1")
            .first()
            is None
        )
        assert (
            db.query(OperationErrorResolution)
            .filter(OperationErrorResolution.id == "res-2")
            .first()
            is not None
        )


# ============================================================================
# BUG 3: chat_process_manager.create_process binds lists/dicts to Text
# columns -> ProgrammingError on SQLite (and PostgreSQL).
# ============================================================================


class TestChatProcessManagerPersistence:
    @pytest.fixture()
    def async_db(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from core.models import ChatProcess, User

        engine = create_async_engine("sqlite+aiosqlite://")
        import asyncio

        async def _init():
            async with engine.begin() as conn:
                await conn.run_sync(
                    Base.metadata.create_all,
                    tables=[ChatProcess.__table__, User.__table__],
                )

        asyncio.get_event_loop().run_until_complete(_init())
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        @asynccontextmanager
        async def _session():
            async with SessionLocal() as s:
                yield s

        with patch("core.chat_process_manager.get_async_db_session", side_effect=_session):
            yield SessionLocal
        asyncio.get_event_loop().run_until_complete(engine.dispose())

    async def test_create_process_roundtrip(self, async_db):
        from core.chat_process_manager import ChatProcessManager
        from core.models import ChatProcess, User

        # A user with a tenant — the created process must inherit it
        # (tenant_id is NOT NULL; omitting it crashed every create).
        async with async_db() as db:
            db.add(
                User(
                    id="u-1",
                    email="u1@example.com",
                    first_name="U",
                    last_name="1",
                    role="member",
                    status="ACTIVE",
                    tenant_id="ten-xyz",
                )
            )
            await db.commit()

        manager = ChatProcessManager()
        pid = await manager.create_process(
            user_id="u-1",
            name="Onboarding",
            steps=[{"step": 1}, {"step": 2}],
            initial_context={"customer": "acme"},
        )
        assert pid
        state = await manager.get_process(pid)
        assert state is not None
        assert state["name"] == "Onboarding"
        assert state["total_steps"] == 2
        assert state["context"]["customer"] == "acme"

        async with async_db() as db:
            stored = await db.get(ChatProcess, pid)
            assert stored is not None
            assert stored.tenant_id == "ten-xyz"


# ============================================================================
# BUG 6: byok_cost_optimizer.analyze_user_usage_pattern does not cache the
# default pattern for users with zero usage history -> simulate_cost_savings /
# get_cost_optimization_recommendations crash with KeyError for new users.
# ============================================================================


class TestCostOptimizerZeroUsageUser:
    def test_recommendations_for_zero_usage_user(self, tmp_path, monkeypatch):
        import pathlib

        import core.byok_cost_optimizer as mod

        monkeypatch.setattr(mod, "Path", lambda p: pathlib.Path(tmp_path) / "up.json")

        class FakeProvider:
            name = "OpenAI"
            is_active = True
            supported_tasks = ["code"]
            cost_per_token = 0.00006

        class FakeManager:
            providers = {"openai": FakeProvider()}
            usage_stats = {}

            def get_optimal_provider(self, task_type, budget_constraint=None):
                return "openai"

            def get_api_key(self, provider_id):
                return "sk-test"

        optimizer = mod.BYOKCostOptimizer(FakeManager())
        # A brand-new user with no usage history must still get a recommendation
        # (default pattern is cached, not lost).
        rec = optimizer.get_cost_optimization_recommendations("u-zero", "code")
        assert rec.task_type == "code"
        assert optimizer.usage_patterns["u-zero"].monthly_budget == 50.0

        sim = optimizer.simulate_cost_savings("u-zero")
        assert sim["current_monthly_cost"] == 50.0



class TestCostOptimizerProviderAccess:
    def test_recommendations_read_provider_attribute(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer, UsagePattern

        class FakeProvider:
            def __init__(self, name, tasks, cost, active=True):
                self.name = name
                self.is_active = active
                self.supported_tasks = tasks
                self.cost_per_token = cost

        class FakeUsage:
            def __init__(self, requests=0, cost=0.0):
                self.total_requests = requests
                self.cost_accumulated = cost

        class FakeManager:
            providers = {
                "openai": FakeProvider("OpenAI", ["code", "chat"], 0.0006),
                "deepseek": FakeProvider("DeepSeek", ["code", "math"], 0.00001),
            }
            usage_stats = {"openai": FakeUsage(100, 5.0)}

            def get_optimal_provider(self, task_type, budget_constraint=None):
                return "openai"

            def get_api_key(self, provider_id):
                return "sk-test"

        optimizer = BYOKCostOptimizer(FakeManager())
        # Cost-sensitive user: the cheap provider must win the suitability
        # ranking — and the .get() AttributeError must be gone.
        optimizer.usage_patterns["u-1"] = UsagePattern(
            user_id="u-1",
            task_distribution={"code": 100},
            peak_hours=[9],
            preferred_providers={"openai": 100.0},
            cost_sensitivity="high",
        )
        rec = optimizer.get_cost_optimization_recommendations("u-1", "code")
        assert rec.recommended_provider == "deepseek"
        assert rec.savings_percentage > 0



class TestInstallAgentRealDb:
    def test_install_agent_succeeds_on_real_db(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService
        from core.models import AgentRegistry

        saas = MagicMock()
        saas.get_agent_template_sync = MagicMock(
            return_value={
                "name": "X" * 200,  # exceeds VARCHAR(100) -> must truncate
                "description": "Y" * 600,  # exceeds VARCHAR(500) -> must truncate
                "category": "Finance",
                "configuration": {"system_prompt": "hi"},
                "anonymized_memory_bundle": {
                    "heuristics": [
                        {
                            "error_type": "timeout",
                            "error_code": "E1",
                            "resolution": "retry",
                        }
                    ]
                },
                "capabilities": ["sk-1"],
                "version": "2.0.0",
            }
        )
        saas.install_agent_sync = MagicMock()
        service = AgentMarketplaceService(db, saas_client=saas)

        with patch("core.marketplace_usage_tracker.get_db_session"):
            result = service.install_agent("tpl-1", "ten-1", "u-1")

        assert result["success"] is True, result.get("error")
        agent = (
            db.query(AgentRegistry)
            .filter(AgentRegistry.id == result["agent_id"])
            .first()
        )
        assert agent is not None
        assert agent.name == "X" * 100
        assert agent.module_path == "core.generic_agent"
        assert agent.class_name == "GenericAgent"
