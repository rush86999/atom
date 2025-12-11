#!/usr/bin/env python3
"""Test script for enhanced AI validation system"""

import asyncio
import sys
from utils.enhanced_ai_validation import EnhancedAIValidationSystem, AIProvider


async def test_enhanced_system():
    """Test the enhanced AI validation system"""
    print("Testing Enhanced AI Validation System...")

    # Test with fallback provider (always available)
    system = EnhancedAIValidationSystem(preferred_provider=AIProvider.FALLBACK)

    print("Provider status:", system.get_provider_status())

    # Test claims
    claims = [
        "Automates workflows with natural language processing",
        "Provides seamless integration across platforms",
        "Delivers production-ready AI automation"
    ]

    # Mock test output
    test_output = {
        "workflow_automation": {
            "status": "success",
            "natural_language_input": "Create a workflow to process emails",
            "automated_actions": ["email_classification", "response_generation"],
            "integration_points": ["gmail", "slack", "calendar"]
        },
        "performance_metrics": {
            "processing_time": 1.2,
            "accuracy": 0.95,
            "success_rate": 0.98
        }
    }

    # Test batch validation
    print("Testing batch validation...")
    results = await system.batch_validate_claims(claims, test_output)

    print("Results:")
    for claim, result in results.items():
        status = "PASS" if result.verified else "FAIL"
        print(f"  {status}: {claim[:40]}... (confidence: {result.confidence:.2f}, provider: {result.provider.value})")

    # Test business outcome validation
    print("Testing business outcome validation...")
    business_result = await system.validate_business_outcome(
        "time_savings",
        {"hours_saved_per_task": 2, "tasks_per_month": 100, "hourly_rate": 75}
    )

    print(f"Business outcome: {business_result['verified']} (score: {business_result['business_value_score']:.1f}, projection: {business_result['annual_value_projection']})")

    print("Enhanced AI validation system test complete!")


async def test_backward_compatibility():
    """Test backward compatibility with existing LLM verifier"""
    print("Testing backward compatibility...")

    try:
        from utils.llm_verifier import LLMVerifier

        # Test with fallback (should work without API keys)
        verifier = LLMVerifier(use_enhanced=True)

        claim = "Automates workflows with natural language processing"
        test_output = {"workflow": {"status": "success", "automated": True}}

        result = verifier.verify_marketing_claim(claim, test_output)

        print("Backward compatibility test: PASS")
        print(f"  Claim verified: {result.get('verified', False)}")
        print(f"  Confidence: {result.get('confidence', 0):.2f}")
        print(f"  Provider: {result.get('provider', 'unknown')}")

    except Exception as e:
        print(f"Backward compatibility test: FAIL - {e}")


async def main():
    """Main test function"""
    await test_enhanced_system()
    await test_backward_compatibility()


if __name__ == "__main__":
    asyncio.run(main())