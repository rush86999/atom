module.exports = {
  testEnvironment: "jsdom",
  setupFiles: ["<rootDir>/tests/polyfills.ts"],
  setupFilesAfterEnv: ["<rootDir>/tests/setup.ts"],
  transform: {
    "^.+\\.(ts|tsx)$": "ts-jest",
    "^.+\\.(js|jsx)$": "babel-jest",
  },
  preset: "ts-jest",
  testMatch: [
    "<rootDir>/tests/**/*.test.(ts|tsx|js)",
    "<rootDir>/components/**/__tests__/**/*.test.(ts|tsx|js)",
    "<rootDir>/components/**/__tests__/**/*.a11y.test.(ts|tsx)",
    "<rootDir>/lib/**/__tests__/**/*.test.(ts|tsx|js)",
    "<rootDir>/hooks/**/__tests__/**/*.test.(ts|tsx|js)"
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
  coverageThreshold: {
    // Global floor raised to 80% (Phase 130-05: graduated rollout complete)
    global: {
      branches: 75,
      functions: 80,
      lines: 80,
      statements: 75,
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
  },
  moduleFileExtensions: ["ts", "tsx", "js", "jsx"],
  transformIgnorePatterns: [
    "node_modules/(?!(chakra-ui|@chakra-ui|@emotion|@mui|@tauri-apps|got|msw|@mswjs|@mswjs/interceptors|axios))"
  ],

  // Performance optimizations (Phase 134-11)
  maxWorkers: '50%', // Use half of available CPU cores for parallel execution
  cache: true, // Enable Jest cache (default: true, ensure not disabled)
  clearMocks: true, // Clear mocks automatically between tests
  resetMocks: true, // Reset mocks automatically between tests
  restoreMocks: true, // Restore mocks automatically between tests

  // Reduce test overhead
  testTimeout: 10000, // Default timeout (10s)
  bail: false, // Don't stop on first failure (default)

  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
    "^@pages/(.*)$": "<rootDir>/pages/$1",
    "^@layouts/(.*)$": "<rootDir>/layouts/$1",
    "^@components/(.*)$": "<rootDir>/components/$1",
    "^@lib/(.*)$": "<rootDir>/lib/$1",
    "^@hooks/(.*)$": "<rootDir>/hooks/$1",
    "^@atom/test-utils(.*)$": "<rootDir>/shared/test-utils$1",
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
  },
};