/**
 * useCliHandler — supplemental branch coverage:
 * Tauri scan path (falsy results, execution errors), getMatches failures,
 * and the non-Tauri no-op path.
 */

const mockGetSession = jest.fn();
jest.mock('next-auth/react', () => ({ useSession: () => ({ data: mockGetSession() }) }));
jest.mock('sonner', () => ({
  toast: { loading: jest.fn(), success: jest.fn(), error: jest.fn(), message: jest.fn() },
}));
const mockGetMatches = jest.fn();
jest.mock('@tauri-apps/plugin-cli', () => ({
  __esModule: true,
  getMatches: () => mockGetMatches(),
}));

import { renderHook, act, waitFor } from '@testing-library/react';
import { useCliHandler } from '../useCliHandler';
import { toast } from 'sonner';

const toastError = toast.error as jest.Mock;

describe('useCliHandler (supplemental branches)', () => {
  const originalTauri = (window as any).__TAURI__;
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, 'log').mockImplementation(() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    mockGetSession.mockReturnValue(null);
    (window as any).__TAURI__ = {
      core: { invoke: jest.fn() },
    };
  });

  afterEach(() => {
    if (originalTauri === undefined) delete (window as any).__TAURI__;
    else (window as any).__TAURI__ = originalTauri;
    global.fetch = originalFetch;
  });

  test('reports issues when the scan result is falsy', async () => {
    mockGetMatches.mockResolvedValue({
      subcommand: { name: 'scan', matches: { args: { path: { value: '/tmp/x.py' } } } },
    });
    (window as any).__TAURI__.core.invoke.mockResolvedValue(undefined);
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(mockGetMatches).toHaveBeenCalled();
    });
    expect(toastError).not.toHaveBeenCalled();
  });

  test('toasts an error when the scan command throws', async () => {
    mockGetMatches.mockResolvedValue({
      subcommand: { name: 'scan', matches: { args: { path: { value: '/tmp/x.py' } } } },
    });
    (window as any).__TAURI__.core.invoke.mockRejectedValue(new Error('scanner crashed'));
    (global.fetch as any) = jest.fn().mockRejectedValue(new Error('backend unreachable'));
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith(
        expect.stringContaining('Security scan failed')
      );
    });
  });

  test('tolerates getMatches failures', async () => {
    mockGetMatches.mockRejectedValue(new Error('cli plugin missing'));
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(console.error).toHaveBeenCalledWith('[CLI] Error checking CLI matches:', expect.any(Error));
    });
  });

  test('is a no-op without the Tauri bridge', async () => {
    delete (window as any).__TAURI__;
    renderHook(() => useCliHandler());
    await act(async () => {});
    expect(mockGetMatches).not.toHaveBeenCalled();
  });

  test('is a no-op when getMatches resolves null', async () => {
    (window as any).__TAURI__.core.invoke.mockResolvedValue(undefined);
    mockGetMatches.mockResolvedValue(null);
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(mockGetMatches).toHaveBeenCalled();
    });
    expect(toastError).not.toHaveBeenCalled();
  });

  test('is a no-op when subcommand is absent', async () => {
    (window as any).__TAURI__.core.invoke.mockResolvedValue(undefined);
    mockGetMatches.mockResolvedValue({});
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(mockGetMatches).toHaveBeenCalled();
    });
    expect(toastError).not.toHaveBeenCalled();
  });

  test('is a no-op when subcommand is null', async () => {
    (window as any).__TAURI__.core.invoke.mockResolvedValue(undefined);
    mockGetMatches.mockResolvedValue({ subcommand: null });
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(mockGetMatches).toHaveBeenCalled();
    });
    expect(toastError).not.toHaveBeenCalled();
  });

  test('is a no-op for non-scan subcommands', async () => {
    (window as any).__TAURI__.core.invoke.mockResolvedValue(undefined);
    mockGetMatches.mockResolvedValue({ subcommand: { name: 'serve' } });
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(mockGetMatches).toHaveBeenCalled();
    });
    expect(toastError).not.toHaveBeenCalled();
  });

  test('toasts an error with stderr when the scan finds issues', async () => {
    mockGetMatches.mockResolvedValue({
      subcommand: { name: 'scan', matches: { args: { path: { value: '/tmp/x.py' } } } },
    });
    (window as any).__TAURI__.core.invoke.mockResolvedValue({ success: false, stderr: 'vulnerability found', stdout: '' });
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith('Security scan detected potential vulnerabilities.');
    });
  });

  test('toasts an error with stdout when stderr is empty', async () => {
    mockGetMatches.mockResolvedValue({
      subcommand: { name: 'scan', matches: { args: { path: { value: '/tmp/x.py' } } } },
    });
    (window as any).__TAURI__.core.invoke.mockResolvedValue({ success: false, stderr: '', stdout: 'output here' });
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith('Security scan detected potential vulnerabilities.');
    });
  });

  test('toasts success when the scan is clean', async () => {
    mockGetMatches.mockResolvedValue({
      subcommand: { name: 'scan', matches: { args: { path: { value: '/tmp/x.py' } } } },
    });
    (window as any).__TAURI__.core.invoke.mockResolvedValue({ success: true, stdout: 'no issues' });
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect((toast.success as jest.Mock)).toHaveBeenCalledWith(
        'Security scan complete. Check console for details.',
        { duration: 5000 },
      );
    });
  });

  test('uses the top-level __TAURI__.invoke fallback when core is absent', async () => {
    const fallbackInvoke = jest.fn().mockResolvedValue({ success: false, stderr: 'issues', stdout: '' });
    (window as any).__TAURI__ = { invoke: fallbackInvoke };
    mockGetMatches.mockResolvedValue({
      subcommand: { name: 'scan', matches: { args: { path: { value: '/tmp/x.py' } } } },
    });
    renderHook(() => useCliHandler());
    await waitFor(() => {
      expect(fallbackInvoke).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith('Security scan detected potential vulnerabilities.');
    });
  });
});
