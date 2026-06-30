"""
P2.2 regression tests — notifications REST surface.

Verifies the three endpoints power the Header bell correctly. Uses MagicMock
return_value configuration rather than hand-rolled side-effects so the
SQLAlchemy query chain (.filter().order_by().limit().all() etc.) resolves
predictably regardless of how many chained calls the endpoint makes.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _chain(rows_return=None, first_return=None, count_return=0):
    """Build a MagicMock whose every chained call returns itself, except
    .all() / .count() / .first() which return the supplied values.
    """
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value = chain
    chain.all.return_value = rows_return or []
    chain.first.return_value = first_return
    chain.count.return_value = count_return
    return chain


def _make_row(*, id="n-1", user_id="u-1", read=False, title="t", message="m", **kw):
    n = MagicMock()
    n.id = id
    n.user_id = user_id
    n.read = read
    n.read_at = None
    n.created_at = kw.get("created_at", datetime.now(timezone.utc))
    n.metadata_json = kw.get("metadata_json", {})
    n.type = kw.get("type", "info")
    n.title = title
    n.message = message
    n.action_url = kw.get("action_url")
    n.action_label = kw.get("action_label")
    return n


@pytest.fixture
def app_with_deps():
    """Mount the notifications router with get_current_user + get_db overridden."""
    from api import notifications_routes as nr

    fake_user = MagicMock()
    fake_user.id = "u-1"

    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()

    app = FastAPI()
    app.include_router(nr.router)
    app.dependency_overrides[nr.get_current_user] = lambda: fake_user
    app.dependency_overrides[nr.get_db] = lambda: db
    return app, db


def test_list_returns_user_rows_and_unread_count(app_with_deps):
    app, db = app_with_deps
    rows = [
        _make_row(id="n-1", user_id="u-1", read=False, title="First"),
        _make_row(id="n-2", user_id="u-1", read=True, title="Second"),
    ]
    # First chained query: the list. Second chained query: the unread count.
    # MagicMock .query returns the same chain each time, so we configure the
    # side_effect to return two different chains in call order.
    list_chain = _chain(rows_return=rows)
    count_chain = _chain(count_return=1)
    db.query.side_effect = [list_chain, count_chain]

    client = TestClient(app)
    r = client.get("/api/notifications")
    assert r.status_code == 200, r.text
    body = r.json()
    data = body.get("data", body)
    assert len(data["notifications"]) == 2
    assert data["unread_count"] == 1


def test_list_unread_only_filter_param_accepted(app_with_deps):
    """unread_only=True should not 500; we just verify the call succeeds."""
    app, db = app_with_deps
    db.query.side_effect = [_chain(rows_return=[]), _chain(count_return=0)]

    client = TestClient(app)
    r = client.get("/api/notifications?unread_only=true&limit=10")
    assert r.status_code == 200


def test_mark_read_404_when_row_missing(app_with_deps):
    """If the lookup returns no row (ownership or non-existent), 404."""
    app, db = app_with_deps
    db.query.return_value = _chain(first_return=None)

    client = TestClient(app)
    r = client.post("/api/notifications/does-not-exist/read")
    assert r.status_code == 404


def test_mark_read_success_flips_flag(app_with_deps):
    app, db = app_with_deps
    target = _make_row(id="n-1", read=False)
    db.query.return_value = _chain(first_return=target)

    client = TestClient(app)
    r = client.post("/api/notifications/n-1/read")
    assert r.status_code == 200
    assert target.read is True
    assert target.read_at is not None
    db.commit.assert_called()


def test_mark_read_idempotent_when_already_read(app_with_deps):
    """Marking an already-read row should not re-commit."""
    app, db = app_with_deps
    target = _make_row(id="n-1", read=True)
    db.query.return_value = _chain(first_return=target)

    client = TestClient(app)
    r = client.post("/api/notifications/n-1/read")
    assert r.status_code == 200
    db.commit.assert_not_called()


def test_mark_all_read_returns_count(app_with_deps):
    app, db = app_with_deps
    # The endpoint applies a `read == False` filter; the mock chain returns
    # whatever rows we hand it regardless of filter args. So feed it the two
    # unread rows the filter would have selected in a real DB.
    unread_rows = [
        _make_row(id="n-1", read=False),
        _make_row(id="n-2", read=False),
    ]
    db.query.return_value = _chain(rows_return=unread_rows)

    client = TestClient(app)
    r = client.post("/api/notifications/read-all")
    assert r.status_code == 200
    body = r.json()
    data = body.get("data", body)
    assert data["marked_read"] == 2
    # Every previously-unread row is now read.
    assert all(row.read for row in unread_rows)
    db.commit.assert_called()


def test_list_type_filter_powers_graduation_celebration(app_with_deps):
    """P2.3: GET ?type=agent_graduated must narrow to that metadata type."""
    app, db = app_with_deps
    rows = [
        _make_row(
            id="g-1",
            metadata_json={"notification_type": "agent_graduated"},
            title="Promoted!",
        ),
        _make_row(
            id="other-1",
            metadata_json={"notification_type": "info"},
            title="Unrelated",
        ),
    ]
    db.query.side_effect = [_chain(rows_return=rows), _chain(count_return=1)]

    client = TestClient(app)
    r = client.get("/api/notifications?type=agent_graduated")
    assert r.status_code == 200
    body = r.json()
    data = body.get("data", body)
    # Only the agent_graduated row survives the Python-side filter.
    assert len(data["notifications"]) == 1
    assert data["notifications"][0]["id"] == "g-1"
