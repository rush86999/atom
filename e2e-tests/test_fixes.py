#!/usr/bin/env python3
"""
Test script to verify AI validation system fixes
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.enhanced_ai_validation import (
    EnhancedAIValidationSystem,
    AIProvider,
    create_validation_system,
    validate_marketing_claims
)
from utils.llm_verifier import LLMVerifier
from utils.glm_verifier import GLMVerifier

async def test_enhanced_system():
    """Test enhanced AI validation system with fallback provider"""
    print("🧪 Testing Enhanced AI Validation System...")

    # Create system with fallback provider (should always work)
    system = EnhancedAIValidationSystem(preferred_provider=AIProvider.FALLBACK)

    print("Provider status:", system.get_provider_status())

    # Test claims
    claims = [
        "Automates workflows with natural language processing",
        "Provides seamless integration across platforms",
    ]

    # Mock test output
    test_output = {
        "workflow_automation": {
            "status": "success",
            "natural_language_input": "Create a workflow to process emails",
            "automated_actions": ["email_classification", "response_generation"],
        }
    }

    # Test batch validation
    print("Testing batch validation...")
    results = await system.batch_validate_claims(claims, test_output)

    print("Results:")
    for claim, result in results.items():
        status = "PASS" if result.verified else "FAIL"
        print(f"  {status}: {claim[:40]}... (confidence: {result.confidence:.2f}, provider: {result.provider.value})")

    # Test single claim validation
    print("Testing single claim validation...")
    result = await system.validate_claim(claims[0], test_output)
    print(f"Single claim result: verified={result.verified}, confidence={result.confidence:.2f}")

    print("✅ Enhanced AI validation system test passed")
    return True

async def test_llm_verifier():
    """Test LLMVerifier with enhanced system fallback"""
    print("\n🧪 Testing LLMVerifier with enhanced system...")

    # Create verifier with enhanced system (should fallback to legacy if no API keys)
    verifier = LLMVerifier(use_enhanced=True)

    claim = "Automates workflows with natural language processing"
    test_output = {"workflow": {"status": "success", "automated": True}}

    result = verifier.verify_marketing_claim(claim, test_output)
    print(f"LLMVerifier result: verified={result.get('verified', False)}, confidence={result.get('confidence', 0):.2f}")

    # Test batch verification
    results = verifier.batch_verify_claims([claim], test_output)
    print(f"Batch verification: {len(results)} results")

    print("✅ LLMVerifier test passed")
    return True

async def test_glm_verifier():
    """Test GLMVerifier (requires GLM_API_KEY env var)"""
    print("\n🧪 Testing GLMVerifier...")

    if not os.getenv("GLM_API_KEY"):
        print("⚠️  GLM_API_KEY not set, skipping GLMVerifier test")
        return True

    try:
        verifier = GLMVerifier()
        claim = "Automates workflows with natural language processing"
        test_output = {"workflow": {"status": "success", "automated": True}}

        result = verifier.verify_marketing_claim(claim, test_output)
        print(f"GLMVerifier result: verified={result.get('verified', False)}, confidence={result.get('confidence', 0):.2f}")
        print("✅ GLMVerifier test passed")
        return True
    except Exception as e:
        print(f"❌ GLMVerifier test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting AI Validation System Fix Tests")
    print("=" * 60)

    success = True

    try:
        success &= await test_enhanced_system()
    except Exception as e:
        print(f"❌ Enhanced system test failed: {e}")
        import traceback
        traceback.print_exc()
        success = False

    try:
        success &= await test_llm_verifier()
    except Exception as e:
        print(f"❌ LLMVerifier test failed: {e}")
        import traceback
        traceback.print_exc()
        success = False

    try:
        success &= await test_glm_verifier()
    except Exception as e:
        print(f"❌ GLMVerifier test failed: {e}")
        import traceback
        traceback.print_exc()
        success = False

    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())