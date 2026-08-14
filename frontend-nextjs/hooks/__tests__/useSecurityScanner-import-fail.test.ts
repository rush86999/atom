/**
 * useSecurityScanner Tauri-import-failure Coverage Test (wave 119)
 *
 * Runs in its own registry so the @tauri-apps/api/core mock factory can THROW
 * at module instantiation — exercising the `catch` around the dynamic import
 * (useSecurityScanner.ts line 46): console.warn + web-API fallback.
 */

import { renderHook, act } from '@testing-library/react';

import { useSecurityScanner } from '../useSecurityScanner';

jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
  },
}));

jest.mock('@tauri-apps/api/core', () => {
  throw new Error('cannot resolve module');
});

describe('useSecurityScanner - Tauri import failure', () => {
  let mockFetch: any;

  beforeEach(() => {
    mockFetch = global.fetch = jest.fn();
    jest.clearAllMocks();
    delete (window as any).__TAURI__;
  });

  test('logs a warning and falls back to the web API when the Tauri core module cannot be imported', async () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();
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

    expect(warnSpy).toHaveBeenCalledWith(
      '[Security] Could not load Tauri invoke:',
      expect.any(Error)
    );
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/protection/scan',
      expect.any(Object)
    );
    expect(result.current.results?.isSafe).toBe(true);

    warnSpy.mockRestore();
  });
});
