# Reference Documentation

Technical references, architecture diagrams, and system specifications.

## 📚 Quick Navigation

### Architecture
- **[Technical Overview](TECHNICAL_OVERVIEW.md)** - System technical overview
- **[ATOM Architecture Spec](ATOM_ARCHITECTURE_SPEC.md)** - High-level system design
- **[Code Structure Overview](CODE_STRUCTURE_OVERVIEW.md)** - Codebase organization

### Database
- **[Database Architecture](DATABASE_ARCHITECTURE.md)** - Database design and schema
- **[Database Model Audit](DATABASE_MODEL_AUDIT.md)** - Model audit report
- **[Database Model Best Practices](DATABASE_MODEL_BEST_PRACTICES.md)** - Database guidelines

### Features
- **[Feature Matrix](FEATURE_MATRIX.md)** - Capability comparison matrix

### Architecture Diagrams
- **[Architecture Diagrams](ARCHITECTURE_DIAGRAMS.md)** - System architecture diagrams

### Legal
- **[LICENSE](LICENSE.md)** - AGPL v3 license
- **[Release Notes Template](RELEASE_NOTES_TEMPLATE.md)** - Release notes format

## 🏗️ System Architecture

### Core Components
```
┌─────────────────────────────────────────┐
│           Frontend (Next.js)             │
├─────────────────────────────────────────┤
│           API Layer (FastAPI)            │
├─────────────────────────────────────────┤
│  Agent Governance | LLM | Tools | Canvas │
├─────────────────────────────────────────┤
│     PostgreSQL | Redis | LanceDB         │
└─────────────────────────────────────────┘
```

### Key Technologies
- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0
- **Frontend**: Next.js, React, TypeScript
- **Database**: PostgreSQL/SQLite, Redis
- **Vector DB**: LanceDB
- **LLM**: OpenAI, Anthropic, Gemini, DeepSeek, MiniMax

## 📊 Database Schema

### Core Models
- **AgentRegistry**: Agent definitions and metadata
- **AgentExecution**: Execution history and tracking
- **Episode**: Episodic memory containers
- **Canvas**: Presentation state and history
- **User/Workspace**: User and tenant management

### Key Relationships
- Agent → AgentExecution (1:N)
- Agent → Episode (1:N)
- Episode → EpisodeSegment (1:N)
- Workspace → Agent (1:N)

## 🔧 Quick Reference

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://...

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...

# Application
PORT=8000
LOG_LEVEL=INFO

# Governance
STREAMING_GOVERNANCE_ENABLED=true
CANVAS_GOVERNANCE_ENABLED=true
```

### API Endpoints
- **Health**: `/health/live`, `/health/ready`
- **Agents**: `/api/v1/agents/*`
- **Episodes**: `/api/v1/episodes/*`
- **Canvas**: `/api/v1/canvas/*`

## 📖 Related Documentation

- **[Development](../DEVELOPMENT/README.md)** - Development setup
- **[API Documentation](../API/README.md)** - API reference
- **[Operations](../operations/README.md)** - Operations guides

---

*Last Updated: April 12, 2026*
