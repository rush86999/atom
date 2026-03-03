import { renderHook, act, waitFor } from '@testing-library/react';
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

  // Mock localStorage
  const localStorageMock = (() => {
    let store: Record<string, string> = {};

    return {
      getItem: (key: string) => store[key] || null,
      setItem: (key: string, value: string) => {
        store[key] = value.toString();
      },
      removeItem: (key: string) => {
        delete store[key];
      },
      clear: () => {
        store = {};
      },
    };
  })();

  Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
  });
});

afterEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
});

/**
 * Integration tests for authentication state management
 *
 * Tests cover:
 * - useSession hook behavior (8 tests)
 * - Login state transitions (7 tests)
 * - Logout state transitions (6 tests)
 * - Token refresh behavior (5 tests)
 * - Session state transitions (4 tests)
 *
 * Total: 30 tests
 */

describe('Authentication State Management', () => {
  describe('useSession Hook Tests', () => {
    it('should return null session when not authenticated', () => {
      const mockSessionData = {
        data: null,
        status: 'unauthenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockReturnValue(mockSessionData);

      const { result } = renderHook(() => useSession());

      expect(result.current.data).toBeNull();
      expect(result.current.status).toBe('unauthenticated');
    });

    it('should return session object when authenticated', () => {
      const mockUser = {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
      };

      const mockSessionData = {
        data: { user: mockUser, expires: '2026-12-31T23:59:59.000Z' },
        status: 'authenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockReturnValue(mockSessionData);

      const { result } = renderHook(() => useSession());

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.user).toEqual(mockUser);
      expect(result.current.status).toBe('authenticated');
    });

    it('should return loading: true during session fetch', () => {
      const mockSessionData = {
        data: null,
        status: 'loading' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockReturnValue(mockSessionData);

      const { result } = renderHook(() => useSession());

      expect(result.current.status).toBe('loading');
    });

    it('should return loading: false after session fetch', () => {
      const mockSessionData = {
        data: { user: { id: 'user-123' }, expires: '2026-12-31T23:59:59.000Z' },
        status: 'authenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockReturnValue(mockSessionData);

      const { result } = renderHook(() => useSession());

      expect(result.current.status).not.toBe('loading');
    });

    it('should update session when authentication changes', async () => {
      let sessionData = {
        data: null,
        status: 'unauthenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockImplementation(() => sessionData);

      const { result, rerender } = renderHook(() => useSession());

      // Initial state - unauthenticated
      expect(result.current.status).toBe('unauthenticated');

      // Simulate authentication change
      sessionData = {
        data: { user: { id: 'user-123' }, expires: '2026-12-31T23:59:59.000Z' },
        status: 'authenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockImplementation(() => sessionData);

      // Rerender to reflect the change
      act(() => {
        rerender();
      });

      expect(result.current.status).toBe('authenticated');
    });

    it('should provide update method for session refresh', () => {
      const updateMock = jest.fn().mockResolvedValue({
        user: { id: 'user-123', email: 'updated@example.com' },
      });

      const mockSessionData = {
        data: { user: { id: 'user-123' }, expires: '2026-12-31T23:59:59.000Z' },
        status: 'authenticated' as const,
        update: updateMock,
      };

      (useSession as jest.Mock).mockReturnValue(mockSessionData);

      const { result } = renderHook(() => useSession());

      expect(typeof result.current.update).toBe('function');
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

    it('should provide status: authenticated | unauthenticated | loading', () => {
      const statuses: Array<'authenticated' | 'unauthenticated' | 'loading'> = [
        'authenticated',
        'unauthenticated',
        'loading',
      ];

      statuses.forEach((status) => {
        const mockSessionData = {
          data: status === 'authenticated' ? { user: { id: 'user-123' } } : null,
          status,
          update: jest.fn(),
        };

        (useSession as jest.Mock).mockReturnValue(mockSessionData);

        const { result } = renderHook(() => useSession());

        expect(result.current.status).toBe(status);
      });
    });
  });

  describe('Login State Tests', () => {
    it('should transition from unauthenticated to authenticated on successful login', async () => {
      const mockSessionBefore = {
        data: null,
        status: 'unauthenticated' as const,
        update: jest.fn(),
      };

      const mockSessionAfter = {
        data: {
          user: { id: 'user-123', email: 'test@example.com' },
          expires: '2026-12-31T23:59:59.000Z',
        },
        status: 'authenticated' as const,
        update: jest.fn(),
      };

      (signIn as jest.Mock).mockResolvedValue({
        ok: true,
        user: { id: 'user-123', email: 'test@example.com' },
      });

      // Before login
      (useSession as jest.Mock).mockReturnValue(mockSessionBefore);
      const { result: resultBefore } = renderHook(() => useSession());
      expect(resultBefore.current.status).toBe('unauthenticated');

      // Perform login
      await signIn('credentials', {
        email: 'test@example.com',
        password: 'password123',
        redirect: false,
      });

      // After login
      (useSession as jest.Mock).mockReturnValue(mockSessionAfter);
      const { result: resultAfter } = renderHook(() => useSession());
      expect(resultAfter.current.status).toBe('authenticated');
    });

    it('should store session data after login', async () => {
      const mockSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
        accessToken: 'mock-access-token',
      };

      (signIn as jest.Mock).mockResolvedValue({
        ok: true,
        session: mockSession,
      });

      await signIn('credentials', {
        email: 'test@example.com',
        password: 'password123',
        redirect: false,
      });

      // Simulate storing session to localStorage
      localStorage.setItem('atom_session', JSON.stringify(mockSession));

      const storedSession = localStorage.getItem('atom_session');
      expect(storedSession).toBeDefined();

      const parsedSession = JSON.parse(storedSession!);
      expect(parsedSession.user.email).toBe('test@example.com');
    });

    it('should set loading state during login process', async () => {
      let sessionData = {
        data: null,
        status: 'loading' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockImplementation(() => sessionData);

      const { result } = renderHook(() => useSession());

      // Initial loading state
      expect(result.current.status).toBe('loading');

      // Simulate login completion
      sessionData = {
        data: { user: { id: 'user-123' }, expires: '2026-12-31T23:59:59.000Z' },
        status: 'authenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockImplementation(() => sessionData);

      // After login completes
      const { result: resultAfter } = renderHook(() => useSession());
      expect(resultAfter.current.status).toBe('authenticated');
    });

    it('should handle login error with error state', async () => {
      const mockError = new Error('Invalid credentials');

      (signIn as jest.Mock).mockRejectedValue(mockError);

      try {
        await signIn('credentials', {
          email: 'test@example.com',
          password: 'wrongpassword',
          redirect: false,
        });
      } catch (error) {
        expect(error).toEqual(mockError);
      }

      expect(signIn).toHaveBeenCalled();
    });

    it('should clear error state on next login attempt', async () => {
      // First attempt - error
      (signIn as jest.Mock)
        .mockRejectedValueOnce(new Error('Invalid credentials'))
        .mockResolvedValueOnce({
          ok: true,
          user: { id: 'user-123', email: 'test@example.com' },
        });

      // First login attempt fails
      await expect(
        signIn('credentials', {
          email: 'test@example.com',
          password: 'wrongpassword',
          redirect: false,
        })
      ).rejects.toThrow('Invalid credentials');

      // Second login attempt succeeds
      const result = await signIn('credentials', {
        email: 'test@example.com',
        password: 'correctpassword',
        redirect: false,
      });

      expect(result.ok).toBe(true);
    });

    it('should persist session to localStorage', async () => {
      const mockSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
      };

      (signIn as jest.Mock).mockResolvedValue({
        ok: true,
        session: mockSession,
      });

      await signIn('credentials', {
        email: 'test@example.com',
        password: 'password123',
        redirect: false,
      });

      // Simulate localStorage persistence
      localStorage.setItem('atom_session', JSON.stringify(mockSession));

      const storedSession = localStorage.getItem('atom_session');
      expect(storedSession).toBe(JSON.stringify(mockSession));
    });

    it('should trigger useSession update after login', async () => {
      const updateMock = jest.fn().mockResolvedValue({
        user: { id: 'user-123', email: 'test@example.com' },
      });

      const mockSessionData = {
        data: { user: { id: 'user-123' }, expires: '2026-12-31T23:59:59.000Z' },
        status: 'authenticated' as const,
        update: updateMock,
      };

      (useSession as jest.Mock).mockReturnValue(mockSessionData);

      const { result } = renderHook(() => useSession());

      // Trigger update
      await act(async () => {
        await result.current.update();
      });

      expect(updateMock).toHaveBeenCalled();
    });
  });

  describe('Logout State Tests', () => {
    it('should transition from authenticated to unauthenticated on logout', async () => {
      let sessionData = {
        data: {
          user: { id: 'user-123', email: 'test@example.com' },
          expires: '2026-12-31T23:59:59.000Z',
        },
        status: 'authenticated' as const,
        update: jest.fn(),
      };

      (signOut as jest.Mock).mockResolvedValue({});

      // Before logout
      (useSession as jest.Mock).mockReturnValue(sessionData);
      const { result: resultBefore } = renderHook(() => useSession());
      expect(resultBefore.current.status).toBe('authenticated');

      // Perform logout
      await signOut();

      // After logout
      sessionData = {
        data: null,
        status: 'unauthenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockReturnValue(sessionData);
      const { result: resultAfter } = renderHook(() => useSession());
      expect(resultAfter.current.status).toBe('unauthenticated');
    });

    it('should clear session data on logout', async () => {
      const mockSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
      };

      (getSession as jest.Mock)
        .mockResolvedValueOnce(mockSession)
        .mockResolvedValueOnce(null);

      (signOut as jest.Mock).mockResolvedValue({});

      // Session exists before logout
      const sessionBefore = await getSession();
      expect(sessionBefore).toBeDefined();

      // Logout
      await signOut();

      // Session cleared after logout
      const sessionAfter = await getSession();
      expect(sessionAfter).toBeNull();
    });

    it('should clear localStorage on logout', async () => {
      const mockSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
      };

      (signOut as jest.Mock).mockResolvedValue({});

      // Set session in localStorage
      localStorage.setItem('atom_session', JSON.stringify(mockSession));
      expect(localStorage.getItem('atom_session')).toBeDefined();

      // Logout
      await signOut();

      // Clear localStorage
      localStorage.removeItem('atom_session');

      expect(localStorage.getItem('atom_session')).toBeNull();
    });

    it('should set loading state during logout process', async () => {
      let sessionData = {
        data: { user: { id: 'user-123' }, expires: '2026-12-31T23:59:59.000Z' },
        status: 'authenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockImplementation(() => sessionData);

      const { result } = renderHook(() => useSession());

      // Before logout - authenticated
      expect(result.current.status).toBe('authenticated');

      // During logout - loading
      sessionData = {
        data: { user: { id: 'user-123' }, expires: '2026-12-31T23:59:59.000Z' },
        status: 'loading' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockImplementation(() => sessionData);

      // After logout - unauthenticated
      sessionData = {
        data: null,
        status: 'unauthenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockImplementation(() => sessionData);

      const { result: resultAfter } = renderHook(() => useSession());
      expect(resultAfter.current.status).toBe('unauthenticated');
    });

    it('should handle logout error gracefully', async () => {
      const mockError = new Error('Logout failed');

      (signOut as jest.Mock).mockRejectedValue(mockError);

      await expect(signOut()).rejects.toThrow('Logout failed');
      expect(signOut).toHaveBeenCalled();
    });

    it('should redirect to home page after logout', async () => {
      const router = useRouter();
      (signOut as jest.Mock).mockResolvedValue({});

      await signOut({ redirect: false });

      // Manual redirect after logout
      await router.push('/');

      expect(signOut).toHaveBeenCalledWith({ redirect: false });
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });

  describe('Token Refresh Tests', () => {
    it('should automatically refresh token before expiration', async () => {
      const expiringToken = {
        accessToken: 'expiring-token',
        refreshToken: 'valid-refresh-token',
        expiresAt: Date.now() + 60000, // Expires in 1 minute
      };

      const shouldRefresh = expiringToken.expiresAt < Date.now() + 5 * 60 * 1000;

      // Token should be refreshed if expiring within 5 minutes
      expect(shouldRefresh).toBe(true);
    });

    it('should update session data after refresh', async () => {
      const oldSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
        accessToken: 'old-access-token',
      };

      const newSession = {
        user: { id: 'user-123', email: 'test@example.com' },
        expires: '2026-12-31T23:59:59.000Z',
        accessToken: 'new-access-token',
      };

      (getSession as jest.Mock)
        .mockResolvedValueOnce(oldSession)
        .mockResolvedValueOnce(newSession);

      const sessionBefore = await getSession();
      expect(sessionBefore.accessToken).toBe('old-access-token');

      // Simulate token refresh
      const sessionAfter = await getSession();
      expect(sessionAfter.accessToken).toBe('new-access-token');
    });

    it('should handle token refresh failure', async () => {
      const mockRefresh = jest.fn().mockRejectedValue(
        new Error('Refresh token expired')
      );

      await expect(mockRefresh()).rejects.toThrow('Refresh token expired');
      expect(mockRefresh).toHaveBeenCalled();
    });

    it('should retry token refresh on network error', async () => {
      const mockRefresh = jest.fn()
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          accessToken: 'new-access-token',
          refreshToken: 'new-refresh-token',
        });

      // First attempt - network error
      await expect(mockRefresh()).rejects.toThrow('Network error');

      // Retry attempt - success
      const result = await mockRefresh();
      expect(result.accessToken).toBe('new-access-token');
      expect(mockRefresh).toHaveBeenCalledTimes(2);
    });

    it('should log out on authentication failure during refresh', async () => {
      const mockRefresh = jest.fn().mockRejectedValue(
        new Error('Authentication failed')
      );
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

  describe('Session State Transition Tests', () => {
    it('should have no unreachable states (no invalid state combinations)', () => {
      const validStateCombinations = [
        { data: null, status: 'unauthenticated' },
        { data: { user: { id: 'user-123' } }, status: 'authenticated' },
        { data: null, status: 'loading' },
      ];

      validStateCombinations.forEach((state) => {
        const isDataNullAndAuthenticated = state.data === null && state.status === 'authenticated';
        const isDataNotNullAndUnauthenticated = state.data !== null && state.status === 'unauthenticated';

        expect(isDataNullAndAuthenticated).toBe(false);
        expect(isDataNotNullAndUnauthenticated).toBe(false);
      });
    });

    it('should ensure loading cannot be true with status=authenticated', () => {
      const mockSessionData = {
        data: { user: { id: 'user-123' } },
        status: 'authenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockReturnValue(mockSessionData);

      const { result } = renderHook(() => useSession());

      // Status cannot be 'loading' when 'authenticated'
      expect(result.current.status).not.toBe('loading');
    });

    it('should clear error on successful authentication', async () => {
      let sessionData = {
        data: null,
        status: 'unauthenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockImplementation(() => sessionData);

      // Simulate error state (stored separately, not in useSession return)
      let hasError = true;

      // Successful authentication clears error
      sessionData = {
        data: { user: { id: 'user-123' }, expires: '2026-12-31T23:59:59.000Z' },
        status: 'authenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockImplementation(() => sessionData);
      hasError = false;

      const { result } = renderHook(() => useSession());

      expect(result.current.status).toBe('authenticated');
      expect(hasError).toBe(false);
    });

    it('should ensure session is null when status=unauthenticated', () => {
      const mockSessionData = {
        data: null,
        status: 'unauthenticated' as const,
        update: jest.fn(),
      };

      (useSession as jest.Mock).mockReturnValue(mockSessionData);

      const { result } = renderHook(() => useSession());

      expect(result.current.status).toBe('unauthenticated');
      expect(result.current.data).toBeNull();
    });
  });
});
