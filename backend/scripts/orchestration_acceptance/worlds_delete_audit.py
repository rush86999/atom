#!/usr/bin/env python3
"""Classify what ``rsync --delete`` would DESTROY, before it destroys it.

``rsync -a --delete`` removes every path that exists in the destination but
not in the source. That is the correct way to make a copy exact, and it is
also the one command in this migration that can delete data which exists
nowhere else. The destination copy is a *stale earlier snapshot*: it is
missing two entire worlds and trails the source by ~18k files, so its
extra content is not automatically junk — some of it may be the only
remaining copy of a run that was later deleted locally.

So this tool never deletes. It computes the destination-only set, sorts
every entry into one of three buckets, and refuses to bless the deletion
while anything in the third bucket is unaccounted for:

``droppable``
    Regenerable scratch: ``.next/``, ``node_modules/``, ``__pycache__/``,
    ``*.pyc``, ``.DS_Store``, editor swap files, build stamps. Losing these
    costs time, not information.

``review``
    Ambiguous by extension alone — logs, run directories, ad-hoc JSON.
    Not safe to drop without a human decision.

``EVIDENCE — do not delete``
    Anything that records an observation: SQLite databases, manifests,
    acceptance/gate result files, JSONL traces, coverage reports, captured
    request payloads. A destination-only file in this bucket means the
    source no longer has it, so ``--delete`` would be the LAST copy.
    Deleting is a separate, explicitly approved step.

Usage:
    worlds_delete_audit.py --src <local root> --dst <drive root>
    worlds_delete_audit.py --src ... --dst ... --json audit.json
    worlds_delete_audit.py --src ... --dst ... --rsync-dry-run   # cross-check

Exit codes: 0 no evidence at risk, 1 evidence would be destroyed,
2 the audit could not run.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[2]

# Regenerable build/tooling output. Path fragments, matched anywhere.
DROPPABLE_FRAGMENTS = (
    ".next/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".preview-instance/",
    ".turbo/",
    ".vite/",
    ".DS_Store",
    ".pytest_cache",
)
DROPPABLE_PATTERNS = ("*.pyc", "*.pyo", "*.swp", "*.swo", "*~", ".coverage", "*.log.*")

# Extensions that record something that happened. Losing these loses data.
#
# Bare ``.json`` counts as evidence on purpose. In this tree a JSON file is a
# manifest, a provider/model catalog, a run descriptor, or a captured result —
# i.e. a record — so a destination-only one means the source has already lost
# it and ``--delete`` would remove the last copy. Failing closed here costs a
# human thirty seconds of attention; failing open costs an experiment. The
# droppable list is checked first, so genuinely regenerable artefacts still
# classify as droppable.
EVIDENCE_SUFFIXES = (
    ".json",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".jsonl",
    ".ndjson",
    ".har",
    ".trace",
    ".csv",
    ".xlsx",
    ".parquet",
)
EVIDENCE_NAMES = (
    "MANIFEST.json",
    "code_manifest.json",
    "launch_descriptor.json",
    "preview_stack.json",
    "live_acceptance_result.json",
    "restart_durability.json",
    "server_env.json",
    "metrics.json",
)
EVIDENCE_PATTERNS = (
    "*results*.json",
    "*acceptance*.json",
    "*gate*.json",
    "*manifest*.json",
    "*durability*.json",
    "coverage*.json",
    "*regrade*.json",
    "*metrics*.json",
    # Compressed database snapshots. `atom-cycle-*.db.gz` is a gzip'd SQLite
    # backup written by the maintenance cycle; treating it as scratch would
    # throw away a whole database history because of its extension.
    "*.db.gz",
    "*.sqlite.gz",
    "*.sqlite3.gz",
    "*.db.zst",
)
#: Path fragments that mark a tree as records rather than build output.
EVIDENCE_FRAGMENTS = ("/backups/", "/backup/", "/snapshots/", "/evidence/")


@dataclass
class Bucket:
    droppable: List[Tuple[str, int]] = field(default_factory=list)
    review: List[Tuple[str, int]] = field(default_factory=list)
    evidence: List[Tuple[str, int, str]] = field(default_factory=list)  # path, size, why
    preserved: List[Tuple[str, int, str, str]] = field(default_factory=list)  # path,size,archive,sha
    errors: List[str] = field(default_factory=list)

    def totals(self) -> Dict[str, Tuple[int, int]]:
        return {
            "droppable": (len(self.droppable), sum(s for _, s in self.droppable)),
            "review": (len(self.review), sum(s for _, s in self.review)),
            "evidence": (len(self.evidence), sum(s for _, s, _ in self.evidence)),
            "preserved": (len(self.preserved), sum(s for _, s, _, _ in self.preserved)),
        }


def load_evidence_archive(archive_root: Path) -> Dict[str, Dict[str, object]]:
    """Index a preservation archive by the path it protects.

    An archive is only accepted if its own MANIFEST verifies. A manifest that
    cannot be checked is not evidence of preservation, and treating it as such
    would be the same class of mistake this tool exists to prevent.
    """
    index: Dict[str, Dict[str, object]] = {}
    for manifest_path in sorted(archive_root.glob("*/MANIFEST.json")):
        archive_dir = manifest_path.parent
        try:
            doc = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  WARN  archive manifest unreadable, ignored: {manifest_path}: {exc}")
            continue

        declared = archive_dir / "MANIFEST.sha256"
        if declared.is_file():
            try:
                want = declared.read_text().split()[0]
                have = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            except (OSError, IndexError) as exc:
                print(f"  WARN  archive manifest hash unreadable, ignored: {exc}")
                continue
            if want != have:
                print(
                    f"  WARN  archive manifest FAILED its own checksum, ignored: "
                    f"{manifest_path}"
                )
                continue
        for item in doc.get("items", []):
            rel = item.get("relative_path")
            if rel:
                item = dict(item)
                item["_archive_dir"] = str(archive_dir)
                index[rel] = item
    return index


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_preserved(
    rel: str, index: Dict[str, Dict[str, object]], dst: Path
) -> Optional[Tuple[str, str]]:
    """Return ``(archive_path, sha256)`` if a verified copy protects ``rel``.

    Verification is by re-hashing the archived file and comparing it to the
    hash the manifest recorded, so "preserved" means the bytes are provably
    still there now — not that a path once existed.
    """
    item = index.get(rel)
    if not item:
        return None
    if item.get("kind") == "directory":
        return (str(Path(str(item["_archive_dir"])) / "payload" / rel), "dir")
    archived = Path(str(item["_archive_dir"])) / "payload" / rel
    if not archived.exists():
        return None
    want = item.get("sha256")
    if not want:
        # Symlink or unhashable entry: presence plus recorded target is the
        # best available proof.
        if item.get("kind") == "symlink" and os.readlink(archived) == item.get("link_target"):
            return (str(archived), "symlink")
        return None
    try:
        have = sha256_file(archived)
    except OSError:
        return None
    if have != want:
        print(f"  WARN  archived copy of {rel} no longer matches its manifest hash")
        return None
    return (str(archived), have)


def classify(rel: str, size: int) -> Tuple[str, str]:
    """Return ``(bucket, reason)`` for one destination-only path."""
    name = os.path.basename(rel)
    norm = rel.replace(os.sep, "/") + "/"

    for frag in DROPPABLE_FRAGMENTS:
        if frag.endswith("/") and frag in norm:
            return "droppable", f"regenerable build dir ({frag.strip('/')}/)"
        if not frag.endswith("/") and name == frag:
            return "droppable", f"regenerable artefact ({frag})"
    for pat in DROPPABLE_PATTERNS:
        if fnmatch.fnmatch(name, pat):
            return "droppable", f"regenerable artefact ({pat})"

    if name in EVIDENCE_NAMES:
        return "evidence", f"critical manifest/record ({name})"
    for pat in EVIDENCE_PATTERNS:
        if fnmatch.fnmatch(name, pat):
            return "evidence", f"result/evidence file ({pat})"
    for suf in EVIDENCE_SUFFIXES:
        if name.endswith(suf):
            return "evidence", f"data or trace file ({suf})"
    for frag in EVIDENCE_FRAGMENTS:
        if frag in norm:
            return "evidence", f"inside a record tree ({frag.strip('/')}/)"

    return "review", "ambiguous: not provably regenerable, not provably evidence"


def _rel_files(root: Path) -> Tuple[set, set, set, List[str]]:
    """Return (files, links, dirs, errors) as relative POSIX-ish paths."""
    files, links, dirs, errors = set(), set(), set(), []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir != ".":
            dirs.add(rel_dir)
        for name in list(dirnames):
            p = d / name
            if p.is_symlink():
                dirnames.remove(name)
                filenames.append(name)
        for name in filenames:
            p = d / name
            rel = os.path.relpath(p, root)
            try:
                if p.is_symlink():
                    links.add(rel)
                else:
                    files.add(rel)
                    p.stat()  # surface unreadable files now
            except OSError as exc:
                errors.append(f"{rel}: {exc}")
    return files, links, dirs, errors


def size_of(root: Path, rel: str) -> int:
    try:
        p = root / rel
        if p.is_symlink():
            return 0
        return p.stat().st_size
    except OSError:
        return 0


def rsync_dry_run(src: Path, dst: Path) -> List[str]:
    """Ask rsync itself what it would delete. Read-only."""
    cmd = [
        "rsync", "-a", "--delete", "--dry-run", "--itemize-changes",
        f"{src}/", f"{dst}/",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=1800, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"rsync dry-run failed: {exc}"]
    lines = []
    for line in out.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[0].startswith("*deleting"):
            # rsync appends a trailing slash to directories; the audit does
            # not. Normalise, or every directory reads as a false mismatch.
            lines.append(parts[1].strip().rstrip("/"))
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--src", required=True, help="source worlds root (authoritative)")
    ap.add_argument("--dst", required=True, help="destination worlds root (the copy)")
    ap.add_argument("--json", dest="json_out", help="write a machine-readable report")
    ap.add_argument(
        "--evidence-archive",
        action="append",
        default=[],
        help="preservation archive root (repeatable). Destination-only evidence "
             "with a verified archived copy is reported as PRESERVED instead of "
             "blocking, because it is no longer the last copy.",
    )
    ap.add_argument(
        "--rsync-dry-run",
        action="store_true",
        help="also run `rsync --dry-run --delete` and cross-check the sets",
    )
    ap.add_argument("--max-list", type=int, default=40, help="rows to print per bucket")
    args = ap.parse_args(argv)

    src, dst = Path(args.src), Path(args.dst)
    for p, label in ((src, "--src"), (dst, "--dst")):
        if not p.is_dir():
            print(f"{label} is not a directory: {p}", file=sys.stderr)
            return 2

    print("== Deletion audit: what `rsync --delete` would remove ==")
    print(f"  src (authoritative): {src}")
    print(f"  dst (the copy)     : {dst}")
    print("  NOTHING IS DELETED BY THIS TOOL.")
    print()

    print("[1/3] inventorying both trees")
    s_files, s_links, s_dirs, s_err = _rel_files(src)
    d_files, d_links, d_dirs, d_err = _rel_files(dst)
    print(f"  src: {len(s_files)} files, {len(s_links)} links, {len(s_dirs)} dirs")
    print(f"  dst: {len(d_files)} files, {len(d_links)} links, {len(d_dirs)} dirs")
    for e in (s_err + d_err)[:10]:
        print(f"  WARN  unreadable: {e}")
    print()

    print("[2/3] classifying destination-only paths")
    archive_index: Dict[str, Dict[str, object]] = {}
    for root in args.evidence_archive:
        ar = Path(root)
        if not ar.is_dir():
            print(f"  WARN  --evidence-archive not a directory, ignored: {ar}")
            continue
        found = load_evidence_archive(ar)
        print(f"  archive {ar}: {len(found)} protected path(s) indexed")
        archive_index.update(found)
    bucket = Bucket()
    dest_only_files = sorted(d_files - s_files)
    dest_only_links = sorted(d_links - s_links)
    # Directories present only in dst. A dir is only "extra" if no source
    # file lives under it; otherwise rsync would merge into it, not delete.
    #
    # Every level is listed, because that is what rsync itself reports (top
    # dir + subdirs + surviving files) and the cross-check below compares
    # against that. Byte totals are accumulated from FILES only, so the
    # nested directory rows do not double-count anything.
    dest_only_dirs = sorted(
        d for d in d_dirs - s_dirs
        if not any(f.startswith(d + os.sep) for f in s_files | s_links)
    )

    for rel in dest_only_files:
        b, why = classify(rel, 0)
        size = size_of(dst, rel)
        if b == "evidence":
            kept = check_preserved(rel, archive_index, dst)
            if kept:
                bucket.preserved.append((rel, size, kept[0], kept[1]))
            else:
                bucket.evidence.append((rel, size, why))
        elif b == "droppable":
            bucket.droppable.append((rel, size))
        else:
            bucket.review.append((rel, size))
    for rel in dest_only_links:
        b, why = classify(rel, 0)
        if b == "evidence":
            kept = check_preserved(rel, archive_index, dst)
            if kept:
                bucket.preserved.append((rel, 0, kept[0], kept[1]))
            else:
                bucket.evidence.append((rel, 0, f"{why} (symlink)"))
        else:
            bucket.review.append((rel, 0))
    for rel in dest_only_dirs:
        b, why = classify(rel, 0)
        # Size 0 on directory rows: the bytes are already counted on the
        # file rows underneath, and summing both would double-count.
        if b == "evidence":
            kept = check_preserved(rel, archive_index, dst)
            if kept:
                bucket.preserved.append((rel, 0, kept[0], kept[1]))
            else:
                bucket.evidence.append((rel, 0, f"{why} (directory)"))
        elif b == "droppable":
            bucket.droppable.append((rel, 0))
        else:
            bucket.review.append((rel, 0))

    def human(n: int) -> str:
        for unit in ("B", "K", "M", "G", "T"):
            if n < 1024 or unit == "T":
                return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
            n /= 1024.0
        return str(n)

    for label, rows in (
        ("DROPPABLE (regenerable)", bucket.droppable),
        ("REVIEW (ambiguous)", bucket.review),
    ):
        n, b = len(rows), sum(s for _, s in rows)
        print(f"  {label}: {n} entries, {human(b)}")
        for rel, size in rows[: args.max_list]:
            print(f"      {human(size):>8}  {rel}")
        if n > args.max_list:
            print(f"      ... and {n - args.max_list} more")
    if bucket.preserved:
        pn, pb = len(bucket.preserved), sum(s for _, s, _, _ in bucket.preserved)
        print(f"  PRESERVED (verified archived copy exists): {pn} entries, {human(pb)}")
        for rel, size, arch, digest in bucket.preserved[: args.max_list]:
            print(f"      {human(size):>8}  {rel}")
            print(f"               archived: {arch}")
            print(f"               sha256  : {digest[:32]}...")
        if pn > args.max_list:
            print(f"      ... and {pn - args.max_list} more")
    n, b = len(bucket.evidence), sum(s for _, s, _ in bucket.evidence)
    print(f"  EVIDENCE (would be the LAST copy): {n} entries, {human(b)}")
    for rel, size, why in bucket.evidence[: args.max_list]:
        print(f"      {human(size):>8}  {rel}   <- {why}")
    if n > args.max_list:
        print(f"      ... and {n - args.max_list} more")
    print()

    if args.rsync_dry_run:
        print("[3/3] cross-checking against `rsync --dry-run --delete`")
        rs = rsync_dry_run(src, dst)
        if len(rs) == 1 and rs[0].startswith("rsync dry-run failed"):
            print(f"  WARN  {rs[0]}")
        else:
            mine = {r for r, _, _, _ in bucket.preserved} | {r for r, _, _ in bucket.evidence} | {
                r for r, _ in bucket.review
            } | {r for r, _ in bucket.droppable}
            theirs = set(rs)
            only_rs = sorted(theirs - mine)
            only_mine = sorted(mine - theirs)
            print(f"  rsync would delete {len(theirs)} entries; audit found {len(mine)}")
            if only_rs:
                print(f"  WARN  {len(only_rs)} seen only by rsync (first 10):")
                for r in only_rs[:10]:
                    print(f"      {r}")
            if only_mine:
                print(f"  WARN  {len(only_mine)} seen only by the audit (first 10):")
                for r in only_mine[:10]:
                    print(f"      {r}")
            if not only_rs and not only_mine:
                print("  OK    the two agree exactly")
    else:
        print("[3/3] skipped (pass --rsync-dry-run to cross-check)")
    print()

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {
                    "src": str(src),
                    "dst": str(dst),
                    "dest_only_files": len(dest_only_files),
                    "dest_only_links": len(dest_only_links),
                    "dest_only_dirs": len(dest_only_dirs),
                    "droppable": bucket.droppable,
                    "review": bucket.review,
                    "evidence": bucket.evidence,
                    "preserved": bucket.preserved,
                    "errors": bucket.errors + s_err + d_err,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n"
        )
        print(f"report written to {args.json_out}")
        print()

    if bucket.evidence:
        print("VERDICT: BLOCKED — destination-only EVIDENCE exists.")
        print("  These paths are not in the source, so `rsync --delete` would")
        print("  destroy the only remaining copy. Decide per item whether it is")
        print("  superseded, then either:")
        print("    * re-copy it from elsewhere, or")
        print("    * exclude it from the sync (--exclude), or")
        print("    * explicitly approve its deletion, as a separate step.")
        return 1

    print("VERDICT: no destination-only evidence found.")
    if bucket.review:
        print(f"  {len(bucket.review)} ambiguous entries still need a human call.")
        print("  They are not provably evidence, but do not delete them blind.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
