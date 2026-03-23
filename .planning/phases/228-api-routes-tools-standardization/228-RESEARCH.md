# Phase 228: API Routes & Tools Standardization - Research

**Researched:** March 22, 2026
**Domain:** LLM Service Standardization, API Routes Migration
**Confidence:** HIGH

## Summary

Phase 228 completes the BYOKHandler → LLMService migration by updating **3 remaining API route files** that still use BYOKHandler directly. Phase 225.1 successfully migrated all agent services, and Phase 227 migrated `atom_agent_endpoints.py`, but several API routes remain on the old BYOKHandler pattern.

**Primary recommendation:** Update the 3 remaining API routes to use LLMService instead of BYOKHandler, following the proven pattern from Phase 225.1 and Phase 227. This completes STD-04 and STD-05 (BYOKHandler Standardization for API routes and tools).

**Key files identified:**
1. `backend/api/competitor_analysis_routes.py` - Competitor analysis with structured LLM output
2. `backend/api/learning_plan_routes.py` - AI-generated learning plans with structured output
3. `backend/api/mobile_agent_routes.py` - Mobile-optimized agent chat with streaming

**Confidence: HIGH** - Migration pattern is well-established from Phase 225.1 (8 plans completed) and Phase 227 (atom_agent_endpoints.py migration). All patterns, pitfalls, and test strategies are documented.

---

## Standard Stack

### Core Components (No New Libraries)

| Component | Version | Purpose | Status |
|-----------|---------|---------|--------|
| **LLMService** | Existing | Unified LLM interface wrapper | ✅ Ready |
| **BYOKHandler** | Existing | LLM provider routing & BYOK key resolution | ✅ Ready (infrastructure) |
| **API Routes** | Existing | FastAPI route handlers | ✅ Ready (migration needed) |

### LLMService API (from Phase 225.1)

```python
from core.llm_service import LLMService

# Initialize
llm = LLMService(workspace_id="default", db=db_session)

# Generate response (old: generate_response)
response = await llm.generate(prompt="...", model="gpt-4o")

# Generate structured output (old: generate_structured_response)
structured = await llm.generate_structured(
    prompt="...",
    response_model=MyResponseModel,
    temperature=0.3
)

# Stream completion
async for chunk in llm.stream_completion(messages=[...], model="gpt-4o"):
    yield chunk

# Cognitive tier classification
tier = llm.analyze_query_complexity(query)

# Get optimal provider
provider_id, model = llm.get_optimal_provider(tier, task_type="chat")
```

### Method Name Changes (Critical)

| Old Method (BYOKHandler) | New Method (LLMService) |
|--------------------------|-------------------------|
| `generate_response()` | `generate()` |
| `generate_structured_response()` | `generate_structured()` |
| `stream_completion()` | `stream_completion()` (unchanged) |
| `analyze_query_complexity()` | `analyze_query_complexity()` (unchanged) |
| `get_optimal_provider()` | `get_optimal_provider()` (unchanged) |

---

## Architecture Patterns

### Pattern 1: Module-Level BYOKHandler Instantiation

**What:** Replace module-level BYOKHandler singleton with LLMService instances.

**When to use:** API routes that instantiate BYOKHandler at module level.

**Example:**
```python
# OLD (Phase 228 before)
from core.llm.byok_handler import BYOKHandler

# Module-level singleton
byok_handler = BYOKHandler()

@router.post("/analyze")
async def analyze(request):
    result = await byok_handler.generate_structured_response(...)

# NEW (Phase 228 after)
from core.llm_service import LLMService

# Function-level instantiation
@router.post("/analyze")
async def analyze(request, db: Session = Depends(get_db)):
    llm = LLMService(workspace_id="default", db=db)
    result = await llm.generate_structured(...)
```

**Source:** Phase 227 Plan 01 Summary, mobile_agent_routes.py migration pattern

**Why module-level singletons are problematic:**
- No database session for usage tracking
- Workspace ID hardcoded to "default"
- Difficult to test (can't patch per-request instances)
- Violates dependency injection principles

### Pattern 2: Structured Output Migration

**What:** Update `generate_structured_response()` calls to `generate_structured()`.

**When to use:** Routes using Pydantic models for structured LLM output.

**Example:**
```python
# OLD
from core.llm.byok_handler import BYOKHandler
from pydantic import BaseModel

class CompetitorInsight(BaseModel):
    competitor: str
    strengths: List[str]
    weaknesses: List[str]

byok_handler = BYOKHandler()
result = await byok_handler.generate_structured_response(
    prompt=prompt,
    system_instruction=system_instruction,
    response_model=CompetitorInsight,
    temperature=0.3
)

# NEW
from core.llm_service import LLMService

llm = LLMService(workspace_id="default", db=db)
result = await llm.generate_structured(
    prompt=prompt,
    system_instruction=system_instruction,
    response_model=CompetitorInsight,
    temperature=0.3
)
```

**Source:** Phase 225.1 Plan 01 Summary - GenericAgent migration

### Pattern 3: WebSocket Streaming Migration

**What:** Update streaming endpoints to use LLMService.stream_completion().

**When to use:** WebSocket-based streaming LLM responses.

**Example:**
```python
# OLD (mobile_agent_routes.py lines 322-363)
from core.llm.byok_handler import BYOKHandler

byok_handler = BYOKHandler(workspace_id="default", provider_id="auto")
complexity = byok_handler.analyze_query_complexity(message, task_type="chat")
provider_id, model = byok_handler.get_optimal_provider(complexity, ...)

async for token in byok_handler.stream_completion(
    messages=messages,
    model=model,
    provider_id=provider_id,
    ...
):
    yield token

# NEW
from core.llm_service import LLMService

llm_service = LLMService(workspace_id="default")
complexity = llm_service.analyze_query_complexity(message, task_type="chat")
provider_id, model = llm_service.get_optimal_provider(complexity, ...)

async for token in llm_service.stream_completion(
    messages=messages,
    model=model,
    provider_id=provider_id,
    ...
):
    yield token
```

**Source:** Phase 227 Plan 01 Summary - atom_agent_endpoints.py streaming migration

### Pattern 4: Import Path Corrections

**What:** Use correct import path for LLMService.

**When to use:** Importing LLMService in API route files.

**Example:**
```python
# CORRECT
from core.llm_service import LLMService

# WRONG (old Phase 225.1 Plan 02 bug)
from core.llm.llm_service import LLMService
```

**Source:** Phase 225.1 Plan 03 Summary - Import path corrections

### Anti-Patterns to Avoid

- **Module-level BYOKHandler singletons:** Use function-level LLMService instances
- **Old method names:** Use `generate()` not `generate_response()`, `generate_structured()` not `generate_structured_response()`
- **Wrong import path:** Use `from core.llm_service import` not `from core.llm.llm_service import`
- **Missing database session:** Pass `db=db` to LLMService for usage tracking

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM provider routing | Custom provider switching logic | LLMService.get_optimal_provider() | BPC algorithm, cache-aware routing, cost optimization |
| BYOK key resolution | Custom API key management | LLMService (wraps BYOKHandler) | Encryption, audit trail, workspace isolation |
| Usage tracking | Custom token counting | LLMService with db session | Automatic tracking, cost monitoring, quota enforcement |
| Structured output | Custom JSON parsing/validation | LLMService.generate_structured() | Pydantic validation, retry logic, error handling |

**Key insight:** LLMService provides a complete abstraction over BYOKHandler with added benefits (usage tracking, cost optimization, caching). Building custom LLM handling code bypasses these benefits.

---

## Common Pitfalls

### Pitfall 1: Module-Level Singletons

**What goes wrong:** Module-level BYOKHandler instances can't track usage per-request.

**Why it happens:** Copying old pattern from initial API route development.

**How to avoid:** Instantiate LLMService inside route handlers:
```python
# BAD
byok_handler = BYOKHandler()  # Module level

# GOOD
@router.post("/endpoint")
async def endpoint(db: Session = Depends(get_db)):
    llm = LLMService(workspace_id="default", db=db)  # Function level
```

**Warning signs:** Global BYOKHandler instances at module top, no database session parameter

### Pitfall 2: Using Old Method Names

**What goes wrong:** Calling `generate_response()` or `generate_structured_response()` on LLMService causes AttributeError.

**Why it happens:** Phase 225.1 renamed methods for consistency (generate_response → generate).

**How to avoid:** Use new method names:
- `generate()` (not `generate_response()`)
- `generate_structured()` (not `generate_structured_response()`)

**Warning signs:** AttributeError: 'LLMService' object has no attribute 'generate_response'

### Pitfall 3: Wrong Import Path

**What goes wrong:** ImportError: No module named 'core.llm.llm_service'

**Why it happens:** Phase 225.1 Plan 02 initially used wrong path, corrected in Plan 03.

**How to avoid:** Always use `from core.llm_service import LLMService`

**Warning signs:** ImportError when importing LLMService

### Pitfall 4: Forgetting Database Session

**What goes wrong:** LLM usage not tracked in database, costs not monitored.

**Why it happens:** LLMService requires db session for usage tracking.

**How to avoid:** Pass db session when tracking is needed:
```python
llm = LLMService(workspace_id=ws_id, db=db)
```

**Warning signs:** Missing records in llm_usage_tracker table

### Pitfall 5: Test Mock Patches

**What goes wrong:** Tests still patching BYOKHandler fail with AttributeError.

**Why it happens:** Test mocks not updated after migration.

**How to avoid:** Patch the import path used by code under test:
```python
# If code imports LLMService
from unittest.mock import patch

# Patch LLMService, not BYOKHandler
with patch('api.mobile_agent_routes.LLMService') as mock_llm:
    mock_llm.return_value.generate_structured.return_value = result
```

**Warning signs:** Tests failing with AttributeError in migrated code

---

## Code Examples

### Example 1: Migrating competitor_analysis_routes.py

**Current code (lines 18, 27, 156):**
```python
from core.llm.byok_handler import BYOKHandler

# Module-level singleton
byok_handler = BYOKHandler()

# Usage in analyze_with_llm function
result = await byok_handler.generate_structured_response(
    prompt=prompt,
    system_instruction=system_instruction,
    response_model=CompetitorInsight,
    temperature=0.3,
    task_type="analysis",
    agent_id=None
)
```

**Migrated code:**
```python
from core.llm_service import LLMService

# Function-level instantiation
async def analyze_with_llm(competitor_data: dict, focus_areas: List[str], db: Session):
    llm = LLMService(workspace_id="default", db=db)

    result = await llm.generate_structured(
        prompt=prompt,
        system_instruction=system_instruction,
        response_model=CompetitorInsight,
        temperature=0.3,
        task_type="analysis",
        agent_id=None
    )
```

**Source:** Phase 225.1 Pattern 1, Phase 227 streaming migration

### Example 2: Migrating learning_plan_routes.py

**Current code (lines 18, 27, 128):**
```python
from core.llm.byok_handler import BYOKHandler

# Module-level singleton
byok_handler = BYOKHandler()

# Usage in generate_learning_modules function
result = await byok_handler.generate_structured_response(
    prompt=prompt,
    system_instruction=system_instruction,
    response_model=LearningPlanModules,
    temperature=0.4,
    task_type="analysis",
    agent_id=None
)
```

**Migrated code:**
```python
from core.llm_service import LLMService

async def generate_learning_modules(
    topic: str,
    current_level: str,
    duration_weeks: int,
    preferred_formats: List[str],
    learning_goals: List[str] = [],
    db: Session
) -> List[LearningModule]:
    llm = LLMService(workspace_id="default", db=db)

    result = await llm.generate_structured(
        prompt=prompt,
        system_instruction=system_instruction,
        response_model=LearningPlanModules,
        temperature=0.4,
        task_type="analysis",
        agent_id=None
    )
```

**Source:** Phase 225.1 Pattern 1 - GenericAgent migration

### Example 3: Migrating mobile_agent_routes.py

**Current code (lines 26, 322-363):**
```python
from core.llm.byok_handler import BYOKHandler

# In mobile_agent_chat function
byok_handler = BYOKHandler(workspace_id="default", provider_id="auto")
complexity = byok_handler.analyze_query_complexity(request.message, task_type="chat")
provider_id, model = byok_handler.get_optimal_provider(
    complexity,
    task_type="chat",
    prefer_cost=True,
    tenant_plan="free",
    is_managed_service=False,
    requires_tools=False
)

async for token in byok_handler.stream_completion(
    messages=messages,
    model=model,
    provider_id=provider_id,
    temperature=0.7,
    max_tokens=2000,
    agent_id=agent_id
):
    yield token
```

**Migrated code:**
```python
from core.llm_service import LLMService

# In mobile_agent_chat function
llm_service = LLMService(workspace_id="default")
complexity = llm_service.analyze_query_complexity(request.message, task_type="chat")
provider_id, model = llm_service.get_optimal_provider(
    complexity,
    task_type="chat",
    prefer_cost=True,
    tenant_plan="free",
    is_managed_service=False,
    requires_tools=False
)

async for token in llm_service.stream_completion(
    messages=messages,
    model=model,
    provider_id=provider_id,
    temperature=0.7,
    max_tokens=2000,
    agent_id=agent_id
):
    yield token
```

**Source:** Phase 227 Plan 01 Summary - atom_agent_endpoints.py streaming migration

### Example 4: Updating Test Mocks

**Current tests (if they exist):**
```python
from unittest.mock import patch

@patch('api.competitor_analysis_routes.BYOKHandler')
async def test_analyze_competitors(mock_byok):
    mock_byok.return_value.generate_structured_response.return_value = insight
```

**Updated tests:**
```python
from unittest.mock import patch

@patch('api.competitor_analysis_routes.LLMService')
async def test_analyze_competitors(mock_llm_class):
    mock_llm = AsyncMock()
    mock_llm_class.return_value = mock_llm
    mock_llm.generate_structured.return_value = insight
```

**Source:** Phase 225.1 Plan 05-07 Summary - Test mock updates

---

## State of the Art

### LLM Service Architecture Evolution

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct BYOKHandler in API routes | LLMService wrapper | Phase 225.1 (Feb 2026) | Unified interface, usage tracking |
| Module-level singletons | Function-level instances | Phase 227 (Mar 2026) | Per-request tracking, testability |
| Inconsistent method names | Standardized API | Phase 225.1 | generate(), generate_structured() |
| Manual usage tracking | Automatic tracking via db session | Phase 225.1 | Cost monitoring, quota enforcement |

**Deprecated patterns:**
- **Module-level BYOKHandler:** Use function-level LLMService instances
- **Method names:** generate_response → generate, generate_structured_response → generate_structured
- **Import path:** from core.llm.llm_service → from core.llm_service

---

## File-by-File Migration Guide

### File 1: backend/api/competitor_analysis_routes.py

**Current usage (lines 18, 27, 156):**
```python
from core.llm.byok_handler import BYOKHandler

byok_handler = BYOKHandler()  # Module-level singleton

result = await byok_handler.generate_structured_response(
    prompt=prompt,
    system_instruction=system_instruction,
    response_model=CompetitorInsight,
    temperature=0.3,
    task_type="analysis",
    agent_id=None
)
```

**Migration steps:**
1. Replace import: `from core.llm_service import LLMService`
2. Remove module-level singleton (line 27)
3. Add `db: Session` parameter to `analyze_with_llm()` function
4. Replace instantiation: `llm = LLMService(workspace_id="default", db=db)`
5. Update method call: `generate_structured_response()` → `generate_structured()`
6. Update function signature to accept db parameter

**Complexity:** LOW - Single function, straightforward replacement

**Testing:** Competitor analysis API tests

### File 2: backend/api/learning_plan_routes.py

**Current usage (lines 18, 27, 128):**
```python
from core.llm.byok_handler import BYOKHandler

byok_handler = BYOKHandler()  # Module-level singleton

result = await byok_handler.generate_structured_response(
    prompt=prompt,
    system_instruction=system_instruction,
    response_model=LearningPlanModules,
    temperature=0.4,
    task_type="analysis",
    agent_id=None
)
```

**Migration steps:**
1. Replace import: `from core.llm_service import LLMService`
2. Remove module-level singleton (line 27)
3. Add `db: Session` parameter to `generate_learning_modules()` function
4. Replace instantiation: `llm = LLMService(workspace_id="default", db=db)`
5. Update method call: `generate_structured_response()` → `generate_structured()`
6. Update route handler to pass db session to helper function

**Complexity:** LOW - Single function, straightforward replacement

**Testing:** Learning plan API tests

### File 3: backend/api/mobile_agent_routes.py

**Current usage (lines 26, 322-363):**
```python
from core.llm.byok_handler import BYOKHandler

# In mobile_agent_chat function
byok_handler = BYOKHandler(workspace_id="default", provider_id="auto")
complexity = byok_handler.analyze_query_complexity(request.message, task_type="chat")
provider_id, model = byok_handler.get_optimal_provider(complexity, ...)

async for token in byok_handler.stream_completion(
    messages=messages,
    model=model,
    provider_id=provider_id,
    temperature=0.7,
    max_tokens=2000,
    agent_id=agent_id
):
    yield token
```

**Migration steps:**
1. Replace import: `from core.llm_service import LLMService`
2. Replace instantiation: `llm_service = LLMService(workspace_id="default")`
3. Update method calls (analyze_query_complexity, get_optimal_provider unchanged)
4. Update stream_completion call (method name unchanged)
5. Optional: Pass db session for usage tracking

**Complexity:** LOW - Single route function, streaming pattern proven in Phase 227

**Testing:** Mobile agent chat API tests, WebSocket streaming tests

---

## Testing Strategy

### Unit Tests

**What to test:**
- LLMService initialization with workspace_id and db session
- Method calls (generate, generate_structured, stream_completion)
- Database session injection for usage tracking

**Example:**
```python
from unittest.mock import patch, AsyncMock

@patch('api.competitor_analysis_routes.LLMService')
async def test_analyze_with_llm(mock_llm_class):
    mock_llm = AsyncMock()
    mock_llm_class.return_value = mock_llm
    mock_llm.generate_structured.return_value = CompetitorInsight(
        competitor="Test Corp",
        strengths=["Strong brand"],
        weaknesses=["High cost"]
    )

    result = await analyze_with_llm(
        competitor_data={"name": "Test Corp"},
        focus_areas=["products"],
        db=test_db
    )

    assert mock_llm.generate_structured.called
    assert result.competitor == "Test Corp"
```

### Integration Tests

**What to test:**
- End-to-end API endpoint execution with LLMService
- Structured output generation with real LLM providers
- WebSocket streaming with real providers (mobile_agent_routes)
- Usage tracking in database

**Reference:** Phase 225.1 verification tests (31/36 agent execution passed, 0 BYOKHandler errors)

### Test Mock Updates

**Critical:** Update test mocks to patch LLMService, not BYOKHandler

**Pattern:**
```python
# Patch the import path used by the code under test
@patch('api.competitor_analysis_routes.LLMService')
# NOT: @patch('api.competitor_analysis_routes.BYOKHandler')
```

---

## Open Questions

### Question 1: Usage Tracking for API Routes

**What we know:** All 3 API routes currently use module-level BYOKHandler singletons without database sessions.

**What's unclear:** Should API routes track LLM usage in the database?

**Recommendation:** Pass db session to LLMService for usage tracking:
```python
llm = LLMService(workspace_id="default", db=db)
```

**Reason:** Usage tracking provides cost monitoring and quota enforcement for API endpoints, same as agent services.

### Question 2: Test Coverage for API Routes

**What we know:** Phase 225.1 Plans 05-07 updated agent service tests.

**What's unclear:** Do tests exist for these 3 API routes?

**Recommendation:** Search for test files:
- `tests/api/test_competitor_analysis_routes.py`
- `tests/api/test_learning_plan_routes.py`
- `tests/api/test_mobile_agent_routes.py`

**Reason:** Need to update test mocks if tests exist.

### Question 3: Workspace ID for API Routes

**What we know:** Current module-level singletons use default workspace_id.

**What's unclear:** Should API routes use user-specific workspace IDs?

**Recommendation:** Use "default" workspace_id for now, consistent with current behavior:
```python
llm = LLMService(workspace_id="default", db=db)
```

**Reason:** Workspace-based isolation is a future enhancement, not required for Phase 228.

### Question 4: Error Handling and Fallbacks

**What we know:** All 3 routes have fallback logic when LLM fails.

**What's unclear:** Does fallback logic need updating?

**Recommendation:** Verify fallback logic works with LLMService errors.

**Reason:** LLMService may raise different exceptions than BYOKHandler.

---

## Sources

### Primary Sources (HIGH Confidence)

- **Phase 225.1 Summary Documents** (8 plans, all complete) - Migration pattern, method changes, test updates
- **Phase 227 Summary Documents** (1 plan complete) - atom_agent_endpoints.py WebSocket streaming migration
- **LLMService API Documentation** (`backend/core/llm_service.py`) - Complete API reference
- **GenericAgent Migration** (`backend/core/generic_agent.py`) - Reference implementation
- **Phase 225.1 Verification Report** - 5/5 truths verified, gap closure confirmed
- **Phase 227 Plan 01 Summary** - WebSocket streaming migration pattern

### Secondary Sources (MEDIUM Confidence)

- **BYOKHandler Documentation** (`backend/core/llm/byok_handler.py`) - BPC routing, provider selection
- **API Route Source Code** - Current BYOKHandler usage patterns
  - `backend/api/competitor_analysis_routes.py`
  - `backend/api/learning_plan_routes.py`
  - `backend/api/mobile_agent_routes.py`

### Tertiary Sources (LOW Confidence)

- **Test files** - May need verification of test coverage for API routes

---

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** - All components exist, Phase 225.1 and 227 established patterns
- Architecture: **HIGH** - Clear pattern from Phase 225.1 (8 plans) and Phase 227 (1 plan), all completed successfully
- Pitfalls: **HIGH** - Documented from Phase 225.1 experience (Plans 05-07 test mock issues)
- Migration scope: **HIGH** - 3 files confirmed via grep, all patterns identified

**Research date:** March 22, 2026
**Valid until:** April 21, 2026 (30 days)
**Next review:** April 22, 2026

---

## Next Steps for Planner

### Task 1: Migrate competitor_analysis_routes.py

**Goal:** Update competitor analysis endpoint to use LLMService.

**Actions:**
1. Replace BYOKHandler import with LLMService import
2. Remove module-level BYOKHandler singleton (line 27)
3. Add `db: Session` parameter to `analyze_with_llm()` function
4. Replace BYOKHandler instantiation with LLMService
5. Update method call: `generate_structured_response()` → `generate_structured()`
6. Update route handler to pass db session
7. Run competitor analysis tests

### Task 2: Migrate learning_plan_routes.py

**Goal:** Update learning plan endpoint to use LLMService.

**Actions:**
1. Replace BYOKHandler import with LLMService import
2. Remove module-level BYOKHandler singleton (line 27)
3. Add `db: Session` parameter to `generate_learning_modules()` function
4. Replace BYOKHandler instantiation with LLMService
5. Update method call: `generate_structured_response()` → `generate_structured()`
6. Update route handler to pass db session
7. Run learning plan tests

### Task 3: Migrate mobile_agent_routes.py

**Goal:** Update mobile agent chat endpoint to use LLMService.

**Actions:**
1. Replace BYOKHandler import with LLMService import
2. Replace BYOKHandler instantiation with LLMService (line 322)
3. Update method calls (analyze_query_complexity, get_optimal_provider unchanged)
4. Update stream_completion call (method name unchanged)
5. Optional: Pass db session for usage tracking
6. Run mobile agent chat tests
7. Run WebSocket streaming tests

### Task 4: Update Test Mocks (if tests exist)

**Goal:** Ensure tests patch LLMService, not BYOKHandler.

**Actions:**
1. Search for test files for the 3 API routes
2. Update @patch decorators from BYOKHandler to LLMService
3. Update mock return values (new method names)
4. Run test suite to verify no BYOKHandler errors

### Task 5: Verification

**Goal:** Confirm migration complete, no BYOKHandler usage in API routes.

**Actions:**
1. Grep for remaining BYOKHandler usage in `backend/api/` directory
2. Run API route test suite
3. Verify no BYOKHandler AttributeError in tests
4. Update VERIFICATION.md with migration status

---

*Phase: 228-api-routes-tools-standardization*
*Research completed: March 22, 2026*
*Researcher: Claude (Sonnet 4.5)*
*Status: Ready for planning*
