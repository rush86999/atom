module.exports = {
  testEnvironment: "node",
  roots: ["<rootDir>/src", "<rootDir>/tests"],
  testMatch: ["**/*.test.ts", "**/*.spec.ts"],
  transform: {
    "^.+\\.(t|j)sx?$": "ts-jest",
  },
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
  collectCoverageFrom: [
    "src/**/*.{ts,js}",
    "!src/**/*.d.ts",
    "!src/**/*.test.ts",
    "!src/**/*.spec.ts",
  ],
  coverageDirectory: "coverage",
  coverageReporters: ["text", "lcov", "html"],
  moduleFileExtensions: ["ts", "js", "json"],
  testPathIgnorePatterns: [
    "/node_modules/",
    "/dist/",
    "/.venv/",
    "/.vscode/",
    "/.github/",
    "/.pytest_cache/",
    "/coverage/",
    "/logs/",
    "/terraform/",
    "/deployment/",
  ],
  globals: {
    "ts-jest": {
      tsconfig: "tsconfig.json",
      diagnostics: {
        warnOnly: true,
      },
    },
  },
};
