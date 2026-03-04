module.exports = {
  testEnvironment: "jsdom",
  setupFiles: ["<rootDir>/tests/polyfills.ts"],
  setupFilesAfterEnv: ["<rootDir>/tests/setup.ts"],
  transform: {
    "^.+\\.(js|jsx|ts|tsx)$": "babel-jest",
  },
  testMatch: [
    "<rootDir>/tests/**/*.test.(ts|tsx|js)",
    "<rootDir>/components/**/__tests__/**/*.test.(ts|tsx|js)",
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
    // Global floor - ramp to 80% by end of Phase 130
    global: {
      branches: 75,
      functions: 75,
      lines: 75,
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
    // Integration components - complex, external dependencies
    // Starting at 70%, ramp to 80% in Phase 131+
    './components/integrations/**/*.{ts,tsx}': {
      branches: 65,
      functions: 70,
      lines: 70,
      statements: 70,
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
    "node_modules/(?!(chakra-ui|@chakra-ui|@emotion|@mui|@tauri-apps|got|msw|@mswjs|@mswjs/interceptors))"
  ],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
    "^@pages/(.*)$": "<rootDir>/pages/$1",
    "^@layouts/(.*)$": "<rootDir>/layouts/$1",
    "^@components/(.*)$": "<rootDir>/components/$1",
    "^@lib/(.*)$": "<rootDir>/lib/$1",
    "^@hooks/(.*)$": "<rootDir>/hooks/$1",
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
  },
};