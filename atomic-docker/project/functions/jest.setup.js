// Jest setup for comprehensive E2E testing
process.env.NODE_ENV = 'test';
process.env.JWT_SECRET = 'test-jwt-secret-key-for-e2e-testing';
process.env.DATABASE_URL = process.env.TEST_DATABASE_URL || 'sqlite://:memory:';
process.env.OPENAI_API_KEY = process.env.OPENAI_API_KEY || 'sk-test-key-for-e2e';
process.env.PORT = process.env.TEST_PORT || '3001';
process.env.MOCK_EXTERNAL_APIS = 'true';

// Increase timeout for API calls
jest.setTimeout(30000);

// Global test utilities
global.console = {
  ...console,
  // Uncomment to suppress logs during tests
  // log: jest.fn(),
  // debug: jest.fn(),
  // info: jest.fn(),
  // warn: jest.fn(),
  // error: console.error,
};

// Mock environment variables for external services
process.env.GOOGLE_CLIENT_ID = 'test-google-client-id';
process.env.GOOGLE_CLIENT_SECRET = 'test-google-client-secret';
process.env.LINKEDIN_CLIENT_ID = 'test-linkedin-client-id';
process.env.LINKEDIN_CLIENT_SECRET = 'test-linkedin-client-secret';
process.env.SLACK_CLIENT_ID = 'test-slack-client-id';
process.env.SLACK_CLIENT_SECRET = 'test-slack-client-secret';

// Setup file cleanup
afterAll(async () => {
  // Clean up test files if any were created
  try {
    const fs = require('fs');
    const path = require('path');
    const testFiles = [
      path.join(__dirname, 'test-db.sqlite'),
      path.join(__dirname, 'test-uploads')
    ];

    testFiles.forEach(file => {
      if (fs.existsSync(file)) {
        if (fs.lstatSync(file).isDirectory()) {
          fs.rmSync(file, { recursive: true });
        } else {
          fs.unlinkSync(file);
        }
      }
    });
  } catch (error) {
    console.warn('Cleanup warning:', error.message);
  }
});
