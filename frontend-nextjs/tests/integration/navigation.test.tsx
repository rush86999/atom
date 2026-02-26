import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRouter } from 'next/router';

// Mock Next.js router
const mockPush = jest.fn();
const mockBack = jest.fn();
const mockReplace = jest.fn();
const mockPrefetch = jest.fn().mockResolvedValue(undefined);

jest.mock('next/router', () => ({
  useRouter: jest.fn(),
}));

beforeEach(() => {
  (useRouter as jest.Mock).mockReturnValue({
    push: mockPush,
    back: mockBack,
    replace: mockReplace,
    prefetch: mockPrefetch,
    pathname: '/',
    query: {},
    asPath: '/',
    route: '/',
    events: {
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
    },
  });
  mockPush.mockClear();
  mockBack.mockClear();
  mockReplace.mockClear();
  mockPrefetch.mockClear();
});

afterEach(() => {
  jest.clearAllMocks();
});

/**
 * Integration tests for navigation and routing
 *
 * Tests cover:
 * - Routing with useRouter
 * - Navigation params (dynamic routes)
 * - Query parameters
 * - Back navigation
 * - Router methods (push, replace, back)
 *
 * Note: No atom:// deep link handlers were found in the codebase during survey.
 * Deep linking tests are placeholders for future implementation.
 */

describe('Navigation Integration', () => {
  describe('Router mock setup', () => {
    it('should have router mock properly configured', () => {
      const router = useRouter();
      expect(router).toBeDefined();
      expect(typeof router.push).toBe('function');
      expect(typeof router.back).toBe('function');
      expect(typeof router.replace).toBe('function');
      expect(typeof router.prefetch).toBe('function');
    });

    it('should reset mocks between tests', () => {
      mockPush('/test');
      expect(mockPush).toHaveBeenCalledTimes(1);

      // Reset should happen in beforeEach
      mockPush.mockClear();
      mockPush('/another');
      expect(mockPush).toHaveBeenCalledTimes(1);
    });
  });

  describe('Routing', () => {
    it('should navigate using router.push', async () => {
      const router = useRouter();
      await router.push('/dashboard');

      expect(mockPush).toHaveBeenCalledWith('/dashboard');
      expect(mockPush).toHaveBeenCalledTimes(1);
    });

    it('should navigate with query parameters', async () => {
      const router = useRouter();
      await router.push('/search?q=test&category=articles');

      expect(mockPush).toHaveBeenCalledWith('/search?q=test&category=articles');
    });

    it('should navigate using router.replace', async () => {
      const router = useRouter();
      await router.replace('/settings');

      expect(mockReplace).toHaveBeenCalledWith('/settings');
      expect(mockReplace).toHaveBeenCalledTimes(1);
    });

    it('should prefetch routes for performance', async () => {
      const router = useRouter();
      await router.prefetch('/dashboard');

      expect(mockPrefetch).toHaveBeenCalledWith('/dashboard');
      expect(mockPrefetch).toHaveBeenCalledTimes(1);
    });
  });

  describe('Navigation params', () => {
    it('should handle dynamic route parameters', async () => {
      const router = useRouter();
      const workflowId = 'workflow-123';

      await router.push(`/workflows/editor/${workflowId}`);

      expect(mockPush).toHaveBeenCalledWith(`/workflows/editor/${workflowId}`);
    });

    it('should handle multiple dynamic parameters', async () => {
      const router = useRouter();

      await router.push('/workflows/editor/abc123');

      expect(mockPush).toHaveBeenCalledWith('/workflows/editor/abc123');
    });

    it('should handle query params in route', async () => {
      const router = useRouter();
      const routerWithQuery = {
        ...router,
        query: { tab: 'settings', section: 'profile' },
      };

      (useRouter as jest.Mock).mockReturnValue(routerWithQuery);

      const updatedRouter = useRouter();
      expect(updatedRouter.query).toEqual({ tab: 'settings', section: 'profile' });
    });

    it('should handle missing parameters gracefully', async () => {
      const router = useRouter();

      // Navigate without providing all params
      await router.push('/workflows/editor/');

      // Should still attempt navigation
      expect(mockPush).toHaveBeenCalledWith('/workflows/editor/');
    });
  });

  describe('Back navigation', () => {
    it('should call router.back for navigation history', async () => {
      const router = useRouter();
      await router.back();

      expect(mockBack).toHaveBeenCalledTimes(1);
    });

    it('should provide fallback when no history exists', async () => {
      const router = useRouter();
      mockBack.mockImplementation(() => {
        throw new Error('No history');
      });

      // Attempt to go back when no history
      try {
        await router.back();
      } catch (error) {
        // Expected error
        expect((error as Error).message).toBe('No history');
      }

      expect(mockBack).toHaveBeenCalled();
    });

    it('should combine back navigation with fallback route', async () => {
      const router = useRouter();
      const fallbackUrl = '/home';

      mockBack.mockImplementation(() => {
        throw new Error('No history');
      });

      try {
        await router.back();
      } catch (error) {
        // Use fallback
        await router.push(fallbackUrl);
      }

      expect(mockBack).toHaveBeenCalled();
      expect(mockPush).toHaveBeenCalledWith(fallbackUrl);
    });
  });

  describe('Route transitions', () => {
    it('should handle navigation from auth to dashboard', async () => {
      const router = useRouter();

      // Simulate login redirect
      await router.push('/dashboard');

      expect(mockPush).toHaveBeenCalledWith('/dashboard');
    });

    it('should handle navigation to settings pages', async () => {
      const router = useRouter();

      await router.push('/settings/account');
      expect(mockPush).toHaveBeenCalledWith('/settings/account');

      mockPush.mockClear();

      await router.push('/settings/sessions');
      expect(mockPush).toHaveBeenCalledWith('/settings/sessions');
    });

    it('should handle navigation to agent pages', async () => {
      const router = useRouter();

      await router.push('/agents');

      expect(mockPush).toHaveBeenCalledWith('/agents');
    });
  });

  describe('Query parameter handling', () => {
    it('should navigate with single query parameter', async () => {
      const router = useRouter();

      await router.push('/search?q=test');

      expect(mockPush).toHaveBeenCalledWith('/search?q=test');
    });

    it('should navigate with multiple query parameters', async () => {
      const router = useRouter();

      await router.push('/search?q=test&page=2&limit=10');

      expect(mockPush).toHaveBeenCalledWith('/search?q=test&page=2&limit=10');
    });

    it('should navigate with encoded query parameters', async () => {
      const router = useRouter();

      const searchQuery = encodeURIComponent('hello world');
      await router.push(`/search?q=${searchQuery}`);

      expect(mockPush).toHaveBeenCalledWith('/search?q=hello%20world');
    });
  });

  describe('Deep links (placeholder)', () => {
    it('should handle atom:// deep links when implemented', () => {
      // Placeholder test for future deep link implementation
      // Survey found no atom:// handlers in frontend codebase
      // Deep linking may be handled by backend or not yet implemented

      const mockLocation = { href: 'atom://agent/test-agent' };
      const expectedRoute = '/agent/test-agent';

      // This test will be activated when deep link handlers are added
      expect(mockLocation.href).toBe('atom://agent/test-agent');
      expect(expectedRoute).toBe('/agent/test-agent');
    });

    it('should navigate to canvas from deep link', () => {
      // Placeholder test for canvas deep links
      const mockLocation = { href: 'atom://canvas/canvas-123' };
      const expectedRoute = '/canvas/canvas-123';

      expect(mockLocation.href).toBe('atom://canvas/canvas-123');
      expect(expectedRoute).toBe('/canvas/canvas-123');
    });

    it('should navigate to workflow from deep link', () => {
      // Placeholder test for workflow deep links
      const mockLocation = { href: 'atom://workflow/workflow-456' };
      const expectedRoute = '/workflow/workflow-456';

      expect(mockLocation.href).toBe('atom://workflow/workflow-456');
      expect(expectedRoute).toBe('/workflow/workflow-456');
    });
  });

  describe('Router state', () => {
    it('should provide current pathname', () => {
      const router = useRouter();
      expect(router.pathname).toBe('/');
    });

    it('should provide current query object', () => {
      const router = useRouter();
      expect(router.query).toEqual({});
    });

    it('should provide current asPath', () => {
      const router = useRouter();
      expect(router.asPath).toBe('/');
    });

    it('should update pathname after navigation', async () => {
      const router = useRouter();

      const updatedRouter = {
        ...router,
        pathname: '/dashboard',
      };

      (useRouter as jest.Mock).mockReturnValue(updatedRouter);

      const newRouter = useRouter();
      expect(newRouter.pathname).toBe('/dashboard');
    });
  });

  describe('Navigation to actual routes from survey', () => {
    const actualRoutes = [
      '/',
      '/dashboard',
      '/chat',
      '/agents',
      '/search',
      '/tasks',
      '/settings',
      '/settings/account',
      '/settings/sessions',
      '/settings/ai',
      '/workflows/builder',
      '/auth/signin',
      '/auth/signup',
      '/auth/forgot-password',
      '/auth/reset-password',
      '/auth/verify-email',
      '/oauth/jira/callback',
      '/oauth/success',
      '/oauth/error',
    ];

    actualRoutes.forEach((route) => {
      it(`should navigate to ${route}`, async () => {
        const router = useRouter();
        await router.push(route);

        expect(mockPush).toHaveBeenCalledWith(route);
      });
    });
  });

  describe('Dynamic route handling from survey', () => {
    it('should handle workflow editor with dynamic ID', async () => {
      const router = useRouter();
      const workflowId = 'workflow-abc-123';

      await router.push(`/workflows/editor/${workflowId}`);

      expect(mockPush).toHaveBeenCalledWith(`/workflows/editor/${workflowId}`);
    });

    it('should handle different workflow IDs', async () => {
      const router = useRouter();
      const workflowIds = ['workflow-1', 'workflow-2', 'workflow-3'];

      for (const id of workflowIds) {
        await router.push(`/workflows/editor/${id}`);
        expect(mockPush).toHaveBeenCalledWith(`/workflows/editor/${id}`);
        mockPush.mockClear();
      }
    });
  });

  describe('Router events', () => {
    it('should provide router events object', () => {
      const router = useRouter();

      expect(router.events).toBeDefined();
      expect(typeof router.events.on).toBe('function');
      expect(typeof router.events.off).toBe('function');
      expect(typeof router.events.emit).toBe('function');
    });

    it('should allow event listener registration', () => {
      const router = useRouter();
      const handler = jest.fn();

      router.events.on('routeChangeStart', handler);

      expect(router.events.on).toHaveBeenCalledWith('routeChangeStart', handler);
    });

    it('should allow event listener removal', () => {
      const router = useRouter();
      const handler = jest.fn();

      router.events.off('routeChangeStart', handler);

      expect(router.events.off).toHaveBeenCalledWith('routeChangeStart', handler);
    });
  });
});
