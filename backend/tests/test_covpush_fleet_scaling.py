"""
Coverage-push + bug-hunt tests for fleet scaling services
(overage, scaling proposals, scaler, auto-approval, predictive).
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.fleet_orchestration.overage_service import (
    OverageService,
    get_overage_service,
)
from core.fleet_orchestration.scaling_proposal_service import (
    ScalingProposal,
    ScalingProposalService,
    ScalingProposalStatus,
    ScalingProposalType,
    get_scaling_proposal_service,
)
from core.fleet_orchestration.fleet_scaler_service import (
    FleetScalerService,
    ScalingOperation,
    ScalingOperationStatus,
    get_fleet_scaler_service,
)
from core.fleet_orchestration.auto_approval_service import (
    AutoApprovalService,
    get_auto_approval_service,
)
from core.fleet_orchestration.predictive_scaling_service import (
    PredictiveScalingService,
    get_predictive_scaling_service,
)
from core.models import ScalingAutoApproval
from core.fleet_orchestration.performance_metrics_service import (
    PerformanceMetrics,
)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db_session():
    """Per-test isolated SQLite engine (temp file)."""
    import tempfile
    from core.models_registration import Base
    _fd, _db_path = tempfile.mkstemp(suffix=".db")
    os.close(_fd)
    engine = create_engine(f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})
    _seen_idx = set()
    for _table in list(Base.metadata.tables.values()):
        for _idx in list(_table.indexes):
            if _idx.name in _seen_idx:
                _table.indexes.remove(_idx)
            else:
                _seen_idx.add(_idx.name)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.unlink(_db_path)
        except OSError:
            pass


def _metrics(success_rate=95.0, latency=5000, throughput=3.0, count=5):
    return PerformanceMetrics(
        chain_id="chain-1",
        success_rate=success_rate,
        avg_latency_ms=latency,
        throughput_per_minute=throughput,
        execution_count=count,
        window="5m",
    )


def _proposal(chain_id="chain-1", type_=ScalingProposalType.EXPANSION,
              current=5, proposed=8, reason="r", cost=0.72, hours=24.0,
              status=ScalingProposalStatus.PENDING):
    return ScalingProposal(
        chain_id=chain_id,
        proposal_type=type_,
        current_fleet_size=current,
        proposed_fleet_size=proposed,
        reason=reason,
        cost_estimate=cost,
        duration_hours=hours,
        status=status,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


class TestOverageService:
    @pytest.mark.asyncio
    async def test_approve_overage_exceeds_max(self, db_session):
        svc = OverageService(db_session)
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "10"}):
            with pytest.raises(ValueError):
                await svc.approve_overage(
                    "chain-1", "tenant-1", proposed_size=999, user_id="u1")

    @pytest.mark.asyncio
    async def test_approve_overage_with_tenant(self, db_session):
        from core.models import Tenant
        db_session.add(Tenant(id="tenant-1", name="T", subdomain="t1", plan_type="enterprise"))
        db_session.commit()
        svc = OverageService(db_session)
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "10"}):
            with patch.object(svc.notification_service, "send_notification", new=AsyncMock()):
                result = await svc.approve_overage(
                    "chain-1", "tenant-1", proposed_size=15, user_id="u1")
        assert result["success"] is True
        assert result["approved_size"] == 15
        assert result["base_limit"] == 10

    @pytest.mark.asyncio
    async def test_approve_overage_no_tenant_default_plan(self, db_session):
        svc = OverageService(db_session)
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "100"}):
            with patch.object(svc.notification_service, "send_notification", new=AsyncMock()):
                result = await svc.approve_overage(
                    "chain-1", "tenant-missing", proposed_size=120, user_id="u1")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_approve_overage_caps_duration(self, db_session):
        svc = OverageService(db_session)
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "100"}):
            with patch.object(svc.notification_service, "send_notification", new=AsyncMock()):
                result = await svc.approve_overage(
                    "chain-1", "tenant-x", proposed_size=110, user_id="u1",
                    duration_hours=1000)
        assert result["duration_hours"] <= 48

    @pytest.mark.asyncio
    async def test_approve_overage_cancels_existing(self, db_session):
        from core.models import FleetOverage
        original = FleetOverage(
            tenant_id="tenant-x", chain_id="chain-1", base_limit=10,
            temporary_limit=15, current_size=5, expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True)
        db_session.add(original)
        db_session.commit()
        svc = OverageService(db_session)
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "100"}):
            with patch.object(svc.notification_service, "send_notification", new=AsyncMock()):
                await svc.approve_overage(
                    "chain-1", "tenant-x", proposed_size=110, user_id="u1")
        db_session.expire_all()
        old = db_session.query(FleetOverage).filter(
            FleetOverage.id == original.id).first()
        assert old.is_active is False
        active = db_session.query(FleetOverage).filter(
            FleetOverage.is_active == True).all()
        assert len(active) == 1

    def test_get_effective_limit_active_overage(self, db_session):
        from core.models import FleetOverage
        db_session.add(FleetOverage(
            tenant_id="t", chain_id="chain-1", base_limit=10,
            temporary_limit=25, current_size=5,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1), is_active=True))
        db_session.commit()
        svc = OverageService(db_session)
        assert svc.get_effective_limit("chain-1") == 25

    def test_get_effective_limit_no_overage_with_chain(self, db_session):
        from core.models import DelegationChain
        db_session.add(DelegationChain(
            id="chain-1", tenant_id="t", root_agent_id="r", status="active"))
        db_session.commit()
        svc = OverageService(db_session)
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "50"}):
            assert svc.get_effective_limit("chain-1") == 50

    def test_get_effective_limit_no_chain(self, db_session):
        svc = OverageService(db_session)
        assert svc.get_effective_limit("missing-chain") == 2

    def test_get_active_overage(self, db_session):
        from core.models import FleetOverage
        db_session.add(FleetOverage(
            tenant_id="t", chain_id="chain-1", base_limit=10,
            temporary_limit=25, current_size=5,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1), is_active=True))
        db_session.commit()
        svc = OverageService(db_session)
        assert svc.get_active_overage("chain-1") is not None
        assert svc.get_active_overage("other") is None

    @pytest.mark.asyncio
    async def test_check_overage_expiry_none(self, db_session):
        svc = OverageService(db_session)
        assert await svc.check_overage_expiry("chain-1") is False

    @pytest.mark.asyncio
    async def test_check_overage_expiry_expires(self, db_session):
        from core.models import FleetOverage
        overage = FleetOverage(
            tenant_id="t", chain_id="chain-1", base_limit=10,
            temporary_limit=25, current_size=5,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1), is_active=True)
        db_session.add(overage)
        db_session.commit()
        svc = OverageService(db_session)
        with patch.object(svc.notification_service, "send_notification", new=AsyncMock()):
            assert await svc.check_overage_expiry("chain-1") is True
        db_session.expire_all()
        assert db_session.query(FleetOverage).first().is_active is False

    def test_get_expiring_overages(self, db_session):
        from core.models import FleetOverage
        db_session.add(FleetOverage(
            tenant_id="t", chain_id="chain-1", base_limit=10,
            temporary_limit=25, current_size=5,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30), is_active=True))
        db_session.commit()
        svc = OverageService(db_session)
        assert len(svc.get_expiring_overages(hours_threshold=2)) == 1

    @pytest.mark.asyncio
    async def test_send_overage_notification_error(self, db_session):
        svc = OverageService(db_session)
        svc.notification_service.send_notification = AsyncMock(
            side_effect=RuntimeError("notif down"))
        await svc._send_overage_notification(
            "t", "u1", "chain-1", 10, 15, datetime.now(timezone.utc))

    def test_get_overage_service_factory(self, db_session):
        svc = get_overage_service(db_session)
        assert isinstance(svc, OverageService)


class TestScalingProposalService:
    @pytest.mark.asyncio
    async def test_validate_fleet_size_limit_exceeds(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.overage_service, "get_effective_limit", return_value=10), \
             patch.object(svc, "_get_current_fleet_size", new=AsyncMock(return_value=8)):
            result = await svc.validate_fleet_size_limit("chain-1", proposed_size=20)
        assert result["allowed"] is False
        assert "exceeds" in result["reason"]
        assert result["usage_percent"] == 80.0

    @pytest.mark.asyncio
    async def test_validate_fleet_size_limit_within(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.overage_service, "get_effective_limit", return_value=10), \
             patch.object(svc, "_get_current_fleet_size", new=AsyncMock(return_value=5)):
            result = await svc.validate_fleet_size_limit("chain-1", proposed_size=6)
        assert result["allowed"] is True

    def test_fleet_size_warnings(self):
        svc = ScalingProposalService(Mock())
        assert svc._get_fleet_size_warnings(5, 0) == []
        critical = svc._get_fleet_size_warnings(9, 10)
        assert critical[0]["severity"] == "critical"
        warning = svc._get_fleet_size_warnings(8, 10)
        assert warning[0]["severity"] == "warning"
        assert svc._get_fleet_size_warnings(5, 10) == []

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_expansion_critical(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.metrics_service, "get_metrics",
                          new=AsyncMock(return_value=_metrics(success_rate=60.0))):
            proposal = await svc.analyze_scaling_need("chain-1")
        assert proposal is not None
        assert proposal.proposal_type == ScalingProposalType.EXPANSION
        assert proposal.metadata["urgency"] == "critical"

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_expansion_warning(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.metrics_service, "get_metrics",
                          new=AsyncMock(return_value=_metrics(success_rate=80.0))):
            proposal = await svc.analyze_scaling_need("chain-1")
        assert proposal.metadata["urgency"] == "warning"

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_latency_critical(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.metrics_service, "get_metrics",
                          new=AsyncMock(return_value=_metrics(success_rate=95.0, latency=50000))):
            proposal = await svc.analyze_scaling_need("chain-1")
        assert proposal.proposal_type == ScalingProposalType.EXPANSION

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_latency_warning(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.metrics_service, "get_metrics",
                          new=AsyncMock(return_value=_metrics(success_rate=95.0, latency=25000))):
            proposal = await svc.analyze_scaling_need("chain-1")
        assert proposal.metadata["urgency"] == "warning"

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_contraction(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.metrics_service, "get_metrics",
                          new=AsyncMock(return_value=_metrics(success_rate=98.0, throughput=1.0))):
            proposal = await svc.analyze_scaling_need("chain-1")
        assert proposal.proposal_type == ScalingProposalType.CONTRACTION

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_none(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.metrics_service, "get_metrics",
                          new=AsyncMock(return_value=_metrics())):
            assert await svc.analyze_scaling_need("chain-1") is None

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_exception(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.metrics_service, "get_metrics",
                          new=AsyncMock(side_effect=RuntimeError("metrics down"))):
            assert await svc.analyze_scaling_need("chain-1") is None

    @pytest.mark.asyncio
    async def test_check_hysteresis_no_redis(self, db_session):
        svc = ScalingProposalService(db_session)
        assert await svc._check_hysteresis("chain-1", "expansion") is True

    @pytest.mark.asyncio
    async def test_create_expansion_proposal(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc.overage_service, "get_effective_limit", return_value=100), \
             patch.object(svc, "_get_current_fleet_size", new=AsyncMock(return_value=5)), \
             patch.object(svc, "_set_hysteresis_timestamp", new=AsyncMock()):
            proposal = await svc.create_expansion_proposal(
                "chain-1", current_size=5, proposed_size=8, reason="growth")
        assert proposal.proposal_type == ScalingProposalType.EXPANSION
        assert proposal.cost_estimate == 0.72

    @pytest.mark.asyncio
    async def test_create_contraction_proposal(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc, "_set_hysteresis_timestamp", new=AsyncMock()):
            proposal = await svc.create_contraction_proposal(
                "chain-1", current_size=10, proposed_size=6, reason="shrink")
        assert proposal.proposal_type == ScalingProposalType.CONTRACTION
        assert proposal.cost_estimate < 0

    @pytest.mark.asyncio
    async def test_persist_and_get_proposal(self, db_session):
        svc = ScalingProposalService(db_session)
        proposal = _proposal()
        await svc._persist_proposal(proposal)
        from core.models import ScalingProposal as ScalingProposalRecord
        row = db_session.query(ScalingProposalRecord).filter(
            ScalingProposalRecord.id == proposal.id).first()
        assert row is not None
        assert row.status == "pending"
        fetched = await svc.get_proposal(proposal.id)
        assert fetched is not None
        assert fetched.current_fleet_size == 5
        assert fetched.proposed_fleet_size == 8
        assert fetched.proposal_type == ScalingProposalType.EXPANSION

    @pytest.mark.asyncio
    async def test_get_proposal_missing(self, db_session):
        svc = ScalingProposalService(db_session)
        assert await svc.get_proposal("nope") is None

    @pytest.mark.asyncio
    async def test_get_pending_proposals(self, db_session):
        svc = ScalingProposalService(db_session)
        await svc._persist_proposal(_proposal())
        await svc._persist_proposal(_proposal(status=ScalingProposalStatus.APPROVED))
        pending = await svc.get_pending_proposals()
        assert len(pending) == 1
        assert pending[0].status == ScalingProposalStatus.PENDING

    @pytest.mark.asyncio
    async def test_approve_proposal(self, db_session):
        svc = ScalingProposalService(db_session)
        proposal = _proposal()
        await svc._persist_proposal(proposal)
        approved = await svc.approve_proposal(proposal.id, approved_by="user-1")
        assert approved.status == ScalingProposalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_approve_proposal_missing(self, db_session):
        svc = ScalingProposalService(db_session)
        with pytest.raises(ValueError):
            await svc.approve_proposal("nope", approved_by="u")

    @pytest.mark.asyncio
    async def test_approve_proposal_not_pending(self, db_session):
        svc = ScalingProposalService(db_session)
        proposal = _proposal()
        await svc._persist_proposal(proposal)
        await svc.approve_proposal(proposal.id, approved_by="u")
        with pytest.raises(ValueError):
            await svc.approve_proposal(proposal.id, approved_by="u")

    @pytest.mark.asyncio
    async def test_approve_proposal_expired(self, db_session):
        svc = ScalingProposalService(db_session)
        proposal = _proposal()
        proposal.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await svc._persist_proposal(proposal)
        with pytest.raises(ValueError):
            await svc.approve_proposal(proposal.id, approved_by="u")
        from core.models import ScalingProposal as ScalingProposalRecord
        row = db_session.query(ScalingProposalRecord).filter(
            ScalingProposalRecord.id == proposal.id).first()
        assert row.status == "expired"

    @pytest.mark.asyncio
    async def test_reject_proposal(self, db_session):
        svc = ScalingProposalService(db_session)
        proposal = _proposal()
        await svc._persist_proposal(proposal)
        with patch.object(svc, "_set_rejection_suppression", new=AsyncMock()) as suppress:
            rejected = await svc.reject_proposal(proposal.id, rejected_by="u", reason="nope")
            suppress.assert_awaited_once()
        assert rejected.status == ScalingProposalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_reject_proposal_missing(self, db_session):
        svc = ScalingProposalService(db_session)
        with pytest.raises(ValueError):
            await svc.reject_proposal("nope", rejected_by="u", reason="x")

    @pytest.mark.asyncio
    async def test_reject_proposal_not_pending(self, db_session):
        svc = ScalingProposalService(db_session)
        proposal = _proposal()
        await svc._persist_proposal(proposal)
        await svc.approve_proposal(proposal.id, approved_by="u")
        with pytest.raises(ValueError):
            await svc.reject_proposal(proposal.id, rejected_by="u", reason="x")

    @pytest.mark.asyncio
    async def test_estimate_scaling_cost_and_predict(self, db_session):
        svc = ScalingProposalService(db_session)
        cost = await svc.estimate_scaling_cost(5, 8, 24.0)
        assert cost == 0.72
        prediction = await svc.predict_scaling_cost(5, 8, duration_hours=24.0)
        assert prediction["total"] == 0.72
        assert prediction["hourly_cost"] == 0.03
        assert prediction["breakdown"]["agent_cost"] == 0.58

    @pytest.mark.asyncio
    async def test_validate_budget_for_proposal(self, db_session):
        svc = ScalingProposalService(db_session)
        with patch.object(svc, "_get_current_fleet_size", new=AsyncMock(return_value=5)):
            result = await svc.validate_budget_for_proposal("chain-1", 10, 24.0)
        assert result["allowed"] is True

    def test_get_scaling_proposal_service_singleton(self, db_session):
        first = get_scaling_proposal_service(db_session)
        second = get_scaling_proposal_service(db_session)
        assert first is second
        from core.fleet_orchestration.scaling_proposal_service import _service_instance
        _service_instance = None


class TestScalingOperationModel:
    def test_to_dict(self):
        op = ScalingOperation(
            id="op-1", chain_id="chain-1", proposal_id="p-1",
            operation_type="expand", from_size=2, to_size=4,
            status=ScalingOperationStatus.COMPLETED,
            started_at=datetime.now(timezone.utc))
        d = op.to_dict()
        assert d["id"] == "op-1"
        assert d["status"] == "completed"
        assert d["from_size"] == 2
        assert d["completed_at"] is None


class TestFleetScalerService:
    @pytest.mark.asyncio
    async def test_monitor_and_scale_creates_proposal(self, db_session):
        svc = FleetScalerService(db_session)
        svc.metrics_service.get_metrics = AsyncMock(return_value=_metrics(success_rate=60.0))
        proposal = _proposal()
        svc.proposal_service.analyze_scaling_need = AsyncMock(return_value=proposal)
        svc.proposal_service._persist_proposal = AsyncMock()
        result = await svc.monitor_and_scale("chain-1")
        assert result is proposal
        svc.proposal_service._persist_proposal.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_monitor_and_scale_no_proposal(self, db_session):
        svc = FleetScalerService(db_session)
        svc.metrics_service.get_metrics = AsyncMock(return_value=_metrics())
        svc.proposal_service.analyze_scaling_need = AsyncMock(return_value=None)
        assert await svc.monitor_and_scale("chain-1") is None

    @pytest.mark.asyncio
    async def test_execute_scaling_not_found(self, db_session):
        svc = FleetScalerService(db_session)
        svc.proposal_service.get_proposal = AsyncMock(return_value=None)
        with pytest.raises(ValueError):
            await svc.execute_scaling("nope")

    @pytest.mark.asyncio
    async def test_execute_scaling_not_approved(self, db_session):
        svc = FleetScalerService(db_session)
        proposal = _proposal(status=ScalingProposalStatus.PENDING)
        svc.proposal_service.get_proposal = AsyncMock(return_value=proposal)
        with pytest.raises(ValueError):
            await svc.execute_scaling("p-1")

    @pytest.mark.asyncio
    async def test_execute_scaling_expired(self, db_session):
        svc = FleetScalerService(db_session)
        proposal = _proposal(status=ScalingProposalStatus.APPROVED)
        proposal.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        svc.proposal_service.get_proposal = AsyncMock(return_value=proposal)
        with pytest.raises(ValueError):
            await svc.execute_scaling("p-1")

    @pytest.mark.asyncio
    async def test_execute_scaling_expansion(self, db_session):
        svc = FleetScalerService(db_session)
        proposal = _proposal(status=ScalingProposalStatus.APPROVED,
                             current=2, proposed=4)
        svc.proposal_service.get_proposal = AsyncMock(return_value=proposal)
        svc.proposal_service._update_proposal_status = AsyncMock()
        with patch.object(svc, "_execute_expansion",
                          new=AsyncMock(return_value={"recruited_agents": ["x"]})), \
             patch.object(svc, "_persist_operation", new=AsyncMock()):
            operation = await svc.execute_scaling("p-1")
        assert operation.status == ScalingOperationStatus.COMPLETED
        assert operation.to_size == 4

    @pytest.mark.asyncio
    async def test_execute_scaling_contraction(self, db_session):
        svc = FleetScalerService(db_session)
        proposal = _proposal(status=ScalingProposalStatus.APPROVED,
                             type_=ScalingProposalType.CONTRACTION,
                             current=6, proposed=3)
        svc.proposal_service.get_proposal = AsyncMock(return_value=proposal)
        svc.proposal_service._update_proposal_status = AsyncMock()
        with patch.object(svc, "_execute_contraction",
                          new=AsyncMock(return_value={"removed_agents": ["x"]})), \
             patch.object(svc, "_persist_operation", new=AsyncMock()):
            operation = await svc.execute_scaling("p-1")
        assert operation.status == ScalingOperationStatus.COMPLETED
        assert operation.operation_type == "contract"

    @pytest.mark.asyncio
    async def test_execute_scaling_exception(self, db_session):
        svc = FleetScalerService(db_session)
        proposal = _proposal(status=ScalingProposalStatus.APPROVED)
        svc.proposal_service.get_proposal = AsyncMock(return_value=proposal)
        with patch.object(svc, "_execute_expansion",
                          new=AsyncMock(side_effect=RuntimeError("recruit failed"))), \
             patch.object(svc, "_persist_operation", new=AsyncMock()):
            operation = await svc.execute_scaling("p-1")
        assert operation.status == ScalingOperationStatus.FAILED
        assert "recruit failed" in operation.error_message

    @pytest.mark.asyncio
    async def test_execute_expansion_recruits(self, db_session):
        from core.models import ChainLink
        svc = FleetScalerService(db_session)
        proposal = _proposal(current=1, proposed=3)
        op = ScalingOperation(
            id="op-1", chain_id="chain-1", proposal_id="p-1",
            operation_type="expand", from_size=1, to_size=3,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc))
        with patch("core.fleet_orchestration.get_distributed_blackboard",
                   return_value=Mock(notify_state_update=AsyncMock())):
            result = await svc._execute_expansion(proposal, op)
        assert len(result["recruited_agents"]) == 2
        assert len(op.agents_added) == 2
        assert db_session.query(ChainLink).count() == 2

    @pytest.mark.asyncio
    async def test_execute_expansion_no_blackboard(self, db_session):
        svc = FleetScalerService(db_session)
        proposal = _proposal(current=1, proposed=2)
        op = ScalingOperation(
            id="op-1", chain_id="chain-1", proposal_id="p-1",
            operation_type="expand", from_size=1, to_size=2,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc))
        with patch("core.fleet_orchestration.get_distributed_blackboard",
                   return_value=None):
            result = await svc._execute_expansion(proposal, op)
        assert len(result["recruited_agents"]) == 1

    @pytest.mark.asyncio
    async def test_execute_contraction_removes(self, db_session):
        from core.models import ChainLink
        for i in range(4):
            db_session.add(ChainLink(
                chain_id="chain-1", parent_agent_id="p",
                child_agent_id=f"agent-{i}", task_description="t",
                status="active", link_order=i))
        db_session.commit()
        svc = FleetScalerService(db_session)
        proposal = _proposal(type_=ScalingProposalType.CONTRACTION,
                             current=4, proposed=2)
        op = ScalingOperation(
            id="op-1", chain_id="chain-1", proposal_id="p-1",
            operation_type="contract", from_size=4, to_size=2,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc))
        with patch("core.fleet_orchestration.get_distributed_blackboard",
                   return_value=Mock(notify_state_update=AsyncMock())):
            result = await svc._execute_contraction(proposal, op)
        assert len(result["removed_agents"]) == 2
        assert len(op.agents_removed) == 2
        db_session.expire_all()
        active = db_session.query(ChainLink).filter(
            ChainLink.status == "active").count()
        assert active == 2

    @pytest.mark.asyncio
    async def test_check_scaling_constraints_within_limit(self, db_session):
        svc = FleetScalerService(db_session)
        with patch.object(svc.overage_service, "get_effective_limit", return_value=10), \
             patch.object(svc, "_get_current_fleet_size", new=AsyncMock(return_value=4)), \
             patch.object(svc.overage_service, "check_overage_expiry",
                          new=AsyncMock(return_value=False)):
            result = await svc.check_scaling_constraints("chain-1", proposed_size=8)
        assert result["allowed"] is True
        assert result["constraints"]["fleet_size_limit"]["within_limit"] is True

    @pytest.mark.asyncio
    async def test_check_scaling_constraints_exceeds(self, db_session):
        svc = FleetScalerService(db_session)
        with patch.object(svc.overage_service, "get_effective_limit", return_value=5), \
             patch.object(svc, "_get_current_fleet_size", new=AsyncMock(return_value=4)), \
             patch.object(svc.overage_service, "check_overage_expiry",
                          new=AsyncMock(return_value=False)):
            result = await svc.check_scaling_constraints("chain-1", proposed_size=8)
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_check_scaling_constraints_overage_expiry(self, db_session):
        svc = FleetScalerService(db_session)
        with patch.object(svc.overage_service, "get_effective_limit", return_value=10), \
             patch.object(svc, "_get_current_fleet_size", new=AsyncMock(return_value=4)), \
             patch.object(svc.overage_service, "check_overage_expiry",
                          new=AsyncMock(return_value=True)):
            result = await svc.check_scaling_constraints("chain-1", proposed_size=8)
        assert "overage_expiry" in result["constraints"]

    @pytest.mark.asyncio
    async def test_get_scaling_status(self, db_session):
        from core.models import ChainLink, ScalingProposal as ScalingProposalRecord
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a1",
            task_description="t", status="active", link_order=0))
        db_session.add(ScalingProposalRecord(
            id="p-1", tenant_id="default", chain_id="chain-1",
            proposal_type="expansion", current_agents=1, proposed_agents=3,
            reason="r", status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db_session.commit()
        svc = FleetScalerService(db_session)
        with patch.object(svc, "_get_recent_operations", new=AsyncMock(return_value=[])):
            status = await svc.get_scaling_status("chain-1")
        assert status["current_fleet_size"] == 1
        assert len(status["pending_proposals"]) == 1
        assert status["pending_proposals"][0]["proposal_type"] == "expansion"

    @pytest.mark.asyncio
    async def test_get_scaling_status_no_proposals(self, db_session):
        svc = FleetScalerService(db_session)
        with patch.object(svc, "_get_recent_operations", new=AsyncMock(return_value=[])):
            status = await svc.get_scaling_status("chain-1")
        assert status["current_fleet_size"] == 0
        assert status["pending_proposals"] == []

    @pytest.mark.asyncio
    async def test_continuous_monitoring_loop(self, db_session):
        from core.models import DelegationChain
        db_session.add(DelegationChain(
            id="chain-1", tenant_id="default", root_agent_id="r", status="active"))
        db_session.commit()
        svc = FleetScalerService(db_session)
        svc.running = True
        with patch.object(svc, "monitor_and_scale", new=AsyncMock()) as mock_scale, \
             patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)):
            with pytest.raises(asyncio.CancelledError):
                await svc.continuous_monitoring_loop(interval_seconds=1)
        mock_scale.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_current_fleet_size(self, db_session):
        from core.models import ChainLink
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a1",
            task_description="t", status="active", link_order=0))
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a2",
            task_description="t", status="in_progress", link_order=1))
        db_session.commit()
        svc = FleetScalerService(db_session)
        assert await svc._get_current_fleet_size("chain-1") == 2
        assert await svc._get_current_fleet_size("other") == 0

    @pytest.mark.asyncio
    async def test_persist_operation_no_model(self, db_session):
        svc = FleetScalerService(db_session)
        op = ScalingOperation(
            id="op-1", chain_id="chain-1", proposal_id="p-1",
            operation_type="expand", from_size=1, to_size=2,
            status=ScalingOperationStatus.COMPLETED,
            started_at=datetime.now(timezone.utc))
        await svc._persist_operation(op)

    @pytest.mark.asyncio
    async def test_get_recent_operations_no_model(self, db_session):
        svc = FleetScalerService(db_session)
        assert await svc._get_recent_operations("chain-1") == []

    @pytest.mark.asyncio
    async def test_get_active_chains(self, db_session):
        from core.models import FleetOverage, ScalingProposal as ScalingProposalRecord
        db_session.add(FleetOverage(
            tenant_id="t", chain_id="chain-1", base_limit=5,
            temporary_limit=8, current_size=3,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1), is_active=True))
        db_session.add(ScalingProposalRecord(
            id="p-1", tenant_id="default", chain_id="chain-2",
            proposal_type="expansion", current_agents=1, proposed_agents=2,
            reason="r", status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db_session.commit()
        svc = FleetScalerService(db_session)
        chains = await svc._get_active_chains()
        assert "chain-1" in chains
        assert "chain-2" in chains

    @pytest.mark.asyncio
    async def test_handle_overage_expiry_chain_missing(self, db_session):
        svc = FleetScalerService(db_session)
        await svc._handle_overage_expiry("missing")

    @pytest.mark.asyncio
    async def test_handle_overage_expiry_contracts(self, db_session):
        from core.models import DelegationChain, ChainLink
        db_session.add(DelegationChain(
            id="chain-1", tenant_id="default", root_agent_id="r", status="active"))
        for i in range(8):
            db_session.add(ChainLink(
                chain_id="chain-1", parent_agent_id="r",
                child_agent_id=f"agent-{i}", task_description="t",
                status="active", link_order=i))
        db_session.commit()
        svc = FleetScalerService(db_session)
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "3"}):
            with patch.object(svc.proposal_service, "create_contraction_proposal",
                              new=AsyncMock(return_value=_proposal(
                                  type_=ScalingProposalType.CONTRACTION,
                                  current=8, proposed=3))) as create_prop, \
                 patch.object(svc.proposal_service, "approve_proposal",
                              new=AsyncMock(return_value=_proposal())):
                await svc._handle_overage_expiry("chain-1")
            create_prop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self):
        svc = FleetScalerService(Mock())
        await svc.start_monitoring()
        assert svc.running is True
        assert svc._monitor_task is not None
        await svc.start_monitoring()
        await svc.stop_monitoring()
        assert svc.running is False

    @pytest.mark.asyncio
    async def test_stop_monitoring_when_not_running(self):
        svc = FleetScalerService(Mock())
        await svc.stop_monitoring()

    @pytest.mark.asyncio
    async def test_execute_scaling_proposal(self, db_session):
        svc = FleetScalerService(db_session)
        proposal = _proposal()
        svc.proposal_service.get_proposal = AsyncMock(return_value=proposal)
        with patch.object(svc, "check_scaling_constraints",
                          new=AsyncMock(return_value={"allowed": True})):
            result = await svc.execute_scaling_proposal("p-1")
        assert result["success"] is True
        assert result["previous_size"] == 5

    @pytest.mark.asyncio
    async def test_execute_scaling_proposal_missing(self, db_session):
        svc = FleetScalerService(db_session)
        svc.proposal_service.get_proposal = AsyncMock(return_value=None)
        with pytest.raises(ValueError):
            await svc.execute_scaling_proposal("nope")

    @pytest.mark.asyncio
    async def test_execute_scaling_proposal_constraints_blocked(self, db_session):
        svc = FleetScalerService(db_session)
        proposal = _proposal()
        svc.proposal_service.get_proposal = AsyncMock(return_value=proposal)
        with patch.object(svc, "check_scaling_constraints",
                          new=AsyncMock(return_value={"allowed": False})):
            with pytest.raises(ValueError):
                await svc.execute_scaling_proposal("p-1")

    def test_get_fleet_scaler_factory(self, db_session):
        svc = get_fleet_scaler_service(db_session)
        assert isinstance(svc, FleetScalerService)


class TestAutoApprovalService:
    def test_create_rule(self, db_session):
        svc = AutoApprovalService(db_session)
        rule = svc.create_auto_approval_rule(
            rule_name="safe-expansion", created_by="admin",
            description="Small expansions", max_agents=10,
            max_cost_increase_percent=50.0, risk_threshold=0.3)
        assert rule.is_active is True
        assert rule.max_agents == 10
        fetched = db_session.query(ScalingAutoApproval).filter(
            ScalingAutoApproval.id == rule.id).first()
        assert fetched is not None

    def test_get_active_rules_orders_and_filters(self, db_session):
        svc = AutoApprovalService(db_session)
        svc.create_auto_approval_rule(rule_name="r1", created_by="a")
        svc.create_auto_approval_rule(rule_name="r2", created_by="a", is_active=False)
        rules = svc.get_active_rules(chain_id="chain-1")
        assert len(rules) == 1

    def test_evaluate_proposal_no_rules(self, db_session):
        svc = AutoApprovalService(db_session)
        approved, rule, reason = svc.evaluate_proposal(_proposal())
        assert approved is False
        assert rule is None
        assert "No auto-approval rules" in reason

    def test_evaluate_proposal_matches(self, db_session):
        svc = AutoApprovalService(db_session)
        svc.create_auto_approval_rule(
            rule_name="liberal", created_by="a",
            max_agents=20, max_cost_increase_percent=100.0, risk_threshold=1.0)
        proposal = _proposal(current=5, proposed=8, cost=1.0, hours=1.0)
        proposal.metadata["risk_score"] = 0.1
        approved, rule, reason = svc.evaluate_proposal(proposal)
        assert approved is True
        assert rule is not None
        assert "All conditions met" in reason

    def test_evaluate_proposal_size_exceeds(self, db_session):
        svc = AutoApprovalService(db_session)
        svc.create_auto_approval_rule(
            rule_name="strict", created_by="a",
            max_agents=5, max_cost_increase_percent=100.0, risk_threshold=1.0)
        approved, rule, reason = svc.evaluate_proposal(
            _proposal(current=5, proposed=8))
        assert approved is False
        assert "exceeds max" in reason

    def test_evaluate_proposal_cost_exceeds(self, db_session):
        svc = AutoApprovalService(db_session)
        svc.create_auto_approval_rule(
            rule_name="cost-cap", created_by="a",
            max_agents=100, max_cost_increase_percent=10.0, risk_threshold=1.0)
        approved, rule, reason = svc.evaluate_proposal(
            _proposal(current=5, proposed=8))
        assert approved is False
        assert "Cost increase" in reason

    def test_evaluate_proposal_risk_exceeds(self, db_session):
        svc = AutoApprovalService(db_session)
        svc.create_auto_approval_rule(
            rule_name="low-risk", created_by="a",
            max_agents=100, max_cost_increase_percent=100.0, risk_threshold=0.1)
        proposal = _proposal(current=5, proposed=8)
        proposal.metadata["risk_score"] = 0.9
        approved, rule, reason = svc.evaluate_proposal(proposal)
        assert approved is False
        assert "Risk" in reason

    @pytest.mark.asyncio
    async def test_auto_approve_proposal_not_found(self, db_session):
        svc = AutoApprovalService(db_session)
        result = await svc.auto_approve_proposal("nope")
        assert result["approved"] is False
        assert "not found" in result["reason"]

    @pytest.mark.asyncio
    async def test_auto_approve_proposal_not_pending(self, db_session):
        from core.models import ScalingProposal as ScalingProposalRecord
        db_session.add(ScalingProposalRecord(
            id="p-1", tenant_id="default", chain_id="chain-1",
            proposal_type="expansion", current_agents=5, proposed_agents=8,
            reason="r", status="approved",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db_session.commit()
        svc = AutoApprovalService(db_session)
        result = await svc.auto_approve_proposal("p-1")
        assert result["approved"] is False
        assert result["proposal"] is not None

    @pytest.mark.asyncio
    async def test_auto_approve_proposal_success(self, db_session):
        from core.models import ScalingProposal as ScalingProposalRecord
        svc = AutoApprovalService(db_session)
        rule = svc.create_auto_approval_rule(
            rule_name="liberal", created_by="a",
            max_agents=20, max_cost_increase_percent=100.0, risk_threshold=1.0)
        db_session.add(ScalingProposalRecord(
            id="p-1", tenant_id="default", chain_id="chain-1",
            proposal_type="expansion", current_agents=5, proposed_agents=8,
            reason="r", status="pending", risk_score=0.1,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db_session.commit()
        result = await svc.auto_approve_proposal("p-1")
        assert result["approved"] is True
        assert result["rule_name"] == "liberal"
        db_session.expire_all()
        row = db_session.query(ScalingProposalRecord).filter(
            ScalingProposalRecord.id == "p-1").first()
        assert row.status == "approved"
        assert row.approved_by == f"auto-approval-rule:{rule.id}"

    def test_update_rule(self, db_session):
        svc = AutoApprovalService(db_session)
        rule = svc.create_auto_approval_rule(rule_name="r", created_by="a")
        updated = svc.update_rule(rule.id, {"max_agents": 50, "is_active": False})
        assert updated.max_agents == 50
        assert updated.is_active is False
        assert svc.update_rule("nope", {"max_agents": 1}) is None

    def test_delete_rule(self, db_session):
        svc = AutoApprovalService(db_session)
        rule = svc.create_auto_approval_rule(rule_name="r", created_by="a")
        assert svc.delete_rule(rule.id) is True
        assert svc.delete_rule(rule.id) is False

    def test_get_rule_statistics(self, db_session):
        svc = AutoApprovalService(db_session)
        svc.create_auto_approval_rule(rule_name="r1", created_by="a")
        svc.create_auto_approval_rule(rule_name="r2", created_by="a", is_active=False)
        stats = svc.get_rule_statistics()
        assert stats["total_rules"] == 2
        assert stats["active_rules"] == 1
        assert stats["inactive_rules"] == 1
        assert stats["rules"][0]["max_agents"] == 10

    def test_get_auto_approval_factory(self, db_session):
        svc = get_auto_approval_service(db_session)
        assert isinstance(svc, AutoApprovalService)


class TestPredictiveScalingService:
    @pytest.mark.asyncio
    async def test_analyze_trend_insufficient_data(self, db_session):
        svc = PredictiveScalingService(db_session)
        result = svc.analyze_trend("chain-1", "success_rate", min_data_points=10)
        assert result["direction"] == "unknown"
        assert "Insufficient data" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_trend_with_data(self, db_session):
        from core.models import FleetPerformanceMetric
        base = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        for i in range(12):
            db_session.add(FleetPerformanceMetric(
                tenant_id="default", chain_id="chain-1",
                metric_type="success_rate", metric_value=50.0 + i * 2,
                window_start=base - timedelta(hours=11 - i),
                window_end=base - timedelta(hours=10 - i)))
        db_session.commit()
        svc = PredictiveScalingService(db_session)
        result = svc.analyze_trend("chain-1", "success_rate")
        assert result["direction"] == "increasing"
        assert result["data_points"] == 12
        assert result["current_value"] is not None

    @pytest.mark.asyncio
    async def test_predict_threshold_breach_insufficient(self, db_session):
        svc = PredictiveScalingService(db_session)
        result = svc.predict_threshold_breach("chain-1", "success_rate", 85.0)
        assert result["will_breach"] is False
        assert result["confidence"] == "unknown"

    @pytest.mark.asyncio
    async def test_predict_threshold_breach_already_below(self, db_session):
        from core.models import FleetPerformanceMetric
        base = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        for i in range(12):
            db_session.add(FleetPerformanceMetric(
                tenant_id="default", chain_id="chain-1",
                metric_type="success_rate", metric_value=50.0,
                window_start=base - timedelta(hours=11 - i),
                window_end=base - timedelta(hours=10 - i)))
        db_session.commit()
        svc = PredictiveScalingService(db_session)
        result = svc.predict_threshold_breach("chain-1", "success_rate", 85.0)
        assert result["will_breach"] is True
        assert result["hours_until_breach"] == 0

    @pytest.mark.asyncio
    async def test_predict_threshold_breach_stable_no_breach(self, db_session):
        from core.models import FleetPerformanceMetric
        base = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        for i in range(12):
            db_session.add(FleetPerformanceMetric(
                tenant_id="default", chain_id="chain-1",
                metric_type="success_rate", metric_value=95.0,
                window_start=base - timedelta(hours=11 - i),
                window_end=base - timedelta(hours=10 - i)))
        db_session.commit()
        svc = PredictiveScalingService(db_session)
        result = svc.predict_threshold_breach("chain-1", "success_rate", 85.0)
        assert result["will_breach"] is False

    @pytest.mark.asyncio
    async def test_predict_threshold_breach_above(self, db_session):
        from core.models import FleetPerformanceMetric
        base = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        for i in range(12):
            db_session.add(FleetPerformanceMetric(
                tenant_id="default", chain_id="chain-1",
                metric_type="avg_latency", metric_value=100.0 + i * 100,
                window_start=base - timedelta(hours=11 - i),
                window_end=base - timedelta(hours=10 - i)))
        db_session.commit()
        svc = PredictiveScalingService(db_session)
        result = svc.predict_threshold_breach(
            "chain-1", "avg_latency", threshold=500, breach_direction="above")
        assert result["will_breach"] is True
        assert result["confidence"] in ("high", "medium", "low")

    @pytest.mark.asyncio
    async def test_generate_proactive_proposal_chain_missing(self, db_session):
        svc = PredictiveScalingService(db_session)
        result = await svc.generate_proactive_proposal("missing")
        assert result["proposal_needed"] is False
        assert "not found" in result["reason"]

    @pytest.mark.asyncio
    async def test_generate_proactive_proposal_no_breach(self, db_session):
        from core.models import DelegationChain
        db_session.add(DelegationChain(
            id="chain-1", tenant_id="default", root_agent_id="r", status="active"))
        db_session.commit()
        svc = PredictiveScalingService(db_session)
        with patch.object(svc, "analyze_trend",
                          return_value={"direction": "stable", "slope": 0.0,
                                        "r_squared": 0.0, "current_value": 95.0}):
            with patch.object(svc, "predict_threshold_breach",
                              new=Mock(return_value={"will_breach": False})):
                result = await svc.generate_proactive_proposal("chain-1")
        assert result["proposal_needed"] is False

    @pytest.mark.asyncio
    async def test_generate_proactive_proposal_with_breach(self, db_session):
        from core.models import DelegationChain
        db_session.add(DelegationChain(
            id="chain-1", tenant_id="default", root_agent_id="r", status="active"))
        db_session.commit()
        svc = PredictiveScalingService(db_session)
        with patch.object(svc, "analyze_trend",
                          return_value={"direction": "decreasing", "slope": -3.0,
                                        "r_squared": 0.8, "current_value": 90.0}):
            with patch.object(svc, "predict_threshold_breach",
                              new=Mock(side_effect=[
                                  {"will_breach": True, "hours_until_breach": 6},
                                  {"will_breach": False}])):
                result = await svc.generate_proactive_proposal("chain-1")
        from core.models import ScalingProposal as ScalingProposalRecord
        assert db_session.query(ScalingProposalRecord).count() == 1

    @pytest.mark.asyncio
    async def test_detect_seasonal_pattern_insufficient(self, db_session):
        svc = PredictiveScalingService(db_session)
        result = svc.detect_seasonal_pattern("chain-1", "success_rate")
        assert result["pattern_detected"] is False
        assert "Insufficient" in result["error"]

    @pytest.mark.asyncio
    async def test_detect_seasonal_pattern_with_data(self, db_session):
        from core.models import FleetPerformanceMetric
        base = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        for i in range(60):
            db_session.add(FleetPerformanceMetric(
                tenant_id="default", chain_id="chain-1",
                metric_type="success_rate", metric_value=float(i % 10),
                window_start=base - timedelta(hours=60 - i),
                window_end=base - timedelta(hours=59 - i)))
        db_session.commit()
        svc = PredictiveScalingService(db_session)
        result = svc.detect_seasonal_pattern("chain-1", "success_rate")
        assert "pattern_detected" in result
        assert len(result.get("peak_hours", [])) == 3

    def test_linear_regression(self):
        svc = PredictiveScalingService(Mock())
        slope, intercept, r2 = svc._linear_regression([0, 1, 2, 3], [0, 1, 2, 3])
        assert slope == 1.0
        assert intercept == 0.0
        assert r2 == 1.0

    def test_linear_regression_flat(self):
        svc = PredictiveScalingService(Mock())
        slope, intercept, r2 = svc._linear_regression([1, 2, 3], [5, 5, 5])
        assert slope == 0.0

    def test_linear_regression_single_point(self):
        svc = PredictiveScalingService(Mock())
        slope, intercept, r2 = svc._linear_regression([1], [5])
        assert slope == 0.0
        assert intercept == 5.0

    def test_get_fleet_size(self, db_session):
        from core.models import ChainLink
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a",
            task_description="t", status="active", link_order=0))
        db_session.commit()
        svc = PredictiveScalingService(db_session)
        assert svc._get_fleet_size("chain-1") == 1

    def test_factory(self, db_session):
        svc = get_predictive_scaling_service(db_session)
        assert isinstance(svc, PredictiveScalingService)
