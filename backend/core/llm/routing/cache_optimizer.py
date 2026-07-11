"""
Cache Optimization with Learning

Based on 2025-2026 research:
- "RouteLLM: Learning to Route" (arXiv:2406.18665)
- "State of AI 2025: 100T Token Study" (openrouter.ai)

Implements:
- Predictive cache warming based on access patterns
- Cache hit prediction and optimization
- Dynamic cache size adjustment
"""

import hashlib
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class CacheStrategy(Enum):
    """Cache warming strategies"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    PREDICTIVE = "predictive"  # ML-based prediction
    ADAPTIVE = "adaptive"  # Adaptive hybrid


class AccessPattern(Enum):
    """Types of access patterns"""
    SEQUENTIAL = "sequential"  # Sequential accesses
    TEMPORAL = "temporal"  # Time-based patterns
    HIERARCHICAL = "hierarchical"  # Nested patterns
    RANDOM = "random"  # No discernible pattern


@dataclass
class CacheOptimizationConfig:
    """Configuration for cache optimization"""
    # Prediction
    enable_prediction: bool = True
    prediction_window_minutes: int = 60
    min_prediction_confidence: float = 0.7

    # Cache warming
    auto_warm_cache: bool = True
    warm_cache_prompts_per_batch: int = 10
    warm_cache_interval_ms: int = 1000

    # Cache sizing
    enable_dynamic_sizing: bool = True
    min_cache_size_mb: int = 100
    max_cache_size_mb: int = 1000
    target_hit_rate: float = 0.95

    # Pattern detection
    pattern_detection_window: int = 100  # Number of accesses to analyze
    min_pattern_frequency: int = 3

    # Performance tracking
    track_performance: bool = True
    performance_log_interval: int = 100


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class CacheAccess:
    """Record of a cache access event"""
    timestamp: datetime = field(default_factory=datetime.now)
    prompt_hash: str = ""
    was_hit: bool = False
    latency_ms: int = 0
    model: str = ""
    provider: str = ""

    def __hash__(self):
        return hash((self.prompt_hash, self.timestamp))


@dataclass
class CacheStatistics:
    """Statistics for cache performance"""
    total_accesses: int = 0
    total_hits: int = 0
    total_misses: int = 0
    hit_rate: float = 0.0
    avg_latency_ms: float = 0.0

    def update(self, was_hit: bool, latency_ms: int = 0) -> None:
        """Update statistics with new access"""
        self.total_accesses += 1
        if was_hit:
            self.total_hits += 1
        else:
            self.total_misses += 1

        if self.total_accesses > 0:
            self.hit_rate = self.total_hits / self.total_accesses

        # Update average latency
        if self.total_accesses > 0:
            self.avg_latency_ms = (
                (self.avg_latency_ms * (self.total_accesses - 1) + latency_ms) /
                self.total_accesses
            )


@dataclass
class WarmedCacheEntry:
    """Entry for warmed cache data"""
    prompt_hash: str = ""
    prompt_prefix: str = ""
    estimated_tokens: int = 0
    access_probability: float = 0.5
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    model: str = ""
    provider: str = ""


# ============================================================================
# Access Pattern Analyzer
# ============================================================================

class AccessPatternAnalyzer:
    """Analyzes cache access patterns to optimize caching strategy"""

    def __init__(self, config: Optional[CacheOptimizationConfig] = None):
        self.config = config or CacheOptimizationConfig()
        self.access_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.pattern_cache: Dict[str, AccessPattern] = {}

    def record_access(self, prompt_hash: str, timestamp: datetime) -> None:
        """Record cache access for pattern analysis"""
        self.access_history[prompt_hash].append(timestamp)

    def detect_pattern(self, prompt_hash: str) -> AccessPattern:
        """
        Detect access pattern for a prompt hash.

        Args:
            prompt_hash: Hash of prompt prefix

        Returns:
            Detected access pattern
        """
        if prompt_hash in self.pattern_cache:
            return self.pattern_cache[prompt_hash]

        history = list(self.access_history[prompt_hash])
        if len(history) < 3:
            self.pattern_cache[prompt_hash] = AccessPattern.RANDOM
            return AccessPattern.RANDOM

        # Analyze gaps between accesses
        gaps = []
        for i in range(1, len(history)):
            gap = (history[i] - history[i-1]).total_seconds()
            gaps.append(gap)

        # Detect pattern
        if len(gaps) < 3:
            self.pattern_cache[prompt_hash] = AccessPattern.RANDOM
            return AccessPattern.RANDOM

        gap_variance = sum((g - np.mean(gaps))**2 for g in gaps) / len(gaps)

        if gap_variance < 60:  # Regular pattern (<1min variance)
            pattern = AccessPattern.TEMPORAL
        elif self._is_sequential(history):
            pattern = AccessPattern.SEQUENTIAL
        else:
            pattern = AccessPattern.RANDOM

        self.pattern_cache[prompt_hash] = pattern
        return pattern

    def _is_sequential(self, timestamps: List[datetime]) -> bool:
        """Check if timestamps are sequential"""
        for i in range(1, len(timestamps)):
            if (timestamps[i] - timestamps[i-1]).total_seconds() > 300:  # 5 min
                return False
        return True

    def get_access_frequency(self, prompt_hash: str, window_minutes: int = 60) -> float:
        """Get access frequency for prompt hash"""
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        history = self.access_history.get(prompt_hash, deque())

        count = sum(1 for ts in history if ts >= cutoff)
        return count / max(window_minutes, 1)

    def get_next_access_probability(self, prompt_hash: str) -> float:
        """
        Predict probability of next access within prediction window.

        Uses access frequency and pattern analysis.
        """
        frequency = self.get_access_frequency(prompt_hash, self.config.prediction_window_minutes)
        pattern = self.detect_pattern(prompt_hash)

        # Pattern-based adjustment
        pattern_boost = {
            AccessPattern.TEMPORAL: 1.5,
            AccessPattern.SEQUENTIAL: 2.0,
            AccessPattern.HIERARCHICAL: 1.2,
            AccessPattern.RANDOM: 1.0,
        }

        adjusted_freq = min(frequency * pattern_boost.get(pattern, 1.0), 1.0)
        return adjusted_freq


# ============================================================================
# Cache Warmer
# ============================================================================

class CacheWarmer:
    """
    Predictive cache warming system.

    Identifies prompts likely to be accessed and pre-warms cache.
    """

    def __init__(self, config: Optional[CacheOptimizationConfig] = None):
        self.config = config or CacheOptimizationConfig()
        self.analyzer = AccessPatternAnalyzer(config)
        self.warmed_entries: Dict[str, WarmedCacheEntry] = {}

    def should_warm(self, prompt_hash: str, access_probability: float) -> bool:
        """
        Determine if cache entry should be warmed.

        Args:
            prompt_hash: Hash of prompt prefix
            access_probability: Predicted access probability

        Returns:
            True if should warm cache entry
        """
        # High probability entries should be warmed
        if access_probability >= 0.7:
            return True

        # Check if this is a frequent pattern
        frequency = self.analyzer.get_access_frequency(prompt_hash, 60)
        if frequency >= self.config.min_pattern_frequency / 60:
            return True

        return False

    def get_warm_candidates(
        self,
        workspace_id: str,
        limit: int = 50
    ) -> List[WarmedCacheEntry]:
        """
        Get top candidates for cache warming.

        Args:
            workspace_id: Workspace identifier
            limit: Maximum candidates to return

        Returns:
            List of candidates sorted by access probability
        """
        candidates = []

        for prompt_hash, entry in self.warmed_entries.items():
            probability = self.analyzer.get_next_access_probability(prompt_hash)
            if probability >= self.config.min_prediction_confidence:
                entry.access_probability = probability
                candidates.append(entry)

        # Sort by access probability
        candidates.sort(key=lambda x: x.access_probability, reverse=True)
        return candidates[:limit]


# ============================================================================
# Cache Optimizer
# ============================================================================

class CacheOptimizer:
    """
    Optimizes cache performance using learned patterns.

    Features:
    - Predictive cache warming
    - Dynamic cache sizing
    - Hit rate optimization
    """

    def __init__(self, config: Optional[CacheOptimizationConfig] = None):
        self.config = config or CacheOptimizationConfig()
        self.analyzer = AccessPatternAnalyzer(config)
        self.warmer = CacheWarmer(config)
        self.statistics = CacheStatistics()

        # Access tracking
        self.accesses: List[CacheAccess] = []
        self.access_index: Dict[str, List[int]] = defaultdict(list)

    def record_access(
        self,
        prompt_hash: str,
        was_hit: bool,
        latency_ms: int = 0,
        model: str = "",
        provider: str = ""
    ) -> None:
        """Record cache access for learning"""
        access = CacheAccess(
            prompt_hash=prompt_hash,
            was_hit=was_hit,
            latency_ms=latency_ms,
            model=model,
            provider=provider
        )
        self.accesses.append(access)
        self.access_index[prompt_hash].append(len(self.accesses) - 1)

        self.analyzer.record_access(prompt_hash, access.timestamp)
        self.statistics.update(was_hit, latency_ms)

    def get_cache_recommendations(
        self,
        workspace_id: str,
        current_cache_size_mb: float
    ) -> Dict[str, Any]:
        """
        Get cache optimization recommendations.

        Args:
            workspace_id: Workspace identifier
            current_cache_size_mb: Current cache size in MB

        Returns:
            Recommendations for cache optimization
        """
        recommendations = []

        # Hit rate recommendation
        if self.statistics.hit_rate < 0.8:
            recommendations.append({
                "type": "hit_rate",
                "severity": "warning",
                "message": f"Low hit rate ({self.statistics.hit_rate:.1%}). Consider cache warming.",
                "action": "enable_predictive_warming"
            })
        elif self.statistics.hit_rate > 0.98:
            recommendations.append({
                "type": "hit_rate",
                "severity": "info",
                "message": f"High hit rate ({self.statistics.hit_rate:.1%}). Cache may be oversized.",
                "action": "reduce_cache_size"
            })

        # Cache size recommendation
        if self.config.enable_dynamic_sizing:
            if current_cache_size_mb < self.config.min_cache_size_mb:
                recommendations.append({
                    "type": "cache_size",
                    "severity": "warning",
                    "message": f"Cache size ({current_cache_size_mb}MB) below minimum.",
                    "action": f"increase_to_{self.config.min_cache_size_mb}MB"
                })
            elif current_cache_size_mb > self.config.max_cache_size_mb:
                recommendations.append({
                    "type": "cache_size",
                    "severity": "warning",
                    "message": f"Cache size ({current_cache_size_mb}MB) exceeds maximum.",
                    "action": f"reduce_to_{self.config.max_cache_size_mb}MB"
                })

        return {
            "current_hit_rate": round(self.statistics.hit_rate, 3),
            "avg_latency_ms": round(self.statistics.avg_latency_ms, 1),
            "total_accesses": self.statistics.total_accesses,
            "recommendations": recommendations,
            "warming_candidates": len(self.warmer.warmed_entries)
        }

    def get_optimal_cache_size(self, target_hit_rate: float = 0.95) -> int:
        """
        Calculate optimal cache size based on access patterns.

        Args:
            target_hit_rate: Target hit rate (0-1)

        Returns:
            Recommended cache size in MB
        """
        # Analyze working set
        prompt_counts = defaultdict(int)
        for access in self.accesses[-10000:]:  # Last 10k accesses
            prompt_counts[access.prompt_hash] += 1

        # Sort by frequency
        sorted_prompts = sorted(prompt_counts.items(), key=lambda x: x[1], reverse=True)

        # Find cache size needed for target hit rate
        cumulative_hits = 0
        total_accesses = sum(prompt_counts.values())

        if total_accesses == 0:
            return self.config.min_cache_size_mb

        for prompt_hash, count in sorted_prompts:
            cumulative_hits += count
            if cumulative_hits / total_accesses >= target_hit_rate:
                # Estimate memory per entry
                entry_size_mb = 0.001  # ~1KB per entry
                required_entries = len(sorted_prompts) - len([
                    p for p, c in sorted_prompts
                    if cumulative_hits - sum(c for _, c in sorted_prompts[:sorted_prompts.index((prompt_hash, count))]) > target_hit_rate * total_accesses
                ])
                return int(max(
                    self.config.min_cache_size_mb,
                    required_entries * entry_size_mb
                ))

        return int(self.config.min_cache_size_mb)


# ============================================================================
# Factory
# ============================================================================

def get_cache_optimizer(config: Optional[CacheOptimizationConfig] = None) -> CacheOptimizer:
    """Factory function to get cache optimizer instance"""
    return CacheOptimizer(config)


def get_cache_warmer(config: Optional[CacheOptimizationConfig] = None) -> CacheWarmer:
    """Factory function to get cache warmer instance"""
    return CacheWarmer(config)


def get_pattern_analyzer(config: Optional[CacheOptimizationConfig] = None) -> AccessPatternAnalyzer:
    """Factory function to get pattern analyzer instance"""
    return AccessPatternAnalyzer(config)
