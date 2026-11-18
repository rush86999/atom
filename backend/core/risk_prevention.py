
import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class CustomerProtectionService:
    def __init__(self, db: Session = None):
        self.db = db

    async def predict_churn_risk(self, tenant_id: str = "") -> List[Dict[str, Any]]:
        """
        Analyzes customer usage and sentiment to predict churn.

        Returns recorded signals only. The previous hardcoded Acme/Beta story
        was presented as a live prediction on every workspace; with no
        customer-usage feed connected the truthful result is empty.

        Subscriptions are tenant-scoped rows, so callers must supply the
        authenticated principal's tenant binding. An empty binding fails
        closed rather than querying across tenants.
        """
        try:
            from core.models import Subscription
        except Exception:
            return []

        if self.db is None or not tenant_id:
            return []
        # A canceled subscription with a future billing date is a recorded
        # churn signal; without usage/sentiment feeds nothing stronger can be
        # claimed.
        rows = (
            self.db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id,
                Subscription.status.in_(["canceled", "cancelled"]),
            )
            .limit(20)
            .all()
        )
        risks: List[Dict[str, Any]] = []
        for row in rows:
            customer = getattr(row, "customer", None)
            # The subscription's tenant scope does not prove the linked
            # customer row belongs to the same tenant. Do not surface its
            # display fields unless the persisted customer binding agrees.
            customer_visible = (
                customer is not None
                and str(getattr(customer, "tenant_id", "") or "") == str(tenant_id)
            )
            risks.append({
                "customer_id": getattr(row, "customer_id", ""),
                "customer_name": (
                    (
                        getattr(customer, "name", None)
                        or getattr(customer, "email", None)
                    )
                    if customer_visible
                    else None
                ) or "Recorded customer",
                "churn_probability": 1.0,
                "risk_factors": ["Subscription recorded as canceled"],
                "mrr_at_risk": float(getattr(row, "mrr", 0) or 0),
                "recommended_action": "Confirm the cancellation and close the billing record.",
            })
        return risks

class EarlyWarningService:
    def __init__(self, db: Session = None):
        self.db = db

    async def detect_ar_delays(self, workspace_id: str = "") -> List[Dict[str, Any]]:
        """
        Predicts late payments from recorded invoices.

        Invoices are workspace-scoped rows, so callers must supply the
        authenticated principal's workspace binding. An empty binding fails
        closed rather than querying across workspaces.

        Without a connected accounting source this returns [] rather than the
        former Globeх demo alert.
        """
        try:
            from accounting.models import Invoice, InvoiceStatus
        except Exception:
            return []
        if self.db is None or not workspace_id:
            return []
        invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.workspace_id == workspace_id,
                Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.VOID]),
            )
            .limit(50)
            .all()
        )
        alerts: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for inv in invoices:
            due = getattr(inv, "due_date", None)
            if due is None:
                continue
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due < now:
                alerts.append({
                    "invoice_id": getattr(inv, "id", ""),
                    "client_name": getattr(inv, "client_name", None)
                    or getattr(inv, "customer_name", None)
                    or "Recorded invoice",
                    "amount": float(getattr(inv, "amount", 0) or 0),
                    "due_date": due.isoformat(),
                    "likelihood_late": 1.0,
                    "reason": "Invoice due date has passed and it is still unpaid.",
                })
        return alerts

    async def monitor_booking_drops(self, workspace_id: str) -> Dict[str, Any]:
        """
        Alerts on unusual dips in lead volume.

        No booking series is connected here, so report the absence of data
        instead of a fabricated 52% drop.
        """
        return {
            "status": "no_data",
            "metric": "bookings",
            "current_value": None,
            "expected_value": None,
            "drop_percent": None,
            "anomaly_detected": False,
            "message": "No booking history is recorded for this workspace.",
        }

class FraudDetectionService:
    def __init__(self, db: Session = None):
        self.db = db

    async def detect_anomalies(self, tenant_id: str = "") -> List[Dict[str, Any]]:
        """
        Flags large refunds or suspicious transactions.

        Ecommerce orders are tenant-scoped rows, so callers must supply the
        authenticated principal's tenant binding. An empty binding fails
        closed rather than querying across tenants.

        Returns only recorded transaction rows. The former hardcoded refund
        alert appeared on every workspace regardless of activity.
        """
        try:
            from ecommerce.models import EcommerceOrder
        except Exception:
            return []
        if self.db is None or not tenant_id:
            return []
        orders = (
            self.db.query(EcommerceOrder)
            .filter(
                EcommerceOrder.tenant_id == tenant_id,
                EcommerceOrder.status.in_(["refunded", "chargeback"]),
            )
            .limit(20)
            .all()
        )
        anomalies: List[Dict[str, Any]] = []
        for order in orders:
            anomalies.append({
                "transaction_id": getattr(order, "id", ""),
                "type": str(getattr(order, "status", "")).upper() or "REFUND",
                "amount": float(getattr(order, "total_price", 0) or 0),
                "timestamp": (
                    order.updated_at.isoformat()
                    if getattr(order, "updated_at", None)
                    else datetime.utcnow().isoformat()
                ),
                "severity": "MEDIUM",
                "flag_reason": f"Order recorded as {getattr(order, 'status', 'refunded')}.",
            })
        return anomalies

class ExpansionPlaybookService:
    def __init__(self, db: Session = None):
        self.db = db

    async def check_scaling_readiness(self, workspace_id: str) -> Dict[str, Any]:
        """
        Evaluates constraints for growth.

        Without support and cash-flow sources this reports no assessment
        rather than a fabricated 72/100 score.
        """
        return {
            "readiness_score": None,
            "can_scale": None,
            "bottlenecks": [],
            "status": "no_data",
            "message": "Connect support and accounting data to assess scaling readiness.",
        }

def get_risk_services(db: Session = None):
    return {
        "churn": CustomerProtectionService(db),
        "warning": EarlyWarningService(db),
        "fraud": FraudDetectionService(db),
        "growth": ExpansionPlaybookService(db)
    }
