# Platform Documentation

Architecture, deployment models, and technical platform overview.

## 📚 Quick Navigation

- **[Platform](PLATFORM.md)** - Complete platform overview
- **[Architecture](architecture.md)** - System architecture
- **[Single Tenant (Legacy)](single-tenant-legacy.md)** - Single-tenant deployment

## 🏗️ Platform Overview

### Deployment Models

#### Personal Edition
- **Target**: Individual users, home labs
- **Database**: SQLite
- **Deployment**: Docker Compose
- **Cost**: Free (self-hosted)
- **Setup**: 5-15 minutes

#### Enterprise Edition
- **Target**: Teams, organizations
- **Database**: PostgreSQL
- **Deployment**: Kubernetes/ECS
- **Features**: Multi-user, monitoring, scaling
- **Setup**: 30-60 minutes

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend Layer                    │
│              (Next.js + TypeScript)                 │
├─────────────────────────────────────────────────────┤
│                   API Layer                         │
│              (FastAPI + Python 3.11)                │
├─────────────────────────────────────────────────────┤
│              Business Logic Layer                   │
│  Agent Governance | LLM Service | Canvas | Tools    │
├─────────────────────────────────────────────────────┤
│              Data Layer                             │
│   PostgreSQL | Redis | LanceDB | File Storage       │
├─────────────────────────────────────────────────────┤
│              Integration Layer                      │
│   Slack | Gmail | HubSpot | Salesforce | 40+ more   │
└─────────────────────────────────────────────────────┘
```

## 🎯 Key Features

### Single-Tenant Architecture
- **Simpler Setup**: No tenant isolation overhead
- **Better Performance**: Direct database access
- **Self-Hosted**: Your data never leaves your infrastructure
- **Unlimited Usage**: No subscription fees or quotas

### Multi-Agent System
- **Specialty Agents**: Sales, Marketing, Engineering, Support
- **Governance**: 4-tier maturity (STUDENT → AUTONOMOUS)
- **Orchestration**: Queen Agent (structured) + Fleet Admiral (unstructured)

### Intelligence Systems
- **Episodic Memory**: PostgreSQL + LanceDB hybrid storage
- **GraphRAG**: Knowledge graph with entity extraction
- **Self-Evolution**: Agents learn from mistakes
- **World Model**: JIT fact provision with citations

### Canvas System
- **Visual Presentations**: Charts, forms, markdown
- **AI Accessibility**: Hidden accessibility trees
- **LLM Summaries**: Enhanced episode retrieval

## 📊 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Next.js, React, TypeScript | Web UI |
| **Backend** | FastAPI, Python 3.11 | REST API |
| **Database** | PostgreSQL/SQLite | Data storage |
| **Cache** | Redis | Caching, job queue |
| **Vector DB** | LanceDB | Semantic search |
| **LLM** | OpenAI, Anthropic, Gemini | AI inference |
| **Browser** | Playwright CDP | Browser automation |

## 🚀 Deployment Options

### Personal Edition (Docker Compose)
```bash
docker-compose -f docker-compose-personal.yml up -d
```

### Enterprise (Kubernetes)
```bash
kubectl apply -f deploy/kubernetes/
```

### Cloud (DigitalOcean)
- [1-Click Deploy](https://cloud.digitalocean.com/apps/new?repo=https://github.com/rush86999/atom/tree/main&config=deploy/digitalocean/app.yaml)

## 📖 Related Documentation

- **[Architecture Diagrams](../reference/ARCHITECTURE_DIAGRAMS.md)** - System diagrams
- **[Deployment](../DEPLOYMENT/README.md)** - Deployment guides
- **[Operations](../operations/README.md)** - Operations and monitoring

---

*Last Updated: April 12, 2026*
