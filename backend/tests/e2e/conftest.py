"""
End-to-End Test Configuration and Fixtures

This module provides fixtures for comprehensive E2E testing of Atom's high-impact features.
All tests use in-memory SQLite for fast execution and support real API keys for LLM providers.
"""

import os
import sys
import asyncio
import time
import jwt
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator, Dict, Any
from pathlib import Path
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient
import httpx

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from core.models import Base, AgentRegistry
from core.database import get_db
from core.governance_cache import GovernanceCache
from core.agent_governance_service import AgentGovernanceService


# =============================================================================
# Environment Configuration
# =============================================================================

def setup_test_environment():
    """Configure environment for E2E testing."""
    os.environ["ATOM_ENVIRONMENT"] = "test"
    os.environ["ATOM_DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["LOG_LEVEL"] = "DEBUG"

    # Feature flags
    os.environ["STREAMING_GOVERNANCE_ENABLED"] = "true"
    os.environ["CANVAS_GOVERNANCE_ENABLED"] = "true"
    os.environ["BROWSER_AUTOMATION_ENABLED"] = "true"
    os.environ["EPISODIC_MEMORY_ENABLED"] = "true"

    # LLM Providers (use real keys if available)
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "sk-test-key-for-testing"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key-for-testing"


setup_test_environment()


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def db_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables, handling index already exists errors gracefully
    # Some models have duplicate index definitions that cause issues
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception as e:
        # If we get an index already exists error, try creating tables individually
        if "already exists" in str(e):
            # Create tables one by one to handle partial failures
            for table in Base.metadata.sorted_tables:
                try:
                    table.create(engine, checkfirst=True)
                except Exception as table_error:
                    # Only skip if it's an index error
                    if "already exists" not in str(table_error):
                        print(f"Warning: Could not create table {table.name}: {table_error}")
        else:
            raise

    yield engine

    # Clean up is automatic with in-memory database


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create database session for testing."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()


# =============================================================================
# E2E Docker Compose Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def e2e_docker_compose():
    """
    Start docker-compose for E2E tests.

    This fixture starts PostgreSQL and Redis services in Docker for the entire test session.
    Tests run on the host machine and connect to these services.
    """
    import subprocess
    from pathlib import Path

    compose_file = Path(__file__).parent.parent.parent / "docker-compose-e2e.yml"

    if not compose_file.exists():
        pytest.skip(f"Docker compose file not found: {compose_file}")

    print(f"\n=== Starting E2E Docker Environment ===")
    print(f"Compose file: {compose_file}")

    # Start docker-compose
    try:
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        print("Docker compose output:", result.stdout)
    except subprocess.TimeoutExpired:
        pytest.skip("Docker compose start timed out - Docker may not be running")
    except subprocess.CalledProcessError as e:
        pytest.skip(f"Failed to start docker-compose: {e.stderr}\nDocker may not be running")

    # Wait for services to be healthy
    print("Waiting for services to be ready...")
    max_wait = 30
    start_wait = time.time()

    while time.time() - start_wait < max_wait:
        try:
            # Check if PostgreSQL is ready
            result = subprocess.run(
                ["docker-compose", "-f", str(compose_file), "ps", "postgres-e2e"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if "healthy" in result.stdout or "Up" in result.stdout:
                print("PostgreSQL service is ready")
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        print("Warning: Services may not be fully ready, proceeding anyway")

    yield

    # Cleanup: Stop and remove containers, volumes
    print("\n=== Stopping E2E Docker Environment ===")
    try:
        subprocess.run(
            ["docker-compose", "-f", str(compose_file), "down", "-v"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        print("Docker compose stopped successfully")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to stop docker-compose: {e.stderr}")


@pytest.fixture(scope="function")
def e2e_postgres_db(e2e_docker_compose):
    """
    Create PostgreSQL connection for E2E tests.

    This fixture provides a real PostgreSQL database connection for E2E testing.
    Tables are created fresh for each test function.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # PostgreSQL connection string (connects to Docker container on localhost:5433)
    database_url = "postgresql://e2e_tester:test_password@localhost:5433/atom_e2e_test"

    print(f"\n=== Creating E2E PostgreSQL Connection ===")
    print(f"Database URL: {database_url}")

    # Create engine with connection pooling for tests
    engine = create_engine(
        database_url,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,
        max_overflow=10,
        echo=False,  # Set to True for SQL query debugging
    )

    # Create all tables
    print("Creating database tables...")
    try:
        Base.metadata.create_all(engine, checkfirst=True)
        print("Tables created successfully")
    except Exception as e:
        print(f"Warning: Some tables may have failed to create: {e}")

    # Create session
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()

    yield session

    # Cleanup
    print("\n=== Cleaning up E2E PostgreSQL Connection ===")
    session.close()
    engine.dispose()


@pytest.fixture(scope="function")
def mcp_service(e2e_postgres_db):
    """
    Initialize MCP service with test database.

    This fixture provides an MCP service instance configured for E2E testing.
    The service is initialized with test mode enabled for safer execution.
    """
    try:
        from integrations.mcp_service import MCPService
    except ImportError:
        pytest.skip("MCP service not available - integrations module not found")

    print("\n=== Initializing MCP Service ===")

    service = MCPService()
    service.test_mode = True  # Enable test mode for safer execution
    service.db_session = e2e_postgres_db

    yield service

    print("\n=== MCP Service cleanup ===")


@pytest.fixture(scope="function")
def e2e_redis(e2e_docker_compose):
    """
    Create Redis connection for E2E tests.

    This fixture provides a real Redis (Valkey) connection for WebSocket and pubsub testing.
    Database is flushed after each test for isolation.
    """
    try:
        import redis
    except ImportError:
        pytest.skip("Redis library not available - install with: pip install redis")

    print("\n=== Creating E2E Redis Connection ===")

    # Connect to Redis container on localhost:6380
    client = redis.Redis(
        host="localhost",
        port=6380,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
    )

    # Verify connection
    try:
        client.ping()
        print("Redis connection successful")
    except redis.ConnectionError as e:
        pytest.skip(f"Failed to connect to Redis: {e}")

    yield client

    # Cleanup: Flush all data and close connection
    print("\n=== Cleaning up E2E Redis Connection ===")
    try:
        client.flushall()  # Clear all keys for test isolation
        client.close()
    except Exception as e:
        print(f"Warning: Redis cleanup failed: {e}")


# =============================================================================
# FastAPI Test Client Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def test_app(db_session: Session) -> FastAPI:
    """Create FastAPI app with database override."""
    # For E2E tests, we don't need the full app - we test services directly
    # Return None to avoid import issues
    return None

    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def test_client(test_app):
    """Create test client for API testing."""
    if test_app is not None:
        return TestClient(test_app)
    return None


@pytest.fixture(scope="function")
async def async_client(test_app):
    """Create async HTTP client for testing."""
    if test_app is not None:
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            yield client
    else:
        yield None


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def test_user_token() -> str:
    """Create JWT token for test user."""
    secret = os.getenv("JWT_SECRET", "test-secret-key")
    payload = {
        "user_id": "test-user-123",
        "email": "test@example.com",
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


@pytest.fixture(scope="function")
def auth_headers(test_user_token: str) -> Dict[str, str]:
    """Create authentication headers for API requests."""
    return {"Authorization": f"Bearer {test_user_token}"}


# =============================================================================
# Agent Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def student_agent(db_session: Session) -> AgentRegistry:
    """Create STUDENT maturity level agent."""
    agent = AgentRegistry(
        id="student-agent-test",
        name="Test Student Agent",
        description="Student agent for E2E testing",
        category="Testing",
        module_path="test.student",
        class_name="StudentAgent",
        status="STUDENT",
        confidence_score=0.4,
        configuration={"capabilities": ["markdown", "charts"]},
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def intern_agent(db_session: Session) -> AgentRegistry:
    """Create INTERN maturity level agent."""
    agent = AgentRegistry(
        id="intern-agent-test",
        name="Test Intern Agent",
        description="Intern agent for E2E testing",
        category="Testing",
        module_path="test.intern",
        class_name="InternAgent",
        status="INTERN",
        confidence_score=0.6,
        configuration={"capabilities": ["markdown", "charts", "streaming", "forms"]},
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def supervised_agent(db_session: Session) -> AgentRegistry:
    """Create SUPERVISED maturity level agent."""
    agent = AgentRegistry(
        id="supervised-agent-test",
        name="Test Supervised Agent",
        description="Supervised agent for E2E testing",
        category="Testing",
        module_path="test.supervised",
        class_name="SupervisedAgent",
        status="SUPERVISED",
        confidence_score=0.8,
        configuration={
            "capabilities": [
                "markdown",
                "charts",
                "streaming",
                "forms",
                "browser_automation",
                "device_control",
            ]
        },
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def autonomous_agent(db_session: Session) -> AgentRegistry:
    """Create AUTONOMOUS maturity level agent."""
    agent = AgentRegistry(
        id="autonomous-agent-test",
        name="Test Autonomous Agent",
        description="Autonomous agent for E2E testing",
        category="Testing",
        module_path="test.autonomous",
        class_name="AutonomousAgent",
        status="AUTONOMOUS",
        confidence_score=0.95,
        configuration={"capabilities": ["all"]},
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def test_agents(
    student_agent: AgentRegistry,
    intern_agent: AgentRegistry,
    supervised_agent: AgentRegistry,
    autonomous_agent: AgentRegistry,
) -> Dict[str, AgentRegistry]:
    """Dictionary of all test agents by maturity level."""
    return {
        "STUDENT": student_agent,
        "INTERN": intern_agent,
        "SUPERVISED": supervised_agent,
        "AUTONOMOUS": autonomous_agent,
    }


# =============================================================================
# Service Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def governance_cache() -> GovernanceCache:
    """Create governance cache instance."""
    cache = GovernanceCache()
    cache._cache.clear()
    return cache


@pytest.fixture(scope="function")
def governance_service(db_session: Session, governance_cache: GovernanceCache) -> AgentGovernanceService:
    """Create agent governance service instance."""
    service = AgentGovernanceService(db_session)
    # Inject cache manually if needed
    service.cache = governance_cache
    return service


# =============================================================================
# WebSocket Fixtures
# =============================================================================

@pytest.fixture(scope="function")
async def websocket_client(test_app: FastAPI, test_user_token: str):
    """Create WebSocket client for testing."""
    from fastapi.testclient import TestClient
    import asyncio

    client = TestClient(test_app)

    class WebSocketTestClient:
        def __init__(self):
            self.client = client
            self.token = test_user_token
            self.connections = []

        async def connect(self, path: str):
            """Connect to WebSocket endpoint."""
            ws_url = f"{path}?token={self.token}"
            with self.client.websocket_connect(ws_url) as websocket:
                self.connections.append(websocket)
                return websocket

        async def send_json(self, websocket, data: dict):
            """Send JSON data to WebSocket."""
            await asyncio.sleep(0)  # Yield to event loop
            websocket.send_json(data)

        async def receive_json(self, websocket, timeout: float = 5.0):
            """Receive JSON data from WebSocket."""
            await asyncio.sleep(0)  # Yield to event loop
            return websocket.receive_json(timeout=timeout)

        def close_all(self):
            """Close all WebSocket connections."""
            for ws in self.connections:
                try:
                    ws.close()
                except Exception:
                    pass
            self.connections.clear()

    ws_client = WebSocketTestClient()
    yield ws_client
    ws_client.close_all()


# =============================================================================
# Performance Testing Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def performance_monitor():
    """Monitor and report performance metrics."""

    class PerformanceMonitor:
        def __init__(self):
            self.metrics = {}

        def start_timer(self, name: str):
            """Start timing an operation."""
            self.metrics[name] = {"start": time.perf_counter()}

        def stop_timer(self, name: str) -> float:
            """Stop timing and return duration in milliseconds."""
            if name in self.metrics:
                duration = (time.perf_counter() - self.metrics[name]["start"]) * 1000
                self.metrics[name]["duration_ms"] = duration
                return duration
            return 0.0

        def get_metric(self, name: str) -> Dict[str, Any]:
            """Get metric by name."""
            return self.metrics.get(name, {})

        def assert_under(self, name: str, max_ms: float):
            """Assert operation completed under threshold."""
            duration = self.get_metric(name).get("duration_ms", 0)
            assert duration < max_ms, f"{name} took {duration:.2f}ms, expected <{max_ms}ms"

        def print_summary(self):
            """Print performance summary."""
            print("\n=== Performance Summary ===")
            for name, data in self.metrics.items():
                if "duration_ms" in data:
                    print(f"{name}: {data['duration_ms']:.2f}ms")

    monitor = PerformanceMonitor()
    yield monitor
    monitor.print_summary()


# =============================================================================
# Test Data Factory Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def crm_contact_factory():
    """Create test CRM contact data."""
    import uuid

    def create_contact(**kwargs):
        defaults = {
            "first_name": "Test",
            "last_name": "User",
            "email": f"test.user.{uuid.uuid4()}@example.com",
            "phone": "+15551234567",
            "company": "Test Corp",
            "status": "lead",
            "source": "e2e_test",
        }
        defaults.update(kwargs)
        return defaults

    return create_contact


@pytest.fixture(scope="function")
def task_factory():
    """Create test task data."""
    import uuid

    def create_task(**kwargs):
        defaults = {
            "title": f"Test Task {uuid.uuid4()}",
            "description": "Test task description",
            "status": "todo",
            "priority": "medium",
            "assignee": "test-user",
            "due_date": None,
        }
        defaults.update(kwargs)
        return defaults

    return create_task


@pytest.fixture(scope="function")
def ticket_factory():
    """Create test support ticket data."""
    import uuid

    def create_ticket(**kwargs):
        defaults = {
            "subject": f"Test Issue {uuid.uuid4()}",
            "description": "Test ticket description",
            "priority": "normal",
            "status": "open",
            "customer_email": f"customer.{uuid.uuid4()}@example.com",
        }
        defaults.update(kwargs)
        return defaults

    return create_ticket


@pytest.fixture(scope="function")
def knowledge_doc_factory():
    """Create test knowledge document data."""
    import uuid

    def create_document(**kwargs):
        defaults = {
            "title": f"Test Doc {uuid.uuid4()}",
            "content": "Test knowledge content",
            "source": "e2e_test",
            "doc_type": "text",
            "tags": ["test", "e2e"],
        }
        defaults.update(kwargs)
        return defaults

    def create_business_fact(**kwargs):
        defaults = {
            "fact": "Test business fact",
            "citations": ["test/doc.pdf"],
            "reason": "For testing",
            "source": "e2e_test",
        }
        defaults.update(kwargs)
        return defaults

    return {"create_document": create_document, "create_business_fact": create_business_fact}


@pytest.fixture(scope="function")
def canvas_data_factory():
    """Create test canvas presentation data."""
    import uuid

    def create_chart_data(chart_type="line"):
        return {
            "type": chart_type,
            "title": f"Test Chart {uuid.uuid4()}",
            "data": {
                "labels": ["A", "B", "C", "D", "E"],
                "datasets": [
                    {
                        "label": "Dataset 1",
                        "data": [10, 20, 30, 40, 50],
                        "borderColor": "rgb(75, 192, 192)",
                    }
                ],
            },
        }

    def create_form_data():
        return {
            "type": "form",
            "title": f"Test Form {uuid.uuid4()}",
            "fields": [
                {"name": "email", "type": "email", "label": "Email", "required": True},
                {"name": "name", "type": "text", "label": "Full Name", "required": True},
                {"name": "consent", "type": "checkbox", "label": "I agree", "required": True},
            ],
        }

    return {"create_chart_data": create_chart_data, "create_form_data": create_form_data}


@pytest.fixture(scope="function")
def finance_data_factory():
    """Create test finance data."""
    import uuid

    def create_invoice(**kwargs):
        defaults = {
            "customer_id": f"cust_{uuid.uuid4().hex[:8]}",
            "amount": 100.00,
            "currency": "USD",
            "description": "Test invoice",
            "status": "pending",
            "due_date": None,
        }
        defaults.update(kwargs)
        return defaults

    return create_invoice


# =============================================================================
# Legacy Test Data Fixtures (kept for backward compatibility)
# =============================================================================

@pytest.fixture(scope="function")
def sample_chart_data() -> Dict[str, Any]:
    """Sample chart data for canvas presentations."""
    return {
        "type": "line",
        "title": "Test Performance Metrics",
        "data": {
            "labels": ["Jan", "Feb", "Mar", "Apr", "May"],
            "datasets": [
                {
                    "label": "Accuracy",
                    "data": [0.85, 0.87, 0.90, 0.92, 0.94],
                    "borderColor": "rgb(75, 192, 192)",
                }
            ],
        },
    }


@pytest.fixture(scope="function")
def sample_form_data() -> Dict[str, Any]:
    """Sample form data for canvas presentations."""
    return {
        "type": "form",
        "title": "User Registration",
        "fields": [
            {"name": "email", "type": "email", "label": "Email", "required": True},
            {"name": "name", "type": "text", "label": "Full Name", "required": True},
            {"name": "consent", "type": "checkbox", "label": "I agree to terms", "required": True},
        ],
    }


@pytest.fixture(scope="function")
def sample_episode_data() -> Dict[str, Any]:
    """Sample episode data for episodic memory testing."""
    return {
        "title": "Test Episode: Customer Support Query",
        "summary": "Agent resolved customer billing issue",
        "content": {
            "user_query": "Why was I charged $50?",
            "agent_response": "The charge was for the premium plan upgrade on Feb 1st.",
            "resolution": "Customer understood and accepted the explanation",
        },
        "agent_id": "test-agent-123",
        "episode_type": "customer_support",
        "tags": ["billing", "resolved", "premium"],
    }


# =============================================================================
# Cleanup Fixture
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_test_data(db_session: Session):
    """Automatically clean up test data after each test."""
    yield
    # Rollback any uncommitted changes
    db_session.rollback()


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "e2e: End-to-end scenario tests")
    config.addinivalue_line("markers", "slow: Tests that take >10 seconds")
    config.addinivalue_line("markers", "integration: Tests requiring external services")


# =============================================================================
# Skip Conditions
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """Skip tests based on conditions."""
    skip_slow = pytest.mark.skip(reason="Skipping slow tests in CI")
    skip_requires_api_keys = pytest.mark.skip(reason="No API keys provided")

    for item in items:
        # Skip slow tests if --skip-slow is provided
        if config.getoption("--skip-slow", default=False):
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

        # Skip tests requiring API keys if not provided
        if "requires_api_keys" in item.keywords:
            if not os.environ.get("OPENAI_API_KEY") or os.environ.get(
                "OPENAI_API_KEY"
            ).startswith("sk-test"):
                item.add_marker(skip_requires_api_keys)
