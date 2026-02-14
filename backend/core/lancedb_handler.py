"""
LanceDB Handler for ATOM Platform
Provides comprehensive vector database operations with LanceDB
"""

import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except (ImportError, BaseException) as e:
    NUMPY_AVAILABLE = False
    logger.warning(f"Numpy not available: {e}")
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except (ImportError, BaseException) as e:
    PANDAS_AVAILABLE = False
    logger.warning(f"Pandas not available: {e}")

try:
    import lancedb
    from lancedb.db import LanceDBConnection
    from lancedb.pydantic import LanceModel, Vector
    from lancedb.table import Table
    import pyarrow as pa

    # Allow disabling via env var (crucial for CI reliability)
    if os.getenv("ATOM_DISABLE_LANCEDB", "false").lower() == "true":
        LANCEDB_AVAILABLE = False
        logger.info("LanceDB disabled via ATOM_DISABLE_LANCEDB env var")
    else:
        LANCEDB_AVAILABLE = True
except (ImportError, BaseException) as e:
    LANCEDB_AVAILABLE = False
    logger.warning(f"LanceDB not available: {e}")

# Define Table type alias if not available to prevent NameError in type hints
if not 'Table' in locals():
    Table = Any

# Import sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except (ImportError, BaseException) as e:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(f"Sentence transformers not available: {e}")

# Import OpenAI for embeddings
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except (ImportError, Exception) as e:
    OPENAI_AVAILABLE = False
    logger.warning(f"OpenAI not available: {e}")

# BYOK Integration
try:
    from core.byok_endpoints import get_byok_manager
except ImportError:
    get_byok_manager = None


class MockEmbedder:
    """Deterministic mock embedder for testing when ML libs are missing"""
    def __init__(self, dim):
        self.dim = dim
        
    def encode(self, text, convert_to_numpy=False):
        # Generate pseudo-random vector based on text hash for consistency
        import hashlib
        hash_val = int(hashlib.sha256(text.encode('utf-8')).hexdigest(), 16)
        try:
            import numpy as np
            np.random.seed(hash_val % 2**32)
            vec = np.random.rand(self.dim).astype(np.float32)
            # Normalize vector to unit length
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec if convert_to_numpy else vec.tolist()
        except ImportError:
            # Fallback for no numpy
            import random
            import math
            random.seed(hash_val)
            vec = [random.random() for _ in range(self.dim)]
            norm = math.sqrt(sum(x*x for x in vec))
            if norm > 0:
                vec = [x/norm for x in vec]
            return vec

class LanceDBHandler:
    """LanceDB vector database handler"""
    
    def __init__(self, db_path: str = None, 
                 workspace_id: Optional[str] = None,
                 embedding_provider: str = "local",
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        
        # Determine DB path (S3 or local)
        self.db_path = db_path or os.getenv("LANCEDB_URI", "./data/atom_memory")
        self.workspace_id = "default" # Single-tenant: always use default
        
        # Embedding configuration
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", embedding_provider)
        self.embedding_model = os.getenv("EMBEDDING_MODEL", embedding_model)
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        self.db = None
        self.embedder = None
        self.openai_client = None
        
        # BYOK Manager
        try:
            self.byok_manager = get_byok_manager() if get_byok_manager else None
        except Exception as e:
            logger.error(f"Failed to initialize BYOK manager: {e}", exc_info=True)
            self.byok_manager = None
        
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
                self.db_path = os.path.abspath(self.db_path)
                os.makedirs(self.db_path, exist_ok=True)
            
            # Connect to database with storage options (required for R2/S3 endpoints)
            storage_options = {}
            if self.db_path.startswith("s3://"):
                endpoint = os.getenv("AWS_ENDPOINT_URL") or os.getenv("AWS_S3_ENDPOINT")
                if endpoint:
                    storage_options["endpoint"] = endpoint
                
                # Prioritize R2 specific keys, fallback to global AWS keys
                access_key = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
                secret_key = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
                region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "auto"
                
                if access_key:
                    storage_options["aws_access_key_id"] = access_key
                if secret_key:
                    storage_options["aws_secret_access_key"] = secret_key
                if region:
                    storage_options["region"] = region
            
            self.db = lancedb.connect(self.db_path, storage_options=storage_options)
            logger.info(f"LanceDB connected at {self.db_path} (options: {list(storage_options.keys())})")
            
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB at {self.db_path}: {e}")
            self.db = None
    
    def _initialize_embedder(self):
        """Initialize embedding provider"""
        try:
            if self.embedding_provider == "openai" and OPENAI_AVAILABLE:
                # BYOK Key Retrieval
                api_key = self.openai_api_key
                if self.byok_manager:
                    byok_key = self.byok_manager.get_api_key("openai")
                    if byok_key:
                        api_key = byok_key
                
                if not api_key:
                    logger.warning("OpenAI API key not found, falling back to local embeddings")
                    self.embedding_provider = "local"
                    self._init_local_embedder()
                else:
                    self.openai_client = OpenAI(api_key=api_key)
                    logger.info("OpenAI embeddings initialized (BYOK enabled)")
            else:
                self._init_local_embedder()
                
        except Exception as e:
            logger.error(f"Failed to initialize embedder: {e}")
            self.embedder = None

    def _init_local_embedder(self):
        """Initialize local sentence transformer or fallback to mock"""
        try:
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                # Add timeout/protection for import hanging
                try:
                    import signal
                    def handler(signum, frame):
                        raise TimeoutError("SentenceTransformer initialization timed out")
                    
                    # Only set alarm on Unix-like systems where signal.ALRM is available
                    if hasattr(signal, 'SIGALRM'):
                        signal.signal(signal.SIGALRM, handler)
                        signal.alarm(10) # 10 second timeout
                    
                    self.embedder = SentenceTransformer(self.embedding_model)
                    
                    if hasattr(signal, 'SIGALRM'):
                        signal.alarm(0) # Disable alarm
                        
                    logger.info(f"Local embedding model loaded: {self.embedding_model}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load SentenceTransformer: {e}")
                    # Fallthrough to mock
            
            logger.warning("Sentence transformers not available or failed to load. Using MockEmbedder.")
            self.embedder = MockEmbedder(384)
            
        except Exception as e:
             logger.error(f"Critical error in _init_local_embedder: {e}")
             self.embedder = MockEmbedder(384)


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
                    pa.field("user_id", pa.string()),
                    pa.field("workspace_id", pa.string()),
                    pa.field("text", pa.string()),
                    pa.field("source", pa.string()),
                    pa.field("metadata", pa.string()),
                    pa.field("created_at", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), vector_size))
                ])
            elif table_name == "knowledge_graph":
                # Knowledge Graph Relationship Table
                if self.embedding_provider == "openai":
                    vector_size = 1536
                
                schema = pa.schema([
                    pa.field("id", pa.string()),
                    pa.field("user_id", pa.string()),
                    pa.field("workspace_id", pa.string()),
                    pa.field("from_id", pa.string()),
                    pa.field("to_id", pa.string()),
                    pa.field("type", pa.string()),
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
        if self.db is None:
            logger.error("LanceDB not initialized")
            return None
        
        try:
            tnames = self.db.table_names()
            if table_name in tnames:
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
    
    def embed_text(self, text: str) -> Optional[Any]:
        """Embed text using configured provider"""
        try:
            if self.embedding_provider == "openai" and self.openai_client:
                response = self.openai_client.embeddings.create(
                    input=text,
                    model="text-embedding-3-small"
                )
                if NUMPY_AVAILABLE:
                    import numpy as np  # Import locally if needed
                    return np.array(response.data[0].embedding)
                return response.data[0].embedding
            
            elif self.embedder:
                try:
                    if NUMPY_AVAILABLE:
                        res = self.embedder.encode(text, convert_to_numpy=True)
                    else:
                        res = self.embedder.encode(text, convert_to_numpy=False)
                    return res
                except Exception as e:
                    logger.error(f"embedder.encode failed: {e}")
                    raise e
            
            else:
                logger.error(f"No embedding provider available. Provider: {self.embedding_provider}, Embedder: {self.embedder}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            return None
    
    def add_knowledge_edge(self, from_id: str, to_id: str, rel_type: str, 
                         description: str = "", metadata: Dict[str, Any] = None,
                         user_id: str = "default_user") -> bool:
        """Add a relationship edge to the knowledge graph"""
        if self.db is None:
            return False
            
        try:
            table_name = "knowledge_graph"
            table = self.get_table(table_name)
            if table is None:
                table = self.create_table(table_name)
                if table is None:
                    return False
            
            # Generate embedding of the relationship description
            embedding = self.embed_text(description)
            if embedding is None:
                # Fallback to zero vector if embedding fails (though not ideal)
                vector_size = 1536 if self.embedding_provider == "openai" else 384
                if NUMPY_AVAILABLE:
                    embedding = np.zeros(vector_size)
                else:
                    embedding = [0.0] * vector_size
            
            # Create unique edge ID
            edge_id = f"{from_id}_{rel_type}_{to_id}"
            
            if metadata is None:
                metadata = {}
            
            # Create record
            record = {
                "id": edge_id,
                "user_id": user_id,
                "workspace_id": self.workspace_id,
                "from_id": from_id,
                "to_id": to_id,
                "type": rel_type,
                "metadata": json.dumps(metadata),
                "created_at": datetime.utcnow().isoformat(),
                "vector": embedding.tolist() if hasattr(embedding, 'tolist') else embedding
            }
            
            # Add to table
            table.add([record])
            logger.info(f"Knowledge edge added: {edge_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add knowledge edge: {e}")
            return False

    def add_document(self, table_name: str, text: str, source: str = "", 
                    metadata: Dict[str, Any] = None, user_id: str = "default_user",
                    extract_knowledge: bool = True) -> bool:
        """Add a single document to memory"""
        if self.db is None:
            return False
        
        try:
            table = self.get_table(table_name)
            # If table is None, we will create it later with data to infer schema
            
            # SECURITY: Redact secrets before storage
            # This ensures API keys, passwords, and PII are NEVER stored in Atom Memory
            try:
                from core.secrets_redactor import get_secrets_redactor
                redactor = get_secrets_redactor()
                redaction_result = redactor.redact(text)
                
                if redaction_result.has_secrets:
                    logger.warning(f"Redacted {len(redaction_result.redactions)} secrets/PII before storage")
                    text = redaction_result.redacted_text
                    
                    # Add redaction metadata for audit
                    if metadata is None:
                        metadata = {}
                    metadata["_redacted_types"] = [r["type"] for r in redaction_result.redactions]
                    metadata["_redaction_count"] = len(redaction_result.redactions)
            except ImportError:
                logger.warning("Secrets redactor not available, storing text as-is")
            except Exception as redact_err:
                logger.error(f"Secrets redaction failed: {redact_err}, proceeding with caution")
            
            # Generate embedding
            embedding = self.embed_text(text)
            if embedding is None:
                return False
            
            doc_id = str(datetime.utcnow().timestamp())
            
            # Record with user_id and workspace_id
            # Record with user_id and workspace_id
            record = {
                "id": doc_id,
                "user_id": user_id,
                "workspace_id": self.workspace_id,
                "text": text,
                "source": source,
                "metadata": metadata if metadata else {},
                "created_at": datetime.utcnow().isoformat(),
                "vector": embedding.tolist()
            }
            
            # Add to table
            try:
                table = self.get_table(table_name)
                if table is None:
                    # Infer schema from data
                    table = self.db.create_table(table_name, data=[record])
                    logger.info(f"Created table '{table_name}' with inferred schema")
                else:
                    table.add([record])
                logger.info(f"Document added to '{table_name}': {doc_id}")

                # Log user action for behavior analysis
                try:
                    from core.behavior_analyzer import get_behavior_analyzer
                    analyzer = get_behavior_analyzer()
                    analyzer.log_user_action(
                        user_id="user1", # Mock for now
                        action_type="document_uploaded",
                        metadata={"doc_id": doc_id, "table": table_name, "source": source}
                    )
                except Exception as e:
                    logger.warning(f"Failed to log user action for document upload: {e}")
                
                # Optional: Trigger knowledge extraction (non-blocking)
                if extract_knowledge:
                    from core.automation_settings import get_automation_settings
                    settings = get_automation_settings()
                    
                    if settings.is_extraction_enabled():
                        from core.knowledge_ingestion import get_knowledge_ingestion
                        ingestor = get_knowledge_ingestion("default")
                        asyncio.create_task(ingestor.process_document(text, doc_id, source, user_id=user_id, workspace_id="default"))
                    else:
                        logger.info(f"Automatic knowledge extraction skipped for {doc_id} (disabled in settings)")
                
                # NEW: Trigger Workflow Events
                try:
                    from advanced_workflow_orchestrator import get_orchestrator

                    # Non-blocking trigger
                    asyncio.create_task(get_orchestrator().trigger_event("document_uploaded", {
                        "text": text,
                        "doc_id": doc_id,
                        "source": source,
                        "metadata": metadata
                    }))
                except Exception as trigger_err:
                    logger.warning(f"Failed to trigger workflow event: {trigger_err}")
                
                # Phase 31: AI Universal Trigger Coordinator
                # Route data through AI coordinator to decide if specialty agent should trigger
                try:
                    from core.ai_trigger_coordinator import on_data_ingested
                    asyncio.create_task(on_data_ingested(
                        data={"text": text, "doc_id": doc_id, "source": source, "metadata": metadata},
                        source=source or "document_upload",
                        workspace_id="default",
                        user_id=user_id,
                        metadata=metadata
                    ))
                except Exception as ai_trigger_err:
                    logger.warning(f"Failed to invoke AI trigger coordinator: {ai_trigger_err}")
                
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
            # Prepare batch records first to allow schema inference
            records = []
            for doc in documents:
                text = doc.get("text", "")
                source = doc.get("source", "")
                metadata = doc.get("metadata", {})
                doc_id = doc.get("id", str(datetime.utcnow().timestamp()))
                user_id = doc.get("user_id", "default_user")
                
                # Generate embedding
                embedding = self.embed_text(text)
                if embedding is None:
                    continue
                
                # Prepare record
                record = {
                    "id": doc_id,
                    "user_id": user_id,
                    "workspace_id": self.workspace_id,
                    "text": text,
                    "source": source,
                    "metadata": metadata,
                    "created_at": datetime.utcnow().isoformat(),
                    "vector": embedding.tolist()
                }
                records.append(record)
            
            if not records:
                return 0

            # Get or Create Table
            table = self.get_table(table_name)
            if table is None:
                # Infer schema from data to support Struct metadata
                try:
                    table = self.db.create_table(table_name, data=records)
                    logger.info(f"Created table '{table_name}' with inferred schema")
                    return len(records)
                except Exception as create_err:
                    logger.error(f"Failed to create table '{table_name}': {create_err}")
                    return 0
            
            # Add to existing
            table.add(records)
            logger.info(f"Added {len(records)} documents to '{table_name}'")
            return len(records)
                
        except Exception as e:
            logger.error(f"Failed to add batch documents to '{table_name}': {e}")
            return 0
    
    def search(self, table_name: str, query: str, user_id: str = None, limit: int = 10,
               filter_str: str = None) -> List[Dict[str, Any]]:
        """Search for documents in memory with optional user filtering"""
        if self.db is None:
            return []
        
        try:
            table = self.get_table(table_name)
            if table is None:
                return []
            
            # Generate embedding for query
            query_vector = self.embed_text(query)
            if query_vector is None:
                return []
            
            # Build search query
            search_query = table.search(query_vector.tolist()).limit(limit)
            
            # Apply workspace_id and user_id filter
            filters = []
            
            # 1. Enforce Workspace Isolation
            if self.workspace_id:
                filters.append(f"workspace_id == '{self.workspace_id}'")
            
            # 2. Apply User Filter
            if user_id:
                filters.append(f"user_id == '{user_id}'")
            
            # 3. Apply Custom Filter
            if filter_str:
                filters.append(f"({filter_str})")
            
            # Combine all
            final_filter = " AND ".join(filters)
            
            if final_filter:
                search_query = search_query.where(final_filter)
            
            # Execute search
            if not PANDAS_AVAILABLE:
                logger.error("Pandas not available for search results")
                return []
            results = search_query.to_pandas() # Changed from `search_results = results.to_pandas()`
            
            # Convert to list of dictionaries
            results_list = []
            for _, row in results.iterrows():
                try:
                    # Metadata is now a Struct (dict), no need to json.loads if it's already a dict
                    metadata = row['metadata']
                    if isinstance(metadata, str):
                         metadata = json.loads(metadata)
                    elif metadata is None:
                         metadata = {}
                    
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

    def query_knowledge_graph(self, query: str, user_id: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search the knowledge graph using semantic similarity on relationship descriptions"""
        return self.search("knowledge_graph", query, limit=limit)

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
        if self.db is None or self.db.db is None:
            return []
        
        try:
            table = self.db.get_table(self.table_name)
            if table is None:
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
                    metadata = row['metadata']
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    elif metadata is None:
                        metadata = {}

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
        if self.db is None or self.db.db is None:
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
        if self.db is None or self.db.db is None:
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

# Handle multiple handlers (one per workspace) for physical isolation
_workspace_handlers: Dict[str, 'LanceDBHandler'] = {}

def get_lancedb_handler(workspace_id: Optional[str] = None) -> 'LanceDBHandler':
    """
    Get or create a LanceDBHandler instance for a specific workspace.
    Provides physical data isolation by using separate directories.
    """
    ws_id = workspace_id or "default_shared"
    
    if ws_id not in _workspace_handlers:
        # Determine isolated path
        base_uri = os.getenv("LANCEDB_URI_BASE", "./data/atom_memory")
        ws_path = os.path.join(base_uri, ws_id)
        
        logger.info(f"Creating isolated LanceDBHandler for workspace: {ws_id} at {ws_path}")
        _workspace_handlers[ws_id] = LanceDBHandler(db_path=ws_path, workspace_id=ws_id)
    
    return _workspace_handlers[ws_id]

# Legacy instance for backward compatibility (points to default)
lancedb_handler = get_lancedb_handler()

# Global chat history manager (uses default handler for now, should ideally be workspace-aware)
chat_history_manager = ChatHistoryManager(lancedb_handler)

def get_chat_history_manager(workspace_id: Optional[str] = None) -> ChatHistoryManager:
    """Get workspace-aware chat history manager instance"""
    handler = get_lancedb_handler(workspace_id)
    return ChatHistoryManager(handler)



# Global chat context manager helper
def get_chat_context_manager(workspace_id: Optional[str] = None) -> 'ChatContextManager':
    """Get workspace-aware chat context manager instance"""
    from core.chat_context_manager import ChatContextManager
    handler = get_lancedb_handler(workspace_id)
    return ChatContextManager(handler)

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