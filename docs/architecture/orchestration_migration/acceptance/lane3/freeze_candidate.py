#!/usr/bin/env python3
"""Freeze and re-verify one candidate's identity without rebuilding it.

WHY THIS EXISTS
`build_world` re-exports the working tree, so re-running a launcher against a
moving checkout silently produces a DIFFERENT candidate under the same name. The
only safe way to keep a passing result attributable is to record the bytes that
were actually running and then be able to re-check them later.

The world already holds an immutable, read-only export (`<world>/code`) plus
`code_manifest.json` mapping every exported path to its sha256. That manifest --
not `git rev-parse` -- is the authority: HEAD is still a8bc48dc1 while the
running source is `a8bc48dc1-dirty.58293b7b2484`, so a commit hash alone
understates what served the traffic.

This tool never writes to a world, never rebuilds one, and never touches a
running process. It only reads and hashes.

    NOTE: `--results` takes a LIST, so pass every artifact after ONE flag.
    Repeating the flag silently keeps only the last one, which would bind a
    single result and read as a complete record.

    freeze_candidate.py freeze   --world candidate_fix1 --out <dir> \
        --results a.json b.json c.json
    freeze_candidate.py verify   --world candidate_fix1 --record <dir>/candidate_freeze.json
    freeze_candidate.py diff     --world candidate_fix1 --record <dir>/candidate_freeze.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[5]
WORLDS = REPO / "backend" / "data" / "acceptance_worlds"


def sha256_file(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def manifest_tree_digest(manifest: Dict[str, str]) -> str:
    """One deterministic digest over the whole export.

    Order-independent by construction (sorted keys), so it is stable across
    Python versions and comparable between two freezes of the same source.
    """
    h = hashlib.sha256()
    for path in sorted(manifest):
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(manifest[path].encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def live_health(port: int) -> Dict[str, Any]:
    try:
        import httpx
        r = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=10,
                      trust_env=False)
        return (r.json() or {}).get("identity", {}) or {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def open_db_paths(pid: Optional[int]) -> List[str]:
    if not pid:
        return []
    try:
        out = subprocess.run(["lsof", "-p", str(pid)], capture_output=True,
                             text=True, timeout=60).stdout
    except Exception:
        return []
    paths = set()
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        name = parts[-1]
        if name.endswith((".db", ".db-wal", ".db-shm")):
            paths.add(name)
    return sorted(paths)


def load(world: str, name: str) -> Optional[Dict[str, Any]]:
    p = WORLDS / world / name
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _server_env_digest(world: Path, descriptor: Dict[str, Any]) -> Dict[str, Any]:
    """Hash the server environment the world was launched with.

    Configuration is part of what produced a result, and it lives outside the
    code export: the launch descriptor names the run dir, and that run dir holds
    `server_env.json` -- the resolved whitelist, not the shell it came from. Two
    runs on identical code with different flags are different candidates, and the
    only way to tell them apart later is this hash.
    """
    run_id = descriptor.get("run_id")
    out: Dict[str, Any] = {"run_id": run_id, "found": False}
    if not run_id:
        return out
    env_path = world / "runs" / str(run_id) / "server_env.json"
    if not env_path.is_file():
        return out
    try:
        payload = json.loads(env_path.read_text())
    except (OSError, ValueError):
        return out
    out["found"] = True
    out["path"] = str(env_path)
    out["sha256"] = sha256_file(env_path)
    out["key_count"] = len(payload) if isinstance(payload, dict) else None
    return out


def cmd_freeze(args: argparse.Namespace) -> int:
    world = WORLDS / args.world
    if not world.is_dir():
        print(f"no such world: {world}", file=sys.stderr)
        return 2

    code_manifest = load(args.world, "code_manifest.json") or {}
    manifest = load(args.world, "MANIFEST.json") or {}
    descriptor = load(args.world, "launch_descriptor.json") or {}
    stack = load(args.world, "preview_stack.json") or {}
    identity = descriptor.get("health_identity") or {}

    backend_port = stack.get("backend_port") or args.port
    health = live_health(backend_port)

    # The exported bytes that are actually on disk right now, re-hashed. This is
    # the independent check: the manifest says what was exported, this says what
    # is there.
    export_root = world / "code"
    rehashed: Dict[str, str] = {}
    mismatched: List[Dict[str, str]] = []
    for rel, want in sorted(code_manifest.items()):
        got = sha256_file(export_root / rel)
        if got is None:
            mismatched.append({"path": rel, "expected": want, "actual": "<missing>"})
        elif got != want:
            mismatched.append({"path": rel, "expected": want, "actual": got})
        else:
            rehashed[rel] = got

    # Per-file hashes for exactly the paths that make this source dirty relative
    # to HEAD. These are the files a reviewer needs to see, not 3000 clean ones.
    dirty = list(identity.get("dirty_paths") or [])
    untracked = list(identity.get("untracked_paths") or [])
    dirty_hashes: Dict[str, Dict[str, Optional[str]]] = {}
    for rel in dirty + untracked:
        in_export = sha256_file(export_root / rel)
        in_tree = sha256_file(REPO / rel)
        dirty_hashes[rel] = {"export": in_export, "working_tree": in_tree,
                             "drifted": in_export != in_tree}

    pid = health.get("pid") or identity.get("pid")
    record = {
        "schema": "lane3-candidate-freeze-v2",
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": args.world,
        "world_path": str(world),
        # ------------------------------------------------------------------
        # IDENTITY, IN THREE SEPARATE BOXES, AND THE ORDER MATTERS.
        #
        # `code` is the only thing that decides which program produced a
        # result, so it is the immutable export-tree digest over
        # code_manifest.json. `config` and `fixture` are recorded separately
        # because they change behaviour without changing a line of code: a flag
        # flipped or a different dataset yields different results from
        # identical code, and citing the code hash alone would hide that.
        #
        # `launch` is deliberately NOT identity. `source_id` /
        # `instance_id` describe one PROCESS, and for a world they are not even
        # stable across launches of identical code: the dirty digest is taken
        # over the world's own `git status --untracked-files=all`, which
        # includes the evidence directory, so writing a result file changes the
        # next launch's digest. Two runs on byte-identical exports read
        # `…dirty.9b2084c16e84` and `…dirty.21ce2b24fd0b`. Cite
        # `identity.code.export_tree_sha256`.
        # ------------------------------------------------------------------
        "identity": {
            "code": {
                "export_tree_sha256": manifest_tree_digest(code_manifest),
                "export_file_count": len(code_manifest),
                "export_rehashed_ok": len(rehashed),
                "export_mismatches": mismatched,
                "export_intact": not mismatched,
                "code_snapshot_sha256": (manifest or {}).get("code_snapshot_sha256"),
            },
            "config": {
                # the resolved launch environment; its own sha256 is inside,
                # because "not found" is itself an answer worth recording
                "server_env": _server_env_digest(world, descriptor),
                "effective_flags": descriptor.get("effective_flags") or {},
                "network_boundary": (manifest or {}).get("network_boundary"),
                "harness_version": (manifest or {}).get("harness_version"),
            },
            "fixture": {
                "atom_db_sha256": (manifest or {}).get("atom_db_sha256"),
                "db_frozen_at": (manifest or {}).get("db_frozen_at"),
                "parquet_files_verified": (manifest or {}).get("parquet_files_verified"),
                "credential_scrub": (manifest or {}).get("credential_scrub"),
                "venv_freeze_sha256": (manifest or {}).get("venv_freeze_sha256"),
            },
            "launch": {
                "source_id": health.get("source_id") or identity.get("source_id"),
                "instance_id": health.get("instance_id") or identity.get("instance_id"),
                "git_commit": health.get("git_commit") or identity.get("git_commit"),
                "revision": health.get("revision") or identity.get("revision"),
                "dirty_digest": health.get("dirty_digest") or identity.get("dirty_digest"),
                "pid": pid,
                "backend_port": backend_port,
                "frontend_port": stack.get("frontend_port"),
                "open_db_paths": open_db_paths(pid),
                "note": "process identity, NOT code identity -- see identity.code",
            },
        },
        # kept at the top level so existing readers of this record keep working
        "source_id": health.get("source_id") or identity.get("source_id"),
        "git_commit": health.get("git_commit") or identity.get("git_commit"),
        "revision": health.get("revision") or identity.get("revision"),
        "dirty_digest": health.get("dirty_digest") or identity.get("dirty_digest"),
        "instance_id": health.get("instance_id") or identity.get("instance_id"),
        "export_tree_sha256": manifest_tree_digest(code_manifest),
        "export_file_count": len(code_manifest),
        "export_rehashed_ok": len(rehashed),
        "export_mismatches": mismatched,
        "export_intact": not mismatched,
        "dirty_paths": dirty,
        "untracked_paths": untracked,
        "dirty_file_hashes": dirty_hashes,
        "ports": {"backend": backend_port, "frontend": stack.get("frontend_port")},
        "process": {"pid": pid, "open_db_paths": open_db_paths(pid)},
        "effective_flags": descriptor.get("effective_flags") or {},
        "world_manifest": manifest,
        "results": {},
    }

    for rel in args.results:
        p = REPO / rel
        if p.exists():
            record["results"][rel] = {
                "sha256": sha256_file(p),
                "generated_at": (json.loads(p.read_text()).get("generated_at")
                                 if p.suffix == ".json" else None),
            }
        else:
            record["results"][rel] = {"error": "missing"}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidate_freeze.json").write_text(json.dumps(record, indent=2))

    # Copy the evidence next to the record so the pair cannot drift apart.
    for rel in args.results:
        p = REPO / rel
        if p.exists():
            (out / Path(rel).name).write_bytes(p.read_bytes())
    for name in ("launch_descriptor.json", "MANIFEST.json", "preview_stack.json"):
        p = world / name
        if p.exists():
            (out / name).write_bytes(p.read_bytes())

    print(f"source_id        {record['source_id']}")
    print(f"instance_id      {record['instance_id']}")
    print(f"export tree      {record['export_tree_sha256']}")
    print(f"export files     {record['export_file_count']} "
          f"(rehashed ok {record['export_rehashed_ok']}, "
          f"mismatched {len(mismatched)})")
    print(f"export intact    {record['export_intact']}")
    print(f"pid / open db    {pid} / {len(record['process']['open_db_paths'])}")
    drifted = [k for k, v in dirty_hashes.items() if v["drifted"]]
    print(f"dirty files      {len(dirty_hashes)} "
          f"(working tree drifted from export: {len(drifted)})")
    for d in drifted:
        print(f"    DRIFT {d}")
    print(f"-> {out/'candidate_freeze.json'}")
    return 0 if record["export_intact"] else 1


def _compare(world: str, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    problems: List[str] = []
    export_root = WORLDS / world / "code"
    identity = record.get("identity") or {}
    if identity and identity.get("code", {}).get("export_tree_sha256"):
        # v2 records carry the code identity in its own box; prefer it
        record = {**record, "export_tree_sha256":
                  identity["code"]["export_tree_sha256"]}
    want_tree = record.get("export_tree_sha256")
    manifest = load(world, "code_manifest.json") or {}
    if manifest and manifest_tree_digest(manifest) != want_tree:
        problems.append("the world's code_manifest.json no longer hashes to the "
                        "frozen export_tree_sha256 (the world was rebuilt)")
    for rel in sorted(manifest):
        got = sha256_file(export_root / rel)
        if got != manifest[rel]:
            problems.append(f"export byte drift: {rel}")
            if len(problems) > 20:
                problems.append("... more")
                break
    for rel, info in (record.get("dirty_file_hashes") or {}).items():
        got = sha256_file(export_root / rel)
        if info.get("export") and got != info["export"]:
            problems.append(f"frozen dirty file changed: {rel}")
    return not problems, problems


def cmd_verify(args: argparse.Namespace) -> int:
    record = json.loads(Path(args.record).read_text())
    world = args.world or record["world"]
    ok, problems = _compare(world, record)
    print(f"candidate        {record['source_id']}")
    print(f"frozen at        {record['frozen_at']}")
    print(f"export tree      {record['export_tree_sha256']}")
    print(f"still intact     {ok}")
    for p in problems:
        print(f"    {p}")
    return 0 if ok else 1


def cmd_diff(args: argparse.Namespace) -> int:
    """Compare the frozen candidate's source against the CURRENT working tree."""
    record = json.loads(Path(args.record).read_text())
    same, changed, gone, new = [], [], [], []
    for rel, info in (record.get("dirty_file_hashes") or {}).items():
        tree = sha256_file(REPO / rel)
        exp = info.get("export")
        if tree is None:
            gone.append(rel)
        elif tree == exp:
            same.append(rel)
        else:
            changed.append(rel)
    print(f"identical to the frozen export : {len(same)}")
    print(f"changed since the freeze       : {len(changed)}")
    for c in changed:
        print(f"    CHANGED {c}")
    print(f"absent from the working tree    : {len(gone)}")
    for g in gone:
        print(f"    GONE    {g}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("freeze")
    f.add_argument("--world", required=True)
    f.add_argument("--port", type=int, default=8071)
    f.add_argument("--out", required=True)
    f.add_argument("--results", nargs="*", default=[
        "docs/architecture/orchestration_migration/acceptance/task_correction_results.json",
    ])
    f.set_defaults(func=cmd_freeze)

    v = sub.add_parser("verify")
    v.add_argument("--world")
    v.add_argument("--record", required=True)
    v.set_defaults(func=cmd_verify)

    d = sub.add_parser("diff")
    d.add_argument("--world")
    d.add_argument("--record", required=True)
    d.set_defaults(func=cmd_diff)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
