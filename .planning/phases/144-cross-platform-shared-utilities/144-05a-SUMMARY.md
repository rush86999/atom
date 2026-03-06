---
phase: 144-cross-platform-shared-utilities
plan: 05a
title: "Shared Test Data Fixtures"
status: COMPLETE
date: 2026-03-06
duration: 3 minutes
tasks: 3
commits: 2
deviations: 0
---

# Phase 144 Plan 05a: Shared Test Data Fixtures - Summary

## Objective

Create shared test data fixtures with common mock data (agents, workflows, users) usable across frontend, mobile, and desktop platforms, reducing duplication and ensuring consistent test data.

## One-Liner

Created centralized test-data.ts module with mockAgents (4 agents across all maturity levels), mockWorkflows (3 workflows in different states), mockUser, and testDataFixture, plus JSON fixtures for Rust desktop tests.

## Tasks Completed

| Task | Name | Commit | Files Created/Modified |
|------|------|--------|----------------------|
| 1 | Create test-data.ts module | a34fb32a5 | frontend-nextjs/shared/test-utils/test-data.ts (133 lines) |
| 2 | Create JSON fixtures | 3c0f7320e | frontend-nextjs/shared/test-utils/fixtures/mock_data.json (18 lines) |
| 3 | Update index.ts export | - | Already updated in previous plan |

## Files Created

### frontend-nextjs/shared/test-utils/test-data.ts (133 lines)
- **Purpose**: Centralized test data fixtures for cross-platform testing
- **Exports**:
  - `mockAgents`: Array of 4 mock agents (AUTONOMOUS, SUPERVISED, INTERN, STUDENT)
  - `mockWorkflows`: Array of 3 mock workflows (pending, running, completed)
  - `mockUser`: Single mock user object
  - `testDataFixture`: Aggregated bundle with all fixtures
- **Features**:
  - Type-safe imports from types.ts (MockAgent, MockWorkflow, MockUser, TestDataFixture)
  - JSDoc documentation with usage examples for all exports
  - Platform-agnostic design (works with web, mobile, desktop testing)

### frontend-nextjs/shared/test-utils/fixtures/mock_data.json (18 lines)
- **Purpose**: JSON fixtures for Rust desktop tests
- **Structure**: Matches TypeScript test-data.ts fixtures
- **Usage**: Rust tests can consume via symlink: `tests/shared_fixtures/mock_data.json`
- **Contents**: 4 agents, 3 workflows, 1 user (same as TypeScript version)

## Files Modified

### frontend-nextjs/shared/test-utils/index.ts
- **Change**: Added test-data exports (lines 90-99)
- **Status**: Already updated in previous plan (144-04)
- **Exports**:
  - Named exports: mockAgents, mockWorkflows, mockUser, testDataFixture
  - Wildcard export: export * from './test-data'

## Verification

✅ test-data.ts exports mockAgents, mockWorkflows, mockUser, testDataFixture  
✅ fixtures/mock_data.json contains valid JSON matching TypeScript fixtures  
✅ index.ts properly exports all test-data fixtures  
✅ All fixtures match types defined in types.ts (MockAgent, MockWorkflow, MockUser)  
✅ JSDoc documentation with usage examples for all exports  
✅ fixtures/ directory exists for Rust symlink target  

## Deviations from Plan

**None** - Plan executed exactly as written.

## Success Criteria

1. ✅ test-data.ts exports mockAgents, mockWorkflows, mockUser, testDataFixture
2. ✅ fixtures/mock_data.json contains valid JSON matching TypeScript fixtures
3. ✅ index.ts properly exports all test-data fixtures
4. ✅ All fixtures match types defined in types.ts
5. ✅ fixtures/ directory exists for Rust symlink target

## Handoff to Plan 05b

Plan 05b (Configure mobile and desktop platforms to use shared test utilities) can now proceed with:
- Mobile TypeScript path mapping for @atom/test-utils
- Mobile Jest moduleNameMapper for @atom/test-utils
- Symlinks: mobile/src/shared and src-tauri/tests/shared_fixtures
- Cross-platform validation test (will import test-data fixtures)

## Test Data Structure

### MockAgent interface
```typescript
{
  id: string;
  name: string;
  maturity: 'STUDENT' | 'INTERN' | 'SUPERVISED' | 'AUTONOMOUS';
  confidence?: number;
}
```

### MockWorkflow interface
```typescript
{
  id: string;
  name: string;
  steps: number;
  status?: 'pending' | 'running' | 'completed' | 'failed';
}
```

### MockUser interface
```typescript
{
  id: string;
  name: string;
  email: string;
}
```

## Commits

1. `a34fb32a5` - feat(144-05a): create test-data.ts module with common test fixtures
2. `3c0f7320e` - feat(144-05a): create JSON fixtures for Rust desktop tests

## Next Steps

Execute Plan 144-05b: Configure mobile and desktop platforms to use shared test utilities
- Task 1: Configure mobile TypeScript path mapping for @atom/test-utils
- Task 2: Configure mobile Jest moduleNameMapper for @atom/test-utils
- Task 3: Create symlinks for mobile and desktop platforms
- Task 4: Create cross-platform validation test (imports from test-data)
