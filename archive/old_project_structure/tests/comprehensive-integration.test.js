/**
 * Comprehensive Integration Test Suite for Atom AI Assistant
 * Tests all personas (Alex, Maria, Ben) with complete user journeys
 * Includes authentication, workflows, budgets, automation, and cross-service integration
 */

const { test, describe, expect, beforeEach, afterEach } = require('@jest/globals');
const axios = require('axios');
const { WebSocket } = require('ws');

// Test configuration
const TEST_CONFIG = {
  baseUrl: process.env.TEST_BASE_URL || 'http://localhost:3000',
  apiUrl: process.env.TEST_API_URL || 'http://localhost:5000',
  timeout: 15000,
  retries: 3,
  headless: process.env.CI === 'true'
};

// Test data factories
const createTestUser = (persona, index = 0) => ({
  email: `${persona}.test${index}@example.com`,
  password: `SecurePass123!${index}`,
  name: `${persona.charAt(0).toUpperCase() + persona.slice(1)} TestUser${index}`,
  persona: persona
});

const createWorkflow = (type, persona) => {
  const baseWorkflows = {
    alex: {
      name: 'Daily Productivity Automation',
      description: 'Automates daily standup and task management',
      triggers: ['daily-9am', 'meeting-reminder'],
      actions: ['check-calendar', 'create-standup-notes', 'update-task-list']
    },
    maria: {
      name: 'Monthly Budget Tracking',
      description: 'Tracks monthly expenses and savings goals',
      triggers: ['monthly-1st', 'spending-alert'],
      actions: ['analyze-spending', 'update-budget', 'send-alerts']
    },
    ben: {
      name: 'Business Automation Suite',
      description: 'Automates client communication and project tracking',
      triggers: ['new-client', 'project-deadline'],
      actions: ['send-welcome-email', 'create-project-board', 'schedule-followup']
    }
  };
  return { ...baseWorkflows[persona], type };
};

// Mock data for API responses
const mockResponses = {
  auth: {
    signup: { success: true, userId: 'test-user-123', token: 'test-jwt-token' },
    login: { success: true, token: 'test-jwt-token', user: { name: 'Test User', persona: 'alex' } }
  },
  workflows: {
    create: { success: true, workflowId: 'workflow-123', message: 'Workflow created successfully' },
    list: { success: true, workflows: [] }
  },
  budgets: {
    create: { success: true, budgetId: 'budget-123', message: 'Budget created successfully' },
    analyze: { success: true, analysis: { monthlyIncome: 8000, recommendedBudget: 3000 } }
  }
};

// Test utilities
class IntegrationTestHelper {
  constructor() {
    this.authToken = null;
    this.testUsers = {
      alex: createTestUser('alex', 1),
      maria: createTestUser('maria', 1),
      ben: createTestUser('ben', 1)
    };
  }

  async makeRequest(method, endpoint, data = null, options = {}) {
    const url = `${TEST_CONFIG.baseUrl}${endpoint}`;
    const config = {
      method,
      url,
      timeout: TEST_CONFIG.timeout,
      headers: {
        'Content-Type': 'application/json',
        ...(this.authToken && { Authorization: `Bearer ${this.authToken}` }),
        ...options.headers
      },
      validateStatus: () => true // Don't throw on error status codes
    };

    if (data) {
      config.data = data;
    }

    try {
      const response = await axios(config);
      return response;
    } catch (error) {
      throw new Error(`API request failed: ${error.message}`);
    }
  }

  async healthCheck() {
    const response = await this.makeRequest('GET', '/api/health');
    return response.status === 200;
  }

  async waitForService(retries = 3, delay = 2000) {
    for (let i = 0; i < retries; i++) {
      try {
        if (await this.healthCheck()) {
          return true;
        }
      } catch (error) {
        // Service not ready yet
      }
      await new Promise(resolve => setTimeout(resolve, delay));
    }
    throw new Error('Service not available after multiple retries');
  }
}

describe('Atom AI - Comprehensive Integration Test Suite', () => {
  const helper = new IntegrationTestHelper();

  beforeAll(async () => {
    console.log('🚀 Setting up integration test environment...');
    await helper.waitForService();
    console.log('✅ Test environment ready');
  });

  afterEach(async () => {
    // Clear auth token between tests
    helper.authToken = null;
  });

  describe('Environment Validation', () => {
    test('Service health check should pass', async () => {
      const response = await helper.makeRequest('GET', '/api/health');
      expect(response.status).toBeLessThan(400);
      expect(response.data).toHaveProperty('status');
    });

    test('Database connection should be healthy', async () => {
      const response = await helper.makeRequest('GET', '/api/health/db');
      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('connected');
    });

    test('Authentication service should be available', async () => {
      const response = await helper.makeRequest('GET', '/api/auth/health');
      expect(response.status).toBeLessThan(500);
    });
  });

  describe('Alex Chen - Growth Professional Journey', () => {
    const alexData = helper.testUsers.alex;

    test('Alex should complete signup and onboarding', async () => {
      // Signup
      const signupResponse = await helper.makeRequest('POST', '/api/auth/signup', {
        email: alexData.email,
        password: alexData.password,
        name: alexData.name,
        persona: alexData.persona
      });

      expect(signupResponse.status).toBe(200);
      expect(signupResponse.data).toHaveProperty('success', true);
      expect(signupResponse.data).toHaveProperty('token');

      helper.authToken = signupResponse.data.token;

      // Complete onboarding
      const onboardingResponse = await helper.makeRequest('POST', '/api/onboarding', {
        jobTitle: 'Senior Product Manager',
        companySize: 'medium',
        goals: ['productivity', 'automation']
      });

      expect(onboardingResponse.status).toBe(200);
      expect(onboardingResponse.data).toHaveProperty('completed', true);
    });

    test('Alex should create productivity workflow', async () => {
      await helper.makeRequest('POST', '/api/auth/login', {
        email: alexData.email,
        password: alexData.password
      });

      const workflow = createWorkflow('productivity', 'alex');
      const response = await helper.makeRequest('POST', '/api/workflows', workflow);

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('success', true);
      expect(response.data).toHaveProperty('workflowId');
    });

    test('Alex should manage meeting preparations', async () => {
      await helper.makeRequest('POST', '/api/auth/login', {
        email: alexData.email,
        password: alexData.password
      });

      const meetingData = {
        title: 'Q2 Planning Review',
        attendees: 5,
        duration: 60,
        autoPrep: true
      };

      const response = await helper.makeRequest('POST', '/api/meetings/prep', meetingData);
      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('prepared', true);
    });

    test('Alex should retrieve workflow analytics', async () => {
      await helper.makeRequest('POST', '/api/auth/login', {
        email: alexData.email,
        password: alexData.password
      });

      const response = await helper.makeRequest('GET', '/api/analytics/workflows');
      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('workflows');
      expect(Array.isArray(response.data.workflows)).toBe(true);
    });
  });

  describe('Maria Rodriguez - Financial Optimizer Journey', () => {
    const mariaData = helper.testUsers.maria;

    test('Maria should complete financial signup', async () => {
      const signupResponse = await helper.makeRequest('POST', '/api/auth/signup', {
        email: mariaData.email,
        password: mariaData.password,
        name: mariaData.name,
        persona: mariaData.persona
      });

      expect(signupResponse.status).toBe(200);
      helper.authToken = signupResponse.data.token;

      // Financial setup
      const financialResponse = await helper.makeRequest('POST', '/api/financial-setup', {
        monthlyIncome: 8000,
        monthlyExpenses: 4000,
        savingsGoal: 'emergency-fund',
        riskTolerance: 'moderate'
      });

      expect(financialResponse.status).toBe(200);
      expect(financialResponse.data).toHaveProperty('planCreated', true);
    });

    test('Maria should create budget tracking workflow', async () => {
      await helper.makeRequest('POST', '/api/auth/login', {
        email: mariaData.email,
        password: mariaData.password
      });

      const budgetData = {
        name: 'Monthly Essentials Budget',
        amount: 3000,
        categories: ['groceries', 'transportation', 'utilities', 'dining'],
        alerts: true,
        alertThreshold: 0.8
      };

      const response = await helper.makeRequest('POST', '/api/budgets', budgetData);
      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('success', true);
    });

    test('Maria should analyze spending patterns', async () => {
      await helper.makeRequest('POST', '/api/auth/login', {
        email: mariaData.email,
        password: mariaData.password
      });

      const spendingData = {
        month: '2024-01',
        categories: ['groceries', 'dining', 'entertainment'],
        amount: 1500
      };

      const response = await helper.makeRequest('POST', '/api/analytics/spending', spendingData);
      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('analysis');
      expect(response.data.analysis).toHaveProperty('recommendations');
    });

    test('Maria should set up savings goals', async () => {
      await helper.makeRequest('POST', '/api/auth/login', {
        email: mariaData.email,
        password: mariaData.password
      });

      const goalsData = {
        emergencyFund: 10000,
        retirement: 500000,
        shortTermGoals: ['vacation', 'new-laptop'],
        monthlyContribution: 1000
      };

      const response = await helper.makeRequest('POST', '/api/goals/savings', goalsData);
      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('goalsSet', true);
    });
  });

  describe('Ben Carter - Solopreneur Journey', () => {
    const benData = helper.testUsers.ben;

    test('Ben should complete business signup', async () => {
      const signupResponse = await helper.makeRequest('POST', '/api/auth/signup', {
        email: benData.email,
        password: benData.password,
        name: benData.name,
        persona: benData.persona
      });

      expect(signupResponse.status).toBe(200);
      helper.authToken = signupResponse.data.token;

      // Business setup
      const businessResponse = await helper.makeRequest('POST', '/api/business-setup', {
        businessName: 'TechStartup LLC',
        businessType: 'technology',
        revenue: 120000,
        clients: 5,
        automationNeeds: ['client-communication', 'project-management']
      });

      expect(businessResponse.status).toBe(200);
      expect(businessResponse.data).toHaveProperty('setupComplete', true);
    });

    test('Ben should create client automation workflow', async () => {
      await helper.makeRequest('POST', '/api/auth/login', {
        email: benData.email,
        password: benData.password
      });

      const automationData = {
        name: 'Client Onboarding Automation',
        description: 'Automates new client welcome and setup process',
        triggers: ['new-client-signup'],
        actions: [
          'send-welcome-email',
          'create-project-folder',
          'schedule-kickoff-call',
          'setup-tracking'
        ],
        conditions: ['client-type=premium']
      };

      const response = await helper.makeRequest('POST', '/api/automation/workflows', automationData);
      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('workflowId');
    });

    test('Ben should manage project timelines', async () => {
      await helper.makeRequest('POST', '/api/auth/login', {
        email: benData.email,
        password: benData.password
      });

      const projectData = {
        name: 'Website Redesign',
        deadline: '2024-03-15',
        milestones: [
          { name: 'Design Approval', date: '2024-02-15' },
          { name: 'Development Complete', date: '2024-03-01' }
        ],
        client: 'Acme Corp'
      };

      const response = await helper.makeRequest('POST', '/api/projects/timeline', projectData);
      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('timelineCreated', true);
    });

    test('Ben should generate business reports', async () => {
      await helper.makeRequest('POST', '/api/auth/login', {
        email: benData.email,
        password: benData.password
      });

      const reportData = {
        period: 'last-quarter',
        metrics: ['revenue', 'clients', 'projects', 'profitability'],
        format: 'detailed'
      };

      const response = await helper.makeRequest('POST', '/api/reports/business', reportData);
      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('report');
      expect(response.data.report).toHaveProperty('summary');
    });
  });

  describe('Cross-Service Integration Tests', () => {
    test('Authentication should work across all services', async () => {
      const loginResponse = await helper.makeRequest('POST', '/api/auth/login', {
        email: helper.testUsers.alex.email,
        password: helper.testUsers.alex.password
      });

      expect(loginResponse.status).toBe(200);
      const token = loginResponse.data.token;

      // Test token works with different services
      const services = ['/api/workflows', '/api/budgets', '/api/automation'];

      for (const service of services) {
        const response = await helper.makeRequest('GET', service, null, {
          headers: { Authorization: `Bearer ${token}` }
        });
        expect(response.status).not.toBe(401); // Should not be unauthorized
      }
    });

    test('Data should persist across user sessions', async () => {
      // Create workflow as Alex
      await helper.makeRequest('POST', '/api/auth/login', {
        email: helper.testUsers.alex.email,
        password: helper.testUsers.alex.password
      });

      const workflow = createWorkflow('productivity', 'alex');
      const createResponse = await helper.makeRequest('POST', '/api/workflows', workflow);
      const workflowId = createResponse.data.workflowId;

      // Log out and log back in
      helper.authToken = null;
      await helper.makeRequest('POST', '/api/auth/login', {
        email: helper.testUsers.alex.email,
        password: helper.testUsers.alex.password
      });

      // Should be able to retrieve the workflow
      const getResponse = await helper.makeRequest('GET', `/api/workflows/${workflowId}`);
      expect(getResponse.status).toBe(200);
      expect(getResponse.data).toHaveProperty('id', workflowId);
    });

    test('Error handling should be consistent across APIs', async () => {
      const invalidRequests = [
        { endpoint: '/api/auth/login', data: { email: 'invalid', password: 'wrong' } },
        { endpoint: '/api/workflows', data: {} },
        { endpoint: '/api/budgets', data: { invalid: 'data' } }
      ];

      for (const request of invalidRequests) {
        const response = await helper.makeRequest('POST', request.endpoint, request.data);
        expect(response.status).toBeGreaterThanOrEqual(400);
        expect(response.data).toHaveProperty('error');
        expect(response.data.error).toHaveProperty('message');
      }
    });
  });

  describe('Performance and Reliability Tests', () => {
    test('API responses should be within acceptable time limits', async () => {
      const endpoints = [
        '/api/health',
        '/api/auth/health',
        '/api/workflows',
        '/api/budgets'
      ];

      const maxResponseTime = 2000; // 2 seconds max

      for (const endpoint of endpoints) {
        const start = Date.now();
        const response = await helper.makeRequest('GET', endpoint);
        const duration = Date.now() - start;

        expect(response.status).toBeLessThan(500);
        expect(duration).toBeLessThan(maxResponseTime);
      }
    });

    test('Service should handle concurrent requests', async () => {
      const requests = Array(5).fill().map(() =>
        helper.makeRequest('GET', '/api/health')
      );

      const responses = await Promise.all(requests);
      responses.forEach(response => {
        expect(response.status).toBeLessThan(400);
      });
    });

    test('Database connections should be properly managed', async () => {
      // Make multiple sequential requests to test connection pooling
      for (let i = 0; i < 10; i++) {
        const response = await helper.makeRequest('GET', '/api/health/db');
        expect(response.status).toBe(200);
      }
    });
  });
});

// Export for use in other test files
module.exports = {
  IntegrationTestHelper,
  createTestUser,
  createWorkflow,
  TEST_CONFIG
};
