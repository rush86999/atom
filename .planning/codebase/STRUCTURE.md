# Codebase Structure

**Analysis Date:** 2026-02-10

## Directory Layout

```
atom/
├── backend/                     # Main backend application
│   ├── alembic/                # Database migrations
│   ├── api/                    # API routes and endpoints
│   │   ├── admin/             # Admin-specific routes
│   │   ├── canvas_routes.py   # Canvas and form handling
│   │   ├── browser_routes.py  # Browser automation endpoints
│   │   ├── device_capabilities.py  # Device control endpoints
│   │   ├── deeplinks.py       # Deep linking functionality
│   │   └── mobile_*           # Mobile-specific routes
│   ├── core/                   # Core business logic
│   │   ├── models.py          # Database models
│   │   ├── agent_governance_service.py  # Agent lifecycle management
│   │   ├── trigger_interceptor.py      # Maturity-based routing
│   │   ├── episode_segmentation_service.py  # Memory segmentation
│   │   ├── student_training_service.py # Training orchestrator
│   │   ├── governance_cache.py        # Performance cache
│   │   ├── service_factory.py        # Dependency injection
│   │   ├── canvas_type_registry.py   # Presentation registry
│   │   └── llm/               # LLM provider integration
│   ├── tools/                  # Tool implementations
│   │   ├── canvas_tool.py    # Canvas presentation tool
│   │   ├── browser_tool.py   # Browser automation tool
│   │   └── device_tool.py     # Device control tool
│   ├── tests/                  # Comprehensive test suite
│   │   ├── property_tests/    # Property-based testing
│   │   ├── e2e/              # End-to-end testing
│   │   ├── integration/       # Integration testing
│   │   └── coverage_reports/  # Test coverage artifacts
│   ├── integrations/           # External service integrations
│   │   ├── adapters/         # Integration adapters
│   │   ├── universal/         # Universal integration patterns
│   │   └── pdf_processing/   # Document processing
│   ├── workers/               # Background processing
│   ├── migrations/            # Legacy migrations
│   └── docs/                 # Backend documentation
├── mobile/                    # React Native mobile app
│   ├── App.js                # Main app component
│   ├── components/           # Mobile UI components
│   ├── navigation/          # Navigation stack
│   └── package.json          # Mobile dependencies
├── docs/                     # Comprehensive documentation
│   ├── EPISODIC_MEMORY_IMPLEMENTATION.md
│   ├── STUDENT_AGENT_TRAINING_IMPLEMENTATION.md
│   ├── CANVAS_IMPLEMENTATION_COMPLETE.md
│   ├── AGENT_GUIDANCE_IMPLEMENTATION.md
│   ├── BROWSER_AUTOMATION.md
│   ├── DEVICE_CAPABILITIES.md
│   └── DEEPLINK_IMPLEMENTATION.md
└── workflow_templates/       # Pre-built workflow templates
```

## Directory Purposes

**backend/api/**:
- Purpose: HTTP API endpoints and WebSocket handlers
- Contains: Route definitions, request/response handling, authentication
- Key files: `canvas_routes.py`, `browser_routes.py`, `device_capabilities.py`
- Tests: `backend/tests/api/`

**backend/core/**:
- Purpose: Core business logic and domain services
- Contains: Agent management, governance, memory system, LLM integration
- Key files: `agent_governance_service.py`, `trigger_interceptor.py`, `models.py`
- Tests: `backend/tests/core/`

**backend/tools/**:
- Purpose: Agent tool implementations for external capabilities
- Contains: Canvas presentations, browser automation, device control
- Key files: `canvas_tool.py`, `browser_tool.py`, `device_tool.py`
- Tests: `backend/tests/tools/`

**backend/integrations/**:
- Purpose: Third-party service integrations
- Contains: OAuth adapters, service bridges, processing utilities
- Key files: Various adapter implementations
- Tests: `backend/tests/integrations/`

**backend/tests/**:
- Purpose: Comprehensive test coverage across all domains
- Contains: Unit tests, integration tests, property-based tests, E2E tests
- Structure: Organized by feature area with coverage reports
- Key directories: `property_tests/`, `e2e/`, `integration/`

**mobile/**:
- Purpose: React Native mobile application
- Contains: UI components, navigation, device integration
- Key files: `App.js`, components, navigation stack
- Tests: Mobile-specific testing with Expo

**docs/**:
- Purpose: Comprehensive feature documentation
- Contains: Implementation guides, API documentation, feature specs
- Key files: Feature-specific markdown files with examples

## Key File Locations

**Entry Points:**
- `backend/main_api_app.py`: Main FastAPI application server
- `backend/core/atom_agent_endpoints.py`: Chat and streaming endpoints
- `mobile/App.js`: Mobile app entry point

**Configuration:**
- `backend/alembic.ini`: Database migration configuration
- `backend/requirements.txt`: Python dependencies
- `mobile/package.json`: Mobile dependencies

**Core Logic:**
- `backend/core/models.py`: Database schema and relationships
- `backend/core/agent_governance_service.py`: Agent lifecycle management
- `backend/core/trigger_interceptor.py`: Maturity-based routing
- `backend/core/episode_segmentation_service.py`: Memory segmentation

**API Endpoints:**
- `backend/api/canvas_routes.py`: Canvas and form handling
- `backend/api/browser_routes.py`: Browser automation
- `backend/api/device_capabilities.py`: Device control
- `backend/api/deeplinks.py`: Deep linking

**Testing:**
- `backend/tests/test_trigger_interceptor.py`: Agent routing tests
- `backend/tests/test_episode_segmentation.py`: Memory system tests
- `backend/tests/test_agent_guidance_canvas.py`: Real-time guidance tests
- `backend/tests/property_tests/`: Property-based testing framework

## Naming Conventions

**Files:**
- Services: `*_service.py` (e.g., `agent_governance_service.py`)
- Tools: `*_tool.py` (e.g., `canvas_tool.py`)
- Routes: `*_routes.py` (e.g., `canvas_routes.py`)
- Tests: `test_*.py` (e.g., `test_trigger_interceptor.py`)
- Models: `models.py` (single file for all models)

**Classes:**
- PascalCase for services and models (e.g., `AgentGovernanceService`)
- PascalCase for tools (e.g., `CanvasTool`)

**Functions:**
- snake_case for functions (e.g., `submit_feedback`)
- snake_case for methods (e.g., `register_agent`)

**Variables:**
- snake_case for local variables (e.g., `agent_id`)
- UPPER_SNAKE_CASE for constants (e.g., `CACHE_TTL`)

**Database Tables:**
- snake_case for table names (e.g., `agent_registry`)
- snake_case for column names (e.g., `created_at`)

## Where to Add New Code

**New Agent Feature:**
- Core logic: `backend/core/` (new service or existing service)
- API endpoints: `backend/api/` (new route file)
- Tool implementation: `backend/tools/` (if external capability)
- Tests: `backend/tests/test_*.py` and `backend/tests/property_tests/`
- Documentation: `backend/docs/`

**New Integration:**
- Adapter: `backend/integrations/adapters/`
- Service config: `backend/integrations/service_configs/`
- API routes: `backend/api/` (if endpoint needed)
- Tests: `backend/tests/integrations/`

**New Canvas Type:**
- Registration: `backend/core/canvas_type_registry.py`
- Implementation: `backend/tools/canvas_tool.py` (extend existing)
- Tests: `backend/tests/tools/test_canvas_tool.py`

**New Memory Feature:**
- Service: `backend/core/` (e.g., `episode_retrieval_service.py`)
- API: `backend/api/episode_routes.py` (extend existing)
- Tests: `backend/tests/test_episode_*.py`

**New Mobile Feature:**
- Components: `mobile/components/`
- Navigation: `mobile/navigation/`
- API integration: `mobile/api/` (if needed)

## Special Directories

**backend/.pytest_cache/**:
- Purpose: Test execution artifacts
- Generated: Yes
- Committed: No (in .gitignore)

**backend/alembic/**:
- Purpose: Database migration history
- Generated: Yes (but migrations are committed)
- Committed: Yes

**backend/tests/coverage_reports/**:
- Purpose: Test coverage artifacts
- Generated: Yes
- Committed: Yes (for CI/CD tracking)

**mobile/node_modules/**:
- Purpose: Node.js dependencies
- Generated: Yes
- Committed: No (in .gitignore)

**backend/.archive/**:
- Purpose: Historical project archives
- Generated: Yes
- Committed: Yes (for reference)

---

*Structure analysis: 2026-02-10*