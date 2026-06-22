"""
Event Bus for Event-Driven Workflow Triggering

Based on 2025-2026 research:
- AgentOrchestra Case Study (arXiv:2506.12508v4)
- Enterprise Agent Workflows

Implements:
- Pub/Sub event bus for workflow events
- Event subscriptions and routing
- Event-driven workflow triggering
- Event persistence and replay
"""

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque
from functools import wraps
import threading
import queue

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class EventType(Enum):
    """Types of workflow events"""
    # Workflow lifecycle
    WORKFLOW_CREATED = "workflow.created"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_CANCELLED = "workflow.cancelled"
    WORKFLOW_PAUSED = "workflow.paused"
    WORKFLOW_RESUMED = "workflow.resumed"

    # Step events
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    STEP_RETRYING = "step.retrying"

    # External triggers
    TIMER_TRIGGER = "timer.trigger"
    WEBHOOK_TRIGGER = "webhook.trigger"
    MESSAGE_RECEIVED = "message.received"
    CONDITION_MET = "condition.met"

    # Data events
    DATA_AVAILABLE = "data.available"
    DATA_UPDATED = "data.updated"
    INTEGRATION_EVENT = "integration.event"

    # System events
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_STARTUP = "system.startup"


class EventDelivery(Enum):
    """Event delivery semantics"""
    FIRE_AND_FORGET = "fire_and_forget"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


@dataclass
class EventBusConfig:
    """Configuration for event bus"""
    # Delivery
    default_delivery: EventDelivery = EventDelivery.AT_LEAST_ONCE
    max_retry_attempts: int = 3
    retry_backoff_ms: int = 1000

    # Buffer
    event_buffer_size: int = 10000
    subscriber_timeout_ms: int = 5000

    # Persistence
    enable_persistence: bool = True
    persistence_interval_ms: int = 5000
    event_retention_days: int = 7

    # Replay
    enable_replay: bool = True
    max_replay_events: int = 1000

    # Monitoring
    enable_metrics: bool = True
    metrics_interval_ms: int = 60000


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class WorkflowEvent:
    """Event in the workflow system"""
    event_id: str = ""
    event_type: EventType = EventType.WORKFLOW_CREATED
    source: str = ""  # workflow_id, system, or external source
    source_type: str = "workflow"  # workflow, system, external

    # Event data
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Delivery
    delivery_semantic: EventDelivery = EventDelivery.AT_LEAST_ONCE
    requires_ack: bool = True
    ack_timeout_ms: int = 5000

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Tracking
    delivered_to: List[str] = field(default_factory=list)
    acked_by: List[str] = field(default_factory=list)
    failed_deliveries: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "source_type": self.source_type,
            "data": self.data,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }

    def get_fingerprint(self) -> str:
        """Get unique fingerprint for deduplication"""
        data = f"{self.event_type.value}:{self.source}:{json.dumps(self.data, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class EventSubscription:
    """Subscription to workflow events"""
    subscription_id: str = ""
    subscriber_id: str = ""  # workflow_id, agent_id, or service name

    # Filter
    event_types: List[EventType] = field(default_factory=list)
    source_filter: Optional[str] = None  # Regex pattern for source
    data_filter: Optional[Dict[str, Any]] = None  # Key-value pairs to match

    # Handler
    handler: Optional[Callable] = None
    handler_type: str = "callback"  # callback, webhook, queue

    # Delivery
    delivery_semantic: EventDelivery = EventDelivery.AT_LEAST_ONCE
    max_retries: int = 3
    batch_size: int = 1
    batch_timeout_ms: int = 1000

    # State
    active: bool = True
    subscribed_at: datetime = field(default_factory=datetime.now)
    last_event_at: Optional[datetime] = None
    events_processed: int = 0

    def matches(self, event: WorkflowEvent) -> bool:
        """Check if subscription matches event"""
        if not self.active:
            return False

        # Check event type
        if self.event_types and event.event_type not in self.event_types:
            return False

        # Check source filter
        if self.source_filter:
            import re
            if not re.match(self.source_filter, event.source):
                return False

        # Check data filter
        if self.data_filter:
            for key, value in self.data_filter.items():
                if event.data.get(key) != value:
                    return False

        return True


@dataclass
class EventAck:
    """Acknowledgment for event delivery"""
    ack_id: str = ""
    event_id: str = ""
    subscriber_id: str = ""
    success: bool = False
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================================================
# Event Bus
# ============================================================================

class EventBus:
    """
    Pub/Sub event bus for event-driven workflows.

    Features:
    - Event publishing and routing
    - Subscription management
    - At-least-once delivery
    - Event persistence and replay
    - Deduplication
    """

    def __init__(self, config: Optional[EventBusConfig] = None):
        self.config = config or EventBusConfig()

        # Event storage
        self._events: Dict[str, WorkflowEvent] = {}
        self._event_buffer: deque = deque(maxlen=self.config.event_buffer_size)
        self._event_fingerprints: Set[str] = set()  # For deduplication

        # Subscriptions
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._type_index: Dict[EventType, List[str]] = defaultdict(list)

        # Acknowledgments
        self._pending_acks: Dict[str, EventAck] = {}
        self._ack_results: Dict[str, EventAck] = {}

        # Delivery queue (for async delivery)
        self._delivery_queue: queue.Queue = queue.Queue()
        self._delivery_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the event bus delivery thread"""
        if self._running:
            return

        self._running = True
        self._delivery_thread = threading.Thread(target=self._delivery_loop, daemon=True)
        self._delivery_thread.start()
        logger.info("Event bus started")

    def stop(self) -> None:
        """Stop the event bus"""
        self._running = False
        if self._delivery_thread:
            self._delivery_thread.join(timeout=5)
        logger.info("Event bus stopped")

    def publish(
        self,
        event_type: EventType,
        source: str,
        data: Dict[str, Any],
        source_type: str = "workflow",
        delivery_semantic: Optional[EventDelivery] = None,
        expires_at: Optional[datetime] = None
    ) -> str:
        """
        Publish an event to the bus.

        Args:
            event_type: Type of event
            source: Source of event
            data: Event payload
            source_type: Type of source
            delivery_semantic: Delivery semantic
            expires_at: Optional expiration time

        Returns:
            Event ID
        """
        # Create event
        event_id = f"evt_{uuid.uuid4().hex}"
        event = WorkflowEvent(
            event_id=event_id,
            event_type=event_type,
            source=source,
            source_type=source_type,
            data=data,
            delivery_semantic=delivery_semantic or self.config.default_delivery,
            created_at=datetime.now(),
            expires_at=expires_at
        )

        # Check for duplicates
        fingerprint = event.get_fingerprint()
        if fingerprint in self._event_fingerprints:
            logger.debug(f"Duplicate event detected: {event_id}")
            return event_id

        # Store event
        self._events[event_id] = event
        self._event_buffer.append(event)
        self._event_fingerprints.add(fingerprint)
        event.published_at = datetime.now()

        # Queue for delivery
        self._delivery_queue.put(event)

        logger.debug(f"Published event: {event_type.value} from {source}")
        return event_id

    def subscribe(
        self,
        subscriber_id: str,
        event_types: List[EventType],
        handler: Callable,
        source_filter: Optional[str] = None,
        delivery_semantic: EventDelivery = EventDelivery.AT_LEAST_ONCE
    ) -> str:
        """
        Subscribe to workflow events.

        Args:
            subscriber_id: ID of subscriber
            event_types: Types of events to subscribe to
            handler: Callback function
            source_filter: Optional regex for source filtering
            delivery_semantic: Delivery semantic

        Returns:
            Subscription ID
        """
        subscription_id = f"sub_{uuid.uuid4().hex}"

        subscription = EventSubscription(
            subscription_id=subscription_id,
            subscriber_id=subscriber_id,
            event_types=event_types,
            source_filter=source_filter,
            handler=handler,
            delivery_semantic=delivery_semantic
        )

        self._subscriptions[subscription_id] = subscription

        # Index by event type
        for event_type in event_types:
            self._type_index[event_type].append(subscription_id)

        logger.info(f"Subscription created: {subscription_id} for {subscriber_id}")
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription"""
        if subscription_id not in self._subscriptions:
            return False

        subscription = self._subscriptions[subscription_id]

        # Remove from type index
        for event_type in subscription.event_types:
            if subscription_id in self._type_index[event_type]:
                self._type_index[event_type].remove(subscription_id)

        del self._subscriptions[subscription_id]
        logger.info(f"Subscription removed: {subscription_id}")
        return True

    def unsubscribe_all(self, subscriber_id: str) -> int:
        """Remove all subscriptions for a subscriber"""
        removed = 0
        for sub_id, sub in list(self._subscriptions.items()):
            if sub.subscriber_id == subscriber_id:
                if self.unsubscribe(sub_id):
                    removed += 1
        logger.info(f"Removed {removed} subscriptions for {subscriber_id}")
        return removed

    def _delivery_loop(self) -> None:
        """Background thread for event delivery"""
        while self._running:
            try:
                # Get event with timeout
                try:
                    event = self._delivery_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Check if event expired
                if event.expires_at and datetime.now() > event.expires_at:
                    logger.debug(f"Event expired: {event.event_id}")
                    continue

                # Deliver to matching subscriptions
                self._deliver_event(event)

            except Exception as e:
                logger.error(f"Delivery loop error: {e}")

    def _deliver_event(self, event: WorkflowEvent) -> None:
        """Deliver event to matching subscribers"""
        # Find matching subscriptions
        subscription_ids = self._type_index.get(event.event_type, [])

        for sub_id in subscription_ids:
            if sub_id not in self._subscriptions:
                continue

            subscription = self._subscriptions[sub_id]
            if not subscription.matches(event):
                continue

            try:
                # Call handler
                if subscription.handler:
                    subscription.handler(event)
                    event.delivered_to.append(subscription.subscriber_id)
                    subscription.events_processed += 1
                    subscription.last_event_at = datetime.now()

                    # Track acknowledgment for exactly-once
                    if subscription.delivery_semantic == EventDelivery.EXACTLY_ONCE:
                        self._ack_results[f"{event.event_id}:{subscription.subscriber_id}"] = EventAck(
                            ack_id=f"ack_{uuid.uuid4().hex}",
                            event_id=event.event_id,
                            subscriber_id=subscription.subscriber_id,
                            success=True
                        )

            except Exception as e:
                logger.error(f"Delivery failed to {subscription.subscriber_id}: {e}")
                event.failed_deliveries[subscription.subscriber_id] += 1

                # Retry logic
                if event.failed_deliveries[subscription.subscriber_id] < self.config.max_retry_attempts:
                    # Re-queue for retry
                    self._delivery_queue.put(event)

    def get_events(
        self,
        source: Optional[str] = None,
        event_type: Optional[EventType] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[WorkflowEvent]:
        """Get events from the buffer"""
        events = list(self._event_buffer)

        # Filter by source
        if source:
            events = [e for e in events if e.source == source]

        # Filter by type
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Filter by time
        if since:
            events = [e for e in events if e.created_at >= since]

        return events[-limit:]

    def get_subscriptions(
        self,
        subscriber_id: Optional[str] = None
    ) -> List[EventSubscription]:
        """Get subscriptions"""
        if subscriber_id:
            return [
                sub for sub in self._subscriptions.values()
                if sub.subscriber_id == subscriber_id
            ]
        return list(self._subscriptions.values())

    def create_workflow_trigger(
        self,
        workflow_id: str,
        trigger_event: EventType,
        condition: Optional[str] = None
    ) -> str:
        """
        Create a trigger for workflow execution.

        Args:
            workflow_id: Workflow to trigger
            trigger_event: Event that triggers execution
            condition: Optional condition to check

        Returns:
            Subscription ID
        """
        def trigger_handler(event: WorkflowEvent):
            """Handler that triggers workflow"""
            # Check condition
            if condition:
                try:
                    # SECURITY: use safe_eval (AST-validated) instead of raw eval()
                    # to prevent code injection via workflow trigger conditions.
                    from core.safe_evaluator import safe_eval, SafeEvalError
                    try:
                        result = safe_eval(condition, {"event": event, "data": event.data})
                    except SafeEvalError as e:
                        logger.warning(f"Condition rejected by safe_eval: {e}")
                        return
                    if not result:
                        logger.debug(f"Condition not met for workflow {workflow_id}")
                        return
                except Exception as e:
                    logger.error(f"Condition evaluation failed: {e}")
                    return

            # Trigger workflow
            logger.info(f"Triggering workflow {workflow_id} due to event {trigger_event.value}")
            # In production, this would call the workflow engine
            self.publish(
                event_type=EventType.WORKFLOW_STARTED,
                source=workflow_id,
                data={"triggered_by": trigger_event.value, "trigger_event": event.to_dict()}
            )

        return self.subscribe(
            subscriber_id=workflow_id,
            event_types=[trigger_event],
            handler=trigger_handler
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            "total_events": len(self._events),
            "buffer_size": len(self._event_buffer),
            "total_subscriptions": len(self._subscriptions),
            "active_subscriptions": sum(1 for s in self._subscriptions.values() if s.active),
            "pending_acks": len(self._pending_acks),
            "type_index_size": sum(len(ids) for ids in self._type_index.values()),
            "running": self._running
        }


# ============================================================================
# Factory
# ============================================================================

_event_bus_instance: Optional[EventBus] = None


def get_event_bus(config: Optional[EventBusConfig] = None) -> EventBus:
    """Get or create event bus instance"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus(config)
        _event_bus_instance.start()
    return _event_bus_instance
