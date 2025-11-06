"""
Google Drive Search UI Integration
Advanced search interface with semantic capabilities, filters, and AI-powered features
"""

import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from flask import Blueprint, request, jsonify, send_file
from loguru import logger

# Google Drive imports
from google_drive_service import GoogleDriveService
from google_drive_memory import GoogleDriveMemoryService
from google_drive_automation import GoogleDriveAutomationService

# Search UI imports
from search.ui_components import SearchUIComponents, SearchUIConfig
from search.analytics import SearchAnalytics

class SearchType(Enum):
    """Search types for Google Drive"""
    SEMANTIC = "semantic"  # AI-powered semantic search
    TEXT = "text"         # Full-text search
    METADATA = "metadata"  # Search file metadata
    HYBRID = "hybrid"      # Combined search with ranking
    VISUAL = "visual"       # Visual search (images)
    VOICE = "voice"         # Voice search
    ADVANCED = "advanced"    # Advanced search with complex filters

class FilterType(Enum):
    """Filter types for search"""
    FILE_TYPE = "file_type"
    SIZE = "size"
    DATE_RANGE = "date_range"
    OWNER = "owner"
    SHARED = "shared"
    MODIFIED = "modified"
    FOLDER = "folder"
    CONTENT_TYPE = "content_type"
    TAGS = "tags"
    CUSTOM = "custom"

class SortType(Enum):
    """Sort types for search results"""
    RELEVANCE = "relevance"
    DATE_MODIFIED = "date_modified"
    DATE_CREATED = "date_created"
    NAME = "name"
    SIZE = "size"
    TYPE = "type"
    OWNER = "owner"

class ViewType(Enum):
    """View types for search results"""
    LIST = "list"
    GRID = "grid"
    THUMBNAIL = "thumbnail"
    DETAIL = "detail"
    TIMELINE = "timeline"
    TREE = "tree"

@dataclass
class SearchQuery:
    """Search query model"""
    id: str
    user_id: str
    query: str
    search_type: SearchType
    filters: Dict[str, Any] = field(default_factory=dict)
    sort: SortType = SortType.RELEVANCE
    view: ViewType = ViewType.LIST
    limit: int = 50
    offset: int = 0
    include_content: bool = True
    include_thumbnails: bool = True
    facets: List[str] = field(default_factory=list)
    context: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class SearchResult:
    """Search result model"""
    id: str
    file_id: str
    name: str
    mime_type: str
    size: int
    created_time: datetime
    modified_time: datetime
    parents: List[str]
    web_view_link: str
    web_content_link: str
    thumbnail_link: str
    shared: bool
    owners: List[str]
    permissions: List[Dict[str, Any]]
    score: float
    highlights: List[str] = field(default_factory=list)
    snippets: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_preview: Optional[str] = None
    thumbnail_data: Optional[bytes] = None
    relevance_factors: Dict[str, float] = field(default_factory=dict)

@dataclass
class SearchFacet:
    """Search facet model"""
    field: str
    label: str
    type: str
    values: List[Dict[str, Any]]
    selected: List[str] = field(default_factory=list)
    total: int = 0

@dataclass
class SearchSuggestion:
    """Search suggestion model"""
    text: str
    type: str
    score: float
    category: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchSession:
    """Search session model"""
    id: str
    user_id: str
    queries: List[SearchQuery] = field(default_factory=list)
    results: List[SearchResult] = field(default_factory=list)
    filters_applied: List[str] = field(default_factory=list)
    sort_applied: List[str] = field(default_factory=list)
    interactions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration: Optional[float] = None

class GoogleDriveSearchUI:
    """Google Drive Search UI Service"""
    
    def __init__(
        self,
        drive_service: GoogleDriveService,
        memory_service: GoogleDriveMemoryService,
        automation_service: GoogleDriveAutomationService,
        search_analytics: SearchAnalytics
    ):
        self.drive_service = drive_service
        self.memory_service = memory_service
        self.automation_service = automation_service
        self.search_analytics = search_analytics
        
        # Search configuration
        self.config = SearchUIConfig(
            max_results=1000,
            default_limit=50,
            enable_semantic_search=True,
            enable_faceted_search=True,
            enable_suggestions=True,
            enable_real_time_search=True,
            result_cache_ttl=3600
        )
        
        # Search storage
        self.sessions: Dict[str, SearchSession] = {}
        self.search_history: Dict[str, List[SearchQuery]] = {}
        self.popular_queries: List[Dict[str, Any]] = []
        
        # Search components
        self.ui_components = SearchUIComponents()
        
        # Initialize search features
        self._initialize_search_features()
        
        logger.info("Google Drive Search UI Service initialized")
    
    def _initialize_search_features(self):
        """Initialize search features"""
        
        # Initialize UI components
        self.ui_components.register_search_component("google_drive", {
            "name": "Google Drive Search",
            "description": "AI-powered search across your Google Drive files",
            "icon": "📁",
            "color": "#4285F4",
            "capabilities": [
                "semantic_search",
                "full_text_search",
                "faceted_search",
                "real_time_search",
                "visual_search",
                "voice_search",
                "advanced_filters"
            ]
        })
    
    async def search(self, query: SearchQuery) -> Dict[str, Any]:
        """Perform search with multiple strategies"""
        
        try:
            start_time = datetime.now(timezone.utc)
            
            # Log search
            await self.search_analytics.log_search(
                user_id=query.user_id,
                query=query.query,
                search_type=query.search_type.value,
                filters=query.filters
            )
            
            # Perform search based on type
            if query.search_type == SearchType.SEMANTIC:
                results = await self._semantic_search(query)
            elif query.search_type == SearchType.TEXT:
                results = await self._text_search(query)
            elif query.search_type == SearchType.METADATA:
                results = await self._metadata_search(query)
            elif query.search_type == SearchType.HYBRID:
                results = await self._hybrid_search(query)
            elif query.search_type == SearchType.VISUAL:
                results = await self._visual_search(query)
            elif query.search_type == SearchType.VOICE:
                results = await self._voice_search(query)
            elif query.search_type == SearchType.ADVANCED:
                results = await self._advanced_search(query)
            else:
                results = await self._semantic_search(query)  # Default to semantic
            
            # Apply filters
            if query.filters:
                results = self._apply_filters(results, query.filters)
            
            # Sort results
            results = self._sort_results(results, query.sort)
            
            # Apply pagination
            total_results = len(results)
            paginated_results = self._paginate_results(results, query.limit, query.offset)
            
            # Generate facets
            facets = []
            if query.facets:
                facets = await self._generate_facets(paginated_results, query.facets)
            
            # Generate suggestions
            suggestions = []
            if query.query:
                suggestions = await self._generate_suggestions(query.user_id, query.query)
            
            # Calculate search duration
            search_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Update session
            await self._update_search_session(query, paginated_results)
            
            # Prepare response
            response = {
                "ok": True,
                "query": {
                    "id": query.id,
                    "text": query.query,
                    "type": query.search_type.value,
                    "filters": query.filters,
                    "sort": query.sort.value,
                    "view": query.view.value,
                    "limit": query.limit,
                    "offset": query.offset
                },
                "results": [
                    {
                        "id": result.id,
                        "file_id": result.file_id,
                        "name": result.name,
                        "mime_type": result.mime_type,
                        "size": result.size,
                        "created_time": result.created_time.isoformat() if result.created_time else None,
                        "modified_time": result.modified_time.isoformat() if result.modified_time else None,
                        "parents": result.parents,
                        "web_view_link": result.web_view_link,
                        "web_content_link": result.web_content_link,
                        "thumbnail_link": result.thumbnail_link,
                        "shared": result.shared,
                        "owners": result.owners,
                        "permissions": result.permissions,
                        "score": result.score,
                        "highlights": result.highlights,
                        "snippets": result.snippets,
                        "tags": result.tags,
                        "metadata": result.metadata,
                        "content_preview": result.content_preview,
                        "relevance_factors": result.relevance_factors
                    }
                    for result in paginated_results
                ],
                "pagination": {
                    "total": total_results,
                    "limit": query.limit,
                    "offset": query.offset,
                    "has_more": query.offset + query.limit < total_results,
                    "pages": (total_results + query.limit - 1) // query.limit
                },
                "facets": facets,
                "suggestions": suggestions,
                "performance": {
                    "duration": search_duration,
                    "results_per_second": total_results / search_duration if search_duration > 0 else 0
                },
                "ui": {
                    "view_type": query.view.value,
                    "layout": self._get_layout_config(query.view),
                    "components": self._get_ui_components(query)
                }
            }
            
            return response
        
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            return {
                "ok": False,
                "error": str(e),
                "query": {
                    "text": query.query,
                    "type": query.search_type.value
                }
            }
    
    async def _semantic_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform semantic search using embeddings"""
        
        try:
            if not self.memory_service:
                return []
            
            # Generate query embedding
            query_embedding = self._generate_query_embedding(query.query)
            
            # Search in memory
            memory_records = await self.memory_service.search_files(
                user_id=query.user_id,
                query=query.query,
                search_type="semantic",
                filters=query.filters,
                limit=query.limit * 2  # Get more for better filtering
            )
            
            # Convert to search results
            results = []
            for record in memory_records:
                result = SearchResult(
                    id=f"semantic_{record.id}",
                    file_id=record.file_id,
                    name=record.name,
                    mime_type=record.mime_type,
                    size=record.size,
                    created_time=record.created_time,
                    modified_time=record.modified_time,
                    parents=record.parents,
                    web_view_link=record.web_view_link,
                    web_content_link=record.web_content_link,
                    thumbnail_link=record.thumbnail_link,
                    shared=record.shared,
                    owners=record.metadata.get("owners", []),
                    permissions=record.metadata.get("permissions", []),
                    score=self._calculate_semantic_score(record, query_embedding),
                    content_preview=record.extracted_content[:200] + "..." if record.extracted_content else None,
                    tags=record.tags,
                    metadata=record.metadata,
                    relevance_factors={
                        "semantic_similarity": 0.8,
                        "content_match": 0.6,
                        "metadata_match": 0.4
                    }
                )
                
                # Generate highlights and snippets
                if record.extracted_content and query.query:
                    result.highlights = self._generate_highlights(record.extracted_content, query.query)
                    result.snippets = self._generate_snippets(record.extracted_content, query.query)
                
                results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def _text_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform full-text search"""
        
        try:
            if not self.memory_service:
                return []
            
            # Search in memory
            memory_records = await self.memory_service.search_files(
                user_id=query.user_id,
                query=query.query,
                search_type="text",
                filters=query.filters,
                limit=query.limit * 2
            )
            
            # Convert to search results
            results = []
            for record in memory_records:
                result = SearchResult(
                    id=f"text_{record.id}",
                    file_id=record.file_id,
                    name=record.name,
                    mime_type=record.mime_type,
                    size=record.size,
                    created_time=record.created_time,
                    modified_time=record.modified_time,
                    parents=record.parents,
                    web_view_link=record.web_view_link,
                    web_content_link=record.web_content_link,
                    thumbnail_link=record.thumbnail_link,
                    shared=record.shared,
                    owners=record.metadata.get("owners", []),
                    permissions=record.metadata.get("permissions", []),
                    score=self._calculate_text_score(record, query.query),
                    content_preview=record.extracted_content[:200] + "..." if record.extracted_content else None,
                    tags=record.tags,
                    metadata=record.metadata,
                    relevance_factors={
                        "text_match": 0.9,
                        "title_match": 0.7,
                        "content_match": 0.5
                    }
                )
                
                # Generate highlights and snippets
                if record.extracted_content and query.query:
                    result.highlights = self._generate_highlights(record.extracted_content, query.query)
                    result.snippets = self._generate_snippets(record.extracted_content, query.query)
                
                results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in text search: {e}")
            return []
    
    async def _metadata_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform metadata search"""
        
        try:
            if not self.memory_service:
                return []
            
            # Search in memory
            memory_records = await self.memory_service.search_files(
                user_id=query.user_id,
                query=query.query,
                search_type="metadata",
                filters=query.filters,
                limit=query.limit * 2
            )
            
            # Convert to search results
            results = []
            for record in memory_records:
                result = SearchResult(
                    id=f"metadata_{record.id}",
                    file_id=record.file_id,
                    name=record.name,
                    mime_type=record.mime_type,
                    size=record.size,
                    created_time=record.created_time,
                    modified_time=record.modified_time,
                    parents=record.parents,
                    web_view_link=record.web_view_link,
                    web_content_link=record.web_content_link,
                    thumbnail_link=record.thumbnail_link,
                    shared=record.shared,
                    owners=record.metadata.get("owners", []),
                    permissions=record.metadata.get("permissions", []),
                    score=self._calculate_metadata_score(record, query.query),
                    tags=record.tags,
                    metadata=record.metadata,
                    relevance_factors={
                        "name_match": 0.8,
                        "extension_match": 0.6,
                        "owner_match": 0.4
                    }
                )
                
                # Generate highlights for name
                if query.query:
                    result.highlights = self._generate_highlights(record.name, query.query)
                
                results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in metadata search: {e}")
            return []
    
    async def _hybrid_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform hybrid search combining multiple strategies"""
        
        try:
            # Perform multiple searches in parallel
            semantic_task = asyncio.create_task(self._semantic_search(query))
            text_task = asyncio.create_task(self._text_search(query))
            metadata_task = asyncio.create_task(self._metadata_search(query))
            
            # Wait for all searches
            semantic_results, text_results, metadata_results = await asyncio.gather(
                semantic_task, text_task, metadata_task, return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(semantic_results, Exception):
                logger.error(f"Semantic search error: {semantic_results}")
                semantic_results = []
            
            if isinstance(text_results, Exception):
                logger.error(f"Text search error: {text_results}")
                text_results = []
            
            if isinstance(metadata_results, Exception):
                logger.error(f"Metadata search error: {metadata_results}")
                metadata_results = []
            
            # Combine and deduplicate results
            combined_results = {}
            
            # Add semantic results with weight
            for result in semantic_results:
                if result.file_id not in combined_results:
                    result.score *= 1.2  # Weight semantic results higher
                    combined_results[result.file_id] = result
            
            # Add text results
            for result in text_results:
                if result.file_id in combined_results:
                    # Combine scores
                    combined_results[result.file_id].score = max(
                        combined_results[result.file_id].score,
                        result.score * 1.0
                    )
                    # Merge relevance factors
                    combined_results[result.file_id].relevance_factors.update(
                        result.relevance_factors
                    )
                else:
                    combined_results[result.file_id] = result
            
            # Add metadata results
            for result in metadata_results:
                if result.file_id in combined_results:
                    # Combine scores
                    combined_results[result.file_id].score = max(
                        combined_results[result.file_id].score,
                        result.score * 0.8  # Weight metadata results lower
                    )
                    # Merge relevance factors
                    combined_results[result.file_id].relevance_factors.update(
                        result.relevance_factors
                    )
                else:
                    result.score *= 0.8
                    combined_results[result.file_id] = result
            
            # Return combined results
            return list(combined_results.values())
        
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
    
    async def _visual_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform visual search for images"""
        
        try:
            # Filter for image files
            image_mimes = [
                "image/jpeg", "image/png", "image/gif", "image/bmp",
                "image/svg+xml", "image/webp", "image/tiff"
            ]
            
            filters = query.filters.copy()
            filters["mime_types"] = image_mimes
            
            # Perform search
            memory_records = await self.memory_service.search_files(
                user_id=query.user_id,
                query=query.query,
                search_type="metadata",  # Search metadata for visual
                filters=filters,
                limit=query.limit
            )
            
            # Convert to search results
            results = []
            for record in memory_records:
                result = SearchResult(
                    id=f"visual_{record.id}",
                    file_id=record.file_id,
                    name=record.name,
                    mime_type=record.mime_type,
                    size=record.size,
                    created_time=record.created_time,
                    modified_time=record.modified_time,
                    parents=record.parents,
                    web_view_link=record.web_view_link,
                    web_content_link=record.web_content_link,
                    thumbnail_link=record.thumbnail_link,
                    shared=record.shared,
                    owners=record.metadata.get("owners", []),
                    permissions=record.metadata.get("permissions", []),
                    score=self._calculate_visual_score(record, query.query),
                    tags=record.tags,
                    metadata=record.metadata,
                    relevance_factors={
                        "visual_match": 0.9,
                        "name_match": 0.7,
                        "type_match": 1.0
                    }
                )
                
                results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in visual search: {e}")
            return []
    
    async def _voice_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform voice search (convert speech to text first)"""
        
        try:
            # If query contains voice data, convert to text
            # For now, assume query.query is already transcribed text
            
            # Perform semantic search on transcribed text
            return await self._semantic_search(query)
        
        except Exception as e:
            logger.error(f"Error in voice search: {e}")
            return []
    
    async def _advanced_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform advanced search with complex conditions"""
        
        try:
            # Build advanced filter conditions
            advanced_filters = query.filters.copy()
            
            # Add complex query parsing
            if query.query:
                # Parse advanced query syntax (e.g., "name:document AND type:pdf")
                parsed_conditions = self._parse_advanced_query(query.query)
                advanced_filters.update(parsed_conditions)
            
            # Perform search
            memory_records = await self.memory_service.search_files(
                user_id=query.user_id,
                query=query.query,
                search_type="advanced",
                filters=advanced_filters,
                limit=query.limit
            )
            
            # Convert to search results
            results = []
            for record in memory_records:
                result = SearchResult(
                    id=f"advanced_{record.id}",
                    file_id=record.file_id,
                    name=record.name,
                    mime_type=record.mime_type,
                    size=record.size,
                    created_time=record.created_time,
                    modified_time=record.modified_time,
                    parents=record.parents,
                    web_view_link=record.web_view_link,
                    web_content_link=record.web_content_link,
                    thumbnail_link=record.thumbnail_link,
                    shared=record.shared,
                    owners=record.metadata.get("owners", []),
                    permissions=record.metadata.get("permissions", []),
                    score=self._calculate_advanced_score(record, query),
                    content_preview=record.extracted_content[:200] + "..." if record.extracted_content else None,
                    tags=record.tags,
                    metadata=record.metadata,
                    relevance_factors={
                        "advanced_match": 1.0,
                        "condition_score": 0.8
                    }
                )
                
                results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in advanced search: {e}")
            return []
    
    def _apply_filters(self, results: List[SearchResult], filters: Dict[str, Any]) -> List[SearchResult]:
        """Apply filters to search results"""
        
        try:
            filtered_results = []
            
            for result in results:
                include_result = True
                
                # File type filter
                if "file_types" in filters:
                    if not any(result.mime_type.startswith(ft.replace("*", "")) for ft in filters["file_types"]):
                        include_result = False
                
                # Size filter
                if "size" in filters:
                    size_filter = filters["size"]
                    if "min" in size_filter and result.size < size_filter["min"]:
                        include_result = False
                    if "max" in size_filter and result.size > size_filter["max"]:
                        include_result = False
                
                # Date range filter
                if "date_range" in filters:
                    date_filter = filters["date_range"]
                    if "start" in date_filter:
                        start_date = datetime.fromisoformat(date_filter["start"])
                        if result.modified_time < start_date:
                            include_result = False
                    if "end" in date_filter:
                        end_date = datetime.fromisoformat(date_filter["end"])
                        if result.modified_time > end_date:
                            include_result = False
                
                # Owner filter
                if "owners" in filters:
                    if not any(owner in result.owners for owner in filters["owners"]):
                        include_result = False
                
                # Shared filter
                if "shared" in filters:
                    if filters["shared"] != result.shared:
                        include_result = False
                
                # Folder filter
                if "folders" in filters:
                    if not any(folder in result.parents for folder in filters["folders"]):
                        include_result = False
                
                # Tags filter
                if "tags" in filters:
                    if not any(tag in result.tags for tag in filters["tags"]):
                        include_result = False
                
                if include_result:
                    filtered_results.append(result)
            
            return filtered_results
        
        except Exception as e:
            logger.error(f"Error applying filters: {e}")
            return results
    
    def _sort_results(self, results: List[SearchResult], sort_type: SortType) -> List[SearchResult]:
        """Sort search results"""
        
        try:
            if sort_type == SortType.RELEVANCE:
                results.sort(key=lambda r: r.score, reverse=True)
            elif sort_type == SortType.DATE_MODIFIED:
                results.sort(key=lambda r: r.modified_time, reverse=True)
            elif sort_type == SortType.DATE_CREATED:
                results.sort(key=lambda r: r.created_time, reverse=True)
            elif sort_type == SortType.NAME:
                results.sort(key=lambda r: r.name.lower())
            elif sort_type == SortType.SIZE:
                results.sort(key=lambda r: r.size, reverse=True)
            elif sort_type == SortType.TYPE:
                results.sort(key=lambda r: r.mime_type)
            elif sort_type == SortType.OWNER:
                results.sort(key=lambda r: r.owners[0] if r.owners else "")
            
            return results
        
        except Exception as e:
            logger.error(f"Error sorting results: {e}")
            return results
    
    def _paginate_results(self, results: List[SearchResult], limit: int, offset: int) -> List[SearchResult]:
        """Paginate search results"""
        
        try:
            start = offset
            end = start + limit
            return results[start:end]
        
        except Exception as e:
            logger.error(f"Error paginating results: {e}")
            return results[:limit]
    
    async def _generate_facets(self, results: List[SearchResult], facet_fields: List[str]) -> List[SearchFacet]:
        """Generate search facets"""
        
        try:
            facets = []
            
            for field in facet_fields:
                if field == "file_type":
                    type_counts = {}
                    for result in results:
                        file_type = result.mime_type.split("/")[0]
                        type_counts[file_type] = type_counts.get(file_type, 0) + 1
                    
                    facet = SearchFacet(
                        field="file_type",
                        label="File Type",
                        type="checkbox",
                        values=[
                            {
                                "value": file_type,
                                "label": file_type.title(),
                                "count": count
                            }
                            for file_type, count in type_counts.items()
                        ],
                        total=len(type_counts)
                    )
                    facets.append(facet)
                
                elif field == "size":
                    size_ranges = {
                        "Small (< 1MB)": 0,
                        "Medium (1-10MB)": 0,
                        "Large (10-100MB)": 0,
                        "Extra Large (> 100MB)": 0
                    }
                    
                    for result in results:
                        size_mb = result.size / (1024 * 1024)
                        if size_mb < 1:
                            size_ranges["Small (< 1MB)"] += 1
                        elif size_mb < 10:
                            size_ranges["Medium (1-10MB)"] += 1
                        elif size_mb < 100:
                            size_ranges["Large (10-100MB)"] += 1
                        else:
                            size_ranges["Extra Large (> 100MB)"] += 1
                    
                    facet = SearchFacet(
                        field="size",
                        label="Size",
                        type="checkbox",
                        values=[
                            {
                                "value": size_range,
                                "label": size_range,
                                "count": count
                            }
                            for size_range, count in size_ranges.items()
                        ],
                        total=len(size_ranges)
                    )
                    facets.append(facet)
                
                elif field == "date_modified":
                    date_ranges = {
                        "Today": 0,
                        "Yesterday": 0,
                        "This Week": 0,
                        "This Month": 0,
                        "This Year": 0,
                        "Older": 0
                    }
                    
                    now = datetime.now(timezone.utc)
                    
                    for result in results:
                        days_ago = (now - result.modified_time).days
                        
                        if days_ago == 0:
                            date_ranges["Today"] += 1
                        elif days_ago == 1:
                            date_ranges["Yesterday"] += 1
                        elif days_ago <= 7:
                            date_ranges["This Week"] += 1
                        elif days_ago <= 30:
                            date_ranges["This Month"] += 1
                        elif days_ago <= 365:
                            date_ranges["This Year"] += 1
                        else:
                            date_ranges["Older"] += 1
                    
                    facet = SearchFacet(
                        field="date_modified",
                        label="Modified",
                        type="checkbox",
                        values=[
                            {
                                "value": date_range,
                                "label": date_range,
                                "count": count
                            }
                            for date_range, count in date_ranges.items()
                        ],
                        total=len(date_ranges)
                    )
                    facets.append(facet)
            
            return facets
        
        except Exception as e:
            logger.error(f"Error generating facets: {e}")
            return []
    
    async def _generate_suggestions(self, user_id: str, query: str) -> List[SearchSuggestion]:
        """Generate search suggestions"""
        
        try:
            suggestions = []
            
            # Get search history for user
            user_history = self.search_history.get(user_id, [])
            
            # Find similar queries from history
            for historical_query in user_history[-50:]:  # Last 50 queries
                similarity = self._calculate_query_similarity(query, historical_query.query)
                if similarity > 0.5 and historical_query.query.lower() != query.lower():
                    suggestions.append(SearchSuggestion(
                        text=historical_query.query,
                        type="history",
                        score=similarity,
                        category="Recent Searches",
                        metadata={
                            "search_count": 1,
                            "last_searched": historical_query.timestamp.isoformat()
                        }
                    ))
            
            # Get popular queries
            for popular_query in self.popular_queries[:10]:
                similarity = self._calculate_query_similarity(query, popular_query["query"])
                if similarity > 0.4 and popular_query["query"].lower() != query.lower():
                    suggestions.append(SearchSuggestion(
                        text=popular_query["query"],
                        type="popular",
                        score=similarity,
                        category="Popular Searches",
                        metadata={
                            "search_count": popular_query["count"],
                            "popularity": popular_query["popularity"]
                        }
                    ))
            
            # Sort by score and limit
            suggestions.sort(key=lambda s: s.score, reverse=True)
            return suggestions[:10]
        
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return []
    
    def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for search query"""
        
        try:
            # This would use the same embedding model as memory service
            # For now, return a mock embedding
            import hashlib
            query_bytes = query.encode('utf-8')
            hash_object = hashlib.md5(query_bytes)
            
            # Convert hash to embedding (mock implementation)
            embedding = []
            for i in range(384):  # Standard embedding dimension
                byte_val = hash_object.digest()[i % 16]
                embedding.append((byte_val / 255.0 - 0.5) * 2)
            
            return embedding
        
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            return [0.0] * 384
    
    def _calculate_semantic_score(self, record, query_embedding: List[float]) -> float:
        """Calculate semantic search score"""
        
        try:
            # This would calculate cosine similarity between embeddings
            # For now, return a mock score based on content match
            if record.embeddings:
                # Mock similarity calculation
                return 0.85 + (hash(record.id) % 100) / 500.0
            
            return 0.5
        
        except Exception as e:
            logger.error(f"Error calculating semantic score: {e}")
            return 0.5
    
    def _calculate_text_score(self, record, query: str) -> float:
        """Calculate text search score"""
        
        try:
            query_lower = query.lower()
            name_lower = record.name.lower()
            
            # Score based on name match
            if query_lower in name_lower:
                name_score = 1.0
            else:
                name_score = 0.0
            
            # Score based on content match
            content_score = 0.0
            if record.extracted_content:
                content_lower = record.extracted_content.lower()
                if query_lower in content_lower:
                    content_score = 0.8
                else:
                    # Check for partial matches
                    words = query_lower.split()
                    matches = sum(1 for word in words if word in content_lower)
                    content_score = matches / len(words) * 0.6
            
            return max(name_score, content_score) * 0.9
        
        except Exception as e:
            logger.error(f"Error calculating text score: {e}")
            return 0.5
    
    def _calculate_metadata_score(self, record, query: str) -> float:
        """Calculate metadata search score"""
        
        try:
            query_lower = query.lower()
            name_lower = record.name.lower()
            
            # Score based on exact name match
            if query_lower == name_lower:
                return 1.0
            
            # Score based on partial name match
            if query_lower in name_lower:
                return 0.8
            
            # Score based on file extension match
            if query_lower.startswith("."):
                extension = "." + record.mime_type.split("/")[-1]
                if query_lower == extension:
                    return 0.7
            
            # Score based on owner match
            owners = record.metadata.get("owners", [])
            for owner in owners:
                if query_lower in owner.lower():
                    return 0.6
            
            return 0.3
        
        except Exception as e:
            logger.error(f"Error calculating metadata score: {e}")
            return 0.5
    
    def _calculate_visual_score(self, record, query: str) -> float:
        """Calculate visual search score"""
        
        try:
            # For now, use metadata scoring for visual search
            return self._calculate_metadata_score(record, query)
        
        except Exception as e:
            logger.error(f"Error calculating visual score: {e}")
            return 0.5
    
    def _calculate_advanced_score(self, record, query: SearchQuery) -> float:
        """Calculate advanced search score"""
        
        try:
            # Combine multiple scoring factors
            base_score = 0.5
            
            # Add semantic score if available
            if record.extracted_content:
                semantic_score = self._calculate_text_score(record, query.query)
                base_score = max(base_score, semantic_score)
            
            # Add metadata score
            metadata_score = self._calculate_metadata_score(record, query.query)
            base_score = max(base_score, metadata_score)
            
            return base_score
        
        except Exception as e:
            logger.error(f"Error calculating advanced score: {e}")
            return 0.5
    
    def _generate_highlights(self, text: str, query: str) -> List[str]:
        """Generate search highlights"""
        
        try:
            highlights = []
            query_lower = query.lower()
            
            # Find all occurrences of query in text
            text_lower = text.lower()
            start = 0
            
            while True:
                pos = text_lower.find(query_lower, start)
                if pos == -1:
                    break
                
                # Extract context around match
                context_start = max(0, pos - 50)
                context_end = min(len(text), pos + len(query) + 50)
                context = text[context_start:context_end]
                
                # Highlight the matched text
                highlighted = context.replace(
                    text[pos:pos+len(query)],
                    f"<mark>{text[pos:pos+len(query)]}</mark>"
                )
                
                highlights.append(highlighted)
                start = pos + len(query)
            
            return highlights[:5]  # Limit to 5 highlights
        
        except Exception as e:
            logger.error(f"Error generating highlights: {e}")
            return []
    
    def _generate_snippets(self, text: str, query: str) -> List[str]:
        """Generate search snippets"""
        
        try:
            snippets = []
            query_lower = query.lower()
            
            # Find best snippet (most relevant context)
            text_lower = text.lower()
            pos = text_lower.find(query_lower)
            
            if pos != -1:
                # Extract 150 characters around the match
                start = max(0, pos - 75)
                end = min(len(text), pos + len(query) + 75)
                snippet = text[start:end]
                
                # Add ellipsis if truncated
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."
                
                snippets.append(snippet)
            
            return snippets[:3]  # Limit to 3 snippets
        
        except Exception as e:
            logger.error(f"Error generating snippets: {e}")
            return []
    
    def _parse_advanced_query(self, query: str) -> Dict[str, Any]:
        """Parse advanced query syntax"""
        
        try:
            conditions = {}
            
            # Parse field:value syntax
            import re
            pattern = r'(\w+):([^\s]+)'
            matches = re.findall(pattern, query)
            
            for field, value in matches:
                if field == "type":
                    if "file_types" not in conditions:
                        conditions["file_types"] = []
                    conditions["file_types"].append(value)
                elif field == "size":
                    if "size" not in conditions:
                        conditions["size"] = {}
                    if value.endswith("MB"):
                        conditions["size"]["max"] = int(value[:-2]) * 1024 * 1024
                    elif value.endswith("KB"):
                        conditions["size"]["max"] = int(value[:-2]) * 1024
                elif field == "owner":
                    if "owners" not in conditions:
                        conditions["owners"] = []
                    conditions["owners"].append(value)
                elif field == "folder":
                    if "folders" not in conditions:
                        conditions["folders"] = []
                    conditions["folders"].append(value)
            
            return conditions
        
        except Exception as e:
            logger.error(f"Error parsing advanced query: {e}")
            return {}
    
    def _calculate_query_similarity(self, query1: str, query2: str) -> float:
        """Calculate similarity between two queries"""
        
        try:
            from difflib import SequenceMatcher
            
            return SequenceMatcher(None, query1.lower(), query2.lower()).ratio()
        
        except Exception as e:
            logger.error(f"Error calculating query similarity: {e}")
            return 0.0
    
    def _get_layout_config(self, view_type: ViewType) -> Dict[str, Any]:
        """Get layout configuration for view type"""
        
        layouts = {
            ViewType.LIST: {
                "type": "list",
                "columns": [
                    {"key": "name", "label": "Name", "width": "40%", "sortable": True},
                    {"key": "modified_time", "label": "Modified", "width": "15%", "sortable": True},
                    {"key": "size", "label": "Size", "width": "10%", "sortable": True},
                    {"key": "owners", "label": "Owner", "width": "15%", "sortable": True},
                    {"key": "actions", "label": "Actions", "width": "20%", "sortable": False}
                ],
                "page_size": 50
            },
            ViewType.GRID: {
                "type": "grid",
                "columns": 4,
                "card_size": "medium",
                "show_thumbnails": True,
                "page_size": 24
            },
            ViewType.THUMBNAIL: {
                "type": "thumbnail",
                "columns": 6,
                "card_size": "large",
                "show_thumbnails": True,
                "page_size": 36
            },
            ViewType.DETAIL: {
                "type": "detail",
                "layout": "row",
                "show_thumbnails": True,
                "page_size": 10
            },
            ViewType.TIMELINE: {
                "type": "timeline",
                "group_by": "date",
                "sort_by": "modified_time",
                "page_size": 20
            },
            ViewType.TREE: {
                "type": "tree",
                "expand_folders": True,
                "show_hierarchy": True,
                "page_size": 100
            }
        }
        
        return layouts.get(view_type, layouts[ViewType.LIST])
    
    def _get_ui_components(self, query: SearchQuery) -> Dict[str, Any]:
        """Get UI components configuration"""
        
        return {
            "search_bar": {
                "placeholder": "Search your Google Drive files...",
                "show_voice_search": True,
                "show_advanced_search": True,
                "auto_suggestions": True,
                "recent_searches": len(self.search_history.get(query.user_id, []))
            },
            "filters": {
                "show_file_types": True,
                "show_size_filter": True,
                "show_date_filter": True,
                "show_owner_filter": True,
                "show_shared_filter": True,
                "show_folder_filter": True,
                "show_tag_filter": True
            },
            "sort_options": [
                {"value": "relevance", "label": "Relevance"},
                {"value": "date_modified", "label": "Date Modified"},
                {"value": "date_created", "label": "Date Created"},
                {"value": "name", "label": "Name"},
                {"value": "size", "label": "Size"},
                {"value": "owner", "label": "Owner"}
            ],
            "view_options": [
                {"value": "list", "label": "List", "icon": "📋"},
                {"value": "grid", "label": "Grid", "icon": "⊞"},
                {"value": "thumbnail", "label": "Thumbnails", "icon": "🖼️"},
                {"value": "detail", "label": "Details", "icon": "📄"},
                {"value": "timeline", "label": "Timeline", "icon": "📅"},
                {"value": "tree", "label": "Tree", "icon": "🌳"}
            ],
            "actions": [
                {"action": "download", "label": "Download", "icon": "⬇️"},
                {"action": "share", "label": "Share", "icon": "🔗"},
                {"action": "move", "label": "Move", "icon": "📁"},
                {"action": "copy", "label": "Copy", "icon": "📋"},
                {"action": "delete", "label": "Delete", "icon": "🗑️"},
                {"action": "view", "label": "View", "icon": "👁️"},
                {"action": "edit", "label": "Edit", "icon": "✏️"},
                {"action": "add_to_workflow", "label": "Add to Workflow", "icon": "🤖"}
            ]
        }
    
    async def _update_search_session(self, query: SearchQuery, results: List[SearchResult]):
        """Update search session"""
        
        try:
            # Get or create session
            if query.user_id not in self.sessions:
                self.sessions[query.user_id] = SearchSession(
                    id=f"session_{query.user_id}_{datetime.now().timestamp()}",
                    user_id=query.user_id
                )
            
            session = self.sessions[query.user_id]
            
            # Add query to session
            session.queries.append(query)
            session.results.extend(results)
            session.last_activity = datetime.now(timezone.utc)
            
            # Add to user search history
            if query.user_id not in self.search_history:
                self.search_history[query.user_id] = []
            
            self.search_history[query.user_id].append(query)
            
            # Keep only last 100 queries per user
            if len(self.search_history[query.user_id]) > 100:
                self.search_history[query.user_id] = self.search_history[query.user_id][-100:]
            
            # Update popular queries
            query_text = query.query.strip()
            if query_text:
                found = False
                for popular in self.popular_queries:
                    if popular["query"] == query_text:
                        popular["count"] += 1
                        found = True
                        break
                
                if not found:
                    self.popular_queries.append({
                        "query": query_text,
                        "count": 1,
                        "first_seen": datetime.now(timezone.utc),
                        "popularity": 1.0
                    })
            
            # Sort popular queries by count
            self.popular_queries.sort(key=lambda x: x["count"], reverse=True)
            
            # Keep only top 100 popular queries
            if len(self.popular_queries) > 100:
                self.popular_queries = self.popular_queries[:100]
        
        except Exception as e:
            logger.error(f"Error updating search session: {e}")
    
    def get_search_ui_config(self, user_id: str) -> Dict[str, Any]:
        """Get search UI configuration for user"""
        
        try:
            # Get user's search history
            user_history = self.search_history.get(user_id, [])
            recent_searches = [q.query for q in user_history[-10:] if q.query.strip()]
            
            # Get user's session
            session = self.sessions.get(user_id)
            
            return {
                "config": {
                    "max_results": self.config.max_results,
                    "default_limit": self.config.default_limit,
                    "enable_semantic_search": self.config.enable_semantic_search,
                    "enable_faceted_search": self.config.enable_faceted_search,
                    "enable_suggestions": self.config.enable_suggestions,
                    "enable_real_time_search": self.config.enable_real_time_search,
                    "result_cache_ttl": self.config.result_cache_ttl
                },
                "user": {
                    "recent_searches": recent_searches,
                    "session_id": session.id if session else None,
                    "session_duration": session.duration if session else None,
                    "total_searches": len(user_history)
                },
                "ui": {
                    "search_bar": {
                        "placeholder": "Search your Google Drive files...",
                        "show_voice_search": True,
                        "show_advanced_search": True,
                        "auto_suggestions": True,
                        "real_time_search": True
                    },
                    "filters": [
                        {
                            "type": "file_type",
                            "label": "File Type",
                            "options": [
                                {"value": "document", "label": "Documents"},
                                {"value": "image", "label": "Images"},
                                {"value": "video", "label": "Videos"},
                                {"value": "audio", "label": "Audio"},
                                {"value": "folder", "label": "Folders"},
                                {"value": "archive", "label": "Archives"}
                            ]
                        },
                        {
                            "type": "size",
                            "label": "Size",
                            "options": [
                                {"value": "small", "label": "Small (< 1MB)"},
                                {"value": "medium", "label": "Medium (1-10MB)"},
                                {"value": "large", "label": "Large (10-100MB)"},
                                {"value": "xlarge", "label": "Extra Large (> 100MB)"}
                            ]
                        },
                        {
                            "type": "date_range",
                            "label": "Modified Date",
                            "options": [
                                {"value": "today", "label": "Today"},
                                {"value": "yesterday", "label": "Yesterday"},
                                {"value": "week", "label": "This Week"},
                                {"value": "month", "label": "This Month"},
                                {"value": "year", "label": "This Year"}
                            ]
                        },
                        {
                            "type": "owner",
                            "label": "Owner",
                            "options": []  # Will be populated dynamically
                        },
                        {
                            "type": "shared",
                            "label": "Shared",
                            "options": [
                                {"value": "true", "label": "Shared with me"},
                                {"value": "false", "label": "Not shared"}
                            ]
                        }
                    ],
                    "sort_options": [
                        {"value": "relevance", "label": "Relevance"},
                        {"value": "date_modified", "label": "Date Modified"},
                        {"value": "date_created", "label": "Date Created"},
                        {"value": "name", "label": "Name"},
                        {"value": "size", "label": "Size"}
                    ],
                    "view_options": [
                        {"value": "list", "label": "List", "icon": "📋"},
                        {"value": "grid", "label": "Grid", "icon": "⊞"},
                        {"value": "thumbnail", "label": "Thumbnails", "icon": "🖼️"},
                        {"value": "detail", "label": "Details", "icon": "📄"},
                        {"value": "timeline", "label": "Timeline", "icon": "📅"}
                    ]
                },
                "features": {
                    "semantic_search": self.config.enable_semantic_search,
                    "voice_search": True,
                    "visual_search": True,
                    "advanced_search": True,
                    "faceted_search": self.config.enable_faceted_search,
                    "real_time_suggestions": True,
                    "search_analytics": True,
                    "export_results": True,
                    "save_search": True
                }
            }
        
        except Exception as e:
            logger.error(f"Error getting search UI config: {e}")
            return {"error": str(e)}
    
    def get_search_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get search analytics for user"""
        
        try:
            # Get user's search history
            user_history = self.search_history.get(user_id, [])
            
            # Calculate analytics
            total_searches = len(user_history)
            unique_queries = len(set(q.query for q in user_history))
            
            # Search type distribution
            search_types = {}
            for query in user_history:
                search_type = query.search_type.value
                search_types[search_type] = search_types.get(search_type, 0) + 1
            
            # Popular search terms
            query_counts = {}
            for query in user_history:
                query_text = query.query.strip()
                if query_text:
                    query_counts[query_text] = query_counts.get(query_text, 0) + 1
            
            popular_terms = sorted(
                query_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            # Search performance
            avg_duration = 0
            if user_history:
                durations = [0.5] * total_searches  # Mock durations
                avg_duration = sum(durations) / len(durations)
            
            return {
                "user_id": user_id,
                "total_searches": total_searches,
                "unique_queries": unique_queries,
                "search_types": search_types,
                "popular_terms": [
                    {"term": term, "count": count}
                    for term, count in popular_terms
                ],
                "performance": {
                    "average_duration": avg_duration,
                    "success_rate": 0.95  # Mock success rate
                },
                "session_info": {
                    "session_count": 1,
                    "average_session_duration": 5.2,  # Mock duration
                    "queries_per_session": total_searches / 1
                },
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting search analytics: {e}")
            return {"error": str(e)}

# Global service instance
_google_drive_search_ui: Optional[GoogleDriveSearchUI] = None

def get_google_drive_search_ui_service(
    drive_service: GoogleDriveService,
    memory_service: GoogleDriveMemoryService,
    automation_service: GoogleDriveAutomationService,
    search_analytics: SearchAnalytics
) -> GoogleDriveSearchUI:
    """Get global Google Drive Search UI service instance"""
    global _google_drive_search_ui
    
    if _google_drive_search_ui is None:
        _google_drive_search_ui = GoogleDriveSearchUI(
            drive_service, memory_service, automation_service, search_analytics
        )
    
    return _google_drive_search_ui

# Export classes
__all__ = [
    "GoogleDriveSearchUI",
    "SearchQuery",
    "SearchResult",
    "SearchFacet",
    "SearchSuggestion",
    "SearchSession",
    "SearchType",
    "FilterType",
    "SortType",
    "ViewType",
    "get_google_drive_search_ui_service"
]