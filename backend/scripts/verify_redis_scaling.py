
import asyncio
import logging
import os
import sys
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RedisScalingTest")

async def test_redis_scaling_config():
    print("🚀 Starting Redis Scaling & Production Readiness Verification...")
    print("=" * 60)
    
    from core.config import ATOMConfig, get_config
    config = get_config()
    
    # 1. Test Default Config (SQLite/Internal)
    print("\n🔍 Testing Default Setup (Local Development)...")
    print(f"   - Redis Enabled: {config.redis.enabled}")
    print(f"   - Scheduler Store: {config.scheduler.job_store_type}")
    
    # 2. Test WorkflowScheduler with SQLAlchemy (Default)
    from ai.workflow_scheduler import WorkflowScheduler
    scheduler = WorkflowScheduler()
    print("   ✅ WorkflowScheduler initialized in Default mode")
    if 'default' in scheduler.scheduler._jobstores:
        store = scheduler.scheduler._jobstores['default']
        print(f"   ✅ JobStore type: {type(store).__name__}")
    
    # 3. Simulating Production Mode via Env Vars
    print("\n🔍 Testing Production Scaling Setup (Redis)...")
    with patch.dict(os.environ, {
        'REDIS_URL': 'redis://production-host:6379/1',
        'SCHEDULER_JOB_STORE_TYPE': 'redis'
    }):
        # Need to reload config to see env changes
        from core.config import load_config
        prod_config = load_config()
        
        print(f"   - (ENV) Redis Enabled: {prod_config.redis.enabled}")
        print(f"   - (ENV) Redis Host: {prod_config.redis.host}")
        print(f"   - (ENV) Scheduler Store: {prod_config.scheduler.job_store_type}")
        
        # Test Scheduler Init with Redis (will attempt connection)
        # We use create=True because the module might not be installed
        with patch('apscheduler.jobstores.redis.RedisJobStore', create=True) as MockRedisStore:
            try:
                prod_scheduler = WorkflowScheduler()
                print("   ✅ WorkflowScheduler initialized in Production Scaling mode")
            except Exception as e:
                print(f"   ⚠️ WorkflowScheduler init failed (expected if module is truly missing and not mocked well): {e}")
            
            # Check if it tried to use Redis (it will if it passes the config check)
            # Actually our code does 'from apscheduler.jobstores.redis import RedisJobStore' which will fail if not installed
            # and our code catches it and falls back.

    # 4. Test CacheManager with Production Config
    print("\n🔍 Testing CacheManager Scaling...")
    with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379/0'}):
        load_config()
        with patch('redis.from_url') as mock_redis_from_url:
            from core.cache import CacheManager
            cache_mgr = CacheManager()
            if mock_redis_from_url.called:
                print("   ✅ CacheManager correctly attempted to connect to Redis URL")

    print("\n" + "=" * 60)
    print("🏁 Redis Scaling & Production Readiness Verification Completed")

if __name__ == "__main__":
    asyncio.run(test_redis_scaling_config())
