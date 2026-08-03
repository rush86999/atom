"""Token compression pipeline for LLM prompts and tool outputs.

Two engines, both gated behind ``ATOM_COMPRESSION_ENABLED`` (default true):

  - **RTK**: compresses terminal/build/test log output (lossless signal
    preservation — strips ANSI noise, collapses repeated lines, detects
    test-runner formats). NEVER touches structured data (JSON/SQL/API
    responses). Safe for business automation where prompts carry financial
    records.

  - **Session-dedup**: replaces byte-identical repeated text across turns
    with reference markers (exact-match hash only — zero information loss).
    No semantic/Caveman rewriting.

Evidence basis: observation compression (stripping noise from tool output)
is categorized as safe vs. lossy prompt compression which degrades agentic
accuracy (ICML 2025, arXiv 2510.22963). The structured-data guard ensures
business records (invoices, CRM data, SQL results) are never altered.

See docs/architecture/TOKEN_COMPRESSION.md.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# --- Configuration (default ON per user decision) ---------------------------

COMPRESSION_ENABLED: bool = os.getenv("ATOM_COMPRESSION_ENABLED", "true").lower() == "true"
RTK_ENABLED: bool = os.getenv("COMPRESS_RTK_ENABLED", "true").lower() == "true"
SESSION_DEDUP_ENABLED: bool = os.getenv("COMPRESS_SESSION_DEDUP_ENABLED", "true").lower() == "true"

# Max chars per observation block before truncation (RTK).
RTK_MAX_SECTION_CHARS: int = int(os.getenv("COMPRESS_RTK_MAX_SECTION_CHARS", "8000"))


@dataclass
class CompressionMetrics:
    """Result of a compression pass."""

    original_tokens: int = 0
    compressed_tokens: int = 0
    engines_applied: List[str] = field(default_factory=list)

    @property
    def savings_tokens(self) -> int:
        return max(0, self.original_tokens - self.compressed_tokens)

    @property
    def savings_pct(self) -> float:
        if self.original_tokens <= 0:
            return 0.0
        return (self.savings_tokens / self.original_tokens) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "savings_tokens": self.savings_tokens,
            "savings_pct": round(self.savings_pct, 1),
            "engines_applied": self.engines_applied,
        }


class CompressionPipeline:
    """Runs enabled compression engines in sequence on a text input.

    Each engine receives the output of the previous one. Metrics accumulate.
    All engines are best-effort: any exception is caught and the input is
    returned unchanged (compression must never break the hot path).
    """

    def __init__(self) -> None:
        from core.llm.compression.rtk_engine import RTKEngine

        self._rtk = RTKEngine()

    def compress_tool_output(self, text: str) -> tuple[str, CompressionMetrics]:
        """Compress free-form tool/terminal output (RTK path).

        This is the ONLY compression entry point for prompt content. It
        targets terminal/build/test logs — structured data (JSON, SQL, API
        responses) is detected and skipped entirely.
        """
        metrics = CompressionMetrics()
        if not text or not text.strip():
            return text, metrics

        try:
            from core.llm.context.token_counter import TokenCounter

            tc = TokenCounter()
            metrics.original_tokens = tc.count_tokens(text)
        except Exception:
            metrics.original_tokens = len(text) // 4

        if not COMPRESSION_ENABLED or not RTK_ENABLED:
            metrics.compressed_tokens = metrics.original_tokens
            return text, metrics

        result = text
        try:
            result = self._rtk.compress(result)
            if result != text:
                metrics.engines_applied.append("rtk")
        except Exception:
            logger.debug("RTK compression failed; returning original", exc_info=True)
            result = text

        try:
            from core.llm.context.token_counter import TokenCounter

            tc = TokenCounter()
            metrics.compressed_tokens = tc.count_tokens(result)
        except Exception:
            metrics.compressed_tokens = len(result) // 4

        if metrics.savings_tokens > 0:
            logger.info(
                f"[Compression] RTK saved {metrics.savings_tokens} tokens "
                f"({metrics.savings_pct:.0f}%) via {metrics.engines_applied}"
            )

        return result, metrics


# Module-level singleton (stateless pipeline).
_default_pipeline: Optional[CompressionPipeline] = None


def get_compression_pipeline() -> CompressionPipeline:
    """Return the process-wide default CompressionPipeline."""
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = CompressionPipeline()
    return _default_pipeline
