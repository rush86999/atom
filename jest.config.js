module.exports = {
  testEnvironment: "node",
  preset: "ts-jest/presets/js-with-ts",
  roots: ["<rootDir>/src", "<rootDir>/atomic-docker/project/functions"],
  testMatch: [
    "**/__tests__/**/*.(test|spec).(js|jsx|ts|tsx)",
    "**/**/test*.{js,jsx,ts,tsx}",
    "**/**/*.{test,spec}.{js,jsx,ts,tsx}",
    "**/tests/**/*.(test|spec).(js|jsx|ts|tsx)",
    "!**/atomic-docker/project/functions/atom-agent/templates/**",
    "!**/features-apply/_libs/temp_tests/**",
    "!**/google-calendar-sync/_libs/event2VectorsWorker/test*.js",
  ],
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        useESM: true,
        tsconfig: {
          allowJs: true,
          esModuleInterop: true,
          module: "CommonJS",
          moduleResolution: "node",
          target: "ES2020",
        },
      },
    ],
    "^.+\\.jsx?$": "babel-jest",
  },
  extensionsToTreatAsEsm: [".ts", ".tsx"],
  transformIgnorePatterns: ["node_modules/(?!(module-to-transform)/)"],
  moduleNameMapper: {
    "^(\\.{1,2}/.*)\\.js$": "$1",
    "^../_libs/crypto$":
      "<rootDir>/atomic-docker/project/functions/_libs/crypto.ts",
    "^../_libs/graphqlClient$":
      "<rootDir>/atomic-docker/project/functions/atom-agent/_libs/graphqlClient.ts",
    "^atomic-docker/project/functions/atom-agent/skills/trello$":
      "<rootDir>/atomic-docker/project/functions/atom-agent/skills/trello.ts",
    "^@utils/(.*)$": "<rootDir>/atomic-docker/project/functions/_utils/$1",
  },
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node"],
  setupFilesAfterEnv: ["<rootDir>/tests/setup/jest.setup.js"],
  testTimeout: 60000,
  testPathIgnorePatterns: ["node_modules", "cdk.out", "tests/setup"],
};
