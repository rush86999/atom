// Web UI load test: 20 concurrent users with realistic user flows
// Purpose: Simulate realistic web UI user behavior (login, agent execution, canvas view)

import http from 'k6/http';
import { check, sleep } from 'k6';
import { login, BASE_URL } from './k6_setup.js';

// Test configuration
export const options = {
  stages: [
    { duration: '3m', target: 20 },   // Ramp up to 20 users
    { duration: '5m', target: 20 },   // Stay at 20 users
    { duration: '1m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000', 'p(99)<1500'],
    http_req_failed: ['rate<0.10'],
    checks: ['rate>0.90'],
  },
};

export default function () {
  // Simulate web UI navigation flow

  // Step 1: GET / (load frontend)
  let response = http.get(`${BASE_URL}/`, {
    headers: {
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    },
  });

  check(response, {
    'homepage loaded': (r) => r.status === 200 || r.status === 304,
  });

  sleep(1);

  // Step 2: POST /api/auth/login (authenticate)
  const token = login();

  if (!token) {
    sleep(2);
    return;
  }

  sleep(1);

  // Step 3: GET /dashboard (load dashboard)
  const authHeaders = {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    },
  };

  response = http.get(`${BASE_URL}/dashboard`, authHeaders);

  check(response, {
    'dashboard loaded': (r) => r.status === 200 || r.status === 304,
  });

  // Wait to simulate reading time
  sleep(2);

  // Step 4: GET /api/v1/agents (list agents)
  const apiHeaders = {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };

  response = http.get(`${BASE_URL}/api/v1/agents`, apiHeaders);

  check(response, {
    'agents list retrieved': (r) => r.status === 200,
    'agents list is array': (r) => {
      try {
        const body = r.json();
        return Array.isArray(body) || (body.data && Array.isArray(body.data));
      } catch {
        return false;
      }
    },
  });

  sleep(1);

  // Step 5: POST /api/v1/agents/execute (execute agent)
  const agentPayload = JSON.stringify({
    query: 'Hello, this is a test query from web UI',
    agent_id: 'web-ui-test-agent',
  });

  response = http.post(`${BASE_URL}/api/v1/agents/execute`, agentPayload, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  check(response, {
    'agent execution started': (r) => r.status === 200 || r.status === 202,
    'agent execution has response': (r) => r.body.length > 0,
  });

  sleep(2);

  // Step 6: GET /api/v1/canvas (view canvas)
  const canvasId = 'web-ui-canvas-' + Math.floor(Math.random() * 10);
  response = http.get(`${BASE_URL}/api/v1/canvas/${canvasId}`, apiHeaders);

  check(response, {
    'canvas retrieved': (r) => r.status === 200 || r.status === 404,
  });

  sleep(1);

  // Step 7: POST /api/v1/canvas/present (present canvas)
  const canvasPayload = JSON.stringify({
    canvas_id: canvasId,
  });

  response = http.post(`${BASE_URL}/api/v1/canvas/present`, canvasPayload, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  check(response, {
    'canvas presentation started': (r) => r.status === 200 || r.status === 202,
  });

  sleep(2);

  // Step 8: GET /api/v1/workflows (list workflows - optional)
  if (Math.random() < 0.5) {
    response = http.get(`${BASE_URL}/api/v1/workflows`, apiHeaders);

    check(response, {
      'workflows list retrieved': (r) => r.status === 200,
    });

    sleep(1);
  }

  // Step 9: POST /api/auth/logout (logout) - optional
  if (Math.random() < 0.3) {
    const logoutPayload = JSON.stringify({});
    response = http.post(`${BASE_URL}/api/auth/logout`, logoutPayload, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    check(response, {
      'logout successful': (r) => r.status === 200 || r.status === 204,
    });

    sleep(1);
  }
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

  let summary = `${indent}Web UI Load Test Summary (20 Users)\n`;
  summary += `${indent}==================================\n\n`;

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
