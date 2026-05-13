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
import asyncio
from datetime import datetime, timezone
from typing import Any, Union, Optional

from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.docling_processor import get_docling_processor
from core.graphrag_engine import GraphRAGEngine
from core.hybrid_data_ingestion import DEFAULT_SYNC_CONFIGS, HybridDataIngestionService
from core.lancedb_handler import LanceDBHandler
from core.models import DocumentIngestion, Tenant, UserConnection, IngestionJob, DiscoveredEntity
from core.multi_entity_llm_extractor import MultiEntityLLMExtractor
from core.schema_discovery_service import SchemaDiscoveryService
from core.entity_linking_service import EntityLinkingService
from core.usage_tracking_service import UsageTrackingService

logger = logging.getLogger(__name__)


class IngestionPipelineService(HybridDataIngestionService):
    """
    Orchestrates end-to-end ingestion pipeline from integrations to Knowledge Graph.
    """

    def __init__(self, tenant_id: str = "default", workspace_id: str = "default", db: Session = None):
        """
        Initialize ingestion pipeline service.
        """
        super().__init__(workspace_id=workspace_id, tenant_id=tenant_id)
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id
        self.db = db

        # Initialize LanceDB handler
        self.lancedb = LanceDBHandler(workspace_id=workspace_id, tenant_id=tenant_id)

        # Initialize GraphRAG engine
        self.graphrag = GraphRAGEngine(workspace_id=workspace_id, tenant_id=tenant_id)

        # Phase 323: High-performance Multi-Entity Extraction
        self.multi_entity_extractor = MultiEntityLLMExtractor()

        # Phase 323: Schema Discovery & Linking (Replaces OpenIE)
        self.schema_discovery = SchemaDiscoveryService(db=self.db)
        self.entity_linker = EntityLinkingService(
            db=self.db, schema_discovery_service=self.schema_discovery
        )

        # Initialize usage tracking service (Shimmed in Upstream)
        self.usage_tracker = UsageTrackingService(tenant_id=self.tenant_id, db=self.db)

    def close(self):
        """Close sub-services and sessions"""
        if hasattr(self, "graphrag") and self.graphrag:
            self.graphrag.close()
        if hasattr(self, "usage_tracker") and self.usage_tracker:
            self.usage_tracker.close()

    async def sync_and_ingest(
        self,
        integration_id: str,
        connection_id: Union[str, None] = None,
        trigger_type: str = "manual",
    ) -> dict[str, Any]:
        """
        Sync integration data and ingest into Knowledge Graph.
        """
        # Get sync configuration
        config = self.sync_configs.get(integration_id)
        if not config:
            if integration_id in DEFAULT_SYNC_CONFIGS:
                config = DEFAULT_SYNC_CONFIGS[integration_id]
                self.sync_configs[integration_id] = config
            else:
                return {"error": f"No sync configuration for {integration_id}", "success": False}

        # Create ingestion job for tracking
        job_id = self._create_ingestion_job(
            integration_id=integration_id,
            trigger_type=trigger_type,
            connection_id=connection_id,
        )

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

        start_time = datetime.now(timezone.utc)

        try:
            self._update_ingestion_job(
                job_id=job_id, status="running", started_at=datetime.now(timezone.utc)
            )

            # Step 1: Fetch integration data
            logger.info(f"[{job_id}] Fetching data from {integration_id}")
            records = await self._fetch_integration_data(integration_id, config)
            results["records_fetched"] = len(records)

            if not records:
                self._update_ingestion_job(
                    job_id=job_id,
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                    records_fetched=0,
                )
                results["success"] = True
                results["completed_at"] = datetime.now(timezone.utc).isoformat()
                return results

            # Step 2: Extract entities and relationships
            entities = []
            relationships = []
            ingested_record_ids = []

            for record in records:
                try:
                    text = self._record_to_text(record, integration_id)
                    if not text or len(text) < 10:
                        continue

                    # Idempotency check
                    record_id = record.get("id")
                    if record_id and self._is_doc_already_ingested(self.workspace_id, record_id, text):
                        results["records_processed"] += 1
                        continue

                    results["records_processed"] += 1

                    # Phase 323: Multi-Entity Extraction for Unstructured Data
                    if integration_id in ["outlook", "gmail", "slack", "discord", "whatsapp"]:
                        await self._process_record_with_multi_entity_extraction(record, integration_id, job_id)

                    # Extract structured data (Standard pipeline)
                    entity, rel = self._extract_structured_entities(record, integration_id, text)
                    if entity:
                        entities.append(entity)
                    if rel:
                        relationships.append(rel)
                    if record_id:
                        ingested_record_ids.append((record_id, text))

                except Exception as record_err:
                    results["errors"].append(str(record_err))

            # Step 3: Ingest into Knowledge Graph
            if entities or relationships:
                self.graphrag.ingest_structured_data(
                    workspace_id=self.workspace_id, entities=entities, relationships=relationships
                )
                results["entities_extracted"] = len(entities)
                results["relationships_extracted"] = len(relationships)

                for rid, rtext in ingested_record_ids:
                    self._record_doc_ingestion(self.workspace_id, rid, rtext, integration_id)

            # Step 4: Schema Discovery & Linking (Phase 323)
            # 1. Discover schemas
            await self.schema_discovery.discover_schemas_from_entities(
                tenant_id=self.tenant_id, workspace_id=self.workspace_id
            )
            
            # 2. Link entities to graph (Auto-promotion)
            linked_nodes = await self.entity_linker.link_entities_to_graph(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                auto_create_types=True,
                min_confidence=0.8
            )
            if linked_nodes:
                results["entities_extracted"] += len(linked_nodes)
                logger.info(f"Phase 323 auto-promoted {len(linked_nodes)} entities to Knowledge Graph")

            # Step 5: Update job status
            completed_at = datetime.now(timezone.utc)
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

        except Exception as e:
            error_msg = f"Pipeline failed: {e}"
            results["error"] = error_msg
            self._update_ingestion_job(job_id=job_id, status="failed", error_message=error_msg)
            logger.error(f"[{job_id}] {error_msg}")

        return results

    async def _process_record_with_multi_entity_extraction(
        self, record: dict[str, Any], integration_id: str, job_id: str
    ) -> list[DiscoveredEntity]:
        """Process record using high-performance Multi-Entity LLM Extraction."""
        # Convert record to extraction format
        email_data = {
            "id": record.get("id", "unknown"),
            "subject": record.get("subject", record.get("title", "")),
            "from": record.get("from", record.get("sender", "")),
            "to": record.get("to", record.get("recipients", [])),
            "body": record.get("body", record.get("text", "")),
        }

        # Call extractor
        discovered_entities = await self.multi_entity_extractor.extract_from_email(
            email_data=email_data,
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            batch_id=job_id
        )

        # Add the email message itself as a DiscoveredEntity
        email_discovered_entity = DiscoveredEntity(
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            _discovered_type="EmailMessage",
            properties=email_data,
            confidence_score=1.0,
            source_record_id=email_data["id"],
            source_record_type="email",
            status="pending",
            extraction_metadata={
                "batch_id": job_id,
                "extracted_at": datetime.now(timezone.utc).isoformat()
            }
        )
        discovered_entities.append(email_discovered_entity)

        if discovered_entities:
            # Persist to discovered_entities table using batch add
            self.db.add_all(discovered_entities)
            self.db.flush()
            logger.info(f"[{job_id}] Phase 323 discovered {len(discovered_entities)} entities")

        return discovered_entities

    def _extract_structured_entities(
        self, record: dict[str, Any], integration_id: str, text: str
    ) -> tuple[Optional[dict], Optional[dict]]:
        """Extract basic structured entity and relationship."""
        record_type = record.get("type", "record")
        record_id = record.get("id", "unknown")
        record_name = (
            record.get("name") or record.get("title") or record.get("subject") or f"{record_type}_{record_id}"
        )

        entity = {
            "name": record_name,
            "type": record_type,
            "description": text[:500],
            "properties": {
                "source": integration_id,
                "record_id": record_id,
                "record_type": record_type,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "doc_id": record_id,
            },
        }

        # Common fields
        for key in ["email", "company", "status", "priority"]:
            if key in record and record[key]:
                entity["properties"][key] = record[key]

        rel = {
            "from": record_name,
            "to": integration_id,
            "type": "synced_from",
            "properties": {"source": integration_id}
        }
        return entity, rel

    def _create_ingestion_job(self, **kwargs) -> str:
        session = SessionLocal()
        try:
            job_id = str(uuid.uuid4())
            job = IngestionJob(id=job_id, tenant_id=self.tenant_id, status="pending", **kwargs)
            session.add(job)
            session.commit()
            return job_id
        except Exception as e:
            logger.warning(f"Failed to create IngestionJob: {e}")
            return str(uuid.uuid4())
        finally:
            session.close()

    def _update_ingestion_job(self, job_id: str, **kwargs):
        session = SessionLocal()
        try:
            job = session.query(IngestionJob).filter_by(id=job_id).first()
            if job:
                for k, v in kwargs.items():
                    setattr(job, k, v)
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to update IngestionJob {job_id}: {e}")
        finally:
            session.close()

    def _is_doc_already_ingested(self, workspace_id: str, doc_id: str, text: str) -> bool:
        session = SessionLocal()
        try:
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            existing = session.query(DocumentIngestion).filter_by(workspace_id=workspace_id, doc_id=doc_id).first()
            return existing is not None and existing.content_hash == h
        finally:
            session.close()

    def _record_doc_ingestion(self, workspace_id: str, doc_id: str, text: str, source: str):
        session = SessionLocal()
        try:
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            existing = session.query(DocumentIngestion).filter_by(workspace_id=workspace_id, doc_id=doc_id).first()
            if existing:
                existing.content_hash = h
                existing.source = source
            else:
                session.add(DocumentIngestion(workspace_id=workspace_id, doc_id=doc_id, content_hash=h, source=source))
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def _is_core_entity_type(self, entity_type: str) -> bool:
        return entity_type.lower() in CORE_ENTITY_SCHEMAS

    # Transformers (Simplified for Upstream)
    async def _transform_slack_payload(self, data):
        event = data.get("event", {})
        if data.get("type") == "event_callback" and event.get("type") == "message":
            return [{
                "type": "slack_message",
                "id": event.get("client_msg_id") or event.get("ts"),
                "text": event.get("text", ""),
                "channel": event.get("channel"),
                "user": event.get("user"),
                "timestamp": event.get("ts")
            }]
        return []

    async def _transform_hubspot_payload(self, data):
        events = data if isinstance(data, list) else [data]
        records = []
        for e in events:
            stype = e.get("subscriptionType")
            records.append({
                "type": f"hubspot_{stype}",
                "id": e.get("objectId"),
                "properties": e.get("properties", {})
            })
        return records

    async def _transform_outlook_payload(self, data):
        return [{
            "type": "email",
            "id": data.get("id") or data.get("metadata", {}).get("conversation_id"),
            "subject": data.get("subject", ""),
            "from": data.get("from", ""),
            "to": data.get("to", ""),
            "text": data.get("content", ""),
            "properties": data.get("metadata", {})
        }]
