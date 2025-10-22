import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from workflow_agent_integration import workflow_agent_integration_service
from context_management_service import context_management_service


async def test_workflow_agent_with_context():
    """Test the workflow agent with context management integration"""
    print("🧪 Testing Workflow Agent with Context Management...")

    # Test user ID and session
    test_user_id = "context_test_user_789"
    test_session_id = "context_test_session_123"

    try:
        # Initialize the workflow agent service
        print("\n1️⃣ Initializing workflow agent service...")
        workflow_agent_integration_service.initialize_services()
        print("✅ Workflow agent service initialized")

        # Set up user preferences for testing
        print("\n2️⃣ Setting up user context...")
        test_preferences = {
            "automation_level": "full",
            "communication_style": "professional",
            "preferred_services": ["gmail", "slack", "notion", "github"],
            "business_context": {
                "companySize": "small",
                "technicalSkill": "advanced",
                "goals": ["automation", "collaboration", "productivity"],
            },
        }

        await context_management_service.save_user_preferences(
            test_user_id, test_preferences
        )
        print("✅ User preferences set up")

        # Test 1: Simple workflow request with context
        print("\n3️⃣ Testing simple workflow request...")
        simple_request = "When I receive important emails, send me Slack notifications"

        result = workflow_agent_integration_service.process_natural_language_workflow_request(
            user_input=simple_request, user_id=test_user_id, session_id=test_session_id
        )

        print(f"✅ Simple workflow result: {result.get('success', False)}")
        if result.get("success"):
            print(f"   Workflow ID: {result.get('workflow_id')}")
            print(f"   Workflow Name: {result.get('workflow_name')}")

        # Test 2: Complex multi-step workflow request
        print("\n4️⃣ Testing complex workflow request...")
        complex_request = "Create a workflow that monitors my GitHub repositories for new issues, creates tasks in Notion, and sends Slack notifications to the team channel"

        result = workflow_agent_integration_service.process_natural_language_workflow_request(
            user_input=complex_request, user_id=test_user_id, session_id=test_session_id
        )

        print(f"✅ Complex workflow result: {result.get('success', False)}")
        if result.get("success"):
            print(f"   Workflow ID: {result.get('workflow_id')}")
            print(f"   Workflow Name: {result.get('workflow_name')}")
            print(f"   Steps Count: {result.get('steps_count')}")

        # Test 3: Check conversation history was recorded
        print("\n5️⃣ Verifying conversation history...")
        history = await context_management_service.get_conversation_history(
            test_user_id, test_session_id
        )

        print(f"✅ Conversation history recorded: {len(history)} messages")
        for i, msg in enumerate(history):
            print(f"   {i + 1}. {msg['role']}: {msg['content'][:60]}...")

        # Test 4: Test context-aware suggestions
        print("\n6️⃣ Testing context-aware workflow suggestions...")
        suggestions = (
            await context_management_service.get_context_aware_workflow_suggestions(
                test_user_id
            )
        )

        print(f"✅ Context-aware suggestions: {len(suggestions)} suggestions")
        for i, suggestion in enumerate(suggestions[:5]):  # Show top 5
            print(
                f"   {i + 1}. {suggestion['name']} (confidence: {suggestion['confidence']})"
            )
            print(f"      Services: {', '.join(suggestion['services'])}")

        # Test 5: Test user context summary
        print("\n7️⃣ Testing user context summary...")
        summary = await context_management_service.get_user_context_summary(
            test_user_id
        )

        print(f"✅ User context summary:")
        print(f"   - Recent conversations: {summary.get('recent_conversations', 0)}")
        print(f"   - Active workflows: {summary.get('active_workflows', 0)}")
        print(
            f"   - Preferred services: {', '.join(summary.get('preferred_services', []))}"
        )

        # Test 6: Test conditional workflow with context
        print("\n8️⃣ Testing conditional workflow...")
        conditional_request = "If I receive emails from my manager, create high-priority tasks in Asana and send me a Slack DM"

        result = workflow_agent_integration_service.process_natural_language_workflow_request(
            user_input=conditional_request,
            user_id=test_user_id,
            session_id=test_session_id,
        )

        print(f"✅ Conditional workflow result: {result.get('success', False)}")
        if result.get("success"):
            print(f"   Workflow ID: {result.get('workflow_id')}")
            print(f"   Workflow Name: {result.get('workflow_name')}")

        # Test 7: Verify context is influencing workflow generation
        print("\n9️⃣ Testing context influence...")

        # Get the updated conversation history
        updated_history = await context_management_service.get_conversation_history(
            test_user_id, test_session_id
        )

        # Check if context hints are being used
        workflow_messages = [
            msg
            for msg in updated_history
            if msg.get("message_type") == "workflow_response"
        ]
        print(f"✅ Workflow responses recorded: {len(workflow_messages)}")

        # Show how context influenced the workflows
        user_preferences = await context_management_service.get_user_preferences(
            test_user_id
        )
        print(f"✅ User preferences influencing workflows:")
        print(f"   - Automation level: {user_preferences.get('automation_level')}")
        print(
            f"   - Preferred services: {', '.join(user_preferences.get('preferred_services', []))}"
        )

        print("\n🎉 All workflow agent context tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


async def test_context_aware_analysis():
    """Test the context-aware workflow analysis specifically"""
    print("\n🔍 Testing Context-Aware Workflow Analysis...")

    test_user_id = "analysis_test_user"

    try:
        # Set up specific preferences for analysis testing
        analysis_preferences = {
            "automation_level": "moderate",
            "communication_style": "friendly",
            "preferred_services": ["gmail", "google_calendar", "notion"],
            "business_context": {
                "companySize": "solo",
                "technicalSkill": "intermediate",
                "goals": ["efficiency", "organization"],
            },
        }

        await context_management_service.save_user_preferences(
            test_user_id, analysis_preferences
        )

        # Add some conversation history for context
        await context_management_service.add_conversation_message(
            user_id=test_user_id,
            session_id="analysis_session",
            role="user",
            content="I need help organizing my emails and calendar",
            message_type="general_request",
        )

        # Test different workflow requests with context
        test_requests = [
            "Schedule meetings when I get calendar invites",
            "Create tasks from important emails",
            "Organize my documents automatically",
        ]

        for i, request in enumerate(test_requests):
            print(f"\n   Testing request {i + 1}: {request}")
            result = workflow_agent_integration_service.process_natural_language_workflow_request(
                user_input=request, user_id=test_user_id, session_id="analysis_session"
            )

            if result.get("success"):
                print(f"      ✅ Workflow created: {result.get('workflow_name')}")
            else:
                print(f"      ❌ Failed: {result.get('error', 'Unknown error')}")

        print("\n✅ Context-aware analysis tests completed!")

    except Exception as e:
        print(f"❌ Context analysis test failed: {e}")


if __name__ == "__main__":
    print("🚀 Starting Workflow Agent Context Management Tests")
    print("=" * 60)

    # Run tests
    asyncio.run(test_workflow_agent_with_context())
    asyncio.run(test_context_aware_analysis())

    print("\n" + "=" * 60)
    print("🏁 All workflow agent context tests completed!")
