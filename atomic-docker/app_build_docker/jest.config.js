const nextJest = require('next/jest');

// Provide the path to your Next.js app to load next.config.js and .env files in your test environment
const createJestConfig = nextJest({
  dir: './',
});

// Add any custom config to be passed to Jest
const customJestConfig = {
  testEnvironment: 'jest-environment-jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleDirectories: ['node_modules', '<rootDir>/'],
  moduleNameMapper: {
    // Handle module aliases configured in tsconfig.json
    '^@components/(.*)$': '<rootDir>/components/$1',
    '^@layouts/(.*)$': '<rootDir>/layouts/$1',
    '^@lib/(.*)$': '<rootDir>/lib/$1',
    '^@styles/(.*)$': '<rootDir>/styles/$1',
    '^@pages/(.*)$': '<rootDir>/pages/$1',
    '^@contexts/(.*)$': '<rootDir>/contexts/$1',
    '^@config/(.*)$': '<rootDir>/config/$1',
    // Force module resolution for lodash to the project's node_modules.
    // This can help resolve issues with multiple versions of lodash.
    '^lodash/(.*)$': '<rootDir>/node_modules/lodash/$1',
  },
  testPathIgnorePatterns: ['<rootDir>/node_modules/', '<rootDir>/.next/'],
  transform: {
    // Use babel-jest to transpile tests with the next/babel preset
    // https://jestjs.io/docs/configuration#transform-objectstring-pathtotransformer--pathtotransformer-object
    '^.+\\.(js|jsx|ts|tsx)$': ['babel-jest', { presets: ['next/babel'] }],
  },
  transformIgnorePatterns: [
    '/node_modules/',
    '^.+\\.module\\.(css|sass|scss)$',
  ],
};

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
module.exports = createJestConfig(customJestConfig);
