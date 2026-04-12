# Authentication Migration Guide

**Created**: February 2, 2026
**Status**: In Progress
**Goal**: Remove `default_user` placeholder authentication and implement proper user resolution

---

## Overview

This document guides the migration from placeholder authentication (`default_user`) to proper user authentication using the new `auth_helpers` module.

---

## New Authentication Helper Module

**Location**: `backend/core/auth_helpers.py`

### Functions

1. **`require_authenticated_user(user_id, db, allow_default=False)`**
   - Validates user authentication
   - Checks user exists in database (if db provided)
   - Raises HTTPException if not authenticated
   - Use for: Protected operations requiring authentication

2. **`get_optional_user(user_id, db)`**
   - Returns user if authenticated, None otherwise
   - Does not raise exceptions
   - Use for: Optional features, personalized content

3. **`validate_user_context(user_id, operation)`**
   - Quick validation without database query
   - Raises HTTPException if user_id missing
   - Use for: Fast validation in service methods

---

## Migration Pattern

### BEFORE (Old Pattern)
```python
async def some_function(user_id: str = "default_user"):
    # Function uses default_user without validation
    result = process_with_user(user_id)
    return result
```

### AFTER (New Pattern)
```python
from core.auth_helpers import require_authenticated_user

async def some_function(user_id: Optional[str] = None, db: Session = None):
    # Validate user authentication
    user = await require_authenticated_user(user_id, db, allow_default=False)
    user_id = user.id  # Use validated user.id

    result = process_with_user(user_id)
    return result
```

---

## Files Requiring Migration

### Priority 1 - Critical (High Usage)
1. `backend/core/lancedb_handler.py` - Vector database operations
2. `backend/core/workflow_analytics_engine.py` - Workflow analytics
3. `backend/integrations/mcp_service.py` - MCP integration
4. `backend/core/atom_agent_endpoints.py` - Agent endpoints

### Priority 2 - API Routes
5. `backend/api/graphrag_routes.py` - GraphRAG API
6. `backend/api/intelligence_routes.py` - Intelligence API
7. `backend/api/project_routes.py` - Project API
8. `backend/api/sales_routes.py` - Sales API
9. `backend/integrations/chat_routes.py` - Chat routes

### Priority 3 - Core Services
10. `backend/core/formula_extractor.py` - Formula extraction
11. `backend/core/formula_memory.py` - Formula memory
12. `backend/core/knowledge_ingestion.py` - Knowledge ingestion
13. `backend/core/knowledge_query_endpoints.py` - Knowledge queries
14. `backend/integrations/atom_communication_ingestion_pipeline.py` - Communication pipeline
15. `backend/integrations/bytewax_service.py` - Bytewax service
16. `backend/integrations/chat_orchestrator.py` - Chat orchestration

---

## Migration Steps

### Step 1: Add Import
```python
from core.auth_helpers import require_authenticated_user
```

### Step 2: Update Function Signature
```python
# Change parameter type from str to Optional[str]
# Add db: Session = None parameter

# BEFORE
async def query_vectors(..., user_id: str = "default_user"):

# AFTER
async def query_vectors(..., user_id: Optional[str] = None, db: Session = None):
```

### Step 3: Validate User
```python
# Add at the start of function
user = await require_authenticated_user(user_id, db, allow_default=False)
user_id = user.id
```

### Step 4: Test
```python
# Test that authentication is enforced
# - Missing user_id should return 401
# - Invalid user_id should return 404
# - Valid user_id should work
```

---

## Example Migration

### File: `backend/core/lancedb_handler.py`

#### BEFORE
```python
def query_vectors(self, query: str, top_k: int = 5,
                 user_id: str = "default_user") -> List[Dict]:
    """Query the vector database"""
    if self.db is None:
        return []

    # ... uses user_id directly without validation
```

#### AFTER
```python
from core.auth_helpers import require_authenticated_user
from typing import Optional

def query_vectors(self, query: str, top_k: int = 5,
                 user_id: Optional[str] = None, db: Session = None) -> List[Dict]:
    """Query the vector database"""
    # Validate user authentication
    user = require_authenticated_user(user_id, db, allow_default=False)
    user_id = user.id

    if self.db is None:
        return []

    # ... uses validated user_id
```

---

## Testing Checklist

After migrating each file, verify:

- [ ] Function signature updated (user_id: Optional[str] = None)
- [ ] Database parameter added (db: Session = None)
- [ ] Authentication helper imported
- [ ] User validation at function start
- [ ] Tests pass with valid user_id
- [ ] Tests fail with missing user_id (401)
- [ ] Tests fail with invalid user_id (404)
- [ ] No default_user references remain

---

## Rollback Plan

If migration causes issues:

1. Each file migration is independent - rollback one file at a time
2. Git commits are per-phase - rollback to previous commit
3. Feature flag available: `ALLOW_DEFAULT_USER=true` for emergency bypass

```python
# Emergency bypass for testing
user = await require_authenticated_user(user_id, db, allow_default=True)
```

---

## Progress Tracking

### Phase 2.1 - Authentication Helper ✅
- [x] Create `backend/core/auth_helpers.py`
- [x] Add helper functions
- [x] Document usage patterns

### Phase 2.2 - File Migration (In Progress)
- [ ] Priority 1 files (4)
- [ ] Priority 2 files (5)
- [ ] Priority 3 files (7)

### Phase 2.3 - Email Verification
- [ ] Implement email sending
- [ ] Add email service integration

### Phase 2.4 - JWT Verification
- [ ] Implement JWT verification
- [ ] Add token validation

---

## Notes

- **Backwards Compatibility**: Use `allow_default=True` during migration period
- **Testing**: Comprehensive test coverage required before deployment
- **Monitoring**: Add logging for authentication failures
- **Security**: Never allow `default_user` in production

---

## References

- Original Issue: 80+ incomplete implementations
- Authentication Pattern: `backend/core/auth_helpers.py`
- Testing: `pytest tests/test_auth_helpers.py -v`
