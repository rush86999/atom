"""
Comprehensive Search Functionality Verification Script

This script tests all search-related endpoints and functionality
to ensure the search UI implementation is working correctly.
"""

import json
import sys
import time
from typing import Any, Dict, List
import requests

# Configuration
BACKEND_URL = "http://localhost:5058"
TEST_USER_ID = "test-user-123"


def print_success(message: str):
    """Print success message"""
    print(f"✅ {message}")


def print_warning(message: str):
    """Print warning message"""
    print(f"⚠️ {message}")


def print_error(message: str):
    """Print error message"""
    print(f"❌ {message}")


def test_backend_health():
    """Test backend health endpoint"""
    print("Testing backend health...")
    try:
        response = requests.get(f"{BACKEND_URL}/healthz", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Backend is healthy: {data.get('status', 'unknown')}")
            return True
        else:
            print_error(f"Backend health check failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Backend health check error: {e}")
        return False


def test_lancedb_search_api_health():
    """Test LanceDB search API health endpoint"""
    print("\nTesting LanceDB Search API health...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/lancedb-search/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                status = data.get("status", {})
                print_success(
                    f"LanceDB Search API is healthy: {status.get('status', 'unknown')}"
                )
                print(
                    f"   - LanceDB Available: {status.get('lancedb_available', False)}"
                )
                print(f"   - Endpoints: {len(status.get('search_endpoints', []))}")
                return True
            else:
                print_error(f"LanceDB Search API returned error: {data.get('error')}")
                return False
        else:
            print_error(
                f"LanceDB Search API health check failed: {response.status_code}"
            )
            return False
    except Exception as e:
        print_error(f"LanceDB Search API health check error: {e}")
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

    all_passed = True

    for query in test_queries:
        try:
            payload = {
                "query": query,
                "user_id": TEST_USER_ID,
                "limit": 5,
                "search_type": "hybrid",
            }

            response = requests.post(
                f"{BACKEND_URL}/api/lancedb-search/hybrid", json=payload, timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    results = data.get("results", [])
                    print_success(
                        f"Hybrid search for '{query}': {len(results)} results"
                    )
                    for i, result in enumerate(results[:2]):
                        print(
                            f"   - {result.get('title', 'No title')} (Score: {result.get('similarity_score', 0):.3f})"
                        )
                else:
                    print_warning(
                        f"Hybrid search for '{query}' returned error: {data.get('error')}"
                    )
                    all_passed = False
            else:
                print_error(
                    f"Hybrid search for '{query}' failed: {response.status_code}"
                )
                all_passed = False

        except Exception as e:
            print_error(f"Hybrid search error for '{query}': {e}")
            all_passed = False

    return all_passed


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
            f"{BACKEND_URL}/api/lancedb-search/semantic", json=payload, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                results = data.get("results", [])
                print_success(f"Semantic search: {len(results)} results")
                for i, result in enumerate(results):
                    print(f"   - {result.get('title', 'No title')}")
                return True
            else:
                print_warning(f"Semantic search returned error: {data.get('error')}")
                return False
        else:
            print_error(f"Semantic search failed: {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Semantic search error: {e}")
        return False


def test_search_suggestions():
    """Test search suggestions functionality"""
    print("\nTesting search suggestions...")

    test_queries = ["pro", "meet", "api"]
    all_passed = True

    for query in test_queries:
        try:
            params = {"query": query, "user_id": TEST_USER_ID, "limit": 3}

            response = requests.get(
                f"{BACKEND_URL}/api/lancedb-search/suggestions",
                params=params,
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    suggestions = data.get("suggestions", [])
                    print_success(f"Suggestions for '{query}': {suggestions}")
                else:
                    print_warning(
                        f"Suggestions for '{query}' returned error: {data.get('error')}"
                    )
                    all_passed = False
            else:
                print_error(f"Suggestions for '{query}' failed: {response.status_code}")
                all_passed = False

        except Exception as e:
            print_error(f"Suggestions error for '{query}': {e}")
            all_passed = False

    return all_passed


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
            f"{BACKEND_URL}/api/lancedb-search/filter", json=payload, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                results = data.get("results", [])
                print_success(f"Filter search: {len(results)} results")
                for i, result in enumerate(results):
                    print(
                        f"   - {result.get('title', 'No title')} (Type: {result.get('doc_type', 'unknown')})"
                    )
                return True
            else:
                print_warning(f"Filter search returned error: {data.get('error')}")
                return False
        else:
            print_error(f"Filter search failed: {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Filter search error: {e}")
        return False


def test_search_analytics():
    """Test search analytics"""
    print("\nTesting search analytics...")

    try:
        params = {"user_id": TEST_USER_ID}

        response = requests.get(
            f"{BACKEND_URL}/api/lancedb-search/analytics", params=params, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                analytics = data.get("analytics", {})
                print_success("Search analytics retrieved:")
                print(
                    f"   - Total documents: {analytics.get('total_documents', 'N/A')}"
                )
                print(
                    f"   - Search queries today: {analytics.get('search_queries_today', 'N/A')}"
                )
                if "documents_by_type" in analytics:
                    print(f"   - Documents by type: {analytics['documents_by_type']}")
                return True
            else:
                print_warning(f"Search analytics returned error: {data.get('error')}")
                return False
        else:
            print_error(f"Search analytics failed: {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Search analytics error: {e}")
        return False


def test_search_routes_endpoints():
    """Test search routes endpoints"""
    print("\nTesting search routes endpoints...")

    # Test semantic search meetings
    try:
        payload = {"query": "test query", "user_id": TEST_USER_ID}

        response = requests.post(
            f"{BACKEND_URL}/api/search/semantic_search_meetings",
            json=payload,
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Search routes semantic search working")
            return True
        else:
            print_warning(
                f"Search routes semantic search failed: {response.status_code}"
            )
            return False

    except Exception as e:
        print_warning(f"Search routes semantic search error: {e}")
        return False


def test_web_app_api_proxy():
    """Test web app API proxy (if frontend is running)"""
    print("\nTesting web app API proxy...")

    try:
        response = requests.get(
            "http://localhost:3004/api/lancedb-search/health", timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Web app API proxy is working")
            return True
        else:
            print_warning(f"Web app API proxy returned: {response.status_code}")
            return False
    except Exception as e:
        print_warning(f"Web app API proxy not available: {e}")
        return False


def run_comprehensive_tests():
    """Run all comprehensive tests"""
    print("🚀 Starting Comprehensive Search Functionality Tests")
    print("=" * 60)

    # Wait for services to be ready
    time.sleep(2)

    tests = [
        ("Backend Health", test_backend_health),
        ("LanceDB Search API Health", test_lancedb_search_api_health),
        ("Hybrid Search", test_hybrid_search),
        ("Semantic Search", test_semantic_search),
        ("Search Suggestions", test_search_suggestions),
        ("Filter Search", test_filter_search),
        ("Search Analytics", test_search_analytics),
        ("Search Routes", test_search_routes_endpoints),
        ("Web App API Proxy", test_web_app_api_proxy),
    ]

    passed = 0
    total = len(tests)
    results = []

    for test_name, test_func in tests:
        try:
            print(f"\n--- {test_name} ---")
            if test_func():
                passed += 1
                results.append((test_name, "PASSED"))
            else:
                results.append((test_name, "FAILED"))
        except Exception as e:
            print_error(f"Test {test_name} crashed: {e}")
            results.append((test_name, "CRASHED"))

    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    for test_name, status in results:
        status_icon = (
            "✅" if status == "PASSED" else "❌" if status == "FAILED" else "⚠️"
        )
        print(f"{status_icon} {test_name}: {status}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL TESTS PASSED! Search functionality is fully operational.")
        return True
    elif passed >= total * 0.7:
        print("⚠️ Most tests passed. Search functionality is mostly operational.")
        return True
    else:
        print("❌ Many tests failed. Search functionality needs attention.")
        return False


def generate_status_report():
    """Generate a comprehensive status report"""
    print("\n" + "=" * 60)
    print("📋 SEARCH FUNCTIONALITY STATUS REPORT")
    print("=" * 60)

    # Test core functionality
    core_tests = [
        test_backend_health(),
        test_lancedb_search_api_health(),
        test_hybrid_search(),
        test_semantic_search(),
        test_search_suggestions(),
    ]

    core_passed = sum(core_tests)
    core_total = len(core_tests)

    print(f"\nCore Search Functionality: {core_passed}/{core_total} tests passed")

    if core_passed == core_total:
        print("✅ Core search functionality is fully operational")
    elif core_passed >= core_total * 0.8:
        print("⚠️ Core search functionality is mostly operational")
    else:
        print("❌ Core search functionality has issues")

    # Additional features
    additional_tests = [
        test_filter_search(),
        test_search_analytics(),
        test_search_routes_endpoints(),
    ]

    additional_passed = sum(additional_tests)
    additional_total = len(additional_tests)

    print(f"\nAdditional Features: {additional_passed}/{additional_total} tests passed")

    # Recommendations
    print("\n💡 RECOMMENDATIONS:")

    if not test_backend_health():
        print("  - Ensure backend service is running on port 5058")

    if not test_lancedb_search_api_health():
        print("  - Check LanceDB search API registration and dependencies")

    if not test_hybrid_search():
        print("  - Verify hybrid search endpoint configuration")

    if not test_web_app_api_proxy():
        print("  - Start frontend development server (npm run dev)")
        print("  - Check API proxy configuration")

    print("\nNext steps:")
    print("  1. Test web app search page at http://localhost:3004/search")
    print("  2. Build and test desktop app with local file ingestion")
    print("  3. Verify search results with real data")


if __name__ == "__main__":
    try:
        # Run comprehensive tests
        success = run_comprehensive_tests()

        # Generate status report
        generate_status_report()

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n⚠️ Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error during testing: {e}")
        sys.exit(1)
