from __future__ import annotations

"""
Historical Data Sync Service - Import 3+ months of integration data

Implements chunked historical sync for backfilling integration data into Knowledge Graph.
Supports progress tracking, resumability, and API pagination abstraction.
"""

import asyncio
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional

from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.ingestion_pipeline import IngestionPipelineService
from core.integration_registry import IntegrationRegistry
from core.structured_logger import get_logger
from core.models import HistoricalSyncJob
from core.sync_job_queue import JobPriority, SyncJobQueue

logger = get_logger(__name__)

# Shared DB engine, 1 conn per chunk. Safe to use concurrent LLM calls.
_LLM_SEMAPHORE = asyncio.Semaphore(3)

async def _llm_extract_with_handler(
    llm_service,  # Pre-created LLMService instance (shared across chunk)
    text: str,
    doc_id: str,
    source: str,
    workspace_id: str,
    tenant_id: str,
    system_instruction_override: str | None = None,
    extra_metadata: dict | None = None,
) -> tuple[list, list]:
    """Extract entities and relationships using a pre-created LLMService."""
    import json as _json
    from core.graphrag_engine import Entity, Relationship
    from core.openie_schema_discovery import CORE_ENTITY_SCHEMAS

    # 1. Build the prompt
    core_entities_section = """
Core Entity Types (prefer these when matching):
""" + _json.dumps(CORE_ENTITY_SCHEMAS, indent=2)

    instructions = """
Extract entities and relationships from the text.
1. Check if entities match Core Entity Types above - use canonical_type if match found
2. For non-matching entities, create appropriate custom types
3. Respond with valid JSON only.
"""

    prompt = f"""{core_entities_section}

{instructions}

Text:
\"\"\"
{text[:6000]}
\"\"\"

JSON Schema:
{{
  "entities": [{{
    "name": "string",
    "type": "string",
    "canonical_type": "string (optional: user, organization, contact, project, task)",
    "description": "string",
    "confidence": 0.85,
    "properties": {{}}
  }}],
  "relationships": [{{
    "from": "string",
    "to": "string",
    "type": "string",
    "description": "string"
  }}]
}}"""

    system_instruction = (system_instruction_override or "You are a knowledge graph extractor. Output valid JSON only.")

    # 2. Retry loop with fallback models
    models_to_try = [
        "auto",
        "google/gemini-2.0-flash",
        "deepseek/deepseek-chat",
    ]
    data = None
    last_error = None

    for attempt, model in enumerate(models_to_try):
        try:
            response_text = await llm_service.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                model=model,
                task_type="extraction",
            )
        except Exception as exc:
            logger.warning(f"LLM extraction attempt {attempt + 1} raised for doc {doc_id}: {exc}")
            last_error = str(exc)[:200]
            continue

        if not response_text or not response_text.strip():
            last_error = "Empty response from LLM"
            continue

        cleaned = response_text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        try:
            data = _json.loads(cleaned)
            break
        except _json.JSONDecodeError as e:
            last_error = f"JSON decode error: {e}"
            continue

    if data is None:
        logger.error(f"LLM extraction failed after {len(models_to_try)} attempts for doc {doc_id}. Last error: {last_error}")
        return [], []

    # 3. Build Entity / Relationship objects
    entities = []
    for e in data.get("entities", []):
        properties = {"source": source, "doc_id": doc_id, "llm_extracted": True}
        if extra_metadata:
            properties.update(extra_metadata)
        if e.get("canonical_type"):
            properties["canonical_type"] = e["canonical_type"]
        entities.append(
            Entity(
                id=str(uuid.uuid4()),
                name=e["name"],
                entity_type=e["type"],
                description=e.get("description", ""),
                properties=properties,
                confidence=float(e.get("confidence", 0.0)),
            )
        )

    relationships = []
    for r in data.get("relationships", []):
        relationships.append(
            Relationship(
                id=str(uuid.uuid4()),
                from_entity=r["from"],
                to_entity=r["to"],
                rel_type=r["type"],
                description=r.get("description", ""),
                properties={"llm_extracted": True, **(extra_metadata or {})},
            )
        )

    return entities, relationships


def _log_job_event(db, job_id: str, tenant_id: str, event: str) -> None:
    """Persist a diagnostic event to the job record so it survives restarts."""
    try:
        from core.models import HistoricalSyncJob

        j = (
            db.query(HistoricalSyncJob)
            .filter(
                HistoricalSyncJob.id == job_id,
                HistoricalSyncJob.tenant_id == tenant_id,
            )
            .first()
        )
        if j:
            data = j.checkpoint_data or {}
            events = data.get("events", [])
            events.append(f"[{datetime.now(timezone.utc).isoformat()}] {event}")
            data["events"] = events[-10:]
            j.checkpoint_data = data
            db.commit()
            logger.info(f"[JOB_EVENT] {job_id}: {event}")
    except Exception:
        pass


class HistoricalSyncService:
    """
    Historical data sync service for backfilling integration data.
    """

    def __init__(
        self,
        tenant_id: str,
        db: Session = None,
        workspace_id: Union[str, None] = None,
    ):
        self.tenant_id = tenant_id
        self._db = db
        self._internal_session = False
        self._workspace_id = workspace_id
        self._ingestion_pipeline = None
        self._integration_registry = None

    async def _extract_chunk_and_ingest(
        self,
        job_id: str,
        chunk_count: int,
        llm_task_records: list,
        workspace_id: str,
        integration_id: str = "",
    ) -> tuple[int, int]:
        """Two-phase LLM extraction: extract in parallel, then ingest to DB."""
        import time
        from core.graphrag_engine import GraphRAGEngine as _G
        from core.llm_service import LLMService

        record_count = len(llm_task_records)
        logger.info(
            f"Chunk {chunk_count + 1}: Starting extraction for {record_count} records",
            tenant_id=self.tenant_id,
            job_id=job_id,
        )
        _log_job_event(
            self.db,
            job_id,
            self.tenant_id,
            f"Chunk {chunk_count + 1} start: {record_count} records for LLM extraction",
        )

        shared_db = SessionLocal()
        shared_engine = _G(workspace_id=workspace_id, tenant_id=self.tenant_id)

        # Create LLMService ONCE for all tasks — avoids per-task DB connections
        llm_service = LLMService(db=shared_db, workspace_id=workspace_id, tenant_id=self.tenant_id)

        try:
            async def _extract_one(doc_id, txt, src):
                async with _LLM_SEMAPHORE:
                    for attempt in range(2):
                        try:
                            entities, rels = await asyncio.wait_for(
                                _llm_extract_with_handler(
                                    llm_service, txt, doc_id, src, workspace_id, self.tenant_id
                                ),
                                timeout=120.0,
                            )
                            return {"doc_id": doc_id, "entities": entities, "relationships": rels}
                        except Exception as e:
                            logger.warning(f"LLM call failed for doc {doc_id} (attempt {attempt + 1}/2): {e}")
                    return None

            llm_tasks = [asyncio.create_task(_extract_one(doc_id, txt, src)) for doc_id, txt, src in llm_task_records]
            done, pending = await asyncio.wait(llm_tasks, timeout=600.0, return_when=asyncio.ALL_COMPLETED)
            
            for task in pending:
                task.cancel()

            valid_results = []
            for task in done:
                try:
                    res = task.result()
                    if res:
                        valid_results.append(res)
                except Exception:
                    pass

            # Phase 2: Ingest into Knowledge Graph
            total_entities = 0
            total_relationships = 0
            
            for res in valid_results:
                if res["entities"] or res["relationships"]:
                    shared_engine.ingestion_pipeline_batch(
                        workspace_id=workspace_id,
                        entities=res["entities"],
                        relationships=res["relationships"]
                    )
                    total_entities += len(res["entities"])
                    total_relationships += len(res["relationships"])

            _log_job_event(
                self.db,
                job_id,
                self.tenant_id,
                f"Chunk {chunk_count + 1} complete: {total_entities} entities, {total_relationships} relationships extracted",
            )
            return total_entities, total_relationships

        finally:
            shared_db.close()
            shared_engine.close()

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
            self._internal_session = True
        return self._db

    @property
    def workspace_id(self) -> str:
        if self._workspace_id is None:
            # Fallback to tenant_id if workspace_id not provided
            self._workspace_id = self.tenant_id
        return self._workspace_id

    @property
    def ingestion_pipeline(self) -> IngestionPipelineService:
        if self._ingestion_pipeline is None:
            self._ingestion_pipeline = IngestionPipelineService(
                tenant_id=self.tenant_id, workspace_id=self.workspace_id, db=self.db
            )
        return self._ingestion_pipeline

    @property
    def integration_registry(self) -> IntegrationRegistry:
        if self._integration_registry is None:
            self._integration_registry = IntegrationRegistry(self.db)
        return self._integration_registry

    async def start_historical_sync(
        self,
        integration_id: str,
        connection_id: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        chunk_size: int = 100,
        scope: str = "personal",
    ) -> str:
        """Start a historical sync job."""
        if not end_date:
            end_date = start_date + timedelta(days=90)

        job_id = str(uuid.uuid4())
        job = HistoricalSyncJob(
            id=job_id,
            tenant_id=self.tenant_id,
            integration_id=integration_id,
            source_connection_id=connection_id,
            start_date=start_date,
            end_date=end_date,
            status="pending",
            scope=scope,
            chunk_size=chunk_size,
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(job)
        self.db.commit()

        # Enqueue job to Redis (if available)
        try:
            queue = SyncJobQueue()
            await queue.enqueue(
                job_data={
                    "job_id": job_id,
                    "tenant_id": self.tenant_id,
                    "integration_id": integration_id,
                    "connection_id": connection_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "chunk_size": chunk_size,
                    "scope": scope,
                },
                priority=JobPriority.NORMAL,
            )
        except Exception as e:
            logger.warning(f"Failed to enqueue sync job: {e}. It will remain in pending.")

        return job_id

    async def _heartbeat_loop(self, job_id: str):
        """Background heartbeat task to keep job alive in DB during long operations"""
        logger.info(f"💓 Starting background heartbeat for job {job_id}")
        try:
            while True:
                try:
                    # Use a fresh session every time to avoid transaction issues
                    with SessionLocal() as hb_db:
                        hb_db.query(HistoricalSyncJob).filter(
                            HistoricalSyncJob.id == job_id,
                            HistoricalSyncJob.tenant_id == self.tenant_id,
                        ).update({"last_heartbeat": datetime.now(timezone.utc)})
                        hb_db.commit()
                except Exception as hb_err:
                    logger.warning(f"Background heartbeat failed for job {job_id}: {hb_err}")

                await asyncio.sleep(120)  # 2 minutes
        except asyncio.CancelledError:
            logger.info(f"💓 Heartbeat task for job {job_id} cancelled")
        except Exception as e:
            logger.error(f"💓 Heartbeat task for job {job_id} crashed: {e}")

    async def _process_sync_job(self, job_id: str):
        """Main processing loop for a sync job with chunked extraction and resumption."""
        bg_db = SessionLocal()
        heartbeat_task = None
        
        try:
            job = bg_db.query(HistoricalSyncJob).filter_by(id=job_id, tenant_id=self.tenant_id).first()
            if not job:
                logger.error(f"Job {job_id} not found for tenant {self.tenant_id}")
                return

            if job.status in ["completed", "failed"]:
                logger.info(f"Job {job_id} already in terminal state {job.status}")
                return

            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.last_heartbeat = datetime.now(timezone.utc)
            bg_db.commit()

            # Start heartbeat
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(job_id))

            # Fetch and process in chunks
            page_token = job.checkpoint_data.get("last_page_token") if job.checkpoint_data else None
            chunk_count = job.completed_chunks or 0
            records_processed = job.records_processed or 0
            total_entities = job.entities_extracted or 0
            total_relationships = job.relationships_extracted or 0

            _log_job_event(bg_db, job_id, self.tenant_id, f"Resuming sync from chunk {chunk_count}")

            while True:
                # Check for cancellation/pause
                bg_db.refresh(job)
                if job.status in ["paused", "cancelled"]:
                    logger.info(f"Job {job_id} {job.status} by user/system")
                    break

                result = await self.integration_registry.fetch_paginated_records(
                    integration_id=job.integration_id,
                    tenant_id=self.tenant_id,
                    start_date=job.start_date,
                    end_date=job.end_date,
                    page_size=job.chunk_size,
                    page_token=page_token,
                    connection_id=job.source_connection_id,
                )

                if "error" in result:
                    raise Exception(result["error"])

                records = result.get("records", [])
                if not records:
                    break

                # Prepare records for parallel extraction
                llm_task_records = []
                for record in records:
                    text = self.ingestion_pipeline._record_to_text(record, job.integration_id)
                    if text and len(text) > 10:
                        llm_task_records.append((str(record.get("id")), text, job.integration_id))

                # Process chunk via two-phase extraction
                if llm_task_records:
                    ent_count, rel_count = await self._extract_chunk_and_ingest(
                        job_id=job_id,
                        chunk_count=chunk_count,
                        llm_task_records=llm_task_records,
                        workspace_id=self.workspace_id,
                        integration_id=job.integration_id
                    )
                    total_entities += ent_count
                    total_relationships += rel_count

                # Update progress
                records_processed += len(records)
                chunk_count += 1
                page_token = result.get("next_page_token")
                
                job.records_processed = records_processed
                job.completed_chunks = chunk_count
                job.entities_extracted = total_entities
                job.relationships_extracted = total_relationships
                job.checkpoint_data = {"last_page_token": page_token}
                bg_db.commit()

                if not page_token:
                    break

            # Final pass: Schema Discovery
            try:
                from core.schema_discovery_service import SchemaDiscoveryService
                discovery = SchemaDiscoveryService(db=bg_db)
                await discovery.discover_schemas_from_entities(
                    tenant_id=self.tenant_id,
                    workspace_id=self.workspace_id
                )
            except Exception as e:
                logger.warning(f"Final schema discovery pass failed for job {job_id}: {e}")

            if job.status == "running":
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                bg_db.commit()
                _log_job_event(bg_db, job_id, self.tenant_id, "Sync completed successfully")

        except Exception as e:
            logger.error(f"Sync job {job_id} failed: {e}")
            try:
                # Refresh job to ensure we're not using stale data
                job = bg_db.query(HistoricalSyncJob).filter_by(id=job_id).first()
                if job:
                    job.status = "failed"
                    job.last_error = str(e)
                    bg_db.commit()
                    _log_job_event(bg_db, job_id, self.tenant_id, f"Sync failed: {e}")
            except Exception as commit_err:
                logger.error(f"Failed to mark job {job_id} as failed: {commit_err}")
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
            bg_db.close()

    async def get_sync_progress(self, job_id: str) -> dict[str, Any]:
        """Get progress of a historical sync job."""
        job = self.db.query(HistoricalSyncJob).filter_by(id=job_id, tenant_id=self.tenant_id).first()
        if not job:
            return {"error": "Job not found", "job_id": job_id}

        return {
            "job_id": job.id,
            "status": job.status,
            "records_processed": job.records_processed or 0,
            "entities_extracted": job.entities_extracted or 0,
            "relationships_extracted": job.relationships_extracted or 0,
            "completed_chunks": job.completed_chunks or 0,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "last_error": job.last_error,
        }

    async def cancel_sync(self, job_id: str) -> bool:
        """Cancel a running historical sync job."""
        job = self.db.query(HistoricalSyncJob).filter_by(id=job_id, tenant_id=self.tenant_id).first()
        if not job:
            return False
        
        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    async def pause_sync(self, job_id: str) -> bool:
        """Manually pause a running historical sync job."""
        job = self.db.query(HistoricalSyncJob).filter_by(id=job_id, tenant_id=self.tenant_id).first()
        if not job or job.status not in ["running", "pending"]:
            return False
        
        job.status = "paused"
        self.db.commit()
        return True

    async def resume_sync(self, job_id: str) -> bool:
        """Resume a paused or failed sync job."""
        job = self.db.query(HistoricalSyncJob).filter_by(id=job_id, tenant_id=self.tenant_id).first()
        if not job:
            return False
        
        job.status = "pending"
        self.db.commit()

        # Re-enqueue
        try:
            queue = SyncJobQueue()
            await queue.enqueue(
                job_data={
                    "job_id": job_id,
                    "tenant_id": self.tenant_id,
                    "integration_id": job.integration_id,
                    "connection_id": job.source_connection_id,
                    "start_date": job.start_date.isoformat(),
                    "end_date": job.end_date.isoformat(),
                    "chunk_size": job.chunk_size,
                    "scope": job.scope,
                },
                priority=JobPriority.NORMAL,
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to re-enqueue sync job: {e}")
            return False
