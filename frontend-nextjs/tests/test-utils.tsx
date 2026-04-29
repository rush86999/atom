/**
 * Test Utilities for Phase 299-07
 *
 * Provides helper functions for rendering components with proper context providers.
 * This fixes "Element Not Found" errors caused by missing context providers.
 */

import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

// Create a test-specific QueryClient
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      cacheTime: 0,
    },
    mutations: {
      retry: false,
    },
  },
});

/**
 * renderWithProviders - Render components with all required context providers
 *
 * This helper wraps components with:
 * - QueryClientProvider (React Query)
 * - BrowserRouter (React Router)
 * - ThemeProvider (if needed in future)
 *
 * Usage:
 *   renderWithProviders(<MyComponent />)
 *   renderWithProviders(<MyComponent />, { options })
 */
interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  queryClient?: QueryClient;
  router?: boolean;
}

export function renderWithProviders(
  ui: ReactElement,
  {
    queryClient = createTestQueryClient(),
    router = true,
    ...renderOptions
  }: RenderWithProvidersOptions = {}
) {
  function Wrapper({ children }: { children: React.ReactNode }) {
    let wrapped = children;

    // Wrap with QueryClientProvider
    wrapped = <QueryClientProvider client={queryClient}>{wrapped}</QueryClientProvider>;

    // Wrap with BrowserRouter if router is enabled
    if (router) {
      wrapped = <BrowserRouter>{wrapped}</BrowserRouter>;
    }

    return <>{wrapped}</>;
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient,
  };
}

/**
 * Re-export everything from React Testing Library
 */
export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
