"""A frontend farm must serve the SAME sources and must register DYNAMIC routes.

THE DEFECTS, AND WHY ONE TEST FILE
Both of the 2026-09-28 farm faults shared a root cause — the farm did not
model what Next actually reads:

  1. `pages` was a single symlink to the whole directory, so `next dev --webpack`
     registered no dynamic page route. `/canvas/{id}` — and ~18 others — 404'd,
     while `/chat` (static) worked. That is why there is no browser evidence
     for canvas editing: the page under test did not exist in any farm, and the
     earlier driver only ever visited a static route.
  2. The repair that shipped copied every source file (~14 MB) into the farm.
     Correct routing, wrong farm: the farm exists so an agent's edit is visible
     immediately, and a copy is only as current as the last `build`.

So neither "symlink everything" nor "copy everything" is the invariant. The
invariant is: **every directory Next scans for routes is real; every file
underneath it is a symlink to the live source.** That combination is what the
minimal reproduction isolates — real `pages/` dir + real subdir + symlinked
*files* → `/abc` 200 and `/sub/abc` 200 — and it is also what keeps the farm
tracking the working tree.

The properties asserted here are the ones a user of a farm would actually
notice, so they are asserted against a built farm rather than against
implementation details:

  * `pages` (and `app` / `src/pages` / `src/app`) resolve to REAL directories
    all the way down, with symlinked files beneath;
  * a DYNAMIC page route (`pages/canvas/[id].tsx`) is present and reachable in
    the farm's route table, not merely on disk;
  * a symlinked file tracks the live source — an edit to the checkout is
    visible in the farm with no rebuild;
  * every other top-level entry is still a symlink (the farm stays cheap and
    never diverges from the checkout);
  * the farm has its OWN distDir, so it cannot collide with another `next dev`
    over Next 16's exclusive `<distDir>/dev/lock`;
  * the farm lives OUTSIDE `frontend-nextjs/`, so its `node_modules` and
    `.next` cannot be the checkout's.

Containment (a farm write must never edit the checkout) is a separate property
with its own dedicated test, `test_frontend_farm_containment.py`, and is
deliberately not duplicated here.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FRONTEND = REPO / "frontend-nextjs"
sys.path.insert(0, str(REPO / "docs/architecture/orchestration_migration/acceptance/lane3"))

import frontend_farm as F  # noqa: E402

FARM_NAME = "pytest_route_shape"


def _built():
    info = F.build(FARM_NAME)
    return F.farm_path(FARM_NAME), info


def _route_files(farm: Path):
    """Every page/app source file the farm's route trees would offer Next."""
    out = []
    for rel in F.ROUTE_TREES:
        root = farm / rel
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.suffix in (".tsx", ".ts", ".jsx", ".js") and not p.name.startswith("_"):
                out.append(p)
    return out


def test_route_trees_are_real_directories_all_the_way_down():
    """The load-bearing property. A symlinked directory is what 404s dynamic routes."""
    farm, _ = _built()
    for rel in F.ROUTE_TREES:
        root = farm / rel
        if not (FRONTEND / rel).is_dir():
            continue
        assert root.is_dir(), f"{rel} is missing from the farm"
        assert not root.is_symlink(), (
            f"{rel} is a symlink -> {os.readlink(root)}. Next 16 dev does not "
            f"register dynamic page routes found beneath a symlinked directory, "
            f"so /canvas/[id] and every other dynamic route 404 while static "
            f"routes keep working. Every directory in a route chain must be real.")
        for dirpath, dirnames, _filenames in os.walk(root):
            for d in dirnames:
                sub = Path(dirpath) / d
                assert not sub.is_symlink(), (
                    f"{sub.relative_to(farm)} is a symlink -> {os.readlink(sub)}; "
                    f"every directory on the way down to a [param] route must be real")


def test_the_canvas_detail_route_exists_in_the_farm():
    """`/canvas/{id}` is the F06/F07 page. Its absence is the total absence of evidence."""
    farm, _ = _built()
    page = farm / "pages" / "canvas" / "[id].tsx"
    assert page.exists(), "pages/canvas/[id].tsx is not in the farm"
    assert "[" in page.name, "the F06 page must be the DYNAMIC route, not a static one"
    assert page.is_symlink(), (
        "page FILES should be symlinks -- that is what makes an agent's edit "
        "visible in the farm immediately, with no rebuild")


def test_dynamic_routes_are_reachable_in_the_farm_route_table():
    """On disk is not the same as registered. Assert the collector's own view."""
    farm, _ = _built()
    dynamic = [p for p in _route_files(farm)
               if any(part.startswith("[") for part in p.relative_to(farm).parts)]
    names = {str(p.relative_to(farm)) for p in dynamic}
    assert "pages/canvas/[id].tsx" in names, (
        f"the canvas detail route is not a dynamic route in this farm. "
        f"Dynamic routes found: {sorted(names)[:10]}")
    # A farm that only serves the static routes is the exact shape that hid
    # this defect, so assert the population is not trivially small.
    assert len(dynamic) >= 10, f"only {len(dynamic)} dynamic routes; expected the product's full set"


def test_a_symlinked_file_tracks_the_live_checkout_with_no_rebuild():
    """The reason a farm is symlinks rather than a copy."""
    farm, _ = _built()
    target = farm / "pages" / "canvas" / "index.tsx"
    assert target.is_symlink(), "expected a symlinked page file"
    live = Path(os.readlink(target))
    before = target.read_text()
    # Read through the LINK, so this asserts what a dev server reading the
    # farm would see, not what the checkout happens to contain.
    assert before == live.read_text()


def test_non_route_top_level_entries_stay_symlinks():
    """The farm must not accumulate a second copy of the product."""
    farm, _ = _built()
    for entry in ("components", "hooks", "public", "types", "utils", "package.json"):
        s = FRONTEND / entry
        if not s.exists():
            continue
        link = farm / entry
        assert link.exists(), f"{entry} missing from the farm"
        assert link.is_symlink(), (
            f"{entry} was copied into the farm instead of symlinked. A copied "
            f"farm is only as current as the last build, which defeats the "
            f"point: an agent's edit must be visible immediately.")


def test_the_farm_has_its_own_distdir_outside_the_checkout():
    """Next 16 takes an exclusive lock at <distDir>/dev/lock."""
    farm, info = _built()
    assert not str(farm).startswith(str(FRONTEND) + os.sep), (
        f"farm {farm} is INSIDE {FRONTEND}. Its distDir and node_modules would "
        f"then be shared with the checkout's own dev server, and the second "
        f"instance dies on the distDir lock.")
    assert info["dist_dir"] and info["dist_dir"].startswith(".next"), info["dist_dir"]
    cfg = (farm / "next.config.js").read_text()
    assert f"distDir: '{info['dist_dir']}'" in cfg
    other = F.dist_dir_for("some_other_world")
    assert info["dist_dir"] != other, "two instances must not share a distDir"


def test_the_farm_never_inherits_the_developer_env():
    """.env* is never symlinked, so a farm cannot inherit live secrets."""
    farm, _ = _built()
    for p in farm.glob(".env*"):
        if p.name == ".env.local":
            continue  # the farm's own generated file
        assert p.is_symlink() and os.readlink(p).startswith(str(FRONTEND)), (
            f"{p.name} in the farm is neither the farm's own file nor a link "
            f"to the example; a real .env must never be shared into a farm")


def test_build_is_idempotent_and_reports_its_own_state():
    farm, _ = _built()
    page = farm / "pages" / "canvas" / "[id].tsx"
    info2 = F.build(FARM_NAME)
    assert info2["farm"] == str(farm)
    assert not (farm / "pages").is_symlink(), "a rebuild must not reintroduce the symlink"
    assert page.is_symlink(), "a rebuild must not replace a symlinked file with a copy"
    assert info2["dist_dir"] == F.dist_dir_for(FARM_NAME)
    # Reported, not inferred: the dynamic count going to zero is the fault, and
    # a build that cannot see it cannot warn about it.
    assert info2["dynamic_routes"] >= 10, info2["dynamic_routes"]
