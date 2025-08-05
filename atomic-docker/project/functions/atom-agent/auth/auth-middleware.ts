import { Request } from 'express';
import jwt from 'jsonwebtoken';
import { createClient } from '@supabase/supabase-js';

// JWT secret - should be loaded from environment in production
const JWT_SECRET = process.env.JWT_SECRET || 'your-super-secret-jwt-key-change-in-production';

interface AuthenticatedRequest extends Request {
  user?: {
    id: string;
    email: string;
    roles?: string[];
  };
}

interface JWTPayload {
  id: string;
  email: string;
  roles?: string[];
  exp?: number;
  iat?: number;
}

class AuthMiddleware {
  private supabaseClient;

  constructor() {
    // Initialize Supabase client
    const supabaseUrl = process.env.SUPABASE_URL || '';
    const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || '';

    if (supabaseUrl && supabaseKey) {
      this.supabaseClient = createClient(supabaseUrl, supabaseKey);
    }
  }

  /**
   * Extract user ID from JWT token or session
   * @param req Express request object
   * @returns User ID if authenticated, null otherwise
   */
  async getAuthenticatedUserId(req: AuthenticatedRequest | any): Promise<string | null> {
    try {
      // Priority 1: JWT from Authorization header
      const authHeader = req.headers?.authorization;
      if (authHeader && authHeader.startsWith('Bearer ')) {
        const token = authHeader.substring(7);
        const decoded = jwt.verify(token, JWT_SECRET) as JWTPayload;

        if (decoded && decoded.id) {
          req.user = {
            id: decoded.id,
            email: decoded.email,
            roles: decoded.roles
          };
          return decoded.id;
        }
      }

      // Priority 2: Session cookie
      const sessionToken = req.cookies?.session || req.headers?.['x-session-token'];
      if (sessionToken) {
        const userId = await this.validateSession(sessionToken);
        if (userId) {
          req.user = { id: userId }; // Additional user data can be fetched
          return userId;
        }
      }

      // Priority 3: API key (for external integrations)
      const apiKey = req.headers?.['x-api-key'];
      if (apiKey) {
        const userId = await this.validateApiKey(apiKey);
        if (userId) {
          req.user = { id: userId };
          return userId;
        }
      }

      // Fallback: For testing environments with mock users
      const isTestEnvironment = process.env.NODE_ENV === 'test' || process.env.TESTING === 'true';
      if (isTestEnvironment) {
        return this.getTestUserId(req);
      }

      return null;
    } catch (error) {
      console.error('Auth middleware error:', error);
      return null;
    }
  }

  /**
   * Validate session token from auth.sessions table
   * @param sessionToken The session token to validate
   * @returns User ID if valid session, null otherwise
   */
  private async validateSession(sessionToken: string): Promise<string | null> {
    try {
      if (!this.supabaseClient) return null;

      const { data, error } = await this.supabaseClient
        .from('auth.sessions')
        .select('user_id, expires_at')
        .eq('refresh_token', sessionToken)
        .eq('revoked', false)
        .gt('expires_at', new Date().toISOString())
        .single();

      if (error || !data) {
        console.error('Session validation error:', error);
        return null;
      }

      return data.user_id;
    } catch (error) {
      console.error('Session validation exception:', error);
      return null;
    }
  }

  /**
   * Validate API key for external integrations
   * @param apiKey The API key to validate
   * @returns User ID if valid API key, null otherwise
   */
  private async validateApiKey(apiKey: string): Promise<string | null> {
    try {
      // In a real implementation, you'd query your API keys table
      // This is a placeholder implementation
      const userIdFromApiKey = process.env.API_KEY_USERS?.split(',').find(pair =>
        pair.split(':')[1] === apiKey
      )?.split(':')[0];

      return userIdFromApiKey || null;
    } catch (error) {
      console.error('API key validation error:', error);
      return null;
    }
  }

  /**
   * Get test user ID for testing environments
   * @param req Request object
   * @returns Test user ID
   */
  private getTestUserId(req: any): string | null {
    // Check for test user override in headers
    const testUserHeader = req.headers?.['x-test-user-id'];
    if (testUserHeader) return testUserHeader;

    // Get from environment for backward compatibility
    const testUserId = process.env.TEST_USER_ID || process.env.USER_ID || 'test_user_001';
    return testUserId;
  }

  /**
   * Generate JWT token for a user
   * @param userId The user ID
   * @param email User email
   * @param roles User roles
   * @returns JWT token
   */
  generateToken(userId: string, email: string, roles?: string[]): string {
    return jwt.sign(
      {
        id: userId,
        email,
        roles: roles || ['user']
      },
      JWT_SECRET,
      { expiresIn: '24h' }
    );
  }

  /**
   * Express middleware wrapper
   */
  public expressMiddleware() {
    return async (req: any, res: any, next: any) => {
      const userId = await this.getAuthenticatedUserId(req);

      if (!userId) {
        return res.status(401).json({
          error: 'Unauthorized',
          message: 'Valid authentication required'
        });
      }

      req.userId = userId;
      next();
    };
  }
}

// Export singleton instance
export const authMiddleware = new AuthMiddleware();

// Export types
export type { AuthenticatedRequest, JWTPayload };
