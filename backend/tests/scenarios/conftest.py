"""
Scenario test fixtures.

Extends security/conftest.py fixtures for scenario testing.
"""
import pytest
from sqlalchemy.orm import Session
from tests.factories.user_factory import MemberUserFactory
from core.auth import create_access_token
from tests.security.conftest import (
    client,
    db_session,
    test_user_with_password,
    valid_auth_token,
    admin_user,
    admin_token,
)


@pytest.fixture(scope="function")
def member_token(db_session: Session) -> str:
    """Create authentication token for regular member user."""
    user = MemberUserFactory(_session=db_session)
    return create_access_token(data={"sub": str(user.id)})


# Re-export fixtures from security/conftest for convenience
__all__ = [
    "client",
    "db_session",
    "test_user_with_password",
    "valid_auth_token",
    "admin_user",
    "admin_token",
    "member_token",
]
