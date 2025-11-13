"""
LanceDB Handler for ATOM Platform
Provides comprehensive vector database operations with LanceDB
"""

import os
import json
import logging
import numpy as np
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

try:
    import lancedb
    from lancedb.db import LanceDBConnection
    from lancedb.table import Table
    from lancedb.pydantic import LanceModel, Vector
    import pyarrow as pa
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    print("LanceDB not available. Install with: pip install lancedb")

# Import sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("Sentence transformers not available. Install with: pip install sentence-transformers")

logger = logging.getLogger(__name__)

class LanceDBHandler:
    """LanceDB vector database handler"""
    
    def __init__(self, db_path: str = "./data/atom_memory", 
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.db_path = db_path
        self.embedding_model = embedding_model
        self.db = None
        self.embedder = None
        
        # Initialize LanceDB if available
        if LANCEDB_AVAILABLE:
            self._initialize_db()
        
        # Initialize embedder if available
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            self._initialize_embedder()
    
    def _initialize_db(self):
        """Initialize LanceDB connection"""
        try:
            # Create directory if it doesn't exist
            Path(self.db_path).mkdir(parents=True, exist_ok=True)
            
            # Connect to database
            self.db = lancedb.connect(self.db_path)
            logger.info(f"LanceDB connected at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB: {e}")
            self.db = None
    
    def _initialize_embedder(self):
        """Initialize sentence transformer embedder"""
        try:
            self.embedder = SentenceTransformer(self.embedding_model)
            logger.info(f"Embedding model loaded: {self.embedding_model}")
        except Exception as e:
            logger.error(f"Failed to initialize embedder: {e}")
            self.embedder = None
    
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
                "db_path": self.db_path
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
        if not self.db:
            logger.error("LanceDB not initialized")
            return None
        
        try:
            # Create schema if not provided
            if schema is None:
                schema = {
                    "id": str,
                    "text": str,
                    "source": str,
                    "metadata": str,
                    "created_at": str,
                    "vector": Vector(vector_size)
                }
            
            # Create table
            table = self.db.create_table(table_name, schema=schema)
            logger.info(f"Table '{table_name}' created successfully")
            return table
            
        except Exception as e:
            logger.error(f"Failed to create table '{table_name}': {e}")
            return None
    
    def get_table(self, table_name: str) -> Optional[Table]:
        """Get existing table"""
        if not self.db:
            logger.error("LanceDB not initialized")
            return None
        
        try:
            if table_name in self.db.table_names():
                return self.db.open_table(table_name)
            else:
                logger.warning(f"Table '{table_name}' does not exist")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get table '{table_name}': {e}")
            return None
    
    def drop_table(self, table_name: str) -> bool:
        """Drop a table"""
        if not self.db:
            logger.error("LanceDB not initialized")
            return False
        
        try:
            self.db.drop_table(table_name)
            logger.info(f"Table '{table_name}' dropped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to drop table '{table_name}': {e}")
            return False
    
    def embed_text(self, text: str) -> Optional[np.ndarray]:
        """Embed text using sentence transformer"""
        if not self.embedder:
            logger.error("Embedder not initialized")
            return None
        
        try:
            embedding = self.embedder.encode(text, convert_to_numpy=True)
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            return None
    
    def add_document(self, table_name: str, text: str, source: str = "",
                    metadata: Dict[str, Any] = None, doc_id: str = None) -> bool:
        """Add a document to the vector database"""
        if not self.db or not self.embedder:
            return False
        
        try:
            table = self.get_table(table_name)
            if not table:
                # Create table if it doesn't exist
                table = self.create_table(table_name)
                if not table:
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
            
            # Convert metadata to JSON string
            metadata_json = json.dumps(metadata)
            
            # Create record
            record = {
                "id": doc_id,
                "text": text,
                "source": source,
                "metadata": metadata_json,
                "created_at": datetime.utcnow().isoformat(),
                "vector": embedding.tolist()
            }
            
            # Add to table
            table.add([record])
            logger.debug(f"Document added to '{table_name}': {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document to '{table_name}': {e}")
            return False
    
    def add_documents_batch(self, table_name: str, documents: List[Dict[str, Any]]) -> int:
        """Add multiple documents in batch"""
        if not self.db or not self.embedder:
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
        if not self.db or not self.embedder:
            return []
        
        try:
            table = self.get_table(table_name)
            if not table:
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
                        "score": row.get('_distance', 0.0)
                    }
                    results_list.append(result)
                except Exception as e:
                    logger.warning(f"Error parsing search result: {e}")
                    continue
            
            return results_list
            
        except Exception as e:
            logger.error(f"Failed to search in '{table_name}': {e}")
            return []
    
    def get_document(self, table_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID"""
        if not self.db:
            return None
        
        try:
            table = self.get_table(table_name)
            if not table:
                return None
            
            # Query by ID
            results = table.search().where(f"id = '{doc_id}'").limit(1).to_pandas()
            
            if len(results) == 0:
                return None
            
            # Convert to dictionary
            row = results.iloc[0]
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
            
            return {
                "id": row['id'],
                "text": row['text'],
                "source": row['source'],
                "metadata": metadata,
                "created_at": row['created_at']
            }
            
        except Exception as e:
            logger.error(f"Failed to get document {doc_id} from '{table_name}': {e}")
            return None
    
    def delete_document(self, table_name: str, doc_id: str) -> bool:
        """Delete a document by ID"""
        if not self.db:
            return False
        
        try:
            table = self.get_table(table_name)
            if not table:
                return False
            
            # Delete by ID
            table.delete(f"id = '{doc_id}'")
            logger.info(f"Document {doc_id} deleted from '{table_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id} from '{table_name}': {e}")
            return False
    
    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Get table statistics"""
        if not self.db:
            return {}
        
        try:
            table = self.get_table(table_name)
            if not table:
                return {}
            
            # Get count
            count = len(table)
            
            # Get sources
            results = table.search().select(['source']).to_pandas()
            sources = results['source'].value_counts().to_dict()
            
            return {
                "table_name": table_name,
                "document_count": count,
                "sources": sources,
                "db_path": self.db_path
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats for '{table_name}': {e}")
            return {}
    
    def list_tables(self) -> List[str]:
        """List all tables"""
        if not self.db:
            return []
        
        try:
            return self.db.table_names()
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return []
    
    def optimize_table(self, table_name: str) -> bool:
        """Optimize table for better search performance"""
        if not self.db:
            return False
        
        try:
            table = self.get_table(table_name)
            if not table:
                return False
            
            # Optimize index
            table.create_index()
            logger.info(f"Table '{table_name}' optimized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to optimize table '{table_name}': {e}")
            return False
    
    def backup_table(self, table_name: str, backup_path: str) -> bool:
        """Backup table to file"""
        if not self.db:
            return False
        
        try:
            table = self.get_table(table_name)
            if not table:
                return False
            
            # Export table
            df = table.to_pandas()
            df.to_parquet(backup_path, index=False)
            
            logger.info(f"Table '{table_name}' backed up to {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup table '{table_name}': {e}")
            return False
    
    def restore_table(self, table_name: str, backup_path: str) -> bool:
        """Restore table from backup file"""
        if not self.db:
            return False
        
        try:
            # Load backup
            df = pd.read_parquet(backup_path)
            
            # Drop existing table if it exists
            if table_name in self.db.table_names():
                self.db.drop_table(table_name)
            
            # Create new table
            table = self.create_table(table_name)
            if not table:
                return False
            
            # Insert data
            records = df.to_dict('records')
            table.add(records)
            
            logger.info(f"Table '{table_name}' restored from {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore table '{table_name}': {e}")
            return False

# Global instance for easy access
lancedb_handler = LanceDBHandler()

def get_lancedb_handler() -> LanceDBHandler:
    """Get LanceDB handler instance"""
    return lancedb_handler

# Utility functions
def embed_documents_batch(texts: List[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> Optional[np.ndarray]:
    """Embed a batch of texts"""
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return None
    
    try:
        embedder = SentenceTransformer(model_name)
        embeddings = embedder.encode(texts, convert_to_numpy=True)
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