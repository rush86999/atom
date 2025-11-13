#!/usr/bin/env python3
"""
Simple LanceDB Conversation Storage and Retrieval Demo

This script demonstrates how to store and retrieve conversations from LanceDB
without requiring the full Atom backend infrastructure.

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
from typing import Any, Dict, List, Optional

try:
    import lancedb
    import numpy as np

    LANCEDB_AVAILABLE = True
except ImportError as e:
    print(f"❌ Required dependencies not available: {e}")
    print("Please install: pip install lancedb numpy")
    LANCEDB_AVAILABLE = False


class SimpleLanceDBDemo:
    """Simple demo class for LanceDB conversation storage and retrieval"""

    def __init__(self, db_path: str = "data/lancedb"):
        self.db_path = db_path
        self.db = None
        self.conversations_table = None

    async def initialize(self) -> bool:
        """Initialize LanceDB connection and create tables"""
        if not LANCEDB_AVAILABLE:
            print("❌ LanceDB dependencies not available")
            return False

        try:
            # Create database directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            # Connect to LanceDB
            self.db = lancedb.connect(self.db_path)
            print(f"✅ Connected to LanceDB at: {self.db_path}")

            # Define conversation schema
            schema = lancedb.schema(
                [
                    ("id", lancedb.string()),
                    ("user_id", lancedb.string()),
                    ("session_id", lancedb.string()),
                    ("role", lancedb.string()),
                    ("content", lancedb.string()),
                    ("message_type", lancedb.string()),
                    ("timestamp", lancedb.string()),
                    ("metadata", lancedb.string()),
                    ("embedding", lancedb.vector(384)),  # Standard embedding dimension
                ]
            )

            # Create or open conversations table
            try:
                self.conversations_table = self.db.open_table("conversations")
                print("✅ Conversations table loaded")
            except:
                self.conversations_table = self.db.create_table(
                    "conversations", schema=schema
                )
                print("✅ Conversations table created")

            return True

        except Exception as e:
            print(f"❌ Failed to initialize LanceDB: {e}")
            return False

    async def store_sample_conversations(self) -> int:
        """Store sample conversations for demonstration"""
        print("📝 Storing sample conversations...")

        sample_conversations = [
            {
                "id": str(uuid.uuid4()),
                "user_id": "demo-user-001",
                "session_id": "session-001",
                "role": "user",
                "content": "Hello, I need help with my account settings.",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": json.dumps({"topic": "account", "priority": "medium"}),
                "embedding": self._generate_simple_embedding(
                    "Hello, I need help with my account settings."
                ),
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "demo-user-001",
                "session_id": "session-001",
                "role": "assistant",
                "content": "I'd be happy to help you with your account settings. What specific issue are you experiencing?",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": json.dumps(
                    {"topic": "account", "response_type": "helpful"}
                ),
                "embedding": self._generate_simple_embedding(
                    "I'd be happy to help you with your account settings. What specific issue are you experiencing?"
                ),
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "demo-user-001",
                "session_id": "session-001",
                "role": "user",
                "content": "I can't change my password. The system says it's too weak.",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": json.dumps({"topic": "password", "issue": "validation"}),
                "embedding": self._generate_simple_embedding(
                    "I can't change my password. The system says it's too weak."
                ),
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "demo-user-001",
                "session_id": "session-001",
                "role": "assistant",
                "content": "For password security, please use at least 8 characters with a mix of uppercase, lowercase, numbers, and symbols.",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": json.dumps({"topic": "password", "advice": "security"}),
                "embedding": self._generate_simple_embedding(
                    "For password security, please use at least 8 characters with a mix of uppercase, lowercase, numbers, and symbols."
                ),
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "demo-user-002",
                "session_id": "session-002",
                "role": "user",
                "content": "How do I integrate the API with my application?",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": json.dumps({"topic": "api", "integration": "technical"}),
                "embedding": self._generate_simple_embedding(
                    "How do I integrate the API with my application?"
                ),
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "demo-user-002",
                "session_id": "session-002",
                "role": "assistant",
                "content": "You can integrate our API by following the documentation at docs.example.com. Would you like me to help with a specific integration scenario?",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": json.dumps({"topic": "api", "resources": "documentation"}),
                "embedding": self._generate_simple_embedding(
                    "You can integrate our API by following the documentation at docs.example.com. Would you like me to help with a specific integration scenario?"
                ),
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "demo-user-003",
                "session_id": "session-003",
                "role": "user",
                "content": "I'm having trouble with billing and payments.",
                "message_type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": json.dumps({"topic": "billing", "category": "financial"}),
                "embedding": self._generate_simple_embedding(
                    "I'm having trouble with billing and payments."
                ),
            },
        ]

        try:
            # Add conversations to the table
            self.conversations_table.add(sample_conversations)
            print(
                f"✅ Successfully stored {len(sample_conversations)} sample conversations"
            )
            return len(sample_conversations)

        except Exception as e:
            print(f"❌ Failed to store conversations: {e}")
            return 0

    def get_conversation_history(
        self, user_id: str, session_id: Optional[str] = None, limit: int = 50
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
            results = query.limit(limit).to_list()

            # Sort by timestamp
            results.sort(key=lambda x: x.get("timestamp", ""))

            # Process results
            conversations = []
            for result in results:
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

            # Create embedding for search query
            query_embedding = self._generate_simple_embedding(query_text)

            # Perform semantic search
            results = (
                self.conversations_table.search(query_embedding)
                .where(filter_condition)
                .limit(limit * 2)
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
            filtered_results = filtered_results[:limit]

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

    def export_conversations(self, user_id: str, output_file: str) -> bool:
        """Export conversations to JSON file"""
        print(f"💾 Exporting conversations for '{user_id}' to {output_file}")

        result = self.get_conversation_history(user_id, limit=100)

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
            return True
        else:
            print(f"❌ Failed to export conversations: {result.get('message')}")
            return False

    def list_users(self) -> Dict[str, Any]:
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
        """Generate a simple embedding for demonstration"""
        # This is a placeholder implementation
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


async def run_demo():
    """Run the complete LanceDB conversation demo"""
    print("🚀 Starting Simple LanceDB Conversation Storage and Retrieval Demo")
    print("=" * 60)

    # Initialize demo
    demo = SimpleLanceDBDemo()

    if not await demo.initialize():
        print("❌ Demo initialization failed")
        return

    print("\n1. 📝 STORING SAMPLE CONVERSATIONS")
    print("-" * 40)
    stored_count = await demo.store_sample_conversations()
    if stored_count == 0:
        print("❌ Cannot proceed without sample conversations")
        return

    print("\n2. 📖 RETRIEVING CONVERSATION HISTORY")
    print("-" * 40)

    # Demo user 001
    print("User: demo-user-001")
    result = demo.get_conversation_history("demo-user-001", limit=5)
    if result["status"] == "success":
        for i, conv in enumerate(result["conversations"], 1):
            role = conv.get("role", "unknown").upper()
            content = conv.get("content", "")
            print(f"   {i}. [{role}] {content}")
    print()

    # Demo user 002
    print("User: demo-user-002")
    result = demo.get_conversation_history("demo-user-002", limit=3)
    if result["status"] == "success":
        for i, conv in enumerate(result["conversations"], 1):
            role = conv.get("role", "unknown").upper()
            content = conv.get("content", "")
            print(f"   {i}. [{role}] {content}")
    print()

    print("\n3. 🔍 SEMANTIC SEARCH DEMONSTRATION")
    print("-" * 40)

    # Search for account-related conversations
    print("Search: 'account settings' for demo-user-001")
    result = demo.search_conversations("account settings", "demo-user-001")
    if result["status"] == "success":
        for i, res in enumerate(result["results"], 1):
            role = res.get("role", "unknown").upper()
            content = res.get("content", "")
            similarity = res.get("similarity_score", 0)
            print(f"   {i}. [{role}] Similarity: {similarity:.3f}")
            print(f"      {content}")
    print()

    # Search for API-related conversations
    print("Search: 'API integration' for demo-user-002")
    result = demo.search_conversations("API integration", "demo-user-002")
    if result["status"] == "success":
        for i, res in enumerate(result["results"], 1):
            role = res.get("role", "unknown").upper()
            content = res.get("content", "")
            similarity = res.get("similarity_score", 0)
            print(f"   {i}. [{role}] Similarity: {similarity:.3f}")
            print(f"      {content}")
    print()

    print("\n4. 💾 EXPORTING CONVERSATIONS")
    print("-" * 40)
    export_file = (
        f"simple_demo_conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    demo.export_conversations("demo-user-001", export_file)

    print("\n5. 👥 USER MANAGEMENT")
    print("-" * 40)
    users_result = demo.list_users()
    if users_result["status"] == "success":
        users = users_result["users"]
        print(f"📊 Found {len(users)} users with conversations:")
        for user in users:
            count_result = demo.get_conversation_history(user, limit=1)
            count = count_result.get("total_count", 0)
            print(f"   - {user} ({count} conversations)")

    print("\n" + "=" * 60)
    print("🎉 Demo completed successfully!")
    print(f"💾 Conversations exported to: {export_file}")
    print("\n📚 Next steps:")
    print("   - Use standalone_lancedb_retriever.py for ongoing retrieval")
    print("   - Integrate with proper embedding models for semantic search")
