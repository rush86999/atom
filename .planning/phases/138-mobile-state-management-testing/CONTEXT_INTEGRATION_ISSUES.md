# Context Integration Tests - Known Issues

## Status: Tests created but blocked by React Native TurboModule issue

## Problem
The integration tests in `ContextIntegration.test.tsx` cannot run due to a React Native 0.73+ TurboModule issue with the `SettingsManager` module.

### Error Details
```
Invariant Violation: TurboModuleRegistry.getEnforcing(...): 'SettingsManager' could not be found.
```

### Root Cause
React Native 0.73+ uses TurboModules (new native module architecture) for certain modules like Settings. The current Jest configuration and mock setup cannot properly mock these TurboModules before they are loaded by `@testing-library/react-native`.

### Attempted Solutions (all failed)
1. Mocking `react-native/Libraries/Settings/NativeSettingsManager.js` - Virtual mock applied too late
2. Mocking `react-native/Libraries/Settings/Settings.ios.js` - Same issue
3. Adding `SettingsManager` to `NativeModules` mock - Not loaded before Settings.ios.js
4. Adding `TurboModuleRegistry.getEnforcing` mock - Still triggers too late
5. Creating `__mocks__/react-native.js` - Mock applied after module is already loaded
6. Using Object.keys instead of destructuring - Still triggers module load
7. Disabling `@testing-library/jest-native` - `@testing-library/react-native` also triggers the issue

### Impact
- Context integration tests cannot run
- Test coverage for context provider integration is blocked
- Plan 138-05 cannot be completed successfully

## Recommended Solutions

### Option 1: Upgrade React Native (Recommended)
Upgrade to React Native 0.74+ which has better TurboModule support in Jest:
```bash
npm install react-native@latest
npm install @react-native/eslint-config@latest
```

### Option 2: Use Detox for Integration Tests
Create a separate E2E test suite using Detox that doesn't rely on Jest mocks:
```bash
npm install --save-dev detox
detox init --jest
```

### Option 3: Mock at Transpilation Time
Configure Babel to replace Settings imports during transpilation:
```javascript
// babel.config.js
module.exports = {
  plugins: [
    ['transform-define', {
      'react-native/Libraries/Settings/NativeSettingsManager': '{}',
    }],
  ],
};
```

### Option 4: Manual Integration Testing
Document manual testing procedures for context integration until automated tests can be fixed.

## Test Coverage Impact
Without integration tests, we have:
- ✅ Unit tests for AuthContext (42 tests, 95% pass rate)
- ✅ Unit tests for DeviceContext (41 tests, 27% pass rate)
- ✅ Unit tests for WebSocketContext (28 tests, 14% pass rate)
- ❌ Integration tests for all three providers together

## Next Steps
1. Discuss with team which approach to take
2. Implement chosen solution
3. Re-run ContextIntegration.test.tsx
4. Verify integration test coverage
5. Update this document with resolution

## Created
2026-03-05
## Phase/Plan
138-05: Context Integration Tests
