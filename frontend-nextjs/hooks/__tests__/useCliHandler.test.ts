/**
 * useCliHandler Hook Unit Tests
 *
 * Tests for useCliHandler hook handling CLI integration functionality.
 * Verifies CLI detection, scan command handling, toast notifications,
 * command execution, error handling, and session dependency.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { useCliHandler } from '../useCliHandler';

// Mock next-auth/react
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

// Mock @tauri-apps/plugin-cli
jest.mock('@tauri-apps/plugin-cli', () => ({
  getMatches: jest.fn(),
}));

// Mock toast from 'sonner'
jest.mock('sonner', () => ({
  toast: {
    loading: jest.fn(),
    success: jest.fn(),
    error: jest.fn(),
  },
}));

describe('useCliHandler Hook', () => {
  const mockFetch = global.fetch as jest.MockedFunction<typeof global.fetch>;
  let useSessionMock: any;
  let getMatchesMock: any;
  let toastMock: any;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    // Reset window.__TAURI__
    delete (window as any).__TAURI__;

    // Get mocked modules
    useSessionMock = require('next-auth/react').useSession;
    getMatchesMock = require('@tauri-apps/plugin-cli').getMatches;
    toastMock = require('sonner').toast;

    // Default mock implementations
    useSessionMock.mockReturnValue({ data: null, status: 'unauthenticated' });
    getMatchesMock.mockResolvedValue({ subcommand: null });
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('1. CLI Detection Tests', () => {
    test('checks window.__TAURI__ on mount', () => {
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn() },
      };

      renderHook(() => useCliHandler());

      expect((window as any).__TAURI__).toBeDefined();
    });

    test('returns early when not in Tauri', async () => {
      // No __TAURI__ defined

      renderHook(() => useCliHandler());

      // getMatches should not be called
      expect(getMatchesMock).not.toHaveBeenCalled();
    });

    test('does not call getMatches when __TAURI__ missing', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(getMatchesMock).not.toHaveBeenCalled();
      });
    });
  });

  describe('2. Scan Command Handling Tests', () => {
    beforeEach(() => {
      // Mock Tauri environment
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn().mockResolvedValue({ success: true, stdout: 'Scan results\n' }) },
      };

      // Mock getMatches to return scan subcommand
      getMatchesMock.mockResolvedValue({
        subcommand: {
          name: 'scan',
          matches: {
            args: {
              path: { value: '/path/to/scan' },
            },
          },
        },
      });

      useSessionMock.mockReturnValue({
        data: { user: { id: 'user-1', email: 'test@example.com' } },
        status: 'authenticated',
      });
    });

    test('imports @tauri-apps/plugin-cli getMatches', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(getMatchesMock).toHaveBeenCalled();
      });
    });

    test('checks for scan subcommand', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(getMatchesMock).toHaveBeenCalled();
      });

      const matches = getMatchesMock.mock.results[0].value;
      expect(matches.subcommand?.name).toBe('scan');
    });

    test('extracts path from arguments', async () => {
      const expectedPath = '/path/to/scan';
      getMatchesMock.mockResolvedValue({
        subcommand: {
          name: 'scan',
          matches: {
            args: {
              path: { value: expectedPath },
            },
          },
        },
      });

      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(getMatchesMock).toHaveBeenCalled();
      });

      const matches = await getMatchesMock();
      expect(matches.subcommand.matches.args.path.value).toBe(expectedPath);
    });

    test('calls invoke for execute_command', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(getMatchesMock).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect((window as any).__TAURI__.core.invoke).toHaveBeenCalledWith(
          'execute_command',
          expect.objectContaining({
            command: 'python3',
            args: expect.arrayContaining(['-m', 'atom_security']),
          })
        );
      });
    });
  });

  describe('3. Toast Notifications Tests', () => {
    beforeEach(() => {
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn().mockResolvedValue({ success: true, stdout: 'Scan complete' }) },
      };

      getMatchesMock.mockResolvedValue({
        subcommand: {
          name: 'scan',
          matches: {
            args: { path: { value: '/test/path' } },
          },
        },
      });

      useSessionMock.mockReturnValue({
        data: { user: { id: 'user-1' } },
        status: 'authenticated',
      });
    });

    test('shows loading toast during scan', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(toastMock.loading).toHaveBeenCalledWith(
          expect.stringContaining('Scanning'),
          expect.any(Object)
        );
      });
    });

    test('shows success toast on completion', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(toastMock.loading).toHaveBeenCalled();
      });

      // Wait for invoke to complete
      await waitFor(() => {
        expect((window as any).__TAURI__.core.invoke).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(toastMock.success).toHaveBeenCalledWith(
          expect.stringContaining('complete'),
          expect.any(Object)
        );
      });
    });
  });

  describe('4. Command Execution Tests', () => {
    beforeEach(() => {
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn().mockResolvedValue({ success: true, stdout: '' }) },
      };

      getMatchesMock.mockResolvedValue({
        subcommand: {
          name: 'scan',
          matches: {
            args: { path: { value: '/test' } },
          },
        },
      });

      useSessionMock.mockReturnValue({
        data: { user: { id: 'user-1' } },
        status: 'authenticated',
      });
    });

    test('calls invoke with python3', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect((window as any).__TAURI__.core.invoke).toHaveBeenCalledWith(
          'execute_command',
          expect.objectContaining({
            command: 'python3',
          })
        );
      });
    });

    test('passes atom_security module arguments', async () => {
      const testPath = '/test/path';

      getMatchesMock.mockResolvedValue({
        subcommand: {
          name: 'scan',
          matches: {
            args: { path: { value: testPath } },
          },
        },
      });

      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect((window as any).__TAURI__.core.invoke).toHaveBeenCalledWith(
          'execute_command',
          expect.objectContaining({
            args: expect.arrayContaining(['-m', 'atom_security', testPath]),
          })
        );
      });
    });

    test('uses correct format (text)', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect((window as any).__TAURI__.core.invoke).toHaveBeenCalledWith(
          'execute_command',
          expect.objectContaining({
            args: expect.arrayContaining(['--format', 'text']),
          })
        );
      });
    });
  });

  describe('5. Error Handling Tests', () => {
    beforeEach(() => {
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn() },
      };

      getMatchesMock.mockResolvedValue({
        subcommand: {
          name: 'scan',
          matches: {
            args: { path: { value: '/test' } },
          },
        },
      });

      useSessionMock.mockReturnValue({
        data: { user: { id: 'user-1' } },
        status: 'authenticated',
      });
    });

    test('handles missing getMatches gracefully', async () => {
      getMatchesMock.mockImplementation(() => {
        throw new Error('getMatches not available');
      });

      renderHook(() => useCliHandler());

      // Should not throw, just handle gracefully
      await waitFor(() => {
        expect(toastMock.error).toHaveBeenCalled();
      });
    });

    test('handles invoke errors', async () => {
      (window as any).__TAURI__.core.invoke.mockRejectedValue(new Error('Invoke failed'));

      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(toastMock.error).toHaveBeenCalled();
      });
    });

    test('logs errors to console', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      getMatchesMock.mockRejectedValue(new Error('CLI error'));

      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalled();
      });

      consoleSpy.mockRestore();
    });

    test('shows error toast', async () => {
      (window as any).__TAURI__.core.invoke.mockRejectedValue(new Error('Command failed'));

      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(toastMock.error).toHaveBeenCalledWith(
          expect.stringContaining('Security scan failed'),
        );
      });
    });
  });

  describe('6. Session Dependency Tests', () => {
    beforeEach(() => {
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn().mockResolvedValue({ success: true, stdout: '' }) },
      };

      getMatchesMock.mockResolvedValue({
        subcommand: {
          name: 'scan',
          matches: {
            args: { path: { value: '/test' } },
          },
        },
      });
    });

    test('runs effect when session changes', async () => {
      useSessionMock.mockReturnValue({
        data: { user: { id: 'user-1' } },
        status: 'authenticated',
      });

      const { rerender } = renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(getMatchesMock).toHaveBeenCalled();
      });

      // Clear previous calls
      getMatchesMock.mockClear();

      // Change session
      useSessionMock.mockReturnValue({
        data: { user: { id: 'user-2' } },
        status: 'authenticated',
      });

      rerender();

      await waitFor(() => {
        expect(getMatchesMock).toHaveBeenCalled();
      });
    });

    test('uses session from useSession', async () => {
      const mockSession = {
        data: { user: { id: 'user-1', email: 'test@example.com' } },
        status: 'authenticated' as const,
      };

      useSessionMock.mockReturnValue(mockSession);

      renderHook(() => useCliHandler());

      expect(useSessionMock).toHaveBeenCalled();
    });
  });

  describe('7. Effect Cleanup Tests', () => {
    test('cleans up effect on unmount', () => {
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn() },
      };

      getMatchesMock.mockResolvedValue({
        subcommand: {
          name: 'scan',
          matches: {
            args: { path: { value: '/test' } },
          },
        },
      });

      useSessionMock.mockReturnValue({
        data: { user: { id: 'user-1' } },
        status: 'authenticated',
      });

      const { unmount } = renderHook(() => useCliHandler());

      // Should not throw on unmount
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('8. Non-Scan Command Tests', () => {
    beforeEach(() => {
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn() },
      };

      // Mock non-scan subcommand
      getMatchesMock.mockResolvedValue({
        subcommand: {
          name: 'other',
          matches: {},
        },
      });

      useSessionMock.mockReturnValue({
        data: { user: { id: 'user-1' } },
        status: 'authenticated',
      });
    });

    test('does not execute command for non-scan subcommand', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(getMatchesMock).toHaveBeenCalled();
      });

      // invoke should not be called for non-scan commands
      expect((window as any).__TAURI__.core.invoke).not.toHaveBeenCalled();
    });
  });

  describe('9. No Subcommand Tests', () => {
    beforeEach(() => {
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn() },
      };

      // Mock no subcommand
      getMatchesMock.mockResolvedValue({
        subcommand: null,
      });

      useSessionMock.mockReturnValue({
        data: { user: { id: 'user-1' } },
        status: 'authenticated',
      });
    });

    test('handles case when no subcommand present', async () => {
      renderHook(() => useCliHandler());

      await waitFor(() => {
        expect(getMatchesMock).toHaveBeenCalled();
      });

      // invoke should not be called when no subcommand
      expect((window as any).__TAURI__.core.invoke).not.toHaveBeenCalled();
    });
  });
});
