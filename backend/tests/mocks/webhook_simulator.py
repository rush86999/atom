"""
Webhook Simulator for testing retry, out-of-order, and burst scenarios.

This module provides tools to simulate real-world webhook delivery patterns
that Stripe warns about: duplicate events, out-of-order delivery, retries
with exponential backoff, and burst delivery.
"""

import asyncio
import hashlib
import hmac
import json
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx


class WebhookSimulator:
    """
    Simulate webhook delivery with retry, out-of-order, and duplicate scenarios.

    This class helps test webhook endpoint robustness by simulating challenging
    delivery patterns that occur in production.

    Example:
        >>> simulator = WebhookSimulator("http://localhost:8000/api/stripe/webhooks")
        >>> event = {"id": "evt_test", "type": "payment_intent.succeeded"}
        >>> response = simulator.send_event(event)
        >>> print(response.status_code)
        200
    """

    def __init__(self, webhook_endpoint_url: str, webhook_secret: Optional[str] = None):
        """
        Initialize webhook simulator.

        Args:
            webhook_endpoint_url: Target URL for webhook delivery
            webhook_secret: Optional secret for signature generation
        """
        self.webhook_endpoint_url = webhook_endpoint_url
        self.webhook_secret = webhook_secret
        self.client = httpx.Client(timeout=30.0)

    def send_event(
        self, event_data: Dict[str, Any], signature: Optional[str] = None
    ) -> httpx.Response:
        """
        Send a single webhook event to the endpoint.

        Args:
            event_data: Event payload (dict)
            signature: Optional pre-generated signature header

        Returns:
            httpx.Response: Response from webhook endpoint
        """
        headers = {"Content-Type": "application/json"}

        # Generate signature if secret provided and no signature supplied
        if self.webhook_secret and signature is None:
            signature = generate_stripe_signature(
                json.dumps(event_data), self.webhook_secret
            )

        if signature:
            headers["Stripe-Signature"] = signature

        return self.client.post(
            self.webhook_endpoint_url,
            json=event_data,
            headers=headers,
        )

    def send_batch(
        self, events: List[Dict[str, Any]], delay_ms: int = 0
    ) -> List[httpx.Response]:
        """
        Send multiple webhooks with optional delay between each.

        Args:
            events: List of event payloads
            delay_ms: Milliseconds to wait between each webhook

        Returns:
            List of responses from webhook endpoint
        """
        responses = []

        for event in events:
            response = self.send_event(event)
            responses.append(response)

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

        return responses

    def send_out_of_order(self, events: List[Dict[str, Any]]) -> List[httpx.Response]:
        """
        Send webhooks in random order (shuffled).

        Simulates Stripe's out-of-order delivery warning.

        Args:
            events: List of event payloads

        Returns:
            List of responses from webhook endpoint
        """
        shuffled_events = simulate_out_of_order_delivery(events)
        return self.send_batch(shuffled_events)

    def send_with_retry(
        self,
        event: Dict[str, Any],
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> httpx.Response:
        """
        Send webhook with exponential backoff retry logic.

        Simulates Stripe's retry behavior: 1s, 2s, 4s delays.

        Args:
            event: Event payload
            max_retries: Maximum retry attempts
            base_delay: Initial delay in seconds

        Returns:
            httpx.Response: Final response (success or last failure)
        """
        for attempt in range(max_retries + 1):
            response = self.send_event(event)

            # Success (2xx status)
            if 200 <= response.status_code < 300:
                return response

            # Don't retry client errors (4xx) - they won't succeed on retry
            if 400 <= response.status_code < 500:
                return response

            # Server error (5xx) - retry with exponential backoff
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                time.sleep(delay)
            else:
                return response

        return response

    def send_duplicate(
        self, event: Dict[str, Any], count: int = 2
    ) -> List[httpx.Response]:
        """
        Send the same event multiple times to test deduplication.

        Args:
            event: Event payload
            count: Number of times to send the event

        Returns:
            List of responses from webhook endpoint
        """
        responses = []

        for _ in range(count):
            response = self.send_event(event)
            responses.append(response)

        return responses

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class WebhookEventBuilder:
    """
    Build Stripe webhook events with realistic structure.

    Creates properly formatted webhook events for various Stripe event types.

    Example:
        >>> builder = WebhookEventBuilder()
        >>> event = builder.create_payment_succeeded("pi_123", 1000)
        >>> print(event["type"])
        'payment_intent.succeeded'
    """

    def create_payment_succeeded(
        self, payment_id: str, amount: int, currency: str = "usd"
    ) -> Dict[str, Any]:
        """
        Build a payment_intent.succeeded event.

        Args:
            payment_id: Payment intent ID
            amount: Amount in cents
            currency: Currency code (default: usd)

        Returns:
            Webhook event dictionary
        """
        return {
            "id": f"evt_{generate_event_id()}",
            "object": "event",
            "api_version": "2023-10-16",
            "created": int(datetime.now().timestamp()),
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": payment_id,
                    "object": "payment_intent",
                    "amount": amount,
                    "currency": currency,
                    "status": "succeeded",
                    "customer": f"cus_{generate_event_id()}",
                },
                "previous_attributes": None,
            },
            "livemode": False,
            "pending_webhooks": 0,
            "request": None,
            "metadata": {},
        }

    def create_payment_failed(
        self, payment_id: str, error_code: str, error_message: str = "Card declined"
    ) -> Dict[str, Any]:
        """
        Build a payment_intent.payment_failed event.

        Args:
            payment_id: Payment intent ID
            error_code: Stripe error code (e.g., card_declined)
            error_message: Human-readable error message

        Returns:
            Webhook event dictionary
        """
        return {
            "id": f"evt_{generate_event_id()}",
            "object": "event",
            "api_version": "2023-10-16",
            "created": int(datetime.now().timestamp()),
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": payment_id,
                    "object": "payment_intent",
                    "status": "requires_payment_method",
                    "last_payment_error": {
                        "code": error_code,
                        "message": error_message,
                        "type": "card_error",
                    },
                },
                "previous_attributes": None,
            },
            "livemode": False,
            "pending_webhooks": 0,
            "request": None,
            "metadata": {},
        }

    def create_subscription_created(self, subscription_id: str) -> Dict[str, Any]:
        """
        Build a customer.subscription.created event.

        Args:
            subscription_id: Subscription ID

        Returns:
            Webhook event dictionary
        """
        return {
            "id": f"evt_{generate_event_id()}",
            "object": "event",
            "api_version": "2023-10-16",
            "created": int(datetime.now().timestamp()),
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": subscription_id,
                    "object": "subscription",
                    "status": "active",
                    "customer": f"cus_{generate_event_id()}",
                    "current_period_start": int(datetime.now().timestamp()),
                    "current_period_end": int(
                        (datetime.now().timestamp() + 30 * 24 * 60 * 60)
                    ),
                },
                "previous_attributes": None,
            },
            "livemode": False,
            "pending_webhooks": 0,
            "request": None,
            "metadata": {},
        }

    def create_invoice_paid(
        self, invoice_id: str, amount: int, currency: str = "usd"
    ) -> Dict[str, Any]:
        """
        Build an invoice.payment_succeeded event.

        Args:
            invoice_id: Invoice ID
            amount: Amount in cents
            currency: Currency code (default: usd)

        Returns:
            Webhook event dictionary
        """
        return {
            "id": f"evt_{generate_event_id()}",
            "object": "event",
            "api_version": "2023-10-16",
            "created": int(datetime.now().timestamp()),
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": invoice_id,
                    "object": "invoice",
                    "amount_paid": amount,
                    "amount_due": amount,
                    "currency": currency,
                    "status": "paid",
                    "customer": f"cus_{generate_event_id()}",
                },
                "previous_attributes": None,
            },
            "livemode": False,
            "pending_webhooks": 0,
            "request": None,
            "metadata": {},
        }

    def with_signature(
        self, payload: Dict[str, Any], secret: str
    ) -> tuple[Dict[str, Any], str]:
        """
        Add Stripe signature to event payload.

        Args:
            payload: Event payload
            secret: Webhook secret for signature

        Returns:
            Tuple of (payload, signature_header)
        """
        signature = generate_stripe_signature(json.dumps(payload), secret)
        return payload, signature


def generate_stripe_signature(payload: str, secret: str) -> str:
    """
    Generate realistic Stripe webhook signature header.

    Stripe signatures use HMAC-SHA256 with timestamp for replay attack prevention.
    Format: t={timestamp},v1={hmac_signature}

    Args:
        payload: JSON payload as string
        secret: Webhook signing secret

    Returns:
        Signature header value

    Example:
        >>> sig = generate_stripe_signature('{"id": "evt_123"}', 'whsec_abc')
        >>> print(sig)
        't=1234567890,v1=abc123...'
    """
    timestamp = int(datetime.now().timestamp())

    # Construct signed payload
    signed_payload = f"{timestamp}.{payload}"

    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Return Stripe-format signature header
    return f"t={timestamp},v1={signature}"


def simulate_out_of_order_delivery(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Shuffle events to simulate out-of-order webhook delivery.

    Stripe explicitly warns webhooks may not arrive in chronological order.

    Args:
        events: List of events in correct order

    Returns:
        Shuffled list of events

    Example:
        >>> events = [{"id": "evt_1"}, {"id": "evt_2"}, {"id": "evt_3"}]
        >>> shuffled = simulate_out_of_order_delivery(events)
        >>> print(shuffled[0]["id"])
        'evt_3'  # Random order
    """
    shuffled = events.copy()
    random.shuffle(shuffled)
    return shuffled


def simulate_burst_delivery(
    events: List[Dict[str, Any]], events_per_second: int = 100
) -> List[Dict[str, Any]]:
    """
    Generate events in bursts (e.g., 100 events in 1 second).

    Simulates high-volume webhook delivery scenarios.

    Args:
        events: List of events
        events_per_second: Target delivery rate

    Returns:
        Events tagged with timing information for burst simulation
    """
    delay_ms = 1000 / events_per_second

    # Tag events with intended delivery time
    tagged_events = []
    for i, event in enumerate(events):
        event_with_timing = {
            **event,
            "_simulated_delay_ms": int(i * delay_ms),
        }
        tagged_events.append(event_with_timing)

    return tagged_events


def simulate_retry_scenario(failure_count: int = 2) -> Dict[str, Any]:
    """
    Generate scenario configuration for retry testing.

    Creates a dict specifying which attempts should fail.

    Args:
        failure_count: Number of initial attempts to fail

    Returns:
        Scenario configuration dict

    Example:
        >>> scenario = simulate_retry_scenario(2)
        >>> print(scenario)
        {'fail_attempts': [1, 2], 'succeed_on': 3}
    """
    return {
        "fail_attempts": list(range(1, failure_count + 1)),
        "succeed_on": failure_count + 1,
        "retry_delays": [1.0, 2.0, 4.0],  # Stripe's exponential backoff
    }


def generate_event_id() -> str:
    """
    Generate unique event ID for testing.

    Returns:
        Random event ID string
    """
    import uuid

    return str(uuid.uuid4())[:8]


__all__ = [
    "WebhookSimulator",
    "WebhookEventBuilder",
    "generate_stripe_signature",
    "simulate_out_of_order_delivery",
    "simulate_burst_delivery",
    "simulate_retry_scenario",
]
