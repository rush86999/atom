# Architecture Documentation

System architecture, design patterns, and technical specifications.

## 📚 Quick Navigation

### Core Architecture
- **[Backend Architecture](BACKEND_ARCHITECTURE.md)** - Backend system design
- **[Database Schema](DATABASE_SCHEMA.md)** - Database structure and relationships
- **[Database Standardization](DATABASE_STANDARDIZATION.md)** - Database standards

### BYOK LLM Integration
- **[BYOK Implementation Summary](BYOK_IMPLEMENTATION_SUMMARY.md)** - BYOK overview
- **[BYOK LLM Integration Complete](BYOK_LLM_INTEGRATION_COMPLETE.md)** - Complete LLM integration
- **[BYOK V6 Migration Guide](BYOK_V6_MIGRATION_GUIDE.md)** - Migration to v6.0

### Cognitive Systems
- **[Cognitive Tier System](COGNITIVE_TIER_SYSTEM.md)** - 5-tier LLM routing

### Application Design
- **[Decorator Application Complete](DECORATOR_APPLICATION_COMPLETE.md)** - Decorator patterns
- **[API Reference](API_REFERENCE.md)** - Architecture API reference

### Database Sessions
- **[Database Session Guide](DATABASE_SESSION_GUIDE.md)** - Session management

## 🏗️ System Architecture

### Layer Architecture
```
┌─────────────────────────────────────────┐
│         Presentation Layer               │
│      (Next.js + TypeScript)              │
├─────────────────────────────────────────┤
│         API Layer (FastAPI)              │
│   REST + WebSocket + Streaming           │
├─────────────────────────────────────────┤
│         Business Logic Layer             │
│  Agent Governance | LLM | Canvas | Tools │
├─────────────────────────────────────────┤
│         Data Access Layer                │
│    SQLAlchemy ORM + Repository Pattern   │
├─────────────────────────────────────────┤
│         Data Storage Layer               │
│  PostgreSQL | Redis | LanceDB | Files    │
└─────────────────────────────────────────┘
```

### Key Design Patterns

#### Repository Pattern
```python
class AgentRepository:
    def get(self, agent_id: str) -> Agent:
        return db.query(Agent).filter(Agent.id == agent_id).first()
```

#### Service Layer Pattern
```python
class AgentGovernanceService:
    def can_execute_action(self, agent_id: str, action: str) -> bool:
        # Business logic here
        pass
```

#### Dependency Injection
```python
@app.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    return agent_service.get_agent(agent_id, db)
```

## 🎯 Architecture Principles

### 1. Single Responsibility
- Each component has one clear purpose
- Services handle business logic
- Repositories handle data access
- Controllers handle HTTP concerns

### 2. Separation of Concerns
- Frontend and backend are separate
- Business logic independent of frameworks
- Data access abstracted behind repositories

### 3. Governance First
- Every AI action is attributable
- Maturity-based access control
- Complete audit trail

### 4. Performance Matters
- Sub-millisecond cached governance checks
- Hybrid storage (hot + cold)
- Efficient database queries with proper indexing

## 📊 Database Architecture

### Core Tables
- **users**: User accounts
- **workspaces**: Tenant/workspace isolation
- **agent_registry**: Agent definitions
- **agent_executions**: Execution history
- **episodes**: Episodic memory
- **canvases**: Canvas presentations

### Relationships
```
users (1) → (N) workspaces
workspaces (1) → (N) agent_registry
agent_registry (1) → (N) agent_executions
agent_registry (1) → (N) episodes
episodes (1) → (N) episode_segments
```

## 🔧 Technology Choices

### Why FastAPI?
- **Performance**: ASGI support, async/await
- **Type Safety**: Automatic validation with Pydantic
- **Documentation**: Auto-generated OpenAPI docs
- **Modern**: Python 3.11+ features

### Why PostgreSQL?
- **Reliability**: ACID compliance
- **Features**: JSONB, CTEs, full-text search
- **Performance**: Excellent query optimization
- **Extensibility**: Custom functions, extensions

### Why Next.js?
- **Performance**: Server-side rendering
- **Developer Experience**: React + TypeScript
- **Ecosystem**: Rich component library
- **SEO**: Built-in optimization

## 📖 Related Documentation

- **[Technical Overview](../reference/TECHNICAL_OVERVIEW.md)** - Technical overview
- **[Code Structure](../reference/CODE_STRUCTURE_OVERVIEW.md)** - Code organization
- **[Database Architecture](../reference/DATABASE_ARCHITECTURE.md)** - Database design

---

*Last Updated: April 12, 2026*
