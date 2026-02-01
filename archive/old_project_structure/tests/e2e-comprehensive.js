#!/usr/bin/env node

/**
 * Comprehensive E2E Integration Test Suite
 * Tests Atom AI across Web + Desktop + Backend + Database
 * Identifies and documents bugs for immediate fixing
 */

const { spawn, exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');
const { WebSocket } = require('ws');

const execAsync = promisify(exec);

class AtomE2ETester {
  constructor() {
    this.config = {
      webUrl: 'http://localhost:3000',
      timeout: 30000,
      attempts: 3,
      logFile: 'e2e-results.log'
    };

    this.results = {
      summary: {
        total: 0,
        passed: 0,
        failed: 0,
        bugs: []
      },
      environment: [],
      webApp: [],
      desktopApp: [],
      backend: [],
      database: [],
      integration: []
    };
  }

  async log(level, message, data = {}) {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] ${level}: ${message} ${data.detail || ''}`.trim() + '\n';

    if (Object.keys(data).length > 1) {
      logEntry += JSON.stringify(data, null, 2) + '\n';
    }

    await fs.appendFile(path.join(__dirname, this.config.logFile), logEntry);

    const icons = { ERROR: '❌', SUCCESS: '✅', WARN: '⚠️', INFO: 'ℹ️' };
    console.log(`${icons[level] || ''} ${message}`);
  }

  async runTest(testName, testFn, category, fixSuggestion = null) {
    this.results.summary.total++;

    try {
      const result = await testFn();
      this.results.summary.passed++;
      this.results[category].push({ name: testName, status: 'PASSED', result });
      return true;

    } catch (error) {
      const testResult = {
        name: testName,
        status: 'FAILED',
        error: error.message,
        suggestion: fixSuggestion,
        details: error
      };

      this.results.summary.failed++;
      this.results.summary.bugs.push(testResult);
      this.results[category].push(testResult);

      await this.log('ERROR', `${testName} FAILED: ${error.message}`, {
        category,
        suggestion: fixSuggestion,
        stack: error.stack
      });

      return false;
    }
  }

  async detectAndFixBugs() {
    console.log('🔍 Starting Comprehensive E2E Bug Detection...\n');

    await this.testEnvironment();
    await this.testWebApp();
    await this.testBackend();
    await this.testDatabase();
    await this.testIntegration();

    await this.generateFixReport();
  }

  async testEnvironment() {
    const tests = [
      {
        name: 'critical_env_variables',
        test: async () => {
          const required = ['DATABASE_URL', 'OPENAI_API_KEY'];
          const missing = required.filter(key => !process.env[key]);
          if (missing.length > 0) throw new Error(`Missing: ${missing.join(', ')}`);
          //
        },
        fix: 'Add DATABASE_URL="postgresql://user:pass@localhost:5432/atom" and OPENAI_API_KEY to .env'
      },
      {
        name: 'nodejs_compatibility',
        test: async () => {
          const { stdout } = await execAsync('node --version');
          const version = stdout.trim();
          if (!version.startsWith('v18.') && !version.startsWith('v20.')) {
            throw new Error(`Unsupported Node.js version: ${version}`);
          }
        },
        fix: 'Upgrade to Node.js 18+ or 20+ for better stability'
      }
    ];

    for (const { name, test, fix } of tests) {
      await this.runTest(name, test, 'environment', fix);
    }
  }

  async testWebApp() {
    const baseUrl = this.config.webUrl;

    const tests = [
      // Build & Startup Tests
      {
        name: 'nextjs_build_and_start',
        test: async () => {
          await execAsync('cd atomic-docker/app_build_docker && npm run build');
          const { stdout } = await execAsync('cd atomic-docker/app_build_docker && npm start &');
          await new Promise(resolve => setTimeout(resolve, 5000)); // Wait for startup
          return { started: true, build: 'successful' };
        },
        fix: 'Run "npm install && npm run build" in atomic-docker/app_build_docker'
      },
