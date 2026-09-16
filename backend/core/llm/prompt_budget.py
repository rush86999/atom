# -*- coding: utf-8 -*-
"""Prompt token accounting — the number the 18k-char evidence budget never had.

The incident audit set ``ATOM_EVIDENCE_BUDGET_CHARS = 18000`` by measurement
and flagged it as underived: a *character* budget says nothing about whether
the assembled prompt fits the model that will receive it, because the same
18k characters cost a different number of tokens depending on content, and
because evidence is only ONE of the sections competing for the window. The
other sections — system instructions, conversation history, the open canvas,
tool schemas — were never counted at all.

This module makes the whole prompt countable:

    sections = {
        "instructions": system_prompt,
        "history": history_text,
        "canvas": canvas_text,
        "evidence": evidence_block,
    }
    acct = account_prompt(sections, provider_id="openrouter")
    acct.total_input_tokens      # everything the model will read
    acct.available_input_tokens  # what the window allows after the output reservation
    acct.fits                    # bool

and provides ``trim_to_tokens``, which trims a section to a token budget while
keeping the lines that carry decisive content (rows, formulas, units, dates,
attribution) — the categories the audit named, which are exactly the ones a
naive head/tail cut destroys.

Nothing here raises: an accounting helper must never be the reason a turn
fails. When the tokenizer is unavailable it falls back to a conservative
character heuristic and says so via ``estimated=True``.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# The per-call completion budget the handler uses when the caller names none.
DEFAULT_OUTPUT_RESERVATION = int(
    os.getenv("ATOM_COMPLETION_MAX_TOKENS", "6000") or 6000)

# Fallback used when no provider-specific window is configured. Deliberately
# conservative — understating the window over-trims, which is recoverable;
# overstating it truncates the answer, which is not.
FALLBACK_CONTEXT_WINDOW = int(
    os.getenv("ATOM_PROMPT_FALLBACK_CONTEXT", "32000") or 32000)

_TOKENIZER = None
_TOKENIZER_TRIED = False

# Lines carrying decisive content. Ordering matters only for readability; a
# line matching ANY pattern is kept ahead of prose.
_DECISIVE_PATTERNS: Tuple[Tuple[str, re.Pattern], ...] = (
    ("row", re.compile(r"^\s*(?:R\d{1,5}\b|\|\s*R\d{1,5}\b)")),
    ("formula", re.compile(r"\bFORMULAS?\b|\b[A-Z]{1,3}\d{1,5}\s*==")),
    ("sql", re.compile(r"\bSQL RESULT\b", re.IGNORECASE)),
    ("money", re.compile(r"[$€£₹]\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:USD|CAD|EUR|GBP|INR)\b")),
    ("unit", re.compile(
        r"\b\d+(?:\.\d+)?\s?(?:kg|g|lb|lbs|mm|cm|m|in|ft|psi|bar|kW|W|V|A|"
        r"Hz|rpm|L|ml|gal|pcs|units?|ea|hrs?|days?|weeks?|months?|years?)\b",
        re.IGNORECASE)),
    ("percent", re.compile(r"\d+(?:\.\d+)?\s?%")),
    ("date", re.compile(
        r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b"
        r"|\b\d{4}-\d{2}-\d{2}\b"
        r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
        r"\s+\d{1,2}(?:,?\s+\d{4})?\b",
        re.IGNORECASE)),
    ("attribution", re.compile(
        r"^\s*(?:from|to|cc|bcc|sender|recipient|sent|received|subject|re)\s*:",
        re.IGNORECASE)),
    ("citation", re.compile(r"\b(?:full|open):\s?knowledge/")),
)


def _tokenizer():
    """cl100k_base via tiktoken, cached; None when unavailable."""
    global _TOKENIZER, _TOKENIZER_TRIED
    if _TOKENIZER_TRIED:
        return _TOKENIZER
    _TOKENIZER_TRIED = True
    try:
        import tiktoken

        _TOKENIZER = tiktoken.get_encoding("cl100k_base")
    except Exception as e:  # noqa: BLE001 — accounting must not depend on it
        logger.debug(f"tiktoken unavailable, using char heuristic: {e}")
        _TOKENIZER = None
    return _TOKENIZER


def count_tokens(text: Optional[str]) -> Tuple[int, bool]:
    """(token_count, estimated).

    ``estimated`` is True when the count came from the character heuristic
    rather than a real tokenizer — callers that make a budget decision should
    surface it rather than presenting a guess as a measurement.
    """
    if not text:
        return 0, False
    enc = _tokenizer()
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=())), False
        except Exception as e:  # noqa: BLE001
            logger.debug(f"tokenizer failed, using char heuristic: {e}")
    # ~4 chars/token is the standard English rule of thumb; ceil so a short
    # string never counts as zero tokens.
    return max(1, (len(text) + 3) // 4), True


def context_window_for(provider_id: Optional[str]) -> Tuple[int, bool]:
    """(window, from_provider_config).

    Reads the provider's configured cap (``OPENROUTER_MAX_CONTEXT`` etc. via
    ``provider_rate_limits``); falls back to a conservative constant so an
    unconfigured provider is never treated as unbounded.
    """
    if provider_id:
        try:
            from core.llm.provider_rate_limits import get_provider_rate_tracker

            window = get_provider_rate_tracker().get_max_context(provider_id)
            if window and window > 0:
                return int(window), True
        except Exception as e:  # noqa: BLE001
            logger.debug(f"context window lookup failed for {provider_id}: {e}")
    return FALLBACK_CONTEXT_WINDOW, False


@dataclass
class PromptAccount:
    """What the assembled prompt costs, section by section."""

    sections: Dict[str, int] = field(default_factory=dict)
    total_input_tokens: int = 0
    output_reservation: int = DEFAULT_OUTPUT_RESERVATION
    context_window: int = FALLBACK_CONTEXT_WINDOW
    window_from_provider: bool = False
    estimated: bool = False

    @property
    def available_input_tokens(self) -> int:
        """Window left for input once the output reservation is honoured."""
        return max(0, self.context_window - self.output_reservation)

    @property
    def fits(self) -> bool:
        return self.total_input_tokens <= self.available_input_tokens

    @property
    def overflow_tokens(self) -> int:
        return max(0, self.total_input_tokens - self.available_input_tokens)

    @property
    def largest_section(self) -> Optional[str]:
        return max(self.sections, key=self.sections.get) if self.sections else None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "sections": dict(self.sections),
            "total_input_tokens": self.total_input_tokens,
            "output_reservation": self.output_reservation,
            "context_window": self.context_window,
            "window_from_provider": self.window_from_provider,
            "available_input_tokens": self.available_input_tokens,
            "fits": self.fits,
            "overflow_tokens": self.overflow_tokens,
            "largest_section": self.largest_section,
            "estimated": self.estimated,
        }


def account_prompt(
    sections: Dict[str, Optional[str]],
    provider_id: Optional[str] = None,
    output_reservation: Optional[int] = None,
) -> PromptAccount:
    """Count every section of the assembled prompt and decide whether it fits.

    ``sections`` should include EVERYTHING the model will read — instructions,
    history, canvas, evidence — not just the evidence block. Counting only the
    evidence is how an 18k-char budget came to be treated as a context bound.
    """
    acct = PromptAccount()
    window, from_provider = context_window_for(provider_id)
    acct.context_window = window
    acct.window_from_provider = from_provider
    acct.output_reservation = int(
        output_reservation
        if output_reservation is not None
        else DEFAULT_OUTPUT_RESERVATION)
    total = 0
    for name, text in (sections or {}).items():
        tokens, estimated = count_tokens(text)
        acct.sections[name] = tokens
        acct.estimated = acct.estimated or estimated
        total += tokens
    acct.total_input_tokens = total
    return acct


def relevant_window(
    text: Optional[str],
    query: Optional[str],
    max_chars: int = 3800,
    head_chars: int = 2600,
    tail_chars: int = 1200,
) -> Tuple[str, bool, Optional[int]]:
    """A bounded window of ``text`` centred on the part the QUERY is about.

    Returns ``(window, matched, line_number)``.

    Why not a plain head/tail: the one-shot reply model sees this window
    instead of the full artifact, so a head+tail cut silently omits anything
    in the middle — which is exactly where a forwarded thread's decisive line
    sits. Scoring lines by the query's own tokens puts the window where the
    question is, and when nothing matches the caller can say so instead of
    implying the artifact was read in full.

    ``matched=False`` means no query token appeared anywhere in the text: the
    window is then a plain head/tail and the caller MUST NOT present it as a
    complete read.
    """
    if not text:
        return "", False, None
    if max_chars <= 0:
        return "", False, None
    if len(text) <= max_chars:
        return text, True, 0

    tokens = {
        t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{2,}", (query or "").lower())
    }
    lines = text.splitlines()
    best_idx: Optional[int] = None
    best_score = 0
    if tokens:
        for idx, line in enumerate(lines):
            low = line.lower()
            score = sum(1 for t in tokens if t in low)
            if score > best_score:
                best_score = score
                best_idx = idx

    if best_idx is None:
        head = text[:head_chars]
        tail = text[-tail_chars:] if len(text) > head_chars + tail_chars else ""
        return (head + ("\n…\n" + tail if tail else "")), False, None

    # Centre the window on the matched line, weighted toward the text before
    # it (a decisive row usually follows its own context).
    before_chars = int(max_chars * 0.6)
    after_chars = max_chars - before_chars
    out: List[str] = []
    used = 0
    # walk backwards then forwards from the match
    start = best_idx
    while start > 0 and used < before_chars:
        start -= 1
        used += len(lines[start]) + 1
    used = 0
    end = best_idx
    while end < len(lines) - 1 and used < after_chars:
        end += 1
        used += len(lines[end]) + 1
    out = lines[start:end + 1]
    window = "\n".join(out)
    if len(window) > max_chars * 2:  # guard against pathological long lines
        window = window[: max_chars * 2]
    prefix = "…\n" if start > 0 else ""
    suffix = "\n…" if end < len(lines) - 1 else ""
    return prefix + window + suffix, True, best_idx + 1


def decisive_kind(line: str) -> Optional[str]:
    """Which decisive category a line belongs to, else None."""
    for kind, pattern in _DECISIVE_PATTERNS:
        if pattern.search(line):
            return kind
    return None


def trim_to_tokens(
    text: Optional[str],
    max_tokens: int,
    keep_order: bool = True,
) -> Tuple[str, Dict[str, int]]:
    """Trim ``text`` to ``max_tokens``, spending the budget on decisive lines
    first and prose only with what remains.

    Returns (trimmed_text, stats) where stats counts the decisive lines kept
    per category — so a caller can report *what survived* instead of claiming
    completeness from the presence of a single citation.

    A pure head/tail cut is what loses a mid-document decisive row; this keeps
    the rows, formulas, units, dates and attribution lines wherever they are.
    """
    stats: Dict[str, int] = {}
    if not text:
        return "", stats
    if max_tokens <= 0:
        return "", stats

    lines = text.splitlines()
    decisive: List[Tuple[int, str, str]] = []
    prose: List[Tuple[int, str]] = []
    for idx, line in enumerate(lines):
        kind = decisive_kind(line)
        if kind:
            decisive.append((idx, line, kind))
        elif line.strip():
            prose.append((idx, line))

    kept: List[Tuple[int, str]] = []
    used = 0
    for idx, line, kind in decisive:
        cost, _est = count_tokens(line)
        if used + cost > max_tokens:
            continue
        kept.append((idx, line))
        used += cost
        stats[kind] = stats.get(kind, 0) + 1
    for idx, line in prose:
        cost, _est = count_tokens(line)
        if used + cost > max_tokens:
            break
        kept.append((idx, line))
        used += cost

    if keep_order:
        kept.sort(key=lambda p: p[0])
    dropped = len(lines) - len(kept)
    out = "\n".join(line for _idx, line in kept)
    if dropped > 0:
        stats["dropped_lines"] = dropped
    stats["tokens_used"] = used
    return out, stats
