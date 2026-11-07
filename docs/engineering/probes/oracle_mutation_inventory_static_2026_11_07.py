#!/usr/bin/env python3
"""READ-ONLY static mutation-surface scan from Git objects.

Author artifact for docs/engineering/ORACLE_MUTATION_QUEUE_2026_11_07.md.
It does not import the app, start a server, read a live DB, or check out
backend/evidence. It uses only stdlib + `git archive` and emits full row sets
so two Git sources can be diffed exactly.

Reproduces the accepted oracle_mutation_surface_inventory.py AST rules:
  * mutating route decorators under backend/api + backend/integrations
  * high-risk markers on function+route
  * provider write-method prefixes on class methods under backend/integrations

Usage:
    python3 docs/engineering/probes/oracle_mutation_inventory_static_2026_11_07.py \
        <base-ref> <head-ref> <outdir>
"""
from __future__ import annotations

import ast
import io
import json
import subprocess
import sys
import tarfile
from collections import Counter

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
PROVIDER_PREFIX = "backend/integrations/"


def _files(source):
    proc = subprocess.Popen(
        ["git", "archive", "--format=tar", source,
         "backend/api", "backend/integrations"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for member in tar:
                if not member.isfile() or not member.name.endswith(".py"):
                    continue
                parts = member.name.split("/")
                if "__pycache__" in parts or "tests" in parts:
                    continue
                data = tar.extractfile(member).read()
                yield member.name, data
        rc = proc.wait()
        if rc:
            raise SystemExit(proc.stderr.read().decode(errors="replace"))
    finally:
        if proc.poll() is None:
            proc.kill()


def scan(source):
    routes = []
    writes = []
    for name, data in _files(source):
        try:
            tree = ast.parse(data.decode("utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
                routes.append({
                    "file": name, "function": node.name,
                    "method": method.upper(), "route": route,
                    "lineno": node.lineno,
                })
        if name.startswith(PROVIDER_PREFIX):
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for item in node.body:
                    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if item.name.startswith(WRITE_PREFIXES):
                        writes.append({
                            "file": name, "class": node.name,
                            "method": item.name, "lineno": item.lineno,
                        })
    high = [
        r for r in routes
        if any(marker in f"{r['function']} {r['route']}".lower()
               for marker in HIGH_RISK_MARKERS)
    ]
    return {
        "source": source,
        "routes": routes,
        "high_risk": high,
        "provider_writes": writes,
        "counts": {
            "routes": len(routes),
            "high_risk": len(high),
            "provider_writes": len(writes),
            "by_method": dict(Counter(r["method"] for r in routes)),
            "by_file": dict(Counter(r["file"] for r in routes).most_common()),
        },
    }


def key_route(r):
    return (r["file"], r["function"], r["method"], r["route"])


def key_write(r):
    return (r["file"], r["class"], r["method"])


def main():
    base = sys.argv[1]
    head = sys.argv[2]
    outdir = sys.argv[3]
    b = scan(base)
    h = scan(head)
    bset = {key_route(r) for r in b["routes"]}
    hset = {key_route(r) for r in h["routes"]}
    bhigh = {key_route(r) for r in b["high_risk"]}
    hhigh = {key_route(r) for r in h["high_risk"]}
    bw = {key_write(r) for r in b["provider_writes"]}
    hw = {key_write(r) for r in h["provider_writes"]}

    def rows(keys, src_rows, keyfn):
        index = {}
        for r in src_rows:
            index.setdefault(keyfn(r), r)
        return [index[k] for k in sorted(keys)]

    delta = {
        "base_source": base,
        "head_source": head,
        "base_counts": b["counts"],
        "head_counts": h["counts"],
        "routes_added": rows(hset - bset, h["routes"], key_route),
        "routes_removed": rows(bset - hset, b["routes"], key_route),
        "high_risk_added": rows(hhigh - bhigh, h["high_risk"], key_route),
        "high_risk_removed": rows(bhigh - hhigh, b["high_risk"], key_route),
        "provider_writes_added": rows(hw - bw, h["provider_writes"], key_write),
        "provider_writes_removed": rows(bw - hw, b["provider_writes"], key_write),
    }
    with open(f"{outdir}/base_routes.json", "w") as fh:
        json.dump(b, fh, indent=1, sort_keys=True)
    with open(f"{outdir}/head_routes.json", "w") as fh:
        json.dump(h, fh, indent=1, sort_keys=True)
    with open(f"{outdir}/delta.json", "w") as fh:
        json.dump(delta, fh, indent=1, sort_keys=True)
    print(json.dumps({
        "base_counts": b["counts"],
        "head_counts": h["counts"],
        "routes_added": len(delta["routes_added"]),
        "routes_removed": len(delta["routes_removed"]),
        "high_risk_added": len(delta["high_risk_added"]),
        "high_risk_removed": len(delta["high_risk_removed"]),
        "provider_writes_added": len(delta["provider_writes_added"]),
        "provider_writes_removed": len(delta["provider_writes_removed"]),
    }, indent=2))


if __name__ == "__main__":
    main()
