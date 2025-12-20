"""
LanceDB Handler for ATOM Platform
Provides comprehensive vector database operations with LanceDB
"""

import os
import json
import logging
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Numpy not available")
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Pandas not available")

try:
    import lancedb
    from lancedb.db import LanceDBConnection
    from lancedb.table import Table
    from lancedb.pydantic import LanceModel, Vector
    import pyarrow as pa
    LANCEDB_AVAILABLE = True
except (ImportError, Exception) as e:
    LANCEDB_AVAILABLE = False
    print(f"LanceDB not available: {e}")

# Import sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except (ImportError, Exception) as e:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print(f"Sentence transformers not available: {e}")

# Import OpenAI for embeddings
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except (ImportError, Exception) as e:
    OPENAI_AVAILABLE = False
    print(f"OpenAI not available: {e}")

logger = logging.getLogger(__name__)

class LanceDBHandler:
    """LanceDB vector database handler"""
    
    def __init__(self, db_path: str = None, 
                 embedding_provider: str = "local",
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        
        # Determine DB path (S3 or local)
        self.db_path = db_path or os.getenv("LANCEDB_URI", "./data/atom_memory")
        
        # Embedding configuration
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", embedding_provider)
        self.embedding_model = os.getenv("EMBEDDING_MODEL", embedding_model)
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        self.db = None
        self.embedder = None
        self.openai_client = None
        
        # Initialize LanceDB if available
        logger.info(f"LanceDBHandler initialized. ID: {id(self)}. LANCEDB_AVAILABLE: {LANCEDB_AVAILABLE}")
        if LANCEDB_AVAILABLE:
            self._initialize_db()
        
        # Initialize embedder
        self._initialize_embedder()
    
    def _initialize_db(self):
        """Initialize LanceDB connection"""
        try:
            # Handle local path creation
            if not self.db_path.startswith("s3://"):
                Path(self.db_path).mkdir(parents=True, exist_ok=True)
            
            # Connect to database
            self.db = lancedb.connect(self.db_path)
            logger.info(f"LanceDB connected at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB: {e}")
            self.db = None
    
    def _initialize_embedder(self):
        """Initialize embedding provider"""
        try:
            if self.embedding_provider == "openai" and OPENAI_AVAILABLE:
                if not self.openai_api_key:
                    logger.warning("OpenAI API key not found, falling back to local embeddings")
                    self.embedding_provider = "local"
                    self._init_local_embedder()
                else:
                    self.openai_client = OpenAI(api_key=self.openai_api_key)
                    logger.info("OpenAI embeddings initialized")
            else:
                self._init_local_embedder()
                
        except Exception as e:
            logger.error(f"Failed to initialize embedder: {e}")
            self.embedder = None

    def _init_local_embedder(self):
        """Initialize local sentence transformer"""
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            self.embedder = SentenceTransformer(self.embedding_model)
            logger.info(f"Local embedding model loaded: {self.embedding_model}")
        else:
            logger.error("Sentence transformers not available for local embeddings")

    def test_connection(self) -> Dict[str, Any]:
        """Test LanceDB connection"""
        if not LANCEDB_AVAILABLE:
            return {
                "status": "error",
                "message": "LanceDB not available",
                "connected": False
            }
        
        try:
            if self.db is None:
                return {
                    "status": "error",
                    "message": "LanceDB not initialized",
                    "connected": False
                }
            
            # List tables to test connection
            tables = self.db.table_names()
            return {
                "status": "success",
                "message": "LanceDB connection successful",
                "connected": True,
                "tables": tables,
                "db_path": self.db_path,
                "embedding_provider": self.embedding_provider
            }
            
        except Exception as e:
            logger.error(f"LanceDB connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "connected": False
            }
    
    def create_table(self, table_name: str, schema: Optional[Dict[str, Any]] = None,
                    vector_size: int = 384) -> Optional[Table]:
        """Create a new table"""
        if self.db is None:
            logger.error("LanceDB not initialized")
            return None
        
        try:
            # Create schema if not provided
            if schema is None:
                # Adjust vector size for OpenAI
                if self.embedding_provider == "openai":
                    vector_size = 1536
                
                # Create PyArrow schema
                schema = pa.schema([
                    pa.field("id", pa.string()),
                    pa.field("text", pa.string()),
                    pa.field("source", pa.string()),
                    pa.field("metadata", pa.string()),
                    pa.field("created_at", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), vector_size))
                ])
            
            # Create table
            table = self.db.create_table(table_name, schema=schema, mode="overwrite")
            logger.info(f"Table '{table_name}' created/accessed successfully")
            return table
            
        except Exception as e:
            logger.error(f"Failed to create table '{table_name}': {e}")
            return None
    
    def get_table(self, table_name: str) -> Optional[Table]:
        """Get existing table"""
        logger.info(f"get_table called on instance {id(self)}. self.db is {self.db}")
        if self.db is None:
            logger.error("LanceDB not initialized")
            return None
        
        try:
            if table_name in self.db.table_names():
                return self.db.open_table(table_name)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get table '{table_name}': {e}")
            return None
    
    def drop_table(self, table_name: str) -> bool:
        """Drop a table"""
        if self.db is None:
            logger.error("LanceDB not initialized")
            return False
        
        try:
            if table_name in self.db.table_names():
                self.db.drop_table(table_name)
                logger.info(f"Table '{table_name}' dropped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to drop table '{table_name}': {e}")
            return False
    
    def embed_text(self, text: str) -> Optional[np.ndarray]:
        """Embed text using configured provider"""
        try:
            if self.embedding_provider == "openai" and self.openai_client:
                response = self.openai_client.embeddings.create(
                    input=text,
                    model="text-embedding-3-small"
                )
                if NUMPY_AVAILABLE:
                    return np.array(response.data[0].embedding)
                return response.data[0].embedding
            
            elif self.embedder:
                if NUMPY_AVAILABLE:
                    return self.embedder.encode(text, convert_to_numpy=True)
                return self.embedder.encode(text, convert_to_numpy=False)
            
            else:
                logger.error(f"No embedding provider available. Provider: {self.embedding_provider}, Embedder: {self.embedder}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            return None
    
    def add_document(self, table_name: str, text: str, source: str = "",
                    metadata: Dict[str, Any] = None, doc_id: str = None) -> bool:
        """Add a document to the vector database"""
        if self.db is None:
            return False
        
        try:
            table = self.get_table(table_name)
            if table is None:
                table = self.create_table(table_name)
                if table is None:
                    return False
            
            # Generate embedding
            embedding = self.embed_text(text)
            if embedding is None:
                return False
            
            # Prepare data
            if doc_id is None:
                doc_id = str(datetime.utcnow().timestamp())
            
            if metadata is None:
                metadata = {}
            
            # Create record
            record = {
                "id": doc_id,
                "text": text,
                "source": source,
                "metadata": json.dumps(metadata),
                "created_at": datetime.utcnow().isoformat(),
                "vector": embedding.tolist()
            }
            
            # Add to table
            try:
                table.add([record])
                logger.info(f"Document added to '{table_name}': {doc_id}")
                return True
            except Exception as e:
                logger.error(f"CRITICAL: Failed to add record to table '{table_name}': {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False
                
        except Exception as e:
            logger.error(f"Failed to add document to '{table_name}': {e}")
            return False
    
    def add_documents_batch(self, table_name: str, documents: List[Dict[str, Any]]) -> int:
        """Add multiple documents in batch"""
        if self.db is None:
            return 0
        
        try:
            table = self.get_table(table_name)
            if not table:
                table = self.create_table(table_name)
                if not table:
                    return 0
            
            # Prepare batch records
            records = []
            for doc in documents:
                text = doc.get("text", "")
                source = doc.get("source", "")
                metadata = doc.get("metadata", {})
                doc_id = doc.get("id", str(datetime.utcnow().timestamp()))
                
                # Generate embedding
                embedding = self.embed_text(text)
                if embedding is None:
                    continue
                
                # Prepare record
                record = {
                    "id": doc_id,
                    "text": text,
                    "source": source,
                    "metadata": json.dumps(metadata),
                    "created_at": datetime.utcnow().isoformat(),
                    "vector": embedding.tolist()
                }
                records.append(record)
            
            if records:
                table.add(records)
                logger.info(f"Added {len(records)} documents to '{table_name}'")
                return len(records)
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Failed to add batch documents to '{table_name}': {e}")
            return 0
    
    def search(self, table_name: str, query: str, limit: int = 10,
              filter_expression: str = None) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        if self.db is None:
            return []
        
        try:
            table = self.get_table(table_name)
            if table is None:
                logger.warning(f"Table '{table_name}' does not exist")
                return []
            
            # Generate query embedding
            query_embedding = self.embed_text(query)
            if query_embedding is None:
                return []
            
            # Search
            results = table.search(query_embedding).limit(limit)
            
            # Apply filter if provided
            if filter_expression:
                results = results.where(filter_expression)
            
            # Execute search
            if not PANDAS_AVAILABLE:
                logger.error("Pandas not available for search results")
                return []
            search_results = results.to_pandas()
            
            # Convert to list of dictionaries
            results_list = []
            for _, row in search_results.iterrows():
                try:
                    metadata = json.loads(row['metadata']) if row['metadata'] else {}
                    result = {
                        "id": row['id'],
                        "text": row['text'],
                        "source": row['source'],
                        "metadata": metadata,
                        "created_at": row['created_at'],
                        "score": 1.0 - row.get('_distance', 0.0) # Convert distance to similarity score
                    }
                    results_list.append(result)
                except Exception as e:
                    logger.warning(f"Error parsing search result: {e}")
                    continue
            
            return results_list
            
        except Exception as e:
            logger.error(f"Failed to search in '{table_name}': {e}")
            return []

    def seed_mock_data(self, documents: List[Dict[str, Any]]) -> int:
        """Seed mock data for validation"""
        return self.add_documents_batch("documents", documents)

# Chat History Extension for LanceDBHandler
class ChatHistoryManager:
    """Manages chat history using LanceDB for semantic search"""
    
    def __init__(self, lancedb_handler: LanceDBHandler):
        self.db = lancedb_handler
        self.table_name = "chat_messages"
        self._ensure_table()
    
    def _ensure_table(self):
        """Ensure chat_messages table exists"""
        if self.db.db is None:
            logger.warning("LanceDB not initialized, chat history disabled")
            return
            
        try:
            # Create table if it doesn't exist
            if self.table_name not in self.db.db.table_names():
                self.db.create_table(self.table_name)
                logger.info(f"Created chat_messages table")
        except Exception as e:
            logger.error(f"Failed to ensure chat_messages table: {e}")
    
    def save_message(
        self,
        session_id: str,
        user_id: str,
        role: str,  # "user" or "assistant"
        content: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Save a chat message with automatic embedding.
        
        metadata can include:
        - intent: str
        - entities: dict (workflow_ids, task_ids, etc.)
        - workflow_id: str
        - task_id: str
        - schedule_id: str
        """
        if self.db.db is None:
            logger.error("save_message: DB is None")
            return False
        
        try:
            logger.info(f"save_message: Saving {role} message for session {session_id}")
            # Prepare metadata
            msg_metadata = metadata or {}
            msg_metadata.update({
                "session_id": session_id,
                "user_id": user_id,
                "role": role
            })
            
            # Create unique message ID
            message_id = f"{session_id}_{datetime.utcnow().timestamp()}"
            
            # Save using existing add_document method
            success = self.db.add_document(
                table_name=self.table_name,
                text=content,
                source=f"chat_{role}",
                metadata=msg_metadata,
                doc_id=message_id
            )
            
            if success:
                logger.debug(f"Saved chat message: {message_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to save chat message: {e}")
            return False
    
    def get_session_history(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent messages from a session (chronological order).
        
        Returns list of messages with:
        - id, text, source, role, created_at, metadata
        """
        if not self.db.db:
            return []
        
        try:
            table = self.db.get_table(self.table_name)
            if not table:
                return []
            
            # Query all messages for session (LanceDB doesn't have chronological sorting built-in)
            # So we'll fetch all and sort in memory
            # For better performance with large histories, consider using filter + limit
            
            if not PANDAS_AVAILABLE:
                logger.error("Pandas not available for session history")
                return []
            results = table.search().where(f"metadata LIKE '%{session_id}%'").limit(limit * 2).to_pandas()
            
            # Parse and filter
            messages = []
            for _, row in results.iterrows():
                try:
                    metadata = json.loads(row['metadata']) if row['metadata'] else {}
                    if metadata.get('session_id') == session_id:
                        messages.append({
                            "id": row['id'],
                            "text": row['text'],
                            "role": metadata.get('role', 'unknown'),
                            "created_at": row['created_at'],
                            "metadata": metadata
                        })
                except Exception as e:
                    logger.warning(f"Error parsing message: {e}")
                    continue
            
            # Sort by created_at
            messages.sort(key=lambda x: x['created_at'])
            
            return messages[-limit:]  # Return most recent
            
        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return []
    
    def search_relevant_context(
        self,
        query: str,
        session_id: str = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find semantically similar messages using vector search.
        
        If session_id provided, search within that session only.
        Otherwise, search across all sessions.
        """
        if not self.db.db:
            return []
        
        try:
            # Use existing search method
            filter_expr = None
            if session_id:
                filter_expr = f"metadata LIKE '%{session_id}%'"
            
            results = self.db.search(
                table_name=self.table_name,
                query=query,
                limit=limit,
                filter_expression=filter_expr
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search relevant context: {e}")
            return []
    
    def get_entity_mentions(
        self,
        entity_type: str,  # "workflow_id", "task_id", "schedule_id"
        entity_id: str,
        session_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Find all messages mentioning a specific entity.
        """
        if not self.db.db:
            return []
        
        try:
            table = self.db.get_table(self.table_name)
            if not table:
                return []
            
            # Search for entity_id in metadata
            filter_expr = f"metadata LIKE '%{entity_id}%'"
            if not PANDAS_AVAILABLE:
                logger.error("Pandas not available for entity mentions")
                return []
            results = table.search().where(filter_expr).limit(50).to_pandas()
            
            # Parse and filter
            messages = []
            for _, row in results.iterrows():
                try:
                    metadata = json.loads(row['metadata']) if row['metadata'] else {}
                    
                    # Check if this message mentions the entity
                    if metadata.get(entity_type) == entity_id:
                        # Filter by session if provided
                        if session_id is None or metadata.get('session_id') == session_id:
                            messages.append({
                                "id": row['id'],
                                "text": row['text'],
                                "role": metadata.get('role'),
                                "created_at": row['created_at'],
                                "metadata": metadata
                            })
                except Exception as e:
                    logger.warning(f"Error parsing message: {e}")
                    continue
            
            # Sort by created_at
            messages.sort(key=lambda x: x['created_at'])
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get entity mentions: {e}")
            return []

# Global instance for easy access (must be first)
lancedb_handler = LanceDBHandler()

def get_lancedb_handler() -> LanceDBHandler:
    """Get LanceDB handler instance"""
    return lancedb_handler

# Global chat history manager (uses lancedb_handler)
chat_history_manager = ChatHistoryManager(lancedb_handler)

def get_chat_history_manager() -> ChatHistoryManager:
    """Get global chat history manager instance"""
    return chat_history_manager

# Global chat context manager (uses lancedb_handler)
from core.chat_context_manager import ChatContextManager
import core.chat_context_manager
core.chat_context_manager.chat_context_manager = ChatContextManager(lancedb_handler)

# Utility functions
def embed_documents_batch(texts: List[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> Optional[Any]:
    """Embed a batch of texts"""
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return None
    
    try:
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer(model_name)
        if NUMPY_AVAILABLE:
            embeddings = embedder.encode(texts, convert_to_numpy=True)
        else:
            embeddings = embedder.encode(texts, convert_to_numpy=False)
        return embeddings
    except Exception as e:
        logger.error(f"Failed to embed batch texts: {e}")
        return None

def create_memory_schema(vector_size: int = 384) -> Dict[str, Any]:
    """Create standard memory schema for ATOM"""
    return {
        "id": str,
        "text": str,
        "source": str,
        "metadata": str,  # JSON string
        "created_at": str,
        "vector": Vector(vector_size)
    }