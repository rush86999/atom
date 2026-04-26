"""
Memory Integration Mixin - Generic backfill framework for ALL integrations

Provides a reusable base class that adds memory integration capabilities
to any integration with minimal code changes (1 line to inherit).

Usage:
    class OutlookIntegration(MemoryIntegrationMixin):
        def __init__(self):
            super().__init__(integration_id="outlook")

        async def fetch_records(self, start_date, end_date):
            # Existing fetch logic
            return emails
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod

from core.embedding_service import EmbeddingService, EmbeddingProvider
from core.integration_entity_extractor import IntegrationEntityExtractor
from core.database import SessionLocal
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class BackfillJob:
    """Tracks backfill job progress"""

    def __init__(self, job_id: str, integration_id: str):
        self.job_id = job_id
        self.integration_id = integration_id
        self.status = "pending"  # pending, running, completed, failed
        self.progress = 0  # 0-100
        self.total_records = 0
        self.processed_records = 0
        self.failed_records = 0
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.task = None  # asyncio.Task reference for error handling

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "integration_id": self.integration_id,
            "status": self.status,
            "progress": self.progress,
            "total_records": self.total_records,
            "processed_records": self.processed_records,
            "failed_records": self.failed_records,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error
        }


# Global job registry (in-memory, use Redis in production)
_backfill_jobs: Dict[str, BackfillJob] = {}


class MemoryIntegrationMixin(ABC):
    """
    Generic mixin that adds memory integration capabilities to any integration.

    Provides:
    - Generic backfill_to_memory() method
    - Automatic entity extraction
    - Embedding generation
    - LanceDB storage
    - Progress tracking

    Integrations must implement:
    - fetch_records(): Fetch data from integration API
    - get_integration_type(): Return integration category
    """

    def __init__(self, integration_id: str, workspace_id: str = "default"):
        self.integration_id = integration_id
        self.workspace_id = workspace_id

        # Initialize services
        self.embedding_service = EmbeddingService()
        self.entity_extractor = IntegrationEntityExtractor()

        # Initialize LanceDB handler
        try:
            from core.lancedb_handler import get_lancedb_handler
            self.lancedb = get_lancedb_handler(workspace_id)
        except ImportError:
            self.lancedb = None
            logger.warning(f"LanceDB handler not available for {integration_id}")

        # Check for OpenAI key
        import os
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.use_llm_extraction = bool(self.openai_key)

    @abstractmethod
    async def fetch_records(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Fetch records from integration API.

        Must be implemented by each integration.

        Args:
            start_date: Fetch records from this date (default: 30 days ago)
            end_date: Fetch records until this date (default: now)
            limit: Maximum number of records to fetch

        Returns:
            List of records (integration-specific format)
        """
        pass

    def get_integration_type(self) -> str:
        """
        Return integration category for entity extraction.

        Categories:
        - email: Outlook, Gmail
        - crm: Salesforce, HubSpot, Zoho
        - communication: Slack, Teams
        - project: Jira, Asana, Notion
        - support: Zendesk, Intercom
        - calendar: Google Calendar, Outlook Calendar
        - other: Everything else

        Returns:
            Integration category string
        """
        # Auto-detect from integration_id
        email_integrations = ["outlook", "gmail", "email"]
        crm_integrations = ["salesforce", "hubspot", "zoho", "pipedrive"]
        comm_integrations = ["slack", "teams", "discord"]
        project_integrations = ["jira", "asana", "notion", "trello", "monday"]
        support_integrations = ["zendesk", "intercom", "freshdesk"]
        calendar_integrations = ["google_calendar", "outlook_calendar", "calendar"]

        integration_lower = self.integration_id.lower()

        if integration_lower in email_integrations:
            return "email"
        elif integration_lower in crm_integrations:
            return "crm"
        elif integration_lower in comm_integrations:
            return "communication"
        elif integration_lower in project_integrations:
            return "project"
        elif integration_lower in support_integrations:
            return "support"
        elif integration_lower in calendar_integrations:
            return "calendar"
        else:
            return "other"

    async def backfill_to_memory(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 500,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Generic backfill method - works for ANY integration.

        Fetches records from integration API, extracts entities,
        generates embeddings, and stores in LanceDB.

        Args:
            start_date: Fetch records from this date
            end_date: Fetch records until this date
            limit: Maximum records to fetch
            batch_size: Process records in batches

        Returns:
            Dict with job_id, status, and initial progress
        """
        import uuid
        job_id = str(uuid.uuid4())

        # Create job tracker
        job = BackfillJob(job_id, self.integration_id)
        _backfill_jobs[job_id] = job

        # Start async backfill with error handling
        task = asyncio.create_task(
            self._run_backfill(job, start_date, end_date, limit, batch_size)
        )

        # Add error callback to handle task failures
        def handle_error(task):
            try:
                exception = task.exception()
                if exception:
                    logger.error(f"Backfill task failed for {job.job_id}: {exception}")
                    job.status = "failed"
                    job.error = str(exception)
                    job.completed_at = datetime.now()
            except asyncio.CancelledError:
                logger.warning(f"Backfill task cancelled for {job.job_id}")

        task.add_done_callback(handle_error)

        # Store task reference for cancellation support
        job.task = task

        return {
            "success": True,
            "job_id": job_id,
            "integration_id": self.integration_id,
            "status": "started",
            "message": f"Backfill started for {self.integration_id}"
        }

    async def _run_backfill(
        self,
        job: BackfillJob,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        limit: int,
        batch_size: int
    ):
        """Internal method that runs the actual backfill"""
        try:
            job.status = "running"
            job.started_at = datetime.now()

            # Step 1: Fetch records
            logger.info(f"Fetching records for {self.integration_id}")
            records = await self.fetch_records(start_date, end_date, limit)
            job.total_records = len(records)

            if not records:
                job.status = "completed"
                job.completed_at = datetime.now()
                job.progress = 100
                logger.info(f"No records found for {self.integration_id}")
                return

            # Step 2: Process in batches
            logger.info(f"Processing {len(records)} records for {self.integration_id}")

            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]

                # Extract entities
                integration_type = self.get_integration_type()
                entities = await self.entity_extractor.extract(
                    integration_type=integration_type,
                    records=batch,
                    use_llm=self.use_llm_extraction
                )

                # Generate embeddings and store
                if self.lancedb:
                    for entity in entities:
                        try:
                            # Generate embedding
                            text = entity.get("text", "")
                            if text:
                                entity["vector"] = self.embedding_service.generate_embedding(text)

                            # Store in LanceDB
                            await self.lancedb.add_documents([entity])

                            job.processed_records += 1

                        except Exception as e:
                            logger.error(f"Error processing entity: {e}")
                            job.failed_records += 1

                # Update progress
                job.progress = int((i + len(batch)) / len(records) * 100)
                logger.info(f"Progress: {job.progress}% ({job.processed_records}/{job.total_records})")

            # Step 3: Complete
            job.status = "completed"
            job.completed_at = datetime.now()
            job.progress = 100

            logger.info(
                f"Backfill completed for {self.integration_id}: "
                f"{job.processed_records} processed, {job.failed_records} failed"
            )

        except Exception as e:
            logger.error(f"Backfill failed for {self.integration_id}: {e}")
            job.status = "failed"
            job.completed_at = datetime.now()
            job.error = str(e)

    @staticmethod
    def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a backfill job"""
        job = _backfill_jobs.get(job_id)
        return job.to_dict() if job else None


class IntegrationBackfillManager:
    """
    Manages backfill jobs across all integrations.

    Provides:
    - Trigger backfill for any integration
    - Trigger backfill for all integrations
    - Job status tracking
    """

    @staticmethod
    async def trigger_backfill(
        integration_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 500
    ) -> Dict[str, Any]:
        """
        Trigger backfill for a specific integration.

        Args:
            integration_id: Integration to backfill (e.g., "outlook", "gmail")
            start_date: Fetch records from this date
            end_date: Fetch records until this date
            limit: Maximum records to fetch

        Returns:
            Dict with job_id and status
        """
        # Import integration service dynamically
        try:
            # Map integration_id to service class
            service_map = {
                "outlook": "integrations.outlook_integration:OutlookIntegration",
                "gmail": "integrations.gmail_service:GmailService",
                "slack": "integrations.slack_service:SlackService",
                # Add more integrations as needed
            }

            if integration_id not in service_map:
                return {
                    "success": False,
                    "error": f"Integration {integration_id} not found or not supported"
                }

            # Dynamically import and instantiate service
            module_path, class_name = service_map[integration_id].split(":")
            module = __import__(module_path, fromlist=[class_name])
            service_class = getattr(module, class_name)

            # Create service instance (should inherit MemoryIntegrationMixin)
            service = service_class()

            # Trigger backfill
            return await service.backfill_to_memory(start_date, end_date, limit)

        except Exception as e:
            logger.error(f"Failed to trigger backfill for {integration_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    async def trigger_all_backfills(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit_per_integration: int = 500
    ) -> Dict[str, Any]:
        """
        Trigger backfill for ALL integrations.

        Args:
            start_date: Fetch records from this date
            end_date: Fetch records until this date
            limit_per_integration: Max records per integration

        Returns:
            Dict with overall status and list of job_ids
        """
        # List of integrations to backfill
        integrations = [
            "outlook", "gmail", "slack",
            "salesforce", "hubspot",
            "jira", "asana", "notion"
        ]

        job_ids = []
        errors = []

        for integration_id in integrations:
            try:
                result = await IntegrationBackfillManager.trigger_backfill(
                    integration_id, start_date, end_date, limit_per_integration
                )
                if result.get("success"):
                    job_ids.append(result["job_id"])
                else:
                    errors.append(f"{integration_id}: {result.get('error')}")

            except Exception as e:
                errors.append(f"{integration_id}: {str(e)}")

        return {
            "success": len(job_ids) > 0,
            "total_triggered": len(job_ids),
            "job_ids": job_ids,
            "errors": errors,
            "message": f"Triggered {len(job_ids)} backfills, {len(errors)} failed"
        }
