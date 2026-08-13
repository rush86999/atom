# -*- coding: utf-8 -*-
"""Coverage wave 72 — core/conflict_resolution_service (in-memory SQLite,
no network, no real DB).

Closes the remaining gaps: MEDIUM severity tier, compare_versions None
handling on the remote side, compare_content both-hashes-present, the
count_unresolved_conflicts filters, merge() timestamp merging (ISO strings
with Z suffix and datetime objects), resolve_conflict local_wins/merge/manual
strategies, and auto_resolve_conflict remote_wins/local_wins/merge return
paths.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ConflictLog
from core.conflict_resolution_service import ConflictResolutionService


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def svc(db):
    return ConflictResolutionService(db)


BASE_LOCAL = {
    "skill_id": "skill-1",
    "name": "Local Skill",
    "version": "1.0.0",
    "code": "def run():\n    return 1",
    "command": "python run.py",
    "python_packages": ["requests"],
    "npm_packages": ["lodash"],
    "description": "local description",
    "tags": ["local"],
    "examples": [],
    "parameters": {"p": 1},
    "metadata": {"m": 1},
    "env_vars": {"K": "V"},
    "local_files": ["main.py"],
}

BASE_REMOTE = {
    "skill_id": "skill-1",
    "name": "Remote Skill",
    "version": "1.0.0",
    "code": "def run():\n    return 1",
    "command": "python run.py",
    "python_packages": ["requests"],
    "npm_packages": ["lodash"],
    "description": "remote description",
    "tags": ["remote"],
    "examples": [],
    "parameters": {"p": 1},
    "metadata": {"m": 1},
    "env_vars": {"K": "V"},
    "local_files": ["main.py"],
}


def _log(svc, skill_id="skill-1", conflict_type="VERSION_MISMATCH", severity="HIGH"):
    return svc.log_conflict(
        skill_id=skill_id,
        conflict_type=conflict_type,
        severity=severity,
        local_data=BASE_LOCAL,
        remote_data=BASE_REMOTE,
    )


# ============================================================================
# detect_skill_conflict
# ============================================================================

def test_detect_version_mismatch(svc):
    local = dict(BASE_LOCAL, version="2.0.0")
    assert svc.detect_skill_conflict(local, BASE_REMOTE) == "VERSION_MISMATCH"


def test_detect_content_mismatch(svc):
    local = dict(BASE_LOCAL, code="def run():\n    return 2")
    assert svc.detect_skill_conflict(local, BASE_REMOTE) == "CONTENT_MISMATCH"


def test_detect_dependency_mismatch(svc):
    local = dict(BASE_LOCAL, python_packages=["requests", "numpy"])
    assert svc.detect_skill_conflict(local, BASE_REMOTE) == "DEPENDENCY_CONFLICT"


def test_detect_no_conflict(svc):
    assert svc.detect_skill_conflict(dict(BASE_LOCAL), dict(BASE_REMOTE)) is None


# ============================================================================
# calculate_severity
# ============================================================================

def test_severity_critical_code(svc):
    local = dict(BASE_LOCAL, code="return 99")
    assert svc.calculate_severity(local, BASE_REMOTE, "CONTENT_MISMATCH") == "CRITICAL"


def test_severity_critical_command(svc):
    local = dict(BASE_LOCAL, command="run.py --prod")
    assert svc.calculate_severity(local, BASE_REMOTE, "CONTENT_MISMATCH") == "CRITICAL"


def test_severity_critical_local_files(svc):
    local = dict(BASE_LOCAL, local_files=[])
    assert svc.calculate_severity(local, BASE_REMOTE, "CONTENT_MISMATCH") == "CRITICAL"


def test_severity_critical_one_sided_field(svc):
    """Field exists on one side only -> unequal -> CRITICAL."""
    local = dict(BASE_LOCAL)
    del local["command"]
    assert svc.calculate_severity(local, BASE_REMOTE, "CONTENT_MISMATCH") == "CRITICAL"


def test_severity_high_version(svc):
    local = dict(BASE_LOCAL, version="2.0.0")
    assert svc.calculate_severity(local, BASE_REMOTE, "VERSION_MISMATCH") == "HIGH"


def test_severity_high_python_packages(svc):
    local = dict(BASE_LOCAL, python_packages=["numpy"])
    assert svc.calculate_severity(local, BASE_REMOTE, "DEPENDENCY_CONFLICT") == "HIGH"


def test_severity_high_npm_packages(svc):
    local = dict(BASE_LOCAL, npm_packages=["react"])
    assert svc.calculate_severity(local, BASE_REMOTE, "DEPENDENCY_CONFLICT") == "HIGH"


def test_severity_medium_parameters(svc):
    local = dict(BASE_LOCAL, parameters={"p": 2})
    assert svc.calculate_severity(local, BASE_REMOTE, "CONTENT_MISMATCH") == "MEDIUM"


def test_severity_medium_metadata(svc):
    local = dict(BASE_LOCAL, metadata={"m": 2})
    assert svc.calculate_severity(local, BASE_REMOTE, "CONTENT_MISMATCH") == "MEDIUM"


def test_severity_medium_env_vars(svc):
    local = dict(BASE_LOCAL, env_vars={"K2": "V2"})
    assert svc.calculate_severity(local, BASE_REMOTE, "CONTENT_MISMATCH") == "MEDIUM"


def test_severity_low_description(svc):
    local = dict(BASE_LOCAL, description="different")
    assert svc.calculate_severity(local, BASE_REMOTE, "CONTENT_MISMATCH") == "LOW"


# ============================================================================
# compare_versions / compare_content / compare_dependencies
# ============================================================================

def test_compare_versions_equal_and_none_handling(svc):
    assert svc.compare_versions(BASE_LOCAL, BASE_REMOTE) is False
    assert svc.compare_versions({"version": None}, {"version": None}) is False
    # remote None falls back to the default -> differs from an explicit bump
    assert svc.compare_versions({"version": "2.0.0"}, {"version": None}) is True
    assert svc.compare_versions({}, {"version": None}) is False  # both defaults
    assert svc.compare_versions({"version": 2}, {"version": "2"}) is False  # str coercion
    assert svc.compare_versions({"version": "1.1.0"}, {"version": "1.2.0"}) is True


def test_compare_content_both_hashes(svc):
    assert svc.compare_content(
        {"content_hash": "abc"}, {"content_hash": "abc"}
    ) is False
    assert svc.compare_content(
        {"content_hash": "abc"}, {"content_hash": "def"}
    ) is True


def test_compare_content_code_fallback(svc):
    assert svc.compare_content({"code": "a"}, {"code": "a"}) is False
    assert svc.compare_content({"code": "a"}, {"code": "a \n "}) is False  # whitespace-normalized
    assert svc.compare_content({"code": "a"}, {"code": "b"}) is True
    assert svc.compare_content({"code": None}, {"code": ""}) is False
    assert svc.compare_content({"code": "a"}, {}) is True


def test_compare_dependencies(svc):
    assert svc.compare_dependencies(BASE_LOCAL, BASE_REMOTE) is False
    assert svc.compare_dependencies(
        {"python_packages": ["numpy"]}, {"python_packages": ["requests"]}
    ) is True
    assert svc.compare_dependencies(
        {"npm_packages": ["react"]}, {"npm_packages": ["lodash"]}
    ) is True
    # unsorted lists compare equal after sorting
    assert svc.compare_dependencies(
        {"python_packages": ["b", "a"]}, {"python_packages": ["a", "b"]}
    ) is False
    # non-list values degrade to [] instead of crashing
    assert svc.compare_dependencies(
        {"python_packages": "requests"}, {"python_packages": ["requests"]}
    ) is True


def test_calculate_content_hash(svc):
    h1 = svc.calculate_content_hash(BASE_LOCAL)
    assert len(h1) == 64
    assert h1 == svc.calculate_content_hash(BASE_LOCAL)
    assert h1 != svc.calculate_content_hash(dict(BASE_LOCAL, code="x"))


# ============================================================================
# log_conflict / queries
# ============================================================================

def test_log_conflict_roundtrip(svc):
    conflict = _log(svc, conflict_type="CONTENT_MISMATCH", severity="MEDIUM")
    assert conflict.id is not None
    assert conflict.resolved_at is None
    assert conflict.resolution_strategy is None
    assert conflict.local_data["name"] == "Local Skill"


def test_get_unresolved_conflicts_filters(svc, db):
    _log(svc, conflict_type="VERSION_MISMATCH", severity="HIGH")
    _log(svc, conflict_type="CONTENT_MISMATCH", severity="MEDIUM")
    resolved = _log(svc, conflict_type="DEPENDENCY_CONFLICT", severity="LOW")
    resolved.resolution_strategy = "remote_wins"
    resolved.resolved_at = datetime.now(timezone.utc)
    db.commit()

    assert len(svc.get_unresolved_conflicts()) == 2
    assert len(svc.get_unresolved_conflicts(severity="MEDIUM")) == 1
    assert len(svc.get_unresolved_conflicts(conflict_type="CONTENT_MISMATCH")) == 1
    assert len(svc.get_unresolved_conflicts(severity="HIGH", conflict_type="VERSION_MISMATCH")) == 1
    assert len(svc.get_unresolved_conflicts(severity="LOW")) == 0
    assert len(svc.get_unresolved_conflicts(limit=1, offset=1)) == 1
    assert len(svc.get_unresolved_conflicts(limit=0)) == 0


def test_count_unresolved_conflicts(svc, db):
    _log(svc, conflict_type="VERSION_MISMATCH", severity="HIGH")
    _log(svc, conflict_type="CONTENT_MISMATCH", severity="MEDIUM")
    _log(svc, conflict_type="DEPENDENCY_CONFLICT", severity="LOW")
    assert svc.count_unresolved_conflicts() == 3
    assert svc.count_unresolved_conflicts(severity="HIGH") == 1
    assert svc.count_unresolved_conflicts(conflict_type="CONTENT_MISMATCH") == 1
    assert svc.count_unresolved_conflicts(severity="HIGH", conflict_type="CONTENT_MISMATCH") == 0


def test_get_conflict_by_id(svc, db):
    conflict = _log(svc)
    assert svc.get_conflict_by_id(conflict.id) is not None
    assert svc.get_conflict_by_id(99999) is None


# ============================================================================
# strategies
# ============================================================================

def test_remote_wins(svc):
    result = svc.remote_wins(BASE_LOCAL, BASE_REMOTE)
    assert result == BASE_REMOTE
    assert result is not BASE_REMOTE  # copy


def test_local_wins(svc):
    result = svc.local_wins(BASE_LOCAL, BASE_REMOTE)
    assert result == BASE_LOCAL
    assert result is not BASE_LOCAL


def test_merge_automatic_fields_and_critical(svc):
    local = dict(BASE_LOCAL, description="short", tags=["l"], updated_at="2026-08-01T10:00:00Z")
    remote = dict(BASE_REMOTE, description="a much longer remote description", tags=["r"], updated_at="2026-08-05T10:00:00Z")
    merged = svc.merge(local, remote)
    assert merged["description"] == remote["description"]  # longer wins
    assert merged["tags"] == ["l"]  # equal str length -> local kept
    assert merged["code"] == local["code"]  # critical stays local
    assert merged["command"] == local["command"]
    assert merged["local_files"] == local["local_files"]
    assert merged["version"] == "1.0.0+merged+1.0.0"
    assert isinstance(merged["updated_at"], datetime)  # parsed, not string
    assert merged["updated_at"].isoformat().startswith("2026-08-05T10:00:00")


def test_merge_dependencies_union_sorted(svc):
    local = dict(BASE_LOCAL, python_packages=["b", "a"], npm_packages=["z"])
    remote = dict(BASE_REMOTE, python_packages=["c", "a"], npm_packages=["y"])
    merged = svc.merge(local, remote)
    assert merged["python_packages"] == ["a", "b", "c"]
    assert merged["npm_packages"] == ["y", "z"]


def test_merge_datetime_objects_and_fallback(svc):
    dt1 = datetime(2026, 8, 1, 10, 0, 0)
    dt2 = datetime(2026, 8, 3, 10, 0, 0)
    local = dict(BASE_LOCAL, updated_at=dt1)
    remote = dict(BASE_REMOTE, updated_at=dt2)
    assert svc.merge(local, remote)["updated_at"] == dt2
    # only one side has updated_at -> stays unmerged
    merged = svc.merge(dict(BASE_LOCAL, updated_at=dt1), dict(BASE_REMOTE))
    assert merged["updated_at"] == dt1


def test_merge_missing_skill_id(svc):
    merged = svc.merge({"name": "l"}, {"name": "r"})
    assert merged["version"] == "1.0.0+merged+1.0.0"


def test_manual_logs_conflict(svc, db):
    result = svc.manual(BASE_LOCAL, BASE_REMOTE, "skill-9", "VERSION_MISMATCH", "HIGH")
    assert result is None
    assert db.query(ConflictLog).filter(
        ConflictLog.skill_id == "skill-9"
    ).count() == 1


# ============================================================================
# resolve_conflict / auto_resolve_conflict
# ============================================================================

def test_resolve_conflict_not_found(svc):
    assert svc.resolve_conflict(99999, "remote_wins", "user") is None


def test_resolve_conflict_remote_wins(svc, db):
    conflict = _log(svc)
    result = svc.resolve_conflict(conflict.id, "remote_wins", "user-1")
    assert result == BASE_REMOTE
    db.refresh(conflict)
    assert conflict.resolution_strategy == "remote_wins"
    assert conflict.resolved_by == "user-1"
    assert conflict.resolved_at is not None


def test_resolve_conflict_local_wins(svc, db):
    conflict = _log(svc)
    result = svc.resolve_conflict(conflict.id, "local_wins", "user-1")
    assert result == BASE_LOCAL
    db.refresh(conflict)
    assert conflict.resolution_strategy == "local_wins"


def test_resolve_conflict_merge(svc, db):
    conflict = _log(svc)
    result = svc.resolve_conflict(conflict.id, "merge", "user-1")
    assert result["version"] == "1.0.0+merged+1.0.0"
    db.refresh(conflict)
    assert conflict.resolution_strategy == "merge"


def test_resolve_conflict_manual_keeps_unresolved(svc, db):
    conflict = _log(svc)
    assert svc.resolve_conflict(conflict.id, "manual", "user-1") is None
    db.refresh(conflict)
    assert conflict.resolved_at is None
    assert conflict.resolution_strategy is None


def test_auto_resolve_no_conflict_returns_remote(svc):
    result = svc.auto_resolve_conflict(dict(BASE_LOCAL), dict(BASE_REMOTE), "merge")
    assert result == BASE_REMOTE


def test_auto_resolve_remote_wins(svc):
    local = dict(BASE_LOCAL, version="2.0.0")
    result = svc.auto_resolve_conflict(local, BASE_REMOTE, "remote_wins")
    assert result == BASE_REMOTE


def test_auto_resolve_local_wins(svc):
    local = dict(BASE_LOCAL, version="2.0.0")
    result = svc.auto_resolve_conflict(local, BASE_REMOTE, "local_wins")
    assert result == local


def test_auto_resolve_merge(svc):
    local = dict(BASE_LOCAL, version="2.0.0", python_packages=["a", "b"])
    remote = dict(BASE_REMOTE, python_packages=["b", "c"])
    result = svc.auto_resolve_conflict(local, remote, "merge")
    assert result["python_packages"] == ["a", "b", "c"]
    assert result["version"] == "2.0.0+merged+1.0.0"


def test_auto_resolve_manual_logs(svc, db):
    local = dict(BASE_LOCAL, version="2.0.0")
    assert svc.auto_resolve_conflict(local, BASE_REMOTE, "manual") is None
    assert db.query(ConflictLog).filter(
        ConflictLog.skill_id == "skill-1"
    ).count() == 1


def test_auto_resolve_unknown_strategy(svc):
    local = dict(BASE_LOCAL, version="2.0.0")
    assert svc.auto_resolve_conflict(local, BASE_REMOTE, "bogus") is None
