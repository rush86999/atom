"""Standalone SQLite tests for invoice -> provider invoice bindings."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from accounting.invoice_provider_binding import (
    InvoiceProviderBindingConflict,
    InvoiceProviderBindingConnectionNotFound,
    InvoiceProviderBindingInvoiceNotFound,
    bind_invoice_to_provider,
)
from accounting.models import (
    Entity,
    EntityType,
    Invoice,
    InvoiceProviderBinding,
    InvoiceProviderBindingRevision,
    InvoiceStatus,
)
from core.database import Base
from core.models import Tenant, User, UserConnection, Workspace


HOME = {
    "invoice_id": "invoice-home-1",
    "workspace_id": "workspace-home",
    "provider": "stripe",
    "provider_account_id": "acct_fixture",
    "provider_mode": "test",
    "external_invoice_id": "in_first",
    "connection_id": "connection-home",
    "actor_id": "user-home",
    "reason": "Confirmed provider identity",
}


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'invoice_binding.sqlite3'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def _seed(session):
    now = datetime.now(timezone.utc)
    for suffix in ("home", "foreign"):
        tenant_id = f"tenant-{suffix}"
        workspace_id = f"workspace-{suffix}"
        user_id = f"user-{suffix}"
        session.add_all(
            [
                Tenant(id=tenant_id, name=tenant_id, subdomain=tenant_id),
                Workspace(id=workspace_id, tenant_id=tenant_id, name=workspace_id),
                User(
                    id=user_id,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    email=f"{user_id}@example.invalid",
                    first_name="Fixture",
                    last_name="User",
                    role="workspace_admin",
                    status="active",
                ),
                UserConnection(
                    id=f"connection-{suffix}",
                    user_id=user_id,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    integration_id="stripe",
                    connection_name="Fixture",
                    credentials="ciphertext-fixture",
                    status="active",
                ),
                Entity(
                    id=f"customer-{suffix}",
                    workspace_id=workspace_id,
                    name="Synthetic customer",
                    type=EntityType.CUSTOMER,
                ),
            ]
        )
        session.flush()
        for number in (1, 2):
            session.add(
                Invoice(
                    id=f"invoice-{suffix}-{number}",
                    workspace_id=workspace_id,
                    customer_id=f"customer-{suffix}",
                    invoice_number=str(number),
                    issue_date=now - timedelta(days=45),
                    due_date=now - timedelta(days=15),
                    amount=Decimal("123.45"),
                    currency="CAD",
                    status=InvoiceStatus.OPEN,
                )
            )
    session.commit()


def _bind(session, **changes):
    return bind_invoice_to_provider(session, **{**HOME, **changes})


def _audit(session, binding_id):
    return (
        session.execute(
            select(InvoiceProviderBindingRevision)
            .where(InvoiceProviderBindingRevision.binding_id == binding_id)
            .order_by(InvoiceProviderBindingRevision.revision)
        )
        .scalars()
        .all()
    )


def test_creation_and_correction_preserve_exact_audit(session_factory):
    with session_factory() as session:
        _seed(session)
        created = _bind(session)
        binding_id = created.id
        assert created.revision == 1
        session.commit()

    with session_factory() as session:
        corrected = _bind(
            session,
            external_invoice_id="in_second",
            expected_revision=1,
            reason="Corrected exact invoice",
        )
        assert corrected.id == binding_id
        assert corrected.revision == 2

        repeated = _bind(
            session,
            external_invoice_id="in_second",
            expected_revision=2,
        )
        assert repeated.id == binding_id
        assert repeated.revision == 2
        session.commit()

    with session_factory() as session:
        current = session.get(InvoiceProviderBinding, binding_id)
        assert current.external_invoice_id == "in_second"
        assert current.revision == 2

        history = _audit(session, binding_id)
        assert [row.revision for row in history] == [1, 2]
        first, second = history

        assert first.actor_id == second.actor_id == "user-home"
        assert first.reason == "Confirmed provider identity"
        assert second.reason == "Corrected exact invoice"
        assert (
            first.prior_provider,
            first.prior_provider_account_id,
            first.prior_provider_mode,
            first.prior_external_invoice_id,
            first.prior_connection_id,
        ) == (None, None, None, None, None)
        assert (
            first.new_provider,
            first.new_provider_account_id,
            first.new_provider_mode,
            first.new_external_invoice_id,
            first.new_connection_id,
        ) == ("stripe", "acct_fixture", "test", "in_first", "connection-home")
        assert (
            second.prior_provider,
            second.prior_provider_account_id,
            second.prior_provider_mode,
            second.prior_external_invoice_id,
            second.prior_connection_id,
        ) == ("stripe", "acct_fixture", "test", "in_first", "connection-home")
        assert (
            second.new_provider,
            second.new_provider_account_id,
            second.new_provider_mode,
            second.new_external_invoice_id,
            second.new_connection_id,
        ) == ("stripe", "acct_fixture", "test", "in_second", "connection-home")


def test_duplicate_external_invoice_is_refused_without_side_effects(session_factory):
    with session_factory() as session:
        _seed(session)
        _bind(session)
        session.commit()

    with session_factory() as session:
        with pytest.raises(InvoiceProviderBindingConflict) as caught:
            _bind(session, invoice_id="invoice-home-2")
        assert caught.value.current_revision is None
        session.rollback()

    with session_factory() as session:
        assert session.query(InvoiceProviderBinding).count() == 1
        assert session.query(InvoiceProviderBindingRevision).count() == 1
        assert (
            session.query(InvoiceProviderBinding)
            .filter_by(invoice_id="invoice-home-2")
            .one_or_none()
            is None
        )


def test_stale_revision_is_refused_without_side_effects(session_factory):
    with session_factory() as session:
        _seed(session)
        _bind(session)
        session.commit()

    with session_factory() as session:
        _bind(
            session,
            external_invoice_id="in_second",
            expected_revision=1,
            reason="Corrected exact invoice",
        )
        session.commit()

    with session_factory() as session:
        with pytest.raises(InvoiceProviderBindingConflict) as caught:
            _bind(
                session,
                external_invoice_id="in_third",
                expected_revision=1,
                reason="Stale correction",
            )
        assert caught.value.expected_revision == 1
        assert caught.value.current_revision == 2
        session.rollback()

    with session_factory() as session:
        current = session.query(InvoiceProviderBinding).one()
        assert current.external_invoice_id == "in_second"
        assert current.revision == 2
        assert [row.revision for row in _audit(session, current.id)] == [1, 2]


def test_foreign_connection_and_foreign_invoice_are_refused(session_factory):
    with session_factory() as session:
        _seed(session)

        with pytest.raises(InvoiceProviderBindingConnectionNotFound):
            _bind(session, connection_id="connection-foreign")
        with pytest.raises(InvoiceProviderBindingConnectionNotFound):
            _bind(session, actor_id="user-foreign")
        with pytest.raises(InvoiceProviderBindingInvoiceNotFound):
            _bind(
                session,
                invoice_id="invoice-foreign-1",
                workspace_id="workspace-home",
            )
        with pytest.raises(InvoiceProviderBindingInvoiceNotFound):
            _bind(session, workspace_id="workspace-foreign")
        session.rollback()

    with session_factory() as session:
        assert session.query(InvoiceProviderBinding).count() == 0
        assert session.query(InvoiceProviderBindingRevision).count() == 0


def test_binding_never_mutates_invoice_paid_state(session_factory):
    with session_factory() as session:
        _seed(session)
        paid = session.get(Invoice, "invoice-home-2")
        paid.status = InvoiceStatus.PAID
        session.commit()

    with session_factory() as session:
        _bind(session)
        _bind(session, invoice_id="invoice-home-2", external_invoice_id="in_second")
        _bind(session, external_invoice_id="in_third", expected_revision=1)
        session.commit()

    with session_factory() as session:
        assert session.get(Invoice, "invoice-home-1").status == InvoiceStatus.OPEN
        assert session.get(Invoice, "invoice-home-2").status == InvoiceStatus.PAID
        assert session.query(Invoice).count() == 4


def test_caller_rollback_leaves_no_binding_or_audit_rows(session_factory):
    with session_factory() as session:
        _seed(session)

    with session_factory() as session:
        binding = _bind(session)
        assert binding.revision == 1
        session.rollback()

    with session_factory() as session:
        assert session.query(InvoiceProviderBinding).count() == 0
        assert session.query(InvoiceProviderBindingRevision).count() == 0
