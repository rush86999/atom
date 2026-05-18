from __future__ import annotations

import uuid
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.routes.ingestion_crud_routes import router
from core.models import (
    DiscoveredEntity,
    GraphEdge,
    GraphNode,
    IngestionAuditLog,
    IngestionJob,
    Tenant,
    User,
)
from core.ingestion_crud_service import IngestionCRUDService

# ============================================================================
# Fixtures & Test App Setup
# ============================================================================

_current_test_user = None


@pytest.fixture
def app_with_overrides(db_session: Session):
    """Create a localized FastAPI app with dependency overrides for testing."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from api.dependencies import get_current_user

    def override_get_db():
        yield db_session

    def override_get_current_user():
        if _current_test_user is None:
            raise Exception("Mock user is not set for this test")
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield app

    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def client(app_with_overrides: FastAPI):
    """FastAPI TestClient instance."""
    return TestClient(app_with_overrides, raise_server_exceptions=False)


@pytest.fixture
def test_setup(db_session: Session) -> Dict[str, Any]:
    """Generates tenant, user, workspace, and core mock data for testing."""
    from core.models import Workspace

    tenant_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # 1. Setup Tenant
    tenant = Tenant(id=tenant_id, subdomain=f"test-saas-{uuid.uuid4().hex[:8]}", name="Test Ingestion Tenant")
    db_session.add(tenant)

    # 2. Setup Workspace
    workspace = Workspace(
        id=workspace_id,
        name="Default Test Workspace",
        tenant_id=tenant_id,
    )
    db_session.add(workspace)

    # 3. Setup User
    user = User(
        id=user_id,
        email=f"operator-{uuid.uuid4().hex[:8]}@test.com",
        tenant_id=tenant_id,
        role="operator",
        status="active",
    )
    user.workspace_id = workspace_id
    db_session.add(user)
    db_session.commit()

    global _current_test_user
    _current_test_user = user

    return {
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "user": user,
    }


# ============================================================================
# Test Cases - Phase 1: Reads & Lists
# ============================================================================


def test_list_entities_api(client: TestClient, db_session: Session, test_setup: Dict[str, Any]):
    """Test listing discovered entities with various status and type filters."""
    tenant_id = test_setup["tenant_id"]

    # Add dummy entities
    e1 = DiscoveredEntity(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h1",
        _discovered_type="contact",
        status="pending",
        confidence_score=0.85,
        properties={"email": "alice@hubspot.com"},
    )
    e2 = DiscoveredEntity(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h2",
        _discovered_type="company",
        status="linked",
        confidence_score=0.92,
        properties={"domain": "acme.com"},
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    # 1. Fetch all hubspot entities
    response = client.get("/api/v1/ingestion/hubspot/entities")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["entities"]) == 2

    # 2. Filter by status
    response = client.get("/api/v1/ingestion/hubspot/entities?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["entities"][0]["source_record_id"] == "h1"

    # 3. Filter by type
    response = client.get("/api/v1/ingestion/hubspot/entities?type=company")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["entities"][0]["_discovered_type"] == "company"


def test_get_single_entity_api(client: TestClient, db_session: Session, test_setup: Dict[str, Any]):
    """Test fetching details of a single discovered entity."""
    tenant_id = test_setup["tenant_id"]
    entity_id = uuid.uuid4()

    ent = DiscoveredEntity(
        id=entity_id,
        tenant_id=tenant_id,
        source_record_type="jira",
        source_record_id="jira-101",
        _discovered_type="ticket",
        status="pending",
        confidence_score=0.90,
        properties={"summary": "Fix login crash"},
    )
    db_session.add(ent)
    db_session.commit()

    # Successful retrieval
    response = client.get(f"/api/v1/ingestion/jira/entities/{entity_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(entity_id)
    assert data["source_record_id"] == "jira-101"
    assert data["properties"]["summary"] == "Fix login crash"

    # Mismatched integration ID -> 404
    response = client.get(f"/api/v1/ingestion/wrong_integration/entities/{entity_id}")
    assert response.status_code == 404

    # Non-existent ID -> 404
    response = client.get(f"/api/v1/ingestion/jira/entities/{uuid.uuid4()}")
    assert response.status_code == 404


def test_list_sync_jobs_api(client: TestClient, db_session: Session, test_setup: Dict[str, Any]):
    """Test retrieving historical backfill and sync jobs under workspace boundary."""
    workspace_id = test_setup["workspace_id"]

    job1 = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=workspace_id,  # maps to workspace_id in database schema
        integration_id="hubspot",
        trigger_type="scheduled",
        status="completed",
        records_fetched=15,
        records_processed=15,
        entities_extracted=2,
        relationships_extracted=1,
    )
    job2 = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=workspace_id,
        integration_id="hubspot",
        trigger_type="manual",
        status="failed",
        error_message="API Rate limit exceeded",
    )
    db_session.add_all([job1, job2])
    db_session.commit()

    response = client.get("/api/v1/ingestion/hubspot/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["jobs"]) == 2
    trigger_types = {j["trigger_type"] for j in data["jobs"]}
    assert trigger_types == {"scheduled", "manual"}
    assert any(j["status"] == "failed" for j in data["jobs"])
    assert any(j["error_message"] == "API Rate limit exceeded" for j in data["jobs"])


def test_tenant_scoped_vs_personal_scoped_jobs_api(
    client: TestClient, db_session: Session, test_setup: Dict[str, Any]
):
    """Verify that tenant-scoped integrations fetch jobs across all tenant workspaces,

    while personal-scoped integrations are strictly confined to the active workspace.
    """
    tenant_id = test_setup["tenant_id"]
    workspace_id = test_setup["workspace_id"]

    from core.models import Workspace

    # 1. Create a second workspace under the same tenant
    other_workspace_id = str(uuid.uuid4())
    other_workspace = Workspace(
        id=other_workspace_id,
        name="Secondary Workspace",
        tenant_id=tenant_id,
    )
    db_session.add(other_workspace)

    # 2. Add an IngestionJob under the primary workspace (HubSpot - Tenant Scoped)
    job_tenant_scoped1 = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=workspace_id,
        integration_id="hubspot",
        trigger_type="manual",
        status="completed",
    )
    # 3. Add an IngestionJob under the secondary workspace (HubSpot - Tenant Scoped)
    job_tenant_scoped2 = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=other_workspace_id,
        integration_id="hubspot",
        trigger_type="scheduled",
        status="completed",
    )
    # 4. Add an IngestionJob under the secondary workspace (Gmail - Personal Scoped)
    job_personal_scoped = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=other_workspace_id,
        integration_id="gmail",
        trigger_type="webhook",
        status="completed",
    )

    db_session.add_all([job_tenant_scoped1, job_tenant_scoped2, job_personal_scoped])
    db_session.commit()

    # Case A: Tenant-scoped integration (HubSpot) -> should return BOTH jobs (across workspaces)
    response = client.get("/api/v1/ingestion/hubspot/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["jobs"]) == 2

    # Case B: Personal-scoped integration (Gmail) -> should return ZERO jobs (as active user is in primary workspace)
    response = client.get("/api/v1/ingestion/gmail/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["jobs"]) == 0



def test_get_status_metrics_api(client: TestClient, db_session: Session, test_setup: Dict[str, Any]):
    """Test aggregating pipeline statistics for an integration."""
    tenant_id = test_setup["tenant_id"]
    workspace_id = test_setup["workspace_id"]

    # Entities with different statuses
    e1 = DiscoveredEntity(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source_record_type="slack",
        source_record_id="s1",
        _discovered_type="message",
        status="pending",
        confidence_score=0.9,
    )
    e2 = DiscoveredEntity(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source_record_type="slack",
        source_record_id="s2",
        _discovered_type="message",
        status="linked",
        confidence_score=0.95,
    )
    db_session.add_all([e1, e2])

    # Add sync jobs for metrics (one success, one failure)
    job1 = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=workspace_id,
        integration_id="slack",
        trigger_type="manual",
        status="completed",
    )
    job2 = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=workspace_id,
        integration_id="slack",
        trigger_type="manual",
        status="failed",
    )
    db_session.add_all([job1, job2])
    db_session.commit()

    response = client.get("/api/v1/ingestion/slack/status")
    assert response.status_code == 200
    data = response.json()
    assert data["integration_id"] == "slack"
    assert data["status_counts"]["pending"] == 1
    assert data["status_counts"]["linked"] == 1
    assert data["error_rate"] == 0.5
    assert data["latest_job_status"] is not None


# ============================================================================
# Test Cases - Phase 2: Cascading Deletes & Unlinks
# ============================================================================


def test_cascading_delete_single_source_node(client: TestClient, db_session: Session, test_setup: Dict[str, Any]):
    """Test that deleting a DiscoveredEntity linked to a single-source GraphNode purges both node & edges."""
    tenant_id = test_setup["tenant_id"]
    entity_id = uuid.uuid4()
    node_id = uuid.uuid4()

    # 1. Create GraphNode
    node = GraphNode(
        id=node_id,
        tenant_id=tenant_id,
        workspace_id=tenant_id,
        name="Linked HubSpot Acme",
        type="company",
        source_ids=[str(entity_id)],  # Sole source reference
    )
    db_session.add(node)

    # 2. Create incident GraphEdges
    edge1 = GraphEdge(
        id=uuid.uuid4(),
        workspace_id=tenant_id,
        source_node_id=node_id,
        target_node_id=uuid.uuid4(),
        relationship_type="member_of",
    )
    db_session.add(edge1)

    # 3. Create DiscoveredEntity linked to that node
    ent = DiscoveredEntity(
        id=entity_id,
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h-acme",
        _discovered_type="company",
        status="linked",
        confidence_score=0.99,
        linked_to_graph_node_id=node_id,
        content_hash="acme-hash-123",
    )
    db_session.add(ent)
    db_session.commit()

    # 4. Perform DELETE API operation
    response = client.delete(f"/api/v1/ingestion/hubspot/entities/{entity_id}?performed_by=test_user")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 5. Assert cascading cleanup
    # DiscoveredEntity is deleted
    assert db_session.query(DiscoveredEntity).filter(DiscoveredEntity.id == entity_id).first() is None
    # GraphNode is deleted (since it was a single source)
    assert db_session.query(GraphNode).filter(GraphNode.id == node_id).first() is None
    # Incident GraphEdge is deleted
    assert db_session.query(GraphEdge).filter(GraphEdge.source_node_id == node_id).first() is None

    # Audit log entry exists
    audit = (
        db_session.query(IngestionAuditLog)
        .filter(
            IngestionAuditLog.entity_id == entity_id,
            IngestionAuditLog.operation == "delete",
        )
        .first()
    )
    assert audit is not None
    assert audit.performed_by == "test_user"
    assert audit.idempotency_key == "acme-hash-123"


def test_cascading_delete_multi_source_node(client: TestClient, db_session: Session, test_setup: Dict[str, Any]):
    """Test that deleting a DiscoveredEntity linked to a multi-source GraphNode retains the node but unlinks it."""
    tenant_id = test_setup["tenant_id"]
    entity_id1 = uuid.uuid4()
    entity_id2 = uuid.uuid4()
    node_id = uuid.uuid4()

    # 1. Create GraphNode with multiple source references
    node = GraphNode(
        id=node_id,
        tenant_id=tenant_id,
        workspace_id=tenant_id,
        name="Shared Node",
        type="company",
        source_ids=[str(entity_id1), str(entity_id2)],
    )
    db_session.add(node)

    # 2. Create entities
    ent1 = DiscoveredEntity(
        id=entity_id1,
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h1",
        _discovered_type="company",
        status="linked",
        confidence_score=0.99,
        linked_to_graph_node_id=node_id,
    )
    ent2 = DiscoveredEntity(
        id=entity_id2,
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h2",
        _discovered_type="company",
        status="linked",
        confidence_score=0.98,
        linked_to_graph_node_id=node_id,
    )
    db_session.add_all([ent1, ent2])
    db_session.commit()

    # 3. Perform DELETE API operation on the first entity
    response = client.delete(f"/api/v1/ingestion/hubspot/entities/{entity_id1}")
    assert response.status_code == 200

    # 4. Assertions
    # Entity 1 is deleted
    assert db_session.query(DiscoveredEntity).filter(DiscoveredEntity.id == entity_id1).first() is None
    # GraphNode is RETAINED
    node_after = db_session.query(GraphNode).filter(GraphNode.id == node_id).first()
    assert node_after is not None
    # Source list is updated to remove entity 1
    assert str(entity_id1) not in node_after.source_ids
    assert str(entity_id2) in node_after.source_ids


def test_unlink_entity(client: TestClient, db_session: Session, test_setup: Dict[str, Any]):
    """Test unlinking a DiscoveredEntity from a GraphNode resets status and clears connections."""
    tenant_id = test_setup["tenant_id"]
    entity_id = uuid.uuid4()
    node_id = uuid.uuid4()

    # Create GraphNode with multiple references
    node = GraphNode(
        id=node_id,
        tenant_id=tenant_id,
        workspace_id=tenant_id,
        name="Acme",
        type="company",
        source_ids=[str(entity_id), "another_id"],
    )
    db_session.add(node)

    # Create DiscoveredEntity
    ent = DiscoveredEntity(
        id=entity_id,
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h-acme",
        _discovered_type="company",
        status="linked",
        confidence_score=0.99,
        linked_to_graph_node_id=node_id,
        content_hash="acme-hash",
    )
    db_session.add(ent)
    db_session.commit()

    # 1. Trigger unlink
    response = client.post(f"/api/v1/ingestion/hubspot/entities/{entity_id}/unlink?performed_by=unlink_op")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 2. Check updated states
    db_session.refresh(ent)
    assert ent.status == "pending"
    assert ent.linked_to_graph_node_id is None

    # Check updated GraphNode source ids
    db_session.refresh(node)
    assert str(entity_id) not in node.source_ids

    # Check Audit Log
    audit = (
        db_session.query(IngestionAuditLog)
        .filter(
            IngestionAuditLog.entity_id == entity_id,
            IngestionAuditLog.operation == "unlink",
        )
        .first()
    )
    assert audit is not None
    assert audit.performed_by == "unlink_op"


def test_bulk_delete_entities(client: TestClient, db_session: Session, test_setup: Dict[str, Any]):
    """Test atomicity and cascading of bulk cascade deletions."""
    tenant_id = test_setup["tenant_id"]
    e1_id = uuid.uuid4()
    e2_id = uuid.uuid4()

    e1 = DiscoveredEntity(
        id=e1_id,
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h1",
        _discovered_type="contact",
        status="pending",
        confidence_score=0.8,
    )
    e2 = DiscoveredEntity(
        id=e2_id,
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h2",
        _discovered_type="contact",
        status="pending",
        confidence_score=0.9,
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    # Bulk delete call
    payload = {"entity_ids": [str(e1_id), str(e2_id)]}
    response = client.post("/api/v1/ingestion/hubspot/entities/bulk-delete?performed_by=bulk_op", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "deleted 2 out of 2" in response.json()["message"]

    # Verify db deletion
    assert db_session.query(DiscoveredEntity).filter(DiscoveredEntity.id.in_([e1_id, e2_id])).count() == 0


# ============================================================================
# Test Cases - Phase 3: Content Hashing & Idempotency
# ============================================================================


def test_stable_content_hash_calculation():
    """Verify that recursive sorting of properties keys generates stable SHA-256 signatures."""
    props1 = {
        "email": "abc@test.com",
        "nested": {"z": 10, "a": 1, "m": [1, 2, 3]},
        "role": "admin",
    }
    props2 = {
        "role": "admin",
        "nested": {"a": 1, "z": 10, "m": [1, 2, 3]},
        "email": "abc@test.com",
    }

    # Although keys are declared in different order, they sort identically
    hash1 = IngestionCRUDService.calculate_content_hash("Contact Name", "contact", props1)
    hash2 = IngestionCRUDService.calculate_content_hash("Contact Name", "contact", props2)
    assert hash1 == hash2


# ============================================================================
# Test Cases - Phase 4: Event Listeners & Knowledge Graph Syncing
# ============================================================================


def test_event_listener_sync_properties_on_update(db_session: Session, test_setup: Dict[str, Any]):
    """Test that modifying a DiscoveredEntity's properties automatically syncs to its promoted GraphNode."""
    tenant_id = test_setup["tenant_id"]
    entity_id = uuid.uuid4()
    node_id = uuid.uuid4()

    # Setup linked GraphNode
    node = GraphNode(
        id=node_id,
        tenant_id=tenant_id,
        workspace_id=tenant_id,
        name="Old Name",
        type="contact",
        source_ids=[str(entity_id)],
        properties={"phone": "123"},
    )
    db_session.add(node)

    # Setup DiscoveredEntity
    ent = DiscoveredEntity(
        id=entity_id,
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h-contact",
        _discovered_type="contact",
        entity_name="Old Name",
        status="linked",
        confidence_score=0.99,
        linked_to_graph_node_id=node_id,
        properties={"phone": "123"},
    )
    db_session.add(ent)
    db_session.commit()

    # Update DiscoveredEntity directly
    ent.entity_name = "New Unified Name"
    ent.properties = {"phone": "123", "address": "123 Main St"}
    db_session.add(ent)
    db_session.commit()  # Triggers after_update listener

    # Reload GraphNode to verify updates propagated
    db_session.refresh(node)
    assert node.name == "New Unified Name"
    assert node.properties["address"] == "123 Main St"


def test_event_listener_cleanup_on_direct_delete(db_session: Session, test_setup: Dict[str, Any]):
    """Test that deleting a DiscoveredEntity directly via db.delete cascades automatically via listeners."""
    tenant_id = test_setup["tenant_id"]
    entity_id = uuid.uuid4()
    node_id = uuid.uuid4()

    # Setup linked GraphNode
    node = GraphNode(
        id=node_id,
        tenant_id=tenant_id,
        workspace_id=tenant_id,
        name="To Be Orphaned Node",
        type="contact",
        source_ids=[str(entity_id)],
    )
    db_session.add(node)

    # Setup DiscoveredEntity
    ent = DiscoveredEntity(
        id=entity_id,
        tenant_id=tenant_id,
        source_record_type="hubspot",
        source_record_id="h-del",
        _discovered_type="contact",
        status="linked",
        confidence_score=0.99,
        linked_to_graph_node_id=node_id,
    )
    db_session.add(ent)
    db_session.commit()

    # Delete entity directly from DB
    db_session.delete(ent)
    db_session.commit()  # Triggers after_delete listener

    # Check that GraphNode was cascaded and deleted because it had no other sources
    assert db_session.query(GraphNode).filter(GraphNode.id == node_id).first() is None
