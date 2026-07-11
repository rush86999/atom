from __future__ import annotations

"""
Ingestion Pipeline Service - Orchestrates data flow from integrations to Knowledge Graph

Extends HybridDataIngestionService to automatically ingest fetched data into
GraphRAG for entity/relationship extraction and knowledge graph construction.

Key features:
- Fetches integration data via HybridDataIngestionService
- Extracts entities/relationships via GraphRAGEngine.ingest_structured_data()
- Tracks progress in IngestionJob table
- Enforces tenant_id isolation throughout
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from core.database import SessionLocal
from core.docling_processor import get_docling_processor
from core.entity_linking_service import EntityLinkingService
from core.graphrag_engine import GraphRAGEngine
from core.hybrid_data_ingestion import DEFAULT_SYNC_CONFIGS, HybridDataIngestionService
from core.integration_constants import MULTI_ENTITY_INTEGRATIONS
from core.lancedb_handler import LanceDBHandler
from core.models import DiscoveredEntity, DocumentIngestion, Tenant, UserConnection
from core.multi_entity_llm_extractor import MultiEntityLLMExtractor
from core.schema_discovery_service import SchemaDiscoveryService
from core.usage_tracking_service import UsageTrackingService

# Import IngestionJob if it exists (created in Task 2 of 220-01)
try:
    from core.models import IngestionJob

    INGESTION_JOB_EXISTS = True
except ImportError:
    INGESTION_JOB_EXISTS = False
    IngestionJob = None

logger = logging.getLogger(__name__)


class IngestionPipelineService(HybridDataIngestionService):
    """
    Orchestrates end-to-end ingestion pipeline from integrations to Knowledge Graph.

    Extends HybridDataIngestionService to add automatic GraphRAG ingestion
    after fetching integration data. Tracks all jobs in IngestionJob table
    for monitoring and progress tracking.

    All operations are tenant-isolated via tenant_id filtering.
    """

    def __init__(self, tenant_id: str, workspace_id: str, db: Session = None):
        """
        Initialize ingestion pipeline service.

        Args:
            tenant_id: Tenant/workspace ID for multi-tenant isolation
            workspace_id: Workspace identifier (same as tenant_id in multi-tenant setup)
            db: Optional database session
        """
        super().__init__(workspace_id=str(workspace_id), tenant_id=str(tenant_id))
        self.tenant_id = str(tenant_id)
        self.workspace_id = str(workspace_id)

        self.db = db

        # Initialize LanceDB handler for Basic Tier (search-ready) processing
        self.lancedb = LanceDBHandler(
            workspace_id=self.workspace_id, tenant_id=self.tenant_id, db=db
        )

        # Initialize GraphRAG engine for entity/relationship extraction
        self._graphrag = GraphRAGEngine(db=self.db)

        # Phase 323: High-performance Multi-Entity Extraction
        # Create LLMService once with proper tenant context (reused across all extractions)
        from core.llm_service import LLMService

        _llm_service = LLMService(
            tenant_id=self.tenant_id, workspace_id=self.workspace_id, db=self.db
        )
        self.multi_entity_extractor = MultiEntityLLMExtractor(llm_service=_llm_service)

        # Phase 323: Schema Discovery & Linking (Replaces OpenIE)
        self.schema_discovery = SchemaDiscoveryService(db=self.db)
        self.entity_linker = EntityLinkingService(
            db=self.db, schema_discovery_service=self.schema_discovery
        )
        from core.meta_agent_orchestrator import MetaAgentOrchestrator

        self.meta_agent_orchestrator = MetaAgentOrchestrator(db=self.db)

        # Initialize usage tracking service for ACU monitoring
        self.usage_tracker = UsageTrackingService(tenant_id=self.tenant_id, db=self.db)

    def close(self):
        """Close sub-services and sessions"""
        if self.graphrag:
            self.graphrag.close()
        if self.usage_tracker:
            self.usage_tracker.close()

    async def sync_and_ingest(
        self,
        integration_id: str,
        connection_id: Union[str, None] = None,
        trigger_type: str = "manual",
    ) -> dict[str, Any]:
        """
        Sync integration data and ingest into Knowledge Graph.

        Orchestrates the full pipeline:
        1. Fetch integration data via HybridDataIngestionService._fetch_integration_data()
        2. Convert each record to text via _record_to_text()
        3. Extract entities/relationships via GraphRAGEngine.ingest_structured_data()
        4. Track progress in IngestionJob table

        Args:
            integration_id: Integration identifier (e.g., "salesforce", "slack")
            connection_id: Optional UserConnection ID for credentials
            trigger_type: Job trigger type ("scheduled", "manual", "webhook")

        Returns:
            Dict with sync results:
                - records_fetched: Number of records fetched from integration
                - entities_extracted: Number of entities extracted
                - relationships_extracted: Number of relationships extracted
                - errors: List of error messages
                - job_id: IngestionJob ID for tracking
        """
        # Get sync configuration
        config = self.sync_configs.get(integration_id)
        if not config:
            # Use default config if available
            if integration_id in DEFAULT_SYNC_CONFIGS:
                config = DEFAULT_SYNC_CONFIGS[integration_id]
                self.sync_configs[integration_id] = config
            else:
                return {"error": f"No sync configuration for {integration_id}", "success": False}

        # Create ingestion job for tracking (if IngestionJob model exists)
        if INGESTION_JOB_EXISTS:
            job_id = self._create_ingestion_job(
                integration_id=integration_id,
                trigger_type=trigger_type,
                connection_id=connection_id,
            )
        else:
            job_id = f"fallback-{uuid.uuid4()}"

        results = {
            "integration_id": integration_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "job_id": job_id,
            "trigger_type": trigger_type,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "records_fetched": 0,
            "records_processed": 0,
            "entities_extracted": 0,
            "relationships_extracted": 0,
            "errors": [],
        }

        # Track start time for ACU calculation
        start_time = datetime.now(timezone.utc)

        try:
            # Update job status to running (if IngestionJob model exists)
            if INGESTION_JOB_EXISTS:
                self._update_ingestion_job(
                    job_id=job_id, status="running", started_at=datetime.now(timezone.utc)
                )

            # Step 1: Fetch integration data using existing HybridDataIngestionService method
            logger.info(f"[{job_id}] Fetching data from {integration_id}")
            records = await self._fetch_integration_data(integration_id, config)
            results["records_fetched"] = len(records)

            if not records:
                logger.info(f"[{job_id}] No records fetched from {integration_id}")
                if INGESTION_JOB_EXISTS:
                    self._update_ingestion_job(
                        job_id=job_id,
                        status="completed",
                        completed_at=datetime.now(timezone.utc),
                        records_fetched=0,
                        records_processed=0,
                        entities_extracted=0,
                        relationships_extracted=0,
                    )
                results["success"] = True
                results["completed_at"] = datetime.now(timezone.utc).isoformat()
                return results

            # Step 2: Convert records to text and prepare for GraphRAG ingestion
            entities = []
            relationships = []

            ingested_record_ids = []  # Track for post-ingestion idempotency recording

            for record in records:
                try:
                    # Step 2: Convert record to text representation
                    text = self._record_to_text(record, integration_id)

                    # Skip if no meaningful text
                    if not text or len(text) < 10:
                        continue

                    # Document-level idempotency: skip unchanged records
                    record_id = str(record.get("id"))
                    if record_id and self._is_doc_already_ingested(
                        self.workspace_id, record_id, text
                    ):
                        logger.debug(f"Skipping already-ingested record: {record_id}")
                        results["records_processed"] += 1
                        continue

                    results["records_processed"] += 1

                    # Phase 323: High-performance Multi-Entity Extraction (Advanced)
                    # For complex unstructured data, extract multiple business entities
                    if integration_id in MULTI_ENTITY_INTEGRATIONS:
                        await self._process_multi_entity_extraction(
                            record, integration_id, text, job_id
                        )

                    # Extract basic structured entities and relationships
                    entity, rel = self._extract_structured_entities(record, integration_id, text)
                    if entity:
                        entities.append(entity)
                    if rel:
                        relationships.append(rel)
                    if record_id:
                        ingested_record_ids.append((record_id, text))

                except Exception as record_err:
                    error_msg = (
                        f"Failed to process record {record.get('id', 'unknown')}: {record_err}"
                    )
                    results["errors"].append(error_msg)
                    logger.warning(f"[{job_id}] {error_msg}")

            # Step 3: Batch ingest into GraphRAG
            if entities or relationships:
                logger.info(
                    f"[{job_id}] Ingesting {len(entities)} entities, {len(relationships)} relationships to GraphRAG"
                )
                self.graphrag.ingest_structured_data(
                    workspace_id=self.workspace_id, entities=entities, relationships=relationships
                )
                results["entities_extracted"] += len(entities)
                results["relationships_extracted"] += len(relationships)

                # Record successful ingestion for document-level idempotency
                for rid, rtext in ingested_record_ids:
                    self._record_doc_ingestion(self.workspace_id, rid, rtext, integration_id)

            # Phase 323 Step 4: Schema Discovery & Auto-Promotion
            # Replaces legacy OpenIE loop
            if results["records_processed"] > 0:
                await self._run_schema_discovery(results)

            results["draft_types_created"] = (
                0  # Draft types are handled inside _run_schema_discovery
            )
            results["custom_entity_types"] = []

            # Calculate ACU consumption
            completed_at = datetime.now(timezone.utc)
            processing_duration_ms = int((completed_at - start_time).total_seconds() * 1000)

            # Estimate LLM usage (GraphRAG doesn't expose token counts directly)
            # Use record count as proxy for LLM complexity
            estimated_llm_calls = len(entities) + len(relationships)
            estimated_tokens = (
                results["records_processed"] * 500
            )  # Rough estimate: 500 tokens per record

            # Calculate ACU consumed
            acu_consumed = self._calculate_acu_consumed(
                llm_calls=estimated_llm_calls,
                total_tokens=estimated_tokens,
                processing_duration_ms=processing_duration_ms,
            )

            # Track ACU usage
            try:
                usage_log = await self.usage_tracker.track_acu_usage(
                    job_id=job_id,
                    job_type="historical_sync" if trigger_type == "scheduled" else "manual",
                    integration_id=integration_id,
                    acu_consumed=acu_consumed,
                    llm_calls=estimated_llm_calls,
                    total_tokens=estimated_tokens,
                    prompt_tokens=int(estimated_tokens * 0.7),  # Estimate: 70% prompt tokens
                    completion_tokens=int(
                        estimated_tokens * 0.3
                    ),  # Estimate: 30% completion tokens
                    processing_duration_ms=processing_duration_ms,
                    records_processed=results["records_processed"],
                    entities_extracted=results["entities_extracted"],
                    relationships_extracted=results["relationships_extracted"],
                    source_connection_id=connection_id,
                )
                results["usage_log_id"] = usage_log.id
                results["acu_consumed"] = acu_consumed
                logger.info(f"[{job_id}] ACU usage tracked: {acu_consumed:.2f} ACU")
            except Exception as usage_err:
                # Don't fail the job if usage tracking fails
                logger.warning(f"[{job_id}] Failed to track ACU usage: {usage_err}")
                results["usage_tracking_error"] = str(usage_err)

            # Update job as completed (if IngestionJob model exists)
            if INGESTION_JOB_EXISTS:
                self._update_ingestion_job(
                    job_id=job_id,
                    status="completed",
                    completed_at=completed_at,
                    records_fetched=results["records_fetched"],
                    records_processed=results["records_processed"],
                    entities_extracted=results["entities_extracted"],
                    relationships_extracted=results["relationships_extracted"],
                )

            results["success"] = True
            results["completed_at"] = completed_at.isoformat()

            logger.info(
                f"[{job_id}] Sync completed: {results['records_processed']}/{results['records_fetched']} records, "
                f"{results['entities_extracted']} entities, {results['relationships_extracted']} relationships"
            )

        except Exception as e:
            error_msg = f"Pipeline failed for {integration_id}: {e}"
            results["errors"].append(error_msg)
            results["success"] = False
            results["error"] = error_msg

            # Update job as failed (if IngestionJob model exists)
            if INGESTION_JOB_EXISTS:
                self._update_ingestion_job(
                    job_id=job_id,
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    error_message=error_msg,
                    error_details={"exception": str(e)},
                )

            logger.error(f"[{job_id}] {error_msg}")

        return results

    def _extract_structured_entities(
        self, record: dict[str, Any], integration_id: str, text: str
    ) -> Union[tuple[dict, dict], tuple[None, None]]:
        """
        Extract structured entity and relationship from a record.

        Converts integration records to GraphRAG entity/relationship format.
        This is a simplified version - LLM extraction happens in GraphRAGEngine.

        Args:
            record: Raw record from integration
            integration_id: Integration identifier
            text: Text representation of record

        Returns:
            Tuple of (entity_dict, relationship_dict) or (None, None)
        """
        record_type = record.get("type", "record")
        record_id = str(
            record.get("id", "unknown")
        )  # Convert UUID to string for JSON serialization
        record_name = (
            record.get("name")
            or record.get("title")
            or record.get("subject")
            or f"{record_type}_{record_id}"
        )

        # Create entity for this record
        entity = {
            "name": record_name,
            "type": record_type,
            "description": text[:500],  # Truncate for description
            "properties": {
                "source": integration_id,
                "record_id": record_id,
                "record_type": record_type,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "doc_id": record_id,  # For idempotency/source tracking
            },
        }

        # Add additional metadata from record
        for key in ["email", "company", "stage", "status", "amount"]:
            if key in record and record[key]:
                entity["properties"][key] = record[key]

        # Promote key fields to properties for better schema inference
        for field in ["subject", "content", "summary", "description"]:
            if field in record and field not in entity.get("properties", {}):
                entity.setdefault("properties", {})[field] = record[field]

        # Create relationship to integration
        relationship = {
            "from": record_name,
            "to": integration_id,
            "type": "synced_from",
            "properties": {
                "source": integration_id,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "doc_id": record_id,  # For idempotency/source tracking
            },
        }

        return entity, relationship

    @staticmethod
    def _hash_text(text: str) -> str:
        """Generate a SHA-256 hash of text for document-level idempotency."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _record_doc_ingestion(self, workspace_id: str, doc_id: str, text: str, source: str) -> None:
        """Upsert a DocumentIngestion record after successful processing."""
        from sqlalchemy.exc import IntegrityError

        session = SessionLocal()
        try:
            doc_hash = self._hash_text(text)
            existing = (
                session.query(DocumentIngestion)
                .filter_by(workspace_id=workspace_id, doc_id=doc_id)
                .first()
            )
            if existing:
                existing.content_hash = doc_hash
                existing.source = source
            else:
                session.add(
                    DocumentIngestion(
                        workspace_id=workspace_id,
                        doc_id=doc_id,
                        content_hash=doc_hash,
                        source=source,
                    )
                )
            session.commit()
        except IntegrityError:
            session.rollback()
        except Exception as e:
            session.rollback()
            logger.warning(f"Failed to record document ingestion for {doc_id}: {e}")
        finally:
            session.close()

    def _is_doc_already_ingested(self, workspace_id: str, doc_id: str, text: str) -> bool:
        """Check if a document has already been ingested with the same content."""
        session = SessionLocal()
        try:
            doc_hash = self._hash_text(text)
            existing = (
                session.query(DocumentIngestion)
                .filter_by(workspace_id=workspace_id, doc_id=doc_id)
                .first()
            )
            return existing is not None and existing.content_hash == doc_hash
        finally:
            session.close()

    def _get_user_credentials(
        self, integration_id: str, user_id: str
    ) -> Union[dict[str, Any], None]:
        """
        Get user credentials for integration authentication.

        Queries UserConnection table for tenant-isolated credentials.

        Args:
            integration_id: Integration identifier
            user_id: User ID to get credentials for

        Returns:
            Dict with credentials (tokens, secrets) or None if not found
        """
        session = SessionLocal()
        try:
            # Query UserConnection with tenant isolation
            connection = (
                session.query(UserConnection)
                .filter(
                    UserConnection.tenant_id == self.tenant_id,
                    UserConnection.integration_id == integration_id,
                    UserConnection.user_id == user_id,
                    UserConnection.is_active == True,
                )
                .first()
            )

            if not connection:
                logger.warning(f"No active connection found for {integration_id} user {user_id}")
                return None

            # Return credentials dict (excluding sensitive fields from logs)
            credentials = {
                "connection_id": connection.id,
                "integration_id": connection.integration_id,
                "user_id": connection.user_id,
                "token_valid_until": connection.expires_at.isoformat()
                if connection.expires_at
                else None,
            }

            return credentials

        except Exception as e:
            logger.error(f"Failed to get credentials for {integration_id}: {e}")
            return None
        finally:
            session.close()

    def _create_ingestion_job(
        self, integration_id: str, trigger_type: str, connection_id: Union[str, None] = None
    ) -> str:
        """
        Create IngestionJob record for progress tracking.

        Args:
            integration_id: Integration identifier
            trigger_type: Job trigger type ("scheduled", "manual", "webhook")
            connection_id: Optional UserConnection ID

        Returns:
            Job ID (UUID string)
        """
        if not INGESTION_JOB_EXISTS:
            # Fallback if model doesn't exist yet
            return f"fallback-{uuid.uuid4()}"

        session = SessionLocal()
        try:
            job = IngestionJob(
                id=str(uuid.uuid4()),
                tenant_id=self.tenant_id,
                integration_id=integration_id,
                trigger_type=trigger_type,
                source_connection_id=connection_id,
                status="pending",
                created_at=datetime.now(timezone.utc),
            )

            session.add(job)
            session.commit()

            logger.info(
                f"Created ingestion job {job.id} for {integration_id} (trigger: {trigger_type})"
            )
            return job.id

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create ingestion job: {e}")
            # Return fallback ID for error tracking
            return f"fallback-{uuid.uuid4()}"
        finally:
            session.close()

    def _update_ingestion_job(
        self,
        job_id: str,
        status: str,
        completed_at: Union[datetime, None] = None,
        started_at: Union[datetime, None] = None,
        records_fetched: Union[int, None] = None,
        records_processed: Union[int, None] = None,
        entities_extracted: Union[int, None] = None,
        relationships_extracted: Union[int, None] = None,
        error_message: Union[str, None] = None,
        error_details: Union[dict, None] = None,
    ) -> bool:
        """
        Update IngestionJob record with progress and results.

        Args:
            job_id: Job ID to update
            status: New status ("pending", "running", "completed", "failed")
            completed_at: Job completion timestamp
            started_at: Job start timestamp
            records_fetched: Number of records fetched
            records_processed: Number of records successfully processed
            entities_extracted: Number of entities extracted
            relationships_extracted: Number of relationships extracted
            error_message: Error message if failed
            error_details: Detailed error information

        Returns:
            True if update successful, False otherwise
        """
        if not INGESTION_JOB_EXISTS:
            # Silently skip if model doesn't exist yet
            return False

        session = SessionLocal()
        try:
            job = (
                session.query(IngestionJob)
                .filter(
                    IngestionJob.id == job_id,
                    IngestionJob.tenant_id == self.tenant_id,  # Tenant isolation
                )
                .first()
            )

            if not job:
                logger.warning(f"IngestionJob {job_id} not found for tenant {self.tenant_id}")
                return False

            # Update status
            job.status = status

            if started_at:
                job.started_at = started_at

            if completed_at:
                job.completed_at = completed_at

            if records_fetched is not None:
                job.records_fetched = records_fetched

            if records_processed is not None:
                job.records_processed = records_processed

            if entities_extracted is not None:
                job.entities_extracted = entities_extracted

            if relationships_extracted is not None:
                job.relationships_extracted = relationships_extracted

            if error_message:
                job.error_message = error_message

            if error_details:
                job.error_details = error_details

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update ingestion job {job_id}: {e}")
            return False
        finally:
            session.close()

    async def _prepare_record_text_async(
        self, record: dict[str, Any], integration_id: str, connection_id: Union[str, None] = None
    ) -> str:
        """
        Asynchronously prepare record text for ingestion.

        Standardized binary ingestion path:
        1. Checks for 'file' or 'files' type
        2. Applies global and per-provider feature flags
        3. Validates extension against Docling supported formats
        4. Downloads file bytes via standardized download_file contract
        5. Parses with Docling singleton
        """
        logger.info(
            f"[INGEST_PREPARE] Preparing text for {integration_id} record {record.get('id')}",
            tenant_id=self.tenant_id,
            record_type=record.get("type"),
        )
        # 0. Global Kill Switch check
        if os.getenv("ENABLE_BINARY_INGESTION", "true").lower() == "false":
            return self._record_to_text(record, integration_id)

        # 1. Detect File Record (Standardized 'file' or Zoho 'files')
        if record.get("type") in ["file", "files"]:
            # Per-provider legacy flag (backward compat)
            legacy_flag = f"ENABLE_{integration_id.upper()}_FILE_PARSING"
            if os.getenv(legacy_flag, "true").lower() == "false":
                return self._record_to_text(record, integration_id)

            # Check for WorkDrive specific flag too for safety
            if (
                integration_id == "zoho_workdrive"
                and os.getenv("ENABLE_WORKDRIVE_FILE_PARSING", "true").lower() == "false"
            ):
                return self._record_to_text(record, integration_id)

            file_id = record.get("id")
            file_name = record.get("name", "unnamed_file")
            extension = record.get("extension")

            # 2. Validate Format with Docling Singleton
            processor = get_docling_processor()
            if extension and not processor.is_format_supported(extension):
                logger.info(
                    f"[INGEST_BINARY_SKIP] Unsupported extension: {extension}. Falling back to metadata.",
                    tenant_id=self.tenant_id,
                    file_name=file_name,
                )
                # Fall back early if format is unsupported
                return self._record_to_text(record, integration_id)

            try:
                # 3. Get service instance from registry
                service = await self.integration_registry.get_service(
                    integration_id, self.tenant_id, connection_id
                )

                # Duck-typing check for standardized download contract
                if (
                    not service
                    or not hasattr(service, "download_file")
                    or not callable(service.download_file)
                ):
                    return self._record_to_text(record, integration_id)

                logger.info(f"Downloading {integration_id} file: {file_name} ({file_id})")

                # 4. Download file bytes
                file_bytes = await service.download_file(file_id=file_id)

                if not file_bytes:
                    logger.warning(f"Empty file content downloaded for {file_name} ({file_id})")
                    return self._record_to_text(record, integration_id)

                # 5. Check file size
                MAX_FILE_SIZE = int(os.getenv("MAX_INGESTION_FILE_SIZE_MB", "50")) * 1024 * 1024
                file_size = len(file_bytes)
                if file_size > MAX_FILE_SIZE:
                    logger.warning(
                        f"File {file_name} ({file_size} bytes) exceeds size limit "
                        f"({MAX_FILE_SIZE} bytes), falling back to metadata"
                    )
                    return self._record_to_text(record, integration_id)

                logger.info(
                    f"Parsing {integration_id} file: {file_name} ({file_size} bytes, {extension or 'unknown format'})"
                )

                # 6. Parse document with Docling
                result = await processor.process_document(
                    file_bytes, file_type=extension, file_name=file_name
                )

                # Extract text content from result dictionary
                if not result or not result.get("success"):
                    logger.warning(
                        f"Docling parsing failed for {file_name}: {result.get('error', 'unknown error')}"
                    )
                    return self._record_to_text(record, integration_id)

                extracted_text = result.get("content", "")
                if not extracted_text or len(extracted_text) < 10:
                    logger.warning(
                        f"Docling extracted insufficient text from {file_name} "
                        f"({len(extracted_text)} chars)"
                    )
                    return self._record_to_text(record, integration_id)

                logger.info(f"Successfully extracted {len(extracted_text)} chars from {file_name}")
                return extracted_text

            except Exception as e:
                logger.error(f"Error processing binary file {file_name} from {integration_id}: {e}")
                return self._record_to_text(record, integration_id)

        # ========================================================================
        # Email Attachments (Phase 1: Attachment Ingestion)
        # ========================================================================
        # Check for attachments - handle both webhook and backfill type values
        # Webhook: type="email" or "gmail_message"
        # Backfill: type="messages" or "emails" (from historical sync raw API responses)
        has_attachments = record.get("hasAttachments") is True
        # Also check nested metadata or raw_json for backfill records
        if not has_attachments and isinstance(record.get("metadata"), dict):
            has_attachments = record["metadata"].get("hasAttachments") is True
        if not has_attachments and isinstance(record.get("raw_json"), dict):
            has_attachments = record["raw_json"].get("hasAttachments") is True

        if (
            integration_id in ["outlook", "gmail"]
            and record.get("type") in ["email", "gmail_message", "messages", "emails"]
            and has_attachments
        ):
            try:
                # Check feature flag
                flag_name = f"ENABLE_{integration_id.upper()}_ATTACHMENT_INGESTION"
                if os.getenv(flag_name, "true").lower() == "false":
                    return self._record_to_text(record, integration_id)

                message_id = record.get("id")
                if not message_id:
                    return self._record_to_text(record, integration_id)

                logger.info(f"Processing attachments for {integration_id} message {message_id}")

                # Get service instance for attachment metadata
                service = await self.integration_registry.get_service(
                    integration_id, self.tenant_id, connection_id
                )

                if not service:
                    logger.warning(
                        f"Could not get {integration_id} service for attachment processing"
                    )
                    return self._record_to_text(record, integration_id)

                # Get base email body text
                base_text = self._record_to_text(record, integration_id)

                # Fetch attachment metadata using standardized service method
                attachments = await service.get_attachment_metadata(
                    user_id=connection_id or self.tenant_id, message_id=message_id
                )

                # Get access token from service config
                token = None
                if hasattr(service, "config"):
                    token = service.config.get("access_token")
                elif hasattr(service, "_config"):
                    token = service._config.get("access_token")

                if not attachments:
                    return base_text

                # Limit number of attachments processed to avoid runaway costs
                MAX_ATTACHMENTS = int(
                    os.getenv(f"MAX_{integration_id.upper()}_ATTACHMENTS_PER_EMAIL", "5")
                )
                processed_count = 0
                attachment_texts = []

                processor = get_docling_processor()

                for attachment in attachments[:MAX_ATTACHMENTS]:
                    attachment_id = attachment.get("id")
                    attachment_name = attachment.get("name", "unknown")
                    attachment_size = attachment.get("size", 0)
                    content_type = attachment.get("contentType", "")

                    # Extract extension from filename
                    _, ext = os.path.splitext(attachment_name)
                    extension = ext.lstrip(".").lower() if ext else None

                    # Check format support
                    if extension and not processor.is_format_supported(extension):
                        logger.info(
                            f"Skipping attachment {attachment_name} (extension '{extension}' not supported)"
                        )
                        continue

                    # Skip oversized attachments
                    MAX_ATTACHMENT_SIZE = (
                        int(os.getenv(f"MAX_{integration_id.upper()}_ATTACHMENT_SIZE_MB", "10"))
                        * 1024
                        * 1024
                    )
                    if attachment_size > MAX_ATTACHMENT_SIZE:
                        logger.warning(
                            f"Skipping attachment {attachment_name} ({attachment_size} bytes) "
                            f"exceeds size limit ({MAX_ATTACHMENT_SIZE} bytes)"
                        )
                        continue

                    try:
                        # Download attachment binary content
                        attachment_bytes = await service.download_attachment(
                            user_id=connection_id or self.tenant_id,
                            message_id=message_id,
                            attachment_id=attachment_id,
                            token=token,
                        )

                        if not attachment_bytes:
                            logger.warning(f"Failed to download attachment {attachment_name}")
                            continue

                        # Parse with Docling
                        result = await processor.process_document(
                            attachment_bytes, file_type=extension, file_name=attachment_name
                        )

                        if result and result.get("success"):
                            extracted = result.get("content", "")
                            if extracted and len(extracted) >= 10:
                                attachment_texts.append(
                                    f"\n\n[Attachment: {attachment_name}]\n{extracted}"
                                )
                                processed_count += 1
                                logger.info(
                                    f"Successfully processed attachment {attachment_name} "
                                    f"({len(extracted)} chars)"
                                )
                            else:
                                logger.warning(
                                    f"Docling extracted insufficient text from {attachment_name} "
                                    f"({len(extracted)} chars)"
                                )
                        else:
                            logger.warning(
                                f"Docling parsing failed for {attachment_name}: "
                                f"{result.get('error', 'unknown error')}"
                            )

                    except Exception as e:
                        logger.error(f"Error processing attachment {attachment_name}: {e}")
                        continue

                if attachment_texts:
                    logger.info(
                        f"Successfully processed {processed_count}/{len(attachments)} "
                        f"attachments for message {message_id}"
                    )
                    # Combine base text with attachment texts
                    return base_text + "".join(attachment_texts)
                else:
                    return base_text

            except Exception as e:
                logger.error(f"Error processing {integration_id} attachments: {e}")
                # Fall back to base text
                return self._record_to_text(record, integration_id)

        # 7. Default fallback for non-file records
        return self._record_to_text(record, integration_id)

    async def process_webhook_payload(
        self,
        integration_id: str,
        webhook_data: dict[str, Any],
        source_connection_id: Union[str, None] = None,
    ) -> dict[str, Any]:
        """
        Process webhook payload and ingest to Knowledge Graph.

        Transforms integration-specific webhook payloads into standardized records,
        extracts entities/relationships via GraphRAGEngine, and stores in graph.

        Args:
            integration_id: Integration identifier (e.g., "slack", "salesforce")
            webhook_data: Raw webhook payload from integration
            source_connection_id: Optional UserConnection ID

        Returns:
            Dict with processing results:
                - records_processed: Number of records processed
                - entities_extracted: Number of entities extracted
                - relationships_extracted: Number of relationships extracted
                - errors: List of error messages
                - success: bool

        CRITICAL: Tenant_id is enforced for multi-tenant security.
        """
        results = {
            "integration_id": integration_id,
            "tenant_id": self.tenant_id,
            "records_processed": 0,
            "entities_extracted": 0,
            "relationships_extracted": 0,
            "errors": [],
            "success": False,
        }

        # Track start time for ACU calculation
        start_time = datetime.now(timezone.utc)

        try:
            # Transform webhook payload to standardized record format
            # Include source_connection_id in webhook_data for transformers that need it
            if source_connection_id:
                webhook_data["_source_connection_id"] = source_connection_id
            records = await self._transform_webhook_payload(integration_id, webhook_data)

            if not records:
                logger.info(
                    f"No records extracted from webhook payload for {integration_id}",
                    tenant_id=self.tenant_id,
                )
                results["success"] = True
                return results

            # Process each record
            entities = []
            relationships = []

            for record in records:
                try:
                    import sys

                    print(
                        f"[FATAL_DEBUG] Processing record: type={record.get('type')}, id={record.get('id')[:8] if record.get('id') else 'N/A'}",
                        file=sys.stderr,
                        flush=True,
                    )
                    # Convert record to text (potentially parsing attachments asynchronously)
                    text = await self._prepare_record_text_async(
                        record, integration_id, source_connection_id
                    )
                    record["content"] = text
                    if "body" in record:
                        if isinstance(record["body"], dict):
                            record["body"]["content"] = text
                        else:
                            record["body"] = text
                    if "bodyPreview" in record:
                        record["bodyPreview"] = ""

                    print(
                        f"[FATAL_DEBUG] Record text length: {len(text) if text else 0}, text preview: {text[:50] if text else 'None'}...",
                        file=sys.stderr,
                        flush=True,
                    )
                    if not text or len(text) < 10:
                        print(
                            f"[FATAL_DEBUG] Skipping record: text too short",
                            file=sys.stderr,
                            flush=True,
                        )
                        continue

                    results["records_processed"] += 1

                    # Extract entities and relationships
                    entity, rel = self._extract_structured_entities(record, integration_id, text)
                    print(
                        f"[FATAL_DEBUG] Extracted: entity={bool(entity)}, rel={bool(rel)}",
                        file=sys.stderr,
                        flush=True,
                    )
                    if entity:
                        entities.append(entity)
                    if rel:
                        relationships.append(rel)

                except Exception as record_err:
                    error_msg = f"Failed to process webhook record: {record_err}"
                    results["errors"].append(error_msg)
                    logger.warning(
                        error_msg, integration_id=integration_id, tenant_id=self.tenant_id
                    )

            # Batch ingest into GraphRAG
            if entities or relationships:
                import sys

                print(
                    f"[FATAL_DEBUG] Ingesting to GraphRAG: {len(entities)} entities, {len(relationships)} relationships",
                    file=sys.stderr,
                    flush=True,
                )
                logger.info(
                    f"Ingesting webhook data: {len(entities)} entities, {len(relationships)} relationships",
                    integration_id=integration_id,
                    tenant_id=self.tenant_id,
                )
                self.graphrag.ingest_structured_data(
                    workspace_id=self.workspace_id, entities=entities, relationships=relationships
                )
                results["entities_extracted"] = len(entities)
                results["relationships_extracted"] = len(relationships)
            else:
                import sys

                print(
                    f"[FATAL_DEBUG] No entities/relationships extracted, skipping GraphRAG ingestion",
                    file=sys.stderr,
                    flush=True,
                )

            # Phase 323: Multi-entity extraction to discovered_entities
            # This enables schema discovery and entity type promotion
            import sys

            print(
                f"[FATAL_DEBUG] === PHASE 323 MULTI-ENTITY EXTRACTION === records_count={len(records)}",
                file=sys.stderr,
                flush=True,
            )
            logger.info(f"[PHASE_323] Starting multi-entity extraction for {len(records)} records")
            for record in records:
                # Use pre-mutated content (including attachment text) rather than recomputing via _record_to_text
                text = record.get("content") or record.get("text", "")
                print(
                    f"[FATAL_DEBUG] Phase 323: record_id={record.get('id', 'unknown')[:8]}, text_len={len(text) if text else 0}",
                    file=sys.stderr,
                    flush=True,
                )
                if text and len(text) > 50:
                    try:
                        job_id = f"webhook_{record.get('id', 'unknown')[:8]}"
                        print(
                            f"[FATAL_DEBUG] Phase 323: calling _process_multi_entity_extraction with job_id={job_id}",
                            file=sys.stderr,
                            flush=True,
                        )
                        discovered_count = await self._process_multi_entity_extraction(
                            record, integration_id, text, job_id
                        )
                        print(
                            f"[FATAL_DEBUG] Phase 323: returned discovered_count={discovered_count}",
                            file=sys.stderr,
                            flush=True,
                        )
                        if discovered_count > 0:
                            results["entities_extracted"] += discovered_count
                    except Exception as extract_err:
                        print(
                            f"[FATAL_DEBUG] Phase 323: EXCEPTION - {extract_err}",
                            file=sys.stderr,
                            flush=True,
                        )
                        import traceback

                        traceback.print_exc()
                        logger.warning(
                            f"Multi-entity extraction failed for record {record.get('id')}: {extract_err}"
                        )
                else:
                    print(
                        f"[FATAL_DEBUG] Phase 323: SKIPPED - text too short or empty",
                        file=sys.stderr,
                        flush=True,
                    )

            # LanceDB indexing for webhook records (communication memory)
            # This enables semantic search for email/chat content
            if integration_id in ["outlook", "gmail", "slack"]:
                try:
                    from core.lancedb_handler import LanceDBHandler

                    lancedb = LanceDBHandler(
                        tenant_id=self.tenant_id,
                        workspace_id=self.workspace_id,
                    )

                    for record in records:
                        # Extract text content from record
                        text = record.get("text") or record.get("content", "")
                        if not text:
                            # Try to construct from other fields
                            if record.get("type") == "email":
                                subject = record.get("subject", "")
                                body = record.get("body", "")
                                text = f"{subject}\n\n{body}"

                        if text and len(text) > 10:  # Minimum content threshold
                            doc_id = str(record.get("id", ""))  # Convert UUID to string
                            source = f"{integration_id}_webhook"

                            # Build metadata
                            metadata = {
                                "integration_id": integration_id,
                                "source_connection_id": source_connection_id,
                                "record_type": record.get("type", "unknown"),
                                "timestamp": record.get("timestamp") or record.get("created_at"),
                            }
                            # Add email-specific metadata
                            if record.get("type") == "email":
                                metadata["from"] = record.get("from")
                                metadata["to"] = record.get("to")
                                metadata["subject"] = record.get("subject")

                            lancedb.add_document(
                                table_name="atom_communications",
                                text=text,
                                source=source,
                                metadata=metadata,
                                user_id=self.tenant_id,
                                workspace_id=self.workspace_id,
                                doc_id=doc_id,
                                extract_knowledge=False,  # Already extracted via GraphRAG
                                skip_ai_triggers=True,  # Prevent loops
                            )

                    logger.info(
                        f"Indexed {len(records)} webhook records in LanceDB",
                        integration_id=integration_id,
                        tenant_id=self.tenant_id,
                    )
                    results["lancedb_indexed"] = len(records)
                except Exception as lancedb_err:
                    # Don't fail webhook processing if LanceDB fails
                    logger.warning(
                        f"LanceDB indexing failed for webhook: {lancedb_err}",
                        integration_id=integration_id,
                        tenant_id=self.tenant_id,
                    )
                    results["lancedb_error"] = str(lancedb_err)

            # Calculate ACU consumption
            completed_at = datetime.now(timezone.utc)
            processing_duration_ms = int((completed_at - start_time).total_seconds() * 1000)

            # Estimate LLM usage
            estimated_llm_calls = len(entities) + len(relationships)
            estimated_tokens = (
                results["records_processed"] * 300
            )  # Webhook payloads are typically smaller

            # Calculate ACU consumed
            acu_consumed = self._calculate_acu_consumed(
                llm_calls=estimated_llm_calls,
                total_tokens=estimated_tokens,
                processing_duration_ms=processing_duration_ms,
            )

            # Track ACU usage
            try:
                job_id = f"webhook-{uuid.uuid4()}"
                usage_log = await self.usage_tracker.track_acu_usage(
                    job_id=job_id,
                    job_type="webhook_ingestion",
                    integration_id=integration_id,
                    acu_consumed=acu_consumed,
                    llm_calls=estimated_llm_calls,
                    total_tokens=estimated_tokens,
                    prompt_tokens=int(estimated_tokens * 0.7),
                    completion_tokens=int(estimated_tokens * 0.3),
                    processing_duration_ms=processing_duration_ms,
                    records_processed=results["records_processed"],
                    entities_extracted=results["entities_extracted"],
                    relationships_extracted=results["relationships_extracted"],
                    source_connection_id=source_connection_id,
                )
                results["usage_log_id"] = usage_log.id
                results["acu_consumed"] = acu_consumed
                logger.info(f"Webhook ACU usage tracked: {acu_consumed:.2f} ACU")
            except Exception as usage_err:
                # Don't fail webhook processing if usage tracking fails
                logger.warning(f"Failed to track webhook ACU usage: {usage_err}")
                results["usage_tracking_error"] = str(usage_err)

            results["success"] = True

            logger.info(
                f"Webhook payload processing complete for {integration_id}",
                tenant_id=self.tenant_id,
                records_processed=results["records_processed"],
                entities_extracted=results["entities_extracted"],
                relationships_extracted=results["relationships_extracted"],
            )
        except Exception as e:
            logger.error(f"Webhook processing failed for {integration_id}: {e}")
            results["error"] = str(e)

        return results

    async def process_webhook_payload_tiered(
        self,
        integration_id: str,
        webhook_data: dict[str, Any],
        source_connection_id: Union[str, None] = None,
    ) -> dict[str, Any]:
        """
        Process webhook payload with Tiered Ingestion (Basic vs Deep).

        1. Basic Tier: Indexes to LanceDB (extract_knowledge=False) [ALWAYS RUNS]
        2. Deep Tier: Entity extraction via GraphRAG [GATED BY QUOTA]

        Args:
            integration_id: Integration identifier
            webhook_data: Raw webhook payload
            source_connection_id: Optional UserConnection ID

        Returns:
            Dict with results and tier executed
        """
        results = {
            "integration_id": integration_id,
            "tenant_id": self.tenant_id,
            "records_processed": 0,
            "entities_extracted": 0,
            "tier": "none",
            "success": False,
        }

        # Track start time for duration
        start_time = datetime.now(timezone.utc)

        try:
            # Include source_connection_id in webhook_data for transformers that need it
            if source_connection_id:
                webhook_data["_source_connection_id"] = source_connection_id
            # 1. Transform payload
            records = await self._transform_webhook_payload(integration_id, webhook_data)
            if not records:
                results["success"] = True
                return results

            # 2. Check Quota BEFORE processing (prevents race conditions)
            # Estimated cost for Deep ingestion (GraphRAG)
            estimated_deep_acu = 0.5
            quota_check = await self.usage_tracker.check_quota_before_job(
                integration_id=integration_id, estimated_acu=estimated_deep_acu
            )

            # 3. Basic Tier - LanceDB Indexing (ALWAYS)
            for record in records:
                text = self._record_to_text(record, integration_id)

                # 3.1. SPECIAL CASE: Communication Apps (Outlook, Gmail, Slack, Teams)
                # These use the specialized CommunicationIngestionPipeline for LanceDB/Hub persistence
                if integration_id in ("outlook", "gmail", "slack", "microsoft_teams"):
                    try:
                        from integrations.atom_communication_ingestion_pipeline import (
                            get_ingestion_pipeline,
                        )

                        comm_pipeline = get_ingestion_pipeline(self.tenant_id)
                        # ingest_message handles normalization and LanceDB/Postgres persistence
                        comm_pipeline.ingest_message(integration_id, record)
                        results["records_processed"] += 1
                        results["tier"] = "basic"
                        continue  # Skip standard indexing as it's now handled
                    except Exception as bridge_err:
                        logger.error(
                            f"Failed to bridge webhook to CommunicationIngestionPipeline: {bridge_err}"
                        )

                # 3.2. Standard Indexing for all other integration types (or fallback)
                if text and len(text) >= 10:
                    results["records_processed"] += 1
                    # Index in LanceDB for searchability (Lite mode)
                    self.lancedb.add_document(
                        table_name=f"tenant_{self.tenant_id}_messages",
                        text=text,
                        source=f"{integration_id}_webhook",
                        metadata={
                            "integration_id": integration_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "sender_id": record.get("sender_id", "unknown"),
                            "direction": record.get("direction", "inbound"),
                        },
                        user_id=self.tenant_id,
                        workspace_id=self.workspace_id,
                        extract_knowledge=False,  # CRITICAL: Basic tier only
                        skip_ai_triggers=True,  # Prevent workflow loops
                    )

            results["tier"] = "basic"

            # 4. Deep Tier - GraphRAG (always run for real-time webhooks)
            # Entity extraction (_extract_structured_entities) is non-LLM and cheap,
            # so we always run it for real-time data regardless of quota.
            entities = []
            relationships = []
            webhook_ingested_ids = []

            for record in records:
                text = self._record_to_text(record, integration_id)
                record_id = str(record.get("id", ""))  # Convert UUID to string
                if record_id and self._is_doc_already_ingested(self.workspace_id, record_id, text):
                    continue

                # Phase 323: High-performance Multi-Entity Extraction (Advanced)
                # Same pipeline process as backfill to ensure semantic data and review queue parity
                if integration_id in MULTI_ENTITY_INTEGRATIONS:
                    job_id = f"webhook_{int(datetime.now(timezone.utc).timestamp())}"
                    await self._process_multi_entity_extraction(
                        record, integration_id, text, job_id
                    )

                entity, rel = self._extract_structured_entities(record, integration_id, text)
                if entity:
                    entities.append(entity)
                if rel:
                    relationships.append(rel)
                if record_id:
                    webhook_ingested_ids.append((record_id, text))

            if entities or relationships:
                self.graphrag.ingest_structured_data(
                    workspace_id=self.workspace_id, entities=entities, relationships=relationships
                )
                results["entities_extracted"] = len(entities)
                results["relationships_extracted"] = len(relationships)
                results["tier"] = "deep"

                # Record successful ingestion for document-level idempotency
                for wid, wtext in webhook_ingested_ids:
                    self._record_doc_ingestion(self.workspace_id, wid, wtext, integration_id)

            # 4.5. LLM-Powered Extraction - extract meaningful entities
            # (people, organizations, topics) from message content.
            # Requires Solo+ tier AND BYOK/OpenAI key; silently skipped if unavailable.
            session = SessionLocal()
            try:
                tenant = session.query(Tenant).filter(Tenant.id == self.tenant_id).first()
                plan_type = tenant.plan_type or "free" if tenant else "free"
            except Exception:
                plan_type = "free"
            finally:
                session.close()

            TIER_ORDER = {"free": 0, "solo": 1, "team": 2, "enterprise": 3}
            if TIER_ORDER.get(plan_type, 0) >= 1:
                llm_entities = 0
                for record in records:
                    text = self._record_to_text(record, integration_id)
                    if text and len(text) > 50:
                        try:
                            await self.graphrag.ingest_document(
                                workspace_id=self.workspace_id,
                                doc_id=str(
                                    record.get("id", str(uuid.uuid4()))
                                ),  # Convert UUID to string
                                text=text,
                                source=f"{integration_id}_realtime",
                            )
                            llm_entities += 1
                        except Exception as llm_err:
                            logger.debug(
                                f"LLM extraction skipped for {integration_id} record: {llm_err}"
                            )

                if llm_entities:
                    results["llm_entities_extracted"] = llm_entities
                    if results["tier"] != "deep":
                        results["tier"] = "deep"

            # 5. Track ACU Usage
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            use_lite_rates = results["tier"] == "basic"

            # Simple approximation for tokens
            total_tokens = results["records_processed"] * 300

            acu_consumed = self.usage_tracker.calculate_acu_consumed(
                llm_calls=results["entities_extracted"] + results.get("relationships_extracted", 0),
                total_tokens=total_tokens,
                processing_duration_ms=duration_ms,
                use_lite_rates=use_lite_rates,
            )

            await self.usage_tracker.track_acu_usage(
                job_id=f"webhook_tiered_{uuid.uuid4()}",
                job_type=f"webhook_ingestion_{results['tier']}",
                integration_id=integration_id,
                acu_consumed=acu_consumed,
                total_tokens=total_tokens,
                processing_duration_ms=duration_ms,
                records_processed=results["records_processed"],
                entities_extracted=results["entities_extracted"],
                use_lite_rates=use_lite_rates,
            )

            results["success"] = True
            results["acu_consumed"] = acu_consumed

        except Exception as e:
            logger.error(f"Tiered webhook processing failed for {integration_id}: {e}")
            results["error"] = str(e)

        return results

    async def _transform_webhook_payload(
        self, integration_id: str, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Transform webhook payload into standardized record format.

        Dispatches to integration-specific transformer based on integration_id.
        Each transformer extracts relevant data from webhook payload.

        Args:
            integration_id: Integration identifier
            webhook_data: Raw webhook payload

        Returns:
            List of standardized record dicts

        CRITICAL: Tenant_id is enforced for multi-tenant security.
        """
        import sys

        print(
            f"[FATAL_DEBUG] _transform_webhook_payload ENTERED: integration_id={integration_id}, webhook_data keys={list(webhook_data.keys())}",
            file=sys.stderr,
            flush=True,
        )
        # Integration-specific payload transformers
        transformers = {
            # Existing (from 220-04)
            "slack": self._transform_slack_payload,
            "hubspot": self._transform_hubspot_payload,
            "salesforce": self._transform_salesforce_payload,
            "gmail": self._transform_gmail_payload,
            "notion": self._transform_notion_payload,
            # Zoho Suite (10 integrations)
            "zoho_crm": self._transform_zoho_crm_payload,
            "zoho_books": self._transform_zoho_books_payload,
            "zoho_projects": self._transform_zoho_projects_payload,
            "zoho_desk": self._transform_zoho_desk_payload,
            "zoho_recruit": self._transform_zoho_recruit_payload,
            "zoho_campaigns": self._transform_zoho_campaigns_payload,
            "zoho_forms": self._transform_zoho_forms_payload,
            "zoho_showtime": self._transform_zoho_showtime_payload,
            "zoho_meeting": self._transform_zoho_meeting_payload,
            "zoho_assist": self._transform_zoho_assist_payload,
            # Project Management (5 integrations)
            "jira": self._transform_jira_payload,
            "asana": self._transform_asana_payload,
            "trello": self._transform_trello_payload,
            "monday": self._transform_monday_payload,
            "clickup": self._transform_clickup_payload,
            "linear": self._transform_linear_payload,
            # CRM & Sales (5 integrations)
            "pipedrive": self._transform_pipedrive_payload,
            "zendesk_sell": self._transform_zendesk_sell_payload,
            "insightly": self._transform_insightly_payload,
            "freshsales": self._transform_freshsales_payload,
            "salesloft": self._transform_salesloft_payload,
            # Marketing (5 integrations)
            "mailchimp": self._transform_mailchimp_payload,
            "activecampaign": self._transform_activecampaign_payload,
            "sendgrid": self._transform_sendgrid_payload,
            "convertkit": self._transform_convertkit_payload,
            "getresponse": self._transform_getresponse_payload,
            # Communication (5 integrations)
            "discord": self._transform_discord_payload,
            "teams": self._transform_teams_payload,
            "telegram": self._transform_telegram_payload,
            "twilio": self._transform_twilio_payload,
            "whatsapp": self._transform_whatsapp_payload,
            "intercom": self._transform_intercom_payload,
            # Development (5 integrations)
            "github": self._transform_github_payload,
            "gitlab": self._transform_gitlab_payload,
            "bitbucket": self._transform_bitbucket_payload,
            # Productivity (5 integrations)
            "google_drive": self._transform_google_drive_payload,
            "dropbox": self._transform_dropbox_payload,
            "box": self._transform_box_payload,
            "onedrive": self._transform_onedrive_payload,
            # E-commerce (5 integrations)
            "shopify": self._transform_shopify_payload,
            "woocommerce": self._transform_woocommerce_payload,
            "bigcommerce": self._transform_bigcommerce_payload,
            "magento": self._transform_magento_payload,
            "stripe": self._transform_stripe_payload,
            # Additional Integrations
            "airtable": self._transform_airtable_payload,
            "webex": self._transform_webex_payload,
            "zoom": self._transform_zoom_payload,
            "freshdesk": self._transform_freshdesk_payload,
            "figma": self._transform_figma_payload,
            "outlook": self._transform_outlook_payload,
        }

        # Get the transformer for this integration
        transformer = transformers.get(integration_id)
        if not transformer:
            logger.warning(
                f"No webhook payload transformer for {integration_id}", tenant_id=self.tenant_id
            )
            return []

        try:
            records = await transformer(webhook_data)
            if not records:
                return []

            # CENTRAL STANDARDIZER FOR PHASE 3 (FORMAT ALIGNMENT)
            standardized_records = []
            for record in records:
                if not isinstance(record, dict):
                    continue

                # 1. Guarantee string id
                rec_id = record.get("id")
                if rec_id is not None:
                    rec_id = str(rec_id)
                else:
                    rec_id = ""

                # 2. Extract sender_id / author / user / creator / email / from
                sender_id = (
                    record.get("sender_id")
                    or record.get("user")
                    or record.get("user_id")
                    or record.get("email")
                    or record.get("from")
                    or record.get("creator")
                    or record.get("author")
                    or (record.get("properties") or {}).get("email")
                    or ""
                )
                sender_id = str(sender_id) if sender_id is not None else ""

                # 3. Extract subject / title / name / topic
                subject = (
                    record.get("subject")
                    or record.get("title")
                    or record.get("name")
                    or record.get("topic")
                    or record.get("event_type")
                    or record.get("type")
                    or ""
                )
                subject = str(subject) if subject is not None else ""

                # 4. Extract content / text / summary / description / body
                content = (
                    record.get("content")
                    or record.get("text")
                    or record.get("summary")
                    or record.get("description")
                    or record.get("body")
                    or ""
                )
                # If content is a dict (like Outlook body), extract string
                if isinstance(content, dict):
                    content = (
                        content.get("content")
                        or content.get("text")
                        or content.get("body")
                        or content.get("value")
                        or ""
                    )
                content = str(content) if content is not None else ""

                # 5. Extract timestamp / date / ts / created_at
                timestamp = (
                    record.get("timestamp")
                    or record.get("ts")
                    or record.get("date")
                    or record.get("created_at")
                    or ""
                )
                timestamp = str(timestamp) if timestamp is not None else ""

                # 6. Extract and sanitize metadata
                # Merge existing metadata, properties, changes, or raw fields
                metadata = {}
                for k in ["metadata", "properties", "changes", "raw"]:
                    val = record.get(k)
                    if isinstance(val, dict):
                        for inner_k, inner_v in val.items():
                            metadata[inner_k] = str(inner_v) if isinstance(inner_v, object) and type(inner_v).__name__ == "UUID" else inner_v
                    elif isinstance(val, list):
                        metadata[k] = [str(item) if isinstance(item, object) and type(item).__name__ == "UUID" else item for item in val]
                    elif val is not None:
                        metadata[k] = str(val) if isinstance(val, object) and type(val).__name__ == "UUID" else val

                # Include other flat keys from record into metadata for preservation
                for k, val in record.items():
                    if k not in ["id", "sender_id", "subject", "content", "timestamp", "metadata", "properties", "changes", "raw"]:
                        metadata[k] = str(val) if isinstance(val, object) and type(val).__name__ == "UUID" else val

                # Ensure all values in metadata are sanitized for UUID serialization
                sanitized_metadata = {}
                for k, val in metadata.items():
                    if isinstance(val, dict):
                        sanitized_metadata[k] = {
                            inner_k: (str(inner_v) if type(inner_v).__name__ == "UUID" else inner_v)
                            for inner_k, inner_v in val.items()
                        }
                    elif isinstance(val, list):
                        sanitized_metadata[k] = [
                            (str(item) if type(item).__name__ == "UUID" else item)
                            for item in val
                        ]
                    elif type(val).__name__ == "UUID":
                        sanitized_metadata[k] = str(val)
                    else:
                        sanitized_metadata[k] = val

                # Build standardized record preserving all custom fields at the top level
                standardized_record = {
                    **record,  # Preserve all original fields for backward compatibility
                    "id": rec_id,
                    "sender_id": sender_id,
                    "subject": subject,
                    "content": content,
                    "timestamp": timestamp,
                    "metadata": sanitized_metadata,
                }
                standardized_records.append(standardized_record)

            return standardized_records
        except Exception as e:
            logger.error(
                f"Webhook payload transformation failed for {integration_id}: {e} (tenant={self.tenant_id[:8]})"
            )
            return []

    async def _transform_slack_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform Slack webhook payload to records.

        Extracts message data from Slack events (message, team, channel, user, timestamp).

        Args:
            webhook_data: Slack event webhook payload

        Returns:
            List of record dicts with type, id, text, channel, user, timestamp
        """
        records = []

        # Extract event type
        event_type = webhook_data.get("type", "")
        event = webhook_data.get("event", {})

        # Handle message events
        if event_type == "event_callback" and event.get("type") == "message":
            record = {
                "type": "slack_message",
                "id": event.get("client_msg_id") or event.get("ts"),
                "text": event.get("text", ""),
                "channel": event.get("channel"),
                "user": event.get("user"),
                "team": webhook_data.get("team_id"),
                "timestamp": event.get("ts"),
                "event_type": "message",
            }
            records.append(record)

        logger.debug(
            f"Transformed Slack webhook payload: {len(records)} records", tenant_id=self.tenant_id
        )

        return records

    async def _transform_hubspot_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Transform HubSpot webhook payload to records.

        Extracts contact/company/deal data from HubSpot CRM events.

        Args:
            webhook_data: HubSpot CRM webhook payload

        Returns:
            List of record dicts with type, id, object_type, properties
        """
        records = []

        # HubSpot webhooks can contain multiple events
        events = webhook_data if isinstance(webhook_data, list) else [webhook_data]

        for event in events:
            subscription_type = event.get("subscriptionType")
            object_id = event.get("objectId")

            # Extract object data based on subscription type
            record = {
                "type": f"hubspot_{subscription_type}",
                "id": object_id,
                "object_type": subscription_type,  # contact, company, deal
                "properties": event.get("properties", {}),
                "event_type": subscription_type,
            }
            records.append(record)

        logger.debug(
            f"Transformed HubSpot webhook payload: {len(records)} records", tenant_id=self.tenant_id
        )

        return records

    async def _transform_salesforce_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Transform Salesforce webhook payload to records.

        Extracts record data from Salesforce event notifications (Account, Contact, Lead, Opportunity).

        Args:
            webhook_data: Salesforce event webhook payload

        Returns:
            List of record dicts with type, id, object_type, changes
        """
        records = []

        # Salesforce event notifications
        event_type = webhook_data.get("eventType", "")
        object_type = webhook_data.get("objectType", "")  # Account, Contact, Lead, Opportunity
        record_id = webhook_data.get("recordIds", [])

        for rec_id in record_id:
            record = {
                "type": f"salesforce_{object_type.lower()}",
                "id": rec_id,
                "object_type": object_type,
                "event_type": event_type,
                "changes": webhook_data.get("changeEventHeader", {}).get("changeTypes", []),
                "properties": webhook_data.get("payload", {}),
            }
            records.append(record)

        logger.debug(
            f"Transformed Salesforce webhook payload: {len(records)} records",
            tenant_id=self.tenant_id,
        )

        return records

    async def _transform_gmail_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform Gmail webhook payload to records.

        Extracts email data from Gmail push notifications.

        Args:
            webhook_data: Gmail push notification payload

        Returns:
            List of record dicts with type, id, thread_id, message_id, subject, from, to
        """
        records = []

        history_id = webhook_data.get("historyId")
        source_connection_id = webhook_data.get("_source_connection_id")

        if source_connection_id and history_id:
            try:
                # 1. Fetch history from Gmail API using startHistoryId
                history_data = await self._fetch_gmail_resource_direct(
                    source_connection_id,
                    f"users/me/history?startHistoryId={history_id}"
                )

                if history_data and "history" in history_data:
                    # Collect all message IDs that were added
                    message_ids = []
                    for hist in history_data["history"]:
                        for msg_added in hist.get("messagesAdded", []):
                            msg_id = msg_added.get("message", {}).get("id")
                            if msg_id:
                                message_ids.append(msg_id)

                    # Fetch detail for each message
                    for msg_id in message_ids:
                        msg_detail = await self._fetch_gmail_resource_direct(
                            source_connection_id,
                            f"users/me/messages/{msg_id}"
                        )
                        if msg_detail:
                            # Extract headers
                            headers = msg_detail.get("payload", {}).get("headers", [])
                            header_dict = {h["name"].lower(): h["value"] for h in headers}

                            # Extract subject, from, to
                            subject = header_dict.get("subject", "No Subject")
                            sender = header_dict.get("from", "")
                            to_recipients = header_dict.get("to", "")

                            # Extract snippet or body content
                            content = msg_detail.get("snippet", "")

                            # Resolve timestamp
                            internal_date = msg_detail.get("internalDate")
                            timestamp = None
                            if internal_date:
                                try:
                                    timestamp = datetime.fromtimestamp(
                                        float(internal_date) / 1000.0,
                                        tz=timezone.utc
                                    ).isoformat()
                                except Exception:
                                    pass

                            records.append({
                                "type": "gmail_message",
                                "id": msg_id,
                                "thread_id": msg_detail.get("threadId"),
                                "message_id": msg_id,
                                "subject": subject,
                                "content": content,
                                "from": sender,
                                "to": to_recipients,
                                "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
                                "event_type": "message_received",
                                "metadata": msg_detail,
                            })
            except Exception as e:
                logger.error(f"Failed to fetch Gmail webhook message details: {e}")

        # Fallback if direct fetch fails or source_connection_id is missing
        if not records:
            email_address = webhook_data.get("emailAddress")
            records.append({
                "type": "gmail_message",
                "id": str(history_id or "gmail_unknown"),
                "thread_id": str(history_id or "gmail_unknown"),
                "message_id": str(history_id or "gmail_unknown"),
                "subject": "New email notification",
                "from": email_address,
                "to": email_address,
                "event_type": "message_received",
            })

        logger.debug(
            f"Transformed Gmail webhook payload: {len(records)} records (tenant={self.tenant_id})"
        )
        return records

    async def _transform_notion_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform Notion webhook payload to records.

        Extracts page/database data from Notion webhook events.

        Args:
            webhook_data: Notion webhook payload

        Returns:
            List of record dicts with type, id, title, properties
        """
        records = []

        # Notion webhook structure
        activity_type = webhook_data.get("activity_type", "")
        workspace_id = webhook_data.get("workspace_id", "")

        # Extract page/database details
        record = {
            "type": "notion_page",
            "id": webhook_data.get("id", ""),
            "title": webhook_data.get("title", ""),
            "object_type": "page",
            "properties": webhook_data.get("properties", {}),
            "event_type": activity_type,
        }
        records.append(record)

        logger.debug(
            f"Transformed Notion webhook payload: {len(records)} records", tenant_id=self.tenant_id
        )

        return records

    # =========================================================================
    # Zoho Suite Transformers (10 integrations)
    # =========================================================================

    async def _transform_zoho_crm_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho CRM webhook payload to records."""
        records = []
        module_name = webhook_data.get("module", {}).get("api_name", "")
        record_id = webhook_data.get("key_id", "")

        record = {
            "type": f"zoho_crm_{module_name.lower()}",
            "id": record_id,
            "object_type": module_name,  # Leads, Contacts, Deals, etc.
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("operation", ""),
        }
        records.append(record)
        return records

    async def _transform_zoho_books_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho Books webhook payload to records."""
        records = []
        module_name = webhook_data.get("module", "")
        record_id = webhook_data.get("IDs", {}).get("entity_id", "")

        record = {
            "type": f"zoho_books_{module_name.lower()}",
            "id": record_id,
            "object_type": module_name,  # Invoices, Estimates, etc.
            "properties": webhook_data.get("payload", {}),
            "event_type": webhook_data.get("event_type", ""),
        }
        records.append(record)
        return records

    async def _transform_zoho_projects_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho Projects webhook payload to records."""
        records = []
        project_id = webhook_data.get("project_id", "")
        module_name = webhook_data.get("module", "")

        record = {
            "type": f"zoho_projects_{module_name.lower()}",
            "id": webhook_data.get("id", ""),
            "project_id": project_id,
            "object_type": module_name,  # Tasks, Milestones
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("operation", ""),
        }
        records.append(record)
        return records

    async def _transform_zoho_desk_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho Desk webhook payload to records."""
        records = []
        ticket_id = webhook_data.get("ticketId", "")

        record = {
            "type": "zoho_desk_ticket",
            "id": ticket_id,
            "object_type": "ticket",
            "properties": webhook_data.get("ticket", {}),
            "event_type": webhook_data.get("action", ""),
        }
        records.append(record)
        return records

    async def _transform_zoho_recruit_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho Recruit webhook payload to records."""
        records = []
        module_name = webhook_data.get("module", "")

        record = {
            "type": f"zoho_recruit_{module_name.lower()}",
            "id": webhook_data.get("entityId", ""),
            "object_type": module_name,  # Candidates, Job Openings
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("operation", ""),
        }
        records.append(record)
        return records

    async def _transform_zoho_campaigns_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho Campaigns webhook payload to records."""
        records = []

        record = {
            "type": "zoho_campaigns_campaign",
            "id": webhook_data.get("campaign_id", ""),
            "object_type": "campaign",
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("event_type", ""),
        }
        records.append(record)
        return records

    async def _transform_zoho_forms_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho Forms webhook payload to records."""
        records = []

        record = {
            "type": "zoho_forms_submission",
            "id": webhook_data.get("submission_id", ""),
            "object_type": "form_submission",
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("event_type", ""),
        }
        records.append(record)
        return records

    async def _transform_zoho_showtime_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho ShowTime webhook payload to records."""
        records = []

        record = {
            "type": "zoho_showtime_session",
            "id": webhook_data.get("session_id", ""),
            "object_type": "training_session",
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("event_type", ""),
        }
        records.append(record)
        return records

    async def _transform_zoho_meeting_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho Meeting webhook payload to records."""
        records = []

        record = {
            "type": "zoho_meeting_session",
            "id": webhook_data.get("meeting_id", ""),
            "object_type": "meeting",
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("event_type", ""),
        }
        records.append(record)
        return records

    async def _transform_zoho_assist_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zoho Assist webhook payload to records."""
        records = []

        record = {
            "type": "zoho_assist_session",
            "id": webhook_data.get("session_id", ""),
            "object_type": "support_session",
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("event_type", ""),
        }
        records.append(record)
        return records

    # =========================================================================
    # Project Management Transformers (6 integrations)
    # =========================================================================

    async def _transform_jira_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Jira webhook payload to records."""
        records = []
        issue = webhook_data.get("issue", {})

        record = {
            "type": "jira_issue",
            "id": issue.get("id", ""),
            "key": issue.get("key", ""),
            "summary": issue.get("fields", {}).get("summary", ""),
            "status": issue.get("fields", {}).get("status", {}).get("name", ""),
            "assignee": issue.get("fields", {}).get("assignee", {}).get("displayName", ""),
            "object_type": "issue",
            "properties": issue,
            "event_type": webhook_data.get("webhookEvent", ""),
        }
        records.append(record)
        return records

    async def _transform_asana_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Asana webhook payload to records."""
        records = []

        record = {
            "type": "asana_task",
            "id": webhook_data.get("gid", ""),
            "name": webhook_data.get("name", ""),
            "completed": webhook_data.get("completed", False),
            "object_type": "task",
            "properties": webhook_data,
            "event_type": webhook_data.get("action", ""),
        }
        records.append(record)
        return records

    async def _transform_trello_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Trello webhook payload to records."""
        records = []
        action = webhook_data.get("action", {})
        card = action.get("data", {}).get("card", {})

        record = {
            "type": "trello_card",
            "id": card.get("id", ""),
            "name": card.get("name", ""),
            "list_id": action.get("data", {}).get("listAfter", {}).get("id", ""),
            "object_type": "card",
            "properties": card,
            "event_type": action.get("type", ""),
        }
        records.append(record)
        return records

    async def _transform_monday_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Monday webhook payload to records."""
        records = []
        event = webhook_data.get("event", {})
        payload = webhook_data.get("payload", {})

        record = {
            "type": "monday_item",
            "id": payload.get("item_id", ""),
            "name": payload.get("item_name", ""),
            "board_id": payload.get("board_id", ""),
            "column_values": payload.get("column_values", {}),
            "object_type": "item",
            "properties": payload,
            "event_type": event.get("type", ""),
        }
        records.append(record)
        return records

    async def _transform_clickup_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform ClickUp webhook payload to records."""
        records = []
        task = webhook_data.get("task", {})

        record = {
            "type": "clickup_task",
            "id": task.get("id", ""),
            "name": task.get("name", ""),
            "status": task.get("status", ""),
            "object_type": "task",
            "properties": task,
            "event_type": webhook_data.get("event", ""),
        }
        records.append(record)
        return records

    async def _transform_linear_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Linear webhook payload to records."""
        records = []
        data = webhook_data.get("data", {})

        record = {
            "type": "linear_issue",
            "id": data.get("id", ""),
            "title": data.get("title", ""),
            "state": data.get("state", {}).get("name", ""),
            "object_type": "issue",
            "properties": data,
            "event_type": webhook_data.get("action", ""),
        }
        records.append(record)
        return records

    # =========================================================================
    # CRM & Sales Transformers (5 integrations)
    # =========================================================================

    async def _transform_pipedrive_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Pipedrive webhook payload to records."""
        records = []
        current = webhook_data.get("current", {})

        record = {
            "type": f"pipedrive_{webhook_data.get('object', '').lower()}",
            "id": current.get("id", ""),
            "title": current.get("title", ""),
            "value": current.get("value", ""),
            "object_type": webhook_data.get("object", ""),  # deal, activity, person
            "properties": current,
            "event_type": webhook_data.get("event", ""),
        }
        records.append(record)
        return records

    async def _transform_zendesk_sell_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Zendesk Sell webhook payload to records."""
        records = []
        payload = webhook_data.get("payload", "")

        record = {
            "type": f"zendesk_sell_{webhook_data.get('target_type', '').lower()}",
            "id": webhook_data.get("target_id", ""),
            "object_type": webhook_data.get("target_type", ""),  # lead, deal
            "properties": {"payload": payload},
            "event_type": webhook_data.get("trigger", ""),
        }
        records.append(record)
        return records

    async def _transform_insightly_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Insightly webhook payload to records."""
        records = []

        record = {
            "type": f"insightly_{webhook_data.get('object_name', '').lower()}",
            "id": webhook_data.get("record_id", ""),
            "object_type": webhook_data.get("object_name", ""),  # contact, project
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("event", ""),
        }
        records.append(record)
        return records

    async def _transform_freshsales_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Freshsales webhook payload to records."""
        records = []
        payload = webhook_data.get("payload", {})

        record = {
            "type": f"freshsales_{webhook_data.get('entity_type', '').lower()}",
            "id": payload.get("id", ""),
            "object_type": webhook_data.get("entity_type", ""),  # deal, contact
            "properties": payload,
            "event_type": webhook_data.get("action", ""),
        }
        records.append(record)
        return records

    async def _transform_salesloft_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Salesloft webhook payload to records."""
        records = []
        data = webhook_data.get("data", {})

        record = {
            "type": "salesloft_cadence",
            "id": data.get("id", ""),
            "name": data.get("name", ""),
            "object_type": "cadence",
            "properties": data,
            "event_type": webhook_data.get("event", {}).get("action", ""),
        }
        records.append(record)
        return records

    # =========================================================================
    # Marketing Transformers (5 integrations)
    # =========================================================================

    async def _transform_mailchimp_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Mailchimp webhook payload to records."""
        records = []

        record = {
            "type": f"mailchimp_{webhook_data.get('type', '').lower()}",
            "id": webhook_data.get("data", {}).get("id", ""),
            "email": webhook_data.get("data", {}).get("email", ""),
            "object_type": webhook_data.get("type", ""),  # subscribe, unsubscribe
            "properties": webhook_data.get("data", {}),
            "event_type": webhook_data.get("type", ""),
        }
        records.append(record)
        return records

    async def _transform_activecampaign_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform ActiveCampaign webhook payload to records."""
        records = []

        record = {
            "type": "activecampaign_contact",
            "id": webhook_data.get("contact", {}).get("id", ""),
            "email": webhook_data.get("contact", {}).get("email", ""),
            "object_type": "contact",
            "properties": webhook_data,
            "event_type": webhook_data.get("type", ""),
        }
        records.append(record)
        return records

    async def _transform_sendgrid_payload(
        self, webhook_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Transform SendGrid webhook payload to records."""
        records = []

        # SendGrid sends events as an array
        events = webhook_data if isinstance(webhook_data, list) else [webhook_data]

        for event in events:
            record = {
                "type": "sendgrid_email_event",
                "id": event.get("sg_message_id", ""),
                "email": event.get("email", ""),
                "event_type": event.get("event", ""),  # delivered, open, click
                "object_type": "email_event",
                "properties": event,
            }
            records.append(record)

        return records

    async def _transform_convertkit_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform ConvertKit webhook payload to records."""
        records = []

        record = {
            "type": "convertkit_subscriber",
            "id": webhook_data.get("subscriber", {}).get("id", ""),
            "email": webhook_data.get("subscriber", {}).get("email_address", ""),
            "object_type": "subscriber",
            "properties": webhook_data,
            "event_type": webhook_data.get("event", {}).get("name", ""),
        }
        records.append(record)
        return records

    async def _transform_getresponse_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform GetResponse webhook payload to records."""
        records = []

        record = {
            "type": "getresponse_contact",
            "id": webhook_data.get("contact", {}).get("contact_id", ""),
            "email": webhook_data.get("contact", {}).get("email", ""),
            "object_type": "contact",
            "properties": webhook_data,
            "event_type": webhook_data.get("event", "").get("name", ""),
        }
        records.append(record)
        return records

    # =========================================================================
    # Communication Transformers (5 integrations)
    # =========================================================================

    async def _transform_discord_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Discord webhook payload to records."""
        records = []

        record = {
            "type": "discord_message",
            "id": webhook_data.get("id", ""),
            "content": webhook_data.get("content", ""),
            "author": webhook_data.get("author", {}).get("username", ""),
            "channel_id": webhook_data.get("channel_id", ""),
            "object_type": "message",
            "properties": webhook_data,
            "event_type": "message_created",
        }
        records.append(record)
        return records

    async def _transform_teams_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Microsoft Teams webhook payload to records."""
        records = []

        record = {
            "type": "teams_message",
            "id": webhook_data.get("id", ""),
            "text": webhook_data.get("text", ""),
            "from": webhook_data.get("from", {}).get("application", {}).get("displayName", ""),
            "object_type": "message",
            "properties": webhook_data,
            "event_type": "message_created",
        }
        records.append(record)
        return records

    async def _transform_telegram_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Telegram webhook payload to records.

        Handles both private messages (``message``) and channel posts
        (``channel_post``), and enriches the record with structured sender/chat
        metadata so the knowledge graph can model sender↔message relationships.
        """
        records = []
        message = webhook_data.get("message") or webhook_data.get("channel_post") or {}
        if not message:
            return records

        sender = message.get("from", {}) or {}
        chat = message.get("chat", {}) or {}
        text = message.get("text", "") or message.get("caption", "")
        media_type = None
        media_id = None
        for key in ("photo", "video", "voice", "document", "audio", "sticker"):
            if key in message:
                media_type = key
                # photo is a list of sizes; take the largest file_id.
                media_obj = message[key]
                if isinstance(media_obj, list) and media_obj:
                    media_id = media_obj[-1].get("file_id")
                elif isinstance(media_obj, dict):
                    media_id = media_obj.get("file_id")
                break

        record = {
            "type": "telegram_message",
            "id": str(message.get("message_id", "")),
            "name": f"Telegram from {sender.get('username') or sender.get('first_name', 'unknown')}",
            "text": text,
            "from": sender.get("username") or sender.get("first_name", ""),
            "from_id": str(sender.get("id", "")),
            "chat_id": str(chat.get("id", "")),
            "chat_title": chat.get("title") or chat.get("username", ""),
            "object_type": "message",
            "properties": {
                "message_id": message.get("message_id"),
                "text": text,
                "chat_id": chat.get("id"),
                "chat_title": chat.get("title") or chat.get("username"),
                "sender_id": sender.get("id"),
                "sender_name": sender.get("username") or sender.get("first_name"),
                "date": message.get("date"),
                "media_type": media_type,
                "media_id": media_id,
            },
            "event_type": "message_created",
        }
        records.append(record)
        return records

    async def _transform_twilio_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Twilio webhook payload to records."""
        records = []

        record = {
            "type": f"twilio_{webhook_data.get('MessageSid', '') and 'sms' or 'call'}",
            "id": webhook_data.get("MessageSid", webhook_data.get("CallSid", "")),
            "from": webhook_data.get("From", ""),
            "to": webhook_data.get("To", ""),
            "status": webhook_data.get("MessageStatus", webhook_data.get("CallStatus", "")),
            "object_type": "message" if "MessageSid" in webhook_data else "call",
            "properties": webhook_data,
            "event_type": webhook_data.get("MessageStatus", webhook_data.get("CallStatus", "")),
        }
        records.append(record)
        return records

    async def _transform_intercom_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Intercom webhook payload to records."""
        records = []
        data = webhook_data.get("data", {})

        record = {
            "type": "intercom_conversation",
            "id": data.get("id", ""),
            "subject": data.get("conversation_message", {}).get("subject", ""),
            "object_type": "conversation",
            "properties": data,
            "event_type": webhook_data.get("topic", ""),
        }
        records.append(record)
        return records

    # =========================================================================
    # Development Transformers (3 integrations)
    # =========================================================================

    async def _transform_github_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform GitHub webhook payload to records."""
        records = []

        # Handle different GitHub event types
        event_type = webhook_data.get("action", "push")

        if "pull_request" in webhook_data:
            pr = webhook_data.get("pull_request", {})
            record = {
                "type": "github_pull_request",
                "id": str(pr.get("number", "")),
                "title": pr.get("title", ""),
                "state": pr.get("state", ""),
                "object_type": "pull_request",
                "properties": pr,
                "event_type": f"pr_{webhook_data.get('action', '')}",
            }
        elif "issue" in webhook_data:
            issue = webhook_data.get("issue", {})
            record = {
                "type": "github_issue",
                "id": str(issue.get("number", "")),
                "title": issue.get("title", ""),
                "state": issue.get("state", ""),
                "object_type": "issue",
                "properties": issue,
                "event_type": f"issue_{webhook_data.get('action', '')}",
            }
        else:
            # Push event
            record = {
                "type": "github_push",
                "id": webhook_data.get("after", "")[:7],  # Short commit SHA
                "ref": webhook_data.get("ref", ""),
                "object_type": "push",
                "properties": webhook_data,
                "event_type": "push",
            }

        records.append(record)
        return records

    async def _transform_gitlab_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform GitLab webhook payload to records."""
        records = []

        object_kind = webhook_data.get("object_kind", "")

        if object_kind == "merge_request":
            mr = webhook_data.get("object_attributes", {})
            record = {
                "type": "gitlab_merge_request",
                "id": str(mr.get("iid", "")),
                "title": mr.get("title", ""),
                "state": mr.get("state", ""),
                "object_type": "merge_request",
                "properties": webhook_data,
                "event_type": f"mr_{mr.get('action', '')}",
            }
        elif object_kind == "issue":
            issue = webhook_data.get("object_attributes", {})
            record = {
                "type": "gitlab_issue",
                "id": str(issue.get("iid", "")),
                "title": issue.get("title", ""),
                "state": issue.get("state", ""),
                "object_type": "issue",
                "properties": webhook_data,
                "event_type": f"issue_{issue.get('action', '')}",
            }
        else:
            # Push event
            record = {
                "type": "gitlab_push",
                "id": webhook_data.get("after", "")[:7],
                "ref": webhook_data.get("ref", ""),
                "object_type": "push",
                "properties": webhook_data,
                "event_type": "push",
            }

        records.append(record)
        return records

    async def _transform_bitbucket_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Bitbucket webhook payload to records."""
        records = []

        if "pullrequest" in webhook_data:
            pr = webhook_data.get("pullrequest", {})
            record = {
                "type": "bitbucket_pull_request",
                "id": str(pr.get("id", "")),
                "title": pr.get("title", ""),
                "state": pr.get("state", ""),
                "object_type": "pull_request",
                "properties": pr,
                "event_type": f"pr_{webhook_data.get('action', '')}",
            }
        else:
            # Push event
            record = {
                "type": "bitbucket_push",
                "id": webhook_data.get("changes", [{}])[0].get("toHash", "")[:7],
                "ref": webhook_data.get("changes", [{}])[0].get("ref", {}).get("displayId", ""),
                "object_type": "push",
                "properties": webhook_data,
                "event_type": "push",
            }

        records.append(record)
        return records

    # =========================================================================
    # Productivity Transformers (4 integrations)
    # =========================================================================

    async def _transform_google_drive_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Google Drive webhook payload to records."""
        records = []

        record = {
            "type": "google_drive_file",
            "id": webhook_data.get("file_id", ""),
            "name": webhook_data.get("name", ""),
            "object_type": "file",
            "properties": webhook_data,
            "event_type": webhook_data.get("action", ""),
        }
        records.append(record)
        return records

    async def _transform_dropbox_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Dropbox webhook payload to records."""
        records = []

        record = {
            "type": "dropbox_file",
            "id": webhook_data.get("file_id", ""),
            "name": webhook_data.get("name", ""),
            "object_type": "file",
            "properties": webhook_data,
            "event_type": webhook_data.get("event_type", ""),
        }
        records.append(record)
        return records

    async def _transform_box_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Box webhook payload to records."""
        records = []

        record = {
            "type": "box_file",
            "id": webhook_data.get("file_id", ""),
            "name": webhook_data.get("file_name", ""),
            "object_type": "file",
            "properties": webhook_data,
            "event_type": webhook_data.get("event_type", ""),
        }
        records.append(record)
        return records

    async def _transform_onedrive_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform OneDrive webhook payload to records."""
        records = []

        record = {
            "type": "onedrive_file",
            "id": webhook_data.get("file_id", ""),
            "name": webhook_data.get("file_name", ""),
            "object_type": "file",
            "properties": webhook_data,
            "event_type": webhook_data.get("action", ""),
        }
        records.append(record)
        return records

    # =========================================================================
    # E-commerce Transformers (5 integrations)
    # =========================================================================

    async def _transform_shopify_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Shopify webhook payload to records."""
        records = []

        record = {
            "type": f"shopify_{webhook_data.get('topic', '').replace('/', '_')}",
            "id": webhook_data.get("id", ""),
            "email": webhook_data.get("email", ""),
            "total_price": webhook_data.get("total_price", ""),
            "object_type": "order",
            "properties": webhook_data,
            "event_type": webhook_data.get("topic", ""),
        }
        records.append(record)
        return records

    async def _transform_woocommerce_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform WooCommerce webhook payload to records."""
        records = []

        record = {
            "type": "woocommerce_order",
            "id": webhook_data.get("id", ""),
            "total": webhook_data.get("total", ""),
            "status": webhook_data.get("status", ""),
            "object_type": "order",
            "properties": webhook_data,
            "event_type": webhook_data.get("action", ""),
        }
        records.append(record)
        return records

    async def _transform_bigcommerce_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform BigCommerce webhook payload to records."""
        records = []
        data = webhook_data.get("data", {})

        record = {
            "type": "bigcommerce_order",
            "id": data.get("id", ""),
            "total": data.get("total_tax_inc", ""),
            "object_type": "order",
            "properties": data,
            "event_type": webhook_data.get("scope", ""),
        }
        records.append(record)
        return records

    async def _transform_magento_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Magento webhook payload to records."""
        records = []

        record = {
            "type": "magento_order",
            "id": webhook_data.get("entity_id", ""),
            "total": webhook_data.get("grand_total", ""),
            "object_type": "order",
            "properties": webhook_data,
            "event_type": webhook_data.get("event_name", ""),
        }
        records.append(record)
        return records

    async def _transform_stripe_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Stripe webhook payload to records."""
        records = []
        data_object = webhook_data.get("data", {}).get("object", {})

        record = {
            "type": f"stripe_{data_object.get('object', '')}",
            "id": data_object.get("id", ""),
            "amount": data_object.get("amount", ""),
            "currency": data_object.get("currency", ""),
            "object_type": data_object.get("object", ""),  # charge, payment_intent
            "properties": data_object,
            "event_type": webhook_data.get("type", ""),
        }
        records.append(record)
        return records

    # =========================================================================
    # Additional Integration Transformers (5 integrations)
    # =========================================================================

    async def _transform_airtable_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Airtable webhook payload to records."""
        records = []

        record = {
            "type": "airtable_record",
            "id": webhook_data.get("record_id", ""),
            "base_id": webhook_data.get("base_id", ""),
            "table_id": webhook_data.get("table_id", ""),
            "object_type": "record",
            "properties": webhook_data,
            "event_type": webhook_data.get("action", ""),
        }
        records.append(record)
        return records

    async def _transform_webex_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Webex webhook payload to records."""
        records = []
        data = webhook_data.get("data", {})

        record = {
            "type": "webex_message",
            "id": data.get("id", ""),
            "text": data.get("text", ""),
            "person_id": data.get("personId", ""),
            "object_type": "message",
            "properties": data,
            "event_type": webhook_data.get("name", ""),
        }
        records.append(record)
        return records

    async def _transform_zoom_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Zoom webhook payload to records."""
        records = []

        record = {
            "type": "zoom_meeting",
            "id": webhook_data.get("id", ""),
            "topic": webhook_data.get("topic", ""),
            "object_type": "meeting",
            "properties": webhook_data,
            "event_type": webhook_data.get("event", ""),
        }
        records.append(record)
        return records

    async def _transform_freshdesk_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Freshdesk webhook payload to records."""
        records = []

        record = {
            "type": "freshdesk_ticket",
            "id": webhook_data.get("ticket_id", ""),
            "subject": webhook_data.get("subject", ""),
            "status": webhook_data.get("status", ""),
            "object_type": "ticket",
            "properties": webhook_data,
            "event_type": webhook_data.get("trigger", ""),
        }
        records.append(record)
        return records

    async def _transform_figma_payload(self, webhook_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Transform Figma webhook payload to records."""
        records = []

        record = {
            "type": "figma_file",
            "id": webhook_data.get("file_key", ""),
            "name": webhook_data.get("file_name", ""),
            "object_type": "file",
            "properties": webhook_data,
            "event_type": webhook_data.get("event_type", ""),
        }
        records.append(record)
        return records

    async def _transform_outlook_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Transform Outlook webhook payload to records.

        Handles both pre-normalized data and raw Microsoft Graph notifications.
        If raw notification, fetches the full resource data from Graph API.
        """
        import sys

        print(
            f"[FATAL_DEBUG] _transform_outlook_payload ENTERED: keys={list(webhook_data.keys())}, has _source_connection_id={bool(webhook_data.get('_source_connection_id'))}",
            file=sys.stderr,
            flush=True,
        )
        records = []
        # Extract source_connection_id if available (for credentials resolution)
        source_connection_id = webhook_data.get("_source_connection_id")

        # 1. Detect if this is a raw Microsoft Graph notification
        resource_path = webhook_data.get("resource")
        if resource_path and "resourceData" in webhook_data:
            logger.info(f"Processing raw Outlook notification for resource: {resource_path}")
            try:
                # Fetch directly using ConnectionService + httpx (bypass integration_registry)
                # The v2 registry's get_service() doesn't accept connection_id, and returns
                # OutlookIntegration (not V2 with fetch_resource), so we fetch directly.
                full_data = await self._fetch_outlook_resource_direct(
                    source_connection_id, resource_path
                )
                if not full_data:
                    logger.warning(
                        f"Failed to fetch full data for Outlook resource: {resource_path}"
                    )
                    return []

                # Normalize the fetched data based on type
                resource_type = webhook_data.get("resourceData", {}).get("@odata.type", "")

                if "#Microsoft.Graph.Message" in resource_type:
                    sender = full_data.get("from", {}).get("emailAddress", {}).get("address")
                    # Produce the SAME flat format as _fetch_outlook_messages (backfill path).
                    # Both paths flow through CommunicationIngestionPipeline.ingest_message().
                    record = {
                        "id": str(full_data.get("id", "")),
                        "sender_id": sender,
                        "subject": full_data.get("subject", ""),
                        "content": full_data.get("bodyPreview")
                        or full_data.get("body", {}).get("content", ""),
                        "timestamp": full_data.get("receivedDateTime"),
                        "metadata": full_data,
                    }
                    records.append(record)
                elif "#Microsoft.Graph.Event" in resource_type:
                    record = {
                        "type": "calendar_event",
                        "id": str(full_data.get("id", "")),  # Convert UUID to string
                        "name": full_data.get("subject", "(No Subject)"),
                        "subject": full_data.get("subject", ""),
                        "text": full_data.get("body", {}).get("content", ""),
                        "event_type": "event_created",
                        "properties": {
                            "outlook_webhook": True,
                            "start": str(full_data.get("start", "")),  # Convert to string
                            "end": str(full_data.get("end", "")),  # Convert to string
                            "location": str(full_data.get("location", "")),  # Convert to string
                            # Note: 'raw' field removed - it contains UUID objects that cause JSON serialization errors
                        },
                    }
                    records.append(record)
                else:
                    # Fallback for generic drive items or other types
                    record = {
                        "type": "outlook_resource",
                        "id": str(full_data.get("id", "")),  # Convert UUID to string
                        "name": full_data.get("name", full_data.get("subject", "Outlook Item")),
                        "properties": {
                            "outlook_webhook": True,
                            # Note: 'raw' field removed - it contains UUID objects that cause JSON serialization errors
                        },
                        "event_type": "updated",
                    }
                    records.append(record)

            except Exception as e:
                logger.error(f"Failed to fetch Outlook resource {resource_path}: {e}")
                return []
        else:
            # 2. Handle pre-normalized data (existing behavior)
            record = {
                "type": "email",
                "id": webhook_data.get("id")
                or webhook_data.get("metadata", {}).get("conversation_id", ""),
                "name": webhook_data.get("subject", "(No Subject)"),
                "subject": webhook_data.get("subject", ""),
                "from": webhook_data.get("from", ""),
                "to": webhook_data.get("to", ""),
                "text": webhook_data.get("content", ""),
                "email": webhook_data.get("from", ""),
                "event_type": "message_received",
                "direction": webhook_data.get("direction", "inbound"),
                "properties": webhook_data.get("metadata", {}),
            }
            records.append(record)

        import sys

        print(
            f"[FATAL_DEBUG] _transform_outlook_payload RETURNING: {len(records)} records",
            file=sys.stderr,
            flush=True,
        )
        return records

    async def _fetch_outlook_resource_direct(
        self, connection_id: str | None, resource_path: str
    ) -> dict[str, Any] | None:
        """
        Fetch Outlook resource directly from Microsoft Graph API using credentials from UserConnection.

        Bypasses integration_registry which doesn't support connection_id parameter.
        Instead, queries UserConnection directly, decrypts credentials, and makes HTTP request.

        Args:
            connection_id: UserConnection ID to get credentials from
            resource_path: Graph API resource path (e.g., "Users/.../Messages/...")

        Returns:
            Resource data dict or None if fetch fails
        """
        if not connection_id:
            logger.warning("No connection_id provided for Outlook resource fetch")
            return None

        # Create a local db session if self.db is not set
        # (happens when pipeline is created from webhook worker without db param)
        close_session = False
        db = self.db
        if db is None:
            db = SessionLocal()
            close_session = True

        try:
            # 1. Get connection
            import httpx

            from core.connection_service import ConnectionService

            conn = (
                db.query(UserConnection)
                .filter(
                    UserConnection.id == connection_id,
                    UserConnection.tenant_id == self.tenant_id,
                    UserConnection.integration_id == "outlook",
                    UserConnection.status == "active",
                )
                .first()
            )

            if not conn:
                logger.warning(f"No active Outlook connection found for id={connection_id[:8]}...")
                return None

            # 2. Decrypt credentials directly
            conn_service = ConnectionService()
            creds = conn_service._decrypt(conn.credentials)

            if not creds:
                logger.warning(f"No credentials available for connection {connection_id[:8]}...")
                return None

            # 3. Refresh token if needed
            updated_creds = await conn_service._refresh_token_if_needed(conn, creds)
            if updated_creds:
                # Save updated credentials back to database
                conn.credentials = conn_service._encrypt(updated_creds)
                db.commit()
                creds = updated_creds

            access_token = creds.get("access_token")
            if not access_token:
                logger.warning(f"No access_token found in connection {connection_id[:8]}...")
                return None

            # 4. Make Graph API request
            # Normalize URL
            if resource_path.startswith("https://"):
                url = resource_path
            else:
                clean_path = resource_path.lstrip("/")
                url = f"https://graph.microsoft.com/v1.0/{clean_path}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )

                if response.status_code == 404:
                    logger.warning(f"Outlook resource not found: {resource_path}")
                    return {}

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching Outlook resource {resource_path}: {e.response.status_code}"
            )
            return None
        except Exception as e:
            logger.error(f"Error fetching Outlook resource {resource_path}: {e}")
            return None
        finally:
            if close_session:
                db.close()

    async def _fetch_gmail_resource_direct(
        self, connection_id: str | None, resource_path: str
    ) -> dict[str, Any] | None:
        """
        Fetch Gmail resource directly from Google APIs using credentials from UserConnection.

        Bypasses integration_registry which doesn't support connection_id parameter.
        Instead, queries UserConnection directly, decrypts credentials, and makes HTTP request.

        Args:
            connection_id: UserConnection ID to get credentials from
            resource_path: Gmail API resource path (e.g., "users/me/messages/...")

        Returns:
            Resource data dict or None if fetch fails
        """
        if not connection_id:
            logger.warning("No connection_id provided for Gmail resource fetch")
            return None

        # Create a local db session if self.db is not set
        close_session = False
        db = self.db
        if db is None:
            db = SessionLocal()
            close_session = True

        try:
            # 1. Get connection
            import httpx
            from core.connection_service import ConnectionService

            # RLS bypass for external queries
            from sqlalchemy import text
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = off"))

            conn = (
                db.query(UserConnection)
                .filter(
                    UserConnection.id == connection_id,
                    UserConnection.tenant_id == self.tenant_id,
                    UserConnection.integration_id == "gmail",
                    UserConnection.status == "active",
                )
                .first()
            )

            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))

            if not conn:
                logger.warning(f"No active Gmail connection found for id={connection_id[:8]}...")
                return None

            # 2. Decrypt credentials directly
            conn_service = ConnectionService()
            creds = conn_service._decrypt(conn.credentials)

            if not creds:
                logger.warning(f"No credentials available for connection {connection_id[:8]}...")
                return None

            # 3. Refresh token if needed
            updated_creds = await conn_service._refresh_token_if_needed(conn, creds)
            if updated_creds:
                # Save updated credentials back to database
                conn.credentials = conn_service._encrypt(updated_creds)
                db.commit()
                creds = updated_creds

            access_token = creds.get("access_token")
            if not access_token:
                logger.warning(f"No access_token found in connection {connection_id[:8]}...")
                return None

            # 4. Make Gmail API request
            if resource_path.startswith("https://"):
                url = resource_path
            else:
                clean_path = resource_path.lstrip("/")
                url = f"https://gmail.googleapis.com/gmail/v1/{clean_path}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )

                if response.status_code == 404:
                    logger.warning(f"Gmail resource not found: {resource_path}")
                    return {}

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching Gmail resource {resource_path}: {e.response.status_code}"
            )
            return None
        except Exception as e:
            logger.error(f"Error fetching Gmail resource {resource_path}: {e}")
            return None
        finally:
            if close_session:
                db.close()

    def _calculate_acu_consumed(
        self, llm_calls: int, total_tokens: int, processing_duration_ms: int
    ) -> float:
        """
        Calculate ACU consumed based on LLM usage and processing time.

        Formula: ACU = (tokens / 1000) * 0.5 + (duration_ms / 1000) * 0.1

        Args:
            llm_calls: Number of LLM API calls
            total_tokens: Total tokens (prompt + completion)
            processing_duration_ms: Processing duration in milliseconds

        Returns:
            ACU consumed
        """
        # Use UsageTrackingService's calculation method
        return self.usage_tracker.calculate_acu_consumed(
            llm_calls=llm_calls,
            total_tokens=total_tokens,
            processing_duration_ms=processing_duration_ms,
        )

    def _is_core_entity_type(self, entity_type: str) -> bool:
        """
        Check if entity type is a core entity type.

        Args:
            entity_type: Entity type name to check

        Returns:
            True if core type, False if custom
        """
        # Check against CORE_ENTITY_SCHEMAS keys
        for core_type in CORE_ENTITY_SCHEMAS.keys():
            if entity_type.lower() == core_type.lower():
                return True

        # Check against canonical types
        for schema in CORE_ENTITY_SCHEMAS.values():
            if entity_type.lower() == schema["canonical_type"].lower():
                return True

        return False

    async def _transform_whatsapp_payload(
        self, webhook_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Transform Meta WhatsApp webhook payload to standardized records.
        """
        records = []
        try:
            entries = webhook_data.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    # Handle messages
                    messages = value.get("messages", [])
                    for msg in messages:
                        record = {
                            "id": msg.get("id"),
                            "direction": "inbound",
                            "text": msg.get("text", {}).get("body", ""),
                            "sender_id": msg.get("from"),
                            "timestamp": msg.get("timestamp"),
                            "phone_number_id": value.get("metadata", {}).get("phone_number_id"),
                            "integration_id": "whatsapp",
                            "raw": msg,
                        }
                        records.append(record)
        except Exception as e:
            logger.error(f"Failed to transform WhatsApp payload: {e}")
        return records

    # --- Phase 323: High-Performance Extraction Helpers ---

    async def _extract_multi_entity_only(
        self,
        record: Dict[str, Any],
        integration_id: str,
        text: str,
        job_id: str,
        llm_service: Optional[Any] = None,
    ) -> List[DiscoveredEntity]:
        """
        Phase 1: Extract entities via LLM. NO DB ACCESS. Returns entities for caller to persist.

        Includes retry logic with fallback models (matches backfill pattern).
        """
        import sys

        print(
            f"[FATAL_DEBUG] _extract_multi_entity_only ENTERED: record_id={record.get('id')[:8]}, text_len={len(text)}",
            file=sys.stderr,
            flush=True,
        )

        # Use provided LLMService or the instance's LLMService (has tenant context)
        service = llm_service or self.multi_entity_extractor.llm

        # ── Retry loop with fallback models (matches backfill _llm_extract_with_handler) ──
        models_to_try = [
            "auto",
            "deepseek/deepseek-chat",
            "google/gemini-2.0-flash",
        ]

        email_data = {
            "id": str(record.get("id")),
            "subject": record.get("subject", ""),
            "from": record.get("from", ""),
            "to": record.get("to", []),
            "body": text,
        }

        discovered_data = None
        last_error = None

        for attempt, model in enumerate(models_to_try):
            logger.info(
                f"[LLM_RETRY] Attempt {attempt + 1}/{len(models_to_try)} using model={model} for record={record.get('id')[:8]} (tenant={self.tenant_id[:8]}, job={job_id})"
            )

            try:
                # Set integration_id on extractor so _parse_llm_response can use it
                # (it references self.integration_id which defaults to None)
                self.multi_entity_extractor.integration_id = integration_id
                # Build extraction prompt
                prompt = self.multi_entity_extractor._build_extraction_prompt(email_data)

                # Use LLMService.generate with retry model
                response_text = await service.generate(
                    prompt=prompt,
                    system_instruction=(
                        "You are an expert entity extraction system. "
                        "Extract business entities from emails with high precision. "
                        "Always return valid, parseable JSON."
                    ),
                    model=model,
                    task_type="extraction",
                    temperature=0.1,
                    max_tokens=2000,
                    tenant_id=self.tenant_id,
                    workspace_id=self.workspace_id,
                )

                # Log response preview
                resp_preview = (response_text or "")[:200]
                logger.info(
                    f"[LLM_RETRY] Response ({len(response_text or '')} chars): {resp_preview} (tenant={self.tenant_id[:8]}, job={job_id})"
                )

                # Check for empty response
                if not response_text or not response_text.strip():
                    logger.warning(
                        f"[LLM_RETRY] Attempt {attempt + 1} returned empty response (tenant={self.tenant_id[:8]}, job={job_id})"
                    )
                    last_error = "Empty LLM response"
                    continue

                # Set integration_id before parsing (required by MultiEntityLLMExtractor)
                self.multi_entity_extractor.integration_id = integration_id

                # Parse response into DiscoveredEntity instances
                discovered_data = self.multi_entity_extractor._parse_llm_response(
                    response_text,
                    source_record_id=email_data.get("id", ""),
                    tenant_id=self.tenant_id,
                    workspace_id=self.workspace_id,
                    batch_id=job_id,
                    model_name=model,
                )

                # If we got entities, success!
                if discovered_data:
                    logger.info(
                        f"[LLM_RETRY] Success with model={model}, extracted {len(discovered_data)} entities (tenant={self.tenant_id[:8]}, job={job_id})"
                    )
                    break

            except Exception as exc:
                logger.warning(
                    f"[LLM_RETRY] Attempt {attempt + 1} with model={model} failed: {str(exc)[:200]} (tenant={self.tenant_id[:8]}, job={job_id})"
                )
                last_error = str(exc)[:200]
                continue

        # ── If all attempts failed, return empty ──
        if not discovered_data:
            logger.error(
                f"[LLM_RETRY] All {len(models_to_try)} attempts failed for record={record.get('id')[:8]}. Last error: {last_error} (tenant={self.tenant_id[:8]}, job={job_id})"
            )
            return []

        logger.info(
            f"[INGEST_MULTI] Discovered {len(discovered_data)} entities from {integration_id} record {record.get('id')} (tenant={self.tenant_id[:8]})"
        )
        return discovered_data

    async def _process_multi_entity_extraction(
        self,
        record: Dict[str, Any],
        integration_id: str,
        text: str,
        job_id: str,
        llm_service: Optional[Any] = None,
    ) -> int:
        """
        Convenience wrapper for single-threaded callers: extract + persist.
        """
        import sys

        print(
            f"[FATAL_DEBUG] _process_multi_entity_extraction ENTERED: record_id={record.get('id')[:8]}",
            file=sys.stderr,
            flush=True,
        )
        entities = await self._extract_multi_entity_only(
            record, integration_id, text, job_id, llm_service
        )
        print(
            f"[FATAL_DEBUG] _extract_multi_entity_only returned: {len(entities)} entities",
            file=sys.stderr,
            flush=True,
        )
        if entities:
            # Defensive pattern: handle cases where self.db is None
            # (e.g., webhook path where db isn't passed to IngestionPipelineService)
            db = self.db
            close_db = False
            if db is None:
                from core.database import SessionLocal
                db = SessionLocal()
                close_db = True
            try:
                db.add_all(entities)
                db.flush()
                logger.info(
                    f"[{job_id}] Phase 323 discovered {len(entities)} entities from {record.get('id')}"
                )
                return len(entities)
            finally:
                if close_db:
                    db.close()
        return 0

    async def _run_schema_discovery(self, results: Dict[str, Any]) -> None:
        """
        Run schema discovery and auto-promotion to GraphRAG.
        """
        try:
            # 1. Discover schemas from high-confidence entities
            new_types = await self.schema_discovery.discover_schemas_from_entities(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                min_sample_count=5,  # Target threshold for auto-discovery
            )

            if new_types:
                logger.info(f"Phase 323 discovered {len(new_types)} new entity types")

            # 2. Link entities to graph (Auto-promotion)
            # This creates GraphNodes from DiscoveredEntities and marks them as 'linked'
            linked_nodes = await self.entity_linker.link_entities_to_graph(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                auto_create_types=True,  # Allow creating novel types during linking
                min_confidence=0.8,  # Only auto-promote very high confidence entities
            )

            if linked_nodes:
                results["entities_extracted"] += len(linked_nodes)
                logger.info(f"Phase 323 auto-promoted {len(linked_nodes)} entities to GraphRAG")

            # 3. AI-powered Enrichment
            # Trigger MetaAgentOrchestrator to detect patterns and suggest complex schemas
            try:
                await self.meta_agent_orchestrator.orchestrate_ontology_management(
                    tenant_id=self.tenant_id,
                    trigger_context={
                        "trigger_type": "ingestion",
                        "data": {"workspace_id": self.tenant_id},
                    },
                )
            except Exception as orch_err:
                logger.debug(f"AI orchestration skipped during ingestion: {orch_err}")

        except Exception as e:
            logger.error(f"Schema discovery/linking failed: {e}")

    async def _process_extracted_entities(
        self,
        entities: List[Dict[str, Any]],
        source_record: Dict[str, Any],
        sync_job_id: Union[str, uuid.UUID],
    ) -> List[DiscoveredEntity]:
        """
        Process raw extracted entities and save to DiscoveredEntity table.
        Used by Phase 323 'Extract and Type' flow.
        """
        discovered_models = []
        source_id = str(source_record.get("id", "unknown"))
        source_type = str(source_record.get("type", "record"))

        for entity in entities:
            # Create model from extracted data
            discovered = DiscoveredEntity(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                sync_job_id=sync_job_id,
                _discovered_type=entity.get("type", "Unknown"),
                entity_name=entity.get("name"),
                properties=entity.get("properties", {}),
                confidence_score=float(entity.get("confidence", 0.0)),
                source_record_id=source_id,
                source_record_type=source_type,
                status="pending",
                ingested=False,
            )
            discovered_models.append(discovered)

        if discovered_models:
            self.db.add_all(discovered_models)
            self.db.flush()
            logger.info(f"Persisted {len(discovered_models)} discovered entities for {source_id}")

        return discovered_models
