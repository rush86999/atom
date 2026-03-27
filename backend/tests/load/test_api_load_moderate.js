// Moderate load test: 50 concurrent users
// Purpose: Validate system performance under moderate concurrent load

import http from 'k6/http';
import { check, sleep } from 'k6';
import { login, executeAgent, getAgents, getCanvas, presentCanvas, BASE_URL } from './k6_setup.js';

// Test configuration
export const options = {
  stages: [
    { duration: '5m', target: 50 },   // Ramp up to 50 users
    { duration: '10m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<800', 'p(99)<1500'],
    http_req_failed: ['rate<0.10'],
    checks: ['rate>0.90'],
  },
};

export default function () {
  // Login first
  const token = login();

  if (!token) {
    sleep(1);
    return;
  }

  // Scenario distribution
  const scenario = Math.random();

  // Scenario 1: Authentication flow (50% of VUs)
  if (scenario < 0.5) {
    // Login, wait, then logout
    sleep(1);

    // Optionally execute agent
    if (Math.random() < 0.3) {
      executeAgent(token, `moderate-agent-${Math.floor(Math.random() * 100)}`);
    }
  }

  // Scenario 2: Agent execution (30% of VUs)
  else if (scenario < 0.8) {
    // List agents
    getAgents(token);
    sleep(1);

    // Execute agent
    const agentId = `moderate-agent-${Math.floor(Math.random() * 100)}`;
    executeAgent(token, agentId);
    sleep(2);

    // List agents again
    getAgents(token);
  }

  // Scenario 3: Canvas operations (20% of VUs)
  else {
    const canvasId = `canvas-${Math.floor(Math.random() * 50)}`;

    // Get canvas
    getCanvas(token, canvasId);
    sleep(1);

    // Present canvas
    presentCanvas(token, canvasId);
    sleep(2);
  }

  // Sleep to simulate realistic think time
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

  let summary = `${indent}Moderate Load Test Summary (50 Users)\n`;
  summary += `${indent}=====================================\n\n`;

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
