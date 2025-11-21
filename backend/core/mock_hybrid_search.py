"""
Mock Hybrid Search Service
Provides search functionality without LanceDB dependency
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MockHybridSearch:
    """Mock hybrid search that simulates vector search"""
    
    def __init__(self):
        # Pre-populated mock data
        self.documents = [
            {
                "id": "doc_1",
                "text": "Q4 Marketing Strategy focuses on organic growth through content marketing and SEO optimization. Key targets include a 20% increase in inbound leads.",
                "source": "document",
                "metadata": {"title": "Q4 Marketing Plan", "type": "document", "author": "Sarah J."},
                "keywords": ["marketing", "strategy", "SEO", "growth", "leads"]
            },
            {
                "id": "doc_2",
                "text": "API Documentation v2.0: All endpoints now require Bearer token authentication. Rate limits are set to 100 requests per minute.",
                "source": "document",
                "metadata": {"title": "API Docs v2.0", "type": "document", "author": "Dev Team"},
                "keywords": ["API", "documentation", "authentication", "bearer", "rate", "limits"]
            },
            {
                "id": "meeting_1",
                "text": "Meeting Transcript: Team discussed the new frontend architecture. Decided to migrate to Next.js 14 for better server-side rendering performance. Action items: JIRA-123, JIRA-124.",
                "source": "meeting",
                "metadata": {"title": "Frontend Architecture Review", "type": "meeting", "attendees": ["Alice", "Bob"]},
                "keywords": ["meeting", "frontend", "nextjs", "architecture", "jira", "migration"]
            },
            {
                "id": "meeting_2",
                "text": "Client Call Notes: Client requested a new feature for exporting reports to PDF. Timeline agreed for delivery is next Friday.",
                "source": "meeting",
                "metadata": {"title": "Weekly Client Sync", "type": "meeting", "attendees": ["Client", "PM"]},
                "keywords": ["client", "call", "PDF", "export", "reports", "deadline"]
            },
            {
                "id": "task_1",
                "text": "Task: Fix the login page layout issue on mobile devices. The submit button is overlapping with the footer.",
                "source": "task",
                "metadata": {"title": "Fix Mobile Login", "type": "task", "priority": "high"},
                "keywords": ["task", "bug", "login", "mobile", "layout", "UI"]
            },
            {
                "id": "task_2",
                "text": "Task: Update the database schema to support multi-tenant architecture. Migration script needed.",
                "source": "task",
                "metadata": {"title": "DB Schema Migration", "type": "task", "priority": "critical"},
                "keywords": ["task", "database", "schema", "migration", "multi-tenant"]
            }
        ]
        logger.info(f"MockHybridSearch initialized with {len(self.documents)} documents")
    
    def search(self, query: str, limit: int = 10, source_filter: str = None) -> List[Dict[str, Any]]:
        """
        Perform keyword-based search (simulates semantic search)
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        results = []
        for doc in self.documents:
            # Apply source filter if specified
            if source_filter and doc["source"] != source_filter:
                continue
            
            # Calculate simple relevance score
            score = 0
            doc_text_lower = doc["text"].lower()
            doc_keywords_lower = [k.lower() for k in doc["keywords"]]
            
            # Keyword matching
            for word in query_words:
                if word in doc_text_lower:
                    score += 2
                if any(word in keyword for keyword in doc_keywords_lower):
                    score += 3
            
            # Exact phrase matching
            if query_lower in doc_text_lower:
                score += 10
            
            if score > 0:
                results.append({
                    **doc,
                    "score": score / 10.0,  # Normalize to 0-1
                    "created_at": "2024-11-20T00:00:00Z"
                })
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:limit]
    
    def add_document(self, text: str, source: str = "document", metadata: Dict[str, Any] = None) -> bool:
        """Add a document to the mock index"""
        doc_id = f"{source}_{len(self.documents) + 1}"
        keywords = text.lower().split()[:10]  # Simple keyword extraction
        
        self.documents.append({
            "id": doc_id,
            "text": text,
            "source": source,
            "metadata": metadata or {},
            "keywords": keywords
        })
        
        logger.info(f"Added document {doc_id}")
        return True
    
    def test_connection(self) -> Dict[str, Any]:
        """Test mock search connection"""
        return {
            "status": "success",
            "message": "Mock Hybrid Search ready",
            "connected": True,
            "document_count": len(self.documents),
            "sources": list(set(doc["source"] for doc in self.documents))
        }

# Global instance
mock_search = MockHybridSearch()

def get_mock_search() -> MockHybridSearch:
    """Get the global mock search instance"""
    return mock_search
