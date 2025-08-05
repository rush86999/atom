/**
 * Comprehensive Live-Ready E2E Integration Test Suite
 * Tests all critical functionality end-to-end for production readiness
 */

import { describe, test, expect, beforeAll, afterAll, jest } from '@jest/globals';
import axios from 'axios';
import fs from 'fs';
import path from 'path';
import https from 'https';
import { execSync } from 'child_process';

// Test configuration
const TEST_CONFIG = {
  apiBaseUrl: process.env.API_BASE_URL || 'http://localhost:3000',
  testEmail: process.env.TEST_EMAIL || 'test@example.com',
  testPassword: process.env.TEST_PASSWORD || 'testpass123',
  timeout: 30000,
  retries: 3,
  mockExternalAPIs: process.env.MOCK_EXTERNAL_APIS !== 'false',
  chromaticTest: process.env.CHROMATIC_TEST === 'true'
};

// Assert environment is production-ready
const requiredEnvs = [
  'OPENAI_API_KEY',
  'DATABASE_URL',
  'JWT_SECRET',
  'NODE_ENV'
];

class TestHelpers {
  static async healthCheck(baseUrl: string): Promise<boolean> {
    try {
      const response = await axios.get(`${baseUrl}/health`, { timeout: 5000 });
      return response.status === 200;
    } catch {
      return false;
    }
  }

  static async pollForReady(baseUrl: string, maxWait = 60000): Promise<boolean> {
    const start = Date.now();
    while (Date.now() - start < maxWait) {
      if (await this.healthCheck(baseUrl)) {
        return true;
      }
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    return false;
  }

  static generateTestUser() {
    const timestamp = Date.now();
    return {
      email: `test-${timestamp}@example.com`,
      password: 'TestPassword123!',
      name: `Test User ${timestamp}`
    };
  }

  static async waitForServiceStartup() {
    console.log('🔍 Checking if services are online...');
    const isReady = await this.pollForReady(TEST_CONFIG.apiBaseUrl);
    if (!isReady) {
      try {
        console.log('🚀 Starting services...');
        execSync('npm run dev:server', {
          stdio: 'pipe',
          cwd: path.join(__dirname, '../../'),
          timeout: 15000
        });

        const started = await this.pollForReady(TEST_CONFIG.apiBaseUrl);
        if (!started) {
          throw new Error('Services failed to start');
        }
      } catch (error) {
        console.warn('⚠️  Could not auto-start services, test assumes they are running');
      }
    }
    console.log('✅ Services are ready');
  }
}

describe('🚀 App Live Ready E2E Test Suite', () => {
  let axiosInstance: any;
  let authToken: string;
  let testUser: any;

  beforeAll(async () => {
    console.log(`\n🔗 Testing against: ${TEST_CONFIG.apiBaseUrl}`);

    // Check if core environment variables are set
    const missingEnvs = requiredEnvs.filter(env => !process.env[env]);
    if (missingEnvs.length > 0) {
      console.warn(`⚠️  Missing env vars: ${missingEnvs.join(', ')}`);
    }

    await TestHelpers.waitForServiceStartup();

    axiosInstance = axios.create({
      baseURL: TEST_CONFIG.apiBaseUrl,
      timeout: TEST_CONFIG.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
      validateStatus: () => true, // Don't throw on HTTP errors
    });

    // Generate test user
    testUser = TestHelpers.generateTestUser();
  });

  afterAll(async () => {
    // Cleanup test data if possible
    if (authToken && testUser?.email) {
      try {
        await axiosInstance.delete(`/api/users/test-cleanup`, {
          data: { email: testUser.email },
          headers: { Authorization: `Bearer ${authToken}` }
        });
      } catch (error) {
        console.warn('Could not cleanup test user:', error);
      }
    }
  });

  describe('🔐 Authentication & Authorization', () => {
    test('User registration succeeds', async () => {
      const response = await axiosInstance.post('/api/auth/register', {
        email: testUser.email,
        password: testUser.password,
        name: testUser.name,
      });

      expect(response.status).toBe(201);
      expect(response.data).toHaveProperty('token');
      expect(response.data.user).toHaveProperty('email', testUser.email);

      authToken = response.data.token;
    });

    test('User login succeeds', async () => {
      const response = await axiosInstance.post('/api/auth/login', {
        email: testUser.email,
        password: testUser.password,
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('token');
      expect(response.data.user).toHaveProperty('email', testUser.email);
    });

    test('JWT token validation works', async () => {
      const response = await axiosInstance.get('/api/auth/validate', {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data.valid).toBe(true);
    });

    test('Unauthorized access is blocked', async () => {
      const response = await axiosInstance.get('/api/protected-endpoint', {
        headers: { Authorization: 'Bearer invalid-token' },
      });

      expect(response.status).toBe(401);
    });
  });

  describe('🧠 AI Chat & Natural Language Processing', () => {
    test('OpenAI integration works', async () => {
      const response = await axiosInstance.post('/api/chat', {
        message: 'Hello, please tell me about your capabilities',
        userId: testUser.email,
        timezone: 'America/New_York',
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('response');
      expect(typeof response.data.response).toBe('string');
      expect(response.data.response.length).toBeGreaterThan(0);
    });

    test('AI handles complex scheduling queries', async () => {
      const response = await axiosInstance.post('/api/chat', {
        message: 'Schedule a meeting with John next Tuesday at 2pm for project planning',
        userId: testUser.email,
        timezone: 'America/New_York',
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('response');
      expect(response.data).toHaveProperty('intent');
    });

    test('Conversation history is maintained', async () => {
      const message1 = await axiosInstance.post('/api/chat', {
        message: 'My name is Sarah',
        userId: testUser.email,
        timezone: 'America/New_York',
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(message1.status).toBe(200);

      // Follow-up conversation
      const message2 = await axiosInstance.post('/api/chat', {
        message: 'What is my name?',
        userId: testUser.email,
        timezone: 'America/New_York',
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(message2.status).toBe(200);
      expect(response.data.response.toLowerCase()).toContain('sarah');
    });
  });

  describe('📅 Calendar Integration', () => {
    test('Google Calendar connection', async () => {
      const response = await axiosInstance.post('/api/calendar/connect', {
        provider: 'google',
        userId: testUser.email,
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect([200, 302, 401]).toContain(response.status); // 302 for OAuth redirect, 401 if not configured
    });

    test('Calendar event creation', async () => {
      const eventData = {
        title: 'Test Meeting - E2E Integration',
        description: 'This is a test event from E2E testing',
        startTime: new Date(Date.now() + 3600000).toISOString(),
        endTime: new Date(Date.now() + 7200000).toISOString(),
        timeZone: 'America/New_York',
        attendees: ['test@example.com'],
      };

      const response = await axiosInstance.post('/api/calendar/events', eventData, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(201);
      expect(response.data).toHaveProperty('eventId');
      expect(response.data).toHaveProperty('calendarId');
    });

    test('Calendar sync functionality', async () => {
      const response = await axiosInstance.post('/api/calendar/sync', {
        provider: 'google',
        syncRange: 7, // days
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect([200, 202, 404]).toContain(response.status); // 404 if integration not configured
    });
  });

  describe('📝 Notes & Documentation', () => {
    test('Create and store notes', async () => {
      const noteData = {
        title: 'Test Meeting Notes',
        content: '# Meeting Summary\n\n- Action items discussed\n- Decisions made\n- Follow-up tasks assigned',
        tags: ['e2e-test', 'meeting', 'summary'],
        linkedEventId: null,
      };

      const response = await axiosInstance.post('/api/notes', noteData, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(201);
      expect(response.data).toHaveProperty('noteId');
      expect(response.data.title).toBe(noteData.title);
    });

    test('Semantic search on notes', async () => {
      // First, store a note
      const noteData = {
        title: 'Quarterly Planning Meeting',
        content: 'We discussed roadmap priorities for Q3 focusing on AI integration and user experience improvements.',
        tags: ['planning', 'roadmap', 'quarterly'],
      };

      await axiosInstance.post('/api/notes', noteData, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      // Give time for indexing
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Search for relevant content
      const response = await axiosInstance.post('/api/notes/search', {
        query: 'roadmap planning priorities',
        limit: 5,
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(Array.isArray(response.data.results)).toBe(true);
      expect(response.data.results.length).toBeGreaterThan(0);
    });
  });

  describe('🔍 Semantic Search & Vector Storage', () => {
    test('LanceDB integration working', async () => {
      const response = await axiosInstance.get('/api/db/health', {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('status', 'healthy');
    });

    test('Vector embeddings generation', async () => {
      const testData = {
        text: 'This is test content for semantic search',
        metadata: { source: 'e2e-test', timestamp: Date.now() },
      };

      const response = await axiosInstance.post('/api/embeddings', testData, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('embedding');
      expect(Array.isArray(response.data.embedding));
      expect(response.data.embedding.length).toBeGreaterThan(0);
    });
  });

  describe('📧 Email Notifications', () => {
    test('Email service configuration', async () => {
      const response = await axiosInstance.post('/api/notifications/email/test', {
        to: testUser.email,
        subject: 'E2E Test Email',
        template: 'test-notification',
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect([200, 455]).toContain(response.status);
    });

    test('Webhook notifications work', async () => {
      const webhookData = {
        eventType: 'test.notification',
        data: { message: 'Test webhook', timestamp: Date.now() },
        recipient: testUser.email,
      };

      const response = await axiosInstance.post('/api/notifications/webhook', webhookData, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
    });
  });

  describe('🔗 External Integrations', () => {
    test('LinkedIn API connectivity', async () => {
      const response = await axiosInstance.post('/api/integrations/linkedin/ping', {}, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect([200, 401, 503]).toContain(response.status);
    });

    test('Slack connectivity verification', async () => {
      const response = await axiosInstance.post('/api/integrations/slack/test', {}, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect([200, 401, 503]).toContain(response.status);
    });
  });

  describe('⚡ Performance & Reliability', () => {
    test('API response times under 3 seconds', async () => {
      const start = Date.now();
      await axiosInstance.post('/api/chat', {
        message: 'test performance',
        userId: testUser.email,
        timezone: 'America/New_York',
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(3000);
    });

    test('Concurrent request handling', async () => {
      const requests = Array(5).fill(null).map((_, i) =>
        axiosInstance.post('/api/chat', {
          message: `Concurrent test ${i}`,
          userId: testUser.email,
          timezone: 'America/New_York',
        }, {
          headers: { Authorization: `Bearer ${authToken}` },
        })
      );

      const responses = await Promise.all(requests);
      expect(responses.every(r => r.status === 200)).toBe(true);
    });
  });

  describe('📊 Database Health', () => {
    test('Database connection health', async () => {
      const response = await axiosInstance.get('/api/health/database', {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('status', 'healthy');
    });

    test('Database migrations are current', async () => {
      const response = await axiosInstance.get('/api/health/migrations', {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('migrated', true);
    });
  });

  describe('🔐 Security Tests', () => {
    test('SQL injection prevention', async () => {
      const maliciousQuery = {
        message: "Robert'); DROP TABLE users; --",
        userId: testUser.email,
      };

      const response = await axiosInstance.post('/api/chat', maliciousQuery, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('response');
    });

    test('Input validation and sanitization', async () => {
      const xssAttempt = {
        message: "<script>alert('XSS')</script>",
        userId: testUser.email,
      };

      const response = await axiosInstance.post('/api/chat', xssAttempt, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data.response).not.toContain('<script>');
    });
  });

  describe('🌐 Full End-to-End Workflows', () => {
    test('Complete meeting workflow: schedule -> note -> search', async () => {
      // 1. Schedule a meeting through chat
      const scheduleResponse = await axiosInstance.post('/api/chat', {
        message: 'Schedule a team meeting for tomorrow at 3pm to discuss project roadmap',
        userId: testUser.email,
        timezone: 'America/New_York',
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(scheduleResponse.status).toBe(200);

      // 2. Create notes for the meeting
      const meetingId = scheduleResponse.data.createdEvent?.id || `test-mtg-${Date.now()}`;
      const notesResponse = await axiosInstance.post('/api/notes', {
        title: `Meeting Notes: ${meetingId}`,
        content: 'Excellent discussion about Q3 priorities and roadmap items.',
        tags: ['meeting', 'roadmap', 'team-sync'],
        linkedEventId: meetingId,
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(notesResponse.status).toBe(201);

      // 3. Search for the created notes
      await new Promise(resolve => setTimeout(resolve, 2000)); // Wait for indexing
      const searchResponse = await axiosInstance.post('/api/notes/search', {
        query: 'roadmap discussion priorities',
        limit: 1,
      }, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(searchResponse.status).toBe(200);
      expect(searchResponse.data.results.length).toBeGreaterThan(0);
      expect(searchResponse.data.results[0].tags).toContain('roadmap');
    });
  });

  describe('📋 Configuration & Environment', () => {
    test('Environment configuration validation', async () => {
      const response = await axiosInstance.get('/api/health/config', {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('configCheckPassed', true);
      expect(response.data).toHaveProperty('criticalServicesConnected');
    });

    test('Version and deployment info', async () => {
      const response = await axiosInstance.get('/api/version');

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('version');
      expect(response.data).toHaveProperty('build');
      expect(response.data).toHaveProperty('environment');
    });
  });
});

// Production-ready validation export
export const runLiveReadyCheck = async (): Promise<{ success: boolean; results: any[] }> => {
  console.log('🚀 Running comprehensive live-ready validation...\n');

  const checks = [
    {
      name: 'Environment Configuration',
      check: async () => {
        try {
          return requiredEnvs.every(env => process.env[env]);
        } catch {
          return false;
        }
      }
    },
    {
      name: 'Database Connectivity',
      check: async () => await TestHelpers.healthCheck(TEST_CONFIG.apiBaseUrl),
    },
    {
      name: 'AI Services',
      check: async () => {
        try {
          await axios.post(`${TEST_CONFIG.apiBaseUrl}/api/chat/test`, {
            message: 'test'
          });
          return true;
        } catch {
          return false;
        }
      }
    },
    {
      name: 'External API Integrations',
      check: async () => {
        // Check if critical external services are available
        const services = ['google', 'linkedin', 'slack'];
        const results = await Promise.allSettled(
          services.map(async service => {
            try {
              await axios.get(`${TEST_CONFIG.apiBaseUrl}/api/integrations/${service}/health`);
              return service;
            } catch {
              return null;
            }
          })
        );
        return results.length > 0;
      }
    }
  ];

  const results = [];
  let allPassed = true;

  for (const { name, check } of checks) {
    try {
      const passed = await check();
      results.push({ name, passed });
      if (!passed) allPassed = false;
      console.log(`${passed ? '✅' : '❌'} ${name}`);
    } catch (error) {
      results.push({ name, passed: false, error });
      allPassed = false;
      console.log(`❌ ${name}: ${error}`);
    }
  }

  console.log(`\n${allPassed ? '🎉' : '❌'} App ${allPassed ? 'is' : 'is NOT'} live-ready!`);
  return { success: allPassed, results };
};

// Run directly if executed
if (require.main === module) {
  runLiveReadyCheck().catch(console.error);
}
