#!/usr/bin/env python3
"""
LanceDB API Client for Atom Chat Interface

This client provides programmatic access to retrieve conversations from LanceDB
through the Atom Chat Interface API endpoints.

Features:
- Retrieve conversation history for users
- Search conversations using semantic similarity
- Export conversation data
- Test API connectivity
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
import requests


class LanceDBAPIClient:
    """Client for interacting with LanceDB conversation endpoints"""

    def __init__(self, base_url: str = "http://localhost:5059"):
        self.base_url = base_url.rstrip("/")
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _make_sync_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make synchronous HTTP request"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"HTTP request failed: {str(e)}",
                "error": str(e),
            }

    async def _make_async_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make asynchronous HTTP request"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        url = f"{self.base_url}{endpoint}"
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            return {
                "status": "error",
                "message": f"HTTP request failed: {str(e)}",
                "error": str(e),
            }

    async def test_connection(self) -> Dict:
        """Test API connection and health"""
        return await self._make_async_request("GET", "/health")

    async def get_conversation_history(
        self, user_id: str, session_id: Optional[str] = None, limit: int = 50
    ) -> Dict:
        """Get conversation history for a user"""
        endpoint = f"/api/v1/memory/history/{user_id}"
        params = {}
        if session_id:
            params["session_id"] = session_id
        if limit:
            params["limit"] = limit

        return await self._make_async_request("GET", endpoint, params=params)

    async def search_conversations(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> Dict:
        """Search conversations using semantic similarity"""
        endpoint = "/api/v1/memory/search"
        payload = {
            "query": query,
            "user_id": user_id,
            "limit": limit,
            "similarity_threshold": similarity_threshold,
        }
        if session_id:
            payload["session_id"] = session_id

        return await self._make_async_request("POST", endpoint, json=payload)

    async def get_conversation_details(self, conversation_id: str) -> Dict:
        """Get details for a specific conversation"""
        endpoint = f"/api/v1/conversations/{conversation_id}"
        return await self._make_async_request("GET", endpoint)

    async def get_analytics_overview(self) -> Dict:
        """Get analytics overview"""
        endpoint = "/api/v1/analytics/overview"
        return await self._make_async_request("GET", endpoint)

    def get_conversation_history_sync(
        self, user_id: str, session_id: Optional[str] = None, limit: int = 50
    ) -> Dict:
        """Synchronous version of get_conversation_history"""
        endpoint = f"/api/v1/memory/history/{user_id}"
        params = {}
        if session_id:
            params["session_id"] = session_id
        if limit:
            params["limit"] = limit

        return self._make_sync_request("GET", endpoint, params=params)

    def search_conversations_sync(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> Dict:
        """Synchronous version of search_conversations"""
        endpoint = "/api/v1/memory/search"
        payload = {
            "query": query,
            "user_id": user_id,
            "limit": limit,
            "similarity_threshold": similarity_threshold,
        }
        if session_id:
            payload["session_id"] = session_id

        return self._make_sync_request("POST", endpoint, json=payload)


async def test_api_connection(client: LanceDBAPIClient):
    """Test API connection"""
    print("🧪 Testing API Connection...")

    try:
        result = await client.test_connection()

        if "status" in result and result.get("status") == "healthy":
            print("✅ API connection test passed")
            print(f"   Status: {result.get('status', 'unknown')}")
            print(f"   Memory System: {result.get('memory_system', 'unknown')}")
            return True
        else:
            print("❌ API connection test failed")
            print(f"   Response: {result}")
            return False

    except Exception as e:
        print(f"❌ API connection test failed: {e}")
        return False


async def retrieve_user_conversations(
    client: LanceDBAPIClient, user_id: str, limit: int = 20
):
    """Retrieve and display conversations for a user"""
    print(f"📝 Retrieving conversations for user: {user_id}")

    result = await client.get_conversation_history(user_id, limit=limit)

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
        print(
            f"❌ Failed to retrieve conversations: {result.get('message', 'Unknown error')}"
        )


async def search_user_conversations(
    client: LanceDBAPIClient, user_id: str, query: str, limit: int = 10
):
    """Search conversations for a user"""
    print(f"🔍 Searching conversations for user '{user_id}': '{query}'")

    result = await client.search_conversations(query, user_id, limit=limit)

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
        print(
            f"❌ Failed to search conversations: {result.get('message', 'Unknown error')}"
        )


async def export_conversations(
    client: LanceDBAPIClient, user_id: str, output_file: str
):
    """Export conversations to JSON file"""
    print(f"💾 Exporting conversations for user '{user_id}' to {output_file}")

    # Get all conversations with large limit
    result = await client.get_conversation_history(user_id, limit=1000)

    if result.get("status") == "success":
        conversations = result.get("conversations", [])

        # Prepare export data
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "total_conversations": len(conversations),
            "conversations": conversations,
            "source_api": client.base_url,
        }

        # Write to file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(
            f"✅ Successfully exported {len(conversations)} conversations to {output_file}"
        )

    else:
        print(
            f"❌ Failed to export conversations: {result.get('message', 'Unknown error')}"
        )


async def get_analytics(client: LanceDBAPIClient):
    """Get analytics overview"""
    print("📈 Getting analytics overview...")

    result = await client.get_analytics_overview()

    if "total_conversations" in result:
        print(f"📊 Analytics Overview:")
        print(f"   Total Conversations: {result.get('total_conversations', 0)}")
        print(f"   Total Messages: {result.get('total_messages', 0)}")
        print(f"   Total AI Analyses: {result.get('total_ai_analyses', 0)}")
        print(f"   Active Users: {result.get('active_users', 0)}")
    else:
        print(f"❌ Failed to get analytics: {result}")


def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(
        description="LanceDB API Client for Atom Chat Interface"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:5059",
        help="Base URL of the chat interface API",
    )
    parser.add_argument(
        "--user-id", required=True, help="User ID to retrieve conversations for"
    )
    parser.add_argument(
        "--action",
        choices=["test", "retrieve", "search", "export", "analytics"],
        default="retrieve",
        help="Action to perform",
    )
    parser.add_argument("--query", help="Search query (for search action)")
    parser.add_argument(
        "--limit", type=int, default=20, help="Number of conversations to retrieve"
    )
    parser.add_argument("--output", help="Output file for export")

    args = parser.parse_args()

    # Create client
    client = LanceDBAPIClient(base_url=args.base_url)

    async def run_actions():
        async with client:
            # Test connection first for all actions except test
            if args.action != "test":
                connected = await test_api_connection(client)
                if not connected:
                    print("❌ Cannot proceed without API connection")
                    return

            # Perform the requested action
            if args.action == "test":
                await test_api_connection(client)
            elif args.action == "retrieve":
                await retrieve_user_conversations(client, args.user_id, args.limit)
            elif args.action == "search":
                if not args.query:
                    print("❌ Please provide a search query with --query")
                    return
                await search_user_conversations(
                    client, args.user_id, args.query, args.limit
                )
            elif args.action == "export":
                output_file = (
                    args.output
                    or f"conversations_{args.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                await export_conversations(client, args.user_id, output_file)
            elif args.action == "analytics":
                await get_analytics(client)

    # Run async operations
    asyncio.run(run_actions())


if __name__ == "__main__":
    main()
