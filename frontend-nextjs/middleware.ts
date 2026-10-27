import { NextResponse } from 'next/server';

import type { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';

// Define public routes that don't require authentication
// Define public routes that don't require authentication
const publicRoutes = [
  // BUG-120: /dashboard removed from public routes — it's the main
  // authenticated landing page and must require auth. Leaving it public
  // rendered the full app shell for unauthenticated users.
  '/login',
  '/auth/signin',
  '/auth/signup',
  '/auth/error',
];

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

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === '/') {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  // Check if the current path is a public route
  const isPublicRoute = publicRoutes.some(route =>
    pathname.startsWith(route)
  );

  // Check if the current path is a public API route
  const isPublicApiRoute = publicApiRoutes.some(route =>
    pathname.startsWith(route)
  );

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
  if (isPublicApiRoute || pathname.startsWith('/api/')) {
    return withAuthHeader();
  }

  // Client-side route protection: check for the auth_token cookie (set on
  // login by lib/auth.ts). This is a first-line gate — the real security
  // enforcement is API-level (Depends(get_current_user) on every backend
  // endpoint). This middleware prevents unauthenticated users from seeing
  // page shells; without it, every route is public.
  const authToken = request.cookies.get('auth_token')?.value;
  const sessionCookie = request.cookies.get('next-auth.session-token')?.value;

  if (!authToken && !sessionCookie) {
    const signInUrl = new URL('/login', request.url);
    signInUrl.searchParams.set('callbackUrl', request.url);
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



