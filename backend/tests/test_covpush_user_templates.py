"""Coverage-push + bug-hunt: api/user_templates_endpoints.py.

TDD: failing tests first for every bug found, then minimal fixes.

Bugs hunted here:
  * ``create_user_template`` stores ``steps_schema``/``inputs_schema`` (lists of
    pydantic models) directly into JSON columns — json.dumps raises TypeError
    on flush, so every template created with a structured steps_schema 500'd.
  * ``list_user_templates`` accepts a ``complexity`` filter but the model has
    no such column; the filter silently raised AttributeError → 500. (Already
    removed in an earlier fix — tests pin the current behavior.)
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import TemplateExecution, TemplateVersion, User, UserRole, UserStatus, WorkflowTemplate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_user(db, user_id=None, role="member"):
    u = User(
        id=user_id or f"u-{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        first_name="First",
        last_name="Last",
        role=role,
        status=UserStatus.ACTIVE,
        tenant_id="t1",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_template(db, owner_id, name="T", category="automation",
                   is_public=False, steps=None, input_schema=None):
    t = WorkflowTemplate(
        id=f"tpl-{uuid.uuid4().hex[:12]}",
        name=name,
        description="desc",
        category=category,
        icon="default",
        author_id=owner_id,
        steps=steps or [],
        input_schema=input_schema,
        is_public=is_public,
        version="1.0.0",
        usage_count=0,
        rating=0.0,
        rating_count=0,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _valid_create_payload(**overrides):
    payload = {
        "name": "My Template",
        "description": "A useful template",
        "category": "automation",
        "complexity": "intermediate",
        "tags": ["x"],
        "template_json": {"nodes": [{"id": "n1"}]},
        "inputs_schema": [],
        "steps_schema": [],
        "output_schema": {},
        "is_public": False,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def users():
    return {}


@pytest.fixture
def client(db_session, users):
    from core.auth import get_current_user
    from core.database import get_db
    from api.user_templates_endpoints import router

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db_session

    def override_user():
        return users["current"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as c:
        yield c


class _BrokenDB:
    def query(self, *a, **k):
        raise RuntimeError("db down")

    def add(self, *a, **k):
        raise RuntimeError("db down")

    def commit(self, *a, **k):
        raise RuntimeError("db down")

    def refresh(self, *a, **k):
        raise RuntimeError("db down")

    def rollback(self, *a, **k):
        pass


@pytest.fixture
def broken_client(db_session, users):
    from core.auth import get_current_user
    from core.database import get_db
    from api.user_templates_endpoints import router

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield _BrokenDB()

    def override_user():
        return users["current"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as c:
        yield c


class TestDatabaseFailurePaths:
    def test_create_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.post("/api/user/templates", json=_valid_create_payload())
        assert res.status_code == 500
        assert res.json()["detail"]["success"] is False

    def test_list_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.get("/api/user/templates")
        assert res.status_code == 500

    def test_stats_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.get("/api/user/templates/stats")
        assert res.status_code == 500

    def test_get_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.get("/api/user/templates/tpl-1")
        assert res.status_code == 500

    def test_update_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.put("/api/user/templates/tpl-1", json={"name": "x"})
        assert res.status_code == 500

    def test_delete_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.delete("/api/user/templates/tpl-1")
        assert res.status_code == 500

    def test_publish_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.post(
            "/api/user/templates/tpl-1/publish", json={"visibility": "public"}
        )
        assert res.status_code == 500

    def test_duplicate_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.post(
            "/api/user/templates/tpl-1/duplicate", json={"name": "c"}
        )
        assert res.status_code == 500

    def test_versions_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.get("/api/user/templates/tpl-1/versions")
        assert res.status_code == 500

    def test_rate_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.post("/api/user/templates/tpl-1/rate?rating=3")
        assert res.status_code == 500


class _HTTPExceptionDB(_BrokenDB):
    def __init__(self, exc):
        self._exc = exc

    def query(self, *a, **k):
        raise self._exc

    def add(self, *a, **k):
        raise self._exc

    def commit(self, *a, **k):
        raise self._exc

    def refresh(self, *a, **k):
        raise self._exc


@pytest.fixture
def httpexc_client(db_session, users):
    from fastapi import HTTPException
    from core.auth import get_current_user
    from core.database import get_db
    from api.user_templates_endpoints import router

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield _HTTPExceptionDB(HTTPException(status_code=500, detail="boom"))

    def override_user():
        return users["current"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as c:
        yield c


class TestHTTPExceptionPropagation:
    def test_create_rethrows_httpexception(self, httpexc_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = httpexc_client.post("/api/user/templates", json=_valid_create_payload())
        assert res.status_code == 500

    def test_list_rethrows_httpexception(self, httpexc_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = httpexc_client.get("/api/user/templates")
        assert res.status_code == 500

    def test_stats_rethrows_httpexception(self, httpexc_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = httpexc_client.get("/api/user/templates/stats")
        assert res.status_code == 500


# ===========================================================================
# POST /api/user/templates (create)
# ===========================================================================
class TestCreateTemplate:
    def test_create_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        res = client.post("/api/user/templates", json=_valid_create_payload())
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "My Template"
        assert body["author_id"] == u.id
        assert body["version"] == "1.0.0"
        assert body["template_json"]["steps"] == {"nodes": [{"id": "n1"}]}
        row = db_session.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == body["id"]
        ).first()
        assert row is not None
        version = db_session.query(TemplateVersion).filter(
            TemplateVersion.template_id == body["id"]
        ).first()
        assert version is not None
        assert version.change_summary == "Initial version"

    def test_create_with_steps_schema_persists(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        payload = _valid_create_payload(
            steps_schema=[
                {
                    "id": "step1",
                    "name": "Fetch",
                    "step_type": "action",
                    "service": "github",
                    "action": "get",
                    "parameters": [{"name": "repo", "type": "string"}],
                }
            ],
            inputs_schema=[
                {"name": "repo", "type": "string", "required": True}
            ],
        )
        res = client.post("/api/user/templates", json=payload)
        assert res.status_code == 201
        row = db_session.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == res.json()["id"]
        ).first()
        assert row.steps[0]["id"] == "step1"
        assert row.steps[0]["parameters"][0]["name"] == "repo"

    def test_create_invalid_payload_422(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        res = client.post("/api/user/templates", json={"name": ""})
        assert res.status_code == 422


# ===========================================================================
# GET /api/user/templates (list)
# ===========================================================================
class TestListTemplates:
    def test_list_own_and_public(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        other = _make_user(db_session)
        _make_template(db_session, u.id, name="mine")
        _make_template(db_session, other.id, name="theirs-private")
        _make_template(db_session, other.id, name="theirs-public", is_public=True)
        res = client.get("/api/user/templates")
        assert res.status_code == 200
        names = {t["name"] for t in res.json()}
        assert names == {"mine", "theirs-public"}

    def test_list_filters(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        _make_template(db_session, u.id, name="auto", category="automation")
        _make_template(db_session, u.id, name="data", category="data_processing")
        res = client.get("/api/user/templates", params={"category": "automation"})
        assert [t["name"] for t in res.json()] == ["auto"]

    def test_list_featured_only(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        plain = _make_template(db_session, u.id, name="plain")
        featured = _make_template(db_session, u.id, name="featured")
        featured.is_approved = True
        db_session.commit()
        res = client.get("/api/user/templates", params={"featured_only": "true"})
        assert [t["name"] for t in res.json()] == ["featured"]

    def test_list_search(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        _make_template(db_session, u.id, name="Sales Automation")
        _make_template(db_session, u.id, name="Inventory")
        res = client.get("/api/user/templates", params={"search": "sales"})
        assert [t["name"] for t in res.json()] == ["Sales Automation"]

    def test_list_pagination(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        for i in range(3):
            _make_template(db_session, u.id, name=f"t{i}")
        res = client.get("/api/user/templates", params={"limit": 2, "offset": 0})
        assert len(res.json()) == 2

    def test_list_does_not_expose_other_private(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        other = _make_user(db_session)
        _make_template(db_session, other.id, name="secret-private")
        res = client.get("/api/user/templates")
        assert res.json() == []


# ===========================================================================
# GET /api/user/templates/stats
# ===========================================================================
class TestTemplateStats:
    def test_stats_empty(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        res = client.get("/api/user/templates/stats")
        assert res.status_code == 200
        body = res.json()
        assert body["total_templates"] == 0
        assert body["average_rating"] == 0.0
        assert body["most_used_template"] is None

    def test_stats_with_data(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id, name="Popular")
        t.usage_count = 5
        t.rating = 4.0
        t.rating_count = 2
        db_session.commit()
        res = client.get("/api/user/templates/stats")
        body = res.json()
        assert body["total_templates"] == 1
        assert body["public_templates"] == 0
        assert body["private_templates"] == 1
        assert body["total_usage"] == 5
        assert body["average_rating"] == 4.0
        assert body["most_used_template"]["name"] == "Popular"


# ===========================================================================
# GET /{template_id}
# ===========================================================================
class TestGetTemplate:
    def test_get_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.get("/api/user/templates/tpl-ghost")
        assert res.status_code == 404

    def test_get_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id, name="Detail")
        res = client.get(f"/api/user/templates/{t.id}")
        assert res.status_code == 200
        assert res.json()["name"] == "Detail"


# ===========================================================================
# PUT /{template_id}
# ===========================================================================
class TestUpdateTemplate:
    def test_update_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.put("/api/user/templates/tpl-ghost", json={"name": "x"})
        assert res.status_code == 404

    def test_update_403_for_other_user(self, client, db_session, users):
        owner = _make_user(db_session)
        t = _make_template(db_session, owner.id)
        users["current"] = _make_user(db_session)
        res = client.put(f"/api/user/templates/{t.id}", json={"name": "x"})
        assert res.status_code == 403

    def test_update_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id, name="Before")
        res = client.put(
            f"/api/user/templates/{t.id}",
            json={"name": "After", "description": "new desc", "category": "ai_ml"},
        )
        assert res.status_code == 200
        assert res.json()["name"] == "After"
        db_session.refresh(t)
        assert t.category == "ai_ml"

    def test_update_with_change_description_bumps_version(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id, name="V")
        res = client.put(
            f"/api/user/templates/{t.id}",
            json={"name": "V2", "change_description": "renamed"},
        )
        assert res.status_code == 200
        assert res.json()["version"] == "1.0.1"
        v = db_session.query(TemplateVersion).filter(
            TemplateVersion.template_id == t.id
        ).all()
        assert len(v) == 1
        assert v[0].change_summary == "renamed"

    def test_update_unsupported_fields_skipped(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id)
        res = client.put(
            f"/api/user/templates/{t.id}",
            json={"name": "ok", "tags": ["x"], "template_json": {"a": 1}},
        )
        assert res.status_code == 200
        assert res.json()["name"] == "ok"


# ===========================================================================
# DELETE /{template_id}
# ===========================================================================
class TestDeleteTemplate:
    def test_delete_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.delete("/api/user/templates/tpl-ghost")
        assert res.status_code == 404

    def test_delete_403_for_other_user(self, client, db_session, users):
        owner = _make_user(db_session)
        t = _make_template(db_session, owner.id)
        users["current"] = _make_user(db_session)
        res = client.delete(f"/api/user/templates/{t.id}")
        assert res.status_code == 403

    def test_delete_success_removes_related(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id)
        db_session.add(TemplateVersion(
            template_id=t.id, version_number=1, name="v", created_by=u.id,
            change_summary="x",
        ))
        db_session.add(TemplateExecution(
            template_id=t.id, user_id=u.id, execution_status="completed",
        ))
        db_session.commit()
        res = client.delete(f"/api/user/templates/{t.id}")
        assert res.status_code == 204
        assert db_session.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == t.id
        ).first() is None
        assert db_session.query(TemplateVersion).filter(
            TemplateVersion.template_id == t.id
        ).first() is None
        assert db_session.query(TemplateExecution).filter(
            TemplateExecution.template_id == t.id
        ).first() is None


# ===========================================================================
# POST /{template_id}/publish
# ===========================================================================
class TestPublishTemplate:
    def test_publish_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.post(
            "/api/user/templates/tpl-ghost/publish",
            json={"visibility": "public"},
        )
        assert res.status_code == 404

    def test_publish_403_for_other_user(self, client, db_session, users):
        owner = _make_user(db_session)
        t = _make_template(db_session, owner.id)
        users["current"] = _make_user(db_session)
        res = client.post(
            f"/api/user/templates/{t.id}/publish",
            json={"visibility": "public"},
        )
        assert res.status_code == 403

    def test_publish_public(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id)
        res = client.post(
            f"/api/user/templates/{t.id}/publish",
            json={"visibility": "public"},
        )
        assert res.status_code == 200
        db_session.refresh(t)
        assert t.is_public is True

    def test_publish_private(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id, is_public=True)
        res = client.post(
            f"/api/user/templates/{t.id}/publish",
            json={"visibility": "private"},
        )
        assert res.status_code == 200
        db_session.refresh(t)
        assert t.is_public is False

    def test_publish_featured_as_admin(self, client, db_session, users):
        admin = _make_user(db_session, role=UserRole.SUPER_ADMIN)
        users["current"] = admin
        t = _make_template(db_session, admin.id)
        res = client.post(
            f"/api/user/templates/{t.id}/publish",
            json={"visibility": "public", "featured": True},
        )
        assert res.status_code == 200
        db_session.refresh(t)
        assert t.is_approved is True

    def test_publish_featured_denied_for_member(self, client, db_session, users):
        u = _make_user(db_session, role="member")
        users["current"] = u
        t = _make_template(db_session, u.id)
        res = client.post(
            f"/api/user/templates/{t.id}/publish",
            json={"visibility": "public", "featured": True},
        )
        assert res.status_code == 403


# ===========================================================================
# POST /{template_id}/duplicate
# ===========================================================================
class TestDuplicateTemplate:
    def test_duplicate_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.post(
            "/api/user/templates/tpl-ghost/duplicate", json={"name": "copy"}
        )
        assert res.status_code == 404

    def test_duplicate_403_private_of_other(self, client, db_session, users):
        owner = _make_user(db_session)
        t = _make_template(db_session, owner.id)
        users["current"] = _make_user(db_session)
        res = client.post(
            f"/api/user/templates/{t.id}/duplicate", json={"name": "copy"}
        )
        assert res.status_code == 403

    def test_duplicate_public_of_other(self, client, db_session, users):
        owner = _make_user(db_session)
        t = _make_template(db_session, owner.id, name="Orig", is_public=True)
        users["current"] = _make_user(db_session)
        res = client.post(
            f"/api/user/templates/{t.id}/duplicate",
            json={"name": "My Copy", "description": "forked"},
        )
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "My Copy"
        assert body["author_id"] == users["current"].id
        assert body["is_public"] is False
        dup = db_session.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == body["id"]
        ).first()
        assert dup is not None
        assert dup.author_id == users["current"].id

    def test_duplicate_own_private(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id, steps=[{"id": "s1"}])
        res = client.post(
            f"/api/user/templates/{t.id}/duplicate", json={"name": "own copy"}
        )
        assert res.status_code == 201
        assert res.json()["version"] == "1.0.0"


# ===========================================================================
# GET /{template_id}/versions
# ===========================================================================
class TestTemplateVersions:
    def test_versions_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.get("/api/user/templates/tpl-ghost/versions")
        assert res.status_code == 404

    def test_versions_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id)
        db_session.add(TemplateVersion(
            template_id=t.id, version_number=1, name="v1",
            description="first", created_by=u.id, change_summary="init",
        ))
        db_session.commit()
        res = client.get(f"/api/user/templates/{t.id}/versions")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["version"] == "1"
        assert body[0]["change_description"] == "init"


# ===========================================================================
# POST /{template_id}/rate
# ===========================================================================
class TestRateTemplate:
    def test_rate_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.post("/api/user/templates/tpl-ghost/rate?rating=5")
        assert res.status_code == 404

    def test_rate_invalid_out_of_range(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.post("/api/user/templates/tpl-ghost/rate?rating=7")
        assert res.status_code == 422

    def test_rate_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id)
        res = client.post(f"/api/user/templates/{t.id}/rate?rating=4")
        assert res.status_code == 200
        body = res.json()
        assert body["new_rating"] == 4.0
        assert body["rating_count"] == 1

    def test_rate_accumulates_average(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        t = _make_template(db_session, u.id)
        client.post(f"/api/user/templates/{t.id}/rate?rating=2")
        res = client.post(f"/api/user/templates/{t.id}/rate?rating=4")
        assert res.status_code == 200
        assert res.json()["new_rating"] == 3.0
        assert res.json()["rating_count"] == 2
