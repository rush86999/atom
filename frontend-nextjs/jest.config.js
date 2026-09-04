module.exports = {
  testEnvironment: "jsdom",
  setupFiles: ["<rootDir>/tests/polyfills.ts"],
  setupFilesAfterEnv: ["<rootDir>/tests/setup.ts"],  // Fixed: setup.tsx → setup.ts (Phase 299-04-RETRY)
  transform: {
    "^.+\\.(ts|tsx)$": ["ts-jest", {
      tsconfig: {
        jsx: "react",
        esModuleInterop: true,
        allowSyntheticDefaultImports: true,
      },
    }],
    "^.+\\.(js|jsx)$": "babel-jest",
  },
  preset: "ts-jest",
  testMatch: [
    // Shared property tests (Phase 147: Cross-Platform Property Testing).
    // NOTE: only match actual *.test.ts files here — the bare glob previously
    // matched source modules (index.ts, config.ts, types.ts, ...) which threw
    // "Your test suite must contain at least one test" collection errors.
    "<rootDir>/shared/property-tests/**/*.test.(ts|tsx|js)",
    // Standard test files
    "<rootDir>/tests/**/*.test.(ts|tsx|js)",
    "<rootDir>/components/**/__tests__/**/*.test.(ts|tsx|js)",
    "<rootDir>/components/**/__tests__/**/*.a11y.test.(ts|tsx)",
    "<rootDir>/lib/**/__tests__/**/*.test.(ts|tsx|js)",
    "<rootDir>/hooks/**/__tests__/**/*.test.(ts|tsx|js)",
    // Page/API route tests. ALWAYS place these under tests/pages/, NEVER under
    // pages/__tests__/. Next.js' filesystem router treats EVERY file under
    // pages/ as a route and tries to collect page data for it during `next
    // build`, which crashes on test files ("Failed to collect page data for
    // /__tests__/..."). Despite the underscore prefix, __tests__ dirs under
    // pages/ are NOT ignored by the router (only _document/_app are). The
    // `prebuild` script in package.json removes any stray pages/__tests__ as a
    // safety net, but please put tests here in the first place.
    "<rootDir>/tests/pages/**/*.test.(ts|tsx|js)",
    // Page tests co-located under pages/__tests__/. NOTE: the `prebuild`
    // script removes this directory before `next build` so test files never
    // reach the Next.js filesystem router.
    "<rootDir>/pages/__tests__/**/*.test.(ts|tsx|js)",
  ],
  collectCoverageFrom: [
    "components/**/*.{ts,tsx}",
    "pages/**/*.{ts,tsx}",
    "lib/**/*.{ts,tsx}",
    "hooks/**/*.{ts,tsx}",
    "!**/*.d.ts",
    "!**/node_modules/**",
    "!**/.next/**",
    "!**/__tests__/**",
    "!**/*.test.{ts,tsx,js}",
  ],
  coverageDirectory: "coverage",
  coverageReporters: ["json", "json-summary", "text", "lcov"],
  // Progressive coverage thresholds (Phase 153)
  // Phase 1 (70%): Baseline enforcement
  // Phase 2 (75%): Interim target
  // Phase 3 (80%): Final target
  // New code: Always 80% regardless of phase
  // Set COVERAGE_PHASE environment variable to control phase
  get coverageThreshold() {
    const phase = process.env.COVERAGE_PHASE || 'phase_1';

    const thresholds = {
      phase_1: {
        branches: 70,
        functions: 70,
        lines: 70,
        statements: 70,
      },
      phase_2: {
        branches: 75,
        functions: 75,
        lines: 75,
        statements: 75,
      },
      phase_3: {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
    };

    return {
      global: thresholds[phase],
      // New code always requires 80% regardless of phase
      './src/**/*.{ts,tsx}': {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
      // Utilities - critical infrastructure, highly testable
      './lib/**/*.{ts,tsx}': {
        branches: 85,
        functions: 90,
        lines: 90,
        statements: 90,
      },
      // Custom hooks - testable with renderHook pattern
      './hooks/**/*.{ts,tsx}': {
        branches: 80,
        functions: 85,
        lines: 85,
        statements: 85,
      },
      // Canvas components - maintain existing good coverage (73% baseline)
      './components/canvas/**/*.{ts,tsx}': {
        branches: 80,
        functions: 85,
        lines: 85,
        statements: 85,
      },
      // UI components - standard component testing
      './components/ui/**/*.{ts,tsx}': {
        branches: 75,
        functions: 80,
        lines: 80,
        statements: 80,
      },
      // Integration components - graduated rollout complete (70% -> 80%)
      './components/integrations/**/*.{ts,tsx}': {
        branches: 70,
        functions: 75,
        lines: 80,  // Raised from 70%
        statements: 75,
      },
      // Next.js pages
      './pages/**/*.{ts,tsx}': {
        branches: 75,
        functions: 75,
        lines: 80,
        statements: 75,
      },
    };
  },
  moduleFileExtensions: ["ts", "tsx", "js", "jsx"],
  transformIgnorePatterns: [
    // jose ships ESM-only (next-auth dep tree); transform next-auth + jose so
    // next-auth-importing tests (pages/api/meeting_attendance_status) collect.
    "node_modules/(?!(chakra-ui|@chakra-ui|@emotion|@mui|@tauri-apps|got|msw|@mswjs|@mswjs/interceptors|axios|jose|next-auth))"
  ],

  // Performance optimizations (Phase 134-11)
  maxWorkers: '50%', // Use half of available CPU cores for parallel execution
  cache: true, // Enable Jest cache (default: true, ensure not disabled)
  clearMocks: true, // Clear mocks automatically between tests
  resetMocks: true, // Reset mocks automatically between tests
  restoreMocks: true, // Restore mocks automatically between tests

  // Reduce test overhead
  testTimeout: 30000, // Increased from 10s for async operations (Phase 299-03)
  bail: false, // Don't stop on first failure (default)

  moduleNameMapper: {
    // BEFORE the @/(.*) catch-all: the real module uses webpack's
    // new URL(..., import.meta.url), which ts-jest's CJS transform
    // can't parse — tests get the fake-worker stub instead.
    "^@/lib/pdf-worker-src$": "<rootDir>/tests/mocks/pdf-worker-src.ts",
    "^@/(.*)$": "<rootDir>/$1",
    "^@pages/(.*)$": "<rootDir>/pages/$1",
    "^@layouts/(.*)$": "<rootDir>/layouts/$1",
    "^@components/(.*)$": "<rootDir>/components/$1",
    // Dual path mapping for @lib/* - root lib/ and src/lib/
    "^@lib/src/(.*)$": "<rootDir>/src/lib/$1",
    "^@lib/(.*)$": "<rootDir>/lib/$1",
    "^@hooks/(.*)$": "<rootDir>/hooks/$1",
    "^@atom/test-utils(.*)$": "<rootDir>/shared/test-utils$1",
    "^@atom/property-tests(.*)$": "<rootDir>/shared/property-tests$1",
    // Additional path mappings from tsconfig.json (Phase 299-02)
    "^@config/(.*)$": "<rootDir>/config/$1",
    "^@assets/(.*)$": "<rootDir>/public/assets/$1",
    "^@models$": "<rootDir>/src/models",
    "^@styles/(.*)$": "<rootDir>/styles/$1",
    "^@shared/(.*)$": "<rootDir>/src/ui-shared/$1",
    "^@shared-components/(.*)$": "<rootDir>/src/ui-shared/components/$1",
    "^@shared-hooks/(.*)$": "<rootDir>/src/ui-shared/hooks/$1",
    "^@shared-services/(.*)$": "<rootDir>/src/services/$1",
    "^@shared-ai/(.*)$": "<rootDir>/src/services/ai/$1",
    "^@shared-integrations/(.*)$": "<rootDir>/src/services/integrations/$1",
    "^@shared-workflows/(.*)$": "<rootDir>/src/services/workflows/$1",
    "^@shared-utils/(.*)$": "<rootDir>/src/services/utils/$1",
    "^@/orchestration/(.*)$": "<rootDir>/src/orchestration/$1",
    "^@/llm/(.*)$": "<rootDir>/src/llm/$1",
    "^@/utils/(.*)$": "<rootDir>/src/utils/$1",
    "^@/hooks/(.*)$": "<rootDir>/hooks/$1",
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
  },

  // Property test results output (Phase 147-03)
  // Use --json flag for property tests: npm test -- shared-invariants --ci --json --outputFile=coverage/jest-frontend-property-results.json
  reporters: ['default'],

  // Retry Configuration for Flaky Test Detection (Phase 151-02)
  // Used by scripts/jest-retry-wrapper.js for multi-run verification
  // See: .planning/phases/151-quality-infrastructure-reliability/151-RESEARCH.md
  // NOTE: jest-circus retry options commented out - not currently supported
  // testRunner: 'jest-circus',
  // retryTimeoutMs: 30000,
  // maxRetries: 3,

  // Export retry config for wrapper script (unused)
  // module.exports.retryConfig = {
  //   timeoutMs: 30000,
  //   maxAttempts: 3,
  //   delayMs: 1000,
  // };
};