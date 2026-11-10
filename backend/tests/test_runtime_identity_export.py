"""Runtime identity must describe the loaded source, never an ancestor checkout.

Failure-first: an immutable acceptance export nested beneath a canonical Git
repo currently reports the ancestor repo's HEAD/dirty state. These tests use
scratch temporary repositories and files only: no app DB, network, model or
provider.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from core.runtime_identity import capture_runtime_identity


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def _init_repo(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "identity-test@example.com")
    _git(root, "config", "user.name", "Identity Test")
    (root / "backend").mkdir(exist_ok=True)
    (root / "backend" / "base.py").write_text("BASE = True\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return _git(root, "rev-parse", "HEAD")


def _export_metadata(world: Path, *, snapshot: str | None,
                     archive: str | None = None,
                     write_code_manifest: bool = True) -> None:
    manifest = {}
    if snapshot is not None:
        manifest["code_snapshot_sha256"] = snapshot
    if archive is not None:
        manifest["code_archive_sha256"] = archive
    (world / "MANIFEST.json").write_text(json.dumps(manifest))
    if write_code_manifest:
        (world / "code_manifest.json").write_text(
            json.dumps({"backend/base.py": "deadbeef"}))


def test_nested_export_does_not_claim_ancestor_revision(tmp_path: Path) -> None:
    """The pre-repair failure: ancestor HEAD/dirty leaks into the export."""
    repo = tmp_path / "ancestor"
    ancestor_head = _init_repo(repo)
    (repo / "backend" / "base.py").write_text("DIRTY ANCESTOR\n")
    world = repo / "world-failure-first"
    (world / "backend").mkdir(parents=True)
    (world / "MANIFEST.json").write_text(json.dumps({
        "code_snapshot_sha256": hashlib.sha256(b"export").hexdigest(),
    }))
    (world / "code_manifest.json").write_text("{}")

    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.revision != ancestor_head
    assert not ident.source_id.startswith(ancestor_head[:12])


def test_native_clean_checkout_is_attributable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    head = _init_repo(repo)
    ident = capture_runtime_identity(cwd=str(repo / "backend"))
    assert ident.identity_kind == "git"
    assert ident.revision == head
    assert ident.dirty is False
    assert ident.source_id == head[:12]
    assert ident.repo_path == str(repo)
    assert ident.backend_path == str(repo / "backend")


def test_native_dirty_checkout_stays_attributable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    head = _init_repo(repo)
    (repo / "backend" / "base.py").write_text("BASE = False\n")
    ident = capture_runtime_identity(cwd=str(repo / "backend"))
    assert ident.identity_kind == "git"
    assert ident.revision == head
    assert ident.dirty is True
    assert ident.source_id.startswith(head[:12] + "-dirty.")
    assert ident.dirty_digest


def test_nested_export_never_reports_ancestor_revision(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    ancestor_head = _init_repo(repo)
    # Make the ancestor dirty so a wrong attribution is obvious.
    (repo / "backend" / "base.py").write_text("DIRTY ANCESTOR\n")
    (repo / "scratch-untracked.txt").write_text("not the export\n")

    world = repo / "acceptance_worlds" / "world-a"
    (world / "backend").mkdir(parents=True)
    export_sha = hashlib.sha256(b"snapshot export").hexdigest()
    _export_metadata(world, snapshot=export_sha)

    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "export"
    assert ident.revision == "unknown"
    assert ident.source_id == f"export-sha256:{export_sha[:12]}"
    assert ident.export_sha256 == export_sha
    assert ident.dirty is False
    assert ancestor_head[:12] not in ident.source_id
    assert ancestor_head[:12] not in ident.revision
    assert ident.repo_path == str(world)
    assert ident.backend_path == str(world / "backend")
    assert ident.ancestor_git_toplevel == str(repo)
    assert ident.error is None


def test_archive_export_twin_uses_archive_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-archive"
    (world / "backend").mkdir(parents=True)
    archive_sha = hashlib.sha256(b"archive export").hexdigest()
    _export_metadata(world, snapshot=None, archive=archive_sha)
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "export"
    assert ident.export_sha256 == archive_sha
    assert ident.source_id == f"export-sha256:{archive_sha[:12]}"


def test_symlinked_backend_farm_uses_world_export_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-farm"
    code_backend = world / "code" / "backend"
    code_backend.mkdir(parents=True)
    (world / "backend_root").symlink_to(code_backend, target_is_directory=True)
    export_sha = hashlib.sha256(b"farm export").hexdigest()
    _export_metadata(world, snapshot=export_sha)

    ident = capture_runtime_identity(cwd=str(world / "backend_root"))
    assert ident.identity_kind == "export"
    assert ident.export_sha256 == export_sha
    assert ident.repo_path == str(world)
    assert ident.backend_path == str(world / "backend_root")


def test_export_without_metadata_is_unknown_not_ancestor(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    ancestor_head = _init_repo(repo)
    world = repo / "world-no-metadata"
    (world / "backend").mkdir(parents=True)
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "unknown"
    assert ident.revision == "unknown"
    assert ident.source_id == "unknown"
    assert ident.dirty is False
    assert ident.error
    assert ancestor_head[:12] not in ident.source_id
    assert ident.ancestor_git_toplevel == str(repo)


def test_malformed_manifest_is_unknown(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-malformed"
    (world / "backend").mkdir(parents=True)
    (world / "MANIFEST.json").write_text("{not-json")
    (world / "code_manifest.json").write_text("{}")
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "unknown"
    assert ident.source_id == "unknown"
    assert ident.error


def test_conflicting_manifest_hashes_are_unknown(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-conflict"
    (world / "backend").mkdir(parents=True)
    _export_metadata(
        world,
        snapshot=hashlib.sha256(b"one").hexdigest(),
        archive=hashlib.sha256(b"two").hexdigest(),
    )
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "unknown"
    assert ident.source_id == "unknown"
    assert "conflict" in (ident.error or "").lower()


def test_missing_code_manifest_is_unknown(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-no-code-manifest"
    (world / "backend").mkdir(parents=True)
    _export_metadata(
        world,
        snapshot=hashlib.sha256(b"snapshot").hexdigest(),
        write_code_manifest=False,
    )
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "unknown"
    assert ident.source_id == "unknown"
    assert ident.error


def test_nogit_install_is_unknown_not_clean(tmp_path: Path) -> None:
    install = tmp_path / "install"
    (install / "backend").mkdir(parents=True)
    ident = capture_runtime_identity(cwd=str(install / "backend"))
    assert ident.identity_kind == "unknown"
    assert ident.revision == "unknown"
    assert ident.source_id == "unknown"
    assert ident.dirty is False
    assert ident.error


def test_run_isolated_print_names_the_actual_export(tmp_path: Path) -> None:
    from scripts.orchestration_acceptance.run_isolated import (
        PINNED_REV,
        _export_print_label,
    )

    snapshot = hashlib.sha256(b"snapshot").hexdigest()
    assert _export_print_label({
        "code_snapshot_sha256": snapshot,
    }) == f"snapshot-sha256:{snapshot[:12]}"
    assert _export_print_label({
        "code_archive_sha256": hashlib.sha256(b"archive").hexdigest(),
    }) == f"archive:{PINNED_REV[:10]}"
    assert "79b2a41032" not in _export_print_label({
        "code_snapshot_sha256": snapshot,
    })
