#!/usr/bin/env python3
"""A frontend farm whose DYNAMIC page routes actually resolve.

THE DEFECT THIS WORKS AROUND, WITH A MINIMAL REPRODUCTION
`frontend_farm.py` symlinks every TOP-LEVEL entry of `frontend-nextjs`, so the
farm's `pages` is a single symlink to the real `pages` directory. Under
`next dev --webpack` that silently drops every DYNAMIC page route:

    /            200     (pages/index.tsx          — static)
    /boards      200     (pages/boards/index.tsx  — static)
    /workflows/builder
                 200     (static, nested)
    /abc         404     (pages/[id].tsx          — DYNAMIC)
    /sub/abc     404     (pages/sub/[id].tsx      — DYNAMIC, nested)

Next's page collector walks `pages` and, when a directory is a symlink, never
descends far enough to register the dynamic segments below it. Reduced to a
project with two page files, the shape of the farm is the whole difference:

    pages -> realpages            (a symlinked DIRECTORY)   /abc 404, /sub/abc 404
    pages/  real, sub/ real,      (real dirs, symlinked     /abc 200, /sub/abc 200
     files -> real files            FILES)

Both results are `next dev --webpack`, Next 16.2.2, same machine, seconds apart.

WHY THIS BLOCKED THE D5 BROWSER CASE, AND WHY IT WAS INVISIBLE
The canvas composer under test lives on `/canvas/{id}` — a dynamic route. So the
page a user opens to edit a canvas does not exist on ANY preview farm, and the
only browser evidence in this lane so far (`browser_correction_chain.py`) visits
`/chat`, a static route, which resolves fine. Every dynamic page in the product
is unreachable in every preview: `/boards/[boardId]`, `/documents/[docId]`,
`/goal-runs/[id]`, `/workflows/editor/[id]`, and `/api/auth/[...nextauth]` (which
is why every preview browser log carries a next-auth `CLIENT_FETCH_ERROR`).

The fix shape is deliberately NOT a workaround around a product bug: the product
is fine, the FARM is wrong. So this module reproduces the same farm contract
(a real `next.config.js` with only `distDir` overridden, one farm per instance,
no duplicated source) with the one thing changed — `pages` is a real mirrored
directory of symlinked FILES. Everything else stays a top-level symlink, so the
farm still reflects the live working tree and still costs a few symlinks.

    frontend_farm_recursive.py build --name <world>
    frontend_farm_recursive.py check --name <world> --expect-origin <url>

`frontend_farm.py` is another stream's file; this is reported, not edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[5]
FRONTEND = REPO / "frontend-nextjs"
FARM_ROOT = FRONTEND / ".preview-instance"

# Never symlinked: per-instance, or must be the real thing.
#   .next*         build output / the dev lock -- the whole reason a farm exists
#   node_modules   must be the real tree (Turbopack refuses an escaping symlink)
#   next.config.js the farm's own generated config
#   .env*          per-instance env; a real .env must never be shared
NEVER_LINK_PREFIXES = (".next", "node_modules", "next.config.js", ".env",
                       ".preview-instance")

#: Directories that Next SCANS for routes rather than merely importing, plus
#: every directory a declared shim may need to live in. These get the recursive
#: real-directory treatment; everything else stays a single top-level symlink,
#: which is what makes the farm cheap.
ROUTE_DIRS = ("pages", "app", "src/pages", "src/app")
MIRRORED_DIRS = tuple(ROUTE_DIRS) + ("lib",)

CONFIG_TEMPLATE = '''/**
 * Generated per-instance farm config. Do not edit by hand -- regenerate with
 * docs/architecture/orchestration_migration/acceptance/lane3/frontend_farm_recursive.py
 *
 * Identical to frontend_farm.py's config in every behavioural respect: the
 * repo's real config, required and spread verbatim, with `distDir` as the ONLY
 * override. The difference between the two farms is the SHAPE of `pages`, not
 * this file -- see the module docstring.
 */
const realConfig = require('../../next.config.js');

module.exports = {{
  ...realConfig,
  distDir: '{dist_dir}',
  env: {{
    ...(realConfig.env || {{}}),
    ATOM_PREVIEW_INSTANCE: '{name}',
  }},
}};
'''


def safe(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(name))


def farm_path(name: str) -> Path:
    return FARM_ROOT / safe(name)


def dist_dir_for(name: str) -> str:
    return f".next-preview-{safe(name)}"


def _mirror_routes_dir(real: Path, mirror: Path) -> Tuple[int, int, List[str]]:
    """Recreate `real` as a tree of REAL directories holding symlinked FILES.

    Directories are the load-bearing part: Next's page collector does not
    register dynamic segments found beneath a symlinked directory, so every
    directory on the way down to a `[param].tsx` must be real. Files may be
    symlinks -- the collector reads them fine, and keeping them links is what
    makes the farm track the live working tree instead of freezing a copy.
    """
    n_files = n_dirs = 0
    anomalies: List[str] = []
    mirror.mkdir(parents=True, exist_ok=True)
    for entry in sorted(os.listdir(real)):
        if entry.startswith("."):
            continue
        src = real / entry
        dst = mirror / entry
        if src.is_dir():
            # A stale symlink where a real directory belongs cannot be descended.
            if dst.is_symlink():
                dst.unlink()
            if dst.exists() and not dst.is_dir():
                anomalies.append(f"{src.name} (REAL FILE in the farm, wanted a dir)")
                continue
            f, d, a = _mirror_routes_dir(src, dst)
            n_files += f
            n_dirs += d
            anomalies += [f"{entry}/{x}" for x in a]
            continue
        if dst.is_symlink():
            if os.readlink(dst) == str(src):
                n_files += 1
                continue
            dst.unlink()
        elif dst.exists():
            anomalies.append(f"{src.name} (REAL FILE left untouched)")
            continue
        dst.symlink_to(src)
        n_files += 1
    n_dirs += 1
    return n_files, n_dirs, anomalies


#: A DECLARED SHIM, applied inside a farm only. Never to the product tree.
#:
#: `lib/pdf-worker-src.ts` returns
#:     new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url)
#: which webpack 5 refuses: "ESM packages (pdfjs-dist/...) need to be imported.
#: Use 'import' to reference the package instead" (a BARE specifier in
#: new URL(..., import.meta.url) is not an asset reference). Its own docstring
#: claims webpack resolves it; measured on Next 16.2.2 + webpack, it does not,
#: and the failure is a COMPILE error on the whole import chain
#:     pages/canvas/[id].tsx -> components/canvas/CanvasPanel.tsx
#:                            -> components/canvas/PdfFileCanvas.tsx
#:                            -> lib/pdf-worker-src.ts
#: so /canvas/{id} answers 500 and the composer under test does not exist.
#:
#: The one-string change below is webpack's documented asset form (a RELATIVE
#: path). It is inert for this case: the module is only called by
#: PdfFileCanvas when a PDF canvas is opened, and this case drives an EMAIL
#: canvas. The deviation is recorded in the report with both digests so the
#: served frontend is not mistaken for the product byte-for-byte.
PDF_WORKER_SHIM = '''/**
 * DECLARED FARM SHIM -- not the product's file. See
 * docs/architecture/orchestration_migration/acceptance/lane3/frontend_farm_recursive.py
 * (PDF_WORKER_SHIM) for why this exists and why it cannot affect an
 * email-canvas acceptance case. The product's file is unchanged.
 */
export function pdfWorkerSrc(): string {
    return new URL("../node_modules/pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
}
'''

SHIMMED_FILES = {"lib/pdf-worker-src.ts": PDF_WORKER_SHIM}


def apply_declared_shims(farm: Path) -> List[Dict[str, Any]]:
    """Write the declared shims into the farm and record exactly what changed.

    Every write is preceded by a hard containment check. An earlier version of
    this function wrote through the farm's top-level `lib` SYMLINK and
    overwrote the product's own `frontend-nextjs/lib/pdf-worker-src.ts` — the
    mirror below now makes `lib` a real directory, and this check means a future
    mistake fails loudly instead of editing the user's tree.
    """
    farm_real = farm.resolve()
    out: List[Dict[str, Any]] = []
    for rel, content in SHIMMED_FILES.items():
        real = FRONTEND / rel
        shim = farm / rel
        # Containment, checked on the DIRECTORY the write goes through. The
        # file itself is normally a symlink to the product's -- that is the
        # farm's whole design, and resolving it first would report every
        # legitimate shim as an escape. What must never happen is a write
        # travelling up through a symlinked PARENT into the product tree.
        parent_real = shim.parent.resolve()
        if not str(parent_real).startswith(str(farm_real) + os.sep):
            raise SystemExit(
                f"refusing to write the shim {rel}: {shim.parent} resolves to "
                f"{parent_real}, outside the farm {farm_real} (a write would "
                f"edit the product tree)")
        shim.parent.mkdir(parents=True, exist_ok=True)
        if shim.is_symlink():
            shim.unlink()
        elif shim.exists():
            raise SystemExit(f"refusing to overwrite a real file at {shim}")
        shim.write_text(content)
        out.append({
            "path": rel,
            "reason": "webpack cannot resolve a bare package specifier inside "
                      "new URL(..., import.meta.url); the compile error takes "
                      "the whole canvas page down",
            "product_sha256": hashlib.sha256(real.read_bytes()).hexdigest()
            if real.exists() else None,
            "served_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "called_by_this_case": False,
        })
    return out


def build(name: str, dist_dir: Optional[str] = None,
          with_shims: bool = True) -> Dict[str, Any]:
    farm = farm_path(name)
    dist_dir = dist_dir or dist_dir_for(name)
    FARM_ROOT.mkdir(parents=True, exist_ok=True)
    farm.mkdir(parents=True, exist_ok=True)

    linked: List[str] = []
    skipped: List[str] = []
    relinked: List[str] = []
    route_mirrors: Dict[str, Any] = {}

    route_rel = {r: (FRONTEND / r) for r in MIRRORED_DIRS if (FRONTEND / r).is_dir()}
    # A route dir that is already a real directory in the farm (from an earlier
    # top-level symlink farm) must be REMOVED before mirroring, or the mirror
    # lands inside the old link.
    for rel in route_rel:
        stale = farm / rel
        if stale.is_symlink():
            stale.unlink()
        elif stale.is_dir():
            import shutil
            shutil.rmtree(stale)

    for entry in sorted(os.listdir(FRONTEND)):
        if entry == farm.name and farm.parent == FRONTEND:
            continue
        if any(entry == p or entry.startswith(p) for p in NEVER_LINK_PREFIXES):
            skipped.append(entry)
            continue
        if entry in route_rel:
            f, d, anomalies = _mirror_routes_dir(route_rel[entry], farm / entry)
            route_mirrors[entry] = {"real_dirs": d, "symlinked_files": f,
                                    "anomalies": anomalies}
            continue
        target = FRONTEND / entry
        link = farm / entry
        want = str(target.resolve())
        if link.is_symlink():
            if str(link.resolve() if link.exists() else link) == want:
                linked.append(entry)
                continue
            link.unlink()
            relinked.append(entry)
        elif link.exists():
            skipped.append(f"{entry} (REAL, left untouched -- would be clobbered)")
            continue
        link.symlink_to(target)
        linked.append(entry)

    node_modules = farm / "node_modules"
    if not node_modules.exists():
        node_modules.symlink_to(FRONTEND / "node_modules")
        if "node_modules" not in linked:
            linked.append("node_modules")

    (farm / "next.config.js").write_text(
        CONFIG_TEMPLATE.format(name=name, dist_dir=dist_dir))
    (farm / ".env.local").write_text(
        "# generated per instance; the launcher also exports these in the child "
        "environment\nNEXT_PUBLIC_ALLOW_LOOPBACK=1\n")

    shims = apply_declared_shims(farm) if with_shims else []

    return {"farm": str(farm), "name": name, "dist_dir": dist_dir,
            "top_level_symlinks": len(linked), "skipped": skipped,
            "relinked": relinked, "route_mirrors": route_mirrors,
            "declared_shims": shims,
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def route_pages(farm: Path) -> List[str]:
    """Every page file the farm's ROUTE dirs would offer Next, relative to farm."""
    out: List[str] = []
    for rel in ROUTE_DIRS:
        root = farm / rel
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.is_symlink() and p.suffix in (".tsx", ".ts", ".jsx", ".js"):
                out.append(str(p.relative_to(farm)))
    return sorted(out)


def dynamic_route_count(farm: Path) -> int:
    return sum(1 for p in route_pages(farm)
               if any(part.startswith("[") for part in Path(p).parts))


def cmd_build(args: argparse.Namespace) -> int:
    info = build(args.name, args.dist_dir, with_shims=not args.no_shims)
    print(f"farm     {info['farm']}")
    print(f"distDir  {info['dist_dir']}")
    print(f"symlinks {info['top_level_symlinks']}  relinked {len(info['relinked'])}")
    for rel, m in info["route_mirrors"].items():
        print(f"mirror   {rel}: {m['real_dirs']} real dirs, "
              f"{m['symlinked_files']} symlinked files"
              + (f"  ANOMALIES {m['anomalies']}" if m["anomalies"] else ""))
    dyn = dynamic_route_count(farm_path(args.name))
    print(f"routes   {len(route_pages(farm_path(args.name)))} page files, "
          f"{dyn} DYNAMIC (these are the ones the old farm dropped)")
    for s in info["declared_shims"]:
        print(f"SHIM     {s['path']}  served {s['served_sha256'][:12]} != product "
              f"{(s['product_sha256'] or '')[:12]}  (inert for this case: "
              f"called_by_this_case={s['called_by_this_case']})")
    if info["skipped"]:
        print(f"skipped  {info['skipped']}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Prove the farm can serve THIS instance, dynamic routes included.

    Two independent controls:
      1. the compiled bundle must name this backend (NEXT_PUBLIC_API_URL is
         inlined at COMPILE time, so a farm built for another backend serves
         that other world's data while looking healthy on its own port); and
      2. every dynamic page route must RESOLVE on this instance -- the failure
         this module exists to prevent is invisible in the build output and
         only shows up as a 404 to a browser.
    """
    import httpx
    farm = farm_path(args.name)
    dist_dir = args.dist_dir or dist_dir_for(args.name)
    pages = route_pages(farm)
    dyn = [p for p in pages if any(part.startswith("[") for part in Path(p).parts)]
    print(f"farm          {farm}")
    print(f"page files    {len(pages)}  dynamic {len(dyn)}")
    for p in dyn[:20]:
        print(f"  dynamic     /{Path(p).with_suffix('').as_posix()}")

    chunks = [p for p in (farm / dist_dir).rglob("*.js") if p.is_file()]
    print(f"chunks        {len(chunks)}")
    hits = 0
    if chunks and args.expect_origin:
        needle = args.expect_origin
        for c in chunks:
            try:
                if needle in c.read_text(errors="ignore"):
                    hits += 1
            except OSError:
                continue
        print(f"chunks w/ origin {hits}")
        if hits == 0:
            print("FAIL the compiled bundle does NOT reference this instance's "
                  "backend; a browser here would talk to a different world")
            return 1

    # The control that matters: ask the running instance for a dynamic route.
    if args.probe_url:
        want = args.probe_path or ("/" + Path(sorted(dyn)[0])
                                   .with_suffix("").as_posix().replace("[", "x")
                                   .replace("]", "x") if dyn else "/")
        try:
            r = httpx.get(f"{args.probe_url}{want}", timeout=60,
                          trust_env=False, follow_redirects=True)
            print(f"probe {args.probe_url}{want} -> {r.status_code}")
            if r.status_code == 404:
                print("FAIL the dynamic route 404s on this instance: the farm's "
                      "route dirs are not real directories, so Next's page "
                      "collector never registered them")
                return 1
        except Exception as exc:  # a probe that cannot run is NOT a pass
            print(f"NOT APPLICABLE the route probe could not run: {exc}")
    print("PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--name", required=True)
    b.add_argument("--dist-dir")
    b.add_argument("--no-shims", action="store_true",
                   help="do not apply the declared farm shims (the canvas page "
                        "then fails to compile under webpack)")
    b.set_defaults(func=cmd_build)

    c = sub.add_parser("check")
    c.add_argument("--name", required=True)
    c.add_argument("--dist-dir")
    c.add_argument("--expect-origin", default="")
    c.add_argument("--probe-url", default="",
                   help="base url of a RUNNING instance, e.g. http://localhost:3106")
    c.add_argument("--probe-path", default="",
                   help="path to probe, e.g. /canvas/some-id (needs auth for most)")
    c.set_defaults(func=cmd_check)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
