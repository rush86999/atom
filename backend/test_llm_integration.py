#!/usr/bin/env python3
"""
Quick test script to verify BYOK LLM integration in new API endpoints.

Run this to test competitor analysis and learning plan generation.
"""
import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_competitor_analysis():
    """Test competitor analysis with BYOK integration"""
    print("\n" + "="*60)
    print("Testing Competitor Analysis with BYOK Integration")
    print("="*60)

    from api.competitor_analysis_routes import analyze_with_llm

    competitor_data = {
        "name": "Tesla",
        "url": "https://www.tesla.com",
        "data_source": "test"
    }

    focus_areas = ["products", "pricing", "marketing"]

    try:
        insights = await analyze_with_llm(competitor_data, focus_areas)

        print(f"\n✅ Competitor: {insights.competitor}")
        print(f"Strengths: {', '.join(insights.strengths[:2])}...")
        print(f"Weaknesses: {', '.join(insights.weaknesses[:2])}...")
        print(f"Market Position: {insights.market_position}")
        print("\n✅ Competitor analysis test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Competitor analysis test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_learning_plan():
    """Test learning plan generation with BYOK integration"""
    print("\n" + "="*60)
    print("Testing Learning Plan Generation with BYOK Integration")
    print("="*60)

    from api.learning_plan_routes import generate_learning_modules

    topic = "Machine Learning"
    current_level = "beginner"
    duration_weeks = 4
    preferred_formats = ["videos", "exercises"]
    learning_goals = ["Understand neural networks", "Build ML models"]

    try:
        modules = await generate_learning_modules(
            topic=topic,
            current_level=current_level,
            duration_weeks=duration_weeks,
            preferred_formats=preferred_formats,
            learning_goals=learning_goals
        )

        print(f"\n✅ Topic: {topic}")
        print(f"Modules Generated: {len(modules)}")
        print(f"\nFirst Module: {modules[0].title}")
        print(f"Objectives: {', '.join(modules[0].objectives[:2])}...")
        print(f"Resources: {len(modules[0].resources)} items")
        print("\n✅ Learning plan test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Learning plan test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n🧪 BYOK LLM Integration Test Suite")
    print("="*60)

    # Check if API keys are configured
    has_keys = any([
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("DEEPSEEK_API_KEY"),
        os.getenv("GOOGLE_API_KEY")
    ])

    if not has_keys:
        print("\n⚠️  WARNING: No LLM API keys found in environment")
        print("   Tests will use fallback implementations")
        print("   Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY for LLM integration")
    else:
        print("\n✅ LLM API keys detected")

    # Run tests
    results = []
    results.append(await test_competitor_analysis())
    results.append(await test_learning_plan())

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✅ All {total} tests PASSED")
        print("\n🎉 BYOK integration is working correctly!")
    else:
        print(f"⚠️  {passed}/{total} tests passed")
        print("\nNote: Failures may be due to missing API keys (using fallbacks)")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
