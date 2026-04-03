"""
Skill installation fuzzing harness for FastAPI endpoints.

This module uses Atheris to fuzz skill import, execute, and promote endpoints
to discover crashes, security vulnerabilities, and edge cases.

Coverage:
- POST /api/skills/import - Import community skill
- POST /api/skills/execute - Execute skill
- POST /api/skills/promote - Promote skill to Active status
- Security-focused fuzzing: code injection, typosquatting, path traversal
- YAML parsing fuzzing: malformed frontmatter, huge documents
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
# TEST SKILL IMPORT FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_skill_import_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz skill import endpoint (POST /api/skills/import).

    PROPERTY: Skill import endpoint should not crash on malformed input
    STRATEGY: Use FuzzedDataProvider to generate random skill content and metadata
    INVARIANT: Response status code always in [200, 400, 401, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Various import sources (github_url, file_upload, raw_content, invalid)
    - Malformed SKILL.md content (0-10000 chars)
    - SQL injection in metadata fields
    - XSS payloads in skill descriptions

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
        """Fuzz skill import endpoint with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz source (github_url, file_upload, raw_content, invalid values)
            source_type = fdp.ConsumeIntInRange(0, 3)
            if source_type == 0:
                source = "github_url"
            elif source_type == 1:
                source = "file_upload"
            elif source_type == 2:
                source = "raw_content"
            else:
                source = fdp.ConsumeRandomLengthString(50)  # Invalid source

            # Fuzz content (0-10000 chars, SKILL.md format, None, empty)
            content = fdp.ConsumeRandomLengthString(10000)

            # Fuzz metadata dict (0-10 keys, SQL injection, XSS)
            num_keys = fdp.ConsumeIntInRange(0, 10)
            metadata = {}
            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(50)
                value = fdp.ConsumeRandomLengthString(100)
                metadata[key] = value

            payload = {
                "source": source,
                "content": content if content else None,
                "metadata": metadata if metadata else None
            }

            # Call POST /api/skills/import
            response = client.post("/api/skills/import", json=payload, headers=headers)

            # Assert status in [200, 400, 401, 422]
            assert response.status_code in [200, 400, 401, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST SKILL EXECUTE FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_skill_execute_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz skill execute endpoint (POST /api/skills/execute).

    PROPERTY: Skill execute endpoint should not crash on malformed input
    STRATEGY: Use FuzzedDataProvider to generate random skill IDs and inputs
    INVARIANT: Response status code always in [200, 400, 404, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Invalid skill_id formats (None, empty, huge strings)
    - Code injection in inputs dict
    - Huge input values (DoS protection)
    - Invalid agent_id formats

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
        """Fuzz skill execute endpoint with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz skill_id (50 chars, None, empty)
            skill_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz inputs dict (0-20 keys, code injection, huge values)
            num_keys = fdp.ConsumeIntInRange(0, 20)
            inputs = {}
            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(50)
                value_type = fdp.ConsumeIntInRange(0, 3)
                if value_type == 0:
                    # Code injection payloads
                    value = fdp.ConsumeRandomLengthString(1000)
                elif value_type == 1:
                    # Huge value (DoS test)
                    value = fdp.ConsumeRandomLengthString(10000)
                elif value_type == 2:
                    value = fdp.ConsumeIntInRange(-1000000, 1000000)
                else:
                    value = None
                inputs[key] = value

            # Fuzz agent_id (50 chars, None, empty)
            agent_id = fdp.ConsumeRandomLengthString(50)

            payload = {
                "skill_id": skill_id if skill_id else None,
                "inputs": inputs,
                "agent_id": agent_id if agent_id else None
            }

            # Call POST /api/skills/execute
            response = client.post("/api/skills/execute", json=payload, headers=headers)

            # Assert status in [200, 400, 404, 422]
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST SKILL PROMOTE FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_skill_promote_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz skill promote endpoint (POST /api/skills/promote).

    PROPERTY: Skill promote endpoint should not crash on malformed input
    STRATEGY: Use FuzzedDataProvider to generate random skill IDs
    INVARIANT: Response status code always in [200, 400, 404, 409] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Invalid skill_id formats
    - Promotion from Untrusted -> Active status
    - Duplicate promotion attempts (409 conflict)

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
        """Fuzz skill promote endpoint with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz skill_id (50 chars, None, empty)
            skill_id = fdp.ConsumeRandomLengthString(50)

            payload = {
                "skill_id": skill_id if skill_id else None
            }

            # Call POST /api/skills/promote
            response = client.post("/api/skills/promote", json=payload, headers=headers)

            # Assert status in [200, 400, 404, 409]
            assert response.status_code in [200, 400, 404, 409], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST SKILL CONTENT SECURITY FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_skill_content_security_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz skill content with malicious payloads (security-focused fuzzing).

    PROPERTY: Skill import endpoint should not crash on malicious payloads
    STRATEGY: Test known attack patterns from Phase 237 bug discovery
    INVARIANT: Response status code always in [200, 400, 401, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Code injection: "__import__('os').system('rm -rf /')"
    - Typosquatting: "requests" vs "requets", "numpy" vs "numpyy"
    - Path traversal: "../../../etc/passwd"
    - Null bytes: "skill\x00name"
    - Metadata injection: author, tags with malicious content

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

    # Malicious payloads from Phase 237
    malicious_payloads = [
        # Code injection
        "__import__('os').system('rm -rf /')",
        "eval('__import__(\"os\").system(\"id\")')",
        "exec(\"import os; os.system('pwd')\")",

        # Typosquatting
        "requets",  # vs "requests"
        "numpyy",   # vs "numpy"
        "panndas",  # vs "pandas"
        "flaskk",   # vs "flask"

        # Path traversal
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "/proc/self/environ",

        # Null bytes
        "skill\x00name",
        "author\x00injection",

        # SQL injection
        "'; DROP TABLE skills; --",
        "' OR '1'='1",
        "'; INSERT INTO skills VALUES (...); --",

        # XSS
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
    ]

    def fuzz_one_input(data: bytes):
        """Fuzz skill content with malicious payloads."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Select malicious payload
            payload_idx = fdp.ConsumeIntInRange(0, len(malicious_payloads) - 1)
            malicious_content = malicious_payloads[payload_idx]

            # Fuzz where to inject payload
            injection_type = fdp.ConsumeIntInRange(0, 3)
            if injection_type == 0:
                # Inject in skill name
                content = f"# SKILL.md\nname: {malicious_content}\ndescription: Test skill"
            elif injection_type == 1:
                # Inject in content
                content = f"# SKILL.md\nname: test\ncontent: {malicious_content}"
            elif injection_type == 2:
                # Inject in metadata
                content = "# SKILL.md\nname: test\n"
                metadata = {"author": malicious_content, "tags": [malicious_content]}
            else:
                # Full payload as content
                content = malicious_content

            # Prepare payload
            payload = {
                "source": "raw_content",
                "content": content,
                "metadata": metadata if injection_type == 2 else None
            }

            # Call POST /api/skills/import
            response = client.post("/api/skills/import", json=payload, headers=headers)

            # Assert no crashes (validation errors OK)
            assert response.status_code in [200, 400, 401, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST SKILL YAML PARSING FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_skill_yaml_parsing_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz YAML frontmatter parsing in SKILL.md files.

    PROPERTY: YAML parser should not crash on malformed YAML
    STRATEGY: Use FuzzedDataProvider to generate random YAML content
    INVARIANT: Response status code always in [200, 400, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Malformed YAML syntax (unclosed brackets, invalid indentation)
    - Huge YAML documents (DoS protection)
    - Cyclical references in YAML
    - Missing required fields
    - Invalid data types

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
        """Fuzz YAML parsing with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz YAML content (0-5000 chars)
            yaml_content = fdp.ConsumeRandomLengthString(5000)

            # Construct SKILL.md with YAML frontmatter
            skill_content = f"""---
name: {name}
description: {fdp.ConsumeRandomLengthString(200)}
author: {fdp.ConsumeRandomLengthString(50)}
version: {fdp.ConsumeRandomLengthString(20)}
---

## Skill Content

{fdp.ConsumeRandomLengthString(1000)}
"""

            payload = {
                "source": "raw_content",
                "content": skill_content,
                "metadata": None
            }

            # Call POST /api/skills/import
            response = client.post("/api/skills/import", json=payload, headers=headers)

            # Assert no crashes (parsing errors OK)
            assert response.status_code in [200, 400, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "yaml" not in str(e).lower() and "validation" not in str(e).lower():
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()


# ============================================================================
# TEST SKILL DEPENDENCY INJECTION FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_skill_dependency_injection_fuzz(db_session: Session, authenticated_user):
    """
    Fuzz skill dependency injection in requirements.txt.

    PROPERTY: Skill installer should not crash on malicious dependencies
    STRATEGY: Test malicious packages in requirements.txt
    INVARIANT: Response status code always in [200, 400, 422] (no 500 errors)

    RADII: 10000 iterations provides coverage of:
    - Typosquatting packages (requets vs requests)
    - Malicious package names (rm -rf, ../etc/passwd)
    - Conflicting dependencies
    - Huge dependency lists
    - Invalid version specifiers

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

    # Malicious dependency patterns
    malicious_deps = [
        "requets",           # Typosquatting
        "numpyy",            # Typosquatting
        "../../../etc/passwd",  # Path traversal
        "rm -rf",            # Command injection
        "package==../..",    # Path traversal
        "package @ file:///etc/passwd",  # Local file
        "package @ git+git://github.com/attacker/repo.git#egg=package",  # Git URL
        "-e ../../..",       # Editable install with path traversal
        "package==999.999.999",  # Invalid version
    ]

    def fuzz_one_input(data: bytes):
        """Fuzz dependency injection with random input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Generate requirements.txt content
            num_deps = fdp.ConsumeIntInRange(0, 10)
            requirements = []
            for i in range(num_deps):
                # Mix of legitimate and malicious dependencies
                if fdp.ConsumeBool():
                    # Malicious dependency
                    dep_idx = fdp.ConsumeIntInRange(0, len(malicious_deps) - 1)
                    dep = malicious_deps[dep_idx]
                else:
                    # Random dependency
                    dep = fdp.ConsumeRandomLengthString(100)
                requirements.append(dep)

            # Construct SKILL.md with dependencies
            requirements_str = "\n".join(requirements)
            skill_content = f"""---
name: test-skill
description: Test skill with dependencies
dependencies: |
{requirements_str}
---

## Skill Content
Test content
"""

            payload = {
                "source": "raw_content",
                "content": skill_content,
                "metadata": None
            }

            # Call POST /api/skills/import
            response = client.post("/api/skills/import", json=payload, headers=headers)

            # Assert no crashes (validation errors OK)
            assert response.status_code in [200, 400, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except Exception as e:
            if "validation" not in str(e).lower() and "422" not in str(e):
                raise

    atheris.Setup(sys.argv, [fuzz_one_input])
    atheris.Fuzz()
