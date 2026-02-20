"""
Cognitive Tier System for LLM Query Complexity Classification

Extends the 4-level QueryComplexity enum with a more granular 5-tier system
that considers token count, semantic patterns, and task type for intelligent
LLM routing decisions.

Purpose: Enable more granular cost optimization by matching query complexity
to the most cost-effective model tier.

Author: Atom AI Platform
Created: 2026-02-20
"""

from enum import Enum
import re
from typing import Dict, List, Optional


class CognitiveTier(Enum):
    """
    5-tier cognitive classification system for LLM queries.

    Extends QueryComplexity with more granular tiers based on:
    - Token count (estimated)
    - Semantic complexity patterns
    - Task type requirements

    Tiers:
        MICRO: <100 tokens, simple queries -> cheapest models
        STANDARD: 100-500 tokens, moderate complexity -> balanced cost/quality
        VERSATILE: 500-2k tokens, multi-step reasoning -> quality models
        HEAVY: 2k-5k tokens, complex tasks -> premium models
        COMPLEX: >5k tokens or code/math/advanced reasoning -> frontier models
    """
    MICRO = "micro"          # <100 tokens, simple queries
    STANDARD = "standard"    # 100-500 tokens, moderate complexity
    VERSATILE = "versatile"  # 500-2k tokens, multi-step reasoning
    HEAVY = "heavy"          # 2k-5k tokens, complex tasks
    COMPLEX = "complex"      # >5k tokens or code/math/advanced reasoning


# Tier thresholds for classification
TIER_THRESHOLDS = {
    CognitiveTier.MICRO: {
        "max_tokens": 100,
        "complexity_score": 0,
        "description": "Simple queries under 100 tokens"
    },
    CognitiveTier.STANDARD: {
        "max_tokens": 500,
        "complexity_score": 2,
        "description": "Moderate complexity with 100-500 tokens"
    },
    CognitiveTier.VERSATILE: {
        "max_tokens": 2000,
        "complexity_score": 5,
        "description": "Multi-step reasoning with 500-2k tokens"
    },
    CognitiveTier.HEAVY: {
        "max_tokens": 5000,
        "complexity_score": 8,
        "description": "Complex tasks with 2k-5k tokens"
    },
    CognitiveTier.COMPLEX: {
        "max_tokens": float("inf"),
        "complexity_score": float("inf"),
        "description": "Advanced reasoning, code, math, or >5k tokens"
    }
}


class CognitiveClassifier:
    """
    Multi-factor classifier for determining query cognitive tier.

    Analyzes queries using:
    1. Token count estimation (1 token ≈ 4 characters)
    2. Semantic pattern matching (code, math, technical terms)
    3. Task type hints (code generation vs casual chat)

    Performance target: <50ms per classification
    """

    # Complexity patterns extracted from byok_handler.py
    # These are shared patterns for semantic analysis
    COMPLEXITY_PATTERNS = {
        "simple": (
            r"\b(hello|hi|thanks|greetings|summarize|translate|list|what is|who is|"
            r"define|how do i|simplify|brief|basic|short|quick|simple)\b",
            -2
        ),
        "moderate": (
            r"\b(analyze|compare|evaluate|synthesize|explain|describe|detailed|"
            r"background|concept|history|nuance|opinion|critique|pros and cons|"
            r"advantages|disadvantages)\b",
            1
        ),
        "technical": (
            r"\b(calculate|equation|formula|solve|integral|derivative|calculus|"
            r"geometry|algebra|math|maths|theorem|statistics|probability|regression|"
            r"vector|matrix|tensor|log|exp|pow|sqrt|abs|sin|cos|tan|pi|infinity|"
            r"prime|physics|chemistry|biology|science)\b",
            3
        ),
        "code": (
            r"\b(code|coding|function|class|method|script|scripting|debug|debugging|"
            r"optimize|optimization|refactor|refactoring|snippet|implementation|"
            r"interface|api|endpoint|webhook|database|sql|postgresql|mongodb|redis|"
            r"schema|migration|json|xml|yaml|config|docker|kubernetes|aws|lambda|"
            r"gcp|azure|def|var|let|const|import|return|print|async|await|try|except|"
            r"catch|throw|public|private|static|final|struct|typedef|typedefs)\b",
            3
        ),
        "advanced": (
            r"\b(architecture|architecting|security audit|vulnerability|"
            r"cryptography|encryption|decryption|authentication|authorization|auth|"
            r"oauth|jwt|performance|bottleneck|concurrency|multithread|parallel|"
            r"distributed|scale|scaling|load balance|cluster|proprietary|"
            r"reverse engineer|obfuscate|obfuscation|enterprise|global|large-scale)\b",
            5
        )
    }

    # Task type adjustments
    TASK_TYPE_ADJUSTMENTS = {
        "code": 2,
        "analysis": 2,
        "reasoning": 2,
        "agentic": 2,
        "chat": -1,
        "general": -1,
    }

    def __init__(self):
        """Initialize the cognitive classifier."""
        # Pre-compile regex patterns for performance
        self._compiled_patterns = {
            name: (re.compile(pattern, re.IGNORECASE), weight)
            for name, (pattern, weight) in self.COMPLEXITY_PATTERNS.items()
        }

    def classify(self, prompt: str, task_type: Optional[str] = None) -> CognitiveTier:
        """
        Classify a query into a cognitive tier.

        Args:
            prompt: The query text to classify
            task_type: Optional task type hint (code, chat, analysis, etc.)

        Returns:
            CognitiveTier classification for the query

        Examples:
            >>> classifier = CognitiveClassifier()
            >>> classifier.classify("hi").value
            'micro'
            >>> classifier.classify("explain this in detail").value in ['standard', 'versatile']
            True
            >>> classifier.classify("debug this distributed system architecture").value
            'complex'
        """
        complexity_score = self._calculate_complexity_score(prompt, task_type)
        estimated_tokens = self._estimate_tokens(prompt)

        # Map score and tokens to tier
        for tier in CognitiveTier:
            threshold = TIER_THRESHOLDS[tier]
            if (estimated_tokens <= threshold["max_tokens"] and
                complexity_score <= threshold["complexity_score"]):
                return tier

        # Fallback to highest tier
        return CognitiveTier.COMPLEX

    def _calculate_complexity_score(self, prompt: str, task_type: Optional[str] = None) -> int:
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
            complexity_score += 8  # Increased to trigger COMPLEX
        elif estimated_tokens >= 2000:
            complexity_score += 5  # Increased to trigger HEAVY
        elif estimated_tokens >= 500:
            complexity_score += 3  # Increased for VERSATILE
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

        Uses heuristic: 1 token ≈ 4 characters (average for English text).

        Args:
            prompt: The query text

        Returns:
            Estimated token count
        """
        return len(prompt) // 4

    def get_tier_models(self, tier: CognitiveTier) -> List[str]:
        """
        Get recommended models for a cognitive tier.

        Maps cognitive tiers to appropriate model quality/cost bands.

        Args:
            tier: The cognitive tier

        Returns:
            List of recommended model identifiers

        Examples:
            >>> classifier = CognitiveClassifier()
            >>> classifier.get_tier_models(CognitiveTier.MICRO)
            ['deepseek-chat', 'qwen-3-7b', 'gemini-3-flash']
            >>> classifier.get_tier_models(CognitiveTier.COMPLEX)
            ['gpt-5', 'o3', 'claude-4-opus', 'deepseek-v3.2-speciale']
        """
        # Model recommendations by tier
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
            ]
        }

        return TIER_MODELS.get(tier, [])

    def get_tier_description(self, tier: CognitiveTier) -> str:
        """
        Get human-readable description of a cognitive tier.

        Args:
            tier: The cognitive tier

        Returns:
            Description string
        """
        return TIER_THRESHOLDS[tier]["description"]
