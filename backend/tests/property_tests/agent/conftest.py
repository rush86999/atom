"""
Minimal conftest for agent execution property tests.

This conftest avoids importing the full app to bypass cv2/__version__ issues.
"""
import pytest
from unittest.mock import MagicMock


# Provide minimal fixtures without importing main app
@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db
