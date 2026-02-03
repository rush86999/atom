#!/usr/bin/env python3
"""
Evidence Collection API Endpoints
Provides systematic evidence collection for marketing claim validation
"""

import asyncio
import logging
from typing import Any, Dict
from evidence_collection_framework import evidence_framework
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create router for evidence collection endpoints
router = APIRouter(prefix="/api/v1/evidence", tags=["evidence_collection"])

class ValidationReportResponse(BaseModel):
    """Response model for validation report"""
    validation_framework: str
    generated_at: str
    validation_methodology: str
    claims_validated: Dict[str, Any]
    overall_assessment: Dict[str, Any]

class EvidenceSummaryResponse(BaseModel):
    """Response model for evidence summary"""
    claim_id: str
    validation_score: float
    confidence_level: str
    evidence_summary: Dict[str, Any]
    meets_target: bool

@router.get("/validation-report", response_model=ValidationReportResponse)
async def get_validation_report():
    """Generate comprehensive validation report for independent AI validators"""

    try:
        report = await evidence_framework.generate_validation_report()
        return ValidationReportResponse(**report)
    except Exception as e:
        logger.error(f"Failed to generate validation report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ai-workflows-evidence", response_model=EvidenceSummaryResponse)
async def get_ai_workflows_evidence():
    """Get evidence summary for AI workflows claim"""

    try:
        evidence = await evidence_framework.collect_ai_workflow_evidence()
        summary = evidence_framework._create_evidence_summary(evidence)

        return EvidenceSummaryResponse(
            claim_id=evidence.claim_id,
            validation_score=evidence.validation_score,
            confidence_level=evidence.confidence_level,
            evidence_summary=summary,
            meets_target=evidence.validation_score >= 92.0
        )
    except Exception as e:
        logger.error(f"Failed to collect AI workflows evidence: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-evidence-report")
async def generate_evidence_report(background_tasks: BackgroundTasks):
    """Generate and save evidence report to file"""

    try:
        report = await evidence_framework.generate_validation_report()

        # Save report to file
        timestamp = report["generated_at"].replace(":", "-").replace(".", "-")
        filename = f"evidence_validation_report_{timestamp}.json"

        import json
        with open(filename, "w") as f:
            json.dump(report, f, indent=2, default=str)

        return {
            "message": "Evidence validation report generated successfully",
            "filename": filename,
            "overall_score": report["overall_assessment"]["average_score"],
            "claims_meeting_target": report["overall_assessment"]["claims_meeting_target"],
            "total_claims": report["overall_assessment"]["total_claims"]
        }
    except Exception as e:
        logger.error(f"Failed to generate evidence report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/independent-validator-prep")
async def prepare_independent_validator_evidence():
    """Prepare evidence specifically formatted for independent AI validator"""

    try:
        # Get comprehensive evidence
        evidence = await evidence_framework.collect_ai_workflow_evidence()

        # Format for independent AI validator requirements
        independent_validator_evidence = {
            "marketing_claim": "AI-Powered Workflow Automation: Automate complex workflows with intelligent AI assistance",
            "evidence_packages": [],
            "validation_metrics": {
                "complex_workflow_automation": False,
                "ai_driven_decision_making": False,
                "multi_step_processing": False,
                "natural_language_understanding": False,
                "cross_service_integration": False,
                "enterprise_readiness": False
            },
            "performance_metrics": {},
            "independent_ai_requirements": {
                "real_ai_processing": False,
                "complex_workflow_evidence": False,
                "measurable_business_impact": False,
                "enterprise_features": False
            }
        }

        # Process evidence items
        for item in evidence.evidence_items:
            evidence_package = {
                "evidence_type": item.evidence_type,
                "description": item.description,
                "strength": item.strength,
                "verification_method": item.verification_method,
                "source": item.source,
                "data": item.value
            }
            independent_validator_evidence["evidence_packages"].append(evidence_package)

            # Update validation metrics based on evidence
            if isinstance(item.value, dict):
                if item.evidence_type == "live_workflow_execution":
                    independent_validator_evidence["validation_metrics"]["complex_workflow_automation"] = item.value.get("workflow_execution_successful", False)
                    independent_validator_evidence["validation_metrics"]["multi_step_processing"] = item.value.get("steps_executed", 0) > 5
                    independent_validator_evidence["performance_metrics"]["execution_time_ms"] = item.value.get("execution_time_ms", 0)
                    independent_validator_evidence["performance_metrics"]["steps_executed"] = item.value.get("steps_executed", 0)

                elif item.evidence_type == "nlu_processing_capabilities":
                    independent_validator_evidence["validation_metrics"]["natural_language_understanding"] = item.value.get("nlu_processing_successful", False)
                    independent_validator_evidence["independent_ai_requirements"]["real_ai_processing"] = item.value.get("real_ai_processing", False)

                elif item.evidence_type == "real_ai_provider_integration":
                    independent_validator_evidence["validation_metrics"]["ai_driven_decision_making"] = item.value.get("providers_configured", 0) >= 3

                elif item.evidence_type == "cross_service_integration":
                    independent_validator_evidence["validation_metrics"]["cross_service_integration"] = item.value.get("cross_service_integration_ready", False)

                elif item.evidence_type == "complex_workflow_definitions":
                    independent_validator_evidence["independent_ai_requirements"]["complex_workflow_evidence"] = item.value.get("total_workflows", 0) >= 3
                    independent_validator_evidence["validation_metrics"]["enterprise_readiness"] = item.value.get("total_workflows", 0) >= 3

        # Calculate final scores
        validation_metrics = independent_validator_evidence["validation_metrics"]
        independent_ai_requirements = independent_validator_evidence["independent_ai_requirements"]

        validation_score = sum(validation_metrics.values()) / len(validation_metrics) * 100
        requirements_score = sum(independent_ai_requirements.values()) / len(independent_ai_requirements) * 100

        independent_validator_evidence["validation_scores"] = {
            "functionality_score": validation_score,
            "requirements_score": requirements_score,
            "overall_score": (validation_score + requirements_score) / 2,
            "evidence_framework_score": evidence.validation_score
        }

        return independent_validator_evidence

    except Exception as e:
        logger.error(f"Failed to prepare independent validator evidence: {e}")
        raise HTTPException(status_code=500, detail=str(e))