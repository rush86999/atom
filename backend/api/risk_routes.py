import os
from typing import Any, Dict, List, Tuple
from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User
from core.personal_scope import (
    DocumentScopeResolutionError,
    DocumentScopeUnavailable,
    is_bootstrap_identity,
    resolve_document_workspace_id,
    resolve_tenant_id,
)
from core.risk_prevention import (
    CustomerProtectionService,
    EarlyWarningService,
    FraudDetectionService,
)

router = BaseAPIRouter(prefix="/api/risk", tags=["Risk & Security"])

MOCK_MODE = os.getenv("FINANCIAL_FORENSICS_MOCK", "false").lower() == "true"


def _resolve_risk_scope(user: User) -> Tuple[str, str]:
    """Resolve the persisted tenant/workspace binding for risk reads.

    Risk services query tenant-keyed (subscriptions, ecommerce orders) and
    workspace-keyed (invoices) business rows. Only the authenticated
    principal's persisted binding may select those rows. A missing or
    unreadable binding fails closed; the sole exception is the server-owned
    bootstrap identity, which intentionally has NULL scope and keeps its
    Personal Edition fallback.
    """
    try:
        workspace_id = resolve_document_workspace_id(user)
    except (DocumentScopeUnavailable, DocumentScopeResolutionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No workspace scope is bound to this account",
        ) from exc

    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No workspace scope is bound to this account",
        )

    if getattr(user, "tenant_id", None):
        tenant_id = resolve_tenant_id(user)
    else:
        try:
            bootstrap = is_bootstrap_identity(user)
        except Exception as exc:  # noqa: BLE001 — unprovable identity fails closed
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenant scope is bound to this account",
            ) from exc
        if not bootstrap:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenant scope is bound to this account",
            )
        tenant_id = resolve_tenant_id(user)

    return str(workspace_id), tenant_id


@router.get("/customer-protection")
async def get_customer_protection_intel(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get Churn Risk and VIP opportunities.
    """
    if MOCK_MODE:
        return {
            "churn_risk": [
                {"deal_id": "mock-deal-1", "client_name": "Acme Corp", "value": 15000, "days_silent": 45, "risk_level": "HIGH"},
                {"deal_id": "mock-deal-2", "client_name": "Globex", "value": 5000, "days_silent": 32, "risk_level": "MEDIUM"}
            ],
            "vip_opportunities": [
                {"lead_id": "mock-lead-1", "name": "Alice CEO", "company": "TechStart", "ai_score": 98, "potential_value": "High"},
                {"lead_id": "mock-lead-2", "name": "Bob CTO", "company": "DataFlow", "ai_score": 89, "potential_value": "High"}
            ],
            "is_mock": True
        }

    _workspace_id, tenant_id = _resolve_risk_scope(user)
    churn = await CustomerProtectionService(db).predict_churn_risk(tenant_id)

    return {
        "churn_risk": churn,
        "vip_opportunities": [],
        "is_mock": False
    }


@router.get("/early-warning")
async def get_early_warning_alerts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get AR Alerts and Booking trends.
    """
    if MOCK_MODE:
        return {
            "ar_alerts": [
                {"id": "inv-001", "description": "Consulting Services Q3", "amount": 12500, "date": "2025-11-01", "days_overdue": 52},
                {"id": "inv-002", "description": "Retainer Fee", "amount": 2000, "date": "2025-12-01", "days_overdue": 22}
            ],
            "is_mock": True
        }

    workspace_id, _tenant_id = _resolve_risk_scope(user)
    alerts = await EarlyWarningService(db).detect_ar_delays(workspace_id)
    return {
        "ar_alerts": alerts,
        "is_mock": False
    }


@router.get("/fraud")
async def get_fraud_alerts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get Fraud anomalies.
    """
    if MOCK_MODE:
        return {
            "anomalies": [
                {"id": "tx-999", "type": "LARGE_OUTFLOW", "description": "Unusual refund to unknown entity", "amount": 4500, "severity": "HIGH", "date": "2025-12-20"}
            ],
            "is_mock": True
        }

    _workspace_id, tenant_id = _resolve_risk_scope(user)
    anomalies = await FraudDetectionService(db).detect_anomalies(tenant_id)
    return {
        "anomalies": anomalies,
        "is_mock": False
    }
