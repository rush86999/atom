"""
Advanced Bulk Operations Processor
Handles high-volume operations across integrations with performance optimization
"""

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Union

from .integration_data_mapper import BulkOperation, IntegrationDataMapper, get_data_mapper

logger = logging.getLogger(__name__)

class OperationStatus(Enum):
    """Status of bulk operations"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL_SUCCESS = "partial_success"

@dataclass
class BulkJob:
    """Bulk operation job"""
    job_id: str
    operation: BulkOperation
    status: OperationStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_items: int = 0
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    errors: List[Dict[str, Any]] = None
    results: List[Dict[str, Any]] = None
    progress_percentage: float = 0.0
    estimated_completion: Optional[datetime] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.results is None:
            self.results = []
        if self.total_items == 0:
            self.total_items = len(self.operation.items)

class IntegrationBulkProcessor:
    """Advanced bulk operations processor with optimization"""

    def __init__(self, data_mapper: Optional[IntegrationDataMapper] = None):
        self.data_mapper = data_mapper or get_data_mapper()
        self.active_jobs: Dict[str, BulkJob] = {}
        self.job_queue: List[str] = []
        self.max_concurrent_jobs = 5
        self.default_batch_size = 100
        self._job_results_dir = Path("./data/bulk_job_results")
        self._job_results_dir.mkdir(exist_ok=True)

        # Integration-specific processors
        self.integration_processors = {
            "asana": self._process_asana_bulk,
            "jira": self._process_jira_bulk,
            "salesforce": self._process_salesforce_bulk,
            "notion": self._process_notion_bulk,
            "airtable": self._process_airtable_bulk,
            "hubspot": self._process_hubspot_bulk,
            "monday": self._process_monday_bulk
        }

    async def submit_bulk_job(self, operation: BulkOperation) -> str:
        """Submit a bulk operation job for processing"""
        job_id = f"bulk_{int(time.time())}_{len(self.active_jobs)}"

        job = BulkJob(
            job_id=job_id,
            operation=operation,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            total_items=len(operation.items)
        )

        self.active_jobs[job_id] = job
        self.job_queue.append(job_id)

        # Start processing if not already running
        asyncio.create_task(self._process_queue())

        logger.info(f"Submitted bulk job {job_id} with {len(operation.items)} items")
        return job_id

    async def get_job_status(self, job_id: str) -> Optional[BulkJob]:
        """Get status of a bulk job"""
        return self.active_jobs.get(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a bulk job"""
        job = self.active_jobs.get(job_id)
        if not job:
            return False

        if job.status in [OperationStatus.PENDING, OperationStatus.RUNNING]:
            job.status = OperationStatus.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            return True

        return False

    async def _process_queue(self):
        """Process queued bulk jobs"""
        while self.job_queue:
            # Check concurrency limit
            running_jobs = [
                job for job in self.active_jobs.values()
                if job.status == OperationStatus.RUNNING
            ]

            if len(running_jobs) >= self.max_concurrent_jobs:
                await asyncio.sleep(1)
                continue

            # Get next job
            job_id = self.job_queue.pop(0)
            job = self.active_jobs[job_id]

            # Start processing
            asyncio.create_task(self._process_job(job))

    async def _process_job(self, job: BulkJob):
        """Process a single bulk job"""
        try:
            job.status = OperationStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)

            operation = job.operation
            integration_id = operation.integration_id

            # Get integration processor
            processor = self.integration_processors.get(integration_id)
            if not processor:
                raise ValueError(f"No processor found for integration: {integration_id}")

            # Prepare items (apply transformations if needed)
            processed_items = await self._prepare_items(operation)

            # Process in batches
            batch_size = operation.batch_size or self.default_batch_size
            batches = [
                processed_items[i:i + batch_size]
                for i in range(0, len(processed_items), batch_size)
            ]

            logger.info(f"Processing {len(processed_items)} items in {len(batches)} batches")

            # Process batches
            for i, batch in enumerate(batches):
                if job.status == OperationStatus.CANCELLED:
                    break

                batch_start = time.time()
                batch_results = await processor(batch, operation)
                batch_duration = time.time() - batch_start

                # Update job progress
                await self._update_job_progress(job, batch_results, i + 1, len(batches))

                # Calculate estimated completion
                if i > 0:
                    avg_batch_time = batch_duration
                    remaining_batches = len(batches) - (i + 1)
                    estimated_seconds = avg_batch_time * remaining_batches
                    job.estimated_completion = datetime.now(timezone.utc).timestamp() + estimated_seconds

                # Progress callback
                if operation.progress_callback:
                    try:
                        await operation.progress_callback(job)
                    except Exception as e:
                        logger.error(f"Progress callback failed: {e}")

            # Finalize job
            if job.status == OperationStatus.RUNNING:
                if job.failed_items > 0 and job.successful_items > 0:
                    job.status = OperationStatus.PARTIAL_SUCCESS
                elif job.failed_items == 0:
                    job.status = OperationStatus.COMPLETED
                else:
                    job.status = OperationStatus.FAILED

            job.completed_at = datetime.now(timezone.utc)
            job.progress_percentage = 100.0

            # Save job results
            await self._save_job_results(job)

            logger.info(f"Completed bulk job {job_id}: {job.successful_items} success, {job.failed_items} failed")

        except Exception as e:
            logger.error(f"Bulk job {job.job_id} failed: {e}")
            job.status = OperationStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.errors.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "type": "job_error"
            })
            await self._save_job_results(job)

    async def _prepare_items(self, operation: BulkOperation) -> List[Dict[str, Any]]:
        """Prepare items for processing (apply transformations, validation)"""
        items = operation.items.copy()

        # Apply data transformations if mapping specified
        if hasattr(operation, 'mapping_id') and operation.mapping_id:
            try:
                items = self.data_mapper.transform_data(items, operation.mapping_id)
            except Exception as e:
                logger.error(f"Data transformation failed: {e}")

        # Validate items if schema specified
        if hasattr(operation, 'schema_id') and operation.schema_id:
            try:
                validation = self.data_mapper.validate_data(items, operation.schema_id)
                if not validation["valid"]:
                    logger.warning(f"Validation warnings: {validation['warnings']}")
            except Exception as e:
                logger.error(f"Data validation failed: {e}")

        return items

    async def _update_job_progress(
        self,
        job: BulkJob,
        batch_results: List[Dict[str, Any]],
        current_batch: int,
        total_batches: int
    ):
        """Update job progress after batch completion"""
        for result in batch_results:
            job.processed_items += 1
            if result.get("success", False):
                job.successful_items += 1
                job.results.append(result)
            else:
                job.failed_items += 1
                job.errors.append({
                    "item_index": job.processed_items - 1,
                    "error": result.get("error", "Unknown error"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                if operation.stop_on_error:
                    job.status = OperationStatus.FAILED
                    break

        job.progress_percentage = (current_batch / total_batches) * 100

    async def _save_job_results(self, job: BulkJob):
        """Save job results to disk"""
        try:
            results_file = self._job_results_dir / f"{job.job_id}_results.json"

            results_data = {
                "job_id": job.job_id,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "total_items": job.total_items,
                "processed_items": job.processed_items,
                "successful_items": job.successful_items,
                "failed_items": job.failed_items,
                "progress_percentage": job.progress_percentage,
                "results": job.results,
                "errors": job.errors,
                "operation": asdict(job.operation)
            }

            with open(results_file, 'w') as f:
                json.dump(results_data, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to save job results: {e}")

    # Integration-specific processors

    async def _process_asana_bulk(self, items: List[Dict], operation: BulkOperation) -> List[Dict]:
        """
        Process Asana bulk operations using actual Asana API.

        This implementation integrates with the AsanaService to perform
        bulk create, update, delete, and complete operations on Asana tasks.
        """
        import os

        from integrations.asana_service import AsanaService

        results = []

        # Get Asana access token from operation metadata or environment
        access_token = operation.metadata.get("access_token") or os.getenv("ASANA_PAT")

        if not access_token:
            logger.error("Asana access token not found in operation metadata or environment")
            for item in items:
                results.append({
                    "success": False,
                    "item": item,
                    "error": "Asana access token not configured"
                })
            return results

        # Initialize Asana service
        asana_service = AsanaService()

        # Process each item
        for item in items:
            try:
                if operation.operation_type == "create":
                    # Create Asana task
                    task_data = {
                        "name": item.get("name", "Bulk Created Task"),
                        "notes": item.get("notes", ""),
                        "projects": item.get("projects", []),
                        "assignee": item.get("assignee"),
                        "due_on": item.get("due_on")
                    }

                    # Remove None values
                    task_data = {k: v for k, v in task_data.items() if v is not None}

                    result = await asana_service.create_task(access_token, task_data)

                    if result.get("data"):
                        task_gid = result["data"].get("gid")
                        results.append({
                            "success": True,
                            "item": item,
                            "result": {
                                "id": task_gid,
                                "created": True,
                                "data": result["data"]
                            }
                        })
                    else:
                        results.append({
                            "success": False,
                            "item": item,
                            "error": result.get("errors", "Unknown error")
                        })

                elif operation.operation_type == "update":
                    # Update existing task
                    task_gid = item.get("task_id") or item.get("task_gid") or item.get("id")

                    if not task_gid:
                        results.append({
                            "success": False,
                            "item": item,
                            "error": "Missing task_id for update operation"
                        })
                        continue

                    updates = item.get("updates", {})

                    result = await asana_service.update_task(
                        access_token,
                        task_gid,
                        updates
                    )

                    if result.get("data"):
                        results.append({
                            "success": True,
                            "item": item,
                            "result": {
                                "id": task_gid,
                                "updated": True,
                                "data": result["data"]
                            }
                        })
                    else:
                        results.append({
                            "success": False,
                            "item": item,
                            "error": result.get("errors", "Unknown error")
                        })

                elif operation.operation_type == "delete":
                    # Delete task
                    task_gid = item.get("task_id") or item.get("task_gid") or item.get("id")

                    if not task_gid:
                        results.append({
                            "success": False,
                            "item": item,
                            "error": "Missing task_id for delete operation"
                        })
                        continue

                    result = await asana_service.delete_task(access_token, task_gid)

                    if result.get("data"):
                        results.append({
                            "success": True,
                            "item": item,
                            "result": {
                                "id": task_gid,
                                "deleted": True
                            }
                        })
                    else:
                        results.append({
                            "success": False,
                            "item": item,
                            "error": result.get("errors", "Unknown error")
                        })

                elif operation.operation_type == "complete":
                    # Mark task as complete
                    task_gid = item.get("task_id") or item.get("task_gid") or item.get("id")

                    if not task_gid:
                        results.append({
                            "success": False,
                            "item": item,
                            "error": "Missing task_id for complete operation"
                        })
                        continue

                    result = await asana_service.complete_task(
                        access_token,
                        task_gid,
                        completed_at=datetime.now().isoformat()
                    )

                    if result.get("data"):
                        results.append({
                            "success": True,
                            "item": item,
                            "result": {
                                "id": task_gid,
                                "completed": True,
                                "data": result["data"]
                            }
                        })
                    else:
                        results.append({
                            "success": False,
                            "item": item,
                            "error": result.get("errors", "Unknown error")
                        })

                else:
                    results.append({
                        "success": False,
                        "item": item,
                        "error": f"Unsupported operation: {operation.operation_type}"
                    })

                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Failed to process Asana item {item}: {e}")
                results.append({
                    "success": False,
                    "item": item,
                    "error": str(e)
                })

        return results

    async def _process_jira_bulk(self, items: List[Dict], operation: BulkOperation) -> List[Dict]:
        """Process Jira bulk operations"""
        results = []

        for item in items:
            try:
                # Simulate API call
                await asyncio.sleep(0.15)

                if operation.operation_type == "create":
                    # Create Jira issue
                    issue_key = f"ATOM-{int(time.time() % 10000)}"
                    results.append({
                        "success": True,
                        "item": item,
                        "result": {"key": issue_key, "id": f"{int(time.time())}"}
                    })
                elif operation.operation_type == "update":
                    # Update Jira issue
                    results.append({
                        "success": True,
                        "item": item,
                        "result": {"updated": True}
                    })
                else:
                    results.append({
                        "success": False,
                        "item": item,
                        "error": f"Unsupported operation: {operation.operation_type}"
                    })

            except Exception as e:
                results.append({
                    "success": False,
                    "item": item,
                    "error": str(e)
                })

        return results

    async def _process_salesforce_bulk(self, items: List[Dict], operation: BulkOperation) -> List[Dict]:
        """Process Salesforce bulk operations"""
        results = []

        for item in items:
            try:
                # Simulate API call
                await asyncio.sleep(0.2)

                if operation.operation_type == "create":
                    # Create Salesforce record
                    record_id = f"001{int(time.time() * 1000)}"
                    results.append({
                        "success": True,
                        "item": item,
                        "result": {"id": record_id, "success": True}
                    })
                elif operation.operation_type == "update":
                    # Update Salesforce record
                    results.append({
                        "success": True,
                        "item": item,
                        "result": {"success": True}
                    })
                else:
                    results.append({
                        "success": False,
                        "item": item,
                        "error": f"Unsupported operation: {operation.operation_type}"
                    })

            except Exception as e:
                results.append({
                    "success": False,
                    "item": item,
                    "error": str(e)
                })

        return results

    async def _process_notion_bulk(self, items: List[Dict], operation: BulkOperation) -> List[Dict]:
        """Process Notion bulk operations"""
        results = []

        for item in items:
            try:
                # Simulate API call
                await asyncio.sleep(0.1)

                results.append({
                    "success": True,
                    "item": item,
                    "result": {"page_id": f"notion_{int(time.time())}"}
                })

            except Exception as e:
                results.append({
                    "success": False,
                    "item": item,
                    "error": str(e)
                })

        return results

    async def _process_airtable_bulk(self, items: List[Dict], operation: BulkOperation) -> List[Dict]:
        """Process Airtable bulk operations"""
        results = []

        for item in items:
            try:
                # Simulate API call
                await asyncio.sleep(0.05)

                results.append({
                    "success": True,
                    "item": item,
                    "result": {"id": f"rec{int(time.time())}"}
                })

            except Exception as e:
                results.append({
                    "success": False,
                    "item": item,
                    "error": str(e)
                })

        return results

    async def _process_hubspot_bulk(self, items: List[Dict], operation: BulkOperation) -> List[Dict]:
        """Process HubSpot bulk operations"""
        results = []

        for item in items:
            try:
                # Simulate API call
                await asyncio.sleep(0.15)

                results.append({
                    "success": True,
                    "item": item,
                    "result": {"id": f"hubspot_{int(time.time())}"}
                })

            except Exception as e:
                results.append({
                    "success": False,
                    "item": item,
                    "error": str(e)
                })

        return results

    async def _process_monday_bulk(self, items: List[Dict], operation: BulkOperation) -> List[Dict]:
        """Process Monday.com bulk operations"""
        results = []

        for item in items:
            try:
                # Simulate API call
                await asyncio.sleep(0.1)

                results.append({
                    "success": True,
                    "item": item,
                    "result": {"id": f"monday_{int(time.time())}"}
                })

            except Exception as e:
                results.append({
                    "success": False,
                    "item": item,
                    "error": str(e)
                })

        return results

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for bulk operations"""
        completed_jobs = [
            job for job in self.active_jobs.values()
            if job.status in [OperationStatus.COMPLETED, OperationStatus.PARTIAL_SUCCESS, OperationStatus.FAILED]
        ]

        if not completed_jobs:
            return {
                "total_jobs": len(self.active_jobs),
                "running_jobs": len([j for j in self.active_jobs.values() if j.status == OperationStatus.RUNNING]),
                "completed_jobs": 0,
                "average_processing_time": 0,
                "total_items_processed": 0,
                "success_rate": 0
            }

        total_processing_time = sum(
            (job.completed_at - job.started_at).total_seconds()
            for job in completed_jobs
            if job.started_at and job.completed_at
        )

        total_items = sum(job.total_items for job in completed_jobs)
        successful_items = sum(job.successful_items for job in completed_jobs)

        return {
            "total_jobs": len(self.active_jobs),
            "running_jobs": len([j for j in self.active_jobs.values() if j.status == OperationStatus.RUNNING]),
            "completed_jobs": len(completed_jobs),
            "average_processing_time": total_processing_time / len(completed_jobs),
            "total_items_processed": total_items,
            "success_rate": (successful_items / total_items * 100) if total_items > 0 else 0,
            "queue_length": len(self.job_queue)
        }

# Global bulk processor instance
_bulk_processor = None

def get_bulk_processor() -> IntegrationBulkProcessor:
    """Get the global bulk processor instance"""
    global _bulk_processor
    if _bulk_processor is None:
        _bulk_processor = IntegrationBulkProcessor()
    return _bulk_processor