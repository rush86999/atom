import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { useCognitiveTier } from "@/hooks/useCognitiveTier";

interface CostCalculatorProps {
  selectedTier: string;
}

export function CostCalculator({ selectedTier }: CostCalculatorProps) {
  const { estimateCost } = useCognitiveTier();
  const [prompt, setPrompt] = useState("");
  const [requestsPerDay, setRequestsPerDay] = useState([100]);
  const [estimatedCost, setEstimatedCost] = useState<number | null>(null);

  useEffect(() => {
    const calculateCost = async () => {
      if (!prompt) {
        setEstimatedCost(null);
        return;
      }
      const costs = await estimateCost(prompt);
      const tierCost = costs.find(c => c.tier === selectedTier);
      if (tierCost) {
        const monthlyRequests = requestsPerDay[0] * 30;
        const costPerRequest = tierCost.estimated_cost_usd;
        setEstimatedCost(costPerRequest * monthlyRequests);
      }
    };
    calculateCost();
  }, [prompt, requestsPerDay, selectedTier, estimateCost]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cost Calculator</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Sample Prompt</Label>
          <Input
            placeholder="Enter a sample query..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label>Requests Per Day: {requestsPerDay[0]}</Label>
          <Slider
            value={requestsPerDay}
            onValueChange={setRequestsPerDay}
            min={10}
            max={1000}
            step={10}
          />
        </div>

        {estimatedCost !== null && (
          <div className="p-4 bg-blue-50 rounded-lg">
            <div className="text-2xl font-bold">
              ${estimatedCost.toFixed(2)}
            </div>
            <div className="text-sm text-muted-foreground">Estimated monthly cost</div>
          </div>
        )}

        <div className="text-xs text-muted-foreground">
          * Estimates based on {selectedTier} tier. Actual costs may vary.
        </div>
      </CardContent>
    </Card>
  );
}
