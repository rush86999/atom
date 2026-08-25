from __future__ import annotations
"""
Cognitive Tier System for LLM Query Complexity Classification

Extends the 4-level QueryComplexity enum with a more granular 5-tier system
that considers token count, semantic patterns, and task type for intelligent
LLM routing decisions.
"""

import re
from enum import Enum


class CognitiveTier(Enum):
    """
    5-tier cognitive classification system for LLM queries.

    Tiers are ordered by increasing intelligence and cost:
    - MICRO: Ultra-fast, low-cost (gpt-4o-mini, haiku)
    - STANDARD: Balanced performance (gemini-flash, deepseek)
    - VERSATILE: General purpose reasoning (gpt-4o, sonnet)
    - HEAVY: Complex reasoning and large context (opus, pro)
    - COMPLEX: State-of-the-art research models (gpt-5, o3)
    """

    MICRO = "micro"
    STANDARD = "standard"
    VERSATILE = "versatile"
    HEAVY = "heavy"
    COMPLEX = "complex"


# Tier thresholds for classification (score and token counts)
TIER_THRESHOLDS = {
    CognitiveTier.MICRO: {
        "max_tokens": 100,
        "complexity_score": 0,
        "description": "Simple greetings or quick lookups — low-token, low-complexity tasks",
    },
    CognitiveTier.STANDARD: {
        "max_tokens": 500,
        "complexity_score": 2,
        "description": "Moderate complexity queries and short-task explanations",
    },
    CognitiveTier.VERSATILE: {
        "max_tokens": 2000,
        "complexity_score": 5,
        "description": "Multi-step reasoning or technical tasks of moderate token length",
    },
    CognitiveTier.HEAVY: {
        "max_tokens": 5000,
        "complexity_score": 8,
        "description": "Complex analysis and large-context tasks with high token counts",
    },
    CognitiveTier.COMPLEX: {
        "max_tokens": float("inf"),
        "complexity_score": float("inf"),
        "description": "Advanced problem solving and high-stakes reasoning on the most complex tasks",
    },
}


class CognitiveClassifier:
    """
    Analyzes prompt semantic patterns and metadata to classify query complexity.

    Uses weighted regex patterns, token estimation, and task-type adjustments
    to determine the optimal CognitiveTier for any given query.
    """

    # Complexity patterns extracted from byok_handler.py
    # These are shared patterns for semantic analysis
    COMPLEXITY_PATTERNS = {
        "simple": (
            r"\b(hello|hi|thanks|greetings|summarize|translate|list|what is|who is|"
            r"define|how do i|simplify|brief|basic|short|quick|simple)\b",
            -2,
        ),
        "moderate": (
            r"\b(analyze|compare|evaluate|synthesize|explain|describe|detailed|"
            r"background|concept|history|nuance|opinion|critique|pros and cons|"
            r"advantages|disadvantages)\b",
            1,
        ),
        "technical": (
            r"\b(calculate|equation|formula|solve|integral|derivative|calculus|"
            r"geometry|algebra|math|maths|theorem|statistics|probability|regression|"
            r"vector|matrix|tensor|log|exp|pow|sqrt|abs|sin|cos|tan|pi|infinity|"
            r"prime|physics|chemistry|biology|science)\b",
            3,
        ),
        "code": (
            r"\b(code|coding|function|class|method|script|scripting|debug|debugging|"
            r"optimize|optimization|refactor|refactoring|snippet|implementation|"
            r"interface|api|endpoint|webhook|database|sql|postgresql|mongodb|redis|"
            r"schema|migration|json|xml|yaml|config|docker|kubernetes|aws|lambda|"
            r"gcp|azure|def|var|let|const|import|return|print|async|await|try|except|"
            r"catch|throw|public|private|static|final|struct|typedef|typedefs)\b",
            3,
        ),
        "advanced": (
            r"\b(architecture|architecting|security audit|vulnerability|"
            r"cryptography|encryption|decryption|authentication|authorization|auth|"
            r"oauth|jwt|performance|bottleneck|concurrency|multithread|parallel|"
            r"distributed|scale|scaling|load balance|cluster|proprietary|"
            r"reverse engineer|obfuscate|obfuscation|enterprise|global|large-scale)\b",
            5,
        ),
    }

    # Task type bias adjustments
    TASK_TYPE_ADJUSTMENTS = {
        "code": 2,
        "analysis": 2,
        "reasoning": 2,
        "agentic": 2,
        "chat": -1,
        "general": 0,
    }

    def __init__(self):
        """Initialize the classifier and pre-compile regex patterns."""
        self._compiled_patterns = {
            name: (re.compile(pattern, re.IGNORECASE), weight)
            for name, (pattern, weight) in self.COMPLEXITY_PATTERNS.items()
        }

    def classify(self, prompt: str, task_type: str | None = None) -> CognitiveTier:
        """
        Classify a query into a cognitive tier.

        Args:
            prompt: The query text to classify
            task_type: Optional task type hint (code, chat, analysis, etc.)

        Returns:
            CognitiveTier classification for the query
        """
        complexity_score = self._calculate_complexity_score(prompt, task_type)
        estimated_tokens = self._estimate_tokens(prompt)

        # BUG-116 (complete): the score cap in _calculate_complexity_score was
        # insufficient — a long-but-simple prompt (e.g. "hello " x 3000 tokens)
        # still routed to HEAVY through the max_tokens bound alone. Strong
        # simple signals also cap the token bound at VERSATILE's ceiling so a
        # simple prompt never reaches an expensive tier.
        if self._strong_simple_signals(prompt):
            estimated_tokens = min(
                estimated_tokens,
                TIER_THRESHOLDS[CognitiveTier.VERSATILE]["max_tokens"],  # type: ignore[call-overload]
            )

        # Map score and tokens to tier
        for tier in CognitiveTier:
            threshold = TIER_THRESHOLDS[tier]
            if (
                estimated_tokens <= threshold["max_tokens"]
                and complexity_score <= threshold["complexity_score"]
            ):
                return tier

        # Fallback to highest tier
        return CognitiveTier.COMPLEX

    def _strong_simple_signals(self, prompt: str) -> bool:
        """True when the prompt carries strong "simple" keyword signals."""
        simple_signals = 0
        for pattern, weight in self._compiled_patterns.values():
            if pattern.search(prompt) and weight < 0:  # "simple" has negative weight
                simple_signals += abs(weight)
        return simple_signals >= 2

    def _calculate_complexity_score(self, prompt: str, task_type: str | None = None) -> int:
        """
        Calculate semantic complexity score for a prompt.

        Args:
            prompt: The query text
            task_type: Optional task type hint

        Returns:
            Complexity score (lower = simpler, higher = more complex)
        """
        complexity_score = 0

        # 1. Token-based scoring — BUG-116: Previously added token weight
        # unconditionally, so a trivially simple but long prompt (e.g. repeated
        # "hello") scored HEAVY. Now the token contribution is capped when
        # strong "simple" signals are detected (checked first).
        estimated_tokens = self._estimate_tokens(prompt)

        # Check for simple-pattern signals BEFORE applying token weight
        # so they can gate the token contribution.
        simple_signals = 0
        if self._strong_simple_signals(prompt):
            simple_signals = 2

        # Apply token weight, but if the prompt has strong simplicity signals,
        # cap the token contribution so a long-but-simple prompt doesn't
        # get routed to an expensive model.
        token_score = 0
        if estimated_tokens >= 5000:
            token_score = 8
        elif estimated_tokens >= 2000:
            token_score = 5
        elif estimated_tokens >= 500:
            token_score = 3
        elif estimated_tokens >= 100:
            token_score = 1

        # If simple signals are present, token weight can add at most +1
        # (prevents simple-but-long prompts from being routed to HEAVY).
        if simple_signals >= 2:
            token_score = min(token_score, 1)
        complexity_score += token_score

        # 2. Semantic pattern matching
        for pattern, weight in self._compiled_patterns.values():
            if pattern.search(prompt):
                complexity_score += weight

        # 3. Code block detection (significant weight)
        if "```" in prompt:
            complexity_score += 3

        # 4. Task type adjustment
        if task_type:
            adjustment = self.TASK_TYPE_ADJUSTMENTS.get(task_type, 0)
            complexity_score += adjustment

        # Ensure minimum score
        return max(complexity_score, -2)

    def _estimate_tokens(self, prompt: str) -> int:
        """
        Estimate token count for a prompt.
        Uses heuristic: 1 token ≈ 4 characters.
        """
        return len(prompt) // 4

    def get_tier_models(self, tier: CognitiveTier, workspace_id: str | None = None) -> list[str]:
        """
        Get recommended models for a cognitive tier.

        If ``workspace_id`` is provided and the workspace has a
        ``CognitiveTierPreference`` with a ``tier_models`` override in its
        ``metadata_json``, those user-configured models are returned instead
        of the hardcoded defaults. This lets users map their local models
        to tiers (e.g. "use llama3:8b for MICRO, qwen2.5:32b for HEAVY").
        """
        # Check for user-configured overrides.
        if workspace_id:
            try:
                from core.database import get_db_session
                from core.models import CognitiveTierPreference
                with get_db_session() as db:
                    pref = db.query(CognitiveTierPreference).filter(
                        CognitiveTierPreference.workspace_id == workspace_id
                    ).first()
                    if pref and pref.metadata_json:
                        tier_models = pref.metadata_json.get("tier_models")
                        if tier_models and isinstance(tier_models, dict):
                            tier_key = tier.value if hasattr(tier, 'value') else str(tier)
                            user_models = tier_models.get(tier_key, [])
                            if user_models:
                                return user_models
            except Exception:
                pass  # Fall through to defaults.

        # Hardcoded tier defaults. DeepSeek v4 entries are Zen-gateway IDs
        # (served via opencode-go) so an opencode-go-only deployment still
        # resolves every tier; legacy direct-API names are kept for
        # deployments holding a DEEPSEEK_API_KEY.
        TIER_MODELS = {
            CognitiveTier.MICRO: [
                "deepseek-v4-flash",
                "minimax-m3",
                "deepseek-chat",
                "qwen-3-7b",
                "gemini-3-flash",
                "gemini-3.5-flash",
                "gpt-4o-mini",
                "ollama/llama3:8b",
            ],
            CognitiveTier.STANDARD: [
                "deepseek-v4-flash",
                "gemini-3-flash",
                "gemini-3.5-flash",
                "minimax-m3",
                "deepseek-chat",
                "gpt-4o-mini",
                "claude-3-haiku-20240307",
                "ollama/llama3:8b",
            ],
            CognitiveTier.VERSATILE: [
                "deepseek-v4-flash",
                "gemini-3-flash",
                "gemini-3.5-flash",
                "gpt-4o-mini",
                "deepseek-v3",
                "claude-3-5-sonnet",
                "ollama/llama3:8b",
            ],
            CognitiveTier.HEAVY: [
                "deepseek-v4-pro",
                "gpt-4o",
                "claude-3-5-sonnet",
                "gemini-3-pro",
                "deepseek-v3.2",
                "ollama/mixtral:8x7b",
            ],
            CognitiveTier.COMPLEX: [
                "kimi-k2.7-code",
                "glm-5.2",
                "gpt-5",
                "gpt-5.6-sol",
                "o3",
                "claude-4-opus",
                "claude-mythos-5",
                "kimi-k3",
                "deepseek-v3.2-speciale",
                "gemini-3-pro",
                "ollama/mixtral:8x7b",
            ],
        }

        return TIER_MODELS.get(tier, [])

    def get_tier_description(self, tier: CognitiveTier) -> str:
        """
        Get human-readable description of a cognitive tier.
        """
        return TIER_THRESHOLDS[tier]["description"]
