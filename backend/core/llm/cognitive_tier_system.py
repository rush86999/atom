"""
Cognitive Tier System for LLM Query Complexity Classification

Extends the 4-level QueryComplexity enum with a more granular 5-tier system
that considers token count, semantic patterns, and task type for intelligent
LLM routing decisions.
"""

from enum import Enum
import re
from typing import Dict, List, Optional


class CognitiveTier(Enum):
    """
    5-tier cognitive classification system for LLM queries.
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
    """

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
        self._compiled_patterns = {
            name: (re.compile(pattern, re.IGNORECASE), weight)
            for name, (pattern, weight) in self.COMPLEXITY_PATTERNS.items()
        }

    def classify(self, prompt: str, task_type: Optional[str] = None) -> CognitiveTier:
        """Classify a query into a cognitive tier."""
        complexity_score = self._calculate_complexity_score(prompt, task_type)
        estimated_tokens = len(prompt) // 4
        for tier in CognitiveTier:
            threshold = TIER_THRESHOLDS[tier]
            if (estimated_tokens <= threshold["max_tokens"] and
                complexity_score <= threshold["complexity_score"]):
                return tier
        return CognitiveTier.COMPLEX

    def _calculate_complexity_score(self, prompt: str, task_type: Optional[str] = None) -> int:
        """Calculate semantic complexity score for a prompt."""
        complexity_score = 0
        estimated_tokens = len(prompt) // 4
        if estimated_tokens >= 5000:
            complexity_score += 8
        elif estimated_tokens >= 2000:
            complexity_score += 5
        elif estimated_tokens >= 500:
            complexity_score += 3
        elif estimated_tokens >= 100:
            complexity_score += 1

        for pattern, weight in self._compiled_patterns.values():
            if pattern.search(prompt):
                complexity_score += weight
        if "```" in prompt:
            complexity_score += 3
        if task_type:
            adjustment = self.TASK_TYPE_ADJUSTMENTS.get(task_type, 0)
            complexity_score += adjustment
        return max(complexity_score, -2)
