/**
 * API Client Interceptor & Behavior Tests
 *
 * Exercises the REAL runtime behavior of lib/api.ts:
 * - request interceptor: auth header injection (auth_token/token) + X-Request-ID
 * - response interceptor #1: exponential-backoff retry + error enhancement
 * - response interceptor #2: 401 handling (token purge + login redirect)
 * - (apiClient as any).fetch: fetch-style Response wrapper (409/424 passthrough)
 * - fetchWithErrorHandling: retries, 204, null/array/empty-object guards, abort
 * - every exported API namespace calls the right method/URL/payload
 *
 * axios is mocked with a callable instance so interceptor handlers can be
 * extracted and invoked directly; @lifeomic/attempt retry is stubbed.
 */

const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  length: 0,
  key: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: mockLocalStorage,
});

const mockInstance: any = jest.fn();
mockInstance.get = jest.fn();
mockInstance.post = jest.fn();
mockInstance.put = jest.fn();
mockInstance.patch = jest.fn();
mockInstance.delete = jest.fn();
mockInstance.request = jest.fn();
mockInstance.interceptors = {
  request: { use: jest.fn() },
  response: { use: jest.fn() },
};

jest.mock('axios', () => ({
  create: jest.fn(() => mockInstance),
  default: jest.fn(() => mockInstance),
}));

jest.mock('@lifeomic/attempt', () => ({
  retry: jest.fn(),
}));

import axios from 'axios';
import { retry } from '@lifeomic/attempt';
import apiClient, {
  systemAPI,
  serviceRegistryAPI,
  byokAPI,
  workflowAPI,
  oauthAPI,
  integrationAPI,
  dashboardAPI,
  userManagementAPI,
  emailVerificationAPI,
  tenantAPI,
  adminAPI,
  meetingAPI,
  financialAPI,
  fetchWithErrorHandling,
} from '../api';

const instance = (axios.create as jest.Mock).mock.results[0].value;
const requestUse = instance.interceptors.request.use as jest.Mock;
const requestFulfilled = requestUse.mock.calls[0][0];
const requestRejected = requestUse.mock.calls[0][1];
const responseUse = instance.interceptors.response.use as jest.Mock;
const retryRejected = responseUse.mock.calls[0][1];
const authRejected = responseUse.mock.calls[1][1];

const makeHttpError = (status: number, extra: any = {}) => {
  const error: any = new Error(`Request failed with status code ${status}`);
  error.response = { status, data: {}, statusText: 'Err', config: {} };
  error.config = { headers: {}, url: '/api/x' };
  error.code = extra.code;
  return { ...extra, ...error };
};

describe('API client request interceptor', () => {
  beforeEach(() => {
    (mockLocalStorage.getItem as jest.Mock).mockReset();
  });

  it('adds Bearer Authorization from localStorage auth_token', () => {
    (mockLocalStorage.getItem as jest.Mock).mockImplementation((key: string) =>
      key === 'auth_token' ? 'token-abc' : null,
    );
    const config: any = { headers: {}, url: '/api/agents' };
    const result = requestFulfilled(config);
    expect(result.headers.Authorization).toBe('Bearer token-abc');
    expect(result.headers['X-Request-ID']).toMatch(/^req_\d+_[a-z0-9]+$/);
  });

  it('falls back to the "token" key when auth_token is missing', () => {
    (mockLocalStorage.getItem as jest.Mock).mockImplementation((key: string) =>
      key === 'token' ? 'legacy-token' : null,
    );
    const config: any = { headers: {} };
    const result = requestFulfilled(config);
    expect(result.headers.Authorization).toBe('Bearer legacy-token');
  });

  it('adds no Authorization header when no token is stored', () => {
    (mockLocalStorage.getItem as jest.Mock).mockReturnValue(null);
    const config: any = { headers: {} };
    const result = requestFulfilled(config);
    expect(result.headers.Authorization).toBeUndefined();
    expect(result.headers['X-Request-ID']).toBeDefined();
  });

  it('request error handler propagates the rejection', async () => {
    const err = new Error('request setup failed');
    await expect(requestRejected(err)).rejects.toThrow('request setup failed');
  });
});

describe('API client response interceptor (retry + error mapping)', () => {
  beforeEach(() => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'log').mockImplementation(() => {});
    instance.mockReset();
    (retry as jest.Mock).mockReset();
  });

  it('retries a retryable 500 error and resolves with the recovered response', async () => {
    (retry as jest.Mock).mockImplementation(async (fn: any) => fn());
    instance.mockResolvedValueOnce({ data: { recovered: true }, status: 200 });

    const error = makeHttpError(500);
    const result = await retryRejected(error);

    expect(retry).toHaveBeenCalled();
    expect(instance).toHaveBeenCalledWith(error.config);
    expect(error.config.__isRetryRequest).toBe(true);
    expect(result).toEqual({ data: { recovered: true }, status: 200 });
  });

  it('rejects with an enhanced error after retries are exhausted', async () => {
    (retry as jest.Mock).mockImplementation(async (fn: any) => fn());
    instance.mockRejectedValue(makeHttpError(503));

    await expect(retryRejected(makeHttpError(500))).rejects.toMatchObject({
      userMessage: 'Our service is temporarily unavailable. Please try again in a few moments.',
      userAction: 'Retry',
      severity: 'error',
      isRetryable: true,
    });
  });

  it('does not retry non-retryable 404 errors and rejects with enhanced error', async () => {
    const error = makeHttpError(404);

    await expect(retryRejected(error)).rejects.toMatchObject({
      userMessage: 'The requested resource was not found. Please check the URL or contact support.',
      userAction: null,
      severity: 'warning',
      isRetryable: false,
    });
    expect(retry).not.toHaveBeenCalled();
    expect(instance).not.toHaveBeenCalled();
  });

  it('does not retry when the request is already marked __isRetryRequest', async () => {
    const error = makeHttpError(500);
    error.config.__isRetryRequest = true;

    await expect(retryRejected(error)).rejects.toMatchObject({ isRetryable: true });
    expect(retry).not.toHaveBeenCalled();
  });

  it('does not retry when the request opts out via retry: false', async () => {
    const error = makeHttpError(500);
    error.config.retry = false;

    await expect(retryRejected(error)).rejects.toMatchObject({ severity: 'error' });
    expect(retry).not.toHaveBeenCalled();
  });

  it('does not retry when error.config is missing', async () => {
    const error: any = new Error('no config');
    error.response = { status: 500, data: {} };

    await expect(retryRejected(error)).rejects.toMatchObject({ isRetryable: true });
    expect(retry).not.toHaveBeenCalled();
  });
});

describe('API client 401 interceptor', () => {
  // jsdom's window.location is non-configurable and its href setter cannot be
  // spied, so we control the route via history.pushState and assert the
  // observable contract: token purge (or its absence) on 401.
  afterEach(() => {
    window.history.pushState({}, '', '/');
    (mockLocalStorage.removeItem as jest.Mock).mockReset();
  });

  it('purges tokens on 401 outside auth pages', async () => {
    window.history.pushState({}, '', '/dashboard');
    const error = makeHttpError(401);

    await expect(authRejected(error)).rejects.toBe(error);

    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('auth_token');
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('token');
  });

  it('does not purge tokens when already on an auth page', async () => {
    window.history.pushState({}, '', '/login');
    const error = makeHttpError(401);

    await expect(authRejected(error)).rejects.toBe(error);
    expect(mockLocalStorage.removeItem).not.toHaveBeenCalled();
  });

  it('does not purge tokens for /auth/* pages', async () => {
    window.history.pushState({}, '', '/auth/callback');
    const error = makeHttpError(401);

    await expect(authRejected(error)).rejects.toBe(error);
    expect(mockLocalStorage.removeItem).not.toHaveBeenCalled();
  });

  it('leaves non-401 errors untouched', async () => {
    window.history.pushState({}, '', '/dashboard');
    const error = makeHttpError(403);

    await expect(authRejected(error)).rejects.toBe(error);
    expect(mockLocalStorage.removeItem).not.toHaveBeenCalled();
  });
});

describe('apiClient.fetch (fetch-style helper)', () => {
  it('wraps a successful response as a fetch Response', async () => {
    instance.request.mockResolvedValueOnce({
      status: 200,
      statusText: 'OK',
      data: { hello: 'world' },
    });

    const res = await (apiClient as any).fetch('/api/boards');
    expect(res.status).toBe(200);
    expect(res.ok).toBe(true);
    expect(await res.json()).toEqual({ hello: 'world' });
    expect(instance.request).toHaveBeenCalledWith({
      url: '/api/boards',
      method: 'GET',
      headers: undefined,
      data: undefined,
      signal: undefined,
      responseType: 'json',
    });
  });

  it('returns a 409 conflict as a fetch Response instead of throwing', async () => {
    instance.request.mockRejectedValueOnce({
      response: { status: 409, statusText: 'Conflict', data: { error: 'locked' } },
    });

    const res = await (apiClient as any).fetch('/api/boards');
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual({ error: 'locked' });
  });

  it('returns a 424 BYOK-key response as a fetch Response', async () => {
    instance.request.mockRejectedValueOnce({
      response: { status: 424, statusText: 'Failed Dependency', data: { needs_key: true } },
    });

    const res = await (apiClient as any).fetch('/api/agents');
    expect(res.status).toBe(424);
    expect(await res.json()).toEqual({ needs_key: true });
  });

  it('propagates network errors (no response)', async () => {
    instance.request.mockRejectedValueOnce(new Error('ECONNREFUSED'));

    await expect((apiClient as any).fetch('/api/x')).rejects.toThrow('ECONNREFUSED');
  });

  it('passes through method, body, headers and signal', async () => {
    const signal = new AbortController().signal;
    instance.request.mockResolvedValueOnce({ status: 201, statusText: 'Created', data: null });

    const res = await (apiClient as any).fetch('/api/boards', {
      method: 'POST',
      headers: { 'X-Test': '1' },
      body: JSON.stringify({ name: 'Board' }),
      signal,
    });

    expect(res.status).toBe(201);
    expect(instance.request).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/api/boards',
        method: 'POST',
        headers: { 'X-Test': '1' },
        data: JSON.stringify({ name: 'Board' }),
        signal,
      }),
    );
  });
});

describe('fetchWithErrorHandling', () => {
  const originalFetch = global.fetch;
  const mockJson = (data: any) => ({ ok: true, status: 200, statusText: 'OK', json: async () => data });

  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('returns parsed data on success', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(mockJson({ status: 'ok' }));
    await expect(fetchWithErrorHandling('/api/health')).resolves.toEqual({ status: 'ok' });
    expect(global.fetch).toHaveBeenCalledWith('/api/health', {});
  });

  it('returns {} for 204 no-content responses', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, status: 204, json: async () => ({}) });
    await expect(fetchWithErrorHandling('/api/delete')).resolves.toEqual({});
  });

  it('retries on 5xx and succeeds', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: false, status: 500 })
      .mockResolvedValueOnce(mockJson({ recovered: true }));

    await expect(fetchWithErrorHandling('/api/x', { retries: 1 })).resolves.toEqual({ recovered: true });
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('does not retry on 4xx errors', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({ ok: false, status: 404, statusText: 'Not Found' });

    await expect(fetchWithErrorHandling('/api/x', { retries: 3 })).rejects.toThrow('HTTP 404');
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('throws after 5xx retries are exhausted', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({ ok: false, status: 503, statusText: 'Down' });

    await expect(fetchWithErrorHandling('/api/x', { retries: 2 })).rejects.toThrow('HTTP 503');
    expect(global.fetch).toHaveBeenCalledTimes(3);
  });

  it('retries network errors and succeeds', async () => {
    (global.fetch as jest.Mock)
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce(mockJson({ up: true }));

    await expect(fetchWithErrorHandling('/api/x', { retries: 1 })).resolves.toEqual({ up: true });
  });

  it('throws the network error when retries are exhausted', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('network down'));

    await expect(fetchWithErrorHandling('/api/x')).rejects.toThrow('network down');
  });

  it('rejects null responses', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(mockJson(null));
    await expect(fetchWithErrorHandling('/api/x')).rejects.toThrow('Null or undefined response');
  });

  it('rejects array responses', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(mockJson([1, 2, 3]));
    await expect(fetchWithErrorHandling('/api/x')).rejects.toThrow('Array response when object expected');
  });

  it('rejects empty object responses', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(mockJson({}));
    await expect(fetchWithErrorHandling('/api/x')).rejects.toThrow('Missing response fields');
  });

  it('throws "Request aborted" when the signal aborts (even with retries left)', async () => {
    const signal: any = { aborted: true };
    const aborted = { ok: true, status: 200, statusText: 'OK', json: async () => ({}) };
    (global.fetch as jest.Mock).mockResolvedValueOnce(aborted);

    await expect(fetchWithErrorHandling('/api/x', { signal, retries: 2 })).rejects.toThrow(
      'Request aborted',
    );
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('does not retry AbortError rejections', async () => {
    const abortError: any = new Error('aborted');
    abortError.name = 'AbortError';
    (global.fetch as jest.Mock).mockRejectedValue(abortError);

    await expect(fetchWithErrorHandling('/api/x', { retries: 2 })).rejects.toThrow('aborted');
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});

describe('API namespaces hit the correct endpoints', () => {
  beforeEach(() => {
    instance.get.mockReset();
    instance.post.mockReset();
    instance.put.mockReset();
    instance.patch.mockReset();
    instance.delete.mockReset();
  });

  it('systemAPI', () => {
    systemAPI.getHealth();
    expect(instance.get).toHaveBeenCalledWith('/api/health');
    systemAPI.getStatus();
    expect(instance.get).toHaveBeenCalledWith('/api/status');
    systemAPI.getSystemStatus();
    expect(instance.get).toHaveBeenCalledWith('/api/status');
  });

  it('serviceRegistryAPI', () => {
    serviceRegistryAPI.getServices();
    expect(instance.get).toHaveBeenCalledWith('/api/services/registry');
    serviceRegistryAPI.getService('s-1');
    expect(instance.get).toHaveBeenCalledWith('/api/services/registry/s-1');
    serviceRegistryAPI.registerService({ name: 'x' });
    expect(instance.post).toHaveBeenCalledWith('/api/services/registry', { name: 'x' });
    serviceRegistryAPI.updateService('s-1', { name: 'y' });
    expect(instance.put).toHaveBeenCalledWith('/api/services/registry/s-1', { name: 'y' });
    serviceRegistryAPI.deleteService('s-1');
    expect(instance.delete).toHaveBeenCalledWith('/api/services/registry/s-1');
    serviceRegistryAPI.testService('s-1');
    expect(instance.post).toHaveBeenCalledWith('/api/services/registry/s-1/test');
    serviceRegistryAPI.getServiceHealth('s-1');
    expect(instance.get).toHaveBeenCalledWith('/api/services/registry/s-1/health');
  });

  it('byokAPI', () => {
    byokAPI.getProviders();
    expect(instance.get).toHaveBeenCalledWith('/api/ai/providers');
    byokAPI.getProvider('openai');
    expect(instance.get).toHaveBeenCalledWith('/api/ai/providers/openai');
    byokAPI.configureProvider('openai', { key: 'k' });
    expect(instance.post).toHaveBeenCalledWith('/api/ai/providers/openai/configure', { key: 'k' });
    byokAPI.testProvider('openai');
    expect(instance.post).toHaveBeenCalledWith('/api/ai/providers/openai/test');
    byokAPI.getProviderStats('openai');
    expect(instance.get).toHaveBeenCalledWith('/api/ai/providers/openai/stats');
    byokAPI.getProviderCosts('openai');
    expect(instance.get).toHaveBeenCalledWith('/api/ai/providers/openai/costs');
    byokAPI.validateProvider('openai', { key: 'k' });
    expect(instance.post).toHaveBeenCalledWith('/api/ai/providers/openai/validate', { key: 'k' });
  });

  it('workflowAPI', () => {
    workflowAPI.getTemplates();
    expect(instance.get).toHaveBeenCalledWith('/api/workflow-templates/');
    workflowAPI.getTemplate('w-1');
    expect(instance.get).toHaveBeenCalledWith('/api/workflow-templates/w-1');
    workflowAPI.createWorkflow({ name: 'wf' });
    expect(instance.post).toHaveBeenCalledWith('/api/workflows', { name: 'wf' });
    workflowAPI.executeWorkflow('w-1', { input: 1 });
    expect(instance.post).toHaveBeenCalledWith('/api/workflows/w-1/execute', { input: 1 });
    workflowAPI.getWorkflowStatus('w-1');
    expect(instance.get).toHaveBeenCalledWith('/api/workflows/w-1/status');
    workflowAPI.getWorkflowHistory('w-1');
    expect(instance.get).toHaveBeenCalledWith('/api/workflows/w-1/history');
    workflowAPI.cancelWorkflow('w-1');
    expect(instance.post).toHaveBeenCalledWith('/api/workflows/w-1/cancel');
    workflowAPI.getWorkflowLogs('w-1');
    expect(instance.get).toHaveBeenCalledWith('/api/workflows/w-1/logs');
    workflowAPI.validateWorkflow({ name: 'wf' });
    expect(instance.post).toHaveBeenCalledWith('/api/workflows/validate', { name: 'wf' });
  });

  it('oauthAPI', () => {
    oauthAPI.authorize('google', 'http://cb');
    expect(instance.post).toHaveBeenCalledWith('/api/auth/google/authorize', {
      redirect_uri: 'http://cb',
    });
    oauthAPI.handleCallback('google', 'code-1', 'state-1');
    expect(instance.post).toHaveBeenCalledWith('/api/auth/google/callback', {
      code: 'code-1',
      state: 'state-1',
    });
    oauthAPI.getServiceStatus('google');
    expect(instance.get).toHaveBeenCalledWith('/api/auth/google/status');
  });

  it('integrationAPI', () => {
    integrationAPI.asana.getTasks();
    expect(instance.get).toHaveBeenCalledWith('/api/integrations/asana/tasks');
    integrationAPI.asana.createTask({ name: 't' });
    expect(instance.post).toHaveBeenCalledWith('/api/integrations/asana/tasks', { name: 't' });
    integrationAPI.asana.updateTask('a-1', { name: 't2' });
    expect(instance.put).toHaveBeenCalledWith('/api/integrations/asana/tasks/a-1', { name: 't2' });
    integrationAPI.notion.getPages();
    expect(instance.get).toHaveBeenCalledWith('/api/integrations/notion/pages');
    integrationAPI.notion.search('my query');
    expect(instance.get).toHaveBeenCalledWith('/api/integrations/notion/search?query=my%20query');
    integrationAPI.slack.getChannels();
    expect(instance.get).toHaveBeenCalledWith('/api/integrations/slack/channels');
    integrationAPI.slack.sendMessage('C1', 'hello');
    expect(instance.post).toHaveBeenCalledWith('/api/integrations/slack/messages', {
      channel: 'C1',
      text: 'hello',
    });
    integrationAPI.slack.getMessages('C1');
    expect(instance.get).toHaveBeenCalledWith('/api/integrations/slack/messages?channel=C1');
    integrationAPI.googleCalendar.getEvents();
    expect(instance.get).toHaveBeenCalledWith('/api/integrations/google/calendar/events');
    integrationAPI.googleCalendar.createEvent({ title: 'e' });
    expect(instance.post).toHaveBeenCalledWith('/api/integrations/google/calendar/events', { title: 'e' });
    integrationAPI.googleCalendar.updateEvent('ev-1', { title: 'e2' });
    expect(instance.put).toHaveBeenCalledWith('/api/integrations/google/calendar/events/ev-1', { title: 'e2' });
    integrationAPI.gmail.getEmails();
    expect(instance.get).toHaveBeenCalledWith('/api/integrations/google/gmail/emails');
    integrationAPI.gmail.getLabels();
    expect(instance.get).toHaveBeenCalledWith('/api/integrations/google/gmail/labels');
  });

  it('dashboardAPI', () => {
    dashboardAPI.getOverview();
    expect(instance.get).toHaveBeenCalledWith('/api/dashboard/overview');
    dashboardAPI.getIntegrationStatus();
    expect(instance.get).toHaveBeenCalledWith('/api/dashboard/integrations');
  });

  it('userManagementAPI', () => {
    userManagementAPI.getCurrentUser();
    expect(instance.get).toHaveBeenCalledWith('/api/users/me');
    userManagementAPI.getUserSessions();
    expect(instance.get).toHaveBeenCalledWith('/api/users/sessions');
    userManagementAPI.revokeSession('sess-1');
    expect(instance.delete).toHaveBeenCalledWith('/api/users/sessions/sess-1');
    userManagementAPI.revokeAllSessions();
    expect(instance.delete).toHaveBeenCalledWith('/api/users/sessions');
  });

  it('emailVerificationAPI', () => {
    emailVerificationAPI.verifyEmail('a@b.com', '1234');
    expect(instance.post).toHaveBeenCalledWith('/api/email-verification/verify', {
      email: 'a@b.com',
      code: '1234',
    });
    emailVerificationAPI.sendVerificationEmail('a@b.com');
    expect(instance.post).toHaveBeenCalledWith('/api/email-verification/send', { email: 'a@b.com' });
  });

  it('tenantAPI', () => {
    tenantAPI.getTenantBySubdomain('acme');
    expect(instance.get).toHaveBeenCalledWith('/api/tenants/by-subdomain/acme');
    tenantAPI.getTenantContext();
    expect(instance.get).toHaveBeenCalledWith('/api/tenants/context');
  });

  it('adminAPI', () => {
    adminAPI.getAdminUsers();
    expect(instance.get).toHaveBeenCalledWith('/api/admin/users');
    adminAPI.updateAdminLastLogin('u-1');
    expect(instance.patch).toHaveBeenCalledWith('/api/admin/users/u-1/last-login');
  });

  it('meetingAPI', () => {
    meetingAPI.getMeetingAttendance('task-1');
    expect(instance.get).toHaveBeenCalledWith('/api/meetings/attendance/task-1');
  });

  it('financialAPI', () => {
    financialAPI.getNetWorthSummary();
    expect(instance.get).toHaveBeenCalledWith('/api/financial/net-worth/summary');
    financialAPI.listFinancialAccounts();
    expect(instance.get).toHaveBeenCalledWith('/api/financial/accounts');
  });
});
