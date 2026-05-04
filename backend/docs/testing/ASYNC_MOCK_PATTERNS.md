# AsyncMock Pattern Standards

## Background

Phase 297-298 established standards for mock usage in async test scenarios. This document codifies those patterns for consistency across all test files.

## Core Principles

1. **Match the implementation**: Mock type should match the actual method signature
2. **AsyncMock for async**: Use `AsyncMock` only for methods declared with `async def`
3. **Mock for sync**: Use regular `Mock` for synchronous methods and functions
4. **Never mix**: Using AsyncMock for sync methods causes "coroutine object has no attribute" errors

## Decision Tree

```
Is the method async?
├─ Yes → Use AsyncMock
│         └─ Add @pytest.mark.asyncio to test function
└─ No → Use Mock or MagicMock
```

## Examples

### Correct: Sync method with Mock

```python
# Production: def get_graduation_readiness(agent_id, tenant_id, target_level):
episode_service.get_graduation_readiness = Mock(return_value=mock_readiness)
```

### Correct: Async method with AsyncMock

```python
# Production: async def execute_in_sandbox(agent_id, task):
executor.execute_in_sandbox = AsyncMock(return_value=mock_result)
```

### Wrong: AsyncMock for sync method

```python
# DON'T DO THIS - causes "coroutine object has no attribute" error
episode_service.get_graduation_readiness = AsyncMock(return_value=mock_readiness)
```

## Testing Async Functions

When testing async functions:

1. Mark test with `@pytest.mark.asyncio`
2. Use `await` when calling async methods
3. Use AsyncMock for mocked async dependencies

```python
@pytest.mark.asyncio
async def test_async_function():
    mock_async_dep = AsyncMock(return_value="result")
    result = await my_async_function(mock_async_dep)
```

## Common Patterns

### Database Operations (Sync)

```python
db = MagicMock()
db.add = Mock()
db.commit = Mock()
db.query = Mock()
db.refresh = Mock()
```

### Service Methods (Check Signature)

```python
# Check if method is async:
# - grep "async def method_name" core/service.py

# If async:
service.async_method = AsyncMock(return_value=result)

# If sync:
service.sync_method = Mock(return_value=result)
```

### Governance Methods (Mixed)

```python
# can_perform_action is sync (use Mock)
governance.can_perform_action = Mock(return_value={"allowed": True})

# check_governance is also sync (use Mock, not AsyncMock)
governance.check_governance = Mock(return_value={"allowed": False})
```

## Reference

- **Established in**: Phase 297-298
- **Applied in**: Phase 309 test files
- **Related docs**:
  - Phase 297-298 summaries
  - 303-QUALITY-STANDARDS.md
  - test_agent_graduation_service.py (examples)
  - test_agent_context_resolver.py (examples)

## Quick Checklist

When writing or reviewing tests:

- [ ] Is the mocked method actually async? (check with `grep "async def"`)
- [ ] If yes, using AsyncMock?
- [ ] If no, using Mock or MagicMock?
- [ ] Test function marked with `@pytest.mark.asyncio` if testing async code?
- [ ] Using `await` when calling async methods?

## Troubleshooting

### Error: "coroutine object has no attribute 'X'"

**Cause**: Using AsyncMock for a synchronous method

**Fix**: Change `AsyncMock` to `Mock`

```python
# Wrong
service.sync_method = AsyncMock(return_value=result)

# Correct
service.sync_method = Mock(return_value=result)
```

### Error: "object MagicMock can't be used in 'await' expression"

**Cause**: Using Mock for an async method

**Fix**: Change `Mock` to `AsyncMock`

```python
# Wrong
service.async_method = Mock(return_value=result)
await service.async_method()  # Error!

# Correct
service.async_method = AsyncMock(return_value=result)
await service.async_method()  # Works!
```

## Files Following This Pattern

As of Phase 309-24, these test files follow the AsyncMock pattern standards:

- ✅ `tests/test_agent_graduation_service.py` (28 tests)
- ✅ `tests/test_agent_context_resolver.py` (22 tests)
- ✅ `tests/test_agent_integration_gateway.py` (22 tests)
- ✅ `tests/test_ai_accounting_engine.py` (36 tests)

## Future Guidelines

When adding new tests:

1. **Check the method signature first** - Is it `async def` or just `def`?
2. **Use the appropriate mock type** - Mock for sync, AsyncMock for async
3. **Document non-obvious choices** - Add comments explaining why a specific mock type was used
4. **Run tests** - Verify mock type matches the actual implementation

---

*Document created: 2026-05-04*
*Phase: 309-services-coverage-wave-2*
*Plan: 309-24*
