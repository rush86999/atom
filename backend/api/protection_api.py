
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.risk_prevention import get_risk_services

logger = logging.getLogger(__name__)

router = BaseAPIRouter()

class ScanRequest(BaseModel):
    skill_name: str
    instruction_body: str
    file_contents: Optional[Dict[str, str]] = None

@router.get("/churn")
async def get_churn_risk(
    db: Session = Depends(get_db)
):
    """Predict customer churn risks"""
    try:
        services = get_risk_services(db)
        data = await services["churn"].predict_churn_risk("default")
        return router.success_response(
            data=data,
            message="Churn risk data retrieved successfully"
        )
    except Exception as e:
        raise router.internal_error(
            message="Failed to predict churn risk",
            details={"error": str(e)}
        )

@router.get("/financial")
async def get_financial_risk(
    db: Session = Depends(get_db)
):
    """Get AR delays and Fraud alerts"""
    try:
        services = get_risk_services(db)
        ar_risks = await services["warning"].detect_ar_delays("default")
        booking_drops = await services["warning"].monitor_booking_drops("default")
        fraud_alerts = await services["fraud"].detect_anomalies("default")

        return router.success_response(
            data={
                "ar_delays": ar_risks,
                "booking_anomaly": booking_drops,
                "fraud_alerts": fraud_alerts
            },
            message="Financial risk data retrieved successfully"
        )
    except Exception as e:
        raise router.internal_error(
            message="Failed to get financial risk data",
            details={"error": str(e)}
        )

@router.get("/growth")
async def get_growth_readiness(
    db: Session = Depends(get_db)
):
    """Check scaling readiness"""
    try:
        services = get_risk_services(db)
        readiness = await services["growth"].check_scaling_readiness("default")
        return router.success_response(
            data=readiness,
            message="Growth readiness data retrieved successfully"
        )
    except Exception as e:
        raise router.internal_error(
            message="Failed to check growth readiness",
            details={"error": str(e)}
        )

@router.post("/scan")
async def perform_security_scan(request: ScanRequest):
    """
    Perform a multi-layer security scan on a skill.
    Combines static analysis and semantic LLM analysis.
    """
    try:
        from atom_security.analyzers.llm import LLMAnalyzer
        from atom_security.analyzers.static import StaticAnalyzer

        # 1. Static Scan
        static_analyzer = StaticAnalyzer()
        # Combine instructions and files for comprehensive static scanning
        combined_content = f"{request.instruction_body}\n" + "\n".join((request.file_contents or {}).values())
        static_findings = static_analyzer.scan_content(combined_content)

        # 2. Semantic LLM Scan
        llm_findings = []
        # Check if enabled via env var to prevent unexpected costs or latency
        if os.getenv("ATOM_SECURITY_ENABLE_LLM_SCAN", "false").lower() == "true":
            try:
                # Use local mode by default, can be toggled to 'byok'
                mode = os.getenv("ATOM_SECURITY_LLM_MODE", "local")
                llm_analyzer = LLMAnalyzer(mode=mode)
                llm_findings = await llm_analyzer.analyze(request.skill_name, combined_content)
            except Exception as llm_error:
                logger.error(f"Semantic analysis failed: {llm_error}")

        # Merge all findings
        all_findings = []
        for f in static_findings:
            all_findings.append({
                "category": f.rule_id,
                "severity": f.severity.value,
                "description": f.description,
                "analyzer": "static"
            })

        for f in llm_findings:
            all_findings.append({
                "category": f.rule_id,
                "severity": f.severity.value,
                "description": f.description,
                "analyzer": "llm"
            })

        is_safe = not any(f["severity"] in ["HIGH", "CRITICAL"] for f in all_findings)

        return router.success_response(
            data={
                "findings": all_findings,
                "is_safe": is_safe
            },
            message="Security scan completed successfully"
        )
    except Exception as e:
        logger.error(f"Scan endpoint error: {e}")
        raise router.internal_error(
            message="Security scan failed",
            details={"error": str(e)}
        )
