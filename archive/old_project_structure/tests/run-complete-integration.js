#!/usr/bin/env node

/**
 * Complete Integration Test Suite for Atom AI Assistant
 * Tests Web App (Next.js) + Desktop App (Tauri) + Backend API + Database
 * Identifies and fixes critical integration bugs
 */

const { spawn, exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');
const { WebSocket } = require('ws');

const execAsync = promisify(exec);

class AtomIntegrationTester {
  constructor() {
    this.startTime = Date.now();
    this.results = {
      summary: { total: 0, passed: 0, failed: 0, warnings: 0 },
      details: {},
      issues: []
    };

    this.config = {
      webUrl: 'http://localhost:3000',
      desktopPort: 1420,
      timeout: 30000,
      retries: 3
    };
  }

  async log(level, message, data = {}) {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] ${level}: ${message}\n`;

    if (Object.keys(data).length > 0) {
      logEntry += `Data: ${JSON.stringify(data, null, 2)}\n`;
    }

    await fs.appendFile(path.join(__dirname, 'integration-results.log'), logEntry);

    if (level === 'ERROR') {
      this.results.issues.push({ timestamp, message, data });
    }

    const marker = { ERROR: '❌', SUCCESS: '✅', WARN: '⚠️', INFO: 'ℹ️' };
    console.log(`${marker[level] || ''} ${message}`);
  }

  async runTest(testName, testFn, category, fixSuggestion = null) {
    this.results.summary.total++;
    const start = Date.now();

    try {
      const result = await testFn();
      const duration = Date.now() - start;

      this.results.summary.passed++;
      this.results.details[category] = this.results.details[category] || [];
      this.results.details[category].push({
        test: testName,
        status: 'PASSED',
        duration,
        result
      });

      await this.log('SUCCESS', `${category}: ${testName} passed in ${duration}ms`);
      return true;

    } catch (error) {
      this.results.summary.failed++;
      const testResult = {
        test: testName,
        status: 'FAILED',
        error: error.message,
        suggestion: fixSuggestion,
        stack: error.stack
      };

      this.results.details[category] = this.results.details[category] || [];
      this.results.details[category].push(testResult);

      await this.log('ERROR', `${category}: ${testName} failed - ${error.message}`, testResult);
      return false;
    }
  }

  // 1. Environment Validation Tests
  async testEnvironment() {
    const envChecks = [
      {
        name: 'critical_env_variables',
        test: async () => {
          const required = ['DATABASE_URL', 'OPENAI_API_KEY'];
          const missing = required.filter(key => !process.env[key]);
          if (missing.length > 0) {
            throw new Error(`Missing env vars: ${missing.join(', ')}`);
          }
          return { status: 'valid', variables: required };
        },
        fix: 'Set DATABASE_URL and OPENAI_API_KEY in .env file'
      },
      {
        name: 'database_url_format',
        test: async () => {
          const url = process.env.DATABASE_URL;
          if (!url || !url.startsWith('postgresql://')) {
            throw new Error('DATABASE_URL must use postgresql:// protocol');
          }
          return { url_format: 'valid' };
        },
        fix: 'Format DATABASE_URL as postgresql://user:pass@host:port/database'
      }
    ];

    for (const check of envChecks) {
      await this.runTest(check.name, check.test, 'environment', check.fix);
    }
  }

  // 2. Database Integration Tests
  async testDatabase() {
    let pg;
    try {
      pg = require('pg');
    } catch {
      await this.log('WARN', 'PostgreSQL client not available, skipping database tests');
      return;
    }

    const databaseTests = [
      {
        name: 'database_connection',
        test: async () => {
          const client = new pg.Client({ connectionString: process.env.DATABASE_URL });
          await client.connect();
          const result = await client.query('SELECT NOW() as current_time, VERSION() as version');
          await client.end();
          return result.rows[0];
        },
        fix: 'Start PostgreSQL service and verify DATABASE_URL'
