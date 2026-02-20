import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowRight, ArrowLeft, Check } from "lucide-react";
import { TierSelector } from "./TierSelector";
import { CostCalculator } from "./CostCalculator";
import { useCognitiveTier } from "@/hooks/useCognitiveTier";
import { toast } from "sonner";

type Step = "welcome" | "select" | "budget" | "review" | "complete";

export function CognitiveTierWizard() {
  const [step, setStep] = useState<Step>("welcome");
  const [selectedTier, setSelectedTier] = useState("standard");
  const [monthlyBudget, setMonthlyBudget] = useState<number | null>(null);
  const { savePreferences, saving } = useCognitiveTier();

  const steps: Step[] = ["welcome", "select", "budget", "review", "complete"];
  const currentStepIndex = steps.indexOf(step);

  const handleNext = () => {
    if (currentStepIndex < steps.length - 1) {
      setStep(steps[currentStepIndex + 1]);
    }
  };

  const handleBack = () => {
    if (currentStepIndex > 0) {
      setStep(steps[currentStepIndex - 1]);
    }
  };

  const handleComplete = async () => {
    const success = await savePreferences({
      default_tier: selectedTier,
      monthly_budget_cents: monthlyBudget ? monthlyBudget * 100 : null,
      enable_cache_aware_routing: true,
      enable_auto_escalation: true,
    });

    if (success) {
      setStep("complete");
      toast.success("Cognitive tier preferences saved!");
    } else {
      toast.error("Failed to save preferences");
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Progress indicator */}
      <div className="flex justify-between mb-8">
        {steps.map((s, i) => (
          <div
            key={s}
            className={`flex items-center ${
              i <= currentStepIndex ? "text-blue-500" : "text-muted-foreground"
            }`}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              i < currentStepIndex ? "bg-blue-500 text-white" : "border-2"
            }`}>
              {i < currentStepIndex ? <Check className="h-4 w-4" /> : i + 1}
            </div>
            {i < steps.length - 1 && <div className="w-16 h-0.5 bg-gray-200 mx-2" />}
          </div>
        ))}
      </div>

      {/* Step content */}
      {step === "welcome" && (
        <Card>
          <CardHeader>
            <CardTitle>Welcome to Cognitive Tier Configuration</CardTitle>
            <CardDescription>
              Choose how Atom AI routes your queries to optimize for cost and quality
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="mb-4">
              Atom uses a 5-tier cognitive system to match your queries with the most cost-effective models.
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Micro:</strong> Simple queries, fastest response</li>
              <li><strong>Standard:</strong> Everyday tasks, balanced cost</li>
              <li><strong>Versatile:</strong> Complex reasoning, better quality</li>
              <li><strong>Heavy:</strong> Advanced tasks, frontier models</li>
              <li><strong>Complex:</strong> Most demanding queries, highest quality</li>
            </ul>
          </CardContent>
        </Card>
      )}

      {step === "select" && (
        <Card>
          <CardHeader>
            <CardTitle>Select Your Default Tier</CardTitle>
            <CardDescription>
              Choose the tier that best matches your typical usage
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TierSelector selectedTier={selectedTier} onTierSelect={setSelectedTier} />
          </CardContent>
        </Card>
      )}

      {step === "budget" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Set Budget Limits (Optional)</CardTitle>
              <CardDescription>
                Control your monthly spending
              </CardDescription>
            </CardHeader>
            <CardContent>
              <label className="block mb-2 text-sm font-medium">
                Monthly Budget (USD)
              </label>
              <input
                type="number"
                className="w-full p-2 border rounded"
                placeholder="No limit"
                value={monthlyBudget || ""}
                onChange={(e) => setMonthlyBudget(e.target.value ? parseFloat(e.target.value) : null)}
              />
              <p className="text-xs text-muted-foreground mt-2">
                Leave empty for no budget limit
              </p>
            </CardContent>
          </Card>

          <CostCalculator selectedTier={selectedTier} />
        </div>
      )}

      {step === "review" && (
        <Card>
          <CardHeader>
            <CardTitle>Review Your Selection</CardTitle>
            <CardDescription>
              Confirm your cognitive tier preferences
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <span className="font-medium">Default Tier:</span> {selectedTier}
              </div>
              <div>
                <span className="font-medium">Monthly Budget:</span> {monthlyBudget ? `$${monthlyBudget}` : "No limit"}
              </div>
              <div>
                <span className="font-medium">Cache-Aware Routing:</span> Enabled
              </div>
              <div>
                <span className="font-medium">Auto-Escalation:</span> Enabled
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {step === "complete" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-center">Configuration Complete!</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-center text-muted-foreground">
              Your cognitive tier preferences have been saved. Atom will now route your queries
              according to your selected tier and budget limits.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Navigation buttons */}
      {step !== "complete" && (
        <div className="flex justify-between mt-6">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={currentStepIndex === 0}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>

          {step === "review" ? (
            <Button onClick={handleComplete} disabled={saving}>
              Complete Setup
              {saving && <span className="ml-2 animate-spin">⏳</span>}
            </Button>
          ) : (
            <Button onClick={handleNext}>
              {step === "welcome" ? "Get Started" : "Next"}
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
