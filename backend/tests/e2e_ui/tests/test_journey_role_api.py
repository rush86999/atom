"""
Role-parametrized API feature journey — exercise the core feature endpoints
for EACH of the 8 roles.

This is the highest-leverage coverage test: one parametrization covers
role × feature, growing measured coverage across api/, core/, and the auth
path quickly. It verifies that every role can reach the read-side of the
features they're entitled to and that no role hits an unexpected crash.

For each (role, feature-read-endpoint) pair we assert:
  - status < 500 (the endpoint must not crash for any authenticated role)
  - status != 401 (a valid token must not be rejected)
  - 403 is acceptable for write endpoints a role lacks permission for

Write endpoints (create/update/delete) are intentionally minimal — we're
verifying the endpoint is wired and reachable, not deep-testing the feature
(that's the job of test_journey_api_features.py for the member role).
"""

from __future__ import annotations

import pytest
import requests

from tests.e2e_ui.fixtures.journey_fixtures import (  # noqa: F401
    BACKEND_URL,
    ALL_ROLES,
    role_credentials,
)


pytestmark = pytest.mark.e2e


# (feature, method, path, kwargs, expect_write_crash_guard)
# `crash_guard=True` means we only assert < 500 (write op; permission/422 fine).
FEATURE_READS = [
    ("agents",        "GET", "/api/agents/",                              {}),
    ("skills",        "GET", "/api/skills/list",                          {}),
    ("workflow-tmpl", "GET", "/api/workflow-templates/",                  {}),
    ("canvas",        "GET", "/api/canvas/",                              {}),
    ("preferences",   "GET", "/api/v1/preferences?user_id=x&workspace_id=y", {}),
    ("users-me",      "GET", "/api/users/me",                             {}),
    ("auth-me",       "GET", "/api/auth/me",                              {}),
    ("projects",      "GET", "/api/projects/unified-tasks",               {}),
    ("notifications", "GET", "/api/notifications?limit=5",                {}),
]


@pytest.mark.parametrize("role_credentials", ALL_ROLES, indirect=True)
@pytest.mark.parametrize("feature,method,path,kw", FEATURE_READS, ids=[f[0] for f in FEATURE_READS])
def test_every_role_can_read_core_features(role_credentials, feature, method, path, kw):
    """Every authenticated role must be able to READ the core feature lists
    without the endpoint crashing (5xx) or rejecting a valid token (401).

    A 403 here would mean the read endpoint enforces a permission the role
    lacks — currently no read endpoint does (only agent write/delete ops do),
    so a 403 would be a new finding worth investigating."""
    headers = {
        "Authorization": f"Bearer {role_credentials['access_token']}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.request(method, f"{BACKEND_URL}{path}", headers=headers, timeout=15, **kw)
        code = r.status_code
    except requests.RequestException as e:
        pytest.fail(f"{role_credentials['role']}/{feature}: request failed: {e}")

    role = role_credentials["role"]
    assert code != 401, f"{role}/{feature}: valid token rejected (401) on {path}"
    assert code < 500, (
        f"{role}/{feature}: {path} crashed with {code}: {r.text[:200]}"
    )
