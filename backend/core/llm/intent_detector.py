"""
Domain/Intent Detector for LLM routing.

Complements the cognitive tier system (which answers "how hard is this?") with
a domain classifier (which answers "what kind of task is this?"). The detected
intent nudges cognitive tier selection and enriches the learning-router cache
key so per-model predictors can learn intent-specific preferences.

Design mirrors ``CognitiveClassifier`` (weighted regex + structural signals +
task bias) and Manifest's specificity detector (keyword trie + tool-prefix
heuristics + session stickiness). Six routing-relevant categories covering the
distinctions that actually shift model selection.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# --- Categories --------------------------------------------------------------

INTENT_CATEGORIES: Tuple[str, ...] = (
    "coding",
    "data_analysis",
    "web_browsing",
    "creative_writing",
    "reasoning",
    "conversation",
)

_VALID_CATEGORIES = frozenset(INTENT_CATEGORIES)


def is_valid_intent(value: str) -> bool:
    """Return True if ``value`` is a recognized intent category."""
    return value in _VALID_CATEGORIES


# --- Keyword patterns --------------------------------------------------------
# Each entry: (compiled_regex, weight). Matches contribute ``weight`` to the
# category. Patterns use word boundaries and IGNORECASE. A single prompt may
# match multiple categories; the highest-scoring category that clears its
# activation threshold wins.

_INTENT_PATTERNS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "coding": (
        (r"\b(code|coding|function|class|method|def|import|return|async|await)\b", 3),
        (r"\b(debug|debugging|bug|fix|fixes|fixed|refactor|refactoring|compile|compiler|lint|linting)\b", 3),
        (r"\b(api|endpoint|webhook|schema|migration|sql|postgresql|mongodb|redis)\b", 3),
        (r"\b(docker|kubernetes|terraform|aws|gcp|azure|lambda|serverless)\b", 3),
        (r"\b(stack ?trace|exception|error|traceback|segfault|crash)\b", 2),
        (r"\b(unit test|integration test|pytest|jest|coverage|mock|stub)\b", 3),
        (r"\b(algorithm|data structure|complexity|big-?o|recursion|iterate)\b", 3),
    ),
    "data_analysis": (
        (r"\b(analyze|analysis|dataset|dataframe|csv|json|parquet|warehouse)\b", 3),
        (r"\b(regression|correlation|statistics|statistical|distribution|variance)\b", 3),
        (r"\b(chart|graph|plot|visuali[sz]e|visuali[sz]ation|dashboard|histogram)\b", 3),
        (r"\b(pandas|numpy|scipy|matplotlib|tableau|power ?bi|excel ?formula)\b", 3),
        (r"\b(mean|median|mode|percentile|outlier|anomaly|trend|forecast)\b", 3),
        (r"\b(machine learning|model training|feature engineering|inference)\b", 3),
    ),
    "web_browsing": (
        (r"\b(search the web|google|browse|browsing|look ?up online)\b", 3),
        (r"\b(latest news|current (price|rate|value)|today'?s (price|news))\b", 3),
        (r"\b(website|web ?page|url|http[s]?://|hyperlink|landing page)\b", 2),
        (r"\b(scrape|crawl|crawler|spider|extract from (the )?web)\b", 3),
        (r"\b(real-?time (data|price|info)|live (price|rates?|stock))\b", 3),
        (r"\b(who won|what happened|recent (event|update|release))\b", 2),
    ),
    "creative_writing": (
        (r"\b(write a (story|poem|song|novel|screenplay|script|letter|essay))\b", 4),
        (r"\b(creative|creatively|imaginative|fiction|nonfiction|prose)\b", 3),
        (r"\b(poem|poetry|haiku|sonnet|stanza|verse|lyrics?|chorus)\b", 3),
        (r"\b(character|protagonist|antagonist|plot|narrative|setting|dialogue)\b", 3),
        (r"\b(screenplay|screenwriting|monologue|soliloquy|adaptation)\b", 3),
        (r"\b(tagline|slogan|jingle|copywriting|ad copy|brand voice)\b", 3),
    ),
    "reasoning": (
        (r"\b(prove|proof|theorem|lemma|corollary|axiom|postulate)\b", 4),
        (r"\b(step[- ]by[- ]step|reason step|chain of (thought|reasoning))\b", 3),
        (r"\b(logic|logical|deduce|deduction|infer|inference|inductive|deductive)\b", 3),
        (r"\b(derive|derivation|because|therefore|thus|hence|implies|iff)\b", 3),
        (r"\b(contradiction|counterexample|necessary|sufficient|equivalent)\b", 3),
        (r"\b(puzzle|riddle|brain ?teaser|logic problem|word problem)\b", 3),
        (r"\b(QED|proof by (induction|contradiction|cases)|reductio)\b", 4),
    ),
    "conversation": (
        # Low weight: these are common but only signal "casual" when nothing
        # else dominates. Keeps a "hi, debug my function" prompt classified
        # as coding, not conversation.
        (r"\b(hello|hi|hey|greetings|good (morning|afternoon|evening))\b", 1),
        (r"\b(thanks|thank you|appreciate|cheers|got it|makes sense)\b", 1),
        (r"\b(how are you|how'?s it going|what'?s up|how do you do)\b", 1),
        (r"\b(chat|let'?s talk|can we discuss|quick question)\b", 1),
    ),
}

# Per-category activation thresholds. A category must reach this score to be
# considered the winner. Calibrated so a single strong match (~3) plus a
# structural boost clears the bar, but a lone weak "conversation" hit does not.
_ACTIVATION_THRESHOLDS: Dict[str, int] = {
    "coding": 3,
    "data_analysis": 3,
    "web_browsing": 3,
    "creative_writing": 4,  # higher bar — "write" alone is ambiguous
    "reasoning": 3,
    "conversation": 2,
}

# --- Tool-name prefix heuristics --------------------------------------------
# When the request carries agent tools, the tool name prefix strongly signals
# intent. Mirrors Manifest's TOOL_NAME_PATTERNS.
_TOOL_PREFIX_MAP: Dict[str, str] = {
    "browser_": "web_browsing",
    "playwright_": "web_browsing",
    "web_": "web_browsing",
    "search_": "web_browsing",
    "scraper_": "web_browsing",
    "code_": "coding",
    "editor_": "coding",
    "github_": "coding",
    "gitlab_": "coding",
    "database_": "data_analysis",
    "sql_": "data_analysis",
    "chart_": "data_analysis",
    "analytics_": "data_analysis",
}
_TOOL_PREFIX_WEIGHT = 3  # one matching tool prefix == one strong keyword

# --- Session stickiness ------------------------------------------------------
# If the last few turns classified as the same category, add a bias so an
# ambiguous current turn keeps the same routing intent. Tuned to stabilize a
# coding session without locking in: a strong anchor on the current turn
# (>=3 above threshold) still flips.
_STICKY_AGREEMENT_MIN = 3
_STICKY_HISTORY_WINDOW = 3
# Must be >= the highest activation threshold (3) so a fully-neutral turn
# (zero keyword signals) with 3-turn agreement still keeps the intent — the
# previous bias of 2 could never clear the 3-point bar, so the documented
# "ambiguous current turn keeps the same routing intent" never happened.
_STICKY_BIAS = 3


@dataclass
class IntentResult:
    """Outcome of intent detection.

    ``category`` is ``None`` when no signal cleared its activation threshold
    (weak/ambiguous prompt) — callers fall back to default routing.
    ``confidence`` is in [0, 1], scaling how far the winning score exceeded
    its threshold.
    """

    category: Optional[str]
    confidence: float


class IntentDetector:
    """Detects the routing-relevant domain/intent of a prompt.

    Combines weighted keyword matching, structural signal boosts (code fences,
    URLs), tool-name prefix heuristics, and optional session stickiness. The
    output is a single best-fit category (or None) suitable for tier nudging
    and as a learning-router cache-key dimension.
    """

    def __init__(self) -> None:
        self._compiled: Dict[str, List[Tuple[re.Pattern, int]]] = {
            cat: [(re.compile(p, re.IGNORECASE), w) for p, w in pats]
            for cat, pats in _INTENT_PATTERNS.items()
        }
        # Precompile structural-signal regexes once.
        self._code_fence_re = re.compile(r"```")
        self._url_re = re.compile(r"https?://\S+|www\.\S+")
        self._long_formal_re = re.compile(r"\b(therefore|hence|thus|moreover|furthermore|consequently|nevertheless|notwithstanding)\b", re.IGNORECASE)

    def detect(
        self,
        prompt: str,
        tools: Optional[Sequence[object]] = None,
        recent_intents: Optional[Sequence[str]] = None,
        category_penalties: Optional[Dict[str, int]] = None,
    ) -> IntentResult:
        """Classify ``prompt`` into an intent category.

        Args:
            prompt: The user prompt text.
            tools: Optional sequence of tool definitions (dicts with ``name``
                or ``function.name``, or objects with a ``name`` attribute).
                Tool-name prefixes boost the matching category.
            recent_intents: Optional history of recently-detected intents for
                the same session (most-recent first). Enables stickiness.
            category_penalties: Optional per-category score subtractions (e.g.
                to down-weight a category that recently failed).

        Returns:
            IntentResult with the winning category (or None) and confidence.
        """
        if not prompt or not prompt.strip():
            return IntentResult(category=None, confidence=0.0)

        scores: Dict[str, int] = {cat: 0 for cat in INTENT_CATEGORIES}

        # 1. Weighted keyword matching.
        for cat, patterns in self._compiled.items():
            for regex, weight in patterns:
                if regex.search(prompt):
                    scores[cat] += weight

        # 2. Structural signal boosts.
        self._apply_signal_boosts(prompt, scores)

        # 3. Tool-prefix heuristics.
        if tools:
            self._apply_tool_heuristics(tools, scores)

        # 4. Session stickiness bias.
        if recent_intents:
            self._apply_session_bias(recent_intents, scores)

        # 5. Optional per-category penalties.
        if category_penalties:
            for cat, penalty in category_penalties.items():
                if cat in scores:
                    scores[cat] = max(0, scores[cat] - penalty)

        # 6. Pick the highest-scoring category that clears its threshold.
        best_cat: Optional[str] = None
        best_score = 0
        for cat in INTENT_CATEGORIES:
            threshold = _ACTIVATION_THRESHOLDS[cat]
            if scores[cat] >= threshold and scores[cat] > best_score:
                best_cat = cat
                best_score = scores[cat]

        if best_cat is None:
            return IntentResult(category=None, confidence=0.0)

        # Confidence: how far past the threshold, normalized to [0, 1].
        # best_score == threshold -> ~0.33; best_score == 2*threshold -> ~0.67;
        # best_score >= 3*threshold -> 1.0 (capped).
        cat_threshold = _ACTIVATION_THRESHOLDS[best_cat]
        confidence = min(best_score / (cat_threshold * 3), 1.0)
        return IntentResult(category=best_cat, confidence=confidence)

    # --- Tier nudge helper ---------------------------------------------------

    # CognitiveTier import is deferred to avoid a circular import at module
    # load time (cognitive_tier_system imports nothing from here, but keeping
    # the dependency lazy is safer for future refactors).
    def nudge_tier(self, intent: Optional[str], base_tier: str) -> str:
        """Apply an intent-derived floor/cap to a cognitive tier.

        Args:
            intent: Detected intent category (or None).
            base_tier: The tier selected by complexity classification. Must be
                a valid CognitiveTier value string.

        Returns:
            The (possibly nudged) tier value string. If intent is None or the
            nudge does not apply, ``base_tier`` is returned unchanged.
        """
        from core.llm.cognitive_tier_system import CognitiveTier

        try:
            tier = CognitiveTier(base_tier)
        except ValueError:
            return base_tier

        # Ordering for floor/cap comparisons.
        order = [
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY,
            CognitiveTier.COMPLEX,
        ]
        idx = order.index(tier)

        if intent in ("coding", "reasoning"):
            # These intents benefit from stronger models — floor at VERSATILE.
            versatile_idx = order.index(CognitiveTier.VERSATILE)
            if idx < versatile_idx:
                return CognitiveTier.VERSATILE.value
        elif intent == "conversation":
            # Casual chat — cap at STANDARD to avoid spending on frontier models.
            standard_idx = order.index(CognitiveTier.STANDARD)
            if idx > standard_idx:
                return CognitiveTier.STANDARD.value
        elif intent in ("data_analysis", "creative_writing"):
            # Floor at STANDARD so a complexity-misread prompt still gets a
            # capable model, but don't force premium.
            standard_idx = order.index(CognitiveTier.STANDARD)
            if idx < standard_idx:
                return CognitiveTier.STANDARD.value
        # web_browsing: no tier nudge — capability (tools/web access) matters
        # more than model tier; handled by the capability filter.

        return tier.value

    # --- Internal signal helpers --------------------------------------------

    def _apply_signal_boosts(self, prompt: str, scores: Dict[str, int]) -> None:
        # Code fences: strong coding signal.
        if self._code_fence_re.search(prompt):
            scores["coding"] += 2
        # URLs: web_browsing signal.
        if self._url_re.search(prompt):
            scores["web_browsing"] += 2
        # Long-form reasoning connectives: reasoning signal.
        if self._long_formal_re.search(prompt):
            scores["reasoning"] += 2

    def _apply_tool_heuristics(
        self, tools: Sequence[object], scores: Dict[str, int]
    ) -> None:
        for tool in tools:
            name = _extract_tool_name(tool)
            if not name:
                continue
            lower = name.lower()
            for prefix, cat in _TOOL_PREFIX_MAP.items():
                if lower.startswith(prefix):
                    scores[cat] += _TOOL_PREFIX_WEIGHT
                    break  # one boost per tool

    def _apply_session_bias(
        self, recent_intents: Sequence[str], scores: Dict[str, int]
    ) -> None:
        if len(recent_intents) < _STICKY_AGREEMENT_MIN:
            return
        window = list(recent_intents[:_STICKY_HISTORY_WINDOW])
        if len(window) < _STICKY_AGREEMENT_MIN:
            return
        first = window[0]
        if not all(c == first for c in window):
            return
        if first in scores:
            scores[first] += _STICKY_BIAS


def _extract_tool_name(tool: object) -> Optional[str]:
    """Extract a tool name from a heterogeneous tool definition.

    Handles: dicts with ``name`` or ``function.name``; objects with a ``name``
    attribute; plain strings.
    """
    if isinstance(tool, str):
        return tool
    if isinstance(tool, dict):
        return tool.get("name") or (tool.get("function") or {}).get("name")
    return getattr(tool, "name", None)


# Module-level singleton for cheap reuse (stateless detector).
_default_detector: Optional[IntentDetector] = None


def get_intent_detector() -> IntentDetector:
    """Return a process-wide default IntentDetector (stateless, safe to share)."""
    global _default_detector
    if _default_detector is None:
        _default_detector = IntentDetector()
    return _default_detector
