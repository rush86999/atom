#!/usr/bin/env python3
"""Inventory source-bound reference/diagram candidates; never certify accuracy."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

REFERENCE = {".md", ".mdx", ".rst", ".adoc", ".asciidoc"}
DIAGRAM = {".mmd", ".puml", ".plantuml", ".dot", ".drawio", ".excalidraw", ".d2"}
IMAGE = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"}
LANGUAGES = {"mermaid", "plantuml", "dot", "graphviz", "d2", "nomnoml"}
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def git(repo, *args, data=None):
    return subprocess.check_output(["git", "-C", str(repo), *args], input=data)


def purpose(path):
    if path.startswith(".archive/") or "/archive/" in path:
        return "archived_record"
    if "/evidence/" in path or "/orchestration_acceptance/" in path:
        return "source_bound_evidence_record"
    if path in {"README.md", "docs/README.md", "docs/INDEX.md", "CLAUDE.md", "AGENTS.md"}:
        return "entrypoint_or_working_policy"
    if path.startswith("docs/architecture/"):
        return "architecture_reference"
    if path.startswith(("docs/getting_started/", "docs/guides/", "docs/operations/")):
        return "user_or_operator_reference"
    return "needs_owner_classification"


def embedded(path, content):
    result, opened = [], None
    for number, line in enumerate(content.decode("utf-8", errors="replace").splitlines(), 1):
        match = FENCE.match(line)
        if not match:
            continue
        marks, info = match.groups()
        if opened:
            if marks[0] == opened["marker"] and len(marks) >= opened["length"] and not info.strip():
                if opened["language"] in LANGUAGES:
                    result.append({"path": path, "kind": opened["language"], "start_line": opened["line"], "end_line": number, "rendered": False, "semantic_status": "not_reviewed"})
                opened = None
        else:
            opened = {"marker": marks[0], "length": len(marks), "language": info.strip().split()[0].lower() if info.strip() else "", "line": number}
    if opened and opened["language"] in LANGUAGES:
        result.append({"path": path, "kind": opened["language"], "start_line": opened["line"], "end_line": None, "rendered": False, "semantic_status": "unclosed_fence_needs_review"})
    return result


def build_inventory(repo, ref):
    source = git(repo, "rev-parse", "--verify", ref + "^{commit}").decode().strip()
    rows = []
    for raw in git(repo, "ls-tree", "-r", "-l", "-z", source).split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        mode, kind, oid, size = metadata.decode().split()
        if kind != "blob":
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        rows.append({"path": path, "blob_prefix": oid[:12], "bytes": int(size), "mode": mode, "purpose_candidate": purpose(path), "semantic_status": "not_reviewed", "_oid": oid})
    references = [r for r in rows if Path(r["path"]).suffix.lower() in REFERENCE or Path(r["path"]).name.lower() == "readme"]
    diagrams = [dict(r, kind="standalone_diagram_candidate", rendered=False) for r in rows if Path(r["path"]).suffix.lower() in DIAGRAM]
    figures = [r.copy() for r in rows if Path(r["path"]).suffix.lower() in IMAGE]
    for start in range(0, len(references), 32):
        batch = references[start:start + 32]
        output = git(repo, "cat-file", "--batch", data=("\n".join(r["_oid"] for r in batch) + "\n").encode())
        cursor = 0
        for row in batch:
            end = output.index(b"\n", cursor)
            oid, kind, size = output[cursor:end].decode().split()
            assert oid == row["_oid"] and kind == "blob"
            cursor = end + 1
            body = output[cursor:cursor + int(size)]
            cursor += int(size) + 1
            if row["mode"] != "120000":
                diagrams.extend(embedded(row["path"], body))
    for collection in (references, diagrams, figures):
        for row in collection:
            row.pop("_oid", None)
    return {"schema_version": 1, "source_ref": source, "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "all tracked Markdown/MDX/RST/AsciiDoc/README references; named diagram sources and fenced diagram blocks; all tracked image/PDF candidates require classification", "limits": ["Inventory is not accuracy, coverage, rendering or product acceptance.", "Purpose labels are triage candidates, not proof of historical/current authority.", "Nested/indented fences, inline HTML, ASCII art, diagrams inside binary documents and uncategorized assets require manual review.", "Blob prefixes are navigational identifiers, not integrity certificates.", "Historical evidence must retain its actual source and bytes; do not rewrite it to describe current behavior. Reference triage does not reopen accepted runtime outcomes or require stable inference replay."], "summary": {"references": len(references), "diagram_candidates": len(diagrams), "figure_candidates": len(figures), "reference_purpose_candidates": dict(Counter(r["purpose_candidate"] for r in references))}, "references": references, "diagram_candidates": diagrams, "figure_candidates": figures, "accuracy_complete": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("refusing to overwrite an existing source-bound inventory")
    if not args.output.parent.is_dir():
        parser.error("output directory must already exist")
    result = build_inventory(args.repo, args.ref)
    try:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    except FileExistsError:
        parser.error("refusing to overwrite an existing source-bound inventory")
    print(json.dumps({"source_ref": result["source_ref"], **result["summary"], "accuracy_complete": False}))


if __name__ == "__main__":
    main()
