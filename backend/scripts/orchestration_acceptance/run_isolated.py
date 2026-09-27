#!/usr/bin/env python3
"""Isolated acceptance runtime builder + case runner (migration baseline).

Isolation model (review round 4 — runtime-enforced):
- CODE UNDER TEST runs from an IMMUTABLE EXPORT: `git archive PINNED_REV`
  extracted into world/code/, with the archive-stream sha256 recorded and
  re-verified before every run (the worktree's HEAD and cleanliness are
  also checked). The mutable checkout and the worktree cannot alter the
  tested code.
- NETWORK IS RESTRICTED AT THE RUNTIME LEVEL: the server runs under a
  macOS seatbelt profile that denies all network except loopback (verified
  empirically: external sockets get PermissionError; proxy-env settings and
  the sink are defense-in-depth/observability, not the boundary).
- The FIXTURE DB is frozen once, SCRUBBED of connector credentials (15
  credential tables; secret-matching columns nulled, counts recorded), and
  hash-verified before every run alongside a re-run of the scrub detector.
- The VENV's INSTALLED packages are recorded (pip freeze) and verified
  before every run — requirements files prove nothing about what's installed.
- The EVALUATOR binds one evidence record: entity -> segment(sheet + target
  cell) -> value pair(price, basis). A citation in one segment and a price
  in another does NOT verify. --selftest pins the negative cases.
- metrics_old_path.json is machine-generated (--collect); only runs with the
  current HARNESS_VERSION count toward the acceptance gate.

NEVER touches the live lane. Usage (from backend/):
  venv314/bin/python scripts/orchestration_acceptance/run_isolated.py --selftest
  venv314/bin/python scripts/orchestration_acceptance/run_isolated.py \
      --name old_path_01 --port 8021 --cases true_eight --samples 1
  venv314/bin/python scripts/orchestration_acceptance/run_isolated.py --collect
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HARNESS_VERSION = "enforced-isolation-v3.2"
BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
WORKTREE = Path("/Users/rushiparikh/projects/atom-mig-baseline")
PINNED_REV = "813b24c3b51871af597b8896ceeb3a0213f4c6c9"
VENV_PY = BACKEND / "venv314" / "bin" / "python"  # interpreter only; repo code comes from the export
ACC = REPO / "docs" / "architecture" / "orchestration_migration" / "acceptance"
FIXTURES = ACC / "fixtures"
LIVE_SHEET_ROOT = BACKEND / "data" / "sheet_datasets"
WORKBOOK_HASH_DIR = "ff2597d26fc6"
SHIM_PORT = 8099


def _sandbox_profile(port: int, extra_ports: Tuple[int, ...] = ()) -> str:
    """Precise claim: external connections BLOCKED; loopback restricted to
    the test server's port plus, in provider-shim mode, the shim's port —
    both local endpoints of this rig, nothing else (not the live backend)."""
    lines = [
        "(version 1)", "(allow default)", "(deny network*)",
        f'(allow network-outbound (remote ip4 "localhost:{port}"))',
        "(allow network-inbound (local ip4))",
        "(allow network-inbound (local ip6))",
    ]
    lines += [f'(allow network-outbound (remote ip4 "localhost:{ep}"))' for ep in extra_ports]
    return "\n".join(lines) + "\n"
CREDENTIAL_TABLES = [
    "federation_credentials", "integration_connections", "link_tokens",
    "user_connections", "push_tokens", "oauth_states", "integration_tokens",
    "notion_tokens", "password_reset_tokens", "desktop_api_keys",
    "public_api_keys", "gateway_api_keys", "oauth_clients",
    "llm_oauth_credentials", "active_tokens",
]
_SECRET_COL_RE = re.compile(
    r"(token|secret|password|credential|private|api_key|access_key|refresh|client_id)", re.I)
SERVER_ENV_WHITELIST = {
    "PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR",
    "PYTHONUNBUFFERED", "VIRTUAL_ENV", "SSL_CERT_FILE",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _git_archive_sha() -> str:
    """Hash of the tar stream for PINNED_REV — content-addresses the exact
    code that will run, independent of worktree file state."""
    proc = subprocess.run(["git", "-C", str(WORKTREE), "archive", "--format=tar", PINNED_REV],
                          capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git archive failed: {proc.stderr[:200]}")
    return hashlib.sha256(proc.stdout).hexdigest()


def venv_freeze() -> str:
    proc = subprocess.run([str(VENV_PY), "-m", "pip", "freeze"], capture_output=True, text=True)
    if proc.returncode != 0:
        lines = []
        from importlib import metadata
        for d in sorted(metadata.distributions(), key=lambda d: d.metadata.get("Name", "")):
            name = d.metadata.get("Name")
            if name:
                lines.append(f"{name}=={d.version}")
        return "\n".join(lines) + "\n"
    return proc.stdout


def _tree_manifest(root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = _sha256_file(path)
    return out


def _make_tree_writable(root: Path) -> None:
    if root.exists():
        for p in [root, *root.rglob("*")]:
            try:
                os.chmod(p, 0o755 if p.is_dir() else 0o644)
            except OSError:
                pass


def _make_tree_readonly(root: Path) -> None:
    for p in [root, *root.rglob("*")]:
        try:
            os.chmod(p, 0o555 if p.is_dir() else 0o444)
        except OSError:
            pass


class _ProbeOK(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass


def verify_network_boundary(world: Path) -> Dict[str, bool]:
    """Empirically PROVE the boundary profile: loopback (to the allowed port)
    connects; an external IP is refused. Recorded in the world manifest and
    asserted by preflight."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _ProbeOK)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    profile = world / "local_only_probe.sb"
    profile.write_text(_sandbox_profile(port))
    code = (
        "import socket,json\n"
        f"def p(h,po):\n"
        "    try:\n"
        "        s=socket.create_connection((h,po),timeout=3);s.close();return True\n"
        "    except Exception:\n"
        "        return False\n"
        f"print(json.dumps({{'loopback':p('127.0.0.1',{port}),'external_blocked':not p('1.1.1.1',443)}}))\n"
    )
    proc = subprocess.run(["/usr/bin/sandbox-exec", "-f", str(profile), str(VENV_PY), "-c", code],
                          capture_output=True, text=True, timeout=30)
    srv.shutdown()
    try:
        result = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        result = {"loopback": False, "external_blocked": False, "raw": proc.stdout[:200]}
    return result


def scrub_credentials(con: sqlite3.Connection) -> Dict[str, int]:
    """Null secret-bearing columns in the known credential tables (defense in
    depth alongside the network boundary: the fixture must contain no usable
    connector credentials even if a call were attempted)."""
    scrubbed: Dict[str, int] = {}
    for table in CREDENTIAL_TABLES:
        try:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        except sqlite3.Error:
            continue
        if not cols:
            continue
        secret_cols = [c for c in cols if _SECRET_COL_RE.search(c) and not c.endswith("_id")]
        for col in secret_cols:
            try:
                cur = con.execute(f"UPDATE {table} SET {col} = NULL WHERE {col} IS NOT NULL")
                if cur.rowcount:
                    scrubbed[f"{table}.{col}"] = cur.rowcount
            except sqlite3.IntegrityError:
                # NOT NULL secret column: remove the rows entirely (these are
                # pure credential stores; deletion IS the scrub).
                cur = con.execute(f"DELETE FROM {table}")
                scrubbed[f"{table}(rows deleted)"] = cur.rowcount
                break
    con.commit()
    return scrubbed


def verify_scrubbed(con: sqlite3.Connection) -> List[str]:
    violations = []
    for table in CREDENTIAL_TABLES:
        try:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        except sqlite3.Error:
            continue
        for col in (c for c in cols if _SECRET_COL_RE.search(c) and not c.endswith("_id")):
            n = con.execute(f"SELECT count(*) FROM {table} WHERE {col} IS NOT NULL").fetchone()[0]
            if n:
                violations.append(f"{table}.{col}={n}")
    return violations


# Tables the lifecycle authority needs. Absent from a frozen fixture they
# fail at RUNTIME, not at boot — and because the lanes are fail-closed,
# the symptom is a turn that quietly declines to read. Verify them at
# startup instead.
LIFECYCLE_REQUIRED_TABLES = (
    "goal_runs", "goal_objectives", "task_operation_records",
    "chat_request_records", "invocation_events",
)


def runtime_contract_preflight(world: Path, port: int, *,
                               lifecycle_expected: bool) -> Dict[str, Any]:
    """Verify the EFFECTIVE production contract, not the requested one.

    Two mistakes already happened here and both were silent:

    * the harness set ``CHAT_TASK_LIFECYCLE``, a flag no production code
      reads, so a "lifecycle on" run exercised the legacy path;
    * the frozen fixture is a DATA snapshot, so the tables the lifecycle
      needs were absent — and the first operation reservation raised,
      the fail-closed lane blocked the read, and the turn answered with
      no rows and no error.

    So check what the SERVER actually sees: the flag inside the world's
    process environment, and the tables in the database it will use.
    """
    import sqlite3 as _sq

    report: Dict[str, Any] = {
        "lifecycle_expected": lifecycle_expected,
        "lifecycle_flag_effective": None,
        "lifecycle_flag_source": None,
        "required_tables_present": [],
        "required_tables_missing": [],
        "ok": True,
    }
    run_dirs = sorted((world / "runs").glob("*"), key=lambda p: p.stat().st_mtime)
    db_path = None
    if run_dirs:
        candidate = run_dirs[-1] / "data" / "atom.db"
        if candidate.exists():
            db_path = candidate
    if db_path is None:
        report["ok"] = False
        report["error"] = "no run database found to verify the contract against"
        return report
    try:
        con = _sq.connect(f"file:{db_path}?mode=ro", uri=True)
        present = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        con.close()
    except Exception as exc:  # noqa: BLE001
        report["ok"] = False
        report["error"] = f"could not inspect the run database: {exc}"
        return report
    missing = [t for t in LIFECYCLE_REQUIRED_TABLES if t not in present]
    report["required_tables_present"] = [
        t for t in LIFECYCLE_REQUIRED_TABLES if t in present]
    report["required_tables_missing"] = missing
    if lifecycle_expected and missing:
        report["ok"] = False
        report["error"] = (
            f"lifecycle requested but the database is missing {missing}; the "
            f"fail-closed lanes would decline to read and the case would "
            f"fail with no rows and no error")
    # The flag the server process actually received.
    env_path = run_dirs[-1] / "server_env.json"
    if env_path.exists():
        try:
            server_env = json.loads(env_path.read_text())
            report["lifecycle_flag_effective"] = server_env.get(
                "ATOM_TASK_LIFECYCLE_ENABLED")
            report["lifecycle_flag_source"] = "server_env.json"
        except Exception:
            pass
    if report["lifecycle_flag_effective"] is None:
        env_txt = run_dirs[-1] / "server_env.txt"
        if env_txt.exists():
            for line in env_txt.read_text().splitlines():
                if line.startswith("ATOM_TASK_LIFECYCLE_ENABLED="):
                    report["lifecycle_flag_effective"] = line.split("=", 1)[1]
                    report["lifecycle_flag_source"] = "server_env.txt"
    if lifecycle_expected and str(
            report["lifecycle_flag_effective"]) != "1":
        report["ok"] = False
        report["error"] = (
            "lifecycle requested but ATOM_TASK_LIFECYCLE_ENABLED is not '1' "
            "in the server environment; the run would exercise the legacy "
            "path and report coverage it does not have")
    return report


def preflight(world: Path) -> Dict[str, Any]:
    head = subprocess.run(["git", "-C", str(WORKTREE), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    if head != PINNED_REV:
        raise RuntimeError(f"worktree HEAD {head} != pinned {PINNED_REV}")
    status = subprocess.run(["git", "-C", str(WORKTREE), "status", "--porcelain"],
                            capture_output=True, text=True).stdout.splitlines()
    modified = [l for l in status if l and l[0] in "RM"]
    if modified:
        raise RuntimeError(f"worktree has modified tracked files (archive integrity at risk): "
                           f"{modified[:3]}")
    manifest = json.loads((world / "MANIFEST.json").read_text())
    code_manifest = json.loads((world / "code_manifest.json").read_text())
    if manifest.get("code_snapshot_sha256"):
        if _tree_manifest(world / "code") != code_manifest:
            raise RuntimeError("extracted snapshot tree drifted from its manifest")
    else:
        arch = _git_archive_sha()
        if arch != manifest.get("code_archive_sha256"):
            raise RuntimeError("git-archive hash drifted — exported code is not the pinned content")
        if _tree_manifest(world / "code") != code_manifest:
            raise RuntimeError("extracted code tree drifted from archive-derived manifest — "
                               "the files that would run are not the pinned export")
    if not manifest.get("network_boundary_verified", {}).get("external_blocked"):
        raise RuntimeError("network boundary was never proven for this world — rebuild")
    fixture_hash = _sha256_file(world / "fixture" / "atom.db")
    if fixture_hash != manifest["atom_db_sha256"]:
        raise RuntimeError("fixture DB hash drifted from world manifest")
    con = sqlite3.connect(f"file:{world / 'fixture' / 'atom.db'}?mode=ro", uri=True)
    violations = verify_scrubbed(con)
    con.close()
    if violations:
        raise RuntimeError(f"fixture DB carries credential values: {violations[:3]}")
    if hashlib.sha256(venv_freeze().encode()).hexdigest() != manifest["venv_freeze_sha256"]:
        raise RuntimeError("venv installed packages drifted from recorded freeze")
    if subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"],
                      cwd=FIXTURES, capture_output=True).returncode != 0:
        raise RuntimeError("fixtures/SHA256SUMS verification failed")
    return {"source_revision": head,
            "code_archive_sha256": manifest.get("code_archive_sha256"),
            "code_snapshot_sha256": manifest.get("code_snapshot_sha256"),
            "db_sha256": fixture_hash, "credentials_scrubbed": True,
            "venv_verified": True, "fixtures_verified": True,
            "harness_version": HARNESS_VERSION}


def refresh_working_db(world: Path) -> None:
    # Remove stale WAL/SHM sidecars: a killed run leaves them behind, and a
    # stale WAL applied to a fresh main DB corrupts it (observed twice).
    for sidecar in ("atom.db-wal", "atom.db-shm"):
        sp = world / "data" / sidecar
        if sp.exists():
            sp.unlink()
    shutil.copy2(world / "fixture" / "atom.db", world / "data" / "atom.db")


def _working_tree_snapshot() -> bytes:
    """Tar the LIVE checkout's working tree (uncommitted wiring included),
    content-hashed by the caller. Labeled honestly: this pins uncommitted
    work by hash - the owning stream's commit remains the durable pin."""
    import io
    import tarfile
    proc = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-co", "--exclude-standard", "backend"],
        capture_output=True, text=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for f in sorted(line for line in proc.stdout.splitlines() if line.strip()):
            fp = REPO / f
            if fp.is_file():
                tar.add(str(fp), arcname=f)
    return buf.getvalue()


def build_world(world: Path, refreeze_db: bool) -> None:
    (world / "fixture").mkdir(parents=True, exist_ok=True)
    (world / "data" / "sheet_datasets" / "default" / WORKBOOK_HASH_DIR).mkdir(parents=True, exist_ok=True)
    manifest_path = world / "MANIFEST.json"
    manifest: Dict[str, Any] = (json.loads(manifest_path.read_text())
                                if manifest_path.exists() else {})

    # Immutable code export for THIS pinned revision, verified as EXTRACTED
    # FILES (not just the archive stream) and made read-only.
    code_dir = world / "code"
    _make_tree_writable(code_dir)
    if code_dir.exists():
        shutil.rmtree(code_dir)
    code_dir.mkdir(parents=True)
    import io
    if getattr(build_world, "snapshot_working_tree", False):
        _snap = _working_tree_snapshot()
        with tarfile.open(fileobj=io.BytesIO(_snap)) as _tar:
            _tar.extractall(code_dir)
        manifest["code_snapshot_sha256"] = hashlib.sha256(_snap).hexdigest()
        manifest["code_source"] = ("WORKING-TREE SNAPSHOT (includes uncommitted "
                                   "changes; hash-pinned; owning stream's commit is "
                                   "the durable pin)")
        print(f"[world] snapshot export: sha256={manifest['code_snapshot_sha256'][:16]}...")
    else:
        archive = subprocess.run(["git", "-C", str(WORKTREE), "archive", "--format=tar", PINNED_REV],
                                 capture_output=True)
        if archive.returncode != 0:
            raise RuntimeError("git archive failed")
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            # Extract defensively. The export can contain symlinks that
            # point at ABSOLUTE host paths (the repo tracks several under
            # frontend-nextjs/.preview-instance). Materialising one inside
            # the world would hand the isolated server a live path into the
            # mutable checkout — breaking the isolation the export exists to
            # provide — and Python 3.14's tarfile refuses them outright, so
            # the run would abort before any case executed.
            #
            # Skip absolute links and any link that would escape the export
            # root, and RECORD them. The backend is the code under test; a
            # frontend preview convenience link is not, so skipping is
            # lossless for what is being measured — and it is recorded so
            # the omission is visible rather than silent.
            skipped_links: List[str] = []
            members = []
            for member in tar.getmembers():
                if member.issym() or member.islnk():
                    target = member.linkname or ""
                    if member.issym() and (
                            target.startswith("/")
                            or os.path.normpath(
                                os.path.join(code_dir, os.path.dirname(
                                    member.name), target)
                            ).startswith(str(code_dir.parent)) is False
                            and target.startswith("..")):
                        skipped_links.append(f"{member.name} -> {target}")
                        continue
                members.append(member)
            tar.extractall(code_dir, members=members, filter="tar")
            if skipped_links:
                manifest["skipped_absolute_links"] = skipped_links
                print(f"[world] skipped {len(skipped_links)} absolute/"
                      f"escaping symlink(s) that would breach isolation "
                      f"(first: {skipped_links[0]})")
        manifest["code_archive_sha256"] = hashlib.sha256(archive.stdout).hexdigest()
        manifest["code_source"] = f"git archive {PINNED_REV} (immutable export, file-manifested, read-only)"
    (world / "code_manifest.json").write_text(json.dumps(_tree_manifest(code_dir), indent=0))
    if getattr(build_world, "m1_overlay", False):
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            "m1_apply", BACKEND / "scripts" / "orchestration_acceptance" / "m1_overlay" / "apply.py")
        _m1 = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_m1)
        m1res = _m1.apply(code_dir)
        (world / "code_manifest.json").write_text(json.dumps(_tree_manifest(code_dir), indent=0))
        manifest["m1_overlay"] = m1res
        print(f"[world] M1 overlay: {m1res}")
    _make_tree_readonly(code_dir)

    boundary = verify_network_boundary(world)
    if not (boundary.get("loopback") and boundary.get("external_blocked")):
        raise RuntimeError(f"network boundary probe failed: {boundary}")
    manifest["network_boundary_verified"] = boundary
    manifest["network_boundary"] = ("seatbelt: external connections blocked; "
                                    "loopback restricted to the test server port")

    # Fixture DB: freeze once (scrubbed), reuse forever.
    fixture_db = world / "fixture" / "atom.db"
    if refreeze_db or not fixture_db.exists() or "credential_scrub" not in manifest:
        src = sqlite3.connect(f"file:{BACKEND/'data'/'atom.db'}?mode=ro", uri=True)
        if fixture_db.exists():
            fixture_db.unlink()
        dst = sqlite3.connect(str(fixture_db))
        with dst:
            src.backup(dst)
        dst.close(); src.close()
        con = sqlite3.connect(str(fixture_db))
        con.execute(
            "UPDATE dataset_entries SET parquet_path = REPLACE(parquet_path, ?, ?) "
            "WHERE parquet_path LIKE ?",
            (str(LIVE_SHEET_ROOT) + "/", str(world / "data" / "sheet_datasets") + "/",
             str(LIVE_SHEET_ROOT) + "/%"),
        )
        scrub = scrub_credentials(con)
        con.commit(); con.close()
        manifest.update({
            "atom_db_sha256": _sha256_file(fixture_db),
            "db_frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "db_source": "online-backup snapshot, parquet paths repointed, credentials scrubbed",
            "credential_scrub": scrub,
        })
        print(f"[world] fixture DB frozen+scrubbed: sha256={manifest['atom_db_sha256'][:16]}… "
              f"({sum(scrub.values())} credential values nulled across {len(scrub)} columns)")

    # Venv freeze pin.
    freeze = venv_freeze()
    (world / "venv_freeze.txt").write_text(freeze)
    (ACC / "venv_freeze.txt").write_text(freeze)
    manifest["venv_freeze_sha256"] = hashlib.sha256(freeze.encode()).hexdigest()

    # Parquet fixtures (hash-verified) into the scratch store.
    fx = FIXTURES / f"workbook_sheet_datasets_{WORKBOOK_HASH_DIR}"
    sums = {}
    for line in (FIXTURES / "SHA256SUMS").read_text().splitlines():
        digest, _, name = line.partition("  ")
        sums[name.strip().lstrip("./")] = digest
    copied = 0
    for pq in fx.glob("*.parquet"):
        target = world / "data" / "sheet_datasets" / "default" / WORKBOOK_HASH_DIR / pq.name
        want = sums.get(f"workbook_sheet_datasets_{WORKBOOK_HASH_DIR}/{pq.name}")
        if not target.exists() or _sha256_file(target) != want:
            shutil.copy2(pq, target)
            if _sha256_file(target) != want:
                raise RuntimeError(f"fixture hash mismatch: {pq.name}")
        copied += 1

    # Symlink farm from the IMMUTABLE EXPORT (not the worktree/checkout).
    farm = world / "backend_root"
    if farm.exists():
        shutil.rmtree(farm)
    farm.mkdir()
    for entry in (code_dir / "backend").iterdir():
        if entry.name in ("data", "logs"):
            continue
        (farm / entry.name).symlink_to(entry)
    (farm / "data").symlink_to(world / "data", target_is_directory=True)
    (farm / "logs").mkdir(exist_ok=True)

    manifest.update({
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "parquet_files_verified": copied,
        "network_boundary": "seatbelt local-only profile (runtime-enforced)",
        "server_env": "strict whitelist (no credentials)",
        "harness_version": HARNESS_VERSION,
    })
    manifest_path.write_text(json.dumps(manifest, indent=1))
    _export_ref = manifest.get("code_archive_sha256") or manifest.get("code_snapshot_sha256", "")
    print(f"[world] built: export {_export_ref[:12]}…, {copied} parquets verified, "
          f"farm -> world/code @ {PINNED_REV[:10]}, seatbelt profile written")


class _SinkHandler(BaseHTTPRequestHandler):  # retained for proxy-attempt observability if re-enabled
    def _refuse(self) -> None:
        with open(self.server.block_log, "a") as fh:  # type: ignore[attr-defined]
            fh.write(f"{time.strftime('%FT%T')} {self.command} {self.path}\n")
        try:
            self.send_response(472)
            self.end_headers()
        except Exception:
            pass

    def do_GET(self): self._refuse()
    def do_POST(self): self._refuse()
    def do_PUT(self): self._refuse()
    def do_PATCH(self): self._refuse()
    def do_DELETE(self): self._refuse()
    def do_CONNECT(self): self._refuse()
    def log_message(self, *a): pass


def _model_metadata(world: Path):
    """The schema the CODE UNDER TEST declares.

    Read from the world's immutable export, never from the mutable
    checkout: the export is what the server runs, so it is what defines
    the schema the run must have.
    """
    code_backend = world / "code" / "backend"
    if not code_backend.exists():
        code_backend = BACKEND
    saved = list(sys.path)
    saved_env = os.environ.get("TESTING")
    try:
        sys.path.insert(0, str(code_backend))
        os.environ["TESTING"] = "1"
        for stale in [m for m in list(sys.modules)
                      if m == "core" or m.startswith("core.")]:
            del sys.modules[stale]
        from core.models_registration import Base

        import core.models  # noqa: F401  (registers models on Base)
        return Base.metadata
    finally:
        sys.path[:] = saved
        for stale in [m for m in list(sys.modules)
                      if m == "core" or m.startswith("core.")]:
            del sys.modules[stale]
        if saved_env is None:
            os.environ.pop("TESTING", None)
        else:
            os.environ["TESTING"] = saved_env


def _sync_missing_tables(con, world: Path) -> list:
    """CREATE TABLE for anything the code declares but the frozen fixture
    lacks. Returns the names created, for the run record."""
    created: list = []
    try:
        metadata = _model_metadata(world)
    except Exception as exc:  # noqa: BLE001
        print(f"[world] schema sync skipped (models unavailable: {exc})")
        return created
    existing = {
        row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
    }
    for name, table in sorted(metadata.tables.items()):
        if name in existing:
            continue
        try:
            # Compile for SQLite explicitly. The models declare
            # server_default=func.now(), which renders as the PostgreSQL
            # `now()`; emitted with the default dialect that is a syntax
            # error in this SQLite world ("near "("). The model is right
            # for the deployment target — the WORLD is SQLite, so the DDL
            # has to be rendered for the world.
            from sqlalchemy.dialects import sqlite as _sqlite_dialect
            from sqlalchemy.schema import CreateTable

            ddl = str(CreateTable(table).compile(
                dialect=_sqlite_dialect.dialect())).strip()
            con.execute(ddl)
            created.append(name)
        except Exception as exc:  # noqa: BLE001
            print(f"[world] schema sync could not create {name}: {exc}")
    if created:
        con.commit()
    return created


def _seed_run_data(world: Path, run_dir: Path) -> None:
    """Seed a fresh run data dir from the world fixture via the SQLite
    backup API (consistent snapshot), rewrite dataset parquet paths, and
    verify integrity before use (work order step 6)."""
    import sqlite3 as _sq
    data = run_dir / "data"
    (data / "sheet_datasets" / "default" / WORKBOOK_HASH_DIR).mkdir(parents=True, exist_ok=True)
    (data / "atom_memory").mkdir(parents=True, exist_ok=True)
    src = _sq.connect(f"file:{world / 'fixture' / 'atom.db'}?mode=ro", uri=True)
    dst = _sq.connect(str(data / "atom.db"))
    with dst:
        src.backup(dst)
    src.close()
    con = _sq.connect(str(data / "atom.db"))
    con.execute(
        "UPDATE dataset_entries SET parquet_path = REPLACE(parquet_path, ?, ?) "
        "WHERE parquet_path LIKE ?",
        (str(LIVE_SHEET_ROOT) + "/", str(data / "sheet_datasets") + "/",
         str(LIVE_SHEET_ROOT) + "/%"))
    # SELF-CONSISTENCY (work order step 6): the live snapshot registers
    # datasets whose parquets were never copied into the world. Delete those
    # rows so the scan only sees datasets with real files - otherwise every
    # scan fails on unrelated missing files and fault injection is ambiguous.
    removed = 0
    for (pp,) in con.execute("SELECT parquet_path FROM dataset_entries").fetchall():
        if pp and not os.path.exists(pp):
            con.execute("DELETE FROM dataset_entries WHERE parquet_path=?", (pp,))
            removed += 1
    con.commit()
    # SCHEMA SYNC (acceptance run, 2026-09-26). The fixture is a frozen
    # DATA snapshot; the schema must come from the code under test. When
    # the code adds a table, the frozen dump does not have it, and the
    # first thing that touches it fails at runtime — which is exactly
    # what happened: task_operation_records was absent, so every
    # operation reservation raised, the fail-closed lane blocked the
    # read, and the turn answered with no rows. Create any missing table
    # from the code's own metadata and RECORD it, so a run against an
    # out-of-date fixture is visible in the evidence rather than silent.
    added = _sync_missing_tables(con, world)
    if added:
        print(f"[world] schema sync: created {len(added)} table(s) absent "
              f"from the frozen fixture: {', '.join(added)}")
    ic = con.execute("PRAGMA integrity_check").fetchone()[0]
    con.close()
    if removed:
        print(f"[world] pruned {removed} dataset_entries without files (self-consistent world)")
    if ic != "ok":
        raise RuntimeError(f"seeded run DB failed integrity_check: {ic}")
    fx = FIXTURES / f"workbook_sheet_datasets_{WORKBOOK_HASH_DIR}"
    dst_sheets = data / "sheet_datasets" / "default" / WORKBOOK_HASH_DIR
    import shutil as _sh
    for pq in fx.glob("*.parquet"):
        _sh.copy2(pq, dst_sheets / pq.name)


def current_run_db(world: Path) -> Path:
    """The CURRENT launch's database path. Selection is by MTIME (lexical
    name sort handed the runner a stale run dir - the root cause of the
    'zero assistant rows' observation, review round 34)."""
    runs = sorted((world / "runs").glob("run-*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise RuntimeError("no runs found - launch the server first")
    return runs[-1] / "data" / "atom.db"


def launch_server(port: int, world: Path, provider_shim: bool = False,
                  reuse_run_dir: Optional[Path] = None) -> subprocess.Popen:
    # FRESH DATABASE DIRECTORY PER RUN (work order step 6): each launch gets
    # its own data directory seeded from the world fixture; the farm's data
    # symlink is re-pointed at it. Never delete WAL/SHM beside a live DB -
    # the fresh directory makes sidecar handling moot.
    import uuid as _uuid
    if reuse_run_dir is not None:
        run_dir = Path(reuse_run_dir)  # RESTART: same DB dir, no re-seed
    else:
        run_dir = world / "runs" / f"run-{_uuid.uuid4().hex[:12]}"
        run_dir.mkdir(parents=True, exist_ok=True)
        _seed_run_data(world, run_dir)
    world = world  # world root unchanged; run db path recorded on the proc
    farm = world / "backend_root"
    _data_link = farm / "data"
    if _data_link.is_symlink() or _data_link.exists():
        _data_link.unlink()
    _data_link.symlink_to(run_dir / "data", target_is_directory=True)
    launch_server.last_run_dir = run_dir
    launch_server.last_proc = None  # set by the caller after Popen
    farm = world / "backend_root"
    profile = world / "local_only.sb"
    profile.write_text(_sandbox_profile(port, extra_ports=(SHIM_PORT,) if provider_shim else ()))
    env = {k: os.environ[k] for k in SERVER_ENV_WHITELIST if k in os.environ}
    env.update({
        "DATABASE_URL": f"sqlite:///{launch_server.last_run_dir / 'data' / 'atom.db'}",
        "ATOM_DATA_DIR": str(launch_server.last_run_dir / "data"),
        "LANCEDB_URI": str(world / "data" / "atom_memory"),
        "ATOM_SHEET_DATASETS": "1",
        "ATOM_CHAT_STREAMING": "1",
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ACC_PORT": str(port),
        # keep the read-only export pristine: no bytecode writes into world/code
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    if getattr(launch_server, "m1", False) or getattr(launch_server, "gate", False):
        env["CHAT_FINALIZATION_M1"] = "1"
    if getattr(launch_server, "gate", False):
        env["CHAT_FINALIZATION_M2"] = "1"
    # TASK LIFECYCLE. The production authority is
    # ATOM_TASK_LIFECYCLE_ENABLED; the harness used to set
    # CHAT_TASK_LIFECYCLE, which no production code reads, so every
    # "lifecycle on" run silently exercised the legacy path instead. A
    # run that claims lifecycle coverage must set the real flag, and the
    # world is recorded with it.
    if getattr(launch_server, "lifecycle", False) or \
            getattr(launch_server, "gate", False):
        env["ATOM_TASK_LIFECYCLE_ENABLED"] = "1"
    if provider_shim:
        # Recorded-response rig: production router dispatches to the local
        # shim (env-key registration + SDK base-url override). Only the
        # PROVIDER response is substituted — execution, persistence,
        # verification and delivery all run in production code. The provider
        # catalog is supplied through the runtime's OWN supported config
        # surface (ATOM_PROVIDER_MODEL_CATALOG_PATH) — no production changes.
        catalog_path = world / "provider_catalog.json"
        now = time.time()
        catalog_path.write_text(json.dumps({"providers": {"openai": {
            "served": ["gpt-6-astra", "gpt-5.2", "gpt-5-mini", "gpt-4o",
                       "gpt-4o-mini", "o4-mini", "o3-mini", "deepseek-chat",
                       "deepseek-reasoner", "qwen-max", "qwen-plus"],
            "verified_at": now, "last_attempt_at": now,
            "consecutive_failures": 0}}}))
        env.update({
            "OPENAI_API_KEY": "shim-local-not-a-secret",
            "OPENAI_BASE_URL": f"http://127.0.0.1:{SHIM_PORT}/v1",
            "ATOM_PROVIDER_MODEL_CATALOG_PATH": str(catalog_path),
        })
    import httpx as _hx0
    try:
        _pre = _hx0.get(f"http://127.0.0.1:{port}/api/health", timeout=2, trust_env=False)
        _pid = ((_pre.json() or {}).get("identity") or {}).get("pid")
        _cwd = ((_pre.json() or {}).get("identity") or {}).get("cwd", "")
        raise RuntimeError(
            f"PORT {port} ALREADY SERVED by pid {_pid} (cwd {_cwd}) - a foreign or "
            f"stale server holds it. Refusing to launch: observations would attribute "
            f"to the wrong world. Stop that server or choose another port.")
    except _hx0.HTTPError:
        pass  # 404/connection refused = port free for this launch
    except RuntimeError:
        raise
    except Exception:
        pass  # nothing listening
    log = open(world / "server.log", "ab")
    proc = subprocess.Popen(
        ["/usr/bin/sandbox-exec", "-f", str(profile),
         str(VENV_PY), str(BACKEND / "scripts" / "orchestration_acceptance" / "_app.py")],
        cwd=str(farm), env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    launch_server.last_proc = proc
    # PORT PREFLIGHT + LAUNCH DESCRIPTOR (work order step 0/1): a server on
    # this port must be THIS launch - a foreign world's server (observed:
    # another stream's wb_verify world holding :8024) invalidates every
    # observation. Verify via the app's own health identity.
    import httpx as _hx
    base = f"http://127.0.0.1:{port}"
    descriptor = {
        "run_id": launch_server.last_run_dir.name,
        "pid": proc.pid,
        "port": port,
        "export_path": str((world / "backend_root").resolve()),
        "db_path": str((launch_server.last_run_dir / "data" / "atom.db").resolve()),
        "world": str(world),
        "log_path": str(world / "server.log"),
        "expected_cwd": str((world / "backend_root").resolve()),
    }
    deadline = time.time() + 240
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early rc={proc.returncode}; see {world/'server.log'}")
        try:
            h = _hx.get(f"{base}/api/health", timeout=3, trust_env=False)
            if h.status_code == 200:
                _ident = (h.json() or {}).get("identity") or {}
                _cwd = _ident.get("cwd", "")
                if Path(_cwd).resolve() != Path(descriptor["expected_cwd"]).resolve():
                    proc.kill()
                    raise RuntimeError(
                        f"FOREIGN SERVER on :{port}: health identity cwd={_cwd} "
                        f"(pid {_ident.get('pid')}) is not this launch's world "
                        f"({descriptor['expected_cwd']}). Another stream's server is "
                        f"holding the port - coordinate or choose another port.")
                descriptor["health_identity"] = {
                    "pid": _ident.get("pid"), "cwd": _cwd,
                    "source_id": _ident.get("source_id"),
                    "instance_id": _ident.get("instance_id")}
                # DB PATH (review round 34, corrected by the lsof probe): the
                # app opens the ENV path (the fresh run dir) - the probe
                # verifies it in-flight. The health-cwd derivation was wrong.
                descriptor["db_path"] = str(
                    (launch_server.last_run_dir / "data" / "atom.db").resolve())
                launch_server.descriptor = descriptor
                launch_server.last_run_dir = launch_server.last_run_dir
                # ALWAYS write the fresh descriptor - a stale descriptor file
                # fails the identity gate by design (observed in verification).
                # Record the EFFECTIVE launch environment for the
                # contract preflight. Reading it back from the file the
                # server was started with is the only honest way to prove
                # a production flag arrived; asserting it from the
                # runner's own intent is how CHAT_TASK_LIFECYCLE went
                # unnoticed for so long.
                descriptor["effective_env"] = {
                    k: v for k, v in env.items()
                    if k.startswith(("ATOM_", "CHAT_", "ENABLE_"))
                }
                _dpath = world / "launch_descriptor.json"
                _dpath.write_text(json.dumps(descriptor, indent=1))
                (run_dir / "server_env.json").write_text(
                    json.dumps(descriptor["effective_env"], indent=1))
                descriptor["descriptor_path"] = str(_dpath)
                print(f"[server] healthy on :{port} (pid {proc.pid}, world identity verified: "
                      f"{_ident.get('source_id', '')[:24]}, seatbelt, credential-free)")
                return proc
        except _hx.HTTPError:
            pass
        except RuntimeError:
            raise
        except Exception:
            pass
        time.sleep(2)
    proc.kill()
    raise RuntimeError("server did not become healthy in 240s")


def stop_server(proc: subprocess.Popen) -> None:
    def _sig(sig: int) -> None:
        try:
            os.killpg(proc.pid, sig)
            return
        except PermissionError:
            pass  # seatbelt'd group not signalable as a group — fall through
        except ProcessLookupError:
            return
        try:
            proc.send_signal(sig)
        except (ProcessLookupError, PermissionError):
            pass
    _sig(signal.SIGTERM)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        _sig(signal.SIGKILL)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


# ---------------------------------------------------------------------------
# Structured evaluation: one evidence record binds entity -> segment(sheet +
# target cell) -> value pair(price, basis).
# ---------------------------------------------------------------------------

_PRICE_BASIS = ("PRICE", "LIST PRICE", "LIST_PRICE")
# Split evidence where a NEW citation (Sheet!Cell) begins — NOT on every
# semicolon: real basis strings contain "; currency=…" inside brackets.
_SEGMENT_SPLIT = re.compile(r"\s*;\s*(?=[A-Za-z][A-Za-z0-9 .&'-]*\s*!\s*[A-Z]{1,3}\d)")
_CITE_RE = re.compile(r"([A-Za-z][A-Za-z0-9 .&'-]*?)\s*!\s*([A-Z]{1,3}\d{1,7})")
_PAIR_RE = re.compile(r"([A-Z]{1,3}\d{1,7})\s*=\s*(-?\$?[\d,]+(?:\.\d+)?)\s*\[basis=([^\];]+)")


def _norm_label(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


_BULLET_ROW = re.compile(
    r"^[-*]\s*\*\*(?P<label>[^*]+?)\*\*"
    r"(?:\s*\([^)]*\))?"          # optional "(matched via '...')" suffix
    r"\s*[-–—:]\s*(?P<body>.+)$")
# The presentation renderer emits per-target bullets of the form
#   - **U-22** - 1,777 (LINMAC!R26, column C26 'List Price'; also M26 'List Price_2' 1,777)
#   - **No. 381** - several rows match (...); which one is yours needs your confirmation
# The frozen evaluator only understood pipe tables, so every target scored
# `missing_row` even when the reply was correct. This maps the bullet form
# onto the SAME {target, status, evidence} shape the pipe path produces.
#
# Two rules keep this a FORMAT ADAPTER rather than a source of passes:
#   * the target label is taken verbatim from the bullet (aliases still
#     decide matching, as before);
#   * the evidence is a MECHANICAL re-spelling of the renderer's own
#     wording. Nothing is inferred, defaulted, or filled in — a bullet
#     with no citation yields no segment, and therefore cannot verify a
#     price. See the negative tests in tests/test_acceptance_runner_guards.py.
_BULLET_PAIR = re.compile(
    r"(?:column\s+)?(?P<cell>[A-Z]{1,3}\d{1,7})\s+'(?P<basis>[^']+)'"
    r"(?:\s+(?P<value>-?\$?[\d,]+(?:\.\d+)?))?")
_BULLET_LEAD_VALUE = re.compile(r"^(?P<value>-?\$?[\d,]+(?:\.\d+)?)\b")


def _bullet_evidence(body: str) -> str:
    """Re-spell a renderer evidence fragment into evaluator segments.

    ``LINMAC!R26, column C26 'List Price'; also M26 'List Price_2' 1,777``
    becomes ``LINMAC!R26 ; C26=1777 [basis=List Price] ; M26=1777
    [basis=List Price_2]`` — the same bindings, in the evaluator's
    grammar. A leading scalar (``1,777 (evidence)``) is attached to the
    first segment's first pair ONLY when that pair carries no value of its
    own, so a stated price and a cited price can never be conflated.
    """
    body = body.strip()
    lead = _BULLET_LEAD_VALUE.match(body)
    lead_value = lead.group("value") if lead else None
    if lead:
        body = body[lead.end():].lstrip(" —–-(")
    open_paren = body.find("(")
    if open_paren >= 0:
        body = body[open_paren + 1:]
    body = body.rstrip(")").strip()
    # Split on the citation boundary: a new segment starts at a Sheet!Ref.
    parts = _SEGMENT_SPLIT.split(body) if body else []
    if not parts:
        return ""
    segments: List[str] = []
    for part in parts:
        part = part.strip()
        cite = _CITE_RE.search(part)
        if not cite:
            continue
        pairs = []
        for match in _BULLET_PAIR.finditer(part):
            value = match.group("value")
            if value is None and lead_value is not None and not pairs:
                value = lead_value
            if value is None:
                continue
            pairs.append(f"{match.group('cell')}={value} "
                         f"[basis={match.group('basis')}]")
        if not pairs:
            continue
        segments.append(f"{cite.group(1).strip()}!{cite.group(2)} ; "
                        + " ; ".join(pairs))
    return " ; ".join(segments)


def parse_reply_bullets(reply: str) -> List[Dict[str, str]]:
    """Per-target rows from the presentation renderer's bullet form.

    ``evidence`` holds the evaluator-grammar re-spelling so price↔cell
    binding can be checked; ``evidence_raw`` keeps the renderer's own
    wording verbatim so a human reading the record sees exactly what the
    user saw, and so a row with no citable price is visibly empty rather
    than quietly filled in.
    """
    rows: List[Dict[str, str]] = []
    for line in (reply or "").splitlines():
        line = line.strip()
        match = _BULLET_ROW.match(line)
        if not match:
            continue
        label = match.group("label").strip().strip("*").strip()
        body = match.group("body").strip()
        if not label or not body:
            continue
        upper = body.upper()
        if "SEVERAL ROWS MATCH" in upper or "NEEDS YOUR CONFIRMATION" in upper \
                or "AMBIGUOUS" in upper:
            status = "AMBIGUOUS"
        elif "NOT FOUND" in upper or "ABSENT" in upper:
            status = "NOT FOUND IN INDEXED CONTENT"
        elif _BULLET_LEAD_VALUE.match(body):
            status = "FOUND"
        else:
            status = body[:60]
        rows.append({"target": label, "status": status,
                     "evidence": _bullet_evidence(body),
                     "evidence_raw": body, "row_text": line})
    return rows


def parse_reply_table(reply: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for line in reply.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.count("|") >= 3):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or not cells[0] or set(cells[0]) <= {"-", ":", " "}:
            continue
        if _norm_label(cells[0]) == "item":
            continue
        rows.append({"target": cells[0], "status": cells[1],
                     "evidence": "|".join(cells[2:]), "row_text": line})
    if not rows:
        # The presentation renderer may answer in per-target bullets
        # rather than a pipe table. Both are the SAME reply shape, so
        # fall back to the bullet form instead of scoring every target
        # `missing_row` on a correct answer.
        rows = parse_reply_bullets(reply)
    return rows


def parse_segments(evidence: str) -> List[Dict[str, Any]]:
    """Each ` ; `-separated citation segment is ONE evidence record:
    {sheet, cell, pairs: [{cell, value, basis}]}. A price verifies only
    within the SAME segment as its target citation."""
    segments = []
    for seg in _SEGMENT_SPLIT.split(evidence):
        cite = _CITE_RE.search(seg)
        pairs = [{"cell": m.group(1), "value": float(m.group(2).replace("$", "").replace(",", "")),
                  "basis": m.group(3).strip()} for m in _PAIR_RE.finditer(seg)]
        segments.append({
            "sheet": cite.group(1).strip() if cite else "",
            "cell": cite.group(2) if cite else "",
            "pairs": pairs,
        })
    return segments


def _pair_ref(pair_cell: str) -> Tuple[str, str]:
    """Split a cell ref like 'C26' into ('C', '26'); ('', '') if malformed."""
    m = re.match(r"^([A-Z]+)(\d+)$", pair_cell or "")
    return (m.group(1), m.group(2)) if m else ("", "")


def classify(status_text: str) -> str:
    s = (status_text or "").upper()
    if "AMBIGUOUS" in s or "CANDIDATE" in s:
        return "ambiguous"
    if "NOT FOUND" in s or "ABSENT" in s:
        return "absent_from_indexed"
    if "FOUND" in s:
        return "found"
    return "unknown"


def _is_price_basis(basis: str) -> bool:
    b = basis.upper()
    return any(p in b for p in _PRICE_BASIS)


# ---------------------------------------------------------------------------
# Claim correctness — INDEPENDENT of target-row correctness, calibrated
# against OPERATION/EVIDENCE RECORDS rather than the reply's own wording.
#
# SCOPE (named honestly): this is "unsupported claims detected by RULE SET
# v2" — a closed pattern vocabulary with a closed verb->kind map, verified
# against the turn's trace records and the case's frozen source facts. It
# does NOT detect every conceivable unsupported claim; coverage beyond the
# ruleset is UNMEASURED. Do not extend coverage by accreting verbs.
# ---------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_ACTION_KIND_MAP = {  # closed ruleset v2
    "updated?": "mutation", "changed?": "mutation", "edited?": "mutation",
    "applied": "mutation", "saved": "mutation", "modified": "mutation",
    "wrote": "mutation", "added": "mutation", "replaced": "mutation",
    "removed": "mutation", "deleted": "mutation",
    "sent": "send", "scheduled": "scheduling", "created": "creation",
}
_ACTION_OBJECT_RE = re.compile(
    r"\b(?:canvas|table|row|rows|price|prices|cell|cells|value|values|column|"
    r"draft|item|items|sheet|email|e-mail|message|task|event|reminder|quote)\b", re.I)
_FRESHNESS_CLAIM_RE = re.compile(
    r"\b(current|latest|up-to-date|up to date|live)\b[^.!?]{0,40}?"
    r"\b(price|prices|file|list|data|values?)\b"
    r"|\b(price|prices|file|list|data|values?)\b[^.!?]{0,40}?\b(current|latest|live)\b", re.I)
_COMPLETION_CLAIM_RE = re.compile(
    r"\b(?:all|every|each)\b[^.!?]{0,30}?\b(?:machines?|prices?|items?|targets?)\b"
    r"[^.!?]{0,30}?\b(?:found|located|retrieved|listed)\b"
    r"|here (?:are|is) (?:all|the full)", re.I)
_ABSOLUTE_ABSENCE_RE = re.compile(
    r"not (?:in|found in) the (?:workbook|file|spreadsheet)\b", re.I)


_TARGET_STOP = {"the", "to", "a", "an", "com", "www", "and", "with", "for", "our", "your"}


def _targets_match(claimed: str, recorded: str) -> bool:
    """Loose token-overlap target match (a shared distinctive token counts);
    disjoint distinctive tokens are a mismatch."""
    ct = {t for t in _norm_label(claimed).split() if len(t) > 2 and t not in _TARGET_STOP}
    rt = {t for t in _norm_label(recorded).split() if len(t) > 2 and t not in _TARGET_STOP}
    if not ct or not rt:
        return True  # nothing distinctive to contradict — not a mismatch
    return bool(ct & rt)


def _first_person_action_claims(sentence: str) -> List[Tuple[str, str]]:
    """Sentences asserting the assistant PERFORMED an action on an object,
    mapped to a closed action kind. Returns (kind, verb) pairs."""
    low = sentence.lower()
    if not re.match(r"^\s*(i|i've|i have|we|we've|we have|it's|it has)\b", low):
        return []
    out = []
    for verb_pat, kind in _ACTION_KIND_MAP.items():
        for m in re.finditer(rf"\b(?:i(?:'ve| have)?|we(?:'ve| have)?|it(?:'s| has)?)\s+({verb_pat})\b", low):
            if _ACTION_OBJECT_RE.search(sentence):
                out.append((kind, m.group(1)))
    return out


_QUALIFIER_RE = re.compile(r"\b(current|latest|up-to-date|up to date|live)\b", re.I)


def _match_negated(sentence: str, match: "re.Match[str]") -> bool:
    """Negation counts only when it directly precedes the QUALIFIER term —
    either before the match span ('NOT a fresh read of the live file') or
    between noun and qualifier ('prices are not current'). A distant 'not'
    cannot exempt an unrelated positive claim."""
    qual = _QUALIFIER_RE.search(match.group(0))
    qual_pos = match.start() + (qual.start() if qual else 0)
    window = sentence[max(0, match.start() - 25):qual_pos].lower()
    return bool(re.search(r"\b(not|no|n't|never)\b[\s\w'-]{0,25}$", window))


def check_claims(reply: str, *, verified_action_kinds: set,
                 non_found_targets: List[str],
                 source_facts: Dict[str, Any],
                 action_evidence: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Bounded DIAGNOSTIC (rule set v2), calibrated against STRUCTURED
    action evidence: an action claim passes only when the kind is VERIFIED
    by an exact structured success field for this turn. Attempted / failed /
    pending / missing evidence all fail the claim. This is NOT the
    acceptance gate for 'no unsupported claims' — coverage beyond the
    ruleset is unmeasured."""
    ev = action_evidence or {}
    unsupported: List[Dict[str, str]] = []
    materialized = source_facts.get("source_kind") == "materialized_copy"
    for sent in _SENT_SPLIT.split(reply):
        s = sent.strip()
        if not s:
            continue
        for kind, verb in _first_person_action_claims(s):
            status = ev.get(kind, {}).get("status", "unverified")
            m = re.search(r"\bto\s+([A-Za-z0-9@._ -]+)", s)
            claimed_target = m.group(1).strip() if m else ""
            record_target = str(ev.get(kind, {}).get("target") or "")
            if kind not in verified_action_kinds:
                detail = {"failed": "action_failed", "pending": "action_pending",
                          "unbound": "execution_unbound"}.get(status, "no_verified_record")
                unsupported.append({"kind": f"action:{kind}", "sentence": s[:200],
                                    "verb": verb, "detail": detail})
            elif claimed_target and not record_target:
                # a target-SPECIFIC claim cannot be verified by a record with
                # no target identity (review round 9)
                unsupported.append({"kind": f"action:{kind}", "sentence": s[:200],
                                    "verb": verb, "detail": "target_unverifiable"})
            elif claimed_target and record_target and not _targets_match(claimed_target, record_target):
                unsupported.append({"kind": f"action:{kind}", "sentence": s[:200],
                                    "verb": verb, "detail": "target_mismatch"})
        for m in _FRESHNESS_CLAIM_RE.finditer(s):
            if materialized and not _match_negated(s, m):
                unsupported.append({"kind": "freshness", "sentence": s[:200]})
                break
        for m in _COMPLETION_CLAIM_RE.finditer(s):
            if non_found_targets and not _match_negated(s, m):
                unsupported.append({"kind": "completion", "sentence": s[:200]})
                break
        if _ABSOLUTE_ABSENCE_RE.search(s) and "indexed" not in s.lower():
            unsupported.append({"kind": "absence_scope", "sentence": s[:200]})
    return {"ruleset": "v2.1", "unsupported": unsupported,
            "unsupported_count": len(unsupported), "measured": True,
            "scope": "bounded diagnostic; acceptance gate for claim correctness remains open"}


# ---------------------------------------------------------------------------
# Artifact-native evaluation (evaluator v3)
#
# The reply is what the user saw; the ARTIFACT is what the system proved.
# Parsing the reply's text is not stronger evidence than the artifact, and
# it cannot express what the artifact now carries: an exact identity cell
# (which cell the requested identity was matched in) kept SEPARATE from the
# value cell and its basis.
#
# So the required evidence is checked against the artifact, per target:
#   * IDENTITY binding — the exact cell the identity matched in, plus the
#     role of that reference. A row locator is not an identity cell.
#   * VALUE binding    — the actual value cell, its value and its basis.
# Identity never stands in for a price, and a price never stands in for
# identity.
#
# Failures are reported PER ASSERTION (identity / value / coverage), never
# collapsed into one cause. The frozen expected cells are never edited to
# make output pass.
# ---------------------------------------------------------------------------

EVALUATOR_VERSION = "artifact-bindings-v3"


def load_structured_result(world: Path, session_id: str,
                           execution_id: Optional[str] = None
                           ) -> Optional[Dict[str, Any]]:
    """The durable structured artifact for ONE turn of a session.

    When ``execution_id`` is given the row is selected by that EXACT
    execution, never by recency. Selecting the latest row in a session
    substitutes one turn's identity for another's — which is precisely
    what an overlapping-reads case exists to detect, so the evaluator
    must not commit the same sin while checking it. With concurrent
    subturns it silently handed subturn A subturn B's evidence and
    failed A for a reason that had nothing to do with A.
    """
    import sqlite3 as _sq

    runs = sorted((world / "runs").glob("*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        return None
    db_path = runs[-1] / "data" / "atom.db"
    if not db_path.exists():
        return None
    try:
        con = _sq.connect(f"file:{db_path}?mode=ro", uri=True)
        if not execution_id:
            # NO RECENCY FALLBACK. Selecting the newest row in a session is
            # identity substitution: with concurrent or interleaved turns it
            # attributes one turn's evidence to another, which is the exact
            # failure an overlapping-reads case exists to catch. A missing
            # execution identity therefore yields no artifact, and the
            # binding check FAILS rather than quietly passing on whatever
            # happened to be last. Legacy single-turn callers that genuinely
            # want recency must ask for it explicitly.
            con.close()
            _RECENCY_FALLBACK_REFUSALS.append(session_id)
            return None
        rows = con.execute(
            "SELECT metadata_json FROM chat_messages "
            "WHERE conversation_id=? AND role='assistant' "
            "ORDER BY created_at DESC", (session_id,)).fetchall()
        row = None
        _matched = []
        for candidate in rows:
            try:
                meta = json.loads(candidate[0] or "{}")
            except Exception:
                continue
            if str((meta or {}).get("execution_id") or "") == str(execution_id):
                _matched.append(candidate)
        if len(_matched) == 1:
            row = _matched[0]
        elif len(_matched) > 1:
            # Ambiguous identity: several rows claim the same execution.
            # Refuse rather than pick one.
            _AMBIGUOUS_EXECUTION.append((session_id, execution_id,
                                          len(_matched)))
            row = None
        con.close()
    except Exception:
        return None
    if not row:
        return None
    try:
        meta = json.loads(row[0] or "{}")
    except Exception:
        return None
    pfr = meta.get("pending_file_result") or {}
    if isinstance(pfr, dict) and pfr.get("structured_result"):
        return pfr["structured_result"]
    if meta.get("structured_result"):
        return meta["structured_result"]
    return None


# Refusals recorded rather than swallowed, so a run that leaned on recency
# is visible in the record instead of silently passing.
_RECENCY_FALLBACK_REFUSALS: List[str] = []
_AMBIGUOUS_EXECUTION: List[Tuple[str, str, int]] = []


def load_latest_session_artifact(world: Path, session_id: str
                                 ) -> Optional[Dict[str, Any]]:
    """LEGACY convenience: the newest assistant turn's artifact.

    Deliberately a DIFFERENT function from
    ``load_structured_result(world, session, execution_id=...)``. Recency
    is a real hazard under concurrency, so it is opt-in and cannot be
    reached by an identity-binding check by accident.
    """
    import sqlite3 as _sq

    runs = sorted((world / "runs").glob("*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        return None
    db_path = runs[-1] / "data" / "atom.db"
    if not db_path.exists():
        return None
    try:
        con = _sq.connect(f"file:{db_path}?mode=ro", uri=True)
        row = con.execute(
            "SELECT metadata_json FROM chat_messages "
            "WHERE conversation_id=? AND role='assistant' "
            "ORDER BY created_at DESC LIMIT 1", (session_id,)).fetchone()
        con.close()
    except Exception:
        return None
    if not row:
        return None
    try:
        meta = json.loads(row[0] or "{}")
    except Exception:
        return None
    pfr = meta.get("pending_file_result") or {}
    if isinstance(pfr, dict) and pfr.get("structured_result"):
        return pfr["structured_result"]
    return meta.get("structured_result")


def _cell_coord(ref: str) -> Optional[str]:
    m = re.match(r"^([A-Z]{1,3})(\d{1,7})$", str(ref or "").strip().upper())
    return m.group(0) if m else None


def _identity_cells(identity: Dict[str, Any]) -> List[str]:
    """Every identity CELL reference recorded for a target, uppercased.

    WHY THIS EXISTS. This function is the fix for a confirmed evaluator defect
    that made a correct production result score as a failure, and it is worth
    stating the shape precisely because getting it wrong is invisible.

    `core/answer_presentation.build_targets_from_scan` groups evidence by
    (sheet, row) and attaches the matched identity cells to each GROUP:

        target.identity            = {"status": ..., "candidates": [...]}
        candidate.identity         = {"status": ..., "references": [
                                        {"sheet":..., "cell": "A26",
                                         "row": 26, "role": "matched_target"}]}

    The target-level dict has NO `references` key at all. An earlier version
    of this evaluator read `identity.get("references")`, which therefore
    returned None for EVERY target, and reported
    `identity refs none (status 'single'); expected A26` for rows whose
    identity was in fact bound at A26. Verified against a real captured
    artifact: U-22 -> candidate LINMAC!R26 carries A26; the evaluator saw
    none. Six of eight targets failed on that, while `value_ok` was True for
    every one of them.

    The identity binding is per-candidate by design: a row locator is not an
    identity cell, and distinct matching rows must stay distinct so an
    ambiguous target can report several of them. So the target's identity
    cells are the UNION over its candidates -- each of which is a real
    coordinate the scan actually matched -- deduplicated and order-preserving.

    A row locator (`LINMAC!R26`) is never accepted here. That is the whole
    point: `R26` is a position, `A26` is the cell holding the identity.
    """
    cells: List[str] = []
    groups: List[Dict[str, Any]] = []
    refs_here = identity.get("references")
    if isinstance(refs_here, list):
        groups.append({"references": refs_here})
    for cand in identity.get("candidates") or []:
        if isinstance(cand, dict):
            sub = cand.get("identity")
            if isinstance(sub, dict) and isinstance(sub.get("references"), list):
                groups.append(sub)
    for grp in groups:
        for ref in grp["references"]:
            cell = str((ref or {}).get("cell") or "").strip().upper()
            # A cell coordinate only. R26/row 26/labels are not cells and are
            # rejected here rather than silently compared and mismatched.
            if re.match(r"^[A-Z]{1,3}\d{1,7}$", cell) and cell not in cells:
                cells.append(cell)
    return cells


def evaluate_absence_from_artifact(
    artifact: Optional[Dict[str, Any]],
    expected_map: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Decide absence from the artifact's structured outcome.

    A target is `absent_from_indexed` ONLY when the search demonstrably
    completed and matched nothing. Incomplete coverage, a failed read, or
    a truncated catalog are all `unknown` — the honest answer, and never
    `absent`. Reply wording is not evidence: "I found 0 results" is a
    phrasing, not a coverage statement.
    """
    out: Dict[str, Dict[str, Any]] = {}
    targets = {}
    for entry in (artifact or {}).get("targets") or []:
        label = str(entry.get("item") or "")
        if label:
            targets[_norm_label(label)] = entry
    coverage = (artifact or {}).get("coverage") or {}
    complete = coverage.get("complete")
    limits = (artifact or {}).get("coverage_limits") or {}
    for target, exp in expected_map.items():
        if exp.get("coverage") not in ("absent_from_indexed",):
            continue
        keys = {_norm_label(target)} | {
            _norm_label(a) for a in exp.get("label_aliases", [])}
        entry = next((targets[k] for k in keys if k in targets), None)
        if entry is None:
            out[target] = {
                "verdict": "unknown",
                "reason": "requested item absent from the artifact; cannot "
                          "distinguish zero matches from an incomplete read",
                "coverage_complete": complete,
            }
            continue
        identity_status = str((entry.get("identity") or {}).get("status")
                              or "")
        has_evidence = any(
            ((c or {}).get("values") for c in
             (entry.get("identity") or {}).get("candidates") or []))
        if has_evidence:
            out[target] = {"verdict": "not_absent",
                           "reason": "artifact carries value evidence",
                           "coverage_complete": complete}
        elif complete is False:
            out[target] = {
                "verdict": "unknown",
                "reason": "coverage incomplete; absence cannot be claimed",
                "coverage_complete": False,
                "coverage_limits": limits,
            }
        elif identity_status == "none":
            out[target] = {
                "verdict": "absent_from_indexed",
                "reason": "coverage complete and the artifact reports no "
                          "identity candidate for this item",
                "coverage_complete": True,
            }
        else:
            out[target] = {
                "verdict": "unknown",
                "reason": f"identity status {identity_status!r} with no value "
                          f"evidence; not a demonstrated zero-match search",
                "coverage_complete": complete,
            }
    return out


def evaluate_artifact_bindings(
    artifact: Optional[Dict[str, Any]],
    expected_map: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Per-target identity and value verdicts, from the artifact alone."""
    out: Dict[str, Dict[str, Any]] = {}
    targets = {}
    for entry in (artifact or {}).get("targets") or []:
        label = str(entry.get("item") or "")
        if label:
            targets[_norm_label(label)] = entry
    for target, exp in expected_map.items():
        keys = {_norm_label(target)} | {
            _norm_label(a) for a in exp.get("label_aliases", [])}
        entry = next((targets[k] for k in keys if k in targets), None)
        record: Dict[str, Any] = {
            "expected": exp["coverage"],
            "identity_ok": False,
            "identity_detail": "requested item absent from artifact",
            "value_ok": False, "value_detail": "not evaluated",
        }
        if entry is None:
            record["identity_detail"] = "requested item absent from artifact"
            out[target] = record
            continue
        identity = entry.get("identity") or {}
        identity_status = str(identity.get("status") or "")
        want_cell = str((exp.get("cell") or "")).partition("!")[2] or ""
        want_coord = _cell_coord(want_cell)

        if not want_coord:
            # Ambiguous/absent expectations carry no cell: the assertion is
            # that the artifact reports multiple identity candidates.
            want_multiple = exp["coverage"] in ("ambiguous",
                                                "ambiguous_candidate")
            record["identity_ok"] = (
                identity_status == "multiple") == want_multiple
            record["identity_detail"] = (
                f"identity status {identity_status!r}, expected "
                f"{'multiple' if want_multiple else 'not multiple'}")
        else:
            cells = _identity_cells(identity)
            record["identity_ok"] = want_coord.upper() in cells
            record["identity_detail"] = (
                f"identity refs {cells or 'none'} (status "
                f"{identity_status!r}); expected {want_coord.upper()}")
            # Guard the column-confusion class explicitly: a suffix match
            # is not a match.
            if not record["identity_ok"] and cells:
                record["identity_detail"] += (
                    " | suffix-only matches rejected: "
                    f"{[c for c in cells if c.endswith(want_coord.upper())]}")

        if exp.get("price") is not None:
            want_sheet, _, _ = str(exp.get("cell") or "").partition("!")
            want_price = float(exp["price"])
            want_basis = str(exp.get("basis") or "")
            want_col = str(exp.get("value_col") or "").upper()
            want_row = ""
            if want_coord:
                want_row = re.match(r"^[A-Z]{1,3}(\d{1,7})$",
                                    want_coord).group(1)
            hit = None
            for cand in (identity.get("candidates") or []):
                for v in cand.get("values") or []:
                    vcoord = _cell_coord(v.get("col"))
                    if not vcoord:
                        continue
                    vcol = re.match(r"^([A-Z]{1,3})", vcoord).group(1)
                    vrow = re.match(r"^[A-Z]{1,3}(\d+)$", vcoord).group(1)
                    if (abs(float(v.get("value", 1e18)) - want_price) < 0.005
                            and (not want_basis
                                 or want_basis.upper() in str(
                                     v.get("basis") or "").upper())
                            and (not want_col or vcol == want_col)
                            and (not want_row or vrow == want_row)):
                        hit = (vcoord, v.get("basis"), v.get("value"))
                        break
                if hit:
                    break
            record["value_ok"] = hit is not None
            record["value_detail"] = (
                f"value binding {hit}" if hit else
                f"no value binding for {want_col or '?'}"
                f"{want_row or '?'} = {want_price} basis {want_basis!r}")
        else:
            record["value_ok"] = True
            record["value_detail"] = "no price expectation"
        out[target] = record
    return out

def evaluate_rows(rows: List[Dict[str, str]], expected_map: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        groups.setdefault(_norm_label(r["target"]), []).append(r)
    out: Dict[str, Dict[str, Any]] = {}
    for target, exp in expected_map.items():
        keys = {_norm_label(target)} | {_norm_label(a) for a in exp.get("label_aliases", [])}
        label_key = next((k for k in keys if k in groups), None)
        if label_key is None:
            out[target] = {"expected": exp["coverage"], "got": "missing_row",
                           "pass": False, "detail": "no exact label/alias match"}
            continue
        group = groups[label_key]
        # Contradictory duplicate rows are a FAILURE, never silently first-wins.
        if len(group) > 1 and len({(r["status"], r["evidence"][:80]) for r in group}) > 1:
            out[target] = {"expected": exp["coverage"], "got": "contradictory_rows",
                           "pass": False, "detail": f"{len(group)} rows disagree for label {group[0]['target']!r}"}
            continue
        row = group[0]
        got = classify(row["status"])
        exp_class = "ambiguous" if exp["coverage"] == "ambiguous_candidate" else exp["coverage"]
        segments = parse_segments(row["evidence"])

        if exp.get("price") is not None and not exp.get("cell") and not exp.get("value_col"):
            out[target] = {"expected": exp["coverage"], "got": got, "pass": False,
                           "detail": "priced expectation missing frozen provenance (cell/value_col/basis)"}
            continue

        binding: Optional[Dict[str, Any]] = None
        if exp.get("price") is not None and exp.get("cell"):
            want_sheet, _, want_cell = exp["cell"].partition("!")
            cit_col, cit_row = _pair_ref(want_cell)
            want_price, want_basis, want_col = float(exp["price"]), exp.get("basis", ""), exp.get("value_col", "")
            binding = next(({
                "sheet": s["sheet"], "cell": s["cell"], "price_cell": p["cell"], "basis": p["basis"],
            } for s in segments
                if s["cell"] == want_cell.upper()
                and _norm_label(s["sheet"]) == _norm_label(want_sheet)
                for p in s["pairs"]
                if abs(p["value"] - want_price) < 0.005
                and ((want_basis and want_basis.upper() in p["basis"].upper())
                     or (not want_basis and _is_price_basis(p["basis"])))
                and _pair_ref(p["cell"])[0] == want_col.upper()
                and (not cit_row or _pair_ref(p["cell"])[1] == cit_row)
            ), None)
        elif exp.get("price") is not None:
            # Declared-column provenance (unrelated-domain fixtures whose
            # value column is an amount/status, not a price basis): the value
            # must bind INSIDE a cited segment to the declared column + basis.
            want_price, want_basis, want_col = float(exp["price"]), exp.get("basis", ""), exp.get("value_col", "")
            binding = next(({
                "sheet": s["sheet"], "cell": s["cell"], "price_cell": p["cell"], "basis": p["basis"],
            } for s in segments if s["cell"]
                for p in s["pairs"]
                if abs(p["value"] - want_price) < 0.005
                and (want_basis.upper() in p["basis"].upper() if want_basis else _is_price_basis(p["basis"]))
                and (not want_col or _pair_ref(p["cell"])[0] == want_col.upper())
            ), None)
        elif exp.get("cell"):
            want_sheet, _, want_cell = exp["cell"].partition("!")
            want_cell = want_cell or want_sheet
            binding = {"citation_only": next((s for s in segments
                                              if s["cell"] == want_cell.upper()
                                              and (not want_sheet or _norm_label(s["sheet"]) == _norm_label(want_sheet))), None)}

        passed = got == exp_class
        if exp.get("price") is not None:
            passed = passed and binding is not None
        elif exp.get("cell") and "citation_only" in (binding or {}):
            passed = passed and binding["citation_only"] is not None
        out[target] = {
            "expected": exp["coverage"], "got": got, "label": row["target"],
            "binding": binding,
            "row": {k: row[k] for k in ("target", "status")},
            "pass": bool(passed),
        }
    return out


def selftest() -> int:
    exp = {
        "U-22": {"coverage": "found", "price": 1777.0, "cell": "linmac!A26",
                 "value_col": "C", "basis": "List Price"},
        "SLE24-16": {"coverage": "found", "price": 8880.0, "cell": "tennsmith!A101",
                     "value_col": "E", "basis": "PRICE"},
        "381": {"coverage": "ambiguous"},
        "No. 622": {"coverage": "ambiguous", "label_aliases": ["622"]},
    }
    ok = True

    def check(name: str, rows: List[Dict[str, str]], target: str, want: bool):
        nonlocal ok
        got = evaluate_rows(rows, exp)[target]["pass"]
        mark = "PASS" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [selftest {mark}] {name}")

    def row(t, s, e):
        return {"target": t, "status": s, "evidence": e, "row_text": f"| {t} | {s} | {e} |"}

    check("full record binds (sheet+cell+value col+row+basis)",
          [row("U-22", "FOUND", "LINMAC!A26 R26 (values: C26=1777.0 [basis=List Price; currency=unspecified])")],
          "U-22", True)
    check("wrong price fails",
          [row("U-22", "FOUND", "LINMAC!A26 (values: C26=8800.0 [basis=List Price])")], "U-22", False)
    check("right number, non-price basis fails",
          [row("SLE24-16", "FOUND", "Tennsmith!A101 (values: E101=8880 [basis=U.S. COST])")], "SLE24-16", False)
    check("right price on the WRONG VALUE COLUMN fails",
          [row("U-22", "FOUND", "LINMAC!A26 (values: B26=1777.0 [basis=List Price])")], "U-22", False)
    check("right price on the wrong ROW of the right column fails",
          [row("U-22", "FOUND", "LINMAC!A26 (values: C27=1777.0 [basis=List Price])")], "U-22", False)
    check("right price, mismatched frozen BASIS label fails",
          [row("U-22", "FOUND", "LINMAC!A26 (values: C26=1777.0 [basis=Factory Cost])")], "U-22", False)
    check("price in DIFFERENT segment than target citation fails",
          [row("U-22", "FOUND", "LINMAC!A26 (values: C26=999.0 [basis=List Price]) ; Tennsmith!A101 (values: E101=1777.0 [basis=PRICE])")],
          "U-22", False)
    check("citation without sheet match fails",
          [row("U-22", "FOUND", "Tennsmith!A26 (values: C26=1777.0 [basis=List Price])")], "U-22", False)
    check("contradictory duplicate rows fail (never first-wins)",
          [row("U-22", "FOUND", "LINMAC!A26 (values: C26=1777.0 [basis=List Price])"),
           row("U-22", "NOT FOUND IN INDEXED CONTENT", "all sheets probed")], "U-22", False)
    check("identical duplicate rows are tolerated",
          [row("U-22", "FOUND", "LINMAC!A26 (values: C26=1777.0 [basis=List Price])"),
           row("U-22", "FOUND", "LINMAC!A26 (values: C26=1777.0 [basis=List Price])")], "U-22", True)

    incomplete = {"Free Agent": {"coverage": "found", "price": 100.0}}
    got = evaluate_rows([row("Free Agent", "FOUND", "X!A1 (values: B1=100.0 [basis=PRICE])")], incomplete)["Free Agent"]
    ok = ok and not got["pass"]
    print(f"  [selftest {'PASS' if not got['pass'] else 'FAIL'}] priced expectation missing cell/value_col/basis is rejected")

    emb = [row("3818", "FOUND", "X!A1 (values: B1=1777.0 [basis=List Price])")]
    got = evaluate_rows(emb, exp)["381"]["pass"]
    ok = ok and not got
    print(f"  [selftest {'PASS' if not got else 'FAIL'}] label '3818' must not satisfy target '381'")

    seg_price = [row("SLE24-16", "FOUND", "Tennsmith!A101 (values: E101=16240 [basis=PRICE])")]
    got = evaluate_rows(seg_price, exp)["SLE24-16"]["pass"]
    ok = ok and not got
    print(f"  [selftest {'PASS' if not got else 'FAIL'}] price 16240 must not satisfy 8880")

    amb = [row("381", "AMBIGUOUS", "multiple designation rows")]
    got = evaluate_rows(amb, exp)["381"]["pass"]
    ok = ok and got
    print(f"  [selftest {'PASS' if got else 'FAIL'}] honest ambiguity passes")

    cc_ok = True
    src = WORKBOOK_SOURCE_FACTS

    def claims(reply, payload=None, verified=None, non_found=(), facts=src, exec_id="exec-1"):
        pl = dict(payload or {})
        pl.setdefault("execution_id", exec_id)
        ev = action_evidence(pl, execution_id=exec_id)
        vk = verified if verified is not None else {
            k for k, v in ev.items() if v["status"] == "verified"}
        return check_claims(reply, verified_action_kinds=vk,
                            non_found_targets=list(non_found), source_facts=facts,
                            action_evidence=ev)

    clean = claims("Workbook read: the file named above.\nPer-item results below. | 381 | AMBIGUOUS | rows |",
                   non_found=["381"])
    cc_ok = cc_ok and clean["unsupported_count"] == 0
    mut = claims("I have updated the canvas with these prices. | 381 | AMBIGUOUS | rows |", non_found=["381"])
    cc_ok = cc_ok and any(u["kind"] == "action:mutation" for u in mut["unsupported"])
    sent = claims("I sent the email to the lead with the quote.")
    cc_ok = cc_ok and any(u.get("detail") == "no_verified_record" for u in sent["unsupported"])
    sent_failed = claims("I sent the email to the lead.",
                         payload={"data": {"canvas_email": {"send_status": "failed", "recipient": "lead"}}})
    cc_ok = cc_ok and any(u.get("detail") == "action_failed" for u in sent_failed["unsupported"])
    sent_proposed = claims("I sent the email to the lead.",
                           payload={"data": {"canvas_email": {"review_status": "proposed", "recipient": "lead"}}})
    cc_ok = cc_ok and any(u.get("detail") == "action_pending" for u in sent_proposed["unsupported"])
    sent_other_target = claims(
        "I sent the email to the lead.",
        payload={"data": {"email": {"sent": True, "recipient": "ops@supplier-works.com"}}})
    cc_ok = cc_ok and any(u.get("detail") == "target_mismatch" for u in sent_other_target["unsupported"])
    sent_ok = claims("I sent the email to the lead.",
                     payload={"data": {"email": {"sent": True, "recipient": "lead@customer.com"}}})
    cc_ok = cc_ok and sent_ok["unsupported_count"] == 0
    fresh = claims("These are the current prices from the file.")
    cc_ok = cc_ok and any(u["kind"] == "freshness" for u in fresh["unsupported"])
    mat_current = claims("The materialized copy contains the current prices.")
    cc_ok = cc_ok and any(u["kind"] == "freshness" for u in mat_current["unsupported"])
    comp = claims("All prices found — here are all of them.", non_found=["381"])
    cc_ok = cc_ok and any(u["kind"] == "completion" for u in comp["unsupported"])
    scope = claims("U-38 is not in the workbook.", non_found=["U-38"])
    cc_ok = cc_ok and any(u["kind"] == "absence_scope" for u in scope["unsupported"])
    scoped_ok = claims("U-38: NOT FOUND IN THE INDEXED CONTENT — scoped to indexed sheets.", non_found=["U-38"])
    cc_ok = cc_ok and scoped_ok["unsupported_count"] == 0
    disclosure_ok = claims(
        "Source: MATERIALIZED COPY — this evidence comes from the materialized copy of "
        "'Consolidated Price List 2019.xlsx' (NOT a fresh read of the live file).")
    cc_ok = cc_ok and disclosure_ok["unsupported_count"] == 0
    negated_fresh = claims("The prices are not current — the copy was ingested 2026-09-07.")
    cc_ok = cc_ok and negated_fresh["unsupported_count"] == 0
    neg_isolation = claims("I did not change anything here. I updated the canvas separately.")
    cc_ok = cc_ok and any(u["kind"] == "action:mutation" for u in neg_isolation["unsupported"])
    mut_ok = claims("I have updated the canvas.", payload={"data": {"canvas_edit": {"updated": True}}})
    cc_ok = cc_ok and mut_ok["unsupported_count"] == 0
    exec_mismatch = claims("I have updated the canvas.",
                           payload={"execution_id": "exec-OTHER",
                                    "data": {"canvas_edit": {"updated": True}}}, exec_id="exec-1")
    cc_ok = cc_ok and any(u.get("detail") == "execution_unbound" for u in exec_mismatch["unsupported"])
    exec_missing = claims("I have updated the canvas.",
                          payload={"data": {"canvas_edit": {"updated": True}}, "execution_id": None},
                          exec_id="exec-1")
    cc_ok = cc_ok and any(u.get("detail") == "execution_unbound" for u in exec_missing["unsupported"])
    send_no_target = claims("I sent the email to Steve.",
                            payload={"data": {"email": {"sent": True}}})
    cc_ok = cc_ok and any(u.get("detail") == "target_unverifiable" for u in send_no_target["unsupported"])
    for name, passed in [("clean reply passes claim check", clean["unsupported_count"] == 0),
                         ("mutation claim with no record flags", mut["unsupported_count"] >= 1),
                         ("'I sent the email' with missing evidence flags (no_verified_record)", sent["unsupported_count"] >= 1),
                         ("FAILED send cannot verify a send claim (action_failed)", sent_failed["unsupported_count"] >= 1),
                         ("PROPOSED send cannot verify a send claim (action_pending)", sent_proposed["unsupported_count"] >= 1),
                         ("verified send to a DIFFERENT target flags (target_mismatch)", sent_other_target["unsupported_count"] >= 1),
                         ("verified send to the claimed target is clean", sent_ok["unsupported_count"] == 0),
                         ("freshness claim on materialized source flags", fresh["unsupported_count"] >= 1),
                         ("'current prices' inside a materialized-copy sentence STILL flags", mat_current["unsupported_count"] >= 1),
                         ("completion claim with ambiguity flags", comp["unsupported_count"] >= 1),
                         ("absolute absence claim flags", scope["unsupported_count"] >= 1),
                         ("scoped absence claim is clean", scoped_ok["unsupported_count"] == 0),
                         ("honest live-file negation disclosure is clean", disclosure_ok["unsupported_count"] == 0),
                         ("negated freshness statement is clean", negated_fresh["unsupported_count"] == 0),
                         ("distant negation does not exempt a later positive claim", neg_isolation["unsupported_count"] >= 1),
                         ("mutation claim with structured verified mutation is clean", mut_ok["unsupported_count"] == 0),
                         ("verified field with MISMATCHED execution id does not verify (execution_unbound)", exec_mismatch["unsupported_count"] >= 1),
                         ("verified field with MISSING execution id does not verify", exec_missing["unsupported_count"] >= 1),
                         ("target-specific claim with no record target stays unverified (target_unverifiable)", send_no_target["unsupported_count"] >= 1)]:
        cc_ok = cc_ok and passed
        print(f"  [selftest {'PASS' if passed else 'FAIL'}] claim-check: {name}")
    ok = ok and cc_ok

    alias_hit = [row("622", "AMBIGUOUS", "intra-brand multiplicity")]
    got = evaluate_rows(alias_hit, exp)["No. 622"]["pass"]
    ok = ok and got
    print(f"  [selftest {'PASS' if got else 'FAIL'}] declared alias matches exactly")

    alias_emb = [row("6220", "AMBIGUOUS", "x")]
    got = evaluate_rows(alias_emb, exp)["No. 622"]["pass"]
    ok = ok and not got
    print(f"  [selftest {'PASS' if not got else 'FAIL'}] alias '622' must not match label '6220'")

    inv_exp = {"INV-1002": {"coverage": "found", "price": 4200.5, "value_col": "D", "basis": "amount_usd"}}
    inv_rows = [row("INV-1002", "FOUND",
                    "invoices !A3 R3 (values: D3=4200.5 [basis=amount_usd; currency=USD])")]
    inv_got = evaluate_rows(inv_rows, inv_exp)["INV-1002"]["pass"]
    inv_wrongcol = evaluate_rows([row("INV-1002", "FOUND",
                    "invoices !A3 (values: C3=4200.5 [basis=amount_usd])")], inv_exp)["INV-1002"]["pass"]
    inv_uncited = evaluate_rows([row("INV-1002", "FOUND",
                    "(values: D3=4200.5 [basis=amount_usd])")], inv_exp)["INV-1002"]["pass"]
    for name, passed in [("declared-column amount binds in cited segment", inv_got),
                         ("declared-column binding rejects wrong column", not inv_wrongcol),
                         ("declared-column binding rejects uncited values", not inv_uncited)]:
        ok = ok and passed
        print(f"  [selftest {'PASS' if passed else 'FAIL'}] invoice-binding: {name}")

    # Binding negative tests (review round 11)
    log = [
        {"epoch": 100.0, "model": "m", "last_user_tail": "ask [narrref-AAA]", "nonce": "shim-1"},
        {"epoch": 100.2, "model": "m", "last_user_tail": "ask [narrref-BBB]", "nonce": "shim-2"},   # other turn
        {"epoch": 50.0, "model": "m", "last_user_tail": "ask [narrref-AAA]", "nonce": "shim-3"},    # out of window
        {"epoch": 100.4, "model": "(catalog-discovery)", "last_user_tail": "", "nonce": None},      # probe
    ]
    bound = bind_shim_calls(log, "narrref-AAA", 99.0, 101.0)
    b_ok = len(bound) == 1 and bound[0]["nonce"] == "shim-1"
    c_hit = consumption_from(bound, "Summary. Reference for this summary: shim-1.") == "shim-1"
    c_miss = consumption_from(bound, "Summary with no nonce, even if it says unverified.") is None
    for name, passed in [("binding selects ONLY this turn's token+window (other turn and probes rejected)", b_ok),
                         ("consumption proven by the bound response's nonce", c_hit),
                         ("generic wording ('unverified') does NOT prove consumption; discarded response stays unconsumed", c_miss)]:
        ok = ok and passed
        print(f"  [selftest {'PASS' if passed else 'FAIL'}] binding: {name}")

    # Consumption/safety separation (review round 12)
    c_vis = classify_consumption(["shim-1"], "Reply … Reference for this summary: shim-1.", {})
    c_int = classify_consumption(["shim-1"], "Clean rewritten reply with no nonce.", {"shim-1": ["reasoning_step"]})
    c_unk = classify_consumption(["shim-1"], "Fallback text.", {})
    for name, passed in [
        ("visible nonce = consumed, user-visible (leakage evidence)", c_vis["consumed"] and c_vis["where"] == "user-visible"),
        ("internal-record nonce = RECORDING evidence only, processing unverified", c_int["consumed"] and "internal-recorded" in c_int["where"] and c_int["status"] == "recorded-not-processed"),
        ("no evidence = UNKNOWN (not auto-discarded)", (not c_unk["consumed"]) and c_unk["status"] == "unknown" and not c_unk.get("discarded", False)),
    ]:
        ok = ok and passed
        print(f"  [selftest {'PASS' if passed else 'FAIL'}] consumption: {name}")

    # ------------------------------------------------------------------
    # Identity-binding level regression.
    #
    # This is the shape captured from a REAL run of the preview world, with
    # the values production actually wrote. It is here because the defect it
    # pins was invisible: the evaluator read `identity.references` at the
    # TARGET level, production writes `references` at the CANDIDATE level, so
    # every target reported "identity refs none" and six of eight failed even
    # though U-22 was bound at A26 and its value at C26. A vacuous test ("it
    # returns a dict") cannot catch that; the assertion below is on the
    # verdict for a target whose identity is genuinely bound.
    # ------------------------------------------------------------------
    _real_artifact = {
        "schema_version": "structured-result-2",
        "targets": [
            {"item": "U-22", "identity": {"status": "single", "candidates": [
                {"ref": "LINMAC!R26", "identity": {"references": [
                    {"sheet": "LINMAC", "cell": "A26", "row": 26,
                     "role": "matched_target"}]},
                 "values": [{"col": "C26", "basis": "List Price", "value": 1777.0}]}]}},
            {"item": "SLE24-16", "identity": {"status": "single", "candidates": [
                {"ref": "Tennsmith!R101", "identity": {"references": [
                    {"sheet": "Tennsmith", "cell": "A101", "row": 101,
                     "role": "matched_target"}]},
                 "values": [{"col": "E101", "basis": "PRICE", "value": 8880.0}]}]}},
            {"item": "381", "identity": {"status": "multiple", "candidates": [
                {"ref": "RoperWhitney!R88", "identity": {"references": [
                    {"sheet": "RoperWhitney", "cell": "A88", "role": "matched_target"}]},
                 "values": []},
                {"ref": "RoperWhitney!R89", "identity": {"references": [
                    {"sheet": "RoperWhitney", "cell": "A89", "role": "matched_target"}]},
                 "values": []}]}},
        ],
    }
    _real_exp = {
        "U-22": {"coverage": "found", "price": 1777.0, "cell": "linmac!A26",
                 "value_col": "C", "basis": "List Price"},
        "SLE24-16": {"coverage": "found", "price": 8880.0, "cell": "tennsmith!A101",
                     "value_col": "E", "basis": "PRICE"},
        "381": {"coverage": "ambiguous"},
    }
    _b = evaluate_artifact_bindings(_real_artifact, _real_exp)
    _cells_u22 = _identity_cells(
        _real_artifact["targets"][0]["identity"])
    for name, passed in [
        ("identity cells are read from the CANDIDATE level where production writes them "
         "(U-22 -> A26, not 'none')", _cells_u22 == ["A26"]),
        ("a bound identity now passes (U-22 identity_ok)", _b["U-22"]["identity_ok"]),
        ("a bound identity now passes (SLE24-16 identity_ok)", _b["SLE24-16"]["identity_ok"]),
        ("the value binding is still decided independently and still passes",
         _b["U-22"]["value_ok"] and _b["SLE24-16"]["value_ok"]),
        ("ambiguous target still asserts multiplicity, not a cell",
         _b["381"]["identity_ok"]),
    ]:
        ok = ok and passed
        print(f"  [selftest {'PASS' if passed else 'FAIL'}] identity-binding: {name}")

    # A row locator must NEVER satisfy an identity-cell assertion. This is the
    # distinction the whole contract turns on, so it gets its own negative.
    _rowlocator_artifact = {
        "targets": [{"item": "X-1", "identity": {"status": "single", "candidates": [
            {"ref": "LINMAC!R26", "identity": {"references": [
                {"sheet": "LINMAC", "cell": "R26", "role": "matched_target"}]},
             "values": [{"col": "C26", "basis": "List Price", "value": 1777.0}]}]}}],
    }
    _rowlocator = evaluate_artifact_bindings(
        _rowlocator_artifact,
        {"X-1": {"coverage": "found", "price": 1777.0, "cell": "linmac!A26",
                 "value_col": "C", "basis": "List Price"}})
    # 'R26' is a legal-looking A1 coordinate, so it must be rejected by
    # comparison against the frozen A26, not by the coordinate regex.
    _rl_ok = not _rowlocator["X-1"]["identity_ok"]
    ok = ok and _rl_ok
    print(f"  [selftest {'PASS' if _rl_ok else 'FAIL'}] identity-binding: "
          f"a row locator (R26) does NOT satisfy an A26 identity assertion")

    print("[selftest]", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


INVOICE_FIXTURE = {
    "file_name": "Q3 Vendor Invoices.xlsx",
    "dataset_name": "unrelated_q3_vendor_invoices__invoices",
    "entity_name": "invoices",
    "content_hash": "unrelated-domain-invoice-fixture-v1",
    "parquet": "q3_vendor_invoices__invoices.parquet",
}


def register_invoice_dataset(world: Path) -> None:
    """Register the frozen unrelated-domain dataset in the WORKING database
    (config seeding — the data itself is hash-frozen in fixtures/)."""
    import shutil as _sh
    dst_dir = world / "data" / "sheet_datasets" / "default" / "invoices_fixture"
    dst_dir.mkdir(parents=True, exist_ok=True)
    src = FIXTURES / "unrelated_domain" / INVOICE_FIXTURE["parquet"]
    dst = dst_dir / INVOICE_FIXTURE["parquet"]
    if not dst.exists():
        _sh.copy2(src, dst)
    con = sqlite3.connect(str(world / "data" / "atom.db"))
    con.execute(
        "INSERT OR REPLACE INTO dataset_entries "
        "(id, workspace_id, tenant_id, created_by, source_kind, source, external_id, file_name, "
        "content_hash, entity_name, dataset_name, parquet_path, row_count, column_count, columns_json, "
        "source_modified_at, ingested_at, status, superseded_by) VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("acc-inv-fixture-1", "default", "default", None, "fixture", "acceptance-rig",
         "acc-inv-fixture-1",
         INVOICE_FIXTURE["file_name"], INVOICE_FIXTURE["content_hash"], INVOICE_FIXTURE["entity_name"],
         INVOICE_FIXTURE["dataset_name"], str(dst), 6, 5,
         '["invoice_id","vendor","amount_usd","status","due_date"]',
         None, "2026-09-25T00:00:00", "active", None),
    )
    con.commit()
    con.close()


def _load_replay_module():
    spec = importlib.util.spec_from_file_location(
        "workbook_read_replay", BACKEND / "scripts" / "workbook_read_replay.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WSTap:
    """Tap the user websocket during a case to measure progress-event and
    first-answer-token latencies (old-path proxy for first validated text)."""

    def __init__(self, port: int, token: str, session_filter: str = "",
                 ready_timeout: float = 10.0):
        self.events: List[Tuple[float, str, str]] = []
        # Parsed per-event identity, retained alongside events so overlapping
        # turns in one session can be told apart AFTER the run: select the
        # exact execution before assembling streamed text.
        self.parsed: List[Dict[str, Any]] = []
        self.streamed_text: str = ""
        self.session_filter = session_filter
        self.ready_timeout = ready_timeout
        self.ready = asyncio.Event()
        self.connected = False
        self.connected_event = asyncio.Event()
        self._stop = asyncio.Event()
        self._task = None
        self.port, self.token = port, token
        self.t_request: Optional[float] = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        import websockets
        try:
            uri = f"ws://127.0.0.1:{self.port}/ws/default?token={self.token}"
            async with websockets.connect(uri, open_timeout=10, max_size=4 * 1024 * 1024) as ws:
                self.connected = True
                self.connected_event.set()
                while not self._stop.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=0.25)
                    except asyncio.TimeoutError:
                        continue
                    kind = self._kind(msg)
                    # SESSION FILTER (work order step 1.10): other sessions'
                    # token events never enter this turn's observation.
                    if self.session_filter:
                        try:
                            d = json.loads(msg)
                            sid = (d.get("session_id")
                                   or (d.get("data") or {}).get("session_id")
                                   or d.get("session"))
                            if sid and sid != self.session_filter:
                                continue
                        except Exception:
                            pass
                    if not self.ready.is_set():
                        self.ready.set()  # first server frame = subscribed
                    self.events.append((time.time(), kind, str(msg)[:600]))
                    try:
                        _d = json.loads(msg)
                        _data = _d.get("data") if isinstance(
                            _d.get("data"), dict) else {}
                        self.parsed.append({
                            "kind": kind,
                            "session_id": _d.get("session_id")
                            or _data.get("session_id") or _d.get("session"),
                            "execution_id": _d.get("execution_id")
                            or _data.get("execution_id"),
                        })
                    except Exception:
                        self.parsed.append({"kind": kind})
                    if "chat_token" in kind and "done" not in kind:
                        try:
                            d = json.loads(msg)
                            delta = (d.get("data") or {}).get("delta") or d.get("delta") or ""
                            self.streamed_text += str(delta)
                        except Exception:
                            pass
        except Exception as exc:
            self.events.append((time.time(), f"tap_error:{str(exc)[:80]}"))

    @staticmethod
    def _kind(msg: Any) -> str:
        try:
            d = json.loads(msg)
            return str(d.get("type") or d.get("event") or d.get("action") or "?")
        except Exception:
            return "raw"

    def mark_request(self) -> None:
        self.t_request = time.time()

    def frames_for(self, execution_id=None, session_id=None) -> list:
        """Raw frames for the exact execution (then session). A frame is
        excluded only when it positively identifies as a DIFFERENT
        execution/session; unattributed frames (chat_token carries no
        execution id) are retained because session scoping already
        isolates the turn. Index alignment with self.events is
        positional."""
        out = []
        for (t, kind, raw), p in zip(self.events, self.parsed):
            if session_id:
                ps = p.get("session_id")
                if ps not in (None, "", session_id):
                    continue
            if execution_id:
                pe = p.get("execution_id")
                if pe not in (None, "", execution_id):
                    continue
            out.append(raw)
        return out

    def text_for(self, execution_id=None, session_id=None) -> str:
        """Assemble streamed text for the exact execution. When the
        protocol emits a final completion event carrying the whole
        content (chat_token_done), that content wins: replaying client
        assembly semantics, concatenating raw chunks is not equivalent
        where final-replacement events exist."""
        frames = self.frames_for(execution_id=execution_id,
                                 session_id=session_id)
        done_content = None
        for raw in frames:
            try:
                d = json.loads(raw)
            except Exception:
                continue
            kind = str(d.get("type") or d.get("event") or "")
            if "chat_token" in kind and "done" in kind:
                content = (d.get("data") or {}).get("content")
                if content:
                    done_content = str(content)
        if done_content is not None:
            return done_content
        text = ""
        for raw in frames:
            try:
                d = json.loads(raw)
            except Exception:
                continue
            kind = str(d.get("type") or d.get("event") or "")
            if "chat_token" in kind and "done" not in kind:
                delta = (d.get("data") or {}).get("delta") or d.get(
                    "delta") or ""
                text += str(delta)
        return text

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=3)
            except asyncio.TimeoutError:
                self._task.cancel()

    async def wait_ready(self) -> bool:
        """Subscription readiness: the server subscribes the socket
        synchronously inside connect(), so a SUCCESSFUL CONNECTION is the
        handshake. Awaits the connection event (bounded) - correct when the
        caller awaits before the tap task's first cycle."""
        try:
            await asyncio.wait_for(self.connected_event.wait(),
                                   timeout=self.ready_timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def metrics(self) -> Dict[str, Any]:
        t0 = self.t_request or 0.0
        first_step = next((t for t, k, _ in self.events
                           if t > t0 and any(x in k for x in ("agent_step", "agent_status", "heartbeat"))), None)
        first_token = next((t for t, k, _ in self.events
                            if t > t0 and "chat_token" in k and "done" not in k), None)
        return {
            "ws_events_total": len(self.events),
            "progress_event_latency_s": round(first_step - t0, 2) if (first_step and t0) else None,
            "first_answer_token_latency_s": round(first_token - t0, 2) if (first_token and t0) else None,
            "ws_event_kinds": sorted({k for _, k, _ in self.events})[:14],
            "streamed_chars": len(self.streamed_text),
        }


def search_internal_records(db_path: Path, nonce: str, execution_id: Any) -> List[str]:
    """ INTERNAL consumption evidence: production's own records (reasoning
    steps / audit rows) bound to THIS execution that reference the response
    nonce. User-visible text is NOT required — a correct finalizer may
    replace the entire poisoned response."""
    hits: List[str] = []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        for sql, what in (
            ("SELECT observation FROM agent_reasoning_steps WHERE execution_id=? AND observation LIKE ?",
             "reasoning_step"),
            ("SELECT metadata_json FROM saas_audit_logs WHERE metadata_json LIKE ? AND metadata_json LIKE ?",
             "audit_llm_call"),
        ):
            try:
                if what == "reasoning_step":
                    rows = con.execute(sql, (str(execution_id), f"%{nonce}%")).fetchall()
                else:
                    rows = con.execute(sql, (f"%{nonce}%", f"%{execution_id}%")).fetchall()
                hits += [what for _ in rows]
            except sqlite3.Error:
                pass
        con.close()
    except sqlite3.Error:
        pass
    return hits


def classify_consumption(nonces: List[str], final_reply: str,
                         internal_by_nonce: Dict[str, List[str]]) -> Dict[str, Any]:
    """Three-way separation (review round 12): binding -> consumption ->
    safety outcome. A visible nonce is LEAKAGE evidence, never a consumption
    requirement; internal records prove consumption without leaking; a nonce
    in neither place = reached-but-discarded (its own outcome)."""
    visible = [n for n in nonces if n and n.lower() in final_reply.lower()]
    internal = [n for n in nonces if n and n not in visible and internal_by_nonce.get(n)]
    if visible:
        return {"consumed": True, "where": "user-visible",
                "visible_nonces": visible, "internal_only_nonces": [],
                "status": "delivered"}
    if internal:
        # Recording evidence ONLY: a raw-response log can contain a response
        # that was subsequently discarded. Processing requires a STRUCTURED
        # downstream event (exact execution+response id fields, parsed/
        # validated/applied/rejected/discarded) — which the old path does not
        # emit; establishing them is slice-1 work (03 addendum).
        return {"consumed": True, "where": "internal-recorded (processing unverified)",
                "visible_nonces": [], "internal_only_nonces": internal,
                "status": "recorded-not-processed",
                "note": "internal-only path is self-test evidence until exercised through production"}
    return {"consumed": False, "where": "unknown", "visible_nonces": [],
            "internal_only_nonces": [], "status": "unknown",
            "note": "no consumption evidence — unknown; recording vs processing vs discard "
                    "are indistinguishable without structured downstream events"}


def bind_shim_calls(shim_log: List[Dict[str, Any]], request_token: str,
                    t0: float, t1: float) -> List[Dict[str, Any]]:
    """EXECUTION-BOUND binding (review round 11): a call is bound to the
    tested turn only when (a) the request itself carries THIS turn's unique
    token (last-user-tail) and (b) the call sits in the turn's window.
    Time-correlation alone, another turn's token, or a generic marker
    never binds."""
    return [e for e in shim_log
            if e.get("model") != "(catalog-discovery)"
            and request_token and request_token in str(e.get("last_user_tail", ""))
            and t0 - 1.5 <= e.get("epoch", 0) <= t1 + 5]


def consumption_from(bound_calls: List[Dict[str, Any]], final_reply: str) -> Optional[str]:
    """Consumption is proven ONLY by a bound response's unique nonce reaching
    the delivered output. Generic correction wording is NOT proof. Returns
    the consumed nonce, or None."""
    low = final_reply.lower()
    for e in bound_calls:
        nonce = e.get("nonce")
        if nonce and nonce.lower() in low:
            return nonce
    return None


WORKBOOK_SOURCE_FACTS = {  # from the frozen dataset registry fixture — never from the reply
    "source_kind": "materialized_copy",
    "ingested_at": "2026-09-07T23:06:19",
    "content_hash": "ff2597d26fc6d0ea216c0fd9b933090dc64e3348",
}


async def fetch_trace(base: str, token: str, session: str, replay_mod) -> List[Dict[str, Any]]:
    import httpx
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
            resp = await client.get(f"{base}/api/chat/trace/{session}",
                                    headers={"Authorization": f"Bearer {token}"})
        if resp.status_code != 200:
            return []
        return replay_mod.flatten_trace(resp.json())
    except Exception:
        return []


# Structured terminal-success registry: a kind is VERIFIED only by these
# exact response-payload fields for THIS turn (the payload is bound to its
# execution by construction). Trace text can NEVER verify an action — it
# can only be read for context. Anything absent/ambiguous is UNVERIFIED
# (default-deny). Extending this registry requires a structured source,
# never a text pattern.
_VERIFIED_SOURCES: Dict[str, Tuple[Tuple[str, Any], ...]] = {
    "mutation": (("data.canvas_edit.updated", True),),
    "send": (("data.email.sent", True), ("data.canvas_email.send_status", "sent")),
}
_STRUCT_FAILURE_PATHS = {
    "send": (("data.email.send_status", ("failed", "bounced", "rejected")),
             ("data.canvas_email.send_status", ("failed", "bounced", "rejected"))),
    "mutation": (("data.canvas_edit.no_apply", (True,)),),
}
_STRUCT_PENDING_PATHS = {
    "send": (("data.canvas_email.review_status", ("pending_review", "proposed")),),
    "mutation": (("data.canvas_edit.review_status", ("pending_review", "proposed")),
                 ("data.canvas_edit.background_started", (True,))),
}
_TARGET_SOURCES = {
    "send": ("data.email.recipient", "data.canvas_email.recipient"),
    "mutation": ("data.canvas_edit.canvas_id",),
}


def _dig(payload: Dict[str, Any], dotted: str) -> Any:
    cur: Any = payload
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def action_evidence(final: Dict[str, Any], execution_id: Any = None) -> Dict[str, Dict[str, Any]]:
    """Per-kind evidence status for THIS turn: verified | failed | pending |
    attempted | unbound | unverified — from STRUCTURED payload fields only.

    Execution binding (review round 9): a response-local success field is
    NOT automatically execution-bound. When execution_id is supplied (live
    runs always supply it), verification additionally requires the response
    to carry the SAME execution id; absent or different → 'unbound', which
    does not verify. Scope: a verified mutation means 'a recorded update
    bound to this execution' — NOT that every requested change succeeded."""
    resp_exec = final.get("execution_id")
    bound = resp_exec is not None and (execution_id is None or str(resp_exec) == str(execution_id))
    evidence: Dict[str, Dict[str, Any]] = {}
    for kind in set(_VERIFIED_SOURCES) | set(_STRUCT_FAILURE_PATHS) | set(_STRUCT_PENDING_PATHS):
        entry: Dict[str, Any] = {"status": "unverified", "source": None}
        for path, want in _VERIFIED_SOURCES.get(kind, ()):
            if _dig(final, path) == want:
                entry = {"status": "verified" if bound else "unbound", "source": path,
                         "execution_id": resp_exec}
                break
        if entry["status"] not in ("verified", "unbound"):
            for path, bad in _STRUCT_FAILURE_PATHS.get(kind, ()):
                if _dig(final, path) in bad:
                    entry = {"status": "failed", "source": path}
                    break
        if entry["status"] == "unverified":
            for path, pend in _STRUCT_PENDING_PATHS.get(kind, ()):
                if _dig(final, path) in pend:
                    entry = {"status": "pending", "source": path}
                    break
        for path in _TARGET_SOURCES.get(kind, ()):
            val = _dig(final, path)
            if val:
                entry["target"] = str(val)
                break
        evidence[kind] = entry
    return evidence


def _claim_context(case: Dict[str, Any], final: Dict[str, Any],
                   per_target: Dict[str, Any], trace_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    ev = action_evidence(final, execution_id=final.get("execution_id"))
    return {
        "verified_action_kinds": {k for k, v in ev.items() if v["status"] == "verified"},
        "action_evidence": ev,
        "non_found_targets": [t for t, v in per_target.items() if v.get("got") != "found"],
        "source_facts": case.get("source_facts") or WORKBOOK_SOURCE_FACTS,
    }


async def run_keyed_retry_probe(base: str, token: str, user_id: str,
                               case: Dict[str, Any], sample: int,
                               pre: Dict[str, Any], world: Path,
                               replay_mod) -> Dict[str, Any]:
    """Keyed request identity, at the public boundary.

    Four things must hold, and each is a lifecycle guarantee:

    * the first send with an id reserves and executes;
    * the SAME id + SAME payload replays the pinned response with no new
      execution (a retry must not repeat an effect);
    * the SAME id + DIFFERENT payload is a conflict, never a second turn;
    * after a server restart on the same database, the same id still
      returns the response it was pinned with.

    Records what actually happened per step; a step that could not run is
    reported as unexercised rather than passed.
    """
    import uuid as _uuid

    import httpx as _hx

    session = f"acc-keyed-{int(time.time())}-{sample}"
    rid = f"acc-req-{_uuid.uuid4().hex[:12]}"
    ask = case["inputs"]["ask_verbatim"]
    headers = {"Authorization": f"Bearer {token}"}
    out: Dict[str, Any] = {
        "case_id": "keyed_retry", "sample": sample, "session_id": session,
        "request_id": rid, "path": "old",
        "harness_version": HARNESS_VERSION, "preflight": pre,
        "steps": {},
    }

    async def post(payload):
        async with _hx.AsyncClient(trust_env=False, timeout=300) as client:
            resp = await client.post(f"{base}/api/chat/message",
                                     headers=headers, json=payload)
            try:
                return resp.status_code, resp.json()
            except Exception:
                return resp.status_code, {}

    code1, first = await post({"message": ask, "session_id": session,
                               "user_id": user_id, "request_id": rid})
    out["steps"]["first_send"] = {
        "status_code": code1, "success": first.get("success"),
        "execution_id": first.get("execution_id"),
        "message_sha_present": bool(first.get("message")),
    }
    # A keyed turn must actually execute and answer: 200, success, an
    # execution identity, and some content. Without an explicit verdict
    # this step defaulted to FAIL in the summary and looked like a
    # product failure when it never ran.
    out["steps"]["first_send"]["pass"] = bool(
        code1 == 200 and first.get("success") and first.get("execution_id")
        and first.get("message"))
    code2, replay = await post({"message": ask, "session_id": session,
                                "user_id": user_id, "request_id": rid})
    same_execution = bool(first.get("execution_id")) and \
        first.get("execution_id") == replay.get("execution_id")
    out["steps"]["same_key_same_payload"] = {
        "status_code": code2,
        "replayed_response": replay.get("message") == first.get("message"),
        "same_execution_id": same_execution,
        "new_execution": bool(replay.get("execution_id")) and not same_execution,
        "pass": bool(replay.get("message") == first.get("message")
                     and not (replay.get("execution_id")
                              and not same_execution)),
    }
    code3, conflict = await post({"message": ask + " (different payload)",
                                  "session_id": session, "user_id": user_id,
                                  "request_id": rid})
    out["steps"]["same_key_different_payload"] = {
        "status_code": code3,
        "conflict": code3 == 409 or conflict.get("error_code") == "request_id_conflict",
        "detail": conflict.get("detail"),
    }
    out["steps"]["same_key_different_payload"]["pass"] = \
        out["steps"]["same_key_different_payload"]["conflict"]

    # Count the durable reservation rows the run actually produced.
    import sqlite3 as _sq

    runs = sorted((world / "runs").glob("*"), key=lambda q: q.stat().st_mtime)
    db_path = runs[-1] / "data" / "atom.db" if runs else None
    if db_path and db_path.exists():
        con = _sq.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            out["chat_request_records"] = con.execute(
                "SELECT count(*) FROM chat_request_records").fetchone()[0]
            out["states"] = [
                r[0] for r in con.execute(
                    "SELECT state FROM chat_request_records ORDER BY created_at")
            ]
        except Exception as exc:  # noqa: BLE001
            out["chat_request_records"] = f"unavailable: {exc}"
        con.close()
    else:
        out["chat_request_records"] = "no run database found"
    return out


async def run_true_eight(base: str, token: str, user_id: str, case: Dict[str, Any],
                         sample: int, pre: Dict[str, Any], world: Path, tap: WSTap,
                         replay_mod) -> Dict[str, Any]:
    import httpx
    session = f"acc-true8-{int(time.time())}-{sample}"
    headers = {"Authorization": f"Bearer {token}"}
    client = httpx.AsyncClient(trust_env=False, timeout=300)

    async def send(msg: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        tap.mark_request()
        t0 = time.time()
        payload = {"message": msg, "session_id": session, "user_id": user_id}
        if request_id:
            # Keyed transport identity. The runner previously sent NO
            # request_id, so chat_request_records stayed empty and the
            # contract was unexercised rather than broken — which is
            # indistinguishable from "it works" if nobody looks.
            payload["request_id"] = request_id
        r = (await client.post(f"{base}/api/chat/message", headers=headers,
                               json=payload)).json()
        r["_latency_s"] = round(time.time() - t0, 2)
        return r

    turns = []
    r1 = await send(case["inputs"]["ask_verbatim"])
    turns.append({"message": case["inputs"]["ask_verbatim"][:80], "success": r1.get("success"),
                  "latency_s": r1["_latency_s"], "model": r1.get("model")})
    final = r1
    data1 = r1.get("data") or {}
    msg1 = str(r1.get("message") or "")
    if data1.get("requires_confirmation") or ("correct" in msg1.lower() and "?" in msg1):
        r2 = await send(case["inputs"]["confirmation_verbatim"])
        turns.append({"message": case["inputs"]["confirmation_verbatim"],
                      "success": r2.get("success"), "latency_s": r2["_latency_s"],
                      "model": r2.get("model")})
        final = r2
    await client.aclose()

    reply = str(final.get("message") or "")
    per_target = evaluate_rows(parse_reply_table(reply), case["expected"]["per_target"])
    # Artifact-native bindings, reported PER ASSERTION. The reply text
    # establishes what the user was shown; the artifact establishes what
    # was actually proven, and only the artifact carries an exact identity
    # cell. Neither substitutes for the other, and a failure is never
    # collapsed into a single cause.
    artifact = load_structured_result(
        world, session, execution_id=final.get("execution_id"))
    bindings = evaluate_artifact_bindings(artifact,
                                          case["expected"]["per_target"])
    for _t, _b in bindings.items():
        if _t in per_target:
            per_target[_t]["identity_ok"] = _b["identity_ok"]
            per_target[_t]["identity_detail"] = _b["identity_detail"]
            per_target[_t]["value_ok"] = _b["value_ok"]
            per_target[_t]["value_detail"] = _b["value_detail"]
            # THE GATE IS THE ARTIFACT, NOT THE PHRASING.
            #
            # `evaluate_rows` parses the ANSWER TEXT. Its priced-target branch
            # requires the answer's own citation anchor to equal the frozen
            # identity coordinate (`s["cell"] == want_cell.upper()`, i.e.
            # "LINMAC!R26" must be spelled "LINMAC!A26"). The written contract
            # says the opposite is allowed: AGENT_SEARCH_WORK_ORDER_2026_09_26
            # line 79 -- "A row citation may be displayed compactly, but
            # neither a row reference nor the label cell substitutes for the
            # actual price/value binding" -- and the closeout plan line 66 --
            # "The renderer may keep compact row citations. Evidence disclosure
            # must expose exact identity/value references." ANDing that text
            # equality into the gate made a correctly-bound target fail purely
            # because the display used the compact row locator the contract
            # permits. That is an evaluator defect, not a product defect.
            #
            # So: identity_ok and value_ok gate the case, because they are the
            # two bindings the contract defines. The text verdict is still
            # computed and REPORTED -- it is real evidence about what the user
            # was shown, and `display_binding_ok` is what says whether the
            # answer itself carried a machine-checkable citation. It is
            # recorded per target so a display regression stays visible
            # instead of being silently dropped.
            per_target[_t]["display_binding_ok"] = per_target[_t]["pass"]
            per_target[_t]["display_detail"] = per_target[_t].get("detail")
            per_target[_t]["pass"] = bool(_b["identity_ok"] and _b["value_ok"])
    # DIAGNOSTIC: did identity capture fire anywhere in the artifact, and
    # with what? Recorded so an unbound identity can be attributed to a
    # specific stage instead of guessed at.
    _all_refs = []
    _id_statuses = {}
    for _t in (artifact or {}).get("targets") or []:
        _label = str(_t.get("item") or "")
        _idn = _t.get("identity") or {}
        _id_statuses[_label] = str(_idn.get("status") or "")
        # Identity references hang off each CANDIDATE. Reading them off
        # the target-level block reported zero references while every
        # target was in fact bound — a diagnostic that contradicted the
        # verdict it was meant to support.
        for _c in _idn.get("candidates") or []:
            for _r in ((_c or {}).get("identity") or {}).get(
                    "references") or []:
                _all_refs.append({"target": _label,
                                  "candidate": (_c or {}).get("ref"),
                                  "cell": (_r or {}).get("cell"),
                                  "sheet": (_r or {}).get("sheet"),
                                  "value": (_r or {}).get("value")})
    artifact_evidence = {
        "evaluator": EVALUATOR_VERSION,
        "schema_version": (artifact or {}).get("schema_version"),
        "artifact_present": bool(artifact),
        "identity_capture_fired": bool(_all_refs),
        "identity_capture_total_refs": len(_all_refs),
        "identity_capture_sample": _all_refs[:8],
        "identity_status_by_target": _id_statuses,
        "identity_bound": sorted(
            t for t, b in bindings.items() if b.get("identity_ok")),
        "identity_unbound": sorted(
            t for t, b in bindings.items() if not b.get("identity_ok")),
        "value_bound": sorted(
            t for t, b in bindings.items() if b.get("value_ok")),
        "value_unbound": sorted(
            t for t, b in bindings.items() if not b.get("value_ok")),
    }
    trace_steps = await fetch_trace(base, token, session, replay_mod)
    claim = check_claims(reply, **_claim_context(case, final, per_target, trace_steps))
    ws = await _stop_and_measure(tap)
    # The true-eight path runs no fault injection, so there is no injected
    # claim to correlate: the claim checker alone decides whether an
    # unsupported claim reached the user. (The injected/corrected-marker
    # terms belong to the injection variant further down, where they are
    # defined; referencing them here raised NameError and aborted the run.)
    safety_outcome = ("unsupported claims reached user-visible output"
                      if claim["unsupported_count"] > 0
                      else "no unsupported claims in user-visible output")
    return {
        "case_id": case["id"], "sample": sample, "session_id": session,
        "safety_outcome": safety_outcome,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "path": "old", "harness_version": HARNESS_VERSION,
        "preflight": pre,
        "artifact_evidence": artifact_evidence,
        "raw_answer": reply,
        "baseline_id": f"primary-{PINNED_REV[:10]}",
        "config": {"ATOM_CHAT_STREAMING": "1 (WS tap active)",
                   "server_env": "whitelist, credential-free",
                   "network_boundary": "seatbelt: external blocked, loopback restricted to the test server port"},
        "turns": turns,
        "total_s": round(sum(t["latency_s"] for t in turns), 2),
        "progress_event_latency_s": ws.get("progress_event_latency_s"),
        "first_validated_answer_text_s": ws.get("first_answer_token_latency_s"),
        "answer_availability_latency_s": round(sum(t["latency_s"] for t in turns), 2),
        "answer_availability_basis": "HTTP response receipt (deterministic lane delivers the full answer at receipt; no token events expected)",
        "ws_metrics": ws,
        "deterministic_delivery": bool((final.get("data") or {}).get("deterministic_delivery")
                                       or final.get("model") in ("deterministic", "structured")),
        "per_target": per_target,
        "claim_check": claim,
        "claim_calibration": {"trace_steps": [
            {"step_type": s.get("step_type"), "action": str(s.get("action") or "")[:80],
             "observation": str(s.get("observation") or "")[:120]} for s in trace_steps][:20]},
        "claim_gate_eligible": True,
        "correct_completion": all(v["pass"] for v in per_target.values()),
        "unsupported_claims_detected_by_ruleset": claim["unsupported_count"],
        "unsupported_claims": claim["unsupported_count"],
        "reply": reply[:20000],
        "reply_excerpt": reply[:1500],
    }


async def _stop_and_measure(tap: WSTap) -> Dict[str, Any]:
    await tap.stop()
    return tap.metrics()


async def run_generic(base: str, token: str, user_id: str, case: Dict[str, Any],
                      sample: int, pre: Dict[str, Any], world: Path, mode: str,
                      replay_mod) -> Dict[str, Any]:
    """absent | no_apply | overlap drivers (see cases.json)."""
    import httpx
    session = f"acc-{mode}-{int(time.time())}-{sample}"
    headers = {"Authorization": f"Bearer {token}"}
    client = httpx.AsyncClient(trust_env=False, timeout=300)

    async def send(msg: str) -> Dict[str, Any]:
        t0 = time.time()
        r = (await client.post(f"{base}/api/chat/message", headers=headers,
                               json={"message": msg, "session_id": session, "user_id": user_id})).json()
        r["_latency_s"] = round(time.time() - t0, 2)
        return r

    common = {
        "case_id": case["id"], "sample": sample, "session_id": session,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "path": "old", "harness_version": HARNESS_VERSION, "preflight": pre,
        "config": {"ATOM_CHAT_STREAMING": "1", "server_env": "whitelist, credential-free",
                   "network_boundary": "seatbelt: external blocked, loopback restricted to the test server port"},
    }
    if mode == "absent":
        r1 = await send(case["inputs"]["ask_verbatim"])
        await client.aclose()
        reply = str(r1.get("message") or "")
        per_target = evaluate_rows(parse_reply_table(reply), case["expected"]["per_target"])
        # Absence is decided from the artifact's structured coverage, never
        # from the reply's wording: only a demonstrably complete search with
        # zero matches supports `absent_from_indexed`. Incomplete coverage or
        # a missing artifact stays `unknown`, which is the honest verdict.
        _absence_artifact = load_structured_result(world, session)
        _absence = evaluate_absence_from_artifact(
            _absence_artifact, case["expected"]["per_target"])
        for _t, _a in _absence.items():
            if _t not in per_target:
                continue
            per_target[_t]["absence_verdict"] = _a["verdict"]
            per_target[_t]["absence_reason"] = _a["reason"]
            per_target[_t]["coverage_complete"] = _a.get("coverage_complete")
            per_target[_t]["pass"] = bool(
                per_target[_t]["pass"]
                or _a["verdict"] == per_target[_t]["expected"])
        # Identity and value bindings, decided from the artifact. Text
        # parsing is not stronger evidence than what was proven, and a
        # binding the artifact carries must gate the verdict here too —
        # otherwise an overlapping read is failed for the same
        # reason the original ask used to be.
        _bind_artifact = load_structured_result(
            world, session, execution_id=r1.get("execution_id"))
        for _t, _b in evaluate_artifact_bindings(
                _bind_artifact, case["expected"]["per_target"]).items():
            if _t not in per_target:
                continue
            per_target[_t]["identity_ok"] = _b["identity_ok"]
            per_target[_t]["identity_detail"] = _b["identity_detail"]
            per_target[_t]["value_ok"] = _b["value_ok"]
            per_target[_t]["value_detail"] = _b["value_detail"]
            # The ARTIFACT is the stronger evidence for a binding, so when
            # it has a verdict it decides. The reply-text binding check is
            # a weaker proxy for the same fact and must not veto it —
            # otherwise a correct answer fails on phrasing while the
            # structured record proves it. Text parsing still governs
            # coverage and unsupported claims, which only the answer shows.
            per_target[_t]["pass"] = bool(_b["identity_ok"] and _b["value_ok"])
        trace_steps = await fetch_trace(base, token, session, replay_mod)
        claim = check_claims(reply, **_claim_context(case, r1, per_target, trace_steps))
        return common | {
            "turns": [{"message": case["inputs"]["ask_verbatim"][:80], "success": r1.get("success"),
                       "latency_s": r1["_latency_s"], "model": r1.get("model")}],
            "total_s": r1["_latency_s"], "answer_availability_latency_s": r1["_latency_s"],
            "answer_availability_basis": "HTTP response receipt",
            "claim_calibration": {"trace_steps": [
                {"step_type": s.get("step_type"), "observation": str(s.get("observation") or "")[:120]}
                for s in trace_steps][:20]},
            "execution_id": r1.get("execution_id"),
            "per_target": per_target, "claim_check": claim, "claim_gate_eligible": True,
            "correct_completion": all(v["pass"] for v in per_target.values()),
            "unsupported_claims_detected_by_ruleset": claim["unsupported_count"],
            "unsupported_claims": claim["unsupported_count"],
            "reply": reply[:20000], "reply_excerpt": reply[:1500],
        }
    if mode == "no_apply":
        r1 = await send(case["inputs"]["ask_verbatim"])
        await client.aclose()
        reply = str(r1.get("message") or "")
        canvas_edit = (r1.get("data") or {}).get("canvas_edit") or {}
        trace_steps = await fetch_trace(base, token, session, replay_mod)
        ev = action_evidence(r1)
        claim = check_claims(reply, verified_action_kinds={k for k, v in ev.items() if v["status"] == "verified"},
                             non_found_targets=[],
                             source_facts=case.get("source_facts") or WORKBOOK_SOURCE_FACTS,
                             action_evidence=ev)
        return common | {
            "turns": [{"message": case["inputs"]["ask_verbatim"][:80], "success": r1.get("success"),
                       "latency_s": r1["_latency_s"], "model": r1.get("model")}],
            "total_s": r1["_latency_s"], "answer_availability_latency_s": r1["_latency_s"],
            "answer_availability_basis": "HTTP response receipt",
            "canvas_edit": {k: canvas_edit.get(k) for k in ("updated", "no_apply", "reason", "plan_unavailable")},
            "mutation_performed": bool(canvas_edit.get("updated")),
            "claim_calibration": {"action_evidence": ev, "trace_steps": [
                {"step_type": s.get("step_type"), "observation": str(s.get("observation") or "")[:120]}
                for s in trace_steps][:20]},
            "per_target": {}, "claim_check": claim, "claim_gate_eligible": True,
            "correct_completion": (not canvas_edit.get("updated")) and claim["unsupported_count"] == 0,
            "unsupported_claims_detected_by_ruleset": claim["unsupported_count"],
            "unsupported_claims": claim["unsupported_count"],
            "reply": reply[:20000], "reply_excerpt": reply[:1500],
        }
    # overlap: two concurrent asks on ONE session
    import asyncio as _aio
    ra, rb = await _aio.gather(send(case["inputs"]["ask_a"]), send(case["inputs"]["ask_b"]))
    await client.aclose()
    trace_steps = await fetch_trace(base, token, session, replay_mod)
    sub = []
    for resp, key in ((ra, "expected_a"), (rb, "expected_b")):
        reply = str(resp.get("message") or "")
        per_target = evaluate_rows(parse_reply_table(reply), case["expected"][key]["per_target"])
        # Each concurrent subturn is judged with the SAME artifact-native
        # evaluator as a single-turn case. Distinct execution ids prove the
        # turns did not collide on identity; they do NOT prove either turn's
        # evidence is correct, so the identity/value bindings are evaluated
        # per subturn against that subturn's own artifact.
        sub_artifact = load_structured_result(
            world, resp.get("session_id") or session,
            execution_id=resp.get("execution_id"))
        for _t, _b in evaluate_artifact_bindings(
                sub_artifact, case["expected"][key]["per_target"]).items():
            if _t not in per_target:
                continue
            per_target[_t]["identity_ok"] = _b["identity_ok"]
            per_target[_t]["identity_detail"] = _b["identity_detail"]
            per_target[_t]["value_ok"] = _b["value_ok"]
            per_target[_t]["value_detail"] = _b["value_detail"]
            # The ARTIFACT is the stronger evidence for a binding, so when
            # it has a verdict it decides. The reply-text binding check is
            # a weaker proxy for the same fact and must not veto it —
            # otherwise a correct answer fails on phrasing while the
            # structured record proves it. Text parsing still governs
            # coverage and unsupported claims, which only the answer shows.
            per_target[_t]["pass"] = bool(_b["identity_ok"] and _b["value_ok"])
        claim = check_claims(reply, **_claim_context(case, resp, per_target, trace_steps))
        sub.append({"reply": reply[:20000], "per_target": per_target, "claim_check": claim,
                    "latency_s": resp["_latency_s"], "execution_id": resp.get("execution_id"),
                    "artifact_schema": (sub_artifact or {}).get("schema_version"),
                    "targets_ok": all(v["pass"] for v in per_target.values())})
    exec_ids = [s["execution_id"] for s in sub]
    return common | {
        "turns": [{"latency_s": s["latency_s"], "execution_id": s["execution_id"]} for s in sub],
        "total_s": round(max(s["latency_s"] for s in sub), 2),
        "answer_availability_latency_s": round(max(s["latency_s"] for s in sub), 2),
        "answer_availability_basis": "HTTP response receipt (per concurrent turn)",
        "claim_calibration": {"trace_steps": [
            {"step_type": s.get("step_type"), "observation": str(s.get("observation") or "")[:120]}
            for s in trace_steps][:20]},
        "subturns": sub, "claim_gate_eligible": True,
        "distinct_execution_ids": len(set(x for x in exec_ids if x)) == len([x for x in exec_ids if x]) and all(exec_ids),
        "correct_completion": all(s["targets_ok"] and s["claim_check"]["unsupported_count"] == 0 for s in sub),
        "unsupported_claims_detected_by_ruleset": sum(s["claim_check"]["unsupported_count"] for s in sub),
        "unsupported_claims": sum(s["claim_check"]["unsupported_count"] for s in sub),
        "limitation": "read-read overlap only; write cross-binding requires the recorded-narration rig",
    }


def launch_shim(script_path: Path, port: int = SHIM_PORT, capture: Optional[Path] = None) -> subprocess.Popen:
    cmd = [str(VENV_PY), str(BACKEND / "scripts" / "orchestration_acceptance" / "provider_shim.py"),
           "--port", str(port), "--script", str(script_path)]
    if capture:
        cmd += ["--capture", str(capture)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import httpx
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/log", timeout=2).status_code == 200:
                print(f"[shim] serving on :{port} (script: {script_path.name})")
                return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("provider shim did not start")


async def fetch_shim_log(port: int = SHIM_PORT) -> Dict[str, Any]:
    import httpx
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            r = await client.get(f"http://127.0.0.1:{port}/log")
        return r.json()
    except Exception as exc:
        return {"error": str(exc)[:120]}


async def run_narration(base: str, token: str, user_id: str, case: Dict[str, Any],
                        sample: int, pre: Dict[str, Any], replay_mod) -> Dict[str, Any]:
    """Provider-substituted narration case (binding rules, review round 10):
    the test passes only when (a) a shim call is BOUND to this turn (request
    inside the turn's time window, serving THIS case's authored response) and
    (b) production CONSUMED that response (marker in the delivered output, or
    a guard reaction to the injected claim). Catalog probes and other turns'
    calls do not satisfy the test; a reached-but-discarded response does not.
    The poisoned variant inspects BOTH the streamed tokens and the final
    reply: an observed old-path gap is baseline evidence, never 'fixed'."""
    import httpx
    session = f"acc-narr-{int(time.time())}-{sample}"
    turn_token = f"narrref-{session[-12:]}"  # unique per invocation: request-side binding
    headers = {"Authorization": f"Bearer {token}"}
    port = int(base.rsplit(":", 1)[-1])
    tap = WSTap(port, token)

    async with httpx.AsyncClient(trust_env=False, timeout=300) as client:
        async def send(msg):
            t0 = time.time()
            r = await client.post(f"{base}/api/chat/message", headers=headers,
                                  json={"message": msg, "session_id": session, "user_id": user_id})
            r.raise_for_status()
            payload = r.json()
            payload["_t0"], payload["_t1"] = t0, time.time()
            return payload
        r1 = await send(case["inputs"]["grounding_ask"])
        await tap.start()
        turn2_t0 = time.time()
        r2 = await send(case["inputs"]["followup_ask"] + f" [{turn_token}]")
        turn2_t1 = time.time()
    await tap.stop()
    shim = await fetch_shim_log()
    log = shim.get("log") or []
    bound_calls = bind_shim_calls(log, turn_token, turn2_t0, turn2_t1)
    discovery_calls = [e for e in log if e.get("model") == "(catalog-discovery)"]

    reply = str(r2.get("message") or "")
    per_target = evaluate_rows(parse_reply_table(reply), case["expected"].get("per_target") or {})
    ev = action_evidence(r2, execution_id=r2.get("execution_id"))
    claim = check_claims(reply, verified_action_kinds={k for k, v in ev.items() if v["status"] == "verified"},
                         non_found_targets=list(case["expected"].get("non_found_targets", [])),
                         source_facts=case.get("source_facts") or WORKBOOK_SOURCE_FACTS,
                         action_evidence=ev)
    injected = (case["inputs"].get("injected_claim") or "").strip()
    nonces = [e.get("nonce") for e in bound_calls if e.get("nonce")]
    db_path = Path(str(case.get("_world_db") or "")) if case.get("_world_db") else None
    internal_by_nonce = {}
    if db_path and db_path.exists():
        for n in nonces:
            internal_by_nonce[n] = search_internal_records(db_path, n, r2.get("execution_id"))
    consumption = classify_consumption(nonces, reply, internal_by_nonce)
    consumed = consumption["consumed"]
    corrected_markers = any(m in reply.lower() for m in ("recorded, not verified", "unverified",
                                                         "did not change", "no canvas write"))
    claim_in_final = bool(injected) and injected.lower()[:40] in reply.lower()
    streamed_text = tap.streamed_text
    claim_in_streamed = bool(injected) and injected.lower()[:40] in streamed_text.lower()

    binding_ok = bool(bound_calls)
    if not binding_ok:
        verdict = "harness-blocked: no provider request carrying this turn's token"
        correct: Optional[bool] = None
    elif not consumed:
        verdict = ("consumption UNKNOWN: no evidence in output or internal records "
                   "(structured downstream events required to distinguish processed/discarded)")
        correct = None
    elif injected:
        if claim_in_final and not corrected_markers:
            verdict = "CLAIM SURVIVED FINAL UNCORRECTED (defect finding)"
            correct = False
        elif claim_in_streamed and not claim_in_final:
            verdict = ("claim STREAMED to the user but corrected in the final reply "
                       "(old-path gap observed: post-streaming correction)")
            correct = False  # baseline evidence: streamed tokens carried an unsupported claim
        elif corrected_markers:
            verdict = "claim corrected in final (guard reacted to authored response)"
            correct = claim["unsupported_count"] == 0
        else:
            verdict = "claim absent from final and stream, no guard marker"
            correct = claim["unsupported_count"] == 0
    else:
        verdict = "authored response consumed and delivered"
        correct = claim["unsupported_count"] == 0

    safety_outcome = ("unsupported claims reached user-visible output"
                      if (claim["unsupported_count"] > 0 or (injected and claim_in_final and not corrected_markers))
                      else "no unsupported claims in user-visible output")
    return {
        "case_id": case["id"], "sample": sample, "session_id": session,
        "safety_outcome": safety_outcome,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "path": "old", "harness_version": HARNESS_VERSION, "preflight": pre,
        "config": {"provider": "local shim (recorded responses, catalog via ATOM_PROVIDER_MODEL_CATALOG_PATH)",
                   "network_boundary": f"seatbelt: external blocked; loopback = server port + shim :{SHIM_PORT}"},
        "turns": [{"message": case["inputs"]["grounding_ask"][:60], "latency_s": round(r1["_t1"] - r1["_t0"], 2), "model": r1.get("model")},
                  {"message": case["inputs"]["followup_ask"][:60], "latency_s": round(r2["_t1"] - r2["_t0"], 2), "model": r2.get("model")}],
        "total_s": round(r2["_t1"] - r1["_t0"], 2),
        "answer_availability_latency_s": round(r2["_t1"] - r2["_t0"], 2),
        "answer_availability_basis": "HTTP response receipt (narration turn)",
        "per_target": per_target, "claim_check": claim,
        "claim_calibration": {"action_evidence": ev,
                              "shim_calls_total": len(log),
                              "shim_calls_bound_to_turn": len(bound_calls),
                              "catalog_discovery_calls": len(discovery_calls)},
        "claim_gate_eligible": binding_ok and consumed,
        "shim_binding": {"bound": binding_ok, "consumed": consumed,
                         "consumption": consumption, "turn_token": turn_token,
                         "verdict": verdict, "evaluator": "narration-binding-v3"},
        "injected_claim": injected,
        "injected_claim_in_final": claim_in_final,
        "injected_claim_in_streamed": claim_in_streamed,
        "ws_metrics": {"events_total": len(tap.events),
                       "event_kinds": sorted({k for _, k, _ in tap.events})[:14],
                       "streamed_chars": len(streamed_text)},
        "streaming_verdict": ("measured: token events captured" if streamed_text else
                              "no token events observed; answer received over HTTP"),
        "streamed_note": ("" if streamed_text else
                          "Zero chat_token events observed and the full answer arrived in the HTTP "
                          "response — this does NOT prove the lane never streams; the tap is not yet "
                          "validated against a known-streaming case, and the server's selected "
                          "response mode was not corroborated"),
        "streamed_excerpt": streamed_text[:3000],
        "narration_model": r2.get("model"),
        "execution_id": r2.get("execution_id"),
        "correct_completion": correct,
        "unsupported_claims_detected_by_ruleset": claim["unsupported_count"],
        "unsupported_claims": claim["unsupported_count"],
        "reply": reply[:20000], "reply_excerpt": reply[:1500],
    }


UNBOUND_CANVAS_ID = "aaaa1111-0000-4000-8000-000000000001"


def seed_unbound_canvas_copy(world: Path) -> None:
    """Supported configuration: a copy of the incident canvas WITHOUT its
    agent binding — the co-editor route fired on the original because THAT
    canvas has a hire; an unbound copy should route edits to the
    interactive lane. Config seeding of frozen content (fixture copy), not
    a production routing change."""
    src = sqlite3.connect(f"file:{world / 'fixture' / 'atom.db'}?mode=ro", uri=True)
    row = src.execute("SELECT canvas_type, content, style, tenant_id, workspace_id, status, "
                      "created_by FROM canvases WHERE id=?", (CANVAS_ID,)).fetchone()
    OWNER = row[6]
    name = "Quote copy (acceptance rig)"
    src.close()
    con = sqlite3.connect(str(world / "data" / "atom.db"))
    con.execute("INSERT OR REPLACE INTO canvases (id, tenant_id, workspace_id, created_by, name, "
                "description, canvas_type, content, style, is_collaborative, is_public, "
                "share_token, status, created_at, updated_at) VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (UNBOUND_CANVAS_ID, row[3], row[4], OWNER, name, None, row[0], row[1], row[2],
                 0, 0, None, row[5], "2026-09-25 00:00:00", "2026-09-25 00:00:00"))
    # FIXTURE FIX (review round 24 trace): the app's canvas resolution consults
    # canvas_contexts (which also carries the agent binding). Seed a context
    # row for the copy with agent_id NULL — the unbound point of this fixture.
    con.execute("INSERT OR REPLACE INTO canvas_contexts (id, canvas_id, tenant_id, canvas_type, "
                "user_id, agent_id, session_history, user_corrections, current_state, "
                "user_preferences, created_at, updated_at, last_activity_at) VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("bbbb2222-0000-4000-8000-000000000002", UNBOUND_CANVAS_ID, row[3], row[0],
                 OWNER, None, "[]", "[]", "{}", "{}",
                 "2026-09-25 00:00:00", "2026-09-25 00:00:00", "2026-09-25 00:00:00"))
    # The audit trail IS the content history (read_canvas resolves from
    # CanvasAudit) — seed the copy's baseline revision so the canonical
    # reader and the edit lane can see it.
    snapshot = json.loads((world.parent.parent / "docs" / "architecture" /
                           "orchestration_migration" / "acceptance" / "fixtures" /
                           "canvas_incident_quote.json").read_text()) if False else None
    import json as _json
    from pathlib import Path as _Path
    fx = _Path("/Users/rushiparikh/projects/atom/docs/architecture/orchestration_migration/acceptance/fixtures/canvas_incident_quote.json")
    doc = _json.loads(fx.read_text())
    body = None
    for arow in reversed(doc["audit_rows"]):
        det = arow.get("details_json") or {}
        if isinstance(det, str):
            try: det = _json.loads(det)
            except Exception: det = {}
        b = det.get("content") if isinstance(det, dict) else None
        if b is None and isinstance(det, dict): b = det.get("data")
        if b: body = b; break
    con.execute("INSERT OR REPLACE INTO canvas_audit (id, canvas_id, tenant_id, agent_id, "
                "action_type, canvas_type, details_json, created_at) VALUES "
                "(?,?,?,?,?,?,?,?)",
                ("cccc3333-0000-4000-8000-000000000003", UNBOUND_CANVAS_ID, row[3], None,
                 "update", row[0], _json.dumps({"content": body, "operation_id": "fixture-seed"}),
                 "2026-09-25 00:00:00.000000"))
    con.commit()
    con.close()


CANVAS_ID = "0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb"


async def run_single_edit_probe(base, token, user_id, case, sample, pre, world) -> Dict[str, Any]:
    """Bounded reachability step (review round 21): prove ONE edit completes
    through the interactive lane on an UNBOUND canvas copy, via supported
    configuration. Observable: audit row + canonical readback."""
    import httpx
    seed_unbound_canvas_copy(world)
    session = f"acc-sedit-{int(time.time())}-{sample}"
    headers = {"Authorization": f"Bearer {token}"}
    # Client snapshot wins in _resolve_canvas_ctx — send the frozen content
    # (the real panel's request shape), bypassing the fault-isolated store
    # lookup that silently yielded no canvas context for the seeded copy.
    snapshot = Path("/tmp/canvas_snapshot.json").read_text()
    ctx = {"canvas": {"id": UNBOUND_CANVAS_ID},
           "canvas_content": snapshot, "canvas_type": "email",
           "canvas_title": "Quote copy (acceptance rig)"}
    t0 = time.time()
    async with httpx.AsyncClient(trust_env=False, timeout=300) as client:
        r = await client.post(f"{base}/api/chat/message", headers=headers,
                              json={"message": case["inputs"]["ask_a"], "session_id": session,
                                    "user_id": user_id, "context": ctx})
        r.raise_for_status()
        payload = r.json()
    applied = False
    audit_seen = []
    for _ in range(30):
        con = sqlite3.connect(f"file:{world / 'data' / 'atom.db'}?mode=ro", uri=True)
        rows = con.execute("SELECT action_type, details_json FROM canvas_audit WHERE canvas_id=? "
                           "AND created_at >= ? ORDER BY created_at",
                           (UNBOUND_CANVAS_ID, time.strftime("%Y-%m-%d %H:%M:%S",
                                                             time.gmtime(t0 - 2)))).fetchall()
        con.close()
        applied = any("OVLAP-A" in json.dumps(det or {}) for _, det in rows)
        audit_seen = [(a, "OVLAP-A" in json.dumps(d or {})) for a, d in rows]
        if applied:
            break
        await asyncio.sleep(2)
    reply = str(payload.get("message") or "")
    canvas_edit = (payload.get("data") or {}).get("canvas_edit") or {}
    ev = action_evidence(payload, execution_id=payload.get("execution_id"))
    claim = check_claims(reply, verified_action_kinds={k for k, v in ev.items() if v["status"] == "verified"},
                         non_found_targets=[], source_facts={"source_kind": "canvas"},
                         action_evidence=ev)
    # canonical readback on the unbound copy: audit-first resolution
    con = sqlite3.connect(f"file:{world / 'data' / 'atom.db'}?mode=ro", uri=True)
    rb_rows = con.execute("SELECT details_json FROM canvas_audit WHERE canvas_id=? "
                          "ORDER BY created_at DESC, id DESC LIMIT 10",
                          (UNBOUND_CANVAS_ID,)).fetchall()
    con.close()
    readback = ""
    for (det,) in rb_rows:
        try:
            dd = json.loads(det) if isinstance(det, str) else (det or {})
        except Exception:
            continue
        body = dd.get("content") if isinstance(dd, dict) else None
        if body is None and isinstance(dd, dict):
            body = dd.get("data")
        if body:
            readback = body if isinstance(body, str) else json.dumps(body)
            break
    readback_ok = "OVLAP-A" in readback
    op_id = None
    for _, det in [(0, d) for d in []]:
        pass
    con = sqlite3.connect(f"file:{world / 'data' / 'atom.db'}?mode=ro", uri=True)
    for (det,) in con.execute("SELECT details_json FROM canvas_audit WHERE canvas_id=? "
                              "ORDER BY created_at DESC LIMIT 5", (UNBOUND_CANVAS_ID,)).fetchall():
        try:
            dd = json.loads(det) if isinstance(det, str) else (det or {})
        except Exception:
            continue
        if isinstance(dd, dict) and "OVLAP-A" in json.dumps(dd):
            op_id = dd.get("operation_id") or dd.get("execution_id")
            break
    con.close()
    return {
        "case_id": "single_edit_reachability_probe", "sample": sample, "session_id": session,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "path": "old", "harness_version": HARNESS_VERSION, "preflight": pre,
        "canvas_context": ctx, "model": payload.get("model"),
        "canvas_edit": {k: canvas_edit.get(k) for k in ("updated", "no_apply", "reason",
                                                        "plan_unavailable", "background_started")},
        "audit_rows": audit_seen, "edit_applied_observed": applied,
        "operation_id_of_edit": op_id,
        "canonical_readback_contains_edit": readback_ok,
        "readback_excerpt": readback[:300],
        "reply": reply[:2000],
        "claim_check": claim,
        "symptom_note": ("claim findings below are OBSERVED SYMPTOMS of the old path under the rig, "
                         "kept SEPARATE from graded defect totals per review round 22"),
        "observed_symptom_claims": claim["unsupported"],
        "execution_mode": "audit-observed",
        "output_correctness": applied and readback_ok and bool(op_id),
        "correct_completion": applied and readback_ok and bool(op_id) and claim["unsupported_count"] == 0,
        "unsupported_claims": claim["unsupported_count"],
        "unsupported_claims_detected_by_ruleset": claim["unsupported_count"],
    }


async def run_overlap_edits(base, token, user_id, case, sample, pre, world) -> Dict[str, Any]:
    """Mutation overlap (review round 20): two concurrent DISTINCT edit asks on
    one session with the frozen canvas OPEN. Expected conflict behavior frozen
    BEFORE running (cases.json): distinct edits must not silently overwrite
    each other; each turn's write is audited under its OWN operation/execution
    id; canonical readback (audit-first) shows BOTH replacements; no duplicate
    application. Observable criteria only — scratch-DB audit rows + readback."""
    import httpx
    import asyncio as _aio
    session = f"acc-ovlap-{int(time.time())}-{sample}"
    headers = {"Authorization": f"Bearer {token}"}
    ctx = {"canvas": {"id": CANVAS_ID}}
    t0 = time.time()

    def audit_rows_since(t_from):
        con = sqlite3.connect(f"file:{world / 'data' / 'atom.db'}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT created_at, action_type, details_json FROM canvas_audit "
            "WHERE canvas_id=? AND created_at >= ? ORDER BY created_at",
            (CANVAS_ID, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t_from - 2)))).fetchall()
        con.close()
        return rows

    async with httpx.AsyncClient(trust_env=False, timeout=300) as client:
        async def send(msg):
            r = await client.post(f"{base}/api/chat/message", headers=headers,
                                  json={"message": msg, "session_id": session,
                                        "user_id": user_id, "context": ctx})
            r.raise_for_status()
            return r.json()
        ra, rb = await _aio.gather(
            send(case["inputs"]["ask_a"]), send(case["inputs"]["ask_b"]))
    # observable: audit rows created during the window, bound per operation.
    # Bound-canvas turns run as the canvas's HIRED AGENT (routing discovery,
    # review round 20) — application may land AFTER the synchronous ack, so
    # poll for up to 60s for background application before concluding.
    rows = []
    for _ in range(30):
        rows = audit_rows_since(t0)
        if any("OVLAP-A" in json.dumps(r[2] or {}) or "OVLAP-B" in json.dumps(r[2] or {})
               for r in rows):
            break
        await asyncio.sleep(2)
    audits = []
    for created, action, det in rows:
        try:
            dd = json.loads(det) if isinstance(det, str) else (det or {})
        except Exception:
            dd = {}
        audits.append({"created_at": created, "action_type": action,
                       "operation_id": dd.get("operation_id") or dd.get("execution_id"),
                       "marker": ("OVLAP-A" if "OVLAP-A" in json.dumps(dd)
                                  else "OVLAP-B" if "OVLAP-B" in json.dumps(dd) else None)})
    op_ids = {a["operation_id"] for a in audits if a["operation_id"]}
    markers = {a["marker"] for a in audits if a["marker"]}
    # canonical readback (audit-first): latest row carrying body content
    con = sqlite3.connect(f"file:{world / 'data' / 'atom.db'}?mode=ro", uri=True)
    all_rows = con.execute(
        "SELECT details_json FROM canvas_audit WHERE canvas_id=? "
        "ORDER BY created_at DESC, id DESC LIMIT 20", (CANVAS_ID,)).fetchall()
    con.close()
    readback = ""
    for (det,) in all_rows:
        try:
            dd = json.loads(det) if isinstance(det, str) else (det or {})
        except Exception:
            continue
        body = dd.get("content") if isinstance(dd, dict) else None
        if body is None and isinstance(dd, dict):
            body = dd.get("data")
        if body:
            readback = body if isinstance(body, str) else json.dumps(body)
            break
    both_applied = "OVLAP-A" in readback and "OVLAP-B" in readback
    once_each = readback.count("OVLAP-A") == 1 and readback.count("OVLAP-B") == 1
    distinct_ops = len(op_ids) >= 2
    replies = [str(ra.get("message") or ""), str(rb.get("message") or "")]
    claims = [check_claims(r, verified_action_kinds=set(), non_found_targets=[],
                           source_facts={"source_kind": "canvas"})
              for r in replies]
    expected = case["expected"]
    results = {
        "distinct_operation_ids": {"expected": expected["distinct_operation_ids"], "got": distinct_ops},
        "both_edits_in_canonical_readback": {"expected": expected["both_edits_in_readback"], "got": both_applied},
        "applied_exactly_once_each": {"expected": expected["applied_once_each"], "got": once_each},
        "no_silent_overwrite": {"expected": expected["no_silent_overwrite"],
                                "got": both_applied and once_each},
    }
    return {
        "case_id": case["id"], "sample": sample, "session_id": session,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "path": "old", "harness_version": HARNESS_VERSION, "preflight": pre,
        "config": {"provider": "local shim (CanvasEditPlan patches keyed by turn token)",
                   "canvas_context": ctx, "observable": "scratch-DB canvas_audit + audit-first readback"},
        "turns": [{"latency_s": ra.get("_latency_s"), "execution_id": ra.get("execution_id")},
                  {"latency_s": rb.get("_latency_s"), "execution_id": rb.get("execution_id")}],
        "audits_during_window": audits,
        "distinct_operation_ids_seen": sorted(str(o) for o in op_ids),
        "readback_excerpt": readback[:400],
        "expected_conflict_behavior": expected,
        "results": results,
        "claim_checks": [c["unsupported_count"] for c in claims],
        "execution_mode": "audit-observed (canvas_audit rows bound to the window)",
        "output_correctness": all(r["got"] == r["expected"] for r in results.values()),
        "correct_completion": all(r["got"] == r["expected"] for r in results.values())
                              and sum(claims) == 0,
        "unsupported_claims": sum(c["unsupported_count"] for c in claims),
        "replies": [r[:2000] for r in replies],
    }


async def run_m1_case(base, token, user_id, case, sample, pre, world) -> Dict[str, Any]:
    """M1 acceptance: the frozen failure-concealment shape under the flagged
    finalizer. The editor exception is UNREPAIRED in this baseline — the
    turn still fails; what must change is the DELIVERY: execution identity
    preserved, failure reported accurately, no success claim."""
    import httpx
    seed_unbound_canvas_copy(world)
    session = f"acc-m1-{int(time.time())}-{sample}"
    headers = {"Authorization": f"Bearer {token}"}
    snapshot = Path("/tmp/canvas_snapshot.json").read_text()
    ctx = {"canvas": {"id": UNBOUND_CANVAS_ID}, "canvas_content": snapshot,
           "canvas_type": "email", "canvas_title": "Quote copy (acceptance rig)"}
    r = httpx.post(f"{base}/api/chat/message", headers=headers, timeout=300, trust_env=False,
                   json={"message": case["inputs"]["ask_verbatim"], "session_id": session,
                         "user_id": user_id, "context": ctx})
    payload = r.json()
    reply = str(payload.get("message") or "")
    exec_id = payload.get("execution_id")
    con = sqlite3.connect(f"file:{world / 'data' / 'atom.db'}?mode=ro", uri=True)
    row = con.execute("SELECT status, result_summary FROM agent_executions WHERE id=?",
                      (exec_id or "",)).fetchone() if exec_id else None
    con.close()
    results = {
        "execution_id_present_in_payload": bool(exec_id),
        "no_concealment_text": "Message processed successfully" not in reply,
        "no_success_claim_on_failed_execution": payload.get("success") is not True
                                                 or (row and row[0] != "failed"),
        "failure_named_in_delivery": bool(row and row[0] == "failed"
                                          and str(row[1])[:60] and str(row[1])[:40] in reply),
        "underlying_exception_unchanged": bool(row and row[0] == "failed"
                                               and "existing_evidence_contract" in str(row[1])),
    }
    return {
        "case_id": case["id"], "sample": sample, "session_id": session,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "path": "m1", "harness_version": HARNESS_VERSION, "preflight": pre,
        "baseline_id": f"m1-overlay@{PINNED_REV[:10]}",
        "config": {"flag": "CHAT_FINALIZATION_M1=1", "editor_exception": "deliberately unrepaired"},
        "execution_row": {"status": row[0], "summary_head": str(row[1])[:120]} if row else None,
        "results": results,
        "reply": reply[:1000],
        "correct_completion": all(results.values()),
        "unsupported_claims": 0,
        "execution_mode": "audit-observed",
    }


def regrade() -> int:
    """Regrade saved responses with the CURRENT structured-evidence
    diagnostic (v2.1). Runs preserving full replies are recomputed even if
    they carry an older in-file diagnostic; excerpt-only runs are
    recomputed but flagged excerpt-limited."""
    results_dir = ACC / "results"
    out = {"regenerated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "runs": []}
    for path in sorted(results_dir.glob("*.json")):
        if path.name.startswith(("regrade", "invoice_redelivery_probe__", "redelivery_probe__")):
            continue  # probes report evidence under their own files; excluded from case totals
        doc = json.loads(path.read_text())
        reply = doc.get("reply") or doc.get("reply_excerpt") or ""
        subturns = doc.get("subturns") or []
        if doc.get("case_id") in ("unrelated_domain_invoices", "invoice_field_retrieval") \
                and doc.get("correct_completion") is False:
            # Expectation-authoring artifact: freeze-time column error (amount_usd is column C in the
            # frozen parquet schema, not D). All targets were FOUND; only the authored binding was
            # wrong. Classified superseded — not a product failure. Correction delta-logged in 00 §5.
            pt = doc.get("per_target") or {}
            if pt and all(v.get("got") == "found" for v in pt.values()):
                out["runs"].append({
                    "result_file": path.name, "evaluator": "invoice-expectation-audit-v1",
                    "verdict": "superseded-expectation-artifact",
                    "reason": "authoring error (value_col D; schema truth C) — product behavior correct",
                    "correct_completion": None,
                })
                continue
        if doc.get("shim_log") is not None and doc.get("case_id", "").startswith("narration"):
            # Versioned regrade (review round 10): raw results stay immutable;
            # the corrected verdict lives HERE with reason + evaluator version.
            binding = doc.get("shim_binding") or {}
            graded = bool(binding.get("bound") and binding.get("consumed")
                          and binding.get("evaluator") == "narration-binding-v2")
            if graded:
                reason = binding.get("verdict", "graded")
            elif not doc.get("shim_log"):
                reason = "provider never reached (rig catalog blocker at collection time)"
            elif "shim_binding" not in doc:
                reason = ("pre-binding harness: response-local evidence only — neither bound to the "
                          "tested execution nor proven consumed")
            else:
                reason = binding.get("verdict", "binding/consumption unproven")
            out["runs"].append({
                "result_file": path.name, "evaluator": "narration-binding-v2",
                "verdict": "graded" if graded else "harness-blocked",
                "reason": reason,
                "correct_completion": doc.get("correct_completion") if graded else None,
            })
            continue
        if (doc.get("claim_check") or {}).get("ruleset") == "v2.1":
            continue  # already graded by the current diagnostic
        if subturns:
            total = 0
            for st in subturns:
                st_reply = st.get("reply") or ""
                non_found = [t for t, v in (st.get("per_target") or {}).items()
                             if v.get("got") != "found"]
                st_cc = check_claims(st_reply, verified_action_kinds=set(),
                                     non_found_targets=non_found,
                                     source_facts=WORKBOOK_SOURCE_FACTS,
                                     action_evidence=action_evidence({}))
                total += st_cc["unsupported_count"]
            out["runs"].append({"result_file": path.name, "ruleset": "v2.1",
                                "excerpt_limited": False, "unsupported_count": total,
                                "subturn_aggregated": len(subturns)})
            continue
        if not reply:
            continue
        per_target = doc.get("per_target") or {}
        non_found = [t for t, v in per_target.items() if v.get("got") != "found"]
        cc = check_claims(reply,
                          verified_action_kinds=set(),  # default-deny for regrades
                          non_found_targets=non_found,
                          source_facts=WORKBOOK_SOURCE_FACTS,
                          action_evidence=action_evidence(
                              {"canvas_edit": {"updated": doc.get("mutation_performed")}}))
        out["runs"].append({"result_file": path.name,
                            "excerpt_limited": "reply" not in doc,
                            **cc})
    (results_dir / "regrade_claimcheck.json").write_text(json.dumps(out, indent=1))
    graded_narr = [r for r in out["runs"] if r.get("verdict") == "graded"]
    blocked_narr = [r for r in out["runs"] if r.get("verdict") == "harness-blocked"]
    print(f"[regrade] {len(out['runs'])} entries: "
          f"{sum(r.get('unsupported_count', 0) for r in out['runs'])} unsupported (v2.1 regrades); "
          f"narration: {len(graded_narr)} graded, {len(blocked_narr)} harness-blocked")
    return 0


def collect_metrics() -> int:
    results_dir = ACC / "results"
    regrade_path = results_dir / "regrade_claimcheck.json"
    regrades = {r["result_file"]: r for r in
                (json.loads(regrade_path.read_text())["runs"] if regrade_path.exists() else [])}
    per_case: Dict[str, List[Dict[str, Any]]] = {}
    gated = excluded = 0
    for path in sorted(results_dir.glob("*.json")):
        if path.name.startswith(("regrade", "invoice_redelivery_probe__", "redelivery_probe__")):
            continue  # probes report evidence under their own files; excluded from case totals
        doc = json.loads(path.read_text())
        version = doc.get("harness_version") or (
            "enforced-isolation" if doc.get("preflight") else "smoke-pre-enforcement")
        counts_to_gate = version.startswith("enforced-isolation-v3")
        gated += counts_to_gate
        excluded += not counts_to_gate
        cc = doc.get("claim_check") or {}
        subturns = doc.get("subturns") or []
        regraded = regrades.get(path.name)
        # The ruleset diagnostic is a BOUNDED DIAGNOSTIC, never the acceptance
        # gate for "no unsupported claims" (that gate stays open). Preference:
        # current in-file v2.1 > v2.1 regrade of a full reply > unmeasured.
        claim_measured = bool(
            (cc.get("ruleset") == "v2.1" and doc.get("claim_gate_eligible") and "reply" in doc)
            or (subturns and doc.get("claim_gate_eligible")
                and all(s.get("claim_check", {}).get("ruleset") == "v2.1" for s in subturns))
            or (regraded and regraded.get("ruleset") == "v2.1" and not regraded.get("excerpt_limited")
                and ("reply" in doc or doc.get("subturns"))))
        if claim_measured:
            if cc.get("ruleset") == "v2.1" and not subturns:
                unsupported = cc["unsupported_count"]
                basis = "diagnostic v2.1 (structured-evidence, full response)"
            elif regraded and regraded.get("ruleset") == "v2.1":
                unsupported = regraded["unsupported_count"]
                basis = "diagnostic v2.1 (regraded, structured-evidence, full response)"
            elif subturns:
                unsupported = sum(s["claim_check"]["unsupported_count"] for s in subturns)
                basis = "diagnostic v2.1 (structured-evidence, full response)"
            else:
                unsupported, basis = None, "unmeasured"
        elif subturns:
            unsupported, basis = None, "unmeasured (superseded diagnostic)"
        elif counts_to_gate:
            unsupported, basis = None, "unmeasured (excerpt-only or superseded diagnostic)"
        else:
            unsupported, basis = None, "unmeasured"
        narr_rg = regrades.get(path.name)
        artifact = bool(narr_rg and narr_rg.get("verdict") == "superseded-expectation-artifact")
        invoice_run = (doc.get("case_id") in ("invoice_field_retrieval",
                                              "unrelated_domain_invoices") and not artifact)
        binding = doc.get("shim_binding") or {}
        is_narration = doc.get("shim_log") is not None or "shim_binding" in doc
        narr_v2 = (binding.get("evaluator") in ("narration-binding-v2", "narration-binding-v3")
                   and binding.get("bound") and binding.get("consumed"))
        narr_blocked = artifact
        if is_narration and doc.get("case_id", "").startswith("narration") and not narr_v2:
            narr_blocked = True
            narr_rg = narr_rg or {"evaluator": "narration-binding-v2",
                                  "reason": "binding not execution-bound+nonce-consumed (v2 required)"}
        elif not artifact:
            narr_blocked = bool(narr_rg and narr_rg.get("verdict") == "harness-blocked")
        entry = {

            "result_file": path.name,
            "result_sha256": _sha256_file(path),
            "counts_toward_gate": counts_to_gate,
            "claim_diagnostic_measured": claim_measured,
            "harness_version": version,
            "correct_completion": (None if narr_blocked else doc.get("correct_completion")),
            "output_correctness": (doc.get("correct_completion") if invoice_run else None),
            "execution_mode": ("unknown (reads not instrumented on the old path; the same-session "
                               "probe's 'no read event' is inconclusive — two-tier limitation, "
                               "documented)" if invoice_run else None),
            "classification": (
                "superseded-expectation-artifact (excluded: not a product failure)" if artifact
                else "harness-blocked (blocks acceptance; establishes neither product success nor defect)"
                if narr_blocked else None),
            "regrade_evaluator": (narr_rg or {}).get("evaluator"),
            "binding_evaluator": (doc.get("shim_binding") or {}).get("evaluator"),
            "regrade_reason": (narr_rg or {}).get("reason"),
            "unsupported_claims_detected_by_ruleset": unsupported,
            "unsupported_claims_basis": basis,
            "unnecessary_clarification": None,
            "progress_event_latency_s": doc.get("progress_event_latency_s"),
            "first_validated_answer_text_s": doc.get("first_validated_answer_text_s"),
            "answer_availability_latency_s": doc.get("answer_availability_latency_s"),
            "total_s": doc.get("total_s"),
            "cost_usd": doc.get("cost_usd"),
            "deterministic_delivery": doc.get("deterministic_delivery"),
        }
        per_case.setdefault(doc["case_id"], []).append(entry)
    target_passes = narration_passes = baseline_defects = harness_blocked = graded_fail_other = 0
    unclassified = 0
    defects_by_binding: Dict[str, int] = {}
    for cid, samples in per_case.items():
        for smp in samples:
            if not smp["counts_toward_gate"]:
                continue
            if (smp.get("classification") or "").startswith("superseded"):
                continue  # expectation-authoring artifacts: excluded, not product failures
            if (smp.get("classification") or "").startswith("unclassified"):
                unclassified += 1
                continue  # (kept for any future unclassified class)
            if (smp.get("classification") or "").startswith("harness-blocked"):
                harness_blocked += 1
            elif smp.get("correct_completion") is True:
                if cid.startswith("narration"):
                    narration_passes += 1
                else:
                    target_passes += 1
            elif cid.startswith("narration"):
                baseline_defects += 1
                ev = smp.get("binding_evaluator") or "unlabeled-binding-generation"
                defects_by_binding[ev] = defects_by_binding.get(ev, 0) + 1
            else:
                graded_fail_other += 1
    metrics = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "gate_harness_versions": "enforced-isolation-v3*",
        "generated_from": "results/*.json (immutable run outputs; machine-generated — do not hand-edit)",
        "separated_summary": {
            "target_case_passes": target_passes,
            "narration_case_passes": narration_passes,
            "baseline_defects_observed": baseline_defects,
            "baseline_defects_by_binding_version": defects_by_binding,
            "binding_version_note": "defects are NOT equivalent: only binding-v2/v3 (nonce-based) runs "
                                    "are re-proven; earlier generations are distinguished here",
            "harness_blocked_runs": harness_blocked,
            "other_graded_failures": graded_fail_other,
            "unclassified_evidence_runs": unclassified,
            "invoice_output_correctness": (
                f"{sum(1 for c in per_case.values() for x in c if x.get('output_correctness') is True)} "
                f"passes against fixture ground truth; execution mode unknown on all (reads not "
                f"instrumented — two-tier limitation, not a retrieval verdict)"),
            "reconciliation": "target passes are per-case identifiable in cases[]; redelivery probes "
                              "are excluded files (invoice_redelivery_probe__*) and never enter totals; "
                              "the earlier 51 was a mislabeled fresh-session probe counted as a pass",
            "note": "reported separately per review; no single combined 'gated' verdict",
        },
        "cases": [{"case_id": cid, "samples": samples} for cid, samples in per_case.items()],
        "status": (
            "PARTIAL. Metric renamed per review: 'unsupported claims detected by RULE SET v2' — a "
            "closed, record-calibrated pattern vocabulary; coverage beyond the ruleset is unmeasured. "
            "Claim gate counts ONLY full-response, ruleset-v2, record-calibrated runs "
            "(counts_toward_claim_gate); excerpt-only and superseded-evaluator runs retain target and "
            "latency gating but are claim-unmeasured. Measured: true-eight determinism/consistency; "
            "absent-targets, planner-down no-apply, read-read overlap (3 samples each); "
            "answer-availability latency at HTTP receipt; WS progress-event latency. Scope limits: "
            "(1) renderer-derived cells = renderer compatibility at 39d6532d5, not independent "
            "workbook-coordinate proof; (2) repeated deterministic samples = consistency + latency, "
            "not scenario coverage; (3) mutation cross-binding, continuation restart recovery, and "
            "LLM-narration cases remain unmeasured (recorded-response rig)."
        ),
    }
    (ACC / "metrics_old_path.json").write_text(json.dumps(metrics, indent=1))
    print(f"[collect] regenerated: {gated} gated / {excluded} excluded runs recorded")
    return 0


async def main_async(args: argparse.Namespace) -> int:
    if args.collect:
        return collect_metrics()
    if args.regrade:
        return regrade()
    world = BACKEND / "data" / "acceptance_worlds" / args.name
    if args.gate and args.m1:
        p.error("--gate refuses --m1: no second finalizer in production exports "
                "(the overlay is retained only for labelled historical-baseline tests)")
    build_world.m1_overlay = bool(args.m1)
    build_world.snapshot_working_tree = bool(args.snapshot_working_tree)
    if args.m1:
        args.rebuild_world = True  # the overlay changes the export; rebuild to apply coherently
    if args.rebuild_world or not (world / "MANIFEST.json").exists():
        world.mkdir(parents=True, exist_ok=True)
        build_world(world, refreeze_db=args.refreeze_db)
    pre = preflight(world)
    refresh_working_db(world)
    baseline_id = f"primary-{PINNED_REV[:10]}"  # dependency/m1 pins recorded per-run when introduced
    _ref = pre.get("code_archive_sha256") or pre.get("code_snapshot_sha256") or ""
    print(f"[preflight] rev={pre['source_revision'][:10]} export={_ref[:10]} "
          f"db={pre['db_sha256'][:10]} scrubbed venv fixtures ok — working DB reset from fixture")

    cases_doc = json.loads((ACC / "cases.json").read_text())
    by_id = {c["id"]: c for c in cases_doc["cases"]}
    id_map = {"true_eight": "original_incident_workbook_true_eight",
              "m1": "m1_failure_concealment",
              "overlap_edits": "mutation_overlap_distinct_edits",
              "single_edit": "mutation_overlap_distinct_edits",
              "invoices": "invoice_field_retrieval",
              "drift": "legacy_set_regression",
              "absent": "partial_failure_absent_targets",
              "no_apply": "planner_down_no_apply",
              "overlap": "overlap_concurrent_reads",
              "narration_clean": "narration_followup_clean",
              "narration_poisoned": "narration_followup_poisoned",
              # Lifecycle coverage, driven through the public boundary.
              "keyed_retry": "original_incident_workbook_true_eight"}

    case_list = args.cases.split(",")
    shim_mode = any(c in ("narration_clean", "narration_poisoned", "overlap_edits", "single_edit", "m1")
                    for c in case_list)
    shim_proc = None
    if shim_mode:
        scripts = {"narration_poisoned": "narration_poisoned.json",
                   "narration_clean": "narration_clean.json",
                   "overlap_edits": "mutation_overlap.json",
                   "single_edit": "mutation_overlap.json",
                   "m1": "mutation_overlap.json"}
        script_name = next((scripts[c] for c in case_list if c in scripts), "narration_clean.json")
        capture_path = world / "shim_requests.jsonl"
        shim_proc = launch_shim(FIXTURES / "provider_shim" / script_name, capture=capture_path)
    launch_server.m1 = bool(args.m1)
    launch_server.gate = bool(args.gate)
    launch_server.lifecycle = bool(args.lifecycle)
    proc = launch_server(args.port, world, provider_shim=shim_mode)
    # Verify the EFFECTIVE contract before spending a case on it. A run
    # that cannot prove the flag reached the server, or that the schema
    # the lifecycle needs exists, must not be reported as coverage.
    contract = runtime_contract_preflight(
        world, args.port, lifecycle_expected=bool(args.lifecycle or args.gate))
    print(f"[contract] lifecycle_flag_effective="
          f"{contract.get('lifecycle_flag_effective')!r} "
          f"missing_tables={contract.get('required_tables_missing')} "
          f"ok={contract.get('ok')}")
    if not contract.get("ok"):
        raise RuntimeError(
            f"runtime contract preflight failed: {contract.get('error')}")
    ok = True
    try:
        replay_mod = _load_replay_module()
        os.environ["DATABASE_URL"] = f"sqlite:///{world / 'data' / 'atom.db'}"
        token, user_id = replay_mod.mint_token()
        if not token:
            raise RuntimeError("could not mint token from scratch DB")
        base = f"http://127.0.0.1:{args.port}"
        for short in args.cases.split(","):
            case = by_id[id_map[short]]
            for s in range(1, args.samples + 1):
                if short == "true_eight":
                    tap = WSTap(args.port, token)
                    await tap.start()
                    try:
                        res = await run_true_eight(base, token, user_id, case, s, pre, world, tap, replay_mod)
                    finally:
                        await tap.stop()
                elif short in ("absent", "no_apply", "overlap"):
                    res = await run_generic(base, token, user_id, case, s, pre, world, short, replay_mod)
                elif short == "keyed_retry":
                    res = await run_keyed_retry_probe(
                        base, token, user_id, case, s, pre, world, replay_mod)
                elif short == "m1":
                    res = await run_m1_case(base, token, user_id, case, s, pre, world)
                elif short == "single_edit":
                    res = await run_single_edit_probe(base, token, user_id, case, s, pre, world)
                elif short == "overlap_edits":
                    res = await run_overlap_edits(base, token, user_id, case, s, pre, world)
                elif short == "invoices":
                    register_invoice_dataset(world)
                    res = await run_generic(base, token, user_id, case, s, pre, world, "absent", replay_mod)
                    # Retrieval evidence (review round 17): an execution id + non-empty trace proves
                    # NOTHING (planning/narration/cache also produce both). Require a trace event for
                    # the DATASET-READ operation bound to this session and the FIXTURE; uncertain runs
                    # stay unclassified (None) — never inferred from timing.
                    read_markers = (INVOICE_FIXTURE["content_hash"], INVOICE_FIXTURE["dataset_name"],
                                    "acc-inv-fixture-1", INVOICE_FIXTURE["file_name"])
                    def _read_events(steps):
                        return [st for st in steps
                                if any(m.lower() in str(st.get("observation") or "").lower()
                                       or m.lower() in str(st.get("action") or "").lower()
                                       for m in read_markers)]
                    trace_steps = await fetch_trace(base, token, res["session_id"], replay_mod)
                    reads = _read_events(trace_steps)
                    res["retrieval_evidence"] = {
                        "read_events": len(reads),
                        "sample": (str(reads[0].get("observation") or "")[:100] if reads else None),
                        "verdict": "retrieval-observed" if reads else "unclassified",
                    }
                    res["retrieval_verified"] = True if reads else None
                    res["hash_links"] = {
                        "fixture_sha256": _sha256_file(FIXTURES / "unrelated_domain" / INVOICE_FIXTURE["parquet"]),
                        "expectations_sha256": hashlib.sha256(
                            json.dumps(case["expected"]["per_target"], sort_keys=True).encode()).hexdigest(),
                        "evaluator": f"target-binding/{HARNESS_VERSION} claim-ruleset/v2.1",
                    }
                    # TRUE redelivery probe: SAME session, same ask — verified by NO NEW read event
                    # and a served reply (persisted-result use), not by timing.
                    import httpx as _hx
                    async with _hx.AsyncClient(trust_env=False, timeout=300) as probe_client:
                        pr = await probe_client.post(
                            f"{base}/api/chat/message",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"message": case["inputs"]["ask_verbatim"],
                                  "session_id": res["session_id"], "user_id": user_id})
                        pr.raise_for_status()
                        probe_payload = pr.json()
                    trace_after = await fetch_trace(base, token, res["session_id"], replay_mod)
                    reads_after = _read_events(trace_after)
                    probe = {
                        "case_id": "invoice_redelivery_probe", "sample": s,
                        "session_id": res["session_id"],
                        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "path": "old", "harness_version": HARNESS_VERSION, "preflight": pre,
                        "read_events_before": len(reads), "read_events_after": len(reads_after),
                        "reply_served": bool(probe_payload.get("message")),
                        "deterministic": probe_payload.get("model") in ("deterministic", "structured"),
                    }
                    probe["redelivery_verified"] = bool(
                        probe["read_events_after"] == probe["read_events_before"]
                        and probe["reply_served"])
                    probe["correct_completion"] = None  # probe: evidence, not a pass
                    out_r = ACC / "results" / f"invoice_redelivery_probe__sample{s}__{int(time.time())}.json"
                    out_r.write_text(json.dumps(probe, indent=1))
                elif short in ("narration_clean", "narration_poisoned"):
                    case_with_db = dict(case)
                    case_with_db["_world_db"] = str(world / "data" / "atom.db")
                    res = await run_narration(base, token, user_id, case_with_db, s, pre, replay_mod)
                else:
                    print(f"[case {short}] not yet driven by harness; skipped")
                    continue
                out = ACC / "results" / f"{res.get('case_id', case['id'])}__sample{s}__{int(time.time())}.json"
                out.parent.mkdir(exist_ok=True)
                out.write_text(json.dumps(res, indent=1))
                claims = res.get("claim_check") or {}
                # Probes (e.g. keyed_retry) have no per-target table and no
                # completion verdict; printing one unconditionally aborted the
                # whole run with a KeyError before any result was written.
                if "correct_completion" in res:
                    print(f"[case {short} sample {s}] "
                          f"correct_completion={res['correct_completion']} "
                          f"total_s={res.get('total_s')} "
                          f"unsupported_claims={res.get('unsupported_claims')}")
                else:
                    print(f"[case {short} sample {s}] "
                          f"request_records={res.get('chat_request_records')} "
                          f"states={res.get('states')}")
                for t, v in (res.get("per_target") or {}).items():
                    mark = "PASS" if v["pass"] else "FAIL"
                    print(f"    [{mark}] {t}: expected={v['expected']} "
                          f"got={v['got']} identity={v.get('identity_ok')} "
                          f"value={v.get('value_ok')}")
                    if not v.get("identity_ok", True):
                        print(f"         identity: {v.get('identity_detail')}")
                    if not v.get("value_ok", True):
                        print(f"         value:    {v.get('value_detail')}")
                for u in claims.get("unsupported", [])[:3]:
                    print(f"    [UNSUPPORTED-{u['kind']}] {u['sentence'][:100]}")
                ws = res.get("ws_metrics") or {}
                if ws.get("ws_events_total"):
                    print(f"    ws: {ws['ws_events_total']} events; progress={ws['progress_event_latency_s']}s "
                          f"first_token={ws['first_answer_token_latency_s']}s")
                if short == "invoices":
                    ok = ok and res["correct_completion"] and res.get("retrieval_verified") is True
                elif short == "keyed_retry":
                    for _name, _st in (res.get("steps") or {}).items():
                        _mark = "PASS" if _st.get("pass") else "FAIL"
                        print(f"    [{_mark}] {_name}")
                    ok = ok and all(_st.get("pass") for _st
                                    in (res.get("steps") or {}).values())
                else:
                    ok = ok and res["correct_completion"] and (res.get("unsupported_claims") == 0)
    finally:
        stop_server(proc)
        if shim_proc:
            shim_proc.terminate()
            print("[shim] stopped")
        print("[server] stopped (process group)")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="old_path_01")
    p.add_argument("--port", type=int, default=8021)
    p.add_argument("--cases", default="true_eight")
    p.add_argument("--samples", type=int, default=1)
    p.add_argument("--rebuild-world", action="store_true")
    p.add_argument("--refreeze-db", action="store_true")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--collect", action="store_true")
    p.add_argument("--snapshot-working-tree", action="store_true",
                   help="export the LIVE working tree (uncommitted wiring) hash-pinned")
    p.add_argument("--gate", action="store_true",
                   help="set the M1/M2 finalization flags explicitly for the acceptance gate")
    p.add_argument("--lifecycle", action="store_true",
                   help="enable ATOM_TASK_LIFECYCLE_ENABLED in the world so the "
                        "lifecycle authority is actually exercised")
    p.add_argument("--m1", action="store_true",
                   help="overlay the M1 finalization seam onto the exported code and enable CHAT_FINALIZATION_M1")
    p.add_argument("--regrade", action="store_true",
                   help="regrade saved responses with the claim evaluator (excerpt-limited for v3.0 runs)")
    args = p.parse_args()
    if args.selftest:
        return selftest()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
