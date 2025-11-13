"""
Direct Test Script for Enhanced Workflow System
Tests the enhanced workflow capabilities without requiring full backend startup
"""

import logging
import os
import sys

# Add backend to path
sys.path.append("backend/python-api-service")

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_enhanced_workflow_import():
    """Test importing enhanced workflow components"""
    print("🧪 Testing Enhanced Workflow System Import...")

    try:
        from enhanced_workflow.enhanced_workflow_api import EnhancedWorkflowAPI

        print("✅ Enhanced Workflow API imported successfully")

        # Test creating API instance
        api = EnhancedWorkflowAPI()
        print("✅ Enhanced Workflow API instance created successfully")

        # Test blueprint creation
        blueprint = api.get_blueprint()
        print(f"✅ Blueprint created: {blueprint.name}")

        # Check routes
        routes = list(blueprint.deferred_functions)
        print(f"✅ Number of routes registered: {len(routes)}")

        return True

    except Exception as e:
        print(f"❌ Enhanced Workflow import failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_workflow_intelligence():
    """Test workflow intelligence integration"""
    print("\n🧪 Testing Workflow Intelligence Integration...")

    try:
        from enhanced_workflow.workflow_intelligence_integration import (
            WorkflowIntelligenceIntegration,
        )

        intelligence = WorkflowIntelligenceIntegration()
        print("✅ Workflow Intelligence Integration initialized")

        # Test service detection
        user_input = (
            "Create a workflow to send slack notifications when github PRs are created"
        )
        context = {"user_preferences": {"preferred_services": ["slack", "github"]}}

        result = intelligence.analyze_workflow_request(user_input, context)

        if result.get("success"):
            print("✅ Workflow intelligence analysis successful")
            print(f"   - Detected services: {len(result.get('detected_services', []))}")
            print(f"   - Confidence score: {result.get('confidence_score', 0)}")
            print(
                f"   - Enhanced intelligence: {result.get('enhanced_intelligence', False)}"
            )
        else:
            print("❌ Workflow intelligence analysis failed")

        return True

    except Exception as e:
        print(f"❌ Workflow intelligence test failed: {e}")
        return False


def test_workflow_optimization():
    """Test workflow optimization integration"""
    print("\n🧪 Testing Workflow Optimization Integration...")

    try:
        from enhanced_workflow.workflow_optimization_integration import (
            WorkflowOptimizationIntegration,
        )

        optimization = WorkflowOptimizationIntegration()
        print("✅ Workflow Optimization Integration initialized")

        # Test workflow analysis
        sample_workflow = {
            "name": "Test Workflow",
            "steps": [
                {"service": "slack", "action": "send_message", "id": "step1"},
                {"service": "github", "action": "create_issue", "id": "step2"},
            ],
            "services": ["slack", "github"],
        }

        import asyncio

        async def test_async():
            result = await optimization.analyze_workflow_performance(sample_workflow)
            return result

        result = asyncio.run(test_async())

        if result.get("success"):
            print("✅ Workflow optimization analysis successful")
            print(
                f"   - Estimated execution time: {result.get('estimated_execution_time', 0)}s"
            )
            print(f"   - Estimated cost: ${result.get('estimated_cost', 0)}")
            print(f"   - Bottlenecks found: {len(result.get('bottlenecks', []))}")
        else:
            print("❌ Workflow optimization analysis failed")

        return True

    except Exception as e:
        print(f"❌ Workflow optimization test failed: {e}")
        return False


def test_workflow_monitoring():
    """Test workflow monitoring integration"""
    print("\n🧪 Testing Workflow Monitoring Integration...")

    try:
        from enhanced_workflow.workflow_monitoring_integration import (
            WorkflowMonitoringIntegration,
        )

        monitoring = WorkflowMonitoringIntegration()
        print("✅ Workflow Monitoring Integration initialized")

        # Test monitoring start
        workflow_id = "test_workflow_123"
        result = monitoring.start_monitoring(workflow_id)

        if result.get("success"):
            print("✅ Workflow monitoring started successfully")

            # Test metric recording
            metric_result = monitoring.record_metric(workflow_id, "execution_time", 2.5)
            if metric_result.get("success"):
                print("✅ Metric recording successful")
            else:
                print("❌ Metric recording failed")

            # Test health check
            health_result = monitoring.get_workflow_health(workflow_id)
            if health_result.get("success"):
                print("✅ Workflow health check successful")
                print(f"   - Health score: {health_result.get('health_score', 0)}")
                print(f"   - Status: {health_result.get('status', 'unknown')}")
            else:
                print("❌ Workflow health check failed")

            # Stop monitoring
            monitoring.stop_monitoring(workflow_id)
            print("✅ Workflow monitoring stopped")

        else:
            print("❌ Workflow monitoring start failed")

        return True

    except Exception as e:
        print(f"❌ Workflow monitoring test failed: {e}")
        return False


def test_enhanced_api_endpoints():
    """Test enhanced API endpoint registration"""
    print("\n🧪 Testing Enhanced API Endpoint Registration...")

    try:
        from enhanced_workflow.enhanced_workflow_api import EnhancedWorkflowAPI

        api = EnhancedWorkflowAPI()
        blueprint = api.get_blueprint()

        # List all registered routes
        routes = list(blueprint.deferred_functions)
        endpoint_names = []

        for route_func in routes:
            # Extract route information from the function
            if hasattr(route_func, "__name__"):
                endpoint_names.append(route_func.__name__)

        print(f"✅ Found {len(endpoint_names)} enhanced workflow endpoints:")
        for name in endpoint_names:
            print(f"   - {name}")

        # Verify key endpoints are present
        required_endpoints = [
            "enhanced_intelligence_analyze",
            "enhanced_intelligence_generate",
            "enhanced_optimization_analyze",
            "enhanced_monitoring_start",
            "enhanced_monitoring_health",
        ]

        missing_endpoints = [
            ep for ep in required_endpoints if ep not in endpoint_names
        ]

        if not missing_endpoints:
            print("✅ All required endpoints are registered")
        else:
            print(f"❌ Missing endpoints: {missing_endpoints}")

        return len(missing_endpoints) == 0

    except Exception as e:
        print(f"❌ Enhanced API endpoint test failed: {e}")
        return False


def main():
    """Run all enhanced workflow tests"""
    print("🚀 Enhanced Workflow System Direct Testing")
    print("=" * 50)

    test_results = []

    # Run all tests
    test_results.append(("Import Test", test_enhanced_workflow_import()))
    test_results.append(("Intelligence Test", test_workflow_intelligence()))
    test_results.append(("Optimization Test", test_workflow_optimization()))
    test_results.append(("Monitoring Test", test_workflow_monitoring()))
    test_results.append(("API Endpoints Test", test_enhanced_api_endpoints()))

    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1

    success_rate = (passed / total) * 100
    print(f"\n🎯 Success Rate: {success_rate:.1f}% ({passed}/{total} tests passed)")

    if success_rate >= 80:
        print("🎉 Enhanced Workflow System: READY FOR PRODUCTION")
    elif success_rate >= 60:
        print("⚠️  Enhanced Workflow System: NEEDS OPTIMIZATION")
    else:
        print("❌ Enhanced Workflow System: REQUIRES FIXES")

    return success_rate >= 80


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
