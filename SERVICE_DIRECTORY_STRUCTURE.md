# Service Directory Structure Documentation

This document provides a comprehensive overview of the Atom project's service and UI directory structure for easy reference from the progress tracker.

## 📁 Root Directory Structure

```
atom/
├── src/                    # Core source code
├── backend/               # Backend API server
├── frontend-nextjs/       # Next.js frontend application
├── desktop/               # Desktop application
├── services/              # Service layer implementations
├── docs/                  # Documentation
└── deployment/            # Deployment configurations
```

## 🔧 Services Directory (`src/services/`)

The services directory contains all the core business logic and external service integrations:

### Core Services
- **`apiKeyService.ts`** - API key management and validation
- **`authService.ts`** - Authentication and authorization services
- **`connection-status-service.ts`** - Connection monitoring and status tracking
- **`workflowService.ts`** - Workflow orchestration and management
- **`skillService.ts`** - Skill management and execution

### AI/ML Services
- **`hybridLLMService.ts`** - Hybrid language model integration
- **`llmSettingsManager.ts`** - LLM configuration management
- **`nluService.ts`** - Natural Language Understanding service
- **`nluHybridIntegrationService.ts`** - Hybrid NLU integration
- **`openaiService.ts`** - OpenAI API integration

### Autonomous Services
- **`autonomousWorkflowService.ts`** - Autonomous workflow execution
- **`financeAgentService.ts`** - Financial agent services
- **`tradingAgentService.ts`** - Trading agent services

### Trading Services (`src/services/trading/`)
- Specialized trading-related services and utilities

## 🎨 UI Components Directory (`src/ui/`)

### Orchestration UI (`src/ui/orchestration/`)
- **`OrchestrationDashboard.tsx`** - Main orchestration dashboard component
- **`OrchestrationInterface.tsx`** - Orchestration user interface

## 🤖 Autonomous UI Directory (`src/autonomous-ui/`)

Components for autonomous UI interactions and workflows:

- **`AutonomousWebhookMonitor.ts`** - Webhook monitoring for autonomous operations
- **`AutonomousWorkflowIntegration.ts`** - Workflow integration for autonomous UI
- **`AutonomousWorkflowTriggers.ts`** - Trigger management for autonomous workflows
- **`EnhancedAutonomousTriggers.ts`** - Enhanced trigger capabilities
- **`CeleryIntegration.ts`** - Celery task queue integration
- **`autonomousTestRunner.ts`** - Test runner for autonomous features
- **`autonomousUIWorkflowOrchestrator.ts`** - Workflow orchestration for autonomous UI
- **`visualScreenAnalyzer.ts`** - Visual screen analysis capabilities

## 🔄 Orchestration System (`src/orchestration/`)

Core orchestration components and services for managing workflows and autonomous operations.

## 🧠 AI Components (`src/llm/` and `src/nlu_agents/`)

- **`src/llm/`** - Language model implementations and integrations
- **`src/nlu_agents/`** - Natural Language Understanding agents

## 🛠️ Utility Libraries (`src/lib/` and `src/utils/`)

- **`src/lib/`** - Shared libraries and utilities
- **`src/utils/`** - Utility functions and helpers

## 📋 Skills Directory (`src/skills/`)

Reusable skill implementations for various autonomous operations.

## 🏢 Small Business Components (`src/smallbiz/`)

Small business specific components and services.

## 📄 Templates Directory (`src/templates/`)

Template files and configurations for various operations.

## 🌐 Frontend Application (`frontend-nextjs/`)

Next.js frontend application with modern React components and UI.

## 💻 Desktop Application (`desktop/`)

Desktop application implementation using Electron or similar framework.

## 🔌 Backend API (`backend/`)

Backend API server with REST endpoints and service integrations.

## 🔗 Service Integration Patterns

### Authentication Flow
```
authService → apiKeyService → connection-status-service
```

### AI Service Chain
```
nluService → hybridLLMService → autonomousWorkflowService
```

### Orchestration Flow
```
workflowService → skillService → autonomousUIWorkflowOrchestrator
```

## 📊 Key Service Dependencies

| Service | Dependencies | Provides |
|---------|--------------|----------|
| `authService` | `apiKeyService` | Authentication |
| `workflowService` | `skillService`, `autonomousWorkflowService` | Workflow orchestration |
| `nluService` | `hybridLLMService`, `openaiService` | Natural language processing |
| `autonomousUIWorkflowOrchestrator` | All autonomous services | Autonomous UI operations |

## 🔍 Common Development Patterns

### Adding a New Service
1. Create service file in `src/services/`
2. Add TypeScript definitions if needed (`*.d.ts`)
3. Update service dependencies in this document
4. Add integration tests if applicable

### UI Component Development
1. Create component in appropriate UI directory
2. Follow React/TypeScript best practices
3. Add to relevant service integration flows
4. Update documentation

## 📝 Maintenance Notes

- Keep this document updated when adding new services or components
- Reference this document in the progress tracker for service discovery
- Update service dependencies when modifying integration patterns
- Document any new autonomous UI capabilities added

---

*Last Updated: October 18, 2025*
*Reference this document in PROGRESS_TRACKER.md for service discovery*