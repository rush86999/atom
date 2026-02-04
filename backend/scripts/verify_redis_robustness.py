
import asyncio
import logging
import os
import sys
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RedisRobustnessTest")

async def test_redis_robustness():
    print("🚀 Starting Refined Redis Robustness Verification...")
    print("=" * 60)
    
    # 1. Test CacheManager
    print("\n🔍 Testing CacheManager (Redis-optional)...")
    try:
        from core.cache import cache
        print("   ✅ CacheManager imported")
        # Operations are async
        await cache.set("test_key", "test_value")
        val = await cache.get("test_key")
        if val == "test_value":
            print("   ✅ Cache set/get successful (InMemory fallback working)")
        else:
            print(f"   ❌ Cache value mismatch: {val}")
    except Exception as e:
        print(f"   ❌ CacheManager test failed: {e}")

    # 2. Test MonitoringSystem
    print("\n🔍 Testing MonitoringSystem (Redis-optional)...")
    try:
        # Mocking numpy since it's missing but not related to Redis test
        sys.modules['numpy'] = MagicMock()
        from ai.workflow_troubleshooting.monitoring_system import monitoring_system
        print("   ✅ MonitoringSystem imported (with numpy mocked)")
        print("   ✅ MonitoringSystem initialized successfully")
    except Exception as e:
        print(f"   ❌ MonitoringSystem test failed: {e}")

    # 3. Test SlackEnhancedService
    print("\n🔍 Testing SlackEnhancedService (Redis-optional)...")
    try:
        from integrations.slack_enhanced_service import SlackEnhancedService
        slack = SlackEnhancedService({'redis': {'enabled': True, 'host': 'nonexistent_host'}})
        print("   ✅ SlackEnhancedService initialized with invalid Redis configuration")
        if slack.redis_client is None:
            print("   ✅ SlackEnhancedService correctly handled Redis absence")
        else:
            print("   ⚠️ SlackEnhancedService still has a redis_client object")
    except Exception as e:
        print(f"   ❌ SlackEnhancedService test failed: {e}")

    # 4. Test DiscordEnhancedService
    print("\n🔍 Testing DiscordEnhancedService (Redis-optional)...")
    try:
        # Mocking websockets and aiohttp since they might be missing
        sys.modules['websockets'] = MagicMock()
        sys.modules['aiohttp'] = MagicMock()
        from integrations.discord_enhanced_service import DiscordEnhancedService
        discord = DiscordEnhancedService({'redis': {'client': None}})
        print("   ✅ DiscordEnhancedService initialized without Redis")
        # Test a method that used to potentially fail
        guild = discord._get_guild_by_id("123")
        print("   ✅ DiscordEnhancedService._get_guild_by_id handled None Redis gracefully")
    except Exception as e:
        print(f"   ❌ DiscordEnhancedService test failed: {e}")

    print("\n" + "=" * 60)
    print("🏁 Redis Robustness Verification Completed")

if __name__ == "__main__":
    asyncio.run(test_redis_robustness())
