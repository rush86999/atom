"""Execution Sandbox Layer — Phase E (Round 47).

Provenance tagging for context-window chunks. Tags every chunk by trust
level so the agent loop can constrain tool invocation to USER/SYSTEM
provenance only — closing the indirect-prompt-injection gap where a
malicious tool output or web-search result emits a fake tool call.

Mirrors the [Spotlighting defense pattern]
(https://ceur-ws.org/Vol-3920/paper03.pdf) and Microsoft's [IntentGuard
approach](https://arxiv.org/html/2512.00966v1): untrusted chunks are
visibly delimited inside the context window, and the agent loop refuses
to parse tool invocations from untrusted chunks.

Design contract:
  * Pure functions for tagging — no I/O, no side effects.
  * Trust levels form a strict lattice: SYSTEM/USER (trusted) >
    MEMORY (semi-trusted) > TOOL_OUTPUT/FILE/FEDERATION/RETRIEVED
    (untrusted).
  * Tags survive context compression (the tag markers are preserved by
    truncate_to_context's head+tail protection).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ===========================================================================
# Trust levels
# ===========================================================================
class Provenance(str, Enum):
    """Trust level of a context-window chunk.

    The string value is the tag name used in the delimited form
    (e.g. ``<provenance type="tool_output">...</provenance>``).
    """

    SYSTEM = "system"            # trusted — system prompt
    USER = "user"                # trusted — user message
    TOOL_OUTPUT = "tool_output"  # untrusted — spotlighted
    FILE = "file"                # untrusted
    MEMORY = "memory"            # semi-trusted — extracted from prior turns
    FEDERATION = "federation"    # untrusted — external agent
    RETRIEVED = "retrieved"      # untrusted — search results


# Trusted provenance types — only these may carry tool invocations.
TRUSTED_PROVENANCE: Tuple[Provenance, ...] = (Provenance.SYSTEM, Provenance.USER)

# Semi-trusted — may carry facts (memory layer), but tool invocations
# from these are rejected too (extracted facts can be prompt-injected).
SEMI_TRUSTED_PROVENANCE: Tuple[Provenance, ...] = (Provenance.MEMORY,)


def is_trusted(provenance: Provenance) -> bool:
    """True if chunks of this provenance may carry tool invocations."""
    return provenance in TRUSTED_PROVENANCE


# ===========================================================================
# Tagged chunk dataclass
# ===========================================================================
@dataclass(frozen=True)
class ProvenanceTag:
    """A single tagged context-window chunk.

    Attributes:
        type: the Provenance trust level.
        content: the chunk text.
        source: optional source identifier (tool name, file path, URL).
        timestamp: optional ISO timestamp for ordering.
    """

    type: Provenance
    content: str
    source: Optional[str] = None
    timestamp: Optional[str] = None

    @property
    def trusted(self) -> bool:
        return is_trusted(self.type)

    def render(self) -> str:
        """Render this chunk in delimited form for the context window.

        Format: ``<provenance type="tool_output" source="browser_tool">...content...</provenance>``

        Trusted chunks are rendered WITHOUT delimiters — they are the
        agent's own context, not spotlighted content.
        """
        if self.trusted:
            return self.content
        attrs = [f'type="{self.type.value}"']
        if self.source:
            attrs.append(f'source="{_escape_attr(self.source)}"')
        if self.timestamp:
            attrs.append(f'at="{_escape_attr(self.timestamp)}"')
        return (
            f"<provenance {' '.join(attrs)}>\n"
            f"{self.content}\n"
            f"</provenance>"
        )


def _escape_attr(value: str) -> str:
    """Escape a value for inclusion in an XML-style attribute."""
    return (value or "").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


# ===========================================================================
# Tagger
# ===========================================================================
class ProvenanceTagger:
    """Tags context-window chunks with their provenance.

    Usage:
        tagger = ProvenanceTagger()
        chunks = [
            tagger.system(SYSTEM_PROMPT),
            tagger.user(user_msg),
            tagger.tool_output(browser_result, source="browser_tool"),
        ]
        context_window = "\\n\\n".join(c.render() for c in chunks)
    """

    def system(self, content: str) -> ProvenanceTag:
        return ProvenanceTag(type=Provenance.SYSTEM, content=content)

    def user(self, content: str) -> ProvenanceTag:
        return ProvenanceTag(type=Provenance.USER, content=content)

    def tool_output(self, content: str, *, source: Optional[str] = None) -> ProvenanceTag:
        return ProvenanceTag(type=Provenance.TOOL_OUTPUT, content=content, source=source)

    def file(self, content: str, *, source: Optional[str] = None) -> ProvenanceTag:
        return ProvenanceTag(type=Provenance.FILE, content=content, source=source)

    def memory(self, content: str, *, source: Optional[str] = None) -> ProvenanceTag:
        return ProvenanceTag(type=Provenance.MEMORY, content=content, source=source)

    def federation(self, content: str, *, source: Optional[str] = None) -> ProvenanceTag:
        return ProvenanceTag(type=Provenance.FEDERATION, content=content, source=source)

    def retrieved(self, content: str, *, source: Optional[str] = None) -> ProvenanceTag:
        return ProvenanceTag(type=Provenance.RETRIEVED, content=content, source=source)


# ===========================================================================
# Tag parsing (for the agent loop to refuse tool calls from untrusted chunks)
# ===========================================================================

# Regex extracts <provenance type="X" source="Y">...</provenance> blocks.
# Used by the agent loop to identify which provenance a parsed tool call
# came from. Trusted chunks have no tag, so untagged content defaults to
# USER (the safest trusted assumption — without this, every prompt would
# be refused).
import re

_PROVENANCE_RE = re.compile(
    r'<provenance\s+([^>]*)>(.*?)</provenance>',
    re.DOTALL,
)
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def parse_tags(text: str) -> List[Tuple[Provenance, str, int, int]]:
    """Find all tagged chunks in ``text``.

    Returns a list of ``(provenance, content, start, end)`` tuples where
    start/end are character offsets into ``text`` covering the full tag.
    Untagged content is NOT included — callers treat anything outside
    these ranges as USER (trusted).
    """
    out: List[Tuple[Provenance, str, int, int]] = []
    for m in _PROVENANCE_RE.finditer(text):
        attr_str = m.group(1)
        attrs = dict(_ATTR_RE.findall(attr_str))
        type_str = attrs.get("type", "user")
        try:
            prov = Provenance(type_str)
        except ValueError:
            prov = Provenance.USER  # unknown tag → safest trusted default
        content = m.group(2)
        out.append((prov, content, m.start(), m.end()))
    return out


def is_tool_invocation_from_trusted(
    full_text: str,
    tool_invocation_offset: int,
) -> bool:
    """Check whether a tool invocation at the given offset is from a trusted chunk.

    Used by the agent loop after parsing a tool call to refuse execution
    if the call originated inside an untrusted chunk. The offset is the
    character index of the tool-call text inside ``full_text``.

    Defaults to True (trusted) when the offset is outside any tag —
    matching the convention that untagged content is USER.
    """
    for prov, _content, start, end in parse_tags(full_text):
        if start <= tool_invocation_offset < end:
            return is_trusted(prov)
    return True  # outside any tag → trusted (USER)


# ===========================================================================
# Convenience: assemble a context window with proper tagging
# ===========================================================================
def assemble_context(chunks: List[ProvenanceTag]) -> str:
    """Assemble a context window from tagged chunks.

    Trusted chunks render raw; untrusted chunks are spotlighted via
    <provenance> delimiters. Order is preserved.
    """
    return "\n\n".join(c.render() for c in chunks)
