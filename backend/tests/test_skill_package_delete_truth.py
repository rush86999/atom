"""Contract tests for verified Skill Builder package deletion.

Three properties are load-bearing and each gets its own failure-first case:

1. **Admin deletion actually removes the package.** ``POST /api/admin/skills/``
   publishes ``{root}/{tenant}/skills/{name}``; before WA-069 nothing in the
   admin API could delete it. The route must retire the published directory,
   purge the quarantine and scope every path to the acting admin's stored
   tenant — never to the request body.
2. **A retry after an interrupted retirement resumes the operation.** The
   receipt is committed as ``pending`` *before* the filesystem effect. A crash
   between the quarantine rename and the finalize must therefore be recoverable
   by replaying the same ``operation_id``; it must never look like a ``404``
   whose package was "already gone".
3. **The audit receipt is durable.** It is re-read from a fresh engine/session
   after the original session is closed, and it carries the exact operation,
   actor, tenant, target digests and observed outcome.

Everything here uses a scratch SQLite receipt ledger and a scratch skills root.
No test touches ``backend/data`` or a live database.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.admin import skill_routes
from core.database import Base
from core.models import AuditEventType, AuditLog, SecurityLevel, User, UserRole
from core.skill_builder_service import SkillBuilderService, SkillMetadata
from core.skill_package_delete_service import (
    SKILL_PACKAGE_DELETE_SCHEMA,
    _fingerprint,
)


class _Interrupted(BaseException):
    """Stands in for a process death between effect and receipt finalize."""


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'skill-delete-truth.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    admin = User(
        id="u-admin", email="admin@example.com", hashed_password="h",
        first_name="Ada", last_name="Admin",
        role=UserRole.WORKSPACE_ADMIN.value, status="active",
        tenant_id="t-a", workspace_id="ws-a", is_active=True)
    other_admin = User(
        id="u-admin-b", email="other-admin@example.com", hashed_password="h",
        first_name="Bo", last_name="Admin",
        role=UserRole.WORKSPACE_ADMIN.value, status="active",
        tenant_id="t-b", workspace_id="ws-b", is_active=True)
    session.add_all([admin, other_admin])
    session.commit()

    root = tmp_path / "workspaces"
    monkeypatch.setenv("ATOM_WORKSPACE_SKILLS_ROOT", str(root))

    yield session, admin, other_admin, root, engine

    session.close()
    engine.dispose()


def _seed(root: Path, tenant_id: str, name: str,
          scripts: dict | None = None) -> Path:
    builder = SkillBuilderService(workspace_root=str(root))
    result = builder.create_skill_package(
        tenant_id=tenant_id,
        metadata=SkillMetadata(
            name=name, description=f"{name} description",
            capabilities=["test"]),
        scripts=scripts or {"run.py": "print('hello')\n"},
    )
    assert result["success"], result
    return Path(result["path"])


async def _delete(db, admin, skill_id: str, operation_id=None):
    return await skill_routes.delete_skill_package(
        skill_id=skill_id, operation_id=operation_id, admin=admin, db=db)


def _op_id(supplied: str) -> str:
    """The service namespaces every supplied operation id on the receipt."""
    return f"skill-package:delete:{supplied}"


def _receipt(db, operation_id: str) -> AuditLog:
    return db.query(AuditLog).filter(AuditLog.id == operation_id).one()


def _metadata(receipt: AuditLog) -> dict:
    return json.loads(receipt.metadata_json or "{}")


# ---------------------------------------------------------------------------
# Admin deletion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_delete_retires_purges_and_writes_receipt(scratch):
    db, admin, _other, root, _engine = scratch
    package = _seed(root, "t-a", "Weekly Digest")
    assert (package / "SKILL.md").is_file()

    out = await _delete(db, admin, "Weekly Digest", "w-a-1")

    assert out["success"] is True
    assert out["data"]["deleted"] is True
    assert out["data"]["outcome"] == "verified"
    assert out["data"]["effects"] == {
        "package": "retired", "quarantine": "deleted", "pre_files": 2}
    assert out["metadata"]["verification"]["status"] == "verified"
    assert out["metadata"]["verification"]["effect"] == "committed"

    assert not package.exists()
    tenant = root / "t-a"
    assert not (tenant / "skills" / package.name).exists()
    assert not (tenant / ".skill-trash" / package.name).exists()
    assert list((tenant / "skills").iterdir()) == []

    receipt = _receipt(db, out["metadata"]["operation_id"])
    assert receipt.event_type == AuditEventType.DELETE.value
    assert receipt.action == "skill_package_deleted"
    assert receipt.security_level == SecurityLevel.HIGH.value
    assert receipt.user_id == "u-admin"
    assert receipt.tenant_id == "t-a"
    assert receipt.workspace_id == "ws-a"
    assert receipt.success is True
    meta = _metadata(receipt)
    assert meta["outcome"] == "verified"
    assert meta["package"] == package.name
    assert meta["pre_files"] == 2


@pytest.mark.asyncio
async def test_admin_delete_is_tenant_scoped_and_traversal_safe(scratch):
    db, admin, other_admin, root, _engine = scratch
    foreign = _seed(root, "t-b", "report")

    # A foreign tenant's identically named package is invisible: the acting
    # admin's tenant has no such package, so the answer is a truthful 404.
    with pytest.raises(HTTPException) as missing:
        await _delete(db, admin, "report", "w-a-missing-tenant")
    assert missing.value.status_code == 404
    assert foreign.is_dir()
    assert db.query(AuditLog).count() == 0

    # Traversal/separator material is normalized to one path segment, so it
    # can never address another tenant's directory.
    with pytest.raises(HTTPException) as escaped:
        await _delete(db, admin, "../t-b/skills/report", "w-a-traversal")
    assert escaped.value.status_code == 404
    assert foreign.is_dir()
    assert db.query(AuditLog).count() == 0

    # The owning tenant can still delete its own copy, and only that copy.
    own = _seed(root, "t-a", "report")
    await _delete(db, other_admin, "report", "w-b-own")
    assert not foreign.exists()
    assert own.is_dir()


@pytest.mark.asyncio
async def test_delete_requires_workspace_admin_authority(scratch):
    db, _admin, _other, root, _engine = scratch
    package = _seed(root, "t-a", "guarded")
    member = User(
        id="u-member", email="member@example.com", hashed_password="h",
        first_name="Mem", last_name="Ber", role=UserRole.MEMBER.value,
        status="active", tenant_id="t-a", workspace_id="ws-a",
        is_active=True)
    db.add(member)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        await _delete(db, member, "guarded", "w-member")
    assert exc.value.status_code == 403
    assert package.is_dir()
    assert db.query(AuditLog).count() == 0


@pytest.mark.asyncio
async def test_second_delete_with_new_operation_is_no_change(scratch):
    db, admin, _other, root, _engine = scratch
    _seed(root, "t-a", "once")

    first = await _delete(db, admin, "once", "w-first")
    second = await _delete(db, admin, "once", "w-second")

    assert first["metadata"]["verification"]["status"] == "verified"
    assert second["success"] is True
    assert second["metadata"]["verification"]["status"] == "no_change"
    assert second["data"]["outcome"] == "no_change"
    assert db.query(AuditLog).count() == 1, "no_change invented a receipt"


@pytest.mark.asyncio
async def test_same_operation_id_for_another_package_conflicts(scratch):
    db, admin, _other, root, _engine = scratch
    _seed(root, "t-a", "alpha")
    beta = _seed(root, "t-a", "beta")

    await _delete(db, admin, "alpha", "w-shared")
    with pytest.raises(HTTPException) as exc:
        await _delete(db, admin, "beta", "w-shared")

    assert exc.value.status_code == 409
    assert beta.is_dir()
    assert db.query(AuditLog).count() == 1


@pytest.mark.asyncio
async def test_symlinked_package_is_refused_not_resolved(scratch):
    """A symlink is refused, never resolved onto (and deleting) its target."""
    db, admin, _other, root, _engine = scratch
    real = _seed(root, "t-a", "real")
    skills = root / "t-a" / "skills"
    (skills / "alias").symlink_to(real, target_is_directory=True)

    with pytest.raises(HTTPException) as exc:
        await _delete(db, admin, "alias", "w-alias")

    assert exc.value.status_code == 409
    assert (skills / "alias").is_symlink()
    assert real.is_dir()
    assert db.query(AuditLog).count() == 0


# ---------------------------------------------------------------------------
# Retry after an interrupted retirement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_after_rename_before_purge_resumes_and_verifies(
        scratch, monkeypatch):
    """Crash after the quarantine rename: retry must finish, not 404."""
    db, admin, _other, root, engine = scratch
    _seed(root, "t-a", "interrupted")

    import core.skill_package_delete_service as svc

    real_purge = svc._purge
    calls = {"purge": 0}

    def crash_after_rename(trash):
        calls["purge"] += 1
        if calls["purge"] == 1:
            raise _Interrupted("process died after retire")
        return real_purge(trash)

    monkeypatch.setattr(svc, "_purge", crash_after_rename)
    with pytest.raises(_Interrupted):
        await _delete(db, admin, "interrupted", "w-interrupted")

    # Interrupt left the durable intent and the retired directory behind.
    pending = _receipt(db, _op_id("w-interrupted"))
    assert pending.success is False
    assert _metadata(pending)["outcome"] == "pending"
    assert not (root / "t-a" / "skills" / "interrupted").exists()
    assert (root / "t-a" / ".skill-trash" / "interrupted").is_dir()

    # A fresh session sees the pending receipt — the crash did not lose it.
    with sessionmaker(bind=engine)() as observer:
        pending_again = observer.query(AuditLog).filter(
            AuditLog.id == _op_id("w-interrupted")).one()
        assert _metadata(pending_again)["outcome"] == "pending"

    retried = await _delete(db, admin, "interrupted", "w-interrupted")

    assert retried["success"] is True
    assert retried["data"]["outcome"] == "verified"
    assert retried["metadata"]["verification"]["status"] == "verified"
    assert not (root / "t-a" / ".skill-trash" / "interrupted").exists()

    final = _receipt(db, _op_id("w-interrupted"))
    assert final.success is True
    assert _metadata(final)["outcome"] == "verified"
    assert db.query(AuditLog).count() == 1, "retry duplicated the receipt"
    assert calls["purge"] == 2, "retry did not purge the stale quarantine"

    # The same operation id now replays without another filesystem effect.
    replay = await _delete(db, admin, "interrupted", "w-interrupted")
    assert replay["metadata"]["verification"]["status"] == "already_applied"
    assert calls["purge"] == 2
    assert db.query(AuditLog).count() == 1


@pytest.mark.asyncio
async def test_retry_after_purge_before_finalize_finalizes_verified(
        scratch, monkeypatch):
    """Crash after the purge: retry must finalize the receipt, not 404."""
    db, admin, _other, root, _engine = scratch
    _seed(root, "t-a", "late-crash")

    import core.skill_package_delete_service as svc

    real_finalize = svc._finalize
    calls = {"finalize": 0}

    def crash_before_finalize(*args, **kwargs):
        calls["finalize"] += 1
        if calls["finalize"] == 1:
            raise _Interrupted("process died before finalize")
        return real_finalize(*args, **kwargs)

    monkeypatch.setattr(svc, "_finalize", crash_before_finalize)
    with pytest.raises(_Interrupted):
        await _delete(db, admin, "late-crash", "w-late")

    assert not (root / "t-a" / "skills" / "late-crash").exists()
    assert not (root / "t-a" / ".skill-trash" / "late-crash").exists()
    assert _metadata(_receipt(db, _op_id("w-late")))["outcome"] == "pending"

    retried = await _delete(db, admin, "late-crash", "w-late")

    assert retried["success"] is True
    assert retried["metadata"]["verification"]["status"] == "verified"
    final = _receipt(db, _op_id("w-late"))
    assert final.success is True
    assert _metadata(final)["outcome"] == "verified"
    assert _metadata(final)["pre_files"] == 2, "retry lost the counted files"
    assert db.query(AuditLog).count() == 1


@pytest.mark.asyncio
async def test_resumed_retry_keeps_the_original_target_digest(
        scratch, monkeypatch):
    db, admin, _other, root, _engine = scratch
    _seed(root, "t-a", "digest-stable")

    import core.skill_package_delete_service as svc

    real_purge = svc._purge
    calls = {"purge": 0}

    def crash_once(trash):
        calls["purge"] += 1
        if calls["purge"] == 1:
            raise _Interrupted("boom")
        return real_purge(trash)

    monkeypatch.setattr(svc, "_purge", crash_once)
    with pytest.raises(_Interrupted):
        await _delete(db, admin, "digest-stable", "w-digest")

    before = _receipt(db, _op_id("w-digest"))
    retried = await _delete(db, admin, "digest-stable", "w-digest")
    after = _receipt(db, _op_id("w-digest"))

    expected_target = _fingerprint(
        "skill-package-target", "t-a", "digest-stable")
    assert _metadata(before)["target_digest"] == expected_target
    assert _metadata(after)["target_digest"] == expected_target
    assert retried["metadata"]["target_id"] == expected_target


# ---------------------------------------------------------------------------
# Durable audit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_receipt_survives_engine_restart_and_replays_once(scratch):
    db, admin, _other, root, engine = scratch
    _seed(root, "t-a", "durable")

    out = await _delete(db, admin, "durable", "w-durable")
    operation_id = out["metadata"]["operation_id"]

    db.close()
    engine.dispose()

    # Simulate a restarted process: brand new engine, session and ORM user.
    restarted_engine = create_engine(
        f"sqlite:///{engine.url.database}",
        connect_args={"check_same_thread": False},
    )
    restarted = sessionmaker(bind=restarted_engine)()
    try:
        receipt = _receipt(restarted, operation_id)
        assert receipt.success is True
        meta = _metadata(receipt)
        assert meta["schema"] == SKILL_PACKAGE_DELETE_SCHEMA
        assert meta["operation_id"] == operation_id
        assert meta["outcome"] == "verified"
        assert meta["event_type"] == AuditEventType.DELETE.value
        assert meta["tenant_id"] == "t-a"
        assert meta["workspace_id"] == "ws-a"
        assert meta["package"] == "durable"
        assert meta["target_digest"] == _fingerprint(
            "skill-package-target", "t-a", "durable")
        assert meta["request_digest"] == _fingerprint(
            "skill-package-delete-request", "t-a", "durable")
        assert not (root / "t-a" / "skills" / "durable").exists()

        fresh_admin = restarted.query(User).filter(User.id == "u-admin").one()
        replay = await _delete(
            restarted, fresh_admin, "durable", operation_id)
        assert replay["metadata"]["verification"]["status"] == (
            "already_applied")
        assert replay["metadata"]["verification"]["replay"] == (
            "do_not_repeat")
        assert restarted.query(AuditLog).count() == 1
    finally:
        restarted.close()
        restarted_engine.dispose()


@pytest.mark.asyncio
async def test_partial_cleanup_is_truthful_and_durable(scratch, monkeypatch):
    """A refused purge is reported 503, recorded, and never retried blindly."""
    db, admin, _other, root, _engine = scratch
    _seed(root, "t-a", "stuck")

    import core.skill_package_delete_service as svc

    def refuse_purge(_trash):
        return "delete_failed"

    monkeypatch.setattr(svc, "_purge", refuse_purge)

    with pytest.raises(HTTPException) as exc:
        await _delete(db, admin, "stuck", "w-stuck")

    assert exc.value.status_code == 503
    detail = exc.value.detail
    assert detail["verification"]["status"] == "committed_unverified"
    assert detail["verification"]["effect"] == "partial"
    assert detail["verification"]["replay"] == "do_not_repeat"
    assert not (root / "t-a" / "skills" / "stuck").exists()
    assert (root / "t-a" / ".skill-trash" / "stuck").is_dir()

    receipt = _receipt(db, detail["operation_id"])
    assert receipt.success is False
    meta = _metadata(receipt)
    assert meta["outcome"] == "committed_unverified"
    assert meta["package_effect"] == "retired"
    assert meta["quarantine_effect"] == "delete_failed"

    with pytest.raises(HTTPException) as replay_exc:
        await _delete(db, admin, "stuck", "w-stuck")
    assert replay_exc.value.status_code == 503
    assert (replay_exc.value.detail["verification"]["status"]
            == "committed_unverified")
    assert db.query(AuditLog).count() == 1
