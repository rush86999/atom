"""Focused identity tests for the prepared browser acceptance driver.

These load the real driver module (no world/server/browser/provider) and
exercise the pure certification helpers. They deliberately include the
fail-open shapes root found: an unobserved frontend cwd and source
certification that relies on absent/unobserved values.
"""
from __future__ import annotations

import importlib.util
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


def _binding_kwargs(tmp_path: Path):
    world = tmp_path / "world"
    (world / "backend_root").mkdir(parents=True)
    code_manifest = {
        "backend/api/agent_routes.py": "a" * 64,
        "backend/core/personal_scope.py": "b" * 64,
        "backend/scripts/orchestration_acceptance/run_isolated.py": "c" * 64,
    }
    return {
        "frozen_source_sha": "f" * 40,
        "source_head": "f" * 40,
        "preflight": {"source_revision": "f" * 40},
        # The real world MANIFEST has no source_revision; certification must
        # come from the frozen source + exported file hashes.
        "manifest": {"code_snapshot_sha256": "d" * 64},
        "code_manifest": code_manifest,
        "export_tree": dict(code_manifest),
        "health_identity": {
            "cwd": str(world / "backend_root"),
            "source_id": "unknown",
        },
        "descriptor": {"export_path": str(world / "backend_root")},
        "world": world,
    }


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


def test_backend_binding_accepts_export_hashes_without_manifest_source_revision(
        driver, tmp_path):
    binding = driver._backend_source_binding(**_binding_kwargs(tmp_path))
    assert binding["ok"] is True
    assert binding["manifest_source_revision_present"] is False
    assert binding["manifest_source_revision"] is None
    assert binding["backend_export"]["file_count"] == 3
    assert binding["backend_export"]["sha256"]
    assert binding["health_source_id_is_unknown"] is True


def test_backend_binding_accepts_matching_manifest_source_revision(
        driver, tmp_path):
    kwargs = _binding_kwargs(tmp_path)
    kwargs["manifest"] = {
        "code_snapshot_sha256": "d" * 64,
        "source_revision": "f" * 40,
    }
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is True
    assert binding["manifest_source_revision_present"] is True


def test_backend_binding_rejects_missing_frozen_source(driver, tmp_path):
    kwargs = _binding_kwargs(tmp_path)
    kwargs["frozen_source_sha"] = ""
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["frozen_source_sha_present"] is False


def test_backend_binding_rejects_missing_export_hash(driver, tmp_path):
    kwargs = _binding_kwargs(tmp_path)
    kwargs["manifest"] = {}
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["manifest_export_hash_present"] is False


def test_backend_binding_rejects_export_tree_drift(driver, tmp_path):
    kwargs = _binding_kwargs(tmp_path)
    kwargs["export_tree"] = {"backend/api/agent_routes.py": "0" * 64}
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["export_tree_matches_code_manifest"] is False


def test_backend_binding_rejects_unobserved_health_cwd(driver, tmp_path):
    kwargs = _binding_kwargs(tmp_path)
    kwargs["health_identity"] = {"cwd": None, "source_id": "unknown"}
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["health_cwd_exact"] is False


def test_backend_binding_rejects_wrong_descriptor_export(driver, tmp_path):
    kwargs = _binding_kwargs(tmp_path)
    kwargs["descriptor"] = {"export_path": str(tmp_path / "frontend-nextjs")}
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["descriptor_export_exact"] is False


def test_backend_binding_rejects_conflicting_manifest_source_revision(
        driver, tmp_path):
    kwargs = _binding_kwargs(tmp_path)
    kwargs["manifest"] = {
        "code_snapshot_sha256": "d" * 64,
        "source_revision": "0" * 40,
    }
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["manifest_source_revision_not_conflicting"] is False


def test_backend_binding_rejects_preflight_source_mismatch(driver, tmp_path):
    kwargs = _binding_kwargs(tmp_path)
    kwargs["preflight"] = {"source_revision": "0" * 40}
    binding = driver._backend_source_binding(**kwargs)
    assert binding["ok"] is False
    assert binding["preflight_source_matches_frozen"] is False
