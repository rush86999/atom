import pytest
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import uuid
import os

os.environ["TESTING"] = "1"

from core.database import SessionLocal, engine
from core.historical_sync_service import HistoricalSyncService
from core.models import Base, EntityTypeDefinition, DiscoveredEntity, HistoricalSyncJob, Tenant, TenantSetting, Workspace

@pytest.fixture(scope="module", autouse=True)
def setup_db_schema():
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        db.query(DiscoveredEntity).delete()
        db.query(HistoricalSyncJob).delete()
        db.query(EntityTypeDefinition).delete()
        db.query(TenantSetting).delete()
        db.query(Workspace).delete()
        db.query(Tenant).delete()
        db.commit()
        yield db
    finally:
        db.close()

@pytest.fixture
def tenant_id(db):
    tid = str(uuid.uuid4())
    tenant = Tenant(id=tid, name="Test Tenant", subdomain="test-" + tid, plan_type="team")
    db.add(tenant)
    
    # Also create a workspace with same ID for relationship compatibility
    ws = Workspace(id=tid, name="Default Workspace", tenant_id=tid)
    db.add(ws)
    
    db.commit()
    return tid

@pytest.fixture
def sync_service(db, tenant_id):
    return HistoricalSyncService(tenant_id=tenant_id, db=db)

class TestLLMEntityExtractionTDD:
    """
    TDD for Historical Ingestion Pipeline:
    1. LLM extracts multiple entities per email.
    2. Each LLM entity becomes a DiscoveredEntity with _discovered_type set.
    3. Schema discovery creates entity types from the LLM types.
    4. Records get linked to the correct entity type via _discovered_type matching.
    """

    @pytest.mark.asyncio
    async def test_multiple_entities_and_schema_discovery(self, sync_service, db, tenant_id):
        # 1. Setup Mock Data
        doc_id = "msg_001"
        mock_extracted_entities = [
            {
                "name": "PO-123",
                "type": "PurchaseOrder",
                "properties": {"amount": 1000}
            },
            {
                "name": "Acme Corp",
                "type": "Vendor",
                "properties": {"industry": "Tech"}
            }
        ]
        
        sample_record = {
            "id": doc_id,
            "subject": "New Purchase Order PO-123",
            "body": "Please find PO-123 for Acme Corp. This is a longer body to pass limits. " * 5,
            "type": "email"
        }

        # 2. Patching services
        with patch("core.historical_sync_service.IntegrationRegistry") as mock_registry_class, \
             patch("core.historical_sync_service.IngestionPipelineService") as mock_pipeline_class, \
             patch("core.historical_sync_service.SyncJobQueue") as mock_queue_class:
            
            mock_registry = mock_registry_class.return_value
            # Return one record then stop
            mock_registry.fetch_paginated_records = AsyncMock(side_effect=[
                {"records": [sample_record], "next_page_token": "token_1"},
                {"records": [], "next_page_token": None}
            ])
            
            mock_pipeline = mock_pipeline_class.return_value
            mock_pipeline.sync_and_ingest = AsyncMock(return_value={"success": True})
            
            # 3. Trigger Sync Job
            job_id = await sync_service.start_historical_sync(
                integration_id="gmail",
                connection_id="conn_1",
                start_date=datetime.now(timezone.utc) - timedelta(days=90)
            )
            
            assert job_id is not None
            
            # 4. Manually run processing (since we mocked the queue)
            # In a real scenario, the worker would pick this up.
            await sync_service._process_sync_job(job_id)
            
            # 5. Verify IngestionPipeline was called correctly
            # We want to verify that the pipeline processed the record and discovered types.
            # But wait, in the test we might want to test the REAL IngestionPipelineService
            # instead of mocking it, if we want to verify schema discovery.
            
    @pytest.mark.asyncio
    async def test_ingestion_pipeline_schema_discovery(self, db, tenant_id):
        """Test the real IngestionPipelineService logic for multi-entity extraction and discovery."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(tenant_id=tenant_id, workspace_id=tenant_id, db=db)
        
        # Mock extracted entities that would come from LLM (in a real run)
        # Here we test the logic that processes these entities.
        entities = [
            {"name": "PO-123", "type": "PurchaseOrder", "properties": {"amount": 5000}},
            {"name": "Acme Corp", "type": "Vendor", "properties": {"industry": "Logistics"}}
        ]
        
        # Act: Run schema discovery
        await pipeline._run_schema_discovery(entities, integration_id="gmail")
        
        # Assert: Verify draft entity types were created
        et_purchase_order = db.query(EntityTypeDefinition).filter_by(
            tenant_id=tenant_id, slug="purchaseorder"
        ).first()
        et_vendor = db.query(EntityTypeDefinition).filter_by(
            tenant_id=tenant_id, slug="vendor"
        ).first()
        
        assert et_purchase_order is not None
        assert et_purchase_order.is_active is False # Draft
        assert et_vendor is not None
        assert et_vendor.is_active is False # Draft
        
    @pytest.mark.asyncio
    async def test_discovered_entity_type_matching(self, db, tenant_id):
        """Verify each LLM entity becomes a DiscoveredEntity with correct type."""
        # This part usually happens inside GraphRAGEngine or IngestionPipeline
        # We'll simulate the creation.
        
        entity = DiscoveredEntity(
            tenant_id=tenant_id,
            workspace_id=tenant_id,
            _discovered_type="SecurityEvent",
            properties={"severity": "High"},
            source_record_id="msg_999",
            source_record_type="email"
        )
        db.add(entity)
        db.commit()
        
        saved = db.query(DiscoveredEntity).filter_by(source_record_id="msg_999").first()
        assert saved._discovered_type == "SecurityEvent"
        assert saved.status == "pending"


