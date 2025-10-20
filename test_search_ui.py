"""
Test script for search UI functionality

This script tests the LanceDB search API endpoints and verifies that
both web app and desktop app search functionality works correctly.
"""

import requests
import json
import time
import sys
from typing import Dict, List, Any

# Configuration
BACKEND_URL = "http://localhost:5058"
TEST_USER_ID = "test-user-123"


def test_health_check():
    """Test LanceDB search API health check"""
    print("Testing health check...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/lancedb-search/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_hybrid_search():
    """Test hybrid search functionality"""
    print("\nTesting hybrid search...")

    test_queries = [
        "project requirements",
        "meeting notes",
        "API documentation",
        "financial reports",
    ]

    for query in test_queries:
        try:
            payload = {
                "query": query,
                "user_id": TEST_USER_ID,
                "limit": 5,
                "search_type": "hybrid",
            }

            response = requests.post(
                f"{BACKEND_URL}/api/lancedb-search/hybrid", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    results = data.get("results", [])
                    print(
                        f"✅ Hybrid search for '{query}': Found {len(results)} results"
                    )
                    for i, result in enumerate(results[:2]):  # Show first 2 results
                        print(
                            f"   - Result {i + 1}: {result.get('title', 'No title')} "
                            f"(Score: {result.get('similarity_score', 0):.3f})"
                        )
                else:
                    print(
                        f"⚠️ Hybrid search for '{query}' returned error: {data.get('error')}"
                    )
            else:
                print(f"❌ Hybrid search for '{query}' failed: {response.status_code}")

        except Exception as e:
            print(f"❌ Hybrid search error for '{query}': {e}")


def test_semantic_search():
    """Test semantic search functionality"""
    print("\nTesting semantic search...")

    try:
        payload = {
            "query": "machine learning implementation",
            "user_id": TEST_USER_ID,
            "limit": 3,
        }

        response = requests.post(
            f"{BACKEND_URL}/api/lancedb-search/semantic", json=payload
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                results = data.get("results", [])
                print(f"✅ Semantic search: Found {len(results)} results")
                for i, result in enumerate(results):
                    print(f"   - Result {i + 1}: {result.get('title', 'No title')}")
            else:
                print(f"⚠️ Semantic search returned error: {data.get('error')}")
        else:
            print(f"❌ Semantic search failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Semantic search error: {e}")


def test_search_suggestions():
    """Test search suggestions functionality"""
    print("\nTesting search suggestions...")

    test_queries = ["pro", "meet", "api"]

    for query in test_queries:
        try:
            params = {"query": query, "user_id": TEST_USER_ID, "limit": 3}

            response = requests.get(
                f"{BACKEND_URL}/api/lancedb-search/suggestions", params=params
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    suggestions = data.get("suggestions", [])
                    print(f"✅ Suggestions for '{query}': {suggestions}")
                else:
                    print(
                        f"⚠️ Suggestions for '{query}' returned error: {data.get('error')}"
                    )
            else:
                print(f"❌ Suggestions for '{query}' failed: {response.status_code}")

        except Exception as e:
            print(f"❌ Suggestions error for '{query}': {e}")


def test_filter_search():
    """Test filter-based search"""
    print("\nTesting filter search...")

    try:
        payload = {
            "user_id": TEST_USER_ID,
            "filters": {"doc_type": ["document", "meeting"], "tags": ["important"]},
            "limit": 5,
        }

        response = requests.post(
            f"{BACKEND_URL}/api/lancedb-search/filter", json=payload
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                results = data.get("results", [])
                print(f"✅ Filter search: Found {len(results)} results")
                for i, result in enumerate(results):
                    print(
                        f"   - Result {i + 1}: {result.get('title', 'No title')} "
                        f"(Type: {result.get('doc_type', 'unknown')})"
                    )
            else:
                print(f"⚠️ Filter search returned error: {data.get('error')}")
        else:
            print(f"❌ Filter search failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Filter search error: {e}")


def test_document_ingestion():
    """Test document ingestion for desktop app"""
    print("\nTesting document ingestion...")

    test_documents = [
        {
            "title": "Test Document 1",
            "content": "This is a test document about project requirements and implementation details.",
            "type": "document",
            "user_id": TEST_USER_ID,
        },
        {
            "title": "Meeting Notes Test",
            "content": "Meeting notes discussing API documentation and financial reports.",
            "type": "meeting",
            "user_id": TEST_USER_ID,
        },
    ]

    for doc in test_documents:
        try:
            response = requests.post(f"{BACKEND_URL}/api/search/add_document", json=doc)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    print(f"✅ Document ingestion: {doc['title']}")
                    print(f"   - Note ID: {data.get('note_id', 'N/A')}")
                else:
                    print(
                        f"⚠️ Document ingestion failed for {doc['title']}: {data.get('message')}"
                    )
            else:
                print(
                    f"❌ Document ingestion failed for {doc['title']}: {response.status_code}"
                )

        except Exception as e:
            print(f"❌ Document ingestion error for {doc['title']}: {e}")


def test_search_analytics():
    """Test search analytics"""
    print("\nTesting search analytics...")

    try:
        params = {"user_id": TEST_USER_ID}

        response = requests.get(
            f"{BACKEND_URL}/api/lancedb-search/analytics", params=params
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                analytics = data.get("analytics", {})
                print(f"✅ Search analytics retrieved:")
                print(
                    f"   - Total documents: {analytics.get('total_documents', 'N/A')}"
                )
                print(
                    f"   - Search queries today: {analytics.get('search_queries_today', 'N/A')}"
                )
                if "documents_by_type" in analytics:
                    print(f"   - Documents by type: {analytics['documents_by_type']}")
            else:
                print(f"⚠️ Search analytics returned error: {data.get('error')}")
        else:
            print(f"❌ Search analytics failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Search analytics error: {e}")


def run_all_tests():
    """Run all search functionality tests"""
    print("🚀 Starting Search UI Tests")
    print("=" * 50)

    # Wait a moment for services to be ready
    time.sleep(2)

    tests = [
        test_health_check,
        test_hybrid_search,
        test_semantic_search,
        test_search_suggestions,
        test_filter_search,
        test_document_ingestion,
        test_search_analytics,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Search UI is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Check the backend services.")
        return False


if __name__ == "__main__":
    # Check if backend is available
    try:
        response = requests.get(f"{BACKEND_URL}/healthz", timeout=5)
        if response.status_code == 200:
            print(f"✅ Backend is running at {BACKEND_URL}")
            success = run_all_tests()
            sys.exit(0 if success else 1)
        else:
            print(f"❌ Backend not responding at {BACKEND_URL}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to backend at {BACKEND_URL}")
        print("Please make sure the backend is running on port 5058")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error checking backend: {e}")
        sys.exit(1)
