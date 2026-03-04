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
    global: {
      branches: 80,
      functions: 80,
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