#!/usr/bin/env python3
"""
LanceDB Conversation Retrieval Script

This script demonstrates how to retrieve conversations from LanceDB
using the existing memory system integration in Atom.

Features:
- Retrieve conversation history for specific users
- Search conversations using semantic similarity
- Export conversation data in various formats
- Test LanceDB connectivity and health
"""

import argparse
import asyncio
from datetime import datetime
import json
import os
import sys
from typing import Dict, List, Optional

# Add backend to path to import the necessary modules
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

try:
    from backend.python_api_service.lancedb_handler import (
        get_conversation_history,
        get_lancedb_connection,
        search_conversation_context,
        store_conversation_context,
    )

    LANCEDB_AVAILABLE = True
except ImportError as e:
    print(f"Warning: LanceDB modules not available: {e}")
    LANCEDB_AVAILABLE = False


class LanceDBConversationRetriever:
    """Class to handle conversation retrieval from LanceDB"""

    def __init__(self, db_path: str = "data/lancedb"):
        self.db_path = db_path
        self.db_connection = None

    async def initialize(self):
        """Initialize LanceDB connection"""
        if not LANCEDB_AVAILABLE:
            print("LanceDB is not available. Please check the installation.")
            return False

        try:
            self.db_connection = await get_lancedb_connection(self.db_path)
            print(f"✅ Successfully connected to LanceDB at {self.db_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to LanceDB: {e}")
            return False

    async def get_user_conversations(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict:
        """Get conversation history for a specific user"""
        if not self.db_connection:
            return {"status": "error", "message": "LanceDB not connected"}

        try:
            result = await get_conversation_history(
                self.db_connection, user_id, session_id, limit, offset
            )
            return result
        except Exception as e:
            return {"status": "error", "message": f"Failed to get conversations: {e}"}

    async def search_conversations(
        self,
        query_text: str,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 10,
    ) -> Dict:
        """Search conversations using semantic similarity"""
        if not self.db_connection:
            return {"status": "error", "message": "LanceDB not connected"}

        try:
            # Generate a simple embedding for the query (placeholder)
            # In production, this would use a proper embedding model
            query_embedding = [0.1] * 384  # Standard embedding dimension

            result = await search_conversation_context(
                self.db_connection, query_embedding, user_id, session_id, limit
            )
            return result
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to search conversations: {e}",
            }

    async def get_conversation_stats(self, user_id: str) -> Dict:
        """Get conversation statistics for a user"""
        if not self.db_connection:
            return {"status": "error", "message": "LanceDB not connected"}

        try:
            # Get all conversations for the user
            result = await get_conversation_history(
                self.db_connection, user_id, limit=1000
            )

            if result.get("status") != "success":
                return result

            conversations = result.get("conversations", [])

            # Calculate statistics
            stats = {
                "total_conversations": len(conversations),
                "user_id": user_id,
                "first_conversation": None,
                "last_conversation": None,
                "message_counts": {"user": 0, "assistant": 0, "system": 0},
                "timeline": [],
            }

            if conversations:
                # Sort by timestamp
                sorted_conv = sorted(
                    conversations, key=lambda x: x.get("timestamp", "")
                )
                stats["first_conversation"] = sorted_conv[0].get("timestamp")
                stats["last_conversation"] = sorted_conv[-1].get("timestamp")

                # Count messages by role
                for conv in conversations:
                    role = conv.get("role", "user")
                    stats["message_counts"][role] = (
                        stats["message_counts"].get(role, 0) + 1
                    )

                    # Add to timeline
                    stats["timeline"].append(
                        {
                            "timestamp": conv.get("timestamp"),
                            "role": role,
                            "content_preview": conv.get("content", "")[:100] + "..."
                            if len(conv.get("content", "")) > 100
                            else conv.get("content", ""),
                        }
                    )

            return {"status": "success", "stats": stats}

        except Exception as e:
            return {"status": "error", "message": f"Failed to get stats: {e}"}


async def test_lancedb_connection():
    """Test LanceDB connection and basic functionality"""
    print("🧪 Testing LanceDB Connection...")

    retriever = LanceDBConversationRetriever()
    connected = await retriever.initialize()

    if not connected:
        print("❌ LanceDB connection test failed")
        return False

    print("✅ LanceDB connection test passed")
    return True


async def retrieve_user_conversations(user_id: str, limit: int = 20):
    """Retrieve and display conversations for a specific user"""
    print(f"📝 Retrieving conversations for user: {user_id}")

    retriever = LanceDBConversationRetriever()
    await retriever.initialize()

    # Get conversation history
    result = await retriever.get_user_conversations(user_id, limit=limit)

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
            print(f"   {content[:200]}{'...' if len(content) > 200 else ''}")
            print()

    else:
        print(f"❌ Failed to retrieve conversations: {result.get('message')}")


async def search_user_conversations(user_id: str, query: str, limit: int = 10):
    """Search conversations for a specific user"""
    print(f"🔍 Searching conversations for user '{user_id}': '{query}'")

    retriever = LanceDBConversationRetriever()
    await retriever.initialize()

    # Search conversations
    result = await retriever.search_conversations(query, user_id, limit=limit)

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
            print(f"   {content[:200]}{'...' if len(content) > 200 else ''}")
            print()

    else:
        print(f"❌ Failed to search conversations: {result.get('message')}")


async def export_conversations(user_id: str, output_file: str):
    """Export conversations to JSON file"""
    print(f"💾 Exporting conversations for user '{user_id}' to {output_file}")

    retriever = LanceDBConversationRetriever()
    await retriever.initialize()

    # Get all conversations (with large limit)
    result = await retriever.get_user_conversations(user_id, limit=1000)

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


async def get_user_stats(user_id: str):
    """Get conversation statistics for a user"""
    print(f"📊 Getting conversation statistics for user: {user_id}")

    retriever = LanceDBConversationRetriever()
    await retriever.initialize()

    result = await retriever.get_conversation_stats(user_id)

    if result.get("status") == "success":
        stats = result.get("stats", {})

        print(f"📈 Conversation Statistics for {user_id}:")
        print(f"   Total Conversations: {stats.get('total_conversations', 0)}")
        print(f"   First Conversation: {stats.get('first_conversation', 'N/A')}")
        print(f"   Last Conversation: {stats.get('last_conversation', 'N/A')}")
        print(f"   Message Counts:")
        for role, count in stats.get("message_counts", {}).items():
            print(f"     - {role.capitalize()}: {count}")

    else:
        print(f"❌ Failed to get statistics: {result.get('message')}")


def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description="Retrieve conversations from LanceDB")
    parser.add_argument(
        "--user-id", required=True, help="User ID to retrieve conversations for"
    )
    parser.add_argument(
        "--action",
        choices=["retrieve", "search", "export", "stats", "test"],
        default="retrieve",
        help="Action to perform",
    )
    parser.add_argument("--query", help="Search query (for search action)")
    parser.add_argument(
        "--limit", type=int, default=20, help="Number of conversations to retrieve"
    )
    parser.add_argument("--output", help="Output file for export")

    args = parser.parse_args()

    if not LANCEDB_AVAILABLE:
        print("❌ LanceDB is not available. Please ensure:")
        print("   - LanceDB is installed: pip install lancedb")
        print("   - The backend modules are accessible")
        sys.exit(1)

    # Perform the requested action
    if args.action == "test":
        asyncio.run(test_lancedb_connection())
    elif args.action == "retrieve":
        asyncio.run(retrieve_user_conversations(args.user_id, args.limit))
    elif args.action == "search":
        if not args.query:
            print("❌ Please provide a search query with --query")
            sys.exit(1)
        asyncio.run(search_user_conversations(args.user_id, args.query, args.limit))
    elif args.action == "export":
        output_file = (
            args.output
            or f"conversations_{args.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        asyncio.run(export_conversations(args.user_id, output_file))
    elif args.action == "stats":
        asyncio.run(get_user_stats(args.user_id))


if __name__ == "__main__":
    main()
