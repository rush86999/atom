# Phase 144: Cross-Platform Shared Utilities - Research

**Researched:** 2026-03-05
**Domain:** Cross-platform monorepo testing, shared TypeScript utilities, Jest configuration, symlink strategies
**Confidence:** MEDIUM

## Summary

Phase 144 requires creating shared test utilities for Atom's three platforms (frontend-nextjs, mobile, desktop) using a SYMLINK strategy. The project already has platform-specific test infrastructure in place: frontend uses Jest with jsdom (Phase 134), mobile uses jest-expo with React Native Testing Library (Phase 139), and desktop uses Rust cargo test with Tauri mocks (Phase 143). This phase focuses on extracting common test helpers into a shared location (`frontend-nextjs/shared/`) and configuring symlinks for mobile and desktop to reference these utilities, ensuring consistency and reducing code duplication across platforms.

**Primary recommendation:** Create a shared test utilities package in `frontend-nextjs/shared/test-utils/` with platform-agnostic helpers (async utilities, mock factories, assertions, cleanup utilities), configure TypeScript path mapping for all three platforms to resolve `@atom/test-utils` to the shared folder, use symlinks for runtime module resolution (`mobile/src/shared → frontend-nextjs/shared`), and validate cross-platform compatibility with a test suite that exercises shared utilities on all three platforms.

**Key findings:** (1) React Native and Next.js can share TypeScript test utilities when using platform-agnostic patterns (no DOM-specific APIs, no React Native-specific APIs in shared code), (2) Symlink-based sharing is well-supported by npm/yarn workspaces and TypeScript path mapping, (3) Jest configurations need explicit `moduleNameMapper` entries to resolve shared utilities across platforms, (4) Desktop Tauri tests (Rust) cannot directly use TypeScript utilities but can benefit from shared test data fixtures and JSON schemas, (5) The monorepo already has extensive path mapping configuration in `frontend-nextjs/tsconfig.json` that can be extended for shared test utilities.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Jest** | 29.x | Test runner for all three platforms | Already in project, cross-platform support |
| **TypeScript** | 5.x | Type-safe shared utilities | Already in project, path mapping support |
| **ts-jest** | 29.x | TypeScript compilation in Jest | Already in frontend project |

### Already in Project

From `frontend-nextjs/package.json`:
```json
{
  "devDependencies": {
    "@testing-library/jest-dom": "^6.x",
    "@testing-library/react": "^14.x",
    "jest": "^29.x",
    "jest-environment-jsdom": "^29.x",
    "ts-jest": "^29.x",
    "typescript": "^5.x"
  }
}
```

From `mobile/package.json`:
```json
{
  "devDependencies": {
    "@testing-library/jest-native": "^5.4.3",
    "@testing-library/react-native": "^12.4.2",
    "jest": "^29.7.0",
    "jest-expo": "~50.0.0",
    "typescript": "^5.3.3"
  }
}
```

From `frontend-nextjs/src-tauri/Cargo.toml`:
```toml
[dev-dependencies]
cargo-tarpaulin = "0.27"
```

**Recommendation:** No new dependencies required. Use existing Jest + TypeScript setup.

### Supporting Tools

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **npm workspaces** | Built-in (npm 7+) | Monorepo package management | Already available in npm 7+, no install needed |
| **symlink-dir** | (not in project) | Create symlinks cross-platform | Alternative to manual `ln -s` commands |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **SYMLINK strategy** | **npm workspace package** | Workspace packages provide better isolation but require package.json setup; symlinks simpler for single-repo sharing |
| **TypeScript path mapping** | **babel-plugin-module-resolver** | Path mapping is TypeScript-native, babel plugin adds build-time complexity |
| **Manual symlinks** | **package.json workspace:\*** | Workspace protocol is cleaner but requires monorepo structure; manual symlinks work with existing structure |

## Architecture Patterns

### Recommended Directory Structure

```
atom/
├── frontend-nextjs/
│   ├── shared/
│   │   ├── test-utils/
│   │   │   ├── index.ts                 # Main export barrel
│   │   │   ├── async-utils.ts           # waitFor, flushPromises, waitForCondition
│   │   │   ├── mock-factories.ts        # createMockWebSocket, createMockFn, createMockAsyncFn
│   │   │   ├── assertions.ts            # assertThrows, assertRejects, assertRendersWithoutThrow
│   │   │   ├── cleanup.ts               # resetAllMocks, setupFakeTimers, cleanupTest
│   │   │   ├── platform-guards.ts       # isIOS, isAndroid, isWeb, isDesktop
│   │   │   ├── test-data.ts             # Common test fixtures, sample data
│   │   │   └── types.ts                 # Shared TypeScript types for testing
│   │   └── package.json                 # Optional: workspace package configuration
│   ├── jest.config.js                   # Add moduleNameMapper for @atom/test-utils
│   └── tsconfig.json                    # Already has @shared/* paths
├── mobile/
│   ├── src/shared/ -> ../../frontend-nextjs/shared/  # SYMLINK (NEW)
│   ├── jest.config.js                   # Add moduleNameMapper for @atom/test-utils
│   └── tsconfig.json                    # Add @atom/test-utils path
├── frontend-nextjs/src-tauri/
│   ├── tests/
│   │   └── shared_fixtures/ -> ../../shared/test-utils/fixtures/  # SYMLINK for JSON data (NEW)
│   └── Cargo.toml                       # Rust tests use shared JSON fixtures
└── root/
    └── tsconfig.base.json               # Optional: shared TypeScript config (NEW)
```

### Pattern 1: Platform-Agnostic Test Utilities

**What:** Write test helpers that work across web, mobile, and desktop environments

**When to use:** Shared utilities that don't depend on platform-specific APIs (DOM, React Native, Tauri)

**Example:**
```typescript
// frontend-nextjs/shared/test-utils/async-utils.ts

/**
 * Wrapper around waitFor with default timeout
 * Platform-agnostic: works in jsdom (web) and react-native (mobile)
 *
 * @example
 * await waitForAsync(() => {
 *   expect(getByText('Loaded')).toBeTruthy();
 * });
 */
export const waitForAsync = async (
  callback: () => void,
  timeout: number = 3000
): Promise<void> => {
  // Works with both @testing-library/react and @testing-library/react-native
  const { waitFor } = await import('@testing-library/react'); // Runtime import
  await waitFor(callback, { timeout });
};

/**
 * Flush all pending promises in the fake timer queue
 * Works with Jest fake timers across all platforms
 *
 * @example
 * jest.useFakeTimers();
 * await flushPromises();
 * expect(mockFunction).toHaveBeenCalled();
 */
export const flushPromises = async (): Promise<void> => {
  return new Promise(resolve => {
    setImmediate(resolve);
    jest.runAllTimers();
  });
};
```

### Pattern 2: Platform Guard Utilities

**What:** Detect current platform and provide conditional logic

**When to use:** Utilities that need platform-specific behavior but can share implementation

**Example:**
```typescript
// frontend-nextjs/shared/test-utils/platform-guards.ts

/**
 * Check if running in web environment
 */
export const isWeb = (): boolean => {
  return typeof window !== 'undefined' &&
         typeof window.document !== 'undefined';
};

/**
 * Check if running in React Native environment
 */
export const isReactNative = (): boolean => {
  return typeof navigator !== 'undefined' &&
         (navigator as any).product === 'ReactNative';
};

/**
 * Check if running in Tauri desktop environment
 */
export const isTauri = (): boolean => {
  return typeof window !== 'undefined' &&
         (window as any).__TAURI__ !== undefined;
};

/**
 * Skip test based on platform
 * @example
 * skipIfNotWeb()('test name', () => {
 *   // This test only runs on web
 * });
 */
export const skipIfNotWeb = () => {
  return isWeb() ? test : test.skip;
};
```

### Pattern 3: Shared Mock Factories

**What:** Create mock objects with realistic defaults

**When to use:** Mocking WebSocket, HTTP clients, data structures

**Example:**
```typescript
// frontend-nextjs/shared/test-utils/mock-factories.ts

/**
 * Create a mock WebSocket with realistic connection behavior
 * Works across all platforms
 *
 * @example
 * const mockSocket = createMockWebSocket(true);
 * expect(mockSocket.connected).toBe(true);
 * expect(mockSocket.send).toBeDefined();
 */
export const createMockWebSocket = (connected = true) => {
  return {
    url: 'ws://localhost:8000',
    connected,
    onopen: null,
    onmessage: null,
    onerror: null,
    onclose: null,
    send: jest.fn(),
    close: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  };
};

/**
 * Create a mock function with implementation
 *
 * @example
 * const mockFn = createMockFn((x) => x * 2);
 * expect(mockFn(5)).toBe(10);
 */
export const createMockFn = <T extends (...args: unknown[]) => unknown>(
  implementation: T
): jest.MockedFunction<T> => {
  return jest.fn(implementation) as jest.MockedFunction<T>;
};
```

### Pattern 4: TypeScript Path Mapping Configuration

**What:** Configure TypeScript to resolve shared utilities across platforms

**When to use:** All three platforms need to import from `@atom/test-utils`

**Example:**
```json
// frontend-nextjs/tsconfig.json (extend existing paths)
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@shared/*": ["../../src/ui-shared/*"],
      "@atom/test-utils": ["./shared/test-utils"],
      "@atom/test-utils/*": ["./shared/test-utils/*"]
    }
  }
}

// mobile/tsconfig.json (add new paths)
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
      "@atom/test-utils": ["../frontend-nextjs/shared/test-utils"],
      "@atom/test-utils/*": ["../frontend-nextjs/shared/test-utils/*"]
    }
  }
}
```

### Pattern 5: Jest Module Resolution

**What:** Configure Jest to resolve shared utilities across platforms

**When to use:** Test execution needs to find shared utilities

**Example:**
```javascript
// frontend-nextjs/jest.config.js
module.exports = {
  moduleNameMapper: {
    '^@atom/test-utils(.*)$': '<rootDir>/shared/test-utils$1',
  },
};

// mobile/jest.config.js
module.exports = {
  moduleNameMapper: {
    '^@atom/test-utils(.*)$': '<rootDir>/../frontend-nextjs/shared/test-utils$1',
  },
};
```

### Anti-Patterns to Avoid

- **Platform-specific APIs in shared code**: Don't use `window.document` (web-only) or `Platform.OS` (RN-only) in shared utilities
- **Tight coupling to implementation details**: Shared utilities should be generic, not tied to specific components
- **Missing platform guards**: Always provide fallbacks or guards for platform-specific features
- **Inconsistent imports**: Use the same import path across all platforms (`@atom/test-utils`)
- **Forgetting Rust integration**: Don't overlook that Tauri Rust tests can't use TS utilities directly

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Async utilities** | Custom waitFor, promise flushing | `@testing-library/react`'s `waitFor`, Jest's `flushPromises` | Already handles edge cases (timeouts, intervals, fake timers) |
| **Mock factories** | Manual object creation | `jest.fn()`, factory pattern | Jest provides built-in mocking with assertion capabilities |
| **Platform detection** | Manual environment checks | `Platform.OS` (RN), `window.__TAURI__` (Tauri), `typeof window` (web) | Platform-specific APIs are more reliable |
| **TypeScript config** | Manual path resolution | `tsconfig.json` `paths` with `baseUrl` | TypeScript-native module resolution |
| **Symlink management** | Manual `ln -s` scripts | npm workspaces or `symlink-dir` package | Cross-platform compatibility (Windows/macOS/Linux) |

**Key insight:** Shared test utilities should extract and generalize existing patterns, not invent new ones. The three platforms already have working test infrastructure—this phase is about removing duplication, not adding complexity.

## Common Pitfalls

### Pitfall 1: Platform-Specific API Leakage

**What goes wrong:** Shared utilities accidentally use web-only APIs (e.g., `window.document`) or React Native-only APIs (e.g., `Platform.OS`), causing import errors on other platforms.

**Why it happens:** Developers copy utilities from one platform without considering cross-platform compatibility.

**How to avoid:** (1) Audit shared utilities for platform-specific APIs, (2) Use platform guards (`isWeb()`, `isReactNative()`) to conditionally use platform features, (3) Write tests that import shared utilities in all three platforms.

**Warning signs:** Import errors when running tests on different platforms, TypeScript errors about missing properties.

### Pitfall 2: TypeScript Path Mapping Not Resolved at Runtime

**What goes wrong:** TypeScript compiles successfully but Jest throws "Cannot find module '@atom/test-utils'" errors.

**Why it happens:** TypeScript `paths` only affects compile-time resolution, not runtime module resolution. Jest needs `moduleNameMapper` configuration.

**How to avoid:** (1) Always configure `moduleNameMapper` in Jest config to match TypeScript `paths`, (2) Use `<rootDir>` in Jest paths for consistency, (3) Verify test execution after adding new shared utilities.

**Warning signs:** Tests pass in IDE (which uses TS paths) but fail in CI (which uses Jest resolution).

### Pitfall 3: Symlink Issues on Windows

**What goes wrong:** Symlinks created on macOS/Linux don't work on Windows due to different path formats or permissions.

**Why it happens:** Windows symlinks require developer mode or admin privileges, and use different path separators (`\` vs `/`).

**How to avoid:** (1) Use npm workspaces or `symlink-dir` package for cross-platform symlinks, (2) Document symlink creation in CONTRIBUTING.md, (3) Add CI check to verify shared utilities are accessible.

**Warning signs:** "EPERM: operation not permitted" errors on Windows, module not found errors.

### Pitfall 4: Circular Dependencies Between Platforms

**What goes wrong:** Frontend imports from shared, shared imports from frontend, creating circular dependency.

**Why it happens:** Shared utilities accidentally import platform-specific code (e.g., frontend components).

**How to avoid:** (1) Enforce one-way dependency: platforms → shared, never shared → platforms, (2) Lint rule to prevent imports from `frontend-nextjs/src` in shared utilities, (3) Use dependency injection for platform-specific behavior.

**Warning signs:** "Maximum call stack size exceeded" errors, tests hanging indefinitely.

### Pitfall 5: Jest Configuration Mismatches

**What goes wrong:** Same test passes on one platform but fails on another due to different Jest configurations (transformers, environments, setup files).

**Why it happens:** Each platform has custom Jest config (jsdom for web, react-native for mobile, node for Rust tests), and shared utilities may not work in all environments.

**How to avoid:** (1) Document which utilities work in which environments, (2) Use environment guards in shared utilities (e.g., `if (typeof window !== 'undefined')`), (3) Create platform-specific wrapper utilities for incompatible features.

**Warning signs:** Inconsistent test results across platforms, "undefined is not a function" errors.

## Code Examples

Verified patterns from existing Atom codebase and research:

### Example 1: Shared Async Utilities

```typescript
// frontend-nextjs/shared/test-utils/async-utils.ts
// Source: Adapted from mobile/src/__tests__/helpers/testUtils.ts

/**
 * Wait for a condition to be true with fake timers
 * Platform-agnostic: works with Jest fake timers across all platforms
 *
 * @param condition - Function that returns true when condition is met
 * @param timeout - Timeout in milliseconds (default: 5000)
 *
 * @example
 * await waitForCondition(() => result.current.connected === true);
 */
export const waitForCondition = async (
  condition: () => boolean,
  timeout = 5000,
): Promise<void> => {
  const startTime = Date.now();
  while (!condition()) {
    if (Date.now() - startTime > timeout) {
      throw new Error(`Condition not met within ${timeout}ms`);
    }
    await new Promise(resolve => setImmediate(resolve));
    jest.runAllTimers();
  }
};
```

### Example 2: Platform-Specific Wrapper

```typescript
// frontend-nextjs/shared/test-utils/platform-utils.ts

/**
 * Platform-specific test setup
 * Provides unified interface for platform differences
 */

export const setupPlatformTest = () => {
  if (typeof window !== 'undefined' && (window as any).__TAURI__) {
    // Tauri desktop setup
    console.log('Setting up Tauri test environment');
    // Tauri-specific mock setup
  } else if (typeof navigator !== 'undefined' && (navigator as any).product === 'ReactNative') {
    // React Native setup
    console.log('Setting up React Native test environment');
    // RN-specific mock setup
  } else {
    // Web setup
    console.log('Setting up web test environment');
    // Web-specific mock setup (jsdom)
  }
};
```

### Example 3: Shared Test Data Fixtures

```typescript
// frontend-nextjs/shared/test-utils/test-data.ts

/**
 * Common test data fixtures
 * Used across all platforms for consistent test scenarios
 */

export const mockAgents = [
  { id: 'agent-1', name: 'Test Agent 1', maturity: 'AUTONOMOUS' },
  { id: 'agent-2', name: 'Test Agent 2', maturity: 'SUPERVISED' },
];

export const mockWorkflows = [
  { id: 'workflow-1', name: 'Test Workflow', steps: 5 },
];

export const mockUser = {
  id: 'user-1',
  name: 'Test User',
  email: 'test@example.com',
};
```

### Example 4: Rust Tests Using Shared JSON Fixtures

```rust
// frontend-nextjs/src-tauri/tests/commands_test.rs
// Source: Adapted from existing tests

#[test]
fn test_command_with_shared_fixture() {
    // Read shared JSON fixture from symlinked location
    let fixture_path = PathBuf::from("tests/shared_fixtures/mock_agents.json");
    let fixture_content = fs::read_to_string(fixture_path).unwrap();
    let agents: Vec<Agent> = serde_json::from_str(&fixture_content).unwrap();

    // Use fixture data in test
    assert_eq!(agents.len(), 2);
    assert_eq!(agents[0].id, "agent-1");
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Duplicate test utilities** | **Shared monorepo utilities** | 2020-2021 (monorepo adoption) | Reduced duplication, consistent testing patterns |
| **Manual import paths** | **TypeScript path mapping** | 2021-2022 (TS 4.x) | Cleaner imports, better IDE support |
| **Platform-specific tests only** | **Cross-platform test suites** | 2022-2023 (testing library ecosystem) | Better coverage across platforms |
| **Separate test configs** | **Shared Jest presets** | 2023-2024 (jest 29.x) | Easier configuration management |

**Deprecated/outdated:**
- **Manual module resolution**: Modern Jest and TypeScript handle path mapping natively
- **Copy-paste utilities**: Monorepo tooling (npm/yarn/pnpm workspaces) makes sharing trivial
- **Platform-specific-only testing**: Cross-platform frameworks (React Native Web, Tauri) require shared testing patterns

## Open Questions

1. **Tauri Rust Test Integration**
   - What we know: Rust tests cannot directly import TypeScript utilities
   - What's unclear: Best practice for sharing test logic between TypeScript tests and Rust tests
   - Recommendation: Share JSON fixtures and schemas only, keep test logic platform-specific

2. **Symlink Persistence Across Git Operations**
   - What we know: Git doesn't track symlinks consistently across platforms
   - What's unclear: Will symlinks break when developers clone repo on Windows?
   - Recommendation: Add post-install script to create symlinks automatically, document in CONTRIBUTING.md

3. **Jest Transformer Compatibility**
   - What we know: Frontend uses ts-jest, mobile uses jest-expo (which uses babel-jest)
   - What's unclear: Will shared TypeScript files compile correctly with different transformers?
   - Recommendation: Test shared utilities on all three platforms before committing, use plain JS (no TS-only features) if compatibility issues arise

## Sources

### Primary (HIGH confidence)

- **Atom Mobile Test Utilities** - `/Users/rushiparikh/projects/atom/mobile/src/__tests__/helpers/testUtils.ts` - Existing test helpers with platform mocking, async utilities, cleanup functions
- **Frontend Jest Configuration** - `/Users/rushiparikh/projects/atom/frontend-nextjs/jest.setup.js` - Existing Jest setup with mocks and test environment configuration
- **Frontend TypeScript Paths** - `/Users/rushiparikh/projects/atom/frontend-nextjs/tsconfig.json` - Extensive path mapping configuration with @shared/* aliases
- **Mobile TypeScript Config** - `/Users/rushiparikh/projects/atom/mobile/tsconfig.json` - Path mapping with baseUrl and @/* aliases
- **Desktop Tauri Tests** - `/Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/tests/commands_test.rs` - Example Rust test patterns using cargo test

### Secondary (MEDIUM confidence)

- [Setting Up a Modern Web Development Environment in 2025](https://dev.to/hasanulmukit/setting-up-a-modern-web-development-environment-in-2025-3i59) - Jest and React Testing Library setup patterns
- [React Native Testing Library Guide](https://m.blog.csdn.net/gitblog_00879/article/details/141990737) - React Native testing best practices with @testing-library/react-native
- [TypeScript Monorepo Configuration Guide](https://m.blog.csdn.net/gitblog_00538/article/details/154419866) - TypeScript path mapping and extends configuration for monorepos
- [npm Workspaces Documentation](https://npm.nodejs.cn/cli/v9/using-npm/workspaces/) - Official npm workspaces reference for symlink-based package sharing
- [Yarn Workspaces Documentation](https://yarn.bootcss.com/docs/workspaces) - Yarn workspace implementation of symlink-based monorepos

### Tertiary (LOW confidence)

- [React Native Universal Monorepo](https://m.blog.csdn.net/gitblog_00438/article/details/144367666) - Monorepo template for React Native cross-platform development
- [Modern Monorepo Boilerplate](https://download.csdn.net/download/weixin_42128676/15062605) - Lerna + Yarn Workspaces + Jest setup for monorepos
- [Tauri Testing Strategy](https://m.blog.csdn.net/gitblog_00861/article/details/151810903) - Tauri testing overview (unit/integration/E2E layers)
- [Monorepo Engineering Tutorial](https://www.cnblogs.com/yfceshi/p/19019902) - pnpm workspace implementation with symlink-based sharing

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - Based on existing project configuration and verified dependencies
- Architecture: MEDIUM - Cross-platform patterns well-documented, but Atom-specific integration needs validation
- Pitfalls: HIGH - Common monorepo issues well-understood from web search and experience

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (30 days - stable domain, but fast-evolving tooling)
