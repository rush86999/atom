import { NextResponse } from 'next/server';

import type { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';

// Define public routes that don't require authentication
const publicRoutes = [
  '/dashboard',
  '/login',
  '/auth/signin',
  '/auth/signup',
  '/auth/error',
  '/api/auth',
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

  // Allow public routes and API routes to proceed without authentication
  if (isPublicRoute || isPublicApiRoute) {
    return NextResponse.next();
  }

  // Check if pathname is an API route - API routes should NEVER redirect to /login HTML page
  if (pathname.startsWith('/api/')) {
    return NextResponse.next();
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



