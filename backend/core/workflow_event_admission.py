"""Internal workflow event admission.

The connector authenticates and normalizes an inbound provider event, then hands
the trusted identity and payload to this coordinator.  The coordinator is
deliberately storage-agnostic: durable receipt lookup and reservation are
injected callbacks so the orchestration can be tested without a database and
wired to the execution state manager elsewhere.

A saved workflow owns one ``event_subscriptions`` list.  Each subscription is
``{id, connection_id, source, event_type, enabled}``.  New work requires an
explicitly enabled workflow, a matching saved tenant/workspace, an enabled
subscription and an exact connection/source/type match.  A previously admitted
provider event is replayed from its receipt even when the workflow, rule or
subscription was disabled later.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

EVENT_ADMISSION_CONTEXT_KEY = "_atom_event_admission"


class EventAdmissionError(Exception):
    """Base class for admission failures."""


class EventScopeConflict(EventAdmissionError):
    """A prior receipt exists but belongs to a different immutable scope."""


class EventPayloadConflict(EventAdmissionError):
    """The same provider event was presented with a different payload."""


class EventSubscriptionConflict(EventAdmissionError):
    """More than one enabled subscription claims the same event."""


def _token(value: Any, name: str, *, required: bool = True) -> str:
    """Normalize one trusted identity value without inventing a value."""
    if value is None or isinstance(value, bool):
        text = ""
    elif isinstance(value, (str, int, uuid.UUID)):
        text = str(value).strip()
    else:
        text = ""
    if required and not text:
        raise EventAdmissionError(f"{name} is required")
    return text


def _payload_copy(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise EventAdmissionError("event payload must be a mapping")
    return copy.deepcopy(dict(payload))


def payload_digest(payload: Mapping[str, Any]) -> str:
    """Return a stable digest of the normalized payload only."""
    if not isinstance(payload, Mapping):
        raise EventAdmissionError("event payload must be a mapping")
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_event_id(
    *,
    tenant_id: Any,
    workspace_id: Any,
    workflow_id: Any,
    connection_id: Any,
    source: Any,
    event_type: Any,
    provider_event_id: Any,
) -> str:
    """Derive the durable execution id from the stable receipt identity.

    These are exactly the ``EventReceiptKey`` fields.  Workflow revision, the
    selected subscription, owner preferences and payload are intentionally
    absent: two deliveries of one provider event must share one execution even
    if a subscription was replaced between them.
    """
    material = json.dumps(
        [
            _token(tenant_id, "tenant_id"),
            _token(workspace_id, "workspace_id"),
            _token(workflow_id, "workflow_id"),
            _token(connection_id, "connection_id"),
            _token(source, "source"),
            _token(event_type, "event_type"),
            _token(provider_event_id, "provider_event_id"),
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"evt_{digest}"


@dataclass(frozen=True)
class WorkflowEvent:
    """Trusted, normalized inbound event supplied by the server connector."""

    tenant_id: str
    workspace_id: str
    owner_id: str
    connection_id: str
    source: str
    event_type: str
    provider_event_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventSubscription:
    id: str
    connection_id: str
    source: str
    event_type: str
    enabled: bool = True


@dataclass(frozen=True)
class EventReceiptKey:
    """Stable lookup identity for replay across rule changes.

    Event type is part of the provider event identity, so two legitimate event
    types from the same resource/provider event never collapse into one
    receipt.  Subscription id deliberately stays out of the lookup key: a
    disabled, replaced or reconfigured subscription must still find its prior
    receipt.  These same fields, in this same order, derive the durable
    execution id so lookup and insert cannot disagree.
    """

    tenant_id: str
    workspace_id: str
    workflow_id: str
    connection_id: str
    source: str
    event_type: str
    provider_event_id: str

    @classmethod
    def from_event(
        cls, event: WorkflowEvent, workflow_id: str
    ) -> "EventReceiptKey":
        return cls(
            tenant_id=event.tenant_id,
            workspace_id=event.workspace_id,
            workflow_id=_token(workflow_id, "workflow_id"),
            connection_id=event.connection_id,
            source=event.source,
            event_type=event.event_type,
            provider_event_id=event.provider_event_id,
        )

    @property
    def event_id(self) -> str:
        """Return the durable execution id for this stable receipt key."""
        return derive_event_id(
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            workflow_id=self.workflow_id,
            connection_id=self.connection_id,
            source=self.source,
            event_type=self.event_type,
            provider_event_id=self.provider_event_id,
        )


@dataclass(frozen=True)
class EventAdmissionReceipt:
    """Durable receipt for exactly one admitted event and subscription."""

    event_id: str
    tenant_id: str
    workspace_id: str
    workflow_id: str
    owner_id: str
    subscription_id: str
    connection_id: str
    source: str
    event_type: str
    provider_event_id: str
    payload_digest: str
    workflow_snapshot: Mapping[str, Any]
    input_data: Mapping[str, Any] = field(default_factory=dict)

    @property
    def receipt_key(self) -> EventReceiptKey:
        return EventReceiptKey(
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            workflow_id=self.workflow_id,
            connection_id=self.connection_id,
            source=self.source,
            event_type=self.event_type,
            provider_event_id=self.provider_event_id,
        )

    @property
    def admission_context(self) -> Dict[str, Any]:
        """Server-owned context persisted with the admitted execution."""
        return {
            "event_id": self.event_id,
            "execution_id": self.event_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "owner_id": self.owner_id,
            "workflow_id": self.workflow_id,
            "subscription_id": self.subscription_id,
            "connection_id": self.connection_id,
            "source": self.source,
            "event_type": self.event_type,
            "provider_event_id": self.provider_event_id,
            "payload_digest": self.payload_digest,
            "workflow_snapshot": copy.deepcopy(self.workflow_snapshot),
        }


@dataclass(frozen=True)
class ReservationResult:
    """The one canonical result of an atomic receipt reservation.

    A single typed value carries the receipt together with the normalized
    ``input_data`` that is persisted in the pending row.  ``created`` is true
    only when this caller inserted the receipt; false means another writer won
    and its persisted receipt was returned.
    """

    receipt: EventAdmissionReceipt
    input_data: Mapping[str, Any] = field(default_factory=dict)
    created: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.input_data, Mapping):
            raise EventAdmissionError("reservation input_data must be a mapping")
        inputs = copy.deepcopy(dict(self.input_data))
        if not inputs:
            inputs = copy.deepcopy(
                dict(getattr(self.receipt, "input_data", None) or {})
            )
        object.__setattr__(self, "input_data", inputs)
        object.__setattr__(self, "created", bool(self.created))


def _event_inputs(
    receipt: EventAdmissionReceipt, payload: Mapping[str, Any]
) -> Dict[str, Any]:
    """Build durable dispatcher inputs without mixing in workflow config."""
    return {
        EVENT_ADMISSION_CONTEXT_KEY: receipt.admission_context,
        "event": {
            "tenant_id": receipt.tenant_id,
            "workspace_id": receipt.workspace_id,
            "owner_id": receipt.owner_id,
            "connection_id": receipt.connection_id,
            "source": receipt.source,
            "event_type": receipt.event_type,
            "provider_event_id": receipt.provider_event_id,
            "payload": copy.deepcopy(dict(payload)),
        },
    }


@dataclass(frozen=True)
class EventAdmission:
    """One admitted event, with event inputs kept apart from destination config."""

    receipt: EventAdmissionReceipt
    payload: Mapping[str, Any]
    duplicate: bool = False

    @property
    def event_id(self) -> str:
        return self.receipt.event_id

    @property
    def workflow_snapshot(self) -> Mapping[str, Any]:
        return self.receipt.workflow_snapshot

    @property
    def context(self) -> Dict[str, Any]:
        return self.receipt.admission_context

    @property
    def event_inputs(self) -> Dict[str, Any]:
        if self.receipt.input_data:
            return copy.deepcopy(dict(self.receipt.input_data))
        return _event_inputs(self.receipt, self.payload)

    @property
    def input_data(self) -> Dict[str, Any]:
        """Normalized durable inputs for the admitted execution row."""
        return self.event_inputs


ReceiptLookup = Callable[[EventReceiptKey], Awaitable[Optional[EventAdmissionReceipt]]]
ReceiptReserve = Callable[[EventAdmissionReceipt], Awaitable[ReservationResult]]


def _reserve_accepts_input_data(reserve_receipt: ReceiptReserve) -> bool:
    """Detect a callback that wants the receipt and inputs as two arguments."""
    try:
        parameters = inspect.signature(reserve_receipt).parameters.values()
    except (TypeError, ValueError):
        return False
    positional = [
        parameter
        for parameter in parameters
        if parameter.kind
        in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    return len(positional) > 1


def _normalize_event(event: Any) -> WorkflowEvent:
    if isinstance(event, WorkflowEvent):
        raw = event
    elif isinstance(event, Mapping):
        raw = WorkflowEvent(
            tenant_id=event.get("tenant_id"),
            workspace_id=event.get("workspace_id"),
            owner_id=event.get("owner_id", ""),
            connection_id=event.get("connection_id"),
            source=event.get("source"),
            event_type=event.get("event_type"),
            provider_event_id=event.get("provider_event_id"),
            payload=event.get("payload") or {},
        )
    else:
        raise EventAdmissionError("event must be a WorkflowEvent or mapping")

    return WorkflowEvent(
        tenant_id=_token(raw.tenant_id, "tenant_id"),
        workspace_id=_token(raw.workspace_id, "workspace_id"),
        owner_id=_token(raw.owner_id, "owner_id", required=False),
        connection_id=_token(raw.connection_id, "connection_id"),
        source=_token(raw.source, "source"),
        event_type=_token(raw.event_type, "event_type"),
        provider_event_id=_token(raw.provider_event_id, "provider_event_id"),
        payload=_payload_copy(raw.payload),
    )


def _workflow_id(workflow: Mapping[str, Any]) -> str:
    value = workflow.get("id")
    if value is None:
        value = workflow.get("workflow_id")
    return _token(value, "workflow.id")


def _subscription(value: Any) -> Optional[EventSubscription]:
    if isinstance(value, EventSubscription):
        try:
            return EventSubscription(
                id=_token(value.id, "subscription.id"),
                connection_id=_token(value.connection_id, "subscription.connection_id"),
                source=_token(value.source, "subscription.source"),
                event_type=_token(value.event_type, "subscription.event_type"),
                enabled=value.enabled is True,
            )
        except EventAdmissionError:
            return None
    if not isinstance(value, Mapping):
        return None
    try:
        return EventSubscription(
            id=_token(value.get("id"), "subscription.id"),
            connection_id=_token(
                value.get("connection_id"), "subscription.connection_id"
            ),
            source=_token(value.get("source"), "subscription.source"),
            event_type=_token(value.get("event_type"), "subscription.event_type"),
            enabled=value.get("enabled") is True,
        )
    except EventAdmissionError:
        return None


def _matching_subscriptions(
    event: WorkflowEvent, workflow: Mapping[str, Any]
) -> List[EventSubscription]:
    subscriptions = workflow.get("event_subscriptions") or []
    if not isinstance(subscriptions, (list, tuple)):
        return []
    matches: List[EventSubscription] = []
    for raw in subscriptions:
        subscription = _subscription(raw)
        if subscription is None:
            continue
        if (
            subscription.connection_id == event.connection_id
            and subscription.source == event.source
            and subscription.event_type == event.event_type
        ):
            matches.append(subscription)
    return matches


def _scope_matches(receipt: EventAdmissionReceipt, key: EventReceiptKey) -> bool:
    return (
        receipt.tenant_id == key.tenant_id
        and receipt.workspace_id == key.workspace_id
        and receipt.workflow_id == key.workflow_id
        and receipt.connection_id == key.connection_id
        and receipt.source == key.source
        and receipt.event_type == key.event_type
        and receipt.provider_event_id == key.provider_event_id
    )


class WorkflowEventAdmissionCoordinator:
    """Coordinate new-event admission and replay of prior receipts."""

    def __init__(self, lookup_receipt: ReceiptLookup, reserve_receipt: ReceiptReserve):
        self._lookup_receipt = lookup_receipt
        self._reserve_receipt = reserve_receipt

    async def admit(
        self, event: WorkflowEvent, workflow: Mapping[str, Any]
    ) -> Optional[EventAdmission]:
        """Admit one event for one saved workflow.

        Returns ``None`` when the event does not match an enabled workflow,
        exact saved scope and enabled subscription for new work.  A known
        receipt is always considered first so replay survives a later
        disablement or rule change.
        """
        event = _normalize_event(event)
        if not isinstance(workflow, Mapping):
            raise EventAdmissionError("workflow must be a mapping")

        workflow_id = _workflow_id(workflow)
        key = EventReceiptKey.from_event(event, workflow_id)
        existing = await self._lookup_receipt(key)
        if existing is not None:
            return self._from_receipt(existing, key, event, duplicate=True)

        if workflow.get("enabled") is not True:
            return None

        workflow_tenant = _token(
            workflow.get("tenant_id"), "workflow.tenant_id", required=False
        )
        workflow_workspace = _token(
            workflow.get("workspace_id"), "workflow.workspace_id", required=False
        )
        if not workflow_tenant or not workflow_workspace:
            return None
        if workflow_tenant != event.tenant_id:
            return None
        if workflow_workspace != event.workspace_id:
            return None

        matches = _matching_subscriptions(event, workflow)
        enabled = [subscription for subscription in matches if subscription.enabled]
        if not enabled:
            return None
        if len(enabled) > 1:
            ids = ", ".join(subscription.id for subscription in enabled)
            raise EventSubscriptionConflict(
                f"event matches multiple enabled subscriptions: {ids}"
            )

        subscription = enabled[0]
        digest = payload_digest(event.payload)
        candidate = EventAdmissionReceipt(
            event_id=key.event_id,
            tenant_id=event.tenant_id,
            workspace_id=event.workspace_id,
            workflow_id=workflow_id,
            owner_id=event.owner_id,
            subscription_id=subscription.id,
            connection_id=event.connection_id,
            source=event.source,
            event_type=event.event_type,
            provider_event_id=event.provider_event_id,
            payload_digest=digest,
            workflow_snapshot=copy.deepcopy(dict(workflow)),
        )
        candidate = replace(
            candidate, input_data=_event_inputs(candidate, event.payload)
        )

        if _reserve_accepts_input_data(self._reserve_receipt):
            result = await self._reserve_receipt(candidate, candidate.input_data)
        else:
            result = await self._reserve_receipt(candidate)
        if not isinstance(result, ReservationResult):
            raise EventAdmissionError(
                "reservation callback must return ReservationResult"
            )
        winner = result.receipt
        if not isinstance(winner, EventAdmissionReceipt):
            raise EventAdmissionError(
                "reservation callback must return a typed receipt"
            )
        if not winner.input_data and result.input_data:
            winner = replace(
                winner, input_data=copy.deepcopy(dict(result.input_data))
            )
        return self._from_receipt(
            winner, key, event, duplicate=not result.created
        )

    @staticmethod
    def _from_receipt(
        receipt: EventAdmissionReceipt,
        key: EventReceiptKey,
        event: WorkflowEvent,
        *,
        duplicate: bool,
    ) -> EventAdmission:
        if not _scope_matches(receipt, key):
            raise EventScopeConflict(
                "prior receipt belongs to a different event scope"
            )
        if receipt.payload_digest != payload_digest(event.payload):
            raise EventPayloadConflict(
                f"provider event {event.provider_event_id} has a different payload"
            )
        return EventAdmission(
            receipt=receipt,
            payload=_payload_copy(event.payload),
            duplicate=duplicate,
        )
