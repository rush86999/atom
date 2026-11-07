"""Release-kit local backup -> isolated restore contract tests.

Scratch only: TESTING=1, unique temp DB/data/office/email/Lance/output.  No
live DB, world, provider, account, send, spend, install, deploy, or restart of
the live app.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.models  # noqa: F401 - register all models
from core.models import (
    AgentRegistry,
    Canvas,
    CanvasAudit,
    DatasetEntry,
    GoalRun,
    IngestedDocument,
    Tenant,
    User,
    Workspace,
)
from core.models_registration import Base

KIT = Path(__file__).resolve().parents[1]
RELEASE_TOOL = KIT / "release_tool.py"
sys.path.insert(0, str(KIT))
import restore_support  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _env(source: Path, *, office: Path | None = None,
         email: Path | None = None, memory: Path | None = None,
         include_memory: bool = False) -> dict:
    env = dict(os.environ)
    env.update({
        "TESTING": "1",
        "ENVIRONMENT": "test",
        "SECRET_KEY": "synthetic-restore-test",
        "ATOM_DATA_DIR": str(source),
        "DATABASE_URL": f"sqlite:///{source / 'atom.db'}",
        "ATOM_OFFICE_DIR": str(office or source / "office"),
        "ATOM_EMAIL_ATTACHMENT_DIR": str(email or source / "email_attachments"),
        "LANCEDB_URI": str(memory or source / "atom_memory"),
        "LANCEDB_URI_BASE": str(memory or source / "atom_memory"),
        "ATOM_OUTPUT_DIR": str(source / "output"),
        "TMPDIR": str(source / "basetemp"),
    })
    if include_memory:
        env["RESTORE_TEST_MEMORY"] = "1"
    return env


def _make_world(tmp_path: Path, *, external_office: bool = False) -> dict:
    source = tmp_path / "source"
    office = (tmp_path / "external-office") if external_office else (source / "office")
    for path in (source, office, source / "email_attachments", source / "sheet_datasets",
                 source / "atom_memory", source / "docs", source / "output",
                 source / "basetemp"):
        path.mkdir(parents=True, exist_ok=True)

    # Real office artifact and a real parquet artifact.
    from docx import Document
    office_file = office / "restored.docx"
    doc = Document()
    doc.add_paragraph("restored artifact text")
    doc.save(office_file)
    email_file = source / "email_attachments" / "user-1" / "canvas-1" / "staged_restore"
    email_file.parent.mkdir(parents=True, exist_ok=True)
    email_file.write_bytes(b"email attachment bytes")
    parquet = source / "sheet_datasets" / "default" / "ds-1" / "sheet.parquet"
    parquet.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"value": [1, 2]}).to_parquet(parquet)
    # Manual uploads are materialized under ATOM_OFFICE_DIR/uploads (real
    # document upload path), so the office store is the managed authority.
    document_file = office / "uploads" / "document.txt"
    document_file.parent.mkdir(parents=True, exist_ok=True)
    document_file.write_text("restored document text")

    engine = create_engine(f"sqlite:///{source / 'atom.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add_all([
            Tenant(id="tenant-1", name="Tenant One", subdomain="tenant-one"),
            Workspace(id="ws-1", name="Workspace One", tenant_id="tenant-1"),
        ])
        db.flush()
        db.add(User(
            id="user-1", email="user@example.invalid", hashed_password="x",
            first_name="User", last_name="One", role="owner", status="active",
            tenant_id="tenant-1", workspace_id="ws-1", is_active=True,
        ))
        db.add(AgentRegistry(
            id="agent-1", name="Agent One", category="operations",
            module_path="x.a", class_name="A", status="autonomous",
            enabled=True, tenant_id="tenant-1", workspace_id="ws-1",
        ))
        db.flush()
        content = {"office_file": str(office_file), "file_path": str(office_file),
                   "format": "docx"}
        db.add(Canvas(
            id="canvas-1", tenant_id="tenant-1", workspace_id="ws-1",
            created_by="user-1", name="Restored office", canvas_type="office_word",
            content=content, status="active",
        ))
        db.add(CanvasAudit(
            id="audit-1", canvas_id="canvas-1", tenant_id="tenant-1",
            action_type="update", user_id="user-1", agent_id="agent-1",
            canvas_type="office_word", details_json={"content": content},
        ))
        db.add(IngestedDocument(
            id="doc-1", workspace_id="ws-1", tenant_id="tenant-1",
            file_name="document.txt", file_path=str(document_file),
            file_type="txt", integration_id="upload", external_id="doc-1",
            file_size_bytes=document_file.stat().st_size,
        ))
        db.add(DatasetEntry(
            id="ds-1", workspace_id="ws-1", tenant_id="tenant-1", created_by="user-1",
            source_kind="file", source="upload", external_id="ds-1",
            file_name="sheet.xlsx", content_hash="content-hash", entity_name="Sheet1",
            dataset_name="sheet1", parquet_path=str(parquet), row_count=2,
            column_count=1, columns_json=["value"], status="active",
        ))
        db.add(GoalRun(
            id="run-1", tenant_id="tenant-1", workspace_id="ws-1",
            goal_id="goal-1", agent_id="agent-1", role="sales", status="active",
            supervision_mode="shadow", plan=[],
            parameters={"task_lifecycle": {"assignment": {
                "steps": [{"inputs": {"path": str(office_file)}}],
                "deliverables": [{"artifact_path": str(parquet)}],
            }}},
        ))
        db.commit()
    engine.dispose()
    return {
        "source": source, "office": office, "office_file": office_file,
        "email_file": email_file, "parquet": parquet, "document_file": document_file,
    }


def _run(cmd, *, cwd: Path, env: dict):
    return subprocess.run(
        [sys.executable, str(RELEASE_TOOL), "--root", str(cwd), *cmd],
        cwd=str(cwd), env=env, text=True, capture_output=True, timeout=120,
    )


def _backup_world(tmp_path: Path, *, external_office: bool = False,
                  include_memory: bool = False):
    world = _make_world(tmp_path, external_office=external_office)
    root = tmp_path / "release"
    root.mkdir(parents=True, exist_ok=True)
    env = _env(world["source"], office=world["office"],
               email=world["source"] / "email_attachments",
               memory=world["source"] / "atom_memory")
    cmd = ["backup", "--label", "restore-test"]
    if include_memory:
        cmd.append("--include-memory")
    proc = _run(cmd, cwd=root, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    return world, root, env, Path(payload["backup"])


def _restore(backup: Path, target: Path, *, root: Path, env: dict):
    proc = _run([
        "restore", "--backup", str(backup), "--target-data-dir", str(target),
    ], cwd=root, env=env)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"raw": proc.stdout, "stderr": proc.stderr}
    return proc, payload


def _copy_backup(backup: Path, tmp_path: Path, name: str = "bad-backup") -> Path:
    dest = tmp_path / name
    shutil.copytree(backup, dest)
    return dest


def _refresh_manifest_file(backup: Path, name: str) -> None:
    manifest_path = backup / "BACKUP_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    target = backup / name
    manifest["files"][name] = {
        "sha256": _sha(target), "bytes": target.stat().st_size,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))


def _target_session_factory(target: Path):
    engine = create_engine(f"sqlite:///{target / 'atom.db'}")
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    return engine, Session, _session


def test_roundtrip_and_source_absent_portability(tmp_path, monkeypatch):
    world, root, env, backup = _backup_world(tmp_path, external_office=True)
    target = tmp_path / "target"
    proc, result = _restore(backup, target, root=root, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result["status"] == "verified", result
    assert result["memory_included"] is False
    assert result["memory_restored"] is False

    # The original source must be gone before any restored read.
    world["source"].rename(tmp_path / "source-unavailable")
    if world["office"] != world["source"] / "office":
        world["office"].rename(tmp_path / "external-office-unavailable")
    engine, Session, session_cm = _target_session_factory(target)
    import core.database
    monkeypatch.setattr(core.database, "get_db_session", session_cm)
    monkeypatch.setattr(core.database, "SessionLocal", Session)
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(target / "office"))
    monkeypatch.setenv("ATOM_DATA_DIR", str(target))
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(target / "email_attachments"))
    monkeypatch.setenv("LANCEDB_URI", str(target / "atom_memory"))

    import asyncio
    from tools.canvas_crud_tool import read_canvas
    canvas = asyncio.run(read_canvas("user-1", "canvas-1"))
    assert canvas["success"] is True, canvas
    office_file = canvas["content"]["office_file"]
    assert office_file.startswith(str(target / "office")), canvas
    assert Path(office_file).is_file()

    with Session() as db:
        user = db.query(User).filter(User.id == "user-1").one()
        doc = db.query(IngestedDocument).filter(IngestedDocument.id == "doc-1").one()
        dataset = db.query(DatasetEntry).filter(DatasetEntry.id == "ds-1").one()
        run = db.query(GoalRun).filter(GoalRun.id == "run-1").one()
        assert user.email == "user@example.invalid"
        assert doc.file_path.startswith(str(target / "office" / "uploads")), doc.file_path
        assert Path(doc.file_path).is_file()
        assert dataset.parquet_path.startswith(str(target / "sheet_datasets")), dataset.parquet_path
        assert pd.read_parquet(dataset.parquet_path)["value"].tolist() == [1, 2]
        assignment = run.parameters["task_lifecycle"]["assignment"]
        assert assignment["steps"][0]["inputs"]["path"].startswith(str(target / "office"))
        assert assignment["deliverables"][0]["artifact_path"].startswith(str(target / "sheet_datasets"))
        assert Path(assignment["steps"][0]["inputs"]["path"]).is_file()
    assert (target / "email_attachments" / "user-1" / "canvas-1" / "staged_restore").is_file()
    engine.dispose()

    # Fresh engine/session readback after the target is the only source.
    engine2, Session2, session_cm2 = _target_session_factory(target)
    monkeypatch.setattr(core.database, "get_db_session", session_cm2)
    monkeypatch.setattr(core.database, "SessionLocal", Session2)
    with Session2() as db:
        assert db.query(User).filter(User.id == "user-1").count() == 1
        assert db.query(Canvas).filter(Canvas.id == "canvas-1").count() == 1
    engine2.dispose()


def test_wal_committed_row_is_in_backup_and_restore(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    conn = sqlite3.connect(world["source"] / "atom.db")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("INSERT INTO users (id, email, hashed_password, first_name, last_name, role, status, is_active) VALUES ('wal-user','wal@example.invalid','x','W','L','member','active',1)")
    conn.commit()
    # Keep the WAL connection open while the backup runs.
    proc = _run(["backup", "--label", "wal-test"], cwd=root, env=env)
    conn.close()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    wal_backup = Path(json.loads(proc.stdout)["backup"])
    target = tmp_path / "target-wal"
    proc2, result = _restore(wal_backup, target, root=root, env=env)
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    assert result["status"] == "verified", result
    con = sqlite3.connect(target / "atom.db")
    try:
        assert con.execute("SELECT COUNT(*) FROM users WHERE id='wal-user'").fetchone()[0] == 1
    finally:
        con.close()


def test_memory_included_restores_content(tmp_path):
    pytest.importorskip("lancedb")
    import lancedb
    world = _make_world(tmp_path)
    memory = world["source"] / "atom_memory"
    mem_db = lancedb.connect(str(memory))
    mem_db.create_table("documents", [{"id": "m1", "content": "restored memory content"}])
    del mem_db
    root = tmp_path / "release"
    root.mkdir()
    env = _env(world["source"], office=world["office"],
               email=world["source"] / "email_attachments",
               memory=world["source"] / "atom_memory", include_memory=True)
    proc = _run(["backup", "--label", "memory-test", "--include-memory"], cwd=root, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    backup = Path(json.loads(proc.stdout)["backup"])
    target = tmp_path / "target-memory"
    proc2, result = _restore(backup, target, root=root, env=env)
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    assert result["status"] == "verified", result
    assert result["memory_included"] is True and result["memory_restored"] is True
    world["source"].rename(tmp_path / "source-unavailable")
    restored = lancedb.connect(str(target / "atom_memory"))
    rows = restored.open_table("documents").to_arrow().to_pylist()
    assert any(row["content"] == "restored memory content" for row in rows), rows


def test_manifest_hash_mismatch_refused_with_no_target(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    bad = _copy_backup(backup, tmp_path)
    (bad / "office" / "restored.docx").write_bytes(b"tampered")
    target = tmp_path / "target-bad"
    proc, result = _restore(bad, target, root=root, env=env)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert result["status"] == "refused", result
    assert not target.exists()


def test_missing_artifact_refused(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    bad = _copy_backup(backup, tmp_path)
    (bad / "office" / "restored.docx").unlink()
    target = tmp_path / "target-missing"
    proc, result = _restore(bad, target, root=root, env=env)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert result["status"] == "refused", result
    assert not target.exists()


def test_corrupt_database_refused(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    bad = _copy_backup(backup, tmp_path)
    (bad / "atom.db").write_bytes(b"not a sqlite database")
    _refresh_manifest_file(bad, "atom.db")
    target = tmp_path / "target-corrupt"
    proc, result = _restore(bad, target, root=root, env=env)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert result["status"] == "refused", result
    assert not target.exists()


def test_manifest_path_escape_refused(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    bad = _copy_backup(backup, tmp_path)
    manifest_path = bad / "BACKUP_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["../escape"] = {"sha256": "0" * 64, "bytes": 0}
    manifest_path.write_text(json.dumps(manifest))
    target = tmp_path / "target-escape"
    proc, result = _restore(bad, target, root=root, env=env)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert result["status"] == "refused", result
    assert not target.exists()


def test_manifest_colliding_paths_refused(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    bad = _copy_backup(backup, tmp_path)
    manifest_path = bad / "BACKUP_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    first = "office/restored.docx"
    second = "office/RESTORED.DOCX"
    manifest["files"][second] = manifest["files"][first]
    manifest_path.write_text(json.dumps(manifest))
    target = tmp_path / "target-collision"
    proc, result = _restore(bad, target, root=root, env=env)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert result["status"] == "refused", result
    assert not target.exists()


def test_manifest_symlink_and_hardlink_refused(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    for kind in ("symlink", "hardlink"):
        bad = _copy_backup(backup, tmp_path, name=f"bad-{kind}")
        artifact = bad / "office" / "restored.docx"
        artifact.unlink()
        if kind == "symlink":
            artifact.symlink_to(outside)
        else:
            os.link(outside, artifact)
        _refresh_manifest_file(bad, "office/restored.docx")
        target = tmp_path / f"target-{kind}"
        proc, result = _restore(bad, target, root=root, env=env)
        assert proc.returncode == 2, (kind, proc.stdout + proc.stderr)
        assert result["status"] == "refused", (kind, result)
        assert not target.exists()


def test_existing_or_live_target_refused(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    target = tmp_path / "target-existing"
    target.mkdir()
    (target / "keep.txt").write_text("keep")
    proc, result = _restore(backup, target, root=root, env=env)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert result["status"] == "refused", result
    assert (target / "keep.txt").read_text() == "keep"

    live_target = world["source"]
    proc2, result2 = _restore(backup, live_target, root=root, env=env)
    assert proc2.returncode == 2, proc2.stdout + proc2.stderr
    assert result2["status"] == "refused", result2


def test_concurrent_target_claim_one_winner(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    target = tmp_path / "target-concurrent"
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        try:
            return restore_support.restore_backup(
                backup_arg=str(backup), target_arg=str(target), env=env)
        except restore_support.RestoreRefused as exc:
            return {"status": "refused", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    statuses = [item.get("status") for item in results]
    assert statuses.count("verified") == 1, results
    assert statuses.count("refused") == 1, results
    assert (target / "atom.db").is_file()


def test_source_change_during_copy_refused(tmp_path, monkeypatch):
    world, root, env, backup = _backup_world(tmp_path)
    real_copy = restore_support.shutil.copyfile
    changed = [False]

    def tamper(source, destination, *args, **kwargs):
        real_copy(source, destination, *args, **kwargs)
        if str(source).endswith("restored.docx") and not changed[0]:
            changed[0] = True
            Path(source).write_bytes(Path(source).read_bytes() + b"x")

    monkeypatch.setattr(restore_support.shutil, "copyfile", tamper)
    target = tmp_path / "target-source-change"
    with pytest.raises(restore_support.RestoreRefused):
        restore_support.restore_backup(
            backup_arg=str(backup), target_arg=str(target), env=env)
    assert not target.exists()


def test_postpublish_verification_failure_is_committed_unverified(tmp_path, monkeypatch):
    world, root, env, backup = _backup_world(tmp_path)
    real_verify = restore_support._verify_database
    calls = [0]

    def flaky(path, counts):
        calls[0] += 1
        if calls[0] >= 4:
            raise RuntimeError("controlled post-publish verification failure")
        return real_verify(path, counts)

    monkeypatch.setattr(restore_support, "_verify_database", flaky)
    target = tmp_path / "target-uncertain"
    result = restore_support.restore_backup(
        backup_arg=str(backup), target_arg=str(target), env=env)
    assert result["status"] == "committed_unverified", result
    assert target.exists()


def test_unknown_schema_and_absolute_path_refused(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    bad = _copy_backup(backup, tmp_path, name="bad-schema")
    manifest_path = bad / "BACKUP_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema"] = "unknown-schema"
    manifest_path.write_text(json.dumps(manifest))
    proc, result = _restore(bad, tmp_path / "target-schema", root=root, env=env)
    assert proc.returncode == 2 and result["status"] == "refused", result

    bad2 = _copy_backup(backup, tmp_path, name="bad-absolute")
    manifest_path2 = bad2 / "BACKUP_MANIFEST.json"
    manifest2 = json.loads(manifest_path2.read_text())
    manifest2["files"]["/tmp/escape"] = {"sha256": "0" * 64, "bytes": 0}
    manifest_path2.write_text(json.dumps(manifest2))
    proc2, result2 = _restore(bad2, tmp_path / "target-absolute", root=root, env=env)
    assert proc2.returncode == 2 and result2["status"] == "refused", result2


def test_duplicate_manifest_key_refused(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    bad = _copy_backup(backup, tmp_path, name="bad-duplicate")
    manifest_path = bad / "BACKUP_MANIFEST.json"
    original = manifest_path.read_text()
    # Duplicate the schema key at the object level; json.loads must reject it
    # before any target work.
    manifest_path.write_text('{"schema": "atom-assignment-release-backup-1", ' + original[1:])
    proc, result = _restore(bad, tmp_path / "target-duplicate", root=root, env=env)
    assert proc.returncode == 2 and result["status"] == "refused", result


def test_target_symlink_refused(tmp_path):
    world, root, env, backup = _backup_world(tmp_path)
    real_target = tmp_path / "real-target"
    real_target.mkdir()
    link_target = tmp_path / "target-symlink"
    link_target.symlink_to(real_target)
    proc, result = _restore(backup, link_target, root=root, env=env)
    assert proc.returncode == 2 and result["status"] == "refused", result
    assert not any(real_target.iterdir())


def test_unresolved_managed_reference_refuses_before_publish(tmp_path):
    world = _make_world(tmp_path)
    outside = str(tmp_path / "outside-office.docx")
    Path(outside).write_bytes(b"outside")
    con = sqlite3.connect(world["source"] / "atom.db")
    con.execute("UPDATE canvases SET content=? WHERE id='canvas-1'",
                (json.dumps({"office_file": outside, "file_path": outside,
                             "format": "docx"}),))
    con.execute("UPDATE canvas_audit SET details_json=? WHERE id='audit-1'",
                (json.dumps({"content": {"office_file": outside,
                                          "file_path": outside,
                                          "format": "docx"}}),))
    con.commit(); con.close()
    root = tmp_path / "release"
    root.mkdir()
    env = _env(world["source"], office=world["office"])
    proc = _run(["backup", "--label", "unresolved"], cwd=root, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    backup = Path(json.loads(proc.stdout)["backup"])
    target = tmp_path / "target-unresolved"
    proc2, result = _restore(backup, target, root=root, env=env)
    assert proc2.returncode == 2, proc2.stdout + proc2.stderr
    assert result["status"] == "refused", result
    assert "portability" in result.get("error", ""), result
    assert not target.exists()


def test_backup_resolution_refuses_ambiguous_or_missing_config(tmp_path):
    world = _make_world(tmp_path)
    env = _env(world["source"])
    other = tmp_path / "other.db"
    other.write_bytes(b"x")
    bad = dict(env)
    bad["DATABASE_URL"] = f"sqlite:///{other}"
    with pytest.raises(restore_support.BackupConfigError):
        restore_support.resolve_backup_sources(bad, False)
    bad2 = dict(env)
    bad2["ATOM_OFFICE_DIR"] = str(tmp_path / "missing-office")
    with pytest.raises(restore_support.BackupConfigError):
        restore_support.resolve_backup_sources(bad2, False)
    bad3 = dict(env)
    bad3["LANCEDB_URI"] = "s3://bucket/memory"
    with pytest.raises(restore_support.BackupConfigError):
        restore_support.resolve_backup_sources(bad3, True)


def test_external_configured_office_is_recorded_and_restored(tmp_path):
    world, root, env, backup = _backup_world(tmp_path, external_office=True)
    manifest = json.loads((backup / "BACKUP_MANIFEST.json").read_text())
    assert manifest["store_roots"]["office"]["source"] == str(world["office"])
    assert (backup / "office" / "restored.docx").is_file()
    target = tmp_path / "target-external"
    proc, result = _restore(backup, target, root=root, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result["status"] == "verified", result
    assert (target / "office" / "restored.docx").is_file()
