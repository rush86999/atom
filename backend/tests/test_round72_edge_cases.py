"""RED tests — Round 72: edge-case bugs in the B-series fixes.

Discovered by edge-case probing of the Round 70/71 security fixes. Expected to
FAIL against the current code; go green once fixed.

Findings under test:
  B17 — `_validate_dataset_sql` over-blocks: a benign DuckDB dollar-quoted
        string literal that merely *mentions* a restricted function name is
        rejected. DuckDB supports `$$...$$` and `$tag$...$tag$` string
        literals; the current literal-stripper only handles single quotes.
        (Fail-closed, so P2 — but it breaks legitimate queries.)
        (`core/data/dataset_manager.py:_validate_dataset_sql`)
  B18 — `load_dataset` parses `inline_json` with no size/depth cap. A
        pathological inline JSON string is parsed unbounded → server memory
        exhaustion (DoS). load_dataset is INTERN-gated, so lower-maturity
        agents can reach it.
        (`core/data/dataset_manager.py:load` inline_json branch)
  B19 — `/api/auth/{service}/status` echoes a client-controlled `user_id`
        verbatim and leaks the server-global `redirect_uri` to every
        authenticated caller. The `user_id` param implies per-user isolation
        that does not exist (credentials come from server-global config), and
        `redirect_uri` is deployment config that should not be exposed
        per-caller.
        (`oauth_status_routes.py:*_status` endpoints)

NOTE on withdrawn finding (BUG 6): an earlier probe claimed a leading newline
defeats `_looks_like_sql` so the URL-scheme check is skipped. Verified false —
Python's str.lstrip() strips newlines, so `"\nSELECT ... 'https://...'"` is
correctly detected and blocked. Not a bug.

TDD: red first, then fix.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# --- B17: dollar-quoted string false positive --------------------------------


def test_validate_dataset_sql_allows_dollar_quoted_string():
    """B17: a dollar-quoted string literal that mentions a restricted fn name
    must NOT be blocked — the name is data, not a call. DuckDB supports
    `$$...$$` and `$tag$...$tag$` literals."""
    from core.data.dataset_manager import _validate_dataset_sql

    benign = "SELECT $$this string mentions read_csv but is just text$$ AS note"
    assert _validate_dataset_sql(benign) is None, (
        "B17 regression: a dollar-quoted string literal was wrongly blocked. "
        "The restricted-function scan must strip $$...$$ and $tag$...$tag$ "
        "string literals, not just single-quoted ones."
    )

    # Sanity: a real call site in a single-quoted literal is still NOT blocked
    # (it's data), and an actual call IS blocked.
    assert _validate_dataset_sql("SELECT 'read_csv docs' AS note") is None
    assert _validate_dataset_sql("SELECT * FROM read_csv('/etc/passwd')") is not None


# --- B18: inline_json DoS ----------------------------------------------------


def test_load_dataset_rejects_oversized_inline_json():
    """B18: load_dataset must cap inline_json size before parsing. A multi-MB
    inline payload would otherwise be parsed unbounded → memory exhaustion.
    The cap must reject clearly pathological input while accepting reasonable
    datasets (a few thousand rows comfortably fit under a few MB)."""
    from core.data.dataset_manager import get_dataset_manager

    dm = get_dataset_manager()
    # Build an inline JSON payload comfortably above the 5 MiB cap. Each cell
    # is ~1 KiB so we don't need millions of iterations to cross the threshold.
    cell = '{"a": "' + ("x" * 1000) + '"}'
    count = 6000  # 6000 * ~1KiB ≈ 6 MiB > 5 MiB cap
    oversized = "[" + ",".join(cell for _ in range(count)) + "]"
    assert len(oversized) > 5_000_000, "test setup: payload must exceed the 5 MiB cap"

    with pytest.raises(Exception) as excinfo:
        dm.load(source=oversized, name="dos", session_id="b18")
    # The rejection must be a clear validation error, not an opaque OOM/crash.
    msg = str(excinfo.value).lower()
    assert "size" in msg or "too large" in msg or "limit" in msg or "big" in msg, (
        f"B18 regression: oversized inline_json rejected with an unclear error: {excinfo.value!r}"
    )
    dm.clear_session("b18")


# --- B19: OAuth status info disclosure --------------------------------------


@pytest.fixture
def authed_status_client():
    """Mount the OAuth status router with auth overridden to a fixed caller,
    so we can exercise the status endpoint without a real token."""
    from core.auth import get_current_user
    from oauth_status_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "attacker"}
    return TestClient(app)


def test_oauth_status_does_not_echo_client_user_id(authed_status_client):
    """B19: the status endpoint must not echo a client-supplied user_id as if
    it scoped the lookup. Credentials are server-global; echoing an
    attacker-chosen user_id implies per-user isolation that does not exist."""
    resp = authed_status_client.get(
        "/api/auth/gmail/status", params={"user_id": "victim"}
    )
    assert resp.status_code == 200
    body = resp.json()
    # The response must NOT reflect the attacker-chosen user_id verbatim as a
    # per-user-scoped field. (Returning the authenticated principal's id, or
    # omitting user_id entirely, are both acceptable.)
    assert body.get("user_id") != "victim", (
        "B19 regression: status endpoint echoes a client-controlled user_id, "
        "implying per-user isolation that does not exist (credentials are "
        "server-global)."
    )


def test_oauth_status_does_not_leak_redirect_uri(authed_status_client):
    """B19: the server-global OAuth redirect_uri is deployment configuration
    and must not be exposed to every authenticated caller via a status check."""
    resp = authed_status_client.get("/api/auth/gmail/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "redirect_uri" not in body or not body["redirect_uri"], (
        f"B19 regression: status endpoint leaks server-global redirect_uri "
        f"({body.get('redirect_uri')!r}) to any authenticated caller."
    )
