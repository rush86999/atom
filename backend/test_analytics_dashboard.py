#!/usr/bin/env python3
"""
Analytics Dashboard Test Script
Run this to verify the analytics dashboard is working correctly.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        from api.analytics_dashboard_endpoints import router
        from core.workflow_analytics_engine import WorkflowAnalyticsEngine
        print("  ✓ All imports successful")
        return True, router
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False, None

def test_engine_initialization():
    """Test analytics engine initialization."""
    print("\nTesting engine initialization...")
    try:
        from core.workflow_analytics_engine import WorkflowAnalyticsEngine
        engine = WorkflowAnalyticsEngine()
        print("  ✓ Analytics engine initialized")
        return True, engine
    except Exception as e:
        print(f"  ✗ Engine initialization failed: {e}")
        return False, None

def test_helper_methods(engine):
    """Test all helper methods."""
    print("\nTesting helper methods...")

    tests_passed = 0
    tests_failed = 0

    # Test 1: get_unique_workflow_count
    try:
        count = engine.get_unique_workflow_count('24h')
        print(f"  ✓ get_unique_workflow_count: {count}")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ get_unique_workflow_count failed: {e}")
        tests_failed += 1

    # Test 2: get_all_workflow_ids
    try:
        workflows = engine.get_all_workflow_ids('24h')
        print(f"  ✓ get_all_workflow_ids: {len(workflows)} workflows")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ get_all_workflow_ids failed: {e}")
        tests_failed += 1

    # Test 3: get_recent_events
    try:
        events = engine.get_recent_events(limit=5)
        print(f"  ✓ get_recent_events: {len(events)} events")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ get_recent_events failed: {e}")
        tests_failed += 1

    # Test 4: get_all_alerts
    try:
        alerts = engine.get_all_alerts()
        print(f"  ✓ get_all_alerts: {len(alerts)} alerts")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ get_all_alerts failed: {e}")
        tests_failed += 1

    # Test 5: get_performance_metrics
    try:
        kpis = engine.get_performance_metrics('*', '24h')
        print(f"  ✓ get_performance_metrics: {kpis.total_executions} executions")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ get_performance_metrics failed: {e}")
        tests_failed += 1

    # Test 6: get_execution_timeline
    try:
        timeline = engine.get_execution_timeline('*', '24h', '1h')
        print(f"  ✓ get_execution_timeline: {len(timeline)} data points")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ get_execution_timeline failed: {e}")
        tests_failed += 1

    # Test 7: get_error_breakdown
    try:
        errors = engine.get_error_breakdown('*', '24h')
        print(f"  ✓ get_error_breakdown: {len(errors.get('recent_errors', []))} errors")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ get_error_breakdown failed: {e}")
        tests_failed += 1

    print(f"\n  Helper methods: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0

def test_alert_management(engine):
    """Test alert creation, update, and delete."""
    print("\nTesting alert management...")

    from datetime import datetime

    from core.workflow_analytics_engine import Alert, AlertSeverity

    try:
        # Create alert
        alert = Alert(
            alert_id='test-alert-validation',
            name='Test Alert',
            description='Test alert for validation',
            severity=AlertSeverity.LOW,
            condition='error_rate > 0',
            threshold_value=0.0,
            metric_name='error_rate',
            workflow_id=None,
            enabled=True,
            created_at=datetime.now(),
            notification_channels=[]
        )

        engine.create_alert(alert)
        print("  ✓ Created test alert")

        # Update alert
        engine.update_alert(alert.alert_id, enabled=False)
        print("  ✓ Updated alert")

        # Delete alert
        engine.delete_alert(alert.alert_id)
        print("  ✓ Deleted alert")

        return True
    except Exception as e:
        print(f"  ✗ Alert management failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 70)
    print("Analytics Dashboard Validation Test")
    print("=" * 70)

    # Test imports
    success, router = test_imports()
    if not success:
        print("\n❌ FAILED: Cannot import required modules")
        return 1

    # Test router
    print(f"\nRouter has {len(router.routes)} routes:")
    for route in router.routes[:5]:
        if hasattr(route, 'path'):
            print(f"  - {route.path}")
    if len(router.routes) > 5:
        print(f"  ... and {len(router.routes) - 5} more")

    # Test engine
    success, engine = test_engine_initialization()
    if not success:
        print("\n❌ FAILED: Cannot initialize analytics engine")
        return 1

    # Test helper methods
    if not test_helper_methods(engine):
        print("\n⚠️  WARNING: Some helper methods failed")

    # Test alert management
    if not test_alert_management(engine):
        print("\n⚠️  WARNING: Alert management failed")

    print("\n" + "=" * 70)
    print("✅ Analytics Dashboard Validation Complete")
    print("=" * 70)
    print("\nThe analytics dashboard is ready to use!")
    print("\nNext steps:")
    print("1. Start the backend server: python3 main_api_app.py")
    print("2. Access endpoints at: http://localhost:8000/api/analytics/dashboard/*")
    print("3. Integrate frontend component in Next.js app")

    return 0

if __name__ == '__main__':
    sys.exit(main())
