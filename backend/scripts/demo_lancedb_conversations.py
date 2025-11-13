#!/usr/bin/env python3
"""
LanceDB Conversation Storage and Retrieval Demo

This script demonstrates how to store and retrieve conversations from LanceDB
using the existing Atom memory system integration.

Features:
- Store sample conversations in LanceDB
- Retrieve conversation history for users
- Search conversations using semantic similarity
- Export conversation data
- Test the complete workflow
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

try:
    from backend.python_api_service.lancedb_handler import (
        create_generic_document_tables_if_not_exist,
        get_conversation_history,
        get_lancedb_connection,
        search_conversation_context,
        store_conversation_context,
    )

    LANCEDB_AVAILABLE = True
except ImportError as e:
    print(f"❌ LanceDB modules not available: {e}")
    LANCEDB_AVAILABLE = False


class LanceDBDemo:
    """Demo class for LanceDB conversation storage and retrieval"""

    def __init__(self, db_path: str = "data/lancedb"):
        self.db_path = db_path
        self.db_connection = None

    async def initialize(self):
        """Initialize LanceDB connection"""
        if not LANCEDB_AVAILABLE:
            print("❌ LanceDB modules not available")
            return False

        try:
            # Create database directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            self.db_connection = await get_lancedb_connection(self.db_path)
            await create_generic_document_tables_if_not_exist(self.db_connection)
            print(f"✅ LanceDB initialized at: {self.db_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize LanceDB: {e}")
            return False

    async def store_sample_conversations(self):
        """Store sample conversations for demonstration"""
        print("📝 Storing sample conversations...")

        sample_conversations = [
            {
                "user_id": "demo-user-001",
                "session_id": "session-001",
                "role": "user",
                "content": "Hello, I need help with my account settings.",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc),
                "metadata": {"topic": "account", "priority": "medium"},
            },
            {
                "user_id": "demo-user-001",
                "session_id": "session-001",
                "role": "assistant",
                "content": "I'd be happy to help you with your account settings. What specific issue are you experiencing?",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc),
                "metadata": {"topic": "account", "response_type": "helpful"},
            },
            {
                "user_id": "demo-user-001",
                "session_id": "session-001",
                "role": "user",
                "content": "I can't change my password. The system says it's too weak.",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc),
                "metadata": {"topic": "password", "issue": "validation"},
            },
            {
                "user_id": "demo-user-001",
                "session_id": "session-001",
                "role": "assistant",
                "content": "For password security, please use at least 8 characters with a mix of uppercase, lowercase, numbers, and symbols.",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc),
                "metadata": {"topic": "password", "advice": "security"},
            },
            {
                "user_id": "demo-user-002",
                "session_id": "session-002",
                "role": "user",
                "content": "How do I integrate the API with my application?",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc),
                "metadata": {"topic": "api", "integration": "technical"},
            },
            {
                "user_id": "demo-user-002",
                "session_id": "session-002",
                "role": "assistant",
                "content": "You can integrate our API by following the documentation at docs.example.com. Would you like me to help with a specific integration scenario?",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc),
                "metadata": {"topic": "api", "resources": "documentation"},
            },
            {
                "user_id": "demo-user-003",
                "session_id": "session-003",
                "role": "user",
                "content": "I'm having trouble with billing and payments.",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc),
                "metadata": {"topic": "billing", "category": "financial"},
            },
        ]

        stored_count = 0
        for conversation in sample_conversations:
            # Generate a simple embedding for demonstration
            # In production, this would use a proper embedding model
            embedding = self._generate_simple_embedding(conversation["content"])

            result = await store_conversation_context(
                self.db_connection, conversation, embedding
            )

            if result.get("status") == "success":
                stored_count += 1
                print(f"   ✅ Stored: {conversation['content'][:50]}...")
            else:
                print(f"   ❌ Failed to store: {result.get('message')}")

        print(
            f"📊 Successfully stored {stored_count}/{len(sample_conversations)} conversations"
        )
        return stored_count

    async def retrieve_user_conversations(self, user_id: str, limit: int = 10):
        """Retrieve and display conversations for a user"""
        print(f"📝 Retrieving conversations for user: {user_id}")

        result = await get_conversation_history(
            self.db_connection, user_id, limit=limit
        )

        if result.get("status") == "success":
            conversations = result.get("conversations", [])
            total_count = result.get("total_count", 0)

            print(f"📊 Found {len(conversations)} conversations (total: {total_count})")
            print("-" * 80)

            for i, conv in enumerate(conversations, 1):
                timestamp = conv.get("timestamp", "Unknown")
                role = conv.get("role", "unknown").upper()
                content = conv.get("content", "")
                session_id = conv.get("session_id", "N/A")

                print(f"{i}. [{timestamp}] {role} (Session: {session_id})")
                print(f"   {content}")
                print()

        else:
            print(f"❌ Failed to retrieve conversations: {result.get('message')}")

    async def search_conversations(self, query: str, user_id: str, limit: int = 5):
        """Search conversations using semantic similarity"""
        print(f"🔍 Searching conversations for '{user_id}': '{query}'")

        # Generate embedding for search query
        query_embedding = self._generate_simple_embedding(query)

        result = await search_conversation_context(
            self.db_connection, query_embedding, user_id, limit=limit
        )

        if result.get("status") == "success":
            results = result.get("results", [])

            print(f"📊 Found {len(results)} relevant conversations")
            print("-" * 80)

            for i, res in enumerate(results, 1):
                timestamp = res.get("timestamp", "Unknown")
                role = res.get("role", "unknown").upper()
                content = res.get("content", "")
                similarity = res.get("similarity_score", 0)
                session_id = res.get("session_id", "N/A")

                print(f"{i}. [{timestamp}] {role} (Session: {session_id})")
                print(f"   Similarity: {similarity:.3f}")
                print(f"   {content}")
                print()

        else:
            print(f"❌ Failed to search conversations: {result.get('message')}")

    async def export_conversations(self, user_id: str, output_file: str):
        """Export conversations to JSON file"""
        print(f"💾 Exporting conversations for '{user_id}' to {output_file}")

        # Get all conversations
        result = await get_conversation_history(self.db_connection, user_id, limit=100)

        if result.get("status") == "success":
            conversations = result.get("conversations", [])

            # Prepare export data
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "total_conversations": len(conversations),
                "conversations": conversations,
            }

            # Write to file
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            print(
                f"✅ Successfully exported {len(conversations)} conversations to {output_file}"
            )

        else:
            print(f"❌ Failed to export conversations: {result.get('message')}")

    async def list_all_users(self):
        """List all users with conversations in the database"""
        print("👥 Listing all users with conversations...")

        # We'll get conversations for a large limit and extract unique user IDs
        # This is a simplified approach - in production you'd have a proper user table
        test_user_ids = ["demo-user-001", "demo-user-002", "demo-user-003"]

        users_with_conversations = []
        for user_id in test_user_ids:
            result = await get_conversation_history(
                self.db_connection, user_id, limit=1
            )
            if result.get("status") == "success" and result.get("conversations"):
                users_with_conversations.append(user_id)

        if users_with_conversations:
            print(f"📊 Found {len(users_with_conversations)} users with conversations:")
            for user in users_with_conversations:
                # Get conversation count for each user
                count_result = await get_conversation_history(
                    self.db_connection, user, limit=100
                )
                count = len(count_result.get("conversations", []))
                print(f"   - {user} ({count} conversations)")
        else:
            print("ℹ️  No users with conversations found")

    def _generate_simple_embedding(self, text: str) -> List[float]:
        """Generate a simple embedding for demonstration"""
        # This is a simplified embedding generation for demo purposes
        # In production, you would use a proper embedding model
        import hashlib

        # Create deterministic embedding based on text hash
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()

        # Convert to 384-dimensional vector (standard embedding size)
        embedding = []
        for i in range(384):
            byte_idx = i % len(hash_bytes)
            embedding.append(float(hash_bytes[byte_idx]) / 255.0)

        return embedding


async def run_demo():
    """Run the complete LanceDB conversation demo"""
    print("🚀 Starting LanceDB Conversation Storage and Retrieval Demo")
    print("=" * 60)

    # Initialize demo
    demo = LanceDBDemo()

    if not await demo.initialize():
        print("❌ Demo initialization failed")
        return

    print("\n1. 📝 STORING SAMPLE CONVERSATIONS")
    print("-" * 40)
    await demo.store_sample_conversations()

    print("\n2. 📖 RETRIEVING CONVERSATION HISTORY")
    print("-" * 40)
    await demo.retrieve_user_conversations("demo-user-001", limit=5)
    await demo.retrieve_user_conversations("demo-user-002", limit=3)

    print("\n3. 🔍 SEMANTIC SEARCH DEMONSTRATION")
    print("-" * 40)
    await demo.search_conversations("account settings", "demo-user-001")
    await demo.search_conversations("API integration", "demo-user-002")

    print("\n4. 💾 EXPORTING CONVERSATIONS")
    print("-" * 40)
    export_file = f"demo_conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    await demo.export_conversations("demo-user-001", export_file)

    print("\n5. 👥 USER MANAGEMENT")
    print("-" * 40)
    await demo.list_all_users()

    print("\n" + "=" * 60)
    print("🎉 Demo completed successfully!")
    print(f"💾 Conversations exported to: {export_file}")
    print("\n📚 Next steps:")
    print("   - Use the standalone_lancedb_retriever.py for ongoing retrieval")
    print("   - Integrate with the chat interface for real-time memory")
    print("   - Explore advanced semantic search with proper embedding models")


if __name__ == "__main__":
    if not LANCEDB_AVAILABLE:
        print("❌ LanceDB dependencies not available")
        print("Please ensure:")
        print("   - LanceDB is installed: pip install lancedb")
        print("   - The backend modules are accessible")
        sys.exit(1)

    asyncio.run(run_demo())
