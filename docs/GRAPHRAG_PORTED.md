# Knowledge Graph & GraphRAG (Ported)

The Atom Knowledge Graph provides a semantic layer over your existing database records, enabling high-order reasoning and visual relationship management.

## Key Features

### 1. Recursive GraphRAG
Unlike flat vector search, GraphRAG can traverse relationships to find indirect connections (e.g., "Find all formulas used in tasks assigned to the support team"). 
- **Local Search**: Explores the immediate neighborhood of an entity.
- **Global Search**: Summarizes high-level themes across the entire graph.

### 2. Canonical Anchoring
Every node in the graph can be "anchored" to a concrete database record:
- **Users**: Designate roles and specialties.
- **Support Tickets**: Link tickets to related technical concepts.
- **Formulas**: Map business logic to entities.
- **Tasks**: Associate tasks with the broader project context.

### 3. Bidirectional Sync
Updating a property on an anchored node (e.g., changing a user's `specialty`) will automatically sync the change back to the underlying database record. This allows the Graph UI to act as a powerful administrative tool.

## Technical Implementation

### Backend
- **Stateless Recursive CTEs**: High-performance graph traversal using PostgreSQL without the need for a dedicated graph database.
- **Entity Registry**: Centralized configuration in `core.graphrag_engine` for all anchorable models.
- **Sanitization & Logic**: Ensures only specific allowed fields are synced back to the SQL database.

### Frontend
- **D3.js Visualization**: Interactive force-directed layout for exploring complex relationships.
- **Anchoring UI**: Integrated search and selection for linking nodes to DB records.
- **Specialty Sync**: Real-time update of user expertise from the graph interface.

## Usage
Navigate to `/graph` in your local development environment to start exploring and building your knowledge base.
