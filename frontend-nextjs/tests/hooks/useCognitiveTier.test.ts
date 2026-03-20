/**
 * useCognitiveTier Hook Tests
 *
 * Purpose: Validate cognitive tier preferences hook behavior
 *
 * Testing Strategy:
 * - Test preferences fetching and state management
 * - Test saving preferences
 * - Test cost estimation
 * - Test tier comparison
 * - Test loading and saving states
 * - Test error handling
 *
 * Coverage Targets:
 * - API interactions for tier preferences
 * - State management (loading, saving)
 * - Error scenarios
 * - Cost estimation and tier comparison
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { useCognitiveTier, type TierPreference } from '@/hooks/useCognitiveTier';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch as any;

describe('useCognitiveTier', () => {
  const mockPreferences: TierPreference = {
    id: 'pref-1',
    workspace_id: 'default',
    default_tier: 'standard',
    min_tier: 'micro',
    max_tier: 'complex',
    monthly_budget_cents: 10000,
    max_cost_per_request_cents: 50,
    enable_cache_aware_routing: true,
    enable_auto_escalation: true,
    enable_minimax_fallback: false,
    preferred_providers: ['openai', 'anthropic']
  };

  beforeEach(() => {
    // Clear mock and reset implementation
    mockFetch.mockClear();
    mockFetch.mockReset();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('initialization', () => {
    test('initializes with null preferences and loading true', () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      expect(result.current.preferences).toBeNull();
      expect(result.current.loading).toBe(true);
      expect(result.current.saving).toBe(false);
    });

    test('fetches preferences on mount', async () => {
      mockFetch.mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: async () => mockPreferences
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      // Wait for loading to complete and state to update
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.preferences).toEqual(mockPreferences);
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/cognitive-tier/preferences/default');
    });

    test('handles fetch error gracefully', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.preferences).toBeNull();
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch tier preferences:',
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });

    test('handles non-ok response gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.preferences).toBeNull();
    });
  });

  describe('fetchPreferences', () => {
    test('manually fetches preferences', async () => {
      mockFetch.mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: async () => mockPreferences
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      mockFetch.mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({ ...mockPreferences, default_tier: 'versatile' })
        })
      );

      await act(async () => {
        await result.current.fetchPreferences();
      });

      await waitFor(() => {
        expect(result.current.preferences?.default_tier).toBe('versatile');
      });
    });
  });

  describe('savePreferences', () => {
    test('saves preferences successfully', async () => {
      mockFetch.mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: async () => mockPreferences
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      const updatedPrefs = { default_tier: 'versatile' };
      mockFetch.mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({ ...mockPreferences, ...updatedPrefs })
        })
      );

      let saveResult: boolean | undefined;
      await act(async () => {
        saveResult = await result.current.savePreferences(updatedPrefs);
      });

      expect(saveResult).toBe(true);

      await waitFor(() => {
        expect(result.current.preferences?.default_tier).toBe('versatile');
      });
    });

    test('returns false on save error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      let saveResult: boolean | undefined;
      await act(async () => {
        saveResult = await result.current.savePreferences({ default_tier: 'versatile' });
      });

      expect(saveResult).toBe(false);
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to save tier preferences:',
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe('estimateCost', () => {
    test('estimates cost successfully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      const mockCostEstimates = [
        {
          tier: 'micro',
          estimated_cost_usd: 0.001,
          models_in_tier: ['gpt-4o-mini', 'claude-haiku']
        },
        {
          tier: 'standard',
          estimated_cost_usd: 0.01,
          models_in_tier: ['gpt-4o', 'claude-sonnet']
        }
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockCostEstimates
      });

      let estimates: any;
      await act(async () => {
        estimates = await result.current.estimateCost('test prompt', 100);
      });

      expect(estimates).toEqual(mockCostEstimates);
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/cognitive-tier/estimate-cost?prompt=test+prompt&estimated_tokens=100'
      );
    });

    test('estimates cost without estimated tokens', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => []
      });

      await act(async () => {
        await result.current.estimateCost('test prompt');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/cognitive-tier/estimate-cost?prompt=test+prompt'
      );
    });

    test('returns empty array on estimate error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      let estimates: any;
      await act(async () => {
        estimates = await result.current.estimateCost('test prompt', 100);
      });

      expect(estimates).toEqual([]);
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to estimate cost:',
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe('compareTiers', () => {
    test('compares tiers successfully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      const mockComparisons = [
        {
          tier: 'micro',
          quality_range: '70-75%',
          cost_range: '$0.10-0.50/M tokens',
          example_models: ['gpt-4o-mini'],
          supports_cache: true
        },
        {
          tier: 'standard',
          quality_range: '75-85%',
          cost_range: '$2-10/M tokens',
          example_models: ['gpt-4o', 'claude-sonnet-4.5'],
          supports_cache: true
        }
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockComparisons
      });

      let comparisons: any;
      await act(async () => {
        comparisons = await result.current.compareTiers();
      });

      expect(comparisons).toEqual(mockComparisons);
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/cognitive-tier/compare-tiers');
    });

    test('returns empty array on compare error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      let comparisons: any;
      await act(async () => {
        comparisons = await result.current.compareTiers();
      });

      expect(comparisons).toEqual([]);
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to compare tiers:',
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe('integration scenarios', () => {
    test('fetch and save preferences workflow', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.preferences).toEqual(mockPreferences);

      const updatedPrefs = {
        default_tier: 'versatile',
        monthly_budget_cents: 20000
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...mockPreferences, ...updatedPrefs })
      });

      await act(async () => {
        await result.current.savePreferences(updatedPrefs);
      });

      expect(result.current.preferences?.default_tier).toBe('versatile');
      expect(result.current.preferences?.monthly_budget_cents).toBe(20000);
    });

    test('multiple save operations', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...mockPreferences, default_tier: 'versatile' })
      });

      await act(async () => {
        await result.current.savePreferences({ default_tier: 'versatile' });
      });

      expect(result.current.preferences?.default_tier).toBe('versatile');

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...mockPreferences, default_tier: 'heavy' })
      });

      await act(async () => {
        await result.current.savePreferences({ default_tier: 'heavy' });
      });

      expect(result.current.preferences?.default_tier).toBe('heavy');
    });

    test('cost estimation after preference update', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...mockPreferences, max_cost_per_request_cents: 10 })
      });

      await act(async () => {
        await result.current.savePreferences({ max_cost_per_request_cents: 10 });
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            tier: 'micro',
            estimated_cost_usd: 0.001,
            models_in_tier: ['gpt-4o-mini']
          }
        ]
      });

      let estimates: any;
      await act(async () => {
        estimates = await result.current.estimateCost('test prompt', 100);
      });

      expect(estimates).toHaveLength(1);
      expect(estimates[0].tier).toBe('micro');
    });
  });

  describe('state persistence', () => {
    test('maintains state across re-renders', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences
      });

      const { result, rerender } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      const initialPrefs = result.current.preferences;

      rerender();

      expect(result.current.preferences).toEqual(initialPrefs);
      expect(result.current.loading).toBe(false);
      expect(result.current.saving).toBe(false);
    });
  });
});
