import asyncio
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
backend_root = Path(__file__).parent.parent.resolve()
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from core.workflow_analytics_engine import get_analytics_engine
from core.automation_insight_manager import get_insight_manager
from core.behavior_analyzer import get_behavior_analyzer
from core.lancedb_handler import get_lancedb_handler

async def verify_user_isolation():
    print("🚀 Starting Per-User Isolation Verification...")
    
    analytics = get_analytics_engine()
    insight_manager = get_insight_manager()
    behavior_analyzer = get_behavior_analyzer()
    lancedb = get_lancedb_handler()
    
    user_a = "user_alpha"
    user_b = "user_beta"
    
    # 1. Verify Analytics Isolation
    print("\n1. Verifying Analytics Isolation...")
    # Simulate User A activity
    analytics.track_step_execution("wf1", "exec1", "step1", "Step 1", "step_completed", user_id=user_a)
    analytics.track_manual_override("wf1", "exec1", "res1", "fix_deadline", user_id=user_a)
    
    # Simulate User B activity
    analytics.track_step_execution("wf2", "exec2", "step2", "Step 2", "step_completed", user_id=user_b)
    
    await analytics.flush()
    await asyncio.sleep(2) # Wait for batch processing
    
    # Check drift metrics for User A
    insights_a = insight_manager.get_drift_metrics(user_id=user_a)
    print(f"User A Insights: {json.dumps(insights_a, indent=2)}")
    
    # Check drift metrics for User B
    insights_b = insight_manager.get_drift_metrics(user_id=user_b)
    print(f"User B Insights: {json.dumps(insights_b, indent=2)}")
    
    # Verify User B doesn't see User A's override
    has_override_a = any(i['overrides'] > 0 for i in insights_a)
    has_override_b = any(i['overrides'] > 0 for i in insights_b)
    
    if has_override_a and not has_override_b:
        print("✅ Analytics isolation verified!")
    else:
        print(f"❌ Analytics isolation failed! (A override: {has_override_a}, B override: {has_override_b})")

    # 2. Verify Memory Isolation
    print("\n2. Verifying Memory Isolation...")
    table_name = "test_isolation_table"
    lancedb.add_document(table_name, "This is top secret context for User A", user_id=user_a)
    lancedb.add_document(table_name, "This is public info for User B", user_id=user_b)
    
    # Search for User A
    results_a = lancedb.search(table_name, "top secret", user_id=user_a)
    print(f"User A Search Results: {len(results_a)}")
    
    # Search for User B
    results_b = lancedb.search(table_name, "top secret", user_id=user_b)
    print(f"User B Search Results: {len(results_b)}")
    
    # Verify User B doesn't see User A's secret document
    allowed_a = any("top secret" in r['text'].lower() for r in results_a)
    allowed_b = any("top secret" in r['text'].lower() for r in results_b)
    
    if allowed_a and not allowed_b:
        print("✅ Memory isolation verified!")
    else:
        print(f"❌ Memory isolation failed! (A found secret: {allowed_a}, B found secret: {allowed_b})")

    print("\n🎉 Per-User Isolation Verification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_user_isolation())
