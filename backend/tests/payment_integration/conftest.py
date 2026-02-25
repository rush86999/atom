"""
Pytest fixtures for payment integration tests.

Provides stripe-mock server, database sessions, and test clients
for deterministic payment testing.
"""

import os
import pytest
import stripe
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
    Creates all tables from core.models.Base on setup.

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

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create and yield session
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables to clean up
        Base.metadata.drop_all(engine)
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


__all__ = [
    "stripe_mock_container",
    "mock_stripe_api",
    "db_session",
    "payment_client",
    "stripe_access_token",
    "stripe_test_customer",
]
