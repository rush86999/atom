#!/usr/bin/env python3
"""Archive destination-only EVIDENCE out of an rsync target, before mirroring.

``rsync -a --delete`` makes the destination match the source exactly, which
means every path that exists only in the destination is destroyed. When the
destination is a *stale earlier snapshot*, some of those paths are not junk:
they are the last remaining copy of a record that the source has since dropped.
On 2026-09-27 that was 551.8M of gzip'd SQLite maintenance snapshots
(``atom-cycle-*.db.gz`` under ``*/data/backups/``) in two worlds.

This tool relocates the EVIDENCE bucket somewhere rsync will never look —
a timestamped archive, deliberately OUTSIDE the sync target — and proves the
copy before anything is deleted:

* copies each evidence file, preserving its path relative to the source root
  so the original location is recoverable;
* records original path, byte size, and SHA-256 for every item;
* re-reads each archived file and re-hashes it, comparing to the source hash;
* writes a manifest that is itself checksummed, and refuses to continue if any
  item fails verification.

It only ever READS the source and the sync target, and WRITES under the
archive root. It never modifies a world, so it is safe to run while another
session is building worlds.

Usage:
    archive_dest_only_evidence.py --src <local root> --dst <drive root> \\
        --archive-root "/Volumes/<drive>/worlds-evidence-archive"
    ... --dry-run          # report only, copy nothing
    ... --include review   # also archive the ambiguous bucket (off by default)

Exit codes: 0 archived and verified (or nothing to archive), 1 verification
failed, 2 the tool could not run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CHUNK = 1024 * 1024

_spec = importlib.util.spec_from_file_location(
    "worlds_delete_audit",
    Path(__file__).resolve().parent / "worlds_delete_audit.py",
)
_audit = importlib.util.module_from_spec(_spec)
sys.modules["worlds_delete_audit"] = _audit
_spec.loader.exec_module(_audit)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def human(n: float) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024.0
    return str(n)


def find_evidence(src: Path, dst: Path) -> Tuple[List[Tuple[str, int, str]], List[str], List[str]]:
    """Destination-only paths, split into (evidence, review, droppable)."""
    s_files, s_links, s_dirs, s_err = _audit._rel_files(src)
    d_files, d_links, d_dirs, d_err = _audit._rel_files(dst)

    evidence: List[Tuple[str, int, str]] = []
    review: List[Tuple[str, int]] = []
    droppable: List[Tuple[str, int]] = []

    for rel in sorted(d_files - s_files):
        b, why = _audit.classify(rel, 0)
        size = _audit.size_of(dst, rel)
        if b == "evidence":
            evidence.append((rel, size, why))
        elif b == "droppable":
            droppable.append((rel, size))
        else:
            review.append((rel, size))
    for rel in sorted(d_links - s_links):
        b, why = _audit.classify(rel, 0)
        # A symlink is preserved as its target string, not its contents.
        (evidence if b == "evidence" else review).append(
            (rel, 0) if b != "evidence" else (rel, 0, f"{why} (symlink)")
        )
    for rel in sorted(
        d for d in d_dirs - s_dirs
        if not any(f.startswith(d + os.sep) for f in s_files | s_links)
    ):
        b, why = _audit.classify(rel, 0)
        # Directory rows carry 0 bytes: the bytes belong to the file rows.
        if b == "evidence":
            evidence.append((rel, 0, f"{why} (directory)"))
        elif b == "droppable":
            droppable.append((rel, 0))
        else:
            review.append((rel, 0))
    return evidence, review, droppable


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--src", required=True, help="source worlds root (authoritative)")
    ap.add_argument("--dst", required=True, help="the rsync destination (stale copy)")
    ap.add_argument(
        "--archive-root",
        required=True,
        help="archive directory, OUTSIDE --dst (e.g. <drive>/worlds-evidence-archive)",
    )
    ap.add_argument("--dry-run", action="store_true", help="report only; copy nothing")
    ap.add_argument(
        "--include-review",
        action="store_true",
        help="also archive the ambiguous bucket (off by default — those need a human call)",
    )
    args = ap.parse_args(argv)

    src, dst, root = Path(args.src), Path(args.dst), Path(args.archive_root)

    for p, label in ((src, "--src"), (dst, "--dst")):
        if not p.is_dir():
            print(f"{label} is not a directory: {p}", file=sys.stderr)
            return 2

    # The whole point is that rsync cannot reach the archive. Refuse to run if
    # the archive is inside the sync target, rather than quietly creating a
    # directory that the next --delete will remove along with the evidence.
    try:
        archive_abs = root.resolve()
        dst_abs = dst.resolve()
    except OSError as exc:
        print(f"cannot resolve paths: {exc}", file=sys.stderr)
        return 2
    if archive_abs == dst_abs or dst_abs in archive_abs.parents:
        print(
            "REFUSING: --archive-root is INSIDE the rsync destination.\n"
            f"  archive: {archive_abs}\n"
            f"  target : {dst_abs}\n"
            "  Anything stored there is deleted by the next `rsync --delete`.\n"
            "  Pick a sibling directory on the same volume.",
            file=sys.stderr,
        )
        return 2

    print("== Destination-only evidence archive ==")
    print(f"  source        : {src}")
    print(f"  rsync target  : {dst}")
    print(f"  archive root  : {root}")
    print()

    print("[1/3] classifying destination-only paths")
    evidence, review, droppable = find_evidence(src, dst)
    total = sum(s for _, s, _ in evidence)
    print(f"  EVIDENCE  : {len(evidence)} entries, {human(total)}")
    print(f"  review    : {len(review)} entries")
    print(f"  droppable : {len(droppable)} entries")
    to_archive = list(evidence)
    if args.include_review:
        to_archive += [(r, s, "ambiguous (--include-review)") for r, s in review]
        print(f"  --include-review: archiving {len(review)} ambiguous entries too")
    print()

    if not to_archive:
        print("Nothing to archive — no destination-only evidence.")
        print("It is safe to proceed with `rsync -a --delete` from an evidence")
        print("standpoint (re-run worlds_delete_audit.py to confirm).")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest_root = root / stamp

    if dest_root.exists():
        print(f"REFUSING: archive directory already exists: {dest_root}", file=sys.stderr)
        return 2

    print(f"[2/3] copying {len(to_archive)} entries -> {dest_root}")
    if args.dry_run:
        for rel, size, why in to_archive:
            print(f"  would archive {human(size):>8}  {rel}   <- {why}")
        print()
        print("DRY RUN — nothing copied.")
        return 0

    manifest: List[Dict[str, object]] = []
    failures: List[str] = []
    for rel, size, why in to_archive:
        original = dst / rel
        archived = dest_root / "payload" / rel
        entry: Dict[str, object] = {
            "original_path": str(original),
            "relative_path": rel,
            "bytes": size,
            "classification": why,
        }
        try:
            archived.parent.mkdir(parents=True, exist_ok=True)
            if original.is_symlink():
                target = os.readlink(original)
                os.symlink(target, archived)
                entry["kind"] = "symlink"
                entry["link_target"] = target
            elif original.is_dir():
                archived.mkdir(parents=True, exist_ok=True)
                entry["kind"] = "directory"
            else:
                # copy2 preserves mtime, which matters for dated snapshots.
                shutil.copy2(original, archived)
                entry["kind"] = "file"
        except OSError as exc:
            entry["error"] = f"copy failed: {exc}"
            failures.append(f"{rel}: copy failed: {exc}")
            manifest.append(entry)
            continue

        # Verify by RE-READING both sides and comparing digests. A copy that
        # reports success is not evidence that it is byte-identical.
        if entry["kind"] == "file":
            try:
                src_hash = sha256_file(original)
                dst_hash = sha256_file(archived)
            except OSError as exc:
                entry["error"] = f"hash failed: {exc}"
                failures.append(f"{rel}: hash failed: {exc}")
                manifest.append(entry)
                continue
            entry["sha256"] = src_hash
            entry["archived_sha256"] = dst_hash
            entry["archived_path"] = str(archived)
            if src_hash != dst_hash:
                entry["error"] = "sha256 mismatch between original and archive"
                failures.append(f"{rel}: sha256 mismatch")
            else:
                actual = archived.stat().st_size
                if actual != size:
                    entry["error"] = f"size mismatch: expected {size}, got {actual}"
                    failures.append(f"{rel}: size mismatch")
                else:
                    print(f"  verified {human(size):>8}  {rel}")
        manifest.append(entry)

    print()
    print("[3/3] writing manifest")
    doc = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "created_at_epoch": time.time(),
        "archive_dir": str(dest_root),
        "source_root": str(src),
        "rsync_target": str(dst),
        "reason": (
            "Destination-only EVIDENCE preserved before `rsync -a --delete`. "
            "These paths are not in the source, so --delete would have removed "
            "the only remaining copy."
        ),
        "item_count": len(manifest),
        "total_bytes": sum(int(e.get("bytes") or 0) for e in manifest),
        "items": manifest,
    }
    body = json.dumps(doc, indent=2, sort_keys=True)
    manifest_path = dest_root / "MANIFEST.json"
    manifest_path.write_text(body + "\n")
    manifest_hash = sha256_file(manifest_path)
    (dest_root / "MANIFEST.sha256").write_text(f"{manifest_hash}  MANIFEST.json\n")

    print(f"  manifest      : {manifest_path}")
    print(f"  manifest sha256: {manifest_hash}")
    print(f"  items archived : {len(manifest)}  total {human(doc['total_bytes'])}")
    print()

    if failures:
        print(f"VERDICT: FAILED — {len(failures)} item(s) did not verify:")
        for f in failures:
            print(f"  - {f}")
        print("Do NOT run rsync --delete. Fix the archive first.")
        return 1

    print("VERDICT: archived and verified.")
    print(f"  {dest_root}")
    print("Re-run worlds_delete_audit.py to confirm no unique evidence is left")
    print("exposed to deletion, then proceed with the window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
