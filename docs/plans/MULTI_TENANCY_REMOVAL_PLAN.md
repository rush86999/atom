# Multi-Tenancy Removal Plan

## Overview

**Decision**: Atom is being refactored from a multi-tenant to a single-tenant architecture.

**Reason**: Simplify the codebase by removing workspace-based isolation throughout the system.

**Scope**: Remove all `workspace_id` references from:
- Database models
- Agent resolution logic
- API endpoints
- Canvas and streaming functionality
- Tests

---

## Tasks

### ✅ Completed

1. **Update CLAUDE.md** - Documentation updated to reflect single-tenant architecture

### In Progress

2. **Create Database Migration** - Remove workspace_id from tables
3. **Update Database Models** - Remove workspace relationships from models.py
4. **Update Agent Context Resolver** - Simplify agent resolution
5. **Update Governance Service** - Remove workspace filtering
6. **Update Streaming Endpoint** - Remove workspace_id parameters
7. **Update Canvas Tool** - Remove workspace_id from functions
8. **Update Canvas Routes** - Remove workspace logic
9. **Update BYOK Handler** - Remove workspace from handler
10. **Update Tests** - Remove workspace from all tests

---

## Implementation Plan

### Phase 1: Database Migration

**File**: `backend/alembic/versions/remove_workspace_multi_tenancy.py`

**Changes**:
- Drop `agent_id` index from `chat_sessions`
- Drop `workspace_id` column from `chat_sessions`
- Drop `workspace_id` index from `agent_executions` (keep column for backward compatibility)
- Drop `workspace_id` index from `canvas_audit` (keep column for backward compatibility)

**Rationale**: Keep workspace_id columns in execution tables for audit trail purposes, but remove constraints and indexes

### Phase 2: Database Models

**File**: `backend/core/models.py`

**Changes**:
- Remove `workspace_id` from `ChatSession` model
- Remove `Workspace` relationship from `ChatSession`
- Update `AgentExecution` to not require workspace_id
- Update `CanvasAudit` to not require workspace_id
- Remove workspace relationships

### Phase 3: Agent Context Resolver

**File**: `backend/core/agent_context_resolver.py`

**Changes**:
- Remove `workspace_id` parameter from `resolve_agent_for_request()`
- Remove `_get_workspace_default_agent()` method
- Remove `set_workspace_default_agent()` method
- Update fallback chain to: Explicit agent_id → Session agent → System default
- Remove workspace_id from resolution_context
- Update all docstrings

### Phase 4: Canvas Tool

**File**: `backend/tools/canvas_tool.py`

**Changes**:
- Remove `workspace_id` parameter from all functions
- Set default value "default" for workspace_id in canvas_audit entries
- Remove workspace filtering logic
- Keep all governance functionality intact

### Phase 5: Streaming Endpoint

**File**: `backend/core/atom_agent_endpoints.py`

**Changes**:
- Remove `workspace_id` from `ChatRequest` model
- Remove workspace_id logic from streaming
- Simplify to use single global chat history
- Keep all governance functionality

### Phase 6: Canvas Routes

**File**: `backend/api/canvas_routes.py`

**Changes**:
- Remove workspace_id from form submission
- Use user_id directly instead of workspace lookup
- Keep all governance checks

### Phase 7: BYOK Handler

**File**: `backend/core/llm/byok_handler.py`

**Changes**:
- Remove `workspace_id` from handler initialization
- Simplify provider routing
- Keep all streaming functionality

### Phase 8: Tests

**Files**:
- `backend/tests/test_governance_streaming.py`
- `backend/tests/test_governance_performance.py`

**Changes**:
- Remove workspace_id from test fixtures
- Remove workspace filtering from assertions
- Update test scenarios
- Ensure all tests still pass

---

## Impact Analysis

### Breaking Changes

- **API Endpoints**: Requests with `workspace_id` will be ignored (but won't break)
- **Database**: workspace_id columns kept for backward compatibility but unused
- **Agent Resolution**: No workspace-level agent defaults

### Non-Breaking

- All existing data preserved (workspace_id columns kept as nullable)
- Agent execution tracking still works
- Governance system still functional
- Canvas presentations still work

---

## Migration Strategy

### Rollout Steps

1. ✅ Update documentation (CLAUDE.md)
2. Create database migration
3. Update database models
4. Update core services (resolver, governance)
5. Update API endpoints and tools
6. Update tests
7. Run tests to verify
8. Deploy to staging
9. Monitor for issues
10. Deploy to production

### Rollback Plan

If issues arise:
1. Revert code changes via git
2. Run `alembic downgrade -1` to restore workspace columns
3. Redeploy previous version

---

## Success Criteria

- [ ] All workspace_id parameters removed from API methods
- [ ] Database workspace_id columns kept for audit trail
- [ ] All tests passing (27/27)
- [ ] No workspace filtering in queries
- [ ] Agent resolution simplified to 3-level fallback
- [ ] Documentation updated
- [ ] Zero regression in functionality

---

## Notes

### Why Keep workspace_id in Execution Tables?

Even though we're removing multi-tenancy, keeping workspace_id in `agent_executions` and `canvas_audit`:
- Preserves audit trail
- Allows future analysis
- Doesn't hurt performance (nullable columns)
- Maintains backward compatibility

### Simplified Agent Resolution

**Before**: 4-level fallback
1. Explicit agent_id
2. Session agent
3. Workspace default
4. System default

**After**: 3-level fallback
1. Explicit agent_id
2. Session agent
3. System default

---

**Status**: In progress (1/10 tasks complete)
