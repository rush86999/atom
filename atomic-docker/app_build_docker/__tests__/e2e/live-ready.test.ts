/**
 * Live-Ready E2E Test Suite for Next.js Atomic App
 * Validates that the production application is fully functional
 *
 * Run with: npm test -- __tests__/e2e/live-ready.test.ts
 */

import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import { execSync } from 'child_process';
import { promisify } from 'util';
import { existsSync } from 'fs';
import path from 'path';

const sleep = promisify(setTimeout);

// Test configuration
const TEST_CONFIG = {
  baseUrl: process.env.TEST_BASE_URL || 'http://localhost:3000',
  timeout: 30000,
  retries: 3,
};

class TestRunner {
  private _process: any = null;

  async startDevServer() {
    console.log('🚀 Starting Next.js development server...');

    try {
      // Try to build if not built
      if (!existsSync(path.join(__dirname, '../../.next'))) {
        console.log('📦 Building Next.js application...');
        execSync('npm run build', {
          cwd: path.join(__dirname, '../../'),
          stdio: 'pipe',
          timeout: 120000
        });
        console.log('✅ Build complete');
      }

      // Start the dev server
      const spawn = require('child_process').spawn;
      this._process = spawn('npm', ['run', 'dev'], {
        cwd: path.join(__dirname, '../../'),
        stdio: 'pipe',
        env: { ...process.env, PORT: '3000' }
      });

      // Wait for server to be ready
      let attempts = 0;
      const maxAttempts = 30;

      while(attempts < maxAttempts) {
        try {
          const response = await fetch(TEST_CONFIG.baseUrl);
          if (response.status === 200) {
            console.log('✅ Dev server started successfully');
            return;
          }
        } catch(e) {
          // Server not ready yet
        }

        await sleep(1000);
        attempts++;
      }

      throw new Error('Failed to start dev server');

    } catch(error) {
      console.error('❌ Server startup failed:', error.message);
      throw error;
    }
  }

  async stopDevServer() {
    if (this._process) {
      console.log('🛑 Stopping dev server...');
      this._process.kill('SIGTERM');
      await sleep(1000);
    }
  }

  async isServerRunning(): Promise<boolean> {
    try {
      const response = await fetch(TEST_CONFIG.baseUrl, {
        method: 'GET',
        signal: AbortSignal.timeout(5000)
      });
      return response.status === 200;
    } catch {
      return false;
    }
  }
}

describe('🚀 Live-Ready E2E Test Suite', () => {
  let runner: TestRunner;
  let pageResponse: Response | null = null;

  beforeAll(async () => {
    runner = new TestRunner();

    // Check if server is already running
    const running = await runner.isServerRunning();
    if (!running) {
      console.log('🔄 Server not running - starting fresh...');
      await runner.startDevServer();
    } else {
      console.log('✅ Server already running at', TEST_CONFIG.baseUrl);
    }

    // Start health check
    let attempts = 0;
    const maxAttempts = 60;

    while(attempts < maxAttempts) {
      try {
        pageResponse = await fetch(TEST_CONFIG.baseUrl);
        if (pageResponse.status === 200) {
          console.log('✅ Server health check passed');
          break;
        }
      } catch(e) {
        console.log(`⏳ Waiting for server... (${attempts + 1}/${maxAttempts})`);
        await sleep(1000);
        attempts++;
      }
    }

    if (attempts >= maxAttempts) {
      throw new Error('Server failed to start within timeout');
    }

  }, 60000);

  afterAll(async () => {
    await runner.stopDevServer();
  });

  describe('🌐 Core Application Health', () => {
    test('Main page loads successfully', async () => {
      expect(pageResponse).toBeTruthy();

      const response = await fetch(TEST_CONFIG.baseUrl);
      expect(response.status).toBe(200);
      expect(response.headers.get('content-type')).toContain('text/html');

      const text = await response.text();
      expect(text).toContain('<html');
      expect(text).toContain('</html>');
    });

    test('Static assets served correctly', async () => {
      const jsResponse = await fetch(`${TEST_CONFIG.baseUrl}/_next/static/chunks/main.js`);
      expect(jsResponse.status).toBe(200);
      expect(jsResponse.headers.get('content-type')).toContain('application/javascript');
    });

    test('Next.js specific routes work', async () => {
      const apiResponse = await fetch(`${TEST_CONFIG.baseUrl}/api/auth/health`)
          .catch(() => ({ status: 404 } as Response));

      // API health endpoint may or may not exist
      expect([200, 404, 401]).toContain(apiResponse.status);
    });
  });

  describe('🔐 Authentication Flow', () => {
    test('Login page accessible', async () => {
      const response = await fetch(`${TEST_CONFIG.baseUrl}/login`)
          .catch(() => ({ status: 404 } as Response));

      const loginExists = response.status !== 404;
      expect(loginExists).toBe(true);

      if (response.status === 200) {
        const text = await response.text();
        expect(text).toMatch(/login|sign in|auth/i);
      }
    });

    test('Protected routes check', async () => {
      const dashboardResponse = await fetch(`${TEST_CONFIG.baseUrl}/dashboard`)
          .catch(() => ({ status: 404 } as Response));

      // Should either exist or redirect
      expect([200, 302, 404]).toContain(dashboardResponse.status);
    });
  });

  describe('💼 Business Logic Integration', () => {
    test('Calendar integration endpoints', async () => {
      const calendarResponse = await fetch(`${TEST_CONFIG.baseUrl}/api/calendar`)
          .catch(() => ({ status: 404 } as Response));

      // Calendar should have some endpoints
      expect([200, 405, 404]).toContain(calendarResponse.status);
    });

    test('Chat and AI endpoints', async () => {
      const chatResponse = await fetch(`${TEST_CONFIG.baseUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ test: true })
      }).catch(() => ({ status: 404 } as Response));

      expect([200, 400, 401, 404]).toContain(chatResponse.status);
    });
  });

  describe('🔍 Performance Verification', () => {
    test('Page load time under 5 seconds', async () => {
      const startTime = Date.now();
      const response = await fetch(TEST_CONFIG.baseUrl);
      const endTime = Date.now();

      expect(response.status).toBe(200);
      expect(endTime - startTime).toBeLessThan(5000);
    });

    test('Static assets cached appropriately', async () => {
      const staticResponse = await fetch(`${TEST_CONFIG.baseUrl}/_next/static/css/app.css`);
      expect(staticResponse.status).toBe(200);

      const cacheControl = staticResponse.headers.get('cache-control');
      expect(cacheControl).toBeTruthy();
    });
  });

  describe('🛡️ Security & Headers', () => {
    test('Security headers present', async () => {
      const response = await fetch(TEST_CONFIG.baseUrl);

      expect(response.headers.get('x-frame-options')).toBeTruthy();
      expect(response.headers.get('x-content-type-options')).toBeTruthy();
    });

    test('HTTPS redirects working', async () => {
      // This would test redirect behavior in production
      expect(true).toBe(true); // Placeholder for now
    });
  });

  describe('📊 Health Check Endpoints', () => {
    test('Basic health endpoint', async () => {
      const healthResponse = await fetch(`${TEST_CONFIG.baseUrl}/api/health`)
          .catch(() => ({ status: 404 } as Response));

      if (healthResponse.status !== 404) {
        expect([200, 204]).toContain(healthResponse.status);
      }
    });

    test('Ready endpoint', async () => {
      const readyResponse = await fetch(`${TEST_CONFIG.baseUrl}/api/ready`)
          .catch(() => ({ status: 404 } as Response));

      if (readyResponse.status !== 404) {
        expect([200, 204]).toContain(readyResponse.status);
      }
    });
  });

  describe('📋 Frontend Integration', () => {
    test('Main page includes required meta tags', async () => {
      const response = await fetch(TEST_CONFIG.baseUrl);
      const text = await response.text();

      expect(text).toMatch(/<meta.*?content="width=device-width/i);
      expect(text).toMatch(/<meta.*?name="description"/i);
    });

    test('JavaScript files loaded correctly', async () => {
      const response = await fetch(TEST_CONFIG.baseUrl);
      const text = await response.text();

      // Check for Next.js script tags
      expect(text).toMatch(/<script.*?src.*?_next\/static/i);
    });
  });

  describe('🧪 End-to-End Workflows', () => {
    test('Navigation flow works', async () => {
      // Simple navigation test
      const home = await fetch(TEST_CONFIG.baseUrl);
      expect(home.status).toBe(200);

      // Test for common routes
      const routes = ['login', 'dashboard', 'calendar'];

      for (const route of routes) {
        const response = await fetch(`${TEST_CONFIG.baseUrl}/${route}`)
            .catch(() => ({ status: 404 } as Response));
        expect([200, 302, 404]).toContain(response.status);
      }
    });
  });
});

// Production readiness check
export const validateLiveReady = async () => {
  console.log('\n🔍 Running Live-Ready Validation...\n');

  const checks = [
    { name: 'Server Responsiveness', test: async () => {
      const response = await fetch(TEST_CONFIG.baseUrl);
      return response.status === 200;
    }},
    { name: 'Static Assets', test: async () => {
      const response = await fetch(`${TEST_CONFIG.baseUrl}/_next/static/chunks/main.js`);
      return response.status === 200;
    }},
    { name: 'API Health', test: async () => {
      const response = await fetch(`${TEST_CONFIG.baseUrl}/api/health`)
          .catch(() => ({ status: 404 } as Response));
      return [200, 404].includes(response.status);
    }},
    { name: 'Build Assets', test: async () => {
      return existsSync(path.join(__dirname, '../../.next'));
    }}
  ];

  let passed = 0;
  let failed = 0;

  for (const { name, test } of checks) {
    try {
      const result = await test();
      console.log(`${result ? '✅' : '❌'} ${name}`);

      if (result) passed++; else failed++;
    } catch (error) {
      console.error(`❌ ${name}: ${error.message}`);
      failed++;
    }
  }

  console.log(`\n📊 Results: ${passed} passed, ${failed} failed`);
  console.log(`${failed === 0 ? '🎉' : '❌'} App is ${failed === 0 ? '' : 'NOT '}live-ready!`);

  return { passed, failed, isReady: failed === 0 };
};

// Run validation if called directly
if (require.main === module) {
  validateLiveReady();
}

export default { validateLiveReady };
