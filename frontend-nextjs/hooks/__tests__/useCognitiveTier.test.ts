/**
 * useCognitiveTier Hook Unit Tests
 *
 * Tests for useCognitiveTier hook managing LLM cognitive tier preferences.
 * Verifies preference fetching, saving, cost estimation, tier comparison,
 * and loading/saving state management.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useCognitiveTier } from '../useCognitiveTier';
import { rest } from 'msw';
import { overrideHandler } from '@/tests/mocks/server';

describe('useCognitiveTier Hook', () => {
  const mockPreferences = {
    id: 'pref-1',
    workspace_id: 'default',
    default_tier: 'Standard',
    min_tier: 'Micro',
    max_tier: 'Complex',
    monthly_budget_cents: 10000,
    max_cost_per_request_cents: 50,
    enable_cache_aware_routing: true,
    enable_auto_escalation: true,
    enable_minimax_fallback: false,
    preferred_providers: ['openai', 'anthropic'],
  };

  beforeEach(() => {
    // Set up default handler for preferences endpoint
    overrideHandler(
      rest.get('/api/v1/cognitive-tier/preferences/default', (req, res, ctx) => {
        return res(ctx.json(mockPreferences));
      })
    );
  });

  describe('1. Fetch Preferences Tests', () => {
    test('fetches preferences on mount', async () => {
      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.preferences).toEqual(mockPreferences);
      });
    });

    test('sets preferences state on successful fetch', async () => {
      const customPrefs = {
        id: 'pref-2',
        workspace_id: 'default',
        default_tier: 'Versatile',
        min_tier: null,
        max_tier: null,
        monthly_budget_cents: 5000,
        max_cost_per_request_cents: 25,
        enable_cache_aware_routing: false,
        enable_auto_escalation: false,
        enable_minimax_fallback: true,
        preferred_providers: ['openai'],
      };

      overrideHandler(
        rest.get('/api/v1/cognitive-tier/preferences/default', (req, res, ctx) => {
          return res(ctx.json(customPrefs));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.preferences).toEqual(customPrefs);
      });
    });

    test('sets loading to false after fetch', async () => {
      const { result } = renderHook(() => useCognitiveTier());

      expect(result.current.loading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
    });

    test('handles API errors gracefully', async () => {
      overrideHandler(
        rest.get('/api/v1/cognitive-tier/preferences/default', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.preferences).toBeNull();
    });
  });

  describe('2. Save Preferences Tests', () => {
    test('sends POST request with correct payload', async () => {
      const mockUpdatedPrefs = {
        default_tier: 'Versatile',
        enable_cache_aware_routing: true,
      };

      const mockResponse = {
        id: 'pref-1',
        workspace_id: 'default',
        ...mockUpdatedPrefs,
        min_tier: null,
        max_tier: null,
        monthly_budget_cents: null,
        max_cost_per_request_cents: null,
        enable_auto_escalation: false,
        enable_minimax_fallback: false,
        preferred_providers: [],
      };

      let receivedPayload: any = null;

      overrideHandler(
        rest.post('/api/v1/cognitive-tier/preferences/default', async (req, res, ctx) => {
          receivedPayload = await req.json();
          return res(ctx.json(mockResponse));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      await act(async () => {
        const success = await result.current.savePreferences(mockUpdatedPrefs);
        expect(success).toBe(true);
      });

      expect(receivedPayload).toMatchObject(mockUpdatedPrefs);
      expect(receivedPayload?.workspace_id).toBe('default');
    });

    test('updates preferences state on success', async () => {
      const mockUpdatedPrefs = {
        default_tier: 'Heavy',
      };

      const mockResponse = {
        id: 'pref-1',
        workspace_id: 'default',
        default_tier: 'Heavy',
        min_tier: null,
        max_tier: null,
        monthly_budget_cents: null,
        max_cost_per_request_cents: null,
        enable_cache_aware_routing: false,
        enable_auto_escalation: false,
        enable_minimax_fallback: false,
        preferred_providers: [],
      };

      overrideHandler(
        rest.post('/api/v1/cognitive-tier/preferences/default', (req, res, ctx) => {
          return res(ctx.json(mockResponse));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      await act(async () => {
        await result.current.savePreferences(mockUpdatedPrefs);
      });

      await waitFor(() => {
        expect(result.current.preferences?.default_tier).toBe('Heavy');
      });
    });

    test('returns true on success, false on failure', async () => {
      overrideHandler(
        rest.post('/api/v1/cognitive-tier/preferences/default', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      let success;
      await act(async () => {
        success = await result.current.savePreferences({ default_tier: 'Standard' });
      });

      expect(success).toBe(false);
    });

    test('sets saving state correctly', async () => {
      const mockResponse = {
        id: 'pref-1',
        workspace_id: 'default',
        default_tier: 'Standard',
        min_tier: null,
        max_tier: null,
        monthly_budget_cents: null,
        max_cost_per_request_cents: null,
        enable_cache_aware_routing: false,
        enable_auto_escalation: false,
        enable_minimax_fallback: false,
        preferred_providers: [],
      };

      overrideHandler(
        rest.post('/api/v1/cognitive-tier/preferences/default', (req, res, ctx) => {
          return res(ctx.json(mockResponse));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      await act(async () => {
        const savePromise = result.current.savePreferences({ default_tier: 'Standard' });
        await savePromise;
      });

      expect(result.current.saving).toBe(false);
    });
  });

  describe('3. Estimate Cost Tests', () => {
    test('sends request with prompt and optional tokens', async () => {
      const mockEstimates = [
        {
          tier: 'Micro',
          estimated_cost_usd: 0.0001,
          models_in_tier: ['gpt-4o-mini'],
        },
      ];

      overrideHandler(
        rest.get('/api/v1/cognitive-tier/estimate-cost', (req, res, ctx) => {
          const prompt = req.url.searchParams.get('prompt');
          const tokens = req.url.searchParams.get('estimated_tokens');

          expect(prompt).toBe('Test prompt');
          expect(tokens).toBe('1000');

          return res(ctx.json(mockEstimates));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      await act(async () => {
        await result.current.estimateCost('Test prompt', 1000);
      });
    });

    test('returns cost estimates array', async () => {
      const mockEstimates = [
        {
          tier: 'Micro',
          estimated_cost_usd: 0.0001,
          models_in_tier: ['gpt-4o-mini'],
        },
        {
          tier: 'Standard',
          estimated_cost_usd: 0.001,
          models_in_tier: ['claude-3-haiku', 'gpt-4o'],
        },
      ];

      overrideHandler(
        rest.get('/api/v1/cognitive-tier/estimate-cost', (req, res, ctx) => {
          return res(ctx.json(mockEstimates));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      let estimates;
      await act(async () => {
        estimates = await result.current.estimateCost('Test');
      });

      expect(estimates).toEqual(mockEstimates);
      expect(estimates).toHaveLength(2);
    });

    test('handles missing/invalid parameters', async () => {
      overrideHandler(
        rest.get('/api/v1/cognitive-tier/estimate-cost', (req, res, ctx) => {
          return res(ctx.json([]));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      let estimates;
      await act(async () => {
        estimates = await result.current.estimateCost('', undefined);
      });

      expect(estimates).toEqual([]);
    });

    test('returns empty array on error', async () => {
      overrideHandler(
        rest.get('/api/v1/cognitive-tier/estimate-cost', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      let estimates;
      await act(async () => {
        estimates = await result.current.estimateCost('Test');
      });

      expect(estimates).toEqual([]);
    });
  });

  describe('4. Compare Tiers Tests', () => {
    test('fetches tier comparisons', async () => {
      const mockComparisons = [
        {
          tier: 'Micro',
          quality_range: '1-50',
          cost_range: '$0.0001-$0.001',
          example_models: ['gpt-4o-mini', 'claude-3-haiku'],
          supports_cache: true,
        },
        {
          tier: 'Standard',
          quality_range: '50-70',
          cost_range: '$0.001-$0.01',
          example_models: ['claude-3.5-sonnet', 'gpt-4o'],
          supports_cache: true,
        },
      ];

      overrideHandler(
        rest.get('/api/v1/cognitive-tier/compare-tiers', (req, res, ctx) => {
          return res(ctx.json(mockComparisons));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      let comparisons;
      await act(async () => {
        comparisons = await result.current.compareTiers();
      });

      expect(comparisons).toEqual(mockComparisons);
    });

    test('returns tier comparison array', async () => {
      const mockComparisons = [
        {
          tier: 'Heavy',
          quality_range: '70-85',
          cost_range: '$0.01-$0.05',
          example_models: ['claude-3-opus', 'gpt-4-turbo'],
          supports_cache: true,
        },
      ];

      overrideHandler(
        rest.get('/api/v1/cognitive-tier/compare-tiers', (req, res, ctx) => {
          return res(ctx.json(mockComparisons));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      let comparisons;
      await act(async () => {
        comparisons = await result.current.compareTiers();
      });

      expect(Array.isArray(comparisons)).toBe(true);
      expect(comparisons).toHaveLength(1);
    });

    test('handles API errors', async () => {
      overrideHandler(
        rest.get('/api/v1/cognitive-tier/compare-tiers', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      let comparisons;
      await act(async () => {
        comparisons = await result.current.compareTiers();
      });

      expect(comparisons).toEqual([]);
    });
  });

  describe('5. State Management Tests', () => {
    test('initial loading state is true', () => {
      const { result } = renderHook(() => useCognitiveTier());

      expect(result.current.loading).toBe(true);
    });

    test('loading becomes false after fetch', async () => {
      const { result } = renderHook(() => useCognitiveTier());

      expect(result.current.loading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
    });

    test('saving state transitions correctly', async () => {
      const mockResponse = {
        id: 'pref-1',
        workspace_id: 'default',
        default_tier: 'Standard',
        min_tier: null,
        max_tier: null,
        monthly_budget_cents: null,
        max_cost_per_request_cents: null,
        enable_cache_aware_routing: false,
        enable_auto_escalation: false,
        enable_minimax_fallback: false,
        preferred_providers: [],
      };

      overrideHandler(
        rest.post('/api/v1/cognitive-tier/preferences/default', (req, res, ctx) => {
          return res(ctx.json(mockResponse));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      expect(result.current.saving).toBe(false);

      await act(async () => {
        await result.current.savePreferences({ default_tier: 'Standard' });
      });

      expect(result.current.saving).toBe(false);
    });

    test('exposes fetchPreferences function', () => {
      const { result } = renderHook(() => useCognitiveTier());

      expect(typeof result.current.fetchPreferences).toBe('function');
    });

    test('fetchPreferences can be called manually', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/v1/cognitive-tier/preferences/default', (req, res, ctx) => {
          fetchCount++;
          return res(ctx.json(mockPreferences));
        })
      );

      const { result } = renderHook(() => useCognitiveTier());

      // Initial fetch on mount
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      await act(async () => {
        await result.current.fetchPreferences();
      });

      // Should be 2 after manual call
      expect(fetchCount).toBe(2);
    });
  });
});
