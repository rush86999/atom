"""
Memory Backfill Routes - Generic backfill endpoints for ALL integrations

Provides REST API endpoints for triggering backfill and checking status:
- POST /api/integrations/{integration_id}/backfill
- GET /api/integrations/{integration_id}/backfill/status/{job_id}
- POST /api/integrations/backfill/all
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.memory_integration_mixin import MemoryIntegrationMixin, IntegrationBackfillManager

logger = logging.getLogger(__name__)


def parse_iso_datetime(date_str: str) -> datetime:
    """
    Parse ISO datetime string with timezone validation.

    Args:
        date_str: ISO 8601 datetime string

    Returns:
        Timezone-aware datetime in UTC

    Raises:
        ValueError: If date format is invalid
    """
    try:
        # Parse ISO format datetime
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

        # Ensure timezone-aware
        if dt.tzinfo is None:
            # Assume UTC if no timezone specified
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC for consistency
            dt = dt.astimezone(timezone.utc)

        return dt
    except ValueError as e:
        raise ValueError(f"Invalid datetime format: {date_str}. Expected ISO 8601 format.") from e

router = BaseAPIRouter(prefix="/api/integrations", tags=["Integrations Memory"])

# Pydantic Models
class BackfillRequest(BaseModel):
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")
    limit: int = Field(500, description="Maximum records to fetch", ge=1, le=10000)


class BackfillAllRequest(BaseModel):
    integration_ids: List[str] = Field(
        default=[],
        description="List of integration IDs to backfill (empty = all)"
    )
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")
    limit_per_integration: int = Field(
        500,
        description="Maximum records per integration",
        ge=1,
        le=10000
    )


# Generic backfill endpoint for any integration
@router.post("/{integration_id}/backfill")
async def trigger_backfill(
    integration_id: str,
    request: BackfillRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger backfill for a specific integration.

    Fetches records from integration API, extracts entities,
    generates embeddings, and stores in LanceDB.

    **Integrations supported:**
    - outlook, gmail, slack
    - salesforce, hubspot, zoho
    - jira, asana, notion
    - zendesk, and more...

    **Response:**
    ```json
    {
        "success": true,
        "job_id": "uuid",
        "integration_id": "outlook",
        "status": "started"
    }
    ```
    """
    try:
        # Parse dates with timezone validation
        start_date = None
        end_date = None

        if request.start_date:
            start_date = parse_iso_datetime(request.start_date)
        if request.end_date:
            end_date = parse_iso_datetime(request.end_date)

        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before end_date"
            )

        # Trigger backfill
        result = await IntegrationBackfillManager.trigger_backfill(
            integration_id=integration_id,
            start_date=start_date,
            end_date=end_date,
            limit=request.limit
        )

        return router.success_response(
            data=result,
            message=f"Backfill {'started' if result.get('success') else 'failed'} for {integration_id}"
        )

    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to trigger backfill for {integration_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{integration_id}/backfill/status/{job_id}")
async def get_backfill_status(
    integration_id: str,
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get status of a backfill job.

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "job_id": "uuid",
            "integration_id": "outlook",
            "status": "running",
            "progress": 45,
            "total_records": 500,
            "processed_records": 225,
            "failed_records": 2
        }
    }
    ```
    """
    try:
        status = MemoryIntegrationMixin.get_job_status(job_id)

        if not status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return router.success_response(
            data=status,
            message=f"Status for job {job_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backfill/all")
async def trigger_all_backfills(
    request: BackfillAllRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger backfill for ALL integrations (or specified list).

    **Request Body:**
    ```json
    {
        "integration_ids": ["outlook", "gmail", "slack"],
        "start_date": "2026-03-27T00:00:00Z",
        "end_date": "2026-04-26T23:59:59Z",
        "limit_per_integration": 500
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "total_triggered": 3,
        "job_ids": ["uuid1", "uuid2", "uuid3"],
        "errors": []
    }
    ```
    """
    try:
        # Parse dates with timezone validation
        start_date = None
        end_date = None

        if request.start_date:
            start_date = parse_iso_datetime(request.start_date)
        if request.end_date:
            end_date = parse_iso_datetime(request.end_date)

        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before end_date"
            )

        # If integration_ids specified, trigger only those
        if request.integration_ids:
            job_ids = []
            errors = []

            for integration_id in request.integration_ids:
                try:
                    result = await IntegrationBackfillManager.trigger_backfill(
                        integration_id, start_date, end_date, request.limit_per_integration
                    )
                    if result.get("success"):
                        job_ids.append(result["job_id"])
                    else:
                        errors.append(f"{integration_id}: {result.get('error')}")

                except Exception as e:
                    errors.append(f"{integration_id}: {str(e)}")

            result = {
                "success": len(job_ids) > 0,
                "total_triggered": len(job_ids),
                "job_ids": job_ids,
                "errors": errors,
                "message": f"Triggered {len(job_ids)} backfills, {len(errors)} failed"
            }
        else:
            # Trigger all supported integrations
            result = await IntegrationBackfillManager.trigger_all_backfills(
                start_date=start_date,
                end_date=end_date,
                limit_per_integration=request.limit_per_integration
            )

        return router.success_response(
            data=result,
            message=result.get("message", "Backfill triggered")
        )

    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to trigger all backfills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backfill/active")
async def list_active_backfills(db: Session = Depends(get_db)):
    """
    List all active (running/pending) backfill jobs.

    **Response:**
    ```json
    {
        "success": true,
        "data": [
            {
                "job_id": "uuid",
                "integration_id": "outlook",
                "status": "running",
                "progress": 45
            }
        ]
    }
    """
    try:
        from core.memory_integration_mixin import _backfill_jobs

        active_jobs = [
            job.to_dict()
            for job in _backfill_jobs.values()
            if job.status in ["pending", "running"]
        ]

        return router.success_response(
            data=active_jobs,
            message=f"Found {len(active_jobs)} active jobs"
        )

    except Exception as e:
        logger.error(f"Failed to list active jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
