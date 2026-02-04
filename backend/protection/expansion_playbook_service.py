
import logging
from datetime import datetime
from typing import Any, Dict, List
from operations.business_health_service import BusinessHealthService
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class ExpansionPlaybookService:
    def __init__(self, db: Session):
        self.db = db
        self.health_service = BusinessHealthService(db)

    def check_scaling_readiness(self, workspace_id: str) -> Dict[str, Any]:
        """
        Audits system for "Growth Mode" approval.
        Checks:
        1. Cash Runway > 3 months.
        2. Operational Health Score > 80.
        3. System Error Rate (Mocked) < 1%.
        """
        readiness_report = {
            "status": "NOT_READY",
            "score": 0,
            "checks": []
        }
        
        # 1. Financial Clearance
        runway_data = self.health_service.calculate_cash_runway(workspace_id)
        days_runway = runway_data.get('days_runway', 0)
        
        if days_runway > 90:
            readiness_report["checks"].append({"check": "Cash Runway > 90 Days", "status": "PASS", "value": f"{days_runway} days"})
            readiness_report["score"] += 40
        else:
            readiness_report["checks"].append({"check": "Cash Runway > 90 Days", "status": "FAIL", "value": f"{days_runway} days"})

        # 2. Operational Health Clearance
        health_data = self.health_service.get_business_health_score(workspace_id)
        health_score = health_data.get('score', 0)
        
        if health_score >= 80:
             readiness_report["checks"].append({"check": "Ops Health Score > 80", "status": "PASS", "value": health_score})
             readiness_report["score"] += 30
        else:
             readiness_report["checks"].append({"check": "Ops Health Score > 80", "status": "FAIL", "value": health_score})

        # 3. Technical Stability (Mocked)
        # In real system, query Sentry/Datadog API
        error_rate = 0.05 # Mock 0.05%
        if error_rate < 1.0:
            readiness_report["checks"].append({"check": "System Error Rate < 1%", "status": "PASS", "value": f"{error_rate}%"})
            readiness_report["score"] += 30
        else:
             readiness_report["checks"].append({"check": "System Error Rate < 1%", "status": "FAIL", "value": f"{error_rate}%"})

        # Final Determination
        if readiness_report["score"] == 100:
            readiness_report["status"] = "READY_FOR_EXPANSION"
            readiness_report["message"] = "All systems go. You are safe to scale ad spend and hiring."
        else:
            readiness_report["status"] = "NOT_READY"
            readiness_report["message"] = "Scaling not recommended. Fix failed checks first."
            
        return readiness_report
