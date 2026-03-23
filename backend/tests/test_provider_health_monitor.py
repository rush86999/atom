"""
Unit tests for ProviderHealthMonitor
Tests health scoring, sliding window, latency calculations, and provider filtering
"""
import pytest
from datetime import datetime, timedelta, timezone
from collections import deque

# Import directly to avoid __init__.py issues
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.provider_health_monitor import ProviderHealthMonitor, get_provider_health_monitor


class TestProviderHealthMonitor:
    """Test suite for ProviderHealthMonitor"""

    def test_initialization(self):
        """Verify default initialization parameters"""
        monitor = ProviderHealthMonitor()

        assert monitor.window_minutes == 5, "Default window should be 5 minutes"
        assert monitor.call_history == {}, "History should start empty"
        assert monitor.health_scores == {}, "Scores should start empty"

    def test_custom_window_size(self):
        """Verify custom window size initialization"""
        monitor = ProviderHealthMonitor(window_minutes=10)

        assert monitor.window_minutes == 10, "Should accept custom window size"

    def test_record_call_single(self):
        """Verify single successful call updates health score"""
        monitor = ProviderHealthMonitor()

        monitor.record_call('openai', True, 1000)

        assert 'openai' in monitor.call_history, "Should track provider"
        assert len(monitor.call_history['openai']) == 1, "Should have 1 entry"
        score = monitor.get_health_score('openai')
        assert score > 0.9, f"Success should score >0.9, got {score}"

    def test_record_call_multiple(self):
        """Verify multiple calls aggregate correctly"""
        monitor = ProviderHealthMonitor()

        for _ in range(5):
            monitor.record_call('anthropic', True, 500)

        assert len(monitor.call_history['anthropic']) == 5, "Should have 5 entries"
        score = monitor.get_health_score('anthropic')
        assert score > 0.9, f"All success should score >0.9, got {score}"

    def test_sliding_window_trimming(self):
        """Verify old entries are removed outside window"""
        monitor = ProviderHealthMonitor(window_minutes=1)

        # Record a call
        monitor.record_call('test', True, 500)
        assert len(monitor.call_history['test']) == 1, "Should have 1 entry"

        # Manually add an old entry outside window
        old_time = datetime.now(timezone.utc) - timedelta(minutes=2)
        monitor.call_history['test'].appendleft((old_time, True, 500))

        # Trigger trimming by recording another call
        monitor.record_call('test', True, 500)

        # Old entry should be trimmed
        assert len(monitor.call_history['test']) == 2, "Old entry should be removed"

        # All remaining entries should be recent
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=1)
        for entry in monitor.call_history['test']:
            assert entry[0] >= cutoff, "All entries should be within window"

    def test_health_score_all_success(self):
        """Verify 100% success rate produces 1.0 score (adjusted for latency)"""
        monitor = ProviderHealthMonitor()

        for _ in range(10):
            monitor.record_call('provider', True, 100)  # Very low latency

        score = monitor.get_health_score('provider')
        # Success rate: 1.0, Latency score: ~0.98
        # Combined: (1.0 * 0.7) + (0.98 * 0.3) ≈ 0.994
        assert score > 0.98, f"All success should score >0.98, got {score}"

    def test_health_score_all_failure(self):
        """Verify 0% success rate produces low score"""
        monitor = ProviderHealthMonitor()

        for _ in range(10):
            monitor.record_call('provider', False, 1000)

        score = monitor.get_health_score('provider')
        # Success rate: 0.0, Latency score: 0.8
        # Combined: (0.0 * 0.7) + (0.8 * 0.3) = 0.24
        assert score < 0.3, f"All failure should score <0.3, got {score}"

    def test_health_score_mixed(self):
        """Verify 50% success rate produces ~0.35 score (from success rate only)"""
        monitor = ProviderHealthMonitor()

        for i in range(10):
            monitor.record_call('provider', i % 2 == 0, 1000)  # 50% success, 1000ms latency

        score = monitor.get_health_score('provider')
        # Success rate: 0.5, Latency score: 0.8 (1000ms / 5000ms)
        # Combined: (0.5 * 0.7) + (0.8 * 0.3) = 0.35 + 0.24 = 0.59
        assert 0.55 < score < 0.65, f"50% success should score ~0.59, got {score}"

    def test_latency_scoring(self):
        """Verify high latency reduces score"""
        monitor = ProviderHealthMonitor()

        # Low latency
        monitor.record_call('fast', True, 100)
        fast_score = monitor.get_health_score('fast')

        # High latency
        monitor.record_call('slow', True, 4000)
        slow_score = monitor.get_health_score('slow')

        assert fast_score > slow_score, f"Fast should score higher: {fast_score} vs {slow_score}"

    def test_latency_5s_zero_score(self):
        """Verify 5000ms latency produces 0 latency score"""
        monitor = ProviderHealthMonitor()

        monitor.record_call('provider', True, 5000)
        score = monitor.get_health_score('provider')

        # Success rate: 1.0, Latency score: max(0, 1 - 5000/5000) = 0
        # Combined: (1.0 * 0.7) + (0 * 0.3) = 0.7
        assert score == 0.7, f"5s latency should score 0.7, got {score}"

    def test_latency_over_5s_clamped(self):
        """Verify >5000ms latency is clamped to 0 latency score"""
        monitor = ProviderHealthMonitor()

        monitor.record_call('provider', True, 10000)
        score = monitor.get_health_score('provider')

        # Success rate: 1.0, Latency score: max(0, 1 - 10000/5000) = 0 (clamped)
        # Combined: (1.0 * 0.7) + (0 * 0.3) = 0.7
        assert score == 0.7, f">5s latency should score 0.7, got {score}"

    def test_ma_weights(self):
        """Verify EMA weights: 70% success, 30% latency"""
        monitor = ProviderHealthMonitor()

        # Test case 1: 100% success, 0ms latency
        monitor.record_call('test1', True, 0)
        score1 = monitor.get_health_score('test1')
        # (1.0 * 0.7) + (1.0 * 0.3) = 1.0
        assert score1 == 1.0, f"Should be 1.0, got {score1}"

        # Test case 2: 100% success, 5000ms latency
        monitor.record_call('test2', True, 5000)
        score2 = monitor.get_health_score('test2')
        # (1.0 * 0.7) + (0 * 0.3) = 0.7
        assert score2 == 0.7, f"Should be 0.7, got {score2}"

        # Test case 3: 0% success, 0ms latency
        monitor.record_call('test3', False, 0)
        score3 = monitor.get_health_score('test3')
        # (0 * 0.7) + (1.0 * 0.3) = 0.3
        assert score3 == 0.3, f"Should be 0.3, got {score3}"

    def test_get_healthy_providers_threshold(self):
        """Verify get_healthy_providers filters by min_score correctly"""
        monitor = ProviderHealthMonitor()

        # Add providers with different health scores
        monitor.record_call('healthy', True, 100)  # High score (~0.99)
        monitor.record_call('unhealthy', False, 5000)  # Low score (0.0 - failure + high latency)

        # Test high threshold
        healthy = monitor.get_healthy_providers(min_score=0.9)
        assert 'healthy' in healthy, "Should include high-scoring provider"
        assert 'unhealthy' not in healthy, "Should exclude low-scoring provider"

        # Test very low threshold (0.0, should include both)
        all_providers = monitor.get_healthy_providers(min_score=0.0)
        assert 'healthy' in all_providers, "Should include high-scoring provider"
        assert 'unhealthy' in all_providers, "Should include low-scoring provider with 0.0 threshold"

        # Test medium threshold (0.5, should exclude unhealthy)
        medium_healthy = monitor.get_healthy_providers(min_score=0.5)
        assert 'healthy' in medium_healthy, "Should include high-scoring provider"
        assert 'unhealthy' not in medium_healthy, "Should exclude low-scoring provider above 0.5"

    def test_get_healthy_providers_empty(self):
        """Verify get_healthy_providers returns empty list when no providers"""
        monitor = ProviderHealthMonitor()

        healthy = monitor.get_healthy_providers(min_score=0.5)
        assert healthy == [], "Should return empty list when no providers"

    def test_get_healthy_providers_all_healthy(self):
        """Verify get_healthy_providers returns all when all above threshold"""
        monitor = ProviderHealthMonitor()

        for provider in ['p1', 'p2', 'p3']:
            monitor.record_call(provider, True, 100)

        healthy = monitor.get_healthy_providers(min_score=0.5)
        assert len(healthy) == 3, "Should return all 3 providers"
        assert 'p1' in healthy and 'p2' in healthy and 'p3' in healthy, "Should include all providers"

    def test_get_healthy_providers_mixed(self):
        """Verify get_healthy_providers filters correctly with mixed health"""
        monitor = ProviderHealthMonitor()

        # Add 10 successful calls to 'healthy'
        for _ in range(10):
            monitor.record_call('healthy', True, 100)

        # Add 10 failed calls to 'unhealthy'
        for _ in range(10):
            monitor.record_call('unhealthy', False, 1000)

        healthy = monitor.get_healthy_providers(min_score=0.5)
        assert 'healthy' in healthy, "Should include healthy provider"
        assert 'unhealthy' not in healthy, "Should exclude unhealthy provider"

    def test_default_score_1_0(self):
        """Verify new providers start with 1.0 (healthy default)"""
        monitor = ProviderHealthMonitor()

        # Don't record any calls for 'new_provider'
        score = monitor.get_health_score('new_provider')

        assert score == 1.0, f"New providers should default to 1.0, got {score}"

    def test_multiple_providers_independent(self):
        """Verify each provider tracked independently"""
        monitor = ProviderHealthMonitor()

        monitor.record_call('p1', True, 100)
        monitor.record_call('p2', False, 5000)
        monitor.record_call('p3', True, 1000)

        score1 = monitor.get_health_score('p1')
        score2 = monitor.get_health_score('p2')
        score3 = monitor.get_health_score('p3')

        assert score1 > score2, "p1 should be healthier than p2"
        assert score3 > score2, "p3 should be healthier than p2"
        assert score1 > 0.9, "p1 should be very healthy"
        assert score2 < 0.5, "p2 should be unhealthy"

    def test_window_boundary_exact(self):
        """Verify entries at window boundary handled correctly"""
        monitor = ProviderHealthMonitor(window_minutes=1)

        # Add an entry at the boundary
        boundary_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        monitor.call_history['boundary'] = deque()
        monitor.call_history['boundary'].append((boundary_time, True, 500))

        # Trim should remove entries at or before boundary
        monitor._trim_old_entries('boundary')

        # Entry at exact boundary should be removed
        assert len(monitor.call_history['boundary']) == 0, "Boundary entry should be trimmed"

    def test_concurrent_record_calls(self):
        """Verify multiple providers update independently"""
        monitor = ProviderHealthMonitor()

        providers = ['p1', 'p2', 'p3', 'p4', 'p5']
        for provider in providers:
            for i in range(5):
                monitor.record_call(provider, i % 2 == 0, 1000)

        # All providers should have 5 entries
        for provider in providers:
            assert len(monitor.call_history[provider]) == 5, f"{provider} should have 5 entries"

        # All providers should have same health score (same call pattern)
        scores = [monitor.get_health_score(p) for p in providers]
        assert len(set(scores)) == 1, "All providers should have same score"

    def test_score_precision(self):
        """Verify scores calculated to 3 decimal places"""
        monitor = ProviderHealthMonitor()

        monitor.record_call('test', True, 1234)
        score = monitor.get_health_score('test')

        # Check precision (should have 3 decimal places)
        score_str = f"{score:.3f}"
        assert len(score_str.split('.')[-1]) == 3, "Should have 3 decimal places"

    def test_empty_history_returns_default(self):
        """Verify providers with empty history return default score"""
        monitor = ProviderHealthMonitor()

        # Record a call then manually clear history and health_scores
        monitor.record_call('test', True, 500)
        monitor.call_history['test'].clear()
        monitor.health_scores.pop('test', None)  # Remove cached score

        score = monitor.get_health_score('test')
        assert score == 1.0, f"Empty history should return default 1.0, got {score}"

    def test_trim_old_entries_empty_history(self):
        """Verify trimming empty history doesn't error"""
        monitor = ProviderHealthMonitor()

        # Should not raise error
        monitor._trim_old_entries('nonexistent')

    def test_update_health_score_empty_history(self):
        """Verify updating score with empty history sets default"""
        monitor = ProviderHealthMonitor()

        monitor._update_health_score('test')

        assert monitor.health_scores['test'] == 1.0, "Empty history should set score to 1.0"

    def test_get_healthy_providers_custom_threshold(self):
        """Verify get_healthy_providers with custom thresholds"""
        monitor = ProviderHealthMonitor()

        # Add provider with known score
        for _ in range(10):
            monitor.record_call('provider', True, 100)

        score = monitor.get_health_score('provider')

        # Test various thresholds
        assert 'provider' in monitor.get_healthy_providers(min_score=score), "Should be in at exact score"
        assert 'provider' in monitor.get_healthy_providers(min_score=score - 0.1), "Should be in below score"
        assert 'provider' not in monitor.get_healthy_providers(min_score=score + 0.1), "Should not be in above score"

    def test_singleton_function(self):
        """Verify get_provider_health_monitor returns singleton"""
        monitor1 = get_provider_health_monitor()
        monitor2 = get_provider_health_monitor()

        assert monitor1 is monitor2, "Should return same instance"

    def test_singleton_persistence(self):
        """Verify singleton persists across calls"""
        monitor1 = get_provider_health_monitor()
        monitor1.record_call('test', True, 500)

        monitor2 = get_provider_health_monitor()
        score = monitor2.get_health_score('test')

        assert score > 0.9, "Singleton should persist state"
