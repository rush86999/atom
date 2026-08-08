"""Coverage-push + bug-hunt: api/learning_plan_routes.py.

TDD: failing tests first for every bug found, then minimal fixes.

Bugs hunted here:
  * ``create_learning_plan`` built ``LearningPlan(...)`` with kwargs
    ``target_skill_level``/``milestones``/``assessment_criteria``/
    ``notion_page_id`` — none of these columns exist on the stub model in
    core/models.py, so EVERY plan creation raised
    ``TypeError: 'target_skill_level' is an invalid keyword argument`` → 500.
    The ``progress`` dict was also bound to the model's Integer ``progress``
    column → ProgrammingError on flush. Fix: persist the full payload inside
    the ``modules`` JSON column (sidecar) and keep the Integer column as the
    aggregate 0-100 percentage. core/models.py is out of scope (read-only).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import (
    IntegrationToken,
    LearningPlan,
    User,
    UserStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_user(db, user_id=None):
    u = User(
        id=user_id or f"u-{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        first_name="First",
        last_name="Last",
        role="member",
        status=UserStatus.ACTIVE,
        tenant_id="t1",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_token(db, user, provider="notion"):
    t = IntegrationToken(
        id=f"tok-{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        tenant_id=user.tenant_id,
        provider=provider,
        access_token="notion-secret-token",
        status="active",
    )
    db.add(t)
    db.commit()
    return t


def _modules_payload():
    return {
        "modules": [
            {
                "week": 1,
                "title": "Intro to Python",
                "objectives": ["Setup"],
                "resources": [{"type": "article", "url": "https://x"}],
                "exercises": ["Hello World"],
                "estimated_hours": 5.0,
            }
        ]
    }


def _patch_llm(monkeypatch, modules=None, exc=None):
    from core import llm_service as mod
    from types import SimpleNamespace

    async def _fake_generate_structured(self, **kwargs):
        if exc is not None:
            raise exc
        if modules is None:
            return None
        return SimpleNamespace(modules=modules)

    monkeypatch.setattr(mod.LLMService, "generate_structured", _fake_generate_structured)


@pytest.fixture
def users():
    return {}


@pytest.fixture
def client(db_session, users, monkeypatch):
    from core.auth import get_current_user
    from core.database import get_db
    from api.learning_plan_routes import router

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


def _valid_payload(**overrides):
    payload = {
        "topic": "Python",
        "current_skill_level": "beginner",
        "learning_goals": ["basics"],
        "time_commitment": "medium",
        "duration_weeks": 4,
        "preferred_format": ["articles", "videos"],
    }
    payload.update(overrides)
    return payload


class _BrokenDB:
    def query(self, *a, **k):
        raise RuntimeError("db down")

    def add(self, *a, **k):
        raise RuntimeError("db down")

    def commit(self, *a, **k):
        raise RuntimeError("db down")

    def refresh(self, *a, **k):
        raise RuntimeError("db down")


@pytest.fixture
def broken_client(users, monkeypatch):
    from core.auth import get_current_user
    from core.database import get_db
    from api.learning_plan_routes import router
    from core import llm_service as mod

    async def _fake_generate_structured(self, **kwargs):
        from types import SimpleNamespace
        return SimpleNamespace(modules=[])

    monkeypatch.setattr(mod.LLMService, "generate_structured", _fake_generate_structured)

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


class TestCreateDatabaseFailure:
    def test_create_500_on_db_error(self, broken_client, db_session, users):
        users["current"] = _make_user(db_session)
        res = broken_client.post("/api/v1/learning/plans", json=_valid_payload())
        assert res.status_code == 500


# ===========================================================================
# POST /api/v1/learning/plans (create)
# ===========================================================================
class TestCreateLearningPlan:
    def test_create_success_with_llm_modules(self, client, db_session, users, monkeypatch):
        from api.learning_plan_routes import LearningPlanModules, LearningModule
        u = _make_user(db_session)
        users["current"] = u
        module = LearningModule(
            week=1, title="Intro", objectives=["o1"], resources=[],
            exercises=["e1"], estimated_hours=5.0,
        )
        _patch_llm(monkeypatch, modules=[module])
        res = client.post("/api/v1/learning/plans", json=_valid_payload())
        assert res.status_code == 200
        body = res.json()
        assert body["plan_id"]
        assert body["topic"] == "Python"
        assert body["target_skill_level"] == "intermediate"
        assert len(body["modules"]) == 1
        assert body["milestones"]
        assert body["assessment_criteria"]

        row = db_session.query(LearningPlan).filter(
            LearningPlan.id == body["plan_id"]
        ).first()
        assert row is not None
        assert row.user_id == u.id
        assert row.progress == 0

    def test_create_falls_back_to_template_when_llm_fails(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        _patch_llm(monkeypatch, exc=RuntimeError("provider down"))
        res = client.post("/api/v1/learning/plans", json=_valid_payload(duration_weeks=2))
        assert res.status_code == 200
        body = res.json()
        assert len(body["modules"]) == 2
        assert body["modules"][0]["title"].startswith("Python")

    def test_create_falls_back_when_llm_returns_nothing(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        _patch_llm(monkeypatch, modules=None)
        res = client.post("/api/v1/learning/plans", json=_valid_payload())
        assert res.status_code == 200
        assert len(res.json()["modules"]) == 4

    def test_create_rejects_blank_topic(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        _patch_llm(monkeypatch, exc=RuntimeError())
        res = client.post("/api/v1/learning/plans", json=_valid_payload(topic="   "))
        assert res.status_code == 400

    def test_create_rejects_invalid_skill_level(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        _patch_llm(monkeypatch, exc=RuntimeError())
        res = client.post(
            "/api/v1/learning/plans",
            json=_valid_payload(current_skill_level="guru"),
        )
        assert res.status_code == 400

    def test_create_rejects_invalid_time_commitment(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        _patch_llm(monkeypatch, exc=RuntimeError())
        res = client.post(
            "/api/v1/learning/plans",
            json=_valid_payload(time_commitment="whenever"),
        )
        assert res.status_code == 400

    def test_create_with_notion_export(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        _make_token(db_session, u)
        _patch_llm(monkeypatch, exc=RuntimeError("fallback"))
        captured = {}

        async def _fake_export(plan, modules, notion_token):
            captured["token"] = notion_token
            captured["db_id"] = plan.notion_database_id
            return "page-123"

        monkeypatch.setattr(
            "api.learning_plan_routes.export_learning_plan_to_notion", _fake_export
        )
        res = client.post(
            "/api/v1/learning/plans",
            json=_valid_payload(notion_database_id="db-xyz"),
        )
        assert res.status_code == 200
        assert captured["token"] == "notion-secret-token"
        assert captured["db_id"] == "db-xyz"
        row = db_session.query(LearningPlan).filter(
            LearningPlan.id == res.json()["plan_id"]
        ).first()
        decoded = row.modules
        assert decoded["notion_page_id"] == "page-123"

    def test_create_with_notion_export_failure_still_saves(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        _make_token(db_session, u)
        _patch_llm(monkeypatch, exc=RuntimeError("fallback"))

        async def _fake_export(plan, modules, notion_token):
            return None

        monkeypatch.setattr(
            "api.learning_plan_routes.export_learning_plan_to_notion", _fake_export
        )
        res = client.post(
            "/api/v1/learning/plans",
            json=_valid_payload(notion_database_id="db-xyz"),
        )
        assert res.status_code == 200

    def test_create_with_notion_db_but_no_token(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        _patch_llm(monkeypatch, exc=RuntimeError("fallback"))
        res = client.post(
            "/api/v1/learning/plans",
            json=_valid_payload(notion_database_id="db-xyz"),
        )
        assert res.status_code == 200


# ===========================================================================
# GET /api/v1/learning/plans/{plan_id}
# ===========================================================================
class TestGetLearningPlan:
    def _create_plan(self, db, user, topic="Python"):
        plan = LearningPlan(
            id=f"lp-{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            topic=topic,
            current_skill_level="beginner",
            time_commitment="medium",
            duration_weeks=4,
            modules={
                "modules": [
                    {
                        "week": 1, "title": "Intro", "objectives": ["o"],
                        "resources": [], "exercises": ["e"], "estimated_hours": 1.0,
                    }
                ],
                "target_skill_level": "intermediate",
                "milestones": ["m1"],
                "assessment_criteria": ["c1"],
                "notion_page_id": None,
                "progress": {"completed_modules": [], "feedback_scores": {}, "time_spent": {}, "adjustments_made": []},
            },
            progress=0,
        )
        db.add(plan)
        db.commit()
        return plan

    def test_get_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.get("/api/v1/learning/plans/lp-ghost")
        assert res.status_code == 404

    def test_get_403_for_other_user(self, client, db_session, users):
        owner = _make_user(db_session)
        plan = self._create_plan(db_session, owner)
        users["current"] = _make_user(db_session)
        res = client.get(f"/api/v1/learning/plans/{plan.id}")
        assert res.status_code == 403

    def test_get_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        plan = self._create_plan(db_session, u)
        res = client.get(f"/api/v1/learning/plans/{plan.id}")
        assert res.status_code == 200
        body = res.json()
        assert body["plan_id"] == plan.id
        assert body["milestones"] == ["m1"]
        assert body["target_skill_level"] == "intermediate"
        assert len(body["modules"]) == 1


# ===========================================================================
# GET /api/v1/learning/plans (list)
# ===========================================================================
class TestListLearningPlans:
    def test_list_empty(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        res = client.get("/api/v1/learning/plans")
        assert res.status_code == 200
        assert res.json()["plans"] == []
        assert res.json()["total"] == 0

    def test_list_own_plans_only(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        other = _make_user(db_session)
        plan = LearningPlan(
            id=f"lp-{uuid.uuid4().hex[:8]}", user_id=u.id, topic="Mine",
            current_skill_level="beginner", time_commitment="medium", duration_weeks=4,
            modules={
                "modules": [], "target_skill_level": "intermediate",
                "milestones": [], "assessment_criteria": [],
                "notion_page_id": None, "progress": {"completed_modules": []},
            },
            progress=0,
        )
        other_plan = LearningPlan(
            id=f"lp-{uuid.uuid4().hex[:8]}", user_id=other.id, topic="Theirs",
            current_skill_level="beginner", time_commitment="medium", duration_weeks=4,
            modules={
                "modules": [], "target_skill_level": "intermediate",
                "milestones": [], "assessment_criteria": [],
                "notion_page_id": None, "progress": {},
            }, progress=0,
        )
        db_session.add_all([plan, other_plan])
        db_session.commit()
        res = client.get("/api/v1/learning/plans")
        body = res.json()
        assert body["total"] == 1
        assert body["plans"][0]["topic"] == "Mine"
        assert body["plans"][0]["progress"] == {"completed_modules": []}

    def test_list_pagination(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        for i in range(3):
            db_session.add(LearningPlan(
                id=f"lp-{uuid.uuid4().hex[:8]}", user_id=u.id, topic=f"t{i}",
                current_skill_level="beginner", time_commitment="medium",
                duration_weeks=2,
                modules={
                    "modules": [], "target_skill_level": "intermediate",
                    "milestones": [], "assessment_criteria": [],
                    "notion_page_id": None, "progress": {},
                }, progress=0,
            ))
        db_session.commit()
        res = client.get("/api/v1/learning/plans", params={"limit": 2, "offset": 0})
        assert len(res.json()["plans"]) == 2


# ===========================================================================
# POST /api/v1/learning/plans/{plan_id}/progress
# ===========================================================================
class TestUpdatePlanProgress:
    def _plan(self, db, user):
        plan = LearningPlan(
            id=f"lp-{uuid.uuid4().hex[:8]}", user_id=user.id, topic="T",
            current_skill_level="beginner", time_commitment="medium", duration_weeks=4,
            modules={
                "modules": [{"week": 1, "title": "x", "objectives": [], "resources": [], "exercises": [], "estimated_hours": 1.0}],
                "target_skill_level": "intermediate", "milestones": [], "assessment_criteria": [],
                "notion_page_id": None,
                "progress": {"completed_modules": [], "feedback_scores": {}, "time_spent": {}, "adjustments_made": []},
            },
            progress=0,
        )
        db.add(plan)
        db.commit()
        return plan

    def test_progress_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.post(
            "/api/v1/learning/plans/lp-ghost/progress",
            json={"module_week": 1, "feedback_score": 4, "time_spent_hours": 1.0},
        )
        assert res.status_code == 404

    def test_progress_403_for_other_user(self, client, db_session, users):
        owner = _make_user(db_session)
        plan = self._plan(db_session, owner)
        users["current"] = _make_user(db_session)
        res = client.post(
            f"/api/v1/learning/plans/{plan.id}/progress",
            json={"module_week": 1, "feedback_score": 4, "time_spent_hours": 1.0},
        )
        assert res.status_code == 403

    def test_progress_success_records_completion(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        plan = self._plan(db_session, u)
        res = client.post(
            f"/api/v1/learning/plans/{plan.id}/progress",
            json={"module_week": 2, "feedback_score": 4, "time_spent_hours": 3.0},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["progress"]["completed_modules"] == ["2"]
        assert body["progress"]["feedback_scores"]["2"] == 4
        assert body["adjustments"] == []

    def test_progress_duplicate_week_not_repeated(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        plan = self._plan(db_session, u)
        payload = {"module_week": 1, "feedback_score": 4, "time_spent_hours": 1.0}
        client.post(f"/api/v1/learning/plans/{plan.id}/progress", json=payload)
        res = client.post(f"/api/v1/learning/plans/{plan.id}/progress", json=payload)
        assert res.json()["progress"]["completed_modules"] == ["1"]

    def test_progress_low_score_triggers_remediation(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        plan = self._plan(db_session, u)
        res = client.post(
            f"/api/v1/learning/plans/{plan.id}/progress",
            json={"module_week": 1, "feedback_score": 2, "time_spent_hours": 4.0},
        )
        body = res.json()
        assert body["adjustments"][0]["type"] == "remediation"
        assert body["progress"]["adjustments_made"][0]["type"] == "remediation"

    def test_progress_high_score_fast_triggers_acceleration(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        plan = self._plan(db_session, u)
        res = client.post(
            f"/api/v1/learning/plans/{plan.id}/progress",
            json={"module_week": 1, "feedback_score": 5, "time_spent_hours": 1.0},
        )
        body = res.json()
        assert body["adjustments"][0]["type"] == "acceleration"

    def test_progress_legacy_plain_list_modules(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        plan = LearningPlan(
            id=f"lp-{uuid.uuid4().hex[:8]}", user_id=u.id, topic="Legacy",
            current_skill_level="beginner", time_commitment="medium",
            duration_weeks=4,
            modules=[
                {"week": 1, "title": "old", "objectives": [], "resources": [],
                 "exercises": [], "estimated_hours": 1.0}
            ],
            progress=0,
        )
        db_session.add(plan)
        db_session.commit()
        res = client.post(
            f"/api/v1/learning/plans/{plan.id}/progress",
            json={"module_week": 1, "feedback_score": 3, "time_spent_hours": 2.0},
        )
        assert res.status_code == 200
        assert res.json()["progress"]["completed_modules"] == ["1"]
        get = client.get(f"/api/v1/learning/plans/{plan.id}")
        assert get.status_code == 200
        assert get.json()["milestones"] == []

    def test_progress_non_dict_progress_reinitialized(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        plan = LearningPlan(
            id=f"lp-{uuid.uuid4().hex[:8]}", user_id=u.id, topic="BadProgress",
            current_skill_level="beginner", time_commitment="medium",
            duration_weeks=4,
            modules={
                "modules": [], "target_skill_level": "intermediate",
                "milestones": [], "assessment_criteria": [],
                "notion_page_id": None, "progress": 5,
            },
            progress=0,
        )
        db_session.add(plan)
        db_session.commit()
        res = client.post(
            f"/api/v1/learning/plans/{plan.id}/progress",
            json={"module_week": 1, "feedback_score": 3, "time_spent_hours": 2.0},
        )
        assert res.status_code == 200
        assert res.json()["progress"]["completed_modules"] == ["1"]
        assert res.json()["progress"]["feedback_scores"] == {"1": 3}


# ===========================================================================
# DELETE /api/v1/learning/plans/{plan_id}
# ===========================================================================
class TestDeleteLearningPlan:
    def test_delete_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.delete("/api/v1/learning/plans/lp-ghost")
        assert res.status_code == 404

    def test_delete_403_for_other_user(self, client, db_session, users):
        owner = _make_user(db_session)
        plan = LearningPlan(
            id=f"lp-{uuid.uuid4().hex[:8]}", user_id=owner.id, topic="T",
            current_skill_level="beginner", time_commitment="medium", duration_weeks=2,
            modules={
                "modules": [], "target_skill_level": "intermediate",
                "milestones": [], "assessment_criteria": [],
                "notion_page_id": None, "progress": {},
            }, progress=0,
        )
        db_session.add(plan)
        db_session.commit()
        users["current"] = _make_user(db_session)
        res = client.delete(f"/api/v1/learning/plans/{plan.id}")
        assert res.status_code == 403

    def test_delete_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        plan = LearningPlan(
            id=f"lp-{uuid.uuid4().hex[:8]}", user_id=u.id, topic="T",
            current_skill_level="beginner", time_commitment="medium", duration_weeks=2,
            modules={
                "modules": [], "target_skill_level": "intermediate",
                "milestones": [], "assessment_criteria": [],
                "notion_page_id": None, "progress": {},
            }, progress=0,
        )
        db_session.add(plan)
        db_session.commit()
        res = client.delete(f"/api/v1/learning/plans/{plan.id}")
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert db_session.query(LearningPlan).filter(
            LearningPlan.id == plan.id
        ).first() is None


# ===========================================================================
# GET /api/v1/learning/topics/suggested
# ===========================================================================
class TestSuggestedTopics:
    def test_suggested_topics(self, client):
        res = client.get("/api/v1/learning/topics/suggested")
        assert res.status_code == 200
        body = res.json()
        assert "programming" in body["categories"]
        assert body["total_topics"] > 0


# ===========================================================================
# Unit tests: module generation helpers
# ===========================================================================
class TestGenerateLearningModules:
    def test_target_level_progression(self):
        from api.learning_plan_routes import generate_learning_modules
        import asyncio
        levels = ["beginner", "intermediate", "advanced", "expert"]

    def test_template_focus_phases(self):
        from api.learning_plan_routes import _generate_template_modules
        mods = _generate_template_modules(
            topic="Python", current_level="beginner", target_level="intermediate",
            duration_weeks=6, preferred_formats=["articles", "videos", "exercises"],
        )
        assert len(mods) == 6
        assert "Foundation" in mods[0].title
        assert "Application" in mods[3].title
        assert "Mastery" in mods[5].title
        assert len(mods[0].resources) == 3
        assert mods[0].estimated_hours == 5.0

    def test_template_formats_filtered(self):
        from api.learning_plan_routes import _generate_template_modules
        mods = _generate_template_modules(
            topic="SQL", current_level="beginner", target_level="intermediate",
            duration_weeks=1, preferred_formats=["videos"],
        )
        assert len(mods[0].resources) == 1
        assert mods[0].resources[0]["type"] == "video"

    def test_milestones_by_duration(self):
        from api.learning_plan_routes import generate_milestones
        assert generate_milestones("SQL", 2) == []
        m4 = generate_milestones("SQL", 4)
        assert len(m4) == 1 and "Week 4" in m4[0]
        m8 = generate_milestones("SQL", 8)
        assert len(m8) == 2
        m16 = generate_milestones("SQL", 16)
        assert len(m16) == 4

    def test_assessment_criteria(self):
        from api.learning_plan_routes import generate_assessment_criteria
        criteria = generate_assessment_criteria("SQL")
        assert len(criteria) == 4
        assert all("SQL" in c for c in criteria)


class TestExportToNotion:
    def test_export_success_returns_page_id(self, monkeypatch):
        from api.learning_plan_routes import export_learning_plan_to_notion
        from api.learning_plan_routes import LearningModule

        class FakeNotion:
            def __init__(self, access_token):
                self.token = access_token

            def create_page(self, parent, properties, children):
                assert parent["database_id"] == "db-1"
                assert properties["Topic"]["title"][0]["text"]["content"] == "Python"
                assert any(b["type"] == "to_do" for b in children)
                return {"id": "page-42"}

        monkeypatch.setattr("api.learning_plan_routes.NotionService", FakeNotion)
        plan = type("Plan", (), {
            "notion_database_id": "db-1",
            "topic": "Python",
            "current_skill_level": "beginner",
            "target_skill_level": "intermediate",
            "duration_weeks": 4,
            "created_at": __import__("datetime").datetime(2026, 1, 1),
            "milestones": ["m1"],
            "modules": {
                "modules": [],
                "target_skill_level": "intermediate",
                "milestones": ["m1"],
                "assessment_criteria": ["c1"],
                "notion_page_id": None,
                "progress": {},
            },
        })()
        module = LearningModule(
            week=1, title="Intro", objectives=["o1"], resources=[],
            exercises=["e1"], estimated_hours=1.0,
        )
        import asyncio
        page_id = asyncio.run(export_learning_plan_to_notion(plan, [module], "tok"))
        assert page_id == "page-42"

    def test_export_no_id_returns_none(self, monkeypatch):
        from api.learning_plan_routes import export_learning_plan_to_notion

        class FakeNotion:
            def __init__(self, access_token):
                pass

            def create_page(self, parent, properties, children):
                return {"not_an_id": True}

        monkeypatch.setattr("api.learning_plan_routes.NotionService", FakeNotion)
        plan = type("Plan", (), {
            "notion_database_id": "db-1", "topic": "T",
            "current_skill_level": "beginner", "target_skill_level": "intermediate",
            "duration_weeks": 2, "created_at": __import__("datetime").datetime(2026, 1, 1),
            "milestones": [],
            "modules": {
                "modules": [], "target_skill_level": "intermediate",
                "milestones": [], "assessment_criteria": [],
                "notion_page_id": None, "progress": {},
            },
        })()
        import asyncio
        assert asyncio.run(export_learning_plan_to_notion(plan, [], "tok")) is None

    def test_export_exception_returns_none(self, monkeypatch):
        from api.learning_plan_routes import export_learning_plan_to_notion

        class FakeNotion:
            def __init__(self, access_token):
                raise RuntimeError("boom")

        monkeypatch.setattr("api.learning_plan_routes.NotionService", FakeNotion)
        plan = type("Plan", (), {
            "notion_database_id": "db-1", "topic": "T",
            "current_skill_level": "beginner", "target_skill_level": "intermediate",
            "duration_weeks": 2, "created_at": __import__("datetime").datetime(2026, 1, 1),
            "milestones": [],
            "modules": {
                "modules": [], "target_skill_level": "intermediate",
                "milestones": [], "assessment_criteria": [],
                "notion_page_id": None, "progress": {},
            },
        })()
        import asyncio
        assert asyncio.run(export_learning_plan_to_notion(plan, [], "tok")) is None
