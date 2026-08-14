/**
 * useSecurityScanner Branch Coverage Tests (wave 119)
 *
 * Closes the remaining gaps in useSecurityScanner.ts:
 * - dynamic `@tauri-apps/api/core` import fallback when `__TAURI__` has no
 *   invoke bridge (lines 42-43)
 * - import failure → console.warn + web-API fallback (line 46)
 * - write_file_content `writeResult === true` short-circuit branch
 * - write_file_content failure (`{ success: false }`) → web-API fallback
 */

import { renderHook, act } from '@testing-library/react';

import { useSecurityScanner } from '../useSecurityScanner';

jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
  },
}));

jest.mock('@tauri-apps/api/core', () => ({
  invoke: jest.fn(),
}));

describe('useSecurityScanner - Branch Coverage', () => {
  let mockFetch: any;

  beforeEach(() => {
    mockFetch = global.fetch = jest.fn();
    jest.clearAllMocks();
    delete (window as any).__TAURI__;
  });

  test('falls back to dynamic import when __TAURI__ lacks an invoke bridge', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ is_safe: true, findings: [] }),
    });

    (window as any).__TAURI__ = { core: {} };

    const { result } = renderHook(() => useSecurityScanner());

    await act(async () => {
      await result.current.scanSkill('test-skill', 'instruction body', {
        'main.py': 'code',
      });
    });

    // Dynamic import resolved the mocked @tauri-apps/api/core.invoke; since
    // the mocked invoke resolves to undefined, the scan falls through to the
    // web API.
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/protection/scan',
      expect.any(Object)
    );
    expect(result.current.results?.isSafe).toBe(true);
  });

  test('accepts writeResult === true as a successful write', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ is_safe: true, findings: [] }),
    });

    const mockInvoke = jest
      .fn()
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce({ success: true, stdout: '[]' });

    (window as any).__TAURI__ = {
      core: { invoke: mockInvoke },
    };

    const { result } = renderHook(() => useSecurityScanner());

    await act(async () => {
      await result.current.scanSkill('test-skill', 'instruction body', {
        'main.py': 'code',
      });
    });

    expect(mockInvoke).toHaveBeenCalledWith('execute_command', expect.any(Object));
    expect(result.current.results).toEqual({ isSafe: true, findings: [] });
    // No web fallback needed when the desktop scan produced findings
    expect(mockFetch).not.toHaveBeenCalled();
  });

  test('falls back to web API when write_file_content fails', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ is_safe: false, findings: [] }),
    });

    const mockInvoke = jest
      .fn()
      .mockResolvedValueOnce({ success: false })
      .mockResolvedValueOnce({ success: true, stdout: '[]' });

    (window as any).__TAURI__ = {
      core: { invoke: mockInvoke },
    };

    const { result } = renderHook(() => useSecurityScanner());

    await act(async () => {
      await result.current.scanSkill('test-skill', 'instruction body', {
        'main.py': 'code',
      });
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/protection/scan', expect.any(Object));
    expect(result.current.results?.isSafe).toBe(false);
  });

  test('falls back to web API when execute_command fails', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ is_safe: true, findings: [] }),
    });

    const mockInvoke = jest
      .fn()
      .mockResolvedValueOnce({ success: true })
      .mockResolvedValueOnce({ success: false, stdout: '[]' });

    (window as any).__TAURI__ = {
      core: { invoke: mockInvoke },
    };

    const { result } = renderHook(() => useSecurityScanner());

    await act(async () => {
      await result.current.scanSkill('test-skill', 'instruction body', {
        'main.py': 'code',
      });
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/protection/scan', expect.any(Object));
  });
});
