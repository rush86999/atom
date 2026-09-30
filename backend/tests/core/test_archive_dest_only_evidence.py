"""Tests for archive_dest_only_evidence.py.

The tool's only job is to make `rsync --delete` safe to run. That makes its
failure modes unusually expensive:

* archiving nothing when evidence exists  -> evidence destroyed silently
* archiving into a path rsync also writes  -> destroyed anyway, but later
* reporting success without verifying    -> destroyed, and falsely blessed
* clobbering an existing archive          -> the previous verified copy is lost

Each of those is pinned below. Verification is deliberately tested against a
CORRUPTED archive, because a test that only ever sees good input would pass
against a verifier that does nothing.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "archive_dest_only_evidence",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "orchestration_acceptance"
    / "archive_dest_only_evidence.py",
)
arch = importlib.util.module_from_spec(_spec)
sys.modules["archive_dest_only_evidence"] = arch
_spec.loader.exec_module(arch)


def _build(tmp_path: Path, dest_only=(), shared=("w1/MANIFEST.json",)):
    """src (authoritative) + dst (stale copy)."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    for root in (src, dst):
        for rel in shared:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('{"rev":"abc"}')
    for rel in dest_only:
        p = dst / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"SNAPSHOT-BYTES" * 64)
    return src, dst


# ---------------------------------------------------------------------------
# archiving
# ---------------------------------------------------------------------------
def test_archives_dest_only_evidence(tmp_path, capsys):
    src, dst = _build(tmp_path, ["w1/data/backups/atom-cycle-1.db.gz"])
    rc = arch.main(
        [
            "--src", str(src), "--dst", str(dst),
            "--archive-root", str(tmp_path / "arch"),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "archived and verified" in out
    root = next((tmp_path / "arch").iterdir())
    payload = root / "payload" / "w1/data/backups/atom-cycle-1.db.gz"
    assert payload.is_file()
    assert payload.read_bytes() == b"SNAPSHOT-BYTES" * 64


def test_manifest_records_path_size_and_hash(tmp_path, capsys):
    src, dst = _build(tmp_path, ["w1/data/backups/atom-cycle-1.db.gz"])
    arch.main(
        ["--src", str(src), "--dst", str(dst), "--archive-root", str(tmp_path / "arch")]
    )
    root = next((tmp_path / "arch").iterdir())
    doc = json.loads((root / "MANIFEST.json").read_text())
    item = doc["items"][0]
    assert item["relative_path"] == "w1/data/backups/atom-cycle-1.db.gz"
    assert item["bytes"] == len(b"SNAPSHOT-BYTES" * 64)
    assert len(item["sha256"]) == 64
    assert item["sha256"] == item["archived_sha256"]
    assert Path(item["original_path"]).is_file()
    # The manifest itself must be checksummed, or it is not evidence.
    assert (root / "MANIFEST.sha256").is_file()


def test_nothing_to_archive_is_a_pass(tmp_path, capsys):
    src, dst = _build(tmp_path, dest_only=[])
    rc = arch.main(
        ["--src", str(src), "--dst", str(dst), "--archive-root", str(tmp_path / "arch")]
    )
    assert rc == 0
    assert "Nothing to archive" in capsys.readouterr().out


def test_dry_run_copies_nothing(tmp_path, capsys):
    src, dst = _build(tmp_path, ["w1/data/backups/atom-cycle-1.db.gz"])
    rc = arch.main(
        [
            "--src", str(src), "--dst", str(dst),
            "--archive-root", str(tmp_path / "arch"),
            "--dry-run",
        ]
    )
    assert rc == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert not (tmp_path / "arch").exists()


def test_source_tree_is_not_modified(tmp_path, capsys):
    """Reading worlds must never write to them: another session is using them."""
    src, dst = _build(tmp_path, ["w1/data/backups/atom-cycle-1.db.gz"])
    before = sorted(os.walk(src).__next__()[1] + os.walk(src).__next__()[2])
    arch.main(
        ["--src", str(src), "--dst", str(dst), "--archive-root", str(tmp_path / "arch")]
    )
    after = sorted(os.walk(src).__next__()[1] + os.walk(src).__next__()[2])
    assert before == after


# ---------------------------------------------------------------------------
# the safety rails
# ---------------------------------------------------------------------------
def test_refuses_archive_inside_sync_target(tmp_path, capsys):
    """The single most important refusal.

    An archive under the rsync destination is deleted by the next
    `rsync --delete` — the copy would be made and then destroyed, with the
    tool reporting success in between.
    """
    src, dst = _build(tmp_path, ["w1/data/backups/atom-cycle-1.db.gz"])
    rc = arch.main(
        [
            "--src", str(src), "--dst", str(dst),
            "--archive-root", str(dst / "arch"),
        ]
    )
    assert rc == 2
    assert "INSIDE the rsync destination" in capsys.readouterr().err


def test_refuses_to_clobber_existing_archive(tmp_path, capsys, monkeypatch):
    """Each run normally gets a fresh timestamped dir; a same-second rerun
    must not overwrite an already-verified archive."""
    src, dst = _build(tmp_path, ["w1/data/backups/atom-cycle-1.db.gz"])
    root = tmp_path / "arch"

    # Freeze the stamp so the tool would collide with what we pre-create.
    monkeypatch.setattr(arch.time, "strftime", lambda fmt: "20200101-000000")
    existing = root / "20200101-000000"
    existing.mkdir(parents=True)
    (existing / "MANIFEST.json").write_text('{"previous": "verified copy"}')

    rc = arch.main(["--src", str(src), "--dst", str(dst), "--archive-root", str(root)])
    assert rc == 2
    assert "already exists" in capsys.readouterr().err
    # The pre-existing archive must be intact, not merged into or overwritten.
    assert json.loads((existing / "MANIFEST.json").read_text()) == {
        "previous": "verified copy"
    }
    assert not (existing / "payload").exists()


def test_detects_corrupted_archive_copy(tmp_path, capsys, monkeypatch):
    """Verification must actually be able to fail.

    A verifier that only ever sees good input would pass here too if it were
    a no-op, so the copy is corrupted in flight and the run must fail.
    """
    src, dst = _build(tmp_path, ["w1/data/backups/atom-cycle-1.db.gz"])
    real = arch.shutil.copy2

    def _corrupt(a, b, **kw):
        real(a, b, **kw)
        with open(b, "r+b") as f:
            f.seek(0)
            f.write(b"XXXXXXXX")

    monkeypatch.setattr(arch.shutil, "copy2", _corrupt)
    rc = arch.main(
        ["--src", str(src), "--dst", str(dst), "--archive-root", str(tmp_path / "arch")]
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "did not verify" in out
    assert "sha256 mismatch" in out


def test_missing_root_returns_2(tmp_path, capsys):
    rc = arch.main(
        [
            "--src", str(tmp_path / "nope"), "--dst", str(tmp_path),
            "--archive-root", str(tmp_path / "arch"),
        ]
    )
    assert rc == 2


# ---------------------------------------------------------------------------
# the audit's PRESERVED verdict depends on this archive being verifiable
# ---------------------------------------------------------------------------
def test_audit_unblocks_only_with_a_valid_archive(tmp_path, capsys):
    """End-to-end: archive, then the audit must stop reporting exposure."""
    _audit_spec = importlib.util.spec_from_file_location(
        "worlds_delete_audit",
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "orchestration_acceptance"
        / "worlds_delete_audit.py",
    )
    audit = importlib.util.module_from_spec(_audit_spec)
    sys.modules["worlds_delete_audit"] = audit
    _audit_spec.loader.exec_module(audit)

    src, dst = _build(tmp_path, ["w1/data/backups/atom-cycle-1.db.gz"])
    arc = tmp_path / "arch"

    # Before archiving: blocked.
    assert audit.main(["--src", str(src), "--dst", str(dst)]) == 1
    capsys.readouterr()

    # After archiving: no longer exposed.
    assert (
        arch.main(["--src", str(src), "--dst", str(dst), "--archive-root", str(arc)]) == 0
    )
    capsys.readouterr()
    assert (
        audit.main(
            ["--src", str(src), "--dst", str(dst), "--evidence-archive", str(arc)]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "PRESERVED" in out
    assert "EVIDENCE (would be the LAST copy): 0" in out


def test_audit_ignores_an_archive_whose_manifest_fails_its_checksum(tmp_path, capsys):
    """A tampered manifest is not proof of preservation.

    Otherwise anyone could silence the blocker by dropping a plausible-looking
    MANIFEST.json next to a payload that is empty or absent.
    """
    _audit_spec = importlib.util.spec_from_file_location(
        "worlds_delete_audit2",
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "orchestration_acceptance"
        / "worlds_delete_audit.py",
    )
    audit = importlib.util.module_from_spec(_audit_spec)
    sys.modules["worlds_delete_audit2"] = audit
    _audit_spec.loader.exec_module(audit)

    src, dst = _build(tmp_path, ["w1/data/backups/atom-cycle-1.db.gz"])
    arc = tmp_path / "arch" / "20260101-000000"
    rel = "w1/data/backups/atom-cycle-1.db.gz"
    (arc / "payload" / rel).parent.mkdir(parents=True)
    (arc / "payload" / rel).write_bytes(b"junk")
    (arc / "MANIFEST.json").write_text(
        json.dumps({"items": [{"relative_path": rel, "sha256": "0" * 64, "bytes": 4}]})
    )
    (arc / "MANIFEST.sha256").write_text(f"{'f' * 64}  MANIFEST.json\n")

    assert (
        audit.main(
            ["--src", str(src), "--dst", str(dst), "--evidence-archive", str(tmp_path / "arch")]
        )
        == 1
    )
    out = capsys.readouterr().out
    assert "FAILED its own checksum" in out
