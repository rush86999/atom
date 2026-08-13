# -*- coding: utf-8 -*-
"""Coverage wave 69 — core/skill_marketplace_service (in-memory SQLite full
schema, mocked AtomAgentOSMarketplaceClient, zero LLM spend, no network).

- __init__: injected saas client, skill registry wiring, ANALYTICS_ENABLED
  auto-registration (instance-missing → worker._ensure_instance_registered,
  instance-present → skip, worker exception → tolerated).
- search_skills: Atom Agent OS success (source=atom_agent_os); exception →
  local fallback with query/category/skill_type filters, created/name/relevance
  sort, pagination, page_size<=0 → empty, rating enrichment.
- get_skill_by_id: saas hit, saas exception → local hit w/ ratings, saas None
  + local miss → None.
- get_categories: saas hit; saas exception → local aggregation with
  display_name transformation.
- rate_skill: invalid rating; saas success returned verbatim; saas exception →
  local create; existing rating → update ("updated"); skill not found.
- install_skill: saas success, saas not-success fall-through, saas exception,
  skill not found.
- uninstall_skill: saas success / not-success / exception; local miss;
  success with model lacking install_count (hasattr-guard skips decrement);
  success with install_count-bearing row (decrement + floor at 0); commit
  exception → rollback.
- helpers: _skill_to_dict populated/None input_params/None created_at,
  _get_average_rating hit/empty, _get_skill_ratings populated/empty/limit.
- async stubs: sync_with_marketplace, _cache_skills, _cache_categories.
"""
import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import SkillExecution, SkillRating
from core.models_registration import Base
from core.skill_marketplace_service import SkillMarketplaceService


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def service(db):
    saas = MagicMock()
    for method in (
        "fetch_skills_sync", "get_skill_by_id_sync", "get_categories_sync",
        "rate_skill_sync", "install_skill_sync", "uninstall_skill_sync",
    ):
        getattr(saas, method).side_effect = Exception("SaaS unavailable (mocked)")
    return SkillMarketplaceService(db, saas_client=saas)


def _skill(db, skill_id="sk-1", *, source="community", status="Active",
           category="automation", skill_type="python_code", name="Test Skill",
           tags=None, description="A skill", author="Auth", version="1.0.0",
           install_count=None):
    input_params = {
        "skill_name": name,
        "skill_type": skill_type,
        "skill_metadata": {
            "description": description, "category": category, "tags": tags or [],
            "author": author, "version": version,
        },
    }
    kwargs = {}
    if install_count is not None:
        kwargs["install_count"] = install_count
    skill = SkillExecution(
        id=skill_id, agent_id="agent-1", tenant_id="t1", skill_id=skill_id,
        skill_source=source, status=status, input_params=input_params,
        created_at=datetime.now(timezone.utc), **kwargs,
    )
    db.add(skill)
    db.commit()
    return skill


# ============================================================================
# Construction / auto-registration
# ============================================================================

class TestInit:
    def test_injected_saas_client_and_registry(self, db):
        saas = MagicMock()
        svc = SkillMarketplaceService(db, saas_client=saas)
        assert svc.saas_client is saas
        assert svc.skill_registry is not None

    def test_auto_registration_when_analytics_enabled(self, db, monkeypatch):
        monkeypatch.setenv("ANALYTICS_ENABLED", "true")
        worker = MagicMock()
        with patch("core.marketplace_sync_worker.AnalyticsSyncWorker", return_value=worker):
            svc = SkillMarketplaceService(db, saas_client=MagicMock())
        worker._ensure_instance_registered.assert_called_once()

    def test_auto_registration_skips_when_instance_exists(self, db, monkeypatch):
        monkeypatch.setenv("ANALYTICS_ENABLED", "true")
        from core.models import MarketplaceInstance
        db.add(MarketplaceInstance(saas_instance_id="i1"))
        db.commit()
        worker = MagicMock()
        with patch("core.marketplace_sync_worker.AnalyticsSyncWorker", return_value=worker):
            SkillMarketplaceService(db, saas_client=MagicMock())
        worker._ensure_instance_registered.assert_not_called()

    def test_auto_registration_exception_tolerated(self, db, monkeypatch):
        monkeypatch.setenv("ANALYTICS_ENABLED", "true")
        with patch("core.marketplace_sync_worker.AnalyticsSyncWorker",
                   side_effect=RuntimeError("reg failed")):
            svc = SkillMarketplaceService(db, saas_client=MagicMock())
        assert svc.db is db


# ============================================================================
# search_skills
# ============================================================================

class TestSearchSkills:
    def test_saas_first_success(self, service):
        service.saas_client.fetch_skills_sync.side_effect = None
        result = {"skills": [{"id": "r1"}], "total": 1, "page": 1, "page_size": 20}
        service.saas_client.fetch_skills_sync.return_value = result
        out = service.search_skills(query="q", category="c", skill_type="t", page=2, page_size=50)
        assert out["source"] == "atom_agent_os"
        assert out["skills"] == [{"id": "r1"}]
        service.saas_client.fetch_skills_sync.assert_called_once_with(
            query="q", category="c", skill_type="t", page=2, page_size=50
        )

    def test_local_fallback_basic(self, service, db):
        _skill(db, "sk-1", name="Email Helper", description="Email triage helper")
        out = service.search_skills(query="triage")
        assert out["source"] == "local"
        assert out["total"] == 1
        assert out["skills"][0]["skill_name"] == "Email Helper"
        assert out["skills"][0]["avg_rating"] == 0.0

    def test_local_fallback_trims_query(self, service, db):
        _skill(db, "sk-1", name="Email Helper", description="Email triage helper")
        out = service.search_skills(query="   triage   ")
        assert out["total"] == 1

    def test_local_fallback_category_and_type_filters(self, service, db):
        _skill(db, "sk-1", category="automation", skill_type="python_code")
        _skill(db, "sk-2", category="data", skill_type="prompt_only")
        assert service._search_local_skills(category="data")["total"] == 1
        assert service._search_local_skills(skill_type="prompt_only")["total"] == 1
        assert service._search_local_skills(category="nope")["total"] == 0

    def test_local_fallback_sort_variants(self, service, db):
        _skill(db, "sk-1", name="Alpha")
        _skill(db, "sk-2", name="Beta")
        assert service._search_local_skills(sort_by="created")["total"] == 2
        assert service._search_local_skills(sort_by="name")["skills"][0]["skill_name"] == "Alpha"
        assert service._search_local_skills(sort_by="relevance")["total"] == 2

    def test_local_fallback_pagination(self, service, db):
        for i in range(5):
            _skill(db, f"sk-{i}", name=f"Skill {i}")
        out = service._search_local_skills(page=2, page_size=2)
        assert out["total_pages"] == 3
        assert len(out["skills"]) == 2

    def test_local_fallback_invalid_page_size(self, service, db):
        _skill(db, "sk-1")
        out = service._search_local_skills(page_size=0)
        assert out["skills"] == []
        assert out["total_pages"] == 0


# ============================================================================
# get_skill_by_id / categories
# ============================================================================

class TestGetSkillById:
    def test_saas_hit(self, service):
        service.saas_client.get_skill_by_id_sync.side_effect = None
        service.saas_client.get_skill_by_id_sync.return_value = {"id": "r9", "name": "R"}
        out = service.get_skill_by_id("r9")
        assert out["source"] == "atom_agent_os"
        assert out["name"] == "R"

    def test_local_fallback_with_ratings(self, service, db):
        _skill(db, "sk-1")
        service.db.add(SkillRating(
            tenant_id="t1", skill_id="sk-1", user_id="u1", rating=4, review="good",
            created_at=datetime.now(timezone.utc),
        ))
        service.db.commit()
        out = service.get_skill_by_id("sk-1")
        assert out["source"] == "local"
        assert out["avg_rating"] == 4.0
        assert out["rating_count"] == 1
        assert out["ratings"][0]["user_id"] == "u1"

    def test_not_found_returns_none(self, service):
        assert service.get_skill_by_id("missing") is None


class TestGetCategories:
    def test_saas_hit(self, service):
        service.saas_client.get_categories_sync.side_effect = None
        service.saas_client.get_categories_sync.return_value = [{"name": "a", "skill_count": 1}]
        out = service.get_categories()
        assert out == [{"name": "a", "skill_count": 1}]

    def test_saas_empty_then_local(self, service, db):
        service.saas_client.get_categories_sync.side_effect = Exception("down")
        _skill(db, "sk-1", category="data_analysis")
        out = service.get_categories()
        assert out[0]["name"] == "data_analysis"
        assert out[0]["display_name"] == "Data Analysis"
        assert out[0]["skill_count"] == 1


# ============================================================================
# rate_skill
# ============================================================================

class TestRateSkill:
    def test_invalid_rating(self, service):
        out = service.rate_skill("sk-1", "u1", 6)
        assert out["success"] is False
        assert "between 1 and 5" in out["error"]

    def test_saas_success_returned(self, service, db):
        _skill(db, "sk-1")
        service.saas_client.rate_skill_sync.side_effect = None
        service.saas_client.rate_skill_sync.return_value = {"success": True, "remote": "ok"}
        out = service.rate_skill("sk-1", "u1", 5)
        assert out == {"success": True, "remote": "ok"}

    def test_local_create_on_saas_failure(self, service, db):
        _skill(db, "sk-1")
        out = service.rate_skill("sk-1", "u1", 5, comment="great")
        assert out["success"] is True
        assert out["action"] == "created"
        assert out["average_rating"] == 5.0
        assert out["source"] == "local"
        rating = service.db.query(SkillRating).filter_by(skill_id="sk-1", user_id="u1").first()
        assert rating.rating == 5
        assert rating.review == "great"

    def test_update_existing_rating(self, service, db):
        _skill(db, "sk-1")
        service.db.add(SkillRating(
            tenant_id="t1", skill_id="sk-1", user_id="u1", rating=3,
            review="meh", created_at=datetime.now(timezone.utc),
        ))
        service.db.commit()
        out = service.rate_skill("sk-1", "u1", 4)
        assert out["action"] == "updated"
        assert service.db.query(SkillRating).filter_by(skill_id="sk-1").count() == 1

    def test_skill_not_found(self, service):
        out = service.rate_skill("missing", "u1", 5)
        assert out["success"] is False
        assert out["error"] == "Skill not found"


# ============================================================================
# install_skill / uninstall_skill
# ============================================================================

class TestInstallSkill:
    def test_saas_success(self, service, db):
        _skill(db, "sk-1")
        service.saas_client.install_skill_sync.side_effect = None
        service.saas_client.install_skill_sync.return_value = {"success": True, "remote": "ok"}
        out = service.install_skill("sk-1", "agent-1")
        assert out["success"] is True
        assert out["skill_id"] == "sk-1"
        assert out["source"] == "local"

    def test_saas_not_success_falls_through(self, service, db):
        _skill(db, "sk-1")
        service.saas_client.install_skill_sync.side_effect = None
        service.saas_client.install_skill_sync.return_value = {"success": False, "error": "nope"}
        out = service.install_skill("sk-1", "agent-1")
        assert out["success"] is True

    def test_saas_exception_tolerated(self, service, db):
        _skill(db, "sk-1")
        out = service.install_skill("sk-1", "agent-1")
        assert out["success"] is True

    def test_skill_not_found(self, service):
        out = service.install_skill("missing", "agent-1")
        assert out["success"] is False
        assert "not found" in out["error"]


class TestUninstallSkill:
    def test_saas_success(self, service, db):
        _skill(db, "sk-1")
        service.saas_client.uninstall_skill_sync.side_effect = None
        service.saas_client.uninstall_skill_sync.return_value = {"success": True}
        out = service.uninstall_skill("sk-1", "agent-1")
        assert out["success"] is True
        assert out["message"] == "Skill uninstalled successfully"

    def test_saas_not_success_and_exception(self, service, db):
        _skill(db, "sk-1")
        service.saas_client.uninstall_skill_sync.side_effect = None
        service.saas_client.uninstall_skill_sync.return_value = {"success": False, "error": "no"}
        assert service.uninstall_skill("sk-1", "agent-1")["success"] is True
        service.saas_client.uninstall_skill_sync.side_effect = RuntimeError("down")
        assert service.uninstall_skill("sk-1", "agent-1")["success"] is True

    def test_local_miss(self, service):
        out = service.uninstall_skill("missing", "agent-1")
        assert out["success"] is False
        assert "not found" in out["error"]

    def test_success_model_without_install_count(self, service, db):
        _skill(db, "sk-1")
        out = service.uninstall_skill("sk-1", "agent-1")
        assert out["success"] is True

    def test_decrement_install_count_with_fake_row(self, service):
        fake = MagicMock()
        fake.id = "sk-9"
        fake.skill_source = "community"
        fake.install_count = 5
        service.db = MagicMock()
        service.db.query.return_value.filter.return_value.first.return_value = fake
        out = service.uninstall_skill("sk-9", "agent-1")
        assert fake.install_count == 4
        assert out["success"] is True
        service.db.commit.assert_called_once()

    def test_decrement_floors_at_zero(self, service):
        fake = MagicMock()
        fake.id = "sk-9"
        fake.skill_source = "community"
        fake.install_count = 0
        service.db = MagicMock()
        service.db.query.return_value.filter.return_value.first.return_value = fake
        service.uninstall_skill("sk-9", "agent-1")
        assert fake.install_count == 0

    def test_commit_exception_rolls_back(self, service):
        fake = MagicMock()
        fake.skill_source = "community"
        service.db = MagicMock()
        service.db.query.return_value.filter.return_value.first.return_value = fake
        service.db.commit.side_effect = RuntimeError("db down")
        out = service.uninstall_skill("sk-9", "agent-1")
        assert out["success"] is False
        service.db.rollback.assert_called_once()


# ============================================================================
# helpers + async stubs
# ============================================================================

class TestHelpers:
    def test_skill_to_dict_populated(self, service, db):
        skill = _skill(db, "sk-1", tags=["a"])
        skill.sandbox_enabled = True
        skill.security_scan_result = {"safe": True}
        out = service._skill_to_dict(skill)
        assert out["skill_name"] == "Test Skill"
        assert out["category"] == "automation"
        assert out["tags"] == ["a"]
        assert out["author"] == "Auth"
        assert out["version"] == "1.0.0"
        assert out["sandbox_enabled"] is True
        assert out["security_scan_result"] == {"safe": True}
        assert out["skill_source"] == "community"
        assert out["created_at"] is not None

    def test_skill_to_dict_none_input_params(self, service):
        skill = SkillExecution(
            id="sk-n", agent_id="a", tenant_id="t1", skill_id="sk-n",
            skill_source="community", input_params=None, created_at=None,
        )
        out = service._skill_to_dict(skill)
        assert out["skill_name"] == "sk-n"
        assert out["skill_type"] == "unknown"
        assert out["description"] == ""
        assert out["category"] == "general"
        assert out["created_at"] is None

    def test_average_rating_hit_and_empty(self, service, db):
        _skill(db, "sk-1")
        service.db.add_all([
            SkillRating(tenant_id="t1", skill_id="sk-1", user_id="u1", rating=5,
                        created_at=datetime.now(timezone.utc)),
            SkillRating(tenant_id="t1", skill_id="sk-1", user_id="u2", rating=3,
                        created_at=datetime.now(timezone.utc)),
        ])
        service.db.commit()
        out = service._get_average_rating("sk-1")
        assert out["average"] == 4.0
        assert out["count"] == 2
        assert service._get_average_rating("nope") == {"average": 0.0, "count": 0}

    def test_get_skill_ratings(self, service, db):
        _skill(db, "sk-1")
        for i in range(4):
            service.db.add(SkillRating(
                tenant_id="t1", skill_id="sk-1", user_id=f"u{i}", rating=i + 1,
                review=f"r{i}", created_at=datetime.now(timezone.utc),
            ))
        service.db.commit()
        out = service._get_skill_ratings("sk-1", limit=2)
        assert len(out) == 2
        assert out[0]["user_id"] is not None
        assert "comment" in out[0]
        assert service._get_skill_ratings("nope") == []


class TestAsyncStubs:
    def test_sync_with_marketplace(self, service):
        asyncio.run(service.sync_with_marketplace())  # no-op, must not raise

    def test_cache_skills(self, service):
        asyncio.run(service._cache_skills([{"id": "1"}]))

    def test_cache_categories(self, service):
        asyncio.run(service._cache_categories([{"name": "a"}]))
