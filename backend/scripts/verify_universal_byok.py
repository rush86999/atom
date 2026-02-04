import asyncio
import logging
import os
import sys

# Set up path and logging
sys.path.append(os.getcwd())
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from core.byok_endpoints import get_byok_manager
except ImportError:
    # Try alternate path
    try:
        from backend.core.byok_endpoints import get_byok_manager
    except ImportError:
        logger.error("Could not import BYOKManager")
        get_byok_manager = None

async def verify_byok_integration():
    logger.info("Starting Universal BYOK Verification...")
    
    if not get_byok_manager:
        logger.error("BYOKManager not available. Skipping verification.")
        return

    manager = get_byok_manager()
    
    # 1. Test Key Injection
    test_key = "sk-verify-byok-test-key-12345"
    manager.store_api_key("openai", test_key, key_name="verification_test")
    logger.info("Stored test key in BYOKManager")
    
    # Check retrieval
    retrieved_key = manager.get_api_key("openai", key_name="verification_test")
    if retrieved_key == test_key:
        logger.info("SUCCESS: BYOKManager returned the correct injected key")
    else:
        logger.error(f"FAILURE: BYOKManager returned {retrieved_key}")
        return

    # 2. Check Service Integration (Internal Check)
    try:
        from integrations.ai_enhanced_service import ai_enhanced_service
        if ai_enhanced_service.byok_manager == manager:
            logger.info("SUCCESS: AIEnhancedService is linked to the correct BYOKManager")
        else:
            logger.warning("AIEnhancedService BYOKManager mismatch")
    except Exception as e:
        logger.warning(f"Could not verify AIEnhancedService link: {e}")

    # 3. Usage Tracking Check
    manager.track_usage("openai", success=True, tokens_used=500)
    usage = manager.usage_stats.get("openai")
    if usage and usage.total_tokens_used >= 500:
        logger.info("SUCCESS: Usage tracking is functional")
    else:
        logger.error("FAILURE: Usage tracking failed")

    logger.info("Universal BYOK Verification Complete.")

if __name__ == "__main__":
    asyncio.run(verify_byok_integration())
