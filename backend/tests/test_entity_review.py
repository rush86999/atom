"""
Entity Review System Tests

Tests for human-in-the-loop review workflow including EntityReviewService,
API endpoints, and ReviewAnalyticsService.

Phase 323-04: Human-in-the-Loop Review System
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone

from core.entity_review_service import EntityReviewService
from core.review_analytics_service import ReviewAnalyticsService
from core.models import DiscoveredEntity, EntityTypeDefinition, GraphNode, User
from api.entity_review_routes import (
    ApproveEntityRequest,
    RejectEntityRequest,
    BulkApproveRequest,
    BulkRejectRequest
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def review_service(db_session):
    """EntityReviewService instance."""
    return EntityReviewService(db_session)


@pytest.fixture
def analytics_service(db_session):
    """ReviewAnalyticsService instance."""
    return ReviewAnalyticsService(db_session)


@pytest.fixture
def sample_entities(db_session):
    """Sample DiscoveredEntity instances for testing."""
    entities = [
        DiscoveredEntity(
            id=f"entity-{i:03d}",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder" if i < 3 else "SecurityEvent",
            properties={
                "po_number" if i < 3 else "event_id": f"PO-{i}" if i < 3 else f"EVT-{i}",
                "amount": 1000.0 + i * 100 if i < 3 else None,
                "severity": None if i < 3 else "high"
            },
            confidence_score=0.5 + i * 0.1,  # 0.5 to 0.9
            source_record_id=f"email-{i}",
            source_record_type="email",
            status="pending"
        )
        for i in range(1, 8)  # 7 entities
    ]

    for entity in entities:
        db_session.add(entity)
    db_session.commit()

    return entities


@pytest.fixture
def sample_user(db_session):
    """Sample user for authentication testing."""
    user = User(
        id="user-001",
        email="admin@example.com",
        tenant_id="tenant-001",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


# ============================================================================
# Test Class 1: Entity Review Service - Flagging
# ============================================================================

class TestEntityFlagging:
    """Tests for flagging entities for review."""

    @pytest.mark.asyncio
    async def test_flag_low_confidence_entities(self, review_service, sample_entities):
        """Test flagging entities with low confidence (<0.7)."""
        # Arrange - entities 1-3 have confidence 0.5, 0.6, 0.7
        # Act
        flagged_count = await review_service.flag_entities_for_review(
            tenant_id="tenant-001",
            confidence_threshold=0.7
        )

        # Assert - entities with confidence <0.7 should be flagged
        assert flagged_count >= 2  # At least 2 entities (0.5, 0.6)

        # Verify status updated
        flagged_entities = review_service.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.status == "needs_review"
        ).all()

        assert len(flagged_entities) >= 2
        assert all(e.confidence_score < 0.7 for e in flagged_entities)

    @pytest.mark.asyncio
    async def test_flag_novel_types(self, review_service, db_session):
        """Test flagging novel types (<5 samples)."""
        # Arrange - Create 3 entities of novel type "NovelType"
        for i in range(3):
            entity = DiscoveredEntity(
                id=f"novel-{i}",
                tenant_id="tenant-001",
                workspace_id="workspace-001",
                _discovered_type="NovelType",
                properties={"data": f"value-{i}"},
                confidence_score=0.8,
                source_record_id=f"email-{i}",
                source_record_type="email",
                status="pending"
            )
            db_session.add(entity)
        db_session.commit()

        # Act
        flagged_count = await review_service.flag_entities_for_review(
            tenant_id="tenant-001",
            min_sample_count=5
        )

        # Assert
        assert flagged_count >= 3  # Novel type entities flagged

        novel_entities = db_session.query(DiscoveredEntity).filter(
            DiscoveredEntity._discovered_type == "NovelType",
            DiscoveredEntity.status == "needs_review"
        ).all()

        assert len(novel_entities) == 3

    @pytest.mark.asyncio
    async def test_flag_combines_low_confidence_and_novel_types(self, review_service, db_session):
        """Test that flagging combines both criteria."""
        # Arrange - Create mixed entities
        # Low confidence, common type
        entity1 = DiscoveredEntity(
            id="mixed-1",
            tenant_id="tenant-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-1"},
            confidence_score=0.5,  # Low
            source_record_id="email-1",
            source_record_type="email",
            status="pending"
        )

        # High confidence, novel type
        entity2 = DiscoveredEntity(
            id="mixed-2",
            tenant_id="tenant-001",
            _discovered_type="RareType",  # Novel
            properties={"data": "value"},
            confidence_score=0.9,  # High
            source_record_id="email-2",
            source_record_type="email",
            status="pending"
        )

        review_service.db.add(entity1)
        review_service.db.add(entity2)
        review_service.db.commit()

        # Act
        flagged_count = await review_service.flag_entities_for_review(
            tenant_id="tenant-001",
            confidence_threshold=0.7,
            min_sample_count=5
        )

        # Assert - Both should be flagged
        assert flagged_count >= 2


# ============================================================================
# Test Class 2: Entity Review Service - Approval
# ============================================================================

class TestEntityApproval:
    """Tests for approving entities."""

    @pytest.mark.asyncio
    async def test_approve_entity_links_to_graph(self, review_service, db_session):
        """Test that approval creates GraphNode."""
        # Arrange
        entity = DiscoveredEntity(
            id="approve-001",
            tenant_id="tenant-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-123"},
            confidence_score=0.8,
            source_record_id="email-1",
            source_record_type="email",
            status="needs_review"
        )
        db_session.add(entity)
        db_session.commit()

        # Create EntityTypeDefinition
        entity_type = EntityTypeDefinition(
            id="type-001",
            tenant_id="tenant-001",
            slug="purchase_order",
            display_name="PurchaseOrder",
            json_schema={"type": "object"},
            source="llm_discovery",
            is_active=True
        )
        db_session.add(entity_type)
        db_session.commit()

        # Act
        graph_node = await review_service.approve_entity(
            entity_id="approve-001",
            entity_type_slug="purchase_order",
            reviewer_user_id="user-001",
            notes="Valid extraction"
        )

        # Assert
        assert graph_node is not None
        assert graph_node.type == "purchase_order"

        # Verify entity status updated
        entity = db_session.query(DiscoveredEntity).filter(
            DiscoveredEntity.id == "approve-001"
        ).first()

        assert entity.status == "linked"
        assert entity.linked_to_graph_node_id == graph_node.id
        assert entity.extraction_metadata["review_decision"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_entity_creates_type_if_missing(self, review_service, db_session):
        """Test that approval creates EntityTypeDefinition if missing."""
        # Arrange
        entity = DiscoveredEntity(
            id="approve-002",
            tenant_id="tenant-001",
            _discovered_type="Invoice",
            properties={"invoice_number": "INV-001"},
            confidence_score=0.8,
            source_record_id="email-2",
            source_record_type="email",
            status="needs_review"
        )
        db_session.add(entity)
        db_session.commit()

        # Act - Invoice type doesn't exist yet
        graph_node = await review_service.approve_entity(
            entity_id="approve-002",
            entity_type_slug="invoice",
            reviewer_user_id="user-001",
            create_type_if_missing=True
        )

        # Assert
        assert graph_node is not None
        assert graph_node.type == "invoice"

        # Verify EntityTypeDefinition was created
        entity_type = db_session.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.slug == "invoice"
        ).first()

        assert entity_type is not None


# ============================================================================
# Test Class 3: Entity Review Service - Rejection
# ============================================================================

class TestEntityRejection:
    """Tests for rejecting entities."""

    @pytest.mark.asyncio
    async def test_reject_entity_updates_status(self, review_service, db_session):
        """Test that rejection updates entity status."""
        # Arrange
        entity = DiscoveredEntity(
            id="reject-001",
            tenant_id="tenant-001",
            _discovered_type="InvalidType",
            properties={"data": "bad"},
            confidence_score=0.8,
            source_record_id="email-1",
            source_record_type="email",
            status="needs_review"
        )
        db_session.add(entity)
        db_session.commit()

        # Act
        success = await review_service.reject_entity(
            entity_id="reject-001",
            reviewer_user_id="user-001",
            reason="hallucination",
            notes="Entity type doesn't exist"
        )

        # Assert
        assert success is True

        entity = db_session.query(DiscoveredEntity).filter(
            DiscoveredEntity.id == "reject-001"
        ).first()

        assert entity.status == "rejected"
        assert entity.extraction_metadata["review_decision"] == "rejected"
        assert entity.extraction_metadata["rejection_reason"] == "hallucination"

    @pytest.mark.asyncio
    async def test_reject_entity_tracks_reasons(self, review_service, db_session):
        """Test that rejection reasons are tracked correctly."""
        # Arrange
        entity = DiscoveredEntity(
            id="reject-002",
            tenant_id="tenant-001",
            _discovered_type="GenericEmail",
            properties={"subject": "Hello"},
            confidence_score=0.6,
            source_record_id="email-2",
            source_record_type="email",
            status="needs_review"
        )
        db_session.add(entity)
        db_session.commit()

        # Act
        await review_service.reject_entity(
            entity_id="reject-002",
            reviewer_user_id="user-001",
            reason="incorrect_type",
            notes="Too generic"
        )

        # Assert
        entity = db_session.query(DiscoveredEntity).filter(
            DiscoveredEntity.id == "reject-002"
        ).first()

        assert entity.extraction_metadata["rejection_reason"] == "incorrect_type"
        assert entity.extraction_metadata["review_notes"] == "Too generic"


# ============================================================================
# Test Class 4: Bulk Operations
# ============================================================================

class TestBulkOperations:
    """Tests for bulk approval and rejection."""

    @pytest.mark.asyncio
    async def test_bulk_approve_by_type(self, review_service, db_session):
        """Test bulk approving entities by type."""
        # Arrange - Create 5 PurchaseOrder entities
        for i in range(5):
            entity = DiscoveredEntity(
                id=f"bulk-po-{i}",
                tenant_id="tenant-001",
                _discovered_type="PurchaseOrder",
                properties={"po_number": f"PO-{i}"},
                confidence_score=0.8 + i * 0.02,
                source_record_id=f"email-{i}",
                source_record_type="email",
                status="needs_review"
            )
            db_session.add(entity)

        # Create EntityTypeDefinition
        entity_type = EntityTypeDefinition(
            id="type-bulk",
            tenant_id="tenant-001",
            slug="purchase_order",
            display_name="PurchaseOrder",
            json_schema={"type": "object"},
            source="llm_discovery",
            is_active=True
        )
        db_session.add(entity_type)
        db_session.commit()

        # Act
        approved_count = await review_service.bulk_approve_by_type(
            discovered_type="PurchaseOrder",
            entity_type_slug="purchase_order",
            reviewer_user_id="user-001",
            tenant_id="tenant-001"
        )

        # Assert
        assert approved_count == 5

        # Verify all linked
        linked_count = db_session.query(DiscoveredEntity).filter(
            DiscoveredEntity._discovered_type == "PurchaseOrder",
            DiscoveredEntity.status == "linked"
        ).count()

        assert linked_count == 5

    @pytest.mark.asyncio
    async def test_bulk_reject_by_type(self, review_service, db_session):
        """Test bulk rejecting entities by type."""
        # Arrange - Create 3 InvalidType entities
        for i in range(3):
            entity = DiscoveredEntity(
                id=f"bulk-reject-{i}",
                tenant_id="tenant-001",
                _discovered_type="InvalidType",
                properties={"data": f"value-{i}"},
                confidence_score=0.8,
                source_record_id=f"email-{i}",
                source_record_type="email",
                status="needs_review"
            )
            db_session.add(entity)
        db_session.commit()

        # Act
        rejected_count = await review_service.bulk_reject_by_type(
            discovered_type="InvalidType",
            reviewer_user_id="user-001",
            tenant_id="tenant-001",
            reason="bulk_rejection"
        )

        # Assert
        assert rejected_count == 3

        # Verify all rejected
        rejected_entities = db_session.query(DiscoveredEntity).filter(
            DiscoveredEntity._discovered_type == "InvalidType",
            DiscoveredEntity.status == "rejected"
        ).all()

        assert len(rejected_entities) == 3
        assert all(
            e.extraction_metadata.get("rejection_reason") == "bulk_rejection"
            for e in rejected_entities
        )


# ============================================================================
# Test Class 5: Review Statistics
# ============================================================================

class TestReviewStatistics:
    """Tests for review statistics."""

    def test_get_review_stats(self, review_service, sample_entities):
        """Test getting review statistics."""
        # Act
        stats = review_service.get_review_stats(tenant_id="tenant-001")

        # Assert
        assert "pending" in stats
        assert "needs_review" in stats
        assert "linked" in stats
        assert "rejected" in stats
        assert "total" in stats
        assert "approval_rate" in stats
        assert "unique_types" in stats

        # Verify total count
        assert stats["total"] == 7  # 7 sample entities

    def test_get_entities_for_review(self, review_service, sample_entities):
        """Test getting entities pending review."""
        # Flag some entities
        for entity in sample_entities[:3]:
            entity.status = "needs_review"
        review_service.db.commit()

        # Act
        entities = review_service.get_entities_for_review(
            tenant_id="tenant-001",
            status="needs_review",
            limit=10
        )

        # Assert
        assert len(entities) == 3
        assert all(e.status == "needs_review" for e in entities)


# ============================================================================
# Test Class 6: Review Analytics
# ============================================================================

class TestReviewAnalytics:
    """Tests for review analytics service."""

    @pytest.mark.asyncio
    async def test_get_review_stats(self, analytics_service, db_session):
        """Test getting review statistics."""
        # Arrange - Create entities with different statuses
        for i, status in enumerate(["linked", "linked", "rejected", "pending"]):
            entity = DiscoveredEntity(
                id=f"analytics-{i}",
                tenant_id="tenant-001",
                _discovered_type="TestType",
                properties={"data": f"value-{i}"},
                confidence_score=0.7 + i * 0.05,
                source_record_id=f"email-{i}",
                source_record_type="email",
                status=status
            )
            db_session.add(entity)
        db_session.commit()

        # Act
        stats = await analytics_service.get_review_stats(
            tenant_id="tenant-001",
            days=30
        )

        # Assert
        assert stats["total_reviewed"] == 3  # linked + rejected
        assert stats["approved"] == 2
        assert stats["rejected"] == 1
        assert stats["approval_rate"] == 2/3
        assert stats["rejection_rate"] == 1/3

    @pytest.mark.asyncio
    async def test_get_rejection_reasons(self, analytics_service, db_session):
        """Test getting rejection reason breakdown."""
        # Arrange - Create rejected entities with reasons
        for i, reason in enumerate(["hallucination", "incorrect_type", "missing_data"]):
            entity = DiscoveredEntity(
                id=f"reject-reason-{i}",
                tenant_id="tenant-001",
                _discovered_type="TestType",
                properties={"data": "value"},
                confidence_score=0.8,
                source_record_id=f"email-{i}",
                source_record_type="email",
                status="rejected",
                extraction_metadata={"rejection_reason": reason}
            )
            db_session.add(entity)
        db_session.commit()

        # Act
        reasons = await analytics_service.get_rejection_reasons(
            tenant_id="tenant-001",
            days=30
        )

        # Assert
        assert reasons["hallucination"] == 1
        assert reasons["incorrect_type"] == 1
        assert reasons["missing_data"] == 1

    @pytest.mark.asyncio
    async def test_get_type_accuracy_stats(self, analytics_service, db_session):
        """Test getting accuracy statistics by type."""
        # Arrange - Create entities of different types
        for i in range(10):
            entity = DiscoveredEntity(
                id=f"accuracy-{i}",
                tenant_id="tenant-001",
                _discovered_type="PurchaseOrder" if i < 7 else "Invoice",
                properties={"data": f"value-{i}"},
                confidence_score=0.8,
                source_record_id=f"email-{i}",
                source_record_type="email",
                status="linked" if i < 7 else "rejected"
            )
            db_session.add(entity)
        db_session.commit()

        # Act
        type_stats = await analytics_service.get_type_accuracy_stats(
            tenant_id="tenant-001",
            days=30
        )

        # Assert
        assert len(type_stats) >= 2

        # Find PurchaseOrder stats
        po_stats = next(s for s in type_stats if s["discovered_type"] == "PurchaseOrder")
        assert po_stats["total_reviewed"] == 7
        assert po_stats["approved"] == 7
        assert po_stats["approval_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_generate_prompt_feedback(self, analytics_service, db_session):
        """Test generating prompt improvement feedback."""
        # Arrange - Create rejected entities
        for i in range(5):
            entity = DiscoveredEntity(
                id=f"feedback-{i}",
                tenant_id="tenant-001",
                _discovered_type="ProblematicType",
                properties={"data": f"value-{i}"},
                confidence_score=0.6,
                source_record_id=f"email-{i}",
                source_record_type="email",
                status="rejected",
                extraction_metadata={"rejection_reason": "hallucination"}
            )
            db_session.add(entity)
        db_session.commit()

        # Act
        feedback = await analytics_service.generate_prompt_feedback(
            tenant_id="tenant-001",
            days=30
        )

        # Assert
        assert len(feedback) >= 1

        # Should have feedback about high rejection rate
        high_rejection_feedback = next(
            (f for f in feedback if f["type"] == "high_rejection_rate"),
            None
        )
        assert high_rejection_feedback is not None
        assert high_rejection_feedback["entity_type"] == "ProblematicType"


# ============================================================================
# Test Class 7: API Request Models
# ============================================================================

class TestAPIRequestModels:
    """Tests for API request/response models."""

    def test_approve_entity_request(self):
        """Test ApproveEntityRequest validation."""
        # Valid request
        request = ApproveEntityRequest(
            entity_type_slug="purchase_order",
            notes="Valid extraction"
        )
        assert request.entity_type_slug == "purchase_order"
        assert request.notes == "Valid extraction"

    def test_reject_entity_request(self):
        """Test RejectEntityRequest validation."""
        # Valid request
        request = RejectEntityRequest(
            reason="hallucination",
            notes="Entity doesn't exist"
        )
        assert request.reason == "hallucination"
        assert request.notes == "Entity doesn't exist"

    def test_bulk_approve_request(self):
        """Test BulkApproveRequest validation."""
        # Valid request
        request = BulkApproveRequest(
            discovered_type="PurchaseOrder",
            entity_type_slug="purchase_order",
            confidence_min=0.7
        )
        assert request.discovered_type == "PurchaseOrder"
        assert request.entity_type_slug == "purchase_order"
        assert request.confidence_min == 0.7

    def test_bulk_reject_request(self):
        """Test BulkRejectRequest validation."""
        # Valid request
        request = BulkRejectRequest(
            discovered_type="InvalidType",
            reason="incorrect_type"
        )
        assert request.discovered_type == "InvalidType"
        assert request.reason == "incorrect_type"
