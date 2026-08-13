# -*- coding: utf-8 -*-
"""Coverage wave 86 — core/identity_resolver (user/agent lookup, alias, not-found).

CustomerResolutionEngine tested against a real in-memory SQLite schema
(ecommerce + sales + accounting models):

- resolve_customer: existing customer passthrough, new customer creation,
  CRM (Lead) linking, Accounting (Entity) linking, and persistence of a
  newly-created customer even when no cross-system link is found (bug fix:
  previously only committed when a link was found, silently losing new
  customers), plus the tenant/workspace filter on Lead (bug fix: filtered a
  non-existent Lead.tenant_id column → AttributeError).
- get_unified_identity: found customer → full unified dict; not found → {}.

Zero LLM spend, no network.
"""
import logging
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from accounting.models import Entity, EntityType  # noqa: F401
from core.database import Base
from core.identity_resolver import CustomerResolutionEngine
from ecommerce.models import EcommerceCustomer  # noqa: F401
from sales.models import Lead  # noqa: F401


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _fresh_session(engine):
    return sessionmaker(bind=engine)()


def _make_customer(db, *, tenant_id="ws-1", email="jane@example.com",
                   first="Jane", last="Doe", crm_id=None, acct_id=None):
    c = EcommerceCustomer(
        tenant_id=tenant_id, email=email, first_name=first, last_name=last,
        external_id="ext-1",
        crm_contact_id=crm_id, accounting_entity_id=acct_id,
    )
    db.add(c)
    db.commit()
    return c


def _make_lead(db, *, workspace_id="ws-1", email="jane@example.com"):
    lead = Lead(workspace_id=workspace_id, email=email,
                first_name="Jane", last_name="Doe", status="new")
    db.add(lead)
    db.commit()
    return lead


def _make_entity(db, *, workspace_id="ws-1", name="Jane Doe"):
    entity = Entity(workspace_id=workspace_id, name=name, type=EntityType.CUSTOMER)
    db.add(entity)
    db.commit()
    return entity


# ---------------------------------------------------------------------------
# resolve_customer
# ---------------------------------------------------------------------------

def test_resolve_existing_customer_unchanged(db):
    existing = _make_customer(db, crm_id="crm-1", acct_id="ent-1")
    engine = db.get_bind()
    with patch("core.identity_resolver.logger") as mock_logger:
        result = CustomerResolutionEngine(db).resolve_customer("ws-1", "jane@example.com")
    assert result.id == existing.id
    assert result.crm_contact_id == "crm-1"
    assert result.accounting_entity_id == "ent-1"
    assert mock_logger.info.call_count == 0


def test_resolve_existing_customer_links_crm_lead(db):
    _make_customer(db)
    lead = _make_lead(db)
    result = CustomerResolutionEngine(db).resolve_customer("ws-1", "jane@example.com")
    assert result.crm_contact_id == lead.id


def test_resolve_existing_customer_links_accounting_entity(db):
    _make_customer(db)
    entity = _make_entity(db)
    result = CustomerResolutionEngine(db).resolve_customer("ws-1", "jane@example.com")
    assert result.accounting_entity_id == entity.id


def test_resolve_existing_customer_links_both(db):
    _make_customer(db)
    lead = _make_lead(db)
    entity = _make_entity(db)
    result = CustomerResolutionEngine(db).resolve_customer("ws-1", "jane@example.com")
    assert result.crm_contact_id == lead.id
    assert result.accounting_entity_id == entity.id


def test_resolve_new_customer_with_links(db, engine):
    lead = _make_lead(db, email="bob@example.com")
    entity = _make_entity(db, name="Bob Smith")
    result = CustomerResolutionEngine(db).resolve_customer(
        "ws-1", "bob@example.com", first_name="Bob", last_name="Smith"
    )
    assert result.id
    assert result.crm_contact_id == lead.id  # links by email
    assert result.email == "bob@example.com"

    fresh = _fresh_session(engine)
    row = fresh.query(EcommerceCustomer).filter(EcommerceCustomer.email == "bob@example.com").first()
    fresh.close()
    assert row is not None  # committed


def test_resolve_new_customer_without_links_still_persisted(db, engine):
    """BUG FIX (RED): a newly-created customer was only committed when a
    cross-system link was found — with no Lead/Entity match the new customer
    was silently rolled back. Must be persisted either way."""
    engine2 = engine
    result = CustomerResolutionEngine(db).resolve_customer(
        "ws-1", "nobody@example.com", first_name="No", last_name="Body"
    )
    assert result.id
    assert result.crm_contact_id is None
    assert result.accounting_entity_id is None

    fresh = _fresh_session(engine2)
    row = fresh.query(EcommerceCustomer).filter(EcommerceCustomer.email == "nobody@example.com").first()
    fresh.close()
    assert row is not None  # committed despite no links


def test_resolve_lead_lookup_uses_workspace_id_column(db):
    """BUG FIX (RED): the CRM lookup filtered `Lead.tenant_id` but Lead has
    no such column (only workspace_id) → AttributeError/500 on every
    unlinked customer. Must query by Lead.workspace_id."""
    _make_customer(db)
    _make_lead(db, workspace_id="ws-1")
    with patch("core.identity_resolver.logger"):
        result = CustomerResolutionEngine(db).resolve_customer("ws-1", "jane@example.com")
    assert result.crm_contact_id is not None


def test_resolve_entity_name_mismatch_no_link(db):
    _make_customer(db)
    _make_entity(db, name="Someone Else")
    result = CustomerResolutionEngine(db).resolve_customer("ws-1", "jane@example.com")
    assert result.accounting_entity_id is None


def test_resolve_new_customer_logs_creation(db, caplog):
    with caplog.at_level(logging.INFO, logger="core.identity_resolver"):
        CustomerResolutionEngine(db).resolve_customer("ws-1", "fresh@example.com")
    assert "Created new EcommerceCustomer: fresh@example.com" in caplog.text


# ---------------------------------------------------------------------------
# get_unified_identity
# ---------------------------------------------------------------------------

def test_get_unified_identity_found(db):
    customer = _make_customer(db, crm_id="crm-9", acct_id="ent-9")
    identity = CustomerResolutionEngine(db).get_unified_identity(customer.id)
    assert identity == {
        "ecommerce_id": customer.id,
        "external_id": "ext-1",
        "email": "jane@example.com",
        "crm_contact_id": "crm-9",
        "accounting_entity_id": "ent-9",
        "name": "Jane Doe",
    }


def test_get_unified_identity_not_found(db):
    assert CustomerResolutionEngine(db).get_unified_identity("missing-id") == {}
