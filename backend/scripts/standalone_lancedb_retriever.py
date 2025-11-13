#!/usr/bin/env python3
"""
Standalone LanceDB Conversation Retriever

This script provides a standalone solution for retrieving conversations from LanceDB
without requiring the full Atom backend infrastructure.

Features:
- Direct LanceDB connection and querying
- Retrieve conversation history for users
- Search conversations using semantic similarity
- Export conversation data in various formats
- Simple command-line interface
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import lancedb
    import numpy as np
    import pyarrow as pa

    LANCEDB_AVAILABLE = True
except ImportError as e:
    print(f"❌ Required dependencies not available: {e}")
    print("Please install: pip install lancedb pyarrow numpy")
    LANCEDB_AVAILABLE = False


class StandaloneLanceDBRetriever:
    """Standalone class for retrieving conversations from LanceDB"""

    def __init__(self, db_path: str = "data/lancedb"):
        self.db_path = db_path
        self.db = None
        self.conversations_table = None

    async def initialize(self) -> bool:
        """Initialize LanceDB connection and load conversations table"""
        if not LANCEDB_AVAILABLE:
            print("❌ LanceDB dependencies not available")
            return False

        try:
            # Create database directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            # Connect to LanceDB
            self.db = lancedb.connect(self.db_path)
            print(f"✅ Connected to LanceDB at: {self.db_path}")

            # Try to open conversations table
            try:
                self.conversations_table = self.db.open_table("conversations")
                print("✅ Conversations table loaded successfully")
                return True
            except Exception as e:
                print(f"⚠️  Conversations table not found: {e}")
                print("   This is normal if no conversations have been stored yet")
                return False

        except Exception as e:
            print(f"❌ Failed to initialize LanceDB: {e}")
            return False

    def get_conversation_history(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get conversation history for a specific user"""
        if not self.conversations_table:
            return {"status": "error", "message": "Conversations table not available"}

        try:
            # Build filter condition
            filter_condition = f"user_id = '{user_id}'"
            if session_id:
                filter_condition += f" AND session_id = '{session_id}'"

            # Query the table
            query = self.conversations_table.search().where(filter_condition)
            results = query.limit(limit + offset).to_list()

            # Sort by timestamp and apply offset
            results.sort(key=lambda x: x.get("timestamp", ""))
            paginated_results = results[offset : offset + limit]

            # Process results
            conversations = []
            for result in paginated_results:
                conversations.append(
                    {
                        "id": result.get("id", ""),
                        "user_id": result.get("user_id", ""),
                        "session_id": result.get("session_id", ""),
                        "role": result.get("role", "user"),
                        "content": result.get("content", ""),
                        "message_type": result.get("message_type", "text"),
                        "timestamp": result.get("timestamp", ""),
                        "metadata": self._parse_metadata(result.get("metadata", "{}")),
                    }
                )

            return {
                "status": "success",
                "conversations": conversations,
                "count": len(conversations),
                "total_count": len(results),
                "has_more": len(results) > offset + limit,
            }

        except Exception as e:
            return {"status": "error", "message": f"Failed to get conversations: {e}"}

    def search_conversations(
        self,
        query_text: str,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """Search conversations using semantic similarity"""
        if not self.conversations_table:
            return {"status": "error", "message": "Conversations table not available"}

        try:
            # Build filter condition
            filter_condition = f"user_id = '{user_id}'"
            if session_id:
                filter_condition += f" AND session_id = '{session_id}'"

            # Create a simple embedding for the query
            # Note: In production, this would use a proper embedding model
            query_embedding = self._generate_simple_embedding(query_text)

            # Perform semantic search
            results = (
                self.conversations_table.search(query_embedding)
                .where(filter_condition)
                .limit(limit * 2)  # Get more results for filtering
                .to_list()
            )

            # Filter by similarity threshold and process results
            filtered_results = []
            for result in results:
                similarity_score = 1.0 - result.get("_distance", 1.0)

                if similarity_score >= similarity_threshold:
                    filtered_results.append(
                        {
                            "id": result.get("id", ""),
                            "user_id": result.get("user_id", ""),
                            "session_id": result.get("session_id", ""),
                            "role": result.get("role", "user"),
                            "content": result.get("content", ""),
                            "message_type": result.get("message_type", "text"),
                            "timestamp": result.get("timestamp", ""),
                            "metadata": self._parse_metadata(
                                result.get("metadata", "{}")
                            ),
                            "similarity_score": similarity_score,
                        }
                    )

            # Sort by similarity score (highest first)
            filtered_results.sort(key=lambda x: x["similarity_score"], reverse=True)
            filtered_results = filtered_results[:limit]  # Apply final limit

            return {
                "status": "success",
                "results": filtered_results,
                "count": len(filtered_results),
                "query": query_text,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to search conversations: {e}",
            }

    def get_conversation_stats(self, user_id: str) -> Dict[str, Any]:
        """Get conversation statistics for a user"""
        if not self.conversations_table:
            return {"status": "error", "message": "Conversations table not available"}

        try:
            # Get all conversations for the user
            result = self.get_conversation_history(user_id, limit=1000)

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
                            "content_preview": (
                                conv.get("content", "")[:100] + "..."
                                if len(conv.get("content", "")) > 100
                                else conv.get("content", "")
                            ),
                        }
                    )

            return {"status": "success", "stats": stats}

        except Exception as e:
            return {"status": "error", "message": f"Failed to get stats: {e}"}

    def list_available_users(self) -> Dict[str, Any]:
        """List all users with conversations in the database"""
        if not self.conversations_table:
            return {"status": "error", "message": "Conversations table not available"}

        try:
            # Get all records to extract unique user IDs
            results = self.conversations_table.search().limit(1000).to_list()

            user_ids = set()
            for result in results:
                user_id = result.get("user_id")
                if user_id:
                    user_ids.add(user_id)

            users_list = list(user_ids)

            return {"status": "success", "users": users_list, "count": len(users_list)}

        except Exception as e:
            return {"status": "error", "message": f"Failed to list users: {e}"}

    def _generate_simple_embedding(self, text: str) -> List[float]:
        """Generate a simple embedding for search queries"""
        # This is a placeholder implementation
        # In production, you would use a proper embedding model
        # For now, we create a simple hash-based embedding
        import hashlib

        # Create a deterministic embedding based on text hash
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()

        # Convert to 384-dimensional vector (standard embedding size)
        embedding = []
        for i in range(384):
            # Use different parts of the hash to fill the vector
            byte_idx = i % len(hash_bytes)
            embedding.append(float(hash_bytes[byte_idx]) / 255.0)

        return embedding

    def _parse_metadata(self, metadata_str: str) -> Dict:
        """Parse metadata string to dictionary"""
        try:
            if isinstance(metadata_str, str):
                return json.loads(metadata_str)
            elif isinstance(metadata_str, dict):
                return metadata_str
            else:
                return {}
        except:
            return {}


async def test_connection(retriever: StandaloneLanceDBRetriever):
    """Test LanceDB connection"""
    print("🧪 Testing LanceDB Connection...")

    connected = await retriever.initialize()
    if connected:
        print("✅ LanceDB connection successful")

        # List available users
        users_result = retriever.list_available_users()
        if users_result.get("status") == "success":
            users = users_result.get("users", [])
            print(f"📊 Found {len(users)} users with conversations:")
            for user in users[:5]:  # Show first 5 users
                print(f"   - {user}")
            if len(users) > 5:
                print(f"   ... and {len(users) - 5} more")
        else:
            print(
                "ℹ️  No conversations found in database (this is normal for new installations)"
            )
    else:
        print("❌ LanceDB connection failed")


async def retrieve_user_conversations(
    retriever: StandaloneLanceDBRetriever, user_id: str, limit: int = 20
):
    """Retrieve and display conversations for a specific user"""
    print(f"📝 Retrieving conversations for user: {user_id}")

    await retriever.initialize()

    result = retriever.get_conversation_history(user_id, limit=limit)

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


async def search_user_conversations(
    retriever: StandaloneLanceDBRetriever, user_id: str, query: str, limit: int = 10
):
    """Search conversations for a specific user"""
    print(f"🔍 Searching conversations for user '{user_id}': '{query}'")

    await retriever.initialize()

    result = retriever.search_conversations(query, user_id, limit=limit)

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


async def export_conversations(
    retriever: StandaloneLanceDBRetriever, user_id: str, output_file: str
):
    """Export conversations to JSON file"""
    print(f"💾 Exporting conversations for user '{user_id}' to {output_file}")

    await retriever.initialize()

    # Get all conversations (with large limit)
    result = retriever.get_conversation_history(user_id, limit=1000)

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


async def get_user_stats(retriever: StandaloneLanceDBRetriever, user_id: str):
    """Get conversation statistics for a user"""
    print(f"📊 Getting conversation statistics for user: {user_id}")

    await retriever.initialize()

    result = retriever.get_conversation_stats(user_id)

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


async def list_users(retriever: StandaloneLanceDBRetriever):
    """List all users with conversations"""
    print("👥 Listing all users with conversations...")

    await retriever.initialize()

    result = retriever.list_available_users()

    if result.get("status") == "success":
        users = result.get("users", [])

        print(f"📊 Found {len(users)} users with conversations:")
        for i, user in enumerate(users, 1):
            # Get stats for each user
            stats_result = retriever.get_conversation_stats(user)
            if stats_result.get("status") == "success":
                stats = stats_result.get("stats", {})
                count = stats.get("total_conversations", 0)
                print(f"   {i}. {user} ({count} conversations)")
            else:
                print(f"   {i}. {user}")

    else:
        print(f"❌ Failed to list users: {result.get('message')}")


def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(
        description="Standalone LanceDB Conversation Retriever"
    )
    parser.add_argument(
        "--db-path", default="data/lancedb", help="Path to LanceDB database directory"
    )
    parser.add_argument(
        "--user-id",
        help="User ID to retrieve conversations for (required for most actions)",
    )
    parser.add_argument(
        "--action",
        choices=["test", "retrieve", "search", "export", "stats", "list-users"],
        default="test",
        help="Action to perform",
    )
    parser.add_argument("--query", help="Search query (for search action)")
    parser.add_argument(
        "--limit", type=int, default=20, help="Number of conversations to retrieve"
    )
    parser.add_argument("--output", help="Output file for export")

    args = parser.parse_args()

    if not LANCEDB_AVAILABLE:
        print("❌ LanceDB dependencies not available")
        print("Please install: pip install lancedb pyarrow numpy")
        sys.exit(1)

    # Validate arguments
    if args.action in ["retrieve", "search", "export", "stats"] and not args.user_id:
        print("❌ Please provide --user-id for this action")
        sys.exit(1)

    if args.action == "search" and not args.query:
        print("❌ Please provide --query for search action")
        sys.exit(1)

    # Create retriever instance
    retriever = StandaloneLanceDBRetriever(db_path=args.db_path)

    async def run_actions():
        # Perform the requested action
        if args.action == "test":
            await test_connection(retriever)
        elif args.action == "retrieve":
            await retrieve_user_conversations(retriever, args.user_id, args.limit)
        elif args.action == "search":
            await search_user_conversations(
                retriever, args.user_id, args.query, args.limit
            )
        elif args.action == "export":
            output_file = (
                args.output
                or f"conversations_{args.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            await export_conversations(retriever, args.user_id, output_file)
        elif args.action == "stats":
            await get_user_stats(retriever, args.user_id)
        elif args.action == "list-users":
            await list_users(retriever)

    # Run async operations
    asyncio.run(run_actions())


if __name__ == "__main__":
    main()
