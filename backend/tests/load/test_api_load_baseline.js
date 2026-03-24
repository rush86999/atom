// Baseline load test: 10 concurrent users
// Purpose: Establish baseline performance metrics under light load

import http from 'k6/http';
import { check, sleep, Trend } from 'k6';
import { login, executeAgent, getAgents, BASE_URL } from './k6_setup.js';

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp up to 10 users
    { duration: '3m', target: 10 },   // Stay at 10 users
    { duration: '1m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.05'],
    checks: ['rate>0.95'], // 95% of checks should pass
  },
};


export default function () {
  // Scenario 1: Authentication flow (60% of VUs)
  if (Math.random() < 0.6) {
    // Login
    const token = login();

    // Wait to simulate user think time
    sleep(1);

    // Optional: Execute agent after login
    if (token && Math.random() < 0.5) {
      executeAgent(token, 'baseline-test-agent');
    }
  }

  // Scenario 2: Agent execution (40% of VUs)
  else {
    // First login to get token
    const token = login();

    if (token) {
      // Execute agent
      executeAgent(token, 'baseline-test-agent');

      // Wait to simulate user think time
      sleep(2);

      // Optional: List agents
      getAgents(token);
    }
  }

  // Sleep to simulate realistic think time between requests
  sleep(1);
}

// Teardown: Print summary
export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };
}

// Helper function for text summary
function textSummary(data, options = {}) {
  const { indent = '', enableColors = false } = options;

  let summary = `${indent}Baseline Load Test Summary\n`;
  summary += `${indent}========================\n\n`;

  // Test metrics
  const httpReqs = data.metrics.http_reqs;
  const httpFailed = data.metrics.http_req_failed;
  const httpDuration = data.metrics.http_req_duration;
  const checks = data.metrics.checks;

  if (httpReqs && httpReqs.values) {
    summary += `${indent}Total Requests: ${httpReqs.values.count || 0}\n`;
  }

  if (httpFailed && httpFailed.values) {
    summary += `${indent}Failed Requests: ${httpFailed.values.fails || 0}\n`;
    summary += `${indent}Failure Rate: ${((httpFailed.values.rate || 0) * 100).toFixed(2)}%\n\n`;
  }

  // Response times
  if (httpDuration && httpDuration.values) {
    summary += `${indent}Response Times:\n`;
    summary += `${indent}  P50: ${(httpDuration.values['p(50)'] || 0).toFixed(0)}ms\n`;
    summary += `${indent}  P95: ${(httpDuration.values['p(95)'] || 0).toFixed(0)}ms\n`;
    summary += `${indent}  P99: ${(httpDuration.values['p(99)'] || 0).toFixed(0)}ms\n\n`;
  }

  // Checks
  if (checks && checks.values) {
    summary += `${indent}Checks:\n`;
    summary += `${indent}  Passed: ${checks.values.passes || 0}\n`;
    summary += `${indent}  Failed: ${checks.values.fails || 0}\n`;
    const passRate = checks.values.count > 0
      ? ((checks.values.passes / checks.values.count) * 100).toFixed(2)
      : '0.00';
    summary += `${indent}  Pass Rate: ${passRate}%\n`;
  }

  return summary;
}
