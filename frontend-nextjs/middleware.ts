import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';

// Define public routes that don't require authentication
const publicRoutes = [
  '/auth/signin',
  '/auth/signup',
  '/auth/error',
  '/api/auth',
];

// Define API routes that don't require authentication
const publicApiRoutes = [
  '/api/auth',
  '/api/health',
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

  // Get the token from the request
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET,
  });

  // If there's no token and the route is not public, redirect to sign in
  if (!token) {
    const signInUrl = new URL('/auth/signin', request.url);
    signInUrl.searchParams.set('callbackUrl', request.url);
    return NextResponse.redirect(signInUrl);
  }

  // User is authenticated, allow the request to proceed
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
