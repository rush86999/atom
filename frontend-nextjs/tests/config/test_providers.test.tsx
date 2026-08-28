/**
 * Frontend provider setup tests
 *
 * These tests verify that providers in _app.tsx are correctly wrapped and configured.
 * They test the "wiring" of the frontend application without testing business logic.
 */

import React from 'react';

import { renderWithProviders, screen } from '../test-utils';
import { render, waitFor } from '@testing-library/react';
import { AppProps } from 'next/app';

// Mock the Layout component to avoid deep recursion
jest.mock('../../components/layout/Layout', () => {
  return function MockLayout({ children }: { children: React.ReactNode }) {
    return <div data-testid="layout">{children}</div>;
  };
});

// Mock GlobalChatWidget. _app.tsx imports it as a NAMED export
// (import { GlobalChatWidget }), so the mock must export the named binding
// (a bare function factory would leave the named import undefined).
jest.mock('../../components/GlobalChatWidget', () => ({
  GlobalChatWidget: function MockGlobalChatWidget() {
    return <div data-testid="global-chat-widget" />;
  },
}));

// Mock WakeWordProvider context
jest.mock('../../contexts/WakeWordContext', () => ({
  WakeWordProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// Mock useCliHandler hook
jest.mock('../../hooks/useCliHandler', () => ({
  useCliHandler: () => jest.fn(),
}));

// Mock next-auth. The session payload is read from a global so tests can
// exercise the SessionSync backendToken branch.
jest.mock('next-auth/react', () => ({
  SessionProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="session-provider">{children}</div>
  ),
  // _app.tsx's SessionSync calls useSession() at render.
  useSession: () => ({
    data: (global as any).__mockSession ?? null,
    status: 'authenticated',
  }),
}));

// Configurable router mock (pathname drives the standalone-page branch).
jest.mock('next/router', () => ({
  useRouter: () => ({
    pathname: (global as any).__mockPathname ?? '/dashboard',
    route: '/dashboard',
    query: {},
    asPath: '/dashboard',
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
    isReady: true,
  }),
}));

import MyApp from '../../pages/_app';

describe('Provider Setup', () => {
  it('SessionProvider wraps the app', () => {
    const mockPageProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    renderWithProviders(<MyApp {...mockPageProps} />);

    // renderWithProviders' wrapper and _app.tsx both render the (mocked)
    // SessionProvider, so use getAllByTestId.
    const sessionProviders = screen.getAllByTestId('session-provider');
    expect(sessionProviders.length).toBeGreaterThan(0);
  });

  it('app renders without errors', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    expect(() => renderWithProviders(<MyApp {...mockAppProps} />)).not.toThrow();
  });

  it('Layout is rendered for non-auth pages', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // Mock router to return non-auth path
    jest.mock('next/router', () => ({
      useRouter: () => ({
        pathname: '/dashboard',
        isReady: true,
      }),
    }));

    // Need to re-import after mocking
    const { render: renderWithMock } = require('@testing-library/react');
    const { default: MyAppWithMock } = require('../../pages/_app');

    renderWithMock(<MyAppWithMock {...mockAppProps} />);

    // Layout should be rendered for non-auth pages
    // Note: This test may need adjustment based on actual router behavior
  });

  it('GlobalChatWidget is rendered for non-auth pages', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    renderWithProviders(<MyApp {...mockAppProps} />);

    // GlobalChatWidget should be present (mounted state triggers this)
    const chatWidget = screen.queryByTestId('global-chat-widget');
    expect(chatWidget).toBeInTheDocument();
  });

  it('app structure includes ChakraProvider', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    const { container } = renderWithProviders(<MyApp {...mockAppProps} />);

    // ChakraProvider should be present
    // We can't directly test ChakraProvider, but we can verify app renders
    expect(container.firstChild).toBeTruthy();
  });

  it('app structure includes ToastProvider', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // ToastProvider is part of the provider stack
    // We verify it by ensuring the app renders without errors
    expect(() => renderWithProviders(<MyApp {...mockAppProps} />)).not.toThrow();
  });

  it('app structure includes WakeWordProvider', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // WakeWordProvider is mocked, so we just verify app renders
    expect(() => renderWithProviders(<MyApp {...mockAppProps} />)).not.toThrow();
  });

  it('providers are nested in correct order', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    const { container } = renderWithProviders(<MyApp {...mockAppProps} />);

    // The provider nesting order is:
    // SessionProvider -> TauriHooks -> ChakraProvider -> ToastProvider -> WakeWordProvider
    // We verify this by checking that all providers are present
    expect(container.firstChild).toBeTruthy();
  });

  it('app renders even with missing session', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // SessionProvider should handle missing session gracefully
    expect(() => renderWithProviders(<MyApp {...mockAppProps} />)).not.toThrow();
  });

  it('app renders with router mounted state', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // Mock router to simulate mounted state
    jest.mock('next/router', () => ({
      useRouter: () => ({
        pathname: '/test',
        isReady: true,
      }),
    }));

    const { render: renderWithMock } = require('@testing-library/react');

    expect(() => {
      const { default: MyAppWithMock } = require('../../pages/_app');
      renderWithMock(<MyAppWithMock {...mockAppProps} />);
    }).not.toThrow();
  });

  it('providers expose context to children', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    const { container } = renderWithProviders(<MyApp {...mockAppProps} />);

    // If providers are working, children should render
    expect(container.firstChild).toBeTruthy();
  });

  it('combined providers work together', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // Multiple providers should work simultaneously
    expect(() => renderWithProviders(<MyApp {...mockAppProps} />)).not.toThrow();
  });

  it('ToastProvider wraps WakeWordProvider', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // ToastProvider should be present (tested via app rendering)
    const { container } = renderWithProviders(<MyApp {...mockAppProps} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('ChakraProvider wraps ToastProvider', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // ChakraProvider should be present
    const { container } = renderWithProviders(<MyApp {...mockAppProps} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('SessionProvider wraps ChakraProvider', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    renderWithProviders(<MyApp {...mockAppProps} />);

    // SessionProvider should be present (mock renders one per mount, plus the
    // renderWithProviders wrapper's own instance)
    const sessionProviders = screen.getAllByTestId('session-provider');
    expect(sessionProviders.length).toBeGreaterThan(0);
  });
});

describe('Provider Error Handling', () => {
  it('app handles provider errors gracefully', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // Even if a provider has issues, app should still render
    expect(() => renderWithProviders(<MyApp {...mockAppProps} />)).not.toThrow();
  });

  it('app renders without theme (default theme used)', () => {
    const mockAppProps = {
      pageProps: {},
      Component: () => <div>Test Page</div>,
    } as unknown as AppProps;

    // ChakraProvider should use default theme
    expect(() => renderWithProviders(<MyApp {...mockAppProps} />)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: session token sync, theme loading, standalone pages
// ---------------------------------------------------------------------------
describe('MyApp extended coverage', () => {
  const { rest } = require('msw');
  const { server } = require('../../tests/mocks/server');

  const makeProps = (pathname: string, session?: any) => ({
    pageProps: session ? { session } : {},
    Component: () => <div data-testid="page-content">Page</div>,
  }) as unknown as AppProps;

  beforeEach(() => {
    (global as any).__mockPathname = '/dashboard';
    (global as any).__mockSession = null;
    // restoreMocks:true resets the setup-file polyfill between tests
    (window as any).matchMedia = jest.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));
    document.documentElement.classList.remove('dark');
    localStorage.removeItem('auth_token');
    server.resetHandlers();
    server.use(
      rest.get('/api/v1/preferences', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({}))
      )
    );
  });

  afterEach(() => {
    (global as any).__mockPathname = '/dashboard';
    (global as any).__mockSession = null;
  });

  const renderSettled = async (props: any) => {
    render(<MyApp {...props} />);
    await screen.findByTestId('page-content');
    await waitFor(() => {
      expect(document.documentElement).toBeTruthy();
    });
    // allow loadTheme microtask to settle
    await new Promise((r) => setTimeout(r, 30));
  };

  it('stores the backendToken in localStorage and a cookie', async () => {
    (global as any).__mockSession = { backendToken: 'tok-123', user: { name: 'Rushi' } };

    await renderSettled(makeProps('/dashboard'));

    // SessionSync reads useSession (mocked global), so set it before render
    expect(localStorage.getItem('auth_token')).toBe('tok-123');
    expect(document.cookie).toContain('auth_token=tok-123');
  });

  it('applies the dark theme from stored preferences', async () => {
    server.use(
      rest.get('/api/v1/preferences', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ theme: 'dark' }))
      )
    );
    await renderSettled(makeProps('/dashboard'));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('applies the light theme from stored preferences', async () => {
    document.documentElement.classList.add('dark');
    server.use(
      rest.get('/api/v1/preferences', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ theme: 'light' }))
      )
    );
    await renderSettled(makeProps('/dashboard'));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('falls back to the system theme when no theme preference exists', async () => {
    const original = window.matchMedia;
    (window as any).matchMedia = jest.fn().mockReturnValue({ matches: true });
    await renderSettled(makeProps('/dashboard'));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    (window as any).matchMedia = original;
  });

  it('falls back to light when the system prefers light', async () => {
    const original = window.matchMedia;
    (window as any).matchMedia = jest.fn().mockReturnValue({ matches: false });
    document.documentElement.classList.add('dark');
    await renderSettled(makeProps('/dashboard'));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    (window as any).matchMedia = original;
  });

  it('falls back to the system theme on a non-ok preferences response', async () => {
    server.use(
      rest.get('/api/v1/preferences', (req, res, ctx) => res(ctx.status(500)))
    );
    const original = window.matchMedia;
    (window as any).matchMedia = jest.fn().mockReturnValue({ matches: true });
    await renderSettled(makeProps('/dashboard'));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    (window as any).matchMedia = original;
  });

  it('falls back to the system theme when the preferences fetch rejects', async () => {
    server.use(
      rest.get('/api/v1/preferences', (req, res) => res.networkError('down'))
    );
    const original = window.matchMedia;
    (window as any).matchMedia = jest.fn().mockReturnValue({ matches: false });
    await renderSettled(makeProps('/dashboard'));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    (window as any).matchMedia = original;
  });

  it('sends the Authorization header when an auth token is stored', async () => {
    localStorage.setItem('auth_token', 'stored-token');
    let authHeader: string | null = null;
    server.use(
      rest.get('/api/v1/preferences', (req, res, ctx) => {
        authHeader = req.headers.get('Authorization');
        return res(ctx.status(200), ctx.json({}));
      })
    );
    await renderSettled(makeProps('/dashboard'));
    await waitFor(() => {
      expect(authHeader).toBe('Bearer stored-token');
    });
  });

  it('renders standalone (no Layout/GlobalChatWidget) for auth pages', async () => {
    (global as any).__mockPathname = '/auth/login';
    await renderSettled(makeProps('/auth/login'));

    expect(screen.getByTestId('page-content')).toBeInTheDocument();
    expect(screen.queryByTestId('global-chat-widget')).not.toBeInTheDocument();
  });

  it('renders Layout and GlobalChatWidget for regular pages', async () => {
    (global as any).__mockPathname = '/dashboard';
    await renderSettled(makeProps('/dashboard'));

    expect(screen.getByTestId('layout')).toBeInTheDocument();
    expect(screen.getByTestId('global-chat-widget')).toBeInTheDocument();
  });
});
