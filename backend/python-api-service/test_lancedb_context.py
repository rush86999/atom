import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from lancedb_handler import (
    get_lancedb_connection,
    store_conversation_context,
    search_conversation_context,
    get_conversation_history,
    delete_conversation_context,
    create_generic_document_tables_if_not_exist,
)
from context_management_service import context_management_service


async def test_lancedb_conversation_storage():
    """Test storing conversation context in LanceDB"""
    print("🧪 Testing LanceDB Conversation Storage...")

    test_user_id = "lancedb_test_user"
    test_session_id = "lancedb_test_session"

    try:
        # Get LanceDB connection
        db_conn = await get_lancedb_connection()
        if not db_conn:
            print("❌ Failed to get LanceDB connection")
            return False

        # Ensure tables exist
        await create_generic_document_tables_if_not_exist(db_conn)

        # Test conversation data
        conversation_data = {
            "id": "test_conversation_1",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "role": "user",
            "content": "I need help creating a workflow for email automation",
            "message_type": "workflow_request",
            "timestamp": "2024-01-01T10:00:00Z",
            "metadata": {"intent": "workflow_creation", "topic": "email_automation"},
        }

        # Test embedding (simple vector for testing)
        test_embedding = [0.1] * 50  # 50-dimensional embedding

        # Store conversation
        storage_result = await store_conversation_context(
            db_conn, conversation_data, test_embedding
        )

        if storage_result.get("status") == "success":
            print("✅ Conversation stored successfully in LanceDB")
            print(f"   Conversation ID: {storage_result.get('conversation_id')}")
            return True
        else:
            print(f"❌ Failed to store conversation: {storage_result.get('message')}")
            return False

    except Exception as e:
        print(f"❌ Conversation storage test failed: {e}")
        return False


async def test_lancedb_conversation_search():
    """Test semantic search for conversations in LanceDB"""
    print("\n🔍 Testing LanceDB Conversation Search...")

    test_user_id = "lancedb_test_user"
    test_session_id = "lancedb_test_session"

    try:
        db_conn = await get_lancedb_connection()
        if not db_conn:
            print("❌ Failed to get LanceDB connection")
            return False

        # Test query embedding (similar to the stored conversation)
        query_embedding = [0.1] * 50

        # Search for similar conversations
        search_result = await search_conversation_context(
            db_conn=db_conn,
            query_embedding=query_embedding,
            user_id=test_user_id,
            session_id=test_session_id,
            limit=5,
            similarity_threshold=0.5,
        )

        if search_result.get("status") == "success":
            results = search_result.get("results", [])
            print(f"✅ Found {len(results)} similar conversations")

            for i, result in enumerate(results):
                print(
                    f"   {i + 1}. Similarity: {result.get('similarity_score', 0):.3f}"
                )
                print(f"      Content: {result.get('content', '')[:50]}...")
                print(f"      Role: {result.get('role')}")

            return len(results) > 0
        else:
            print(f"❌ Search failed: {search_result.get('message')}")
            return False

    except Exception as e:
        print(f"❌ Conversation search test failed: {e}")
        return False


async def test_lancedb_conversation_history():
    """Test retrieving conversation history from LanceDB"""
    print("\n📜 Testing LanceDB Conversation History...")

    test_user_id = "lancedb_test_user"
    test_session_id = "lancedb_test_session"

    try:
        db_conn = await get_lancedb_connection()
        if not db_conn:
            print("❌ Failed to get LanceDB connection")
            return False

        # Get conversation history
        history_result = await get_conversation_history(
            db_conn=db_conn, user_id=test_user_id, session_id=test_session_id, limit=10
        )

        if history_result.get("status") == "success":
            conversations = history_result.get("conversations", [])
            print(f"✅ Retrieved {len(conversations)} conversations from history")

            for i, conv in enumerate(conversations):
                print(
                    f"   {i + 1}. {conv.get('role')}: {conv.get('content', '')[:50]}..."
                )
                print(f"      Timestamp: {conv.get('timestamp')}")

            return True
        else:
            print(f"❌ History retrieval failed: {history_result.get('message')}")
            return False

    except Exception as e:
        print(f"❌ Conversation history test failed: {e}")
        return False


async def test_context_management_integration():
    """Test integration between context management and LanceDB"""
    print("\n🤝 Testing Context Management + LanceDB Integration...")

    test_user_id = "integration_test_user"
    test_session_id = "integration_test_session"

    try:
        # Test 1: Store conversation via context management
        print("1️⃣ Testing conversation storage via context management...")

        success = context_management_service.add_conversation_message_sync(
            user_id=test_user_id,
            session_id=test_session_id,
            role="user",
            content="I want to automate my email workflow with Gmail and Slack",
            message_type="workflow_request",
            metadata={"services": ["gmail", "slack"], "intent": "automation"},
        )

        if success:
            print("✅ Conversation stored via context management")
        else:
            print("❌ Failed to store conversation via context management")
            return False

        # Test 2: Search similar conversations
        print("2️⃣ Testing semantic conversation search...")

        similar_conversations = (
            context_management_service.search_similar_conversations_sync(
                user_id=test_user_id,
                query_text="email automation workflow",
                session_id=test_session_id,
                limit=3,
            )
        )

        print(f"✅ Found {len(similar_conversations)} similar conversations")

        # Test 3: Get contextual history
        print("3️⃣ Testing contextual conversation history...")

        contextual_history = (
            context_management_service.get_contextual_conversation_history_sync(
                user_id=test_user_id,
                current_message="I need help with email automation",
                session_id=test_session_id,
                semantic_limit=3,
                chronological_limit=5,
            )
        )

        print(f"✅ Retrieved {len(contextual_history)} contextual conversations")

        return True

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


async def test_cleanup():
    """Clean up test data from LanceDB"""
    print("\n🧹 Cleaning up test data...")

    test_user_id = "lancedb_test_user"

    try:
        db_conn = await get_lancedb_connection()
        if not db_conn:
            print("❌ Failed to get LanceDB connection for cleanup")
            return False

        # Delete test conversations
        delete_result = await delete_conversation_context(
            db_conn=db_conn, user_id=test_user_id
        )

        if delete_result.get("status") == "success":
            print("✅ Test data cleaned up successfully")
            return True
        else:
            print(f"❌ Cleanup failed: {delete_result.get('message')}")
            return False

    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False


async def run_all_tests():
    """Run all LanceDB context management tests"""
    print("🚀 Starting LanceDB Context Management Tests")
    print("=" * 60)

    test_results = []

    # Run tests
    test_results.append(await test_lancedb_conversation_storage())
    test_results.append(await test_lancedb_conversation_search())
    test_results.append(await test_lancedb_conversation_history())
    test_results.append(await test_context_management_integration())

    # Cleanup
    await test_cleanup()

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    passed_tests = sum(test_results)
    total_tests = len(test_results)

    print(f"✅ Passed: {passed_tests}/{total_tests}")
    print(f"❌ Failed: {total_tests - passed_tests}/{total_tests}")

    if passed_tests == total_tests:
        print("🎉 All LanceDB context management tests passed!")
        return True
    else:
        print("💥 Some tests failed. Check the logs above.")
        return False


if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_all_tests())

    if success:
        print("\n🏁 LanceDB Context Management System is working correctly!")
    else:
        print("\n💥 LanceDB Context Management System needs attention!")
        sys.exit(1)
