"""Focused identity/provenance tests for the prepared browser driver.

Every valid source-binding case uses a real temporary Git repository and real
``git ls-tree`` / ``git cat-file`` bytes. Fake manifest hashes are only used in
negative tests and can never certify provenance by being self-consistent.
"""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DRIVER_PATH = REPO / "scripts" / "acceptance" / "browser_agent_job_wait.py"


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "browser_agent_job_wait_identity", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load_driver()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _make_git_repo(tmp_path: Path):
    repo = tmp_path / "source"
    repo.mkdir()
    files = {
        "backend/api/agent_routes.py": b"# actual tracked source\n",
        "backend/core/personal_scope.py": b"# actual personal scope\n",
    }
    for rel, data in files.items():
        _write(repo / rel, data)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "backend"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=test@example.com",
         "-c", "user.name=Test", "commit", "-q", "-m", "fixture"],
        check=True)
    revision = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    return repo, revision, files


def _world_binding_kwargs(
    tmp_path: Path,
    repo: Path,
    revision: str,
    source_files: dict[str, bytes],
    *,
    extra_files: dict[str, bytes] | None = None,
    manifest_overrides: dict[str, str] | None = None,
):
    world = tmp_path / "world"
    (world / "backend_root").mkdir(parents=True)
    export_root = world / "code"
    for rel, data in source_files.items():
        _write(export_root / rel, data)
    for rel, data in (extra_files or {}).items():
        _write(export_root / rel, data)
    actual_hashes = {
        path.relative_to(export_root).as_posix(): _sha256(path.read_bytes())
        for path in export_root.rglob("*") if path.is_file()
    }
    code_manifest = dict(actual_hashes)
    export_tree = dict(actual_hashes)
    for rel, digest in (manifest_overrides or {}).items():
        code_manifest[rel] = digest
        export_tree[rel] = digest
    return {
        "frozen_source_sha": revision,
        "source_head": revision,
        "preflight": {"source_revision": revision},
        "manifest": {"code_snapshot_sha256": "d" * 64},
        "code_manifest": code_manifest,
        "export_tree": export_tree,
        "health_identity": {
            "cwd": str(world / "backend_root"),
            "source_id": "unknown",
        },
        "descriptor": {"export_path": str(world / "backend_root")},
        "world": world,
        "git_repo": repo,
    }


# ---------------------------------------------------------------------------
# frontend cwd fail-open
# ---------------------------------------------------------------------------
def test_frontend_cwd_none_is_not_certified(driver, tmp_path):
    expected = tmp_path / "world" / "frontend_snapshot"
    assert driver._frontend_cwd_matches(None, expected) is False


def test_frontend_cwd_wrong_tree_is_not_certified(driver, tmp_path):
    expected = tmp_path / "world" / "frontend_snapshot"
    assert driver._frontend_cwd_matches(str(tmp_path / "frontend-nextjs"),
                                        expected) is False


def test_frontend_cwd_exact_isolated_path_is_certified(driver, tmp_path):
    expected = tmp_path / "world" / "frontend_snapshot"
    assert driver._frontend_cwd_matches(str(expected), expected) is True


# ---------------------------------------------------------------------------
# actual Git blob provenance
# ---------------------------------------------------------------------------
def test_valid_actual_git_blob_twin_is_certified(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, files)
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is True
    assert binding["git_blob_files_checked"] == 2
    assert binding["expected_commit_file_count"] == 2
    assert binding["manifest_source_revision_present"] is False
    assert binding["git_blob_mismatches"] == []


def test_consistent_but_wrong_export_does_not_certify(driver, tmp_path):
    repo, revision, _files = _make_git_repo(tmp_path)
    wrong = {
        "backend/api/agent_routes.py": b"# not the frozen file\n",
        "backend/core/personal_scope.py": b"# not the frozen file\n",
    }
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, wrong)
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert "backend/api/agent_routes.py" in binding["git_blob_mismatches"]


def test_original_self_consistent_fake_manifest_negative(driver, tmp_path):
    """Preserve the external root negative: matching fake maps are insufficient."""
    world = tmp_path / "world"
    (world / "backend_root").mkdir(parents=True)
    revision = driver._git("rev-parse", "HEAD") or "f" * 40
    wrong = {"backend/api/agent_routes.py": "0" * 64}
    binding = driver._backend_source_binding(
        frozen_source_sha=revision,
        source_head=revision,
        preflight={"source_revision": revision},
        manifest={"code_snapshot_sha256": "d" * 64},
        code_manifest=wrong,
        export_tree=dict(wrong),
        health_identity={
            "cwd": str(world / "backend_root"),
            "source_id": "unknown",
        },
        descriptor={"export_path": str(world / "backend_root")},
        world=world,
    )
    assert binding["ok"] is False
    assert binding["missing_exported_files"]


def test_missing_exported_tracked_file_is_rejected(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    only_one = {"backend/api/agent_routes.py": files[
        "backend/api/agent_routes.py"]}
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, only_one)
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert "backend/core/personal_scope.py" in binding["missing_exported_files"]


def test_tampered_export_byte_is_rejected(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, files)
    _write(kwargs["world"] / "code" / "backend/api/agent_routes.py",
           b"# tampered\n")
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert "backend/api/agent_routes.py" in binding["git_blob_mismatches"]


def test_wrong_consistent_manifest_hashes_are_rejected(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(
        tmp_path, repo, revision, files,
        manifest_overrides={
            "backend/api/agent_routes.py": "0" * 64,
            "backend/core/personal_scope.py": "0" * 64,
        })
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["code_manifest_mismatches"]
    assert binding["export_tree_mismatches"]


def test_unexpected_backend_file_is_rejected(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(
        tmp_path, repo, revision, files,
        extra_files={"backend/api/rogue.py": b"# not in frozen commit\n"})
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert "backend/api/rogue.py" in binding["unexpected_exported_files"]


def test_launcher_generated_backend_file_is_accounted_for(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(
        tmp_path, repo, revision, files,
        extra_files={"backend/logs/runner.log": b"launcher output\n"})
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is True
    assert "backend/logs/runner.log" in (
        binding["launcher_generated_exported_files"])


def test_missing_frozen_commit_is_rejected(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, files)
    kwargs["frozen_source_sha"] = "0" * 40
    kwargs["preflight"] = {"source_revision": "0" * 40}
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["git_commit_resolved"] is False


def test_wrong_health_cwd_is_rejected(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, files)
    kwargs["health_identity"] = {
        "cwd": str(tmp_path / "frontend-nextjs"), "source_id": "unknown"}
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["health_cwd_exact"] is False


def test_wrong_descriptor_export_is_rejected(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, files)
    kwargs["descriptor"] = {
        "export_path": str(tmp_path / "frontend-nextjs")}
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["descriptor_export_exact"] is False


def test_conflicting_manifest_source_revision_is_rejected(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, files)
    kwargs["manifest"] = {
        "code_snapshot_sha256": "d" * 64,
        "source_revision": "0" * 40,
    }
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["manifest_source_revision_not_conflicting"] is False


def test_preflight_source_mismatch_is_rejected(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, files)
    kwargs["preflight"] = {"source_revision": "0" * 40}
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["preflight_source_matches_frozen"] is False


def test_matching_manifest_source_revision_is_accepted(driver, tmp_path):
    repo, revision, files = _make_git_repo(tmp_path)
    kwargs = _world_binding_kwargs(tmp_path, repo, revision, files)
    kwargs["manifest"] = {
        "code_snapshot_sha256": "d" * 64,
        "source_revision": revision,
    }
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is True
    assert binding["manifest_source_revision_present"] is True
