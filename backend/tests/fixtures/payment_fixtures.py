"""
Factory Boy factories for payment test data.

Generates Stripe payment objects (charges, invoices, subscriptions, webhooks)
with Decimal precision for monetary values.
"""

import factory
from datetime import datetime, timedelta
from typing import Dict, Any

from core.decimal_utils import to_decimal


class StripeChargeFactory(factory.Factory):
    """
    Factory for Stripe charge objects.

    Generates dict objects matching Stripe Charge API response structure.
    All monetary values use Decimal for precision, converted to integer cents.

    Example:
        >>> charge = StripeChargeFactory()
        >>> print(charge["id"])
        'ch_test_0'
        >>> print(charge["amount"])
        1000  # $10.00 in cents
    """

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: f"ch_test_{n}")
    object = "charge"
    amount = int(to_decimal("10.00") * 100)  # $10.00 in cents
    amount_captured = amount
    amount_refunded = 0
    currency = "usd"
    status = "succeeded"
    customer = factory.Sequence(lambda n: f"cus_test_{n}")
    description = factory.Sequence(lambda n: f"Test charge ch_test_{n}")
    created = factory.LazyFunction(lambda: int(datetime.now().timestamp()))
    livemode = False
    paid = True
    refunded = False
    metadata = factory.LazyFunction(dict)

    # Optional fields
    invoice = None
    payment_intent = factory.Sequence(lambda n: f"pi_test_{n}")
    receipt_email = factory.Sequence(lambda n: f"customer_{n}@example.com")


class StripeCustomerFactory(factory.Factory):
    """
    Factory for Stripe customer objects.

    Generates dict objects matching Stripe Customer API response structure.

    Example:
        >>> customer = StripeCustomerFactory()
        >>> print(customer["id"])
        'cus_test_0'
        >>> print(customer["email"])
        'customer_0@example.com'
    """

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: f"cus_test_{n}")
    object = factory.LazyAttribute(lambda obj: "customer")
    email = factory.Sequence(lambda n: f"customer_{n}@example.com")
    name = factory.Sequence(lambda n: f"Test Customer {n}")
    description = "Test customer for payment integration"
    created = factory.LazyFunction(lambda: int(datetime.now().timestamp()))
    livemode = False
    metadata = factory.LazyFunction(dict)


class StripeInvoiceFactory(factory.Factory):
    """
    Factory for Stripe invoice objects.

    Generates dict objects matching Stripe Invoice API response structure.
    All monetary values use Decimal precision, converted to integer cents.

    Example:
        >>> invoice = StripeInvoiceFactory()
        >>> print(invoice["id"])
        'in_test_0'
        >>> print(invoice["amount_due"])
        1000  # $10.00 in cents
    """

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: f"in_test_{n}")
    object = "invoice"
    amount_due = int(to_decimal("10.00") * 100)  # $10.00 in cents
    amount_paid = amount_due
    amount_remaining = 0
    currency = "usd"
    status = "paid"
    total = amount_due
    subtotal = amount_due

    # Customer reference
    customer = factory.Sequence(lambda n: f"cus_test_{n}")
    subscription = factory.Sequence(lambda n: f"sub_test_{n}")

    # Timestamps
    created = factory.LazyFunction(lambda: int(datetime.now().timestamp()))
    due_date = factory.LazyFunction(
        lambda: int((datetime.now() + timedelta(days=7)).timestamp())
    )
    period_start = factory.LazyFunction(lambda: int(datetime.now().timestamp()))
    period_end = factory.LazyFunction(
        lambda: int((datetime.now() + timedelta(days=30)).timestamp())
    )

    livemode = False
    paid = True
    attempted = True
    metadata = factory.LazyFunction(dict)


class StripeSubscriptionItemFactory(factory.Factory):
    """
    Factory for Stripe subscription item objects.

    Generates dict objects matching Stripe SubscriptionItem API response structure.

    Example:
        >>> item = StripeSubscriptionItemFactory()
        >>> print(item["id"])
        'si_test_0'
    """

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: f"si_test_{n}")
    object = "subscription_item"
    price = factory.Sequence(lambda n: f"price_test_{n}")
    quantity = 1
    metadata = factory.LazyFunction(dict)


class StripeSubscriptionFactory(factory.Factory):
    """
    Factory for Stripe subscription objects.

    Generates dict objects matching Stripe Subscription API response structure.
    Uses Decimal precision for monetary calculations.

    Example:
        >>> sub = StripeSubscriptionFactory()
        >>> print(sub["id"])
        'sub_test_0'
        >>> print(sub["status"])
        'active'
    """

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: f"sub_test_{n}")
    object = factory.LazyAttribute(lambda obj: "subscription")
    status = "active"
    current_period_start = factory.LazyFunction(lambda: int(datetime.now().timestamp()))
    current_period_end = factory.LazyFunction(
        lambda: int((datetime.now() + timedelta(days=30)).timestamp())
    )

    # Customer reference
    customer = factory.Sequence(lambda n: f"cus_test_{n}")

    # Subscription items
    items = factory.LazyAttribute(
        lambda o: {
            "object": "list",
            "data": [StripeSubscriptionItemFactory()],
            "has_more": False,
        }
    )

    # Pricing (in cents, using Decimal)
    # Default: $9.99/month
    items_data = [
        {
            "price": "price_test",
            "quantity": 1,
        }
    ]

    # Timestamps
    created = factory.LazyFunction(lambda: int(datetime.now().timestamp()))
    start_date = factory.LazyFunction(lambda: int(datetime.now().timestamp()))

    livemode = False
    metadata = factory.LazyFunction(dict)
    collection_method = "charge_automatically"


class StripeWebhookEventFactory(factory.Factory):
    """
    Factory for Stripe webhook event objects.

    Generates dict objects matching Stripe Event API response structure.
    Supports various event types (payment_intent.succeeded, etc.).

    Example:
        >>> event = StripeWebhookEventFactory(type="payment_intent.succeeded")
        >>> print(event["id"])
        'evt_test_0'
        >>> print(event["type"])
        'payment_intent.succeeded'
    """

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: f"evt_test_{n}")
    object = factory.LazyAttribute(lambda obj: "event")
    type = "payment_intent.succeeded"
    api_version = "2023-10-16"
    created = factory.LazyFunction(lambda: int(datetime.now().timestamp()))

    # Event data (contains the actual object)
    data = factory.LazyAttribute(
        lambda obj: {
            "object": StripeChargeFactory(),
            "previous_attributes": None,
        }
    )

    livemode = False
    pending_webhooks = 0
    request = None
    metadata = factory.LazyFunction(dict)


class StripePaymentIntentFactory(factory.Factory):
    """
    Factory for Stripe payment intent objects.

    Generates dict objects matching Stripe PaymentIntent API response structure.
    Uses Decimal precision for amounts.

    Example:
        >>> intent = StripePaymentIntentFactory()
        >>> print(intent["id"])
        'pi_test_0'
        >>> print(intent["amount"])
        1000  # $10.00 in cents
    """

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: f"pi_test_{n}")
    object = factory.LazyAttribute(lambda obj: "payment_intent")
    amount = factory.LazyAttribute(
        lambda obj: int(to_decimal("10.00") * 100)  # $10.00 in cents
    )
    amount_capturable = 0
    amount_received = factory.LazyAttribute(lambda obj: obj["amount"])
    currency = "usd"
    status = "succeeded"

    # Customer reference
    customer = factory.Sequence(lambda n: f"cus_test_{n}")

    # Timestamps
    created = factory.LazyFunction(lambda: int(datetime.now().timestamp()))

    livemode = False
    metadata = factory.LazyFunction(dict)
    description = factory.Sequence(lambda n: f"Payment intent pi_test_{n}")


# Export all factories
__all__ = [
    "StripeChargeFactory",
    "StripeCustomerFactory",
    "StripeInvoiceFactory",
    "StripeSubscriptionItemFactory",
    "StripeSubscriptionFactory",
    "StripeWebhookEventFactory",
    "StripePaymentIntentFactory",
]
