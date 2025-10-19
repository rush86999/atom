module.exports = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/tests/setup.ts"],
  transform: {
    "^.+\\.(js|jsx|ts|tsx)$": "babel-jest",
  },
  testMatch: ["<rootDir>/tests/**/*.test.(ts|tsx)"],
  collectCoverageFrom: [
    "components/**/*.{ts,tsx}",
    "pages/**/*.{ts,tsx}",
    "!**/*.d.ts",
    "!**/node_modules/**",
  ],
  moduleFileExtensions: ["ts", "tsx", "js", "jsx"],
  transformIgnorePatterns: ["node_modules/(?!(chakra-ui|@chakra-ui)/)"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
  },
};
