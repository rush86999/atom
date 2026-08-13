# -*- coding: utf-8 -*-
"""Coverage wave 79 — core/skill_versioning_service.py 92% → 100% (gaps left by
tests/test_r79_gap_skill_versioning.py).

Covers: _bump_version invalid-format fallbacks, rollback_to_version
target-missing + skill-missing branches and full field restore + pre-rollback
snapshot, get_version_history ordering + empty + cross-tenant leak (BUG 79-6:
tenant_id parameter was ignored → any tenant could read another tenant's
version history), compare_versions per-field differences + missing-version
ValueError, _compare_versions malformed input, get_latest_version stable-only
filtering.

Real in-memory SQLite schema, zero LLM spend, no network.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, Skill, SkillVersion
from core.skill_versioning_service import SkillVersioningService


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _skill(db, skill_id="sk1", tenant_id="tenantA", version="1.0.0", **kw):
    skill = Skill(
        id=skill_id,
        tenant_id=tenant_id,
        name=kw.get("name", "Calc"),
        description=kw.get("description", "a calculator"),
        version=version,
        type=kw.get("type", "tool"),
        input_schema=kw.get("input_schema", {"a": "int"}),
        output_schema=kw.get("output_schema", {}),
        config=kw.get("config", {"mode": "fast"}),
        code=kw.get("code", "print(1)"),
        dependencies=kw.get("dependencies", []),
    )
    db.add(skill)
    db.commit()
    return skill


def _version(db, vid, skill_id="sk1", tenant_id="tenantA", version="1.0.0",
             created_days=0, **kw):
    v = SkillVersion(
        id=vid,
        skill_id=skill_id,
        tenant_id=tenant_id,
        version=version,
        changelog=kw.get("changelog", "chg"),
        name=kw.get("name", "Calc"),
        description=kw.get("description", "a calculator"),
        type=kw.get("type", "tool"),
        input_schema=kw.get("input_schema", {"a": "int"}),
        output_schema=kw.get("output_schema", {}),
        config=kw.get("config", {"mode": "fast"}),
        code=kw.get("code", "print(1)"),
        dependencies=kw.get("dependencies", []),
        is_stable=kw.get("is_stable", False),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=created_days),
    )
    db.add(v)
    db.commit()
    return v


# ============================================================================
# _bump_version
# ============================================================================

class TestBumpVersion:
    def test_patch_major_minor(self, db):
        svc = SkillVersioningService(db)
        assert svc._bump_version("1.2.3", "patch") == "1.2.4"
        assert svc._bump_version("1.2.3", "minor") == "1.3.0"
        assert svc._bump_version("1.2.3", "major") == "2.0.0"

    def test_invalid_segment_count_returns_unchanged(self, db):
        svc = SkillVersioningService(db)
        assert svc._bump_version("1.2") == "1.2"
        assert svc._bump_version("1") == "1"

    def test_non_numeric_segments_returns_unchanged(self, db):
        svc = SkillVersioningService(db)
        assert svc._bump_version("a.b.c") == "a.b.c"
        assert svc._bump_version("1.x.3") == "1.x.3"

    def test_empty_string_returns_unchanged(self, db):
        svc = SkillVersioningService(db)
        assert svc._bump_version("") == ""


# ============================================================================
# create_version
# ============================================================================

class TestCreateVersion:
    def test_creates_snapshot_and_bumps_skill(self, db):
        skill = _skill(db, version="1.0.0")
        svc = SkillVersioningService(db)
        version = svc.create_version("sk1", "added feature", "tenantA")
        assert version.version == "1.0.1"
        assert version.skill_id == "sk1"
        assert version.changelog == "added feature"
        assert version.name == "Calc"
        assert version.description == "a calculator"
        assert version.type == "tool"
        assert version.code == "print(1)"
        assert version.dependencies == []
        assert version.is_stable is False
        db.refresh(skill)
        assert skill.version == "1.0.1"

    def test_creates_stable_version(self, db):
        _skill(db, version="2.0.0")
        version = SkillVersioningService(db).create_version(
            "sk1", "stable release", "tenantA", is_stable=True)
        assert version.is_stable is True
        assert version.version == "2.0.1"

    def test_skill_not_found_raises(self, db):
        with pytest.raises(ValueError, match="Skill sk1 not found"):
            SkillVersioningService(db).create_version("sk1", "x", "tenantA")

    def test_tenant_mismatch_skill_not_found(self, db):
        _skill(db, tenant_id="tenantA")
        with pytest.raises(ValueError, match="Skill sk1 not found"):
            SkillVersioningService(db).create_version("sk1", "x", "otherTenant")


# ============================================================================
# rollback_to_version
# ============================================================================

class TestRollback:
    def test_rollback_restores_all_fields(self, db):
        skill = _skill(db, version="1.1.0")
        _version(db, "v-old", version="1.0.0", name="OldName",
                 description="old desc", type="workflow", code="print(0)",
                 input_schema={"b": "str"}, output_schema={"o": 1},
                 config={"mode": "slow"}, dependencies=["dep-old"],
                 is_stable=True)
        svc = SkillVersioningService(db)
        result = svc.rollback_to_version("sk1", "v-old", "tenantA")
        assert result is skill
        assert skill.version == "1.0.0"
        assert skill.name == "OldName"
        assert skill.description == "old desc"
        assert skill.type == "workflow"
        assert skill.code == "print(0)"
        assert skill.input_schema == {"b": "str"}
        assert skill.output_schema == {"o": 1}
        assert skill.config == {"mode": "slow"}
        assert skill.dependencies == ["dep-old"]

    def test_rollback_creates_pre_rollback_snapshot(self, db):
        _skill(db, version="1.1.0")
        _version(db, "v-old", version="1.0.0")
        svc = SkillVersioningService(db)
        svc.rollback_to_version("sk1", "v-old", "tenantA")
        snapshots = db.query(SkillVersion).filter(
            SkillVersion.version == "1.1.0-pre-rollback").all()
        assert len(snapshots) == 1
        assert snapshots[0].changelog == "Pre-rollback snapshot of 1.1.0"
        assert snapshots[0].is_stable is False

    def test_target_version_not_found_raises(self, db):
        _skill(db)
        with pytest.raises(ValueError, match="Target version not found"):
            SkillVersioningService(db).rollback_to_version("sk1", "nope", "tenantA")

    def test_skill_not_found_raises(self, db):
        _version(db, "v1")  # version exists but skill is missing
        with pytest.raises(ValueError, match="Skill not found"):
            SkillVersioningService(db).rollback_to_version("sk1", "v1", "tenantA")

    def test_rollback_other_tenant_skill_not_found(self, db):
        _skill(db, tenant_id="tenantA")
        _version(db, "v1", tenant_id="tenantA")
        with pytest.raises(ValueError, match="Skill not found"):
            SkillVersioningService(db).rollback_to_version("sk1", "v1", "tenantB")


# ============================================================================
# get_version_history (incl. BUG 79-6 tenant scoping)
# ============================================================================

class TestVersionHistory:
    def test_history_newest_first(self, db):
        _skill(db)
        _version(db, "v1", version="1.0.0", created_days=1)
        _version(db, "v2", version="1.0.1", created_days=5)
        history = SkillVersioningService(db).get_version_history("sk1", "tenantA")
        assert [h["version"] for h in history] == ["1.0.1", "1.0.0"]
        assert history[0]["id"] == "v2"
        assert history[0]["changelog"] == "chg"
        assert history[0]["is_stable"] is False
        assert "created_at" in history[0]

    def test_history_empty(self, db):
        _skill(db)
        assert SkillVersioningService(db).get_version_history("sk1", "tenantA") == []

    def test_cross_tenant_history_hidden(self, db):
        """BUG 79-6: get_version_history ignored the tenant_id parameter —
        a caller from another tenant could read the full version history
        (changelogs) of a skill they do not own."""
        _skill(db, tenant_id="tenantA")
        _version(db, "v1", tenant_id="tenantA", version="1.0.0")
        _version(db, "v2", tenant_id="tenantA", version="1.0.1")
        history = SkillVersioningService(db).get_version_history("sk1", "tenantB")
        assert history == []

    def test_same_tenant_history_visible(self, db):
        _skill(db, tenant_id="tenantA")
        _version(db, "v1", tenant_id="tenantA", version="1.0.0")
        history = SkillVersioningService(db).get_version_history("sk1", "tenantA")
        assert len(history) == 1


# ============================================================================
# compare_versions
# ============================================================================

class TestCompareVersions:
    def test_identical_versions_equal(self, db):
        _version(db, "v1", version="1.0.0")
        _version(db, "v2", version="1.0.0")
        result = SkillVersioningService(db).compare_versions("sk1", "v1", "v2")
        assert result["comparison"] == "equal"
        assert result["differences"] == []

    def test_all_field_differences_reported(self, db):
        _version(db, "v1", version="1.0.0", name="A", description="d1",
                 type="tool", config={"m": 1}, input_schema={"x": 1}, code="a")
        _version(db, "v2", version="1.0.1", name="B", description="d2",
                 type="workflow", config={"m": 2}, input_schema={"x": 2}, code="b")
        result = SkillVersioningService(db).compare_versions("sk1", "v1", "v2")
        assert result["comparison"] == "v1_older"
        fields = {d["field"] for d in result["differences"]}
        assert fields == {"name", "description", "type", "config",
                          "input_schema", "code"}
        config_diff = next(d for d in result["differences"] if d["field"] == "config")
        assert config_diff["changed"] is True
        name_diff = next(d for d in result["differences"] if d["field"] == "name")
        assert name_diff["v1"] == "A" and name_diff["v2"] == "B"

    def test_version_metadata_included(self, db):
        _version(db, "v1", version="1.0.0")
        _version(db, "v2", version="1.0.1")
        result = SkillVersioningService(db).compare_versions("sk1", "v1", "v2")
        assert result["version_1"]["id"] == "v1"
        assert result["version_2"]["version"] == "1.0.1"
        assert "created_at" in result["version_1"]

    def test_v1_newer(self, db):
        _version(db, "v1", version="1.1.0")
        _version(db, "v2", version="1.0.0")
        result = SkillVersioningService(db).compare_versions("sk1", "v1", "v2")
        assert result["comparison"] == "v1_newer"

    def test_missing_version_raises(self, db):
        _version(db, "v1", version="1.0.0")
        with pytest.raises(ValueError, match="versions not found"):
            SkillVersioningService(db).compare_versions("sk1", "v1", "missing")
        with pytest.raises(ValueError, match="versions not found"):
            SkillVersioningService(db).compare_versions("sk1", "missing", "v1")

    def test_compare_malformed_versions_equal(self, db):
        # List comparison: [1, 2] < [1, 2, 3] → "1.2" sorts before "1.2.3"
        assert SkillVersioningService(db)._compare_versions("1.2", "1.2.3") == "v1_older"
        assert SkillVersioningService(db)._compare_versions("x.y", "1.2.3") == "equal"


# ============================================================================
# get_latest_version
# ============================================================================

class TestLatestVersion:
    def test_returns_latest_stable(self, db):
        _version(db, "v1", version="1.0.0", is_stable=True, created_days=1)
        _version(db, "v2", version="1.0.1", is_stable=True, created_days=5)
        latest = SkillVersioningService(db).get_latest_version("sk1")
        assert latest.id == "v2"

    def test_unstable_versions_ignored(self, db):
        _version(db, "v1", version="1.0.0", is_stable=False, created_days=1)
        assert SkillVersioningService(db).get_latest_version("sk1") is None

    def test_no_versions_returns_none(self, db):
        assert SkillVersioningService(db).get_latest_version("sk1") is None

    def test_stable_older_preferred_over_unstable_newer(self, db):
        _version(db, "v1", version="1.0.0", is_stable=True, created_days=3)
        _version(db, "v2", version="1.0.1", is_stable=False, created_days=1)
        latest = SkillVersioningService(db).get_latest_version("sk1")
        assert latest.id == "v1"
