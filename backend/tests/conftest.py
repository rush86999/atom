"""
Root conftest.py for test suite configuration

This file is loaded before any test modules and sets up necessary fixtures
and configuration for the entire test suite.
"""

import sys
import os
import uuid
import pytest
import ast
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import AsyncIterator
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import fixture modules for availability in tests (avoid circular imports)
# Note: Some fixture modules contain placeholder implementations
# TODO: Implement actual models in workflow_fixtures.py and episode_fixtures.py

# from tests.fixtures.agent_fixtures import (
#     create_test_agent, create_student_agent, create_intern_agent,
#     create_supervised_agent, create_autonomous_agent, create_agent_batch
# )
# from tests.fixtures.workflow_fixtures import (
#     create_test_workflow, create_workflow_execution,
#     create_workflow_step, create_workflow_with_steps
# )
# from tests.fixtures.episode_fixtures import (
#     create_test_episode, create_episode_segment,
#     create_episode_with_segments, create_intervention_episode, create_episode_batch
# )
# from tests.fixtures.api_fixtures import (
#     create_chat_request, create_canvas_request, create_workflow_request,
#     create_agent_response, create_canvas_response, create_error_response, MockTestClient
# )
from tests.fixtures.mock_services import (
    MockLLMProvider, MockEmbeddingService, MockStorageService,
    MockCacheService, MockWebSocket
)


# Critical environment variables to isolate between tests
_CRITICAL_ENV_VARS = [
    'SECRET_KEY', 'ENVIRONMENT', 'DATABASE_URL', 'ALLOW_DEV_TEMP_USERS',
    'BYOK_CONFIG_FILE', 'BYOK_KEYS_FILE', 'BYOK_ENCRYPTION_KEY'
]


# CRITICAL: This code runs when conftest.py is first imported by pytest.
# It restores numpy/pandas/lancedb/pyarrow modules that may have been
# set to None or mocked as MagicMock by previously imported test modules
# (like test_webhook_bridge.py and test_browser_agent_ai.py).
#
# This must happen at module level, not in a function, to ensure it runs
# before test collection begins.
#
# Hypothesis's check_sample() fails with TypeError: isinstance() arg 2 must be a type
# when these modules are mocked, because MagicMock().ndarray is also a MagicMock, not a type.
for mod in ["numpy", "pandas", "lancedb", "pyarrow"]:
    if mod in sys.modules:
        module = sys.modules[mod]
        # Remove if set to None OR mocked as MagicMock
        # MagicMock has _spec_class attribute that real modules don't have
        if module is None or hasattr(module, '_spec_class'):
            sys.modules.pop(mod, None)


def pytest_configure(config):
    """
    Pytest hook called after command line options have been parsed.
    Configures pytest-xdist worker isolation.
    """
    # Set unique worker ID for parallel execution
    if hasattr(config, 'workerinput'):
        # Running in pytest-xdist worker
        worker_id = config.workerinput.get('workerid', 'master')
        os.environ['PYTEST_XDIST_WORKER_ID'] = worker_id


@pytest.fixture(autouse=True)
def ensure_numpy_available(request):
    """
    Auto-use fixture that ensures numpy/pandas/lancedb/pyarrow are available
    before each test runs.

    This is a safety net in case any test sets these to None or mocks them as MagicMock.
    """
    # Restore modules before each test
    for mod in ["numpy", "pandas", "lancedb", "pyarrow"]:
        if mod in sys.modules:
            module = sys.modules[mod]
            # Remove if set to None OR mocked as MagicMock
            # MagicMock has _spec_class attribute that real modules don't have
            if module is None or hasattr(module, '_spec_class'):
                sys.modules.pop(mod, None)

    yield

    # No cleanup needed


@pytest.fixture(autouse=True)
def isolate_environment():
    """
    Isolate environment variables between tests.

    Prevents test pollution from environment modifications by saving and restoring
    critical environment variables (SECRET_KEY, ENVIRONMENT, DATABASE_URL, etc.)
    before and after each test.
    """
    # Save critical env vars
    saved = {}
    for var in _CRITICAL_ENV_VARS:
        if var in os.environ:
            saved[var] = os.environ[var]

    yield

    # Restore saved env vars, delete ones that weren't set before
    for var in _CRITICAL_ENV_VARS:
        if var in saved:
            os.environ[var] = saved[var]
        else:
            os.environ.pop(var, None)


@pytest.fixture(scope="session", autouse=True)
def setup_byok_test_env():
    """
    Setup temporary environment for BYOK tests to prevent data pollution.
    Runs once per test session.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "byok_config.json")
        keys_path = os.path.join(tmp_dir, "byok_keys.json")
        
        # Set environment variables for the session
        os.environ['BYOK_CONFIG_FILE'] = config_path
        os.environ['BYOK_KEYS_FILE'] = keys_path
        # Use a stable but test-specific encryption key
        os.environ['BYOK_ENCRYPTION_KEY'] = "test-encryption-key-must-be-32-chars-long-!"[:32]
        
        # Initialize empty files
        with open(config_path, 'w') as f:
            json.dump({"providers": []}, f)
        with open(keys_path, 'w') as f:
            json.dump({"keys": {}}, f)
            
        yield
        
        # Env vars will be popped/restored by isolate_environment fixture if it was used,
        # but setup_byok_test_env is session-scoped, so it sets them for everyone.


@pytest.fixture(autouse=True)
def reset_agent_task_registry(request):
    """
    Reset agent task registry before each test for isolation.

    This prevents task ID collisions between tests by ensuring each test
    starts with a clean registry state. The AgentTaskRegistry is a singleton
    that persists across test runs, so we need to explicitly reset it.

    This is an autouse fixture, so it runs automatically before every test
    without requiring explicit reference in test signatures.
    """
    from core.agent_task_registry import agent_task_registry
    agent_task_registry._reset()
    yield
    # No cleanup needed - each test gets fresh state at start


@pytest.fixture(scope="function")
def unique_resource_name():
    """
    Generate a unique resource name for parallel test execution.
    Combines worker ID with UUID to ensure no collisions.

    Usage example:
        def test_file_operations(unique_resource_name):
            filename = f"{unique_resource_name}.txt"
            # No collision with parallel tests
    """
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    unique_id = str(uuid.uuid4())[:8]
    return f"test_{worker_id}_{unique_id}"


@pytest.fixture(scope="function")
def db_session():
    """
    Standardized database session fixture for all tests.

    Creates a fresh in-memory SQLite database for each test function.
    This fixture is function-scoped to ensure complete test isolation.

    Uses tempfile-based SQLite file for better compatibility with
    SQLAlchemy multiprocessing and LanceDB integration tests.

    Usage:
        def test_my_feature(db_session):
            agent = AgentRegistry(name="test", ...)
            db_session.add(agent)
            db_session.commit()
    """
    # Import here to avoid circular imports
    from core.database import Base

    # Use file-based temp SQLite for tests (more stable than :memory:)
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create tables using create_all with checkfirst
    # This handles missing foreign key references gracefully
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception:
        # If create_all fails, create tables individually
        for table in Base.metadata.tables.values():
            try:
                table.create(engine, checkfirst=True)
            except Exception:
                # Skip tables that can't be created (missing FK refs, etc.)
                continue

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    # Delete temp database file
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass


@pytest.fixture(scope="function")
def test_agent_student(db_session: Session):
    """Create a STUDENT maturity test agent (confidence < 0.5).

    STUDENT agents cannot execute automated triggers and require
    human supervision for all actions.

    Usage:
        def test_student_blocked_from_deletes(test_agent_student):
            with pytest.raises(PermissionError):
                execute_delete_action(test_agent_student)
    """
    from core.models import AgentRegistry, AgentStatus

    agent = AgentRegistry(
        name="StudentAgent",
        category="test",
        module_path="test.module",
        class_name="TestStudent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3,  # Below STUDENT threshold
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def test_agent_intern(db_session: Session):
    """Create an INTERN maturity test agent (0.5-0.7 confidence).

    INTERN agents can execute triggers but require human approval
    for actions before execution.

    Usage:
        def test_intern_requires_approval(test_agent_intern):
            result = execute_action(test_agent_intern)
            assert result.requires_approval is True
    """
    from core.models import AgentRegistry, AgentStatus

    agent = AgentRegistry(
        name="InternAgent",
        category="test",
        module_path="test.module",
        class_name="TestIntern",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,  # INTERN range
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def test_agent_supervised(db_session: Session):
    """Create a SUPERVISED maturity test agent (0.7-0.9 confidence).

    SUPERVISED agents can execute actions under real-time monitoring
    with human intervention capability.

    Usage:
        def test_supervised_execution(test_agent_supervised):
            result = execute_action(test_agent_supervised)
            assert result.executed is True
            assert result.monitored is True
    """
    from core.models import AgentRegistry, AgentStatus

    agent = AgentRegistry(
        name="SupervisedAgent",
        category="test",
        module_path="test.module",
        class_name="TestSupervised",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.8,  # SUPERVISED range
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def test_agent_autonomous(db_session: Session):
    """Create an AUTONOMOUS maturity test agent (>0.9 confidence).

    AUTONOMOUS agents have full execution privileges without oversight
    and can perform all actions including deletions.

    Usage:
        def test_autonomous_full_access(test_agent_autonomous):
            result = execute_delete_action(test_agent_autonomous)
            assert result.success is True
    """
    from core.models import AgentRegistry, AgentStatus

    agent = AgentRegistry(
        name="AutonomousAgent",
        category="test",
        module_path="test.module",
        class_name="TestAutonomous",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,  # AUTONOMOUS range
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def mock_llm_response():
    """Provide deterministic mock LLM responses for testing.

    Yields a mock object that returns predictable responses for:
    - Single completions: mock_llm_response.complete(prompt) -> "Mock response"
    - Streaming: mock_llm_response.stream(prompt) -> ["Mock", " response"]
    - Errors: mock_llm_response.set_error_mode(rate_limited|timeout)

    This fixture eliminates dependency on real LLM APIs and provides
    deterministic outputs for test repeatability.

    Usage:
        def test_agent_response(mock_llm_response):
            response = mock_llm_response.complete("test")
            assert response == "Mock response 1 for: test"

        def test_llm_errors(mock_llm_response):
            mock_llm_response.set_error_mode("rate_limited")
            with pytest.raises(Exception, match="Rate limit"):
                mock_llm_response.complete("test")
    """
    from unittest.mock import MagicMock
    import asyncio
    from typing import AsyncIterator

    class MockLLMResponse:
        def __init__(self):
            self._error_mode = None
            self._response_count = 0

        def complete(self, prompt: str, **kwargs) -> str:
            """Return deterministic mock response."""
            self._response_count += 1
            if self._error_mode == "rate_limited":
                raise Exception("Rate limit exceeded")
            elif self._error_mode == "timeout":
                raise asyncio.TimeoutError("LLM timeout")
            return f"Mock response {self._response_count} for: {prompt[:50]}"

        async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
            """Return deterministic mock streaming response."""
            self._response_count += 1
            response = f"Mock streaming response {self._response_count}"
            for char in response:
                if self._error_mode:
                    if self._error_mode == "rate_limited":
                        raise Exception("Rate limit exceeded")
                    elif self._error_mode == "timeout":
                        raise asyncio.TimeoutError("LLM timeout")
                yield char
                await asyncio.sleep(0.001)  # Simulate network delay

        def set_error_mode(self, mode: str):
            """Set error mode for testing failure scenarios.

            Args:
                mode: One of "rate_limited", "timeout", or None (no errors)
            """
            self._error_mode = mode

        def reset(self):
            """Reset error mode and response count."""
            self._error_mode = None
            self._response_count = 0

    mock = MockLLMResponse()
    yield mock
    # Cleanup
    mock.reset()


@pytest.fixture(scope="function")
def mock_embedding_vectors():
    """Provide deterministic mock embedding vectors for similarity testing.

    Yields a mock object that returns:
    - Deterministic vectors: same input always produces same vector
    - Known similarity scores: predefined cosine similarities
    - Dimension handling: supports 384-dim (FastEmbed) and 1536-dim (OpenAI)

    This fixture eliminates dependency on real embedding models and provides
    deterministic vectors for testing similarity search and retrieval logic.

    Usage:
        def test_similarity_search(mock_embedding_vectors):
            vec1 = mock_embedding_vectors.embed("query")
            vec2 = mock_embedding_vectors.embed("query")  # Same!
            assert vec1 == vec2

        def test_known_similarities(mock_embedding_vectors):
            similarity = mock_embedding_vectors.get_similarity("exact", "exact")
            assert similarity == 1.0
    """
    import hashlib
    import numpy as np

    class MockEmbeddingVectors:
        def __init__(self):
            self._dimension = 384  # Default FastEmbed dimension
            self._known_similarities = {
                ("exact", "exact"): 1.0,
                ("similar", "similar"): 0.9,
                ("related", "related"): 0.7,
                ("unrelated", "unrelated"): 0.1,
            }

        def set_dimension(self, dim: int):
            """Set embedding dimension (384 for FastEmbed, 1536 for OpenAI)."""
            self._dimension = dim

        def embed(self, text: str) -> list[float]:
            """Generate deterministic embedding vector from text.

            Uses hash of text to generate consistent values.
            """
            # Create hash of text for determinism
            hash_obj = hashlib.sha256(text.encode())
            hash_bytes = hash_obj.digest()

            # Convert to floats in [-1, 1] range
            values = []
            for i in range(self._dimension):
                byte_idx = i % len(hash_bytes)
                byte_val = hash_bytes[byte_idx]
                # Convert byte to float in [-1, 1]
                float_val = (byte_val - 128) / 128.0
                values.append(float_val)

            return values

        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            """Generate embeddings for multiple texts."""
            return [self.embed(text) for text in texts]

        def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
            """Calculate cosine similarity between two vectors."""
            import math
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            mag1 = math.sqrt(sum(a * a for a in vec1))
            mag2 = math.sqrt(sum(b * b for b in vec2))
            if mag1 == 0 or mag2 == 0:
                return 0.0
            return dot_product / (mag1 * mag2)

        def get_similarity(self, text1: str, text2: str) -> float:
            """Get similarity score using known table or computed cosine."""
            # Check known similarities first
            key = tuple(sorted([text1.lower(), text2.lower()]))
            for known_pair, score in self._known_similarities.items():
                if set(known_pair) == set([text1.lower(), text2.lower()]):
                    return score
            # Fall back to computed cosine similarity
            return self.cosine_similarity(self.embed(text1), self.embed(text2))

    mock = MockEmbeddingVectors()
    yield mock


@pytest.fixture(scope="function")
def test_user(db_session: Session):
    """Create a test user with authentication token.

    Usage:
        def test_authenticated_request(test_user):
            user, token = test_user
            headers = {"Authorization": f"Bearer {token}"}
    """
    from core.models import User
    import secrets

    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashed_password_here",
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Generate test token
    token = secrets.token_urlsafe(32)
    return user, token


@pytest.fixture(scope="function")
def admin_user(db_session: Session):
    """Create an admin user with elevated permissions.

    Usage:
        def test_admin_action(admin_user):
            user, token = admin_user
            # User has admin privileges
    """
    from core.models import User
    import secrets

    user = User(
        email="admin@example.com",
        username="admin",
        hashed_password="hashed_password_here",
        is_active=True,
        is_superuser=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Generate test token
    token = secrets.token_urlsafe(32)
    return user, token


@pytest.fixture(scope="function")
def test_token():
    """Generate a test authentication token.

    Usage:
        def test_with_token(test_token):
            headers = {"Authorization": f"Bearer {test_token}"}
    """
    import secrets
    return secrets.token_urlsafe(32)


@pytest.fixture(scope="function")
def temp_directory():
    """Create a temporary directory for file operations.

    Automatically cleaned up after test.

    Usage:
        def test_file_operations(temp_directory):
            filepath = os.path.join(temp_directory, "test.txt")
            with open(filepath, 'w') as f:
                f.write("test")
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir
    # Cleanup is automatic


@pytest.fixture(scope="function")
def frozen_time():
    """Freeze time for deterministic testing.

    Uses freezegun if available, otherwise mock.

    Usage:
        def test_time_dependent_logic(frozen_time):
            # datetime.now() always returns the frozen time
            assert datetime.now().isoformat() == "2024-01-01T00:00:00"

        with frozen_time.move_to("2024-02-01"):
            # Time moved to Feb 1
            pass
    """
    try:
        from freezegun import freeze_time

        # Freeze to a fixed timestamp
        frozen_datetime = datetime(2024, 1, 1, 0, 0, 0)
        with freeze_time(frozen_datetime) as frozen_time_ctx:
            yield frozen_time_ctx
    except ImportError:
        # Fallback: just return current time (not frozen, but functional)
        class MockFrozenTime:
            def __init__(self):
                self._current_time = datetime(2024, 1, 1, 0, 0, 0)

            def move_to(self, new_time):
                """Move to a new time."""
                if isinstance(new_time, str):
                    # Parse ISO string
                    new_time = datetime.fromisoformat(new_time)
                self._current_time = new_time
                return self

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        yield MockFrozenTime()


@pytest.fixture(scope="function")
def current_time():
    """Get current test time for consistent timestamps.

    Returns a fixed datetime for reproducible tests.

    Usage:
        def test_timestamps(current_time):
            created_at = current_time
            updated_at = current_time + timedelta(hours=1)
    """
    return datetime(2024, 1, 1, 0, 0, 0)


@pytest.fixture(scope="session")
def mock_llm_service():
    """Session-scoped mock LLM service for all tests.

    Reduces fixture creation overhead.

    Usage:
        def test_llm_integration(mock_llm_service):
            response = mock_llm_service.complete("test")
            assert "Mock LLM response" in response
    """
    service = MockLLMProvider()
    yield service
    service.reset()


@pytest.fixture(scope="session")
def mock_cache_service():
    """Session-scoped mock cache service for all tests.

    Usage:
        def test_caching(mock_cache_service):
            mock_cache_service.set("key", "value")
            assert mock_cache_service.get("key") == "value"
    """
    service = MockCacheService()
    yield service
    service.clear()


@pytest.fixture(scope="function")
def mock_storage_service():
    """Function-scoped mock storage service (cleaned per test).

    Usage:
        def test_file_upload(mock_storage_service):
            url = mock_storage_service.store("file.txt", b"data")
            assert "mock-storage" in url
    """
    service = MockStorageService()
    yield service
    service.reset()


@pytest.fixture(scope="function")
def test_client():
    """Create a test API client.

    Requires FastAPI app to be importable.

    Usage:
        def test_api_endpoint(test_client):
            response = test_client.get("/api/health")
            assert response.status_code == 200
    """
    try:
        from fastapi.testclient import TestClient
        # Try to import the app
        try:
            from main import app
        except ImportError:
            # Fallback to creating a mock app
            from fastapi import FastAPI
            app = FastAPI()

        client = TestClient(app)
        yield client
    except Exception:
        # If FastAPI is not available, use our mock
        yield MockTestClient()


@pytest.fixture(scope="function")
def mock_requests():
    """Mock HTTP requests for external API calls.

    Uses responses library if available, otherwise provides simple mock.

    Usage:
        def test_external_api(mock_requests):
            mock_requests.add("GET", "https://api.example.com/test",
                             body={"status": "ok"})
            # Make HTTP call, it will be mocked
    """
    try:
        import responses
        with responses.RequestsMock() as rsps:
            yield rsps
    except ImportError:
        # Fallback mock
        class MockRequests:
            def __init__(self):
                self._calls = []

            def add(self, method, url, body=None, status=200):
                """Add a mock response."""
                self._calls.append({"method": method, "url": url, "body": body, "status": status})

            def verify(self):
                """Verify all mocks were called."""
                # Simple implementation
                pass

        yield MockRequests()


@pytest.fixture(scope="function")
def clean_db(db_session: Session):
    """Provide a completely empty database.

    Deletes all data before test. Useful for tests that need clean state.

    Usage:
        def test_with_clean_db(clean_db):
            # Database is guaranteed to be empty
            agent = AgentRegistry(name="test")
            db_session.add(agent)
            db_session.commit()
    """
    from core.database import Base

    # Delete all data
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()

    yield db_session


@pytest.fixture(scope="function")
def sample_agent(db_session: Session):
    """Pre-created sample agent for quick testing.

    Usage:
        def test_quick_check(sample_agent):
            assert sample_agent.name == "SampleAgent"
    """
    from core.models import AgentRegistry, AgentStatus

    agent = AgentRegistry(
        name="SampleAgent",
        category="testing",
        module_path="test.module",
        class_name="SampleClass",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        description="A sample test agent",
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def sample_workflow(db_session: Session):
    """Pre-created sample workflow for quick testing.

    Usage:
        def test_workflow_execution(sample_workflow):
            assert sample_workflow.name == "SampleWorkflow"
    """
    from core.models import WorkflowDefinition

    workflow = WorkflowDefinition(
        name="SampleWorkflow",
        description="A sample test workflow",
        status="active",
        version=1,
        definition={"steps": [{"name": "step1", "action": "test"}]},
        created_by="test_user",
        created_at=datetime.utcnow()
    )
    db_session.add(workflow)
    db_session.commit()
    db_session.refresh(workflow)
    return workflow


@pytest.fixture(scope="function")
def sample_episode(db_session: Session):
    """Pre-created sample episode for quick testing.

    Usage:
        def test_episode_retrieval(sample_episode):
            assert sample_episode.title == "Sample Episode"
    """
    from core.models import Episode

    now = datetime.utcnow()
    episode = Episode(
        agent_id="sample_agent",
        title="Sample Episode",
        summary="A sample test episode",
        start_time=now - timedelta(hours=1),
        end_time=now,
        maturity_level="INTERN",
        intervention_count=0,
        created_at=now
    )
    db_session.add(episode)
    db_session.commit()
    db_session.refresh(episode)
    return episode


@pytest.fixture(scope="function")
def async_client():
    """Create an async test client for FastAPI.

    Usage:
        @pytest.mark.asyncio
        async def test_async_endpoint(async_client):
            response = await async_client.get("/api/async-endpoint")
            assert response.status_code == 200
    """
    import asyncio
    try:
        from httpx import AsyncClient
        try:
            from main import app
        except ImportError:
            from fastapi import FastAPI
            app = FastAPI()

        # Create async client using a helper coroutine
        async def get_client():
            async with AsyncClient(app=app, base_url="http://test") as client:
                yield client

        # Run the async generator
        loop = asyncio.get_event_loop()
        gen = get_client()
        client = loop.run_until_complete(gen.__anext__())
        yield client
        try:
            loop.run_until_complete(gen.__anext__())
        except StopAsyncIteration:
            pass
    except Exception:
        # Fallback: return None (test should skip if async is needed)
        yield None


@pytest.fixture(scope="function")
def test_database():
    """Create a test database with all tables.

    Alternative to db_session that creates the DB but not the session.

    Usage:
        def test_with_db(test_database):
            engine, SessionLocal = test_database
            session = SessionLocal()
            # Use session
    """
    from core.database import Base

    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )
    engine._test_db_path = db_path

    # Create all tables
    Base.metadata.create_all(engine, checkfirst=True)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield engine, SessionLocal

    # Cleanup
    engine.dispose()
    try:
        os.unlink(engine._test_db_path)
    except Exception:
        pass


@pytest.fixture(scope="function")
def mock_lancedb_client(monkeypatch):
    """Mock LanceDB client for CI environments.

    Returns an in-memory LanceDB mock that simulates table operations
    without requiring the external LanceDB service. This enables
    LanceDB integration tests to run in CI without service containers.

    Usage:
        def test_episode_storage(mock_lancedb_client):
            # Create mock table
            table = mock_lancedb_client.create_table("test_table")
            table.add([{"id": "1", "vector": [1.0, 2.0]}])
    """
    import os

    # Check if LanceDB is disabled (CI environment)
    if os.getenv("ATOM_DISABLE_LANCEDB", "false").lower() == "true":
        # Use in-memory mock
        class MockLanceDBTable:
            def __init__(self, name, schema=None):
                self.name = name
                self.schema = schema
                self._data = []
                self._index = {}

            def create_index(self, *args, **kwargs):
                """Mock index creation."""
                self._index["created"] = True

            def add(self, data):
                """Mock add operation."""
                if isinstance(data, list):
                    self._data.extend(data)
                else:
                    self._data.append(data)

            def search(self, query, *args, **kwargs):
                """Mock search operation - returns all data."""
                return self._data

            def to_arrow(self):
                """Mock to_arrow conversion."""
                import pyarrow as pa
                import pyarrow.table as pat
                # Return empty table if no data
                if not self._data:
                    return pa.table({})
                # Convert list of dicts to Arrow table
                return pa.table(self._data)

            def delete(self, where=None):
                """Mock delete operation."""
                if where:
                    # Simple mock delete - clear all data
                    self._data.clear()

            def length(self):
                """Return number of records."""
                return len(self._data)

        class MockLanceDBClient:
            def __init__(self, uri=None):
                self.uri = uri
                self._tables = {}

            def create_table(self, name, schema=None, mode="overwrite"):
                """Create or get a mock table."""
                if name not in self._tables or mode == "overwrite":
                    self._tables[name] = MockLanceDBTable(name, schema)
                return self._tables[name]

            def open_table(self, name):
                """Open existing table or create new."""
                if name not in self._tables:
                    self._tables[name] = MockLanceDBTable(name)
                return self._tables[name]

            def table_names(self):
                """Return list of table names."""
                return list(self._tables.keys())

        # Mock lancedb.connect
        def mock_connect(uri=None, *args, **kwargs):
            return MockLanceDBClient(uri)

        monkeypatch.setattr("lancedb.connect", mock_connect)

        yield MockLanceDBClient()
    else:
        # LanceDB not disabled - use real client (tests should skip if service unavailable)
        try:
            import lancedb
            # Try to connect - will fail if service not available
            client = lancedb.connect(os.getenv("LANCEDB_URI", "/tmp/lancedb"))
            yield client
        except Exception:
            # Service unavailable - yield None, tests should skip
            yield None


@pytest.fixture(scope="function")
def mock_knowledge_graph():
    """Mock Knowledge Graph validation service for governance exams.

    Returns mock constitutional rule validation results without requiring
    the external Knowledge Graph service. This enables governance exam
    tests to run in CI without the Knowledge Graph dependency.

    Usage:
        def test_governance_exam(mock_knowledge_graph):
            result = mock_knowledge_graph.validate_compliance(
                agent_id="test",
                rules=["constitutional_rule_1"]
            )
            assert result["passed"] is True
            assert result["score"] >= 0.95
    """
    class MockKnowledgeGraph:
        def __init__(self):
            self._constitutional_rules = {
                "rule_001": {
                    "id": "rule_001",
                    "name": "Human Oversight Required",
                    "category": "safety",
                    "description": "Agents must require human approval for destructive actions"
                },
                "rule_002": {
                    "id": "rule_002",
                    "name": "Data Privacy Protection",
                    "category": "privacy",
                    "description": "Agents must protect user data and comply with GDPR"
                },
                "rule_003": {
                    "id": "rule_003",
                    "name": "Transparent Decision Making",
                    "category": "transparency",
                    "description": "Agents must explain their reasoning for all actions"
                }
            }

        def get_constitutional_rules(self, category=None):
            """Get constitutional rules, optionally filtered by category."""
            rules = list(self._constitutional_rules.values())
            if category:
                rules = [r for r in rules if r["category"] == category]
            return rules

        def validate_compliance(self, agent_id, rules=None, actions=None):
            """Validate agent compliance against constitutional rules.

            Returns mock compliance result with high score (0.95-0.99).
            """
            import random

            selected_rules = rules or list(self._constitutional_rules.keys())

            # Mock validation - most agents pass
            passed_scores = {
                "student": 0.65,  # Student agents need more training
                "intern": 0.82,   # Intern agents mostly compliant
                "supervised": 0.92,  # Supervised agents highly compliant
                "autonomous": 0.98  # Autonomous agents fully compliant
            }

            # Determine maturity from agent_id if present
            maturity = "autonomous"  # Default
            for level in ["student", "intern", "supervised", "autonomous"]:
                if level in agent_id.lower():
                    maturity = level
                    break

            base_score = passed_scores.get(maturity, 0.90)
            # Add small random variation (0.95-0.99 range for autonomous)
            score = min(0.99, base_score + random.uniform(0.0, 0.05))

            return {
                "agent_id": agent_id,
                "passed": score >= 0.90,
                "score": score,
                "rules_evaluated": len(selected_rules),
                "rules_passed": int(len(selected_rules) * score),
                "interventions": max(0, len(selected_rules) - int(len(selected_rules) * score)),
                "timestamp": datetime.utcnow().isoformat()
            }

        def check_rule_violations(self, agent_action, rule_id):
            """Check if an action violates a specific rule.

            Returns violation details or None if compliant.
            """
            # Most actions are compliant in mock
            import random

            if random.random() > 0.1:  # 90% of actions are compliant
                return None

            return {
                "rule_id": rule_id,
                "action": agent_action,
                "violation_type": "constitutional_breach",
                "severity": "high" if "delete" in agent_action else "medium",
                "description": f"Action '{agent_action}' may violate rule {rule_id}",
                "timestamp": datetime.utcnow().isoformat()
            }

    mock_kg = MockKnowledgeGraph()
    yield mock_kg


@pytest.fixture(scope="function")
def mock_prometheus_client(monkeypatch):
    """Mock Prometheus client for analytics tests.

    Returns mock Prometheus metrics (Gauge, Counter, Histogram) that
    track metric calls in memory without requiring the Prometheus server.
    This enables analytics tests to run in CI without external dependencies.

    Usage:
        def test_metric_tracking(mock_prometheus_client):
            gauge = mock_prometheus_client.Gauge("test_gauge", "Test gauge")
            gauge.set(42)
            assert mock_prometheus_client.get_metric_value("test_gauge") == 42
    """
    class MockMetric:
        def __init__(self, name, metric_type, documentation):
            self.name = name
            self.metric_type = metric_type
            self.documentation = documentation
            self._value = 0
            self._labels = {}
            self._samples = []

        def set(self, value):
            """Set gauge value."""
            self._value = value
            self._samples.append((datetime.utcnow(), value))

        def inc(self, amount=1):
            """Increment counter."""
            self._value += amount
            self._samples.append((datetime.utcnow(), self._value))

        def dec(self, amount=1):
            """Decrement gauge."""
            self._value -= amount
            self._samples.append((datetime.utcnow(), self._value))

        def observe(self, amount):
            """Observe histogram value."""
            self._value += amount
            self._samples.append((datetime.utcnow(), amount))

        def labels(self, **kwargs):
            """Return self with labels set."""
            self._labels = kwargs
            return self

        def get_value(self):
            """Get current metric value."""
            return self._value

        def get_samples(self):
            """Get all recorded samples."""
            return self._samples

    class MockPrometheusRegistry:
        def __init__(self):
            self._metrics = {}

        def Gauge(self, name, documentation, labelnames=()):
            """Create mock Gauge metric."""
            if name not in self._metrics:
                self._metrics[name] = MockMetric(name, "gauge", documentation)
            return self._metrics[name]

        def Counter(self, name, documentation, labelnames=()):
            """Create mock Counter metric."""
            if name not in self._metrics:
                self._metrics[name] = MockMetric(name, "counter", documentation)
            return self._metrics[name]

        def Histogram(self, name, documentation, labelnames=(), buckets=None):
            """Create mock Histogram metric."""
            if name not in self._metrics:
                self._metrics[name] = MockMetric(name, "histogram", documentation)
            return self._metrics[name]

        def get_metric_value(self, name):
            """Get current value of a metric."""
            if name in self._metrics:
                return self._metrics[name].get_value()
            return None

        def get_all_metrics(self):
            """Get all registered metrics."""
            return self._metrics

        def get_metric_samples(self, name):
            """Get all samples for a metric."""
            if name in self._metrics:
                return self._metrics[name].get_samples()
            return []

    class MockPrometheusClient:
        def __init__(self):
            self.registry = MockPrometheusRegistry()
            self._metrics = {}

        def Gauge(self, name, documentation, labelnames=()):
            """Create or get Gauge metric."""
            return self.registry.Gauge(name, documentation, labelnames)

        def Counter(self, name, documentation, labelnames=()):
            """Create or get Counter metric."""
            return self.registry.Counter(name, documentation, labelnames)

        def Histogram(self, name, documentation, labelnames=(), buckets=None):
            """Create or get Histogram metric."""
            return self.registry.Histogram(name, documentation, labelnames, buckets)

        def start_http_server(self, port, *args, **kwargs):
            """Mock HTTP server start - skip port binding."""
            pass  # Don't actually start server in tests

        def get_metric_value(self, name):
            """Get current metric value."""
            return self.registry.get_metric_value(name)

        def get_all_metrics(self):
            """Get all metrics."""
            return self.registry.get_all_metrics()

    mock_client = MockPrometheusClient()

    # Mock prometheus_client module
    mock_prometheus = MagicMock()
    mock_prometheus.Gauge = mock_client.Gauge
    mock_prometheus.Counter = mock_client.Counter
    mock_prometheus.Histogram = mock_client.Histogram
    mock_prometheus.start_http_server = mock_client.start_http_server
    mock_prometheus.Counter = mock_client.Counter
    mock_prometheus.Gauge = mock_client.Gauge
    mock_prometheus.Histogram = mock_client.Histogram

    # Mock start_http_server at module level
    monkeypatch.setattr("prometheus_client.start_http_server", mock_client.start_http_server, raising=False)
    monkeypatch.setattr("prometheus_client.Gauge", lambda *args, **kwargs: mock_client.Gauge(*args, **kwargs), raising=False)
    monkeypatch.setattr("prometheus_client.Counter", lambda *args, **kwargs: mock_client.Counter(*args, **kwargs), raising=False)
    monkeypatch.setattr("prometheus_client.Histogram", lambda *args, **kwargs: mock_client.Histogram(*args, **kwargs), raising=False)

    yield mock_client


@pytest.fixture(scope="function")
def mock_grafana_client():
    """Mock Grafana client for dashboard tests.

    Returns mock Grafana API responses for dashboard updates without
    requiring the Grafana server. This enables dashboard tests to run
    in CI without external dependencies.

    Usage:
        def test_dashboard_update(mock_grafana_client):
            mock_grafana_client.add_response(
                "POST",
                "/api/dashboards/db",
                status=200,
                json={"id": 123, "uid": "abc123", "url": "http://grafana/d/abc123"}
            )
            # Make API call - will be mocked
    """
    try:
        import responses

        class MockGrafanaClient:
            def __init__(self):
                self._responses = responses.RequestsMock()
                self._responses.start()
                self._default_dashboard = {
                    "dashboard": {
                        "id": 1,
                        "title": "Test Dashboard",
                        "panels": []
                    },
                    "overwrite": False
                }

            def add_response(self, method, url, status=200, json=None):
                """Add a mock Grafana API response."""
                self._responses.add(
                    method=getattr(responses, method.upper()),
                    url=f"http://grafana:3000{url}",
                    status=status,
                    json=json or {}
                )

            def add_dashboard_update_response(self, dashboard_id, status=200):
                """Add mock dashboard update response."""
                self.add_response(
                    "POST",
                    "/api/dashboards/db",
                    status=status,
                    json={
                        "id": dashboard_id,
                        "uid": f"dashboard_{dashboard_id}",
                        "url": f"http://grafana:3000/d/dashboard_{dashboard_id}",
                        "status": "success"
                    }
                )

            def add_dashboard_get_response(self, dashboard_uid, dashboard_data=None):
                """Add mock dashboard get response."""
                self.add_response(
                    "GET",
                    f"/api/dashboards/uid/{dashboard_uid}",
                    status=200,
                    json=dashboard_data or self._default_dashboard
                )

            def verify(self):
                """Verify all mocked endpoints were called."""
                self._responses.verify()

            def stop(self):
                """Stop the mock server."""
                self._responses.stop()
                self._responses.reset()

        mock_grafana = MockGrafanaClient()
        yield mock_grafana

        # Cleanup
        mock_grafana.stop()

    except ImportError:
        # responses library not available - yield simple mock
        class SimpleMockGrafana:
            def __init__(self):
                self._calls = []

            def add_response(self, method, url, status=200, json=None):
                """Record response mock."""
                self._calls.append({"method": method, "url": url, "status": status})

            def verify(self):
                """Verify calls were made."""
                pass

            def stop(self):
                """Stop mock."""
                pass

        mock_grafana = SimpleMockGrafana()
        yield mock_grafana


def _count_assertions(node: ast.AST) -> int:
    """Count assert statements and pytest assertions in AST node."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
        # Check for common assertion patterns
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute):
                if child.func.attr in ('assertEqual', 'assertTrue', 'assertFalse',
                                       'assertIn', 'assertNotIn', 'assertRaises',
                                       'assertIs', 'assertIsNone', 'assertIsNotNone'):
                    count += 1
    return count


def _calculate_assertion_density(test_file: Path) -> float:
    """Calculate assertions per line of test code."""
    try:
        source = test_file.read_text()
        tree = ast.parse(source)
        lines = len(source.splitlines())
        if lines == 0:
            return 0.0
        asserts = _count_assertions(tree)
        return asserts / lines
    except Exception:
        return 0.0


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Display quality metrics after test run.

    Reports assertion density and coverage summary.
    """
    # Assertion density check
    min_density = 0.15  # 15 assertions per 100 lines
    test_files = list(Path("tests").rglob("test_*.py"))
    low_density_files = []

    for test_file in test_files:
        density = _calculate_assertion_density(test_file)
        if 0 < density < min_density:
            low_density_files.append((test_file, density))

    if low_density_files:
        terminalreporter.write_sep("=", "WARNING: Low Assertion Density", red=True)
        for test_file, density in low_density_files[:5]:  # Show first 5
            terminalreporter.write_line(
                f"  {test_file}: {density:.3f} (target: {min_density:.2f})",
                red=True
            )

    # Coverage summary
    try:
        import json
        coverage_path = Path("tests/coverage_reports/metrics/coverage.json")
        if coverage_path.exists():
            with open(coverage_path) as f:
                coverage_data = json.load(f)

            line_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)
            terminalreporter.write_sep("=", f"Coverage: {line_coverage:.1f}%", red=True)
    except Exception:
        pass
