#!/usr/bin/env python3
"""
check_doc_links.py — Verify internal markdown links resolve to a real file.

Scans `docs/` and `backend/docs/` (or any --root dirs) for markdown links of the
form `[text](path.md)` or `[text](path.md#anchor)`, resolves each relative to the
linking file, and reports broken links.

Resolution rules:
- Filenames are the source of truth (case-sensitive, via `git ls-files` — the
  macOS filesystem is case-insensitive by default and would silently match wrong).
- Anchor (`#section`) is stripped before file resolution. Anchor validity is out
  of scope.
- External `http(s)://` URLs, `mailto:`, and bare anchors (`#section`) are skipped.
- Links inside fenced code blocks (``` ... ```) are skipped — those are docs
  examples, not navigation.
- Links to non-markdown files (e.g. `.png`, `.py`) are skipped.

Outputs:
- Stdout summary: `X broken links across Y files`
- JSON report (stdout or --json-file): array of
  {linking_file, line, target, raw, reason}
- Exit code: 1 if any breaks found, 0 otherwise.

Usage:
    python3 scripts/check_doc_links.py --root docs/ backend/docs/
    python3 scripts/check_doc_links.py --json-file report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


# Regex: [text](target) — captures the target portion. Allows nested brackets
# in text but not in target. Target may include optional #anchor.
# Skips images ![alt](src) via negative lookbehind — we still want them checked,
# so we actually include them. Let's match both [text](url) and ![alt](url).
LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

# Fenced code block markers (``` or ~~~). We treat any line that opens or closes
# a fence as toggling the "in_code_block" state.
FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass
class BrokenLink:
    linking_file: str
    line: int
    target: str  # normalized (anchor stripped)
    raw: str     # original target as written
    reason: str


def get_tracked_files(repo_root: Path) -> set[str]:
    """Return set of repo-relative paths tracked by git. Case-sensitive."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return {line for line in out.splitlines() if line}
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: filesystem walk. Still case-sensitive on the FS side, but
        # macOS HFS+/APFS (default) is case-insensitive — so this is strictly
        # worse than the git path. We warn.
        print(
            "WARNING: git not available; falling back to filesystem walk "
            "(may be case-insensitive on macOS).",
            file=sys.stderr,
        )
        tracked = set()
        for root, _, files in os.walk(repo_root):
            for f in files:
                tracked.add(str((Path(root) / f).relative_to(repo_root)))
        return tracked


def is_skippable_target(target: str) -> bool:
    """Should this link target be skipped (not a markdown file we can verify)?"""
    if not target:
        return True
    # Strip anchor
    path_part = target.split("#", 1)[0]
    if not path_part:
        return True  # bare anchor like `#section`
    lower = path_part.lower()
    # External
    if lower.startswith(("http://", "https://", "mailto:", "ftp://", "tel:")):
        return True
    # Non-markdown file extensions (images, code, etc.)
    _, ext = os.path.splitext(lower)
    if ext and ext not in {".md", ".markdown"}:
        return True
    return False


def iter_markdown_files(roots: list[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if path in seen:
                continue
            # Skip node_modules, .git, venv, etc.
            parts = path.parts
            if any(
                skip in parts
                for skip in {"node_modules", ".git", "venv", "__pycache__", ".venv"}
            ):
                continue
            seen.add(path)
            yield path


def find_broken_links(
    md_files: list[Path],
    tracked: set[str],
    repo_root: Path,
) -> list[BrokenLink]:
    """Scan all markdown files and return list of broken links."""
    broken: list[BrokenLink] = []
    # Index tracked files for O(1) lookup. Normalize to repo-relative posix paths.
    tracked_posix = {p.replace(os.sep, "/") for p in tracked}
    # Also a lookup for markdown-only resolution (case-sensitive).
    tracked_md = {p for p in tracked_posix if p.lower().endswith((".md", ".markdown"))}

    for md_file in md_files:
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        in_fence = False
        for line_no, line in enumerate(text.splitlines(), start=1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            # Find all link matches on this line
            for m in LINK_RE.finditer(line):
                # Match group 2 = image target, group 4 = link target
                target = m.group(2) or m.group(4)
                if target is None:
                    continue
                if is_skippable_target(target):
                    continue
                # Strip anchor and query
                path_part = target.split("#", 1)[0].split("?", 1)[0]
                if not path_part:
                    continue
                # Resolve relative to the linking file's directory
                linking_dir = md_file.parent
                resolved = (linking_dir / path_part).resolve(strict=False)
                try:
                    rel = resolved.relative_to(repo_root)
                except ValueError:
                    # Resolves outside the repo — can't verify, skip
                    continue
                rel_posix = str(rel).replace(os.sep, "/")
                # If it's an .md file (we only check those), see if it's tracked
                lower = rel_posix.lower()
                if lower.endswith((".md", ".markdown")):
                    if rel_posix not in tracked_md:
                        broken.append(
                            BrokenLink(
                                linking_file=str(
                                    md_file.relative_to(repo_root)
                                ).replace(os.sep, "/"),
                                line=line_no,
                                target=rel_posix,
                                raw=target,
                                reason="missing",
                            )
                        )
                # else: non-md file; skip (out of scope per plan)
    return broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        nargs="+",
        default=[Path("docs"), Path("backend/docs")],
        type=Path,
        help="Root directories to scan (default: docs/ backend/docs/)",
    )
    parser.add_argument(
        "--json-file",
        type=Path,
        default=None,
        help="Write JSON report to this file (default: stdout if --json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON report to stdout instead of human summary",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root (default: git toplevel or cwd)",
    )
    args = parser.parse_args(argv)

    # Determine repo root
    repo_root = args.repo_root
    if repo_root is None:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            repo_root = Path(out)
        except (subprocess.CalledProcessError, FileNotFoundError):
            repo_root = Path.cwd()
    repo_root = repo_root.resolve()

    tracked = get_tracked_files(repo_root)

    # Resolve the scan roots relative to repo_root
    roots = []
    for r in args.root:
        rp = r if r.is_absolute() else (repo_root / r)
        if rp.exists():
            roots.append(rp)

    md_files = list(iter_markdown_files(roots))
    broken = find_broken_links(md_files, tracked, repo_root)

    # Dedupe identical (file, line, raw) entries (regex can double-match images)
    seen = set()
    unique = []
    for b in broken:
        key = (b.linking_file, b.line, b.raw)
        if key not in seen:
            seen.add(key)
            unique.append(b)
    broken = unique

    files_affected = {b.linking_file for b in broken}

    if args.json or args.json_file:
        payload = [asdict(b) for b in broken]
        if args.json_file:
            args.json_file.write_text(json.dumps(payload, indent=2))
            print(
                f"Wrote {len(payload)} broken links to {args.json_file}",
                file=sys.stderr,
            )
        else:
            print(json.dumps(payload, indent=2))
    else:
        if broken:
            print(f"Broken links ({len(broken)}):", file=sys.stderr)
            for b in broken:
                print(
                    f"  {b.linking_file}:{b.line}  →  {b.raw}",
                    file=sys.stderr,
                )
            print("", file=sys.stderr)

    summary = f"{len(broken)} broken links across {len(files_affected)} files"
    print(summary)
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
