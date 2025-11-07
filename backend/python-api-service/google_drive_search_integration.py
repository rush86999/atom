"""
Google Drive Search Integration with ATOM Search System
Registers Google Drive as a search provider and handles search requests
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

# Local imports
from loguru import logger
from config import get_config_instance

# Try to import required services
try:
    from google_drive_service import GoogleDriveService, get_google_drive_service, GoogleDriveFile
    from google_drive_memory import GoogleDriveMemoryService, get_google_drive_memory_service
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logger.warning("Google Drive services not available")

# Try to import search system
try:
    from search.ui.search_interface import SearchProvider, SearchResult
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    logger.warning("Search system not available")

@dataclass
class GoogleDriveSearchResult:
    """Google Drive search result data model"""
    file_id: str
    file_name: str
    file_path: str
    file_type: str
    mime_type: str
    file_size: int
    content: Optional[str] = None
    description: Optional[str] = None
    excerpt: Optional[str] = None
    highlights: List[Dict[str, Any]] = None
    score: float = 0.0
    relevance: float = 0.0
    distance: float = 0.0
    metadata: Dict[str, Any] = None
    thumbnail_url: Optional[str] = None
    web_view_link: Optional[str] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.highlights is None:
            self.highlights = []
        if self.metadata is None:
            self.metadata = {}
    
    def to_search_result(self) -> Dict[str, Any]:
        """Convert to search result format"""
        return {
            "id": self.file_id,
            "title": self.file_name,
            "type": self.file_type,
            "mime_type": self.mime_type,
            "size": self.file_size,
            "content": self.content,
            "excerpt": self.excerpt,
            "description": self.description,
            "highlights": self.highlights,
            "score": self.score,
            "relevance": self.relevance,
            "distance": self.distance,
            "metadata": {
                "provider": "google_drive",
                "file_id": self.file_id,
                "file_path": self.file_path,
                "thumbnail_url": self.thumbnail_url,
                "web_view_link": self.web_view_link,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "modified_at": self.modified_at.isoformat() if self.modified_at else None,
                **self.metadata
            }
        }

class GoogleDriveSearchProvider:
    """Google Drive Search Provider for ATOM"""
    
    def __init__(self, config=None):
        self.config = config or get_config_instance()
        self.search_config = self.config.search
        
        if not GOOGLE_DRIVE_AVAILABLE:
            raise ImportError("Google Drive services not available")
        
        if not SEARCH_AVAILABLE:
            raise ImportError("Search system not available")
        
        # Services
        self._drive_service: Optional[GoogleDriveService] = None
        self._memory_service: Optional[GoogleDriveMemoryService] = None
        
        # Search configuration
        self.enable_semantic_search = self.search_config.enable_semantic_search
        self.enable_faceted_search = self.search_config.enable_faceted_search
        self.max_results = self.search_config.max_results
        self.default_limit = self.search_config.default_limit
        self.cache_ttl = self.search_config.cache_ttl
        
        # Cache for search results
        self._search_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Google Drive Search Provider initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_services()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def _ensure_services(self):
        """Ensure required services are available"""
        
        if self._drive_service is None:
            self._drive_service = await get_google_drive_service()
        
        if self._memory_service is None:
            self._memory_service = await get_google_drive_memory_service()
        
        if not self._drive_service or not self._memory_service:
            raise ValueError("Required services not available")
    
    async def close(self):
        """Close provider and cleanup resources"""
        
        if self._drive_service:
            await self._drive_service.close()
            self._drive_service = None
        
        if self._memory_service:
            await self._memory_service.close()
            self._memory_service = None
        
        self._search_cache.clear()
        logger.debug("Google Drive Search Provider closed")
    
    # ==================== SEARCH PROVIDER INTERFACE ====================
    
    async def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information"""
        
        return {
            "name": "Google Drive",
            "type": "google_drive",
            "version": "1.0.0",
            "description": "Search across Google Drive files with semantic and text search",
            "features": {
                "semantic_search": self.enable_semantic_search,
                "faceted_search": self.enable_faceted_search,
                "full_text_search": True,
                "file_type_filtering": True,
                "date_filtering": True,
                "size_filtering": True,
                "highlighting": True
            },
            "capabilities": {
                "max_results": self.max_results,
                "default_limit": self.default_limit,
                "cache_ttl": self.cache_ttl,
                "supported_file_types": [
                    "pdf", "doc", "docx", "txt", "rtf", "odt",
                    "jpg", "jpeg", "png", "gif", "bmp", "svg",
                    "mp4", "avi", "mov", "wmv", "flv", "webm",
                    "mp3", "wav", "flac", "aac", "ogg",
                    "zip", "rar", "7z", "tar", "gz"
                ]
            },
            "configuration": {
                "semantic_search": self.enable_semantic_search,
                "faceted_search": self.enable_faceted_search,
                "cache_enabled": True,
                "cache_ttl": self.cache_ttl
            },
            "status": "ready"
        }
    
    async def search(self, 
                     query: str,
                     options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform search with specified options"""
        
        try:
            # Parse search options
            search_options = self._parse_search_options(options)
            
            # Check cache first
            cache_key = self._generate_cache_key(query, search_options)
            if cache_key in self._search_cache:
                cached_result = self._search_cache[cache_key]
                if datetime.utcnow() - cached_result["cached_at"] < timedelta(seconds=self.cache_ttl):
                    return cached_result
            
            await self._ensure_services()
            
            # Determine search type
            search_type = search_options.get("search_type", "semantic")
            
            if search_type == "semantic" and self.enable_semantic_search:
                result = await self._semantic_search(query, search_options)
            elif search_type == "hybrid":
                result = await self._hybrid_search(query, search_options)
            else:
                result = await self._text_search(query, search_options)
            
            # Apply filters and pagination
            filtered_result = await self._apply_filters(result, search_options)
            
            # Format results
            formatted_result = await self._format_search_results(filtered_result, search_options)
            
            # Cache result
            formatted_result["cached_at"] = datetime.utcnow()
            self._search_cache[cache_key] = formatted_result
            
            # Clear old cache entries
            await self._cleanup_cache()
            
            return formatted_result
        
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "total_found": 0,
                "query": query,
                "provider": "google_drive"
            }
    
    async def get_facets(self, 
                         query: Optional[str] = None,
                         filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get search facets for filtering"""
        
        try:
            await self._ensure_services()
            
            facets = {
                "file_types": {},
                "mime_types": {},
                "size_ranges": {},
                "date_ranges": {},
                "folders": {}
            }
            
            # Get all files for faceting (limited for performance)
            files_result = await self._drive_service.list_files(
                query=None,
                page_size=1000
            )
            
            if not files_result["success"]:
                return {
                    "success": False,
                    "error": files_result.get("error", "Failed to get files for faceting"),
                    "facets": facets
                }
            
            # Process files for facets
            for file_data in files_result["files"]:
                file_obj = GoogleDriveFile(**file_data)
                
                # File type facet
                file_ext = file_obj.file_extension or "folder"
                file_type = self._get_file_type(file_obj.mime_type)
                
                facets["file_types"][file_type] = facets["file_types"].get(file_type, 0) + 1
                
                # MIME type facet
                facets["mime_types"][file_obj.mime_type] = facets["mime_types"].get(file_obj.mime_type, 0) + 1
                
                # Size range facet
                size_range = self._get_size_range(file_obj.size)
                facets["size_ranges"][size_range] = facets["size_ranges"].get(size_range, 0) + 1
                
                # Date range facet
                date_range = self._get_date_range(file_obj.modified_time)
                facets["date_ranges"][date_range] = facets["date_ranges"].get(date_range, 0) + 1
                
                # Folder facet
                for parent_id in file_obj.parents:
                    folder_name = f"folder_{parent_id}"  # Would need folder name lookup
                    facets["folders"][folder_name] = facets["folders"].get(folder_name, 0) + 1
            
            return {
                "success": True,
                "facets": facets,
                "total_files": len(files_result["files"])
            }
        
        except Exception as e:
            logger.error(f"Failed to get facets: {e}")
            return {
                "success": False,
                "error": str(e),
                "facets": {}
            }
    
    async def get_suggestions(self, 
                            query: str,
                            limit: int = 10) -> Dict[str, Any]:
        """Get search suggestions"""
        
        try:
            await self._ensure_services()
            
            suggestions = []
            
            # Get recent files for suggestions
            recent_result = await self._drive_service.list_files(
                query=None,
                page_size=100,
                order_by="modifiedTime desc"
            )
            
            if recent_result["success"]:
                for file_data in recent_result["files"]:
                    file_obj = GoogleDriveFile(**file_data)
                    
                    # Suggest based on file name
                    if query.lower() in file_obj.name.lower():
                        suggestions.append({
                            "type": "file_name",
                            "text": file_obj.name,
                            "file_id": file_obj.id,
                            "mime_type": file_obj.mime_type,
                            "metadata": {
                                "file_type": self._get_file_type(file_obj.mime_type),
                                "size": file_obj.size,
                                "modified_time": file_obj.modified_time.isoformat() if file_obj.modified_time else None
                            }
                        })
                    
                    if len(suggestions) >= limit:
                        break
            
            return {
                "success": True,
                "suggestions": suggestions[:limit],
                "query": query
            }
        
        except Exception as e:
            logger.error(f"Failed to get suggestions: {e}")
            return {
                "success": False,
                "error": str(e),
                "suggestions": []
            }
    
    # ==================== SEARCH IMPLEMENTATIONS ====================
    
    async def _semantic_search(self, 
                               query: str,
                               options: Dict[str, Any]) -> Dict[str, Any]:
        """Perform semantic search using LanceDB"""
        
        try:
            # Search in memory service
            memory_result = await self._memory_service.semantic_search(
                query=query,
                limit=options.get("limit", self.default_limit),
                min_score=options.get("min_score", 0.1)
            )
            
            if not memory_result["success"]:
                return {
                    "success": False,
                    "error": memory_result.get("error"),
                    "results": [],
                    "total_found": 0
                }
            
            return {
                "success": True,
                "results": memory_result["results"],
                "total_found": len(memory_result["results"]),
                "search_type": "semantic",
                "query": query,
                "embedding_model": memory_result.get("embedding_model")
            }
        
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "total_found": 0
            }
    
    async def _text_search(self, 
                            query: str,
                            options: Dict[str, Any]) -> Dict[str, Any]:
        """Perform text-based search using Google Drive API"""
        
        try:
            # Search in Google Drive
            drive_result = await self._drive_service.search_files(
                query=query,
                page_size=options.get("limit", self.default_limit),
                order_by=options.get("sort_by", "relevance desc")
            )
            
            if not drive_result["success"]:
                return {
                    "success": False,
                    "error": drive_result.get("error"),
                    "results": [],
                    "total_found": 0
                }
            
            return {
                "success": True,
                "results": drive_result["files"],
                "total_found": len(drive_result["files"]),
                "search_type": "text",
                "query": query
            }
        
        except Exception as e:
            logger.error(f"Text search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "total_found": 0
            }
    
    async def _hybrid_search(self, 
                             query: str,
                             options: Dict[str, Any]) -> Dict[str, Any]:
        """Perform hybrid search combining semantic and text"""
        
        try:
            # Perform both searches
            semantic_task = self._semantic_search(query, options)
            text_task = self._text_search(query, options)
            
            # Wait for both searches
            semantic_result, text_result = await asyncio.gather(
                semantic_task,
                text_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(semantic_result, Exception):
                logger.error(f"Semantic search failed: {semantic_result}")
                semantic_result = {"success": False, "results": [], "total_found": 0}
            
            if isinstance(text_result, Exception):
                logger.error(f"Text search failed: {text_result}")
                text_result = {"success": False, "results": [], "total_found": 0}
            
            # Combine results
            combined_results = self._combine_search_results(
                semantic_result.get("results", []),
                text_result.get("results", []),
                semantic_weight=options.get("semantic_weight", 0.7),
                text_weight=options.get("text_weight", 0.3)
            )
            
            return {
                "success": True,
                "results": combined_results,
                "total_found": len(combined_results),
                "search_type": "hybrid",
                "query": query,
                "semantic_results": len(semantic_result.get("results", [])),
                "text_results": len(text_result.get("results", []))
            }
        
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "total_found": 0
            }
    
    # ==================== SEARCH UTILITIES ====================
    
    def _parse_search_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse and validate search options"""
        
        if not options:
            options = {}
        
        return {
            "limit": min(options.get("limit", self.default_limit), self.max_results),
            "offset": options.get("offset", 0),
            "sort_by": options.get("sort_by", "relevance desc"),
            "search_type": options.get("search_type", "semantic"),
            "file_types": options.get("file_types", []),
            "mime_types": options.get("mime_types", []),
            "size_min": options.get("size_min", 0),
            "size_max": options.get("size_max", None),
            "date_from": options.get("date_from", None),
            "date_to": options.get("date_to", None),
            "folder_id": options.get("folder_id", None),
            "semantic_weight": options.get("semantic_weight", 0.7),
            "text_weight": options.get("text_weight", 0.3),
            "min_score": options.get("min_score", 0.1),
            "highlight": options.get("highlight", True),
            "fields": options.get("fields", ["name", "content", "description"])
        }
    
    def _generate_cache_key(self, query: str, options: Dict[str, Any]) -> str:
        """Generate cache key for search"""
        
        import hashlib
        
        # Create cache string
        cache_parts = [
            query,
            str(options.get("limit", "")),
            str(options.get("offset", "")),
            str(options.get("sort_by", "")),
            str(options.get("search_type", "")),
            str(sorted(options.get("file_types", []))),
            str(sorted(options.get("mime_types", []))),
            str(options.get("size_min", "")),
            str(options.get("size_max", "")),
            str(options.get("date_from", "")),
            str(options.get("date_to", "")),
            str(options.get("folder_id", "")),
            str(options.get("semantic_weight", "")),
            str(options.get("text_weight", "")),
            str(options.get("min_score", ""))
        ]
        
        cache_string = "|".join(cache_parts)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    async def _apply_filters(self, result: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Apply filters to search results"""
        
        try:
            results = result.get("results", [])
            filtered_results = []
            
            for item in results:
                # File type filter
                if options.get("file_types"):
                    item_mime_type = item.get("mime_type", "")
                    item_type = self._get_file_type(item_mime_type)
                    
                    if item_type not in options["file_types"]:
                        continue
                
                # MIME type filter
                if options.get("mime_types"):
                    if item.get("mime_type") not in options["mime_types"]:
                        continue
                
                # Size filter
                if options.get("size_min", 0) > 0:
                    if item.get("size", 0) < options["size_min"]:
                        continue
                
                if options.get("size_max"):
                    if item.get("size", 0) > options["size_max"]:
                        continue
                
                # Date filter
                if options.get("date_from"):
                    item_date_str = item.get("modified_time") or item.get("created_time")
                    if item_date_str:
                        try:
                            item_date = datetime.fromisoformat(item_date_str.replace('Z', '+00:00'))
                            filter_date = datetime.fromisoformat(options["date_from"].replace('Z', '+00:00'))
                            
                            if item_date < filter_date:
                                continue
                        except Exception:
                            pass
                
                if options.get("date_to"):
                    item_date_str = item.get("modified_time") or item.get("created_time")
                    if item_date_str:
                        try:
                            item_date = datetime.fromisoformat(item_date_str.replace('Z', '+00:00'))
                            filter_date = datetime.fromisoformat(options["date_to"].replace('Z', '+00:00'))
                            
                            if item_date > filter_date:
                                continue
                        except Exception:
                            pass
                
                filtered_results.append(item)
            
            return {
                **result,
                "results": filtered_results,
                "total_found": len(filtered_results)
            }
        
        except Exception as e:
            logger.error(f"Failed to apply filters: {e}")
            return result
    
    async def _format_search_results(self, result: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Format search results into standard format"""
        
        try:
            raw_results = result.get("results", [])
            formatted_results = []
            
            for item in raw_results:
                # Convert to Google Drive file object if needed
                if "name" in item and "id" in item and "mime_type" in item:
                    file_obj = GoogleDriveFile(**item)
                else:
                    # Handle memory service result
                    file_id = item.get("file_id", "")
                    file_data = await self._drive_service.get_file(file_id)
                    if file_data["success"]:
                        file_obj = GoogleDriveFile(**file_data["file"])
                    else:
                        continue
                
                # Create search result
                search_result = GoogleDriveSearchResult(
                    file_id=file_obj.id,
                    file_name=file_obj.name,
                    file_path=self._get_file_path(file_obj),
                    file_type=self._get_file_type(file_obj.mime_type),
                    mime_type=file_obj.mime_type,
                    file_size=file_obj.size,
                    content=item.get("content") or item.get("text", ""),
                    description=file_obj.description,
                    excerpt=self._create_excerpt(item.get("content", ""), options.get("query", "")),
                    highlights=item.get("highlights", []) if "highlights" in item else [],
                    score=item.get("score", 0.0),
                    relevance=item.get("relevance", 0.0),
                    distance=item.get("distance", 0.0),
                    metadata=self._get_file_metadata(file_obj),
                    thumbnail_url=file_obj.thumbnail_link,
                    web_view_link=file_obj.web_view_link,
                    created_at=file_obj.created_time,
                    modified_at=file_obj.modified_time
                )
                
                # Apply highlighting if requested
                if options.get("highlight", True) and options.get("query"):
                    search_result.highlights = self._create_highlights(
                        search_result.content or search_result.description or "",
                        options["query"]
                    )
                
                formatted_results.append(search_result.to_search_result())
            
            # Apply pagination
            offset = options.get("offset", 0)
            limit = options.get("limit", self.default_limit)
            paginated_results = formatted_results[offset:offset + limit]
            
            return {
                "success": True,
                "results": paginated_results,
                "total_found": len(formatted_results),
                "returned": len(paginated_results),
                "offset": offset,
                "limit": limit,
                "query": options.get("query", ""),
                "search_type": result.get("search_type", "unknown"),
                "has_more": offset + limit < len(formatted_results),
                "execution_time": result.get("execution_time", 0.0)
            }
        
        except Exception as e:
            logger.error(f"Failed to format search results: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "total_found": 0
            }
    
    def _combine_search_results(self, 
                                 semantic_results: List[Dict[str, Any]],
                                 text_results: List[Dict[str, Any]],
                                 semantic_weight: float = 0.7,
                                 text_weight: float = 0.3) -> List[Dict[str, Any]]:
        """Combine semantic and text search results"""
        
        combined_results = []
        seen_ids = set()
        
        # Add semantic results
        for result in semantic_results:
            file_id = result.get("file_id", "")
            if file_id and file_id not in seen_ids:
                combined_result = result.copy()
                combined_result["semantic_score"] = result.get("relevance", 0.0)
                combined_result["text_score"] = 0.0
                combined_result["combined_score"] = result.get("relevance", 0.0) * semantic_weight
                combined_results.append(combined_result)
                seen_ids.add(file_id)
        
        # Add text results
        for result in text_results:
            file_id = result.get("id", "")
            if file_id:
                if file_id in seen_ids:
                    # Update existing result
                    for combined_result in combined_results:
                        if combined_result.get("file_id") == file_id:
                            combined_result["text_score"] = 1.0  # Text search gives perfect match
                            combined_result["combined_score"] = (
                                combined_result.get("semantic_score", 0.0) * semantic_weight +
                                text_weight
                            )
                            break
                else:
                    # Add new result
                    combined_result = result.copy()
                    combined_result["file_id"] = file_id
                    combined_result["semantic_score"] = 0.0
                    combined_result["text_score"] = 1.0
                    combined_result["combined_score"] = text_weight
                    combined_results.append(combined_result)
                    seen_ids.add(file_id)
        
        # Sort by combined score
        combined_results.sort(key=lambda x: x.get("combined_score", 0.0), reverse=True)
        
        return combined_results
    
    # ==================== UTILITY METHODS ====================
    
    def _get_file_type(self, mime_type: str) -> str:
        """Get file type from MIME type"""
        
        type_mapping = {
            "application/pdf": "pdf",
            "application/msword": "doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "text/plain": "txt",
            "application/rtf": "rtf",
            "application/vnd.oasis.opendocument.text": "odt",
            
            "image/jpeg": "image",
            "image/png": "image",
            "image/gif": "image",
            "image/bmp": "image",
            "image/svg+xml": "image",
            
            "video/mp4": "video",
            "video/quicktime": "video",
            "video/x-msvideo": "video",
            "video/x-ms-wmv": "video",
            "video/webm": "video",
            
            "audio/mpeg": "audio",
            "audio/wav": "audio",
            "audio/flac": "audio",
            "audio/aac": "audio",
            "audio/ogg": "audio",
            
            "application/zip": "archive",
            "application/x-rar-compressed": "archive",
            "application/x-7z-compressed": "archive",
            "application/x-tar": "archive",
            "application/gzip": "archive"
        }
        
        return type_mapping.get(mime_type, "other")
    
    def _get_file_path(self, file_obj: GoogleDriveFile) -> str:
        """Get file path (simplified)"""
        
        # In a real implementation, this would resolve parent folder names
        if file_obj.parents:
            return f"/{file_obj.name}"  # Simplified
        return f"/{file_obj.name}"
    
    def _get_file_metadata(self, file_obj: GoogleDriveFile) -> Dict[str, Any]:
        """Get file metadata"""
        
        return {
            "is_folder": file_obj.is_folder,
            "is_shared": file_obj.is_shared,
            "is_starred": file_obj.is_starred,
            "is_trashed": file_obj.is_trashed,
            "parents": file_obj.parents,
            "permissions": file_obj.permissions,
            "owners": file_obj.owners,
            "checksum_md5": file_obj.checksum_md5,
            "checksum_sha1": file_obj.checksum_sha1,
            "checksum_sha256": file_obj.checksum_sha256
        }
    
    def _get_size_range(self, size: int) -> str:
        """Get size range for faceting"""
        
        if size < 1024 * 100:  # < 100KB
            return "small"
        elif size < 1024 * 1024 * 10:  # < 10MB
            return "medium"
        elif size < 1024 * 1024 * 100:  # < 100MB
            return "large"
        else:
            return "extra_large"
    
    def _get_date_range(self, date_time: datetime) -> str:
        """Get date range for faceting"""
        
        now = datetime.utcnow()
        delta = now - date_time
        
        if delta.days < 1:
            return "today"
        elif delta.days < 7:
            return "this_week"
        elif delta.days < 30:
            return "this_month"
        elif delta.days < 365:
            return "this_year"
        else:
            return "older"
    
    def _create_excerpt(self, content: str, query: str, max_length: int = 200) -> str:
        """Create excerpt from content"""
        
        if not content:
            return ""
        
        # Find query in content
        query_lower = query.lower()
        content_lower = content.lower()
        query_pos = content_lower.find(query_lower)
        
        if query_pos == -1:
            # Just return first part
            return content[:max_length] + ("..." if len(content) > max_length else "")
        
        # Extract around query
        start_pos = max(0, query_pos - 100)
        end_pos = min(len(content), query_pos + max_length - 100)
        
        excerpt = content[start_pos:end_pos]
        
        if start_pos > 0:
            excerpt = "..." + excerpt
        if end_pos < len(content):
            excerpt = excerpt + "..."
        
        return excerpt
    
    def _create_highlights(self, content: str, query: str) -> List[Dict[str, Any]]:
        """Create highlights from content"""
        
        if not content or not query:
            return []
        
        highlights = []
        content_lower = content.lower()
        query_lower = query.lower()
        
        # Find all occurrences
        query_pos = content_lower.find(query_lower)
        while query_pos != -1:
            # Extract context
            start_context = max(0, query_pos - 50)
            end_context = min(len(content), query_pos + len(query) + 50)
            
            context_text = content[start_context:end_context]
            if start_context > 0:
                context_text = "..." + context_text
            if end_context < len(content):
                context_text = context_text + "..."
            
            highlights.append({
                "text": context_text,
                "start_pos": query_pos,
                "end_pos": query_pos + len(query),
                "type": "match"
            })
            
            # Find next occurrence
            query_pos = content_lower.find(query_lower, query_pos + 1)
        
        return highlights
    
    async def _cleanup_cache(self):
        """Clean up expired cache entries"""
        
        try:
            expired_keys = []
            current_time = datetime.utcnow()
            
            for cache_key, cache_value in self._search_cache.items():
                cached_at = cache_value.get("cached_at")
                if cached_at and (current_time - cached_at) > timedelta(seconds=self.cache_ttl * 2):
                    expired_keys.append(cache_key)
            
            for key in expired_keys:
                del self._search_cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")

# Global search provider instance
_google_drive_search_provider: Optional[GoogleDriveSearchProvider] = None

async def get_google_drive_search_provider() -> Optional[GoogleDriveSearchProvider]:
    """Get global Google Drive search provider instance"""
    
    global _google_drive_search_provider
    
    if _google_drive_search_provider is None:
        try:
            config = get_config_instance()
            _google_drive_search_provider = GoogleDriveSearchProvider(config)
            logger.info("Google Drive Search Provider created")
        except Exception as e:
            logger.error(f"Failed to create Google Drive Search Provider: {e}")
            _google_drive_search_provider = None
    
    return _google_drive_search_provider

def clear_google_drive_search_provider():
    """Clear global search provider instance"""
    
    global _google_drive_search_provider
    _google_drive_search_provider = None
    logger.info("Google Drive Search Provider cleared")

# Export classes and functions
__all__ = [
    'GoogleDriveSearchProvider',
    'GoogleDriveSearchResult',
    'get_google_drive_search_provider',
    'clear_google_drive_search_provider'
]