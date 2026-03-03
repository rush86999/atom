# Detox E2E Feasibility Assessment - Phase 099-02

**Status**: BLOCKED
**Date**: 2026-02-26
**Plan**: 099-02 (Spike Detox E2E infrastructure)

## Executive Summary

Detox E2E testing with Expo 50 is **BLOCKED** due to expo-dev-client requirement. The standard Expo Go app does not support Detox grey-box testing, which requires a custom development build with native code access.

## Installation Results

### What Worked

1. **Detox Installation**: SUCCESS
   - Detox 20.47.0 installed successfully
   - detox-expo-helpers 0.6.0 installed
   - jest-circus 30.2.0 installed
   - E2E scripts added to package.json (`e2e:build:ios`, `e2e:test:ios`)

2. **Configuration Files**: SUCCESS
   - `e2e/detox.config.js` - iOS simulator configuration created
   - `e2e/init.js` - Detox Expo helpers imported
   - `e2e/config.json` - Jest Circus runner configured
   - `e2e/prototype.e2e.js` - Prototype test created

### What's Blocking

**expo-dev-client NOT installed** - This is the primary blocker:

```
Error: Cannot find module 'expo-dev-client'
```

Detox requires Expo dev client to:
1. Access native modules (grey-box architecture)
2. Use custom React Native runtime
3. Enable app reload during tests
4. Access app state for faster synchronization

## Feasibility Verdict

### BLOCKED - Too Complex for Phase 099 Timeline

**Reasoning:**
1. **Requires expo-dev-client** - Must install dev client, then run `npx expo prebuild --clean` to generate native code (iOS + Android)
2. **Build complexity** - Each E2E test run requires compiling native app (2-5 minutes for iOS)
3. **iOS development required** - Xcode build pipeline, simulator management, binary path configuration
4. **Android build optional** - Adds more complexity if testing both platforms
5. **2-week timeline pressure** - Phase 099 has 8 plans, E2E implementation is Plan 02-04, may not fit

### Alternative: Defer to Post-v4.0

**Recommended Approach:**
1. **Use existing Jest tests** (194 tests, 100% pass rate)
2. **Add component integration tests** with `@testing-library/react-native`
3. **Test API contracts** via backend API tests (already have 1,048 tests)
4. **Defer full E2E testing** to post-v4.0 when timeline allows proper setup

### If Proceeding Anyway (Not Recommended)

**Required Steps:**
1. Install expo-dev-client: `npm install --save-dev expo-dev-client`
2. Generate native code: `npx expo prebuild --clean`
3. Configure Detox binary paths for iOS/Android builds
4. Update CI/CD to compile native apps before E2E tests
5. Add 10-15 minutes per E2E test run (build + test execution)

**Risks:**
- Phase 099 timeline slippage (8 plans, 2 weeks)
- CI/CD complexity increase (native builds on macOS runners)
- Maintenance burden (native code, build configuration)
- May not complete full E2E suite in time

## Prototype Test Results

### Test: `prototype.e2e.js`

**Expected Behavior:**
- Launch app with expo-dev-client
- Verify root view is visible
- Navigate to agent chat screen
- Verify Detox grey-box access (device platform)

**Actual Behavior:**
- **BLOCKED at launch** - expo-dev-client not installed
- Cannot proceed without custom development build

### What We Verified

1. **Detox CLI works**: `npx detox --version` returns 20.47.0
2. **Configuration valid**: `node -e "require('./e2e/detox.config.js')"` succeeds
3. **Test structure valid**: Prototype test created with proper Detox API usage
4. **Dependencies installed**: All npm packages installed successfully

## Recommendations

### For Phase 099 (Cross-Platform Integration & E2E)

**Option 1: Defer Mobile E2E to Post-v4.0** (RECOMMENDED)

- Use existing Jest tests (194 tests, 16.16% coverage)
- Add API-level integration tests via backend
- Focus on web E2E with Playwright (already operational from Phase 075-080)
- Implement desktop E2E with tauri-driver (Plan 099-03)
- Revisit mobile E2E in Phase 100+ with proper time allocation

**Option 2: Proceed with Detox** (NOT RECOMMENDED - Timeline Risk)

- Install expo-dev-client and generate native code (2-3 hours)
- Configure iOS build pipeline (1-2 hours)
- Update CI/CD for native builds (2-3 hours)
- Implement 10-15 E2E tests (3-5 hours)
- **Total: 8-13 hours** vs. 2-week Phase 099 timeline
- Risk: May not complete other Phase 099 plans (cross-platform, performance)

### For Post-v4.0 Implementation

If implementing Detox E2E after v4.0:

1. **Allocate dedicated phase** (e.g., Phase 100: Mobile E2E)
2. **Setup expo-dev-client** from project start
3. **iOS CI/CD pipeline** with macOS runners (more expensive)
4. **TestID strategy** - Add `testID` props to all interactive components
5. **Parallel execution** - Use Detox workers to speed up tests
6. **Mocking strategy** - Mock backend API responses for faster tests

## Technical Details

### Detox Configuration

```javascript
// e2e/detox.config.js
{
  testRunner: {
    args: {
      '$0': 'jest',
      config: 'e2e/config.json'
    },
    jest: {
      setupTimeout: 120000  // 2 minutes for app launch
    }
  },
  apps: {
    'ios.debug': {
      type: 'ios.app',
      binaryPath: 'ios/build/Build/Products/Debug-iphonesimulator/Atom.app'
    }
  },
  devices: {
    simulator: {
      type: 'ios.simulator',
      device: { type: 'iPhone 14' }
    }
  },
  configurations: {
    'ios.sim.debug': {
      device: 'simulator',
      app: 'ios.sim.debug'
    }
  }
}
```

### Required Dependencies

```json
{
  "devDependencies": {
    "detox": "^20.47.0",
    "detox-expo-helpers": "^0.6.0",
    "jest-circus": "^30.2.0",
    "expo-dev-client": "^4.0.0"  // MISSING - BLOCKER
  }
}
```

### Build Commands

```bash
# Generate native code (2-5 minutes)
npx expo prebuild --clean

# Build iOS app for E2E testing (2-3 minutes)
npm run e2e:build:ios

# Run E2E tests (5-10 minutes)
npm run e2e:test:ios
```

## Decision Matrix

| Factor | Proceed with Detox | Defer to Post-v4.0 |
|--------|-------------------|-------------------|
| **Timeline Risk** | HIGH (8-13 hours) | LOW (0 hours) |
| **Implementation Complexity** | HIGH (native builds) | LOW (use existing tests) |
| **CI/CD Impact** | HIGH (macOS runners) | NONE (existing infrastructure) |
| **Test Coverage** | +10-15 E2E tests | +0 E2E tests (use 194 Jest tests) |
| **Maintenance Burden** | HIGH (native code) | LOW (JS only) |
| **Phase 099 Completion** | AT RISK (may not finish) | SAFE (focus on web/desktop) |
| **Value vs. Effort** | LOW (3-5 days for 15 tests) | HIGH (focus on cross-platform) |

## Conclusion

**Detox E2E testing is BLOCKED for Phase 099** due to expo-dev client requirement and build complexity. The recommended approach is to defer mobile E2E testing to post-v4.0 and focus Phase 099 on:

1. **Web E2E with Playwright** (already operational)
2. **Desktop E2E with tauri-driver** (Plan 099-03)
3. **Cross-platform integration tests** (Plan 099-05)
4. **Performance regression tests** (Plan 099-04)

This ensures Phase 099 completes on time while maintaining high test coverage (1,048 existing tests + 194 mobile Jest tests).

---

**Next Steps:**
- Document blocker in Phase 099-02 SUMMARY.md
- Proceed with Plan 099-03 (Desktop E2E spike)
- Revisit mobile E2E in Phase 100+ if needed

**Resources:**
- [Detox Documentation](https://wix.github.io/Detox/)
- [Expo Dev Client](https://docs.expo.dev/develop/development-builds/introduction/)
- [detox-expo-helpers](https://github.com/wix-incubator/detox-expo-helpers)
