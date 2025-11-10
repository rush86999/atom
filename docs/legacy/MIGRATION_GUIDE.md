# ATOM Migration Guide

## Overview

This guide documents the recent reorganization of the ATOM codebase to improve maintainability, reduce duplication, and create a clearer separation between web and desktop applications.

## Changes Summary

### 1. Frontend Services Reorganization

**Before:**
```
src/services/
├── ChatOrchestrationService.ts
├── apiKeyService.ts
├── authService.ts
├── autonomousWorkflowService.ts
├── connection-status-service.ts
├── financeAgentService.ts
├── hybridLLMService.ts
├── llmSettingsManager.ts
├── nluHybridIntegrationService.ts
├── nluService.ts
├── openaiService.ts
├── skillService.ts
├── tradingAgentService.ts
├── workflowService.ts
└── trading/
```

**After:**
```
src/services/
├── ai/                          # AI and ML services
│   ├── ChatOrchestrationService.ts
│   ├── hybridLLMService.ts
│   ├── llmSettingsManager.ts
│   ├── nluHybridIntegrationService.ts
│   ├── nluService.ts
│   ├── openaiService.ts
│   ├── skillService.ts
│   ├── financeAgentService.ts
│   ├── tradingAgentService.ts
│   └── trading/
├── integrations/                # External service integrations
│   ├── apiKeyService.ts
│   ├── authService.ts
│   └── connection-status-service.ts
├── workflows/                   # Workflow automation
│   ├── autonomousWorkflowService.ts
│   └── workflowService.ts
└── utils/                       # Utility services
```

### 2. Backend Consolidation

**New Structure:**
```
backend/consolidated/
├── core/                       # Core backend functionality
│   ├── database_manager.py
│   └── auth_service.py
├── integrations/               # External service integrations
│   ├── asana_service.py
│   ├── asana_routes.py
│   ├── dropbox_service.py
│   ├── dropbox_routes.py
│   ├── outlook_service.py
│   └── outlook_routes.py
├── workflows/                  # Workflow engine
└── api/                        # API endpoints
```

## Migration Steps

### For Frontend Developers

#### 1. Update Import Paths

**Before:**
```typescript
import { ChatOrchestrationService } from '../services/ChatOrchestrationService';
import { authService } from '../services/authService';
import { workflowService } from '../services/workflowService';
```

**After:**
```typescript
import { ChatOrchestrationService } from '../services/ai/ChatOrchestrationService';
import { authService } from '../services/integrations/authService';
import { workflowService } from '../services/workflows/workflowService';
```

#### 2. Update Test Imports

**Before:**
```typescript
import { nluService } from '../services/nluService';
```

**After:**
```typescript
import { nluService } from '../services/ai/nluService';
```

### For Backend Developers

#### 1. Use Consolidated Services

**Before:**
```python
from backend.integrations.asana_service import AsanaService
from backend.python-api-service.database_manager import DatabaseManager
```

**After:**
```python
from backend.consolidated.integrations.asana_service import AsanaService
from backend.consolidated.core.database_manager import DatabaseManager
```

#### 2. Integration Service Updates

The following integration services have been consolidated:
- `asana_service.py` → `consolidated/integrations/asana_service.py`
- `dropbox_service_enhanced.py` → `consolidated/integrations/dropbox_service.py`
- `outlook_service_enhanced.py` → `consolidated/integrations/outlook_service.py`

### For Desktop App Developers

#### No Changes Required

The desktop app continues to use its embedded backend in:
```
desktop/tauri/src-tauri/python-backend/backend/python-api-service/
```

The desktop-specific modifications (local storage, audio processing) are preserved.

## Impact Analysis

### Breaking Changes

1. **Frontend Import Paths**: All service imports in the frontend need to be updated to reflect the new directory structure.

2. **Test Files**: Test imports for service files need to be updated.

3. **Backend References**: Any direct references to moved backend files need updating.

### Non-Breaking Changes

1. **Desktop App**: No changes required as it uses its own embedded backend.

2. **API Endpoints**: All existing API endpoints remain unchanged.

3. **Database Schema**: No database schema changes.

## Verification Steps

### 1. Test Frontend Build

```bash
cd frontend-nextjs
npm run build
```

### 2. Test Backend Startup

```bash
cd backend/python-api-service
python start_app.py
```

### 3. Test Desktop App

```bash
cd desktop/tauri
npm run dev
```

### 4. Run Integration Tests

```bash
./test-all-features.sh
```

## Rollback Plan

If issues are encountered:

1. **Frontend**: Revert to previous service file locations
2. **Backend**: Continue using original backend files
3. **Desktop**: No changes needed (unaffected)

## Benefits of Reorganization

1. **Better Organization**: Services grouped by domain (AI, integrations, workflows)
2. **Reduced Duplication**: Consolidated backend integration services
3. **Clearer Architecture**: Separation between web and desktop backends
4. **Improved Maintainability**: Logical grouping makes code easier to navigate
5. **Enhanced Collaboration**: Clear boundaries between different service types

## Future Considerations

1. **Shared Library**: Consider creating a shared library for common utilities
2. **API Gateway**: Implement API gateway for better microservice management
3. **Event Bus**: Add event-driven architecture for better scalability
4. **Monitoring**: Enhanced observability across all services

## Support

For migration assistance, contact the ATOM development team or refer to the updated architecture documentation in `ARCHITECTURE.md`.

---
*Migration Guide Version: 1.0*
*Last Updated: 2025*