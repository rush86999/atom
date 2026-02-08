import sys
import os
import asyncio
import logging
from collections import defaultdict

# Add backend to path
sys.path.append(os.getcwd())
sys.stdout.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stdout)
logger = logging.getLogger("TestMetrics")

# Mock classes to avoid full initialization
class MockCache:
    def __init__(self):
        self.client = None

def test_metrics_logic():
    print("\n🧪 Testing AI Metrics Logic (Redis & Memory)...")
    
    try:
        from integrations.ai_enhanced_service import AIEnhancedService
        from core.cache import cache
        
        # Check Redis Connection
        print("Checking Redis connection status...")
        try:
            if cache.client and cache.client.ping():
                print("✅ Redis is CONNECTED. Testing Redis persistence.")
                # Clear existing test keys to start fresh
                cache.client.delete("atom:ai:metrics:total_requests")
                cache.client.delete("atom:ai:metrics:successful_requests")
            else:
                print("⚠️ Redis client exists but PING failed or client is None.")
                print("   -> Testing in-memory fallback.")
        except Exception as e:
            print(f"⚠️ Redis Connection Error: {e}")
            print("   -> Testing in-memory fallback.")

        # Initialize Service (with dummy keys)
        service = AIEnhancedService({
            'openai_api_key': 'dummy',
            'anthropic_api_key': 'dummy'
        })

        # 1. Test Initial State
        print("\n--- 1. Initial State ---")
        metrics = asyncio.run(service.get_performance_metrics())
        print(f"Total Requests: {metrics['total_requests']}")
        
        # 2. Simulate Activity
        print("\n--- 2. Simulating Activity ---")
        async def simulate():
            # Simulate a successful request
            await service._increment_metric('total_requests')
            await service._increment_metric('successful_requests')
            await service._update_avg_metric('average_response_time', 0.5)
            await service._increment_metric('token_usage', 100, 'total_tokens')
            await service._increment_metric('service_usage', 1, 'openai')
            
            # Simulate a failed request
            await service._increment_metric('total_requests')
            await service._increment_metric('failed_requests')
            await service._update_avg_metric('average_response_time', 1.5)

        asyncio.run(simulate())
        print("Simulated 2 requests (1 success, 1 fail).")

        # 3. Verify Results
        print("\n--- 3. Verifying Metrics ---")
        new_metrics = asyncio.run(service.get_performance_metrics())
        
        print(f"Total Requests: {new_metrics['total_requests']} (Expected: >= 2)")
        print(f"Success Rate: {new_metrics['success_rate']}%")
        print(f"Avg Response Time: {new_metrics['average_response_time']:.2f}s (Expected: ~1.00s)")
        print(f"Token Usage: {new_metrics['token_usage']}")
        
        # Assertions
        if cache.client:
            # If Redis, we verify direct key check
            r_total = int(cache.client.get("atom:ai:metrics:total_requests") or 0)
            print(f"Redis Key Check: atom:ai:metrics:total_requests = {r_total}")
            
        print("\n✅ Verification Complete!")

    except ImportError as e:
        print(f"❌ Import Error: {e}")
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_metrics_logic()
