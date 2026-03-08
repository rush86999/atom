/**
 * Jest Configuration for Atom Mobile App
 *
 * This file configures Jest with:
 * - jest-expo preset for Expo SDK 50 compatibility
 * - 80% coverage threshold for mobile code
 * - Coverage collection from src/ directory
 * - Excludes type definitions and test files
 *
 * Coverage scripts:
 * - npm run test:coverage - Run tests with coverage report
 * - Coverage reports: coverage/ (JSON, LCOV, HTML)
 */

module.exports = {
  // Use Expo's Jest preset
  preset: 'jest-expo',

  // Setup files to run after test environment is installed
  setupFilesAfterEnv: ['./jest.setup.js'],

  // TransformIgnorePatterns for node_modules that need transformation
  transformIgnorePatterns: [
    'node_modules/(?!(jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?|@expo-google-fonts|react-navigation|@react-navigation|@unimodules|expo-modules|sentry-expo|native-base|react-native-webview|@react-native-clipboard|@react-native-community|@react-native-cookies|react-native-firebase|@react-native-async-storage|axios|@expo/config)/'
  ],

  // Module name mapper for shared utilities
  moduleNameMapper: {
    '^@atom/test-utils(.*)$': '<rootDir>/../frontend-nextjs/shared/test-utils$1',
    '^@atom/property-tests(.*)$': '<rootDir>/src/shared/property-tests$1',
  },

  // Test file patterns
  testMatch: [
    '**/__tests__/**/*.[jt]s?(x)',
    '**/?(*.)+(spec|test).[jt]s?(x)'
  ],

  // Coverage collection configuration
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/types/**',
    '!src/**/*.stories.tsx',
    '!src/**/*.stories.ts',
    // Platform-specific coverage
    'src/__tests__/platform-specific/ios/**/*.{ts,tsx}',
    'src/__tests__/platform-specific/android/**/*.{ts,tsx}',
    'src/__tests__/platform-specific/**/*.{ts,tsx}',
    // Platform-specific source files
    'src/screens/**/*.{ts,tsx}',
    'src/components/**/*.{ts,tsx}',
  ],

  // Coverage reporters (JSON for CI/CD, LCOV for diff coverage, HTML for local viewing)
  coverageReporters: ['json', 'lcov', 'text', 'html'],

  // Coverage output directory
  coverageDirectory: 'coverage',

  // Progressive coverage thresholds (Phase 153)
  // Mobile thresholds: 50% → 55% → 60% (lower due to React Native testing complexity)
  // New code: Always 80% regardless of phase
  get coverageThreshold() {
    const phase = process.env.COVERAGE_PHASE || 'phase_1';

    const thresholds = {
      phase_1: {
        branches: 50,
        functions: 50,
        lines: 50,
        statements: 50,
      },
      phase_2: {
        branches: 55,
        functions: 55,
        lines: 55,
        statements: 55,
      },
      phase_3: {
        branches: 60,
        functions: 60,
        lines: 60,
        statements: 60,
      },
    };

    return {
      global: thresholds[phase],
      // New code always requires 80% regardless of phase
      './src/**/*.{ts,tsx,js,jsx}': {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
      './src/__tests__/helpers/testUtils.ts': {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
      './src/__tests__/helpers/platformPermissions.test.ts': {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
    };
  },

  // Property test results output (Phase 147-03)
  // Use --json flag for property tests: npm test -- --ci --json --outputFile=coverage/jest-mobile-property-results.json
  reporters: ['default'],

  // Retry Configuration for Flaky Test Detection (Phase 151-02)
  // Used by scripts/jest-retry-wrapper.js for multi-run verification
  // See: .planning/phases/151-quality-infrastructure-reliability/151-RESEARCH.md
  testRunner: 'jest-circus', // Supports retry hooks (future enhancement)
  retryTimeoutMs: 30000, // 30s per retry attempt
  maxRetries: 3, // For jest-circus retry mechanism (if enabled later)
};

// Export retry config for wrapper script
module.exports.retryConfig = {
  timeoutMs: 30000,
  maxAttempts: 3,
  delayMs: 1000, // Delay between retries (for future use)
};
