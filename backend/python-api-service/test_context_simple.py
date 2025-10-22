import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from context_management_service import context_management_service


def test_context_management_simple():
    """Simple test for context management without database dependency"""
    print("🧪 Testing Context Management System (Simple)...")

    # Test user ID
    test_user_id = "simple_test_user"
    test_session_id = "simple_test_session"

    try:
        # Test 1: Get user preferences (should return defaults)
        print("\n1️⃣ Testing user preferences...")
        preferences = context_management_service.get_user_preferences_sync(test_user_id)
        print(f"✅ User preferences retrieved: {preferences}")

        # Test 2: Context-aware workflow suggestions
        print("\n2️⃣ Testing context-aware suggestions...")
        suggestions = (
            context_management_service.get_context_aware_workflow_suggestions_sync(
                test_user_id
            )
        )
        print(f"✅ Suggestions generated: {len(suggestions)} suggestions")
        for i, suggestion in enumerate(suggestions):
            print(
                f"   {i + 1}. {suggestion['name']} (confidence: {suggestion['confidence']})"
            )

        # Test 3: User context summary
        print("\n3️⃣ Testing user context summary...")
        summary = context_management_service.get_user_context_summary_sync(test_user_id)
        print(f"✅ User context summary:")
        print(f"   - User ID: {summary.get('user_id')}")
        print(
            f"   - Preferred services: {', '.join(summary.get('preferred_services', []))}"
        )
        print(
            f"   - Automation level: {summary.get('preferences', {}).get('automation_level')}"
        )

        # Test 4: Context extraction from conversation
        print("\n4️⃣ Testing context extraction...")

        # Simulate some conversation history
        test_conversation = [
            {
                "role": "user",
                "content": "I need help with email automation",
                "message_type": "workflow_request",
                "timestamp": "2024-01-01T10:00:00",
            },
            {
                "role": "assistant",
                "content": "I can help you set up email automation workflows",
                "message_type": "workflow_response",
                "timestamp": "2024-01-01T10:01:00",
            },
        ]

        # Test the context extraction method directly
        context_service = context_management_service
        extracted_context = context_service._extract_context_from_history(
            test_conversation
        )
        print(f"✅ Context extracted: {extracted_context}")

        # Test 5: Context-aware analysis
        print("\n5️⃣ Testing context-aware analysis...")
        user_input = "Create a workflow for email management"
        user_preferences = preferences
        conversation_history = test_conversation

        # Test the analysis method directly
        analysis_result = context_service._analyze_conversation_for_workflows(
            conversation_history, user_preferences
        )
        print(
            f"✅ Context-aware analysis: {len(analysis_result)} workflow opportunities found"
        )

        print("\n🎉 All simple context management tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


def test_workflow_agent_integration():
    """Test workflow agent integration with context management"""
    print("\n🤖 Testing Workflow Agent Integration...")

    try:
        from workflow_agent_integration import workflow_agent_integration_service

        # Initialize the service
        workflow_agent_integration_service.initialize_services()
        print("✅ Workflow agent service initialized")

        # Test workflow generation with context
        test_user_id = "integration_test_user"
        test_session_id = "integration_test_session"

        test_requests = [
            "Send me Slack notifications for important emails",
            "Create tasks in Notion when I get calendar invites",
            "Automate file organization in Google Drive",
        ]

        for i, request in enumerate(test_requests):
            print(f"\n   Testing request {i + 1}: {request}")
            try:
                result = workflow_agent_integration_service.process_natural_language_workflow_request(
                    user_input=request, user_id=test_user_id, session_id=test_session_id
                )

                if result.get("success"):
                    print(f"      ✅ Workflow created successfully")
                    print(f"      Workflow ID: {result.get('workflow_id')}")
                else:
                    print(f"      ❌ Failed: {result.get('error', 'Unknown error')}")

            except Exception as e:
                print(f"      ❌ Exception: {e}")

        print("\n✅ Workflow agent integration tests completed!")

    except Exception as e:
        print(f"❌ Workflow agent integration test failed: {e}")


if __name__ == "__main__":
    print("🚀 Starting Simple Context Management Tests")
    print("=" * 50)

    # Run tests
    test_context_management_simple()
    test_workflow_agent_integration()

    print("\n" + "=" * 50)
    print("🏁 All simple tests completed!")
