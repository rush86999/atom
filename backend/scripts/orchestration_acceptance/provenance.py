"""Provenance: prove which code a preview instance is actually serving.

WHY THIS EXISTS
The 2026-09-27 candidate_fix1 investigation produced a launch descriptor and
a ``loaded_modules`` block that both *looked* like a source fingerprint and
were not one:

  * ``preview_stack.loaded_module_fingerprint`` ran ``importlib.import_module``
    against the world's read-only ``code/`` export. The import was allowed to
    fail, and the resulting ``import_ok: false`` entries were recorded and
    ignored. Three of the twenty key modules -- ``main_api_app``,
    ``integrations.chat_orchestrator`` and ``integrations.chat_routes`` --
    reported ``PermissionError`` while the server demonstrably imported and
    served all three. The block was therefore describing the probe's
    environment, not the serving process.
  * Nothing compared the export's hashes against anything the *running*
    process had loaded. The world ran a ``chat_orchestrator.py`` of 807,512
    bytes while the live checkout held 818,829 bytes, and the descriptor
    reported no discrepancy because it never asked the question.

So the fingerprint was structurally incapable of failing. This module splits
the problem into the two questions that were being conflated:

  1. ``static_resolve`` -- which file WOULD this world import for these module
     names? Answered with ``importlib.machinery.PathFinder.find_spec``, which
     resolves a spec by walking ``sys.path`` WITHOUT executing any module
     body. That matters because a world export is immutable: executing an
     entrypoint touches ``<backend>/data`` and against a read-only export it
     raises ``PermissionError`` for reasons that say nothing about identity.
     A spec walk is read-only, so it works on an immutable export.
  2. ``serving_report`` -- which files DID the serving process import? Read
     from ``sys.modules`` inside the serving process, so it is an observation
     rather than an inference. It also enumerates every module loaded from
     outside the world, which is how a silent fallback to the mutable
     checkout gets caught.

Both halves are required to agree, by path AND by hash, before a provenance
pass is recorded. Any error in either half is a failure, never a warning: a
check that cannot answer must not be able to pass.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "static_resolve",
    "serving_report",
    "compare",
    "write_report",
    "sha256_file",
]


def sha256_file(path: str) -> Optional[str]:
    """sha256 of a file, or None when it cannot be read.

    A None is a failure signal, not a value to be smoothed over: a fingerprint
    that silently omits an unreadable module is the defect this module exists
    to remove.
    """
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _split_dotted(name: str) -> List[str]:
    return name.split(".")


def _find_spec_no_exec(name: str, roots: Sequence[str]) -> Tuple[Optional[str], Optional[str]]:
    """Resolve ``name`` to a file path without importing anything.

    Returns ``(origin, error)``. Walks the dotted path one component at a time
    so parent packages are never executed: ``PathFinder`` only inspects the
    filesystem, so ``integrations.chat_orchestrator`` resolves without
    ``integrations/__init__.py`` ever running.
    """
    search: List[str] = [r for r in roots if r]
    origin: Optional[str] = None
    for part in _split_dotted(name):
        try:
            spec = importlib.machinery.PathFinder.find_spec(part, search)
        except (ImportError, AttributeError, ValueError) as exc:
            return None, f"{type(exc).__name__}: {exc}"
        if spec is None:
            return None, f"not found on {';'.join(search) or '<empty path>'}"
        origin = spec.origin
        if origin in (None, "built-in", "frozen"):
            return None, f"non-file origin {origin!r}"
        search = list(spec.submodule_search_locations or [])
        if not search and len(_split_dotted(name)) > 1:
            # A namespace package exposes no __init__; keep looking beside the
            # resolved parent rather than giving up.
            search = [os.path.dirname(origin)]
    if not origin:
        return None, "no origin"
    return os.path.realpath(origin), None


def static_resolve(names: Iterable[str], roots: Sequence[str]) -> Dict[str, Any]:
    """Expected identity of each module, read from disk only.

    ``roots`` are searched in order, mirroring ``sys.path`` precedence.
    """
    out: Dict[str, Any] = {}
    for name in names:
        rec: Dict[str, Any] = {"expected_roots": list(roots)}
        origin, err = _find_spec_no_exec(name, roots)
        if err:
            rec["resolve_error"] = err
            rec["resolved_from"] = None
            rec["sha256"] = None
        else:
            rec["resolved_from"] = origin
            rec["sha256"] = sha256_file(origin) if origin else None
            if rec["sha256"] is None:
                rec["resolve_error"] = f"unreadable: {origin}"
        out[name] = rec
    return out


def _allowed_prefixes(farm_root: Optional[str]) -> List[str]:
    """Roots a module may legitimately come from.

    The world is not the only legitimate source: the interpreter's own stdlib
    and site-packages are, by definition, not world code. Flagging ``__future__``
    or ``collections.abc`` as a bleed would make the check cry wolf on the first
    real run and train everyone to ignore it. What MUST be empty is the mutable
    checkout -- that is the whole failure being guarded against.
    """
    roots: List[str] = []
    if farm_root:
        roots.append(os.path.realpath(farm_root))
    try:
        import sysconfig
        for key in ("stdlib", "platstdlib", "purelib", "platlib"):
            p = sysconfig.get_paths().get(key)
            if p:
                roots.append(os.path.realpath(p))
    except Exception:  # noqa: BLE001 - a missing sysconfig must not skip stdlib
        pass
    for p in (sys.prefix, sys.base_prefix):
        if p:
            roots.append(os.path.realpath(p))
    return [r for r in roots if r]


def _under(real: str, root: str) -> bool:
    return real == root or real.startswith(root + os.sep)


def _world_roots(farm_root: Optional[str], world_root: Optional[str]) -> List[str]:
    """Roots that count as "this world".

    Both halves count: the runnable farm the server imports from, and the
    immutable ``code/`` export the fingerprint hashes. They are different
    directories holding the same content by construction.

    This distinction is load-bearing because the worlds tree lives INSIDE the
    mutable checkout (``backend/data/acceptance_worlds``). A naive
    "is it under the checkout?" test therefore flags the world itself, which is
    how the first run of this check reported ``accounting`` -- a module that had
    loaded perfectly, from the world's own export -- as a checkout bleed.
    """
    roots: List[str] = []
    for r in (farm_root, world_root):
        if r:
            real = os.path.realpath(r)
            roots.append(real)
            roots.append(os.path.join(real, "code"))
            roots.append(os.path.join(real, "backend_root"))
    seen, out = set(), []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def serving_report(
    names: Iterable[str],
    farm_root: Optional[str] = None,
    mutable_root: Optional[str] = None,
    world_root: Optional[str] = None,
    harness_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Observed identity of each module inside the ALREADY RUNNING process.

    Called from inside the serving process after the app is imported, so
    ``sys.modules`` reflects real imports.

    ``mutable_root`` is the live checkout the world was copied from. A module
    resolved from THERE -- and from nowhere inside the world -- is the failure
    that matters: the world is supposed to serve its own export, and a silent
    fallback to the mutable tree makes the whole fingerprint meaningless while
    still looking healthy. That is a hard error.

    ``harness_root`` exempts the acceptance harness itself. The launcher
    deliberately runs from the live checkout rather than the world copy, so that
    ``scripts/restart_backend.sh``'s ``pkill -f "uvicorn main_api_app:app"``
    -- which matches on the full command line -- cannot sweep an isolated
    acceptance server when another stream restarts the live backend. The
    harness is therefore *supposed* to come from the repo; flagging it would
    flag the isolation mechanism as a breach. Only the application code the
    world exists to pin is in scope.
    """
    names = list(names)
    out: Dict[str, Any] = {"modules": {}, "outside_world": [], "mutable_bleed": []}
    farm = os.path.realpath(farm_root) if farm_root else None
    mutable = os.path.realpath(mutable_root) if mutable_root else None
    harness = os.path.realpath(harness_root) if harness_root else None
    world_roots = _world_roots(farm, world_root)
    interp = _allowed_prefixes(None)

    for name in names:
        mod = sys.modules.get(name)
        rec: Dict[str, Any] = {}
        if mod is None:
            rec["import_error"] = "not in sys.modules (never imported by the server)"
            rec["resolved_from"] = None
            rec["sha256"] = None
        else:
            raw = getattr(mod, "__file__", None)
            if not raw:
                rec["import_error"] = f"no __file__ (origin={getattr(mod, '__spec__', None) and getattr(mod.__spec__, 'origin', None)!r})"
                rec["resolved_from"] = None
                rec["sha256"] = None
            else:
                real = os.path.realpath(raw)
                rec["resolved_from"] = real
                rec["sha256"] = sha256_file(real)
                if rec["sha256"] is None:
                    rec["import_error"] = f"unreadable: {real}"
        out["modules"][name] = rec

    if world_roots:
        for name, mod in list(sys.modules.items()):
            raw = getattr(mod, "__file__", None)
            if not raw:
                continue
            try:
                real = os.path.realpath(raw)
            except (OSError, ValueError):
                continue
            in_world = any(_under(real, r) for r in world_roots)
            if in_world:
                continue
            if harness and _under(real, harness):
                continue  # the harness is meant to run from the checkout
            # Interpreter and its site-packages are checked BEFORE the mutable
            # checkout, and the order is load-bearing. The project's venv lives
            # at backend/venv314, i.e. INSIDE the mutable root, so testing
            # "mutable" first flags every third-party dependency -- PIL, mypyc,
            # numpy -- as a checkout bleed. Dependencies are not app code and
            # are not what this check is about; the world's farm deliberately
            # runs on the same interpreter.
            if any(_under(real, r) for r in interp):
                continue
            if mutable and _under(real, mutable):
                out["mutable_bleed"].append({"module": name, "path": real})
            else:
                out["outside_world"].append({"module": name, "path": real})
    out["mutable_bleed"].sort(key=lambda r: (r["path"], r["module"]))
    out["outside_world"].sort(key=lambda r: (r["path"], r["module"]))
    return out


def compare(expected: Dict[str, Any], observed: Dict[str, Any]) -> Dict[str, Any]:
    """Decide a provenance pass/fail from the two halves.

    The two halves deliberately name files at DIFFERENT paths and that is not
    a discrepancy: ``expected`` is read from the immutable export
    (``<world>/code/backend``) while the server necessarily imports from its
    runnable copy (``<world>/backend_root``). The export exists precisely so
    the runnable copy cannot be edited after the fact, so CONTENT is the
    identity that matters. The comparison is therefore by sha256; path
    containment inside the world is asserted separately via
    ``outside_world``, and the observed path is reported for the record.

    Passes only when every required module resolved on disk, is present in
    ``sys.modules`` in the serving process, hashes identically, and nothing was
    imported from outside the world.
    """
    modules = (observed or {}).get("modules") or {}
    outside = (observed or {}).get("outside_world") or []
    bleed = (observed or {}).get("mutable_bleed") or []
    mismatches: List[Dict[str, Any]] = []
    errors: List[str] = []
    matched = 0

    for name, exp in (expected or {}).items():
        got = modules.get(name)
        if exp.get("resolve_error"):
            errors.append(f"{name}: static resolve failed: {exp['resolve_error']}")
            continue
        if got is None:
            errors.append(f"{name}: absent from the serving process report")
            continue
        if got.get("import_error"):
            errors.append(f"{name}: {got['import_error']}")
            continue
        if got.get("sha256") != exp.get("sha256"):
            mismatches.append({
                "module": name,
                "field": "sha256",
                "expected_export": exp.get("sha256"),
                "observed_serving": got.get("sha256"),
                "expected_path": exp.get("resolved_from"),
                "observed_path": got.get("resolved_from"),
            })
        else:
            matched += 1

    for b in bleed:
        errors.append(
            f"{b['module']} was imported from the MUTABLE CHECKOUT, not the "
            f"world: {b['path']}")
    for item in outside:
        errors.append(
            f"{item['module']} was imported from outside the world and outside "
            f"the interpreter: {item['path']}")

    return {
        "provenance_ok": not errors and not mismatches,
        "checked": len(expected or {}),
        "matched": matched,
        "errors": errors,
        "mismatches": mismatches,
        "mutable_bleed_count": len(bleed),
        "outside_world_count": len(outside),
    }


def write_report(report: Dict[str, Any], path: str) -> None:
    """Persist a report atomically so a reader never sees a half file."""
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
