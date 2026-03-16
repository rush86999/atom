# Coverage Gaps Analysis - Phase 197 Plan 07

**Date:** 2026-03-16
**Current Overall Coverage:** 14.3%
**Target Coverage:** 78-79%
**Gap:** 63.7% improvement needed

## Executive Summary

The codebase currently has 14.3% test coverage, significantly below the 78-79% target. This analysis identifies 50+ modules requiring edge case and error path coverage, prioritized by impact and complexity.

## Methodology

Coverage analysis conducted using:
```bash
python3.11 -m pytest backend/tests/ --cov=backend --cov-report=term-missing --cov-report=html
```

## Coverage by Module Type

### 1. Utility Modules (Target: 5-10% improvement each)

**Low Coverage (<20%):**
- `core/utils/` - Missing comprehensive utility test coverage
- `core/structured_logger.py` - 0% coverage (92 lines)
- `core/validation_service.py` - 0% coverage (264 lines)
- `core/secret_manager.py` - 0% coverage (59 lines)
- `core/security_dependencies.py` - 0% coverage (25 lines)

**Priority Edge Cases:**
- String helpers: Empty strings, unicode, special characters
- Date/time utilities: Timezone handling, DST transitions, invalid dates
- File helpers: Path traversal, permission errors, missing files
- Config validation: Missing env vars, invalid values, type mismatches

### 2. API Modules (Target: 10-15% improvement each)

**Low Coverage (<20%):**
- `api/admin_routes.py` - Critical governance endpoints
- `api/canvas_routes.py` - Canvas presentation system
- `api/browser_routes.py` - Browser automation
- `api/device_capabilities.py` - Device control
- `api/episode_routes.py` - Episodic memory endpoints
- `api/feedback_enhanced.py` - Enhanced feedback system
- `api/permission_checks.py` - Authorization checks
- `api/social_routes.py` - Social media integration

**Priority Edge Cases:**
- Authentication: Missing tokens, invalid credentials, expired tokens
- Authorization: Insufficient permissions, role mismatches
- Request validation: Malformed JSON, missing fields, type errors
- Error responses: 500 errors, rate limiting, timeout handling

### 3. Core Service Modules (Target: 10-20% improvement each)

**Low Coverage (<20%):**
- `core/agent_governance_service.py` - Agent lifecycle management
- `core/governance_cache.py` - Performance cache
- `core/trigger_interceptor.py` - Maturity-based routing
- `core/student_training_service.py` - Training system
- `core/supervision_service.py` - Real-time supervision
- `core/episode_segmentation_service.py` - Episode creation
- `core/episode_retrieval_service.py` - Episode retrieval
- `core/agent_graduation_service.py` - Graduation logic
- `core/llm/byok_handler.py` - LLM routing
- `core/llm/cognitive_tier_system.py` - Cognitive classification

**Priority Edge Cases:**
- Business logic: Boundary conditions, state transitions
- Database operations: Connection errors, constraint violations, deadlocks
- Cache interactions: Cache misses, TTL expiration, eviction
- External services: Timeouts, 5xx errors, retry logic
- Error handling: Exception propagation, user-friendly messages

### 4. Integration Modules (Target: 10-15% improvement each)

**Low Coverage (<20%):**
- `integrations/` - All third-party integrations
- `integrations/slack_integration.py` - Slack API
- `integrations/teams_integration.py` - Teams API
- `integrations/outlook_integration.py` - Outlook/Office365
- `integrations/google_integration.py` - Google services
- `integrations/whatsapp_fastapi_routes.py` - WhatsApp
- `integrations/trello_integration.py` - Trello
- `core/storage.py` - S3/R2 storage adapter

**Priority Edge Cases:**
- Connection handling: Connection failures, timeout, retry logic
- Request/response mapping: Data transformation errors
- Error translation: External errors → internal errors
- Rate limiting: API limits, backoff strategies
- Authentication: Invalid credentials, token refresh

## High-Impact Modules (>500 lines, <20% coverage)

1. `core/workflow_engine.py` - 1164 lines, 0% coverage
2. `core/workflow_analytics_engine.py` - 601 lines, 0% coverage
3. `core/workflow_debugger.py` - 527 lines, 0% coverage
4. `core/unified_message_processor.py` - 272 lines, 0% coverage
5. `core/skill_registry_service.py` - 370 lines, 0% coverage
6. `api/admin_routes.py` - 1000+ lines, low coverage
7. `api/episode_routes.py` - 500+ lines, low coverage
8. `core/agent_graduation_service.py` - 400+ lines, 0% coverage

## Test Infrastructure Issues

**Blocking Issues:**
1. Import errors in 10+ test files (circular imports, missing models)
2. Factory Boy + SQLAlchemy 2.0 incompatibility
3. Duplicate test file names causing collection errors
4. Async test configuration issues
5. Missing test fixtures for complex scenarios

**Priority Fixes:**
1. Fix import errors (User model, Formula class conflicts)
2. Resolve duplicate test file names
3. Configure pytest-asyncio properly
4. Create missing model fixtures
5. Fix Factory Boy Meta.model issues

## Execution Strategy

### Phase 1: Fix Test Infrastructure (Tasks 1-2)
- Resolve import errors
- Fix async test configuration
- Create missing fixtures

### Phase 2: Target Utility Modules (Task 3)
- Test string/date/file helpers
- Config validation
- Error scenarios

### Phase 3: Target API Modules (Task 4)
- All endpoint types (GET/POST/PUT/DELETE)
- Auth/authz scenarios
- Request validation

### Phase 4: Target Core Services (Task 5)
- Business logic
- Database/cache operations
- Error handling

### Phase 5: Target Integration Modules (Task 6)
- External API adapters
- Connection handling
- Error translation

### Phase 6: Edge Case Tests (Task 7)
- Boundary conditions
- Invalid inputs
- Concurrency issues

### Phase 7: Verify Coverage (Task 8)
- Overall coverage 78-79%
- All high-impact modules >70%
- Document results

## Success Metrics

- [ ] Overall coverage: 14.3% → 78-79%
- [ ] Utility modules: 5-10% improvement each
- [ ] API modules: 10-15% improvement each
- [ ] Core services: 10-20% improvement each
- [ ] Integration modules: 10-15% improvement each
- [ ] Edge cases tested across all modules
- [ ] Error handling comprehensive

## Next Steps

1. Create comprehensive edge case test suite
2. Prioritize high-impact modules first
3. Fix test infrastructure blockers
4. Incremental coverage improvements per module type
5. Continuous verification against 78-79% target
