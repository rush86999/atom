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
    '!src/**/*.stories.ts'
  ],

  // Coverage reporters (JSON for CI/CD, LCOV for diff coverage, HTML for local viewing)
  coverageReporters: ['json', 'lcov', 'text', 'html'],

  // Coverage output directory
  coverageDirectory: 'coverage',

  // 80% coverage threshold for mobile app
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  }
};
