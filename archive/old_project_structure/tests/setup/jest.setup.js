const mongoose = require('mongoose');
const { execSync } = require('child_process');
const path = require('path');
require('dotenv').config();

// Global test timeout
jest.setTimeout(60000);

// Test configuration
global.TEST_CONFIG = {
  baseUrl: process.env.TEST_BASE_URL || 'http://localhost:3000',
  apiUrl: process.env.TEST_API_URL || 'http://localhost:5000',
  timeout: 30000,
  retries: 3,
  headless: process.env.CI === 'true'
};

// Global mock setup
beforeAll(async () => {
  console.log('🧪 Setting up E2E test environment...');
  // Ensure test database/clean slate
  await setupTestEnvironment();
});

afterAll(async () => {
  console.log('🧹 Cleaning up E2E test environment...');
  await cleanupTestEnvironment();
});

beforeEach(async () => {
  // Clear any stored state between tests
  await clearTestState();
});

async function setupTestEnvironment() {
  // This will be called before all tests run
  console.log('✅ Test environment configured');
}

async function cleanupTestEnvironment() {
  // Ensure proper cleanup
  console.log('✅ Test environment cleaned');
}

async function clearTestState() {
  // Reset any global state between tests
}

// Custom test matchers
expect.extend({
  toBeWithinRange(received, floor, ceiling) {
    const pass = received >= floor && received <= ceiling;
    return {
      message: () => `expected ${received} to be within range ${floor} - ${ceiling}`,
      pass,
    };
  },
});
