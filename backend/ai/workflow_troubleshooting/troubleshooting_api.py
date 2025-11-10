import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from .troubleshooting_engine import (
    IssueCategory,
    IssueSeverity,
    TroubleshootingSession,
    WorkflowIssue,
    WorkflowTroubleshootingEngine,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the troubleshooting engine
troubleshooting_engine = WorkflowTroubleshootingEngine()

# Create API router
router = APIRouter(
    prefix="/api/workflow-troubleshooting", tags=["workflow-troubleshooting"]
)


# Request/Response Models
class StartTroubleshootingRequest(BaseModel):
    workflow_id: str
    error_logs: List[str]
    additional_context: Optional[Dict[str, Any]] = None


class TroubleshootingSessionResponse(BaseModel):
    session_id: str
    workflow_id: str
    issues_found: int
    current_step: str
    resolution_status: str
    start_time: str
    recommendations_count: int


class WorkflowIssueResponse(BaseModel):
    issue_id: str
    workflow_id: str
    category: str
    severity: str
    description: str
    symptoms: List[str]
    root_cause: Optional[str]
    detection_time: str
    affected_components: List[str]
    metrics_impact: Dict[str, Any]


class MetricsAnalysisRequest(BaseModel):
    session_id: str
    metrics: Dict[str, Any]


class VerificationRequest(BaseModel):
    session_id: str
    test_results: Dict[str, bool]


class HealthScoreResponse(BaseModel):
    workflow_id: str
    health_score: float
    status: str
    reason: str
    last_updated: str


class TroubleshootingSummaryResponse(BaseModel):
    session_id: str
    workflow_id: str
    start_time: str
    end_time: Optional[str]
    duration_seconds: Optional[float]
    issues_found: int
    issues_by_severity: Dict[str, int]
    issues_by_category: Dict[str, int]
    steps_completed: List[str]
    current_step: str
    resolution_status: str
    recommendations_count: int


# API Endpoints
@router.post("/sessions", response_model=TroubleshootingSessionResponse)
async def start_troubleshooting_session(request: StartTroubleshootingRequest):
    """
    Start a new troubleshooting session for a workflow
    """
    try:
        session = troubleshooting_engine.start_troubleshooting_session(
            workflow_id=request.workflow_id, error_logs=request.error_logs
        )

        return TroubleshootingSessionResponse(
            session_id=session.session_id,
            workflow_id=session.workflow_id,
            issues_found=len(session.issues),
            current_step=session.current_step.value,
            resolution_status=session.resolution_status,
            start_time=session.start_time.isoformat(),
            recommendations_count=len(session.recommendations),
        )
    except Exception as e:
        logger.error(f"Failed to start troubleshooting session: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start troubleshooting session: {str(e)}"
        )


@router.get("/sessions/{session_id}/issues", response_model=List[WorkflowIssueResponse])
async def get_session_issues(session_id: str):
    """
    Get all issues identified in a troubleshooting session
    """
    try:
        session = troubleshooting_engine.sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

        issues_response = []
        for issue in session.issues:
            issues_response.append(
                WorkflowIssueResponse(
                    issue_id=issue.issue_id,
                    workflow_id=issue.workflow_id,
                    category=issue.category.value,
                    severity=issue.severity.value,
                    description=issue.description,
                    symptoms=issue.symptoms,
                    root_cause=issue.root_cause,
                    detection_time=issue.detection_time.isoformat(),
                    affected_components=issue.affected_components,
                    metrics_impact=issue.metrics_impact,
                )
            )

        return issues_response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session issues: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get session issues: {str(e)}"
        )


@router.post("/sessions/{session_id}/analyze-metrics")
async def analyze_workflow_metrics(session_id: str, request: MetricsAnalysisRequest):
    """
    Analyze workflow metrics to identify performance and operational issues
    """
    try:
        issues = await troubleshooting_engine.analyze_workflow_metrics(
            session_id=session_id, metrics=request.metrics
        )

        issues_response = []
        for issue in issues:
            issues_response.append(
                WorkflowIssueResponse(
                    issue_id=issue.issue_id,
                    workflow_id=issue.workflow_id,
                    category=issue.category.value,
                    severity=issue.severity.value,
                    description=issue.description,
                    symptoms=issue.symptoms,
                    root_cause=issue.root_cause,
                    detection_time=issue.detection_time.isoformat(),
                    affected_components=issue.affected_components,
                    metrics_impact=issue.metrics_impact,
                )
            )

        return {
            "session_id": session_id,
            "issues_found": len(issues),
            "issues": issues_response,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to analyze workflow metrics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze workflow metrics: {str(e)}"
        )


@router.post("/sessions/{session_id}/diagnose")
async def diagnose_root_causes(session_id: str):
    """
    Diagnose root causes for identified issues in a session
    """
    try:
        root_causes = troubleshooting_engine.diagnose_root_causes(session_id)

        session = troubleshooting_engine.sessions.get(session_id)
        return {
            "session_id": session_id,
            "root_causes": root_causes,
            "current_step": session.current_step.value if session else "unknown",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to diagnose root causes: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to diagnose root causes: {str(e)}"
        )


@router.post("/sessions/{session_id}/recommendations")
async def generate_recommendations(session_id: str):
    """
    Generate resolution recommendations for identified issues
    """
    try:
        recommendations = troubleshooting_engine.generate_recommendations(session_id)

        session = troubleshooting_engine.sessions.get(session_id)
        return {
            "session_id": session_id,
            "recommendations": recommendations,
            "current_step": session.current_step.value if session else "unknown",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate recommendations: {str(e)}"
        )


@router.post("/sessions/{session_id}/verify")
async def verify_resolution(session_id: str, request: VerificationRequest):
    """
    Verify that issues have been resolved
    """
    try:
        verification_results = troubleshooting_engine.verify_resolution(
            session_id=session_id, test_results=request.test_results
        )

        return verification_results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to verify resolution: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to verify resolution: {str(e)}"
        )


@router.get(
    "/sessions/{session_id}/summary", response_model=TroubleshootingSummaryResponse
)
async def get_session_summary(session_id: str):
    """
    Get comprehensive summary of a troubleshooting session
    """
    try:
        summary = troubleshooting_engine.get_session_summary(session_id)
        return TroubleshootingSummaryResponse(**summary)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get session summary: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get session summary: {str(e)}"
        )


@router.get("/workflows/{workflow_id}/health", response_model=HealthScoreResponse)
async def get_workflow_health_score(workflow_id: str):
    """
    Get health score for a workflow based on historical metrics
    """
    try:
        health_data = troubleshooting_engine.get_workflow_health_score(workflow_id)
        return HealthScoreResponse(
            workflow_id=workflow_id,
            health_score=health_data["health_score"],
            status=health_data["status"],
            reason=health_data["reason"],
            last_updated=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to get workflow health score: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get workflow health score: {str(e)}"
        )


@router.get("/sessions")
async def list_active_sessions():
    """
    List all active troubleshooting sessions
    """
    try:
        active_sessions = []
        for session_id, session in troubleshooting_engine.sessions.items():
            if session.resolution_status in ["in_progress", "partial"]:
                active_sessions.append(
                    {
                        "session_id": session_id,
                        "workflow_id": session.workflow_id,
                        "start_time": session.start_time.isoformat(),
                        "current_step": session.current_step.value,
                        "issues_found": len(session.issues),
                        "resolution_status": session.resolution_status,
                    }
                )

        return {
            "active_sessions": active_sessions,
            "total_active": len(active_sessions),
        }
    except Exception as e:
        logger.error(f"Failed to list active sessions: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list active sessions: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def close_session(session_id: str):
    """
    Close a troubleshooting session
    """
    try:
        if session_id in troubleshooting_engine.sessions:
            session = troubleshooting_engine.sessions[session_id]
            session.end_time = datetime.now()
            session.resolution_status = "closed"

            return {
                "session_id": session_id,
                "status": "closed",
                "closed_at": session.end_time.isoformat(),
            }
        else:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close session: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to close session: {str(e)}"
        )


# Background task for automated troubleshooting
async def run_automated_troubleshooting(workflow_id: str, error_logs: List[str]):
    """
    Run automated troubleshooting in the background
    """
    try:
        logger.info(f"Starting automated troubleshooting for workflow {workflow_id}")

        # Start troubleshooting session
        session = troubleshooting_engine.start_troubleshooting_session(
            workflow_id=workflow_id, error_logs=error_logs
        )

        # Perform analysis steps
        await troubleshooting_engine.analyze_workflow_metrics(session.session_id, {})
        troubleshooting_engine.diagnose_root_causes(session.session_id)
        troubleshooting_engine.generate_recommendations(session.session_id)

        logger.info(
            f"Automated troubleshooting completed for session {session.session_id}"
        )

    except Exception as e:
        logger.error(
            f"Automated troubleshooting failed for workflow {workflow_id}: {e}"
        )


@router.post("/automated-troubleshooting")
async def trigger_automated_troubleshooting(
    request: StartTroubleshootingRequest, background_tasks: BackgroundTasks
):
    """
    Trigger automated troubleshooting in the background
    """
    try:
        background_tasks.add_task(
            run_automated_troubleshooting, request.workflow_id, request.error_logs
        )

        return {
            "message": "Automated troubleshooting started",
            "workflow_id": request.workflow_id,
            "status": "processing",
        }
    except Exception as e:
        logger.error(f"Failed to trigger automated troubleshooting: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger automated troubleshooting: {str(e)}",
        )
