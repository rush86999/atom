---
phase: 04-platform-coverage
plan: 03
subsystem: testing
tags: jest-expo, react-native, auth, device-context, permissions

# Dependency graph
requires:
  - phase: 04-platform-coverage
    provides: Jest test infrastructure, expo mocks, Platform.OS utilities
provides:
  - AuthContext test infrastructure (blocked by expo/virtual/env issue)
  - expo/virtual/env stub module
  - babel.config.js with preserveEnvVars option
affects: [04-04, 04-05, 04-06, 04-07, 04-08]

# Tech tracking
tech-stack:
  added: [expo/virtual/env stub, babel-preset-expo preserveEnvVars]
  patterns: [Expo SDK 50 environment variable transformation, Jest module mocking]

key-files:
  created: [mobile/src/__tests__/contexts/AuthContext.test.tsx, mobile/src/__tests__/mocks/exploEnv.ts, mobile/node_modules/expo/virtual/env.js, mobile/node_modules/expo/virtual/package.json]
  modified: [mobile/babel.config.js, mobile/jest.setup.js, mobile/package.json]

key-decisions:
  - "BLOCKER: Expo SDK 50 babel-preset-expo transforms process.env.EXPO_PUBLIC_* to expo/virtual/env which doesn't exist in Jest environment"

patterns-established:
  - "Pattern: babel-preset-expo inline-env-vars plugin adds expo/virtual/env import for EXPO_PUBLIC_ vars in non-production"
  - "Pattern: Jest module resolution requires actual file or virtual mock for expo/virtual/env"

# Metrics
duration: 45min
completed: 2026-02-11
---

# Phase 4 Plan 3: AuthContext and DeviceContext Tests Summary

**Expo SDK 50 + Jest incompatibility blocker: babel-preset-expo transforms process.env.EXPO_PUBLIC_* variables to use expo/virtual/env module which doesn't exist in Jest environment**

## Performance

- **Duration:** 45 minutes (debugging babel transformation issue)
- **Started:** 2026-02-11T11:01:13Z
- **Completed:** 2026-02-11T11:46:00Z
- **Tasks:** 1 of 3 completed (test infrastructure created, tests not runnable)
- **Files modified:** 7 files

## Accomplishments

- Created comprehensive AuthContext.test.tsx (1100+ lines) with test structure for login, logout, biometric auth, token refresh, state persistence, device registration
- Created expo/virtual/env stub module in node_modules
- Updated babel.config.js with `preserveEnvVars: true` option to disable inline env transformation
- Updated jest.setup.js with expo/virtual/env mock
- Created test helper utilities directory structure

## Task Commits

1. **Task 1: Create AuthContext tests** - `60cc8731` (test - BLOCKER)

**Plan metadata:** Pending (tasks 2-3 not completed)

## Files Created/Modified

- `mobile/src/__tests__/contexts/AuthContext.test.tsx` - AuthContext test structure (1100+ lines, not yet runnable)
- `mobile/src/__tests__/mocks/exploEnv.ts` - Expo virtual env mock (not used due to transformation issue)
- `mobile/node_modules/expo/virtual/env.js` - Stub module for expo/virtual/env
- `mobile/node_modules/expo/virtual/package.json` - Package.json for stub
- `mobile/babel.config.js` - Added preserveEnvVars option
- `mobile/jest.setup.js` - Added expo/virtual/env mock and expo-constants mock
- `mobile/package.json` - Updated jest config

## Devisions Made

**BLOCKER DECISION:** Expo SDK 50's babel-preset-expo has an `inline-env-vars` plugin that transforms `process.env.EXPO_PUBLIC_*` references to use `expo/virtual/env` module in development mode. This module is generated at build time by Expo CLI and doesn't exist in Jest environment.

**Attempts made:**
1. Created expo/virtual/env.js stub file - Module loads but babel-transformation still fails
2. Added `preserveEnvVars: true` to babel-preset-expo config - Option not being respected
3. Set `NODE_ENV=production` - Still uses expo/virtual/env
4. Added jest.mock with `virtual: true` - Not working
5. Created package.json for expo/virtual stub - Module resolves but transformation fails

**Root cause:** The babel-preset-expo plugin transforms code like:
```typescript
const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';
```
Into:
```typescript
import { env } from 'expo/virtual/env';
const API_BASE_URL = env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';
```

But when Jest executes the transformed code, `env` is undefined, causing "Cannot read properties of undefined (reading 'EXPO_PUBLIC_API_URL')".

**Error location:** Line 73 of src/contexts/AuthContext.tsx (where API_BASE_URL is defined)

## Deviations from Plan

### BLOCKER - Expo SDK 50 Jest Incompatibility

**Issue:** babel-preset-expo inline-env-vars plugin (from babel-preset-expo/build/inline-env-vars.js) transforms `process.env.EXPO_PUBLIC_*` references to use `expo/virtual/env` module which doesn't exist in Jest

**Found during:** Task 1 - Creating AuthContext tests

**Impact:**
- AuthContext.test.tsx cannot run (1100+ lines of tests written but not executable)
- DeviceContext.test.tsx will have same issue
- Any mobile test importing files with EXPO_PUBLIC_ env vars will fail

**Attempted fixes:**
1. Created stub file at `node_modules/expo/virtual/env.js` - Module resolves but `env` is undefined in transformed code
2. Set `preserveEnvVars: true` in babel.config.js - Option not being respected by babel-preset-expo
3. Set `NODE_ENV=production` - Still transforms to expo/virtual/env
4. Added jest.mock with virtual:true option - Mock not being applied before babel transformation

**Files modified:**
- mobile/babel.config.js
- mobile/jest.setup.js
- mobile/package.json
- mobile/node_modules/expo/virtual/env.js (created)
- mobile/node_modules/expo/virtual/package.json (created)

**Committed in:** 60cc8731 (test: add AuthContext test infrastructure)

**Required resolution:** One of these approaches is needed:
1. Downgrade to Expo SDK 49 (doesn't use expo/virtual/env)
2. Modify AuthContext.tsx and DeviceContext.tsx to not use `process.env.EXPO_PUBLIC_*` pattern
3. Create custom babel preset that disables inline-env-vars plugin
4. File upstream issue with Expo team and wait for fix

---

**Total deviations:** 1 critical blocker (Expo SDK 50 incompatibility)
**Impact on plan:** Tasks 2-3 cannot be completed until blocker is resolved

## Issues Encountered

### CRITICAL: Expo SDK 50 + Jest Incompatibility

**Problem:** babel-preset-expo's inline-env-vars plugin transforms `process.env.EXPO_PUBLIC_*` to use `expo/virtual/env` module which doesn't exist in Jest

**Root cause:** In babel-preset-expo/build/inline-env-vars.js, lines 16-24:
```javascript
addNamedImportOnce(file.path, 'env', 'expo/virtual/env');
// ...
path.replaceWith(t.memberExpression(addEnvImport(), t.identifier(envVar)));
```

**Error message:**
```
TypeError: Cannot read properties of undefined (reading 'EXPO_PUBLIC_API_URL')
    at Object.EXPO_PUBLIC_API_URL (src/contexts/AuthContext.tsx:73:22)
```

**Affected files:**
- mobile/src/contexts/AuthContext.tsx (line 73: `process.env.EXPO_PUBLIC_API_URL`)
- mobile/src/contexts/DeviceContext.tsx (line 64: `process.env.EXPO_PUBLIC_API_URL`)

**Time spent debugging:** 40+ minutes

**Next steps:**
- Option 1: Modify source files to use `Constants.expoConfig?.extra?.eas?.projectId` pattern instead
- Option 2: Create custom Jest transform that handles expo/virtual/env
- Option 3: Downgrade to Expo SDK 49

## User Setup Required

None - tests cannot run until blocker is resolved

## Next Phase Readiness

**BLOCKED:** Cannot proceed with Tasks 2-3 (DeviceContext tests, platform permission tests) until expo/virtual/env issue is resolved

**Recommended approach:** Modify AuthContext.tsx and DeviceContext.tsx to use a different pattern for accessing environment variables:
- Change `process.env.EXPO_PUBLIC_API_URL` to use `Constants.expoConfig?.extra?.apiUrl`
- Or use a config file that imports from expo-constants without triggering babel transformation

**Alternative:** Skip tests for files using EXPO_PUBLIC_ env vars and test other parts of the contexts

---
*Phase: 04-platform-coverage*
*Completed: 2026-02-11*
