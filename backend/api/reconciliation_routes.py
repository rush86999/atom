"""
Reconciliation API Routes - Phase 40
"""

from fastapi import APIRouter
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

router = APIRouter()

class ReconciliationEntryRequest(BaseModel):
    id: str
    source: str
    date: str
    amount: float
    description: str

@router.post("/bank-entries")
async def add_bank_entry(request: ReconciliationEntryRequest):
    from core.reconciliation_engine import reconciliation_engine, ReconciliationEntry
    
    entry = ReconciliationEntry(
        id=request.id,
        source=request.source,
        date=datetime.fromisoformat(request.date),
        amount=request.amount,
        description=request.description
    )
    reconciliation_engine.add_bank_entry(entry)
    return {"status": "added", "id": request.id}

@router.post("/ledger-entries")
async def add_ledger_entry(request: ReconciliationEntryRequest):
    from core.reconciliation_engine import reconciliation_engine, ReconciliationEntry
    
    entry = ReconciliationEntry(
        id=request.id,
        source=request.source,
        date=datetime.fromisoformat(request.date),
        amount=request.amount,
        description=request.description
    )
    reconciliation_engine.add_ledger_entry(entry)
    return {"status": "added", "id": request.id}

@router.post("/reconcile")
async def run_reconciliation():
    from core.reconciliation_engine import reconciliation_engine
    return reconciliation_engine.reconcile()

@router.get("/anomalies")
async def get_anomalies(unresolved_only: bool = True):
    from core.reconciliation_engine import reconciliation_engine
    
    anomalies = reconciliation_engine.get_anomalies(unresolved_only)
    return {
        "count": len(anomalies),
        "anomalies": [
            {
                "id": a.id,
                "type": a.anomaly_type.value,
                "severity": a.severity,
                "description": a.description,
                "confidence": round(a.confidence * 100, 1),
                "suggested_action": a.suggested_action
            }
            for a in anomalies
        ]
    }

@router.post("/detect-anomalies")
async def detect_anomalies():
    from core.reconciliation_engine import reconciliation_engine
    
    new_anomalies = reconciliation_engine.detect_anomalies()
    return {"detected": len(new_anomalies)}

@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(anomaly_id: str):
    from core.reconciliation_engine import reconciliation_engine
    
    reconciliation_engine.resolve_anomaly(anomaly_id)
    return {"status": "resolved", "id": anomaly_id}
