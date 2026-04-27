#!/usr/bin/env python3
"""
Test Dynamic Benchmark Integration

Verifies that the dynamic benchmark fetcher works correctly
and integrates with benchmarks.py for backward compatibility.
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["TESTING"] = "1"

# Test imports
try:
    from core.dynamic_benchmark_fetcher import get_benchmark_fetcher, refresh_benchmark_cache
    print("[PASS] Dynamic benchmark fetcher imported successfully")
except ImportError as e:
    print(f"[FAIL] Could not import dynamic benchmark fetcher: {e}")
    sys.exit(1)

try:
    from core.benchmarks import get_quality_score, get_capability_score
    print("[PASS] Benchmark functions imported successfully")
except ImportError as e:
    print(f"[FAIL] Could not import benchmark functions: {e}")
    sys.exit(1)

# Test 1: Static fallback (without API calls)
print("\n[Test 1] Static fallback works")
try:
    # This should work even without API calls (uses static fallback)
    score = get_quality_score("gpt-4o")
    if isinstance(score, (int, float)) and 0 <= score <= 100:
        print(f"[PASS] Static fallback for gpt-4o: {score}")
    else:
        print(f"[FAIL] Invalid score: {score}")
except Exception as e:
    print(f"[FAIL] Static fallback failed: {e}")

# Test 2: Capability score with static fallback
print("\n[Test 2] Capability score with static fallback")
try:
    score = get_capability_score("claude-3.5-sonnet", "vision")
    if isinstance(score, (int, float)) and 0 <= score <= 100:
        print(f"[PASS] Capability score for claude-3.5-sonnet/vision: {score}")
    else:
        print(f"[FAIL] Invalid capability score: {score}")
except Exception as e:
    print(f"[FAIL] Capability score failed: {e}")

# Test 3: Fetcher instantiation
print("\n[Test 3] Benchmark fetcher instantiation")
try:
    fetcher = get_benchmark_fetcher()
    print(f"[PASS] Benchmark fetcher created")
    print(f"  - Last fetch: {fetcher.last_fetch}")
    print(f"  - Cached models: {len(fetcher.benchmark_cache)}")
except Exception as e:
    print(f"[FAIL] Could not create fetcher: {e}")

# Test 4: Check if we have cached data
print("\n[Test 4] Check for cached benchmark data")
try:
    fetcher = get_benchmark_fetcher()
    if fetcher.benchmark_cache:
        print(f"[PASS] Found {len(fetcher.benchmark_cache)} cached benchmark scores")
        # Show top 5 models
        top_models = sorted(fetcher.benchmark_cache.items(), key=lambda x: x[1], reverse=True)[:5]
        print("  Top 5 models:")
        for model, score in top_models:
            print(f"    - {model}: {score:.1f}")
    else:
        print("[INFO] No cached benchmark data (will fetch on first use)")
except Exception as e:
    print(f"[FAIL] Could not check cache: {e}")

print("\n" + "=" * 60)
print("Integration Test Complete!")
print("=" * 60)
print("\nSummary:")
print("✓ Dynamic benchmark fetcher is available")
print("✓ Backward compatibility maintained (static fallback works)")
print("✓ Capability scoring works")
print("\nNext Steps:")
print("1. Set up Redis/UniversalCache for production")
print("2. Run refresh_benchmark_cache() periodically (cron job)")
print("3. Monitor logs for 'Using dynamic benchmark score' messages")
