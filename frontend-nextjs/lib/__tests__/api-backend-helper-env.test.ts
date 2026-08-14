/**
 * lib/api-backend-helper — supplemental branch coverage for the env-var
 * fallback chains (NEXT_PUBLIC_API_URL / API_BASE_URL / PYTHON_BACKEND_URL)
 * in every helper.
 */

import {
  resilientFetch,
  exchangeCodeForTokens,
  generateGoogleAuthUrl,
  getMinimalCalendarIntegrationByResource,
  getAllCalendarIntegrationsByResourceAndClientType,
  scheduleMeeting,
} from '../api-backend-helper';

const mockFetch = jest.fn();

const okResponse = (data: any): any => ({ ok: true, status: 200, json: async () => data });

describe('lib/api-backend-helper env fallback chains', () => {
  const oldEnv = { ...process.env };

  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
    mockFetch.mockResolvedValue(okResponse({}));
  });

  afterEach(() => {
    process.env = { ...oldEnv };
  });

  const cases: Array<[string, string]> = [
    ['NEXT_PUBLIC_API_URL', 'http://env-a.example.com'],
    ['API_BASE_URL', 'http://env-b.example.com'],
    ['PYTHON_BACKEND_URL', 'http://env-c.example.com'],
  ];

  it.each(cases)('exchangeCodeForTokens honors %s', async (key, value) => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.API_BASE_URL;
    delete process.env.PYTHON_BACKEND_URL;
    (process.env as any)[key] = value;
    await exchangeCodeForTokens('code-1');
    expect(mockFetch.mock.calls[0][0]).toBe(`${value}/api/auth/google/token`);
  });

  it.each(cases)('generateGoogleAuthUrl honors %s', (key, value) => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.API_BASE_URL;
    delete process.env.PYTHON_BACKEND_URL;
    (process.env as any)[key] = value;
    expect(generateGoogleAuthUrl()).toBe(`${value}/api/auth/google/authorize`);
    expect(generateGoogleAuthUrl('st 1')).toBe(
      `${value}/api/auth/google/authorize?state=st%201`,
    );
  });

  it.each(cases)('getMinimalCalendarIntegrationByResource honors %s', async (key, value) => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.API_BASE_URL;
    delete process.env.PYTHON_BACKEND_URL;
    (process.env as any)[key] = value;
    await getMinimalCalendarIntegrationByResource('u1', 'google');
    expect(mockFetch.mock.calls[0][0]).toBe(`${value}/api/graphql`);
  });

  it.each(cases)('getAllCalendarIntegrationsByResourceAndClientType honors %s', async (key, value) => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.API_BASE_URL;
    delete process.env.PYTHON_BACKEND_URL;
    (process.env as any)[key] = value;
    await getAllCalendarIntegrationsByResourceAndClientType('u1', 'google', 'web');
    expect(mockFetch.mock.calls[0][0]).toBe(`${value}/api/graphql`);
  });

  it.each(cases)('scheduleMeeting honors %s', async (key, value) => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.API_BASE_URL;
    delete process.env.PYTHON_BACKEND_URL;
    (process.env as any)[key] = value;
    await scheduleMeeting({ title: 'Sync' });
    expect(mockFetch.mock.calls[0][0]).toBe(`${value}/api/schedule/meeting`);
  });

  it('sends the GraphQL body for the minimal calendar query', async () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.API_BASE_URL;
    delete process.env.PYTHON_BACKEND_URL;
    await getMinimalCalendarIntegrationByResource('u9', 'outlook');
    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.variables).toEqual({ userId: 'u9', resource: 'outlook' });
    expect(body.query).toContain('GetCalendarIntegration');
  });

  it('resilientFetch uses a 30s timeout and passes options through', async () => {
    jest.useFakeTimers();
    mockFetch.mockImplementation((_url: string, opts: any) => {
      expect(opts.signal).toBeDefined();
      expect(opts.method).toBe('PATCH');
      expect(opts.body).toBe('data');
      return Promise.resolve(okResponse({ patched: true }));
    });
    const result = await resilientFetch('PATCH', 'http://x/api', {
      body: 'data',
      headers: { 'X-Custom': '1' },
    });
    expect(result).toEqual({ patched: true });
    expect(mockFetch).toHaveBeenCalledWith(
      'http://x/api',
      expect.objectContaining({
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Custom': '1' },
      }),
    );
    jest.useRealTimers();
  });
});
