module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/src', '<rootDir>/atomic-docker/project/functions', '<rootDir>/atomic-docker/project/functions/_libs', '<rootDir>/atomic-docker/project/functions/atom-agent/_libs'],
  testMatch: ['**/*.test.ts'],
  transform: {
    '^.+\\.tsx?$': 'ts-jest',
    '^.+\\.jsx?$': 'babel-jest',
  },
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
    '^../_libs/crypto$': '<rootDir>/atomic-docker/project/functions/_libs/crypto.ts',
    '^../_libs/graphqlClient$': '<rootDir>/atomic-docker/project/functions/atom-agent/_libs/graphqlClient.ts',
    '^atomic-docker/project/functions/atom-agent/skills/trello$': '<rootDir>/atomic-docker/project/functions/atom-agent/skills/trello.ts',
  },
};
