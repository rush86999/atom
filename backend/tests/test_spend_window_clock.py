"""Spend/admission windows must use the same clock that stamps usage rows.

``TokenUsage.timestamp`` is written by the DB as UTC (``func.now()``). A
window derived from the LOCAL date lags the UTC date between 00:00 UTC and
local midnight, silently excluding rows settled seconds earlier. This suite
simulates that divergence deterministically by faking the local date one
day behind the real UTC date.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_oracle_mini_app_host_mutations import host  # noqa: F401
from core.models import Tenant, TenantSetting, TokenUsage, Workspace

TENANT = "spend-clock-tenant"
WORKSPACE = "spend-clock-workspace"


def _seed(host):
    with host.Session() as db:
        db.add(Tenant(id=TENANT, name=TENANT, subdomain="spend-clock"))
        db.add(Workspace(id=WORKSPACE, name=WORKSPACE, tenant_id=TENANT))
        db.add(TenantSetting(
            tenant_id=TENANT, setting_key="billing",
            setting_value=json.dumps({
                "budget_limit_usd": 100.0,
                "enforcement": {"mode": "hard_stop"},
            })))
        db.commit()


def _utc_stamped_row(**overrides):
    """A row stamped exactly the way production stamps it (DB/UTC clock)."""
    row = dict(
        agent_id=None, workspace_id=WORKSPACE, tenant_id=TENANT,
        model_name="controlled-settled", cost_usd=7.0,
        pricing_status="priced", reservation_status="settled",
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None))
    row.update(overrides)
    return TokenUsage(**row)


def _fake_local_date_lagging_utc(monkeypatch, lag_days=1):
    """Make the local calendar date lag the UTC date by ``lag_days``.

    This is the exact post-00:00-UTC condition in any UTC-negative timezone.
    On unfixed code the window is built from the (lagging) local date and
    drops rows the UTC clock just settled.
    """
    import core.spend_aggregation_service as svc

    class _LaggingDate(datetime.now(timezone.utc).date().__class__):
        @classmethod
        def today(cls):
            return datetime.now(timezone.utc).date() - timedelta(days=lag_days)

    monkeypatch.setattr(svc, "date", _LaggingDate)


def test_settled_row_counts_when_local_date_lags_utc(host, monkeypatch):
    _seed(host)
    with host.Session() as db:
        db.add(_utc_stamped_row())
        db.commit()
    _fake_local_date_lagging_utc(monkeypatch)
    from core.spend_aggregation_service import SpendAggregationService
    with host.Session() as db:
        spend = SpendAggregationService(db).update_tenant_spend(
            TENANT, persist=False, include_liabilities=True)
    assert spend["current_spend_usd"] == pytest.approx(7.0)


def test_unknown_liability_counts_when_local_date_lags_utc(host, monkeypatch):
    _seed(host)
    with host.Session() as db:
        db.add(_utc_stamped_row(
            cost_usd=None, pricing_status="unknown",
            reservation_status="reserved"))
        db.commit()
    _fake_local_date_lagging_utc(monkeypatch)
    from core.spend_aggregation_service import SpendAggregationService
    with host.Session() as db:
        svc = SpendAggregationService(db)
        assert svc.get_unpriced_usage(tenant_id=TENANT) == 1


def test_unattributed_liability_counts_when_local_date_lags_utc(
        host, monkeypatch):
    _seed(host)
    with host.Session() as db:
        db.add(_utc_stamped_row(
            workspace_id=None, tenant_id=None,
            cost_usd=None, pricing_status="unknown",
            reservation_status="reserved"))
        db.commit()
    _fake_local_date_lagging_utc(monkeypatch)
    from core.spend_aggregation_service import SpendAggregationService
    with host.Session() as db:
        svc = SpendAggregationService(db)
        assert svc.get_unattributed_unpriced() >= 1
