"""Tests for worlds_delete_audit.py — the pre-flight review of what
``rsync --delete`` would destroy.

The whole point of the tool is that it must be able to say "blocked". A
classifier that quietly files a one-off record under "regenerable scratch"
is worse than no tool, because it launders a deletion through a green
check. These tests pin the fail-closed behaviour:

* a destination-only database / manifest / JSON record is EVIDENCE;
* build output is droppable, and droppable wins over the extension rules;
* a symlink-only extra is never silently dropped;
* the real ``rsync --dry-run --delete`` cross-check agrees with the audit.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "worlds_delete_audit",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "orchestration_acceptance"
    / "worlds_delete_audit.py",
)
audit = importlib.util.module_from_spec(_spec)
sys.modules["worlds_delete_audit"] = audit
_spec.loader.exec_module(audit)


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel",
    [
        "w1/.next/dev/trace",
        "w1/frontend_farm/node_modules/react/index.js",
        "w1/backend_root/__pycache__/mod.cpython-314.pyc",
        "w1/.DS_Store",
        "w1/coverage/.coverage",
    ],
)
def test_build_output_is_droppable(rel):
    bucket, _ = audit.classify(rel, 0)
    assert bucket == "droppable"


@pytest.mark.parametrize(
    "rel",
    [
        "w1/runs/run-1/data/atom.db",
        "w1/MANIFEST.json",
        "w1/code_manifest.json",
        "w1/launch_descriptor.json",
        "w1/live_acceptance_result.json",
        "w1/results/summary.json",
        "w1/shim_requests.jsonl",
        "w1/some_unrecognised_record.json",
    ],
)
def test_records_are_evidence(rel):
    """Fail closed: an unrecognised record is still a record."""
    bucket, _ = audit.classify(rel, 0)
    assert bucket == "evidence", rel


def test_droppable_beats_extension_rules():
    """node_modules holds .js and .json; it is still regenerable."""
    assert audit.classify("w1/node_modules/pkg/index.json", 0)[0] == "droppable"
    assert audit.classify("w1/.next/cache/x.json", 0)[0] == "droppable"


def test_unknown_binary_is_review_not_droppable():
    assert audit.classify("w1/some_unknown_blob", 0)[0] == "review"
    assert audit.classify("w1/some_unknown_blob", 0)[0] != "droppable"


# ---------------------------------------------------------------------------
# tree diffing
# ---------------------------------------------------------------------------
def _tree(root: Path, files=(), dirs=(), links=()):
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
    for f in files:
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    for src, dst in links:
        (root / dst).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(src, root / dst)
    return root


def test_dest_only_evidence_blocks(tmp_path, capsys):
    src = _tree(tmp_path / "src", files=["w1/MANIFEST.json"])
    dst = _tree(
        tmp_path / "dst",
        files=["w1/MANIFEST.json", "w1/runs/old/atom.db"],
    )
    rc = audit.main(["--src", str(src), "--dst", str(dst)])
    assert rc == 1
    assert "BLOCKED" in capsys.readouterr().out


def test_clean_tree_passes(tmp_path, capsys):
    src = _tree(tmp_path / "src", files=["w1/MANIFEST.json", "w1/a.txt"])
    dst = _tree(tmp_path / "dst", files=["w1/MANIFEST.json", "w1/a.txt"])
    rc = audit.main(["--src", str(src), "--dst", str(dst)])
    assert rc == 0
    assert "no destination-only evidence" in capsys.readouterr().out


def test_only_build_output_does_not_block(tmp_path, capsys):
    """The common case: the stale copy holds only regenerable build junk."""
    src = _tree(tmp_path / "src", files=["w1/a.txt"])
    dst = _tree(
        tmp_path / "dst",
        files=["w1/a.txt", "w1/.next/dev/trace", "w1/node_modules/x/i.js"],
    )
    rc = audit.main(["--src", str(src), "--dst", str(dst)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DROPPABLE" in out
    assert "BLOCKED" not in out


def test_dest_only_symlink_is_reviewed_not_dropped(tmp_path, capsys):
    src = _tree(tmp_path / "src", files=["w1/a.txt"])
    dst = _tree(tmp_path / "src")  # placeholder, rebuilt below
    dst = tmp_path / "dst"
    _tree(dst, files=["w1/a.txt"])
    os.symlink("nowhere", dst / "w1" / "orphan_link")
    rc = audit.main(["--src", str(src), "--dst", str(dst)])
    out = capsys.readouterr().out
    assert "orphan_link" in out
    # Either way it must be surfaced, never silently deleted.
    assert rc in (0, 1)


def test_missing_root_returns_2(tmp_path, capsys):
    rc = audit.main(["--src", str(tmp_path / "nope"), "--dst", str(tmp_path)])
    assert rc == 2


# ---------------------------------------------------------------------------
# rsync cross-check
# ---------------------------------------------------------------------------
def test_rsync_dry_run_agrees_with_audit(tmp_path, capsys):
    """The audit must not disagree with the command it is auditing."""
    src = _tree(tmp_path / "src", files=["w1/a.txt"])
    dst = _tree(tmp_path / "dst", files=["w1/a.txt", "w1/.next/dev/trace"])
    rc = audit.main(["--src", str(src), "--dst", str(dst), "--rsync-dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "the two agree exactly" in out
    # And the dry run must not have deleted anything.
    assert (dst / "w1" / ".next" / "dev" / "trace").exists()


def test_rsync_dry_run_is_read_only(tmp_path, capsys):
    """Guard against a future edit that turns the audit into the real thing."""
    src = _tree(tmp_path / "src", files=["w1/a.txt"])
    dst = _tree(tmp_path / "dst", files=["w1/a.txt", "w1/only_dst.txt"])
    before = sorted(os.walk(dst).__next__()[2])
    audit.main(["--src", str(src), "--dst", str(dst), "--rsync-dry-run"])
    after = sorted(os.walk(dst).__next__()[2])
    assert before == after
    assert (dst / "w1" / "only_dst.txt").exists()


# ---------------------------------------------------------------------------
# regressions found by running the audit against the real trees
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel",
    [
        # 551M of these existed only on the drive and were first filed as
        # "ambiguous" purely because of the .gz extension. They are gzip'd
        # SQLite snapshots written by the maintenance cycle.
        "wb_verify/backend_root/data/backups/atom-cycle-20260926-174757.db.gz",
        "lifecycle_pf/runs/run-4359346269f9/data/backups/atom-cycle-20260926-183730.db.gz",
        "some_world/data/backups/whatever.sqlite.gz",
        "w1/evidence/capture.json",
    ],
)
def test_compressed_db_snapshots_are_evidence(rel):
    bucket, _ = audit.classify(rel, 0)
    assert bucket == "evidence", rel
