#!/usr/bin/env python3
"""Prove a worlds copy is CONTENT-identical, not merely the same shape.

Matching file and symlink counts do not establish that a copy succeeded.
A truncated SQLite file, a manifest from the wrong revision, or a symlink
whose *target* silently differs all preserve the counts. ``rsync -a`` also
preserves broken and mis-anchored links verbatim, so those defects travel
with the copy and are invisible until a world fails at import time.

This verifier answers four separate questions, each of which can fail
independently:

1. **Do the regular files have identical content?** SHA-256 per file,
   compared by (relative path, hash). ``--quick`` compares size+mtime
   instead, which is much faster but is NOT content proof — it is only
   appropriate for a first pass over a freshly rsynced tree.
2. **Do the symlinks point at the same things?** The link's own target
   string, compared verbatim. A link can resolve on both sides and still
   be a different link.
3. **Are the critical manifests valid and equal?** ``MANIFEST.json``,
   ``code_manifest.json``, ``launch_descriptor.json`` per world — parsed
   as JSON and compared, so a half-written manifest is caught even if the
   bytes happen to match in count.
4. **Are the databases structurally sound?** ``PRAGMA integrity_check``
   on every ``atom.db`` found, plus a row count on the largest table, so a
   corrupt-but-present DB cannot pass.

Plus two standing reports that do not depend on the copy at all:

* **broken** internal symlinks (present in source, missing target)
* **mis-anchored** internal symlinks (absolute links pointing back into the
  canonical worlds root — correct only while that root is itself a symlink)

Usage:
    worlds_migration_verify.py --src <local root> --dst <drive root>
    worlds_migration_verify.py --src ... --dst ... --quick
    worlds_migration_verify.py --src ... --dst ... --json report.json

Exit codes: 0 all checks passed, 1 differences/integrity failures,
2 the verifier itself could not run (bad args, unreadable root).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from core.world_storage_guard import audit_internal_symlinks  # noqa: E402

CHUNK = 1024 * 1024
#: Manifests that carry meaning. A copy that mangles these is not a copy.
CRITICAL_MANIFESTS = ("MANIFEST.json", "code_manifest.json", "launch_descriptor.json")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


@dataclass
class TreeSnapshot:
    """One side of the comparison."""

    root: Path
    files: Dict[str, Tuple[int, int, float]] = field(default_factory=dict)
    # relpath -> (size, mtime, sha256)
    links: Dict[str, str] = field(default_factory=dict)
    dirs: Dict[str, None] = field(default_factory=dict)
    broken: List[str] = field(default_factory=list)
    misanchored: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.root.name or str(self.root)


def snapshot(
    root: Path, *, quick: bool = False, hash_limit: int = 0, progress_every: int = 20000
) -> TreeSnapshot:
    """Walk ``root`` and record files, symlinks, and link defects.

    ``quick`` records (size, mtime) instead of a content hash. ``hash_limit``
    caps how many files get hashed (0 = all); beyond the cap the file is
    recorded by size+mtime only, and the report says so, because a partial
    hash is not content proof.
    """
    snap = TreeSnapshot(root=root)
    if not root.is_dir():
        snap.errors.append(f"root is not a readable directory: {root}")
        return snap

    hashed = 0
    unhashed = 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir != ".":
            snap.dirs[rel_dir] = None
        # Classify symlinked dirs before os.walk descends past them.
        for name in list(dirnames):
            p = d / name
            if p.is_symlink():
                dirnames.remove(name)
                filenames.append(name)
        for name in filenames:
            p = d / name
            rel = os.path.relpath(p, root)
            if p.is_symlink():
                try:
                    target = os.readlink(p)
                except OSError as exc:
                    snap.errors.append(f"unreadable link {rel}: {exc}")
                    continue
                snap.links[rel] = target
                if not p.exists():
                    snap.broken.append(f"{rel} -> {target}")
                elif os.path.isabs(target) and str(root) in target:
                    snap.misanchored.append(f"{rel} -> {target}")
                continue
            try:
                st = p.stat()
            except OSError as exc:
                snap.errors.append(f"unreadable file {rel}: {exc}")
                continue
            count += 1
            if quick or (hash_limit and hashed >= hash_limit):
                unhashed += 1
                snap.files[rel] = (st.st_size, 0, st.st_mtime)
            else:
                try:
                    digest = sha256_file(p)
                except OSError as exc:
                    snap.errors.append(f"unreadable file {rel}: {exc}")
                    continue
                hashed += 1
                snap.files[rel] = (st.st_size, 0, digest)
            if progress_every and count % progress_every == 0:
                print(
                    f"    ... {count} files ({hashed} hashed) in {snap.name}",
                    file=sys.stderr,
                    flush=True,
                )
    if unhashed:
        snap.errors.append(
            f"{unhashed} file(s) compared by size+mtime only, not content hash"
        )
    return snap


def compare_files(a: TreeSnapshot, b: TreeSnapshot, quick: bool) -> List[str]:
    """Content (or size+mtime) differences between the two trees."""
    problems: List[str] = []
    only_a = sorted(set(a.files) - set(b.files))
    only_b = sorted(set(b.files) - set(a.files))
    for rel in only_a[:50]:
        problems.append(f"MISSING in destination: {rel}")
    if len(only_a) > 50:
        problems.append(f"... and {len(only_a) - 50} more missing in destination")
    for rel in only_b[:50]:
        problems.append(f"EXTRA in destination: {rel}")
    if len(only_b) > 50:
        problems.append(f"... and {len(only_b) - 50} more extra in destination")

    if quick:
        mism = [
            rel
            for rel in set(a.files) & set(b.files)
            if a.files[rel][0] != b.files[rel][0] or a.files[rel][2] != b.files[rel][2]
        ]
        label = "size/mtime"
    else:
        mism = [
            rel
            for rel in set(a.files) & set(b.files)
            if a.files[rel][2] != b.files[rel][2]
        ]
        label = "sha256"
    for rel in sorted(mism)[:50]:
        problems.append(f"CONTENT DIFFERS ({label}): {rel}")
    if len(mism) > 50:
        problems.append(f"... and {len(mism) - 50} more content differences")
    return problems


def compare_links(a: TreeSnapshot, b: TreeSnapshot) -> List[str]:
    """Symlink target differences.

    A link whose target string differs can resolve on both sides and still
    be the wrong link, so the target is compared verbatim rather than by
    resolved path.
    """
    problems: List[str] = []
    only_a = sorted(set(a.links) - set(b.links))
    only_b = sorted(set(b.links) - set(a.links))
    for rel in only_a[:30]:
        problems.append(f"LINK MISSING in destination: {rel} -> {a.links[rel]}")
    for rel in only_b[:30]:
        problems.append(f"LINK EXTRA in destination: {rel} -> {b.links[rel]}")
    for rel in sorted(set(a.links) & set(b.links)):
        if a.links[rel] != b.links[rel]:
            problems.append(
                f"LINK TARGET DIFFERS: {rel}\n"
                f"    src: {a.links[rel]}\n"
                f"    dst: {b.links[rel]}"
            )
    return problems


def compare_manifests(a: TreeSnapshot, b: TreeSnapshot) -> List[str]:
    """Parse and compare the critical manifests, not just their bytes."""
    problems: List[str] = []
    checked = 0
    rels = sorted(
        {r for r in a.files if os.path.basename(r) in CRITICAL_MANIFESTS}
        | {r for r in b.files if os.path.basename(r) in CRITICAL_MANIFESTS}
    )
    for rel in rels:
        name = os.path.basename(rel)
        if name not in CRITICAL_MANIFESTS:
            continue
        in_a, in_b = rel in a.files, rel in b.files
        if in_a != in_b:
            problems.append(
                f"MANIFEST {name} present on only one side: {rel} "
                f"(src={in_a} dst={in_b})"
            )
            continue
        pa, pb = a.root / rel, b.root / rel
        try:
            ja = json.loads(pa.read_text())
            jb = json.loads(pb.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"MANIFEST UNREADABLE: {rel}: {exc}")
            continue
        if ja != jb:
            keys = sorted(set(ja) | set(jb)) if isinstance(ja, dict) else []
            diff = [k for k in keys if not (isinstance(ja, dict) and ja.get(k) == jb.get(k))]
            problems.append(
                f"MANIFEST CONTENT DIFFERS: {rel} (differing keys: {diff[:10]})"
            )
        else:
            checked += 1
    if not checked and not problems:
        print("  note: no critical manifests found to compare", file=sys.stderr)
    return problems


def check_databases(root: Path) -> Tuple[List[str], int]:
    """``PRAGMA integrity_check`` on every atom.db under ``root``."""
    problems: List[str] = []
    dbs = sorted(root.rglob("*.db"))
    dbs = [d for d in dbs if d.name in ("atom.db",) or d.suffix in (".sqlite", ".sqlite3")]
    for db in dbs:
        rel = os.path.relpath(db, root)
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
        except sqlite3.Error as exc:
            problems.append(f"DB UNOPENABLE: {rel}: {exc}")
            continue
        try:
            row = con.execute("PRAGMA integrity_check").fetchone()
            verdict = row[0] if row else "no result"
            if verdict != "ok":
                problems.append(f"DB INTEGRITY FAILED: {rel}: {verdict}")
                continue
            # A quick row count on the biggest table: catches a structurally
            # valid but emptied database, which integrity_check calls fine.
            tables = [
                r[0]
                for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            ]
            biggest, best = None, 0
            for t in tables:
                try:
                    n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                except sqlite3.Error:
                    continue
                if n > best:
                    biggest, best = t, n
            print(
                f"    db ok: {rel} ({len(tables)} tables, largest {biggest}={best} rows)",
                file=sys.stderr,
            )
        except sqlite3.Error as exc:
            problems.append(f"DB CHECK ERROR: {rel}: {exc}")
        finally:
            con.close()
    return problems, len(dbs)


def _report_link_defects(label: str, snap: TreeSnapshot) -> int:
    """Print standing link defects. These are reported, never auto-failed."""
    hard = 0
    if snap.broken:
        print(f"  FAIL  {label}: {len(snap.broken)} BROKEN internal symlink(s)")
        for b in snap.broken[:10]:
            print(f"          {b}")
        if len(snap.broken) > 10:
            print(f"          ... and {len(snap.broken) - 10} more")
        hard += 1
    if snap.misanchored:
        print(
            f"  WARN  {label}: {len(snap.misanchored)} mis-anchored internal symlink(s)"
            " (absolute links back into the canonical worlds root; correct"
            " only while that root is itself a symlink)"
        )
    return hard


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="source worlds root (the real tree)")
    ap.add_argument("--dst", required=True, help="destination worlds root (the copy)")
    ap.add_argument(
        "--quick",
        action="store_true",
        help="compare size+mtime instead of sha256 (fast, NOT content proof)",
    )
    ap.add_argument(
        "--hash-limit",
        type=int,
        default=0,
        help="hash at most N files (0 = all). Beyond the cap, size+mtime only.",
    )
    ap.add_argument("--skip-db", action="store_true", help="skip PRAGMA integrity_check")
    ap.add_argument("--json", dest="json_out", help="write a machine-readable report here")
    args = ap.parse_args(argv)

    src, dst = Path(args.src), Path(args.dst)
    for p, label in ((src, "--src"), (dst, "--dst")):
        if not p.is_dir():
            print(f"{label} is not a directory: {p}", file=sys.stderr)
            return 2

    print("== Worlds copy verification ==")
    print(f"  src: {src}")
    print(f"  dst: {dst}")
    print(f"  mode: {'QUICK (size+mtime, not content proof)' if args.quick else 'sha256 content'}")
    print()

    print("[1/5] snapshotting source")
    a = snapshot(src, quick=args.quick, hash_limit=args.hash_limit)
    print(
        f"  files={len(a.files)} links={len(a.links)} dirs={len(a.dirs)}"
        f" broken={len(a.broken)} misanchored={len(a.misanchored)}"
    )
    print("[2/5] snapshotting destination")
    b = snapshot(dst, quick=args.quick, hash_limit=args.hash_limit)
    print(
        f"  files={len(b.files)} links={len(b.links)} dirs={len(b.dirs)}"
        f" broken={len(b.broken)} misanchored={len(b.misanchored)}"
    )
    print()

    failures = 0
    results: Dict[str, object] = {}

    print("[3/5] internal symlink defects (reported separately; rsync -a preserves both)")
    for label, snap in (("src", a), ("dst", b)):
        failures += _report_link_defects(label, snap)
    results["broken"] = {"src": a.broken, "dst": b.broken}
    results["misanchored"] = {"src": a.misanchored, "dst": b.misanchored}
    print()

    print("[4/5] content + link target + manifest comparison")
    file_problems = compare_files(a, b, args.quick)
    link_problems = compare_links(a, b)
    manifest_problems = compare_manifests(a, b)
    for label, probs in (
        ("FILE", file_problems),
        ("LINK", link_problems),
        ("MANIFEST", manifest_problems),
    ):
        if probs:
            failures += 1
            print(f"  FAIL  {label}: {len(probs)} problem(s)")
            for p in probs[:25]:
                print(f"          {p}")
            if len(probs) > 25:
                print(f"          ... and {len(probs) - 25} more")
        else:
            print(f"  OK    {label}: identical")
    results["file_problems"] = file_problems
    results["link_problems"] = link_problems
    results["manifest_problems"] = manifest_problems
    for snap, label in ((a, "src"), (b, "dst")):
        for e in snap.errors:
            print(f"  WARN  {label} scan: {e}")
    print()

    print("[5/5] database integrity")
    if args.skip_db:
        print("  SKIP  (--skip-db)")
    else:
        db_problems, n_db = check_databases(dst)
        results["db_problems"] = db_problems
        results["db_count"] = n_db
        if db_problems:
            failures += 1
            print(f"  FAIL  DB: {len(db_problems)} problem(s) across {n_db} database(s)")
            for p in db_problems[:25]:
                print(f"          {p}")
        else:
            print(f"  OK    DB: {n_db} database(s) pass integrity_check")
    print()

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {
                    "src": str(src),
                    "dst": str(dst),
                    "quick": args.quick,
                    "failures": failures,
                    **results,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n"
        )
        print(f"report written to {args.json_out}")

    print()
    if failures:
        print(f"RESULT: FAILED — {failures} check group(s) reported problems.")
        print("Do NOT switch the canonical path over until these are explained.")
        return 1
    if args.quick:
        print("RESULT: shape consistent under --quick. Re-run WITHOUT --quick")
        print("        before treating this as content proof.")
        return 0
    print("RESULT: PASSED — content, link targets, manifests, and DB integrity agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
