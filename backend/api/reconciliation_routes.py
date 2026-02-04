"""
Reconciliation API Routes - Phase 40

Provides endpoints for bank/ledger reconciliation and anomaly detection.
All endpoints require authentication and appropriate governance.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from core.base_routes import BaseAPIRouter
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import User

router = BaseAPIRouter(prefix="/api/reconciliation", tags=["Reconciliation"])

class ReconciliationEntryRequest(BaseModel):
    id: str = Field(..., description="Entry ID")
    source: str = Field(..., description="Source system")
    date: str = Field(..., description="Entry date (ISO format)")
    amount: float = Field(..., description="Entry amount")
    description: str = Field(..., description="Entry description")
    agent_id: Optional[str] = Field(None, description="Agent ID if agent-initiated")


@router.post("/bank-entries")
async def add_bank_entry(
    request: ReconciliationEntryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Add a bank entry for reconciliation.

    Requires authentication. If agent_id is provided, performs governance check
    to verify the agent has permission for financial data modifications.
    """
    try:
        # Governance check if agent-initiated
        if request.agent_id:
            from core.agent_context_resolver import AgentContextResolver
            from core.agent_governance_service import AgentGovernanceService

            resolver = AgentContextResolver(db)
            governance = AgentGovernanceService(db)

            agent, _ = await resolver.resolve_agent_for_request(
                user_id=user.id,
                requested_agent_id=request.agent_id,
                action_type="financial_data_modification"
            )

            if agent:
                governance_check = governance.can_perform_action(
                    agent_id=agent.id,
                    action_type="financial_data_modification"
                )

                if not governance_check["allowed"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Agent not permitted to modify financial data: {governance_check['reason']}"
                    )

        from core.reconciliation_engine import ReconciliationEntry, reconciliation_engine

        entry = ReconciliationEntry(
            id=request.id,
            source=request.source,
            date=datetime.fromisoformat(request.date),
            amount=request.amount,
            description=request.description
        )
        reconciliation_engine.add_bank_entry(entry)

        return {"status": "added", "id": request.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add bank entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add bank entry: {str(e)}"
        )


@router.post("/ledger-entries")
async def add_ledger_entry(
    request: ReconciliationEntryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Add a ledger entry for reconciliation.

    Requires authentication. If agent_id is provided, performs governance check
    to verify the agent has permission for financial data modifications.
    """
    try:
        # Governance check if agent-initiated
        if request.agent_id:
            from core.agent_context_resolver import AgentContextResolver
            from core.agent_governance_service import AgentGovernanceService

            resolver = AgentContextResolver(db)
            governance = AgentGovernanceService(db)

            agent, _ = await resolver.resolve_agent_for_request(
                user_id=user.id,
                requested_agent_id=request.agent_id,
                action_type="financial_data_modification"
            )

            if agent:
                governance_check = governance.can_perform_action(
                    agent_id=agent.id,
                    action_type="financial_data_modification"
                )

                if not governance_check["allowed"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Agent not permitted to modify financial data: {governance_check['reason']}"
                    )

        from core.reconciliation_engine import ReconciliationEntry, reconciliation_engine

        entry = ReconciliationEntry(
            id=request.id,
            source=request.source,
            date=datetime.fromisoformat(request.date),
            amount=request.amount,
            description=request.description
        )
        reconciliation_engine.add_ledger_entry(entry)

        return {"status": "added", "id": request.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add ledger entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add ledger entry: {str(e)}"
        )


@router.post("/reconcile")
async def run_reconciliation(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Run reconciliation process.

    Requires authentication. Returns reconciliation results.
    """
    try:
        from core.reconciliation_engine import reconciliation_engine
        result = reconciliation_engine.reconcile()
        return result
    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation failed: {str(e)}"
        )


@router.get("/anomalies")
async def get_anomalies(
    unresolved_only: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get reconciliation anomalies.

    Requires authentication. Returns list of anomalies.
    """
    try:
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
    except Exception as e:
        logger.error(f"Failed to get anomalies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get anomalies: {str(e)}"
        )


@router.post("/detect-anomalies")
async def detect_anomalies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Detect anomalies in reconciliation data.

    Requires authentication.
    """
    try:
        from core.reconciliation_engine import reconciliation_engine

        new_anomalies = reconciliation_engine.detect_anomalies()
        return {"detected": len(new_anomalies)}
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(e)}"
        )


@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Resolve a reconciliation anomaly.

    Requires authentication.
    """
    try:
        from core.reconciliation_engine import reconciliation_engine

        reconciliation_engine.resolve_anomaly(anomaly_id)
        return {"status": "resolved", "id": anomaly_id}
    except Exception as e:
        logger.error(f"Failed to resolve anomaly: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve anomaly: {str(e)}"
        )
