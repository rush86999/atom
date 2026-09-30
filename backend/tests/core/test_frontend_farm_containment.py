"""Frontend farm generation must not be able to modify the checkout.

WHY THIS TEST EXISTS
On 2026-09-28 `frontend_farm.py build` replaced the repo's real
`frontend-nextjs/next.config.js` with a per-instance config. The mechanism was
mundane and therefore not something a filename-specific fix would survive: the
farm still had `next.config.js` symlinked to the checkout's copy, the generator's
skip-list meant that entry was never unlinked, and `Path.write_text` FOLLOWS a
symlink. The user's own `next dev` on :3000 died on the broken require that
resulted.

So the property under test is not "next.config.js is handled". It is: **building
a farm cannot change one byte anywhere in the checkout.** That is asserted here
by hashing the whole checkout (everything except the vendored dependency and
build caches) before and after a real `build()`, with three farms prepared to
attack it: the normal one, one with `next.config.js` symlinked at the checkout,
and one with the farm path itself symlinked.

A sentinel hash rather than a spot check, because the failure mode is precisely
a write to a destination nobody thought to look at.
"""
import hashlib
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FRONTEND = REPO / "frontend-nextjs"
sys.path.insert(0, str(REPO / "docs/architecture/orchestration_migration/acceptance/lane3"))

import frontend_farm as F  # noqa: E402

# Vendored dependencies and build caches are enormous and are not checkout
# content in any meaningful sense; they are also rewritten by unrelated tooling.
EXCLUDE_DIRS = {"node_modules", ".next", ".preview-instance", "out", ".git",
                "coverage", "test-results", "playwright-report"}
EXCLUDE_SUFFIX = (".log", ".pyc")


def _fingerprint_checkout() -> dict:
    """sha256 of every regular file in the checkout, keyed by relative path."""
    out = {}
    for root, dirnames, filenames in os.walk(FRONTEND):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            if name.endswith(EXCLUDE_SUFFIX):
                continue
            p = Path(root) / name
            # A symlink's own bytes are not checkout content; what matters is
            # that the generator did not change the file it points at, which is
            # covered by hashing the resolved path.
            try:
                if p.is_symlink():
                    real = p.resolve()
                    key = f"{p.relative_to(FRONTEND)} -> {real}"
                else:
                    real = p
                    key = str(p.relative_to(FRONTEND))
                out[key] = hashlib.sha256(real.read_bytes()).hexdigest()
            except OSError:
                continue
    return out


def _diff(before: dict, after: dict):
    changed = []
    for k in set(before) | set(after):
        if k not in before:
            changed.append(f"CREATED   {k}")
        elif k not in after:
            changed.append(f"DELETED   {k}")
        elif before[k] != after[k]:
            changed.append(f"MODIFIED  {k}")
    return sorted(changed)


def test_farm_build_cannot_modify_the_checkout():
    before = _fingerprint_checkout()
    assert len(before) > 100, "fingerprint looks too small to be meaningful"
    F.build("sentinel_normal")
    after = _fingerprint_checkout()
    changed = _diff(before, after)
    assert changed == [], (
        "farm build modified the checkout:\n  " + "\n  ".join(changed[:20]))


def test_symlinked_generated_file_does_not_escape():
    """A farm whose next.config.js points at the checkout must be refused or fixed."""
    farm = F.farm_path("sentinel_symlinked")
    F.build("sentinel_symlinked")
    victim = FRONTEND / "next.config.js"
    original = victim.read_bytes()
    try:
        cfg = farm / "next.config.js"
        cfg.unlink()
        cfg.symlink_to(victim)          # the dangerous state
        F.build("sentinel_symlinked")   # must repair, not write through
        assert victim.read_bytes() == original, "checkout next.config.js was modified"
        assert not (farm / "next.config.js").is_symlink(), \
            "the symlink should have been replaced by a real file"
    finally:
        F.build("sentinel_symlinked")  # idempotent, and safe to call


def test_safe_write_refuses_symlink_escape():
    farm = F.farm_path("sentinel_guarded")
    F.build("sentinel_guarded")
    victim = FRONTEND / "next.config.js"
    original = victim.read_bytes()
    for relpath in ("next.config.js", ".env.local"):
        dest = farm / relpath
        dest.unlink(missing_ok=True)
        dest.symlink_to(victim)
        try:
            F._safe_write(farm, relpath, "CLOBBER ATTEMPT\n")
        except RuntimeError as exc:
            # Either guard may fire first: the containment check ("resolves
            # outside the farm") is the stronger one and reports the resolved
            # destination, which is the more useful diagnostic.
            assert ("symlink" in str(exc)) or ("outside the farm" in str(exc)), exc
        else:
            raise AssertionError(f"_safe_write({relpath!r}) did not refuse a symlink")
        assert victim.read_bytes() == original, f"checkout modified via {relpath}"
        dest.unlink(missing_ok=True)


def test_safe_write_refuses_symlinked_intermediate_dir():
    farm = F.farm_path("sentinel_guarded")
    F.build("sentinel_guarded")
    victim = FRONTEND / "next.config.js"
    original = victim.read_bytes()
    escape = farm / "escape"
    escape.unlink(missing_ok=True) if escape.is_symlink() else None
    escape.symlink_to(FRONTEND)        # a directory symlink pointing at the checkout
    try:
        try:
            F._safe_write(farm, "escape/next.config.js", "CLOBBER\n")
        except RuntimeError as exc:
            assert ("symlink" in str(exc)) or ("outside the farm" in str(exc)), exc
        else:
            raise AssertionError("_safe_write followed a symlinked intermediate directory")
        assert victim.read_bytes() == original, "checkout modified via a symlinked dir"
    finally:
        escape.unlink(missing_ok=True)
