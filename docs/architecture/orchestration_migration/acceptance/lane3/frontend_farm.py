#!/usr/bin/env python3
"""Per-instance frontend farms, so two previews can each own a real frontend.

WHY THIS EXISTS
`preview_stack.py` had exactly one project directory for every preview:
`frontend-nextjs/.preview-instance`, with a single `distDir` (`.next-preview`).
Next 16 takes an exclusive lock at `<distDir>/dev/lock`, so the SECOND preview's
`next dev` dies with "Another next dev server is already running" -- pointing at
the first preview's port and PID.

That failure was then swallowed: `_start_frontend` returned `None`, the caller
ignored the return value, wrote `"frontend_pid": null` into the world's state
file, printed `frontend: http://localhost:<port>  (pid None)`, and **exited 0**.
The world then advertised a URL that could not answer, and `verify` was the only
thing that noticed. A launch that cannot serve what it advertises must not
report success.

So a farm is per-INSTANCE, named, and carries its own distDir:

    .preview-farms/<name>/           farm project dir, OUTSIDE frontend-nextjs/
        pages/                        REAL dirs, symlinked files (see ROUTE_TREES)
        components/ hooks/ public/   plain symlinks
        lib/                          REAL dirs, symlinked files
        node_modules/                 REAL dir, one symlink per package
        next.config.js                real config, distDir overridden
        <distDir>/                    its own build dir, therefore its own lock

Nothing is duplicated, and nothing is frozen: every source FILE is a symlink to
the checkout, so an agent's edit is visible immediately with no rebuild, and no
two farms can disagree about the same commit.

THE ROUTE SHAPE IS THE WHOLE POINT (2026-09-28)
The first version symlinked every top-level entry, `pages` included. `next dev
--webpack` then registered NO dynamic page route: `/canvas/[id]` -- and ~18
others -- silently 404'd, while static routes kept working. That is the entire
reason there was no browser evidence for canvas editing: the composer under
test lives on a dynamic route, so the page did not exist in any farm, and the
one existing driver only ever visited the static `/chat`.

The repair that fixed routing (copying all sources) fixed the wrong thing: a
copy is only as current as the last `build`, and 14 MB per instance. The shape
that is both correct and current is real DIRECTORIES with symlinked FILES --
see ROUTE_TREES for the reproduction that isolates it.

    frontend_farm.py build   --name candidate_fix1 [--dist-dir .next-preview-cand]
    frontend_farm.py list
    frontend_farm.py check   --name candidate_fix1 --expect-origin http://localhost:8071
                             [--probe-url http://localhost:3106 --probe-path /canvas/x]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[5]
FRONTEND = REPO / "frontend-nextjs"
# Farms live BESIDE frontend-nextjs, not inside it. A farm nested at
# frontend-nextjs/.preview-instance/<world> shares the checkout's own project
# directory, so its distDir and node_modules are the checkout's and the second
# `next dev` dies on the exclusive `<distDir>/dev/lock`. Isolated by
# construction: a farm at <repo>/.preview-farms/<world>, same sources, same
# node_modules, its own lock. The `.next-preview-*` distDir is still why each
# world needs its own directory even here.
FARM_ROOT = REPO / ".preview-farms"

# Never symlinked into a farm: these are per-instance or must be the real thing.
#   .next*        build output / lock -- the whole reason a farm exists
#   node_modules  real dir of per-package symlinks (see build)
#   next.config.js the farm's own generated config
#   .env*         per-instance env, and a real .env must never be shared
#   .preview-instance  the farm root itself
NEVER_LINK_PREFIXES = (".next", "node_modules", "next.config.js", ".env",
                       ".preview-instance")

CONFIG_TEMPLATE = '''/**
 * Generated per-instance farm config. Do not edit by hand -- regenerate with
 * docs/architecture/orchestration_migration/acceptance/lane3/frontend_farm.py
 *
 * WHY A SEPARATE FILE AND A SEPARATE distDir
 * Next 16 sets `experimental.lockDistDir: true` and takes an exclusive lock at
 * `<distDir>/dev/lock`, and it hardcodes the config file name with no env
 * override. So two `next dev` processes cannot share one project directory, no
 * matter which port they are told to bind. The repo's real next.config.js is
 * shared and actively used by the user's own dev server, so it must not be
 * edited to unlock anything.
 *
 * `{dist_dir}` is the ONLY behavioural override. Everything else is the repo's
 * real config, required and spread verbatim, so this instance exercises the
 * same rewrites / env / env-contract as production.
 */
const realConfig = require({real_config!r});

module.exports = {{
  ...realConfig,
  distDir: '{dist_dir}',
  env: {{
    ...(realConfig.env || {{}}),
    ATOM_PREVIEW_INSTANCE: '{name}',
  }},
}};
'''


def farm_path(name: str) -> Path:
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)
    return FARM_ROOT / safe


def dist_dir_for(name: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)
    return f".next-preview-{safe}"


# --------------------------------------------------------------------------
# Symlink-escape containment
#
# INCIDENT (2026-09-28). A farm left over from a hand-built state still had
# `next.config.js` symlinked to the repo's real config. This generator's skip
# list means a skipped entry is never unlinked, and `Path.write_text` FOLLOWS a
# symlink -- so the write landed in `frontend-nextjs/next.config.js`,
# replacing the user's real config with a per-instance one. The user's own
# `next dev` on :3000 then died on a broken require, and the launcher's error
# message pointed at a `frontend_farm.py` path that did not exist.
#
# The lesson is that fixing one filename is not a fix. Every write this module
# performs must be contained, so the containment lives in one place and every
# destination goes through it.
# --------------------------------------------------------------------------
def _escape_reason(farm: Path, dest: Path) -> Optional[str]:
    """Why writing to ``dest`` could escape the farm, or None if it is safe."""
    farm_real = Path(os.path.realpath(farm))
    # The farm itself must be a real directory inside FARM_ROOT. If the farm
    # path is a symlink, every write under it is a write to its target.
    if farm.is_symlink():
        return f"farm path is a symlink -> {os.readlink(farm)}"
    try:
        dest_real = Path(os.path.realpath(dest))
    except OSError as exc:
        return f"cannot resolve destination: {exc}"
    if dest_real != farm_real and farm_real not in dest_real.parents:
        return f"destination resolves outside the farm: {dest_real} not under {farm_real}"
    # Any intermediate component that is a symlink is an escape hatch even when
    # it currently points inside the farm: a later rebuild of the checkout can
    # repoint it, and a farm generator must not depend on that staying true.
    rel = dest.relative_to(farm)
    walked = farm
    for part in rel.parts[:-1]:
        walked = walked / part
        if walked.is_symlink():
            return f"intermediate path component is a symlink: {walked} -> {os.readlink(walked)}"
    if dest.is_symlink():
        return f"destination is a symlink -> {os.readlink(dest)}"
    return None


def _safe_write(farm: Path, relpath: str, text: str) -> None:
    """Write a generated file inside the farm, refusing any symlink escape.

    Goes through a temp file in the same directory and ``os.replace``, so the
    destination is never opened for writing while it is a symlink -- which is
    the specific mechanism that corrupted the checkout.
    """
    dest = farm / relpath
    reason = _escape_reason(farm, dest)
    if reason:
        raise RuntimeError(
            f"refusing to write {relpath} into the farm: {reason}. "
            f"Farm generation must never modify files in the checkout.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.tmp.{os.getpid()}"
    tmp.write_text(text)
    os.replace(tmp, dest)


# Route-scanned trees. Next 16 dev does NOT register dynamic (bracketed) page
# routes found beneath a SYMLINKED DIRECTORY. A controlled reproduction isolates
# the directory as the cause -- all-real dirs -> 200; `pages` symlinked -> 404;
# real `pages` + symlinked `api` -> 404; real `pages`+`api` + symlinked `auth`
# -> 404; all-real dirs with only the catch-all FILE symlinked -> 200. Static
# routes still resolve on demand, so the fault hides behind a working
# `/api/health` and `/api/auth/accounts` and surfaces only as 404s for
# `/canvas/[id]`, `/boards/[boardId]`, `/api/auth/[...nextauth]` and the rest.
#
# THAT IS WHY THERE WAS NO BROWSER EVIDENCE FOR CANVAS EDITING: the canvas
# composer lives on a dynamic route, so the page under test did not exist in
# any farm, and the one existing driver only visited the static `/chat`.
#
# `lib` joins them for a different reason, and a symmetric one: a symlinked
# FILE changes what `import.meta.url` resolves against, so the relative
# `new URL("../node_modules/pdfjs-dist/...", import.meta.url)` in
# `lib/pdf-worker-src.ts` walks up from the farm instead of the source. Real
# directory + symlinked file keeps the module's own directory real, so that
# relative specifier resolves against the real tree.
#
# So these trees are mirrored as REAL directories whose FILES are symlinks.
# That is the shape the reproduction confirms, and it keeps the farm tracking
# the working tree: a symlinked file still reads the live file, so an agent's
# edit is visible immediately with no rebuild.
ROUTE_TREES = ("pages", "app", "src/pages", "src/app", "lib")


def _mirror_route_tree(farm: Path, src: Path) -> Tuple[int, int]:
    """Recreate ``src`` under ``farm`` as REAL directories holding symlinks.

    Directories are the load-bearing part (see ROUTE_TREES). Files stay
    symlinks, which is what keeps the farm honest: it tracks the live working
    tree rather than a snapshot of it, so an agent's edit is served without a
    rebuild and a farm can never silently drift from the checkout.

    Never a copy. The previous repair for the routing fault copied every source
    into the farm, which fixed routing and broke the farm: 14 MB duplicated per
    instance, current only as of the last ``build``, and two farms able to
    disagree about the same commit. A symlinked file has none of those
    properties and does not need them.

    Returns ``(files, dirs)``.
    """
    files = dirs = 0
    src = Path(os.path.realpath(src))
    for root, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames
                       if d not in ("node_modules", ".next", ".git")]
        rel = Path(root).relative_to(src)
        target = farm / rel
        # A stale symlink where a real directory belongs cannot be descended.
        if target.is_symlink():
            target.unlink()
        target.mkdir(parents=True, exist_ok=True)
        dirs += 1
        for name in filenames:
            s, d = Path(root) / name, target / name
            if d.is_symlink():
                if os.readlink(d) == str(s):
                    files += 1
                    continue
                d.unlink()          # points at the wrong place; unlink is safe
            elif d.exists():
                # A real file left by an older copy-based build. Replacing it
                # is required (a copy would freeze the source) and is safe
                # here: it is inside the farm, and `d` is not a symlink.
                d.unlink()
            d.symlink_to(s)
            files += 1
    return files, dirs


def _clear_generated(farm: Path, relpath: str) -> Optional[str]:
    """Remove whatever currently occupies a generated farm path.

    Unlink NEVER follows a symlink, so this is safe even when the occupant
    points at the checkout: removing the LINK cannot touch the file it names.
    That asymmetry is the whole point -- deleting the link is safe, writing
    through it is not -- so a farm left in the dangerous state by an older
    generator can still be repaired, while _safe_write still refuses to write
    through anything. Returns a description of what was removed, if anything.
    """
    dest = farm / relpath
    if not (dest.is_symlink() or dest.exists()):
        return None
    note = f"symlink -> {os.readlink(dest)}" if dest.is_symlink() else "existing file"
    dest.unlink()
    return note


def _copy_source_tree(farm: Path, src: Path) -> Tuple[List[str], List[str]]:
    """Symlink every non-route top-level entry of ``src`` into the farm.

    The farm is symlinks, not a copy. A copy is current only as of the last
    ``build``, so two farms can disagree about the same commit and an agent's
    edit is invisible until someone remembers to rebuild -- which defeats the
    reason a farm exists.

    The route trees are handled separately by :func:`_mirror_route_tree`,
    because there the DIRECTORIES must be real (Next 16 dev does not register
    dynamic routes beneath a symlinked directory) while the files stay links.
    Both halves of that shape are the same property applied to different
    components, so there is one mechanism, not two.

    Env files are skipped: a farm must not inherit the developer's ``.env``,
    and the launcher forwards model credentials to the child by name instead.
    Linking them would push live secrets into an isolated world.

    ``NEVER_LINK_PREFIXES`` is skipped for a sharper reason. ``next.config.js``
    is a file this module GENERATES in the farm, and on 2026-09-28 a farm that
    held it as a symlink to the checkout turned ``Path.write_text`` into a write
    to the user's real config, which killed the ``next dev`` on :3000. The
    containment check catches that write, so the checkout is not corrupted --
    but a generator that first creates the dangerous state and then repairs it
    depends on the repair running. It is skipped here so the state is never
    created, and the repair stays as the second line of defence.
    """
    SKIP_DIRS = {"node_modules", ".next", ".preview-instance", ".git", "out",
                 "coverage", "test-results", "playwright-report", "wdio",
                 # Rust toolchain + build artifacts: ~2.5 GB and irrelevant to
                 # `next dev`. Linking it is cheap, but a dev server that
                 # watches it pays for a tree it never reads.
                 "src-tauri"}
    linked: List[str] = []
    skipped: List[str] = []
    src = Path(os.path.realpath(src))
    for entry in sorted(os.listdir(src)):
        if entry == farm.name and farm.parent == src:
            continue
        if entry in ROUTE_TREES:
            continue          # mirrored with real dirs; see _mirror_route_tree
        if entry in SKIP_DIRS or entry.startswith(".env"):
            skipped.append(entry)
            continue
        if any(entry == p or entry.startswith(p) for p in NEVER_LINK_PREFIXES):
            # Generated per instance, or must be the real thing. See the
            # docstring: linking `next.config.js` at all is what turned a
            # farm write into a write to the user's checkout.
            skipped.append(entry)
            continue
        s, d = src / entry, farm / entry
        if d.is_symlink():
            if os.readlink(d) == str(s):
                linked.append(entry)
                continue
            d.unlink()        # points elsewhere; unlink cannot touch its target
        elif d.exists():
            # A real file or dir left by an older copy-based build. Replace it:
            # leaving a copy in place would keep serving a frozen source. Safe
            # because `d` is not a symlink, so it is farm content.
            if d.is_dir():
                import shutil
                shutil.rmtree(d)
            else:
                d.unlink()
        d.symlink_to(s)
        linked.append(entry)
    return linked, skipped


def build(name: str, dist_dir: Optional[str] = None) -> Dict[str, Any]:
    farm = farm_path(name)
    dist_dir = dist_dir or dist_dir_for(name)
    FARM_ROOT.mkdir(parents=True, exist_ok=True)
    farm.mkdir(parents=True, exist_ok=True)
    if farm.is_symlink():
        raise RuntimeError(
            f"farm path {farm} is a symlink -> {os.readlink(farm)}; refusing to "
            f"build, because every generated file would be written to its target "
            f"instead of into the farm.")


    linked, skipped = _copy_source_tree(farm, FRONTEND)

    # Route trees, mirrored with REAL directories and symlinked files. Done
    # after the top-level pass so a `pages` symlink from an older build is
    # replaced, and before the dev server starts, because Next's page collector
    # reads this shape once at startup and never re-scans a symlink.
    route_mirrors: Dict[str, Dict[str, int]] = {}
    for rel in ROUTE_TREES:
        src_tree = FRONTEND / rel
        if not src_tree.is_dir():
            continue
        n_files, n_dirs = _mirror_route_tree(farm / rel, src_tree)
        route_mirrors[rel] = {"real_dirs": n_dirs, "symlinked_files": n_files}

    node_modules = farm / "node_modules"
    if node_modules.is_symlink():
        # A single symlink for node_modules is not enough. The dev server
        # resolves `new URL("pdfjs-dist/build/pdf.worker.min.mjs",
        # import.meta.url)` in lib/pdf-worker-src.ts as a URL dependency, and
        # through a symlinked node_modules that resolution fails: /login and
        # /canvas/[id] 500 with "Module not found: ESM packages (pdfjs-dist)
        # need to be imported" while the identical checkout on :3000 is fine.
        # node_modules is therefore a REAL directory holding one symlink per
        # package, so resolution sees a real directory and the packages are
        # still shared rather than copied.
        node_modules.unlink()
    if not node_modules.exists():
        node_modules.mkdir(parents=True, exist_ok=True)
        real_nm = FRONTEND / "node_modules"
        if real_nm.is_dir():
            for entry in sorted(os.listdir(real_nm)):
                if entry == ".bin":
                    continue
                link = node_modules / entry
                if not link.exists():
                    try:
                        link.symlink_to(real_nm / entry)
                    except OSError:
                        pass
            if (real_nm / ".bin").exists() and not (node_modules / ".bin").exists():
                (node_modules / ".bin").symlink_to(real_nm / ".bin")
        if "node_modules" not in linked:
            linked.append("node_modules (real dir, per-package symlinks)")

    # These two are written as REAL files in the farm, never symlinks, so the
    # instance gets its own distDir and its own env. Both go through
    # _safe_write, which refuses any symlink escape -- the 2026-09-28 incident
    # was `Path.write_text` following a leftover `next.config.js` symlink into
    # the repo and replacing the user's real config, which killed the `next dev`
    # on :3000. Containment is enforced for the destination, for any
    # intermediate directory, and for the farm itself, rather than for one
    # filename.
    # Repair first, then write through _safe_write. Removing the link is safe
    # (unlink does not follow symlinks); writing through it is what corrupted
    # the checkout on 2026-09-28.
    for generated in ("next.config.js", ".env.local"):
        note = _clear_generated(farm, generated)
        if note:
            print(f"[farm] WARNING: {generated} was a {note}; removed it so the "
                  f"generated file lands in the farm and not in the checkout.")
    _safe_write(farm, "next.config.js",
                CONFIG_TEMPLATE.format(name=name, dist_dir=dist_dir,
                                     real_config=str(FRONTEND / 'next.config.js')))
    # A farm-local env so NEXT_PUBLIC_API_URL is not inherited from the shell or
    # from the user's other dev server.
    _safe_write(farm, ".env.local",
                "# generated per instance; the launcher also exports these in the child "
                "environment\nNEXT_PUBLIC_ALLOW_LOOPBACK=1\n")

    return {"farm": str(farm), "name": name, "dist_dir": dist_dir,
            "symlinks": len(linked), "skipped": skipped,
            "route_mirrors": route_mirrors,
            "dynamic_routes": dynamic_route_count(farm),
            "relinked": [], "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def route_files(farm: Path) -> List[Path]:
    """Every page/app source the farm's route trees would offer Next."""
    out: List[Path] = []
    for rel in ROUTE_TREES:
        root = farm / rel
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.suffix in (".tsx", ".ts", ".jsx", ".js") and not p.name.startswith("_"):
                out.append(p)
    return sorted(out)


def dynamic_route_count(farm: Path) -> int:
    """How many DYNAMIC routes this farm offers — the ones a symlinked tree drops."""
    return sum(1 for p in route_files(farm)
               if any(part.startswith("[") for part in p.relative_to(farm).parts))


def cmd_build(args: argparse.Namespace) -> int:
    info = build(args.name, args.dist_dir)
    print(f"farm     {info['farm']}")
    print(f"distDir  {info['dist_dir']}")
    print(f"symlinks {info['symlinks']}  relinked {len(info['relinked'])}")
    for rel, m in info["route_mirrors"].items():
        print(f"mirror   {rel}: {m['real_dirs']} real dirs, "
              f"{m['symlinked_files']} symlinked files")
    # The fault this shape exists to prevent is invisible in the build output
    # and shows up only as a 404 in a browser, so the count is printed here
    # where a reader will notice it going to zero.
    print(f"routes   {info['dynamic_routes']} DYNAMIC "
          f"(a symlinked route tree registers 0, and /canvas/[id] 404s)")
    if info["skipped"]:
        print(f"skipped  {info['skipped']}")
    print(f"config   {Path(info['farm'])/'next.config.js'}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    if not FARM_ROOT.is_dir():
        print("no farms yet")
        return 0
    rows = []
    for farm in sorted(p for p in FARM_ROOT.iterdir() if p.is_dir()):
        cfg = farm / "next.config.js"
        dist = None
        if cfg.exists():
            for line in cfg.read_text().splitlines():
                if "distDir:" in line:
                    dist = line.split("distDir:")[1].strip().strip("',").strip("'")
        dist_path = farm / (dist or "") if dist else None
        running = None
        if dist_path and dist_path.is_dir():
            for lock in dist_path.rglob("dev/lock"):
                running = lock.parent
                break
        rows.append({"farm": farm.name, "dist_dir": dist,
                     "dist_dir_exists": bool(dist_path and dist_path.is_dir()),
                     "dev_lock": str(running) if running else None})
    print(json.dumps(rows, indent=2))
    return 0


def _scan_chunks(farm: Path, dist_dir: str) -> List[Path]:
    root = farm / dist_dir
    if not root.is_dir():
        return []
    return [p for p in root.rglob("*.js") if p.is_file()]


def cmd_check(args: argparse.Namespace) -> int:
    """Prove the farm can serve THIS instance: right backend, and real routes.

    Two independent controls, because the two ways a farm misreports are
    independent:

      1. the COMPILED bundle must name this backend. A separate port proves
         nothing: `NEXT_PUBLIC_API_URL` is inlined at COMPILE time, so a farm
         built for another backend serves that other backend's world while
         looking perfectly healthy on its own port.
      2. a DYNAMIC page route must actually resolve. The routing fault this
         farm shape exists to prevent is invisible in every build artifact and
         shows up only as a 404 to a browser, so a check that never asks the
         server about a dynamic route cannot detect its return.
    """
    farm = farm_path(args.name)
    dist_dir = args.dist_dir or dist_dir_for(args.name)
    rc = _check_origin(farm, dist_dir, args.expect_origin)
    if rc:
        return rc
    if args.probe_url:
        rc = _check_route_probe(farm, args.probe_url, args.probe_path)
        if rc:
            return rc
    return 0


def _check_route_probe(farm: Path, probe_url: str, probe_path: str) -> int:
    """Ask a RUNNING farm for a dynamic route. A 404 is the defect, not a pass."""
    import httpx

    pages = route_files(farm)
    dynamic = [p for p in pages
               if any(part.startswith("[") for part in p.relative_to(farm).parts)]
    print(f"dynamic routes in the farm: {len(dynamic)}")
    if not dynamic:
        print("FAIL the farm offers no dynamic page routes at all; "
              "/canvas/[id] and the rest are unreachable")
        return 1
    if not probe_path:
        # Prefer the canvas detail page: it is the F06/F07 surface.
        probe_path = "/canvas/probe-id" if (farm / "pages" / "canvas" / "[id].tsx").exists() \
            else "/" + dynamic[0].relative_to(farm).with_suffix("").as_posix()
        probe_path = probe_path.replace("[", "x").replace("]", "x").replace("...", "x")
    try:
        r = httpx.get(f"{probe_url}{probe_path}", timeout=120, trust_env=False,
                      follow_redirects=True)
    except Exception as exc:  # a probe that cannot run is NOT a pass
        print(f"NOT APPLICABLE the route probe could not run: {exc}")
        return 1
    print(f"probe {probe_url}{probe_path} -> {r.status_code}")
    if r.status_code == 404:
        print("FAIL the dynamic route 404s on this instance. The farm's route "
              "directories must be REAL -- Next 16 dev does not register a "
              "dynamic route found beneath a symlinked directory.")
        return 1
    print("PASS a dynamic route resolves on this instance")
    return 0


def _check_origin(farm: Path, dist_dir: str, needle: str) -> int:
    chunks = _scan_chunks(farm, dist_dir)
    if not chunks:
        print(f"FAIL no compiled chunks under {farm/dist_dir}; the farm has not "
              f"been built (is a frontend running?)")
        return 1
    hits, foreign = [], {}
    for chunk in chunks:
        try:
            text = chunk.read_text(errors="ignore")
        except OSError:
            continue
        if needle and needle in text:
            hits.append(chunk.name)
        for token in ("http://localhost:", "http://127.0.0.1:"):
            idx = 0
            while True:
                idx = text.find(token, idx)
                if idx < 0:
                    break
                origin = text[idx:idx + 40].split('"')[0].split("'")[0]
                foreign.setdefault(origin.rstrip("/"), set()).add(chunk.name)
                idx += len(token)
    print(f"chunks            {len(chunks)}")
    print(f"expect origin     {needle}")
    print(f"chunks w/ origin  {len(hits)}")
    other = {o: sorted(f)[0] for o, f in foreign.items()
             if not needle or needle not in o}
    if other:
        print("other loopback origins present in the bundle:")
        for origin, sample in sorted(other.items()):
            print(f"    {origin}   (e.g. {sample})")
    if hits:
        print("PASS the compiled bundle targets this instance's backend")
        return 0
    print("FAIL the compiled bundle does NOT reference this instance's backend; "
          "a browser here would talk to a different world")
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--name", required=True)
    b.add_argument("--dist-dir")
    b.set_defaults(func=cmd_build)

    ls = sub.add_parser("list")
    ls.set_defaults(func=cmd_list)

    c = sub.add_parser("check")
    c.add_argument("--name", required=True)
    c.add_argument("--dist-dir")
    c.add_argument("--expect-origin", required=True)
    c.add_argument("--probe-url", default="",
                   help="base URL of a RUNNING farm, e.g. http://localhost:3106. "
                        "Adds a live dynamic-route probe, which is the only check "
                        "that can see the routing fault return.")
    c.add_argument("--probe-path", default="",
                   help="path to probe; defaults to /canvas/probe-id when present")
    c.set_defaults(func=cmd_check)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
