"""Isolated-acceptance server launcher.

Run as a plain script (cmdline contains neither 'uvicorn' nor
'main_api_app:app'), so scripts/restart_backend.sh's
`pkill -f "uvicorn main_api_app:app"` — which matches by full command line
regardless of port — cannot sweep the isolated acceptance server when
another stream restarts the live backend.
"""
import importlib
import json
import os
import sys

sys.path.insert(0, os.getcwd())  # farm root must be importable when run as a script

# The harness scripts live in the real checkout; the app code comes from the
# farm via cwd. Both are needed here, and the order matters: the app root is
# inserted by the line above and stays ahead, so a farm module still wins.
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)

import uvicorn

import provenance


def _write_serving_provenance() -> None:
    """Record which files this process ACTUALLY imported, before serving.

    The launcher's own fingerprint resolves module names against the export on
    disk, which is an expectation. This is the observation, taken from
    ``sys.modules`` inside the process that will serve traffic, and it is the
    only half that can catch a module that resolved somewhere else at runtime.

    It is written whether or not it looks good. A module that is missing,
    unreadable, or loaded from outside the world is recorded as an error in
    the report and left for the verify gate to fail on, because a report that
    only ever records good news is the defect that let the 2026-09-27
    candidate_fix1 fingerprint pass while three of its key modules were
    unverified and one was absent from the export entirely.
    """
    out = os.environ.get("ACC_PROVENANCE_OUT")
    if not out:
        return
    try:
        names = json.loads(os.environ.get("ACC_PROVENANCE_MODULES") or "[]")
    except json.JSONDecodeError as exc:
        names = []
        report = {
            "modules": {},
            "outside_world": [],
            "fatal": f"ACC_PROVENANCE_MODULES is not valid JSON: {exc}",
        }
        provenance.write_report(report, out)
        return

    farm = os.environ.get("ACC_FARM_ROOT") or os.getcwd()
    mutable = os.environ.get("ACC_MUTABLE_ROOT") or None
    world = os.environ.get("ACC_WORLD_ROOT") or None
    harness = os.environ.get("ACC_HARNESS_ROOT") or _SCRIPTS
    report = {}
    try:
        # Import the app here rather than letting uvicorn do it lazily, so the
        # report describes the same objects that will be served. uvicorn.run
        # resolves the same dotted name and finds it already in sys.modules.
        import main_api_app  # noqa: F401

        # Then import every remaining key module explicitly. Several are only
        # reached lazily on a code path the server has not taken yet, so a
        # sys.modules snapshot taken at startup would report them as "never
        # imported" -- indistinguishable from "this world cannot load it",
        # which is the failure the check exists to catch. Importing them here
        # makes the report an actual attestation: if a module cannot be loaded
        # from the world's own export, the launch fails loudly instead of
        # discovering it mid-acceptance.
        unloaded = []
        for name in names:
            if name in sys.modules:
                continue
            try:
                importlib.import_module(name)
            except Exception as exc:  # noqa: BLE001 - recorded, then reported
                unloaded.append(f"{name}: {type(exc).__name__}: {exc}")
    except BaseException as exc:  # noqa: BLE001 - must be reported, not raised
        report = {
            "modules": {},
            "outside_world": [],
            "mutable_bleed": [],
            "fatal": f"{type(exc).__name__}: {exc}",
        }
        provenance.write_report(report, out)
        raise
    else:
        report = provenance.serving_report(names, farm_root=farm,
                                           mutable_root=mutable,
                                           world_root=world,
                                           harness_root=harness)
        report["farm_root"] = os.path.realpath(farm)
        report["mutable_root"] = os.path.realpath(mutable) if mutable else None
        report["cwd"] = os.getcwd()
        report["pid"] = os.getpid()
        if unloaded:
            report["unloadable"] = unloaded
        provenance.write_report(report, out)


if __name__ == "__main__":
    _write_serving_provenance()
    uvicorn.run(
        "main_api_app:app",
        host="127.0.0.1",
        port=int(os.environ["ACC_PORT"]),
        timeout_keep_alive=75,
    )
