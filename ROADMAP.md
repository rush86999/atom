# Atom Platform - Roadmap

## Overview

This roadmap tracks the development of the Atom AI Workforce Platform (open-source upstream version).

## Version History

### v13.0 - Architecture Alignment & Code Consolidation (2026-04)

**Status**: In Progress

**Focus**: Consolidate duplicate systems and implement Meta-Agent routing

#### Phase: Meta-Agent Routing

**Status**: ✅ Complete

**Features Implemented**:
- Intent classification (CHAT/WORKFLOW/TASK)
- Governance checks (maturity-based permissions)
- FleetAdmiral (dynamic agent recruitment)
- QueenAgent integration (WORKFLOW blueprints)
- Auto-takeover proposal mode

**Architecture**: Single-tenant deployment with user_id-based routing (no billing or quotas)

**Documentation**: See [docs/SINGLE_TENANT.md](docs/SINGLE_TENANT.md) for architecture details

### Future Versions

#### v14.0 - Enhanced Brain Systems (Planned)

- Improved episodic memory
- Enhanced learning algorithms
- Advanced reasoning capabilities

#### v15.0 - Enterprise Features (Planned)

- Advanced security features
- Enhanced monitoring and observability
- Performance optimizations

## Architecture

The Atom platform is organized into several core systems:

### Brain Systems
- **Cognitive Architecture**: Human-like reasoning, memory, attention
- **Learning Engine**: RLHF, pattern adaptation
- **World Model**: Long-term memory, semantic search
- **Reasoning Engine**: Proactive interventions
- **Cross-System Reasoning**: Correlates data from multiple sources
- **Episodic Memory**: Experience tracking and graduation

### Agent Systems
- **Meta-Agent**: Central orchestrator with governance-gated routing
- **FleetAdmiral**: Dynamic agent recruitment
- **QueenAgent**: Workflow blueprint generation
- **Specialist Agents**: Domain-specific agents (finance, sales, etc.)

### Integration Systems
- **MCP (Model Context Protocol)**: Tool integration framework
- **39+ OAuth Integrations**: Slack, Salesforce, GitHub, etc.
- **Canvas Integration**: Skill marketplace

### Governance Systems
- **AgentGovernanceService**: Maturity-based permissions
- **Graduation System**: 4-level maturity progression
- **Audit Logging**: Decision tracking

## Milestones

### Completed

- ✅ Multi-agent framework
- ✅ Governance system
- ✅ Graduation system
- ✅ World model and episodic memory
- ✅ MCP integration framework
- ✅ Meta-Agent routing (v13.0)

### In Progress

- 🔄 Architecture alignment (v13.0)

### Planned

- 📋 Enhanced brain systems (v14.0)
- 📋 Enterprise features (v15.0)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

Atom is open-source software licensed under AGPL v3. See [LICENSE.md](LICENSE.md) for details.
