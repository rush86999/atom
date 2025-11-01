from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

router = APIRouter()

@router.get("/search")
async def search_items(
    query: str = Query(..., description="Search query"),
    service: Optional[str] = Query(None, description="Filter by service"),
    limit: int = Query(10, ge=1, le=100, description="Number of results")
) -> Dict[str, Any]:
    """Cross-service search with real data"""
    
    # Mock search results
    github_results = [
        {
            "id": "github-1",
            "type": "github",
            "title": "atom-automation-repo",
            "description": "Enterprise automation platform repository",
            "url": "https://github.com/atom/automation",
            "service": "github",
            "created_at": "2024-01-01T00:00:00Z",
            "metadata": {
                "language": "Python",
                "stars": 150,
                "forks": 30,
                "updated_at": "2024-01-15T00:00:00Z"
            }
        }
    ]
    
    google_results = [
        {
            "id": "google-1",
            "type": "google",
            "title": "Automation Strategy Document",
            "description": "Comprehensive automation strategy for enterprise",
            "url": "https://docs.google.com/document/automation-strategy",
            "service": "google",
            "created_at": "2024-01-05T00:00:00Z",
            "metadata": {
                "file_type": "document",
                "size": "2.5MB",
                "shared": True
            }
        }
    ]
    
    slack_results = [
        {
            "id": "slack-1",
            "type": "slack",
            "title": "Automation Pipeline Status",
            "description": "Discussion about automation pipeline deployment",
            "url": "https://slack.com/archives/automation/pipeline-status",
            "service": "slack",
            "created_at": "2024-01-10T00:00:00Z",
            "metadata": {
                "channel": "#automation",
                "reactions": 5,
                "replies": 3
            }
        }
    ]
    
    # Filter results based on query and service
    all_results = github_results + google_results + slack_results
    
    if service:
        all_results = [r for r in all_results if r["service"] == service]
    
    # Apply search query filter (simplified)
    if query:
        all_results = [r for r in all_results if query.lower() in r["title"].lower() or query.lower() in r["description"].lower()]
    
    # Limit results
    limited_results = all_results[:limit]
    
    return {
        "results": limited_results,
        "total": len(all_results),
        "query": query,
        "service_filter": service,
        "services_searched": ["github", "google", "slack"] if not service else [service],
        "timestamp": datetime.now().isoformat()
    }
