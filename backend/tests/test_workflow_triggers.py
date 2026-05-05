"""
Workflow Trigger Service Tests

Tests for workflow trigger engine, entity type mapping, property-based routing,
debouncing, and trigger history.

Phase 323-05: Workflow Automation Triggers
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone, timedelta

from core.workflow_trigger_service import WorkflowTriggerService
from core.models import DiscoveredEntity


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def trigger_service(db_session):
    """WorkflowTriggerService instance."""
    return WorkflowTriggerService(db_session)


@pytest.fixture
def sample_entities():
    """Sample DiscoveredEntity instances for testing."""
    return [
        DiscoveredEntity(
            id="po-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={
                "po_number": "PO-12345",
                "vendor": "Acme Corp",
                "amount": 5000.0,
                "currency": "USD"
            },
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        ),
        DiscoveredEntity(
            id="security-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="SecurityEvent",
            properties={
                "event_type": "intrusion_detected",
                "severity": "critical",
                "user": "john@example.com",
                "location": "Unknown IP"
            },
            confidence_score=0.95,
            source_record_id="email-002",
            source_record_type="email"
        ),
        DiscoveredEntity(
            id="invoice-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Invoice",
            properties={
                "invoice_number": "INV-001",
                "vendor": "Global Supplies",
                "amount": 15000.0,
                "currency": "USD"
            },
            confidence_score=0.85,
            source_record_id="email-003",
            source_record_type="email"
        )
    ]


# ============================================================================
# Test Class 1: Workflow Registration
# ============================================================================

class TestWorkflowRegistration:
    """Tests for workflow trigger registration."""

    def test_register_workflow_trigger(self, trigger_service):
        """Test registering a workflow trigger."""
        # Act
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        # Assert
        mappings = trigger_service.get_workflow_mappings("PurchaseOrder")
        assert len(mappings) == 1
        assert mappings[0]["workflow_id"] == "po_approval"
        assert mappings[0]["priority"] == 10
        assert mappings[0]["condition"] == {"amount": {"$gte": 1000}}

    def test_register_multiple_triggers_same_type(self, trigger_service):
        """Test registering multiple triggers for same entity type."""
        # Arrange - Register triggers with different priorities
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="standard_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="executive_approval",
            condition={"amount": {"$gte": 50000}},
            priority=20  # Higher priority
        )

        # Act
        mappings = trigger_service.get_workflow_mappings("PurchaseOrder")

        # Assert - Should be sorted by priority (descending)
        assert len(mappings) == 2
        assert mappings[0]["workflow_id"] == "executive_approval"  # Priority 20
        assert mappings[1]["workflow_id"] == "standard_approval"  # Priority 10

    def test_unregister_workflow_trigger(self, trigger_service):
        """Test unregistering a workflow trigger."""
        # Arrange - Register trigger
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        # Act
        removed = trigger_service.unregister_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval"
        )

        # Assert
        assert removed is True

        mappings = trigger_service.get_workflow_mappings("PurchaseOrder")
        assert len(mappings) == 0

    def test_unregister_nonexistent_trigger(self, trigger_service):
        """Test unregistering a trigger that doesn't exist."""
        # Act
        removed = trigger_service.unregister_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="nonexistent"
        )

        # Assert
        assert removed is False


# ============================================================================
# Test Class 2: Workflow Triggering
# ============================================================================

class TestWorkflowTriggering:
    """Tests for workflow triggering logic."""

    @pytest.mark.asyncio
    async def test_trigger_workflow_on_condition_match(self, trigger_service):
        """Test triggering workflow when condition matches."""
        # Arrange - Register trigger
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        # Create entity with matching condition
        entity = DiscoveredEntity(
            id="po-trigger-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-123", "amount": 5000.0},
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert len(triggered) == 1
        assert "po_approval" in triggered

    @pytest.mark.asyncio
    async def test_no_trigger_when_condition_not_match(self, trigger_service):
        """Test not triggering when condition doesn't match."""
        # Arrange - Register trigger
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        # Create entity with non-matching condition
        entity = DiscoveredEntity(
            id="po-no-trigger-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-999", "amount": 500.0},
            confidence_score=0.9,
            source_record_id="email-002",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_trigger_with_no_condition(self, trigger_service):
        """Test triggering when there's no condition (always trigger)."""
        # Arrange - Register trigger with no condition
        trigger_service.register_workflow_trigger(
            entity_type="Invoice",
            workflow_id="invoice_processing",
            condition=None,
            priority=5
        )

        # Create entity
        entity = DiscoveredEntity(
            id="invoice-always-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Invoice",
            properties={"invoice_number": "INV-001"},
            confidence_score=0.85,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert len(triggered) == 1
        assert "invoice_processing" in triggered

    @pytest.mark.asyncio
    async def test_no_registered_workflows_for_type(self, trigger_service):
        """Test entity type with no registered workflows."""
        # Create entity without registered workflows
        entity = DiscoveredEntity(
            id="no-workflow-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="NovelType",
            properties={"data": "value"},
            confidence_score=0.8,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert len(triggered) == 0


# ============================================================================
# Test Class 3: Property-Based Routing
# ============================================================================

class TestPropertyBasedRouting:
    """Tests for property-based routing rules."""

    @pytest.mark.asyncio
    async def test_route_by_equality_condition(self, trigger_service):
        """Test routing by property equality."""
        # Arrange - Register trigger for critical security events
        trigger_service.register_workflow_trigger(
            entity_type="SecurityEvent",
            workflow_id="security_urgent",
            condition={"severity": "critical"},
            priority=20
        )

        # Create critical security event
        entity = DiscoveredEntity(
            id="security-critical-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="SecurityEvent",
            properties={
                "event_type": "intrusion",
                "severity": "critical"
            },
            confidence_score=0.95,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert "security_urgent" in triggered

    @pytest.mark.asyncio
    async def test_route_by_range_condition(self, trigger_service):
        """Test routing by range filters ($gt, $gte, $lt, $lte)."""
        # Arrange - Register trigger for large POs
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="executive_approval",
            condition={"amount": {"$gte": 50000}},
            priority=20
        )

        # Create large PO
        entity = DiscoveredEntity(
            id="po-large-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-999", "amount": 75000.0},
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert "executive_approval" in triggered

    @pytest.mark.asyncio
    async def test_route_by_in_list_condition(self, trigger_service):
        """Test routing by $in operator."""
        # Arrange - Register trigger for enterprise customers
        trigger_service.register_workflow_trigger(
            entity_type="Lead",
            workflow_id="enterprise_lead_routing",
            condition={"customer_tier": {"$in": ["enterprise", "pro"]}},
            priority=15
        )

        # Create enterprise lead
        entity = DiscoveredEntity(
            id="lead-enterprise-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Lead",
            properties={"name": "John", "customer_tier": "enterprise"},
            confidence_score=0.85,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert "enterprise_lead_routing" in triggered

    @pytest.mark.asyncio
    async def test_route_by_regex_condition(self, trigger_service):
        """Test routing by $regex operator."""
        # Arrange - Register trigger for company email addresses
        trigger_service.register_workflow_trigger(
            entity_type="Lead",
            workflow_id="employee_lead_routing",
            condition={"email": {"$regex": ".*@atom\\.com$"}},
            priority=10
        )

        # Create lead with company email
        entity = DiscoveredEntity(
            id="lead-employee-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Lead",
            properties={"name": "Jane", "email": "jane@atom.com"},
            confidence_score=0.85,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert "employee_lead_routing" in triggered

    @pytest.mark.asyncio
    async def test_route_by_logical_and(self, trigger_service):
        """Test routing by $and logical operator."""
        # Arrange - Register trigger with AND condition
        trigger_service.register_workflow_trigger(
            entity_type="Ticket",
            workflow_id="vip_support_routing",
            condition={
                "$and": [
                    {"severity": "high"},
                    {"customer_tier": "enterprise"}
                ]
            },
            priority=20
        )

        # Create VIP ticket
        entity = DiscoveredEntity(
            id="ticket-vip-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Ticket",
            properties={
                "subject": "System down",
                "severity": "high",
                "customer_tier": "enterprise"
            },
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert "vip_support_routing" in triggered

    @pytest.mark.asyncio
    async def test_route_by_logical_or(self, trigger_service):
        """Test routing by $or logical operator."""
        # Arrange - Register trigger with OR condition
        trigger_service.register_workflow_trigger(
            entity_type="Ticket",
            workflow_id="urgent_support",
            condition={
                "$or": [
                    {"severity": "critical"},
                    {"severity": "high"}
                ]
            },
            priority=15
        )

        # Create high severity ticket
        entity = DiscoveredEntity(
            id="ticket-urgent-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Ticket",
            properties={
                "subject": "Login issue",
                "severity": "high"
            },
            confidence_score=0.85,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert "urgent_support" in triggered


# ============================================================================
# Test Class 4: Debouncing
# ============================================================================

class TestDebouncing:
    """Tests for debounce functionality."""

    @pytest.mark.asyncio
    async def test_debounce_prevents_duplicate_triggers(self, trigger_service):
        """Test that debouncing prevents duplicate triggers."""
        # Arrange - Register trigger
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        # Create entity
        entity = DiscoveredEntity(
            id="po-debounce-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-123", "amount": 5000.0},
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act - Trigger twice
        triggered1 = await trigger_service.check_and_trigger(entity)
        triggered2 = await trigger_service.check_and_trigger(entity)

        # Assert - Second trigger should be debounced
        assert len(triggered1) == 1
        assert len(triggered2) == 0

    @pytest.mark.asyncio
    async def test_force_trigger_skips_debounce(self, trigger_service):
        """Test that force_trigger bypasses debouncing."""
        # Arrange - Register trigger and trigger once
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        entity = DiscoveredEntity(
            id="po-force-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-123", "amount": 5000.0},
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        )

        await trigger_service.check_and_trigger(entity)

        # Act - Force trigger (skip debounce)
        triggered = await trigger_service.check_and_trigger(entity, force_trigger=True)

        # Assert
        assert len(triggered) == 1

    def test_debounce_cache_expires_after_ttl(self, trigger_service):
        """Test that debounce cache expires after TTL."""
        # Arrange - Register trigger and trigger entity
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        entity = DiscoveredEntity(
            id="po-ttl-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-123", "amount": 5000.0},
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Manually add to debounce cache with old timestamp
        entity_hash = trigger_service._hash_entity(entity)
        old_timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)
        trigger_service.debounce_cache[entity_hash] = old_timestamp

        # Act - Check if debounced (should be False due to TTL)
        is_debounced = trigger_service._is_debounced(entity_hash)

        # Assert
        assert is_debounced is False  # Should not be debounced (TTL expired)

    def test_clear_debounce_cache(self, trigger_service):
        """Test clearing debounce cache."""
        # Arrange - Add item to cache
        trigger_service.debounce_cache["test-hash"] = datetime.now(timezone.utc)

        # Act
        trigger_service.clear_debounce_cache()

        # Assert
        assert len(trigger_service.debounce_cache) == 0


# ============================================================================
# Test Class 5: Trigger History
# ============================================================================

class TestTriggerHistory:
    """Tests for trigger history tracking."""

    @pytest.mark.asyncio
    async def test_trigger_history_tracks_workflows(self, trigger_service):
        """Test that trigger history records triggered workflows."""
        # Arrange - Register trigger
        trigger_service.register_workflow_trigger(
            entity_type="SecurityEvent",
            workflow_id="security_alert",
            condition={"severity": "critical"},
            priority=20
        )

        entity = DiscoveredEntity(
            id="security-history-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="SecurityEvent",
            properties={"severity": "critical"},
            confidence_score=0.95,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act - Trigger workflow
        await trigger_service.check_and_trigger(entity)

        # Assert - Check trigger history
        history = trigger_service.get_triggered_workflows("security-history-001")
        assert len(history) == 1
        assert history[0]["entity_type"] == "SecurityEvent"
        assert "security_alert" in history[0]["triggered_workflows"]

    def test_get_workflow_mappings(self, trigger_service):
        """Test getting workflow mappings."""
        # Arrange - Register multiple triggers
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        trigger_service.register_workflow_trigger(
            entity_type="SecurityEvent",
            workflow_id="security_alert",
            condition={"severity": "critical"},
            priority=20
        )

        # Act - Get all mappings
        all_mappings = trigger_service.get_workflow_mappings()

        # Assert
        assert "PurchaseOrder" in all_mappings
        assert "SecurityEvent" in all_mappings
        assert len(all_mappings["PurchaseOrder"]) == 1
        assert len(all_mappings["SecurityEvent"]) == 1

    def test_get_workflow_mappings_filtered_by_type(self, trigger_service):
        """Test getting workflow mappings for specific type."""
        # Arrange
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_approval",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        # Act - Get mappings for specific type
        mappings = trigger_service.get_workflow_mappings("PurchaseOrder")

        # Assert
        assert "PurchaseOrder" in mappings
        assert len(mappings["PurchaseOrder"]) == 1

    def test_clear_trigger_history(self, trigger_service):
        """Test clearing trigger history."""
        # Arrange - Add to history
        trigger_service.trigger_history["entity-001"] = [
            {
                "triggered_at": "2026-05-05T10:00:00Z",
                "triggered_workflows": ["workflow1"],
                "entity_type": "TestType"
            }
        ]

        # Act - Clear specific entity history
        trigger_service.clear_trigger_history("entity-001")

        # Assert
        assert "entity-001" not in trigger_service.trigger_history

    def test_clear_all_trigger_history(self, trigger_service):
        """Test clearing all trigger history."""
        # Arrange - Add multiple histories
        trigger_service.trigger_history["entity-001"] = [{"test": "data1"}]
        trigger_service.trigger_history["entity-002"] = [{"test": "data2"}]

        # Act - Clear all history
        trigger_service.clear_trigger_history()

        # Assert
        assert len(trigger_service.trigger_history) == 0


# ============================================================================
# Test Class 6: Entity Hashing
# ============================================================================

class TestEntityHashing:
    """Tests for entity hashing for deduplication."""

    def test_hash_entity_is_stable(self, trigger_service):
        """Test that entity hash is stable (same input = same hash)."""
        entity = DiscoveredEntity(
            id="hash-test-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-123", "amount": 5000.0},
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act - Hash twice
        hash1 = trigger_service._hash_entity(entity)
        hash2 = trigger_service._hash_entity(entity)

        # Assert - Should be same
        assert hash1 == hash2

    def test_hash_entity_different_for_different_props(self, trigger_service):
        """Test that different entities produce different hashes."""
        entity1 = DiscoveredEntity(
            id="hash-diff-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-123", "amount": 5000.0},
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        )

        entity2 = DiscoveredEntity(
            id="hash-diff-002",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-456", "amount": 3000.0},
            confidence_score=0.9,
            source_record_id="email-002",
            source_record_type="email"
        )

        # Act
        hash1 = trigger_service._hash_entity(entity1)
        hash2 = trigger_service._hash_entity(entity2)

        # Assert - Should be different
        assert hash1 != hash2


# ============================================================================
# Test Class 7: Operator Evaluation
# ============================================================================

class TestOperatorEvaluation:
    """Tests for operator evaluation in conditions."""

    def test_evaluate_operator_eq(self, trigger_service):
        """Test $eq operator."""
        assert trigger_service._evaluate_operator("value", "$eq", "value") is True
        assert trigger_service._evaluate_operator("value", "$eq", "different") is False

    def test_evaluate_operator_ne(self, trigger_service):
        """Test $ne operator."""
        assert trigger_service._evaluate_operator("value", "$ne", "different") is True
        assert trigger_service._evaluate_operator("value", "$ne", "value") is False

    def test_evaluate_operator_gt(self, trigger_service):
        """Test $gt operator."""
        assert trigger_service._evaluate_operator(5000, "$gt", 1000) is True
        assert trigger_service._evaluate_operator(1000, "$gt", 5000) is False
        assert trigger_service._evaluate_operator(None, "$gt", 1000) is False

    def test_evaluate_operator_gte(self, trigger_service):
        """Test $gte operator."""
        assert trigger_service._evaluate_operator(1000, "$gte", 1000) is True
        assert trigger_service._evaluate_operator(5000, "$gte", 1000) is True
        assert trigger_service._evaluate_operator(100, "$gte", 1000) is False

    def test_evaluate_operator_lt(self, trigger_service):
        """Test $lt operator."""
        assert trigger_service._evaluate_operator(1000, "$lt", 5000) is True
        assert trigger_service._evaluate_operator(5000, "$lt", 1000) is False

    def test_evaluate_operator_lte(self, trigger_service):
        """Test $lte operator."""
        assert trigger_service._evaluate_operator(1000, "$lte", 1000) is True
        assert trigger_service._evaluate_operator(1000, "$lte", 5000) is True
        assert trigger_service._evaluate_operator(5000, "$lte", 1000) is False

    def test_evaluate_operator_in(self, trigger_service):
        """Test $in operator."""
        assert trigger_service._evaluate_operator("value", "$in", ["value", "other"]) is True
        assert trigger_service._evaluate_operator("missing", "$in", ["value", "other"]) is False

    def test_evaluate_operator_nin(self, trigger_service):
        """Test $nin operator."""
        assert trigger_service._evaluate_operator("missing", "$nin", ["value", "other"]) is True
        assert trigger_service._evaluate_operator("value", "$nin", ["value", "other"]) is False

    def test_evaluate_operator_regex(self, trigger_service):
        """Test $regex operator."""
        import re
        pattern = re.compile(r".*@atom\.com$")
        assert trigger_service._evaluate_operator("jane@atom.com", "$regex", r".*@atom\.com$") is True
        assert trigger_service._evaluate_operator("jane@example.com", "$regex", r".*@atom\.com$") is False

    def test_evaluate_operator_exists(self, trigger_service):
        """Test $exists operator."""
        assert trigger_service._evaluate_operator("value", "$exists", True) is True
        assert trigger_service._evaluate_operator(None, "$exists", True) is False
        assert trigger_service._evaluate_operator("value", "$exists", False) is False


# ============================================================================
# Test Class 8: Integration Tests
# ============================================================================

class TestWorkflowTriggerIntegration:
    """Integration tests for complete workflow triggering."""

    @pytest.mark.asyncio
    async def test_complete_workflow_trigger_lifecycle(self, trigger_service):
        """Test complete workflow from registration to execution."""
        # Arrange - Register multiple triggers
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="standard_approval",
            condition={"amount": {"$gte": 1000, "$lte": 10000}},
            priority=10
        )

        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="executive_approval",
            condition={"amount": {"$gt": 10000}},
            priority=20
        )

        # Create PO requiring executive approval
        entity = DiscoveredEntity(
            id="po-integration-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-EXEC", "amount": 75000.0},
            confidence_score=0.9,
            source_record_id="email-001",
            source_record_type="email"
        )

        # Act
        triggered = await trigger_service.check_and_trigger(entity)

        # Assert
        assert "executive_approval" in triggered
        assert "standard_approval" not in triggered  # Executive priority higher

        # Check metadata
        assert "triggered_workflows" in entity.extraction_metadata
        assert len(entity.extraction_metadata["triggered_workflows"]) == 1

    @pytest.mark.asyncio
    async def test_multiple_entity_types(self, trigger_service, sample_entities):
        """Test triggering workflows for multiple entity types."""
        # Arrange - Register triggers for each type
        trigger_service.register_workflow_trigger(
            entity_type="PurchaseOrder",
            workflow_id="po_workflow",
            condition={"amount": {"$gte": 1000}},
            priority=10
        )

        trigger_service.register_workflow_trigger(
            entity_type="SecurityEvent",
            workflow_id="security_workflow",
            condition={"severity": "critical"},
            priority=20
        )

        trigger_service.register_workflow_trigger(
            entity_type="Invoice",
            workflow_id="invoice_workflow",
            condition={"amount": {"$gte": 100}},
            priority=5
        )

        # Act - Trigger workflows for all entities
        all_triggered = []
        for entity in sample_entities:
            triggered = await trigger_service.check_and_trigger(entity)
            all_triggered.extend(triggered)

        # Assert - Should trigger workflows
        assert len(all_triggered) >= 2  # At least 2 should match
        assert "po_workflow" in all_triggered
        assert "security_workflow" in all_triggered
        assert "invoice_workflow" in all_triggered
