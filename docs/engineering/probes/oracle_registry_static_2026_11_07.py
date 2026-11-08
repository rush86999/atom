#!/usr/bin/env python3
"""READ-ONLY static registered-action/verifier delta from Git objects.

Author artifact for docs/engineering/ORACLE_MUTATION_QUEUE_2026_11_07.md.
It does not import the app, start a server, read a live DB, or check out
backend/evidence. It parses the registry modules and oracle verifier
registrations with stdlib `ast` only.

Usage:
    python3 docs/engineering/probes/oracle_registry_static_2026_11_07.py \
        <base-ref> <head-ref> <outdir>
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys

REGISTRY_MODULES = [
    "backend/core/action_registry.py",
    "backend/core/connected_actions.py",
    "backend/core/agent_radio/radio_actions.py",
    "backend/core/bpe/actions.py",
]
ORACLE_DIR = "backend/core/oracle"
MUTATING = {
    "write", "create", "update", "delete", "send", "execute",
    "graph_updated", "record_created", "record_updated", "record_deleted",
    "goal_created", "goal_run_started", "goal_evaluated",
}
READ = {"read", "read_only"}
PLAN = {"plan_produced"}


def show(source, path):
    return subprocess.check_output(
        ["git", "show", f"{source}:{path}"], text=True)


def list_py(source, root):
    out = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", source, root], text=True)
    return [p for p in out.splitlines() if p.endswith(".py")]


def effects_of(call):
    for kw in call.keywords:
        if kw.arg == "effects":
            try:
                value = ast.literal_eval(kw.value)
            except Exception:
                return [], False
            if not isinstance(value, list):
                return [], False
            names = []
            for item in value:
                if isinstance(item, str):
                    names.append(item.strip().lower())
                elif isinstance(item, dict) and isinstance(
                        item.get("effect"), str):
                    names.append(item["effect"].strip().lower())
                else:
                    return names, False
            return names, True
    return [], False


def decorator_actions(path, src):
    tree = ast.parse(src)
    rows = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if not (isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Name)
                    and d.func.id == "register_action"):
                continue
            if not d.args or not isinstance(d.args[0], ast.Constant):
                continue
            name = d.args[0].value
            names, valid = effects_of(d)
            rows[name] = {
                "name": name, "effects": names,
                "declaration_valid": valid,
                "handler": node.name, "file": path,
                "mutation": bool(set(names) & MUTATING),
                "read_only": bool(names) and set(names) <= READ,
                "plan_output": bool(names) and set(names) <= (READ | PLAN)
                and bool(set(names) & PLAN),
                "undeclared": not names and not valid,
            }
    return rows


def alias_map(src):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_GENERIC_ALIASES"
                for t in node.targets):
            try:
                return ast.literal_eval(node.value)
            except Exception:
                return {}
    return {}


def verifiers(source, path, src):
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            fname = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else "")
            if fname == "register_postcondition" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    names.add(arg.value)
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
            body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
            if "register_postcondition" in body:
                for elt in node.iter.elts:
                    if isinstance(elt, ast.Constant) and isinstance(
                            elt.value, str):
                        names.add(elt.value)
    return names


def scan(source):
    actions = {}
    for path in REGISTRY_MODULES:
        src = show(source, path)
        actions.update(decorator_actions(path, src))
        if path.endswith("connected_actions.py"):
            for generic, legacy in alias_map(src).items():
                base = actions.get(legacy)
                if base:
                    row = dict(base)
                    row["name"] = generic
                    row["alias_of"] = legacy
                    actions[generic] = row
    verified = set()
    for path in list_py(source, ORACLE_DIR):
        verified |= verifiers(source, path, show(source, path))
    # other backend/core modules may register verifiers too
    for path in list_py(source, "backend/core"):
        if path.startswith(ORACLE_DIR + "/"):
            continue
        try:
            src = show(source, path)
        except subprocess.CalledProcessError:
            continue
        if "register_postcondition" in src:
            verified |= verifiers(source, path, src)
    rows = []
    for name in sorted(actions):
        row = dict(actions[name])
        row["verifier_registered"] = name in verified
        rows.append(row)
    mutation = [r for r in rows if r["mutation"]]
    return {
        "source": source,
        "actions_total": len(rows),
        "mutations_total": len(mutation),
        "mutations_covered": len([r for r in mutation
                                  if r["verifier_registered"]]),
        "mutations_uncovered": [r["name"] for r in mutation
                                if not r["verifier_registered"]],
        "mutating_with_verifier": [r["name"] for r in mutation
                                   if r["verifier_registered"]],
        "undeclared": [r["name"] for r in rows if r["undeclared"]],
        "verifiers": sorted(verified),
        "verifiers_without_action": sorted(verified - set(actions)),
        "actions": rows,
        "counts_by_file": {p: len([r for r in rows if r["file"] == p])
                           for p in REGISTRY_MODULES},
    }


def main():
    base, head, outdir = sys.argv[1:4]
    b = scan(base)
    h = scan(head)
    bn = {r["name"] for r in b["actions"]}
    hn = {r["name"] for r in h["actions"]}
    bi = {r["name"]: r for r in b["actions"]}
    hi = {r["name"]: r for r in h["actions"]}
    effect_changes = []
    for name in sorted(bn & hn):
        if bi[name]["effects"] != hi[name]["effects"]:
            effect_changes.append({
                "name": name, "before": bi[name]["effects"],
                "after": hi[name]["effects"]})
    hver = set(h["verifiers"])
    bver = set(b["verifiers"])
    verifier_added = sorted((hver - bver) & hn)
    verifier_removed = sorted((bver - hver) & bn)
    delta = {
        "base": {k: b[k] for k in (
            "source", "actions_total", "mutations_total",
            "mutations_covered", "mutations_uncovered",
            "undeclared", "counts_by_file")},
        "head": {k: h[k] for k in (
            "source", "actions_total", "mutations_total",
            "mutations_covered", "mutations_uncovered",
            "undeclared", "counts_by_file")},
        "actions_added": sorted(hn - bn),
        "actions_removed": sorted(bn - hn),
        "effect_changes": effect_changes,
        "verifier_added": verifier_added,
        "verifier_removed": verifier_removed,
        "head_verifiers_without_action": h["verifiers_without_action"],
    }
    with open(f"{outdir}/registry_base.json", "w") as fh:
        json.dump(b, fh, indent=1, sort_keys=True)
    with open(f"{outdir}/registry_head.json", "w") as fh:
        json.dump(h, fh, indent=1, sort_keys=True)
    with open(f"{outdir}/registry_delta.json", "w") as fh:
        json.dump(delta, fh, indent=1, sort_keys=True)
    print(json.dumps(delta, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
