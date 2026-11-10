import React from 'react';
import { act, render, waitFor } from '@testing-library/react';
import { useRouter } from 'next/router';

import SsoCallbackPage from '@/pages/auth/sso/callback';
import {
  establishWebSession,
  persistBackendToken,
} from '@/lib/backendAuth';

jest.mock('next/router', () => ({
  useRouter: jest.fn(),
}));

jest.mock('@/lib/backendAuth', () => ({
  establishWebSession: jest.fn(),
  persistBackendToken: jest.fn(),
}));

const originalFetch = global.fetch;

function response(
  body: unknown,
  status = 200,
  contentType = 'application/json',
) {
  return {
    status,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === 'content-type' ? contentType : null,
    },
    json: async () => {
      if (body instanceof Error) throw body;
      return body;
    },
  } as unknown as Response;
}

const validPayload = {
  access_token: 'backend-token',
  token_type: 'bearer',
  email: 'member@example.com',
  return_to: '/settings?tab=account',
};

function routerFor(code: unknown) {
  return {
    isReady: true,
    query: { code },
    replace: jest.fn().mockResolvedValue(true),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function flush() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('SSO callback one-shot exchange', () => {
  let fetchMock: jest.Mock;
  let replaceStateSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    fetchMock = jest.fn().mockResolvedValue(response(validPayload));
    global.fetch = fetchMock as unknown as typeof fetch;
    replaceStateSpy = jest
      .spyOn(window.history, 'replaceState')
      .mockImplementation(() => {});
    (establishWebSession as jest.Mock).mockResolvedValue(undefined);
    (persistBackendToken as jest.Mock).mockImplementation(() => {});
  });

  afterEach(() => {
    global.fetch = originalFetch;
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test('exchanges once, removes the code first, and establishes the SDK before persistence', async () => {
    const router = routerFor('opaque-code');
    (useRouter as jest.Mock).mockReturnValue(router);
    const { container } = render(<SsoCallbackPage />);

    await waitFor(() =>
      expect(establishWebSession).toHaveBeenCalledWith('backend-token'),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(replaceStateSpy.mock.invocationCallOrder[0]).toBeLessThan(
      fetchMock.mock.invocationCallOrder[0],
    );
    expect(replaceStateSpy).toHaveBeenCalledWith(
      window.history.state,
      '',
      '/auth/sso/callback',
    );
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/auth/sso/oidc/web/exchange');
    expect(options.method).toBe('POST');
    expect(options.credentials).toBe('same-origin');
    expect(options.cache).toBe('no-store');
    expect(options.redirect).toBe('error');
    expect(options.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(options.body).code).toBe('opaque-code');
    expect(establishWebSession).toHaveBeenCalledTimes(1);
    expect(persistBackendToken).toHaveBeenCalledTimes(1);
    expect(persistBackendToken).toHaveBeenCalledWith(
      'backend-token',
      'member@example.com',
    );
    expect(
      (establishWebSession as jest.Mock).mock.invocationCallOrder[0],
    ).toBeLessThan(
      (persistBackendToken as jest.Mock).mock.invocationCallOrder[0],
    );
    expect(router.replace).toHaveBeenCalledWith('/settings?tab=account');
    expect(container.innerHTML).not.toContain('backend-token');
  });

  test.each([
    ['missing code', undefined],
    ['empty code', ''],
    ['whitespace code', '   '],
    ['array code', ['one', 'two']],
  ])('%s never exchanges or establishes a session', async (_name, code) => {
    (useRouter as jest.Mock).mockReturnValue(routerFor(code));
    const { container } = render(<SsoCallbackPage />);

    await waitFor(() =>
      expect(container.textContent).toContain('could not be completed'),
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(establishWebSession).not.toHaveBeenCalled();
    expect(persistBackendToken).not.toHaveBeenCalled();
  });

  test.each([
    ['non-200', response({ detail: 'refused' }, 401)],
    ['malformed JSON', response(new Error('bad json'))],
    ['missing token', response({ ...validPayload, access_token: undefined })],
    ['wrong token type', response({ ...validPayload, token_type: 'opaque' })],
    ['missing email', response({ ...validPayload, email: undefined })],
    ['protocol-relative return', response({ ...validPayload, return_to: '//evil.example' })],
    ['backslash return', response({ ...validPayload, return_to: '/\\evil.example' })],
    ['auth-recursive return', response({ ...validPayload, return_to: '/auth/signin' })],
    ['non-JSON content type', response(validPayload, 200, 'text/html')],
  ])('%s does not create an SDK session or persist a token', async (_name, reply) => {
    fetchMock.mockResolvedValue(reply);
    const router = routerFor('opaque-code');
    (useRouter as jest.Mock).mockReturnValue(router);
    render(<SsoCallbackPage />);

    await waitFor(() => expect(router.replace).toHaveBeenCalled());
    expect(establishWebSession).not.toHaveBeenCalled();
    expect(persistBackendToken).not.toHaveBeenCalled();
    expect(router.replace).toHaveBeenCalledWith('/login?sso_error=sso_failed');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test('does not persist when the SDK rejects the backend token', async () => {
    (establishWebSession as jest.Mock).mockRejectedValue(
      new Error('sdk refused'),
    );
    const router = routerFor('opaque-code');
    (useRouter as jest.Mock).mockReturnValue(router);
    render(<SsoCallbackPage />);

    await waitFor(() =>
      expect(router.replace).toHaveBeenCalledWith('/login?sso_error=sso_failed'),
    );
    expect(establishWebSession).toHaveBeenCalledTimes(1);
    expect(persistBackendToken).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test('a transport failure produces one safe failure and no retry', async () => {
    fetchMock.mockRejectedValue(new Error('network'));
    const router = routerFor('opaque-code');
    (useRouter as jest.Mock).mockReturnValue(router);
    render(<SsoCallbackPage />);

    await waitFor(() =>
      expect(router.replace).toHaveBeenCalledWith('/login?sso_error=sso_failed'),
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(establishWebSession).not.toHaveBeenCalled();
    expect(persistBackendToken).not.toHaveBeenCalled();
  });

  test('bounds the one-use exchange with an abort and no hidden retry', async () => {
    jest.useFakeTimers();
    fetchMock.mockImplementation((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new Error('aborted')));
    }));
    const router = routerFor('opaque-code');
    (useRouter as jest.Mock).mockReturnValue(router);
    render(<SsoCallbackPage />);

    await act(async () => {
      jest.advanceTimersByTime(15000);
      await Promise.resolve();
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith('/login?sso_error=sso_failed');
    expect(establishWebSession).not.toHaveBeenCalled();
    expect(persistBackendToken).not.toHaveBeenCalled();
    jest.useRealTimers();
  });

  test('React 18 StrictMode/double effect consumes the code only once', async () => {
    const router = routerFor('opaque-code');
    (useRouter as jest.Mock).mockReturnValue(router);
    render(
      <React.StrictMode>
        <SsoCallbackPage />
      </React.StrictMode>,
    );

    await waitFor(() =>
      expect(establishWebSession).toHaveBeenCalledWith('backend-token'),
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(establishWebSession).toHaveBeenCalledTimes(1);
    expect(persistBackendToken).toHaveBeenCalledTimes(1);
  });

  test('late response from code A cannot persist or navigate after code B starts', async () => {
    const firstFetch = deferred<Response>();
    fetchMock
      .mockImplementationOnce(() => firstFetch.promise)
      .mockResolvedValueOnce(response({
        ...validPayload,
        access_token: 'backend-token-b',
        return_to: '/dashboard',
      }));
    const first = routerFor('opaque-code-a');
    (useRouter as jest.Mock).mockReturnValue(first);
    const view = render(<SsoCallbackPage />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const second = routerFor('opaque-code-b');
    (useRouter as jest.Mock).mockReturnValue(second);
    view.rerender(<SsoCallbackPage />);
    await waitFor(() =>
      expect(persistBackendToken).toHaveBeenCalledWith(
        'backend-token-b',
        'member@example.com',
      ),
    );

    firstFetch.resolve(response(validPayload));
    await flush();

    expect(persistBackendToken).toHaveBeenCalledTimes(1);
    expect(first.replace).not.toHaveBeenCalledWith('/settings?tab=account');
    expect(second.replace).toHaveBeenCalledWith('/dashboard');
  });

  test('late response from code A cannot persist or navigate after the code becomes invalid', async () => {
    const firstFetch = deferred<Response>();
    fetchMock.mockImplementationOnce(() => firstFetch.promise);
    const first = routerFor('opaque-code-a');
    (useRouter as jest.Mock).mockReturnValue(first);
    const view = render(<SsoCallbackPage />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const invalid = routerFor(undefined);
    (useRouter as jest.Mock).mockReturnValue(invalid);
    view.rerender(<SsoCallbackPage />);
    await waitFor(() =>
      expect(invalid.replace).toHaveBeenCalledWith('/login?sso_error=sso_failed'),
    );

    firstFetch.resolve(response(validPayload));
    await flush();

    expect(establishWebSession).not.toHaveBeenCalled();
    expect(persistBackendToken).not.toHaveBeenCalled();
    expect(first.replace).not.toHaveBeenCalledWith('/settings?tab=account');
  });

  test('late response after unmount cannot persist or navigate', async () => {
    const firstFetch = deferred<Response>();
    fetchMock.mockImplementationOnce(() => firstFetch.promise);
    const router = routerFor('opaque-code');
    (useRouter as jest.Mock).mockReturnValue(router);
    const view = render(<SsoCallbackPage />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    view.unmount();
    firstFetch.resolve(response(validPayload));
    await flush();

    expect(establishWebSession).not.toHaveBeenCalled();
    expect(persistBackendToken).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });

  test('serializes SDK establishment so a late old-code SDK cannot overwrite the new code', async () => {
    const firstSdk = deferred<void>();
    (establishWebSession as jest.Mock)
      .mockImplementationOnce(() => firstSdk.promise)
      .mockResolvedValueOnce(undefined);
    fetchMock
      .mockResolvedValueOnce(response({
        ...validPayload,
        access_token: 'backend-token-a',
        return_to: '/settings?tab=account',
      }))
      .mockResolvedValueOnce(response({
        ...validPayload,
        access_token: 'backend-token-b',
        return_to: '/dashboard',
      }));
    const first = routerFor('opaque-code-a');
    (useRouter as jest.Mock).mockReturnValue(first);
    const view = render(<SsoCallbackPage />);
    await waitFor(() => expect(establishWebSession).toHaveBeenCalledTimes(1));

    const second = routerFor('opaque-code-b');
    (useRouter as jest.Mock).mockReturnValue(second);
    view.rerender(<SsoCallbackPage />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await flush();
    expect(establishWebSession).toHaveBeenCalledTimes(1);
    expect(persistBackendToken).not.toHaveBeenCalled();

    firstSdk.resolve();
    await waitFor(() =>
      expect(persistBackendToken).toHaveBeenCalledWith(
        'backend-token-b',
        'member@example.com',
      ),
    );
    expect(establishWebSession).toHaveBeenCalledTimes(2);
    expect(persistBackendToken).toHaveBeenCalledTimes(1);
    expect(first.replace).not.toHaveBeenCalledWith('/settings?tab=account');
    expect(second.replace).toHaveBeenCalledWith('/dashboard');
  });

  test('a genuinely new independent code navigation is exchanged once for the new code', async () => {
    const first = routerFor('opaque-code');
    (useRouter as jest.Mock).mockReturnValue(first);
    const view = render(<SsoCallbackPage />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fetchMock.mockResolvedValue(response({
      ...validPayload,
      access_token: 'backend-token-2',
      return_to: '/dashboard',
    }));
    const second = routerFor('opaque-code-2');
    (useRouter as jest.Mock).mockReturnValue(second);
    view.rerender(<SsoCallbackPage />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][1].body).toBe(
      JSON.stringify({ code: 'opaque-code-2' }),
    );
    expect(establishWebSession).toHaveBeenCalledTimes(2);
    expect(persistBackendToken).toHaveBeenCalledTimes(2);
    expect(second.replace).toHaveBeenCalledWith('/dashboard');
  });
});
