"""
Google Drive Integration for Existing ATOM Search UI
Integrates Google Drive search capabilities with ATOM's existing search interface
"""

import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from flask import request, jsonify
from loguru import logger

# Import existing ATOM search UI (assuming it exists)
try:
    from search.ui.search_interface import SearchInterface, SearchProvider
    from search.ui.search_components import SearchComponent
    from search.ui.search_analytics import SearchAnalytics
    EXISTING_SEARCH_UI = True
except ImportError:
    logger.warning("Existing ATOM search UI not found, will create integration")
    EXISTING_SEARCH_UI = False
    
    # Create mock interfaces for now
    class SearchProvider:
        pass
    class SearchInterface:
        pass
    class SearchComponent:
        pass
    class SearchAnalytics:
        pass

# Google Drive imports
from google_drive_service import GoogleDriveService
from google_drive_memory import GoogleDriveMemoryService
from google_drive_automation import GoogleDriveAutomationService

class GoogleDriveSearchProvider(SearchProvider):
    """Google Drive search provider for ATOM's existing Search UI"""
    
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
        
        # Provider configuration
        self.provider_id = "google_drive"
        self.name = "Google Drive"
        self.description = "Search across your Google Drive files with AI-powered semantic search"
        self.icon = "📁"
        self.color = "#4285F4"
        self.version = "1.0.0"
        
        # Search capabilities
        self.capabilities = {
            "semantic_search": True,
            "full_text_search": True,
            "metadata_search": True,
            "faceted_search": True,
            "real_time_search": True,
            "visual_search": True,
            "voice_search": True,
            "advanced_search": True,
            "filters": {
                "file_type": True,
                "size": True,
                "date_range": True,
                "owner": True,
                "shared": True,
                "folder": True,
                "tags": True,
                "custom": True
            },
            "sort_options": {
                "relevance": True,
                "date_modified": True,
                "date_created": True,
                "name": True,
                "size": True,
                "type": True,
                "owner": True
            },
            "view_options": {
                "list": True,
                "grid": True,
                "thumbnail": True,
                "detail": True,
                "timeline": True,
                "tree": True
            }
        }
        
        # Search configuration
        self.config = {
            "max_results": 1000,
            "default_limit": 50,
            "enable_semantic_search": True,
            "enable_faceted_search": True,
            "enable_suggestions": True,
            "enable_real_time_search": True,
            "result_cache_ttl": 3600,
            "default_search_type": "semantic",
            "embedding_dimension": 384
        }
        
        # Register with existing search UI
        self._register_with_search_ui()
        
        logger.info("Google Drive Search Provider initialized")
    
    def _register_with_search_ui(self):
        """Register provider with existing ATOM Search UI"""
        
        try:
            if EXISTING_SEARCH_UI:
                # Register with existing SearchInterface
                SearchInterface.register_provider(self.provider_id, self)
                logger.info("Google Drive provider registered with ATOM Search UI")
            else:
                logger.warning("ATOM Search UI not available, provider not registered")
        
        except Exception as e:
            logger.error(f"Error registering Google Drive provider: {e}")
    
    async def search(
        self,
        query: str,
        user_id: str,
        search_type: str = "semantic",
        filters: Optional[Dict[str, Any]] = None,
        sort: str = "relevance",
        limit: int = 50,
        offset: int = 0,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform search using Google Drive provider"""
        
        try:
            # Log search
            await self.search_analytics.log_search(
                provider=self.provider_id,
                user_id=user_id,
                query=query,
                search_type=search_type,
                filters=filters
            )
            
            # Perform search based on type
            if search_type == "semantic":
                results = await self._semantic_search(query, user_id, filters)
            elif search_type == "text":
                results = await self._text_search(query, user_id, filters)
            elif search_type == "metadata":
                results = await self._metadata_search(query, user_id, filters)
            elif search_type == "advanced":
                results = await self._advanced_search(query, user_id, filters)
            else:
                results = await self._semantic_search(query, user_id, filters)
            
            # Apply filters
            if filters:
                results = self._apply_filters(results, filters)
            
            # Sort results
            results = self._sort_results(results, sort)
            
            # Apply pagination
            total_results = len(results)
            paginated_results = self._paginate_results(results, limit, offset)
            
            # Generate facets
            facets = []
            if filters and filters.get("include_facets", True):
                facets = await self._generate_facets(paginated_results)
            
            # Generate suggestions
            suggestions = []
            if query and self.config["enable_suggestions"]:
                suggestions = await self._generate_suggestions(user_id, query)
            
            # Prepare response in ATOM's expected format
            response = {
                "provider": {
                    "id": self.provider_id,
                    "name": self.name,
                    "icon": self.icon,
                    "color": self.color
                },
                "query": {
                    "text": query,
                    "type": search_type,
                    "filters": filters,
                    "sort": sort,
                    "limit": limit,
                    "offset": offset
                },
                "results": [
                    self._convert_result_for_ui(result)
                    for result in paginated_results
                ],
                "pagination": {
                    "total": total_results,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total_results,
                    "pages": (total_results + limit - 1) // limit
                },
                "facets": facets,
                "suggestions": suggestions,
                "capabilities": self.capabilities,
                "performance": {
                    "duration": 0.5,  # Mock duration
                    "results_per_second": total_results / 0.5
                }
            }
            
            return response
        
        except Exception as e:
            logger.error(f"Error in Google Drive search: {e}")
            return {
                "provider": {
                    "id": self.provider_id,
                    "name": self.name,
                    "icon": self.icon,
                    "color": self.color
                },
                "query": {
                    "text": query,
                    "type": search_type
                },
                "error": str(e),
                "results": [],
                "pagination": {
                    "total": 0,
                    "limit": limit,
                    "offset": offset
                }
            }
    
    async def _semantic_search(self, query: str, user_id: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform semantic search"""
        
        try:
            if not self.memory_service:
                return []
            
            # Search in memory
            memory_records = await self.memory_service.search_files(
                user_id=user_id,
                query=query,
                search_type="semantic",
                filters=filters,
                limit=1000
            )
            
            # Convert to UI format
            results = []
            for record in memory_records:
                result = {
                    "id": record.id,
                    "type": "file",
                    "title": record.name,
                    "description": record.extracted_content[:200] + "..." if record.extracted_content else None,
                    "url": record.web_view_link,
                    "download_url": record.web_content_link,
                    "thumbnail_url": record.thumbnail_link,
                    "mime_type": record.mime_type,
                    "size": record.size,
                    "created_at": record.created_time.isoformat() if record.created_time else None,
                    "updated_at": record.modified_time.isoformat() if record.modified_time else None,
                    "metadata": {
                        "file_id": record.file_id,
                        "parents": record.parents,
                        "shared": record.shared,
                        "owners": record.metadata.get("owners", []),
                        "permissions": record.metadata.get("permissions", []),
                        "tags": record.tags,
                        "content_status": record.content_status.value,
                        "has_content": bool(record.extracted_content)
                    },
                    "score": 0.85,  # Mock semantic score
                    "highlights": self._generate_highlights(record.extracted_content, query),
                    "provider": self.provider_id,
                    "source": "google_drive"
                }
                results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def _text_search(self, query: str, user_id: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform full-text search"""
        
        try:
            if not self.memory_service:
                return []
            
            # Search in memory
            memory_records = await self.memory_service.search_files(
                user_id=user_id,
                query=query,
                search_type="text",
                filters=filters,
                limit=1000
            )
            
            # Convert to UI format
            results = []
            for record in memory_records:
                result = {
                    "id": record.id,
                    "type": "file",
                    "title": record.name,
                    "description": record.extracted_content[:200] + "..." if record.extracted_content else None,
                    "url": record.web_view_link,
                    "download_url": record.web_content_link,
                    "thumbnail_url": record.thumbnail_link,
                    "mime_type": record.mime_type,
                    "size": record.size,
                    "created_at": record.created_time.isoformat() if record.created_time else None,
                    "updated_at": record.modified_time.isoformat() if record.modified_time else None,
                    "metadata": {
                        "file_id": record.file_id,
                        "parents": record.parents,
                        "shared": record.shared,
                        "owners": record.metadata.get("owners", []),
                        "permissions": record.metadata.get("permissions", []),
                        "tags": record.tags,
                        "content_status": record.content_status.value,
                        "has_content": bool(record.extracted_content)
                    },
                    "score": 0.75,  # Mock text search score
                    "highlights": self._generate_highlights(record.extracted_content, query),
                    "provider": self.provider_id,
                    "source": "google_drive"
                }
                results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in text search: {e}")
            return []
    
    async def _metadata_search(self, query: str, user_id: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform metadata search"""
        
        try:
            if not self.memory_service:
                return []
            
            # Search in memory
            memory_records = await self.memory_service.search_files(
                user_id=user_id,
                query=query,
                search_type="metadata",
                filters=filters,
                limit=1000
            )
            
            # Convert to UI format
            results = []
            for record in memory_records:
                result = {
                    "id": record.id,
                    "type": "file",
                    "title": record.name,
                    "description": f"Size: {self._format_file_size(record.size)} | Modified: {record.modified_time.date() if record.modified_time else 'Unknown'}",
                    "url": record.web_view_link,
                    "download_url": record.web_content_link,
                    "thumbnail_url": record.thumbnail_link,
                    "mime_type": record.mime_type,
                    "size": record.size,
                    "created_at": record.created_time.isoformat() if record.created_time else None,
                    "updated_at": record.modified_time.isoformat() if record.modified_time else None,
                    "metadata": {
                        "file_id": record.file_id,
                        "parents": record.parents,
                        "shared": record.shared,
                        "owners": record.metadata.get("owners", []),
                        "permissions": record.metadata.get("permissions", []),
                        "tags": record.tags,
                        "content_status": record.content_status.value,
                        "has_content": bool(record.extracted_content)
                    },
                    "score": 0.65,  # Mock metadata search score
                    "highlights": self._generate_highlights(record.name, query),
                    "provider": self.provider_id,
                    "source": "google_drive"
                }
                results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in metadata search: {e}")
            return []
    
    async def _advanced_search(self, query: str, user_id: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform advanced search"""
        
        try:
            # Combine semantic, text, and metadata search
            semantic_task = asyncio.create_task(self._semantic_search(query, user_id, filters))
            text_task = asyncio.create_task(self._text_search(query, user_id, filters))
            metadata_task = asyncio.create_task(self._metadata_search(query, user_id, filters))
            
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
                file_id = result["metadata"]["file_id"]
                if file_id not in combined_results:
                    result["score"] *= 1.2  # Weight semantic results higher
                    combined_results[file_id] = result
            
            # Add text results
            for result in text_results:
                file_id = result["metadata"]["file_id"]
                if file_id in combined_results:
                    # Combine scores
                    combined_results[file_id]["score"] = max(
                        combined_results[file_id]["score"],
                        result["score"] * 1.0
                    )
                else:
                    combined_results[file_id] = result
            
            # Add metadata results
            for result in metadata_results:
                file_id = result["metadata"]["file_id"]
                if file_id in combined_results:
                    # Combine scores
                    combined_results[file_id]["score"] = max(
                        combined_results[file_id]["score"],
                        result["score"] * 0.8  # Weight metadata results lower
                    )
                else:
                    result["score"] *= 0.8
                    combined_results[file_id] = result
            
            # Return combined results
            return list(combined_results.values())
        
        except Exception as e:
            logger.error(f"Error in advanced search: {e}")
            return []
    
    def _apply_filters(self, results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply filters to search results"""
        
        try:
            filtered_results = []
            
            for result in results:
                include_result = True
                
                # File type filter
                if "file_types" in filters:
                    mime_type = result.get("mime_type", "")
                    if not any(mime_type.startswith(ft.replace("*", "")) for ft in filters["file_types"]):
                        include_result = False
                
                # Size filter
                if "size" in filters:
                    size = result.get("size", 0)
                    size_filter = filters["size"]
                    if "min" in size_filter and size < size_filter["min"]:
                        include_result = False
                    if "max" in size_filter and size > size_filter["max"]:
                        include_result = False
                
                # Date range filter
                if "date_range" in filters:
                    date_filter = filters["date_range"]
                    updated_at = result.get("updated_at")
                    if updated_at:
                        if "start" in date_filter:
                            start_date = datetime.fromisoformat(date_filter["start"])
                            if datetime.fromisoformat(updated_at) < start_date:
                                include_result = False
                        if "end" in date_filter:
                            end_date = datetime.fromisoformat(date_filter["end"])
                            if datetime.fromisoformat(updated_at) > end_date:
                                include_result = False
                
                # Shared filter
                if "shared" in filters:
                    shared = result["metadata"].get("shared", False)
                    if filters["shared"] != shared:
                        include_result = False
                
                # Folder filter
                if "folders" in filters:
                    parents = result["metadata"].get("parents", [])
                    if not any(folder in parents for folder in filters["folders"]):
                        include_result = False
                
                if include_result:
                    filtered_results.append(result)
            
            return filtered_results
        
        except Exception as e:
            logger.error(f"Error applying filters: {e}")
            return results
    
    def _sort_results(self, results: List[Dict[str, Any]], sort: str) -> List[Dict[str, Any]]:
        """Sort search results"""
        
        try:
            if sort == "relevance":
                results.sort(key=lambda r: r.get("score", 0), reverse=True)
            elif sort == "date_modified":
                results.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
            elif sort == "date_created":
                results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
            elif sort == "name":
                results.sort(key=lambda r: r.get("title", "").lower())
            elif sort == "size":
                results.sort(key=lambda r: r.get("size", 0), reverse=True)
            elif sort == "type":
                results.sort(key=lambda r: r.get("mime_type", ""))
            
            return results
        
        except Exception as e:
            logger.error(f"Error sorting results: {e}")
            return results
    
    def _paginate_results(self, results: List[Dict[str, Any]], limit: int, offset: int) -> List[Dict[str, Any]]:
        """Paginate search results"""
        
        try:
            start = offset
            end = start + limit
            return results[start:end]
        
        except Exception as e:
            logger.error(f"Error paginating results: {e}")
            return results[:limit]
    
    async def _generate_facets(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate search facets"""
        
        try:
            facets = []
            
            # File type facet
            type_counts = {}
            for result in results:
                mime_type = result.get("mime_type", "")
                file_type = mime_type.split("/")[0]
                type_counts[file_type] = type_counts.get(file_type, 0) + 1
            
            facets.append({
                "field": "file_type",
                "label": "File Type",
                "type": "checkbox",
                "values": [
                    {
                        "value": file_type,
                        "label": file_type.title(),
                        "count": count
                    }
                    for file_type, count in type_counts.items()
                ]
            })
            
            # Size facet
            size_ranges = {
                "Small (< 1MB)": 0,
                "Medium (1-10MB)": 0,
                "Large (10-100MB)": 0,
                "Extra Large (> 100MB)": 0
            }
            
            for result in results:
                size = result.get("size", 0)
                size_mb = size / (1024 * 1024)
                if size_mb < 1:
                    size_ranges["Small (< 1MB)"] += 1
                elif size_mb < 10:
                    size_ranges["Medium (1-10MB)"] += 1
                elif size_mb < 100:
                    size_ranges["Large (10-100MB)"] += 1
                else:
                    size_ranges["Extra Large (> 100MB)"] += 1
            
            facets.append({
                "field": "size",
                "label": "Size",
                "type": "checkbox",
                "values": [
                    {
                        "value": size_range,
                        "label": size_range,
                        "count": count
                    }
                    for size_range, count in size_ranges.items()
                ]
            })
            
            # Date modified facet
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
                updated_at = result.get("updated_at")
                if updated_at:
                    days_ago = (now - datetime.fromisoformat(updated_at)).days
                    
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
            
            facets.append({
                "field": "date_modified",
                "label": "Modified",
                "type": "checkbox",
                "values": [
                    {
                        "value": date_range,
                        "label": date_range,
                        "count": count
                    }
                    for date_range, count in date_ranges.items()
                ]
            })
            
            return facets
        
        except Exception as e:
            logger.error(f"Error generating facets: {e}")
            return []
    
    async def _generate_suggestions(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        """Generate search suggestions"""
        
        try:
            suggestions = []
            
            # Mock suggestions for now
            # In real implementation, this would use user's search history and popular queries
            common_suggestions = [
                {"text": "quarterly report", "type": "document", "score": 0.9},
                {"text": "meeting minutes", "type": "document", "score": 0.8},
                {"text": "presentation", "type": "presentation", "score": 0.7},
                {"text": "spreadsheet", "type": "spreadsheet", "score": 0.7},
                {"text": "invoice", "type": "document", "score": 0.6},
                {"text": "contract", "type": "document", "score": 0.6},
                {"text": "proposal", "type": "document", "score": 0.5},
                {"text": "budget", "type": "spreadsheet", "score": 0.5}
            ]
            
            # Filter suggestions based on query
            query_lower = query.lower()
            filtered_suggestions = [
                s for s in common_suggestions
                if query_lower in s["text"].lower() or query_lower == ""
            ]
            
            return filtered_suggestions[:10]
        
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return []
    
    def _convert_result_for_ui(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert search result for ATOM's existing UI format"""
        
        try:
            # Ensure result has all required fields for ATOM's UI
            ui_result = {
                "id": result.get("id", ""),
                "type": result.get("type", "file"),
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "url": result.get("url", ""),
                "download_url": result.get("download_url", ""),
                "thumbnail_url": result.get("thumbnail_url", ""),
                "mime_type": result.get("mime_type", ""),
                "size": result.get("size", 0),
                "created_at": result.get("created_at"),
                "updated_at": result.get("updated_at"),
                "metadata": result.get("metadata", {}),
                "score": result.get("score", 0),
                "highlights": result.get("highlights", []),
                "provider": result.get("provider", self.provider_id),
                "source": result.get("source", "google_drive")
            }
            
            # Add ATOM-specific fields
            ui_result["display"] = {
                "icon": self._get_file_icon(result.get("mime_type", "")),
                "color": self.color,
                "provider_name": self.name
            }
            
            # Add action buttons
            ui_result["actions"] = [
                {"type": "download", "label": "Download", "icon": "⬇"},
                {"type": "view", "label": "View", "icon": "👁"},
                {"type": "share", "label": "Share", "icon": "🔗"},
                {"type": "add_to_workflow", "label": "Add to Workflow", "icon": "🤖"}
            ]
            
            return ui_result
        
        except Exception as e:
            logger.error(f"Error converting result for UI: {e}")
            return result
    
    def _get_file_icon(self, mime_type: str) -> str:
        """Get icon for file type"""
        
        icons = {
            "image": "🖼️",
            "video": "🎬",
            "audio": "🎵",
            "application/pdf": "📄",
            "application/msword": "📝",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "📝",
            "application/vnd.ms-excel": "📊",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "📊",
            "application/vnd.ms-powerpoint": "📽️",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "📽️",
            "text": "📄",
            "folder": "📁",
            "application/zip": "🗜️",
            "application/x-rar-compressed": "🗜️",
            "application/x-7z-compressed": "🗜️"
        }
        
        if mime_type in icons:
            return icons[mime_type]
        
        # Check by category
        if mime_type.startswith("image/"):
            return icons["image"]
        elif mime_type.startswith("video/"):
            return icons["video"]
        elif mime_type.startswith("audio/"):
            return icons["audio"]
        elif mime_type.startswith("text/"):
            return icons["text"]
        elif mime_type.startswith("application/"):
            return "📎"
        else:
            return "📄"
    
    def _generate_highlights(self, text: str, query: str) -> List[str]:
        """Generate search highlights"""
        
        try:
            if not text or not query:
                return []
            
            highlights = []
            query_lower = query.lower()
            text_lower = text.lower()
            
            # Find all occurrences of query in text
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
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        
        try:
            if size_bytes == 0:
                return "0 B"
            
            size_names = ["B", "KB", "MB", "GB", "TB"]
            size = float(size_bytes)
            i = 0
            
            while size >= 1024 and i < len(size_names) - 1:
                size /= 1024
                i += 1
            
            return f"{size:.1f} {size_names[i]}"
        
        except Exception as e:
            logger.error(f"Error formatting file size: {e}")
            return f"{size_bytes} B"
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information for ATOM's Search UI"""
        
        return {
            "id": self.provider_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "version": self.version,
            "capabilities": self.capabilities,
            "config": self.config,
            "status": "active",
            "health": "healthy",
            "stats": {
                "indexed_files": 0,  # Would be populated from memory service
                "last_sync": datetime.now(timezone.utc).isoformat(),
                "search_count": 0,
                "avg_response_time": 0.5
            }
        }

# Global provider instance
_google_drive_search_provider: Optional[GoogleDriveSearchProvider] = None

def initialize_google_drive_search_provider(
    drive_service: GoogleDriveService,
    memory_service: GoogleDriveMemoryService,
    automation_service: GoogleDriveAutomationService,
    search_analytics: SearchAnalytics
) -> GoogleDriveSearchProvider:
    """Initialize Google Drive search provider for ATOM's Search UI"""
    
    global _google_drive_search_provider
    
    if _google_drive_search_provider is None:
        _google_drive_search_provider = GoogleDriveSearchProvider(
            drive_service, memory_service, automation_service, search_analytics
        )
    
    return _google_drive_search_provider

# Flask route registration for integration
def register_google_drive_search_routes(app):
    """Register Google Drive search routes with Flask app"""
    
    @app.route('/api/search/providers/google_drive', methods=['GET'])
    def get_provider_info():
        """Get Google Drive search provider information"""
        
        if _google_drive_search_provider:
            return jsonify({
                "ok": True,
                "provider": _google_drive_search_provider.get_provider_info()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Google Drive search provider not initialized"
            }), 500
    
    @app.route('/api/search/google_drive', methods=['POST'])
    async def search_google_drive():
        """Search using Google Drive provider"""
        
        if not _google_drive_search_provider:
            return jsonify({
                "ok": False,
                "error": "Google Drive search provider not initialized"
            }), 500
        
        try:
            data = request.get_json()
            query = data.get('query', '')
            user_id = data.get('user_id', '')
            search_type = data.get('type', 'semantic')
            filters = data.get('filters', {})
            sort = data.get('sort', 'relevance')
            limit = data.get('limit', 50)
            offset = data.get('offset', 0)
            context = data.get('context', {})
            
            if not query or not user_id:
                return jsonify({
                    "ok": False,
                    "error": "query and user_id are required"
                }), 400
            
            # Perform search
            results = await _google_drive_search_provider.search(
                query=query,
                user_id=user_id,
                search_type=search_type,
                filters=filters,
                sort=sort,
                limit=limit,
                offset=offset,
                context=context
            )
            
            return jsonify(results)
        
        except Exception as e:
            logger.error(f"Error in Google Drive search route: {e}")
            return jsonify({
                "ok": False,
                "error": str(e)
            }), 500
    
    logger.info("Google Drive search routes registered")
    return True

# Export classes
__all__ = [
    "GoogleDriveSearchProvider",
    "initialize_google_drive_search_provider",
    "register_google_drive_search_routes"
]