#!/usr/bin/env node
/**
 * Proof of Concept: Verify Command Injection Fix (Issue #525)
 *
 * This script demonstrates that the vulnerability has been fixed.
 * Original PoC: curl -X POST http://127.0.0.1:3003/sys/install \
 *                 -H "Content-Type: application/json" \
 *                 -d '{"packageName": "express; touch /tmp/pwned #"}'
 *
 * Expected behavior AFTER fix:
 * - Request is rejected with 400 Bad Request (invalid package name)
 * - No command execution occurs
 */

import http from 'http';

const HOST = '127.0.0.1';
const PORT = 3003;

// Test cases
const tests = [
  {
    name: 'Valid package name (with auth)',
    path: '/sys/install',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'test-api-key'
    },
    body: JSON.stringify({ packageName: '@activepieces/piece-github' }),
    expectedStatus: 200, // Should proceed to npm install
    description: 'Should allow valid package with authentication'
  },
  {
    name: 'Command injection: semicolon (without auth)',
    path: '/sys/install',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ packageName: 'express; touch /tmp/pwned #' }),
    expectedStatus: 401,
    description: 'Should reject without authentication'
  },
  {
    name: 'Command injection: semicolon (with auth)',
    path: '/sys/install',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'test-api-key'
    },
    body: JSON.stringify({ packageName: 'express; touch /tmp/pwned #' }),
    expectedStatus: 400,
    description: 'Should reject invalid package name even with auth'
  },
  {
    name: 'Command injection: pipe (with auth)',
    path: '/sys/install',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'test-api-key'
    },
    body: JSON.stringify({ packageName: 'express | cat /etc/passwd' }),
    expectedStatus: 400,
    description: 'Should reject pipe injection'
  },
  {
    name: 'Command injection: backticks (with auth)',
    path: '/sys/install',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'test-api-key'
    },
    body: JSON.stringify({ packageName: 'express`rm -rf /`' }),
    expectedStatus: 400,
    description: 'Should reject backtick injection'
  },
  {
    name: 'Command injection: command substitution (with auth)',
    path: '/sys/install',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'test-api-key'
    },
    body: JSON.stringify({ packageName: 'express$(whoami)' }),
    expectedStatus: 400,
    description: 'Should reject $() command substitution'
  },
  {
    name: 'Health check (no auth required)',
    path: '/health',
    method: 'GET',
    headers: {},
    body: null,
    expectedStatus: 200,
    description: 'Health check should work without authentication'
  }
];

async function makeRequest(test) {
  return new Promise((resolve) => {
    const options = {
      hostname: HOST,
      port: PORT,
      path: test.path,
      method: test.method,
      headers: test.headers
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        resolve({
          status: res.statusCode,
          body: data
        });
      });
    });

    req.on('error', (error) => {
      resolve({
        status: 'ERROR',
        error: error.message
      });
    });

    if (test.body) {
      req.write(test.body);
    }
    req.end();
  });
}

async function runTests() {
  console.log('╔══════════════════════════════════════════════════════════════╗');
  console.log('║  Security Fix Verification: Command Injection (Issue #525)  ║');
  console.log('╚══════════════════════════════════════════════════════════════╝\n');

  console.log(`Target: http://${HOST}:${PORT}`);
  console.log('Starting tests...\n');

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    const result = await makeRequest(test);
    const statusMatch = result.status === test.expectedStatus;

    if (statusMatch) {
      passed++;
      console.log(`✅ PASS: ${test.name}`);
      console.log(`   Expected: ${test.expectedStatus}, Got: ${result.status}`);
      console.log(`   ${test.description}\n`);
    } else {
      failed++;
      console.log(`❌ FAIL: ${test.name}`);
      console.log(`   Expected: ${test.expectedStatus}, Got: ${result.status}`);
      console.log(`   ${test.description}`);
      if (result.error) {
        console.log(`   Error: ${result.error}`);
      } else {
        console.log(`   Response: ${result.body.substring(0, 100)}`);
      }
      console.log();
    }
  }

  console.log('╔══════════════════════════════════════════════════════════════╗');
  console.log(`║  Results: ${passed} passed, ${failed} failed out of ${tests.length} tests  ║`);
  console.log('╚══════════════════════════════════════════════════════════════╝');

  if (failed === 0) {
    console.log('\n✅ All security tests passed! The vulnerability has been fixed.');
    process.exit(0);
  } else {
    console.log('\n❌ Some tests failed. The vulnerability may not be fully fixed.');
    process.exit(1);
  }
}

// Run tests
runTests().catch(console.error);
