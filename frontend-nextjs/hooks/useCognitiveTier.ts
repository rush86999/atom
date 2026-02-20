import { useState, useEffect } from 'react';

export interface TierPreference {
  id: string;
  workspace_id: string;
  default_tier: string;
  min_tier: string | null;
  max_tier: string | null;
  monthly_budget_cents: number | null;
  max_cost_per_request_cents: number | null;
  enable_cache_aware_routing: boolean;
  enable_auto_escalation: boolean;
  enable_minimax_fallback: boolean;
  preferred_providers: string[];
}

export interface CostEstimate {
  tier: string;
  estimated_cost_usd: number;
  models_in_tier: string[];
}

export interface TierComparison {
  tier: string;
  quality_range: string;
  cost_range: string;
  example_models: string[];
  supports_cache: boolean;
}

const workspaceId = "default"; // TODO: Get from context

export function useCognitiveTier() {
  const [preferences, setPreferences] = useState<TierPreference | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Fetch preferences
  const fetchPreferences = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/cognitive-tier/preferences/${workspaceId}`);
      if (res.ok) {
        const data = await res.json();
        setPreferences(data);
      }
    } catch (error) {
      console.error("Failed to fetch tier preferences:", error);
    } finally {
      setLoading(false);
    }
  };

  // Save preferences
  const savePreferences = async (prefs: Partial<TierPreference>) => {
    setSaving(true);
    try {
      const res = await fetch(`/api/v1/cognitive-tier/preferences/${workspaceId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_id: workspaceId, ...prefs }),
      });
      if (res.ok) {
        const data = await res.json();
        setPreferences(data);
        return true;
      }
    } catch (error) {
      console.error("Failed to save tier preferences:", error);
    } finally {
      setSaving(false);
    }
    return false;
  };

  // Estimate cost
  const estimateCost = async (prompt: string, estimatedTokens?: number): Promise<CostEstimate[]> => {
    try {
      const params = new URLSearchParams({ prompt });
      if (estimatedTokens) params.append("estimated_tokens", estimatedTokens.toString());
      const res = await fetch(`/api/v1/cognitive-tier/estimate-cost?${params}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (error) {
      console.error("Failed to estimate cost:", error);
    }
    return [];
  };

  // Compare tiers
  const compareTiers = async (): Promise<TierComparison[]> => {
    try {
      const res = await fetch("/api/v1/cognitive-tier/compare-tiers");
      if (res.ok) {
        return await res.json();
      }
    } catch (error) {
      console.error("Failed to compare tiers:", error);
    }
    return [];
  };

  useEffect(() => {
    fetchPreferences();
  }, []);

  return {
    preferences,
    loading,
    saving,
    fetchPreferences,
    savePreferences,
    estimateCost,
    compareTiers,
  };
}
