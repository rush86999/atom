"""
Financial Audit Routes - REST API for financial audit trail operations.

Phase 94-05: SOX compliance endpoints for external auditors and monitoring.

Endpoints:
- GET /api/v1/financial-audit/validate - Validate SOX compliance
- GET /api/v1/financial-audit/compliance - Generate compliance report
- GET /api/v1/financial-audit/trail/{account_id} - Export audit trail
- GET /api/v1/financial-audit/health - Get health metrics
- GET /api/v1/financial-audit/verify/{account_id} - Verify hash chain
- GET /api/v1/financial-audit/gaps - Detect sequence gaps

All endpoints use FinancialAuditOrchestrator for unified audit operations.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from core.models import FinancialAudit
from core.financial_audit_orchestrator import FinancialAuditOrchestrator
from core.hash_chain_integrity import HashChainIntegrity
from core.chronological_integrity import ChronologicalIntegrityValidator
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/financial-audit",
    tags=["financial-audit"]
)


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/validate")
async def validate_audit_compliance(
    account_id: Optional[str] = Query(None, description="Filter to specific account"),
    start_time: Optional[datetime] = Query(None, description="Start of validation window"),
    end_time: Optional[datetime] = Query(None, description="End of validation window"),
    db: Session = Depends(get_db)
):
    """
    Validate SOX compliance for audit trail.

    Checks all 5 audit requirements:
    - AUD-01: Transaction logging completeness
    - AUD-02: Chronological integrity
    - AUD-03: Immutability and hash chain integrity
    - AUD-04: SOX compliance (traceability, authorization, non-repudiation)
    - AUD-05: End-to-end traceability

    Returns detailed compliance status per requirement.

    Query Parameters:
    - account_id: Optional account filter (validates specific account)
    - start_time: Optional start of validation window
    - end_time: Optional end of validation window

    Returns:
    {
        "validated_at": "2026-02-25T...",
        "account_id": "acct-123" or null,
        "time_range": {"start": "...", "end": "..."},
        "overall_compliant": true,
        "requirements": {
            "AUD-01": {"name": "...", "compliant": true, "details": {...}},
            "AUD-02": {...},
            "AUD-03": {...},
            "AUD-04": {...},
            "AUD-05": {...}
        },
        "summary": {
            "total_requirements": 5,
            "compliant_requirements": 5,
            "non_compliant_requirements": 0,
            "overall_compliant": true
        }
    }
    """
    orchestrator = FinancialAuditOrchestrator(db)

    try:
        result = orchestrator.validate_complete_compliance(
            account_id=account_id,
            start_time=start_time,
            end_time=end_time
        )
        return result
    except Exception as e:
        logger.error(f"Compliance validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/compliance")
async def get_compliance_report(
    format: str = Query("json", description="Report format: json, summary, detailed"),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive SOX compliance report.

    Returns audit statistics, model coverage, and compliance status
    for all financial operations.

    Query Parameters:
    - format: Report format
        - "json": Full report with all details (default)
        - "summary": Simplified report with key metrics only
        - "detailed": Full report (same as json)

    Returns:
    {
        "generated_at": "2026-02-25T...",
        "report_type": "SOX_Compliance_Audit_Trail",
        "format": "json",
        "statistics": {
            "total_audits": 1000,
            "by_action_type": {"create": 400, "update": 500, "delete": 100},
            "by_agent_maturity": {"AUTONOMOUS": 800, "SUPERVISED": 200},
            "success_rate": 0.98,
            "oldest_entry": "2026-01-01T...",
            "newest_entry": "2026-02-25T..."
        },
        "model_coverage": {...},
        "compliance": {...},
        "recommendations": [...]
    }
    """
    orchestrator = FinancialAuditOrchestrator(db)

    try:
        report = orchestrator.get_compliance_report(format=format)
        return report
    except Exception as e:
        logger.error(f"Compliance report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/trail/{account_id}")
async def get_audit_trail(
    account_id: str,
    start_time: Optional[datetime] = Query(None, description="Start of export range"),
    end_time: Optional[datetime] = Query(None, description="End of export range"),
    include_hash_chains: bool = Query(True, description="Include hash verification data"),
    db: Session = Depends(get_db)
):
    """
    Export audit trail for an account.

    Returns all audit entries for the account with optional
    time range filtering and hash chain verification.

    Path Parameters:
    - account_id: Account ID to export

    Query Parameters:
    - start_time: Optional start of export range
    - end_time: Optional end of export range
    - include_hash_chains: Include hash verification data (default True)

    Returns:
    {
        "export_metadata": {
            "generated_at": "2026-02-25T...",
            "account_id": "acct-123",
            "time_range": {"start": "...", "end": "..."},
            "total_entries": 100,
            "include_hash_chains": true
        },
        "audit_entries": [
            {
                "id": "...",
                "timestamp": "...",
                "sequence_number": 1,
                "account_id": "acct-123",
                "user_id": "user-123",
                "agent_id": "agent-123",
                "agent_maturity": "AUTONOMOUS",
                "action_type": "create",
                "success": true,
                "governance_check_passed": true,
                "changes": {...},
                "integrity": {
                    "entry_hash": "...",
                    "prev_hash": "..."
                }
            },
            ...
        ],
        "verification": {
            "hash_chain_valid": true,
            "break_count": 0,
            "first_break": null
        }
    }
    """
    orchestrator = FinancialAuditOrchestrator(db)

    try:
        export = orchestrator.generate_audit_trail_export(
            account_id=account_id,
            start_time=start_time,
            end_time=end_time,
            include_hash_chains=include_hash_chains
        )
        return export
    except Exception as e:
        logger.error(f"Audit trail export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/health")
async def get_audit_health(
    days: int = Query(30, description="Number of days to analyze", ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get audit health metrics for monitoring.

    Returns health score, success rate, and detected issues
    for the specified time period.

    Query Parameters:
    - days: Number of days to analyze (1-365, default 30)

    Returns:
    {
        "period_days": 30,
        "period_start": "2026-01-26T...",
        "period_end": "2026-02-25T...",
        "health_score": 95,
        "total_audits": 1000,
        "success_rate": 0.98,
        "issues_detected": {
            "sequence_gaps": 2,
            "hash_chain_breaks": 0,
            "tampered_accounts": 1
        },
        "recommendations": [...]
    }
    """
    orchestrator = FinancialAuditOrchestrator(db)

    try:
        metrics = orchestrator.get_audit_health_metrics(days=days)
        return metrics
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/verify/{account_id}")
async def verify_hash_chain(
    account_id: str,
    start_sequence: Optional[int] = Query(None, description="Starting sequence number"),
    end_sequence: Optional[int] = Query(None, description="Ending sequence number"),
    db: Session = Depends(get_db)
):
    """
    Verify hash chain integrity for an account.

    Returns cryptographic verification results showing
    whether the audit trail has been tampered with.

    Path Parameters:
    - account_id: Account ID to verify

    Query Parameters:
    - start_sequence: Optional starting sequence number
    - end_sequence: Optional ending sequence number

    Returns:
    {
        "is_valid": true,
        "total_entries": 100,
        "first_break": null,
        "break_count": 0,
        "verified_at": "2026-02-25T..."
    }

    If tampering detected:
    {
        "is_valid": false,
        "total_entries": 100,
        "first_break": {
            "sequence_number": 45,
            "audit_id": "...",
            "issue": "hash_mismatch" | "prev_hash_mismatch",
            "expected_hash": "...",
            "actual_hash": "..."
        },
        "break_count": 3,
        "verified_at": "2026-02-25T..."
    }
    """
    integrity = HashChainIntegrity(db)

    try:
        result = integrity.verify_chain(
            account_id=account_id,
            start_sequence=start_sequence,
            end_sequence=end_sequence
        )
        return result
    except Exception as e:
        logger.error(f"Hash chain verification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.get("/gaps")
async def detect_audit_gaps(
    account_id: Optional[str] = Query(None, description="Filter to specific account"),
    start_time: Optional[datetime] = Query(None, description="Start of check window"),
    end_time: Optional[datetime] = Query(None, description="End of check window"),
    db: Session = Depends(get_db)
):
    """
    Detect gaps in audit trail sequence numbers.

    Returns information about any missing sequence numbers
    that could indicate missing audit entries.

    Query Parameters:
    - account_id: Optional account filter
    - start_time: Optional start of check window
    - end_time: Optional end of check window

    Returns:
    {
        "has_gaps": true,
        "gaps": [
            {
                "account_id": "acct-123",
                "expected_sequence": 10,
                "actual_sequence": 15,
                "gap_size": 4,
                "after_sequence": 9,
                "before_timestamp": "2026-02-25T..."
            },
            ...
        ],
        "total_gaps": 1,
        "accounts_with_gaps": ["acct-123"],
        "checked_at": "2026-02-25T..."
    }

    If no gaps:
    {
        "has_gaps": false,
        "gaps": [],
        "total_gaps": 0,
        "accounts_with_gaps": [],
        "checked_at": "2026-02-25T..."
    }
    """
    validator = ChronologicalIntegrityValidator(db)

    try:
        gaps = validator.detect_gaps(
            account_id=account_id,
            start_time=start_time,
            end_time=end_time
        )
        return gaps
    except Exception as e:
        logger.error(f"Gap detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gap detection failed: {str(e)}")
