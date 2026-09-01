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
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def knowledge_spotlight_enabled() -> bool:
    """Master switch for rendering the knowledge/memory leg as delimited
    UNTRUSTED retrieved content (spotlighting). Off restores the legacy bare
    rendering. Separate from ATOM_DATAMARKING so this one surface can be
    flipped without changing every tool-output renderer."""
    return os.getenv("ATOM_KNOWLEDGE_SPOTLIGHT_ENABLED", "true").lower() == "true"


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
        # Escape any provenance-tag-shaped text inside the content so an
        # untrusted chunk cannot close its own spotlight and re-open one as a
        # trusted type (indirect-prompt-injection escape).
        body = escape_provenance_text(self.content)
        return (
            f"<provenance {' '.join(attrs)}>\n"
            f"{body}\n"
            f"</provenance>"
        )


def _escape_attr(value: str) -> str:
    """Escape a value for inclusion in an XML-style attribute."""
    return (value or "").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def escape_provenance_text(value: Any) -> str:
    """Neutralize provenance-tag-shaped text in UNTRUSTED content or metadata
    rendered inside a spotlight block.

    Without this, a retrieved document — or attacker-controlled METADATA like
    an email sender name — can close its own ``</provenance>`` block early and
    re-open one as a trusted type (indirect prompt-injection escape). This is
    the single definition of the rule so every renderer escapes identically:
    ``ProvenanceTag.render``, the memory-context assembler, and the agents'
    knowledge summaries.
    """
    return str(value or "").replace(
        "</provenance", "&lt;/provenance"
    ).replace("<provenance", "&lt;provenance")


def render_knowledge_summaries(
    knowledge: List[Dict[str, Any]], limit: int = 3, char_cap: int = 100
) -> Optional[str]:
    """Render the RELEVANT KNOWLEDGE memory section from retrieved docs.

    One implementation for every agent prompt builder (atom_meta_agent,
    generic_agent): with knowledge spotlighting enabled, each summary is a
    delimited UNTRUSTED ProvenanceTag — the same contract as the assembler's
    knowledge leg (untrusted retrieved data, delimited, source-attributed,
    escape-proof). Disabled, the legacy bare-bullet rendering is kept.

    Returns the full section text, or None when there is no knowledge.
    """
    if not knowledge:
        return None
    if knowledge_spotlight_enabled():
        rendered = []
        for k in knowledge[:limit]:
            src = str(k.get("source") or "doc")
            body = str(k.get("text", ""))
            if len(body) > char_cap:
                body = body[:char_cap] + "…"
            rendered.append(
                ProvenanceTag(
                    type=Provenance.RETRIEVED,
                    source=src,
                    content=body,
                ).render()
            )
        return "RELEVANT KNOWLEDGE:\n" + "\n".join(rendered)
    lines = [
        f"- ({k.get('source') or 'doc'}: {str(k.get('text', ''))[:char_cap]}...)"
        for k in knowledge[:limit]
    ]
    return "RELEVANT KNOWLEDGE:\n" + "\n".join(lines)


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
