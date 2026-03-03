# Mobile E2E Tests with Detox

## Purpose

End-to-end (E2E) tests for the Atom mobile app using Detox grey-box testing framework. These tests verify critical user workflows (authentication, agent execution, canvas presentations) work correctly on iOS and Android devices.

## What is Detox?

Detox is a grey-box E2E testing framework for React Native that provides:
- **10x faster execution** than Appium (access to app state, no black-box limitations)
- **Automatic synchronization** - waits for animations, network requests, and timers
- **Cross-platform support** - iOS and Android with same test code
- **Debuggable** - run tests in interactive mode with inspector

## Setup for Developers

### Prerequisites

1. **iOS Simulator** (macOS only):
   ```bash
   xcrun simctl list devices
   ```

2. **Android Emulator** (optional):
   ```bash
   emulator -list-avds
   ```

### Install Dependencies

```bash
cd mobile
npm install
```

Detox is already installed in `devDependencies`:
- `detox@20.47.0`
- `detox-expo-helpers@0.6.0`
- `jest-circus@30.2.0`

### Running Tests

#### Build App for Testing

```bash
# iOS simulator
npm run e2e:build:ios
```

#### Run Tests

```bash
# iOS simulator
npm run e2e:test:ios
```

## Known Limitations

### Expo Dev Client Requirement

**IMPORTANT**: Detox requires Expo dev client to work with Expo projects. This means:

1. **Standard Expo Go app won't work** - Must use custom development build
2. **Requires prebuild** - Run `npx expo prebuild --clean` to generate native code
3. **Binary path configuration** - `detox.config.js` must point to compiled app binary

**If expo-dev-client is not installed**, tests will fail with:
```
Error: Cannot find module 'expo-dev-client'
```

To install expo-dev-client:
```bash
cd mobile
npm install --save-dev expo-dev-client
npx expo prebuild --clean
```

### Build Complexity

Detox requires compiling the app for E2E testing:
- **iOS**: Xcode build required (`ios/build/Build/Products/Debug-iphonesimulator/Atom.app`)
- **Android**: Gradle build required (APK in `android/app/build/outputs/apk/`)

This adds 2-5 minutes to test execution time.

### Alternative: API-Level Testing

If Detox proves too complex for Phase 099 timeline:
- Use API-level tests with Jest (already operational)
- Test React Native components with `@testing-library/react-native` (already have 194 tests)
- Defer full E2E testing to post-v4.0

## CI Integration

Planned for Phase 099-07:
```yaml
name: E2E Tests (Mobile)
on: push: branches: [main]
jobs:
  e2e-mobile:
    runs-on: macos-latest  # Required for iOS
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: npm ci
      - name: Build app
        run: npx expo prebuild --clean
      - name: Run Detox tests
        run: npm run e2e:test:ios
```

## Test Structure

```
e2e/
├── detox.config.js        # Detox configuration
├── init.js                # Detox initialization
├── config.json            # Jest configuration
├── __init__.readme.md     # This file
├── prototype.e2e.js       # Prototype test (Plan 099-02)
├── auth/                  # Authentication tests (Plan 099-04)
│   ├── login.e2e.js
│   └── biometric.e2e.js
├── agent/                 # Agent execution tests (Plan 099-04)
│   ├── agentChat.e2e.js
│   └── canvasPresentation.e2e.js
└── cross-platform/        # Feature parity tests (Plan 099-05)
    └── featureParity.e2e.js
```

## Next Steps

1. **Plan 099-02** (Current): Spike Detox feasibility with prototype test
2. **Plan 099-03**: Desktop E2E spike with tauri-driver
3. **Plan 099-04**: Full E2E test implementation (auth, agent, canvas)
4. **Plan 099-05**: Cross-platform feature parity tests
5. **Plan 099-07**: CI/CD orchestration with separate mobile E2E workflow

## Resources

- [Detox Documentation](https://wix.github.io/Detox/)
- [detox-expo-helpers](https://github.com/wix-incubator/detox-expo-helpers)
- [Expo Dev Client](https://docs.expo.dev/develop/development-builds/introduction/)
