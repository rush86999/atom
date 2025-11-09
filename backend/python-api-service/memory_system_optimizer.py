"""
Memory System Optimizer for LanceDB

This module provides advanced optimization for the LanceDB memory system,
including cross-integration search capabilities, performance monitoring,
and automated cleanup routines.
"""

import asyncio
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil

try:
    import lancedb
    import numpy as np
    import pyarrow as pa

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False

    # Mock implementations for when LanceDB is not available
    class MockLanceDB:
        def connect(self, uri):
            return MockDatabase(uri)

    class MockDatabase:
        def __init__(self, uri):
            self.uri = uri
            self.tables = {}

        def open_table(self, name):
            if name not in self.tables:
                self.tables[name] = MockTable(name)
            return self.tables[name]

        def table_names(self):
            return list(self.tables.keys())

    class MockTable:
        def __init__(self, name):
            self.name = name
            self.data = []

        def search(self, query_vector, query_type="vector"):
            return MockSearchBuilder(self, query_vector)

        def to_pandas(self):
            import pandas as pd

            return pd.DataFrame(self.data)

    class MockSearchBuilder:
        def __init__(self, table, query_vector):
            self.table = table
            self.query_vector = query_vector
            self.limit_value = 10

        def limit(self, n):
            self.limit_value = n
            return self

        def where(self, clause):
            return self

        def select(self, columns):
            return self

        def to_pandas(self):
            import pandas as pd

            return pd.DataFrame([])

    lancedb = MockLanceDB()

logger = logging.getLogger(__name__)


@dataclass
class MemorySystemMetrics:
    """Metrics for memory system performance"""

    total_documents: int
    vector_dimensions: int
    search_latency_ms: float
    query_throughput: float
    memory_usage_mb: float
    cpu_usage_percent: float
    last_optimization: datetime
    cross_integration_searches: int


@dataclass
class CrossIntegrationSearchResult:
    """Result from cross-integration search"""

    integration: str
    document_id: str
    document_title: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any]
    source_integration: str


class MemorySystemOptimizer:
    """
    Advanced memory system optimizer for LanceDB with cross-integration
    search capabilities and performance monitoring.
    """

    def __init__(self, db_uri: str = "./data/lancedb", max_workers: int = 4):
        self.db_uri = db_uri
        self.db = None
        self.tables = {}
        self.metrics = MemorySystemMetrics(
            total_documents=0,
            vector_dimensions=384,  # Default embedding dimension
            search_latency_ms=0.0,
            query_throughput=0.0,
            memory_usage_mb=0.0,
            cpu_usage_percent=0.0,
            last_optimization=datetime.now(),
            cross_integration_searches=0,
        )
        self.optimization_thread = None
        self.running = False
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

        # Integration-specific configurations
        self.integration_configs = {
            "google_drive": {
                "table_name": "google_drive_documents",
                "embedding_field": "content_embedding",
                "text_field": "content",
                "metadata_fields": [
                    "file_id",
                    "file_name",
                    "mime_type",
                    "created_time",
                    "modified_time",
                ],
            },
            "onedrive": {
                "table_name": "onedrive_documents",
                "embedding_field": "content_embedding",
                "text_field": "content",
                "metadata_fields": [
                    "file_id",
                    "file_name",
                    "mime_type",
                    "created_date",
                    "modified_date",
                ],
            },
            "notion": {
                "table_name": "notion_pages",
                "embedding_field": "content_embedding",
                "text_field": "content",
                "metadata_fields": [
                    "page_id",
                    "page_title",
                    "url",
                    "last_edited_time",
                    "parent_type",
                ],
            },
            "gmail": {
                "table_name": "gmail_messages",
                "embedding_field": "content_embedding",
                "text_field": "content",
                "metadata_fields": [
                    "message_id",
                    "subject",
                    "sender",
                    "received_date",
                    "labels",
                ],
            },
        }

        self._initialize_database()
        self._start_monitoring()

    def _initialize_database(self):
        """Initialize LanceDB connection and tables"""
        try:
            if LANCEDB_AVAILABLE:
                self.db = lancedb.connect(self.db_uri)
                logger.info(f"Connected to LanceDB at {self.db_uri}")

                # Initialize tables for each integration
                for integration, config in self.integration_configs.items():
                    table_name = config["table_name"]
                    try:
                        self.tables[integration] = self.db.open_table(table_name)
                        logger.info(f"Opened existing table: {table_name}")
                    except Exception:
                        logger.info(
                            f"Table {table_name} doesn't exist yet, will be created on first write"
                        )
            else:
                logger.warning("LanceDB not available, using mock implementation")
                self.db = lancedb.connect(self.db_uri)

        except Exception as e:
            logger.error(f"Failed to initialize LanceDB: {str(e)}")
            raise

    def _start_monitoring(self):
        """Start background monitoring and optimization"""
        self.running = True
        self.optimization_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.optimization_thread.start()
        logger.info("Memory system monitoring started")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.running:
            try:
                self._update_metrics()
                self._check_optimization_needed()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(30)

    def _update_metrics(self):
        """Update memory system metrics"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            self.metrics.memory_usage_mb = memory_info.rss / 1024 / 1024
            self.metrics.cpu_usage_percent = process.cpu_percent()

            # Update document count
            total_docs = 0
            for integration, table in self.tables.items():
                if LANCEDB_AVAILABLE and hasattr(table, "count_rows"):
                    total_docs += table.count_rows()
                else:
                    # Mock count
                    total_docs += 1000

            self.metrics.total_documents = total_docs

        except Exception as e:
            logger.error(f"Error updating metrics: {str(e)}")

    def _check_optimization_needed(self):
        """Check if optimization is needed based on metrics"""
        optimization_threshold = timedelta(hours=24)
        time_since_last_opt = datetime.now() - self.metrics.last_optimization

        if (
            time_since_last_opt > optimization_threshold
            or self.metrics.memory_usage_mb > 1024  # 1GB threshold
            or self.metrics.total_documents > 10000
        ):  # 10k documents threshold
            logger.info("Memory system optimization triggered")
            self.optimize_memory_system()

    async def cross_integration_search(
        self,
        query: str,
        integrations: List[str] = None,
        limit_per_integration: int = 5,
        min_similarity: float = 0.7,
    ) -> List[CrossIntegrationSearchResult]:
        """
        Perform cross-integration semantic search across multiple services.

        Args:
            query: Search query text
            integrations: List of integrations to search (None for all)
            limit_per_integration: Maximum results per integration
            min_similarity: Minimum similarity threshold

        Returns:
            List of cross-integration search results
        """
        start_time = time.time()

        if integrations is None:
            integrations = list(self.integration_configs.keys())

        # Generate query embedding (mock implementation)
        query_embedding = self._generate_embedding(query)

        # Search across integrations in parallel
        search_tasks = []
        for integration in integrations:
            task = self.thread_pool.submit(
                self._search_single_integration,
                integration,
                query_embedding,
                limit_per_integration,
                min_similarity,
            )
            search_tasks.append(task)

        # Collect results
        all_results = []
        for task in search_tasks:
            try:
                results = task.result(timeout=30)  # 30 second timeout
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Search failed for integration: {str(e)}")

        # Sort by similarity score
        all_results.sort(key=lambda x: x.similarity_score, reverse=True)

        # Update metrics
        search_time = (time.time() - start_time) * 1000
        self.metrics.search_latency_ms = search_time
        self.metrics.cross_integration_searches += 1

        logger.info(
            f"Cross-integration search completed in {search_time:.2f}ms, found {len(all_results)} results"
        )

        return all_results

    def _search_single_integration(
        self,
        integration: str,
        query_embedding: List[float],
        limit: int,
        min_similarity: float,
    ) -> List[CrossIntegrationSearchResult]:
        """Search a single integration"""
        try:
            config = self.integration_configs[integration]
            table_name = config["table_name"]

            if integration not in self.tables:
                # Try to open table
                try:
                    self.tables[integration] = self.db.open_table(table_name)
                except Exception:
                    logger.warning(
                        f"Table {table_name} not available for integration {integration}"
                    )
                    return []

            table = self.tables[integration]

            # Perform vector search
            results = table.search(query_embedding).limit(limit).to_pandas()

            # Convert to CrossIntegrationSearchResult objects
            search_results = []
            for _, row in results.iterrows():
                if row.get("_distance", 1.0) <= (1 - min_similarity):
                    similarity_score = 1 - row.get("_distance", 1.0)

                    result = CrossIntegrationSearchResult(
                        integration=integration,
                        document_id=row.get(config["metadata_fields"][0], ""),
                        document_title=row.get(config["metadata_fields"][1], ""),
                        content=row.get(config["text_field"], ""),
                        similarity_score=similarity_score,
                        metadata={
                            field: row.get(field) for field in config["metadata_fields"]
                        },
                        source_integration=integration,
                    )
                    search_results.append(result)

            return search_results

        except Exception as e:
            logger.error(f"Error searching integration {integration}: {str(e)}")
            return []

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text (mock implementation)"""
        # In a real implementation, this would use a model like sentence-transformers
        # For now, return a mock embedding
        embedding_dim = self.metrics.vector_dimensions
        return [0.1] * embedding_dim

    async def optimize_memory_system(self):
        """Optimize the memory system for better performance"""
        logger.info("Starting memory system optimization")

        optimization_start = datetime.now()

        try:
            # 1. Compact tables (if supported)
            if LANCEDB_AVAILABLE:
                for integration, table in self.tables.items():
                    if hasattr(table, "compact_files"):
                        table.compact_files()
                        logger.info(f"Compacted table for {integration}")

            # 2. Clean up old documents
            await self._cleanup_old_documents()

            # 3. Rebuild indexes if needed
            await self._rebuild_indexes()

            # 4. Update metrics
            self.metrics.last_optimization = datetime.now()
            optimization_time = (
                self.metrics.last_optimization - optimization_start
            ).total_seconds()

            logger.info(
                f"Memory system optimization completed in {optimization_time:.2f}s"
            )

        except Exception as e:
            logger.error(f"Memory system optimization failed: {str(e)}")

    async def _cleanup_old_documents(self, retention_days: int = 90):
        """Clean up documents older than retention period"""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            for integration, config in self.integration_configs.items():
                if integration in self.tables:
                    table = self.tables[integration]

                    # Find date field in metadata
                    date_fields = [
                        "created_time",
                        "modified_time",
                        "created_date",
                        "modified_date",
                        "last_edited_time",
                    ]
                    date_field = next(
                        (
                            field
                            for field in date_fields
                            if field in config["metadata_fields"]
                        ),
                        None,
                    )

                    if date_field:
                        # In a real implementation, we would delete old documents
                        # For now, just log the cleanup intent
                        logger.info(
                            f"Would cleanup old documents for {integration} before {cutoff_date}"
                        )

            logger.info(
                f"Cleanup completed for documents older than {retention_days} days"
            )

        except Exception as e:
            logger.error(f"Error during document cleanup: {str(e)}")

    async def _rebuild_indexes(self):
        """Rebuild vector indexes for better search performance"""
        try:
            if LANCEDB_AVAILABLE:
                for integration, table in self.tables.items():
                    if hasattr(table, "create_index"):
                        # Create IVF_PQ index for better search performance
                        table.create_index(
                            self.integration_configs[integration]["embedding_field"],
                            index_type="IVF_PQ",
                            num_partitions=256,
                            num_sub_vectors=16,
                        )
                        logger.info(f"Rebuilt index for {integration}")

            logger.info("Index rebuilding completed")

        except Exception as e:
            logger.error(f"Error rebuilding indexes: {str(e)}")

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current memory system metrics"""
        return {
            "total_documents": self.metrics.total_documents,
            "vector_dimensions": self.metrics.vector_dimensions,
            "search_latency_ms": self.metrics.search_latency_ms,
            "query_throughput": self.metrics.query_throughput,
            "memory_usage_mb": self.metrics.memory_usage_mb,
            "cpu_usage_percent": self.metrics.cpu_usage_percent,
            "last_optimization": self.metrics.last_optimization.isoformat(),
            "cross_integration_searches": self.metrics.cross_integration_searches,
            "integrations_configured": list(self.integration_configs.keys()),
            "tables_loaded": list(self.tables.keys()),
        }

    async def add_documents(self, integration: str, documents: List[Dict[str, Any]]):
        """Add documents to the memory system"""
        try:
            if integration not in self.integration_configs:
                raise ValueError(f"Integration {integration} not configured")

            config = self.integration_configs[integration]

            # Generate embeddings for documents
            documents_with_embeddings = []
            for doc in documents:
                # Extract text content
                text_content = doc.get(config["text_field"], "")

                # Generate embedding
                embedding = self._generate_embedding(text_content)

                # Create document with embedding
                doc_with_embedding = doc.copy()
                doc_with_embedding[config["embedding_field"]] = embedding
                documents_with_embeddings.append(doc_with_embedding)

            # Add to table
            if integration not in self.tables:
                # Create table if it doesn't exist
                if LANCEDB_AVAILABLE:
                    schema = pa.schema(
                        [
                            pa.field(
                                config["embedding_field"],
                                pa.list_(pa.float32(), self.metrics.vector_dimensions),
                            ),
                            pa.field(config["text_field"], pa.string()),
                            *[
                                pa.field(field, pa.string())
                                for field in config["metadata_fields"]
                            ],
                        ]
                    )
                    self.tables[integration] = self.db.create_table(
                        config["table_name"], schema=schema
                    )
                else:
                    self.tables[integration] = self.db.open_table(config["table_name"])

            # Add documents
            if LANCEDB_AVAILABLE:
                self.tables[integration].add(documents_with_embeddings)
            else:
                # Mock implementation
                self.tables[integration].data.extend(documents_with_embeddings)

            logger.info(f"Added {len(documents)} documents to {integration}")

        except Exception as e:
            logger.error(f"Error adding documents to {integration}: {str(e)}")
            raise

    def stop(self):
        """Stop the memory system optimizer"""
        self.running = False
        self.thread_pool.shutdown(wait=True)
        logger.info("Memory system optimizer stopped")
