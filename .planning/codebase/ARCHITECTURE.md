# Architecture

**Analysis Date:** 2026-02-10

## Pattern Overview

**Overall:** Multi-Agent AI Platform with Governance-First Architecture

**Key Characteristics:**
- Agent maturity-based governance (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
- Real-time streaming LLM responses with multi-provider support
- Event-driven episodic memory system
- Canvas-based presentation engine with audit trails
- Browser automation through CDP
- Mobile-first responsive design

## Layers

**Presentation Layer:**
- Purpose: User interfaces for agent interactions
- Location: `backend/api/`, `mobile/`
- Contains: REST API routes, WebSocket handlers, mobile React Native components
- Depends on: Core services, database
- Used by: Frontend clients, mobile apps

**Agent Execution Layer:**
- Purpose: AI agent orchestration and execution
- Location: `backend/core/agent_governance_service.py`, `backend/core/trigger_interceptor.py`
- Contains: Agent lifecycle management, maturity routing, supervision
- Depends on: Governance cache, database, LLM providers
- Used by: Presentation layer for agent operations

**Core Services Layer:**
- Purpose: Business logic and domain services
- Location: `backend/core/`, `backend/tools/`
- Contains: Canvas tool, browser automation, episodic memory, governance
- Depends on: Database, external integrations
- Used by: Agent execution layer

**Data Layer:**
- Purpose: Data persistence and retrieval
- Location: `backend/core/models.py`, `backend/alembic/`
- Contains: SQL models, migrations, LanceDB vector storage
- Depends on: PostgreSQL, SQLite, LanceDB
- Used by: All layers above

**Integration Layer:**
- Purpose: External service integrations
- Location: `backend/integrations/`, `backend/api/browser_routes.py`, `backend/api/device_capabilities.py`
- Contains: OAuth adapters, service bridges, PDF processing
- Depends on: Third-party APIs, cloud services
- Used by: Core services for external connectivity

## Data Flow

**Agent Request Flow:**

1. Request → `AgentContextResolver` → `GovernanceCache` (<1ms)
2. Governance check → `AgentGovernanceService` → Maturity assessment
3. Routing decision → `TriggerInterceptor` → Appropriate handler
4. Execution → `CanvasTool`/`BrowserTool`/`DeviceTool`
5. Response → WebSocket streaming → Real-time updates

**Episodic Memory Flow:**

1. Agent execution → `EpisodeSegmentationService`
2. Automatic segmentation based on time gaps, topic changes, task completion
3. Storage → PostgreSQL (hot) + LanceDB (cold)
4. Retrieval → Four modes: Temporal, Semantic, Sequential, Contextual
5. Learning integration → Agent graduation framework

**Canvas Presentation Flow:**

1. Agent request → `CanvasTool` → Governance validation
2. Canvas creation → `CanvasAudit` tracking → WebSocket updates
3. User interaction → Form submission → Agent execution linking
4. Feedback collection → Episode enrichment → Memory integration

## Key Abstractions

**Agent Maturity:**
- Purpose: Granular permission control and routing
- Examples: `backend/core/trigger_interceptor.py` (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
- Pattern: Enum-based routing with context-aware decisions

**Governance Cache:**
- Purpose: High-performance (<1ms) permission checks
- Examples: `backend/core/governance_cache.py`
- Pattern: In-memory caching with invalidation on state changes

**Canvas Registry:**
- Purpose: Extensible presentation system
- Examples: `backend/core/canvas_type_registry.py`
- Pattern: Plugin architecture for different canvas types (charts, forms, etc.)

**Episode Segmentation:**
- Purpose: Automatic interaction grouping for learning
- Examples: `backend/core/episode_segmentation_service.py`
- Pattern: Time-based + semantic similarity + task completion detection

**Service Factory:**
- Purpose: Dependency injection and service orchestration
- Examples: `backend/core/service_factory.py`
- Pattern: Factory pattern with environment-aware configuration

## Entry Points

**Main API Server:**
- Location: `backend/main_api_app.py`
- Triggers: HTTP requests, WebSocket connections
- Responsibilities: Request routing, middleware, CORS handling

**Agent Endpoints:**
- Location: `backend/core/atom_agent_endpoints.py`
- Triggers: Chat requests, streaming connections
- Responsibilities: LLM routing, agent execution, response streaming

**Canvas Routes:**
- Location: `backend/api/canvas_routes.py`
- Triggers: Canvas interactions, form submissions
- Responsibilities: Presentation management, audit logging

**Browser Automation:**
- Location: `backend/tools/browser_tool.py`, `backend/api/browser_routes.py`
- Triggers: Web scraping requests, form filling
- Responsibilities: CDP session management, element interaction

**Device Capabilities:**
- Location: `backend/tools/device_tool.py`, `backend/api/device_capabilities.py`
- Triggers: Mobile device requests
- Responsibilities: Camera, location, notifications, command execution

**Episodic Memory API:**
- Location: `backend/api/episode_routes.py`
- Triggers: Memory operations, graduation checks
- Responsibilities: Episode CRUD, retrieval, lifecycle management

## Error Handling

**Strategy:** Centralized error handling with graceful degradation

**Patterns:**
- Error decorators with consistent response format (`backend/core/error_handler_decorator.py`)
- Structured logging with correlation IDs
- Circuit breakers for external services
- Fallback mechanisms for non-critical failures

## Cross-Cutting Concerns

**Logging:**
- Structured logging with context (user ID, agent ID, execution ID)
- Centralized logging configuration
- Log aggregation for debugging

**Validation:**
- Pydantic models for API input validation
- Business rule validation in services
- Security validation for external inputs

**Authentication:**
- JWT-based authentication with refresh tokens
- Role-based access control (RBAC)
- OAuth integration for third-party services

**Monitoring:**
- Real-time WebSocket connections for live updates
- Performance metrics collection (governance cache hit rate, response times)
- Health check endpoints for service monitoring

**Caching:**
- Multi-level caching: In-memory (governance) + Redis (session)
- Cache invalidation on data mutations
- Performance optimization for frequent operations

---

*Architecture analysis: 2026-02-10*