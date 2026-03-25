# GraphRAG and Entity Types System

**Last Updated**: March 24, 2026
**Status**: ✅ Production Ready
**Version**: GraphRAG V2 (PostgreSQL-backed)

> **🚀 Quick Start**: For a brief overview of GraphRAG features and usage, see [GRAPHRAG_PORTED.md](./GRAPHRAG_PORTED.md)

---

## Overview

The Atom Knowledge Graph provides a semantic layer over your existing database records, enabling high-order reasoning, visual relationship management, and intelligent entity extraction. Unlike flat vector search, GraphRAG can traverse relationships to find indirect connections (e.g., "Find all formulas used in tasks assigned to the support team").

## Key Features

### 1. PostgreSQL-Backed GraphRAG V2
- **Stateless Recursive CTEs**: High-performance graph traversal using PostgreSQL without the need for a dedicated graph database
- **Bidirectional Traversal**: Efficient graph queries that traverse both incoming and outgoing relationships
- **Local Search**: Explores the immediate neighborhood of an entity (configurable depth)
- **Global Search**: Summarizes high-level themes across the entire graph using pre-computed communities
- **Community Detection**: Background worker using NetworkX + Leiden Algorithm for clustering

### 2. Canonical Entity Types
The system includes **6 built-in canonical entity types** that map directly to database models:

| Type | Database Model | Search Field | Updatable Fields | Description |
|------|---------------|-------------|------------------|-------------|
| `user` | `User` | `email` | `first_name`, `last_name`, `specialty` | User accounts with specialties |
| `workspace` | `Workspace` | `name` | `description` | Workspace/organization |
| `team` | `Team` | `name` | `description` | Teams within workspace |
| `task` | `UserTask` | `title` | `description`, `status` | Tasks and assignments |
| `ticket` | `SupportTicket` | `subject` | `status`, `priority` | Support tickets |
| `formula` | `Formula` | `name` | `expression`, `description` | Business logic formulas |

### 3. Dynamic Custom Entity Types ✨
Users can define their own entity types with:
- **JSON Schema Validation**: Ensure data integrity with custom schemas
- **Dynamic Model Factory**: Runtime model creation for custom types
- **Tenant Isolation**: Custom types are scoped per workspace/tenant
- **Skill Integration**: Associate custom entities with specific skills
- **Schema Evolution**: Versioning support for entity type definitions

### 4. Entity Registry System
The Entity Registry is a centralized configuration that defines:
- **Database Mapping**: Which SQL model to use for canonical entities
- **Search Fields**: Which fields to search when resolving entities
- **Updatable Fields**: Which properties can be synced back to the database
- **Custom Types**: Runtime-loaded entity type definitions

**Canonical Registry** (defined in `graphrag_engine.py`):
```python
canonical_registry = {
    "user": {
        "model": User,
        "search_field": "email",
        "updatable_fields": ["first_name", "last_name", "specialty"]
    },
    "workspace": {
        "model": Workspace,
        "search_field": "name",
        "updatable_fields": ["description"]
    },
    # ... (see table above)
}
```

### 5. Bidirectional Sync ✨
Updating a property on an anchored node automatically syncs changes back to the underlying database record:
- **Graph → Database**: Changes in the graph UI update database records
- **Database → Graph**: Database changes are reflected in the graph
- **Field Whitelisting**: Only explicitly allowed fields can be synced (security)
- **Real-time Updates**: Changes propagate immediately via automation triggers

### 6. LLM-Based Entity Extraction ✨
The system uses LLMService to extract entities and relationships from unstructured text:

**Standard Entity Types**:
- Person, Organization, Location, Date/Time, Email, URL
- Document, Project, Task, Ticket, Formula

**Custom Entity Types**:
- User-defined types are loaded dynamically and included in extraction prompts
- LLM is prompted with custom type descriptions to improve recognition
- Supports any domain-specific entity type (e.g., "Invoice", "Contract", "Product")

---

## Architecture

### Core Components

#### 1. GraphRAGEngine (`backend/core/graphrag_engine.py`)
**Purpose**: PostgreSQL-backed graph traversal and entity extraction

**Key Methods**:
- `local_search(workspace_id, query, depth=2)` - Recursive CTE-based BFS traversal
- `global_search(workspace_id, query)` - Community-based summarization
- `ingest_document(workspace_id, doc_id, text, source)` - Extract entities from text
- `add_entity(entity, workspace_id)` - Insert/update graph node
- `add_relationship(rel, workspace_id)` - Insert graph edge
- `canonical_search(workspace_id, entity_type, query)` - Search canonical records
- `get_context_for_ai(workspace_id, query)` - Format context for AI prompts

**Performance**:
- Recursive CTE queries execute in <100ms for depth-2 traversal
- Bidirectional edge traversal minimizes database round-trips
- Stateless design allows horizontal scaling

#### 2. EntityTypeService (`backend/core/entity_type_service.py`)
**Purpose**: CRUD operations for dynamic entity type definitions

**Key Methods**:
- `create_entity_type(tenant_id, slug, display_name, json_schema, ...)` - Create new type
- `get_entity_type(tenant_id, entity_type_id, slug)` - Retrieve type definition
- `update_entity_type(entity_type_id, json_schema, ...)` - Update schema
- `list_entity_types(tenant_id, is_active)` - List all types
- `delete_entity_type(entity_type_id)` - Soft delete

**Schema Validation**:
- Uses `SchemaValidator` to ensure valid JSON Schema
- Prevents invalid schemas from being created
- Provides clear error messages for validation failures

#### 3. ModelFactory (`backend/core/model_factory.py`)
**Purpose**: Dynamic SQLAlchemy model creation for custom entity types

**Key Methods**:
- `create_model(entity_type_def)` - Generate SQLAlchemy model from schema
- `get_model(tenant_id, slug)` - Retrieve cached model
- `invalidate_cache(tenant_id, slug)` - Force model reload

**Capabilities**:
- Runtime model generation from JSON Schema
- Automatic table creation with proper constraints
- Index generation for search fields
- Model caching for performance

#### 4. KnowledgeExtractor (`backend/core/knowledge_extractor.py`)
**Purpose**: LLM-based entity and relationship extraction from text

**Key Methods**:
- `extract_entities(text, custom_types)` - Extract entities using LLM
- `extract_relationships(text, entities)` - Extract relationships
- `pattern_extraction_fallback(text)` - Regex-based fallback

**Features**:
- Supports both LLM-based and pattern-based extraction
- Automatically detects custom entity types
- Handles unstructured text (documents, emails, messages)

---

## Database Schema

### Graph Tables

#### `graph_nodes`
```sql
CREATE TABLE graph_nodes (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    description TEXT,
    properties JSONB,
    created_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_workspace_type (workspace_id, type),
    INDEX idx_name_trgm (name USING gin)
);
```

#### `graph_edges`
```sql
CREATE TABLE graph_edges (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    source_node_id UUID NOT NULL,
    target_node_id UUID NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    properties JSONB,
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (source_node_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_node_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
    INDEX idx_source_target (source_node_id, target_node_id),
    INDEX idx_rel_type (relationship_type)
);
```

#### `graph_communities`
```sql
CREATE TABLE graph_communities (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    level INTEGER NOT NULL,
    summary TEXT,
    keywords VARCHAR(255)[],
    created_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_workspace_level (workspace_id, level)
);
```

#### `community_membership`
```sql
CREATE TABLE community_membership (
    id UUID PRIMARY KEY,
    community_id UUID NOT NULL,
    node_id UUID NOT NULL,

    FOREIGN KEY (community_id) REFERENCES graph_communities(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
    UNIQUE (community_id, node_id)
);
```

### Entity Type Definition Table

#### `entity_type_definitions`
```sql
CREATE TABLE entity_type_definitions (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    json_schema JSONB NOT NULL,
    available_skills VARCHAR(255)[],
    is_system BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_tenant_slug (tenant_id, slug)
);
```

---

## Usage Examples

### 1. Local Search (Neighborhood Traversal)

```python
from core.graphrag_engine import graphrag_engine

# Find entities related to "John Doe" up to 2 hops away
result = graphrag_engine.local_search(
    workspace_id="default",
    query="John Doe",
    depth=2
)

# Returns:
# {
#     "mode": "local",
#     "start_entities": ["John Doe"],
#     "entities": [
#         {"id": "...", "name": "John Doe", "type": "user", "description": "..."},
#         {"id": "...", "name": "Project Alpha", "type": "project", "description": "..."},
#         {"id": "...", "name": "Task #123", "type": "task", "description": "..."}
#     ],
#     "relationships": [
#         {"from": "...", "to": "...", "type": "assigned_to"},
#         {"from": "...", "to": "...", "type": "related_to"}
#     ],
#     "count": 15
# }
```

### 2. Global Search (Community-Based)

```python
# Get high-level themes across the entire graph
result = graphrag_engine.global_search(
    workspace_id="default",
    query="overview of projects"
)

# Returns:
# {
#     "mode": "global",
#     "summaries": [
#         "Community 1: 5 projects focused on Q1 deliverables...",
#         "Community 2: 3 support tickets related to billing..."
#     ],
#     "answer": "Community 1: ... | Community 2: ..."
# }
```

### 3. Creating Custom Entity Types

```python
from core.entity_type_service import EntityTypeService

service = EntityTypeService()

# Define a custom "Invoice" entity type
invoice_type = service.create_entity_type(
    tenant_id="acme-corp",
    slug="invoice",
    display_name="Invoice",
    description="Customer invoices for billing",
    json_schema={
        "type": "object",
        "properties": {
            "invoice_number": {"type": "string"},
            "amount": {"type": "number"},
            "due_date": {"type": "string", "format": "date"},
            "customer_name": {"type": "string"},
            "status": {"type": "string", "enum": ["pending", "paid", "overdue"]}
        },
        "required": ["invoice_number", "amount", "customer_name"]
    },
    available_skills=["invoice_processing", "payment_reminder"]
)

# The LLM will now recognize "Invoice" entities in documents
```

### 4. Ingesting Documents with Entity Extraction

```python
import asyncio

# Extract entities and relationships from a document
text = """
John Doe assigned Task #456 to Jane Smith.
The task is related to Project Alpha and requires Formula:CalculateRevenue.
"""

result = await graphrag_engine.ingest_document(
    workspace_id="default",
    doc_id="doc-123",
    text=text,
    source="email"
)

# Returns: {"entities": 4, "relationships": 3}
# Entities: John Doe (Person), Jane Smith (Person), Task #456 (Task),
#           Project Alpha (Project), Formula:CalculateRevenue (Formula)
# Relationships: John Doe -> assigned_to -> Task #456, etc.
```

### 5. Canonical Entity Anchoring

```python
# Anchor a graph node to a User record
graphrag_engine.add_entity(
    Entity(
        id="node-123",
        name="john@example.com",
        entity_type="user",
        description="Software Engineer",
        properties={
            "canonical_type": "user",  # Anchors to User model
            "specialty": "Backend Development"  # Syncs to User.specialty
        }
    ),
    workspace_id="default"
)

# The graph node is now linked to the User record
# Changes to properties["specialty"] will sync to User.specialty
```

---

## API Endpoints

### Entity Type Management

#### Create Entity Type
```http
POST /api/v1/entity-types
Content-Type: application/json

{
  "slug": "contract",
  "display_name": "Contract",
  "description": "Legal contracts",
  "json_schema": {
    "type": "object",
    "properties": {
      "contract_number": {"type": "string"},
      "party_a": {"type": "string"},
      "party_b": {"type": "string"}
    }
  },
  "available_skills": ["contract_analysis"]
}
```

#### List Entity Types
```http
GET /api/v1/entity-types?is_active=true
```

#### Get Entity Type
```http
GET /api/v1/entity-types/{entity_type_id}
```

#### Update Entity Type
```http
PUT /api/v1/entity-types/{entity_type_id}
Content-Type: application/json

{
  "json_schema": {...},
  "description": "Updated description"
}
```

#### Delete Entity Type
```http
DELETE /api/v1/entity-types/{entity_type_id}
```

### Graph Operations

#### Local Search
```http
POST /api/v1/graph/search/local
Content-Type: application/json

{
  "query": "John Doe",
  "depth": 2
}
```

#### Global Search
```http
POST /api/v1/graph/search/global
Content-Type: application/json

{
  "query": "project overview"
}
```

#### Ingest Document
```http
POST /api/v1/graph/ingest
Content-Type: application/json

{
  "doc_id": "doc-123",
  "text": "Document text here...",
  "source": "email"
}
```

#### Add Entity
```http
POST /api/v1/graph/entities
Content-Type: application/json

{
  "name": "John Doe",
  "type": "user",
  "description": "Software Engineer",
  "properties": {
    "canonical_type": "user",
    "email": "john@example.com"
  }
}
```

#### Get Context for AI
```http
POST /api/v1/graph/context
Content-Type: application/json

{
  "query": "What tasks are assigned to John?"
}
```

---

## Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Local search (depth-2) | <100ms | ~50-80ms |
| Global search | <200ms | ~100-150ms |
| Entity extraction (LLM) | <5s | ~2-3s |
| Entity extraction (pattern) | <500ms | ~200-300ms |
| Document ingestion | <10s | ~3-5s |
| Graph visualization load | <2s | ~1-1.5s |

---

## Security & Governance

### Field Whitelisting
Only explicitly allowed fields can be synced from graph to database:
```python
"updatable_fields": ["first_name", "last_name", "specialty"]  # User model
```
- **Prevents** unauthorized modifications to sensitive fields
- **Ensures** data integrity by restricting write access
- **Auditable** via property change tracking

### Tenant Isolation
- All graph queries scoped to `workspace_id`
- Custom entity types isolated per tenant
- No cross-tenant data leakage

### Schema Validation
- JSON Schema validation prevents invalid entity types
- Type checking ensures data consistency
- Clear error messages for debugging

---

## Frontend Integration

### Graph Visualization (`/graph`)
- **D3.js Force-Directed Layout**: Interactive graph exploration
- **Node Anchoring UI**: Search and link to database records
- **Real-time Updates**: WebSocket-based live updates
- **Filtering & Search**: Filter by type, search by name
- **Context Menu**: Inspect entities, view relationships

### Entity Type Management UI
- **Type Editor**: Create/edit custom entity types
- **Schema Builder**: Visual JSON Schema editor
- **Preview**: Test extraction with sample text
- **Import/Export**: Share entity types across workspaces

---

## Background Jobs

### Graph Reindex Worker (`backend/workers/reindex_graph_worker.py`)
- **Trigger**: Manual enqueue or scheduled
- **Purpose**: Recalculate communities and update embeddings
- **Algorithm**: NetworkX Leiden for community detection
- **Queue**: Redis-based job queue (UPSTASH_REDIS_URL)

### Automation Integration
```python
# Triggered on entity upsert
orchestrator.trigger_event("graph_entity_upsert", {
    "entity_type": "user",
    "entity_id": "...",
    "name": "John Doe",
    "is_new": True,
    "tenant_id": "default"
})
```

---

## Configuration

### Environment Variables

```bash
# GraphRAG LLM Configuration
GRAPHRAG_LLM_ENABLED=true
GRAPHRAG_LLM_PROVIDER=openai
GRAPHRAG_LLM_MODEL=gpt-4o-mini

# Redis for Job Queue
UPSTASH_REDIS_URL=redis://...
REDIS_URL=redis://...

# Workspace (Multi-tenant)
DEFAULT_WORKSPACE_ID=default
```

---

## Migration from V1 to V2

### Key Changes
1. **In-Memory → PostgreSQL**: No more in-memory graph storage
2. **NetworkX → Recursive CTEs**: Stateless SQL-based traversal
3. **Static → Dynamic Types**: Custom entity types now supported
4. **Manual → Auto-Sync**: Bidirectional sync with database

### Migration Steps
1. Run migration script to create graph tables
2. Export existing graph data (if any)
3. Import into PostgreSQL graph tables
4. Update API calls to use new endpoints
5. Verify custom entity type definitions

---

## Troubleshooting

### Issue: Entity extraction not recognizing custom types
**Solution**:
- Verify entity type is `is_active=True`
- Check `json_schema` is valid
- Ensure LLM is configured (`GRAPHRAG_LLM_ENABLED=true`)

### Issue: Canonical entity sync not working
**Solution**:
- Check `updatable_fields` includes the field
- Verify `canonical_type` matches registry key
- Ensure database model has the field

### Issue: Local search returns no results
**Solution**:
- Verify workspace_id matches
- Check query string is not empty
- Ensure graph has entities (check `graph_nodes` table)

### Issue: Global search returns generic summaries
**Solution**:
- Run community detection worker
- Verify `graph_communities` table has data
- Check workspace_id has communities

---

## Future Enhancements

- **Graph Visual Query Builder**: Drag-and-drop query construction
- **Relationship Types Schema**: Validate relationship types
- **Entity Versioning**: Track entity changes over time
- **Graph Analytics**: Centrality, pathfinding, clustering coefficients
- **Multi-Modal Entities**: Combine text, image, and audio entities
- **Real-time Collaboration**: Multi-user graph editing

---

## References

- **GraphRAG Engine**: `backend/core/graphrag_engine.py`
- **Entity Type Service**: `backend/core/entity_type_service.py`
- **Model Factory**: `backend/core/model_factory.py`
- **API Routes**: `backend/api/entity_type_routes.py`, `backend/api/graphrag_routes.py`
- **Frontend**: `frontend-nextjs/src/app/graph/page.tsx`
- **Visualization**: `frontend-nextjs/src/components/Graph/GraphVisualization.tsx`

---

*Last Updated: March 24, 2026*
