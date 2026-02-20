import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { useCognitiveTier } from "@/hooks/useCognitiveTier";

const TIERS = [
  { value: "micro", label: "Micro", description: "Simple queries <100 tokens" },
  { value: "standard", label: "Standard", description: "Moderate complexity 100-500 tokens" },
  { value: "versatile", label: "Versatile", description: "Multi-step reasoning 500-2k tokens" },
  { value: "heavy", label: "Heavy", description: "Complex tasks 2k-5k tokens" },
  { value: "complex", label: "Complex", description: "Frontier reasoning >5k tokens" },
];

export function CognitiveTierSettings() {
  const { preferences, loading, saving, savePreferences, estimateCost } = useCognitiveTier();
  const [localPrefs, setLocalPrefs] = useState(preferences);
  const [estimatedCost, setEstimatedCost] = useState<number | null>(null);

  useEffect(() => {
    setLocalPrefs(preferences);
  }, [preferences]);

  const handleSave = async (key: string, value: any) => {
    const updated = { ...localPrefs, [key]: value };
    setLocalPrefs(updated);
    const success = await savePreferences(updated);
    if (success) {
      toast.success("Tier preference saved");
    } else {
      toast.error("Failed to save preference");
    }
  };

  const handleEstimateCost = async () => {
    const costs = await estimateCost("What is the capital of France?", 20);
    if (costs.length > 0) {
      const tier = localPrefs?.default_tier || "standard";
      const cost = costs.find(c => c.tier === tier);
      if (cost) {
        setEstimatedCost(cost.estimated_cost_usd * 1000000); // Per 1M tokens
      }
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center p-10">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Default Tier Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Default Cognitive Tier</CardTitle>
          <CardDescription>Select your preferred tier for AI queries</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Default Tier</Label>
              <div className="text-sm text-muted-foreground">
                Higher tiers = better quality but higher cost
              </div>
            </div>
            <Select
              value={localPrefs?.default_tier || "standard"}
              onValueChange={(val) => handleSave("default_tier", val)}
            >
              <SelectTrigger className="w-[200px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIERS.map((tier) => (
                  <SelectItem key={tier.value} value={tier.value}>
                    {tier.label} - {tier.description}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Cost Estimate Button */}
          <Button onClick={handleEstimateCost} variant="outline" className="mt-4">
            Estimate Cost (Per 1M Tokens)
          </Button>
          {estimatedCost !== null && (
            <div className="text-sm">
              Estimated: ${estimatedCost.toFixed(2)} per 1M tokens
            </div>
          )}
        </CardContent>
      </Card>

      {/* Feature Flags */}
      <Card>
        <CardHeader>
          <CardTitle>Smart Routing Features</CardTitle>
          <CardDescription>Enable cost optimization features</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Cache-Aware Routing</Label>
              <div className="text-sm text-muted-foreground">
                Use prompt caching to reduce costs (up to 90% savings)
              </div>
            </div>
            <Switch
              checked={localPrefs?.enable_cache_aware_routing ?? true}
              onCheckedChange={(val) => handleSave("enable_cache_aware_routing", val)}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Auto-Escalation</Label>
              <div className="text-sm text-muted-foreground">
                Automatically upgrade tier on quality issues
              </div>
            </div>
            <Switch
              checked={localPrefs?.enable_auto_escalation ?? true}
              onCheckedChange={(val) => handleSave("enable_auto_escalation", val)}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>MiniMax Fallback</Label>
              <div className="text-sm text-muted-foreground">
                Use MiniMax M2.5 for cost-effective standard tier queries
              </div>
            </div>
            <Switch
              checked={localPrefs?.enable_minimax_fallback ?? true}
              onCheckedChange={(val) => handleSave("enable_minimax_fallback", val)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Budget Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Cost Controls</CardTitle>
          <CardDescription>Set limits to control spending</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Monthly Budget (USD)</Label>
            <Input
              type="number"
              placeholder="No limit"
              value={localPrefs?.monthly_budget_cents ? localPrefs.monthly_budget_cents / 100 : ""}
              onChange={(e) => handleSave("monthly_budget_cents", e.target.value ? parseFloat(e.target.value) * 100 : null)}
            />
          </div>

          <div className="space-y-2">
            <Label>Max Cost Per Request (USD)</Label>
            <Input
              type="number"
              placeholder="No limit"
              value={localPrefs?.max_cost_per_request_cents ? localPrefs.max_cost_per_request_cents / 100 : ""}
              onChange={(e) => handleSave("max_cost_per_request_cents", e.target.value ? parseFloat(e.target.value) * 100 : null)}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
