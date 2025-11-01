#!/usr/bin/env python3
"""
LanceDB Initialization Script for ATOM Platform

This script initializes the LanceDB database with sample data to enable
search functionality in the ATOM platform.

Usage:
    python initialize_lancedb.py
"""

import os
import sys
import logging
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def initialize_lancedb():
    """Initialize LanceDB with sample data for search functionality"""

    try:
        # Import LanceDB
        import lancedb
        import pyarrow as pa
        import pandas as pd
        import numpy as np
    except ImportError as e:
        logger.error(f"LanceDB dependencies not available: {e}")
        logger.info(
            "Please install required packages: pip install lancedb pyarrow pandas numpy"
        )
        return False

    # Get database path from environment or use default
    db_path = os.environ.get("LANCEDB_URI", "/tmp/atom_lancedb")
    logger.info(f"Initializing LanceDB at: {db_path}")

    try:
        # Connect to LanceDB
        db = lancedb.connect(db_path)
        logger.info("Connected to LanceDB")

        # Define schema for document chunks
        chunk_schema = pa.schema(
            [
                pa.field("chunk_id", pa.string()),
                pa.field("doc_id", pa.string()),
                pa.field("user_id", pa.string()),
                pa.field("chunk_index", pa.int32()),
                pa.field("chunk_text", pa.string()),
                pa.field("metadata", pa.string()),
                pa.field(
                    "vector_embedding", pa.list_(pa.float32(), 1536)
                ),  # OpenAI embedding dimension
                pa.field("created_at", pa.string()),
            ]
        )

        # Create or open the document_chunks table
        table_name = "document_chunks"
        if table_name in db.table_names():
            logger.info(f"Table {table_name} already exists, opening...")
            table = db.open_table(table_name)
        else:
            logger.info(f"Creating new table: {table_name}")
            table = db.create_table(table_name, schema=chunk_schema)

        # Generate sample data
        sample_documents = [
            {
                "title": "Project Planning Meeting",
                "content": "Discussed project timelines, resource allocation, and milestones for Q4 2024. Team agreed on aggressive but achievable deadlines.",
                "tags": ["meeting", "planning", "project"],
            },
            {
                "title": "Technical Architecture Review",
                "content": "Reviewed the microservices architecture and API design patterns. Decided to use GraphQL for frontend communication.",
                "tags": ["technical", "architecture", "api"],
            },
            {
                "title": "Customer Feedback Analysis",
                "content": "Analyzed customer feedback from Q3. Key themes: improved UI/UX, faster response times, better documentation.",
                "tags": ["customer", "feedback", "analysis"],
            },
            {
                "title": "Security Audit Report",
                "content": "Completed security audit with penetration testing. Identified vulnerabilities in authentication system.",
                "tags": ["security", "audit", "vulnerabilities"],
            },
            {
                "title": "Team Standup Notes",
                "content": "Daily standup: backend team working on authentication, frontend team implementing search UI, QA team testing workflows.",
                "tags": ["standup", "team", "progress"],
            },
        ]

        # Generate embeddings for sample data
        logger.info("Generating embeddings for sample data...")

        try:
            from note_utils import get_text_embedding_openai

            embedding_function_available = True
        except ImportError:
            logger.warning("note_utils not available, using mock embeddings")
            embedding_function_available = False

        # Prepare data for insertion
        data_to_insert = []
        user_id = "default_user"

        for doc_idx, doc in enumerate(sample_documents):
            doc_id = str(uuid.uuid4())

            # Split content into chunks (simplified - just use the whole content)
            chunks = [
                {
                    "text": doc["content"],
                    "metadata": {
                        "title": doc["title"],
                        "tags": doc["tags"],
                        "source": "sample_data",
                    },
                }
            ]

            for chunk_idx, chunk in enumerate(chunks):
                # Generate embedding
                if embedding_function_available:
                    embedding_result = get_text_embedding_openai(chunk["text"])
                    if embedding_result["status"] == "success":
                        embedding = embedding_result["data"]
                    else:
                        logger.warning(
                            f"Failed to generate embedding: {embedding_result.get('message')}"
                        )
                        # Use mock embedding
                        embedding = [0.01] * 1536
                else:
                    # Use mock embedding
                    embedding = [0.01] * 1536

                # Create chunk record
                chunk_record = {
                    "chunk_id": str(uuid.uuid4()),
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "chunk_index": chunk_idx,
                    "chunk_text": chunk["text"],
                    "metadata": json.dumps(chunk["metadata"]),
                    "vector_embedding": embedding,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                data_to_insert.append(chunk_record)

        # Insert data into LanceDB
        if data_to_insert:
            logger.info(f"Inserting {len(data_to_insert)} document chunks...")
            table.add(data_to_insert)
            logger.info("Sample data inserted successfully!")
        else:
            logger.warning("No data to insert")

        # Verify the data was inserted
        count = table.count_rows()
        logger.info(f"Table now contains {count} rows")

        # Test search functionality
        logger.info("Testing search functionality...")

        # Generate embedding for test query
        test_query = "project planning"
        if embedding_function_available:
            embedding_result = get_text_embedding_openai(test_query)
            if embedding_result["status"] == "success":
                query_embedding = embedding_result["data"]

                # Perform search
                results = table.search(query_embedding).limit(3).to_list()
                logger.info(f"Search test returned {len(results)} results")

                # Display results
                for i, result in enumerate(results):
                    logger.info(
                        f"Result {i + 1}: {result.get('chunk_text', '')[:100]}..."
                    )
            else:
                logger.warning("Could not test search - embedding generation failed")
        else:
            logger.info("Search test skipped - mock embeddings in use")

        logger.info("LanceDB initialization completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize LanceDB: {e}")
        return False


def create_meeting_transcripts_table():
    """Create meeting_transcripts_embeddings table if needed"""

    try:
        import lancedb
        import pyarrow as pa

        db_path = os.environ.get("LANCEDB_URI", "/tmp/atom_lancedb")
        db = lancedb.connect(db_path)

        table_name = "meeting_transcripts_embeddings"
        if table_name not in db.table_names():
            logger.info(f"Creating table: {table_name}")

            # Define schema for meeting transcripts
            schema = pa.schema(
                [
                    pa.field("transcript_id", pa.string()),
                    pa.field("user_id", pa.string()),
                    pa.field("meeting_title", pa.string()),
                    pa.field("content", pa.string()),
                    pa.field("timestamp", pa.string()),
                    pa.field("vector_embedding", pa.list_(pa.float32(), 1536)),
                    pa.field("metadata", pa.string()),
                ]
            )

            db.create_table(table_name, schema=schema)
            logger.info(f"Table {table_name} created successfully")
        else:
            logger.info(f"Table {table_name} already exists")

        return True

    except Exception as e:
        logger.error(f"Failed to create meeting transcripts table: {e}")
        return False


def main():
    """Main execution function"""
    logger.info("Starting LanceDB initialization...")

    # Initialize main document chunks table
    if not initialize_lancedb():
        logger.error("LanceDB initialization failed")
        sys.exit(1)

    # Create meeting transcripts table (for compatibility)
    create_meeting_transcripts_table()

    logger.info("LanceDB setup completed!")
    logger.info(
        "You can now test search functionality at: http://localhost:5058/semantic_search_meetings"
    )


if __name__ == "__main__":
    main()
