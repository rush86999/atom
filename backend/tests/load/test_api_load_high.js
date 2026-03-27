// High load test: 100 concurrent users
// Purpose: Validate system performance under high concurrent load

import http from 'k6/http';
import { check, sleep } from 'k6';
import { login, executeAgent, getAgents, getCanvas, presentCanvas, BASE_URL } from './k6_setup.js';

// Test configuration
export const options = {
  stages: [
    { duration: '10m', target: 100 },  // Ramp up to 100 users
    { duration: '15m', target: 100 },  // Stay at 100 users
    { duration: '3m', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1200', 'p(99)<2000'],
    http_req_failed: ['rate<0.15'],
    checks: ['rate>0.85'],
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

  // Scenario 1: Authentication flow (40% of VUs)
  if (scenario < 0.4) {
    sleep(1);

    // Execute agent
    if (Math.random() < 0.4) {
      executeAgent(token, `high-agent-${Math.floor(Math.random() * 200)}`);
    }
  }

  // Scenario 2: Agent execution (35% of VUs)
  else if (scenario < 0.75) {
    // List agents
    getAgents(token);
    sleep(1);

    // Execute multiple agents
    const numExecutions = Math.floor(Math.random() * 3) + 1;
    for (let i = 0; i < numExecutions; i++) {
      const agentId = `high-agent-${Math.floor(Math.random() * 200)}`;
      executeAgent(token, agentId);
      sleep(1);
    }

    // List agents again
    getAgents(token);
  }

  // Scenario 3: Canvas operations (15% of VUs)
  else if (scenario < 0.9) {
    const canvasId = `canvas-${Math.floor(Math.random() * 100)}`;

    // Get canvas
    getCanvas(token, canvasId);
    sleep(1);

    // Present canvas
    presentCanvas(token, canvasId);
    sleep(2);

    // Get another canvas
    const canvasId2 = `canvas-${Math.floor(Math.random() * 100)}`;
    getCanvas(token, canvasId2);
  }

  // Scenario 4: Workflow execution (10% of VUs)
  else {
    // Execute workflow via API
    const workflowId = `workflow-${Math.floor(Math.random() * 50)}`;
    const payload = JSON.stringify({
      workflow_id: workflowId,
      input_data: { test: 'data' },
    });

    const params = {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    };

    const response = http.post(`${BASE_URL}/api/v1/workflows/${workflowId}/execute`, payload, params);

    check(response, {
      'workflow execution started': (r) => r.status === 200 || r.status === 202,
    });

    sleep(3);
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

  let summary = `${indent}High Load Test Summary (100 Users)\n`;
  summary += `${indent}===================================\n\n`;

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
