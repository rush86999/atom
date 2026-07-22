"""Formal verifier — symbolic equivalence for math / formal answers.

For math, the only robust notion of "correct" is provability. Without
a full proof assistant (see VERGE), the cheap approximation that
captures the vast majority of real-world cases is *symbolic
equivalence*: two answers are the same iff
``simplify(a - b) == 0``. This collapses lexical variation
(``x**2`` vs ``x*x`` vs ``x*x/1``) that would defeat voting.

Candidates are read from ``candidate.get("answer")`` (falling back to
``str(candidate)``). Candidates are parsed with
:func:`sympy.sympify`, grouped by equivalence, and the largest group's
first member is returned — provided it constitutes a majority. On any
parse failure or ambiguity we fall back to exact-string majority vote
(a strict improvement over nothing). If ``sympy`` is not installed,
``winner=None`` is returned and the orchestrator falls back to
voting.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from core.orchestration.verification.base import (
    VerificationResult,
    VerificationStrategy,
    Verifier,
)

logger = logging.getLogger(__name__)

try:  # Optional dependency — degrade gracefully if absent.
    import sympy  # type: ignore
    _HAS_SYMPY = True
except ImportError:  # pragma: no cover — exercised only when sympy missing
    sympy = None
    _HAS_SYMPY = False


class FormalVerifier(Verifier):
    """SymPy equivalence on numeric / symbolic answers."""

    strategy = VerificationStrategy.FORMAL

    async def verify(
        self,
        candidates: List[Any],
        step: Any,
        context: Any,
    ) -> VerificationResult:
        domain = getattr(context, "_resolved_domain", None) or "unknown"

        if not candidates:
            return VerificationResult.empty(domain, self.strategy, reason="no candidates")

        if not _HAS_SYMPY:
            return VerificationResult.empty(
                domain, self.strategy,
                reason="sympy not installed; cannot do formal verification",
            )

        parsed = self._parse_all(candidates)
        # parsed[i] = (candidate, expr_or_None, raw_string)
        valid = [(c, e, s) for (c, e, s) in parsed if e is not None]

        if not valid:
            # Nobody parsed — fall back to exact-string majority.
            return self._exact_string_fallback(candidates, domain)

        groups = self._group_equivalent([e for (_, e, _) in valid])
        # largest group by population
        largest_idx = max(range(len(groups)), key=lambda i: len(groups[i]))
        largest = groups[largest_idx]
        if not largest:
            return self._exact_string_fallback(candidates, domain)

        # Require a strict majority of *valid* (parseable) answers to
        # claim a formal winner; otherwise the symbolic signal is too
        # weak to override voting.
        majority_threshold = len(valid) / 2.0
        if len(largest) <= majority_threshold:
            return self._exact_string_fallback(candidates, domain)

        winner_candidate = valid[largest[0]][0]
        confidence = len(largest) / len(candidates)
        return VerificationResult(
            winner=winner_candidate,
            strategy=self.strategy,
            domain=domain,
            confidence=confidence,
            details={
                "mode": "sympy_equivalence",
                "group_size": len(largest),
                "group_count": len(groups),
                "valid_count": len(valid),
                "candidate_count": len(candidates),
            },
            reason=f"{len(largest)}/{len(valid)} parseable answers are symbolically equivalent",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_answer(candidate: Any) -> str:
        if isinstance(candidate, dict):
            for key in ("answer", "result", "value", "output"):
                val = candidate.get(key)
                if val is not None:
                    return str(val).strip()
        return str(candidate).strip()

    def _parse_all(self, candidates: List[Any]) -> List[Tuple[Any, Any, str]]:
        out: List[Tuple[Any, Any, str]] = []
        for c in candidates:
            raw = self._extract_answer(c)
            expr = self._safe_sympify(raw)
            out.append((c, expr, raw))
        return out

    @staticmethod
    def _safe_sympify(text: str) -> Any:
        if not text:
            return None
        try:
            # local_dict={} forbids implicit name lookup so a stray
            # word like "answer" doesn't get turned into a Symbol.
            return sympy.sympify(text, locals={}, evaluate=True)
        except Exception:  # noqa: BLE001 — sympify is liberal; many inputs fail
            return None

    def _group_equivalent(self, exprs: List[Any]) -> List[List[int]]:
        """Union-find-ish grouping by ``simplify(a - b) == 0``."""
        n = len(exprs)
        # parent[i] = root of i's group
        parent = list(range(n))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj

        for i in range(n):
            for j in range(i + 1, n):
                if find(i) == find(j):
                    continue
                try:
                    diff = sympy.simplify(exprs[i] - exprs[j])
                    if diff == 0:
                        union(i, j)
                except Exception:  # noqa: BLE001
                    continue

        groups_map: Dict[int, List[int]] = {}
        for i in range(n):
            groups_map.setdefault(find(i), []).append(i)
        return list(groups_map.values())

    def _exact_string_fallback(
        self,
        candidates: List[Any],
        domain: Any,
    ) -> VerificationResult:
        """When symbolic verification can't decide, do a string majority vote.

        Notably this is *not* the orchestrator's voting fallback — we
        stay within the FORMAL strategy so the result's diagnostics
        reflect what was attempted. ``winner=None`` if no strict
        majority exists; the orchestrator will then run VOTING.
        """
        raws = [self._extract_answer(c) for c in candidates]
        counts = Counter(raws)
        if not counts:
            return VerificationResult.empty(domain, self.strategy, reason="no answers to compare")
        winner_str, count = counts.most_common(1)[0]
        if count > len(candidates) / 2.0:
            for c, r in zip(candidates, raws):
                if r == winner_str:
                    return VerificationResult(
                        winner=c,
                        strategy=self.strategy,
                        domain=domain,
                        confidence=count / len(candidates),
                        details={
                            "mode": "exact_string_fallback",
                            "majority_count": count,
                            "distinct": len(counts),
                        },
                        reason="symbolic parse failed; exact-string majority used",
                    )
        return VerificationResult(
            winner=None,
            strategy=self.strategy,
            domain=domain,
            confidence=0.0,
            details={
                "mode": "no_majority",
                "distinct": len(counts),
                "candidate_count": len(candidates),
            },
            reason="no symbolic or exact-string majority",
        )


__all__ = ["FormalVerifier"]
