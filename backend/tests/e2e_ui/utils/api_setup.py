"""
API-first setup utilities for fast test initialization.

This module provides utilities for quickly setting up test data by calling
API endpoints directly, bypassing slow UI navigation (10-100x speedup).

Base URL: http://localhost:8001 (non-conflicting with dev backend on port 8000)
"""

import requests
from typing import Any, Dict, Optional


class APIClient:
    """
    HTTP client for making API requests to the backend during tests.

    Provides convenient methods for HTTP requests with JSON handling and
    authentication header support.
    """

    def __init__(self, base_url: str = "http://localhost:8001", token: Optional[str] = None):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the backend API (default: http://localhost:8001)
            token: Optional JWT authentication token
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with authentication if token is available.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a GET request to the API.

        Args:
            path: API endpoint path (e.g., "/api/v1/users")
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            requests.HTTPError: If the request fails
        """
        url = f"{self.base_url}{path}"
        response = self.session.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, data: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a POST request to the API.

        Args:
            path: API endpoint path (e.g., "/api/v1/users")
            data: Optional form data
            json: Optional JSON data

        Returns:
            JSON response data

        Raises:
            requests.HTTPError: If the request fails
        """
        url = f"{self.base_url}{path}"
        response = self.session.post(url, headers=self._get_headers(), data=data, json=json)
        response.raise_for_status()
        return response.json()

    def put(self, path: str, data: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a PUT request to the API.

        Args:
            path: API endpoint path (e.g., "/api/v1/users/me")
            data: Optional form data
            json: Optional JSON data

        Returns:
            JSON response data

        Raises:
            requests.HTTPError: If the request fails
        """
        url = f"{self.base_url}{path}"
        response = self.session.put(url, headers=self._get_headers(), data=data, json=json)
        response.raise_for_status()
        return response.json()

    def delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a DELETE request to the API.

        Args:
            path: API endpoint path (e.g., "/api/v1/projects/123")
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            requests.HTTPError: If the request fails
        """
        url = f"{self.base_url}{path}"
        response = self.session.delete(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    def set_token(self, token: str) -> None:
        """
        Set the authentication token for subsequent requests.

        Args:
            token: JWT authentication token
        """
        self.token = token

    def clear_token(self) -> None:
        """Clear the authentication token."""
        self.token = None


# ============================================================================
# User Setup Functions
# ============================================================================

def _post_with_retry(
    client: APIClient,
    path: str,
    json: Dict[str, Any],
    retries: int = 4,
    on_conflict: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    POST with bounded retries on transient server-side failures.

    The dev backend's SQLite QueuePool can briefly serve failures (e.g. pooled
    connections opened while a test chmod'ed the DB read-only serve write
    errors for up to the pool_recycle window). The backend maps those to
    500 OR to a 400 envelope with error_code="DATABASE_ERROR" — both are
    retried. Validation errors (real 400s, 401/403/404/409) are never retried.

    A register POST can also 500 AFTER committing the user row (the default
    tenant/workspace creation step fails on a broken connection) — the retry
    then hits 400 "Email already registered". on_conflict is invoked in that
    case so callers can recover (e.g. authenticate instead of re-register).

    Args:
        client: APIClient instance
        path: API endpoint path
        json: JSON payload
        retries: Number of retries after the first attempt (default: 4)
        on_conflict: Optional zero-arg callable invoked when the server
            reports the resource already exists (400 "already registered")

    Returns:
        JSON response data

    Raises:
        requests.HTTPError: If the request fails after all retries
    """
    import time

    last_error = None
    for attempt in range(retries + 1):
        try:
            return client.post(path, json=json)
        except requests.HTTPError as e:
            last_error = e
            response = e.response
            status = response.status_code if response is not None else None
            # Retry transient failures: 5xx, or the backend's DB-error
            # envelope (400 + error_code=DATABASE_ERROR).
            transient = status is None or status >= 500
            if status == 400:
                try:
                    body = response.json()
                except Exception:
                    body = {}
                if body.get("error_code") == "DATABASE_ERROR":
                    transient = True
                elif body.get("detail") == "Email already registered" and on_conflict is not None:
                    # Our own previous attempt committed the user but the
                    # response 500'd — recover via the conflict handler.
                    return on_conflict()
            if not transient:
                raise
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    raise last_error  # pragma: no cover - defensive


def create_test_user(
    client: APIClient,
    email: str,
    password: str,
    first_name: str = "Test",
    last_name: str = "User",
    recover_already_registered: bool = False,
) -> Dict[str, Any]:
    """
    Create a test user via API.

    Args:
        client: APIClient instance
        email: User email
        password: User password
        first_name: User first name (default: "Test")
        last_name: User last name (default: "User")
        recover_already_registered: If True, a 400 "Email already
            registered" is treated as a previous retry's committed user and
            recovered by authenticating instead of raising. Only safe for
            callers that always generate fresh emails (a fixture); tests
            that deliberately probe duplicate handling must keep this False.

    Returns:
        User data response from API

    Raises:
        requests.HTTPError: If user creation fails

    Note:
        If a retried POST 500s after committing the user (default
        tenant/workspace creation can fail on a broken pooled connection),
        the follow-up "Email already registered" is recovered by
        authenticating the existing user instead of re-registering.
    """
    if not recover_already_registered:
        return _post_with_retry(
            client,
            "/api/auth/register",
            {
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name
            },
        )

    def on_already_registered() -> Dict[str, Any]:
        token = get_test_user_token(client, email, password)
        return {"access_token": token, "token_type": "bearer"}

    return _post_with_retry(
        client,
        "/api/auth/register",
        {
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name
        },
        on_conflict=on_already_registered,
    )


def authenticate_user(client: APIClient, email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate a user and get access token.

    Args:
        client: APIClient instance
        email: User email
        password: User password

    Returns:
        Authentication response with access_token

    Raises:
        requests.HTTPError: If authentication fails
    """
    return _post_with_retry(
        client,
        "/api/auth/login",
        {
            "username": email,
            "password": password
        }
    )


def get_test_user_token(client: APIClient, email: str, password: str) -> str:
    """
    Get JWT token for a test user.

    Args:
        client: APIClient instance
        email: User email
        password: User password

    Returns:
        JWT access token

    Raises:
        requests.HTTPError: If authentication fails
    """
    response = authenticate_user(client, email, password)
    return response["access_token"]


def set_authenticated_session(page, token: str) -> None:
    """
    Set JWT token in localStorage for Playwright page.

    This authenticates the browser session without going through UI login.

    Args:
        page: Playwright Page object
        token: JWT access token
    """
    page.evaluate(f"localStorage.setItem('auth_token', '{token}')")


# ============================================================================
# Project Setup Functions
# ============================================================================

def create_test_project(client: APIClient, name: str, description: str = "", token: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a test project task via the unified-tasks API.

    The backend exposes project work as unified tasks at POST /api/projects/unified-tasks.
    This creates a task representing the "project" for the test.

    Args:
        client: APIClient instance
        name: Project/task name (sent as 'summary')
        description: Project description (appended to summary)
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Task creation response from API

    Raises:
        requests.HTTPError: If creation fails
    """
    body = {"summary": name, "description": description or name}
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.post("/api/projects/unified-tasks", json=body)
        finally:
            client.token = original_token
    else:
        response = client.post("/api/projects/unified-tasks", json=body)

    return response


def get_test_projects(client: APIClient, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Get all unified tasks (projects) via API.

    Args:
        client: APIClient instance
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Tasks data response from API

    Raises:
        requests.HTTPError: If request fails
    """
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.get("/api/projects/unified-tasks")
        finally:
            client.token = original_token
    else:
        response = client.get("/api/projects/unified-tasks")

    return response


def delete_test_project(client: APIClient, project_id: str, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete a test project task via API.

    Args:
        client: APIClient instance
        project_id: Project/task ID to delete
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Response data

    Raises:
        requests.HTTPError: If deletion fails
    """
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.delete(f"/api/v1/tasks/{project_id}")
        finally:
            client.token = original_token
    else:
        response = client.delete(f"/api/v1/tasks/{project_id}")

    return response


# ============================================================================
# Skill Setup Functions
# ============================================================================

def import_test_skill(
    client: APIClient,
    name: str,
    description: str = "E2E test skill",
    body: str = "Test skill body.",
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Import a test skill via the skills registry API (POST /api/skills/import).

    Skills are authored as SKILL.md (YAML frontmatter + markdown body).

    Args:
        client: APIClient instance
        name: Skill name
        description: Skill description
        body: Markdown body content
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Import response data (contains skill_id, status, scan_result)

    Raises:
        requests.HTTPError: If import fails
    """
    content = f"---\nname: {name}\ndescription: {description}\n---\n\n{body}"
    payload = {"source": "raw_content", "content": content, "metadata": {"author": "e2e"}}

    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.post("/api/skills/import", json=payload)
        finally:
            client.token = original_token
    else:
        response = client.post("/api/skills/import", json=payload)

    return response


# Backward-compatible alias for tests that called install_test_skill.
def install_test_skill(client: APIClient, skill_id: str, agent_id: str = "test-agent", token: Optional[str] = None) -> Dict[str, Any]:
    """
    Install/register a test skill.

    The backend models skills as imported entities (POST /api/skills/import)
    rather than install-from-marketplace. This helper imports a uniquely-named
    skill and returns the import result (which includes the skill_id).

    Args:
        client: APIClient instance
        skill_id: Ignored — kept for backward compat. A unique name is generated.
        agent_id: Ignored — kept for backward compat.
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Import response data
    """
    import uuid
    unique = uuid.uuid4().hex[:8]
    return import_test_skill(
        client,
        name=f"E2E Skill {unique}",
        description=f"Auto-imported by E2E suite ({skill_id})",
        token=token,
    )


def get_installed_skills(client: APIClient, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Get all imported skills via GET /api/skills/list.

    Args:
        client: APIClient instance
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Skills data response from API

    Raises:
        requests.HTTPError: If request fails
    """
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.get("/api/skills/list")
        finally:
            client.token = original_token
    else:
        response = client.get("/api/skills/list")

    return response


def uninstall_test_skill(client: APIClient, skill_id: str, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Uninstall (delete) a skill via DELETE /api/skills/{skill_id}.

    Args:
        client: APIClient instance
        skill_id: Skill ID to delete
        token: Optional JWT token (uses client token if not provided)

    Returns:
        Response data

    Raises:
        requests.HTTPError: If deletion fails
    """
    if token:
        original_token = client.token
        client.set_token(token)
        try:
            response = client.delete(f"/api/skills/{skill_id}")
        finally:
            client.token = original_token
    else:
        response = client.delete(f"/api/skills/{skill_id}")

    return response
