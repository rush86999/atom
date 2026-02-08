module.exports = {
  $schema: '@stryker-mutator/core/schema/stryker-schema.json',
  mutate: [
    'lib/crypto.ts',
    'lib/password-validator.ts',
    'lib/email.ts',
    'components/Agents/AgentManager.tsx',
    'components/Voice/VoiceCommands.tsx',
    'components/integrations/WhatsAppBusinessIntegration.tsx'
  ],
  testRunner: 'jest',
  jest: {
    projectType: 'custom',
    config: {
      // Use existing Jest configuration
      rootDir: '.',
      testEnvironment: 'jsdom',
      setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
      transform: {
        '^.+\\.(js|jsx|ts|tsx)$': 'babel-jest',
      },
      testMatch: [
        '<rootDir>/tests/**/*.test.(ts|tsx|js)',
        '<rootDir>/components/**/__tests__/*.test.(ts|tsx|js)',
        '<rootDir>/lib/**/__tests__/*.test.(ts|tsx|js)'
      ],
      moduleNameMapper: {
        '^@/(.*)$': '<rootDir>/$1',
        '^@pages/(.*)$': '<rootDir>/pages/$1',
        '^@layouts/(.*)$': '<rootDir>/layouts/$1',
        '^@components/(.*)$': '<rootDir>/components/$1',
        '^@lib/(.*)$': '<rootDir>/lib/$1',
        '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
      },
      moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx'],
    }
  },
  reporters: ['html', 'progress', 'clear-text'],
  htmlReporter: {
    baseDir: 'coverage-reports/mutation',
  },
  coverageAnalysis: 'perTest',
  thresholds: {
    high: 80,
    low: 60,
    break: null
  },
  timeouts: {
    // Increase timeout for mutation testing
    mutation: 60000,
    coverageAnalysis: 60000
  }
};
