"""
Mobile API test configuration.

This conftest.py ensures mobile fixtures are available for all mobile API tests.
"""

import sys
import os

# Add backend to path
backend_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Import database fixtures from e2e_ui for db_session
# This ensures mobile tests use the same database isolation
sys.path.insert(0, os.path.join(backend_path, "tests", "e2e_ui"))
from fixtures.database_fixtures import db_session

# Import mobile fixtures
from mobile_api.fixtures.mobile_fixtures import (
    mobile_api_client,
    mobile_auth_token,
    mobile_auth_headers,
    mobile_test_user,
    mobile_authenticated_client,
    mobile_admin_user,
)

# Make fixtures available to all tests in this directory
pytest_plugins = ["mobile_api.fixtures.mobile_fixtures"]
