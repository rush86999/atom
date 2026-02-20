import React, { useState, useEffect } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check } from "lucide-react";
import { useCognitiveTier, TierComparison } from "@/hooks/useCognitiveTier";

interface TierSelectorProps {
  selectedTier: string;
  onTierSelect: (tier: string) => void;
}

const TIER_DESCRIPTIONS = {
  micro: {
    name: "Micro",
    description: "Fast, efficient responses for simple queries",
    use_cases: ["Quick questions", "Summaries", "Translations"],
    color: "bg-green-500",
  },
  standard: {
    name: "Standard",
    description: "Balanced quality and cost for everyday tasks",
    use_cases: ["Explanations", "Analysis", "Content creation"],
    color: "bg-blue-500",
  },
  versatile: {
    name: "Versatile",
    description: "Multi-step reasoning with good quality",
    use_cases: ["Problem solving", "Planning", "Optimization"],
    color: "bg-purple-500",
  },
  heavy: {
    name: "Heavy",
    description: "Complex tasks requiring deep reasoning",
    use_cases: ["Architecture", "Security audits", "Research"],
    color: "bg-orange-500",
  },
  complex: {
    name: "Complex",
    description: "Frontier models for the most demanding tasks",
    use_cases: ["Math proofs", "Code generation", "Advanced analysis"],
    color: "bg-red-500",
  },
};

export function TierSelector({ selectedTier, onTierSelect }: TierSelectorProps) {
  const { compareTiers } = useCognitiveTier();
  const [comparisons, setComparisons] = useState<TierComparison[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    compareTiers().then(data => {
      setComparisons(data);
      setLoading(false);
    });
  }, [compareTiers]);

  const getCostBadge = (tier: string) => {
    const comp = comparisons.find(c => c.tier === tier);
    if (!comp) return <Badge variant="outline">Loading...</Badge>;
    const cost = parseFloat(comp.cost_range);
    if (cost < 0.5) return <Badge className="bg-green-100 text-green-800">$</Badge>;
    if (cost < 5) return <Badge className="bg-blue-100 text-blue-800">$$</Badge>;
    return <Badge className="bg-orange-100 text-orange-800">$$$</Badge>;
  };

  const getQualityBadge = (tier: string) => {
    const comp = comparisons.find(c => c.tier === tier);
    if (!comp) return <Badge variant="outline">Loading...</Badge>;
    const quality = parseInt(comp.quality_range);
    if (quality < 80) return <Badge variant="secondary">Basic</Badge>;
    if (quality < 90) return <Badge className="bg-blue-100 text-blue-800">Good</Badge>;
    return <Badge className="bg-purple-100 text-purple-800">Excellent</Badge>;
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
      {Object.entries(TIER_DESCRIPTIONS).map(([key, tier]) => (
        <Card
          key={key}
          className={`cursor-pointer transition-all ${
            selectedTier === key ? "ring-2 ring-blue-500" : "hover:shadow-md"
          }`}
          onClick={() => onTierSelect(key)}
        >
          <CardContent className="p-4">
            <div className="flex justify-between items-start mb-2">
              <div className={`w-3 h-3 rounded-full ${tier.color}`} />
              {selectedTier === key && <Check className="h-5 w-5 text-blue-500" />}
            </div>
            <h3 className="font-semibold">{tier.name}</h3>
            <p className="text-sm text-muted-foreground mb-3">{tier.description}</p>
            <div className="space-y-1">
              {getCostBadge(key)}
              {getQualityBadge(key)}
            </div>
            <ul className="text-xs text-muted-foreground mt-2 space-y-1">
              {tier.use_cases.map(use_case => (
                <li key={use_case}>• {use_case}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
