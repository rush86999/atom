#!/usr/bin/env python3
"""
Test LUX Model Integration
Comprehensive testing for computer use capabilities
"""

import asyncio
import sys
import os
import json
import logging
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, '/Users/rushiparikh/projects/atom/backend')

from core.lux_config import lux_config
from ai.lux_marketplace import marketplace
from ai.lux_model import get_lux_model

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_lux_config():
    """Test LUX configuration and credentials loading"""
    print("\n🔧 Testing LUX Configuration")
    print("=" * 50)

    try:
        # Test credentials loading
        print("\n1. Testing credentials loading...")
        keys = lux_config.get_all_keys()
        print(f"✅ Loaded {len(keys)} API keys:")
        for provider, key in keys.items():
            masked_key = key[:8] + "..." if len(key) > 8 else key
            print(f"   - {provider}: {masked_key}")

        # Test key validation
        print("\n2. Testing API key validation...")
        validation = lux_config.validate_keys()
        print(f"✅ API key validation results:")
        for provider, is_valid in validation.items():
            status = "✅ Valid" if is_valid else "❌ Invalid"
            print(f"   - {provider}: {status}")

        # Test specific key retrieval
        print("\n3. Testing specific key retrieval...")
        anthropic_key = lux_config.get_anthropic_key()
        if anthropic_key:
            print(f"✅ Anthropic key found: {anthropic_key[:10]}...")
        else:
            print("❌ Anthropic key not found")

        print("✅ LUX configuration test passed!")
        return True

    except Exception as e:
        print(f"❌ LUX configuration test failed: {e}")
        return False

async def test_lux_marketplace():
    """Test LUX marketplace functionality"""
    print("\n🛍️ Testing LUX Marketplace")
    print("=" * 50)

    try:
        # Test getting models
        print("\n1. Testing model retrieval...")
        models = marketplace.get_available_models()
        print(f"✅ Found {len(models)} available models")
        for model in models[:3]:  # Show first 3
            print(f"   - {model.name}: {model.description}")

        # Test getting templates
        print("\n2. Testing template retrieval...")
        templates = marketplace.get_automation_templates()
        print(f"✅ Found {len(templates)} automation templates")
        for template in templates[:3]:  # Show first 3
            print(f"   - {template.name}: {template.description}")

        # Test featured models
        print("\n3. Testing featured models...")
        featured = marketplace.get_featured_models()
        print(f"✅ Found {len(featured)} featured models")

        # Test search functionality
        print("\n4. Testing search functionality...")
        search_results = marketplace.search_models("computer use")
        print(f"✅ Search returned {len(search_results)} results for 'computer use'")

        print("✅ LUX marketplace test passed!")
        return True

    except Exception as e:
        print(f"❌ LUX marketplace test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_lux_model():
    """Test LUX model functionality"""
    print("\n🤖 Testing LUX Model")
    print("=" * 50)

    try:
        # Test model initialization
        print("\n1. Testing model initialization...")
        lux = await get_lux_model()
        print(f"✅ LUX model initialized successfully")
        print(f"   - Screen resolution: {lux.screen_width}x{lux.screen_height}")

        # Test screen info
        print("\n2. Testing screen information...")
        screen_info = await lux.get_screen_info()
        if "error" not in screen_info:
            print(f"✅ Screen info retrieved:")
            print(f"   - Resolution: {screen_info['screen_resolution']}")
            print(f"   - Elements found: {screen_info['elements_found']}")
        else:
            print(f"⚠️  Screen info returned error: {screen_info['error']}")

        # Test screenshot capture
        print("\n3. Testing screenshot capture...")
        screenshot = await lux.capture_screen()
        print(f"✅ Screenshot captured successfully: {screenshot.size}")

        # Test command interpretation (safe command)
        print("\n4. Testing command interpretation...")
        test_command = "wait 1 second"
        actions = await lux.interpret_command(test_command)
        print(f"✅ Command interpretation for '{test_command}':")
        for action in actions:
            print(f"   - {action.action_type.value}: {action.description}")

        # Test command execution
        print("\n5. Testing command execution...")
        result = await lux.execute_command(test_command)
        print(f"✅ Command executed:")
        print(f"   - Success: {result.get('success', False)}")
        print(f"   - Actions: {len(result.get('actions', []))}")
        print(f"   - Execution time: {result.get('execution_time', 0):.2f}s")

        print("✅ LUX model test passed!")
        return True

    except Exception as e:
        print(f"❌ LUX model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_integration_endpoints():
    """Test that LUX endpoints are properly integrated"""
    print("\n🔌 Testing Integration Endpoints")
    print("=" * 50)

    try:
        # Test by importing the routes
        print("\n1. Testing route imports...")

        try:
            from ai.lux_routes import router as lux_router
            print("✅ LUX routes imported successfully")
        except ImportError as e:
            print(f"❌ LUX routes import failed: {e}")
            return False

        try:
            from api.lux_marketplace_routes import router as marketplace_router
            print("✅ LUX marketplace routes imported successfully")
        except ImportError as e:
            print(f"❌ LUX marketplace routes import failed: {e}")
            return False

        # Test route registration
        print("\n2. Testing route registration...")
        lux_routes = [route.path for route in lux_router.routes]
        marketplace_routes = [route.path for route in marketplace_router.routes]

        print(f"✅ LUX routes registered: {len(lux_routes)}")
        print(f"   - Routes: {lux_routes[:3]}...")  # Show first 3

        print(f"✅ Marketplace routes registered: {len(marketplace_routes)}")
        print(f"   - Routes: {marketplace_routes[:3]}...")  # Show first 3

        print("✅ Integration endpoints test passed!")
        return True

    except Exception as e:
        print(f"❌ Integration endpoints test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_comprehensive_test():
    """Run all LUX integration tests"""
    print("🚀 Starting LUX Integration Test Suite")
    print("=" * 70)
    print(f"Test started at: {datetime.now().isoformat()}")

    test_results = []

    # Run all tests
    tests = [
        ("Configuration & Credentials", test_lux_config),
        ("Marketplace System", test_lux_marketplace),
        ("LUX Model Functionality", test_lux_model),
        ("Integration Endpoints", test_integration_endpoints)
    ]

    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            result = await test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception: {e}")
            test_results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("📊 Test Results Summary")
    print("="*70)

    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")

    print(f"\nOverall: {passed}/{total} tests passed")
    print(f"Test completed at: {datetime.now().isoformat()}")

    if passed == total:
        print("\n🎉 All LUX integration tests passed successfully!")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    # Set environment for testing
    os.chdir('/Users/rushiparikh/projects/atom/backend')

    # Run tests
    success = asyncio.run(run_comprehensive_test())

    if success:
        print("\n✨ LUX implementation is ready for use!")
    else:
        print("\n🔧 LUX implementation needs attention.")
        sys.exit(1)