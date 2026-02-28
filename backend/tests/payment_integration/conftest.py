"""
Pytest fixtures for payment integration tests.

Provides stripe-mock server, database sessions, and test clients
for deterministic payment testing.
"""

import os
import pytest
import stripe
from datetime import datetime
from unittest import mock
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.models import Base
from tests.mocks.stripe_mock_server import (
    start_stripe_mock,
    stop_stripe_mock,
    get_stripe_mock_url,
    StripeMockError,
)


@pytest.fixture(scope="session")
def stripe_mock_container():
    """
    Start stripe-mock Docker container once per test session.

    Yields:
        Container: Docker container object

    Example:
        def test_charge(stripe_mock_container):
            # stripe-mock is running on http://localhost:12111
            response = stripe.Charge.create(amount=100, currency="usd")
            assert response["status"] == "succeeded"
    """
    container = None
    try:
        container = start_stripe_mock()
        yield container
    except StripeMockError as e:
        pytest.skip(f"Failed to start stripe-mock: {e}")
    finally:
        if container:
            try:
                stop_stripe_mock(container)
            except Exception as e:
                print(f"Warning: Failed to stop stripe-mock: {e}")


@pytest.fixture(autouse=True)
def mock_stripe_api(stripe_mock_container):
    """
    Automatically configure stripe to use mock server.

    This fixture runs automatically for all tests in this module.
    It sets stripe.api_base to the mock server URL and provides a test API key.

    Example:
        def test_create_charge():
            # stripe.api_base is automatically set to mock server
            charge = stripe.Charge.create(amount=100, currency="usd")
            assert charge["status"] == "succeeded"
    """
    mock_url = get_stripe_mock_url()

    # Save original values
    original_api_base = stripe.api_base
    original_api_key = stripe.api_key

    # Configure stripe to use mock
    stripe.api_base = mock_url
    stripe.api_key = "sk_test_12345"  # Valid-looking test key for stripe-mock

    yield

    # Restore original values
    stripe.api_base = original_api_base
    stripe.api_key = original_api_key


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """
    Create an in-memory SQLite database session for testing.

    Uses SQLAlchemy with in-memory SQLite for fast, isolated tests.
    Creates accounting tables with necessary foreign key tables.

    Yields:
        Session: SQLAlchemy database session

    Example:
        def test_create_customer(db_session):
            customer = Customer(name="Test User")
            db_session.add(customer)
            db_session.commit()
            assert customer.id is not None
    """
    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Import all models
    from accounting.models import (
        Account, Transaction, JournalEntry, CategorizationProposal,
        Entity, Bill, Invoice, Document, TaxNexus, FinancialClose,
        CategorizationRule, Budget
    )
    from sqlalchemy import Table, Column, String, MetaData

    # Create metadata for dummy FK tables
    metadata = MetaData()

    # Create dummy tables for FK references
    workspaces_table = Table(
        "workspaces", metadata,
        Column("id", String, primary_key=True)
    )

    service_projects_table = Table(
        "service_projects", metadata,
        Column("id", String, primary_key=True)
    )

    service_milestones_table = Table(
        "service_milestones", metadata,
        Column("id", String, primary_key=True)
    )

    users_table = Table(
        "users", metadata,
        Column("id", String, primary_key=True)
    )

    # Create dummy tables first
    for table in [workspaces_table, service_projects_table, service_milestones_table, users_table]:
        table.create(engine, checkfirst=True)

    # Now create accounting tables
    accounting_tables = [
        Account.__table__, Transaction.__table__, JournalEntry.__table__,
        CategorizationProposal.__table__, Entity.__table__, Bill.__table__,
        Invoice.__table__, Document.__table__, TaxNexus.__table__,
        FinancialClose.__table__, CategorizationRule.__table__, Budget.__table__,
    ]

    for table in accounting_tables:
        table.create(engine, checkfirst=True)

    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create and yield session
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables to clean up
        for table in reversed(accounting_tables):
            table.drop(engine)
        for table in [users_table, service_milestones_table, service_projects_table, workspaces_table]:
            table.drop(engine)
        engine.dispose()


@pytest.fixture
def payment_client():
    """
    Create a FastAPI TestClient for Stripe routes.

    Note: This fixture is a placeholder for future API route testing.
    For now, we use the stripe Python SDK directly with mock_stripe_api.

    Returns:
        TestClient: FastAPI test client

    Example:
        def test_payments_endpoint(payment_client):
            response = payment_client.get("/api/stripe/payments")
            assert response.status_code == 200
    """
    # Import here to avoid import errors if FastAPI routes don't exist
    try:
        from fastapi.testclient import TestClient
        from integrations.stripe_routes import router

        # Create test app with router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)

        return TestClient(app)
    except ImportError as e:
        pytest.skip(f"FastAPI routes not available: {e}")


@pytest.fixture
def stripe_access_token() -> str:
    """
    Provide a fake Stripe access token for testing.

    Returns:
        str: Mock access token

    Example:
        def test_stripe_service(stripe_access_token):
            result = stripe_service.get_balance(stripe_access_token)
            assert "available" in result
    """
    return "sk_test_mock_token_1234567890"


@pytest.fixture
def stripe_test_customer(stripe_mock_container, mock_stripe_api):
    """
    Create a test Stripe customer.

    Returns:
        dict: Stripe customer object

    Example:
        def test_subscription(stripe_test_customer):
            # Use the customer object
            sub = stripe.Subscription.create(
                customer=stripe_test_customer["id"],
                items=[{"price": "price_test"}]
            )
    """
    customer = stripe.Customer.create(
        email="test@example.com",
        name="Test User",
        description="Test customer for payment integration tests",
    )
    return customer


@pytest.fixture
def setup_customer():
    """
    Create a test customer in the database for payment flow tests.

    Creates a test Stripe customer and stores reference in database.
    Cleans up automatically after test completes.

    Yields:
        tuple: (customer_id: str, customer_object: dict)

    Example:
        def test_charge_flow(setup_customer):
            customer_id, customer = setup_customer
            charge = stripe.Charge.create(
                amount=1000,
                currency="usd",
                customer=customer_id
            )
    """
    import stripe
    from core.decimal_utils import to_decimal

    # Create Stripe customer
    customer = stripe.Customer.create(
        email=f"test_customer_{id(object())}@example.com",
        name="Test Payment Flow Customer",
        description="Customer for payment flow integration tests",
        metadata={"test": "true"},
    )

    # In a real implementation, you would also store this in your database
    # For now, we just return the Stripe customer info

    yield customer["id"], customer

    # Cleanup: Stripe customer will be cleaned up when mock server stops
    # No manual cleanup needed for mock data


__all__ = [
    "stripe_mock_container",
    "mock_stripe_api",
    "payment_client",
    "stripe_access_token",
    "stripe_test_customer",
    "setup_customer",
]
