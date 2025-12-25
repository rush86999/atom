from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import os

from core.database import get_db
from core.risk_prevention import customer_protection, early_warning, fraud_detection

router = APIRouter(prefix="/api/risk", tags=["Risk & Security"])

MOCK_MODE = os.getenv("FINANCIAL_FORENSICS_MOCK", "false").lower() == "true"

@router.get("/customer-protection")
async def get_customer_protection_intel(
    workspace_id: str = Query(..., description="Workspace ID"),
    db: Session = Depends(get_db)
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
        
    churn = await customer_protection.get_churn_risk(db, workspace_id)
    vips = await customer_protection.get_vip_opportunities(db, workspace_id)
    
    return {
        "churn_risk": churn,
        "vip_opportunities": vips,
        "is_mock": False
    }

@router.get("/early-warning")
async def get_early_warning_alerts(
    workspace_id: str = Query(..., description="Workspace ID"),
    db: Session = Depends(get_db)
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

    alerts = await early_warning.get_ar_alerts(db, workspace_id)
    return {
        "ar_alerts": alerts,
        "is_mock": False
    }

@router.get("/fraud")
async def get_fraud_alerts(
    workspace_id: str = Query(..., description="Workspace ID"),
    db: Session = Depends(get_db)
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

    anomalies = await fraud_detection.scan_for_anomalies(db, workspace_id)
    return {
        "anomalies": anomalies,
        "is_mock": False
    }
