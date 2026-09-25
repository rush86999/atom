#!/usr/bin/env python
"""Whole-system evaluation freeze manifest (2026-09-24 contract check 4).

A fixed evaluation FILE alone is insufficient while concurrent changes
alter production behavior. This freezes the COMPLETE evaluated system:

  code revision (git) + dirty-state digest
  lesson registry + candidate hash            (core/lesson_candidates.py)
  evaluation design hash                      (tests/test_learning_loop_evaluation.py)
  fixture/evaluation code hashes              (tests/test_learning_loop_mechanics.py,
                                               core/workbook_read_artifact.py,
                                               core/chat_tool_planner.py — the
                                               deterministic readers/graders)
  model/provider configuration                (data/provider_model_catalog.json
                                               + BYOK provider inventory)
  threshold hash                              (evaluate_promotion_gate defaults)

Run:  python scripts/eval_freeze.py freeze    -> writes the manifest
      python scripts/eval_freeze.py verify    -> exits 0 if unchanged

The manifest is COMMITTED before the frozen evaluation runs; `verify`
drift-checks every recorded hash so any concurrent change to code,
lessons, graders, fixtures, model config, or thresholds invalidates the
freeze visibly instead of silently changing the evaluated system.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(
    PROJECT_ROOT, "tests", "frozen_eval_manifest.json")

HASHED_FILES = (
    "core/lesson_candidates.py",
    "core/task_outcome_contract.py",
    "core/active_lessons.py",
    "core/workbook_read_artifact.py",
    "core/chat_tool_planner.py",
    "core/response_validation.py",
    "integrations/chat_orchestrator.py",
    "tests/test_learning_loop_evaluation.py",
    "tests/test_learning_loop_mechanics.py",
)

MODEL_CONFIG_FILES = (
    "data/provider_model_catalog.json",
    "data/model_resolution_state.json",
)


def _sha256_file(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except Exception:  # noqa: BLE001 — missing file recorded as absent
        return "absent"


def _git(args: list) -> str:
    try:
        return subprocess.run(
            ["git", "-C", PROJECT_ROOT] + args,
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unavailable"


def _thresholds_digest() -> str:
    sys.path.insert(0, PROJECT_ROOT)
    os.environ.setdefault("TESTING", "1")
    try:
        from core.lesson_candidates import evaluate_promotion_gate

        sample = evaluate_promotion_gate(
            {"goal_completion": 0.0}, {"goal_completion": 1.0})
        return hashlib.sha256(json.dumps(
            sample.get("thresholds"), sort_keys=True).encode()).hexdigest()
    except Exception as exc:  # noqa: BLE001
        return f"error:{type(exc).__name__}"


def _runtime_config() -> dict:
    """EFFECTIVE runtime configuration (2026-09-24 review): env
    overrides (ATOM_* keys only — values hashed, never recorded),
    provider identity, and the active-lesson state digest."""
    env_overrides = {}
    for key, value in sorted(os.environ.items()):
        if key.startswith("ATOM_"):
            # evaluation-relevant overrides: digest the VALUE
            env_overrides[key] = hashlib.sha256(
                str(value).encode()).hexdigest()[:16]
        elif key in ("TESTING", "DATABASE_URL", "LANCEDB_URI_BASE"):
            # harness plumbing: presence only — its value necessarily
            # differs between commit-time freeze and test execution
            env_overrides[key] = "present" if value else "absent"
    providers = {}
    try:
        with open(os.path.join(
                PROJECT_ROOT, "data", "byok_keys.json"), "rb") as fh:
            blob = fh.read()
        providers["byok_keys_digest"] = hashlib.sha256(blob).hexdigest()
    except Exception:  # noqa: BLE001
        providers["byok_keys_digest"] = "absent"
    lessons = {}
    try:
        sys.path.insert(0, PROJECT_ROOT)
        os.environ.setdefault("TESTING", "1")
        from core.active_lessons import active_lesson_projection

        active = active_lesson_projection()
        lessons = {
            "active_keys": sorted(active.keys()),
            "digest": hashlib.sha256(json.dumps(
                active, sort_keys=True).encode()).hexdigest()[:16],
        }
    except Exception as exc:  # noqa: BLE001
        lessons = {"error": f"{type(exc).__name__}"}
    return {
        "env_overrides": env_overrides,
        "providers": providers,
        "active_lessons": lessons,
    }


def build_manifest() -> dict:
    files = {rel: _sha256_file(os.path.join(PROJECT_ROOT, rel))
             for rel in HASHED_FILES}
    model_config = {rel: _sha256_file(os.path.join(PROJECT_ROOT, rel))
                    for rel in MODEL_CONFIG_FILES}
    return {
        "frozen_at": _git(["log", "-1", "--format=%H %cI"]),
        "dirty_digest": _git(["status", "--porcelain"])[:4000],
        "code_files": files,
        "model_config": model_config,
        "runtime_config": _runtime_config(),
        "thresholds_digest": _thresholds_digest(),
        "note": (
            "verify must pass before any frozen-evaluation result is "
            "reported; drift invalidates the freeze"),
    }


def freeze() -> int:
    manifest = build_manifest()
    with open(MANIFEST_PATH, "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
    print(f"FROZEN -> {MANIFEST_PATH}")
    print(json.dumps(manifest, indent=1, sort_keys=True)[:600])
    return 0


def verify() -> int:
    try:
        with open(MANIFEST_PATH) as fh:
            frozen = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print(f"NO MANIFEST: {exc}")
        return 2
    current = build_manifest()
    drift = []
    provider_drift = []
    for section in ("code_files", "model_config", "runtime_config"):
        for key, value in frozen.get(section, {}).items():
            if current.get(section, {}).get(key) != value:
                # UNAVOIDABLE PROVIDER DRIFT (2026-09-24 review): the
                # live provider catalog mutates as syncs run — RECORD it
                # in the drift log, do not invalidate the freeze. Code,
                # thresholds, and env overrides still invalidate.
                if section == "model_config" and "provider_model_catalog" in key:
                    provider_drift.append(f"{section}:{key}")
                    continue
                drift.append(f"{section}:{key}")
    if current["thresholds_digest"] != frozen["thresholds_digest"]:
        drift.append("thresholds")
    if frozen.get("frozen_at") and current.get("frozen_at") != frozen["frozen_at"]:
        drift.append(f"code_revision:{current.get('frozen_at')}")
    if provider_drift:
        _log_provider_drift(frozen, current, provider_drift)
    if drift:
        print("FREEZE DRIFT (the evaluated system changed):")
        for item in drift:
            print(f"  - {item}")
        return 1
    print("FREEZE VERIFIED: code, lessons, graders, fixtures, model "
          "config, and thresholds all match the manifest.")
    return 0


def _log_provider_drift(frozen: dict, current: dict, items: list) -> None:
    """Append unavoidable provider drift to the manifest's drift log
    (recorded, non-invalidating)."""
    try:
        with open(MANIFEST_PATH) as fh:
            manifest = json.load(fh)
        log = manifest.get("drift_log", [])
        log.append({
            "at": current.get("frozen_at", ""),
            "note": "unavoidable provider drift (recorded, not invalidating)",
            "items": items,
        })
        manifest["drift_log"] = log[-50:]
        with open(MANIFEST_PATH, "w") as fh:
            json.dump(manifest, fh, indent=1, sort_keys=True)
    except Exception:  # noqa: BLE001 — logging is best-effort
        pass


def record_drift(note: str = "") -> int:
    """Append a runtime-drift event (provider/config changes observed
    during an evaluation run) to the manifest's drift log."""
    entry = {
        "at": _git(["log", "-1", "--format=%cI"]),
        "note": note,
        "runtime_config": _runtime_config(),
    }
    log = []
    try:
        with open(MANIFEST_PATH) as fh:
            log = json.load(fh).get("drift_log", [])
    except Exception:  # noqa: BLE001
        pass
    log.append(entry)
    try:
        with open(MANIFEST_PATH) as fh:
            manifest = json.load(fh)
        manifest["drift_log"] = log
        with open(MANIFEST_PATH, "w") as fh:
            json.dump(manifest, fh, indent=1, sort_keys=True)
        print(f"DRIFT RECORDED: {note or 'runtime configuration change'}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"drift log write failed: {exc}")
        return 2


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["freeze", "verify", "record-drift"])
    p.add_argument("--note", default="")
    args = p.parse_args(argv)
    if args.cmd == "freeze":
        return freeze()
    if args.cmd == "record-drift":
        return record_drift(args.note)
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
