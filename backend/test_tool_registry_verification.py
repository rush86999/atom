#!/usr/bin/env python3
"""
Tool Registry Verification Script
Tests all aspects of the tool registry system.
"""

from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        from api.tools import router
        from tools.registry import ToolMetadata, ToolRegistry, get_tool_registry
        print("  ✓ All imports successful")
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False

def test_router_registration():
    """Test API router registration."""
    print("\n1. API Router Registration")
    print("-" * 70)
    try:
        from api.tools import router

        print(f"✓ Router loaded: {len(router.routes)} routes")
        print("\n  Routes:")
        for route in router.routes:
            if hasattr(route, 'path'):
                methods = getattr(route, 'methods', None)
                print(f"    {methods if methods else 'ALL':8} {route.path}")

        return True
    except Exception as e:
        print(f"✗ Router test failed: {e}")
        return False

def test_registry_initialization():
    """Test tool registry initialization."""
    print("\n2. Registry Initialization")
    print("-" * 70)
    try:
        from tools.registry import get_tool_registry

        registry = get_tool_registry()
        print(f"✓ Registry initialized")
        print(f"✓ Registry type: {type(registry).__name__}")
        print(f"✓ Initialized flag: {registry._initialized}")

        return True, registry
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return False, None

def test_tool_listing(registry):
    """Test listing all registered tools."""
    print("\n3. Tool Listing")
    print("-" * 70)
    try:
        all_tools = registry.list_all()
        print(f"✓ Total tools registered: {len(all_tools)}")

        # List by category
        categories = registry._categories
        print(f"\n  Tools by Category:")
        for category, tools in sorted(categories.items()):
            print(f"    {category:15} {len(tools):2} tools")

        return True
    except Exception as e:
        print(f"✗ Tool listing failed: {e}")
        return False

def test_core_tools(registry):
    """Test that core tools are registered."""
    print("\n4. Core Tools Verification")
    print("-" * 70)

    # Define expected core tools by category
    core_tools = {
        "canvas": ["present_chart", "present_markdown", "present_form"],
        "browser": ["browser_create_session", "browser_navigate", "browser_screenshot"],
        "device": ["device_camera_snap", "device_get_location", "device_send_notification"]
    }

    all_passed = True
    for category, tools in core_tools.items():
        print(f"\n  {category.upper()} Tools:")
        for tool in tools:
            metadata = registry.get(tool)
            if metadata:
                print(f"    ✓ {tool:30} [{metadata.maturity_required}]")
            else:
                print(f"    ✗ {tool:30} NOT FOUND")
                all_passed = False

    return all_passed

def test_governance_integration(registry):
    """Test governance integration by maturity level."""
    print("\n5. Governance Integration")
    print("-" * 70)

    maturity_levels = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

    print("\n  Tools accessible by maturity level:")
    for maturity in maturity_levels:
        tools = registry.list_by_maturity(maturity)
        print(f"    {maturity:12} {len(tools):2} tools")

    # Verify that AUTONOMOUS has access to all tools
    all_tools = registry.list_all()
    autonomous_tools = registry.list_by_maturity("AUTONOMOUS")

    if len(autonomous_tools) == len(all_tools):
        print(f"\n  ✓ AUTONOMOUS agents have access to all tools ({len(all_tools)})")
        return True
    else:
        print(f"\n  ✗ AUTONOMOUS missing {len(all_tools) - len(autonomous_tools)} tools")
        return False

def test_tool_metadata(registry):
    """Test tool metadata structure."""
    print("\n6. Tool Metadata Structure")
    print("-" * 70)

    # Get a sample tool
    all_tools = registry.list_all()
    if not all_tools:
        print("  ⚠️ No tools to test metadata")
        return False

    sample_tool = all_tools[0]
    metadata = registry.get(sample_tool)

    if not metadata:
        print(f"  ✗ Could not get metadata for {sample_tool}")
        return False

    print(f"  Testing: {sample_tool}")
    print(f"    Name: {metadata.name}")
    print(f"    Category: {metadata.category}")
    print(f"    Complexity: {metadata.complexity}")
    print(f"    Maturity Required: {metadata.maturity_required}")
    print(f"    Version: {metadata.version}")
    print(f"    Description: {metadata.description[:50]}...")

    # Test to_dict conversion
    try:
        tool_dict = metadata.to_dict()
        print(f"    ✓ to_dict() works: {len(tool_dict)} fields")
        return True
    except Exception as e:
        print(f"    ✗ to_dict() failed: {e}")
        return False

def test_auto_discovery(registry):
    """Test auto-discovery functionality."""
    print("\n7. Auto-Discovery")
    print("-" * 70)

    # Get current tool count
    initial_count = len(registry.list_all())

    try:
        # Run auto-discovery
        discovered = registry.discover_tools()
        print(f"  ✓ Auto-discovery completed")
        print(f"    Discovered {discovered} new tools")

        final_count = len(registry.list_all())
        print(f"    Total tools: {initial_count} → {final_count}")

        return True
    except Exception as e:
        print(f"  ✗ Auto-discovery failed: {e}")
        return False

def test_api_endpoints():
    """Test that API endpoints are accessible."""
    print("\n8. API Endpoint Verification")
    print("-" * 70)

    from api.tools import router

    expected_endpoints = [
        ("/api/tools", "GET"),
        ("/api/tools/{name}", "GET"),
        ("/api/tools/category/{category}", "GET"),
        ("/api/tools/search", "GET"),
        ("/api/tools/stats", "GET"),
    ]

    all_found = True
    for path, method in expected_endpoints:
        found = False
        for route in router.routes:
            if hasattr(route, 'path') and route.path == path:
                found = True
                break

        if found:
            print(f"  ✓ {method:8} {path}")
        else:
            print(f"  ✗ {method:8} {path} NOT FOUND")
            all_found = False

    return all_found

def test_stats(registry):
    """Test registry statistics."""
    print("\n9. Registry Statistics")
    print("-" * 70)

    try:
        stats = registry.get_stats()

        print(f"  Total tools: {stats['total_tools']}")
        print(f"\n  Categories:")
        for category, count in stats['categories'].items():
            print(f"    {category:15} {count:2} tools")

        print(f"\n  Complexity Distribution:")
        for level, count in stats['complexity_distribution'].items():
            print(f"    {level:10} {count:2} tools")

        print(f"\n  Maturity Distribution:")
        for level, count in stats['maturity_distribution'].items():
            print(f"    {level:10} {count:2} tools")

        return True
    except Exception as e:
        print(f"  ✗ Stats failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 70)
    print("Tool Registry Verification Test")
    print("=" * 70)

    # Test imports
    if not test_imports():
        print("\n❌ FAILED: Cannot import required modules")
        return 1

    # Test router
    if not test_router_registration():
        print("\n⚠️  WARNING: Router registration issues")

    # Test initialization
    success, registry = test_registry_initialization()
    if not success:
        print("\n❌ FAILED: Cannot initialize registry")
        return 1

    # Run all tests
    results = []

    results.append(("Tool Listing", test_tool_listing(registry)))
    results.append(("Core Tools", test_core_tools(registry)))
    results.append(("Governance Integration", test_governance_integration(registry)))
    results.append(("Tool Metadata", test_tool_metadata(registry)))
    results.append(("Auto-Discovery", test_auto_discovery(registry)))
    results.append(("API Endpoints", test_api_endpoints()))
    results.append(("Statistics", test_stats(registry)))

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status} {test_name}")

    print(f"\n  {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! Tool registry is working correctly.")
        print("\nNext steps:")
        print("  1. Start the backend server")
        print("  2. Test API endpoints at http://localhost:8000/api/tools")
        print("  3. Use tools in agents with proper governance checks")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
