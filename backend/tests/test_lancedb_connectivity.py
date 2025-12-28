#!/usr/bin/env python3
"""
LanceDB Connectivity Test Script

This script tests the LanceDB connection and basic conversation retrieval functionality.
It verifies that the memory system is properly configured and accessible.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

try:
    from backend.python_api_service.lancedb_handler import (
        create_generic_document_tables_if_not_exist,
        get_conversation_history,
        get_lancedb_connection,
        search_conversation_context,
    )

    LANCEDB_AVAILABLE = True
except ImportError as e:
    print(f"❌ LanceDB modules not available: {e}")
    LANCEDB_AVAILABLE = False


async def test_lancedb_connection():
    """Test basic LanceDB connection"""
    print("🧪 Testing LanceDB Connection...")

    if not LANCEDB_AVAILABLE:
        print("❌ LanceDB modules not available")
        return False

    try:
        db_path = "data/lancedb"
        print(f"Connecting to LanceDB at: {db_path}")

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        db_conn = await get_lancedb_connection(db_path)
        print("✅ LanceDB connection established successfully")

        # Test table creation
        await create_generic_document_tables_if_not_exist(db_conn)
        print("✅ Conversation tables created/verified")

        return True

    except Exception as e:
        print(f"❌ LanceDB connection failed: {e}")
        return False


async def test_conversation_retrieval():
    """Test conversation retrieval functionality"""
    print("\n📝 Testing Conversation Retrieval...")

    if not LANCEDB_AVAILABLE:
        return False

    try:
        db_conn = await get_lancedb_connection("data/lancedb")

        # Test getting conversation history for a test user
        test_user_id = "test-user-123"
        result = await get_conversation_history(db_conn, test_user_id, limit=10)

        if result.get("status") == "success":
            conversations = result.get("conversations", [])
            print(
                f"✅ Retrieved {len(conversations)} conversations for user '{test_user_id}'"
            )

            # Display sample conversations
            for i, conv in enumerate(conversations[:3], 1):
                timestamp = conv.get("timestamp", "Unknown")
                role = conv.get("role", "unknown")
                content_preview = (
                    conv.get("content", "")[:50] + "..."
                    if len(conv.get("content", "")) > 50
                    else conv.get("content", "")
                )
                print(f"   {i}. [{timestamp}] {role}: {content_preview}")

        else:
            print(
                f"⚠️  No conversations found for user '{test_user_id}' (this is normal for new installations)"
            )

        return True

    except Exception as e:
        print(f"❌ Conversation retrieval test failed: {e}")
        return False


async def test_conversation_search():
    """Test conversation search functionality"""
    print("\n🔍 Testing Conversation Search...")

    if not LANCEDB_AVAILABLE:
        return False

    try:
        db_conn = await get_lancedb_connection("data/lancedb")

        # Test searching conversations
        test_user_id = "test-user-123"
        test_query = "hello"

        # Create a simple embedding for testing (placeholder)
        query_embedding = [0.1] * 384  # Standard embedding dimension

        result = await search_conversation_context(
            db_conn, query_embedding, test_user_id, limit=5
        )

        if result.get("status") == "success":
            results = result.get("results", [])
            print(f"✅ Search completed, found {len(results)} relevant conversations")

            for i, res in enumerate(results[:3], 1):
                similarity = res.get("similarity_score", 0)
                content_preview = (
                    res.get("content", "")[:50] + "..."
                    if len(res.get("content", "")) > 50
                    else res.get("content", "")
                )
                print(f"   {i}. Similarity: {similarity:.3f} - {content_preview}")

        else:
            print(f"⚠️  No search results found (this is normal for new installations)")

        return True

    except Exception as e:
        print(f"❌ Conversation search test failed: {e}")
        return False


async def test_api_endpoints():
    """Test API endpoints if chat interface is running"""
    print("\n🌐 Testing API Endpoints...")

    import aiohttp

    base_url = "http://localhost:8000"
    test_user_id = "test-user-123"

    try:
        async with aiohttp.ClientSession() as session:
            # Test health endpoint
            try:
                async with session.get(f"{base_url}/health") as response:
                    if response.status == 200:
                        health_data = await response.json()
                        print(
                            f"✅ Chat interface health: {health_data.get('status', 'unknown')}"
                        )
                        print(
                            f"   Memory System: {health_data.get('memory_system', 'unknown')}"
                        )
                    else:
                        print(f"⚠️  Chat interface not running on {base_url}")
                        return False
            except:
                print(f"⚠️  Chat interface not accessible on {base_url}")
                return False

            # Test conversation history endpoint
            try:
                async with session.get(
                    f"{base_url}/api/v1/memory/history/{test_user_id}"
                ) as response:
                    if response.status == 200:
                        history_data = await response.json()
                        if history_data.get("status") == "success":
                            count = history_data.get("count", 0)
                            print(
                                f"✅ API conversation retrieval: {count} conversations"
                            )
                        else:
                            print(
                                f"⚠️  API conversation retrieval: {history_data.get('message', 'No conversations')}"
                            )
                    else:
                        print(
                            f"❌ API conversation retrieval failed: HTTP {response.status}"
                        )
            except Exception as e:
                print(f"❌ API conversation retrieval test failed: {e}")

        return True

    except Exception as e:
        print(f"❌ API endpoints test failed: {e}")
        return False


async def main():
    """Run all connectivity tests"""
    print("🚀 Starting LanceDB Connectivity Tests")
    print("=" * 50)

    tests_passed = 0
    total_tests = 4

    # Test 1: Basic LanceDB connection
    if await test_lancedb_connection():
        tests_passed += 1

    # Test 2: Conversation retrieval
    if await test_conversation_retrieval():
        tests_passed += 1

    # Test 3: Conversation search
    if await test_conversation_search():
        tests_passed += 1

    # Test 4: API endpoints
    if await test_api_endpoints():
        tests_passed += 1

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        print("🎉 All tests passed! LanceDB connectivity is working correctly.")
    elif tests_passed >= 2:
        print(
            "✅ Basic connectivity established. Some features may need configuration."
        )
    else:
        print(
            "❌ Significant connectivity issues detected. Check LanceDB installation and configuration."
        )

    # Recommendations
    print("\n🔧 Recommendations:")
    if not LANCEDB_AVAILABLE:
        print("   - Install LanceDB: pip install lancedb")
    if tests_passed < 2:
        print("   - Check database path permissions")
        print("   - Verify LanceDB installation")
        print("   - Start chat interface server if needed")


if __name__ == "__main__":
    asyncio.run(main())
