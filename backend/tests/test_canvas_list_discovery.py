"""
Canvas list discovery — search, derived titles, snippets, pagination.

The user journey this locks in: a user with a growing canvas count opens
/canvas (GET /api/canvas/), types a search, and finds the ONE canvas they
mean — matched by title, by body content (most agent-created canvases have no
title), or by id — with a human display title (never a raw UUID) and a
snippet windowed around the match.

Covers tools/canvas_crud_tool.list_canvases after the rewrite from
"materialize every audit row" to a ROW_NUMBER() latest-per-canvas window with
Python-side search/paging.
"""
import asyncio
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from core.models import Canvas, CanvasAudit, Tenant, User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def discovery_user(db_session):
    tenant = Tenant(id=f"t-{uuid.uuid4()}", name="Disc Tenant",
                    subdomain=f"disc-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        id=f"u-{uuid.uuid4()}",
        email=f"disc-{uuid.uuid4()}@example.com",
        hashed_password="hashed_password_here",
        first_name="Test",
        last_name="User",
        role="member",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    return {"user": user, "tenant": tenant}


@pytest.fixture
def patched_session(db_session):
    """Route core.database.get_db_session to the test session so the tool's
    internal `with get_db_session() as db:` sees our rows."""
    import core.database as db_mod

    original = db_mod.get_db_session

    @contextmanager
    def _test_session():
        yield db_session

    db_mod.get_db_session = _test_session
    try:
        yield db_session
    finally:
        db_mod.get_db_session = original


BASE = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)


def _audit(db, canvas_id, tenant_id, user_id, action_type="present",
           canvas_type="docs", details=None, at=None, audit_id=None):
    row = CanvasAudit(
        id=audit_id or f"a-{uuid.uuid4()}",
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        canvas_type=canvas_type,
        action_type=action_type,
        user_id=user_id,
        details_json=details or {},
        created_at=at or BASE,
    )
    db.add(row)
    return row


def _run(user_id, **kwargs):
    from tools.canvas_crud_tool import list_canvases
    return asyncio.run(list_canvases(user_id, **kwargs))


# ============================================================================
# Core listing semantics (must match the pre-rewrite behavior)
# ============================================================================

class TestListSemantics:
    def test_latest_audit_per_canvas_wins(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-multi", t.id, u.id, "present", "docs",
               {"title": "Old title", "content": "v1"}, at=BASE)
        _audit(db_session, "cv-multi", t.id, u.id, "update", "docs",
               {"title": "New title", "content": "v2"}, at=BASE + timedelta(minutes=5))
        _audit(db_session, "cv-multi", t.id, u.id, "update", "docs",
               {"title": "Newest title", "content": "v3"}, at=BASE + timedelta(minutes=10))

        result = _run(str(u.id))
        assert result["success"] is True
        assert result["total"] == 1
        item = result["canvases"][0]
        assert item["canvas_id"] == "cv-multi"
        assert item["action_type"] == "update"
        assert item["title"] == "Newest title"
        assert item["display_title"] == "Newest title"

    def test_deleted_excluded_by_default_included_on_flag(
        self, db_session, discovery_user, patched_session
    ):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-alive", t.id, u.id, "present", "docs",
               {"title": "Alive", "content": "x"}, at=BASE)
        _audit(db_session, "cv-dead", t.id, u.id, "present", "docs",
               {"title": "Dead", "content": "y"}, at=BASE + timedelta(minutes=1))
        _audit(db_session, "cv-dead", t.id, u.id, "delete", "docs",
               {"deleted": True}, at=BASE + timedelta(minutes=2))

        result = _run(str(u.id))
        assert [c["canvas_id"] for c in result["canvases"]] == ["cv-alive"]

        result = _run(str(u.id), include_deleted=True)
        ids = [c["canvas_id"] for c in result["canvases"]]
        assert set(ids) == {"cv-alive", "cv-dead"}
        dead = next(c for c in result["canvases"] if c["canvas_id"] == "cv-dead")
        assert dead["deleted"] is True

    def test_recency_order_newest_first(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        for i, cid in enumerate(["cv-old", "cv-mid", "cv-new"]):
            _audit(db_session, cid, t.id, u.id, "present", "docs",
                   {"title": cid, "content": "x"}, at=BASE + timedelta(hours=i))

        result = _run(str(u.id))
        assert [c["canvas_id"] for c in result["canvases"]] == \
            ["cv-new", "cv-mid", "cv-old"]

    def test_type_filter_still_filters(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-doc", t.id, u.id, "present", "docs",
               {"title": "Doc", "content": "x"}, at=BASE)
        _audit(db_session, "cv-sheet", t.id, u.id, "present", "sheets",
               {"title": "Sheet", "data": [[1, 2]]}, at=BASE + timedelta(minutes=1))

        result = _run(str(u.id), canvas_type="sheets")
        assert [c["canvas_id"] for c in result["canvases"]] == ["cv-sheet"]

    def test_other_users_canvases_never_leak(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        stranger = User(
            id=f"u-{uuid.uuid4()}", email=f"s-{uuid.uuid4()}@example.com",
            hashed_password="x", first_name="S", last_name="S",
            role="member", status="active",
        )
        db_session.add(stranger)
        db_session.commit()
        _audit(db_session, "cv-mine", t.id, u.id, "present", "docs",
               {"title": "Mine", "content": "x"}, at=BASE)
        _audit(db_session, "cv-theirs", t.id, stranger.id, "present", "docs",
               {"title": "Theirs", "content": "y"}, at=BASE)

        result = _run(str(u.id))
        assert [c["canvas_id"] for c in result["canvases"]] == ["cv-mine"]


# ============================================================================
# Search (the discovery journey)
# ============================================================================

class TestSearch:
    def test_search_matches_title(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "docs",
               {"title": "Q3 Budget Review", "content": "numbers"}, at=BASE)
        _audit(db_session, "cv-2", t.id, u.id, "present", "docs",
               {"title": "Onboarding Notes", "content": "steps"}, at=BASE + timedelta(minutes=1))

        result = _run(str(u.id), q="budget")
        assert [c["canvas_id"] for c in result["canvases"]] == ["cv-1"]

    def test_search_matches_body_of_untitled_canvas(
        self, db_session, discovery_user, patched_session
    ):
        """The core findability case: agent-created canvases usually have no
        title — content is the only way to find them."""
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "docs",
               {"content": "Quarterly procurement plan for the Lisbon office"}, at=BASE)
        _audit(db_session, "cv-2", t.id, u.id, "present", "docs",
               {"content": "Grocery list"}, at=BASE + timedelta(minutes=1))

        result = _run(str(u.id), q="lisbon")
        assert [c["canvas_id"] for c in result["canvases"]] == ["cv-1"]

    def test_search_matches_canvas_id(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "3fa85f64-5717-4562-b3fc-1a2b3c4d5e6f", t.id, u.id,
               "present", "docs", {"content": "doc"}, at=BASE)
        _audit(db_session, "other-id", t.id, u.id, "present", "docs",
               {"content": "doc2"}, at=BASE + timedelta(minutes=1))

        result = _run(str(u.id), q="3fa85f64")
        assert [c["canvas_id"] for c in result["canvases"]] == \
            ["3fa85f64-5717-4562-b3fc-1a2b3c4d5e6f"]

    def test_search_is_case_insensitive(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "docs",
               {"content": "LisBON office"}, at=BASE)
        result = _run(str(u.id), q="lisbon")
        assert result["total"] == 1

    def test_search_no_match_returns_empty_not_error(
        self, db_session, discovery_user, patched_session
    ):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "docs",
               {"content": "doc"}, at=BASE)
        result = _run(str(u.id), q="zzz-no-match")
        assert result["success"] is True
        assert result["canvases"] == []
        assert result["total"] == 0

    def test_search_covers_canvas_row_content_fallback(
        self, db_session, discovery_user, patched_session
    ):
        """chat_draft_to_canvas stores the document ONLY on the Canvas row —
        the audit details carry no body key. Those canvases must still be
        findable by content (same ladder as read_canvas)."""
        u, t = discovery_user["user"], discovery_user["tenant"]
        db_session.add(Canvas(
            id="cv-draft", tenant_id=t.id, created_by=u.id, name="Draft.docx",
            canvas_type="docs", content="Merger termsheet v4 for Acme Corp",
        ))
        _audit(db_session, "cv-draft", t.id, u.id, "present", "docs",
               {"source": "chat_draft"}, at=BASE)
        db_session.commit()

        result = _run(str(u.id), q="acme")
        assert [c["canvas_id"] for c in result["canvases"]] == ["cv-draft"]
        assert "Acme" in result["canvases"][0]["snippet"]


# ============================================================================
# Display titles — never a raw UUID
# ============================================================================

class TestDisplayTitle:
    def test_untitled_doc_derives_first_line(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "docs",
               {"content": "# Launch Checklist\n- ship the thing\n- retire the pager"}, at=BASE)
        result = _run(str(u.id))
        assert result["canvases"][0]["display_title"] == "Launch Checklist"

    def test_email_subject_derives_title(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "email",
               {"content": {"to": "ceo@example.com", "subject": "Board update",
                            "body": "hi"}}, at=BASE)
        result = _run(str(u.id))
        assert result["canvases"][0]["display_title"] == "Board update"

    def test_email_recipient_fallback_when_no_subject(
        self, db_session, discovery_user, patched_session
    ):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "email",
               {"content": {"to": "ceo@example.com, cfo@example.com", "body": "hi"}},
               at=BASE)
        result = _run(str(u.id))
        assert result["canvases"][0]["display_title"] == "Email to ceo@example.com"

    def test_canvas_row_name_used_when_no_audit_title(
        self, db_session, discovery_user, patched_session
    ):
        u, t = discovery_user["user"], discovery_user["tenant"]
        db_session.add(Canvas(
            id="cv-office", tenant_id=t.id, created_by=u.id, name="Budget.xlsx",
            canvas_type="sheets", content={"cells": []},
        ))
        _audit(db_session, "cv-office", t.id, u.id, "present", "sheets",
               {"content": {"cells": []}}, at=BASE)
        db_session.commit()
        result = _run(str(u.id))
        assert result["canvases"][0]["display_title"] == "Budget.xlsx"

    def test_typed_fallback_when_no_title_no_content(
        self, db_session, discovery_user, patched_session
    ):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "sheets",
               {"title": None, "content": ""}, at=BASE)
        result = _run(str(u.id))
        item = result["canvases"][0]
        assert item["display_title"] == "Untitled sheets canvas"
        assert item["snippet"] is None

    def test_long_first_line_capped(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "docs",
               {"content": "A" * 300}, at=BASE)
        result = _run(str(u.id))
        assert len(result["canvases"][0]["display_title"]) <= 81  # 80 + ellipsis


# ============================================================================
# Snippets + pagination
# ============================================================================

class TestSnippetAndPagination:
    def test_snippet_windows_around_match(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        filler = "lorem ipsum dolor sit amet. " * 20  # ~560 chars before the needle
        _audit(db_session, "cv-1", t.id, u.id, "present", "docs",
               {"content": f"{filler}the NEEDLE is here{filler}"}, at=BASE)
        result = _run(str(u.id), q="needle")
        snippet = result["canvases"][0]["snippet"]
        assert "NEEDLE" in snippet
        assert snippet.startswith("…") and snippet.endswith("…")

    def test_snippet_of_unsearched_list_is_prefix(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db_session, "cv-1", t.id, u.id, "present", "docs",
               {"content": "short body"}, at=BASE)
        result = _run(str(u.id))
        assert result["canvases"][0]["snippet"] == "short body"

    def test_pagination_limit_and_offset(self, db_session, discovery_user, patched_session):
        u, t = discovery_user["user"], discovery_user["tenant"]
        for i in range(5):
            _audit(db_session, f"cv-{i}", t.id, u.id, "present", "docs",
                   {"content": f"canvas number {i}"}, at=BASE + timedelta(minutes=i))

        page1 = _run(str(u.id), limit=2, offset=0)
        assert page1["total"] == 5
        assert page1["count"] == 2
        assert [c["canvas_id"] for c in page1["canvases"]] == ["cv-4", "cv-3"]

        page3 = _run(str(u.id), limit=2, offset=4)
        assert page3["count"] == 1
        assert [c["canvas_id"] for c in page3["canvases"]] == ["cv-0"]

    def test_search_total_counts_all_matches_not_page(
        self, db_session, discovery_user, patched_session
    ):
        u, t = discovery_user["user"], discovery_user["tenant"]
        for i in range(3):
            _audit(db_session, f"cv-{i}", t.id, u.id, "present", "docs",
                   {"content": f"acme report {i}"}, at=BASE + timedelta(minutes=i))
        result = _run(str(u.id), q="acme", limit=1)
        assert result["total"] == 3
        assert result["count"] == 1


# ============================================================================
# Route boundary — q/limit/offset must flow through GET /api/canvas/
# ============================================================================

class TestRouteBoundary:
    @pytest.fixture
    def route_client(self, db_session, discovery_user, patched_session):
        from api.canvas_routes import router
        from core.auth import get_current_user
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(router)
        user = discovery_user["user"]
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            app.dependency_overrides.clear()

    def _seed(self, db, discovery_user):
        u, t = discovery_user["user"], discovery_user["tenant"]
        _audit(db, "cv-hit", t.id, u.id, "present", "docs",
               {"content": "acme termsheet"}, at=BASE)
        _audit(db, "cv-miss", t.id, u.id, "present", "docs",
               {"content": "grocery list"}, at=BASE + timedelta(minutes=1))

    def test_route_passes_q_and_returns_derived_fields(
        self, db_session, discovery_user, patched_session, route_client
    ):
        self._seed(db_session, discovery_user)
        resp = route_client.get("/api/canvas/?q=acme")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["canvases"][0]["canvas_id"] == "cv-hit"
        # The discovery fields ride along on the route response.
        assert body["canvases"][0]["display_title"] == "acme termsheet"
        assert "acme" in body["canvases"][0]["snippet"]

    def test_route_pagination_params(self, db_session, discovery_user, patched_session, route_client):
        u, t = discovery_user["user"], discovery_user["tenant"]
        for i in range(3):
            _audit(db_session, f"cv-{i}", t.id, u.id, "present", "docs",
                   {"content": f"doc {i}"}, at=BASE + timedelta(minutes=i))
        resp = route_client.get("/api/canvas/?limit=1&offset=1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["count"] == 1
        assert body["canvases"][0]["canvas_id"] == "cv-1"

    def test_route_rejects_over_limit(self, db_session, discovery_user, patched_session, route_client):
        resp = route_client.get("/api/canvas/?limit=5000")
        assert resp.status_code == 422  # FastAPI validation (le=200)
