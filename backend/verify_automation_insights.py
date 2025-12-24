import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
backend_root = Path(__file__).parent.parent.resolve()
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from core.workflow_analytics_engine import get_analytics_engine
from core.automation_insight_manager import get_insight_manager
from core.behavior_analyzer import get_behavior_analyzer
from core.workflow_engine import WorkflowEngine

async def verify_automation_insights():
    print("🚀 Starting Automation Insights Verification...")
    
    analytics = get_analytics_engine()
    insight_manager = get_insight_manager()
    behavior_analyzer = get_behavior_analyzer()
    
    # 1. Simulate a Workflow Execution that produces a task
    print("\n1. Simulating Workflow Execution...")
    workflow_id = "test-workflow-001"
    execution_id = "exec-123"
    resource_id = "task-456"
    
    analytics.track_step_execution(
        workflow_id=workflow_id,
        execution_id=execution_id,
        step_id="create_task_1",
        step_name="Create Asana Task",
        event_type="step_completed",
        duration_ms=450,
        status="COMPLETED",
        resource_id=resource_id
    )
    
    # 2. Simulate a Manual Override on that task
    print("2. Simulating Manual Override...")
    analytics.track_manual_override(
        workflow_id=workflow_id,
        execution_id=execution_id,
        resource_id=resource_id,
        action="manual_edit_priority",
        metadata={"old_priority": "low", "new_priority": "high"}
    )
    
    # Force process buffer
    await analytics.flush()
    
    # 3. Verify Drift Detection
    print("3. Verifying Drift Metrics...")
    insights = insight_manager.get_drift_metrics(workflow_id=workflow_id)
    if insights and insights[0]['drift_score'] > 0:
        print(f"✅ Drift detected: {insights[0]['drift_score']}")
        print(f"✅ Recommendation: {insights[0]['recommendation']}")
    else:
        print("❌ Drift not detected as expected")

    # 4. Simulate User Behavior Sequence
    print("\n4. Simulating User Behavior Sequence (Meeting -> Task -> Slack)...")
    user_id = "user1"
    behavior_analyzer.log_user_action(user_id, "meeting_ended")
    behavior_analyzer.log_user_action(user_id, "task_created", {"title": "Send follow-up"})
    behavior_analyzer.log_user_action(user_id, "slack_message_sent", {"channel": "#general"})
    
    # 5. Verify Suggestions
    print("5. Verifying Behavior Suggestions...")
    suggestions = behavior_analyzer.detect_patterns(user_id)
    if suggestions:
        print(f"✅ Suggestion found: {suggestions[0]['name']}")
        print(f"✅ Description: {suggestions[0]['description']}")
    else:
        print("❌ No suggestions found")

    print("\n🎉 Verification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_automation_insights())
