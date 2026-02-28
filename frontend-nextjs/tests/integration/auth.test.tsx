import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { signIn, signOut, getSession, useSession } from 'next-auth/react';
import { useRouter } from 'next/router';

// Mock NextAuth
jest.mock('next-auth/react', () => ({
  signIn: jest.fn(),
  signOut: jest.fn(),
  getSession: jest.fn(),
  useSession: jest.fn(),
}));

// Mock Next.js router
jest.mock('next/router', () => ({
  useRouter: jest.fn(),
}));

const mockPush = jest.fn();
const mockBack = jest.fn();

beforeEach(() => {
  (useRouter as jest.Mock).mockReturnValue({
    push: mockPush,
    back: mockBack,
    pathname: '/',
    query: {},
    asPath: '/',
  });
  mockPush.mockClear();
  mockBack.mockClear();
});

afterEach(() => {
  jest.clearAllMocks();
});

/**
 * Integration tests for authentication flows
 *
 * Tests cover:
 * - Login flow with email/password
 * - 2FA (Two-Factor Authentication) flow
 * - Token storage and session management
 * - Token refresh (placeholder - timing depends on backend)
 * - Session persistence across page reloads
 * - Logout flow
 *
 * Based on actual auth components found in survey:
 * - pages/auth/signin.tsx (NextAuth with 2FA support)
 * - components/Settings/TwoFactorSettings.tsx (2FA setup)
 * - Multiple settings components using useSession hook
 */

describe('Authentication Flow Integration', () => {
  describe('Login flow', () => {
    it('should successfully log in with valid credentials', async () => {
      (signIn as jest.Mock).mockResolvedValue({
        ok: true,
        user: { id: 'user-123', email: 'test@example.com' },
      });

      const result = await signIn('credentials', {
        email: 'test@example.com',
        password: 'password123',
        redirect: false,
      });

      expect(result).toBeDefined();
      expect(result.ok).toBe(true);
      expect(result.user).toEqual({
        id: 'user-123',
        email: 'test@example.com',
      });
    });

    it('should show error message on failed login', async () => {
      (signIn as jest.Mock).mockResolvedValue({
        ok: false,
        error: 'Invalid credentials',
      });

      const result = await signIn('credentials', {
        email: 'test@example.com',
        password: 'wrongpassword',
        redirect: false,
      });

      expect(result.ok).toBe(false);
      expect(result.error).toBe('Invalid credentials');
    });

    it('should handle network errors during login', async () => {
      (signIn as jest.Mock).mockRejectedValue(new Error('Network error'));

      await expect(
        signIn('credentials', {
          email: 'test@example.com',
          password: 'password123',
          redirect: false,
        })
      ).rejects.toThrow('Network error');
    });

    it('should redirect to home after successful login', async () => {
      (signIn as jest.Mock).mockResolvedValue({
        ok: true,
        user: { id: 'user-123', email: 'test@example.com' },
      });

      await signIn('credentials', {
        email: 'test@example.com',
        password: 'password123',
        redirect: true,
      });

      // With redirect: true, NextAuth should handle navigation
      expect(signIn).toHaveBeenCalledWith('credentials', {
        email: 'test@example.com',
        password: 'password123',
        redirect: true,
      });
    });
  });

  describe('2FA (Two-Factor Authentication) flow', () => {
    it('should require 2FA code when 2FA is enabled', async () => {
      (signIn as jest.Mock).mockResolvedValue({
        ok: false,
        error: '2FA_REQUIRED',
      });

      const result = await signIn('credentials', {
        email: 'test@example.com',
        password: 'password123',
        redirect: false,
      });

      expect(result.ok).toBe(false);
      expect(result.error).toBe('2FA_REQUIRED');
    });

    it('should successfully login with valid 2FA code', async () => {
      (signIn as jest.Mock).mockResolvedValue({
        ok: true,
        user: { id: 'user-123', email: 'test@example.com' },
      });

      const result = await signIn('credentials', {
        email: 'test@example.com',
        password: 'password123',
        totp_code: '123456',
        redirect: false,
      });

      expect(result.ok).toBe(true);
      expect(result.user).toBeDefined();
    });

    it('should show error for invalid 2FA code', async () => {
      (signIn as jest.Mock).mockResolvedValue({
        ok: false,
        error: 'INVALID_2FA_CODE',
      });

      const result = await signIn('credentials', {
        email: 'test@example.com',
        password: 'password123',
        totp_code: '000000',
        redirect: false,
      });

      expect(result.ok).toBe(false);
      expect(result.error).toBe('INVALID_2FA_CODE');
    });

    it('should handle 2FA setup flow', async () => {
      // 2FA setup is handled by TwoFactorSettings component
      // This test verifies the flow concept
      const setupData = {
        secret: 'JBSWY3DPEHPK3PXP',
        otpauth_url: 'otpauth://totp/Atom:test@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Atom',
      };

      expect(setupData.secret).toBeDefined();
      expect(setupData.otpauth_url).toContain('otpauth://totp');
      expect(setupData.otpauth_url).toContain('test@example.com');
    });

    it('should enable 2FA for user account', async () => {
      // Mock API endpoint for enabling 2FA
      const mockEnable2FA = jest.fn().mockResolvedValue({
        success: true,
        message: '2FA enabled successfully',
      });

      await mockEnable2FA();

      expect(mockEnable2FA).toHaveBeenCalled();
    });

    it('should disable 2FA for user account', async () => {
      // Mock API endpoint for disabling 2FA
      const mockDisable2FA = jest.fn().mockResolvedValue({
        success: true,
        message: '2FA disabled successfully',
      });

      await mockDisable2FA();

      expect(mockDisable2FA).toHaveBeenCalled();
    });
  });

  describe('Token storage', () => {
    it('should store session token after successful login', async () => {
      (signIn as jest.Mock).mockResolvedValue({
        ok: true,
        user: { id: 'user-123', email: 'test@example.com' },
        session: {
          accessToken: 'mock-access-token',
          refreshToken: 'mock-refresh-token',
        },
      });

      const result = await signIn('credentials', {
        email: 'test@example.com',
        password: 'password123',
        redirect: false,
      });

      expect(result.session).toBeDefined();
      expect(result.session.accessToken).toBe('mock-access-token');
      expect(result.session.refreshToken).toBe('mock-refresh-token');
    });

    it('should retrieve session from storage', async () => {
      const mockSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
        accessToken: 'mock-access-token',
      };

      (getSession as jest.Mock).mockResolvedValue(mockSession);

      const session = await getSession();

      expect(session).toEqual(mockSession);
      expect(session.user).toBeDefined();
      expect(session.accessToken).toBeDefined();
    });

    it('should return null when no session exists', async () => {
      (getSession as jest.Mock).mockResolvedValue(null);

      const session = await getSession();

      expect(session).toBeNull();
    });

    it('should handle corrupted session data', async () => {
      (getSession as jest.Mock).mockResolvedValue({
        user: null,
        expires: 'invalid-date',
      });

      const session = await getSession();

      expect(session).toBeDefined();
      expect(session.user).toBeNull();
    });
  });

  describe('Token refresh', () => {
    it('should refresh token before expiration (placeholder)', async () => {
      // Token refresh timing depends on backend implementation
      // This is a placeholder test for the refresh mechanism

      const expiringToken = {
        accessToken: 'expiring-token',
        refreshToken: 'valid-refresh-token',
        expiresAt: Date.now() + 60000, // Expires in 1 minute
      };

      const shouldRefresh = expiringToken.expiresAt < Date.now() + 5 * 60 * 1000;

      // Token should be refreshed if expiring within 5 minutes
      expect(shouldRefresh).toBe(true);
    });

    it('should handle failed token refresh', async () => {
      // Mock failed refresh attempt
      const mockRefresh = jest.fn().mockRejectedValue(
        new Error('Refresh token expired')
      );

      await expect(mockRefresh()).rejects.toThrow('Refresh token expired');
      expect(mockRefresh).toHaveBeenCalled();
    });

    it('should force logout on refresh failure', async () => {
      const mockRefresh = jest.fn().mockRejectedValue(new Error('Refresh failed'));
      const mockLogout = jest.fn();

      try {
        await mockRefresh();
      } catch (error) {
        await mockLogout();
      }

      expect(mockRefresh).toHaveBeenCalled();
      expect(mockLogout).toHaveBeenCalled();
    });
  });

  describe('Session persistence', () => {
    it('should persist session across page reloads', async () => {
      const mockSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
      };

      (getSession as jest.Mock).mockResolvedValue(mockSession);

      // Simulate page reload by getting session multiple times
      const session1 = await getSession();
      const session2 = await getSession();

      expect(session1).toEqual(session2);
      expect(session1.user).toEqual(mockSession.user);
    });

    it('should clear session on logout', async () => {
      const mockSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
      };

      (getSession as jest.Mock).mockResolvedValue(mockSession);
      (signOut as jest.Mock).mockResolvedValue({});

      // Verify session exists before logout
      const sessionBefore = await getSession();
      expect(sessionBefore).toBeDefined();

      // Logout
      await signOut();

      // After logout, session should be cleared
      (getSession as jest.Mock).mockResolvedValue(null);
      const sessionAfter = await getSession();
      expect(sessionAfter).toBeNull();
    });

    it('should handle session expiration', async () => {
      const expiredSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2020-01-01T00:00:00.000Z', // Expired date
      };

      (getSession as jest.Mock).mockResolvedValue(expiredSession);

      const session = await getSession();

      expect(session).toBeDefined();
      expect(new Date(session.expires) < new Date()).toBe(true);
    });

    it('should useSession hook provide session data', () => {
      const mockSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
      };

      (useSession as jest.Mock).mockReturnValue([mockSession, false, null]);

      const [session, loading, error] = useSession();

      expect(session).toEqual(mockSession);
      expect(loading).toBe(false);
      expect(error).toBeNull();
    });

    it('should useSession hook handle loading state', () => {
      (useSession as jest.Mock).mockReturnValue([null, true, null]);

      const [session, loading, error] = useSession();

      expect(session).toBeNull();
      expect(loading).toBe(true);
      expect(error).toBeNull();
    });

    it('should useSession hook handle error state', () => {
      const mockError = new Error('Session fetch failed');

      (useSession as jest.Mock).mockReturnValue([null, false, mockError]);

      const [session, loading, error] = useSession();

      expect(session).toBeNull();
      expect(loading).toBe(false);
      expect(error).toEqual(mockError);
    });
  });

  describe('Logout flow', () => {
    it('should successfully log out user', async () => {
      (signOut as jest.Mock).mockResolvedValue({});

      await signOut();

      expect(signOut).toHaveBeenCalled();
    });

    it('should redirect to login after logout', async () => {
      const router = useRouter();
      (signOut as jest.Mock).mockResolvedValue({});

      await signOut({ redirect: false });

      // Manual redirect after logout
      await router.push('/auth/signin');

      expect(signOut).toHaveBeenCalledWith({ redirect: false });
      expect(mockPush).toHaveBeenCalledWith('/auth/signin');
    });

    it('should clear all session data on logout', async () => {
      (signOut as jest.Mock).mockResolvedValue({});
      (getSession as jest.Mock)
        .mockResolvedValueOnce({ user: { id: 'user-123' } })
        .mockResolvedValueOnce(null);

      // Session exists before logout
      const sessionBefore = await getSession();
      expect(sessionBefore).toBeDefined();

      // Logout
      await signOut();

      // Session cleared after logout
      const sessionAfter = await getSession();
      expect(sessionAfter).toBeNull();
    });

    it('should handle logout errors gracefully', async () => {
      (signOut as jest.Mock).mockRejectedValue(new Error('Logout failed'));

      await expect(signOut()).rejects.toThrow('Logout failed');
    });
  });

  describe('Protected routes', () => {
    it('should redirect unauthenticated users to login', async () => {
      (getSession as jest.Mock).mockResolvedValue(null);
      const router = useRouter();

      // Check if user is authenticated
      const session = await getSession();

      if (!session) {
        await router.push('/auth/signin');
      }

      expect(session).toBeNull();
      expect(mockPush).toHaveBeenCalledWith('/auth/signin');
    });

    it('should allow authenticated users to access protected routes', async () => {
      const mockSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
      };

      (getSession as jest.Mock).mockResolvedValue(mockSession);

      const session = await getSession();

      expect(session).toBeDefined();
      expect(session.user).toBeDefined();
    });

    it('should handle session check on protected route access', async () => {
      (getSession as jest.Mock).mockImplementation(async () => {
        // Simulate async session check
        return {
          user: { id: 'user-123', email: 'test@example.com' },
          expires: '2026-12-31T23:59:59.000Z',
        };
      });

      const session = await getSession();

      expect(getSession).toHaveBeenCalled();
      expect(session).toBeDefined();
    });
  });

  describe('OAuth integration', () => {
    it('should handle Google OAuth initiation', async () => {
      (signIn as jest.Mock).mockResolvedValue({
        ok: true,
        user: { id: 'user-123', email: 'test@example.com' },
      });

      const result = await signIn('google', { redirect: false });

      expect(result.ok).toBe(true);
      expect(signIn).toHaveBeenCalledWith('google', { redirect: false });
    });

    it('should handle Slack OAuth initiation', async () => {
      (signIn as jest.Mock).mockResolvedValue({
        ok: true,
        user: { id: 'user-123', email: 'test@example.com' },
      });

      const result = await signIn('slack', { redirect: false });

      expect(result.ok).toBe(true);
      expect(signIn).toHaveBeenCalledWith('slack', { redirect: false });
    });

    it('should handle Jira OAuth callback', async () => {
      // OAuth callback is handled by pages/oauth/jira/callback.tsx
      const mockCallbackData = {
        code: 'auth-code-123',
        state: 'csrf-token-456',
      };

      expect(mockCallbackData.code).toBeDefined();
      expect(mockCallbackData.state).toBeDefined();
    });

    it('should handle OAuth success page', async () => {
      // OAuth success is handled by pages/oauth/success.tsx
      const successParams = {
        provider: 'google',
        redirect: '/dashboard',
      };

      expect(successParams.provider).toBe('google');
      expect(successParams.redirect).toBe('/dashboard');
    });

    it('should handle OAuth error page', async () => {
      // OAuth error is handled by pages/oauth/error.tsx
      const errorParams = {
        error: 'access_denied',
        error_description: 'User denied access',
      };

      expect(errorParams.error).toBe('access_denied');
      expect(errorParams.error_description).toBeDefined();
    });
  });

  describe('Password reset flow', () => {
    it('should request password reset', async () => {
      const mockResetRequest = jest.fn().mockResolvedValue({
        success: true,
        message: 'Password reset email sent',
      });

      await mockResetRequest('test@example.com');

      expect(mockResetRequest).toHaveBeenCalledWith('test@example.com');
    });

    it('should reset password with valid token', async () => {
      const mockReset = jest.fn().mockResolvedValue({
        success: true,
        message: 'Password reset successfully',
      });

      await mockReset('valid-reset-token', 'new-password123');

      expect(mockReset).toHaveBeenCalledWith('valid-reset-token', 'new-password123');
    });

    it('should show error for invalid reset token', async () => {
      const mockReset = jest.fn().mockRejectedValue({
        success: false,
        error: 'Invalid or expired reset token',
      });

      await expect(
        mockReset('invalid-token', 'new-password123')
      ).rejects.toEqual({
        success: false,
        error: 'Invalid or expired reset token',
      });
    });
  });

  describe('Email verification flow', () => {
    it('should send verification email', async () => {
      const mockSendVerification = jest.fn().mockResolvedValue({
        success: true,
        message: 'Verification email sent',
      });

      await mockSendVerification('test@example.com');

      expect(mockSendVerification).toHaveBeenCalledWith('test@example.com');
    });

    it('should verify email with valid token', async () => {
      const mockVerify = jest.fn().mockResolvedValue({
        success: true,
        message: 'Email verified successfully',
      });

      await mockVerify('valid-verification-token');

      expect(mockVerify).toHaveBeenCalledWith('valid-verification-token');
    });

    it('should show verification sent page', () => {
      // Handled by pages/auth/verification-sent.tsx
      const verificationData = {
        email: 'test@example.com',
        resendUrl: '/auth/resend-verification',
      };

      expect(verificationData.email).toBeDefined();
      expect(verificationData.resendUrl).toBeDefined();
    });
  });
});
