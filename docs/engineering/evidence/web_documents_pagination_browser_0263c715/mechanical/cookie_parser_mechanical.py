#!/usr/bin/env python3
"""Mechanical raw/chunked SDK cookie parser tests; no browser/app/network."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

HARNESS = Path("/private/tmp/root-web-document-pagination-browser-20261110.py")
OLD = Path("/private/tmp/root-web-document-pagination-browser-20261110.failed-1b0208fc.py")
RESULT = Path("/private/tmp/root-web-document-pagination-cookie-parser-mechanical-20261110-result.json")


def load(path):
    spec = importlib.util.spec_from_file_location("doc_pagination_cookie_harness", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main():
    module = load(HARNESS)
    old = load(OLD)
    cases = []

    def add(name, cookies, expected):
        try:
            got = module.select_session_cookie(cookies)
            ok = all(got.get(k) == v for k, v in expected.items())
            cases.append({"case": name, "ok": ok, "got": got})
        except Exception as exc:
            cases.append({"case": name, "ok": False,
                          "error": f"{type(exc).__name__}: {exc}"})

    raw_name = "__Secure-next-auth.session-token"
    insecure_name = "next-auth.session-token"
    raw_value = "header.payload.signature.jwe"

    add("raw_secure_base_name_with_dots", [
        {"name": raw_name, "value": raw_value, "httpOnly": True},
    ], {"name": raw_name, "value": raw_value, "kind": "raw",
        "chunk_indices": [], "complete": True})

    add("chunked_secure_shuffled", [
        {"name": raw_name + ".1", "value": "BBB", "httpOnly": True},
        {"name": raw_name + ".0", "value": "AAA", "httpOnly": True},
    ], {"name": raw_name, "value": "AAABBB", "kind": "chunked",
        "chunk_indices": [0, 1], "complete": True})

    add("raw_insecure_base_name", [
        {"name": insecure_name, "value": "raw.jwe.value", "httpOnly": True},
    ], {"name": insecure_name, "value": "raw.jwe.value", "kind": "raw",
        "complete": True})

    add("dotted_unrelated_cookie_ignored", [
        {"name": "some.other.cookie", "value": "ignore"},
        {"name": raw_name, "value": "chosen", "httpOnly": True},
    ], {"name": raw_name, "value": "chosen", "kind": "raw"})

    add("no_cookie", [], {"name": None, "value": None, "kind": None,
                          "complete": False})

    add("chunk_gap_is_incomplete", [
        {"name": raw_name + ".0", "value": "A"},
        {"name": raw_name + ".2", "value": "C"},
    ], {"name": raw_name, "value": "AC", "kind": "chunked",
        "chunk_indices": [0, 2], "complete": False})

    # Explicit old-bug reproduction: old code sees "." in the base name and
    # calls int('session-token').
    def old_session_cookie(cookies):
        for name in ("__Secure-next-auth.session-token",
                     "next-auth.session-token"):
            found = [c for c in cookies if c["name"] == name or
                     re.fullmatch(re.escape(name) + r"\.\d+", c["name"])]
            if found:
                found.sort(key=lambda c: int(c["name"].rsplit(".", 1)[1])
                           if "." in c["name"] else -1)
                return name, "".join(c["value"] for c in found), found
        return None, None, []

    old_error = None
    try:
        old_session_cookie([{"name": raw_name, "value": raw_value}])
    except Exception as exc:
        old_error = f"{type(exc).__name__}: {exc}"
    cases.append({
        "case": "old_parser_reproduces_int_session_token",
        "ok": old_error is not None and "session-token" in old_error,
        "old_error": old_error,
    })

    passed = all(c["ok"] for c in cases)
    out = {
        "ok": passed,
        "case_count": len(cases),
        "all_cases_pass": passed,
        "harness": str(HARNESS),
        "harness_sha256": hashlib.sha256(HARNESS.read_bytes()).hexdigest(),
        "preserved_failed_harness": str(OLD),
        "preserved_failed_sha256": hashlib.sha256(OLD.read_bytes()).hexdigest(),
        "cases": cases,
    }
    RESULT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
