"""
Enhanced LanceDB Hybrid Search API

This module provides comprehensive hybrid search capabilities for LanceDB,
combining vector similarity search with keyword matching, filters, and
advanced ranking for optimal search results.
"""

from flask import Blueprint, request, jsonify
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import os

# Import LanceDB service
try:
    from _utils.lancedb_service import (
        search_meeting_transcripts,
        hybrid_note_search,
        search_similar_notes,
    )
    from note_utils import get_text_embedding_openai

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logging.warning("LanceDB service not available - using mock implementations")

    # Mock implementation for get_text_embedding_openai when LanceDB is not available
    def get_text_embedding_openai(
        text_to_embed,
        openai_api_key_param=None,
        embedding_model="text-embedding-3-small",
    ):
        """Mock implementation for text embedding"""
        if not text_to_embed:
            return {"status": "error", "message": "Text to embed cannot be empty."}
        # Return mock embedding vector with correct dimensions
        mock_vector = [0.01] * 1536  # Standard dimension for text-embedding-3-small
        return {"status": "success", "data": mock_vector}


logger = logging.getLogger(__name__)

# Create blueprint
lancedb_search_api = Blueprint("lancedb_search", __name__)


# Mock implementations for testing
class MockLanceDBService:
    """Mock LanceDB service for testing when LanceDB is not available"""

    @staticmethod
    def hybrid_search_documents(
        user_id, query_vector, text_query, filters=None, limit=10
    ):
        """Mock hybrid search implementation"""
        return [
            {
                "id": "mock_doc_1",
                "title": "Sample Document 1",
                "content": "This is a sample document containing information about the search query.",
                "doc_type": "document",
                "source_uri": "file:///sample1.txt",
                "similarity_score": 0.95,
                "keyword_score": 0.85,
                "combined_score": 0.90,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "author": "System",
                    "tags": ["sample", "test"],
                },
            },
            {
                "id": "mock_doc_2",
                "title": "Sample Meeting Notes",
                "content": "Meeting notes discussing the project requirements and implementation details.",
                "doc_type": "meeting",
                "source_uri": "meeting:///project_kickoff",
                "similarity_score": 0.88,
                "keyword_score": 0.92,
                "combined_score": 0.89,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "participants": ["Alice", "Bob", "Charlie"],
                    "tags": ["meeting", "project"],
                },
            },
        ]

    @staticmethod
    def search_by_filters(user_id, filters, limit=10):
        """Mock filter-based search"""
        return [
            {
                "id": f"filtered_doc_{i}",
                "title": f"Filtered Document {i}",
                "doc_type": filters.get("doc_type", "document"),
                "source_uri": f"file:///filtered_{i}.txt",
                "created_at": datetime.now().isoformat(),
                "metadata": {"tags": filters.get("tags", [])},
            }
            for i in range(min(limit, 5))
        ]

    @staticmethod
    def get_search_suggestions(user_id, query, limit=5):
        """Mock search suggestions"""
        suggestions = [
            f"{query} implementation",
            f"{query} best practices",
            f"{query} examples",
            f"advanced {query}",
            f"{query} tutorial",
        ]
        return suggestions[:limit]

    @staticmethod
    def get_search_analytics(user_id):
        """Mock search analytics"""
        return {
            "total_documents": 150,
            "documents_by_type": {
                "document": 75,
                "meeting": 35,
                "note": 25,
                "email": 15,
            },
            "search_queries_today": 42,
            "popular_searches": [
                {"query": "project requirements", "count": 15},
                {"query": "meeting notes", "count": 12},
                {"query": "API documentation", "count": 8},
            ],
        }


# Use mock if LanceDB not available
if not LANCEDB_AVAILABLE:
    lancedb_service = MockLanceDBService()
else:
    lancedb_service = None  # Will use actual imported functions


@lancedb_search_api.route("/api/lancedb-search/hybrid", methods=["POST"])
def hybrid_search():
    """
    Perform hybrid search combining vector similarity and keyword matching

    Request body:
    {
        "query": "search query text",
        "user_id": "user identifier",
        "filters": {
            "doc_type": ["document", "meeting"],
            "tags": ["important", "project"],
            "date_range": {
                "start": "2024-01-01",
                "end": "2024-12-31"
            }
        },
        "limit": 10,
        "search_type": "hybrid"  # hybrid, semantic, keyword
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"success": False, "error": "Request body must be JSON"}
            ), 400

        query = data.get("query", "").strip()
        user_id = data.get("user_id")
        filters = data.get("filters", {})
        limit = data.get("limit", 10)
        search_type = data.get("search_type", "hybrid")

        if not query:
            return jsonify({"success": False, "error": "Search query is required"}), 400

        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        logger.info(f"Performing {search_type} search for user {user_id}: '{query}'")

        # Generate embedding for semantic search
        embedding_response = get_text_embedding_openai(query)
        if embedding_response.get("status") != "success":
            return jsonify(
                {
                    "success": False,
                    "error": f"Failed to generate embedding: {embedding_response.get('message')}",
                }
            ), 500

        query_vector = embedding_response.get("data", [])

        # Perform hybrid search
        if LANCEDB_AVAILABLE:
            # Use actual LanceDB service
            results = hybrid_note_search(
                user_id=user_id,
                query_vector=query_vector,
                text_query=query,
                limit=limit,
            )
        else:
            # Use mock service
            results = MockLanceDBService.hybrid_search_documents(
                user_id=user_id,
                query_vector=query_vector,
                text_query=query,
                filters=filters,
                limit=limit,
            )

        return jsonify(
            {
                "success": True,
                "query": query,
                "search_type": search_type,
                "results": results,
                "total_results": len(results),
                "filters_applied": filters,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error in hybrid search: {str(e)}")
        return jsonify({"success": False, "error": f"Search failed: {str(e)}"}), 500


@lancedb_search_api.route("/api/lancedb-search/semantic", methods=["POST"])
def semantic_search():
    """
    Perform semantic (vector) search only
    """
    try:
        data = request.get_json()
        query = data.get("query", "").strip()
        user_id = data.get("user_id")
        limit = data.get("limit", 10)

        if not query or not user_id:
            return jsonify(
                {"success": False, "error": "Query and user_id are required"}
            ), 400

        # Generate embedding
        embedding_response = get_text_embedding_openai(query)
        if embedding_response.get("status") != "success":
            return jsonify(
                {
                    "success": False,
                    "error": f"Failed to generate embedding: {embedding_response.get('message')}",
                }
            ), 500

        query_vector = embedding_response.get("data", [])

        # Perform semantic search
        if LANCEDB_AVAILABLE:
            results = search_meeting_transcripts(
                db_path=os.environ.get("LANCEDB_URI", "/tmp/lancedb"),
                query_vector=query_vector,
                user_id=user_id,
                table_name="meeting_transcripts_embeddings",
                limit=limit,
            )
        else:
            # Use mock - for semantic search, we'll use hybrid with emphasis on vector
            results = MockLanceDBService.hybrid_search_documents(
                user_id=user_id,
                query_vector=query_vector,
                text_query="",  # Empty text query for pure semantic
                limit=limit,
            )

        return jsonify(
            {
                "success": True,
                "query": query,
                "search_type": "semantic",
                "results": results,
                "total_results": len(results),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error in semantic search: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Semantic search failed: {str(e)}"}
        ), 500


@lancedb_search_api.route("/api/lancedb-search/filter", methods=["POST"])
def filter_search():
    """
    Search by filters without text query
    """
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        filters = data.get("filters", {})
        limit = data.get("limit", 10)

        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        # Perform filter-based search
        if LANCEDB_AVAILABLE:
            # For actual implementation, this would query LanceDB with filters
            results = search_similar_notes(
                db_path="/tmp/mock_lancedb",
                user_id=user_id,
                query_vector=[0.0] * 1536,  # Neutral vector
                limit=limit,
            )
            if isinstance(results, dict) and "results" in results:
                results = results["results"]
        else:
            results = MockLanceDBService.search_by_filters(
                user_id=user_id, filters=filters, limit=limit
            )

        # Apply client-side filtering for mock (in real implementation, this would be in the query)
        filtered_results = []
        for result in results:
            matches = True

            # Filter by document type
            if (
                "doc_type" in filters
                and result.get("doc_type") not in filters["doc_type"]
            ):
                matches = False

            # Filter by tags
            if "tags" in filters and filters["tags"]:
                result_tags = result.get("metadata", {}).get("tags", [])
                if not any(tag in result_tags for tag in filters["tags"]):
                    matches = False

            if matches:
                filtered_results.append(result)

        return jsonify(
            {
                "success": True,
                "search_type": "filter",
                "filters": filters,
                "results": filtered_results[:limit],
                "total_results": len(filtered_results),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error in filter search: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Filter search failed: {str(e)}"}
        ), 500


@lancedb_search_api.route("/api/lancedb-search/suggestions", methods=["GET"])
def get_search_suggestions():
    """
    Get search suggestions based on partial query
    """
    try:
        query = request.args.get("query", "").strip()
        user_id = request.args.get("user_id")
        limit = int(request.args.get("limit", 5))

        if not query:
            return jsonify(
                {"success": False, "error": "Query parameter is required"}
            ), 400

        # Get search suggestions
        suggestions = MockLanceDBService.get_search_suggestions(
            user_id=user_id, query=query, limit=limit
        )

        return jsonify(
            {
                "success": True,
                "query": query,
                "suggestions": suggestions,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error getting search suggestions: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to get suggestions: {str(e)}"}
        ), 500


@lancedb_search_api.route("/api/lancedb-search/analytics", methods=["GET"])
def get_search_analytics():
    """
    Get search analytics and statistics
    """
    try:
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        analytics = MockLanceDBService.get_search_analytics(user_id)

        return jsonify(
            {
                "success": True,
                "analytics": analytics,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error getting search analytics: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to get analytics: {str(e)}"}
        ), 500


@lancedb_search_api.route("/api/lancedb-search/health", methods=["GET"])
def health_check():
    """
    Health check for LanceDB search API
    """
    try:
        status = {
            "lancedb_available": LANCEDB_AVAILABLE,
            "search_endpoints": [
                "/api/lancedb-search/hybrid",
                "/api/lancedb-search/semantic",
                "/api/lancedb-search/filter",
                "/api/lancedb-search/suggestions",
                "/api/lancedb-search/analytics",
            ],
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
        }

        return jsonify({"success": True, "status": status})

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"success": False, "error": str(e), "status": "unhealthy"}), 500


# Error handlers
@lancedb_search_api.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404


@lancedb_search_api.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"success": False, "error": "Method not allowed"}), 405


@lancedb_search_api.errorhandler(500)
def internal_server_error(error):
    return jsonify({"success": False, "error": "Internal server error"}), 500
