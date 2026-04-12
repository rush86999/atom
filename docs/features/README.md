# Features Documentation

Feature comparisons, use cases, and capability overviews.

## 📚 Quick Navigation

### Feature Comparisons
- **[Atom vs OpenClaw](atom-vs-openclaw.md)** - Feature comparison with OpenClaw

## 🎯 Key Features

### Agent System
- **Multi-Agent Architecture**: Specialty agents with different maturity levels
- **4-Tier Governance**: STUDENT → INTERN → SUPERVISED → AUTONOMOUS
- **Dynamic Orchestration**: Queen Agent (structured) + Fleet Admiral (unstructured)
- **Self-Evolution**: Agents learn from mistakes and improve capabilities

### Intelligence & Memory
- **Episodic Memory**: PostgreSQL + LanceDB hybrid storage
- **GraphRAG**: Knowledge graph with entity extraction
- **Self-Evolution**: Reflection Pool, Memento-Skills, AlphaEvolver
- **World Model**: JIT fact provision with citations

### Canvas System
- **Visual Presentations**: Charts, forms, markdown, sheets
- **AI Accessibility**: Hidden accessibility trees for agents
- **LLM Summaries**: Enhanced episode retrieval
- **Real-Time Updates**: WebSocket-based live updates

### Integrations
- **46+ Business Integrations**: Slack, Gmail, HubSpot, Salesforce, Zendesk
- **9 Messaging Platforms**: Real-time communication
- **Community Skills**: 5,000+ OpenClaw/ClawHub skills
- **Package Support**: Python (350K+) and npm (2M+) packages

### Security & Governance
- **Maturity-Based Access**: 4-tier agent governance
- **Package Security**: Vulnerability scanning and supply chain protection
- **Audit Trail**: Complete action logging
- **Human-in-the-Loop**: Approval workflows

### Deployment
- **Personal Edition**: Free, self-hosted with SQLite
- **Enterprise Edition**: Multi-user, PostgreSQL, monitoring
- **Docker Support**: Containerized deployment
- **Cloud Ready**: AWS, GCP, Azure deployment guides

## 🆚 Atom vs OpenClaw

| Aspect | Atom | OpenClaw |
|--------|------|----------|
| **Best For** | Business automation, multi-agent workflows | Personal productivity, messaging workflows |
| **Agent Model** | Multi-agent system with specialty agents | Single-agent runtime |
| **Governance** | ✅ 4-tier maturity (Student → Autonomous) | ❌ No maturity levels |
| **Memory** | ✅ Episodic memory with graduation validation | ✅ Persistent Markdown files |
| **Integrations** | 46+ business (CRM, support, dev tools) | 50+ personal (smart home, media, messaging) |
| **Architecture** | Python + FastAPI + PostgreSQL/SQLite | Node.js + local filesystem |
| **Setup** | Docker Compose (~15-30 min) | Single script (~10-30 min) |

## 📖 Related Documentation

- **[Platform Overview](../platform/README.md)** - Platform architecture
- **[Agent System](../agents/README.md)** - Agent documentation
- **[Integrations](../INTEGRATIONS/README.md)** - Integration guides

---

*Last Updated: April 12, 2026*
