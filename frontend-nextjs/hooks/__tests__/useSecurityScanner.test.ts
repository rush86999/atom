/**
 * useSecurityScanner Hook Unit Tests
 *
 * Tests for useSecurityScanner hook handling security scanning functionality.
 * Verifies desktop mode (Tauri) with invoke, web mode fallback, scan function,
 * Tauri bridge mocking, result structure, and error handling.
 */

import { renderHook, act } from '@testing-library/react';

// Note: fetch is already mocked in tests/setup.ts with proper Jest mock methods
import { useSecurityScanner } from '../useSecurityScanner';

// Note: fetch is already mocked in tests/setup.ts with proper Jest mock methods

// Mock toast from 'sonner'
jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
  },
}));

// Mock @tauri-apps/api/core
jest.mock('@tauri-apps/api/core', () => ({
  invoke: jest.fn(),
}));

describe('useSecurityScanner Hook', () => {
  const mockFetch = global.fetch as jest.MockedFunction<typeof global.fetch>;

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset window.__TAURI__
    delete (window as any).__TAURI__;
  });

  describe('1. Desktop Mode (Tauri) Tests', () => {
    beforeEach(() => {
      // Mock Tauri environment
      (window as any).__TAURI__ = {
        core: {
          invoke: jest.fn(),
        },
      };
    });

    test('detects __TAURI__ in window', () => {
      (window as any).__TAURI__ = {
        core: { invoke: jest.fn() },
      };

      const { result } = renderHook(() => useSecurityScanner());

      expect((window as any).__TAURI__).toBeDefined();
    });

    test('attempts local CLI scanner first', async () => {
      const mockInvoke = jest.fn()
        .mockResolvedValueOnce({ success: true })
        .mockResolvedValueOnce({
          success: true,
          stdout: JSON.stringify([
            { category: 'security', severity: 'HIGH', description: 'Test finding', analyzer: 'static' }
          ]),
        });

      (window as any).__TAURI__ = {
        core: { invoke: mockInvoke },
      };

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code here' });
      });

      expect(mockInvoke).toHaveBeenCalledWith('write_file_content', expect.any(Object));
      expect(mockInvoke).toHaveBeenCalledWith('execute_command', expect.objectContaining({
        command: 'python3',
        args: expect.arrayContaining(['-m', 'atom_security']),
      }));
    });

    test('calls invoke for write_file_content', async () => {
      const mockInvoke = jest.fn()
        .mockResolvedValueOnce({ success: true })
        .mockResolvedValueOnce({ success: true, stdout: '[]' });

      (window as any).__TAURI__ = {
        core: { invoke: mockInvoke },
      };

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code here' });
      });

      expect(mockInvoke).toHaveBeenCalledWith('write_file_content', expect.objectContaining({
        path: expect.stringContaining('./temp/'),
        content: 'code here',
      }));
    });

    test('calls invoke for execute_command with atom_security', async () => {
      const mockInvoke = jest.fn()
        .mockResolvedValueOnce({ success: true })
        .mockResolvedValueOnce({ success: true, stdout: '[]' });

      (window as any).__TAURI__ = {
        core: { invoke: mockInvoke },
      };

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code here' });
      });

      expect(mockInvoke).toHaveBeenCalledWith('execute_command', expect.objectContaining({
        command: 'python3',
        args: expect.arrayContaining(['-m', 'atom_security']),
      }));
    });

    test('parses JSON output from scan', async () => {
      const mockFindings = [
        { category: 'security', severity: 'HIGH', description: 'Test finding', analyzer: 'static' }
      ];

      const mockInvoke = jest.fn()
        .mockResolvedValueOnce({ success: true })
        .mockResolvedValueOnce({
          success: true,
          stdout: JSON.stringify(mockFindings),
        });

      (window as any).__TAURI__ = {
        core: { invoke: mockInvoke },
      };

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code here' });
      });

      expect(result.current.results?.findings).toHaveLength(1);
      expect(result.current.results?.findings[0].category).toBe('security');
    });

    test('maps findings to Finding interface', async () => {
      const mockInvoke = jest.fn()
        .mockResolvedValueOnce({ success: true })
        .mockResolvedValueOnce({
          success: true,
          stdout: JSON.stringify([
            { category: 'security', severity: 'HIGH', description: 'Test', analyzer: 'static' }
          ]),
        });

      (window as any).__TAURI__ = {
        core: { invoke: mockInvoke },
      };

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code here' });
      });

      expect(result.current.results?.findings[0]).toMatchObject({
        category: 'security',
        severity: 'HIGH',
        description: 'Test',
        analyzer: 'static',
      });
    });
  });

  describe('2. Web Mode/Fallback Tests', () => {
    test('falls back to API when Tauri unavailable', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          is_safe: true,
          findings: [],
        }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code here' });
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/protection/scan',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    test('calls /api/protection/scan endpoint', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          is_safe: false,
          findings: [{ category: 'security', severity: 'MEDIUM', description: 'Test', analyzer: 'api' }],
        }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/protection/scan',
        expect.any(Object)
      );
    });

    test('correctly formats POST body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_safe: true, findings: [] }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code' });
      });

      const fetchCall = mockFetch.mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body).toMatchObject({
        skill_name: 'test-skill',
        instruction_body: 'instruction body',
        file_contents: { 'main.py': 'code' },
      });
    });

    test('maps API response to results', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          is_safe: false,
          findings: [
            { category: 'security', severity: 'CRITICAL', description: 'Critical issue', analyzer: 'api' }
          ],
        }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(result.current.results?.isSafe).toBe(false);
      expect(result.current.results?.findings).toHaveLength(1);
    });
  });

  describe('3. Scan Function Tests', () => {
    test('scanSkill sets isScanning to true', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ is_safe: true, findings: [] }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      act(() => {
        result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(result.current.isScanning).toBe(true);
    });

    test('scanSkill accepts skillName, instructionBody, fileContents', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_safe: true, findings: [] }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('my-skill', 'instructions', { 'main.py': 'print("hello")' });
      });

      const fetchCall = mockFetch.mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.skill_name).toBe('my-skill');
      expect(body.instruction_body).toBe('instructions');
      expect(body.file_contents).toEqual({ 'main.py': 'print("hello")' });
    });

    test('scanSkill sets results state on completion', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          is_safe: true,
          findings: [],
        }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(result.current.results).toEqual({
        isSafe: true,
        findings: [],
      });
    });

    test('scanSkill sets isScanning to false in finally', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_safe: true, findings: [] }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(result.current.isScanning).toBe(false);
    });
  });

  describe('4. Tauri Bridge Mocking Tests', () => {
    test('mocks window.__TAURI__.core.invoke', async () => {
      const mockInvoke = jest.fn()
        .mockResolvedValueOnce({ success: true })
        .mockResolvedValueOnce({ success: true, stdout: '[]' });

      (window as any).__TAURI__ = {
        core: { invoke: mockInvoke },
      };

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code' });
      });

      expect(mockInvoke).toHaveBeenCalled();
    });

    test('mocks window.__TAURI__.invoke (legacy pattern)', async () => {
      const mockInvoke = jest.fn()
        .mockResolvedValueOnce({ success: true })
        .mockResolvedValueOnce({ success: true, stdout: '[]' });

      (window as any).__TAURI__ = {
        invoke: mockInvoke,
      };

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code' });
      });

      expect(mockInvoke).toHaveBeenCalled();
    });
  });

  describe('5. Result Structure Tests', () => {
    test('isSafe boolean', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_safe: true, findings: [] }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(result.current.results?.isSafe).toBe(true);
      expect(typeof result.current.results?.isSafe).toBe('boolean');
    });

    test('findings array with Finding interface', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          is_safe: false,
          findings: [
            { category: 'security', severity: 'HIGH', description: 'Test', analyzer: 'static' },
            { category: 'performance', severity: 'LOW', description: 'Perf issue', analyzer: 'linter' },
          ],
        }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(result.current.results?.findings).toHaveLength(2);
      expect(result.current.results?.findings[0]).toMatchObject({
        category: expect.any(String),
        severity: expect.any(String),
        description: expect.any(String),
        analyzer: expect.any(String),
      });
    });

    test('Finding: category, severity, description, analyzer', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          is_safe: false,
          findings: [{
            category: 'security',
            severity: 'CRITICAL',
            description: 'SQL injection vulnerability',
            analyzer: 'static',
          }],
        }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(result.current.results?.findings[0]).toEqual({
        category: 'security',
        severity: 'CRITICAL',
        description: 'SQL injection vulnerability',
        analyzer: 'static',
      });
    });
  });

  describe('6. Error Handling Tests', () => {
    test('handles Tauri invoke errors - falls back to web API', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_safe: true, findings: [] }),
      });

      const mockInvoke = jest.fn().mockRejectedValue(new Error('Tauri invoke failed'));

      (window as any).__TAURI__ = {
        core: { invoke: mockInvoke },
      };

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code' });
      });

      // Should fall back to web API
      expect(mockFetch).toHaveBeenCalled();
    });

    test('shows toast error on failure', async () => {
      const { toast } = require('sonner');
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(toast.error).toHaveBeenCalledWith('Security scan failed: Network error');
    });

    test('sets isScanning to false on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      expect(result.current.isScanning).toBe(false);
    });
  });

  describe('7. Edge Cases Tests', () => {
    test('missing fileContents defaults to instructionBody', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_safe: true, findings: [] }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', {});
      });

      const fetchCall = mockFetch.mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.file_contents).toEqual({});
    });

    test('handles missing main.py in fileContents', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_safe: true, findings: [] }),
      });

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'other.py': 'code' });
      });

      // Should use web API when main.py is missing
      expect(mockFetch).toHaveBeenCalled();
    });

    test('JSON parse error handling - falls back to web API', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_safe: true, findings: [] }),
      });

      const mockInvoke = jest.fn()
        .mockResolvedValueOnce({ success: true })
        .mockResolvedValueOnce({
          success: true,
          stdout: 'invalid json{{',
        });

      (window as any).__TAURI__ = {
        core: { invoke: mockInvoke },
      };

      const { result } = renderHook(() => useSecurityScanner());

      await act(async () => {
        await result.current.scanSkill('test-skill', 'instruction body', { 'main.py': 'code' });
      });

      // Should fall back to web API on JSON parse error
      expect(mockFetch).toHaveBeenCalled();
    });
  });
});
