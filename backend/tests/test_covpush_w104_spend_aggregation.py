# -*- coding: utf-8 -*-
"""Coverage wave 104 — core/spend_aggregation_service.py.

Spend aggregation against an in-memory SQLite DB:
- get_total_spend: ACU + BYOK aggregation, per-source isolation, zero
  defaults, exception tolerance (both inner legs + outer).
- get_fleet_spend: chain aggregation, zero default, exception -> 0.0.
- _budget_limit_from_setting: TenantSetting['billing'] JSON parsing
  (limit present/None/non-dict/invalid JSON/missing/empty), fallbacks.
- update_tenant_spend: tenant-missing, success with persisted columns,
  budget-limit precedence (Tenant attr -> setting), utilization math,
  lifetime-start fallback, exception -> error + rollback.

REAL BUG (TDD RED -> GREEN):
  W104-1: the Tenant model had NO current_spend_usd / total_spend_usd
  columns, so update_tenant_spend's assignments were SILENTLY DROPPED on
  commit (the wave-99 billing_email bug class) — spend was computed and
  reported but never persisted, and budget enforcement re-reads through
  this service. Added the columns to the model.

No LLM spend, no network.
"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (  # noqa: F401
    ACUConsumption,
    Tenant,
    TenantSetting,
    TokenUsage,
)
from core.spend_aggregation_service import SpendAggregationService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def svc(db_session):
    return SpendAggregationService(db_session)


@pytest.fixture()
def tenant(db_session):
    t = Tenant(id="t-1", name="Acme", subdomain="acme")
    db_session.add(t)
    db_session.commit()
    return t


def _seed_acu(db, tenant_id, days_ago, cost):
    row = ACUConsumption(
        id=f"acu-{days_ago}",
        tenant_id=tenant_id,
        project_id="proj-1",
        app_name="web",
        consumption_date=date.today() - timedelta(days=days_ago),
        hour=0,
        cpu_cores=1,
        memory_gb=1,
        storage_gib=1,
        runtime_seconds=60,
        acu_consumed=1,
        acu_cost=cost,
    )
    db.add(row)
    db.commit()
    return row


def _seed_usage(db, tenant_id, days_ago, cost, chain_id=None, unique=None):
    row = TokenUsage(
        # id(object()) is memory-address based — GC can reuse the address
        # across seeds in a batch, colliding with UNIQUE constraint. Use
        # uuid4 for guaranteed uniqueness.
        id=f"tu-{unique or days_ago}-{uuid.uuid4()}",
        agent_id="agent-1",
        workspace_id="ws-1",
        tenant_id=tenant_id,
        model_name="gpt-4o",
        cost_usd=cost,
        timestamp=datetime.now() - timedelta(days=days_ago),
        chain_id=chain_id,
    )
    db.add(row)
    db.commit()
    return row


class TestGetTotalSpend:
    def test_both_sources(self, db_session, svc, tenant):
        _seed_acu(db_session, tenant.id, 1, 2.5)
        _seed_usage(db_session, tenant.id, 1, 3.25)
        result = svc.get_total_spend(tenant.id, date.today() - timedelta(days=7), date.today())
        assert result["acu_cost_usd"] == 2.5
        assert result["byok_cost_usd"] == 3.25
        assert result["total_spend_usd"] == 5.75

    def test_acu_only(self, db_session, svc, tenant):
        _seed_acu(db_session, tenant.id, 1, 1.5)
        result = svc.get_total_spend(tenant.id, date.today() - timedelta(days=7), date.today())
        assert result["acu_cost_usd"] == 1.5
        assert result["byok_cost_usd"] == 0.0

    def test_byok_only(self, db_session, svc, tenant):
        _seed_usage(db_session, tenant.id, 1, 0.99)
        result = svc.get_total_spend(tenant.id, date.today() - timedelta(days=7), date.today())
        assert result["acu_cost_usd"] == 0.0
        assert result["byok_cost_usd"] == 0.99

    def test_no_rows_zeros(self, svc, tenant):
        result = svc.get_total_spend(tenant.id, date.today() - timedelta(days=7), date.today())
        assert result == {"acu_cost_usd": 0.0, "byok_cost_usd": 0.0, "total_spend_usd": 0.0}

    def test_date_range_boundary_inclusive(self, db_session, svc, tenant):
        _seed_acu(db_session, tenant.id, 7, 4.0)
        _seed_usage(db_session, tenant.id, 7, 5.0)
        result = svc.get_total_spend(tenant.id, date.today() - timedelta(days=7), date.today())
        assert result["total_spend_usd"] == 9.0

    def test_outside_range_excluded(self, db_session, svc, tenant):
        _seed_acu(db_session, tenant.id, 30, 4.0)
        _seed_usage(db_session, tenant.id, 30, 5.0)
        result = svc.get_total_spend(tenant.id, date.today() - timedelta(days=7), date.today())
        assert result["total_spend_usd"] == 0.0

    def test_other_tenant_excluded(self, db_session, svc, tenant):
        _seed_acu(db_session, "other", 1, 9.0)
        _seed_usage(db_session, "other", 1, 9.0)
        result = svc.get_total_spend(tenant.id, date.today() - timedelta(days=7), date.today())
        assert result["total_spend_usd"] == 0.0

    def test_acu_query_exception_tolerated(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("acu broken")
        svc = SpendAggregationService(db)
        result = svc.get_total_spend("t-1", date(2026, 1, 1), date(2026, 1, 31))
        assert result["acu_cost_usd"] == 0.0
        assert result["byok_cost_usd"] == 0.0

    def test_byok_query_exception_tolerated(self):
        db = MagicMock()
        acu_q = MagicMock()
        acu_q.filter.return_value.scalar.return_value = 1.0
        byok_q = MagicMock()
        byok_q.filter.return_value.scalar.side_effect = RuntimeError("byok broken")
        db.query.side_effect = [acu_q, byok_q]
        svc = SpendAggregationService(db)
        result = svc.get_total_spend("t-1", date(2026, 1, 1), date(2026, 1, 31))
        assert result["acu_cost_usd"] == 1.0
        assert result["byok_cost_usd"] == 0.0
        assert result["total_spend_usd"] == 1.0

    def test_outer_exception_error_dict(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("completely broken")
        svc = SpendAggregationService(db)
        result = svc.get_total_spend("t-1", "not-a-date", date(2026, 1, 31))
        assert result["error"] is not None
        assert result["acu_cost_usd"] == 0.0


class TestGetFleetSpend:
    def test_aggregates_chain(self, db_session, svc, tenant):
        _seed_usage(db_session, tenant.id, 1, 1.0, chain_id="chain-1")
        _seed_usage(db_session, tenant.id, 1, 2.0, chain_id="chain-1")
        _seed_usage(db_session, tenant.id, 1, 3.0, chain_id="chain-2")
        assert svc.get_fleet_spend("chain-1") == 3.0

    def test_no_rows_zero(self, svc):
        assert svc.get_fleet_spend("nope") == 0.0

    def test_exception_returns_zero(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("broken")
        svc = SpendAggregationService(db)
        assert svc.get_fleet_spend("chain-1") == 0.0


class TestBudgetLimitFromSetting:
    def test_limit_parsed(self, db_session, svc, tenant):
        db_session.add(
            TenantSetting(
                tenant_id=tenant.id,
                setting_key="billing",
                setting_value='{"budget_limit_usd": 50.0}',
            )
        )
        db_session.commit()
        assert svc._budget_limit_from_setting(tenant.id) == 50.0

    def test_limit_none_value(self, db_session, svc, tenant):
        db_session.add(
            TenantSetting(
                tenant_id=tenant.id,
                setting_key="billing",
                setting_value='{"budget_limit_usd": null}',
            )
        )
        db_session.commit()
        assert svc._budget_limit_from_setting(tenant.id) == 0.0

    def test_non_dict_json(self, db_session, svc, tenant):
        db_session.add(
            TenantSetting(tenant_id=tenant.id, setting_key="billing", setting_value='[1,2]')
        )
        db_session.commit()
        assert svc._budget_limit_from_setting(tenant.id) == 0.0

    def test_invalid_json(self, db_session, svc, tenant):
        db_session.add(
            TenantSetting(tenant_id=tenant.id, setting_key="billing", setting_value="not json")
        )
        db_session.commit()
        assert svc._budget_limit_from_setting(tenant.id) == 0.0

    def test_no_row(self, svc, tenant):
        assert svc._budget_limit_from_setting(tenant.id) == 0.0

    def test_exception_returns_zero(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("broken")
        svc = SpendAggregationService(db)
        assert svc._budget_limit_from_setting("t-1") == 0.0


class TestUpdateTenantSpend:
    def test_tenant_not_found(self, svc):
        result = svc.update_tenant_spend("ghost")
        assert result == {"error": "Tenant ghost not found"}

    # ---- W104-1 RED: spend must actually PERSIST on the tenant ----
    def test_spend_persisted_on_tenant(self, db_session, svc, tenant):
        # Seed usage/ACU on the creation day (local) so the lifetime window
        # (clamped to today, see W104-2) includes them regardless of TZ skew.
        _seed_acu(db_session, tenant.id, 0, 2.0)
        _seed_usage(db_session, tenant.id, 0, 3.0)
        result = svc.update_tenant_spend(tenant.id)
        assert result["current_spend_usd"] == 5.0
        assert result["total_spend_usd"] == 5.0
        # Reload from a FRESH session: the persisted row must carry the value
        fresh_session = sessionmaker(bind=db_session.get_bind())()
        try:
            fresh = (
                fresh_session.query(Tenant).filter(Tenant.id == tenant.id).first()
            )
            assert fresh.current_spend_usd == 5.0
            assert fresh.total_spend_usd == 5.0
        finally:
            fresh_session.close()

    def test_utilization_with_tenant_budget(self, db_session, svc, tenant):
        tenant.budget_limit_usd = 100.0
        db_session.commit()
        _seed_usage(db_session, tenant.id, 1, 25.0)
        result = svc.update_tenant_spend(tenant.id)
        assert result["budget_limit_usd"] == 100.0
        assert result["utilization_percent"] == 25.0

    def test_utilization_zero_budget(self, db_session, svc, tenant):
        _seed_usage(db_session, tenant.id, 1, 25.0)
        result = svc.update_tenant_spend(tenant.id)
        assert result["budget_limit_usd"] == 0.0
        assert result["utilization_percent"] == 0.0

    def test_budget_from_setting_fallback(self, db_session, svc, tenant):
        db_session.add(
            TenantSetting(
                tenant_id=tenant.id,
                setting_key="billing",
                setting_value='{"budget_limit_usd": 200.0}',
            )
        )
        db_session.commit()
        _seed_usage(db_session, tenant.id, 1, 50.0)
        result = svc.update_tenant_spend(tenant.id)
        assert result["budget_limit_usd"] == 200.0
        assert result["utilization_percent"] == 25.0

    def test_lifetime_spend(self, db_session, svc, tenant):
        _seed_usage(db_session, tenant.id, 0, 7.5)
        result = svc.update_tenant_spend(tenant.id)
        assert result["total_spend_usd"] == 7.5

    def test_created_at_none_uses_2025_default(self, db_session, svc, tenant):
        tenant.created_at = None
        db_session.commit()
        _seed_usage(db_session, tenant.id, 1, 1.0)
        result = svc.update_tenant_spend(tenant.id)
        assert result["total_spend_usd"] == 1.0

    def test_exception_rollback(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("broken")
        svc = SpendAggregationService(db)
        result = svc.update_tenant_spend("t-1")
        assert "error" in result
        db.rollback.assert_called_once()

    def test_returns_rounded_values(self, db_session, svc, tenant):
        _seed_usage(db_session, tenant.id, 1, 1.23456)
        result = svc.update_tenant_spend(tenant.id)
        assert result["current_spend_usd"] == 1.2346
