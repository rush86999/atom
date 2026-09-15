"""
Agent-native virtual filesystem (VFS) base contract (W1, P2a).

Maps Atom's knowledge + integration stores into a uniform directory tree so
agents navigate with ``ls``/``cat``/``grep``/``search`` instead of bespoke
per-integration operations. The citable core is ``content.lines``: every line
``L<n>: <text>``, so ``grep`` returns precise citations and agents can quote
``knowledge/documents/<id>/content.lines:L47``.

This is an EROFS illusion over existing stores (the ChromaFs / Paperclip
pattern) — no real filesystem, sandboxing/egress untouched.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VFSNode:
    """One entry in a directory listing."""
    name: str
    type: str  # "dir" | "file" | "note"
    path: str
    size: Optional[int] = None
    modified: Optional[str] = None  # ISO timestamp
    #: Extra structured context (sender / subject / body size for a message
    #: listing). Optional so every existing ``VFSNode(name, type, path)`` call
    #: keeps working untouched.
    meta: Optional[Dict[str, Any]] = None


@dataclass
class VFSResource:
    """A leaf resource: metadata + line-numbered content."""
    path: str
    meta: Dict[str, Any] = field(default_factory=dict)
    lines: List[str] = field(default_factory=list)  # each "L<n>: <text>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "meta": self.meta,
            "content": "\n".join(self.lines),
            "line_count": len(self.lines),
        }


@dataclass
class VFSCitation:
    """A grep/search hit with a precise line reference."""
    path: str
    line: int
    snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "line": self.line, "snippet": self.snippet}


def to_line_numbered(text: str) -> List[str]:
    """Convert plain text into ``L<n>: <text>`` lines (the citable format)."""
    if not text:
        return []
    raw = text.split("\n")
    return [f"L{i + 1}: {line}" for i, line in enumerate(raw)]


@dataclass
class VFSRegion:
    """A BOUNDED slice of a leaf's content — the addressing unit for large
    artifacts (long email threads, 300-row workbooks, 100-page PDFs).

    Why this exists: a leaf can be tens of thousands of lines, and the only
    reads available were ``cat`` (everything) or ``head``/``tail`` (the ends).
    Agents therefore either blew their context or skipped the file — and a
    skipped file is what produced fabricated "derivations" (live 2026-09-15:
    an invented $8,880 arithmetic chain while the real row sat at line 315 of
    a 324-line workbook).

    ``total_lines`` and ``next_start`` make the slice SELF-DESCRIBING: the
    agent always knows whether it has seen the whole artifact and where to
    continue, so paging is a loop the model can drive without guessing.

    ``degraded`` marks a read that FAILED partway (store error, unreadable
    parquet): an empty degraded region must never read as end-of-content —
    a paging loop that mistakes a transient error for EOF silently drops
    the tail of the evidence, the exact failure family this type exists to
    prevent."""
    path: str
    start_line: int                  # 1-based, inclusive
    lines: List[str] = field(default_factory=list)   # "L<n>: <text>"
    total_lines: int = 0
    next_start: Optional[int] = None  # None == end of content
    degraded: bool = False            # True == the read failed; NOT EOF

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.start_line + max(len(self.lines) - 1, 0),
            "total_lines": self.total_lines,
            "next_start": self.next_start,
            "content": "\n".join(self.lines),
            "returned_lines": len(self.lines),
            "complete": self.next_start is None and not self.degraded,
            "degraded": self.degraded,
        }


class VFSProvider(ABC):
    """Agent-native filesystem view of one store (knowledge, github, etc.)."""

    #: The path prefix this provider owns (e.g. "knowledge", "github").
    prefix: str = ""

    @abstractmethod
    async def ls(self, path: str, ctx: Optional[Dict[str, Any]] = None) -> List[VFSNode]:
        """List children of a VFS path."""

    @abstractmethod
    async def cat(self, path: str, ctx: Optional[Dict[str, Any]] = None) -> VFSResource:
        """Return meta + content.lines (line-numbered) for a leaf path."""

    async def read_region(
        self,
        path: str,
        start_line: int = 1,
        max_lines: int = 200,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> VFSRegion:
        """Read a BOUNDED region of a leaf, with paging metadata.

        The default implementation is built on :meth:`cat` so every existing
        provider gains bounded reads without changes; providers that can seek
        (a table, an indexed store) should override it and avoid materializing
        the whole leaf. ``max_lines`` is clamped by the caller's action
        layer — the point of the primitive is that NO read is unbounded."""
        res = await self.cat(path, ctx)
        all_lines = list(getattr(res, "lines", []) or [])
        total = len(all_lines)
        start = max(int(start_line or 1), 1)
        span = max(int(max_lines or 1), 1)
        window = all_lines[start - 1:start - 1 + span]
        next_start = start + len(window)
        if next_start > total or not window:
            next_start = None
        return VFSRegion(
            path=path,
            start_line=start,
            lines=window,
            total_lines=total,
            next_start=next_start,
        )

    async def grep(
        self, pattern: str, path_prefix: str, ctx: Optional[Dict[str, Any]] = None
    ) -> List[VFSCitation]:
        """Regex search across the provider's content under ``path_prefix``.

        Default implementation: enumerate leaves via ``ls`` and scan each
        ``cat``. Providers may override for efficiency (e.g. SQL ILIKE prefilter).
        """
        import re

        citations: List[VFSCitation] = []
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return citations
        # Walk one level deep (sufficient for the knowledge provider; richer
        # traversal can be added per-provider if needed).
        try:
            nodes = await self.ls(path_prefix, ctx)
        except Exception:
            return citations
        for node in nodes:
            if node.type != "file":
                continue
            try:
                res = await self.cat(node.path, ctx)
            except Exception:
                continue
            for i, line in enumerate(res.lines):
                if regex.search(line):
                    citations.append(VFSCitation(
                        path=res.path, line=i + 1, snippet=line[:200],
                    ))
        return citations

    async def ask_image(
        self, path: str, prompt: str, ctx: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ask a vision-capable model about an image at ``path``.

        Default: unsupported — providers with vision support override this.
        Never raises; returns a degrade result instead.
        """
        return {"success": False, "error": "vision_unavailable",
                "message": "This VFS provider does not support image understanding."}

    async def scan(
        self, path: str, ctx: Optional[Dict[str, Any]] = None,
        max_depth: int = 10,
    ) -> List[VFSNode]:
        """Recursively enumerate every leaf file node under ``path``.

        Breadth-first walk via :meth:`ls` (bounded by ``max_depth``). Providers
        may override for efficiency; the default is correct for the knowledge
        provider (documents/<id>/ → meta.json + content.lines).
        """
        found: List[VFSNode] = []
        frontier: List[VFSNode] = []
        try:
            frontier = list(await self.ls(path, ctx))
        except Exception:
            return found
        for _depth in range(max_depth):
            if not frontier:
                break
            next_level: List[VFSNode] = []
            for node in frontier:
                if node.type == "file":
                    found.append(node)
                    continue
                try:
                    children = await self.ls(node.path, ctx)
                except Exception:
                    continue
                next_level.extend(children)
            frontier = next_level
        return found
