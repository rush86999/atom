"""Runtime identity must describe the loaded source, never an ancestor checkout.

Failure-first: an immutable acceptance export nested beneath a canonical Git
repo currently reports the ancestor repo's HEAD/dirty state. These tests use
scratch temporary repositories and files only: no app DB, network, model or
provider.
"""
from __future__ import annotations

import hashlib
import json
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


def _sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def _write_code(world: Path, rel: str, content: str, *, subdir: bool = True) -> Path:
    root = world / "code" if subdir else world
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _write_metadata(
    world: Path,
    code_manifest: dict,
    *,
    snapshot: str | None = None,
    archive: str | None = None,
    manifest_extra: dict | None = None,
    write_code_manifest: bool = True,
) -> None:
    manifest = {}
    if snapshot is not None:
        manifest["code_snapshot_sha256"] = snapshot
    if archive is not None:
        manifest["code_archive_sha256"] = archive
    if manifest_extra:
        manifest.update(manifest_extra)
    (world / "MANIFEST.json").write_text(json.dumps(manifest))
    if write_code_manifest:
        (world / "code_manifest.json").write_text(json.dumps(code_manifest))


def _snapshot_world(world: Path, *, subdir: bool = False) -> tuple[str, dict]:
    """One real file, its exact code_manifest entry, and an export hash."""
    code = "VALUE = 1\n"
    _write_code(world, "backend/app.py", code, subdir=subdir)
    code_manifest = {"backend/app.py": _sha(code)}
    _write_metadata(
        world, code_manifest,
        snapshot=_sha("snapshot-export"),  # content-addressed placeholder
    )
    return _sha(code), code_manifest


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


def test_nested_export_does_not_claim_ancestor_revision(tmp_path: Path) -> None:
    """The pre-repair failure: ancestor HEAD/dirty leaks into the export."""
    repo = tmp_path / "ancestor"
    ancestor_head = _init_repo(repo)
    (repo / "backend" / "base.py").write_text("DIRTY ANCESTOR\n")
    world = repo / "world-failure-first"
    _snapshot_world(world, subdir=False)

    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.revision != ancestor_head
    assert not ident.source_id.startswith(ancestor_head[:12])


def test_nested_export_never_reports_ancestor_revision(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    ancestor_head = _init_repo(repo)
    (repo / "backend" / "base.py").write_text("DIRTY ANCESTOR\n")
    (repo / "scratch-untracked.txt").write_text("not the export\n")

    world = repo / "acceptance_worlds" / "world-a"
    _snapshot_world(world, subdir=False)

    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "export"
    assert ident.revision == "unknown"
    assert ident.source_id == f"export-sha256:{ident.export_sha256[:12]}"
    assert ident.export_verified_files == 1
    assert ident.export_loaded_files == 1
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
    code = "ARCHIVE = True\n"
    _write_code(world, "backend/app.py", code, subdir=False)
    code_manifest = {"backend/app.py": _sha(code)}
    _write_metadata(world, code_manifest, archive=_sha("archive-export"))
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "export"
    assert ident.export_sha256 == _sha("archive-export")
    assert ident.source_id == f"export-sha256:{ident.export_sha256[:12]}"


def test_symlinked_backend_farm_uses_world_export_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-farm"
    code = "FARM = True\n"
    _write_code(world, "backend/app.py", code, subdir=True)
    (world / "backend_root").symlink_to(
        world / "code" / "backend", target_is_directory=True)
    code_manifest = {"backend/app.py": _sha(code)}
    _write_metadata(world, code_manifest, snapshot=_sha("farm-export"))

    ident = capture_runtime_identity(cwd=str(world / "backend_root"))
    assert ident.identity_kind == "export"
    assert ident.export_verified_files == 1
    assert ident.export_loaded_files == 1
    assert ident.repo_path == str(world)
    assert ident.backend_path == str(world / "backend_root")


def test_runtime_artifacts_do_not_break_unchanged_export(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-runtime-artifacts"
    app = "VALUE = 1\n"
    _write_code(world, "backend/app.py", app, subdir=True)
    _write_code(world, "backend/data/result.json", "{}\n", subdir=True)
    (world / "backend_root").symlink_to(
        world / "code" / "backend", target_is_directory=True)
    (world / "code" / "backend" / ".env").write_text("SHADOW=1\n")
    (world / "code" / "backend" / "workflow_versions.db").write_text("runtime")
    code_manifest = {
        "backend/app.py": _sha(app),
        "backend/data/result.json": _sha("{}\n"),
    }
    _write_metadata(world, code_manifest, snapshot=_sha("artifacts-export"))

    ident = capture_runtime_identity(cwd=str(world / "backend_root"))
    assert ident.identity_kind == "export"
    assert ident.export_verified_files == 2
    assert ident.export_loaded_files == 1
    assert ident.error is None


def test_export_drift_is_rejected_not_certified(tmp_path: Path) -> None:
    """Root drift probe: change exported bytes, keep the original manifest."""
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-drift"
    code = "VALUE = 1\n"
    _write_code(world, "backend/app.py", code, subdir=True)
    (world / "backend_root").symlink_to(
        world / "code" / "backend", target_is_directory=True)
    code_manifest = {"backend/app.py": _sha(code)}
    _write_metadata(world, code_manifest, snapshot=_sha("drift-export"))

    first = capture_runtime_identity(cwd=str(world / "backend_root"))
    assert first.identity_kind == "export"
    assert first.error is None
    first_source_id = first.source_id

    (world / "code" / "backend" / "app.py").write_text("VALUE = 2\n")
    second = capture_runtime_identity(cwd=str(world / "backend_root"))
    assert second.identity_kind == "unknown"
    assert second.source_id == "unknown"
    assert second.error
    assert "changed" in second.error.lower()
    assert second.source_id != first_source_id


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
    _write_metadata(
        world, {"backend/base.py": _sha("base")},
        snapshot=_sha("one"), archive=_sha("two"),
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
    _write_metadata(
        world, {"backend/base.py": _sha("base")},
        snapshot=_sha("snapshot"), write_code_manifest=False,
    )
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "unknown"
    assert ident.source_id == "unknown"
    assert ident.error


def test_manifest_path_escape_is_unknown(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-path-escape"
    (world / "backend").mkdir(parents=True)
    _write_metadata(
        world, {"backend/../../outside.py": _sha("outside")},
        snapshot=_sha("escape"),
    )
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "unknown"
    assert ident.source_id == "unknown"
    assert "unsafe path" in (ident.error or "")


def test_invalid_manifest_entry_is_unknown(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-invalid-entry"
    _write_code(world, "backend/app.py", "VALUE = 1\n", subdir=False)
    _write_metadata(
        world, {"backend/app.py": "not-a-sha256"},
        snapshot=_sha("invalid"),
    )
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "unknown"
    assert ident.source_id == "unknown"
    assert "invalid hash" in (ident.error or "")


def test_missing_manifest_file_is_unknown(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-missing-file"
    (world / "backend").mkdir(parents=True)
    _write_metadata(
        world, {"backend/missing.py": _sha("missing")},
        snapshot=_sha("missing-export"),
    )
    ident = capture_runtime_identity(cwd=str(world / "backend"))
    assert ident.identity_kind == "unknown"
    assert ident.source_id == "unknown"
    assert "missing" in (ident.error or "").lower()


def test_extra_loaded_file_is_unknown(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-extra-loaded"
    code = "VALUE = 1\n"
    _write_code(world, "backend/app.py", code, subdir=True)
    (world / "backend_root").symlink_to(
        world / "code" / "backend", target_is_directory=True)
    (world / "code" / "backend" / "extra.py").write_text("EXTRA = True\n")
    _write_metadata(
        world, {"backend/app.py": _sha(code)},
        snapshot=_sha("extra-export"),
    )
    ident = capture_runtime_identity(cwd=str(world / "backend_root"))
    assert ident.identity_kind == "unknown"
    assert ident.source_id == "unknown"
    assert "extra" in (ident.error or "").lower()


def test_unrelated_farm_cannot_certify_export(tmp_path: Path) -> None:
    repo = tmp_path / "ancestor"
    _init_repo(repo)
    world = repo / "world-unrelated-farm"
    code = "VALUE = 1\n"
    _write_code(world, "backend/app.py", code, subdir=True)
    other = repo / "unrelated" / "backend"
    other.mkdir(parents=True)
    (other / "app.py").write_text(code)  # same bytes, different tree
    (world / "backend_root").symlink_to(other, target_is_directory=True)
    _write_metadata(
        world, {"backend/app.py": _sha(code)},
        snapshot=_sha("unrelated-export"),
    )
    ident = capture_runtime_identity(cwd=str(world / "backend_root"))
    assert ident.identity_kind == "unknown"
    assert ident.source_id == "unknown"
    assert (
        "does not point" in (ident.error or "")
        or "escapes" in (ident.error or "")
    )


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
