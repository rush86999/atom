"""
Tests for Auto-Invoicer Fixes

Tests for:
- Dynamic price lookup (no hardcoded $100 fallback)
- Accounting entity resolver
- Proper handling of missing prices
- Accounting entity creation and linking
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from core.auto_invoicer import AutoInvoicer
from service_delivery.models import Appointment, AppointmentStatus
from accounting.models import Invoice, Entity, EntityType
from ecommerce.models import EcommerceOrder, EcommerceCustomer
from core.models import BusinessProductService, Workspace


class TestAppointmentPriceResolution:
    """Test dynamic appointment price resolution"""

    def test_price_from_deposit_amount(self, db_session):
        """Should use deposit amount when > 0"""
        workspace = self._create_workspace(db_session)
        appointment = self._create_appointment(db_session, workspace, deposit_amount=150.0)

        invoicer = AutoInvoicer(db_session)
        price = invoicer._resolve_appointment_price(appointment, db_session)

        assert price == 150.0
        assert price > 0

    def test_price_from_linked_service(self, db_session):
        """Should use service base_price when deposit is 0"""
        workspace = self._create_workspace(db_session)

        # Create service with price
        service = BusinessProductService(
            workspace_id=workspace.id,
            name="Consulting Service",
            type="service",
            base_price=250.0,
        )
        db_session.add(service)
        db_session.commit()

        # Create appointment with 0 deposit but linked service
        appointment = self._create_appointment(
            db_session,
            workspace,
            deposit_amount=0.0,
            service_id=service.id
        )

        invoicer = AutoInvoicer(db_session)
        price = invoicer._resolve_appointment_price(appointment, db_session)

        assert price == 250.0

    def test_price_from_metadata(self, db_session):
        """Should use service_price from metadata when deposit is 0"""
        workspace = self._create_workspace(db_session)
        appointment = self._create_appointment(
            db_session,
            workspace,
            deposit_amount=0.0,
            metadata_json={"service_price": 175.0}
        )

        invoicer = AutoInvoicer(db_session)
        price = invoicer._resolve_appointment_price(appointment, db_session)

        assert price == 175.0

    def test_price_from_workspace_default(self, db_session):
        """Should use workspace default service price"""
        workspace = self._create_workspace(
            db_session,
            metadata_json={"default_service_price": 200.0}
        )
        appointment = self._create_appointment(db_session, workspace, deposit_amount=0.0)

        invoicer = AutoInvoicer(db_session)
        price = invoicer._resolve_appointment_price(appointment, db_session)

        assert price == 200.0

    def test_price_not_found_returns_none(self, db_session):
        """Should return None when no price can be determined"""
        workspace = self._create_workspace(db_session)
        appointment = self._create_appointment(
            db_session,
            workspace,
            deposit_amount=0.0,
            metadata_json=None
        )

        invoicer = AutoInvoicer(db_session)
        price = invoicer._resolve_appointment_price(appointment, db_session)

        assert price is None

    def test_price_priority_order(self, db_session):
        """Should respect priority order: deposit > service > metadata > workspace"""
        workspace = self._create_workspace(
            db_session,
            metadata_json={"default_service_price": 100.0}
        )

        service = BusinessProductService(
            workspace_id=workspace.id,
            name="Service",
            base_price=200.0,
        )
        db_session.add(service)
        db_session.commit()

        # Deposit amount should win (highest priority)
        appointment = self._create_appointment(
            db_session,
            workspace,
            deposit_amount=300.0,
            service_id=service.id,
            metadata_json={"service_price": 250.0}
        )

        invoicer = AutoInvoicer(db_session)
        price = invoicer._resolve_appointment_price(appointment, db_session)

        assert price == 300.0  # Deposit amount wins


class TestAccountingEntityResolver:
    """Test accounting entity resolution for ecommerce orders"""

    def test_existing_accounting_entity(self, db_session):
        """Should use existing accounting_entity_id from customer"""
        workspace = self._create_workspace(db_session)

        # Create accounting entity
        entity = Entity(
            workspace_id=workspace.id,
            name="John Doe",
            email="john@example.com",
            type=EntityType.CUSTOMER,
        )
        db_session.add(entity)
        db_session.commit()

        # Create customer with linked entity
        customer = EcommerceCustomer(
            workspace_id=workspace.id,
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            accounting_entity_id=entity.id,
        )
        db_session.add(customer)
        db_session.commit()

        order = EcommerceOrder(
            workspace_id=workspace.id,
            customer_id=customer.id,
            total_price=100.0,
            status="pending",
        )
        db_session.add(order)
        db_session.commit()

        invoicer = AutoInvoicer(db_session)
        resolved_id = invoicer._resolve_accounting_entity(order, db_session)

        assert resolved_id == entity.id

    def test_find_entity_by_email(self, db_session):
        """Should find existing entity by email when not linked"""
        workspace = self._create_workspace(db_session)

        # Create accounting entity
        entity = Entity(
            workspace_id=workspace.id,
            name="Jane Doe",
            email="jane@example.com",
            type=EntityType.CUSTOMER,
        )
        db_session.add(entity)
        db_session.commit()

        # Create customer WITHOUT linked entity
        customer = EcommerceCustomer(
            workspace_id=workspace.id,
            email="jane@example.com",
            first_name="Jane",
            last_name="Doe",
            accounting_entity_id=None,
        )
        db_session.add(customer)
        db_session.commit()

        order = EcommerceOrder(
            workspace_id=workspace.id,
            customer_id=customer.id,
            total_price=100.0,
            status="pending",
        )
        db_session.add(order)
        db_session.commit()

        invoicer = AutoInvoicer(db_session)
        resolved_id = invoicer._resolve_accounting_entity(order, db_session)

        # Should find and link existing entity
        assert resolved_id == entity.id
        # Customer should now be linked
        db_session.refresh(customer)
        assert customer.accounting_entity_id == entity.id

    def test_create_new_accounting_entity(self, db_session):
        """Should create new accounting entity if none exists"""
        workspace = self._create_workspace(db_session)

        customer = EcommerceCustomer(
            workspace_id=workspace.id,
            email="new@example.com",
            first_name="New",
            last_name="Customer",
            accounting_entity_id=None,
        )
        db_session.add(customer)
        db_session.commit()

        order = EcommerceOrder(
            workspace_id=workspace.id,
            customer_id=customer.id,
            total_price=100.0,
            status="pending",
        )
        db_session.add(order)
        db_session.commit()

        invoicer = AutoInvoicer(db_session)
        resolved_id = invoicer._resolve_accounting_entity(order, db_session)

        # Should create new entity
        assert resolved_id is not None
        entity = db_session.query(Entity).filter(Entity.id == resolved_id).first()
        assert entity is not None
        assert entity.email == "new@example.com"
        assert entity.type == EntityType.CUSTOMER

        # Customer should be linked
        db_session.refresh(customer)
        assert customer.accounting_entity_id == resolved_id

    def test_no_customer_returns_none(self, db_session):
        """Should return None when order has no customer"""
        workspace = self._create_workspace(db_session)

        # Create order without customer (shouldn't happen in practice)
        order = EcommerceOrder(
            workspace_id=workspace.id,
            customer_id=None,  # No customer
            total_price=100.0,
            status="pending",
        )
        db_session.add(order)
        db_session.commit()

        invoicer = AutoInvoicer(db_session)
        resolved_id = invoicer._resolve_accounting_entity(order, db_session)

        assert resolved_id is None


class TestAppointmentInvoicingWithPriceResolution:
    """Integration tests for appointment invoicing with dynamic pricing"""

    def test_invoice_with_deposit_amount(self, db_session):
        """Should create invoice using deposit amount"""
        workspace = self._create_workspace(db_session)
        appointment = self._create_appointment(
            db_session,
            workspace,
            deposit_amount=150.0,
            status=AppointmentStatus.COMPLETED
        )

        invoicer = AutoInvoicer(db_session)
        invoice = invoicer.invoice_appointment(appointment.id)

        assert invoice is not None
        assert invoice.amount == 150.0

    def test_invoice_no_price_returns_none(self, db_session):
        """Should return None when no price can be determined"""
        workspace = self._create_workspace(db_session)
        appointment = self._create_appointment(
            db_session,
            workspace,
            deposit_amount=0.0,
            status=AppointmentStatus.COMPLETED
        )

        invoicer = AutoInvoicer(db_session)
        invoice = invoicer.invoice_appointment(appointment.id)

        # Should not create invoice without price
        assert invoice is None

    def test_invoice_uses_service_price(self, db_session):
        """Should create invoice using service base_price"""
        workspace = self._create_workspace(db_session)

        service = BusinessProductService(
            workspace_id=workspace.id,
            name="Service",
            base_price=300.0,
        )
        db_session.add(service)
        db_session.commit()

        appointment = self._create_appointment(
            db_session,
            workspace,
            deposit_amount=0.0,
            service_id=service.id,
            status=AppointmentStatus.COMPLETED
        )

        invoicer = AutoInvoicer(db_session)
        invoice = invoicer.invoice_appointment(appointment.id)

        assert invoice is not None
        assert invoice.amount == 300.0


class TestEcommerceOrderInvoicingWithEntityResolution:
    """Integration tests for ecommerce order invoicing with entity resolution"""

    def test_invoice_creates_accounting_entity(self, db_session):
        """Should create accounting entity when invoicing order"""
        workspace = self._create_workspace(db_session)

        customer = EcommerceCustomer(
            workspace_id=workspace.id,
            email="test@example.com",
            first_name="Test",
            last_name="Customer",
            accounting_entity_id=None,
        )
        db_session.add(customer)
        db_session.commit()

        order = EcommerceOrder(
            workspace_id=workspace.id,
            customer_id=customer.id,
            total_price=99.99,
            status="fulfilled",
        )
        db_session.add(order)
        db_session.commit()

        invoicer = AutoInvoicer(db_session)
        invoice = invoicer.invoice_ecommerce_order(order.id)

        assert invoice is not None
        assert invoice.amount == 99.99
        assert invoice.customer_id is not None

        # Verify entity was created
        entity = db_session.query(Entity).filter(Entity.id == invoice.customer_id).first()
        assert entity is not None
        assert entity.email == "test@example.com"

    # Helper methods
    def _create_workspace(self, db: Session, **kwargs):
        """Create a test workspace"""
        defaults = {
            "id": "test-workspace-" + str(datetime.utcnow().timestamp()),
            "name": "Test Workspace",
            "metadata_json": {},
        }
        defaults.update(kwargs)

        workspace = Workspace(**defaults)
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return workspace

    def _create_appointment(
        self,
        db: Session,
        workspace: Workspace,
        deposit_amount: float = 0.0,
        service_id: str = None,
        metadata_json: dict = None,
        status: AppointmentStatus = AppointmentStatus.SCHEDULED,
    ):
        """Create a test appointment"""
        # Create customer
        customer = Entity(
            workspace_id=workspace.id,
            name="Test Customer",
            type=EntityType.CUSTOMER,
        )
        db.add(customer)
        db.commit()

        appointment = Appointment(
            workspace_id=workspace.id,
            customer_id=customer.id,
            service_id=service_id,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=1),
            deposit_amount=deposit_amount,
            metadata_json=metadata_json,
            status=status,
        )
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        return appointment


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
