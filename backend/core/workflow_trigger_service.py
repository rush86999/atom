"""
Workflow Trigger Service

Automatically triggers workflows when specific entity types are discovered.
Supports entity type → workflow mapping, property-based routing, and debouncing.

Phase 323-05: Workflow Automation Triggers
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from collections import defaultdict

from core.models import DiscoveredEntity

logger = logging.getLogger(__name__)


class WorkflowTriggerService:
    """
    Workflow trigger engine for automatic workflow execution.

    Features:
    - Entity type → workflow mapping
    - Property-based routing (e.g., severity="critical" → urgent workflow)
    - Trigger conditions (thresholds, filters)
    - Debouncing (prevent duplicate triggers)
    - Trigger history tracking

    Workflow Trigger Flow:
    1. Entity discovered via LLM extraction
    2. Check if entity type has registered workflows
    3. Evaluate trigger conditions (property filters)
    4. Check debounce cache (prevent duplicates)
    5. Execute triggered workflows
    6. Track trigger history

    Example Usage:
    ```python
    service = WorkflowTriggerService(db)

    # Register workflow trigger
    service.register_workflow_trigger(
        entity_type="PurchaseOrder",
        workflow_id="po_approval",
        condition=lambda e: e.properties.get("amount", 0) > 1000
    )

    # Check and trigger workflows
    triggered = await service.check_and_trigger(discovered_entity)
    ```
    """

    def __init__(self, db: Session):
        """
        Initialize Workflow Trigger Service.

        Args:
            db: Database session
        """
        self.db = db

        # Entity type → workflow mappings
        self.workflow_mappings: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Debounce cache: entity_hash → timestamp
        self.debounce_cache: Dict[str, datetime] = {}

        # Trigger history: entity_id → triggered_workflows
        self.trigger_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Configuration
        self.debounce_ttl = timedelta(minutes=5)  # 5 minutes debounce
        self.max_history_per_entity = 10

    def register_workflow_trigger(
        self,
        entity_type: str,
        workflow_id: str,
        condition: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a workflow trigger for an entity type.

        Args:
            entity_type: PascalCase entity type (e.g., "PurchaseOrder")
            workflow_id: Workflow identifier (e.g., "po_approval")
            condition: Property-based routing condition (e.g., {"severity": "critical"})
            priority: Trigger priority (higher = earlier execution)
            metadata: Additional metadata for the trigger
        """
        trigger = {
            "workflow_id": workflow_id,
            "condition": condition or {},
            "priority": priority,
            "metadata": metadata or {},
            "registered_at": datetime.now(timezone.utc).isoformat()
        }

        # Sort by priority (descending)
        self.workflow_mappings[entity_type].append(trigger)
        self.workflow_mappings[entity_type].sort(
            key=lambda x: x["priority"], reverse=True
        )

        logger.info(
            f"Registered workflow trigger: {entity_type} → {workflow_id} "
            f"(priority: {priority}, condition: {condition})"
        )

    def unregister_workflow_trigger(
        self,
        entity_type: str,
        workflow_id: str
    ) -> bool:
        """
        Unregister a workflow trigger.

        Args:
            entity_type: Entity type
            workflow_id: Workflow ID to unregister

        Returns:
            True if trigger was found and removed
        """
        triggers = self.workflow_mappings.get(entity_type, [])
        original_count = len(triggers)

        # Remove trigger
        self.workflow_mappings[entity_type] = [
            t for t in triggers if t["workflow_id"] != workflow_id
        ]

        removed = len(self.workflow_mappings[entity_type]) < original_count

        if removed:
            logger.info(f"Unregistered workflow trigger: {entity_type} → {workflow_id}")

        return removed

    async def check_and_trigger(
        self,
        entity: DiscoveredEntity,
        force_trigger: bool = False
    ) -> List[str]:
        """
        Check if entity should trigger workflows and execute them.

        Args:
            entity: DiscoveredEntity instance
            force_trigger: Skip debounce check

        Returns:
            List of triggered workflow IDs
        """
        entity_type = entity._discovered_type
        triggered_workflows = []

        # Check if entity type has registered workflows
        if entity_type not in self.workflow_mappings:
            logger.debug(f"No workflows registered for entity type: {entity_type}")
            return []

        # Check debounce cache
        entity_hash = self._hash_entity(entity)
        if not force_trigger and self._is_debounced(entity_hash):
            logger.debug(f"Entity debounced: {entity.id}")
            return []

        # Evaluate each trigger
        for trigger in self.workflow_mappings[entity_type]:
            if self._evaluate_condition(entity, trigger["condition"]):
                # Execute workflow
                workflow_id = trigger["workflow_id"]
                success = await self._execute_workflow(entity, workflow_id, trigger)

                if success:
                    triggered_workflows.append(workflow_id)

        # Update debounce cache
        if triggered_workflows:
            self.debounce_cache[entity_hash] = datetime.now(timezone.utc)

            # Update trigger history
            self.trigger_history[entity.id].append({
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "triggered_workflows": triggered_workflows,
                "entity_type": entity_type
            })

            # Limit history size
            if len(self.trigger_history[entity.id]) > self.max_history_per_entity:
                self.trigger_history[entity.id] = self.trigger_history[entity.id][-self.max_history_per_entity:]

            logger.info(
                f"Triggered {len(triggered_workflows)} workflows for {entity.id} "
                f"(type: {entity_type}, workflows: {triggered_workflows})"
            )

        return triggered_workflows

    def _hash_entity(self, entity: DiscoveredEntity) -> str:
        """
        Generate hash for entity deduplication.

        Args:
            entity: DiscoveredEntity instance

        Returns:
            SHA256 hash string
        """
        # Hash based on type and key properties
        key_data = {
            "type": entity._discovered_type,
            "source_id": entity.source_record_id,
            # Hash properties for stability
            "props": dict(sorted(entity.properties.items()))
        }

        # Serialize to JSON and hash
        import json
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _is_debounced(self, entity_hash: str) -> bool:
        """
        Check if entity is debounced (triggered recently).

        Args:
            entity_hash: Entity hash

        Returns:
            True if debounced (should skip trigger)
        """
        if entity_hash not in self.debounce_cache:
            return False

        triggered_at = self.debounce_cache[entity_hash]
        now = datetime.now(timezone.utc)

        # Check if within TTL
        return (now - triggered_at) < self.debounce_ttl

    def _evaluate_condition(
        self,
        entity: DiscoveredEntity,
        condition: Dict[str, Any]
    ) -> bool:
        """
        Evaluate trigger condition against entity properties.

        Supports:
        - Property equality: {"severity": "critical"}
        - Range filters: {"amount": {"$gt": 1000}}
        - Regex filters: {"email": {"$regex": ".*@company.com$"}}
        - Logical operators: {"$and": [...], "$or": [...], "$not": {...}}

        Args:
            entity: DiscoveredEntity instance
            condition: Condition dict

        Returns:
            True if condition matches
        """
        if not condition:
            return True  # No condition = always trigger

        # Logical operators
        if "$and" in condition:
            return all(
                self._evaluate_condition(entity, cond)
                for cond in condition["$and"]
            )

        if "$or" in condition:
            return any(
                self._evaluate_condition(entity, cond)
                for cond in condition["$or"]
            )

        if "$not" in condition:
            return not self._evaluate_condition(entity, condition["$not"])

        # Property filters
        for prop_key, prop_value in condition.items():
            if prop_key.startswith("$"):
                continue  # Skip operators (handled above)

            entity_value = entity.properties.get(prop_key)

            if isinstance(prop_value, dict):
                # Operator syntax
                for op, op_value in prop_value.items():
                    if not self._evaluate_operator(entity_value, op, op_value):
                        return False
            else:
                # Equality check
                if entity_value != prop_value:
                    return False

        return True

    def _evaluate_operator(
        self,
        entity_value: Any,
        operator: str,
        operator_value: Any
    ) -> bool:
        """
        Evaluate a single operator against entity value.

        Operators:
        - $eq: Equal
        - $ne: Not equal
        - $gt: Greater than
        - $gte: Greater than or equal
        - $lt: Less than
        - $lte: Less than or equal
        - $in: In list
        - $nin: Not in list
        - $regex: Regex match
        - $exists: Property exists

        Args:
            entity_value: Value from entity properties
            operator: Operator string
            operator_value: Value to compare against

        Returns:
            True if operator matches
        """
        if operator == "$eq":
            return entity_value == operator_value
        elif operator == "$ne":
            return entity_value != operator_value
        elif operator == "$gt":
            return entity_value is not None and entity_value > operator_value
        elif operator == "$gte":
            return entity_value is not None and entity_value >= operator_value
        elif operator == "$lt":
            return entity_value is not None and entity_value < operator_value
        elif operator == "$lte":
            return entity_value is not None and entity_value <= operator_value
        elif operator == "$in":
            return entity_value in operator_value
        elif operator == "$nin":
            return entity_value not in operator_value
        elif operator == "$regex":
            import re
            pattern = re.compile(operator_value)
            return entity_value is not None and pattern.search(str(entity_value)) is not None
        elif operator == "$exists":
            return (entity_value is not None) == operator_value
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    async def _execute_workflow(
        self,
        entity: DiscoveredEntity,
        workflow_id: str,
        trigger: Dict[str, Any]
    ) -> bool:
        """
        Execute a triggered workflow.

        In production, this would call the workflow execution engine.
        For now, we'll simulate successful execution.

        Args:
            entity: DiscoveredEntity instance
            workflow_id: Workflow ID to execute
            trigger: Trigger configuration

        Returns:
            True if workflow executed successfully
        """
        # TODO: Integrate with actual workflow execution engine
        # For now, simulate successful execution

        logger.info(
            f"Executing workflow: {workflow_id} "
            f"for entity {entity.id} "
            f"(type: {entity._discovered_type})"
        )

        # Update entity metadata with triggered workflows
        entity.extraction_metadata = entity.extraction_metadata or {}
        triggered_workflows = entity.extraction_metadata.get("triggered_workflows", [])
        triggered_workflows.append({
            "workflow_id": workflow_id,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "trigger_priority": trigger["priority"]
        })
        entity.extraction_metadata["triggered_workflows"] = triggered_workflows

        return True

    def get_triggered_workflows(
        self,
        entity_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get trigger history for an entity.

        Args:
            entity_id: Entity UUID

        Returns:
            List of trigger events
        """
        return self.trigger_history.get(entity_id, [])

    def get_workflow_mappings(
        self,
        entity_type: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get registered workflow mappings.

        Args:
            entity_type: Optional entity type filter

        Returns:
            Dict mapping entity types to workflow lists
        """
        if entity_type:
            return {entity_type: self.workflow_mappings.get(entity_type, [])}
        return dict(self.workflow_mappings)

    def clear_debounce_cache(self) -> None:
        """Clear the debounce cache."""
        self.debounce_cache.clear()
        logger.info("Debounce cache cleared")

    def clear_trigger_history(self, entity_id: Optional[str] = None) -> None:
        """
        Clear trigger history.

        Args:
            entity_id: Optional entity ID to clear (clears all if None)
        """
        if entity_id:
            self.trigger_history.pop(entity_id, None)
        else:
            self.trigger_history.clear()
        logger.info(f"Trigger history cleared (entity_id: {entity_id})")
