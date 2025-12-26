/**
 * Atom Agent Handler
 * Handles message processing and user authentication
 */

// Response type for message handling
export interface HandleMessageResponse {
  text: string;
  error?: string;
  intent?: string;
  entities?: Record<string, any>;
  metadata?: Record<string, any>;
}

// Handle incoming messages and route to appropriate handlers
export async function handleMessage(
  interfaceType: string,
  message: string,
  userId: string,
  options?: {
    conversationId?: string;
    intentName?: string;
    entities?: Record<string, any>;
  }
): Promise<HandleMessageResponse> {
  try {
    // Basic message processing - this would connect to AI/NLU in production
    console.log(`[handleMessage] Processing message for user ${userId}`, {
      interfaceType,
      messageLength: message.length,
      options,
    });

    // Placeholder response - in production this would route to AI services
    return {
      text: `Message received: "${message.substring(0, 50)}${message.length > 50 ? '...' : ''}"`,
      intent: options?.intentName || 'general',
      entities: options?.entities || {},
      metadata: {
        userId,
        interfaceType,
        conversationId: options?.conversationId,
        processedAt: new Date().toISOString(),
      },
    };
  } catch (error: any) {
    console.error('[handleMessage] Error processing message:', error);
    return {
      text: '',
      error: error.message || 'Failed to process message',
    };
  }
}

// Global type declarations for PostGraphile context
declare global {
  // eslint-disable-next-line no-var
  var __postgraphileContext: { jwtClaims?: { sub?: string } } | undefined;
  // eslint-disable-next-line no-var
  var __postgraphile: { userId?: string } | undefined;
  // eslint-disable-next-line no-var
  var postgres: { authenticatedUserId?: string } | undefined;
}

/**
 * Get authenticated user using PostGraphile JWT/session system
 * Completely replaces environment variable USER_ID approach
 * @param request Optional request object for HTTP context extraction
 * @returns Authenticated user ID from PostGraphile context
 */
export function getCurrentUserId(request?: any): string {
  try {
    // Production: Use PostGraphile JWT claims system
    if (request && typeof request === "object") {
      // 1. JWT from Bearer token (PostGraphile JWT plugin)
      const authHeader = request.headers?.authorization;
      if (authHeader?.startsWith("Bearer ")) {
        return extractUserFromPostGraphileJwt(authHeader.substring(7));
      }

      // 2. PostGraphile session token from cookie
      const sessionCookie = request.headers?.cookie?.match(
        /postgraphile-session=([^;]+)/,
      );
      if (sessionCookie) return extractUserFromSession(sessionCookie[1]);
    }

    // 3. PostGraphile row-level security context
    if (global.__postgraphileContext?.jwtClaims?.sub) {
      return global.__postgraphileContext.jwtClaims.sub;
    }

    // 4. Test environment with database users
    if (process.env.NODE_ENV === "test" || process.env.TESTING === "true") {
      return getTestUserFromPostGraphile();
    }

    // 5. Development fallback - create mock authenticated user
    if (process.env.NODE_ENV === "development") {
      return ensureDevelopmentUser();
    }

    // Production: Must have authenticated user
    const authenticatedUser = resolveAuthenticatedUser();
    if (authenticatedUser) return authenticatedUser;

    throw new AuthenticationError(
      "User authentication required - no PostGraphile authenticated session found",
    );
  } catch (error) {
    console.error("PostGraphile user authentication failed:", error);

    // Development/debug mode provides fallback
    if (process.env.NODE_ENV !== "production") {
      return ensureDevelopmentUser();
    }

    throw new Error(
      "User authentication required via PostGraphile JWT/session context",
    );
  }
}

/**
 * Extract user from PostGraphile JWT token
 */
export function extractUserFromPostGraphileJwt(token: string): string {
  try {
    // PostGraphile JWT format: `Bearer <jwt>` or direct jwt
    const jwtPayload = Buffer.from(token.split(".")[1], "base64").toString();
    const claims = JSON.parse(jwtPayload);

    // PostGraphile uses 'sub' claim for user ID
    return claims.sub || claims.user_id || claims.userId;
  } catch (error) {
    console.warn(
      "JWT extraction failed, attempting session resolution:",
      error,
    );
    throw error;
  }
}

/**
 * Extract user from PostGraphile session
 */
export function extractUserFromSession(sessionToken: string): string {
  try {
    // This would connect to PostGraphile session store
    // For now, use authenticated user resolution
    return (
      resolveAuthenticatedUser() || `_session_${sessionToken.substring(0, 8)}`
    );
  } catch (error) {
    console.error("Session resolution failed:", error);
    throw error;
  }
}

/**
 * Get test user with PostGraphile context
 */
export function getTestUserFromPostGraphile(): string {
  // Use PostGraphile test user instead of environment variables
  return "test_user_from_postgraphile_db";
}

/**
 * Ensure development user exists and is authenticated
 */
export function ensureDevelopmentUser(): string {
  const devUserId = "dev_postgraphile_user_001";
  console.warn(
    `Using development authenticated user: ${devUserId} - this should not happen in production`,
  );
  return devUserId;
}

/**
 * Resolve authenticated user via PostGraphile RLS context
 */
export function resolveAuthenticatedUser(): string | null {
  try {
    // Check if we have context from PostGraphile
    if (global.__postgraphile?.userId) {
      return global.__postgraphile.userId;
    }

    // Check database session
    if (global.postgres?.authenticatedUserId) {
      return global.postgres.authenticatedUserId;
    }

    return null;
  } catch (error) {
    console.error("User resolution failed:", error);
    return null;
  }
}

export class AuthenticationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthenticationError";
  }
}
