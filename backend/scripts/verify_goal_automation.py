import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.goal_engine import Goal, goal_engine
from core.workflow_engine import get_workflow_engine


async def verify_goal_automation():
    print("🚀 Starting Goal-Driven Automation Verification...")
    
    # 1. Test Goal Decomposition
    print("\n--- 1. Testing Goal Decomposition ---")
    title = "Close the Series B funding deal"
    target_date = datetime.utcnow() + timedelta(days=30)
    
    goal = await goal_engine.create_goal_from_text(title, target_date)
    print(f"Goal created: {goal.title}")
    print(f"Sub-tasks generated: {len(goal.sub_tasks)}")
    for st in goal.sub_tasks:
        print(f"  - [{st.status}] {st.title} (Due: {st.due_date.strftime('%Y-%m-%d')})")
    
    assert len(goal.sub_tasks) > 0
    assert goal.status == "ACTIVE"

    # 2. Test Progress Updates
    print("\n--- 2. Testing Progress Updates ---")
    st1 = goal.sub_tasks[0]
    st1.status = "COMPLETED"
    await goal_engine.update_goal_progress(goal.id)
    print(f"Sub-task '{st1.title}' marked COMPLETED.")
    print(f"New Progress: {goal.progress}%")
    
    assert goal.progress > 0

    # 3. Test Escalation Detection
    print("\n--- 3. Testing Escalation Detection ---")
    # Manually backdate a sub-task to trigger escalation
    st2 = goal.sub_tasks[1]
    st2.due_date = datetime.utcnow() - timedelta(days=1)
    print(f"Sub-task '{st2.title}' backdated to trigger delay.")
    
    escalations = await goal_engine.check_for_escalations()
    print(f"Escalations detected: {len(escalations)}")
    for esc in escalations:
        print(f"  - ALERT: {esc['goal_title']} -> {esc['sub_task_title']}")
        print(f"    Suggestion: {esc['remediation']}")
    
    assert len(escalations) > 0
    assert st2.status == "DELAYED"

    # 4. Test Workflow Integration
    print("\n--- 4. Testing Workflow Service Registration ---")
    engine = get_workflow_engine()
    # Mock parameters for create_goal action
    params = {
        "title": "Hire Lead Engineer",
        "target_date": (datetime.utcnow() + timedelta(days=14)).isoformat(),
        "owner_id": "test_user"
    }
    
    result = await engine._execute_goal_management_action("create_goal", params)
    print(f"Workflow service 'create_goal' result: {result['title']}")
    assert result['title'] == "Hire Lead Engineer"
    assert len(result['sub_tasks']) > 0

    print("\n✅ Verification Complete! Goal-Driven Automation is functional.")

if __name__ == "__main__":
    asyncio.run(verify_goal_automation())
