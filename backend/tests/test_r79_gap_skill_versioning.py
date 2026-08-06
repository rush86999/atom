# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: core/skill_versioning_service.py (semver bumping,
snapshots, rollback, comparison; zero test references before this file).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from core.models import Skill, SkillVersion
from core.skill_versioning_service import SkillVersioningService


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine, tables=[Skill.__table__, SkillVersion.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def service(db_session):
    return SkillVersioningService(db_session)


def _make_skill(db, name="webhook-skill", version="1.0.0", tenant_id="t1", code="def run(): pass"):
    skill = Skill(
        tenant_id=tenant_id,
        name=name,
        description="desc",
        version=version,
        type="api",
        input_schema={"input": "x"},
        output_schema={"output": "y"},
        config={"url": "https://example.com"},
        code=code,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


class TestCreateVersion:
    def test_bumps_patch_version(self, db_session, service):
        skill = _make_skill(db_session, version="1.2.3")
        version = service.create_version(skill.id, "changelog", "t1")
        assert version.version == "1.2.4"
        assert skill.version == "1.2.4"
        assert version.skill_id == skill.id

    def test_snapshot_copies_skill_fields(self, db_session, service):
        skill = _make_skill(db_session, code="v1 code")
        version = service.create_version(skill.id, "chg", "t1", is_stable=True)
        assert version.code == "v1 code"
        assert version.name == skill.name
        assert version.config == {"url": "https://example.com"}
        assert version.is_stable is True

    def test_unknown_skill_raises(self, db_session, service):
        with pytest.raises(ValueError):
            service.create_version("nope", "chg", "t1")

    def test_tenant_scoped_lookup(self, db_session, service):
        skill = _make_skill(db_session, tenant_id="t1")
        with pytest.raises(ValueError):
            service.create_version(skill.id, "chg", "other-tenant")

    def test_bump_version_helpers(self, service):
        assert service._bump_version("1.2.3", "major") == "2.0.0"
        assert service._bump_version("1.2.3", "minor") == "1.3.0"
        assert service._bump_version("1.2.3", "patch") == "1.2.4"
        assert service._bump_version("not-semver") == "not-semver"


class TestRollback:
    def test_rollback_restores_fields_and_snapshots(self, db_session, service):
        skill = _make_skill(db_session, code="v1 code", version="1.0.0")
        service.create_version(skill.id, "v1", "t1")
        skill.code = "v2 code"
        db_session.commit()
        v3 = service.create_version(skill.id, "v2", "t1")
        assert skill.version == "1.0.2"

        rolled = service.rollback_to_version(skill.id, v3.id, "t1")
        assert rolled.id == skill.id
        assert rolled.code == "v2 code"
        assert rolled.version == "1.0.2"

    def test_rollback_to_older_version_restores_old_code(self, db_session, service):
        skill = _make_skill(db_session, code="original")
        v1 = service.create_version(skill.id, "v1", "t1")
        skill.code = "changed"
        db_session.commit()
        service.create_version(skill.id, "v2", "t1")

        rolled = service.rollback_to_version(skill.id, v1.id, "t1")
        assert rolled.code == "original"

    def test_rollback_missing_version_raises(self, db_session, service):
        skill = _make_skill(db_session)
        with pytest.raises(ValueError):
            service.rollback_to_version(skill.id, "no-such-version", "t1")

    def test_rollback_missing_skill_raises(self, db_session, service):
        skill = _make_skill(db_session)
        v1 = service.create_version(skill.id, "v1", "t1")
        with pytest.raises(ValueError):
            service.rollback_to_version("no-skill", v1.id, "t1")


class TestHistoryAndCompare:
    def test_version_history_ordered_newest_first(self, db_session, service):
        skill = _make_skill(db_session)
        v1 = service.create_version(skill.id, "first", "t1")
        v2 = service.create_version(skill.id, "second", "t1")
        # SQLite server_default func.now() has second granularity — disambiguate
        v1.created_at = datetime(2026, 1, 1, 10, 0, 0)
        v2.created_at = datetime(2026, 1, 2, 10, 0, 0)
        db_session.commit()
        history = service.get_version_history(skill.id, "t1")
        assert [h["changelog"] for h in history] == ["second", "first"]

    def test_compare_versions_fields(self, db_session, service):
        skill = _make_skill(db_session, code="c1")
        v1 = service.create_version(skill.id, "v1", "t1")
        skill.code = "c2"
        db_session.commit()
        v2 = service.create_version(skill.id, "v2", "t1")
        comparison = service.compare_versions(skill.id, v1.id, v2.id)
        assert comparison["comparison"] == "v1_older"
        assert any(d["field"] == "code" for d in comparison["differences"])

    def test_compare_versions_missing_raises(self, db_session, service):
        skill = _make_skill(db_session)
        v1 = service.create_version(skill.id, "v1", "t1")
        with pytest.raises(ValueError):
            service.compare_versions(skill.id, v1.id, "missing")

    def test_internal_semver_comparison(self, service):
        assert service._compare_versions("1.0.0", "1.0.1") == "v1_older"
        assert service._compare_versions("2.0.0", "1.9.9") == "v1_newer"
        assert service._compare_versions("1.0.0", "1.0.0") == "equal"
        assert service._compare_versions("bad", "1.0.0") == "equal"

    def test_latest_stable_version(self, db_session, service):
        skill = _make_skill(db_session)
        service.create_version(skill.id, "v1", "t1", is_stable=False)
        v2 = service.create_version(skill.id, "v2", "t1", is_stable=True)
        service.create_version(skill.id, "v3", "t1", is_stable=False)
        latest = service.get_latest_version(skill.id)
        assert latest.id == v2.id

    def test_latest_stable_none_when_no_stable(self, db_session, service):
        skill = _make_skill(db_session)
        service.create_version(skill.id, "v1", "t1", is_stable=False)
        assert service.get_latest_version(skill.id) is None
