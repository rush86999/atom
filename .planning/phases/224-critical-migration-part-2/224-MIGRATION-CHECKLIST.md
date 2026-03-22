# LLMService Migration Checklist

**Based on Phase 223-224 patterns**

This checklist provides step-by-step guidance for migrating files with direct OpenAI/Anthropic client usage to the unified LLMService API. Use this checklist for Phases 225-232 migrations.

---

## Pre-Migration Checklist

Before starting any migration, verify these prerequisites:

- [ ] **Verify target file uses direct OpenAI/Anthropic clients**
  - Run: `grep -n "from openai import" backend/path/to/file.py`
  - Run: `grep -n "from anthropic import" backend/path/to/file.py`
  - Confirm: Direct client usage found (not already using LLMService)

- [ ] **Check existing tests for target file**
  - Run: `find backend/tests -name "*test*.py" -exec grep -l "target_file_name" {} \;`
  - Confirm: Test file exists or create one if missing

- [ ] **Verify LLMService has required methods**
  - `generate_completion` - For chat completions (GPT-4, Claude)
  - `generate_embedding` - For single text embeddings
  - `generate_embeddings_batch` - For batch embeddings
  - Confirm: LLMService methods available in `backend/core/llm_service.py`

- [ ] **Run baseline tests**
  - Run: `python3 -m pytest backend/tests/path/to/test_file.py -v`
  - Confirm: All tests pass before migration (establish baseline)
  - Note: Document any pre-existing test failures

---

## Migration Steps

### Step 1: Import LLMService

- [ ] **Add LLMService import at top of file**
  ```python
  from core.llm_service import LLMService
  ```
  - Place after existing imports
  - Ensure import is at module level (not inside functions)

### Step 2: Initialize LLMService in __init__

- [ ] **Add LLMService instance to __init__ method**
  ```python
  # Initialize LLMService for unified LLM interactions
  self.llm_service = LLMService(workspace_id="default")
  ```
  - Use `workspace_id="default"` for default workspace operations
  - Use `workspace_id=workspace_id` parameter if file supports multi-tenancy
  - Place initialization after other instance variables

### Step 3: Replace direct client calls

- [ ] **Replace OpenAI chat.completions.create calls**
  - **Before:**
    ```python
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[...]
    )
    content = response.choices[0].message.content
    ```
  - **After:**
    ```python
    response = await self.llm_service.generate_completion(
        messages=[...],
        model="gpt-4o"
    )
    content = response.get("content", "")
    ```

- [ ] **Replace Anthropic messages.create calls**
  - **Before:**
    ```python
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        messages=[...]
    )
    content = response.content[0].text
    ```
  - **After:**
    ```python
    response = await self.llm_service.generate_completion(
        messages=[...],
        model="claude-3-5-sonnet"
    )
    content = response.get("content", "")
    ```

- [ ] **Replace OpenAI embeddings.create calls**
  - **Before:**
    ```python
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    embedding = response.data[0].embedding
    ```
  - **After:**
    ```python
    embedding = await self.llm_service.generate_embedding(
        text=text,
        model="text-embedding-3-small"
    )
    ```

### Step 4: Update response extraction

- [ ] **Extract content using LLMService response format**
  - Use: `response.get("content", "")` for chat completions
  - Use: `embedding` (direct return) for embeddings (List[float])
  - Add empty string check: `if not content: return None`

- [ ] **Remove response_format parameter if present**
  - LLMService doesn't support `response_format={"type": "json_object"}` yet
  - Request JSON mode via system prompt instead
  - Example: "You are a knowledge graph extractor. Output valid JSON."

### Step 5: Make methods async if calling LLMService async methods

- [ ] **Add async keyword to method signatures**
  - Change: `def method_name(self, ...)` to `async def method_name(self, ...)`
  - Add: `await` keyword before LLMService calls
  - Propagate async to all caller methods

- [ ] **Handle sync-to-async bridge if needed**
  ```python
  # For sync methods calling async LLMService
  import asyncio
  result = asyncio.run(self.llm_service.generate_completion(...))
  ```
  - Use only if refactoring to async is not feasible
  - Prefer making methods async instead

### Step 6: Remove direct client imports

- [ ] **Remove OpenAI imports**
  - Delete: `from openai import OpenAI, AsyncOpenAI`
  - Delete: `import openai`

- [ ] **Remove Anthropic imports**
  - Delete: `from anthropic import Anthropic, AsyncAnthropic`
  - Delete: `import anthropic`

- [ ] **Verify no direct client usage remains**
  - Run: `grep -n "client\." backend/path/to/file.py`
  - Confirm: All client usage replaced with LLMService

### Step 7: Update comments and docstrings

- [ ] **Update docstrings to reflect LLMService usage**
  - Example: "Generate embeddings using LLMService for unified OpenAI API interaction"
  - Mention BYOK support, cost tracking, observability benefits

- [ ] **Add comments explaining LLMService delegation**
  - Example: "# LLMService handles provider selection, API key resolution, and client creation"
  - Example: "# Cost tracking via LLMService unified telemetry"

---

## Test Migration Steps

### Step 1: Update @patch decorators

- [ ] **Replace OpenAI/Anthropic patches with LLMService patches**
  - **Before:** `@patch('path.to.file.AsyncOpenAI')`
  - **After:** `@patch('path.to.file.LLMService')` or `@patch.object(instance, 'llm_service')`

### Step 2: Use AsyncMock for async LLMService method calls

- [ ] **Mock generate_completion with AsyncMock**
  ```python
  from unittest.mock import AsyncMock
  mock_service = Mock()
  mock_service.generate_completion = AsyncMock(
      return_value={
          "content": "Generated text",
          "model": "gpt-4o",
          "usage": {"total_tokens": 100}
      }
  )
  ```

- [ ] **Mock generate_embedding with AsyncMock**
  ```python
  mock_service.generate_embedding = AsyncMock(
      return_value=[0.1] * 1536  # 1536 dimensions for text-embedding-3-small
  )
  ```

### Step 3: Add @pytest.mark.asyncio decorators

- [ ] **Add decorator to async test methods**
  ```python
  @pytest.mark.asyncio
  async def test_something(self):
      result = await instance.llm_service.generate_completion(...)
  ```

### Step 4: Make test methods async if they call async production methods

- [ ] **Convert test methods to async**
  - Change: `def test_method(self):` to `async def test_method(self):`
  - Add: `await` before async method calls
  - Add: `@pytest.mark.asyncio` decorator

### Step 5: Verify mock returns match LLMService response format

- [ ] **Chat completion response format**
  ```python
  {
      "content": "Generated text",
      "model": "gpt-4o",
      "usage": {"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50}
  }
  ```

- [ ] **Embedding response format**
  ```python
  [0.1, 0.2, 0.3, ...]  # List[float] with 1536 or 3072 dimensions
  ```

### Step 6: Run full test suite

- [ ] **Run file-specific tests**
  - Run: `python3 -m pytest backend/tests/path/to/test_file.py -v`
  - Verify: All tests pass

- [ ] **Run full test suite to catch cross-file issues**
  - Run: `python3 -m pytest backend/tests/ -v --tb=short`
  - Verify: No new test failures from migration
  - Note: 5-10 min runtime is acceptable per CONTEXT.md decision

---

## Post-Migration Verification

### Step 1: Verify no direct client imports remain

- [ ] **Check for OpenAI imports**
  - Run: `grep -n "from openai import" backend/path/to/file.py`
  - Confirm: No direct OpenAI imports (only in comments)

- [ ] **Check for Anthropic imports**
  - Run: `grep -n "from anthropic import" backend/path/to/file.py`
  - Confirm: No direct Anthropic imports (only in comments)

### Step 2: Verify all LLM calls go through llm_service

- [ ] **Check for LLMService usage**
  - Run: `grep -n "llm_service\." backend/path/to/file.py`
  - Confirm: All LLM interactions use `self.llm_service.generate_completion` or `generate_embedding`

- [ ] **Check for no direct client calls**
  - Run: `grep -n "client\." backend/path/to/file.py`
  - Confirm: No direct client usage (client.chat.completions.create, etc.)

### Step 3: Verify all existing tests pass

- [ ] **Run test suite**
  - Run: `python3 -m pytest backend/tests/path/to/test_file.py -v`
  - Confirm: All tests pass with LLMService integration

### Step 4: Verify cost tracking enabled

- [ ] **Check LLMService initialization**
  - Confirm: `self.llm_service = LLMService(workspace_id=...)` exists
  - Confirm: LLMService handles cost tracking internally via `llm_usage_tracker`

- [ ] **Verify cost telemetry logged**
  - Check logs for: "LLM call: model=..., tokens=..., estimated_cost=..."
  - Confirm: Cost tracking is active for migrated file

### Step 5: Verify no regression in functionality

- [ ] **Test migrated functionality manually**
  - Run integration tests or manual verification
  - Confirm: Output matches pre-migration behavior (same dimensions, values, quality)

- [ ] **Check for error handling improvements**
  - Confirm: LLMService error handling is as good as or better than before
  - Confirm: No unhandled exceptions from migration

---

## Cross-Cutting Verification (Phase 224+)

For multi-file migrations (like Phase 224), verify these cross-cutting concerns:

### Step 1: Verify embeddings work with all consumers

- [ ] **Check embedding dimensions consistency**
  - Verify: All consumers use same embedding model (text-embedding-3-small = 1536 dimensions)
  - Verify: No dimension mismatches between LanceDB, episodic memory, semantic search

- [ ] **Test embedding generation across consumers**
  - Test: `backend/core/lancedb_handler.py` uses `llm_service.generate_embedding`
  - Test: `backend/core/embedding_service.py` uses `llm_service.generate_embedding`
  - Confirm: Both produce consistent embeddings (same dimensions, values for same input)

### Step 2: Verify cost tracking aggregates correctly

- [ ] **Check llm_usage_tracker captures all calls**
  - Verify: All migrated services call LLMService methods
  - Verify: No direct client calls bypass tracking
  - Confirm: Usage tracked from all consumers (LanceDB, social post generator, security analyzer)

- [ ] **Test cost aggregation**
  - Run: Queries on llm_usage_tracker table
  - Confirm: Usage records from all migrated files
  - Confirm: Cost totals include all LLM operations

### Step 3: Run full test suite to catch cross-file issues

- [ ] **Run comprehensive test suite**
  - Run: `python3 -m pytest backend/tests/ -v --tb=short`
  - Verify: No cross-file side effects from migration
  - Note: 5-10 min runtime acceptable for confidence

- [ ] **Check integration test coverage**
  - Verify: Integration tests exist for migrated files
  - Confirm: Tests verify cross-service compatibility

### Step 4: Check for unintended side effects

- [ ] **Verify no broken imports**
  - Run: `python3 -c "import backend.path.to.file"`
  - Confirm: No ImportError or circular import issues

- [ ] **Verify no performance degradation**
  - Test: Migration doesn't add significant overhead
  - Confirm: LLMService performance is acceptable (<100ms for completions, <50ms for embeddings)

- [ ] **Check for breaking API changes**
  - Verify: Public API unchanged (unless breaking change is intentional)
  - Confirm: Callers don't need updates unless planned

---

## Common Pitfalls and Solutions

### Pitfall 1: Forgetting to make methods async

**Problem:** Calling async `llm_service.generate_completion` from sync method

**Solution:**
- Add `async` keyword to method signature
- Add `await` before LLMService calls
- Propagate async to all caller methods

### Pitfall 2: Wrong response format extraction

**Problem:** Using `response.choices[0].message.content` (old OpenAI format)

**Solution:**
- Use `response.get("content", "")` (LLMService dict format)
- Add empty content check: `if not content: return None`

### Pitfall 3: Mocking wrong module path

**Problem:** `@patch('core.llm_service.LLMService')` doesn't mock imported instance

**Solution:**
- Use `@patch('path.to.migrated_file.LLMService')` where LLMService is imported
- Or use `@patch.object(instance, 'llm_service')` to patch instance attribute

### Pitfall 4: Forgetting to remove response_format parameter

**Problem:** `response_format={"type": "json_object"}` causes error

**Solution:**
- Remove `response_format` parameter from LLMService calls
- Request JSON mode via system prompt instead

### Pitfall 5: Not running full test suite after migration

**Problem:** Cross-file issues not caught

**Solution:**
- Always run full test suite after each plan (5-10 min acceptable)
- Integration tests catch issues that unit tests miss

---

## Notes

### Wave Grouping

- Group independent migrations in Wave 1 (no dependencies between files)
- Group dependent migrations in Wave 2 (files that depend on Wave 1 migrations)
- Verify Wave 1 before starting Wave 2

### Integration Tests

- Add integration tests for each migrated file
- Tests should verify LLMService + migrated file compatibility
- Example: `TestLanceDBLLMServiceIntegration` class in `test_lancedb_handler.py`

### Full Test Suite

- Run after each plan (224-01, 224-02, 224-03, etc.)
- 5-10 min runtime is acceptable for confidence
- Catches cross-file issues that unit tests miss

### BYOK Support

- LLMService handles BYOK API key resolution internally
- No need to manually resolve API keys in migrated files
- LLMService uses BYOKHandler.clients for multi-tenant key management

### Cost Tracking

- LLMService automatically tracks usage via `llm_usage_tracker`
- No manual cost tracking needed in migrated files
- Check logs for cost telemetry: "LLM call: model=..., tokens=..., estimated_cost=..."

---

## Phase 223-224 Examples

For detailed examples of completed migrations, see:

- **Phase 223-01:** LLMService embedding generation (`backend/core/llm_service.py`)
- **Phase 223-02:** EmbeddingService migration (`backend/core/embedding_service.py`)
- **Phase 223-03:** GraphRAG engine migration (`backend/core/graphrag_engine.py`)
- **Phase 224-01:** LLMAnalyzer migration (`backend/atom_security/analyzers/llm.py`)
- **Phase 224-02:** LanceDBHandler migration (`backend/core/lancedb_handler.py`)
- **Phase 224-03:** SocialPostGenerator migration (`backend/core/social_post_generator.py`)

These examples show:
- Import patterns for LLMService
- Initialization patterns (workspace_id parameter)
- Response format extraction (`.get("content")`)
- Test migration patterns (AsyncMock, @pytest.mark.asyncio)
- Error handling patterns (specific exception types)

---

**Last Updated:** Phase 224 (2026-03-22)

**Next Phase:** Phase 225 (Critical Migration Part 3)
