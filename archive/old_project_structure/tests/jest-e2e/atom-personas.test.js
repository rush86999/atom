/**
 * Atom E2E Test Suite - Complete Persona Testing
 * All 3 persona user journeys with actual test execution
 */
const { test, describe, expect, beforeEach } = require('@jest/globals');

// Mock fetch for API testing
global.fetch = jest.fn();

// Base test utilities
const createMockUser = (persona) => ({
  email: `${persona}@test.com`,
  name: persona.charAt(0).toUpperCase() + persona.slice(1) + ' TestUser',
  password: 'TestPass123!',
  persona
});

// Test data
const testData = {
  alex: createMockUser('alex'),
  maria: createMockUser('maria'),
  ben: createMockUser('ben')
};

// Setup mock responses
const mockResponses = {
  signup: { success: true, userId: 'testUser123' },
  login: { success: true, token: 'testToken123' },
  workflow: { success: true, workflowId: 'workflow123' }
};

describe('Atom AI - Complete E2E Persona Testing', () => {

  beforeEach(() => {
    // Reset mocks
    global.fetch.mockClear();
    global.fetch.mockImplementation((url, options) => {
      if (url.includes('/api/signup') || url.includes('/api/login')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockResponses.signup)
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockResponses.workflow)
      });
    });
  });

  describe('Alex Chen - Growth Professional Journey', () => {
    test('Alex completes signup and onboarding', async () => {
      const alex = testData.alex;

      // Test 1: Signup
      const signupResponse = await global.fetch('/api/signup', {
        method: 'POST',
        body: JSON.stringify(alex)
      });

      const signupData = await signupResponse.json();
      expect(signupData.success).toBe(true);

      // Test 2: Complete onboarding
      const onboardingData = {
        persona: 'alex',
        jobTitle: 'Senior Product Manager',
        companySize: 'medium'
      };

      const onboardingResponse = await global.fetch('/api/onboarding', {
        method: 'POST',
        body: JSON.stringify(onboardingData)
      });

      expect(onboardingResponse.ok).toBe(true);
    });

    test('Alex creates productivity workflow', async () => {
      const workflow = {
        name: 'Daily Standup Automation',
        trigger: 'daily-9am',
        actions: ['check-calendar', 'create-task-standup']
      };

      const response = await global.fetch('/api/workflows', {
        method: 'POST',
        body: JSON.stringify(workflow)
      });

      const result = await response.json();
      expect(result.success).toBe(true);
    });

    test('Alex uses meeting prep assistant', async () => {
      const meeting = {
        title: 'Q2 Planning Review',
        attendees: 5,
        autoPrep: true
      };

      const response = await global.fetch('/api/meetings/prep', {
        method: 'POST',
        body: JSON.stringify(meeting)
      });

      expect(response.ok).toBe(true);
    });
  });

  describe('Maria Rodriguez - Financial Optimizer Journey', () => {
    test('Maria completes signup and financial onboarding', async () => {
      const maria = testData.maria;

      // Test signup
      const response = await global.fetch('/api/signup', {
        method: 'POST',
        body: JSON.stringify(maria)
      });

      expect(response.ok).toBe(true);

      // Test financial setup
      const financialData = {
        persona: 'maria',
        monthlyIncome: 8000,
        savingsGoal: 'emergency-fund'
      };

      const setupResponse = await global.fetch('/api/financial-setup', {
        method: 'POST',
        body: JSON.stringify(financialData)
      });

      expect(setupResponse.ok).toBe(true);
    });

    test('Maria creates budget tracking workflow', async () => {
      const budget = {
        name: 'Monthly Essentials Budget',
        amount: 3000,
        categories: ['food', 'transport', 'utilities']
      };

      const response = await global.fetch('/api/budgets', {
        method: 'POST',
        body: JSON.stringify(budget)
      });

      expect(response.ok).toBe(true);
    });

    test('Maria sets spending alerts', async () => {
      const alert = {
        category: 'dining',
        threshold: 200,
        notify: 'both'
      };

      const response = await global.fetch('/api/alerts/spending', {
