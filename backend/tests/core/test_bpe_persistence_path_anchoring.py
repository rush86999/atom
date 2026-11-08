"""Read-only path-resolution controls for the BPE workspace store.

The default store must resolve to the same absolute directory whether the
process starts at the repo root or at ``backend/``. These controls only
instantiate the store and resolve paths; they never save, load, migrate or
delete workspace data. Root owns execution.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import core.bpe.persistence as persistence
from core.bpe.persistence import BPEWorkspaceStore
from core.settings_catalog import find_spec


BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

_PROBE = (
    "from core.bpe.persistence import BPEWorkspaceStore; "
    "print(BPEWorkspaceStore().data_dir)"
)


def _probe_store_dir(cwd: Path, data_dir=None) -> Path:
    """Resolve an omitted store directory in a clean root/backend launch."""
    env = os.environ.copy()
    env.pop("ATOM_BPE_DATA_DIR", None)
    if data_dir is not None:
        env["ATOM_BPE_DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = str(BACKEND_DIR)
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    return Path(completed.stdout.strip())


pytestmark = pytest.mark.unit


class TestDefaultPathAnchoring:
    def test_default_store_is_identical_from_repo_root_and_backend(self):
        expected = BACKEND_DIR / "data" / "bpe_workspaces"

        assert _probe_store_dir(REPO_ROOT) == expected
        assert _probe_store_dir(BACKEND_DIR) == expected

    def test_configured_catalog_default_matches_canonical_default(self):
        spec = find_spec("ATOM_BPE_DATA_DIR")

        assert spec is not None
        assert spec.default == persistence.DEFAULT_DATA_DIR
        assert persistence._resolve_data_dir(spec.default) == (
            BACKEND_DIR / "data" / "bpe_workspaces"
        )

    def test_default_helper_reads_relative_override(self, monkeypatch):
        monkeypatch.setenv("ATOM_BPE_DATA_DIR", "data/configured")

        assert persistence._default_data_dir() == (
            BACKEND_DIR / "data" / "configured"
        )


class TestOverrideAnchoring:
    def test_absolute_override_is_preserved_from_either_cwd(self, tmp_path):
        custom = tmp_path / "absolute_bpe_store"

        assert _probe_store_dir(REPO_ROOT, custom) == custom
        assert _probe_store_dir(BACKEND_DIR, custom) == custom

    def test_relative_override_is_backend_relative(self):
        expected = BACKEND_DIR / "data" / "custom_bpe"

        assert _probe_store_dir(REPO_ROOT, "data/custom_bpe") == expected
        assert _probe_store_dir(BACKEND_DIR, "data/custom_bpe") == expected

    def test_legacy_documented_default_spelling_remains_compatible(self):
        expected = BACKEND_DIR / "data" / "bpe_workspaces"

        assert _probe_store_dir(REPO_ROOT, "backend/data/bpe_workspaces") == expected
        assert _probe_store_dir(BACKEND_DIR, "backend/data/bpe_workspaces") == expected

    def test_explicit_data_dir_is_used_as_supplied(self, tmp_path):
        relative = Path("intentionally_supplied_bpe_store")

        assert BPEWorkspaceStore(data_dir=tmp_path).data_dir == tmp_path
        assert BPEWorkspaceStore(data_dir=relative).data_dir == relative
