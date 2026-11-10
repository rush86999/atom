import React, { useEffect, useRef, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { establishWebSession, persistBackendToken } from '@/lib/backendAuth';
import { validateSameAppReturnTo } from '@/lib/safe-return-to';

type ExchangePayload = {
  access_token: string;
  token_type: 'bearer';
  email: string;
  return_to: string;
};

const EXCHANGE_PATH = '/api/auth/sso/oidc/web/exchange';
const CALLBACK_PATH = '/auth/sso/callback';
const SAFE_FAILURE_PATH = '/login?sso_error=sso_failed';
const MAX_CODE_LENGTH = 512;
const EXCHANGE_TIMEOUT_MS = 15_000;

function validCode(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    value.length <= MAX_CODE_LENGTH &&
    value === value.trim() &&
    !/\s/.test(value)
  );
}

function validExchangePayload(value: unknown): value is ExchangePayload {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const data = value as Record<string, unknown>;
  return (
    typeof data.access_token === 'string' &&
    data.access_token.length > 0 &&
    data.access_token.length <= 4096 &&
    !/\s/.test(data.access_token) &&
    data.token_type === 'bearer' &&
    typeof data.email === 'string' &&
    data.email.length > 0 &&
    data.email.length <= 320 &&
    data.email === data.email.trim() &&
    !/\s/.test(data.email) &&
    typeof data.return_to === 'string'
  );
}

export default function SsoCallbackPage() {
  const router = useRouter();
  const handledCode = useRef<string | null>(null);
  const mountedRef = useRef(true);
  const generationRef = useRef(0);
  const currentCodeRef = useRef<string | null>(null);
  const sdkChainRef = useRef<Promise<void>>(Promise.resolve());
  const [status, setStatus] = useState('Completing sign-in…');

  // A real unmount invalidates late work. StrictMode's simulated cleanup is
  // followed immediately by setup, restoring true before async work resumes;
  // deliberately no exchange-cancellation flag here, which would otherwise
  // suppress both StrictMode attempts while handledCode blocks the second.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!router.isReady) return;

    const rawCode = router.query.code;
    const code = validCode(rawCode) ? rawCode : null;

    // Remove the opaque one-use code from the visible URL before any network
    // exchange. RFC 9700 requires one-time codes and no credentials in URLs.
    if (typeof window !== 'undefined') {
      window.history.replaceState(window.history.state, '', CALLBACK_PATH);
    }

    if (!code) {
      if (handledCode.current !== '__invalid__') {
        handledCode.current = '__invalid__';
        generationRef.current += 1;
        currentCodeRef.current = null;
        setStatus('SSO sign-in could not be completed. Please try again.');
        void router.replace(SAFE_FAILURE_PATH);
      }
      return;
    }

    // React 18 StrictMode/double effects and child rerenders must not burn the
    // same one-use code twice. A genuinely new code is a new independent
    // navigation and is allowed exactly once.
    if (handledCode.current === code) return;
    handledCode.current = code;

    const generation = generationRef.current + 1;
    generationRef.current = generation;
    currentCodeRef.current = code;
    const isCurrent = () =>
      mountedRef.current &&
      generationRef.current === generation &&
      currentCodeRef.current === code;
    const fail = () => {
      if (!isCurrent()) return;
      setStatus('SSO sign-in could not be completed. Please try again.');
      void router.replace(SAFE_FAILURE_PATH);
    };

    const exchange = async () => {
      const controller = new AbortController();
      const timeout = setTimeout(
        () => controller.abort(),
        EXCHANGE_TIMEOUT_MS,
      );
      let data: unknown;
      try {
        // Same-origin POST: the backend requires the HttpOnly state cookie and
        // exact Origin. No retry: an uncertain response may already have
        // consumed the one-use code. Abort bounds an indefinite spinner.
        const response = await fetch(EXCHANGE_PATH, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
          },
          body: JSON.stringify({ code }),
          credentials: 'same-origin',
          cache: 'no-store',
          redirect: 'error',
          signal: controller.signal,
        });
        if (!isCurrent()) return;
        if (response.status !== 200) {
          fail();
          return;
        }

        const contentType = response.headers.get('content-type') || '';
        if (!/^application\/json(?:\s*;|$)/i.test(contentType)) {
          fail();
          return;
        }

        try {
          data = await response.json();
        } catch {
          fail();
          return;
        }
      } catch {
        fail();
        return;
      } finally {
        clearTimeout(timeout);
      }

      if (!isCurrent()) return;
      if (!validExchangePayload(data)) {
        fail();
        return;
      }
      const payload = data;
      const returnTo = validateSameAppReturnTo(payload.return_to);
      if (!returnTo) {
        fail();
        return;
      }
      if (!isCurrent()) return;

      // Installed NextAuth v4 API: establishWebSession calls
      // signIn('credentials', { backendToken, redirect: false }). Serialize
      // SDK commits so a late old-code call cannot overwrite a newer code's
      // session after a new navigation starts.
      const sdkRun = sdkChainRef.current.then(() =>
        establishWebSession(payload.access_token),
      );
      sdkChainRef.current = sdkRun.then(
        (): void => undefined,
        (): void => undefined,
      );
      try {
        await sdkRun;
      } catch {
        fail();
        return;
      }

      if (!isCurrent()) return;
      try {
        persistBackendToken(payload.access_token, payload.email);
      } catch {
        fail();
        return;
      }

      if (!isCurrent()) return;
      void router.replace(returnTo);
    };

    void exchange();
  }, [router, router.isReady, router.query.code]);

  return (
    <>
      <Head>
        <title>Completing sign-in - ATOM</title>
        <meta name="referrer" content="no-referrer" />
        <meta name="robots" content="noindex, nofollow" />
      </Head>
      <main className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
        <div
          role="status"
          data-testid="sso-callback-status"
          className="max-w-md text-center text-gray-700 dark:text-gray-300"
        >
          <p>{status}</p>
        </div>
      </main>
    </>
  );
}
