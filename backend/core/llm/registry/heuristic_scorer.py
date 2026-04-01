"""Heuristic quality scoring for LLM models.

Provides quality score estimates for models that lack LMSYS benchmark data.
Scores are derived from model name patterns, version numbers, and context window.
"""
import logging
import re
from typing import Dict, Optional
from datetime import datetime

from core.config import settings

logger = logging.getLogger(__name__)


# Quality tier definitions based on model name patterns
QUALITY_TIERS = {
    # Tier 1: Flagship models (95+)
    'tier_1': {
        'keywords': ['opus', 'ultra', 'flagship'],
        'base_score': 95.0,
        'description': 'Top-tier flagship models'
    },
    # Tier 2: Pro models (90-94)
    'tier_2': {
        'keywords': ['sonnet', 'pro', 'plus'],
        'base_score': 90.0,
        'description': 'Professional-grade models'
    },
    # Tier 3: Balanced models (85-89)
    'tier_3': {
        'keywords': ['haiku', 'flash', 'turbo', 'lite'],
        'base_score': 85.0,
        'description': 'Balanced performance models'
    },
    # Tier 4: Base models (80-84)
    'tier_4': {
        'keywords': ['base', 'small', 'mini'],
        'base_score': 80.0,
        'description': 'Base or smaller models'
    },
    # Tier 5: Experimental (70-79)
    'tier_5': {
        'keywords': ['experimental', 'preview', 'alpha', 'beta', 'rc'],
        'base_score': 70.0,
        'description': 'Experimental or preview models'
    },
}

# Provider-specific model series (for version extraction)
MODEL_SERIES_PATTERNS = {
    'gpt': r'gpt[-_]?(\d+(?:\.\d+)?)',
    'claude': r'claude[-_]?(\d+(?:\.\d+)?)',
    'gemini': r'gemini[-_]?(\d+(?:\.\d+)?)',
    'llama': r'llama[-_]?(\d+(?:\.\d+)?)',
    'mistral': r'mistral[-_]?(\d+(?:\.\d+)?)',
    'qwen': r'qwen[-_]?(\d+(?:\.\d+)?)',
    'deepseek': r'deepseek[-_]?v?(\d+(?:\.\d+)?)',
}

# Context window bonus thresholds
CONTEXT_THRESHOLDS = [
    (128000, 3.0),   # +3 for 128k+ tokens
    (200000, 5.0),   # +5 for 200k+ tokens
    (1000000, 7.0),  # +7 for 1M+ tokens
]

# Default configuration
DEFAULT_MIN_SCORE = 75.0
DEFAULT_MAX_SCORE = 98.0


class HeuristicScorer:
    """Calculates heuristic quality scores for LLM models.

    Uses model name patterns, version numbers, and context window to estimate
    quality when benchmark data is unavailable.

    Usage:
        scorer = HeuristicScorer()
        score = scorer.calculate_score('gpt-4-turbo', context_window=128000)
        # Returns: 92.0 (Tier 2 + version bonus + context bonus)
    """

    def __init__(
        self,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        context_bonus_enabled: bool = True,
        version_bonus_enabled: bool = True
    ):
        """Initialize scorer with optional overrides.

        Args:
            min_score: Minimum possible score (default from settings or 75.0)
            max_score: Maximum possible score (default from settings or 98.0)
            context_bonus_enabled: Enable context window bonus
            version_bonus_enabled: Enable version number bonus
        """
        self.min_score = min_score or getattr(settings, 'HEURISTIC_MIN_SCORE', DEFAULT_MIN_SCORE)
        self.max_score = max_score or getattr(settings, 'HEURISTIC_MAX_SCORE', DEFAULT_MAX_SCORE)
        self.context_bonus_enabled = context_bonus_enabled
        self.version_bonus_enabled = version_bonus_enabled

    def calculate_score(
        self,
        model_name: str,
        context_window: Optional[int] = None,
        provider: Optional[str] = None
    ) -> float:
        """Calculate heuristic quality score for a model.

        Args:
            model_name: Model name (e.g., 'gpt-4-turbo', 'claude-3-opus')
            context_window: Optional context window for bonus calculation
            provider: Optional provider name for provider-specific logic

        Returns:
            Quality score from 0-100 (clamped to min_score-max_score range)
        """
        score = self._get_base_tier_score(model_name)

        # Apply version number bonus
        if self.version_bonus_enabled:
            score += self._calculate_version_bonus(model_name)

        # Apply context window bonus
        if self.context_bonus_enabled and context_window:
            score += self._calculate_context_bonus(context_window)

        # Clamp to configured range
        return max(self.min_score, min(self.max_score, score))

    def _get_base_tier_score(self, model_name: str) -> float:
        """Get base score from model name tier."""
        name_lower = model_name.lower()

        # Check each tier (highest quality first: tier_1 → tier_2 → ... → tier_5)
        for tier_name, tier_config in QUALITY_TIERS.items():
            for keyword in tier_config['keywords']:
                if keyword in name_lower:
                    return tier_config['base_score']

        # Default to mid-range if no tier matches
        return 82.0

    def _calculate_version_bonus(self, model_name: str) -> float:
        """Calculate bonus based on version number.

        Newer versions get higher scores:
        - Version 4+: +5
        - Version 3.5+: +4
        - Version 3: +3
        - Version 2: +1
        - Version 1: 0
        """
        name_lower = model_name.lower()

        # Try to extract version number
        for series, pattern in MODEL_SERIES_PATTERNS.items():
            if series in name_lower:
                match = re.search(pattern, name_lower)
                if match:
                    try:
                        version_str = match.group(1)
                        version = float(version_str)

                        # Version bonus calculation
                        if version >= 4.0:
                            return 5.0
                        elif version >= 3.5:
                            return 4.0
                        elif version >= 3.0:
                            return 3.0
                        elif version >= 2.0:
                            return 1.0
                    except (ValueError, IndexError):
                        pass

        return 0.0

    def _calculate_context_bonus(self, context_window: int) -> float:
        """Calculate bonus based on context window size.

        Larger context windows get modest bonuses up to a cap.
        """
        if not context_window:
            return 0.0

        bonus = 0.0
        for threshold, amount in CONTEXT_THRESHOLDS:
            if context_window >= threshold:
                bonus = amount

        return bonus

    def get_tier_info(self, model_name: str) -> Dict[str, any]:
        """Get tier information for a model.

        Args:
            model_name: Model name to analyze

        Returns:
            Dict with tier info:
            {
                'tier': str,
                'base_score': float,
                'keywords': List[str],
                'description': str
            }
        """
        name_lower = model_name.lower()

        # Check each tier (highest quality first: tier_1 → tier_2 → ... → tier_5)
        for tier_name, tier_config in QUALITY_TIERS.items():
            for keyword in tier_config['keywords']:
                if keyword in name_lower:
                    return {
                        'tier': tier_name,
                        'base_score': tier_config['base_score'],
                        'keywords': tier_config['keywords'],
                        'description': tier_config['description']
                    }

        return {
            'tier': 'unknown',
            'base_score': 82.0,
            'keywords': [],
            'description': 'Unknown model tier'
        }


# Convenience function
def calculate_quality_score(
    model_name: str,
    context_window: Optional[int] = None,
    provider: Optional[str] = None
) -> float:
    """Calculate heuristic quality score for a model.

    Convenience function that creates a scorer instance.

    Args:
        model_name: Model name
        context_window: Optional context window
        provider: Optional provider name

    Returns:
        Quality score from 0-100
    """
    scorer = HeuristicScorer()
    return scorer.calculate_score(model_name, context_window, provider)
