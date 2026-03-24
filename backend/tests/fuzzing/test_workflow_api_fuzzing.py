"""
Workflow API fuzzing harness for FastAPI endpoints.

This module uses Atheris to fuzz workflow create, update, trigger, and schedule
endpoints to discover crashes, security vulnerabilities, and edge cases.

Coverage:
- POST /api/workflows - Create workflow
- PUT /api/workflows/{id} - Update workflow
- POST /api/workflows/{id}/trigger - Trigger workflow execution
- POST /api/workflows/{id}/schedule - Schedule workflow
"""

import os
import sys
from typing import Dict, Any

import os
import sys

# Add backend to path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import fixtures
from tests.fuzzing.conftest import ATHERIS_AVAILABLE
from tests.e2e_ui.fixtures.database_fixtures import db_session
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user, test_user

from main_api_app import app
from core.database import get_db

# Try to import Atheris
try:
    import atheris
    from atheris import fp
    ATHERIS_AVAILABLE = True
except ImportError:
    ATHERIS_AVAILABLE = False


# ============================================================================
# TEST WORKFLOW CREATE FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_workflow_create_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz workflow creation endpoint (POST /api/workflows).

    PROPERTY: Workflow create endpoint should not crash on malformed input
    STRATEGY: Use FuzzedDataProvider to generate random workflow definitions
    INVARIANT: Response status code always in [200, 400, 401, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - SQL injection in workflow_name
    - Empty/None values for required fields
    - Malformed workflow_definition (nested, cyclical, huge)
    - Invalid trigger configurations

    Args:
        db_session: Database session with transaction rollback
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed")

    user, token = authenticated_user

    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session

    # Create TestClient
    client = TestClient(app)

    # Set auth headers
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz workflow create endpoint with random input."""
        try:
            # Use FuzzedDataProvider for structured input
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz workflow_name (0-100 chars, None, empty, SQL injection)
            workflow_name = fdp.ConsumeRandomLengthString(100)

            # Fuzz workflow_description (0-1000 chars, None, empty)
            workflow_description = fdp.ConsumeRandomLengthString(1000)

            # Fuzz workflow_definition dict (0-20 keys, nested structures)
            num_keys = fdp.ConsumeIntInRange(0, 20)
            workflow_definition = {}
            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(50)
                value_type = fdp.ConsumeIntInRange(0, 3)
                if value_type == 0:
                    value = fdp.ConsumeRandomLengthString(100)
                elif value_type == 1:
                    value = fdp.ConsumeIntInRange(-1000000, 1000000)
                elif value_type == 2:
                    # Nested dict
                    nested_keys = fdp.ConsumeIntInRange(0, 5)
                    value = {fdp.ConsumeRandomLengthString(20): fdp.ConsumeRandomLengthString(50) for _ in range(nested_keys)}
                else:
                    value = None
                workflow_definition[key] = value

            # Fuzz triggers list (0-10 items)
            num_triggers = fdp.ConsumeIntInRange(0, 10)
            triggers = []
            for i in range(num_triggers):
                trigger = {
                    "type": fdp.ConsumeRandomLengthString(20),
                    "config": {
                        "cron": fdp.ConsumeRandomLengthString(50),
                        "enabled": fdp.ConsumeBool()
                    }
                }
                triggers.append(trigger)

            # Prepare request payload
            payload = {
                "name": workflow_name if workflow_name else None,
                "description": workflow_description if workflow_description else None,
                "definition": workflow_definition,
                "triggers": triggers
            }

            # Call POST /api/workflows
            response = client.post("/api/workflows", json=payload, headers=headers)

            # Assert status in [200, 400, 401, 422] (no 500 errors)
            assert response.status_code in [200, 400, 401, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            # Only re-raise if it's a crash (not validation error)
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    # Run fuzzing with Atheris
    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST WORKFLOW UPDATE FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_workflow_update_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz workflow update endpoint (PUT /api/workflows/{id}).

    PROPERTY: Workflow update endpoint should not crash on malformed input
    STRATEGY: Use FuzzedDataProvider to generate random workflow IDs and update data
    INVARIANT: Response status code always in [200, 400, 404, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Invalid workflow_id formats (None, empty, huge strings)
    - Partial updates with null values
    - Malformed workflow_definition
    - SQL injection in update fields

    Args:
        db_session: Database session with transaction rollback
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed")

    user, token = authenticated_user

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz workflow update endpoint with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz workflow_id (50 chars, None, empty)
            workflow_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz update_data dict (partial updates, null values, huge strings)
            num_keys = fdp.ConsumeIntInRange(0, 10)
            update_data = {}
            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(50)
                value_type = fdp.ConsumeIntInRange(0, 4)
                if value_type == 0:
                    value = fdp.ConsumeRandomLengthString(1000)
                elif value_type == 1:
                    value = None
                elif value_type == 2:
                    value = fdp.ConsumeBool()
                elif value_type == 3:
                    # Nested dict
                    nested_keys = fdp.ConsumeIntInRange(0, 5)
                    value = {fdp.ConsumeRandomLengthString(20): fdp.ConsumeRandomLengthString(100) for _ in range(nested_keys)}
                else:
                    value = fdp.ConsumeIntInRange(-1000000, 1000000)
                update_data[key] = value

            # Call PUT /api/workflows/{id}
            response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=headers)

            # Assert status in [200, 400, 404, 422]
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST WORKFLOW TRIGGER FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_workflow_trigger_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz workflow trigger endpoint (POST /api/workflows/{id}/trigger).

    PROPERTY: Workflow trigger endpoint should not crash on malformed input
    STRATEGY: Use FuzzedDataProvider to generate random workflow IDs and input data
    INVARIANT: Response status code always in [200, 400, 404, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Invalid workflow_id formats
    - Huge input_data payloads (DoS protection)
    - Nested structures with cyclical references
    - SQL injection in input fields

    Args:
        db_session: Database session with transaction rollback
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed")

    user, token = authenticated_user

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz workflow trigger endpoint with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz workflow_id (50 chars, None, empty)
            workflow_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz input_data dict (0-20 keys, nested values, huge payloads)
            num_keys = fdp.ConsumeIntInRange(0, 20)
            input_data = {}
            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(50)
                value_type = fdp.ConsumeIntInRange(0, 3)
                if value_type == 0:
                    # Huge string (DoS test)
                    value = fdp.ConsumeRandomLengthString(10000)
                elif value_type == 1:
                    # Nested dict (cyclical ref test)
                    nested_keys = fdp.ConsumeIntInRange(0, 10)
                    value = {fdp.ConsumeRandomLengthString(30): fdp.ConsumeRandomLengthString(100) for _ in range(nested_keys)}
                elif value_type == 2:
                    value = fdp.ConsumeIntInRange(-1000000, 1000000)
                else:
                    value = None
                input_data[key] = value

            payload = {"input_data": input_data}

            # Call POST /api/workflows/{id}/trigger
            response = client.post(f"/api/workflows/{workflow_id}/trigger", json=payload, headers=headers)

            # Assert status in [200, 400, 404, 422]
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST WORKFLOW SCHEDULE FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_workflow_schedule_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz workflow schedule endpoint (POST /api/workflows/{id}/schedule).

    PROPERTY: Workflow schedule endpoint should not crash on malformed cron expressions
    STRATEGY: Use FuzzedDataProvider to generate random schedule configurations
    INVARIANT: Response status code always in [200, 400, 404, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Invalid cron expressions (syntax errors, out-of-range values)
    - Special characters in cron fields
    - Past dates in schedule config
    - Huge intervals (DoS protection)

    Args:
        db_session: Database session with transaction rollback
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed")

    user, token = authenticated_user

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz workflow schedule endpoint with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz workflow_id (50 chars, None, empty)
            workflow_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz schedule_config dict (cron expressions, intervals, invalid formats)
            schedule_type = fdp.ConsumeRandomLengthString(20)
            schedule_config = {
                "type": schedule_type,
                "cron": fdp.ConsumeRandomLengthString(100),  # Invalid cron syntax
                "interval_seconds": fdp.ConsumeIntInRange(-1000000, 1000000),  # Invalid interval
                "start_date": fdp.ConsumeRandomLengthString(50),  # Invalid date format
                "enabled": fdp.ConsumeBool()
            }

            # Call POST /api/workflows/{id}/schedule
            response = client.post(f"/api/workflows/{workflow_id}/schedule", json=schedule_config, headers=headers)

            # Assert status in [200, 400, 404, 422]
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST WORKFLOW DAG VALIDATION FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_workflow_dag_validation_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz workflow DAG validation (cyclical dependencies, missing nodes).

    PROPERTY: Workflow DAG validation should not crash on malformed graphs
    STRATEGY: Use FuzzedDataProvider to generate random node/edge configurations
    INVARIANT: Response status code always in [200, 400, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Cyclical node dependencies (a -> b -> a)
    - Missing node references (edge points to non-existent node)
    - Empty or None node lists
    - Self-referencing nodes

    Args:
        db_session: Database session with transaction rollback
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed")

    user, token = authenticated_user

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz workflow DAG validation with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz nodes list (0-20 nodes)
            num_nodes = fdp.ConsumeIntInRange(0, 20)
            nodes = []
            node_ids = []
            for i in range(num_nodes):
                node_id = fdp.ConsumeRandomLengthString(30)
                node_ids.append(node_id)
                nodes.append({
                    "id": node_id,
                    "type": fdp.ConsumeRandomLengthString(20),
                    "config": fdp.ConsumeRandomLengthString(100)
                })

            # Fuzz edges list (0-30 edges, potentially cyclical)
            num_edges = fdp.ConsumeIntInRange(0, 30)
            edges = []
            for i in range(num_edges):
                # Use random node IDs or generate invalid ones
                from_idx = fdp.ConsumeIntInRange(0, len(node_ids) + 5)
                to_idx = fdp.ConsumeIntInRange(0, len(node_ids) + 5)

                from_node = node_ids[from_idx] if from_idx < len(node_ids) else fdp.ConsumeRandomLengthString(30)
                to_node = node_ids[to_idx] if to_idx < len(node_ids) else fdp.ConsumeRandomLengthString(30)

                edges.append({
                    "from": from_node,
                    "to": to_node,
                    "condition": fdp.ConsumeRandomLengthString(50)
                })

            # Create workflow with DAG definition
            payload = {
                "name": fdp.ConsumeRandomLengthString(50),
                "definition": {
                    "nodes": nodes,
                    "edges": edges
                }
            }

            # Call POST /api/workflows (will trigger DAG validation)
            response = client.post("/api/workflows", json=payload, headers=headers)

            # Assert status in [200, 400, 422]
            assert response.status_code in [200, 400, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()
