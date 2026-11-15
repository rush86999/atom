"""Scheduler SQLAlchemy job-store path anchoring + legacy adoption.

The observed bug: the default ``sqlite:///jobs.sqlite`` is CWD-relative, so a
repo-root launch and a ``backend/`` launch used two stores; a job written
under one was absent under the other. These controls pin:

* the canonical URL resolver (relative/absolute/memory/file-URI/query/
  postgres/redis forms);
* actual APScheduler persistence across two fresh processes launched from
  different scratch CWDs with the default URL and the same synthetic backend
  anchor (far-future job only; nothing executes);
* startup reconciliation: absent/fresh, adoption with byte preservation,
  canonical-vs-legacy conflict (no clobber), ambiguous legacy (loud refusal),
  and non-canonical/absolute stores untouched.

Fixture seams (disclosed): the subprocess children use a synthetic backend
root passed to the production resolver and stub ``reschedule_system_pipelines``
(the same seam used by existing scheduler tests) so no system-pipeline import
is needed. All DB/job-store paths are absolute scratch paths; no worktree or
live ``backend/jobs.sqlite`` is opened.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core.scheduler_store as store
from core.local_paths import anchor_sqlite_url

JOB_ID = "scheduler_anchoring_probe"
SYNTH_BACKEND = "backend"


@pytest.fixture(autouse=True)
def _reset_store_state():
    store.reset_scheduler_store_state()
    yield
    store.reset_scheduler_store_state()


def _legacy_sqlite(path: Path, marker: str = "legacy") -> bytes:
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE probe_marker (marker TEXT)")
        con.execute("INSERT INTO probe_marker (marker) VALUES (?)", (marker,))
        con.commit()
    finally:
        con.close()
    return path.read_bytes()


# ---------------------------------------------------------------------------
# URL resolver
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url, expected",
    [
        ("sqlite:///jobs.sqlite", "canonical"),
        ("sqlite:///./jobs.sqlite", "canonical"),
        ("sqlite+pysqlite:///jobs.sqlite", "canonical"),
        ("sqlite+pysqlite:///./data/jobs.sqlite", "canonical-nested"),
        ("sqlite:////tmp/absolute-jobs.sqlite", "unchanged"),
        ("sqlite:///:memory:", "unchanged"),
        ("sqlite://", "unchanged"),
        ("sqlite:///file:memdb1?mode=memory&cache=shared&uri=true", "unchanged"),
        ("sqlite:///file:/tmp/jobs.sqlite?mode=ro&uri=true", "unchanged"),
        ("postgresql://localhost/jobs", "unchanged"),
        ("redis://localhost:6379/1", "unchanged"),
    ],
)
def test_resolver_anchors_only_relative_sqlite_files(tmp_path, url, expected):
    root = tmp_path / SYNTH_BACKEND
    resolved = store.resolve_scheduler_job_store_url(url, root)
    if expected == "canonical":
        assert resolved == f"sqlite:///{root / 'jobs.sqlite'}" or resolved == (
            f"sqlite+pysqlite:///{root / 'jobs.sqlite'}")
    elif expected == "canonical-nested":
        assert resolved == f"sqlite+pysqlite:///{root / 'data' / 'jobs.sqlite'}"
    else:
        assert resolved == url


def test_relative_query_string_is_preserved(tmp_path):
    root = tmp_path / SYNTH_BACKEND
    resolved = store.resolve_scheduler_job_store_url(
        "sqlite:///jobs.sqlite?timeout=10", root)
    assert resolved == f"sqlite:///{root / 'jobs.sqlite'}?timeout=10"


def test_database_anchor_helper_preserves_file_uri():
    """The shared helper also protects the app DB from file-URI mangling."""
    from core.database import _anchor_sqlite_url

    url = "sqlite:///file:memdb1?mode=memory&cache=shared&uri=true"
    assert _anchor_sqlite_url(url) == url


def test_anchor_never_changes_non_sqlite_or_empty_values(tmp_path):
    root = tmp_path / SYNTH_BACKEND
    for value in ("", None, "postgresql://u:p@host/db", "redis://host/0"):
        assert anchor_sqlite_url(value, root) == value


def test_config_construction_is_side_effect_free(tmp_path, monkeypatch):
    """Importing/constructing config must not create or move the store."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCHEDULER_JOB_STORE_URL", raising=False)
    from core.config import SchedulerConfig

    assert SchedulerConfig().job_store_url == "sqlite:///jobs.sqlite"
    assert not (tmp_path / "jobs.sqlite").exists()


# ---------------------------------------------------------------------------
# Actual scheduler persistence across fresh processes / CWDs
# ---------------------------------------------------------------------------
CHILD = r"""
import asyncio, json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.local_paths import anchor_sqlite_url
from ai.workflow_scheduler import WorkflowScheduler
from core.config import SchedulerConfig

step = sys.argv[1]
root = Path(os.environ["SYNTH_BACKEND_ROOT"])
# The module-level singleton was constructed with an absolute scratch URL
# above; pop it so SchedulerConfig() exposes the actual default input.
os.environ.pop("SCHEDULER_JOB_STORE_URL", None)
configured_url = SchedulerConfig().job_store_url
resolved = anchor_sqlite_url(configured_url, root)
run_at = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()

def _store_path(url):
    return Path(url.partition(":///")[2])

async def main():
    scheduler = WorkflowScheduler(db_url=resolved)
    existed_before_start = _store_path(scheduler.job_store_url).exists()
    scheduler.reschedule_system_pipelines = lambda: None
    scheduler.start()
    try:
        if step == "add":
            scheduler.scheduler.add_job(
                scheduler._execute_job, "date", run_date=run_at,
                args=["nonexistent-anchoring-workflow", {}, False],
                id=os.environ["JOB_ID"], replace_existing=True)
        jobs = []
        for job in scheduler.scheduler.get_jobs():
            if job.id == os.environ["JOB_ID"]:
                jobs.append({
                    "id": job.id,
                    "next_run_time": job.next_run_time.isoformat() if getattr(job, "next_run_time", None) else None,
                    "args0": job.args[0] if job.args else None,
                })
        result = {
            "step": step, "pid": os.getpid(), "cwd": os.getcwd(),
            "configured_url": configured_url,
            "resolved_url": resolved,
            "job_store_url": scheduler.job_store_url,
            "store_existed_before_start": existed_before_start,
            "jobs": jobs,
        }
        if step == "remove":
            scheduler.scheduler.remove_job(os.environ["JOB_ID"])
            result["removed"] = True
            result["remaining"] = [j.id for j in scheduler.scheduler.get_jobs()
                                   if j.id == os.environ["JOB_ID"]]
        print("RESULT:" + json.dumps(result))
    finally:
        scheduler.shutdown()

asyncio.run(main())
"""


def _child_env(tmp_path: Path, backend_root: Path) -> dict:
    env = os.environ.copy()
    scratch = tmp_path / "child"
    scratch.mkdir()
    for key in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY",
        "GROQ_API_KEY", "TOGETHER_API_KEY", "OPENCODE_API_KEY",
        "MISTRAL_API_KEY", "XAI_API_KEY", "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT", "TELEGRAM_BOT_TOKEN",
        "OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET",
        "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "SHOPIFY_WEBHOOK_SECRET",
    ):
        env[key] = ""
    env.update({
        "TESTING": "0",
        "ENVIRONMENT": "development",
        "DATABASE_URL": f"sqlite:///{scratch / 'app.db'}",
        "SCHEDULER_JOB_STORE_TYPE": "sqlalchemy",
        # The module-level singleton must not point at a worktree store.
        "SCHEDULER_JOB_STORE_URL": f"sqlite:///{scratch / 'singleton.db'}",
        "ATOM_DATA_DIR": str(scratch / "data"),
        "LANCEDB_URI": str(scratch / "lancedb"),
        "LANCEDB_URI_BASE": str(scratch / "lancedb"),
        "BYOK_CONFIG_FILE": str(scratch / "byok_config.json"),
        "BYOK_KEYS_FILE": str(scratch / "byok_keys.json"),
        "BYOK_ENC_KEY_FILE": str(scratch / "byok_enc_key"),
        "SYNTH_BACKEND_ROOT": str(backend_root),
        "JOB_ID": JOB_ID,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
    })
    return env


def _run_child(script: Path, cwd: Path, env: dict, step: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(script), step], cwd=str(cwd), env=env,
        capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, (result.stdout, result.stderr)
    payload = None
    for line in result.stdout.splitlines():
        if line.startswith("RESULT:"):
            payload = json.loads(line.split("RESULT:", 1)[1])
    assert payload is not None, (result.stdout, result.stderr)
    return payload


def test_default_scheduler_store_persists_across_cwds_and_processes(tmp_path):
    backend_root = tmp_path / SYNTH_BACKEND
    backend_root.mkdir(parents=True)
    cwd_a = tmp_path / "cwd-a"
    cwd_b = tmp_path / "cwd-b"
    cwd_a.mkdir()
    cwd_b.mkdir()
    script = tmp_path / "child_scheduler.py"
    script.write_text(textwrap.dedent(CHILD))
    env = _child_env(tmp_path, backend_root)

    added = _run_child(script, cwd_a, env, "add")
    restarted = _run_child(script, cwd_b, env, "check")
    removed = _run_child(script, cwd_a, env, "remove")
    final = _run_child(script, cwd_b, env, "check")

    canonical = backend_root / "jobs.sqlite"
    assert canonical.is_file()
    assert added["configured_url"] == "sqlite:///jobs.sqlite"
    assert restarted["configured_url"] == added["configured_url"]
    assert added["resolved_url"] == f"sqlite:///{canonical}"
    assert added["store_existed_before_start"] is False
    assert restarted["resolved_url"] == added["resolved_url"]
    assert added["cwd"] != restarted["cwd"]
    assert added["pid"] != restarted["pid"]
    assert added["jobs"] and restarted["jobs"]
    assert added["jobs"][0]["next_run_time"] == restarted["jobs"][0]["next_run_time"]
    assert added["jobs"][0]["args0"] == "nonexistent-anchoring-workflow"
    assert removed["removed"] is True and removed["remaining"] == []
    assert final["jobs"] == []
    # A different CWD never created a second relative store.
    assert not (cwd_a / "jobs.sqlite").exists()
    assert not (cwd_b / "jobs.sqlite").exists()


# ---------------------------------------------------------------------------
# Legacy reconciliation
# ---------------------------------------------------------------------------
def test_fresh_install_and_canonical_present_are_noops(tmp_path):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    fresh = store.reconcile_scheduler_job_store(
        "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert fresh["status"] == "fresh"
    assert not (backend / "jobs.sqlite").exists()

    canonical = backend / "jobs.sqlite"
    canonical.write_bytes(b"canonical-bytes")
    present = store.reconcile_scheduler_job_store(
        "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert present["status"] == "canonical_present"
    assert canonical.read_bytes() == b"canonical-bytes"


def test_legacy_is_adopted_byte_identically_and_preserved(tmp_path):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    legacy = tmp_path / "jobs.sqlite"
    original = _legacy_sqlite(legacy)

    result = store.reconcile_scheduler_job_store(
        "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    canonical = backend / "jobs.sqlite"
    assert result["status"] == "adopted"
    assert result["original_preserved"] is True
    assert canonical.read_bytes() == original
    assert legacy.read_bytes() == original  # original untouched
    assert store._sha256(canonical) == result["canonical_sha256"]


def test_conflict_refuses_automatic_selection_and_preserves_both(tmp_path):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    canonical = backend / "jobs.sqlite"
    legacy = tmp_path / "jobs.sqlite"
    canonical.write_bytes(b"canonical-authoritative")
    _legacy_sqlite(legacy)

    with pytest.raises(store.SchedulerStoreConflict):
        store.reconcile_scheduler_job_store(
            "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert canonical.read_bytes() == b"canonical-authoritative"
    assert legacy.exists()


def test_ambiguous_legacy_refuses_adoption(tmp_path):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    legacy = tmp_path / "jobs.sqlite"
    legacy.mkdir()
    with pytest.raises(store.SchedulerStoreConflict):
        store.reconcile_scheduler_job_store(
            "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert not (backend / "jobs.sqlite").exists()


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_legacy_with_sqlite_sidecars_refuses_adoption(tmp_path, suffix):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    legacy = tmp_path / "jobs.sqlite"
    _legacy_sqlite(legacy)
    Path(str(legacy) + suffix).write_bytes(b"uncheckpointed")
    with pytest.raises(store.SchedulerStoreConflict):
        store.reconcile_scheduler_job_store(
            "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert not (backend / "jobs.sqlite").exists()


def test_sidecar_appearing_during_copy_refuses_adoption(tmp_path, monkeypatch):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    legacy = tmp_path / "jobs.sqlite"
    original = _legacy_sqlite(legacy)

    def copy_then_open_writer(src, dst):
        Path(dst).write_bytes(Path(src).read_bytes())
        Path(str(src) + "-wal").write_bytes(b"writer-opened-after-check")

    monkeypatch.setattr(store.shutil, "copy2", copy_then_open_writer)
    with pytest.raises(store.SchedulerStoreConflict):
        store.reconcile_scheduler_job_store(
            "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert not (backend / "jobs.sqlite").exists()
    assert legacy.read_bytes() == original
    assert not list(backend.glob(".*adopt-*"))


def test_legacy_symlink_refuses_adoption(tmp_path):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    target = tmp_path / "real-jobs.sqlite"
    target.write_bytes(b"x")
    legacy = tmp_path / "jobs.sqlite"
    legacy.symlink_to(target)
    with pytest.raises(store.SchedulerStoreConflict):
        store.reconcile_scheduler_job_store(
            "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert not (backend / "jobs.sqlite").exists()


def test_concurrent_canonical_appearance_does_not_clobber(tmp_path, monkeypatch):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    legacy = tmp_path / "jobs.sqlite"
    _legacy_sqlite(legacy)
    canonical = backend / "jobs.sqlite"

    def raise_exists(src, dst):
        canonical.write_bytes(b"appeared-concurrently")
        raise FileExistsError

    monkeypatch.setattr(store.os, "link", raise_exists)
    with pytest.raises(store.SchedulerStoreConflict):
        store.reconcile_scheduler_job_store(
            "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert canonical.read_bytes() == b"appeared-concurrently"
    assert legacy.exists()
    assert not list(backend.glob(".*adopt-*"))


def test_real_wal_writer_is_refused_and_clean_close_adopts(tmp_path):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    legacy = tmp_path / "jobs.sqlite"
    con = sqlite3.connect(legacy)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE jobs (id TEXT)")
        con.execute("INSERT INTO jobs VALUES ('committed-wal')")
        con.commit()
        wal = Path(str(legacy) + "-wal")
        assert wal.exists()
        with pytest.raises(store.SchedulerStoreConflict):
            store.reconcile_scheduler_job_store(
                "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
        assert not (backend / "jobs.sqlite").exists()
        assert con.execute("SELECT id FROM jobs").fetchone()[0] == "committed-wal"
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("PRAGMA journal_mode=DELETE")
    finally:
        con.close()
    assert not Path(str(legacy) + "-wal").exists()
    assert not Path(str(legacy) + "-shm").exists()

    result = store.reconcile_scheduler_job_store(
        "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert result["status"] == "adopted"
    con2 = sqlite3.connect(backend / "jobs.sqlite")
    try:
        assert con2.execute("SELECT id FROM jobs").fetchone()[0] == "committed-wal"
    finally:
        con2.close()


def test_unsupported_hardlink_fails_closed_without_canonical(tmp_path, monkeypatch):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    legacy = tmp_path / "jobs.sqlite"
    original = _legacy_sqlite(legacy)

    def unsupported(src, dst):
        raise OSError(45, "Operation not supported")

    monkeypatch.setattr(store.os, "link", unsupported)
    with pytest.raises(store.SchedulerStoreConflict):
        store.reconcile_scheduler_job_store(
            "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert not (backend / "jobs.sqlite").exists()
    assert legacy.read_bytes() == original
    assert not list(backend.glob(".*adopt-*"))


def test_disk_full_during_copy_publishes_no_canonical(tmp_path, monkeypatch):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    legacy = tmp_path / "jobs.sqlite"
    original = _legacy_sqlite(legacy)

    def partial_copy(src, dst):
        Path(dst).write_bytes(b"partial")
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(store.shutil, "copy2", partial_copy)
    with pytest.raises(store.SchedulerStoreConflict):
        store.reconcile_scheduler_job_store(
            "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert not (backend / "jobs.sqlite").exists()
    assert legacy.read_bytes() == original
    assert not list(backend.glob(".*adopt-*"))


def test_known_unsafe_store_refuses_schedule_list_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHEDULER_JOB_STORE_TYPE", "sqlalchemy")
    monkeypatch.setenv(
        "SCHEDULER_JOB_STORE_URL", f"sqlite:///{tmp_path / 'singleton.db'}")
    from ai.workflow_scheduler import WorkflowScheduler

    scheduler = WorkflowScheduler(db_url=f"sqlite:///{tmp_path / 'never.db'}")
    store.mark_scheduler_store_failed("two stores disagree")
    far = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    with pytest.raises(store.SchedulerStoreUnavailable):
        scheduler.schedule_workflow("wf", "date", {"run_date": far})
    with pytest.raises(store.SchedulerStoreUnavailable):
        scheduler.schedule_workflow_cron("job", "wf", "* * * * *")
    with pytest.raises(store.SchedulerStoreUnavailable):
        scheduler.list_jobs()
    with pytest.raises(store.SchedulerStoreUnavailable):
        scheduler.remove_schedule("job")
    with pytest.raises(store.SchedulerStoreUnavailable):
        scheduler.reschedule_system_pipelines()
    with pytest.raises(store.SchedulerStoreUnavailable):
        scheduler.start()


def test_unverified_state_keeps_legitimate_pre_start_component_use():
    store.reset_scheduler_store_state()
    store.require_scheduler_store_ready()  # no raise


def test_startup_helper_marks_ready_on_success_and_failed_on_refusal(tmp_path):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    result = store.reconcile_and_mark_scheduler_store(
        "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert result["status"] == "fresh"
    assert store.scheduler_store_state()["ready"] is True

    store.reset_scheduler_store_state()
    canonical = backend / "jobs.sqlite"
    canonical.write_bytes(b"canonical")
    (tmp_path / "jobs.sqlite").write_bytes(b"legacy")
    with pytest.raises(store.SchedulerStoreConflict):
        store.reconcile_and_mark_scheduler_store(
            "sqlite:///jobs.sqlite", root=backend, legacy_root=tmp_path)
    assert store.scheduler_store_state()["ready"] is False
    assert "both canonical" in store.scheduler_store_state()["reason"]
    assert canonical.read_bytes() == b"canonical"
    assert (tmp_path / "jobs.sqlite").read_bytes() == b"legacy"


def test_schedule_endpoint_does_not_swallow_unsafe_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHEDULER_JOB_STORE_TYPE", "sqlalchemy")
    monkeypatch.setenv(
        "SCHEDULER_JOB_STORE_URL", f"sqlite:///{tmp_path / 'singleton.db'}")
    from ai.workflow_scheduler import workflow_scheduler
    from core import workflow_endpoints as endpoints
    from core.scheduler_store import SchedulerStoreUnavailable

    monkeypatch.setattr(
        endpoints, "_find_visible_workflow",
        lambda *args, **kwargs: {"id": "wf", "steps": [], "nodes": []})
    async def _allow(*args, **kwargs):
        return None
    monkeypatch.setattr(endpoints, "require_workflow_executor", _allow)
    monkeypatch.setattr(
        endpoints.RBACService, "check_permission",
        staticmethod(lambda *args, **kwargs: False))
    monkeypatch.setattr(
        "core.workflow_engine.freeze_execution_scope",
        lambda data, **kwargs: data)
    monkeypatch.setattr(
        workflow_scheduler, "schedule_workflow",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SchedulerStoreUnavailable("two stores disagree")))
    with pytest.raises(SchedulerStoreUnavailable):
        asyncio.run(endpoints.schedule_workflow(
            "wf",
            {"trigger_type": "interval", "trigger_config": {"minutes": 60}},
            user=SimpleNamespace(id="u", workspace_id="w", tenant_id="t"),
            db=MagicMock()))


def test_list_and_remove_endpoints_refuse_known_unsafe_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHEDULER_JOB_STORE_TYPE", "sqlalchemy")
    monkeypatch.setenv(
        "SCHEDULER_JOB_STORE_URL", f"sqlite:///{tmp_path / 'singleton.db'}")
    from core import workflow_endpoints as endpoints
    from core.scheduler_store import SchedulerStoreUnavailable

    store.mark_scheduler_store_failed("two stores disagree")
    user = SimpleNamespace(id="u", workspace_id="w", tenant_id="t")
    with pytest.raises(SchedulerStoreUnavailable):
        asyncio.run(endpoints.list_scheduled_jobs(user=user))
    with pytest.raises(SchedulerStoreUnavailable):
        asyncio.run(endpoints.unschedule_workflow("wf", "job", user=user))


def test_noncanonical_absolute_and_non_sqlite_stores_are_untouched(tmp_path):
    backend = tmp_path / SYNTH_BACKEND
    backend.mkdir()
    legacy = tmp_path / "jobs.sqlite"
    _legacy_sqlite(legacy)

    absolute = store.reconcile_scheduler_job_store(
        f"sqlite:///{tmp_path / 'elsewhere.sqlite'}", root=backend,
        legacy_root=tmp_path)
    assert absolute["status"] == "not_canonical"
    assert not (backend / "jobs.sqlite").exists()
    assert legacy.exists()

    for url in ("sqlite:///:memory:", "sqlite://", "postgresql://localhost/jobs",
                "redis://localhost:6379/1",
                "sqlite:///file:memdb1?mode=memory&uri=true"):
        result = store.reconcile_scheduler_job_store(
            url, root=backend, legacy_root=tmp_path)
        assert result["status"] == "not_sqlite_file"
    assert not (backend / "jobs.sqlite").exists()
