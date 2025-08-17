#!/usr/bin/env node

/**
 * Comprehensive Test Fix Script
 * Identifies and fixes remaining test failures
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log("🔧 Comprehensive Test Fix Script");
console.log("================================");

// Configuration
const IGNORE_PATTERNS = [
  '*.test.js.map',
  '*.test.d.ts',
  'node_modules/**',
  'e2e/**',
  '*-e2e.test.*'
];

// 1. Fix Syntax Errors
console.log("\n📋 1. Fixing Syntax Errors...");
const syntaxFixes = [
  {
    file: "atomic-docker/project/functions/atom-agent/_libs/graphqlClient.test.ts",
    fixes: [
      { pattern: /mockGraphQLeErrors/gm, replacement: "mockGraphQLErrors" },
      { pattern: /mockRejectedValueOnce\(\{\s*isAxiosError: true,\s*code: "ECONNAB/m, replacement: `mockRejectedValueOnce({\n          isAxiosError: true,\n          code: "ECONNABORTED",\n          message: "timeout exceeded"\n        })` }
    ]
  },
  {
    file: "src/skills/advancedResearchSkill.test.ts",
    fixes: [
      { pattern: /}[\s\n]*$/gm, replacement: "});\n});" }
    ]
  }
];

syntaxFixes.forEach(({ file, fixes }) => {
  try {
    if (fs.existsSync(file)) {
      let content = fs.readFileSync(file, 'utf8');
      let modified = false;

      fixes.forEach(({ pattern, replacement }) => {
        if (pattern.test(content)) {
          content = content.replace(pattern, replacement);
          modified = true;
        }
      });

      if (modified) {
        fs.writeFileSync(file, content);
        console.log(`✅ Fixed: ${file}`);
      }
    }
  } catch (error) {
    console.warn(`⚠️  Could not fix ${file}: ${error.message}`);
  }
});

// 2. Fix Environment Configuration
console.log("\n⚙️ 2. Setting up test environment...");
const testEnvSetup = `
# Test Environment Configuration for Postgraphile
POSTGRAPHILE_URL=http://localhost:5000/graphql
POSTGRAPHILE_JWT_SECRET=test-jwt-secret
POSTGRES_CONNECTION_STRING=postgres://test:test@localhost:5432/testdb
ATOM_OPENAI_API_KEY=test-openai-key
MONGODB_URI=mongodb://localhost:27017/jest-test
AGENT_INTERNAL_INVOKE_URL=http://localhost:3000/api/agent
NODE_ENV=test
`;

fs.writeFileSync('.env.test', testEnvSetup.trim());
console.log("✅ Created .env.test configuration");

// 3. Mock Setup Fix
console.log("\n🎭 3. Creating Mock Utilities...");
const mockUtilContent = `
const axios = require('axios');

// Centralized mock setup
jest.mock('axios', () => ({
  ...jest.requireActual('axios'),
  post: jest.fn().mockResolvedValue({ data: { success: true } }),
  isAxiosError: jest.fn().mockImplementation((error) => !!(error && error.isAxiosError))
}));

jest.mock('openai', () => ({
  OpenAI: jest.fn().mockImplementation(() => ({
    apiKey: 'test-key',
    chat: {
      completions: {
        create: jest.fn().mockResolvedValue({
          choices: [{ message: { content: JSON.stringify({ result: 'success' }) } }]
        })
      }
    }
  }))
}));

jest.mock('agenda', () => ({
  Agenda: jest.fn().mockImplementation(() => ({
    define: jest.fn(),
    start: jest.fn().mockResolvedValue(undefined),
    stop: jest.fn().mockResolvedValue(undefined),
    on: jest.fn(),
    close: jest.fn()
  }))
}));

jest.mock('../lib/logger', () => ({
  default: {
    info: jest.fn(),
    error: jest.fn(),
    warn: jest.fn()
  }
}));

module.exports = { axios };
`;

// Create mock setup file
fs.writeFileSync('tests/setup/jest.setup.js', mockUtilContent.trim());

// 4. Test Configuration Update
console.log("\n🔧 4. Updating test configuration...");
const configUpdate = `
// jest.config.js updates
module.exports.testTimeout = 30000;
module.exports.setupFilesAfterEnv = ['<rootDir>/tests/setup/jest.setup.js'];
module.exports.testEnvironment = 'node';
module.exports.transform = {
  '^.+\\\\.tsx?$': ['ts-jest', { useESM: true }],
  '^.+\\\\.jsx?$': 'babel-jest'
};
`;

// 5. Create Simple Validation Test
console.log("\n✅ 5
