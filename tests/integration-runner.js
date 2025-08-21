#!/usr/bin/env node

/**
 * Complete Desktop Integration Test Suite
 * Tests Tauri Backend + Web Backend + Desktop Frontend Integration
 * Identifies and fixes critical integration bugs
 */

const { spawn, exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');
const { WebSocket } = require('ws');

const execAsync = promisify(exec);

class IntegrationTestRunner {
  constructor() {
    this.testResults = {
      summary: { total: 0, passed: 0, failed: 0, warnings: 0 },
      categories: {},
      bugs: []
    };
    this.startTime = Date.now();
  }

  async log(level, message, data = {}) {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] ${level}: ${message}\n`;

    if (data && Object.keys(data).length > 0) {
      logEntry += `${JSON.stringify(data, null, 2)}\n`;
    }

    await fs.appendFile(path.join(__dirname, 'integration-test-results.log'), logEntry);

    if (level === 'ERROR') {
      this.testResults.bugs.push({ timestamp, message, data });
    }
  }

  async assert(condition, message) {
    if (!condition) {
      throw new Error(message);
    }
  }

  async runTest(category, testName, testFunction) {
    this.testResults.summary.total++;
    console.log(`🧪 Running ${category} -> ${testName}`);

    try {
      const start = Date.now();
      const result = await testFunction();
      const duration = Date.now() - start;

      const testResult = {
        name: testName,
        status: 'PASSED',
        duration,
        details: result
      };

      this.testResults.summary.passed++;

      if (!this.testResults.categories[category]) {
        this.testResults.categories[category] = [];
      }
      this.testResults.categories[category].push(testResult);

      await this.log('SUCCESS', `${category}.${testName}`, testResult);
      console.log(`   ✅ ${testName} (${duration}ms)`);

    } catch (error) {
      const testResult = {
        name: testName,
        status: 'FAILED',
        error: error.message,
        stack: error.stack
      };

      this.testResults.summary.failed++;

      if (!this.testResults.categories[category]) {
        this.testResults.categories[category] = [];
      }
      this.testResults.categories[category].push(testResult);

      await this.log('ERROR', `${category}.${testName} FAILED`, { error: error.message, stack: error.stack });
      console.error(`   ❌ ${testName}: ${error.message}`);

      // Suggest fix
      this.suggestFix(category, testName, error);
    }
  }

  suggestFix(category, testName, error) {
    const fixes = {
      'web-backend': {
        'health_check': 'Check if backend is running on localhost:3000 and /api/health endpoint exists',
        'database_connection': 'Verify DATABASE_URL and ensure PostgreSQL is running'
      },
      'desktop-backend': {
        'settings_encryption': 'Check ENCRYPTION_KEY environment variable is 32 bytes long',
        'web_socket_connection': 'Verify NEXT_PUBLIC_AUDIO_PROCESSOR_URL is set and accessible'
      }
    };

    const fix = fixes[category]?.[testName];
    if (fix) {
      this.log('INFO', `Suggested fix for ${testName}`, { fix });
    }
  }

  // 1. Web Backend Integration Tests
  async testWebBackendIntegration() {
    const baseUrl = 'http://localhost:3000';

    await this.runTest('web-backend', 'health_check', async () => {
      const response = await axios.get(`${baseUrl}/api/health`, {
        timeout: 5000,
        validateStatus: () => true
      });
      await this.assert(response.status < 400, `Health check failed with status ${response.status}`);
      return { status: response.status, endpoint: '/api/health' };
    });

    await this.runTest('web-backend', 'database_connection', async () => {
      const response = await axios.post(`${baseUrl}/api/health/db`, {
        timeout: 10000,
        validateStatus: () => true
      });
      await this.assert(response.status === 200, `Database connection failed`);
      return response.data;
    });

    await this.runTest('web-backend', 'authentication_endpoints', async () => {
      const endpoints = [
        '/api/auth/health',
        '/api/auth/callback/google',
        '/api/auth/callback/linkedin'
