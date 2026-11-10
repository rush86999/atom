import { NextResponse } from 'next/server';

import type { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';
import { resolveWebAuthSecret } from './lib/web-auth-config';

const SESSION_COOKIE = 'next-auth.session-token';
const SECURE_SESSION_COOKIE = `__Secure-${SESSION_COOKIE}`;

// Define public pages that don't require authentication. Exact paths only:
// a prefix rule here would make every /auth/* route (and any lookalike) public.
const publicPageRoutes = new Set([
  // BUG-120: /dashboard removed from public routes — it's the main
  // authenticated landing page and must require auth. Leaving it public
  // rendered the full app shell for unauthenticated users.
  '/login',
  '/auth/signin',
  '/auth/signup',
  '/auth/error',
  // Genuine password-recovery and email-verification pages. Their forms
  // submit to the backend, which remains the token/currentUser authority;
  // page visibility is not reset or verification authority.
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
  '/auth/verification-sent',
]);

// Define API routes that don't require authentication
const publicApiRoutes = [
  '/api/auth',
  '/api/health',
  '/api/dev',
  '/api/hubspot/oauth/start',
  '/api/integrations/hubspot/callback',
  '/api/integrations/zoom/auth/start',
  '/api/integrations/zoom/callback',
  '/api/integrations/salesforce/auth/start',
  '/api/integrations/salesforce/callback',
  '/api/integrations/slack/auth/start',
  '/api/integrations/slack/callback',
];

function isPublicPageRoute(pathname: string): boolean {
  return publicPageRoutes.has(pathname);
}

function isPublicApiRoute(pathname: string): boolean {
  return publicApiRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
}

function isChunkOf(cookieName: string, baseName: string): boolean {
  if (!cookieName.startsWith(`${baseName}.`)) {
    return false;
  }
  return /^\d+$/.test(cookieName.slice(baseName.length + 1));
}

function hasSessionCookie(request: NextRequest, name: string): boolean {
  return request.cookies.getAll().some(
    ({ name: cookieName, value }) =>
      value.length > 0 &&
      (cookieName === name || isChunkOf(cookieName, name)),
  );
}

function prefersSecureCookie(request: NextRequest): boolean {
  const configured = process.env.NEXTAUTH_URL;
  if (configured) {
    return configured.startsWith('https://');
  }
  return (
    Boolean(process.env.VERCEL) ||
    process.env.NODE_ENV === 'production' ||
    request.nextUrl.protocol === 'https:'
  );
}

/**
 * Page admission only: decode the installed SDK's encrypted session cookie.
 * The backend stays the authorization authority; no role or claim is read here.
 * Authorization headers are excluded so only a browser cookie can admit a page.
 */
async function hasDecodedWebSession(request: NextRequest): Promise<boolean> {
  const candidates = prefersSecureCookie(request)
    ? [SECURE_SESSION_COOKIE, SESSION_COOKIE]
    : [SESSION_COOKIE, SECURE_SESSION_COOKIE];
  // Use the expected cookie name first. Only fall back to the other variant
  // when the expected name is entirely absent, so an invalid expected cookie
  // can never be replaced by a different cookie.
  const cookieName = candidates.find((name) => hasSessionCookie(request, name));
  if (!cookieName) {
    return false;
  }

  let secret: string;
  try {
    secret = resolveWebAuthSecret();
  } catch {
    // Missing or placeholder signing material admits nothing.
    return false;
  }

  try {
    // The SDK's SessionStore reassembles .0/.1 chunks and authenticates the
    // encrypted JWT. The empty headers also disable getToken's Bearer fallback.
    const token = await getToken({
      req: {
        cookies: request.cookies,
        headers: new Headers(),
      } as unknown as NextRequest,
      secret,
      cookieName,
      secureCookie: cookieName === SECURE_SESSION_COOKIE,
    });
    return Boolean(token);
  } catch {
    // Wrong key, expired/tampered token, malformed chunks, or SDK failure.
    return false;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === '/') {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  // Public pages use exact matching; public API routes use path-segment
  // matching. Neither grants blanket /auth or /settings admission.
  const isPublicRoute = isPublicPageRoute(pathname);
  const isPublicApiPath = isPublicApiRoute(pathname);

  // Forward the auth cookie as a Bearer header for API requests. Pages use
  // plain same-origin `fetch("/api/...")`; the Python backend authenticates
  // with a Bearer header only. This runs for public API paths too (2FA
  // status, sessions, notifications): they do not REQUIRE a token, but when
  // one is present the backend needs it. NextAuth's own /api/auth/* handlers
  // still take precedence over the rewrite.
  const withAuthHeader = () => {
    const authToken = request.cookies.get('auth_token')?.value;
    if (authToken && !request.headers.get('authorization')) {
      const headers = new Headers(request.headers);
      headers.set('authorization', `Bearer ${authToken}`);
      return NextResponse.next({ request: { headers } });
    }
    return NextResponse.next();
  };

  // Allow public page routes without authentication.
  if (isPublicRoute) {
    return NextResponse.next();
  }

  // API routes never redirect to the /login HTML page.
  if (isPublicApiPath || pathname.startsWith('/api/')) {
    return withAuthHeader();
  }

  // Page admission only: the legacy auth_token cookie is still accepted, and
  // the actual NextAuth session cookie (secure or development name, chunked)
  // is decoded with the installed SDK. This is a first-line gate — the real
  // authorization is API-level (Depends(get_current_user) on every backend
  // endpoint), and the backend current-user check remains authoritative.
  const authToken = request.cookies.get('auth_token')?.value;
  const hasWebSession = authToken ? false : await hasDecodedWebSession(request);

  if (!authToken && !hasWebSession) {
    const signInUrl = new URL('/login', request.url);
    // The login pages accept only same-app relative return targets
    // (`/path?query`, never `//host`). Passing the absolute request URL made
    // every deep-link bounce fall back to /dashboard, so preserve exactly the
    // path and query here; the open-redirect guard stays on the consumer.
    const callbackUrl = `${request.nextUrl.pathname}${request.nextUrl.search}`;
    signInUrl.searchParams.set('callbackUrl', callbackUrl);
    return NextResponse.redirect(signInUrl);
  }

  // User has a token cookie, allow the request to proceed
  return NextResponse.next();
}

// Configure which routes the middleware should run on
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};



