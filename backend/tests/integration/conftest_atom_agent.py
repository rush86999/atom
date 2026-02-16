"""
Custom fixtures for atom_agent_endpoints integration tests.

This conftest provides a simplified db_session fixture that avoids
the NoReferencedTableError issue when running multiple tests.
"""

import os
import sys
import tempfile
from pathlib import Path

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from main_api_app import app
from core.database import Base
from core.models import AgentRegistry, AgentExecution, AgentFeedback


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    Simplified version that avoids sorted_tables to prevent NoReferencedTableError.
    """
    # Use file-based temp SQLite for tests
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
    except exc.NoReferencedTableError:
        # If there are missing FK references, create tables individually
        for table in Base.metadata.tables.values():
            try:
                table.create(engine, checkfirst=True)
            except exc.NoReferencedTableError:
                # Skip tables with missing FK references
                continue
            except Exception as e:
                # Ignore other errors (duplicate indexes, etc.)
                if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                    raise

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
def client(db_session: Session):
    """
    Create TestClient with dependency override for test database.
    """
    from core.database import get_db

    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db

    # Mock get_current_user to bypass auth
    def _mock_get_current_user():
        from tests.factories.user_factory import AdminUserFactory
        import uuid

        unique_id = str(uuid.uuid4())[:8]
        email = f"test_{unique_id}@integration.com"

        try:
            from core.models import User
            user = db_session.query(User).filter(User.email == email).first()
            if user:
                return user
        except Exception:
            pass

        user = AdminUserFactory(email=email, _session=db_session)
        db_session.commit()
        db_session.refresh(user)
        return user

    # Override get_current_user to bypass auth
    try:
        from core.auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_get_current_user
    except ImportError:
        pass

    # Modify TrustedHostMiddleware to allow testserver
    for middleware in app.user_middleware:
        if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'TrustedHostMiddleware':
            middleware.kwargs['allowed_hosts'] = ['testserver', 'localhost', '127.0.0.1', '0.0.0.0', '*']
            break

    # Create TestClient
    test_client = TestClient(app, base_url="http://testserver")

    yield test_client

    app.dependency_overrides.clear()
