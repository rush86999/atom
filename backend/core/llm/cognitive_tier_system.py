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
        "description": "Simple greetings or quick lookups",
    },
    CognitiveTier.STANDARD: {
        "max_tokens": 500,
        "complexity_score": 2,
        "description": "Moderate complexity queries",
    },
    CognitiveTier.VERSATILE: {
        "max_tokens": 2000,
        "complexity_score": 5,
        "description": "Multi-step reasoning or technical tasks",
    },
    CognitiveTier.HEAVY: {
        "max_tokens": 5000,
        "complexity_score": 8,
        "description": "Complex analysis and large context",
    },
    CognitiveTier.COMPLEX: {
        "max_tokens": float("inf"),
        "complexity_score": float("inf"),
        "description": "Advanced problem solving and high-stakes reasoning",
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
        "reasoning": 3,
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

        # 1. Token-based scoring (adjusted for better tier mapping)
        estimated_tokens = self._estimate_tokens(prompt)
        if estimated_tokens >= 5000:
            complexity_score += 8
        elif estimated_tokens >= 2000:
            complexity_score += 5
        elif estimated_tokens >= 500:
            complexity_score += 3
        elif estimated_tokens >= 100:
            complexity_score += 1

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

    def get_tier_models(self, tier: CognitiveTier) -> list[str]:
        """
        Get recommended models for a cognitive tier.
        """
        TIER_MODELS = {
            CognitiveTier.MICRO: [
                "deepseek-chat",
                "qwen-3-7b",
                "gemini-3-flash",
                "gpt-4o-mini",
            ],
            CognitiveTier.STANDARD: [
                "gemini-3-flash",
                "deepseek-chat",
                "gpt-4o-mini",
                "claude-3-haiku-20240307",
            ],
            CognitiveTier.VERSATILE: [
                "gemini-3-flash",
                "gpt-4o-mini",
                "deepseek-v3",
                "claude-3-5-sonnet",
            ],
            CognitiveTier.HEAVY: [
                "gpt-4o",
                "claude-3-5-sonnet",
                "gemini-3-pro",
                "deepseek-v3.2",
            ],
            CognitiveTier.COMPLEX: [
                "gpt-5",
                "o3",
                "claude-4-opus",
                "deepseek-v3.2-speciale",
                "gemini-3-pro",
            ],
        }

        return TIER_MODELS.get(tier, [])

    def get_tier_description(self, tier: CognitiveTier) -> str:
        """
        Get human-readable description of a cognitive tier.
        """
        return TIER_THRESHOLDS[tier]["description"]
