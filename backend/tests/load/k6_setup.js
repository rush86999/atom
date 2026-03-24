// k6 setup and configuration for Atom load testing
// This file provides base configuration and helper functions for all load tests

import http from 'k6/http';
import { check } from 'k6';

// Base URL configuration
export const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

// Common thresholds configuration
export const BASE_THRESHOLDS = {
  http_req_duration: ['p(95)<500', 'p(99)<1000'],
  http_req_failed: ['rate<0.05'],
};

// Helper function for authentication
export function login() {
  const loginPayload = JSON.stringify({
    email: 'load_test@example.com',
    password: 'test_password_123'
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const response = http.post(`${BASE_URL}/api/auth/login`, loginPayload, params);

  check(response, {
    'login successful': (r) => r.status === 200,
    'received token': (r) => r.json('token') !== undefined,
  });

  return response.json('token');
}

// Helper function to create authenticated headers
export function getAuthHeaders(token) {
  return {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
  };
}

// Helper function for random user selection
export function getRandomUser() {
  const users = [
    { email: 'load_test@example.com', password: 'test_password_123' },
    { email: 'user1@example.com', password: 'password123' },
    { email: 'user2@example.com', password: 'password123' },
  ];
  return users[Math.floor(Math.random() * users.length)];
}

// Helper function for agent execution
export function executeAgent(token, agentId = null) {
  const id = agentId || 'test-agent-' + Math.floor(Math.random() * 1000);
  const payload = JSON.stringify({
    query: 'Hello, this is a test query',
    agent_id: id,
  });

  const params = getAuthHeaders(token);
  const response = http.post(`${BASE_URL}/api/v1/agents/execute`, payload, params);

  check(response, {
    'agent execution started': (r) => r.status === 200 || r.status === 202,
  });

  return response;
}

// Helper function for getting agents list
export function getAgents(token) {
  const params = getAuthHeaders(token);
  const response = http.get(`${BASE_URL}/api/v1/agents`, params);

  check(response, {
    'agents list retrieved': (r) => r.status === 200,
  });

  return response;
}

// Helper function for canvas operations
export function getCanvas(token, canvasId) {
  const params = getAuthHeaders(token);
  const response = http.get(`${BASE_URL}/api/v1/canvas/${canvasId}`, params);

  check(response, {
    'canvas retrieved': (r) => r.status === 200 || r.status === 404, // 404 is acceptable if canvas doesn't exist
  });

  return response;
}

// Helper function for presenting canvas
export function presentCanvas(token, canvasId) {
  const payload = JSON.stringify({
    canvas_id: canvasId,
  });

  const params = getAuthHeaders(token);
  const response = http.post(`${BASE_URL}/api/v1/canvas/present`, payload, params);

  check(response, {
    'canvas presentation started': (r) => r.status === 200 || r.status === 202,
  });

  return response;
}

// Export default options
export const options = {
  thresholds: BASE_THRESHOLDS,
};
