import asyncio
import os
import sys
import time

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

async def test_phase6():
    print("--- Phase 6 Verification: Autonomous Healing & Predictive Analytics ---")
    
    from enhanced_workflow_api import enhanced_workflow_api, MetricsAggregator, IntelligenceAnalyzeRequest, ai_service
    from core.circuit_breaker import circuit_breaker
    
    # Mock AI Service to avoid BYOK provider errors during unit test
    if ai_service:
        async def mock_analyze(*args, **kwargs):
            return "Mock analysis result"
        ai_service.analyze_text = mock_analyze
    
    # 1. Test Predictive Analytics
    print("\n1. Testing Predictive Analytics...")
    # Record some mock metrics first
    MetricsAggregator.record_metric("slack", 0.5, True) # 500ms
    MetricsAggregator.record_metric("slack", 0.6, True) # 600ms
    
    prediction = await enhanced_workflow_api.predict_service_performance({"service_id": "slack"})
    print(f"✓ Prediction Result: {prediction}")
    
    # 2. Test Autonomous Healing Callbacks
    print("\n2. Testing Autonomous Healing Callbacks...")
    # Simulate a circuit open event
    print("Triggering circuit failure for 'slack'...")
    circuit_breaker._disable_integration("slack")
    
    # Check healing logs
    healing_report = await enhanced_workflow_api.get_healing_logs()
    logs = healing_report.get("logs", [])
    print(f"✓ Healing Logs after failure: {logs}")
    
    found_failure_log = any(log["service"] == "slack" and "auto_health_ping" in log["action"] for log in logs)
    if found_failure_log:
        print("✓ AI Healer correctly responded to service failure")
    else:
        print("✗ AI Healer failed to respond to service failure")

    # Simulate recovery
    print("\nTriggering circuit recovery for 'slack'...")
    circuit_breaker.reset("slack") # This should trigger reset callbacks in our implementation if not for the fact reset() clears stats. 
    # Actually, the implementation uses _try_reenable to trigger on_reset. 
    # Let's manually trigger recovery for testing if reset doesn't call it.
    circuit_breaker._try_reenable("slack") 
    
    healing_report = await enhanced_workflow_api.get_healing_logs()
    print(f"✓ Healing Logs after recovery: {healing_report.get('logs')}")

    # 3. Test Predictive Routing in Analysis
    print("\n3. Testing Predictive Routing in Analysis...")
    request = IntelligenceAnalyzeRequest(text="Send a message to slack")
    result = await enhanced_workflow_api.analyze_workflow_intent(request)
    
    for suggestion in result.get("routing_suggestions", []):
        if suggestion.get("primary") == "slack":
            print(f"✓ Routing Suggestion: {suggestion.get('action_suggestion')}")
            if "Predictive Alert" in suggestion.get("action_suggestion"):
                 print("✓ Predictive Alert correctly injected into suggestion")
            else:
                 print("✗ Predictive Alert missing from suggestion")

if __name__ == "__main__":
    asyncio.run(test_phase6())
