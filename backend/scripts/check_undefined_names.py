#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Undefined-name check for modules edited under time pressure.

`compile()` accepts a name that is never bound; the failure appears at runtime,
and when it sits inside a broad ``except`` (or a reply-assembly try block) it is
swallowed — the turn falls back to a canned template and the user never sees an
error. Two such defects shipped in one session on 2026-09-16:

* a rename left ``_fb_models`` referenced after it became ``_fb_routes`` —
  every chat turn on that path answered with "I found 0 results for your
  search." instead of a model reply;
* ``collect_team_signers`` was called but never imported, so outbound signing
  identity silently never resolved.

This is deliberately a small AST pass, not a type checker: it answers exactly
"is every loaded name bound somewhere in this module (or builtin)?".

Usage::

    cd backend && ./venv/bin/python scripts/check_undefined_names.py [paths...]
"""
from __future__ import annotations

import ast
import builtins
import os
import sys

BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__"}

DEFAULT_TARGETS = [
    "integrations/chat_orchestrator.py",
    "core/llm/byok_handler.py",
    "core/llm/model_route_registry.py",
    "core/runtime_identity.py",
    "core/llm_service.py",
    "core/learning_llm_router.py",
    "core/llm/learning_router_registry.py",
    "api/byok_routes.py",
]


def bound_names(tree: ast.AST) -> set:
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.Global):
            names.update(node.names)
        elif isinstance(node, (ast.alias,)):
            pass
    return names


def check(path: str) -> list[tuple[int, str]]:
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    bound = bound_names(tree)
    problems: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in bound and node.id not in BUILTINS:
                problems.setdefault(node.id, node.lineno)
    return sorted(((line, name) for name, line in problems.items()))


def main(argv: list[str]) -> int:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    targets = argv[1:] or [os.path.join(base, t) for t in DEFAULT_TARGETS]
    failed = False
    for path in targets:
        if not os.path.exists(path):
            continue
        for line, name in check(path):
            failed = True
            rel = os.path.relpath(path, base)
            print(f"{rel}:{line}: undefined name {name!r}")
    print("undefined-name check:", "FAILED" if failed else "clean")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
