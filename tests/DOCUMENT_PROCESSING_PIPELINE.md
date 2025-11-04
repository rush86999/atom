# ATOM Document Processing Pipeline Integration Guide

## Overview

The ATOM document processing pipeline provides a unified system for ingesting, processing, and storing documents in the LanceDB-based memory system. This guide covers the complete integration of document processing with the ingestion pipeline for efficient recall and semantic search.

## Architecture

### Core Components

1. **Enhanced Document Service** (`document_service_enhanced.py`)
   - Unified document processing across multiple formats
   - LanceDB integration for vector storage
   - Semantic search capabilities
   - Chunking and embedding generation

2. **Document Processor** (`document_processor.py`)
   - Text extraction from various file formats
   - Metadata extraction
   - Format-specific processing logic

3. **LanceDB Handler** (`lancedb_handler.py`)
   - Vector database operations
   - Schema management
   - Search and retrieval functions

4. **Document Handler** (`document_handler.py`)
   - API endpoint for document ingestion
   - File upload processing
   - Integration with enhanced service

## Document Processing Flow

### 1. Document Upload

```python
# Example: Upload document via API
POST /api/ingest-document
Content-Type: multipart/form-data

{
  "file": [binary file data],
  "user_id": "user_123",
  "source_uri": "upload://document.pdf",
  "title": "Project Proposal"
}
```

### 2. Processing Pipeline

```
Upload → Type Detection → Text Extraction → Chunking → Embedding → LanceDB Storage
```

#### Step-by-Step Processing

1. **Type Detection**
   - Detect document type from file extension
   - Supported formats: PDF, DOCX, TXT, HTML, MD, PPTX, XLSX
   - Fallback to binary processing for unsupported types

2. **Text Extraction**
   - PDF: Uses pdfminer for text extraction
   - DOCX: Uses python-docx with structure preservation
   - TXT: Direct text reading with encoding detection
   - HTML: BeautifulSoup for clean text extraction

3. **Document Chunking**
   - Fixed-size chunks (1000 characters)
   - Sentence boundary awareness
   - Configurable overlap (200 characters)
   - Chunk metadata tracking

4. **Embedding Generation**
   - OpenAI embeddings (1536 dimensions)
   - Fallback to local models if needed
   - Batch processing for efficiency

5. **LanceDB Storage**
   - Two-table schema: documents and chunks
   - Vector indexing for fast search
   - Metadata preservation

## Integration with Ingestion Pipeline

### Connection to Main Ingestion System

The document processing pipeline integrates with the main ingestion pipeline through:

```python
# In ingestion_pipeline/main.py
async def process_document_source(user_id: str, source_config: Dict[str, Any]):
    """Process documents from various sources"""
    lancedb_conn = await get_lancedb_connection()
    doc_service = EnhancedDocumentService(
        db_pool=db_pool,
        lancedb_connection=lancedb_conn
    )
    
    # Process documents based on source type
    if source_config['type'] == 'local_directory':
        await _process_local_documents(doc_service, user_id, source_config)
    elif source_config['type'] == 'cloud_storage':
        await _process_cloud_documents(doc_service, user_id, source_config)
```

### Source Integration Points

1. **Local File System**
   - Monitor directories for new documents
   - Batch processing capabilities
   - File change detection

2. **Cloud Storage**
   - Google Drive integration
   - Dropbox synchronization
   - OneDrive support

3. **Email Attachments**
   - Gmail/Outlook integration
   - Automatic attachment processing
   - Thread context preservation

## Memory System Integration

### LanceDB Schema

#### Documents Table
```python
{
    "doc_id": "string",           # Unique document identifier
    "user_id": "string",          # User ownership
    "source_uri": "string",       # Document source
    "doc_type": "string",         # PDF, DOCX, TXT, etc.
    "title": "string",            # Document title
    "metadata_json": "string",    # JSON metadata
    "ingested_at": "string",      # ISO timestamp
    "processing_status": "string",# UPLOADED, PROCESSING, PROCESSED, FAILED
    "total_chunks": "int32",      # Number of chunks
    "vector_embedding": "float32[]" # Document-level embedding
}
```

#### Chunks Table
```python
{
    "chunk_id": "string",         # Unique chunk identifier
    "doc_id": "string",           # Parent document ID
    "user_id": "string",          # User ownership
    "chunk_index": "int32",       # Position in document
    "chunk_text": "string",       # Text content
    "start_pos": "int32",         # Start position in original text
    "end_pos": "int32",           # End position in original text
    "doc_type": "string",         # Inherited from parent
    "vector_embedding": "float32[]", # Chunk embedding
    "created_at": "string"        # ISO timestamp
}
```

## Search and Retrieval

### Semantic Search

```python
# Example: Search documents by semantic similarity
async def search_documents(user_id: str, query: str, limit: int = 10):
    doc_service = EnhancedDocumentService(lancedb_connection=lancedb_conn)
    results = await doc_service.search_documents(
        user_id=user_id,
        query=query,
        limit=limit,
        similarity_threshold=0.7
    )
    return results
```

### Hybrid Search

Combine semantic search with traditional text search:

```python
async def hybrid_search(user_id: str, query: str, filters: Dict[str, Any]):
    # Semantic search
    semantic_results = await doc_service.search_documents(user_id, query)
    
    # Text search fallback
    text_results = await doc_service._fallback_text_search(user_id, query)
    
    # Combine and rank results
    combined_results = _combine_search_results(semantic_results, text_results)
    return combined_results
```

## Configuration

### Environment Variables

```bash
# LanceDB Configuration
LANCEDB_URI=data/lancedb
LANCEDB_TABLE_NAME=processed_documents
LANCEDB_CHUNKS_TABLE_NAME=document_chunks

# Processing Configuration
DOCUMENT_CHUNK_SIZE=1000
DOCUMENT_CHUNK_OVERLAP=200
MAX_DOCUMENT_SIZE=10485760  # 10MB

# Embedding Configuration
OPENAI_API_KEY=your_api_key
EMBEDDING_MODEL=text-embedding-ada-002
```

### Service Configuration

```python
# Enhanced Document Service Configuration
doc_service = EnhancedDocumentService(
    db_pool=db_pool,
    lancedb_connection=lancedb_conn,
    chunk_size=1000,
    chunk_overlap=200
)
```

## Error Handling and Monitoring

### Processing Status Tracking

```python
class DocumentStatus(Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing" 
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"
```

### Error Recovery

1. **Transient Failures**
   - Automatic retry with exponential backoff
   - Checkpoint recovery for large documents
   - Partial processing support

2. **Permanent Failures**
   - Error logging with context
   - User notification
   - Failed document archiving

### Monitoring Metrics

- Documents processed per hour
- Average processing time
- Chunk generation statistics
- Embedding generation success rate
- Search performance metrics

## Performance Optimization

### Batch Processing

```python
async def batch_process_documents(documents: List[Dict[str, Any]]):
    """Process multiple documents efficiently"""
    # Parallel processing for independent documents
    tasks = [
        doc_service.process_and_store_document(**doc)
        for doc in documents
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### Caching Strategy

- Embedding cache for similar chunks
- Document metadata cache
- Search result caching with TTL

### Memory Management

- Stream processing for large documents
- Chunk-level memory limits
- Garbage collection for temporary files

## Security Considerations

### Data Protection

- Secure file upload validation
- User isolation in LanceDB
- Encryption at rest for sensitive documents
- Access control for document retrieval

### Privacy Compliance

- PII detection and redaction
- GDPR compliance for EU users
- Data retention policies
- Secure deletion procedures

## Testing and Validation

### Unit Tests

```python
class TestDocumentProcessing:
    async def test_pdf_processing(self):
        doc_service = EnhancedDocumentService()
        result = await doc_service.process_and_store_document(
            user_id="test_user",
            file_data=pdf_bytes,
            filename="test.pdf"
        )
        assert result["status"] == DocumentStatus.PROCESSED.value
        
    async def test_semantic_search(self):
        results = await doc_service.search_documents(
            user_id="test_user", 
            query="test query"
        )
        assert len(results) > 0
```

### Integration Tests

- End-to-end processing pipeline
- LanceDB storage validation
- Search functionality testing
- Error handling scenarios

## Deployment Considerations

### Scalability

- Horizontal scaling for document processing
- LanceDB cluster configuration
- Load balancing for API endpoints
- Database connection pooling

### Monitoring and Logging

- Structured logging with context
- Performance metrics collection
- Error tracking and alerting
- Health check endpoints

## Migration from Legacy System

### Data Migration

```python
async def migrate_legacy_documents():
    """Migrate documents from legacy storage to LanceDB"""
    legacy_docs = await get_legacy_documents()
    for doc in legacy_docs:
        await doc_service.process_and_store_document(
            user_id=doc['user_id'],
            file_data=doc['content'],
            filename=doc['filename'],
            source_uri=doc['source_uri']
        )
```

### API Compatibility

- Backward compatibility with existing endpoints
- Gradual feature rollout
- Feature flags for new functionality

## Conclusion

The ATOM document processing pipeline provides a robust, scalable solution for document ingestion and memory storage. By integrating with LanceDB, it enables efficient semantic search and recall while maintaining flexibility for various document types and sources.

The system is designed for extensibility, allowing easy integration of new document types, processing strategies, and storage backends while maintaining consistent performance and reliability.