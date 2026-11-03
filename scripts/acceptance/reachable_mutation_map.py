#!/usr/bin/env python3
"""Map mounted mutation-shaped routes to dispatch/effect families.

Reads the active app's OpenAPI document, matches each route to its source
declaration, and classifies whether the endpoint uses the shared action
registry/assignment executor, a direct service, or an unknown path. This is a
reachability/dispatch map, not proof that every route is effectful.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
READ_MARKERS = (
    "list_", "search_", "get_", "read_", "preview_", "validate_", "check_",
    "status", "query_", "lookup_", "health", "download_", "export_",
    "profile", "retrieve_", "resolve_",
)
WRITE_MARKERS = (
    "create_", "update_", "delete_", "send_", "post_", "upload_", "connect_",
    "disconnect_", "revoke_", "refresh_", "restore_", "approve_", "cancel_",
    "start_", "complete_", "execute_", "run_", "write_", "save_", "present_",
    "submit_", "attach_", "detach_", "fork_", "undelete_", "promote_",
    "reject_", "apply_", "install_", "import_", "invite_", "assign_",
)


def _route_index(root: Path) -> Dict[Tuple[str, str], Dict[str, Any]]:
    index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for base in (root / "backend/api", root / "backend/integrations"):
        for path in sorted(base.rglob("*.py")):
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
                    method = call.func.attr.upper()
                    if method not in MUTATING_METHODS:
                        continue
                    route = ""
                    if call.args and isinstance(call.args[0], ast.Constant):
                        route = str(call.args[0].value)
                    index[(node.name, method)] = {
                        "file": str(path.relative_to(root)),
                        "function": node.name,
                        "method": method,
                        "declared_route": route,
                    }
    return index


def _family(path: str) -> str:
    text = path.lower()
    for prefix, family in (
            ("/api/canvas", "canvas"),
            ("/api/assignments", "assignments"),
            ("/api/goals", "goals"),
            ("/api/goal-runs", "goal_runs"),
            ("/api/autodev", "evolution_review"),
            ("/api/skills", "skills"),
            ("/api/v1/learn", "skills"),
            ("/api/integrations/outlook", "provider_outlook"),
            ("/api/v1/integrations/outlook", "provider_outlook"),
            ("/api/integrations", "provider_integrations"),
            ("/api/auth", "auth"),
            ("/api/chat", "chat"),
            ("/api/document", "documents"),
            ("/api/memory", "memory"),
            ("/api/agent", "agents"),
            ("/api/workflow", "workflows"),
            ("/api/marketplace", "marketplace"),
            ("/api/billing", "billing"),
            ("/api/admin", "admin"),
    ):
        if text.startswith(prefix):
            return family
    return "other"


def _dispatch(source: str, function_source: str) -> str:
    haystack = f"{source}\n{function_source}"
    if "execute_action(" in haystack or "action_registry" in haystack:
        return "shared_action_registry"
    if "AssignmentExecutor" in haystack or "assignment_executor" in haystack:
        return "assignment_executor"
    if "core.oracle" in haystack or "validate(" in haystack:
        return "oracle_consumer"
    if any(marker in haystack for marker in (
            "CanvasAudit", "update_canvas_content", "restore_canvas_version",
            "create_blank_canvas", "delete_canvas", "fork_canvas")):
        return "direct_canvas_service"
    if any(marker in haystack for marker in (
            "GoalService", "GoalRunService", "goal_service")):
        return "direct_goal_service"
    if any(marker in haystack for marker in (
            "OutlookService", "Zoho", "OAuth", "IntegrationService",
            "APService", "AccountingService", "SyncManager")):
        return "direct_provider_service"
    return "direct_or_unknown"


def _effect(path: str, operation_id: str, function: str) -> str:
    text = f"{path} {operation_id} {function}".lower()
    if any(marker in text for marker in WRITE_MARKERS):
        return "mutation_shaped"
    if any(marker in text for marker in READ_MARKERS):
        return "read_only_likely"
    return "unknown_effect"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    spec = requests.get(
        f"{args.api.rstrip('/')}/api/v1/openapi.json", timeout=60).json()
    index = _route_index(root)
    rows: List[Dict[str, Any]] = []
    for path, operations in sorted((spec.get("paths") or {}).items()):
        for method, operation in operations.items():
            method = method.upper()
            if method not in MUTATING_METHODS:
                continue
            operation_id = str(operation.get("operationId") or "")
            function = operation_id.split("_api_", 1)[0]
            match = index.get((function, method))
            source_file = match["file"] if match else ""
            function_source = ""
            module_text = ""
            if match:
                try:
                    module_text = (root / source_file).read_text(
                        errors="ignore")
                    tree = ast.parse(module_text)
                    for node in ast.walk(tree):
                        if isinstance(
                                node, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ) and node.name == function:
                            function_source = ast.get_source_segment(
                                module_text, node) or ""
                            break
                except (OSError, SyntaxError):
                    module_text = ""
            rows.append({
                "path": path,
                "method": method,
                "operation_id": operation_id,
                "function": function,
                "source_file": source_file,
                "matched": bool(match),
                "family": _family(path),
                "effect": _effect(path, operation_id, function),
                "dispatch": _dispatch(module_text, function_source),
            })
    effect_counts = Counter(row["effect"] for row in rows)
    family_counts = Counter(row["family"] for row in rows)
    dispatch_counts = Counter(row["dispatch"] for row in rows)
    bypass = [
        row for row in rows
        if row["effect"] != "read_only_likely"
        and row["dispatch"] in ("direct_canvas_service",
                                "direct_goal_service",
                                "direct_provider_service",
                                "direct_or_unknown")
    ]
    by_family = defaultdict(lambda: {"total": 0, "bypass": 0, "dispatch": Counter()})
    for row in rows:
        entry = by_family[row["family"]]
        entry["total"] += 1
        entry["dispatch"][row["dispatch"]] += 1
        if row in bypass:
            entry["bypass"] += 1
    payload = {
        "schema": "atom-reachable-mutation-map-1",
        "api": args.api,
        "mounted_paths": len(spec.get("paths") or {}),
        "mutation_shaped_routes": len(rows),
        "effect_counts": dict(effect_counts),
        "family_counts": dict(family_counts),
        "dispatch_counts": dict(dispatch_counts),
        "by_family": {
            family: {
                "total": value["total"],
                "bypass": value["bypass"],
                "dispatch": dict(value["dispatch"]),
            }
            for family, value in sorted(by_family.items())
        },
        "bypass_count": len(bypass),
        "bypass_sample": bypass[:120],
        "rows": rows,
        "limitations": [
            "OpenAPI paths reflect the active core profile declaration surface, not proof of reachability or effect.",
            "Operation-id/source matching is best-effort; unmatched rows are marked and remain unknown.",
            "Direct-service classification means the route bypasses the shared action registry/executor, not that its service tests are absent.",
        ],
    }
    (out / "reachable_mutation_map.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Reachable mutation map — active core profile",
        "",
        f"API: `{args.api}`",
        "",
        f"- OpenAPI paths: **{payload['mounted_paths']}**",
        f"- Mutation-shaped mounted routes: **{len(rows)}**",
        f"- Bypass candidates (direct service / unknown): **{len(bypass)}**",
        "",
        "## Effect classification",
        "",
    ]
    lines += [f"- {name}: {count}" for name, count in effect_counts.most_common()]
    lines += ["", "## Dispatch classification", ""]
    lines += [f"- {name}: {count}" for name, count in dispatch_counts.most_common()]
    lines += ["", "## Families with bypass candidates", ""]
    for family, value in sorted(by_family.items(),
                                key=lambda item: item[1]["bypass"],
                                reverse=True)[:15]:
        lines.append(
            f"- `{family}`: {value['total']} mutation-shaped, "
            f"{value['bypass']} bypass candidates; dispatch="
            f"{dict(value['dispatch'])}")
    lines += [
        "",
        "## Boundary",
        "",
        "This is a reachability/dispatch map, not runtime coverage proof. "
        "Direct-service routes still need family-level postcondition controls; "
        "the complete row list is in `reachable_mutation_map.json`.",
        "",
    ]
    (out / "README.md").write_text("\n".join(lines))
    print(json.dumps({
        "paths": payload["mounted_paths"],
        "mutation_shaped": len(rows),
        "bypass": len(bypass),
        "effect_counts": dict(effect_counts),
        "dispatch_counts": dict(dispatch_counts),
        "top_families": [
            (family, value["bypass"])
            for family, value in sorted(
                by_family.items(), key=lambda item: item[1]["bypass"],
                reverse=True)[:10]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
