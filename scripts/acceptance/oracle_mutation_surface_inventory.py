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
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

EXTERNAL_EFFECTS = {
    "create", "update", "delete", "write", "send", "execute",
}
LOCAL_EFFECTS = {
    "goal_created", "goal_run_started", "plan_produced", "goal_evaluated",
    "record_created", "graph_updated", "record_updated", "record_deleted",
}
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
        kinds = _kinds(getattr(action, "effects", None) or [])
        lower = {kind.lower() for kind in kinds}
        if lower & EXTERNAL_EFFECTS:
            classification = "external_mutation"
        elif lower & LOCAL_EFFECTS or name in LOCAL_MUTATING_ACTIONS:
            classification = "local_mutation"
        else:
            classification = "read_or_other"
        rows.append({
            "action": name,
            "effects": kinds,
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
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    registered = _registered_actions()
    routes = _route_scan([
        repo / "backend/api",
        repo / "backend/integrations",
    ])
    writes = _provider_writes([repo / "backend/integrations"])
    high_risk = _high_risk(routes)

    external = [row for row in registered["actions"]
                if row["classification"] == "external_mutation"]
    local = [row for row in registered["actions"]
             if row["classification"] == "local_mutation"]
    external_covered = [row for row in external if row["verifier_registered"]]
    local_covered = [row for row in local if row["verifier_registered"]]

    payload = {
        "schema": "atom-oracle-whole-app-mutation-surface-1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": args.source.strip() or _source(),
        "scope": (
            "Static inventory of registered action classes, mutating HTTP "
            "routes and provider-adapter write methods. It is not a "
            "qualification run and does not prove every route is reachable or "
            "externally effectful."),
        "registered_actions": {
            "total": registered["total"],
            "external_mutation": external,
            "local_mutation": local,
            "read_or_other_count": sum(
                1 for row in registered["actions"]
                if row["classification"] == "read_or_other"),
        },
        "coverage": {
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
            "oracle_verifiers": registered["verifiers"],
        },
        "http_mutation_routes": {
            "total": len(routes),
            "high_risk_total": len(high_risk),
            "by_method": dict(Counter(row["method"] for row in routes)),
            "by_file": _by_file(routes),
            "high_risk_sample": high_risk[:80],
        },
        "provider_write_methods": {
            "total": len(writes),
            "by_file": _by_file(writes),
            "sample": writes[:80],
        },
        "gaps": [
            "External provider mutations are limited to six connected "
            "estimate/bill/draft action names; no other provider write action "
            "is registered or oracle-covered.",
            "Local durable-state mutations through goals/goal_runs/canvas have "
            "at most the existing task/workflow verifiers; canvas update, "
            "present, restore and goal-run state changes are not independently "
            "postcondition-verified.",
            "HTTP mutation routes are overwhelmingly outside the registered "
            "action registry; their correctness is covered, if at all, by "
            "route/service tests rather than the oracle.",
            "Provider adapters expose many write methods; only a small subset "
            "is reachable through registered, verified actions.",
        ],
        "next_verifiers": [
            "canvas.update / canvas.restore_version: compare persisted content "
            "revision/hash against the authorized mutation and reject stale or "
            "different-object writes.",
            "canvas.present_markdown / canvas.present_chart: verify the audit "
            "record and returned canvas identity, not only the broadcast.",
            "goals.create / goal_runs.start: verify the persisted goal/run "
            "identity and state before dependent work continues.",
            "goals.decompose / goals.evaluate: verify the persisted plan or "
            "evaluation revision and its source/goal binding.",
            "Provider send/connect/disconnect/refresh routes: require explicit "
            "operation identity and authoritative readback before claiming "
            "success.",
        ],
    }
    (out / "inventory.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Whole-app ORACLE mutation-surface inventory",
        "",
        f"Source: `{payload['source']}`",
        "",
        "This is a static matrix, not a qualification run. It records where "
        "mutations exist and where an independent postcondition verifier is "
        "registered.",
        "",
        "## Registered actions",
        "",
        f"- Total registered actions: **{registered['total']}**",
        f"- External/provider mutation actions: **{len(external)}** "
        f"({len(external_covered)} covered)",
        f"- Local durable-state mutation actions: **{len(local)}** "
        f"({len(local_covered)} covered)",
        f"- Read/other actions: **{payload['registered_actions']['read_or_other_count']}**",
        "",
        "## HTTP and provider surfaces",
        "",
        f"- Mutating HTTP routes (POST/PUT/PATCH/DELETE) under `api/` and "
        f"`integrations/`: **{len(routes)}**",
        f"- High-risk route names/paths: **{len(high_risk)}**",
        f"- Provider-adapter write methods: **{len(writes)}**",
        "",
        "## Covered external mutations",
        "",
    ]
    lines += [f"- `{row['action']}`" for row in external_covered] or ["- none"]
    lines += [
        "",
        "## Uncovered registered mutations",
        "",
    ]
    uncovered = (external_covered and [
        row["action"] for row in external if not row["verifier_registered"]]
        or []) + [row["action"] for row in local
                  if not row["verifier_registered"]]
    lines += [f"- `{name}`" for name in uncovered] or ["- none"]
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
        "This inventory does not close ORACLE-01's whole-app promise. It "
        "shows why the six connected action classes cannot be treated as "
        "every mutation surface: hundreds of HTTP mutation routes and many "
        "provider write methods sit outside that registry.",
        "",
    ]
    (out / "README.md").write_text("\n".join(lines))
    print(json.dumps({
        "registered": registered["total"],
        "external_mutation": len(external),
        "external_covered": len(external_covered),
        "local_mutation": len(local),
        "local_covered": len(local_covered),
        "http_mutation_routes": len(routes),
        "high_risk_routes": len(high_risk),
        "provider_write_methods": len(writes),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
