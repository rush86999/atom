# -*- coding: utf-8 -*-
"""Coverage wave 80 — core/business_intelligence.py to >=95% (standalone,
in-memory SQLite; AutoInvoicer is absent in this env so the fallback branch
is exercised naturally).

R80 real bugs fixed (TDD red→green):
- Bug: status=="delivered" shipments read `order.status.type.enums`
  (AttributeError — String column has no enums) → every delivered shipment
  crashed. Fix: assign "delivered" directly.
- Bug: all EcommerceOrder lookups filtered on non-existent `workspace_id`
  column (AttributeError) → every shipment/PO-sales-order event crashed and
  was silently rolled back. Fix: `tenant_id` (matches
  integrations/shopify_webhooks.py convention).

Covers:
- process_extracted_events: full pipeline commit, exception → rollback.
- _handle_shipments: tracking-less skip, order-by-id, order-by-external_id,
  shipped/in_transit → fulfilled, delivered, metadata_json init/update,
  order-not-found, non-order entity target.
- _handle_quotes: request intent (deal found/not found/no deal_id), offer
  intent (deal.value set + quotes list), existing metadata_json.
- _handle_orders: PO→Deal link, PO→SalesOrder link, PO→Contract no-op,
  deal/order not found.
- _handle_rules: new insert + existing upsert + default description.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

import core.models  # noqa: F401 (register models)
import ecommerce.models  # noqa: F401
import sales.models  # noqa: F401
from core.business_intelligence import BusinessEventIntelligence
from core.database import Base
from core.models import BusinessRule, EcommerceCustomer, EcommerceOrder
from sales.models import Deal

WS = "t1"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def svc(db):
    return BusinessEventIntelligence(db_session=db)


def _make_order(db, order_id="ord1", external_id="ext-1", status="pending"):
    customer = EcommerceCustomer(
        id=f"cust_{order_id}", tenant_id=WS, email=f"{order_id}@x.com",
    )
    db.add(customer)
    order = EcommerceOrder(
        id=order_id, tenant_id=WS, customer_id=customer.id,
        external_id=external_id, status=status,
    )
    db.add(order)
    db.commit()
    return order


def _make_deal(db, deal_id="deal1"):
    deal = Deal(id=deal_id, workspace_id=WS, name="Deal 1")
    db.add(deal)
    db.commit()
    return deal


SHIPMENT_KNOWLEDGE = {
    "entities": [
        {
            "id": "ship_1", "type": "Shipment",
            "properties": {
                "tracking_number": "TRK123", "carrier": "UPS",
                "status": "shipped",
                "shipped_at": "2026-08-01T10:00:00Z",
                "estimated_delivery": "2026-08-05T10:00:00Z",
            },
        },
        {
            "id": "ord_ent", "type": "EcommerceOrder",
            "properties": {"id": "ord1", "external_id": "ext-1"},
        },
    ],
    "relationships": [
        {"from": "ship_1", "to": "ord_ent", "type": "UPDATES_STATUS"},
    ],
}


# ============================================================================
# process_extracted_events — pipeline + rollback
# ============================================================================

@pytest.mark.asyncio
async def test_process_extracted_events_commits(svc, db):
    _make_order(db, "ord1", "ext-1")
    _make_deal(db, "deal1")
    knowledge = dict(SHIPMENT_KNOWLEDGE)
    knowledge["relationships"].append(
        {"from": "po_1", "to": "deal_ent", "type": "LINKS_TO"})
    knowledge["entities"].extend([
        {
            "id": "po_1", "type": "PurchaseOrder",
            "properties": {"id": "PO-1", "po_number": "PO-1", "amount": 100,
                           "vendor": "Acme"},
        },
        {"id": "deal_ent", "type": "Deal", "properties": {"id": "deal1"}},
    ])
    await svc.process_extracted_events(knowledge, WS)
    order = db.query(EcommerceOrder).filter(EcommerceOrder.id == "ord1").first()
    assert order.status == "fulfilled"
    assert order.metadata_json["tracking_number"] == "TRK123"
    assert order.metadata_json["carrier"] == "UPS"
    assert order.metadata_json["shipped_at"] == "2026-08-01T10:00:00Z"
    deal = db.query(Deal).filter(Deal.id == "deal1").first()
    assert deal.metadata_json["purchase_orders"][0]["po_number"] == "PO-1"


@pytest.mark.asyncio
async def test_process_extracted_events_exception_rollback(svc, db):
    knowledge = {
        "entities": [
            {
                "id": "ship_1", "type": "Shipment",
                "properties": "not-a-dict",
            },
        ],
        "relationships": [],
    }
    await svc.process_extracted_events(knowledge, WS)
    assert db.query(EcommerceOrder).count() == 0


# ============================================================================
# _handle_shipments
# ============================================================================

@pytest.mark.asyncio
async def test_shipments_delivered_status(svc, db):
    """R80 regression: status=='delivered' previously read
    order.status.type.enums (AttributeError — String column has no enums)."""
    _make_order(db, "ord1", "ext-1")
    knowledge = {
        "entities": [
            {
                "id": "ship_1", "type": "Shipment",
                "properties": {"tracking_number": "TRK9", "status": "delivered"},
            },
            {"id": "ord_ent", "type": "Order",
             "properties": {"id": "ord1"}},
        ],
        "relationships": [
            {"from": "ship_1", "to": "ord_ent", "type": "UPDATES_STATUS"},
        ],
    }
    await svc._handle_shipments(knowledge, WS, db)
    db.commit()
    order = db.query(EcommerceOrder).filter(EcommerceOrder.id == "ord1").first()
    assert order.status == "delivered"


@pytest.mark.asyncio
async def test_shipments_in_transit(svc, db):
    _make_order(db, "ord1", "ext-1")
    knowledge = {
        "entities": [
            {
                "id": "ship_1", "type": "Shipment",
                "properties": {"tracking_number": "TRK8", "status": "in_transit"},
            },
            {"id": "ord_ent", "type": "EcommerceOrder",
             "properties": {"external_id": "ext-1"}},
        ],
        "relationships": [
            {"from": "ship_1", "to": "ord_ent", "type": "UPDATES_STATUS"},
        ],
    }
    await svc._handle_shipments(knowledge, WS, db)
    order = db.query(EcommerceOrder).filter(EcommerceOrder.id == "ord1").first()
    assert order.status == "fulfilled"
    assert order.metadata_json["tracking_number"] == "TRK8"


@pytest.mark.asyncio
async def test_shipments_no_tracking_skipped(svc, db):
    knowledge = {
        "entities": [
            {"id": "ship_1", "type": "Shipment", "properties": {}},
            {"id": "ord_ent", "type": "EcommerceOrder",
             "properties": {"id": "ord1"}},
        ],
        "relationships": [
            {"from": "ship_1", "to": "ord_ent", "type": "UPDATES_STATUS"},
        ],
    }
    await svc._handle_shipments(knowledge, WS, db)
    assert db.query(EcommerceOrder).count() == 0


@pytest.mark.asyncio
async def test_shipments_order_not_found(svc, db):
    await svc._handle_shipments(dict(SHIPMENT_KNOWLEDGE), WS, db)
    assert db.query(EcommerceOrder).count() == 0


@pytest.mark.asyncio
async def test_shipments_non_order_entity_ignored(svc, db):
    _make_order(db, "ord1", "ext-1")
    knowledge = {
        "entities": [
            {
                "id": "ship_1", "type": "Shipment",
                "properties": {"tracking_number": "TRK7"},
            },
            {"id": "note_ent", "type": "Note", "properties": {"id": "ord1"}},
        ],
        "relationships": [
            {"from": "ship_1", "to": "note_ent", "type": "UPDATES_STATUS"},
        ],
    }
    await svc._handle_shipments(knowledge, WS, db)
    order = db.query(EcommerceOrder).filter(EcommerceOrder.id == "ord1").first()
    assert order.status == "pending"


@pytest.mark.asyncio
async def test_shipments_existing_metadata_json(svc, db):
    _make_order(db, "ord1", "ext-1")
    order = db.query(EcommerceOrder).filter(EcommerceOrder.id == "ord1").first()
    order.metadata_json = {"note": "keep me"}
    db.commit()
    await svc._handle_shipments(dict(SHIPMENT_KNOWLEDGE), WS, db)
    order = db.query(EcommerceOrder).filter(EcommerceOrder.id == "ord1").first()
    assert order.metadata_json["note"] == "keep me"
    assert order.metadata_json["tracking_number"] == "TRK123"


# ============================================================================
# _handle_quotes
# ============================================================================

@pytest.mark.asyncio
async def test_quotes_request_intent_deal_found(svc, db):
    _make_deal(db, "deal1")
    knowledge = {
        "entities": [
            {"id": "quote_1", "type": "Quote",
             "properties": {"amount": 500.0, "currency": "USD",
                            "deal_id": "deal1"}},
        ],
        "relationships": [
            {"from": "msg_1", "to": "request_quote", "type": "INTENT"},
        ],
    }
    await svc._handle_quotes(knowledge, WS, db)
    deal = db.query(Deal).filter(Deal.id == "deal1").first()
    assert deal.metadata_json["quote_requests"][0]["amount"] == 500.0
    assert deal.metadata_json["quote_requests"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_quotes_request_intent_deal_not_found(svc, db):
    knowledge = {
        "entities": [
            {"id": "quote_1", "type": "QuoteRequest",
             "properties": {"deal_id": "nope", "quote_type": "request"}},
        ],
        "relationships": [
            {"from": "msg_1", "to": "request_quote", "type": "INTENT"},
        ],
    }
    await svc._handle_quotes(knowledge, WS, db)
    assert db.query(Deal).count() == 0


@pytest.mark.asyncio
async def test_quotes_request_no_deal_id(svc, db):
    knowledge = {
        "entities": [
            {"id": "quote_1", "type": "Quote", "properties": {}},
        ],
        "relationships": [
            {"from": "msg_1", "to": "request_quote", "type": "INTENT"},
        ],
    }
    await svc._handle_quotes(knowledge, WS, db)
    assert db.query(Deal).count() == 0


@pytest.mark.asyncio
async def test_quotes_offer_intent(svc, db):
    _make_deal(db, "deal1")
    knowledge = {
        "entities": [
            {"id": "quote_1", "type": "QuoteOffer",
             "properties": {"deal_id": "deal1", "amount": 1200.0,
                            "currency": "EUR", "valid_until": "2026-09-01"}},
        ],
        "relationships": [
            {"from": "msg_1", "to": "offer_quote", "type": "INTENT"},
        ],
    }
    await svc._handle_quotes(knowledge, WS, db)
    deal = db.query(Deal).filter(Deal.id == "deal1").first()
    assert deal.value == 1200.0
    assert deal.metadata_json["quotes"][0]["currency"] == "EUR"
    assert deal.metadata_json["quotes"][0]["valid_until"] == "2026-09-01"


@pytest.mark.asyncio
async def test_quotes_offer_proposal_type_no_amount(svc, db):
    _make_deal(db, "deal1")
    deal = db.query(Deal).filter(Deal.id == "deal1").first()
    deal.metadata_json = {"existing": True}
    db.commit()
    knowledge = {
        "entities": [
            {"id": "quote_1", "type": "Quote",
             "properties": {"deal_id": "deal1", "quote_type": "proposal"}},
        ],
        "relationships": [],
    }
    await svc._handle_quotes(knowledge, WS, db)
    deal = db.query(Deal).filter(Deal.id == "deal1").first()
    assert deal.metadata_json["existing"] is True
    assert deal.metadata_json["quotes"][0]["amount"] is None


# ============================================================================
# _handle_orders
# ============================================================================

@pytest.mark.asyncio
async def test_orders_po_links_deal(svc, db):
    _make_deal(db, "deal1")
    knowledge = {
        "entities": [
            {"id": "po_1", "type": "PurchaseOrder",
             "properties": {"id": "PO-9", "po_number": "PO-9",
                            "amount": 250.0, "vendor": "Acme"}},
            {"id": "deal_ent", "type": "Deal", "properties": {"id": "deal1"}},
        ],
        "relationships": [
            {"from": "po_1", "to": "deal_ent", "type": "LINKS_TO"},
        ],
    }
    await svc._handle_orders(knowledge, WS, db)
    deal = db.query(Deal).filter(Deal.id == "deal1").first()
    assert deal.metadata_json["purchase_orders"][0]["po_number"] == "PO-9"
    assert deal.metadata_json["purchase_orders"][0]["vendor"] == "Acme"


@pytest.mark.asyncio
async def test_orders_po_links_deal_not_found(svc, db):
    knowledge = {
        "entities": [
            {"id": "po_1", "type": "PurchaseOrder",
             "properties": {"id": "PO-1", "po_number": "PO-1"}},
            {"id": "deal_ent", "type": "Deal", "properties": {"id": "nope"}},
        ],
        "relationships": [
            {"from": "po_1", "to": "deal_ent", "type": "LINKS_TO"},
        ],
    }
    await svc._handle_orders(knowledge, WS, db)
    assert db.query(Deal).count() == 0


@pytest.mark.asyncio
async def test_orders_po_refers_sales_order(svc, db):
    _make_order(db, "ord1", "ext-1")
    knowledge = {
        "entities": [
            {"id": "po_1", "type": "PurchaseOrder",
             "properties": {"id": "PO-7", "po_number": "PO-7",
                            "amount": 75.0, "vendor": "Beta"}},
            {"id": "so_ent", "type": "SalesOrder", "properties": {"id": "ord1"}},
        ],
        "relationships": [
            {"from": "po_1", "to": "so_ent", "type": "REFERS_TO"},
        ],
    }
    await svc._handle_orders(knowledge, WS, db)
    order = db.query(EcommerceOrder).filter(EcommerceOrder.id == "ord1").first()
    assert order.metadata_json["purchase_order"]["po_number"] == "PO-7"


@pytest.mark.asyncio
async def test_orders_po_to_contract_noop(svc, db):
    knowledge = {
        "entities": [
            {"id": "po_1", "type": "PurchaseOrder",
             "properties": {"id": "PO-1", "po_number": "PO-1"}},
            {"id": "ct_ent", "type": "Contract", "properties": {"id": "c1"}},
        ],
        "relationships": [
            {"from": "po_1", "to": "ct_ent", "type": "LINKS_TO"},
        ],
    }
    await svc._handle_orders(knowledge, WS, db)
    assert db.query(Deal).count() == 0
    assert db.query(EcommerceOrder).count() == 0


@pytest.mark.asyncio
async def test_orders_po_to_sales_order_not_found(svc, db):
    knowledge = {
        "entities": [
            {"id": "po_1", "type": "PurchaseOrder",
             "properties": {"id": "PO-1", "po_number": "PO-1"}},
            {"id": "so_ent", "type": "SalesOrder", "properties": {"id": "nope"}},
        ],
        "relationships": [
            {"from": "po_1", "to": "so_ent", "type": "REFERS_TO"},
        ],
    }
    await svc._handle_orders(knowledge, WS, db)
    assert db.query(EcommerceOrder).count() == 0


# ============================================================================
# _handle_rules
# ============================================================================

@pytest.mark.asyncio
async def test_rules_new_insert(svc, db):
    knowledge = {
        "entities": [
            {"id": "rule_1", "type": "BusinessRule",
             "properties": {"description": "10% discount over 5 items",
                            "type": "discount", "value": 0.1,
                            "applies_to": "order"}},
        ],
        "relationships": [],
    }
    await svc._handle_rules(knowledge, WS, db)
    rule = db.query(BusinessRule).filter(
        BusinessRule.description == "10% discount over 5 items").first()
    assert rule is not None
    assert rule.rule_type == "discount"
    assert rule.formula == "0.1"
    assert rule.applies_to == "order"


@pytest.mark.asyncio
async def test_rules_existing_upsert(svc, db):
    rule = BusinessRule(workspace_id=WS, description="gold rule",
                        rule_type="pricing", formula="x*2", applies_to="deal")
    db.add(rule)
    db.commit()
    knowledge = {
        "entities": [
            {"id": "rule_1", "type": "BusinessRule",
             "properties": {"description": "gold rule", "type": "tax",
                            "formula": "x*1.2", "applies_to": "quote"}},
        ],
        "relationships": [],
    }
    await svc._handle_rules(knowledge, WS, db)
    db.commit()
    db.expire_all()
    rule = db.query(BusinessRule).filter(
        BusinessRule.description == "gold rule").first()
    assert rule.rule_type == "tax"
    assert rule.formula == "x*1.2"
    assert rule.applies_to == "quote"
    assert db.query(BusinessRule).count() == 1


@pytest.mark.asyncio
async def test_rules_default_description(svc, db):
    knowledge = {
        "entities": [
            {"id": "rule_1", "type": "BusinessRule", "properties": {}},
        ],
        "relationships": [],
    }
    await svc._handle_rules(knowledge, WS, db)
    rule = db.query(BusinessRule).filter(
        BusinessRule.description == "Untitled Rule").first()
    assert rule is not None
    assert rule.rule_type == "pricing"
    assert rule.formula is None
    assert rule.applies_to is None


# ============================================================================
# Constructor / session plumbing
# ============================================================================

def test_init_with_autoinvoicer_available():
    from unittest.mock import MagicMock
    import core.business_intelligence as mod
    fake = MagicMock()
    with patch.object(mod, "AutoInvoicer", fake):
        svc = mod.BusinessEventIntelligence(db_session="sess")
    fake.assert_called_once_with(db_session="sess")
    assert svc.invoicer is not None


@pytest.mark.asyncio
async def test_process_extracted_events_without_injected_session():
    """No db_session → get_db_session() is entered and closed by the service."""
    from unittest.mock import MagicMock
    import core.business_intelligence as mod

    class _FakeSession:
        def __init__(self):
            self.closed = False
            self.committed = False

        def query(self, model):
            return _FakeQuery()

        def commit(self):
            self.committed = True

        def rollback(self):
            pass

        def close(self):
            self.closed = True

    class _FakeQuery:
        def filter(self, *a, **k):
            return self

        def first(self):
            return None

    fake_session = _FakeSession()
    with patch.object(mod, "get_db_session", return_value=fake_session):
        svc = mod.BusinessEventIntelligence()
        await svc.process_extracted_events({"entities": [], "relationships": []}, WS)
    assert fake_session.committed is True
    assert fake_session.closed is True
