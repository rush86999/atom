"""
A/B Testing API Endpoints

REST API for creating and managing A/B tests for agent configuration,
prompt, strategy, and tool comparisons.

Endpoints:
- POST /api/ab-tests/create - Create new A/B test
- POST /api/ab-tests/{test_id}/start - Start a test
- POST /api/ab-tests/{test_id}/complete - Complete a test and get results
- POST /api/ab-tests/{test_id}/assign - Assign user to variant
- POST /api/ab-tests/{test_id}/record - Record metric for participant
- GET /api/ab-tests/{test_id}/results - Get test results
- GET /api/ab-tests - List all tests
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.ab_testing_service import ABTestingService

logger = logging.getLogger(__name__)

router = APIRouter()


# ========================================================================
# Request/Response Models
# ========================================================================

class CreateTestRequest(BaseModel):
    """Request to create a new A/B test."""
    name: str = Field(..., description="Test name")
    test_type: str = Field(..., description="Type of test (agent_config, prompt, strategy, tool)")
    agent_id: str = Field(..., description="ID of agent to test")
    variant_a_config: Dict[str, Any] = Field(..., description="Configuration for control variant")
    variant_b_config: Dict[str, Any] = Field(..., description="Configuration for treatment variant")
    primary_metric: str = Field(..., description="Primary success metric")
    variant_a_name: str = Field(default="Control", description="Name for variant A")
    variant_b_name: str = Field(default="Treatment", description="Name for variant B")
    description: Optional[str] = Field(None, description="Test description")
    traffic_percentage: float = Field(default=0.5, ge=0.0, le=1.0, description="Traffic to variant B")
    min_sample_size: int = Field(default=100, ge=1, description="Min sample size per variant")
    confidence_level: float = Field(default=0.95, ge=0.0, le=1.0, description="Confidence level")
    secondary_metrics: Optional[List[str]] = Field(default=None, description="Additional metrics")


class AssignVariantRequest(BaseModel):
    """Request to assign user to variant."""
    user_id: str = Field(..., description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")


class RecordMetricRequest(BaseModel):
    """Request to record metric for participant."""
    user_id: str = Field(..., description="User ID")
    success: Optional[bool] = Field(None, description="Boolean success indicator")
    metric_value: Optional[float] = Field(None, description="Numerical metric value")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


# ========================================================================
# Test Management Endpoints
# ========================================================================

@router.post("/create")
async def create_test(
    request: CreateTestRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new A/B test.

    Tests different agent configurations, prompts, or strategies
    to measure impact on key metrics.

    Request Body:
        - name: Test name
        - test_type: Type (agent_config, prompt, strategy, tool)
        - agent_id: Agent to test
        - variant_a_config: Control configuration
        - variant_b_config: Treatment configuration
        - primary_metric: Success metric (satisfaction_rate, success_rate, response_time)
        - traffic_percentage: Fraction to variant B (default: 0.5)
        - min_sample_size: Min sample size per variant (default: 100)
        - confidence_level: Statistical confidence (default: 0.95)

    Response:
        Created test data with test_id
    """
    service = ABTestingService(db)
    result = service.create_test(
        name=request.name,
        test_type=request.test_type,
        agent_id=request.agent_id,
        variant_a_config=request.variant_a_config,
        variant_b_config=request.variant_b_config,
        primary_metric=request.primary_metric,
        variant_a_name=request.variant_a_name,
        variant_b_name=request.variant_b_name,
        description=request.description,
        traffic_percentage=request.traffic_percentage,
        min_sample_size=request.min_sample_size,
        confidence_level=request.confidence_level,
        secondary_metrics=request.secondary_metrics
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{test_id}/start")
async def start_test(
    test_id: str,
    db: Session = Depends(get_db)
):
    """
    Start an A/B test.

    Changes test status from 'draft' to 'running' and
    begins variant assignment.

    Response:
        Updated test data with started_at timestamp
    """
    service = ABTestingService(db)
    result = service.start_test(test_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{test_id}/complete")
async def complete_test(
    test_id: str,
    db: Session = Depends(get_db)
):
    """
    Complete an A/B test and calculate results.

    Performs statistical analysis to determine if there's
    a significant difference between variants.

    Response:
        Test results including:
        - variant_a_metrics: Metrics for control
        - variant_b_metrics: Metrics for treatment
        - p_value: Statistical significance
        - winner: 'A', 'B', or 'inconclusive'
    """
    service = ABTestingService(db)
    result = service.complete_test(test_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ========================================================================
# Variant Assignment Endpoints
# ========================================================================

@router.post("/{test_id}/assign")
async def assign_variant(
    test_id: str,
    request: AssignVariantRequest,
    db: Session = Depends(get_db)
):
    """
    Assign a user to a test variant.

    Uses deterministic hash-based assignment to ensure
    consistent assignment for the same user.

    Request Body:
        - user_id: User ID
        - session_id: Optional session ID

    Response:
        Assignment data with:
        - variant: 'A' or 'B'
        - variant_name: Human-readable variant name
        - config: Variant configuration
        - existing_assignment: Boolean
    """
    service = ABTestingService(db)
    result = service.assign_variant(
        test_id=test_id,
        user_id=request.user_id,
        session_id=request.session_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{test_id}/record")
async def record_metric(
    test_id: str,
    request: RecordMetricRequest,
    db: Session = Depends(get_db)
):
    """
    Record a metric for a test participant.

    Tracks outcome data for statistical analysis.

    Request Body:
        - user_id: User ID
        - success: Boolean success (optional)
        - metric_value: Numerical value (optional)
        - metadata: Additional data (optional)

    Response:
        Recorded metric data
    """
    service = ABTestingService(db)
    result = service.record_metric(
        test_id=test_id,
        user_id=request.user_id,
        success=request.success,
        metric_value=request.metric_value,
        metadata=request.metadata
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ========================================================================
# Results and Analytics Endpoints
# ========================================================================

@router.get("/{test_id}/results")
async def get_test_results(
    test_id: str,
    db: Session = Depends(get_db)
):
    """
    Get current results for an A/B test.

    Returns participant counts and metrics for both variants.

    Response:
        Test results with:
        - variant_a: Control variant data
        - variant_b: Treatment variant data
        - winner: Test winner (if completed)
        - statistical_significance: p-value
    """
    service = ABTestingService(db)
    result = service.get_test_results(test_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("")
async def list_tests(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    List A/B tests with optional filtering.

    Query Parameters:
        - agent_id: Optional agent filter
        - status: Optional status filter (draft, running, paused, completed)
        - limit: Maximum results (default: 50)

    Response:
        List of tests with summary data
    """
    service = ABTestingService(db)
    return service.list_tests(
        agent_id=agent_id,
        status=status,
        limit=limit
    )
