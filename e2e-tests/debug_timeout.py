#!/usr/bin/env python3
"""
Debug timeout issue in LLMVerifier enhanced system
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.enhanced_ai_validation import (
    EnhancedAIValidationSystem,
    AIProvider,
    create_validation_system
)
from utils.llm_verifier import LLMVerifier

async def debug_enhanced_direct():
    """Test enhanced system directly with timeout"""
    print("🧪 Direct enhanced system test")
    system = create_validation_system("openai")
    print("Providers:", system.get_provider_status())

    claim = "Automates workflows with natural language processing"
    test_output = {"workflow": {"status": "success", "automated": True}}

    try:
        # Use wait_for to timeout after 5 seconds
        result = await asyncio.wait_for(
            system.validate_claim(claim, test_output),
            timeout=5.0
        )
        print(f"✅ Direct enhanced system result: verified={result.verified}, confidence={result.confidence:.2f}")
    except asyncio.TimeoutError:
        print("❌ Direct enhanced system timed out after 5 seconds")
        return False
    except Exception as e:
        print(f"❌ Direct enhanced system error: {e}")
        import traceback
        traceback.print_exc()
        return False
    return True

async def debug_llm_verifier():
    """Test LLMVerifier with enhanced system"""
    print("\n🧪 LLMVerifier enhanced system test")
    verifier = LLMVerifier(use_enhanced=True)

    claim = "Automates workflows with natural language processing"
    test_output = {"workflow": {"status": "success", "automated": True}}

    try:
        # Use wait_for to timeout after 5 seconds
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: verifier.verify_marketing_claim(claim, test_output)
            ),
            timeout=5.0
        )
        print(f"✅ LLMVerifier result: verified={result.get('verified', False)}, confidence={result.get('confidence', 0):.2f}")
    except asyncio.TimeoutError:
        print("❌ LLMVerifier timed out after 5 seconds")
        return False
    except Exception as e:
        print(f"❌ LLMVerifier error: {e}")
        import traceback
        traceback.print_exc()
        return False
    return True

async def debug_provider_order():
    """Check provider order logic"""
    print("\n🧪 Provider order debug")
    system = create_validation_system("openai")
    print("Providers dict keys:", list(system.providers.keys()))
    print("Preferred provider:", system.preferred_provider)

    # Simulate validate_claim logic
    provider_order = []
    if system.preferred_provider in system.providers:
        provider_order.append(system.preferred_provider)
    for provider in [AIProvider.DEEPSEEK, AIProvider.OPENAI, AIProvider.GLM]:
        if provider in system.providers and provider not in provider_order:
            provider_order.append(provider)
    if AIProvider.FALLBACK in system.providers:
        provider_order.append(AIProvider.FALLBACK)
    print("Provider order:", provider_order)

    # Check each provider's validator
    for provider in provider_order:
        validator = system.providers[provider]
        print(f"  {provider.value}: {type(validator).__name__}")

async def main():
    print("🚀 Debugging Timeout Issue")
    print("=" * 60)

    await debug_provider_order()
    print("-" * 60)
    success = await debug_enhanced_direct()
    print("-" * 60)
    if success:
        await debug_llm_verifier()

    print("\n" + "=" * 60)
    print("Debug complete")

if __name__ == "__main__":
    asyncio.run(main())