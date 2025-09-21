# 🗄️ Atom Database Architecture

## 📋 Overview

This document defines the database architecture for the Atom personal assistant application, establishing clear single sources of truth for PostgreSQL and LanceDB.

## 🎯 Single Source of Truth Principles

### **PostgreSQL: Relational Data Master**
PostgreSQL serves as the single source of truth for all **relational, transactional, and application state data**:
- User profiles and authentication
- OAuth tokens and credentials  
- Tasks, messages, calendar events
- Application configuration and metadata
- Financial transactions and accounts
- Integration settings and state

### **LanceDB: Vector Data Master**  
LanceDB serves as the single source of truth for all **vector embeddings and semantic search data**:
- Document embeddings and vector representations
- Document chunks and processed content
- Semantic search indexes
- Vector similarity data
- AI model outputs and embeddings

## 🏗️ Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     LanceDB     │
│                 │    │                 │
│  • User Data    │    │  • Embeddings   │
│  • OAuth Tokens │    │  • Document     │
│  • Tasks        │    │    Chunks       │
│  • Messages     │    │  • Vector       │
│  • Calendar     │    │    Search       │
│  • App State    │    │  • Semantic     │
│                 │    │    Indexes      │
└─────────────────┘    └─────────────────┘
         │                       │
         └───────────────────────┘
                 │
         ┌─────────────────┐
         │   Atom Backend  │
         │   (Flask API)   │
         └─────────────────┘
```

## 📊 Data Ownership Matrix

| Data Type | Source of Truth | Description |
|-----------|-----------------|-------------|
| User Profiles | PostgreSQL | User account information and preferences |
| OAuth Tokens | PostgreSQL | Encrypted service authentication tokens |
| Tasks | PostgreSQL | User tasks with metadata and status |
| Messages | PostgreSQL | Email, chat, and notification messages |
| Calendar Events | PostgreSQL | Scheduled events and meetings |
| Document Embeddings | LanceDB | Vector representations of document content |
| Document Chunks | LanceDB | Processed text chunks for semantic search |
| Search Indexes | LanceDB | Vector indexes for similarity search |
| AI Model Outputs | LanceDB | Embeddings and model-generated content |

## 🔄 Integration Patterns

### 1. **Data Creation Flow**
```python
# Example: Processing a new document
def process_document(document_id, user_id, content):
    # 1. Store metadata in PostgreSQL (single source of truth)
    store_document_metadata(postgres_conn, document_id, user_id, metadata)
    
    # 2. Process content and store embeddings in LanceDB (single source of truth)
    embeddings = generate_embeddings(content)
    store_in_lancedb(lancedb_conn, document_id, embeddings, content)
    
    # 3. Return success with both database references
    return {"postgres_id": document_id, "lancedb_status": "stored"}
```

### 2. **Data Retrieval Flow**
```python
# Example: Searching for documents
def search_documents(query, user_id):
    # 1. Get user context from PostgreSQL (single source of truth)
    user_context = get_user_context(postgres_conn, user_id)
    
    # 2. Perform vector search in LanceDB (single source of truth)
    results = lancedb_search(lancedb_conn, query, user_id)
    
    # 3. Enrich results with PostgreSQL metadata
    enriched_results = enrich_with_metadata(postgres_conn, results)
    
    return enriched_results
```

### 3. **Data Consistency**
- **PostgreSQL**: ACID compliance ensures transactional integrity
- **LanceDB**: Eventual consistency for vector operations is acceptable
- **Cross-database references**: Use UUIDs as foreign keys between systems

## 🛠️ Configuration

### Environment Variables
```env
# PostgreSQL Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/atom_db
DB_MAX_CONNECTIONS=20
DB_POOL_TIMEOUT=30

# LanceDB Configuration  
LANCEDB_URI=data/lancedb
LANCEDB_TABLE_NAME=processed_documents
LANCEDB_CHUNKS_TABLE_NAME=document_chunks

# Encryption
ATOM_OAUTH_ENCRYPTION_KEY=your-32-character-encryption-key-here
```

### Health Checks
Both databases include health monitoring:
```bash
# Health endpoint returns both database statuses
GET /healthz → {
  "database": {
    "postgresql": "healthy", 
    "lancedb": "healthy"
  }
}
```

## 🔧 Maintenance Procedures

### PostgreSQL Maintenance
```bash
# Backup
pg_dump atom_db > backup.sql

# Restore
psql atom_db < backup.sql

# Monitor
SELECT * FROM pg_stat_activity;
```

### LanceDB Maintenance  
```bash
# Compact database
lancedb compact data/lancedb

# Check integrity
lancedb check data/lancedb
```

## 🚨 Error Handling

### Database Unavailable
```python
def handle_database_error(service, error):
    if service == "postgresql":
        # Critical - degrade functionality
        log_critical("PostgreSQL unavailable - core features disabled")
        return fallback_to_mock_data()
        
    elif service == "lancedb":
        # Non-critical - continue without vector search
        log_warning("LanceDB unavailable - semantic search disabled")
        return continue_with_basic_search()
```

### Data Consistency Issues
```python
def verify_data_consistency():
    # Cross-database integrity checks
    postgres_docs = get_all_documents(postgres_conn)
    lancedb_docs = get_all_documents(lancedb_conn)
    
    # Ensure referential integrity
    missing_in_lancedb = find_missing_references(postgres_docs, lancedb_docs)
    if missing_in_lancedb:
        trigger_reprocessing(missing_in_lancedb)
```

## 📈 Performance Considerations

### PostgreSQL Optimization
- Connection pooling with `psycopg2.pool`
- Indexes on frequently queried columns
- Regular vacuum and analyze operations

### LanceDB Optimization  
- Batch insert operations
- Vector index optimization
- Chunk size tuning for search performance

## 🔐 Security

### Data Encryption
- **PostgreSQL**: Column-level encryption for sensitive data
- **LanceDB**: Filesystem encryption for vector stores
- **Transit**: TLS for all database connections

### Access Control
- Role-based access to database operations
- Service-specific database credentials
- Audit logging for all data operations

## 📝 Versioning & Migration

### Schema Changes
```bash
# PostgreSQL migrations
python -m alembic upgrade head

# LanceDB schema evolution  
lancedb migrate data/lancedb new_schema.json
```

### Backup Strategy
- Daily automated backups for PostgreSQL
- Weekly snapshots for LanceDB
- Cross-database backup verification

---

*This architecture ensures clear separation of concerns with PostgreSQL as the transactional authority and LanceDB as the vector data authority, maintaining single source of truth principles for each domain.*