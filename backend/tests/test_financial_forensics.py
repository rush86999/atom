
import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.financial_forensics import (
    PricingAdvisorService,
    SubscriptionWasteService,
    VendorIntelligenceService,
    get_forensics_services,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _criterion_matches(row, criterion):
    """Evaluate a simple ``column == value`` predicate against a synthetic row."""
    try:
        key = getattr(criterion.left, "key", None) or getattr(criterion.left, "name", None)
        value = criterion.right.value
    except AttributeError:
        return True
    return getattr(row, key, None) == value


class _RecordingQuery:
    """Minimal query stub that records predicates and filters synthetic rows."""

    def __init__(self, rows):
        self._rows = list(rows)
        self.criteria = []

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self

    def first(self):
        for row in self._rows:
            if all(_criterion_matches(row, c) for c in self.criteria):
                return row
        return None

    def all(self):
        return [
            row for row in self._rows
            if all(_criterion_matches(row, c) for c in self.criteria)
        ]


class _RecordingSession:
    """Synthetic session keyed by model class name; no database is touched."""

    def __init__(self, workspaces=(), subscriptions=(), products=()):
        self._tables = {
            "Workspace": list(workspaces),
            "Subscription": list(subscriptions),
            "BusinessProductService": list(products),
        }
        self.queries = []

    def query(self, model):
        query = _RecordingQuery(self._tables.get(model.__name__, ()))
        self.queries.append((model.__name__, query))
        return query

    def query_for(self, model_name):
        return next(q for name, q in self.queries if name == model_name)


def _workspace(workspace_id="ws-1", tenant_id="tenant-a"):
    return SimpleNamespace(id=workspace_id, tenant_id=tenant_id)


def _subscription(
    subscription_id,
    tenant_id,
    status="canceled",
    next_billing_at=None,
    plan_name="Recorded plan",
    mrr=10,
):
    return SimpleNamespace(
        id=subscription_id,
        tenant_id=tenant_id,
        status=status,
        next_billing_at=next_billing_at,
        plan_name=plan_name,
        mrr=mrr,
    )


class TestFinancialForensics(unittest.TestCase):
    def setUp(self):
        self.services = get_forensics_services(MagicMock())

    def test_vendor_drift_reports_no_invented_rows(self):
        drifts = _run(self.services["vendor"].detect_price_drift("ws-1"))
        self.assertEqual(drifts, [])

    def test_pricing_reads_only_the_authorized_workspace(self):
        products = [
            SimpleNamespace(
                id="p-1",
                name="Widget",
                workspace_id="ws-auth",
                base_price=100.0,
                unit_cost=80.0,
            ),
            SimpleNamespace(
                id="p-2",
                name="Healthy margin",
                workspace_id="ws-auth",
                base_price=100.0,
                unit_cost=10.0,
            ),
            SimpleNamespace(
                id="p-other",
                name="Other workspace",
                workspace_id="ws-other",
                base_price=100.0,
                unit_cost=95.0,
            ),
        ]
        session = _RecordingSession(products=products)

        recommendations = _run(
            PricingAdvisorService(session).get_pricing_recommendations("ws-auth")
        )

        self.assertEqual([r["sku"] for r in recommendations], ["p-1"])
        self.assertEqual(recommendations[0]["target_price"], 133.33)
        product_query = session.query_for("BusinessProductService")
        self.assertEqual(product_query.criteria[0].right.value, "ws-auth")

    def test_waste_reads_only_subscriptions_of_the_workspace_tenant(self):
        future = datetime.now(timezone.utc) + timedelta(days=10)
        session = _RecordingSession(
            workspaces=[_workspace("ws-auth", "tenant-a")],
            subscriptions=[
                _subscription("sub-a", "tenant-a", next_billing_at=future),
                _subscription("sub-b", "tenant-b", next_billing_at=future),
            ],
        )

        zombies = _run(
            SubscriptionWasteService(session).find_zombie_subscriptions("ws-auth")
        )

        self.assertEqual([z["subscription_id"] for z in zombies], ["sub-a"])
        workspace_query = session.query_for("Workspace")
        self.assertEqual(workspace_query.criteria[0].right.value, "ws-auth")
        subscription_query = session.query_for("Subscription")
        self.assertEqual(subscription_query.criteria[0].right.value, "tenant-a")

    def test_waste_handles_naive_and_aware_billing_timestamps(self):
        aware_future = datetime.now(timezone.utc) + timedelta(days=5)
        naive_future = datetime.now() + timedelta(days=5)
        past = datetime.now(timezone.utc) - timedelta(days=5)
        session = _RecordingSession(
            workspaces=[_workspace()],
            subscriptions=[
                _subscription("sub-aware", "tenant-a", next_billing_at=aware_future),
                _subscription("sub-naive", "tenant-a", next_billing_at=naive_future),
                _subscription("sub-past", "tenant-a", next_billing_at=past),
                _subscription("sub-active", "tenant-a", status="active",
                              next_billing_at=aware_future),
            ],
        )

        zombies = _run(
            SubscriptionWasteService(session).find_zombie_subscriptions("ws-1")
        )

        self.assertEqual(
            [z["subscription_id"] for z in zombies],
            ["sub-aware", "sub-naive"],
        )

    def test_waste_without_tenant_binding_queries_no_subscriptions(self):
        session = _RecordingSession(
            workspaces=[_workspace("ws-unbound", None)],
            subscriptions=[_subscription("sub-a", "tenant-a")],
        )

        zombies = _run(
            SubscriptionWasteService(session).find_zombie_subscriptions("ws-unbound")
        )

        self.assertEqual(zombies, [])
        self.assertNotIn("Subscription", [name for name, _ in session.queries])


if __name__ == "__main__":
    unittest.main()
