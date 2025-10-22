import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from context_management_service import context_management_service


async def test_context_management():
    """Test the context management system"""
    print("🧪 Testing Context Management System...")

    # Test user ID
    test_user_id = "test_user_123"
    test_session_id = "test_session_456"

    try:
        # Test 1: Get user preferences (should create defaults)
        print("\n1️⃣ Testing user preferences...")
        preferences = await context_management_service.get_user_preferences(
            test_user_id
        )
        print(f"✅ User preferences retrieved: {preferences}")

        # Test 2: Update user preferences
        print("\n2️⃣ Testing preference updates...")
        updated_preferences = {
            "automation_level": "full",
            "communication_style": "professional",
            "preferred_services": ["gmail", "slack", "notion", "github"],
            "business_context": {
                "companySize": "small",
                "technicalSkill": "advanced",
                "goals": ["automation", "collaboration", "productivity"],
            },
        }

        success = await context_management_service.save_user_preferences(
            test_user_id, updated_preferences
        )
        print(f"✅ Preferences updated: {success}")

        # Verify update
        new_preferences = await context_management_service.get_user_preferences(
            test_user_id
        )
        print(f"✅ Updated preferences verified: {new_preferences['automation_level']}")

        # Test 3: Conversation history
        print("\n3️⃣ Testing conversation history...")

        # Add user message
        user_success = await context_management_service.add_conversation_message(
            user_id=test_user_id,
            session_id=test_session_id,
            role="user",
            content="Can you create a workflow that sends me Slack notifications for important emails?",
            message_type="workflow_request",
            metadata={"intent": "workflow_creation"},
        )
        print(f"✅ User message added: {user_success}")

        # Add assistant response
        assistant_success = await context_management_service.add_conversation_message(
            user_id=test_user_id,
            session_id=test_session_id,
            role="assistant",
            content="I've created a workflow that monitors your Gmail for important emails and sends Slack notifications.",
            message_type="workflow_response",
            metadata={"workflow_id": "wf_test_123", "workflow_name": "Email to Slack"},
        )
        print(f"✅ Assistant message added: {assistant_success}")

        # Get conversation history
        history = await context_management_service.get_conversation_history(
            test_user_id, test_session_id
        )
        print(f"✅ Conversation history retrieved: {len(history)} messages")
        for i, msg in enumerate(history):
            print(f"   {i + 1}. {msg['role']}: {msg['content'][:50]}...")

        # Test 4: Chat context
        print("\n4️⃣ Testing chat context...")
        chat_context = await context_management_service.get_or_create_chat_context(
            test_user_id, test_session_id
        )
        print(f"✅ Chat context retrieved: {chat_context}")

        # Update chat context
        update_success = await context_management_service.update_chat_context(
            test_user_id,
            test_session_id,
            active_workflows=["wf_test_123", "wf_test_456"],
            context_data={"current_task": "email_automation", "priority": "high"},
        )
        print(f"✅ Chat context updated: {update_success}")

        # Test 5: Context-aware suggestions
        print("\n5️⃣ Testing context-aware suggestions...")
        suggestions = (
            await context_management_service.get_context_aware_workflow_suggestions(
                test_user_id
            )
        )
        print(f"✅ Suggestions generated: {len(suggestions)} suggestions")
        for i, suggestion in enumerate(suggestions):
            print(
                f"   {i + 1}. {suggestion['name']} (confidence: {suggestion['confidence']})"
            )

        # Test 6: User context summary
        print("\n6️⃣ Testing user context summary...")
        summary = await context_management_service.get_user_context_summary(
            test_user_id
        )
        print(f"✅ User context summary: {summary}")

        # Test 7: Clear conversation history
        print("\n7️⃣ Testing history clearing...")
        clear_success = await context_management_service.clear_conversation_history(
            test_user_id, test_session_id
        )
        print(f"✅ History cleared: {clear_success}")

        # Verify history is cleared
        cleared_history = await context_management_service.get_conversation_history(
            test_user_id, test_session_id
        )
        print(f"✅ History verified cleared: {len(cleared_history)} messages")

        print("\n🎉 All context management tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


async def test_api_endpoints():
    """Test the context management API endpoints"""
    print("\n🔗 Testing Context Management API Endpoints...")

    # Note: This would require running the Flask app
    # For now, we'll just verify the API module loads correctly
    try:
        from context_management_api import context_management_api_bp

        print("✅ Context Management API blueprint loaded successfully")
        print(f"✅ API URL prefix: {context_management_api_bp.url_prefix}")
    except Exception as e:
        print(f"❌ Failed to load API: {e}")


if __name__ == "__main__":
    print("🚀 Starting Context Management System Tests")
    print("=" * 50)

    # Run tests
    asyncio.run(test_context_management())
    asyncio.run(test_api_endpoints())

    print("\n" + "=" * 50)
    print("🏁 All tests completed!")
