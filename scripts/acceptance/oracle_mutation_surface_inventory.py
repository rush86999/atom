#!/usr/bin/env python3
"""Inventory whole-app mutation surfaces and ORACLE verifier coverage.

This is a static coverage matrix, not a qualification run. It answers:

* which registered action classes mutate external/provider or local state;
* which of those have an oracle postcondition verifier;
* how many mutating HTTP routes exist outside the action registry;
* how many provider-adapter write methods exist.

Run from the repository root:

    PYTHONPATH=backend python scripts/acceptance/oracle_mutation_surface_inventory.py \
        --out docs/acceptance/evidence/oracle_whole_app_inventory_20261102
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from core.action_effects import (
    declares_mutation,
    declares_plan_output,
    declares_read_only,
    effect_entries,
)

EXTERNAL_EFFECTS = {
    "create", "update", "delete", "write", "send", "execute",
}
PLAN_OUTPUT_ACTIONS = {"goals.decompose"}
LOCAL_MUTATING_ACTIONS = {
    "canvas.present_chart", "canvas.present_markdown", "canvas.restore_version",
    "canvas.update", "tasks.create",
}
HTTP_MUTATING_METHODS = {"post", "put", "patch", "delete"}
WRITE_PREFIXES = (
    "create_", "update_", "delete_", "send_", "post_", "upload_", "connect_",
    "disconnect_", "revoke_", "refresh_", "restore_", "approve_", "cancel_",
    "start_", "complete_", "execute_", "run_", "write_", "save_", "present_",
)
HIGH_RISK_MARKERS = (
    "create", "update", "delete", "send", "post", "upload", "connect",
    "disconnect", "revoke", "refresh", "restore", "approve", "cancel", "start",
    "complete", "execute", "run", "write", "save", "present", "submit",
)


def _source() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001 - inventory still runs outside git
        return "unknown"


def _kinds(effects: Iterable[Any]) -> List[str]:
    return sorted({
        str(item.get("effect") if isinstance(item, dict) else item)
        for item in effects or []
    })


def _registered_actions() -> Dict[str, Any]:
    import core.connected_actions  # noqa: F401 - register connected actions
    import core.oracle.postcondition_verifiers  # noqa: F401
    from core.action_registry import action_registry
    from core.oracle import _VERIFIERS

    rows = []
    for name in sorted(action_registry.list_actions()):
        action = action_registry.get_action(name)
        effects = effect_entries(getattr(action, "effects", None) or [])
        kinds = _kinds(effects)
        lower = {kind.lower() for kind in kinds}
        scopes = {
            str(item.get("scope") or "").strip().lower()
            for item in effects
            if isinstance(item, dict)
        }
        if declares_mutation(effects):
            if "local" in scopes:
                classification = "local_mutation"
            elif "external" in scopes or lower & EXTERNAL_EFFECTS:
                classification = "external_mutation"
            else:
                classification = "mutation_unscoped"
        elif declares_plan_output(effects) or name in PLAN_OUTPUT_ACTIONS:
            classification = "plan_output_validation"
        elif declares_read_only(effects):
            classification = "read_only"
        elif name in LOCAL_MUTATING_ACTIONS:
            classification = "local_mutation"
        else:
            classification = "undeclared"
        rows.append({
            "action": name,
            "effects": kinds,
            "scopes": sorted(scopes - {""}),
            "classification": classification,
            "verifier_registered": name in _VERIFIERS,
            "description": (getattr(action, "description", "") or "")[:180],
        })
    return {
        "actions": rows,
        "verifiers": sorted(_VERIFIERS),
        "total": len(rows),
    }


def _route_scan(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    rows = []
    for root in paths:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for decorator in node.decorator_list:
                    call = decorator if isinstance(decorator, ast.Call) else None
                    if not call or not isinstance(call.func, ast.Attribute):
                        continue
                    method = call.func.attr.lower()
                    if method not in HTTP_MUTATING_METHODS:
                        continue
                    route = ""
                    if call.args and isinstance(call.args[0], ast.Constant):
                        route = str(call.args[0].value)
                    rows.append({
                        "file": str(path),
                        "function": node.name,
                        "method": method.upper(),
                        "route": route,
                    })
    return rows


def _provider_writes(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    rows = []
    for root in paths:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for item in node.body:
                    if not isinstance(
                            item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if not item.name.startswith(WRITE_PREFIXES):
                        continue
                    rows.append({
                        "file": str(path),
                        "class": node.name,
                        "method": item.name,
                    })
    return rows


def _high_risk(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for row in rows:
        haystack = f"{row['function']} {row['route']}".lower()
        if any(marker in haystack for marker in HIGH_RISK_MARKERS):
            result.append(row)
    return result


def _by_file(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Counter = Counter()
    for row in rows:
        counts[row["file"]] += 1
    return dict(counts.most_common())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--source", default="",
                        help="code source to record (defaults to HEAD)")
    parser.add_argument(
        "--registry-only", action="store_true",
        help="emit only the registered-action / verifier matrix")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    registered = _registered_actions()
    routes = [] if args.registry_only else _route_scan([
        repo / "backend/api",
        repo / "backend/integrations",
    ])
    writes = [] if args.registry_only else _provider_writes([
        repo / "backend/integrations"])
    high_risk = _high_risk(routes)

    external = [row for row in registered["actions"]
                if row["classification"] == "external_mutation"]
    local = [row for row in registered["actions"]
             if row["classification"] == "local_mutation"]
    mutation_unscoped = [row for row in registered["actions"]
                         if row["classification"] == "mutation_unscoped"]
    plan_output = [row for row in registered["actions"]
                   if row["classification"] == "plan_output_validation"]
    read_only = [row for row in registered["actions"]
                 if row["classification"] == "read_only"]
    undeclared = [row for row in registered["actions"]
                  if row["classification"] == "undeclared"]
    mutating = external + local + mutation_unscoped
    external_covered = [row for row in external if row["verifier_registered"]]
    local_covered = [row for row in local if row["verifier_registered"]]
    mutation_unscoped_covered = [
        row for row in mutation_unscoped if row["verifier_registered"]]
    plan_output_covered = [
        row for row in plan_output if row["verifier_registered"]]
    mutating_uncovered = [
        row["action"] for row in mutating if not row["verifier_registered"]]

    payload = {
        "schema": "atom-oracle-mutation-surface-2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": args.source.strip() or _source(),
        "registry_only": bool(args.registry_only),
        "lazy_registration_modules": [
            "core.agent_radio.radio_actions",
            "core.bpe.actions",
        ],
        "scope": (
            "Source-bound inventory of registered action effect declarations "
            "and independent postcondition verifiers. It is not a "
            "qualification run; uncovered declarations remain explicit."),
        "registered_actions": {
            "total": registered["total"],
            "external_mutation": external,
            "local_mutation": local,
            "mutation_unscoped": mutation_unscoped,
            "plan_output_validation": plan_output,
            "read_only": read_only,
            "undeclared": undeclared,
            "read_or_other_count": len(read_only),
        },
        "coverage": {
            "mutating_total": len(mutating),
            "mutating_covered": sum(
                1 for row in mutating if row["verifier_registered"]),
            "mutating_without_verifier": mutating_uncovered,
            "undeclared_actions": [row["action"] for row in undeclared],
            "external_mutation_total": len(external),
            "external_mutation_covered": len(external_covered),
            "external_mutation_uncovered": [
                row["action"] for row in external
                if not row["verifier_registered"]],
            "local_mutation_total": len(local),
            "local_mutation_covered": len(local_covered),
            "local_mutation_uncovered": [
                row["action"] for row in local
                if not row["verifier_registered"]],
            "mutation_unscoped_total": len(mutation_unscoped),
            "mutation_unscoped_covered": len(mutation_unscoped_covered),
            "plan_output_total": len(plan_output),
            "plan_output_covered": len(plan_output_covered),
            "plan_output_note": (
                "goals.decompose is structural plan-output validation; it "
                "does not prove a persisted execution or mutation."),
            "oracle_verifiers": registered["verifiers"],
        },
        "http_mutation_routes": (
            {"skipped": True} if args.registry_only else {
                "total": len(routes),
                "high_risk_total": len(high_risk),
                "by_method": dict(Counter(row["method"] for row in routes)),
                "by_file": _by_file(routes),
                "high_risk_sample": high_risk[:80],
            }),
        "provider_write_methods": (
            {"skipped": True} if args.registry_only else {
                "total": len(writes),
                "by_file": _by_file(writes),
                "sample": writes[:80],
            }),
        "gaps": [
            "Declared mutations without an independent verifier are never "
            "certified applied: the shared adapter downgrades an already "
            "dispatched effect to uncertain and preserves its identity.",
            "The uncovered names above remain explicit; add a verifier or "
            "keep them out of mutating assignment dispatch.",
            "HTTP mutation routes remain outside the registered action "
            "registry; this slice does not qualify them.",
        ],
        "next_verifiers": [
            "Add independent readback verifiers for the remaining local "
            "mini-app mutations or keep them out of mutating assignment "
            "dispatch.",
            "Provider mutations (Shopify) need authoritative readback before "
            "they can be applied through the assignment path.",
            "Plan-output validation remains structural; add persistence "
            "postconditions only where an action actually persists state.",
        ],
    }
    (out / "inventory.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Registered-action ORACLE coverage",
        "",
        f"Source: `{payload['source']}`",
        "",
        "This is a source-bound registry/verifier matrix, not a qualification "
        "run. It records the trusted effect declaration of every registered "
        "action and whether an independent postcondition verifier exists.",
        "",
        "## Registered actions",
        "",
        f"- Total registered actions: **{registered['total']}**",
        f"- Declared mutating actions: **{len(mutating)}** "
        f"({payload['coverage']['mutating_covered']} covered, "
        f"{len(mutating_uncovered)} uncovered)",
        f"  - external/provider mutations: **{len(external)}** "
        f"({len(external_covered)} covered)",
        f"  - local durable-state mutations: **{len(local)}** "
        f"({len(local_covered)} covered)",
        f"  - unscoped mutations: **{len(mutation_unscoped)}** "
        f"({len(mutation_unscoped_covered)} covered)",
        f"- Plan-output validators: **{len(plan_output)}** "
        f"({len(plan_output_covered)} covered; structural, not persisted "
        "execution proof)",
        f"- Explicit read-only actions: **{len(read_only)}**",
        f"- Undeclared actions: **{len(undeclared)}**",
        "",
        "The 90-action surface matches `core.action_registry` + "
        "`core.connected_actions` (the baseline import). Lazy modules "
        "`core.agent_radio.radio_actions` and `core.bpe.actions` also declare "
        "effects but are registered only when their surfaces load; their "
        "mutations remain unverified and follow the same uncertain-after-"
        "dispatch rule.",
    ]
    if not args.registry_only:
        lines += [
            "",
            "## HTTP and provider surfaces",
            "",
            f"- Mutating HTTP routes (POST/PUT/PATCH/DELETE) under `api/` and "
            f"`integrations/`: **{len(routes)}**",
            f"- High-risk route names/paths: **{len(high_risk)}**",
            f"- Provider-adapter write methods: **{len(writes)}**",
        ]
    lines += [
        "",
        "## Covered mutations",
        "",
    ]
    lines += [
        f"- `{row['action']}`"
        for row in external_covered + local_covered
        + mutation_unscoped_covered
    ] or ["- none"]
    lines += [
        "",
        "## Uncovered declared mutations",
        "",
    ]
    lines += [f"- `{name}`" for name in mutating_uncovered] or ["- none"]
    if undeclared:
        lines += [
            "",
            "## Undeclared actions (metadata drift; must be classified)",
            "",
        ]
        lines += [f"- `{row['action']}`" for row in undeclared]
    lines += [
        "",
        "## Highest-priority next verifiers",
        "",
    ]
    lines += [f"- {item}" for item in payload["next_verifiers"]]
    lines += [
        "",
        "## Boundary",
        "",
        "This inventory does not close a whole-app ORACLE promise. It makes "
        "the remaining uncovered registered mutations explicit and keeps "
        "plan-output validation separate from persisted execution proof.",
        "",
    ]
    (out / "README.md").write_text("\n".join(lines))
    print(json.dumps({
        "registered": registered["total"],
        "mutating": len(mutating),
        "mutating_covered": payload["coverage"]["mutating_covered"],
        "mutating_without_verifier": mutating_uncovered,
        "external_mutation": len(external),
        "external_covered": len(external_covered),
        "local_mutation": len(local),
        "local_covered": len(local_covered),
        "mutation_unscoped": len(mutation_unscoped),
        "plan_output": len(plan_output),
        "plan_output_covered": len(plan_output_covered),
        "read_only": len(read_only),
        "undeclared": [row["action"] for row in undeclared],
        "http_mutation_routes": len(routes),
        "high_risk_routes": len(high_risk),
        "provider_write_methods": len(writes),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
