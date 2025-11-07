"""
Google Drive Memory Service - LanceDB Integration
Handles semantic search, vector embeddings, and content indexing
"""

import os
import json
import asyncio
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import aiofiles
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

# LanceDB imports
try:
    import lancedb
    import pyarrow as pa
    from sentence_transformers import SentenceTransformer
    import faiss
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logging.warning("LanceDB or sentence-transformers libraries not available")

# Local imports
from loguru import logger
from config import get_config_instance

@dataclass
class VectorEmbedding:
    """Vector embedding data model"""
    file_id: str
    embedding_model: str
    embedding_dimension: int
    embedding_vector: List[float]
    embedding_text: str
    created_at: datetime
    updated_at: datetime
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array"""
        return np.array(self.embedding_vector, dtype=np.float32)
    
    @classmethod
    def from_array(cls, 
                   file_id: str,
                   embedding_model: str,
                   embedding_vector: np.ndarray,
                   embedding_text: str) -> 'VectorEmbedding':
        """Create from numpy array"""
        return cls(
            file_id=file_id,
            embedding_model=embedding_model,
            embedding_dimension=len(embedding_vector),
            embedding_vector=embedding_vector.tolist(),
            embedding_text=embedding_text,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

@dataclass
class SearchResult:
    """Search result data model"""
    file_id: str
    score: float
    content: str
    metadata: Dict[str, Any]
    relevance: float
    distance: float
    highlighted_text: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "file_id": self.file_id,
            "score": self.score,
            "content": self.content,
            "metadata": self.metadata,
            "relevance": self.relevance,
            "distance": self.distance,
            "highlighted_text": self.highlighted_text,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class GoogleDriveMemoryService:
    """Google Drive Memory Service - LanceDB Integration"""
    
    def __init__(self, config=None):
        self.config = config or get_config_instance()
        self.lancedb_config = self.config.lancedb
        self.search_config = self.config.search
        
        if not LANCEDB_AVAILABLE:
            raise ImportError("LanceDB or sentence-transformers not available. Install: pip install lancedb sentence-transformers")
        
        # LanceDB connection
        self.db: Optional[lancedb.DBConnection] = None
        self.table: Optional[lancedb.Table] = None
        self.embedding_model: Optional[SentenceTransformer] = None
        
        # Cache for performance
        self._embedding_cache: Dict[str, VectorEmbedding] = {}
        self._search_cache: Dict[str, List[SearchResult]] = {}
        self.cache_ttl = self.search_config.cache_ttl
        
        # Batch processing
        self.batch_size = self.lancedb_config.batch_size
        
        logger.info("Google Drive Memory Service initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def connect(self):
        """Connect to LanceDB and initialize table"""
        
        try:
            # Create data directory if needed
            db_path = Path(self.lancedb_config.path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Connect to LanceDB
            self.db = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: lancedb.connect(str(db_path))
            )
            
            # Initialize embedding model
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: SentenceTransformer(self.lancedb_config.embedding_model)
            )
            
            logger.info(f"Connected to LanceDB at: {self.lancedb_config.path}")
            logger.info(f"Using embedding model: {self.lancedb_config.embedding_model}")
            
        except Exception as e:
            logger.error(f"Failed to connect to LanceDB: {e}")
            raise
    
    async def close(self):
        """Close LanceDB connection"""
        
        try:
            if self.table:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.table.close
                )
                self.table = None
            
            if self.db:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.db.close
                )
                self.db = None
            
            logger.info("LanceDB connection closed")
        
        except Exception as e:
            logger.error(f"Error closing LanceDB: {e}")
    
    # ==================== TABLE MANAGEMENT ====================
    
    async def ensure_table(self, table_name: str = "google_drive_embeddings"):
        """Ensure table exists"""
        
        try:
            if not self.db:
                raise ValueError("LanceDB not connected")
            
            # Check if table exists
            table_names = await asyncio.get_event_loop().run_in_executor(
                None,
                self.db.table_names
            )
            
            if table_name not in table_names:
                # Create table schema
                schema = pa.schema([
                    pa.field("file_id", pa.string()),
                    pa.field("embedding_model", pa.string()),
                    pa.field("embedding_dimension", pa.int32()),
                    pa.field("embedding_vector", pa.list_(pa.float32())),
                    pa.field("embedding_text", pa.string()),
                    pa.field("created_at", pa.timestamp('us')),
                    pa.field("updated_at", pa.timestamp('us')),
                    pa.field("vector", pa.list_(pa.float32()))  # Fixed size vector for search
                ])
                
                # Create table
                self.table = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.db.create_table(table_name, schema=schema)
                )
                
                logger.info(f"Created LanceDB table: {table_name}")
            else:
                # Open existing table
                self.table = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.db.open_table(table_name)
                )
                
                logger.info(f"Opened existing LanceDB table: {table_name}")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to ensure table: {e}")
            return False
    
    # ==================== EMBEDDING OPERATIONS ====================
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        
        try:
            # Check cache first
            cache_key = hash(text)
            if cache_key in self._embedding_cache:
                embedding = self._embedding_cache[cache_key]
                return embedding.embedding_vector
            
            # Generate embedding
            def _generate():
                if not self.embedding_model:
                    self.embedding_model = SentenceTransformer(self.lancedb_config.embedding_model)
                
                return self.embedding_model.encode(text, convert_to_numpy=True)
            
            embedding = await asyncio.get_event_loop().run_in_executor(None, _generate)
            
            # Cache embedding
            vector_embedding = VectorEmbedding(
                file_id="",
                embedding_model=self.lancedb_config.embedding_model,
                embedding_dimension=self.lancedb_config.embedding_dimension,
                embedding_vector=embedding.tolist(),
                embedding_text=text,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self._embedding_cache[cache_key] = vector_embedding
            
            return embedding.tolist()
        
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return []
    
    async def store_embedding(self, 
                            file_id: str,
                            text: str,
                            metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store embedding for file"""
        
        try:
            if not self.table:
                await self.ensure_table()
            
            # Generate embedding
            embedding = await self.generate_embedding(text)
            if not embedding:
                return {
                    "success": False,
                    "error": "Failed to generate embedding"
                }
            
            # Create record
            now = datetime.utcnow()
            record = {
                "file_id": file_id,
                "embedding_model": self.lancedb_config.embedding_model,
                "embedding_dimension": self.lancedb_config.embedding_dimension,
                "embedding_vector": embedding,
                "embedding_text": text,
                "created_at": now,
                "updated_at": now,
                "vector": embedding  # Fixed size vector for search
            }
            
            # Add metadata if provided
            if metadata:
                record.update(metadata)
            
            # Store in table
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.table.add([record])
            )
            
            # Update cache
            self._embedding_cache[hash(text)] = VectorEmbedding.from_array(
                file_id=file_id,
                embedding_model=self.lancedb_config.embedding_model,
                embedding_vector=np.array(embedding),
                embedding_text=text
            )
            
            logger.info(f"Stored embedding for file: {file_id}")
            
            return {
                "success": True,
                "file_id": file_id,
                "embedding_dimension": len(embedding),
                "embedding_model": self.lancedb_config.embedding_model
            }
        
        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def batch_store_embeddings(self, 
                                   embeddings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Store multiple embeddings in batch"""
        
        try:
            if not self.table:
                await self.ensure_table()
            
            if not embeddings:
                return {
                    "success": False,
                    "error": "No embeddings provided"
                }
            
            # Process embeddings in batches
            records = []
            now = datetime.utcnow()
            
            for embedding_data in embeddings:
                file_id = embedding_data["file_id"]
                text = embedding_data["text"]
                metadata = embedding_data.get("metadata", {})
                
                # Generate embedding
                embedding = await self.generate_embedding(text)
                if not embedding:
                    continue
                
                # Create record
                record = {
                    "file_id": file_id,
                    "embedding_model": self.lancedb_config.embedding_model,
                    "embedding_dimension": self.lancedb_config.embedding_dimension,
                    "embedding_vector": embedding,
                    "embedding_text": text,
                    "created_at": now,
                    "updated_at": now,
                    "vector": embedding
                }
                
                record.update(metadata)
                records.append(record)
            
            if not records:
                return {
                    "success": False,
                    "error": "No valid embeddings to store"
                }
            
            # Store in batches
            stored_count = 0
            for i in range(0, len(records), self.batch_size):
                batch = records[i:i + self.batch_size]
                
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.table.add(batch)
                )
                
                stored_count += len(batch)
            
            logger.info(f"Batch stored {stored_count} embeddings")
            
            return {
                "success": True,
                "stored_count": stored_count,
                "total_requested": len(embeddings)
            }
        
        except Exception as e:
            logger.error(f"Failed to batch store embeddings: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== SEARCH OPERATIONS ====================
    
    async def semantic_search(self, 
                            query: str,
                            limit: int = 50,
                            min_score: float = 0.1,
                            filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform semantic search"""
        
        try:
            if not self.table:
                await self.ensure_table()
            
            # Check cache
            cache_key = f"semantic_{hash(query)}_{limit}_{min_score}"
            if cache_key in self._search_cache:
                cached_results = self._search_cache[cache_key]
                # Check cache TTL
                cache_time = cached_results[0].created_at if cached_results else datetime.utcnow()
                if datetime.utcnow() - cache_time < timedelta(seconds=self.cache_ttl):
                    return {
                        "success": True,
                        "results": [result.to_dict() for result in cached_results],
                        "total_found": len(cached_results),
                        "query": query,
                        "cached": True
                    }
            
            # Generate query embedding
            query_embedding = await self.generate_embedding(query)
            if not query_embedding:
                return {
                    "success": False,
                    "error": "Failed to generate query embedding"
                }
            
            # Perform search
            def _search():
                return self.table.search(query_embedding).limit(limit).to_pandas()
            
            df = await asyncio.get_event_loop().run_in_executor(None, _search)
            
            # Process results
            results = []
            for _, row in df.iterrows():
                score = row.get('_distance', 0.0)
                
                # Convert distance to relevance score (lower distance = higher relevance)
                relevance = 1.0 / (1.0 + score)
                
                if relevance < min_score:
                    continue
                
                # Create search result
                result = SearchResult(
                    file_id=row['file_id'],
                    score=score,
                    content=row.get('embedding_text', ''),
                    metadata=row.to_dict(),
                    relevance=relevance,
                    distance=score,
                    created_at=row.get('created_at')
                )
                
                results.append(result)
            
            # Sort by relevance
            results.sort(key=lambda x: x.relevance, reverse=True)
            
            # Cache results
            self._search_cache[cache_key] = results
            
            logger.info(f"Semantic search for '{query}' found {len(results)} results")
            
            return {
                "success": True,
                "results": [result.to_dict() for result in results],
                "total_found": len(results),
                "query": query,
                "embedding_model": self.lancedb_config.embedding_model,
                "cached": False
            }
        
        except Exception as e:
            logger.error(f"Failed to perform semantic search: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def hybrid_search(self, 
                          query: str,
                          text_query: Optional[str] = None,
                          limit: int = 50,
                          min_score: float = 0.1,
                          semantic_weight: float = 0.7,
                          text_weight: float = 0.3,
                          filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform hybrid search (semantic + text)"""
        
        try:
            # Perform semantic search
            semantic_result = await self.semantic_search(
                query=query,
                limit=limit * 2,  # Get more for better hybrid
                min_score=min_score * 0.5,
                filters=filters
            )
            
            if not semantic_result["success"]:
                return semantic_result
            
            semantic_results = semantic_result["results"]
            
            # If no text query provided, return semantic results
            if not text_query:
                return {
                    "success": True,
                    "results": semantic_results[:limit],
                    "total_found": len(semantic_results),
                    "query": query,
                    "search_type": "semantic_only",
                    "semantic_weight": semantic_weight,
                    "text_weight": text_weight
                }
            
            # Perform text search
            text_result = await self.text_search(
                query=text_query,
                limit=limit * 2,
                filters=filters
            )
            
            text_results = text_result.get("results", [])
            
            # Combine results
            combined_results = self._combine_search_results(
                semantic_results,
                text_results,
                semantic_weight,
                text_weight
            )
            
            # Sort by combined score and limit
            combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
            limited_results = combined_results[:limit]
            
            return {
                "success": True,
                "results": limited_results,
                "total_found": len(combined_results),
                "query": query,
                "text_query": text_query,
                "search_type": "hybrid",
                "semantic_weight": semantic_weight,
                "text_weight": text_weight,
                "semantic_results_count": len(semantic_results),
                "text_results_count": len(text_results)
            }
        
        except Exception as e:
            logger.error(f"Failed to perform hybrid search: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def text_search(self, 
                         query: str,
                         limit: int = 50,
                         filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform text-based search"""
        
        try:
            if not self.table:
                await self.ensure_table()
            
            # Build SQL filter
            where_conditions = []
            if filters:
                for field, value in filters.items():
                    if isinstance(value, str):
                        where_conditions.append(f"{field} LIKE '%{value}%'")
                    else:
                        where_conditions.append(f"{field} = {value}")
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # Text search condition
            text_condition = f"embedding_text LIKE '%{query}%'"
            final_where = f"{text_condition} AND ({where_clause})"
            
            # Execute search
            def _text_search():
                return self.table.search().where(final_where).limit(limit).to_pandas()
            
            df = await asyncio.get_event_loop().run_in_executor(None, _text_search)
            
            # Process results
            results = []
            for _, row in df.iterrows():
                # Simple text relevance based on term frequency
                text = row.get('embedding_text', '').lower()
                query_lower = query.lower()
                term_count = text.count(query_lower)
                relevance = min(term_count / len(text.split()) * 10, 1.0)
                
                result = {
                    "file_id": row['file_id'],
                    "content": row.get('embedding_text', ''),
                    "metadata": row.to_dict(),
                    "relevance": relevance,
                    "score": 1.0 - relevance,  # Lower distance for higher relevance
                    "distance": 1.0 - relevance,
                    "created_at": row.get('created_at').isoformat() if row.get('created_at') else None
                }
                
                results.append(result)
            
            # Sort by relevance
            results.sort(key=lambda x: x["relevance"], reverse=True)
            
            logger.info(f"Text search for '{query}' found {len(results)} results")
            
            return {
                "success": True,
                "results": results,
                "total_found": len(results),
                "query": query,
                "search_type": "text"
            }
        
        except Exception as e:
            logger.error(f"Failed to perform text search: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _combine_search_results(self, 
                              semantic_results: List[Dict[str, Any]],
                              text_results: List[Dict[str, Any]],
                              semantic_weight: float,
                              text_weight: float) -> List[Dict[str, Any]]:
        """Combine semantic and text search results"""
        
        # Create file_id to result mapping
        file_results = {}
        
        # Add semantic results
        for result in semantic_results:
            file_id = result["file_id"]
            file_results[file_id] = {
                "file_id": file_id,
                "semantic_score": result.get("relevance", 0),
                "text_score": 0,
                "content": result.get("content", ""),
                "metadata": result.get("metadata", {}),
                "created_at": result.get("created_at"),
                "semantic_result": result
            }
        
        # Add text results
        for result in text_results:
            file_id = result["file_id"]
            if file_id in file_results:
                file_results[file_id]["text_score"] = result.get("relevance", 0)
                file_results[file_id]["text_result"] = result
            else:
                file_results[file_id] = {
                    "file_id": file_id,
                    "semantic_score": 0,
                    "text_score": result.get("relevance", 0),
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "created_at": result.get("created_at"),
                    "text_result": result
                }
        
        # Calculate combined scores
        combined_results = []
        for file_id, result in file_results.items():
            combined_score = (
                result["semantic_score"] * semantic_weight +
                result["text_score"] * text_weight
            )
            
            result["combined_score"] = combined_score
            combined_results.append(result)
        
        return combined_results
    
    # ==================== EMBEDDING MANAGEMENT ====================
    
    async def get_embedding(self, file_id: str) -> Dict[str, Any]:
        """Get embedding for specific file"""
        
        try:
            if not self.table:
                await self.ensure_table()
            
            # Search for file
            def _search():
                return self.table.search().where(f"file_id = '{file_id}'").limit(1).to_pandas()
            
            df = await asyncio.get_event_loop().run_in_executor(None, _search)
            
            if df.empty:
                return {
                    "success": False,
                    "error": "Embedding not found"
                }
            
            row = df.iloc[0]
            
            return {
                "success": True,
                "embedding": {
                    "file_id": row['file_id'],
                    "embedding_model": row['embedding_model'],
                    "embedding_dimension": row['embedding_dimension'],
                    "embedding_text": row['embedding_text'],
                    "created_at": row['created_at'].isoformat() if row.get('created_at') else None,
                    "updated_at": row['updated_at'].isoformat() if row.get('updated_at') else None,
                    "embedding_vector": row['embedding_vector']
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_embedding(self, 
                             file_id: str,
                             text: str,
                             metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update embedding for file"""
        
        try:
            # Generate new embedding
            embedding = await self.generate_embedding(text)
            if not embedding:
                return {
                    "success": False,
                    "error": "Failed to generate embedding"
                }
            
            if not self.table:
                await self.ensure_table()
            
            # Update record
            now = datetime.utcnow()
            record = {
                "embedding_vector": embedding,
                "embedding_text": text,
                "updated_at": now,
                "vector": embedding
            }
            
            if metadata:
                record.update(metadata)
            
            def _update():
                return self.table.update(f"file_id = '{file_id}'", values=record)
            
            await asyncio.get_event_loop().run_in_executor(None, _update)
            
            logger.info(f"Updated embedding for file: {file_id}")
            
            return {
                "success": True,
                "file_id": file_id,
                "embedding_dimension": len(embedding)
            }
        
        except Exception as e:
            logger.error(f"Failed to update embedding: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_embedding(self, file_id: str) -> Dict[str, Any]:
        """Delete embedding for file"""
        
        try:
            if not self.table:
                await self.ensure_table()
            
            # Delete embedding
            def _delete():
                return self.table.delete(f"file_id = '{file_id}'")
            
            await asyncio.get_event_loop().run_in_executor(None, _delete)
            
            # Clear cache
            cache_keys_to_remove = [
                key for key, value in self._embedding_cache.items()
                if value.file_id == file_id
            ]
            for cache_key in cache_keys_to_remove:
                del self._embedding_cache[cache_key]
            
            logger.info(f"Deleted embedding for file: {file_id}")
            
            return {
                "success": True,
                "file_id": file_id
            }
        
        except Exception as e:
            logger.error(f"Failed to delete embedding: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def batch_delete_embeddings(self, file_ids: List[str]) -> Dict[str, Any]:
        """Delete multiple embeddings"""
        
        try:
            if not self.table:
                await self.ensure_table()
            
            deleted_count = 0
            for file_id in file_ids:
                result = await self.delete_embedding(file_id)
                if result["success"]:
                    deleted_count += 1
            
            logger.info(f"Batch deleted {deleted_count} embeddings")
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "total_requested": len(file_ids)
            }
        
        except Exception as e:
            logger.error(f"Failed to batch delete embeddings: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== UTILITY METHODS ====================
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory service statistics"""
        
        try:
            if not self.table:
                await self.ensure_table()
            
            # Get table stats
            def _get_stats():
                # Get row count
                df = self.table.to_pandas()
                row_count = len(df)
                
                # Get model info
                models = df['embedding_model'].unique() if not df.empty else []
                
                # Get dimension info
                dimensions = df['embedding_dimension'].unique() if not df.empty else []
                
                # Get date range
                dates = df['created_at'] if not df.empty else []
                min_date = dates.min() if not dates.empty else None
                max_date = dates.max() if not dates.empty else None
                
                return {
                    "total_embeddings": row_count,
                    "embedding_models": models.tolist(),
                    "embedding_dimensions": dimensions.tolist(),
                    "min_created_at": min_date.isoformat() if min_date else None,
                    "max_created_at": max_date.isoformat() if max_date else None,
                    "cache_size": len(self._embedding_cache),
                    "search_cache_size": len(self._search_cache)
                }
            
            stats = await asyncio.get_event_loop().run_in_executor(None, _get_stats)
            
            return {
                "success": True,
                "stats": stats,
                "configuration": {
                    "embedding_model": self.lancedb_config.embedding_model,
                    "embedding_dimension": self.lancedb_config.embedding_dimension,
                    "batch_size": self.batch_size,
                    "cache_ttl": self.cache_ttl
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def clear_cache(self):
        """Clear all caches"""
        
        self._embedding_cache.clear()
        self._search_cache.clear()
        
        logger.info("Memory service cache cleared")
    
    async def optimize_index(self):
        """Optimize LanceDB index for better performance"""
        
        try:
            if not self.table:
                await self.ensure_table()
            
            # Create IVF index for faster vector search
            def _optimize():
                return self.table.create_index(
                    metric="cosine",
                    num_partitions=self.lancedb_config.index_partitions,
                    num_sub_vectors=16
                )
            
            await asyncio.get_event_loop().run_in_executor(None, _optimize)
            
            logger.info("LanceDB index optimized")
            
            return {
                "success": True,
                "message": "Index optimized successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to optimize index: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for memory service"""
        
        try:
            # Check LanceDB connection
            db_connected = self.db is not None
            table_exists = self.table is not None
            
            # Check embedding model
            model_available = self.embedding_model is not None
            
            # Test basic operations
            test_result = await self.generate_embedding("test")
            model_working = len(test_result) > 0
            
            # Get stats
            stats_result = await self.get_stats()
            
            status = "healthy" if all([
                db_connected,
                table_exists,
                model_available,
                model_working,
                stats_result["success"]
            ]) else "degraded"
            
            return {
                "status": status,
                "database_connected": db_connected,
                "table_exists": table_exists,
                "model_available": model_available,
                "model_working": model_working,
                "stats": stats_result.get("stats", {}),
                "configuration": {
                    "lancedb_path": self.lancedb_config.path,
                    "embedding_model": self.lancedb_config.embedding_model,
                    "batch_size": self.batch_size
                }
            }
        
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

# Global memory service instance
_google_drive_memory_service: Optional[GoogleDriveMemoryService] = None

async def get_google_drive_memory_service() -> Optional[GoogleDriveMemoryService]:
    """Get global Google Drive memory service instance"""
    
    global _google_drive_memory_service
    
    if _google_drive_memory_service is None:
        try:
            config = get_config_instance()
            _google_drive_memory_service = GoogleDriveMemoryService(config)
            await _google_drive_memory_service.connect()
            logger.info("Google Drive Memory Service created and connected")
        except Exception as e:
            logger.error(f"Failed to create Google Drive Memory Service: {e}")
            _google_drive_memory_service = None
    
    return _google_drive_memory_service

def clear_google_drive_memory_service():
    """Clear global memory service instance"""
    
    global _google_drive_memory_service
    _google_drive_memory_service = None
    logger.info("Google Drive Memory Service cleared")

# Export classes and functions
__all__ = [
    'GoogleDriveMemoryService',
    'VectorEmbedding',
    'SearchResult',
    'get_google_drive_memory_service',
    'clear_google_drive_memory_service'
]