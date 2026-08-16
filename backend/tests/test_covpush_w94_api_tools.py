# -*- coding: utf-8 -*-
"""Coverage wave 94 — api/learning_plan_routes.py, api/user_templates_endpoints.py,
api/financial_routes.py, tools/smarthome_tool.py, tools/platform_management_tool.py,
tools/office_tool.py, core/business_agents.py.

No network / no LLM / no real DB: every external boundary (LLM service,
Notion, Hue/HomeAssistant bridges, BYOK manager, Office services, ingestion)
is mocked. Plain pytest + unittest.mock with FastAPI TestClient and
dependency_overrides for get_current_user / get_db.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.learning_plan_routes as lp
import api.user_templates_endpoints as ute
import api.financial_routes as fr
import tools.smarthome_tool as sh
import tools.platform_management_tool as pmt
import tools.office_tool as ot
import core.business_agents as ba
from core.database import get_db

USER = SimpleNamespace(id="u1", email="u1@example.com", tenant_id="t1")


# =========================================================================== #
# helpers
# =========================================================================== #
def _ctx_manager(value):
    @contextmanager
    def _cm(*a, **k):
        yield value
    return _cm


class FakeQuery:
    def __init__(self, first=None, all_=None, count=0, scalar=0):
        self._first = first
        self._all = list(all_ or [])
        self._count = count

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def offset(self, *a, **k):
        return self

    def distinct(self, *a, **k):
        return self

    def delete(self, *a, **k):
        return None

    def first(self):
        return self._first

    def all(self):
        return self._all

    def count(self):
        return self._count

    def scalar(self):
        return self._scalar if hasattr(self, "_scalar") else 0


class FakeDB:
    """Routes db.query(Model) to per-model-name results."""

    def __init__(self, routes=None, queue=None):
        self.routes = routes or {}
        self.queue = list(queue or [])
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.deletes = 0

    def query(self, model, *a, **k):
        if self.queue:
            return self.queue.pop(0)
        name = getattr(model, "__name__", str(model))
        cfg = self.routes.get(name, {})
        return FakeQuery(first=cfg.get("first"), all_=cfg.get("all"),
                         count=cfg.get("count", 0))

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        pass

    def delete(self, obj):
        self.deletes += 1

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = "gen-id"

    def execute(self, *a, **k):
        return MagicMock()

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Col:
    """Column stub supporting comparison/boolean operators in filters."""

    def __lt__(self, o): return self
    def __le__(self, o): return self
    def __gt__(self, o): return self
    def __ge__(self, o): return self
    def __eq__(self, o): return self
    def __ne__(self, o): return self
    def __and__(self, o): return self
    def __or__(self, o): return self
    def __invert__(self): return self
    def is_(self, o): return self
    def is_not(self, o): return self
    def in_(self, o): return self
    def like(self, o): return self
    def ilike(self, o): return self
    def desc(self): return self
    def asc(self): return self


class _ModelMeta(type):
    def __getattr__(cls, name):
        return _Col()


def FakeModel(name, defaults=None):
    """A fake model class: column-ish class attrs + kwarg __init__ + defaults."""
    defaults = dict(defaults or {})
    namespace = {"__init__": lambda self, **kw: self.__dict__.update(kw), **defaults}
    return _ModelMeta(name, (), namespace)


def make_client(module, db=None, user=None, get_user_fn=None):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[get_user_fn or module.get_current_user] = lambda: user or USER
    app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
    return TestClient(app, raise_server_exceptions=False)


DT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def lp_plan(**kw):
    base = dict(
        id="p1", user_id="u1", topic="Python", current_skill_level="beginner",
        duration_weeks=4, created_at=DT, updated_at=DT, progress=0,
        # sidecar: the `modules` JSON column holds the FULL payload dict
        modules={
            "modules": [{"week": 1, "title": "t", "objectives": ["o"],
                         "resources": [{"type": "article"}], "exercises": ["e"],
                         "estimated_hours": 5.0}],
            "target_skill_level": "intermediate",
            "milestones": ["m1"],
            "assessment_criteria": ["a1"],
            "notion_page_id": None,
            "progress": {"completed_modules": [], "feedback_scores": {},
                         "time_spent": {}, "adjustments_made": []},
        },
        status="active", notion_database_id=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


# =========================================================================== #
# 1. api/learning_plan_routes.py
# =========================================================================== #
LearningPlanC = FakeModel("LearningPlan", {"created_at": DT, "updated_at": DT})


class TestLearningPlanRoutes:
    def _client(self, db):
        return make_client(lp, db=db, get_user_fn=lp.get_current_user)

    def test_encode_decode_payload(self):
        enc = lp._encode_plan_payload([], "adv", ["m"], ["a"], "np", {"x": 1})
        assert enc["target_skill_level"] == "adv"
        dec = lp._decode_plan_payload(enc)
        assert dec["milestones"] == ["m"]
        # legacy plain-list modules
        legacy = lp._decode_plan_payload([{"week": 1}])
        assert legacy["modules"] == [{"week": 1}]
        assert legacy["target_skill_level"] == "intermediate"
        assert lp._decode_plan_payload(None)["modules"] == []

    def test_template_modules_and_generators(self):
        mods = lp._generate_template_modules("Python", "beginner", "intermediate",
                                             6, ["articles", "videos", "exercises"])
        assert len(mods) == 6
        assert any("Foundation" in m.title for m in mods)
        assert any("Application" in m.title for m in mods)
        assert any("Mastery" in m.title for m in mods)
        assert mods[0].resources and mods[0].exercises
        mods2 = lp._generate_template_modules("Go", "advanced", "expert", 1, [])
        assert mods2[0].resources == []
        assert lp.generate_milestones("Python", 16) and len(lp.generate_milestones("P", 2)) == 0
        assert len(lp.generate_assessment_criteria("Python")) == 4

    async def test_generate_learning_modules_llm_success_and_fallback(self):
        with patch.object(lp, "LLMService") as LS:
            LS.return_value.generate_structured = AsyncMock(return_value=None)
            mods = await lp.generate_learning_modules("Python", "weird-level", 2,
                                                      ["articles"], db=MagicMock())
            assert len(mods) == 2  # None result -> fallback
        with patch.object(lp, "LLMService") as LS:
            LS.return_value.generate_structured = AsyncMock(side_effect=RuntimeError("llm down"))
            mods = await lp.generate_learning_modules("Python", "beginner", 2,
                                                      ["articles"], ["goal"], db=MagicMock())
            assert len(mods) == 2
        with patch.object(lp, "LLMService") as LS:
            LS.return_value.generate_structured = AsyncMock(
                return_value=lp.LearningPlanModules(modules=[
                    lp.LearningModule(week=1, title="AI", objectives=["o"],
                                      resources=[], exercises=[], estimated_hours=1.0)]))
            mods = await lp.generate_learning_modules("Python", "beginner", 4,
                                                      ["articles"], db=MagicMock())
            assert len(mods) == 1 and mods[0].title == "AI"

    async def test_export_learning_plan_to_notion(self):
        plan = lp_plan()
        plan.notion_database_id = "db1"
        modules = lp._generate_template_modules("Python", "beginner", "intermediate", 2, ["articles"])
        with patch.object(lp, "NotionService") as NS:
            NS.return_value.create_page.return_value = {"id": "page-1"}
            page_id = await lp.export_learning_plan_to_notion(plan, modules, "tok")
        assert page_id == "page-1"
        # no id in result
        with patch.object(lp, "NotionService") as NS:
            NS.return_value.create_page.return_value = {}
            assert await lp.export_learning_plan_to_notion(plan, modules, "tok") is None
            NS.return_value.create_page.side_effect = RuntimeError("notion boom")
            assert await lp.export_learning_plan_to_notion(plan, modules, "tok") is None

    def test_create_plan_happy_path(self):
        db = FakeDB()
        with patch.object(lp, "LearningPlan", LearningPlanC), \
             patch.object(lp, "LLMService") as LS:
            LS.return_value.generate_structured = AsyncMock(return_value=None)
            r = self._client(db).post("/api/v1/learning/plans", json={
                "topic": "Python", "current_skill_level": "beginner",
                "duration_weeks": 4, "learning_goals": ["g"],
                "preferred_format": ["articles"]})
        assert r.status_code == 200, r.text
        assert r.json()["modules"]
        assert db.added and db.commits >= 1

    def test_create_plan_validation_and_errors(self):
        c = self._client(FakeDB())
        with patch.object(lp, "LearningPlan", LearningPlanC):
            assert c.post("/api/v1/learning/plans", json={
                "topic": "  ", "current_skill_level": "beginner"}).status_code == 400
            assert c.post("/api/v1/learning/plans", json={
                "topic": "T", "current_skill_level": "godmode"}).status_code == 400
            assert c.post("/api/v1/learning/plans", json={
                "topic": "T", "current_skill_level": "beginner",
                "time_commitment": "always"}).status_code == 400
        db = FakeDB()
        db.commit = Mock(side_effect=RuntimeError("db down"))
        with patch.object(lp, "LearningPlan", LearningPlanC), \
             patch.object(lp, "LLMService") as LS:
            LS.return_value.generate_structured = AsyncMock(return_value=None)
            assert self._client(db).post("/api/v1/learning/plans", json={
                "topic": "T"}).status_code == 500

    def test_create_plan_with_notion_export(self):
        db = FakeDB(routes={"IT": {
            "first": SimpleNamespace(access_token="enc-tok")}})
        IntegrationTokenC = FakeModel("IntegrationToken")

        class IT(IntegrationTokenC):
            pass

        with patch.object(lp, "LearningPlan", LearningPlanC), \
             patch.object(lp, "LLMService") as LS, \
             patch("core.models.IntegrationToken", IT), \
             patch("core.privsec.token_encryption.decrypt_token",
                   lambda v, allow_plaintext=False: "tok"), \
             patch.object(lp, "export_learning_plan_to_notion",
                          AsyncMock(return_value="page-9")):
            LS.return_value.generate_structured = AsyncMock(return_value=None)
            r = self._client(db).post("/api/v1/learning/plans", json={
                "topic": "T", "notion_database_id": "db1"})
        assert r.status_code == 200

        # token present but export fails
        db2 = FakeDB(routes={"IT": {
            "first": SimpleNamespace(access_token="enc-tok")}})
        with patch.object(lp, "LearningPlan", LearningPlanC), \
             patch.object(lp, "LLMService") as LS, \
             patch("core.models.IntegrationToken", IT), \
             patch("core.privsec.token_encryption.decrypt_token",
                   lambda v, allow_plaintext=False: "tok"), \
             patch.object(lp, "export_learning_plan_to_notion",
                          AsyncMock(return_value=None)):
            LS.return_value.generate_structured = AsyncMock(return_value=None)
            assert self._client(db2).post("/api/v1/learning/plans", json={
                "topic": "T", "notion_database_id": "db1"}).status_code == 200
        # no active token
        db3 = FakeDB(routes={"IT": {"first": None}})
        with patch.object(lp, "LearningPlan", LearningPlanC), \
             patch.object(lp, "LLMService") as LS, \
             patch("core.models.IntegrationToken", IT):
            LS.return_value.generate_structured = AsyncMock(return_value=None)
            assert self._client(db3).post("/api/v1/learning/plans", json={
                "topic": "T", "notion_database_id": "db1"}).status_code == 200

    def test_get_plan(self):
        db = FakeDB(routes={"LearningPlan": {"first": lp_plan()}})
        c = self._client(db)
        r = c.get("/api/v1/learning/plans/p1")
        assert r.status_code == 200 and r.json()["plan_id"] == "p1"
        # legacy plain-list payload
        db2 = FakeDB(routes={"LearningPlan": {"first": lp_plan(modules=[])}}
                     ) if False else FakeDB(routes={"LearningPlan": {
                         "first": lp_plan(modules=[{"week": 2, "title": "x",
                                                    "objectives": [], "resources": [],
                                                    "exercises": [], "estimated_hours": 1.0}])}})
        assert self._client(db2).get("/api/v1/learning/plans/p1").status_code == 200
        assert self._client(FakeDB()).get("/api/v1/learning/plans/nope").status_code == 404
        db3 = FakeDB(routes={"LearningPlan": {"first": lp_plan(user_id="other")}})
        assert self._client(db3).get("/api/v1/learning/plans/p1").status_code == 403

    def test_list_plans(self):
        db = FakeDB(routes={"LearningPlan": {
            "all": [lp_plan(), lp_plan(id="p2", modules=None)],
            "count": 2}})
        r = self._client(db).get("/api/v1/learning/plans?limit=5&offset=1")
        body = r.json()
        assert body["total"] == 2 and body["limit"] == 5

    def test_update_progress_branches(self):
        plan = lp_plan()
        db = FakeDB(routes={"LearningPlan": {"first": plan}})
        c = self._client(db)
        # low feedback -> remediation
        r = c.post("/api/v1/learning/plans/p1/progress",
                   json={"module_week": 1, "feedback_score": 1, "time_spent_hours": 3.0})
        assert r.status_code == 200 and r.json()["adjustments"][0]["type"] == "remediation"
        # high feedback, quick -> acceleration
        r = c.post("/api/v1/learning/plans/p1/progress",
                   json={"module_week": 2, "feedback_score": 5, "time_spent_hours": 1.0})
        assert r.json()["adjustments"][0]["type"] == "acceleration"
        # neutral
        r = c.post("/api/v1/learning/plans/p1/progress",
                   json={"module_week": 3, "feedback_score": 3, "time_spent_hours": 2.0})
        assert r.json()["adjustments"] == []
        assert plan.progress == 75  # 3 of 4 weeks
        # non-dict progress in sidecar gets re-initialized
        plan2 = lp_plan()
        payload = plan2.modules
        payload["progress"] = "bogus"
        db2 = FakeDB(routes={"LearningPlan": {"first": plan2}})
        r = self._client(db2).post("/api/v1/learning/plans/p1/progress",
                                   json={"module_week": 1, "feedback_score": 4,
                                         "time_spent_hours": 1.0})
        assert r.status_code == 200
        # validation / 404 / 403
        assert c.post("/api/v1/learning/plans/p1/progress",
                      json={"module_week": 0, "feedback_score": 3,
                            "time_spent_hours": 1.0}).status_code == 422
        assert self._client(FakeDB()).post(
            "/api/v1/learning/plans/nope/progress",
            json={"module_week": 1, "feedback_score": 3,
                  "time_spent_hours": 1.0}).status_code == 404
        db3 = FakeDB(routes={"LearningPlan": {"first": lp_plan(user_id="other")}})
        assert self._client(db3).post(
            "/api/v1/learning/plans/p1/progress",
            json={"module_week": 1, "feedback_score": 3,
                  "time_spent_hours": 1.0}).status_code == 403

    def test_delete_plan(self):
        db = FakeDB(routes={"LearningPlan": {"first": lp_plan()}})
        assert self._client(db).delete("/api/v1/learning/plans/p1").status_code == 200
        assert db.deletes == 1
        assert self._client(FakeDB()).delete("/api/v1/learning/plans/nope").status_code == 404
        db2 = FakeDB(routes={"LearningPlan": {"first": lp_plan(user_id="other")}})
        assert self._client(db2).delete("/api/v1/learning/plans/p1").status_code == 403

    def test_suggested_topics(self):
        r = self._client(FakeDB()).get("/api/v1/learning/topics/suggested")
        assert r.status_code == 200 and r.json()["total_topics"] > 0


# =========================================================================== #
# 2. api/user_templates_endpoints.py
# =========================================================================== #
WorkflowTemplateC = FakeModel("WorkflowTemplate", {
    "usage_count": 0, "rating": 4.0, "rating_count": 1, "version": "1.0.0",
    "created_at": DT, "updated_at": DT, "is_approved": False, "is_public": False,
    "steps": None, "category": "automation", "icon": "i", "author_id": "u1",
    "description": "d", "name": "n", "id": "template_x",
})
TemplateVersionC = FakeModel("TemplateVersion", {"created_at": DT})
TemplateExecutionC = FakeModel("TemplateExecution")
UserC = FakeModel("User")


def ute_template(**kw):
    base = dict(id="template_x", name="n", description="d", category="automation",
                icon="i", author_id="u1", is_public=False, is_approved=False,
                steps=[{"s": 1}], input_schema=None,
                usage_count=3, rating=4.5, rating_count=2, version="1.0.0",
                created_at=DT, updated_at=DT)
    base.update(kw)
    return SimpleNamespace(**base)


class TestUserTemplatesEndpoints:
    def _client(self, db, user=None):
        return make_client(ute, db=db, user=user, get_user_fn=ute.get_current_user)

    def test_create_template(self):
        db = FakeDB()
        with patch.object(ute, "WorkflowTemplate", WorkflowTemplateC), \
             patch.object(ute, "TemplateVersion", TemplateVersionC):
            r = self._client(db).post("/api/user/templates", json={
                "name": "T", "description": "d", "category": "automation",
                "complexity": "beginner", "template_json": {"steps": []},
                "steps_schema": [{"id": "s1", "name": "Step"}],
                "inputs_schema": [{"name": "p1"}], "is_public": True})
        assert r.status_code == 201, r.text
        assert len(db.added) == 2  # template + version
        # error branch
        db2 = FakeDB()
        db2.commit = Mock(side_effect=RuntimeError("x"))
        with patch.object(ute, "WorkflowTemplate", WorkflowTemplateC), \
             patch.object(ute, "TemplateVersion", TemplateVersionC):
            assert self._client(db2).post("/api/user/templates", json={
                "name": "T", "description": "d", "category": "c",
                "complexity": "b", "template_json": {}}).status_code == 500

    def test_list_templates_filters(self):
        db = FakeDB(routes={"WorkflowTemplate": {
            "all": [ute_template(), ute_template(is_public=True, is_approved=True)]}})
        c = self._client(db)
        assert c.get("/api/user/templates").status_code == 200
        assert c.get("/api/user/templates", params={
            "category": "automation", "featured_only": True,
            "search": "nam"}).status_code == 200
        db2 = FakeDB()
        db2.query = Mock(side_effect=RuntimeError("x"))
        assert self._client(db2).get("/api/user/templates").status_code == 500

    def test_stats(self):
        db = FakeDB(routes={"WorkflowTemplate": {
            "all": [ute_template(usage_count=5, rating=4.0, rating_count=2),
                    ute_template(id="t2", is_public=True, usage_count=0,
                                 rating=0.0, rating_count=0)]}})
        r = self._client(db).get("/api/user/templates/stats")
        body = r.json()
        assert body["total_templates"] == 2 and body["public_templates"] == 1
        assert body["most_used_template"]["usage_count"] == 5
        db2 = FakeDB()
        db2.query = Mock(side_effect=RuntimeError("x"))
        assert self._client(db2).get("/api/user/templates/stats").status_code == 500

    def test_get_template(self):
        db = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()}})
        assert self._client(db).get("/api/user/templates/template_x").status_code == 200
        assert self._client(FakeDB()).get("/api/user/templates/nope").status_code == 404
        db2 = FakeDB()
        db2.query = Mock(side_effect=RuntimeError("x"))
        assert self._client(db2).get("/api/user/templates/template_x").status_code == 500

    def test_update_template(self):
        tpl = ute_template()
        db = FakeDB(routes={"WorkflowTemplate": {"first": tpl}})
        with patch.object(ute, "TemplateVersion", TemplateVersionC):
            r = self._client(db).put("/api/user/templates/template_x", json={
                "name": "n2", "is_public": True, "tags": ["x"],
                "change_description": "renamed"})
        assert r.status_code == 200 and r.json()["name"] == "n2"
        assert tpl.version == "1.0.1" and len(db.added) == 1
        # unsupported-field skip path + no version bump
        tpl2 = ute_template()
        db2 = FakeDB(routes={"WorkflowTemplate": {"first": tpl2}})
        r = self._client(db2).put("/api/user/templates/template_x",
                                  json={"description": "d2"})
        # request.dict() always contains template_json/steps_schema keys (as
        # None), so a version record is created on every update
        assert r.status_code == 200 and tpl2.version == "1.0.1" and len(db2.added) == 1
        assert self._client(FakeDB()).put("/api/user/templates/nope",
                                          json={"name": "x"}).status_code == 404
        db3 = FakeDB(routes={"WorkflowTemplate": {
            "first": ute_template(author_id="other")}})
        assert self._client(db3).put("/api/user/templates/template_x",
                                     json={"name": "x"}).status_code == 403
        db4 = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()}})
        db4.commit = Mock(side_effect=RuntimeError("x"))
        assert self._client(db4).put("/api/user/templates/template_x",
                                     json={"name": "x"}).status_code == 500

    def test_delete_template(self):
        db = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()}})
        with patch.object(ute, "TemplateVersion", TemplateVersionC), \
             patch.object(ute, "TemplateExecution", TemplateExecutionC):
            assert self._client(db).delete("/api/user/templates/template_x").status_code == 204
        assert self._client(FakeDB()).delete("/api/user/templates/nope").status_code == 404
        db2 = FakeDB(routes={"WorkflowTemplate": {
            "first": ute_template(author_id="other")}})
        assert self._client(db2).delete("/api/user/templates/template_x").status_code == 403
        db3 = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()}})
        db3.commit = Mock(side_effect=RuntimeError("x"))
        assert self._client(db3).delete("/api/user/templates/template_x").status_code == 500

    def test_publish_template(self):
        tpl = ute_template()
        db = FakeDB(routes={"WorkflowTemplate": {"first": tpl}})
        c = self._client(db)
        assert c.post("/api/user/templates/template_x/publish",
                      json={"visibility": "public"}).status_code == 200
        assert tpl.is_public is True
        assert c.post("/api/user/templates/template_x/publish",
                      json={"visibility": "private"}).status_code == 200
        assert tpl.is_public is False
        # featured as admin
        admin_user = SimpleNamespace(id="u1", email="a@x.com")
        db2 = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()},
                             "User": {"first": SimpleNamespace(role=ute.UserRole.SUPER_ADMIN)}})
        r = self._client(db2, user=admin_user).post(
            "/api/user/templates/template_x/publish",
            json={"visibility": "public", "featured": True})
        assert r.status_code == 200
        # featured as non-admin / missing user
        db3 = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()},
                             "User": {"first": SimpleNamespace(role="member")}})
        assert self._client(db3).post(
            "/api/user/templates/template_x/publish",
            json={"visibility": "public", "featured": True}).status_code == 403
        db4 = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()},
                             "User": {"first": None}})
        assert self._client(db4).post(
            "/api/user/templates/template_x/publish",
            json={"visibility": "public", "featured": True}).status_code == 403
        assert self._client(FakeDB()).post(
            "/api/user/templates/nope/publish",
            json={"visibility": "public"}).status_code == 404
        db5 = FakeDB(routes={"WorkflowTemplate": {
            "first": ute_template(author_id="other")}})
        assert self._client(db5).post(
            "/api/user/templates/template_x/publish",
            json={"visibility": "public"}).status_code == 403
        db6 = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()}})
        db6.commit = Mock(side_effect=RuntimeError("x"))
        assert self._client(db6).post(
            "/api/user/templates/template_x/publish",
            json={"visibility": "public"}).status_code == 500

    def test_duplicate_template(self):
        db = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()}})
        with patch.object(ute, "WorkflowTemplate", WorkflowTemplateC):
            r = self._client(db).post("/api/user/templates/template_x/duplicate",
                                      json={"name": "copy"})
        assert r.status_code == 201 and db.added
        # public original owned by other -> allowed
        db2 = FakeDB(routes={"WorkflowTemplate": {
            "first": ute_template(is_public=True, author_id="other")}})
        with patch.object(ute, "WorkflowTemplate", WorkflowTemplateC):
            assert self._client(db2).post("/api/user/templates/template_x/duplicate",
                                          json={"name": "copy"}).status_code == 201
        # private + not owner -> 403
        db3 = FakeDB(routes={"WorkflowTemplate": {
            "first": ute_template(author_id="other")}})
        assert self._client(db3).post("/api/user/templates/template_x/duplicate",
                                      json={"name": "copy"}).status_code == 403
        assert self._client(FakeDB()).post("/api/user/templates/nope/duplicate",
                                           json={"name": "copy"}).status_code == 404
        db4 = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()}})
        db4.commit = Mock(side_effect=RuntimeError("x"))
        assert self._client(db4).post("/api/user/templates/template_x/duplicate",
                                      json={"name": "copy"}).status_code == 500

    def test_versions_and_rate(self):
        v = SimpleNamespace(id="v1", version_number=1, change_summary="init",
                            created_by="u1", created_at=DT)
        db = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()},
                            "TemplateVersion": {"all": [v]}})
        c = self._client(db)
        r = c.get("/api/user/templates/template_x/versions")
        assert r.status_code == 200 and r.json()[0]["version"] == "1"
        assert self._client(FakeDB()).get(
            "/api/user/templates/nope/versions").status_code == 404
        db2 = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()}})
        r = self._client(db2).post("/api/user/templates/template_x/rate?rating=5")
        assert r.status_code == 200 and r.json()["rating_count"] == 3
        assert self._client(FakeDB()).post(
            "/api/user/templates/nope/rate?rating=5").status_code == 404
        assert self._client(db2).post(
            "/api/user/templates/template_x/rate?rating=9").status_code == 422
        db3 = FakeDB(routes={"WorkflowTemplate": {"first": ute_template()}})
        db3.commit = Mock(side_effect=RuntimeError("x"))
        assert self._client(db3).post(
            "/api/user/templates/template_x/rate?rating=5").status_code == 500
        db4 = FakeDB()
        db4.query = Mock(side_effect=RuntimeError("x"))
        assert self._client(db4).get(
            "/api/user/templates/template_x/versions").status_code == 500


# =========================================================================== #
# 3. api/financial_routes.py
# =========================================================================== #
FinancialAccountC = FakeModel("FinancialAccount", {
    "account_metadata": {}, "balance": 0.0, "currency": "USD",
    "created_at": DT, "name": None, "account_type": "checking", "id": "acc1",
})
NetWorthSnapshotC = FakeModel("NetWorthSnapshot", {
    "created_at": DT, "net_worth": 100.0, "total_assets": 150.0,
    "total_liabilities": 50.0, "user_id": "u1",
})
FinancialAuditC = FakeModel("FinancialAudit")


def fr_account(**kw):
    base = dict(id="acc1", account_type="checking", name="bank",
                account_metadata={"user_id": "u1", "provider": "Chase"},
                balance=100.0, currency="USD", created_at=DT)
    base.update(kw)
    return SimpleNamespace(**base)


class TestFinancialRoutes:
    def _client(self, db):
        return make_client(fr, db=db, get_user_fn=fr.get_current_user)

    def _patch_models(self):
        return [patch.object(fr, "FinancialAccount", FinancialAccountC),
                patch.object(fr, "NetWorthSnapshot", NetWorthSnapshotC),
                patch.object(fr, "FinancialAudit", FinancialAuditC)]

    def test_helpers(self):
        acc = fr_account(account_metadata="not-a-dict")
        assert fr._account_provider(acc) is None
        assert fr._account_user_id(acc) is None
        assert fr._account_provider(fr_account()) == "Chase"

    def test_net_worth_summary(self):
        snap = SimpleNamespace(user_id="u1", created_at=DT, net_worth=100.0,
                               total_assets=150.0, total_liabilities=50.0)
        db = FakeDB(routes={"NetWorthSnapshot": {"first": snap}})
        r = self._client(db).get("/api/financial/net-worth/summary")
        assert r.status_code == 200
        assert Decimal(r.json()["net_worth"]) == Decimal("100.0")
        # no snapshot
        r2 = self._client(FakeDB()).get("/api/financial/net-worth/summary")
        assert r2.status_code == 200 and r2.json()["net_worth"] == "0.00"
        # date-like created_at
        import datetime as _dt
        snap2 = SimpleNamespace(user_id="u1", created_at=_dt.date(2026, 1, 2),
                                net_worth=1.0, total_assets=2.0, total_liabilities=1.0)
        db2 = FakeDB(routes={"NetWorthSnapshot": {"first": snap2}})
        assert self._client(db2).get("/api/financial/net-worth/summary").status_code == 200

    def test_list_accounts(self):
        db = FakeDB(routes={"FinancialAccount": {
            "all": [fr_account(), fr_account(id="a2", account_metadata=None)]}})
        r = self._client(db).get("/api/financial/accounts")
        assert r.status_code == 200 and len(r.json()) == 2

    def test_get_account(self):
        db = FakeDB(routes={"FinancialAccount": {"first": fr_account()}})
        r = self._client(db).get("/api/financial/accounts/acc1")
        assert r.status_code == 200 and r.json()["id"] == "acc1"
        assert self._client(FakeDB()).get("/api/financial/accounts/nope").status_code == 404

    def _agent_patches(self, allowed, agent=True):
        resolver = MagicMock()
        resolver.return_value.resolve_agent_for_request = AsyncMock(
            return_value=(SimpleNamespace(id="g1", status="SUPERVISED") if agent else None, {}))
        gov = MagicMock()
        gov.return_value.can_perform_action.return_value = {
            "allowed": allowed, "requires_human_approval": not allowed}
        return [patch.object(fr, "AgentContextResolver", resolver),
                patch.object(fr, "AgentGovernanceService", gov)]

    def test_create_account(self):
        db = FakeDB()
        for p in self._patch_models():
            p.start()
        try:
            r = self._client(db).post("/api/financial/accounts", json={
                "account_type": "savings", "balance": "250.00",
                "provider": "Chase", "name": "sav"})
            assert r.status_code == 201 and r.json()["account_type"] == "savings"
            # with agent, governance allowed
            db2 = FakeDB()
            with patch.object(fr, "AgentContextResolver") as R, \
                 patch.object(fr, "AgentGovernanceService") as G:
                R.return_value.resolve_agent_for_request = AsyncMock(
                    return_value=(SimpleNamespace(id="g1", status="SUPERVISED"), {}))
                G.return_value.can_perform_action.return_value = {"allowed": True}
                assert self._client(db2).post("/api/financial/accounts", json={
                    "account_type": "savings", "balance": "1",
                    "agent_id": "g1"}).status_code == 201
            # agent resolves to None -> plain create
            db3 = FakeDB()
            with patch.object(fr, "AgentContextResolver") as R:
                R.return_value.resolve_agent_for_request = AsyncMock(
                    return_value=(None, {}))
                assert self._client(db3).post("/api/financial/accounts", json={
                    "account_type": "savings", "balance": "1",
                    "agent_id": "gone"}).status_code == 201
            # governance denied -> 403 + audit
            db4 = FakeDB()
            with patch.object(fr, "AgentContextResolver") as R, \
                 patch.object(fr, "AgentGovernanceService") as G:
                R.return_value.resolve_agent_for_request = AsyncMock(
                    return_value=(SimpleNamespace(id="g1", status="INTERN"), {}))
                G.return_value.can_perform_action.return_value = {"allowed": False}
                assert self._client(db4).post("/api/financial/accounts", json={
                    "account_type": "savings", "balance": "1",
                    "agent_id": "g1"}).status_code == 403
            assert db4.added and db4.commits >= 1
        finally:
            patch.stopall()

    def test_update_account(self):
        acc = fr_account()
        db = FakeDB(routes={"FinancialAccount": {"first": acc}})
        for p in self._patch_models():
            p.start()
        try:
            r = self._client(db).patch("/api/financial/accounts/acc1", json={
                "account_type": "investment", "provider": "Fidelity",
                "name": "n2", "balance": "500", "currency": "EUR"})
            assert r.status_code == 200 and acc.name == "n2"
            # governance denied
            db2 = FakeDB(routes={"FinancialAccount": {"first": acc}})
            with patch.object(fr, "AgentContextResolver") as R, \
                 patch.object(fr, "AgentGovernanceService") as G:
                R.return_value.resolve_agent_for_request = AsyncMock(
                    return_value=(SimpleNamespace(id="g1", status="INTERN"), {}))
                G.return_value.can_perform_action.return_value = {"allowed": False}
                assert self._client(db2).patch("/api/financial/accounts/acc1", json={
                    "balance": "1", "agent_id": "g1"}).status_code == 403
            assert self._client(FakeDB()).patch(
                "/api/financial/accounts/nope", json={"name": "x"}).status_code == 404
        finally:
            patch.stopall()

    def test_delete_account(self):
        db = FakeDB(routes={"FinancialAccount": {"first": fr_account()}})
        for p in self._patch_models():
            p.start()
        try:
            assert self._client(db).delete("/api/financial/accounts/acc1").status_code == 200
            assert db.deletes == 1
            # governance denied
            db2 = FakeDB(routes={"FinancialAccount": {"first": fr_account()}})
            with patch.object(fr, "AgentContextResolver") as R, \
                 patch.object(fr, "AgentGovernanceService") as G:
                R.return_value.resolve_agent_for_request = AsyncMock(
                    return_value=(SimpleNamespace(id="g1", status="INTERN"), {}))
                G.return_value.can_perform_action.return_value = {"allowed": False}
                assert self._client(db2).delete(
                    "/api/financial/accounts/acc1?agent_id=g1").status_code == 403
            assert self._client(FakeDB()).delete("/api/financial/accounts/nope").status_code == 404
        finally:
            patch.stopall()

    def test_create_snapshot(self):
        db = FakeDB()
        with patch.object(fr, "NetWorthSnapshot", NetWorthSnapshotC):
            r = self._client(db).post("/api/financial/net-worth/snapshot", json={
                "net_worth": "100.00", "assets": "150.00", "liabilities": "50.00"})
            assert r.status_code == 201
            r2 = self._client(db).post("/api/financial/net-worth/snapshot", json={
                "net_worth": "100.00", "assets": "150.00", "liabilities": "50.00",
                "snapshot_date": "2026-02-03"})
            assert r2.status_code == 201


# =========================================================================== #
# 4. tools/smarthome_tool.py
# =========================================================================== #
AgentRegistryC = FakeModel("AgentRegistry")


class TestSmarthomeTool:
    async def test_hue_permission_matrix(self):
        # feature flag off
        with patch.object(sh.FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False, create=True):
            ok, reason = await sh._check_hue_permission("g1", "u")
            assert ok is False and "disabled" in reason
        # human
        assert (await sh._check_hue_permission(None, "u")) == (True, None)
        # cached decision
        with patch.object(sh, "_governance_cache") as gc:
            gc.get.return_value = {"allowed": False, "reason": "cached-no"}
            assert await sh._check_hue_permission("g1", "u") == (False, "cached-no")
        # db lookups
        for maturity, allowed in [("SUPERVISED", True), ("AUTONOMOUS", True),
                                  ("INTERN", False)]:
            db = FakeDB(routes={"AgentRegistry": {
                "first": SimpleNamespace(maturity_level=maturity)}})
            with patch.object(sh, "get_db_session", _ctx_manager(db)), \
                 patch.object(sh, "_governance_cache") as gc:
                gc.get.return_value = None
                ok, reason = await sh._check_hue_permission("g1", "u")
                assert ok is allowed
                if not allowed:
                    assert "SUPERVISED+" in reason
        db = FakeDB(routes={"AgentRegistry": {"first": None}})
        with patch.object(sh, "get_db_session", _ctx_manager(db)):
            ok, reason = await sh._check_hue_permission("g1", "u")
            assert ok is False and "not found" in reason
        with patch.object(sh, "get_db_session", side_effect=RuntimeError("db")):
            ok, reason = await sh._check_hue_permission("g1", "u")
            assert ok is False and "Permission check failed" in reason

    async def test_home_assistant_permission_matrix(self):
        with patch.object(sh.FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False, create=True):
            ok, _ = await sh._check_home_assistant_permission("g1", "u")
            assert ok is False
        assert (await sh._check_home_assistant_permission(None, "u")) == (True, None)
        with patch.object(sh, "_governance_cache") as gc:
            gc.get.return_value = {"allowed": True, "reason": None}
            assert (await sh._check_home_assistant_permission("g1", "u")) == (True, None)
        db = FakeDB(routes={"AgentRegistry": {
            "first": SimpleNamespace(maturity_level="STUDENT")}})
        with patch.object(sh, "get_db_session", _ctx_manager(db)), \
             patch.object(sh, "_governance_cache") as gc:
            gc.get.return_value = None
            ok, reason = await sh._check_home_assistant_permission("g1", "u")
            assert ok is False and "Home Assistant" in reason
        db2 = FakeDB(routes={"AgentRegistry": {"first": None}})
        with patch.object(sh, "get_db_session", _ctx_manager(db2)):
            ok, reason = await sh._check_home_assistant_permission("g1", "u")
            assert ok is False
        with patch.object(sh, "get_db_session", side_effect=RuntimeError("db")):
            assert (await sh._check_home_assistant_permission("g1", "u"))[0] is False

    async def test_hue_tools(self):
        with patch.object(sh, "HueService") as HS:
            HS.return_value.discover_bridges = AsyncMock(return_value=["1.2.3.4"])
            r = await sh.hue_discover_bridges()
            assert r["success"] and r["count"] == 1
            HS.return_value.discover_bridges = AsyncMock(side_effect=RuntimeError("mdns"))
            r = await sh.hue_discover_bridges()
            assert r["success"] is False
            HS.return_value.get_all_lights = AsyncMock(
                return_value=[{"id": "1"}])
            r = await sh.hue_get_lights(bridge_ip="b", api_key="k")
            assert r["success"] and r["count"] == 1
            HS.return_value.get_all_lights = AsyncMock(side_effect=RuntimeError("x"))
            assert (await sh.hue_get_lights(bridge_ip="b", api_key="k"))["success"] is False
            HS.return_value.set_light_state = AsyncMock(return_value={"on": True})
            r = await sh.hue_set_light_state(bridge_ip="b", api_key="k",
                                             light_id="1", on=True, brightness=50.0)
            assert r["success"]
            HS.return_value.set_light_state = AsyncMock(side_effect=RuntimeError("x"))
            r = await sh.hue_set_light_state(bridge_ip="b", api_key="k", light_id="1")
            assert r["success"] is False
        # value errors
        with pytest.raises(ValueError):
            await sh.hue_get_lights()
        with pytest.raises(ValueError):
            await sh.hue_set_light_state(bridge_ip="b", api_key="k")
        # permission denied
        with patch.object(sh, "_check_hue_permission", AsyncMock(
                return_value=(False, "nope"))):
            with pytest.raises(PermissionError):
                await sh.hue_discover_bridges(agent_id="g1")
            with pytest.raises(PermissionError):
                await sh.hue_get_lights(agent_id="g1")
            with pytest.raises(PermissionError):
                await sh.hue_set_light_state(agent_id="g1")

    async def test_home_assistant_tools(self):
        with patch.object(sh, "HomeAssistantService") as HA:
            HA.return_value.close = AsyncMock()
            HA.return_value.get_states = AsyncMock(return_value=[{"e": 1}])
            r = await sh.home_assistant_get_states(ha_url="http://h", ha_token="t")
            assert r["success"] and r["count"] == 1
            HA.return_value.get_states = AsyncMock(side_effect=RuntimeError("x"))
            assert (await sh.home_assistant_get_states(
                ha_url="http://h", ha_token="t"))["success"] is False
            HA.return_value.call_service = AsyncMock(return_value={"ok": 1})
            r = await sh.home_assistant_call_service(ha_url="http://h", ha_token="t",
                                                     domain="light", service="turn_on",
                                                     entity_id="l1")
            assert r["success"]
            HA.return_value.call_service = AsyncMock(side_effect=RuntimeError("x"))
            r = await sh.home_assistant_call_service(ha_url="http://h", ha_token="t",
                                                     domain="light", service="turn_on")
            assert r["success"] is False
            HA.return_value.get_lights = AsyncMock(return_value=[{"l": 1}])
            r = await sh.home_assistant_get_lights(ha_url="http://h", ha_token="t")
            assert r["success"] and r["count"] == 1
            HA.return_value.get_lights = AsyncMock(side_effect=RuntimeError("x"))
            assert (await sh.home_assistant_get_lights(
                ha_url="http://h", ha_token="t"))["success"] is False
        with pytest.raises(ValueError):
            await sh.home_assistant_get_states()
        with pytest.raises(ValueError):
            await sh.home_assistant_call_service(ha_url="h", ha_token="t")
        with pytest.raises(ValueError):
            await sh.home_assistant_get_lights()
        with patch.object(sh, "_check_home_assistant_permission", AsyncMock(
                return_value=(False, "nope"))):
            with pytest.raises(PermissionError):
                await sh.home_assistant_get_states(agent_id="g1")
            with pytest.raises(PermissionError):
                await sh.home_assistant_call_service(agent_id="g1")
            with pytest.raises(PermissionError):
                await sh.home_assistant_get_lights(agent_id="g1")

    def test_register_smarthome_tools(self):
        reg = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=reg):
            sh.register_smarthome_tools()
        assert reg.register.call_count == 6


# =========================================================================== #
# 5. tools/platform_management_tool.py
# =========================================================================== #
TenantSettingC = FakeModel("TenantSetting")
TenantC = FakeModel("Tenant", {"metadata_json": {}})
WorkspaceC = FakeModel("Workspace")
UserPC = FakeModel("User", {"name": "A B", "email": "a@x.com", "id": "u1",
                            "role": "member", "status": "active", "is_active": True})
TeamC = FakeModel("Team")


def pmt_session(routes=None, queue=None):
    return FakeDB(routes=routes, queue=queue)


class TestPlatformManagementTool:
    async def test_platform_settings(self):
        db = pmt_session(routes={"TenantSetting": {"all": [
            SimpleNamespace(setting_key="a", setting_value="1"),
            SimpleNamespace(setting_key="b", setting_value="2")]}})
        with patch("core.database.SessionLocal", lambda: db):
            r = await pmt.get_platform_settings({"workspace_id": "w1"})
        assert r == {"a": "1", "b": "2"}
        with patch("core.database.SessionLocal",
                   Mock(side_effect=RuntimeError("db"))):
            assert "error" in await pmt.get_platform_settings()

    async def test_update_platform_setting(self):
        existing = SimpleNamespace(setting_value="old")
        db = pmt_session(routes={"TenantSetting": {"first": existing}})
        with patch("core.database.SessionLocal", lambda: db):
            r = await pmt.update_platform_setting("k", "new", {"workspace_id": "w"})
        assert "updated" in r and existing.setting_value == "new"
        db2 = pmt_session(routes={"TenantSetting": {"first": None}})
        with patch("core.database.SessionLocal", lambda: db2):
            r = await pmt.update_platform_setting("k", "v")
        assert "updated" in r and db2.added
        with patch("core.database.SessionLocal",
                   Mock(side_effect=RuntimeError("db"))):
            assert "Error" in await pmt.update_platform_setting("k", "v")

    async def test_update_tenant_profile(self):
        tenant = SimpleNamespace(name="n", billing_email=None,
                                 metadata_json={}, budget_limit_usd=None)
        db = pmt_session(routes={"Workspace": {"first": SimpleNamespace(tenant_id="t1")},
                                 "Tenant": {"first": tenant}})
        with patch("core.database.SessionLocal", lambda: db):
            r = await pmt.update_tenant_profile(
                name="N", billing_email="b@x.com", logo_url="http://l",
                primary_color="#fff", budget_limit_usd=99.0,
                context={"workspace_id": "w"})
        assert "Fields modified: name, billing_email, logo_url, primary_color, budget_limit_usd" in r
        # no updates
        db2 = pmt_session(routes={"Workspace": {"first": None},
                                  "Tenant": {"first": tenant}})
        with patch("core.database.SessionLocal", lambda: db2):
            assert await pmt.update_tenant_profile() == "No updates provided."
        # default tenant missing
        db3 = pmt_session(routes={"Workspace": {"first": None},
                                  "Tenant": {"first": None}})
        with patch("core.database.SessionLocal", lambda: db3):
            assert "not found" in await pmt.update_tenant_profile()
        # specific tenant missing
        db4 = pmt_session(routes={"Workspace": {"first": SimpleNamespace(tenant_id="tX")},
                                  "Tenant": {"first": None}})
        with patch("core.database.SessionLocal", lambda: db4):
            r = await pmt.update_tenant_profile(name="N", context={"workspace_id": "w"})
            assert "Tenant tX not found" in r
        with patch("core.database.SessionLocal",
                   Mock(side_effect=RuntimeError("db"))):
            assert "Error" in await pmt.update_tenant_profile(name="N")

    async def test_set_byok_api_key(self):
        db = pmt_session()
        with patch("core.database.SessionLocal", lambda: db), \
             patch("core.byok_endpoints.BYOKManager") as BM:
            r = await pmt.set_byok_api_key("openai", "sk-x", {"workspace_id": "w"})
        assert "Successfully set" in r and db.commits == 1
        assert "Error" in await pmt.set_byok_api_key("openai", "sk-x")
        db2 = pmt_session()
        with patch("core.database.SessionLocal", lambda: db2), \
             patch("core.byok_endpoints.BYOKManager") as BM:
            BM.return_value.store_api_key.side_effect = ValueError("bad provider")
            r = await pmt.set_byok_api_key("nope", "k", {"workspace_id": "w"})
        assert "invalid provider" in r and db2.rollbacks == 1
        db3 = pmt_session()
        with patch("core.database.SessionLocal", lambda: db3), \
             patch("core.byok_endpoints.BYOKManager",
                   Mock(side_effect=RuntimeError("boom"))):
            r = await pmt.set_byok_api_key("openai", "k", {"workspace_id": "w"})
        assert r == "Error setting BYOK API key" and db3.rollbacks == 1

    async def test_list_tenant_members(self):
        ws = SimpleNamespace(tenant_id="t1")
        members = [SimpleNamespace(name="A B", email="a@x.com", id="u1",
                                   role="member", status="active"),
                   SimpleNamespace(name=None, email="b@x.com", id="u2",
                                   role="admin", status="active")]
        db = pmt_session(routes={"Workspace": {"first": ws}, "User": {"all": members}})
        with patch("core.database.SessionLocal", lambda: db):
            r = await pmt.list_tenant_members({"workspace_id": "w"})
        assert "Members for Tenant t1" in r and "A B" in r and "b@x.com" in r
        assert "Error" in await pmt.list_tenant_members()
        db2 = pmt_session(routes={"Workspace": {"first": None}})
        with patch("core.database.SessionLocal", lambda: db2):
            assert "not found" in await pmt.list_tenant_members({"workspace_id": "w"})
        db3 = pmt_session(routes={"Workspace": {"first": ws}, "User": {"all": []}})
        with patch("core.database.SessionLocal", lambda: db3):
            assert "No members" in await pmt.list_tenant_members({"workspace_id": "w"})
        dbx = pmt_session(routes={"Workspace": {"first": ws}})
        dbx.query = Mock(side_effect=RuntimeError("db"))
        with patch("core.database.SessionLocal", lambda: dbx):
            assert "Error" in await pmt.list_tenant_members({"workspace_id": "w"})

    async def test_manage_tenant_member(self):
        user = SimpleNamespace(id="u1", role="member", is_active=True)
        db = pmt_session(routes={"User": {"first": user}})
        with patch("core.database.SessionLocal", lambda: db):
            assert "role updated" in await pmt.manage_tenant_member("u1", "update_role", role="admin")
            assert "deactivated" in await pmt.manage_tenant_member("u1", "deactivate")
            assert "reactivated" in await pmt.manage_tenant_member("u1", "reactivate")
            assert "role is required" in await pmt.manage_tenant_member("u1", "update_role")
            assert "Unknown action" in await pmt.manage_tenant_member("u1", "bogus")
        db2 = pmt_session(routes={"User": {"first": None}})
        with patch("core.database.SessionLocal", lambda: db2):
            assert "not found" in await pmt.manage_tenant_member("x", "deactivate")
        db3 = pmt_session()
        db3.commit = Mock(side_effect=RuntimeError("x"))
        db3.routes = {"User": {"first": user}}
        with patch("core.database.SessionLocal", lambda: db3):
            assert "Error" in await pmt.manage_tenant_member("u1", "deactivate")

    async def test_manage_workspace(self):
        ws = SimpleNamespace(id="w1", name="old", description=None, is_startup=False)
        db = pmt_session(routes={"Workspace": {"first": ws}})
        with patch("core.database.SessionLocal", lambda: db):
            r = await pmt.manage_workspace("New", context={"tenant_id": "t1"})
            assert "created successfully" in r and db.added
            r = await pmt.manage_workspace("New2", action="update",
                                           workspace_id="w1",
                                           context={"tenant_id": "t1"})
            assert "updated successfully" in r and ws.name == "New2"
            assert "workspace_id is required" in await pmt.manage_workspace(
                "N", action="update", context={"tenant_id": "t1"})
            assert "Unknown action" in await pmt.manage_workspace(
                "N", action="bogus", context={"tenant_id": "t1"})
        # tenant resolved from workspace ctx
        db2 = pmt_session(routes={"Workspace": {"first": SimpleNamespace(tenant_id="t9")}})
        with patch("core.database.SessionLocal", lambda: db2):
            r = await pmt.manage_workspace("N", context={"workspace_id": "w"})
        assert "created successfully" in r
        assert "Could not resolve tenant" in await pmt.manage_workspace("N", context={})
        db3 = pmt_session(routes={"Workspace": {"first": None}})
        with patch("core.database.SessionLocal", lambda: db3):
            assert "not found" in await pmt.manage_workspace(
                "N", action="update", workspace_id="gone", context={"tenant_id": "t"})
        db4 = pmt_session()
        db4.commit = Mock(side_effect=RuntimeError("x"))
        with patch("core.database.SessionLocal", lambda: db4):
            assert "Error" in await pmt.manage_workspace("N", context={"tenant_id": "t"})

    async def test_manage_team(self):
        team = SimpleNamespace(id="tm1", name="old")
        user = SimpleNamespace(id="u1")
        db = pmt_session(queue=[
            FakeQuery(first=team),   # update lookup
            FakeQuery(first=user),   # member lookup
            FakeQuery(first=None),   # existing membership check
        ])
        with patch("core.database.SessionLocal", lambda: db), \
             patch("core.models.team_members", MagicMock()):
            r = await pmt.manage_team("T", action="update", team_id="tm1",
                                      add_members=["u1"],
                                      context={"workspace_id": "w"})
        assert "updated successfully" in r and "Added 1 members" in r
        # create + already member
        db2 = pmt_session(queue=[FakeQuery(first=user), FakeQuery(first=object())])
        with patch("core.database.SessionLocal", lambda: db2), \
             patch("core.models.team_members", MagicMock()):
            r = await pmt.manage_team("T2", add_members=["u1"],
                                      context={"workspace_id": "w"})
        assert "created successfully" in r and "Added 0 members" in r
        # unknown member identifier
        db3 = pmt_session(queue=[FakeQuery(first=None)])
        with patch("core.database.SessionLocal", lambda: db3), \
             patch("core.models.team_members", MagicMock()):
            r = await pmt.manage_team("T3", add_members=["ghost"],
                                      context={"workspace_id": "w"})
        assert "Added 0 members" in r
        # errors
        assert "Could not resolve" in await pmt.manage_team("T", context={})
        db4 = pmt_session(queue=[FakeQuery(first=None)])
        with patch("core.database.SessionLocal", lambda: db4):
            assert "not found" in await pmt.manage_team(
                "T", action="update", team_id="gone", context={"workspace_id": "w"})
        assert "team_id is required" in await pmt.manage_team(
            "T", action="update", context={"workspace_id": "w"})
        assert "Unknown action" in await pmt.manage_team(
            "T", action="bogus", context={"workspace_id": "w"})
        db5 = pmt_session()
        db5.commit = Mock(side_effect=RuntimeError("x"))
        with patch("core.database.SessionLocal", lambda: db5):
            assert "Error" in await pmt.manage_team("T", context={"workspace_id": "w"})

    async def test_tenant_crud_stubs(self):
        tenant = SimpleNamespace(id="t1", name="old")
        db = pmt_session(routes={"Tenant": {"first": tenant}})
        with patch("core.database.SessionLocal", lambda: db):
            assert "created successfully" in await pmt.create_tenant("Acme")
            assert "updated successfully" in await pmt.update_tenant("t1", name="N")
            assert "deleted successfully" in await pmt.delete_tenant("t1")
            assert db.deletes == 1
        dbn = pmt_session(routes={"Tenant": {"first": None}})
        with patch("core.database.SessionLocal", lambda: dbn):
            assert "not found" in await pmt.update_tenant("x")
            assert "not found" in await pmt.delete_tenant("x")
        for fn, args in [(pmt.create_tenant, ("N",)), (pmt.update_tenant, ("t",)),
                         (pmt.delete_tenant, ("t",))]:
            with patch("core.database.SessionLocal",
                       Mock(side_effect=RuntimeError("db"))):
                assert "Error" in await fn(*args)

    async def test_workspace_team_member_stubs(self):
        ws = SimpleNamespace(id="w1", name="old")
        team = SimpleNamespace(id="tm1", name="old")
        db = pmt_session(routes={"Workspace": {"first": ws}, "Team": {"first": team}})
        with patch("core.database.SessionLocal", lambda: db):
            assert "created successfully" in await pmt.create_workspace("W", "t1")
            assert "updated successfully" in await pmt.update_workspace("w1", name="N")
            assert "deleted successfully" in await pmt.delete_workspace("w1")
            assert "created successfully" in await pmt.create_team("T", "w1")
            assert "updated successfully" in await pmt.update_team("tm1", name="N")
            assert "deleted successfully" in await pmt.delete_team("tm1")
        dbn = pmt_session(routes={"Workspace": {"first": None}, "Team": {"first": None}})
        with patch("core.database.SessionLocal", lambda: dbn):
            assert "not found" in await pmt.update_workspace("x")
            assert "not found" in await pmt.delete_workspace("x")
            assert "not found" in await pmt.update_team("x")
            assert "not found" in await pmt.delete_team("x")
        for fn, args in [(pmt.create_workspace, ("W", "t")),
                         (pmt.update_workspace, ("w",)),
                         (pmt.delete_workspace, ("w",)),
                         (pmt.create_team, ("T", "w")),
                         (pmt.update_team, ("t",)),
                         (pmt.delete_team, ("t",))]:
            with patch("core.database.SessionLocal",
                       Mock(side_effect=RuntimeError("db"))):
                assert "Error" in await fn(*args)
        assert "added to workspace" in await pmt.add_member_to_workspace("u", "w")
        assert "removed from workspace" in await pmt.remove_member_from_workspace("u", "w")
        assert "added to team" in await pmt.add_member_to_team("u", "t")
        assert "removed from team" in await pmt.remove_member_from_team("u", "t")


# =========================================================================== #
# 6. tools/office_tool.py
# =========================================================================== #
class TestOfficeTool:
    async def test_reads(self):
        with patch.object(ot, "office_service") as svc:
            svc.excel.read_range.return_value = {"success": True, "value": 1}
            r = await ot.read_excel_cell("u", "/f.xlsx", "/Sheet1/A1")
            assert r["success"] is True
            svc.excel.read_range.side_effect = RuntimeError("boom")
            assert (await ot.read_excel_cell("u", "/f.xlsx"))["success"] is False
            svc.word.read_document.return_value = {"success": True}
            assert (await ot.read_word_document("u", "/f.docx"))["success"] is True
            svc.word.read_document.side_effect = RuntimeError("boom")
            assert (await ot.read_word_document("u", "/f.docx"))["success"] is False
            svc.pptx.read_slides.return_value = {"success": True}
            assert (await ot.read_pptx_slides("u", "/f.pptx"))["success"] is True
            svc.pptx.read_slides.side_effect = RuntimeError("boom")
            assert (await ot.read_pptx_slides("u", "/f.pptx"))["success"] is False

    async def test_contained_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        assert ot._contained_path(str(tmp_path / "a.xlsx")) is not None
        assert ot._contained_path("/etc/passwd") is None
        assert ot._contained_path("") is None

    async def test_writes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        inside = str(tmp_path / "a.xlsx")
        with patch.object(ot, "office_service") as svc, \
             patch.object(ot, "_ingest_after_write", AsyncMock()):
            svc.excel.write_cell.return_value = {"success": True}
            assert (await ot.write_excel_cell("u", inside, "/Sheet1/A1", 5))["success"] is True
            svc.excel.write_cell.return_value = {"success": False}
            assert (await ot.write_excel_cell("u", inside, "/Sheet1/A1", 5))["success"] is False
            svc.excel.write_cell.side_effect = RuntimeError("x")
            r = await ot.write_excel_cell("u", inside, "/Sheet1/A1", 5)
            assert r["success"] is False and "Failed to write" in r["error"]
            assert (await ot.write_excel_cell("u", "/etc/passwd", "/S/A1", 1))["success"] is False

            svc.word.modify_document.return_value = {"success": True}
            assert (await ot.modify_word_document("u", inside, "append", "text"))["success"] is True
            svc.word.modify_document.return_value = {"success": False}
            assert (await ot.modify_word_document("u", inside, "append", "text"))["success"] is False
            svc.word.modify_document.side_effect = RuntimeError("x")
            r = await ot.modify_word_document("u", inside, "append", "text")
            assert "Failed to modify" in r["error"]
            assert (await ot.modify_word_document("u", "/etc/passwd", "append", "t"))["success"] is False

            svc.pptx.modify_slides.return_value = {"success": True}
            assert (await ot.modify_pptx_slides("u", inside, "add_slide",
                                                title="T"))["success"] is True
            svc.pptx.modify_slides.return_value = {"success": False}
            assert (await ot.modify_pptx_slides("u", inside, "add_slide"))["success"] is False
            svc.pptx.modify_slides.side_effect = RuntimeError("x")
            r = await ot.modify_pptx_slides("u", inside, "add_slide")
            assert "Failed to modify PowerPoint" in r["error"]
            assert (await ot.modify_pptx_slides("u", "/etc/passwd", "add_slide"))["success"] is False

    async def test_workbook_runtime(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        inside = str(tmp_path / "a.xlsx")
        with patch.object(ot, "office_service") as svc, \
             patch.object(ot, "_ingest_after_write", AsyncMock()):
            svc.excel.get_evaluated_range = AsyncMock(return_value={"success": True, "value": 9})
            assert (await ot.get_excel_formula_result("u", inside, "Sheet1", "A4"))["value"] == 9
            svc.excel.get_evaluated_range = AsyncMock(side_effect=RuntimeError("x"))
            assert (await ot.get_excel_formula_result("u", inside, "S", "A"))["success"] is False

            for meth, fn, args in [
                    ("insert_rows", ot.insert_excel_rows, (inside, "Sheet1", 2, 1)),
                    ("insert_columns", ot.insert_excel_columns, (inside, "Sheet1", 2, 1)),
                    ("recalculate", ot.recalculate_excel, (inside,)),
                    ("add_pivot_table", ot.add_excel_pivot_table,
                     (inside, "S", "P", "A1:D9", ["r"], ["c"], [{"field": "x", "function": "SUM"}])),
                    ("run_excel_macro", ot.run_excel_macro, (inside, "Macro1"))]:
                setattr(svc.excel, meth, AsyncMock(return_value={"success": True}))
                r = await fn("u", *args)
                assert r["success"] is True, (meth, r)
                setattr(svc.excel, meth, AsyncMock(return_value={"success": False}))
                assert (await fn("u", *args))["success"] is False
                setattr(svc.excel, meth, AsyncMock(side_effect=RuntimeError("x")))
                assert (await fn("u", *args))["success"] is False

    async def test_ingest_after_write(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        f = tmp_path / "a.xlsx"
        f.write_bytes(b"x")
        with patch("core.auto_document_ingestion.AutoDocumentIngestionService") as Ingest:
            Ingest.return_value.process_file_bytes = AsyncMock()
            await ot._ingest_after_write(str(f), "u")
            Ingest.return_value.process_file_bytes.assert_awaited_once()
            # empty file -> early return
            f.write_bytes(b"")
            await ot._ingest_after_write(str(f), "u")
        # missing file / failure -> swallowed
        await ot._ingest_after_write(str(tmp_path / "missing.xlsx"), "u")

    async def test_present_coedit_canvas(self):
        db = FakeDB()
        with patch("core.database.get_db_session", _ctx_manager(db)), \
             patch.object(ot, "OfficeSyncService") as OSS:
            r = await ot.present_coedit_canvas("u", "/f.xlsx", title="T")
        assert r["success"] is True and r["canvas_id"].startswith("canvas_")
        assert OSS.return_value.broadcast_file_update.called
        with patch("core.database.get_db_session",
                   Mock(side_effect=RuntimeError("db"))):
            r = await ot.present_coedit_canvas("u", "/f.xlsx", canvas_id="c1")
        assert r["success"] is False


# =========================================================================== #
# 7. core/business_agents.py
# =========================================================================== #
class TestBusinessAgents:
    def _ws_db(self, found=True, error=False):
        if error:
            db = MagicMock()
            db.query.side_effect = RuntimeError("db down")
            return db
        return FakeDB(routes={"Workspace": {"first": object() if found else None}})

    AGENTS = ["accounting", "sales", "marketing", "logistics", "shipping",
              "tax", "purchasing", "planning"]

    async def test_all_agents_success(self):
        for name in self.AGENTS:
            agent = ba.get_specialized_agent(name)
            assert agent is not None and agent.domain
            with patch.object(ba, "get_db_session",
                              _ctx_manager(self._ws_db())):
                r = await agent.run("w1", {})
            assert r["status"] == "success", (name, r)
            assert r["agent_id"] and r["summary"]

    async def test_all_agents_missing_workspace_and_empty_id(self):
        for name in self.AGENTS:
            agent = ba.get_specialized_agent(name)
            with patch.object(ba, "get_db_session",
                              _ctx_manager(self._ws_db(found=False))):
                r = await agent.run("gone")
                assert r["status"] == "error" and "not found" in r["error"]
            r = await agent.run("")
            assert r["status"] == "error" and "workspace_id is required" in r["error"]

    async def test_all_agents_exception(self):
        for name in self.AGENTS:
            agent = ba.get_specialized_agent(name)
            with patch.object(ba, "get_db_session",
                              _ctx_manager(self._ws_db(error=True))):
                r = await agent.run("w1")
            assert r["status"] == "error" and "db down" in r["error"]

    async def test_accounting_params(self):
        agent = ba.AccountingAgent()
        with patch.object(ba, "get_db_session", _ctx_manager(self._ws_db())):
            r = await agent.run("w1", {"transaction_limit": 5,
                                       "perform_reconciliation": False})
        assert r["results"]["categorized"] == 5
        assert r["results"]["reconciliations_performed"] == 0
        with patch.object(ba, "get_db_session", _ctx_manager(self._ws_db())):
            r = await agent.run("w1")  # params None
        assert r["results"]["categorized"] == 12

    async def test_sales_params(self):
        agent = ba.SalesAgent()
        with patch.object(ba, "get_db_session", _ctx_manager(self._ws_db())):
            r = await agent.run("w1", {"lead_limit": 10, "pipeline_stage": "proto"})
        assert r["results"]["leads_scored"] == 10
        assert r["results"]["pipeline_health_score"] == 88
        with patch.object(ba, "get_db_session", _ctx_manager(self._ws_db())):
            r = await agent.run("w1")
        assert r["results"]["leads_scored"] == 45

    async def test_marketing_research_branches(self):
        agent = ba.MarketingAgent()
        mcp = MagicMock()
        mcp.web_search = AsyncMock(return_value={"answer": "trend data " * 50})
        agent.mcp = mcp
        with patch.object(ba, "get_db_session", _ctx_manager(self._ws_db())):
            r = await agent.run("w1", {"perform_research": True,
                                       "research_query": "q"})
        assert r["results"]["market_research"]
        assert "Market research" in r["summary"]
        mcp.web_search = AsyncMock(side_effect=RuntimeError("search down"))
        with patch.object(ba, "get_db_session", _ctx_manager(self._ws_db())):
            r = await agent.run("w1", {"perform_research": True})
        assert r["results"]["market_research"] == "Market research unavailable"
        with patch.object(ba, "get_db_session", _ctx_manager(self._ws_db())):
            r = await agent.run("w1")  # params None -> no research
        assert "market_research" not in r["results"]
        assert "Market research" not in r["summary"]

    def test_factory_and_registry(self):
        assert set(ba.AGENT_SUITE) == set(self.AGENTS)
        assert ba.get_specialized_agent("Sales") is not None  # case-insensitive
        assert ba.get_specialized_agent("nope") is None
        agent = ba.get_specialized_agent("accounting", "w1")
        assert agent.name == "Accounting Assistant"
        # abstract base cannot be instantiated
        with pytest.raises(TypeError):
            ba.BusinessAgent("id", "n", "d")
