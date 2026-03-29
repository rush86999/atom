import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Database,
  Zap,
  Download,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { jitVerificationAPI } from "@/lib/api-admin";

/**
 * Cache Actions Component
 *
 * Provides cache management actions with dialogs and confirmations.
 */
export const CacheActions: React.FC = () => {
  const { toast } = useToast();
  const [clearLoading, setClearLoading] = useState(false);
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
  const [warmLoading, setWarmLoading] = useState(false);
  const [warmLimit, setWarmLimit] = useState(100);
  const [warmDialogOpen, setWarmDialogOpen] = useState(false);
  const [warmResult, setWarmResult] = useState<any>(null);

  const handleClearCache = async () => {
    setClearLoading(true);
    try {
      const response = await jitVerificationAPI.clearCache();
      toast({
        title: "Cache cleared",
        description: "All JIT verification caches have been cleared successfully",
      });
    } catch (error: any) {
      toast({
        title: "Failed to clear cache",
        description: error.userMessage || "An error occurred",
        variant: "destructive",
      });
    } finally {
      setClearLoading(false);
    }
  };

  const handleWarmCache = async () => {
    setWarmLoading(true);
    setWarmResult(null);

    try {
      const response = await jitVerificationAPI.warmCache(warmLimit);
      setWarmResult(response.data);

      toast({
        title: "Cache warming complete",
        description: `Warmed ${response.data.citations_verified} citations in ${response.data.duration_seconds.toFixed(2)}s`,
      });
    } catch (error: any) {
      toast({
        title: "Failed to warm cache",
        description: error.userMessage || "An error occurred",
        variant: "destructive",
      });
      setWarmDialogOpen(false);
    } finally {
      setWarmLoading(false);
    }
  };

  const exportMetrics = () => {
    // Create metrics export
    const metrics = {
      exported_at: new Date().toISOString(),
      actions: "cache_clear,warm_cache",
      description: "JIT verification cache management actions",
    };

    // Download as JSON file
    const blob = new Blob([JSON.stringify(metrics, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `jit-cache-metrics-${new Date().toISOString().split("T")[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    toast({
      title: "Metrics exported",
      description: "Cache metrics have been exported successfully",
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cache Management</CardTitle>
        <CardDescription>
          Control and optimize the JIT verification cache
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3">
          {/* Warm Cache Button */}
          <Button
            variant="default"
            disabled={warmLoading}
            onClick={() => setWarmDialogOpen(true)}
          >
            {warmLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Zap className="h-4 w-4 mr-2" />
            )}
            Warm Cache
          </Button>

          {/* Warm Cache Dialog */}
          <Dialog open={warmDialogOpen} onOpenChange={setWarmDialogOpen}>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle>Warm JIT Verification Cache</DialogTitle>
                <DialogDescription>
                  Pre-verify citations to populate cache for faster access. This improves performance for subsequent lookups.
                </DialogDescription>
              </DialogHeader>

              {!warmResult ? (
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="warm-limit">
                      Number of Facts to Warm: {warmLimit}
                    </Label>
                    <Input
                      id="warm-limit"
                      type="number"
                      min={1}
                      max={1000}
                      value={warmLimit}
                      onChange={(e) => setWarmLimit(parseInt(e.target.value))}
                      className="mt-1"
                    />
                    <p className="text-xs text-muted-foreground">
                      More facts = longer warming time, but warmer cache
                    </p>
                  </div>

                  <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                    <p className="text-sm text-blue-800">
                      <strong>What this does:</strong>
                    </p>
                    <ul className="text-xs text-blue-700 mt-2 space-y-1">
                      <li>• Fetches top {warmLimit} business facts</li>
                      <li>• Verifies all citations in those facts</li>
                      <li>• Caches results for fast access</li>
                      <li>• Typically takes 2-5 seconds</li>
                    </ul>
                  </div>
                </div>
              ) : (
                <div className="space-y-4 py-4">
                  <div className="flex items-center justify-center p-4">
                    <CheckCircle2 className="h-12 w-12 text-green-600 mr-4" />
                    <div>
                      <p className="font-semibold text-green-600">Cache Warming Complete!</p>
                      <p className="text-sm text-muted-foreground">
                        {warmResult.citations_verified} citations warmed in {warmResult.duration_seconds.toFixed(2)}s
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 p-4 bg-secondary/20 rounded-lg">
                    <div>
                      <p className="text-xs text-muted-foreground">Facts Processed</p>
                      <p className="text-2xl font-bold">{warmResult.facts_processed}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Citations Verified</p>
                      <p className="text-2xl font-bold">{warmResult.citations_verified}</p>
                    </div>
                  </div>
                </div>
              )}

              <DialogFooter>
                {!warmResult && (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => setWarmDialogOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button onClick={handleWarmCache} disabled={warmLoading}>
                      {warmLoading ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Warming...
                        </>
                      ) : (
                        "Warm Cache"
                      )}
                    </Button>
                  </>
                )}
                {warmResult && (
                  <Button onClick={() => setWarmDialogOpen(false)}>
                    Done
                  </Button>
                )}
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Clear Cache with Confirmation */}
          <Dialog open={clearDialogOpen} onOpenChange={setClearDialogOpen}>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle>Clear All JIT Verification Caches?</DialogTitle>
                <DialogDescription>
                  <strong className="text-red-600">Warning:</strong> This will clear all cached verification results from both L1 memory cache and L2 Redis cache.
                  <br /><br />
                  <strong>Impact:</strong>
                  <ul className="list-disc list-inside mt-2 space-y-1 text-sm">
                    <li>• All citations will require re-verification</li>
                    <li>• Temporary performance degradation (~200ms per citation)</li>
                    <li>• Agent decision-making may slow down</li>
                  </ul>
                  <br />
                  <strong>Recommendation:</strong> Only clear cache if you suspect stale data or need to force fresh verification.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => setClearDialogOpen(false)}>
                  Cancel
                </Button>
                <Button variant="destructive" onClick={handleClearCache} disabled={clearLoading}>
                  {clearLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Clearing...
                    </>
                  ) : (
                    "Clear Cache"
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Clear Cache Button */}
          <Button
            variant="destructive"
            disabled={clearLoading}
            onClick={() => setClearDialogOpen(true)}
          >
            {clearLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Database className="h-4 w-4 mr-2" />
            )}
            Clear All Caches
          </Button>

          {/* Export Metrics */}
          <Button
            variant="outline"
            onClick={exportMetrics}
          >
            <Download className="h-4 w-4 mr-2" />
            Export Metrics
          </Button>
        </div>

        {/* Action Information */}
        <div className="space-y-3 pt-4 border-t">
          <div className="space-y-2">
            <h4 className="text-sm font-medium">When to Use Each Action</h4>

            <div className="grid grid-cols-1 gap-3">
              <div className="flex items-start gap-3 p-3 bg-secondary/20 rounded-lg">
                <Zap className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium">Warm Cache</p>
                  <p className="text-xs text-muted-foreground">
                    Use before high-traffic periods or after deploying new business facts. Pre-loads verification results into cache.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-red-800">Clear All Caches</p>
                  <p className="text-xs text-red-700">
                    Use only when necessary. Clears all cached results and forces re-verification. Will slow down operations temporarily.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <Download className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-blue-800">Export Metrics</p>
                  <p className="text-xs text-blue-700">
                    Download cache performance metrics for analysis or reporting. Useful for monitoring and optimization.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Best Practices */}
          <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
            <p className="text-sm font-medium text-green-800 mb-2">
              ✓ Best Practices
            </p>
            <ul className="text-xs text-green-700 space-y-1">
              <li>• <strong>Warm cache</strong> during low-traffic periods</li>
              <li>• <strong>Monitor hit rates</strong> - aim for &gt;85% L1 hit rate</li>

              <li>• <strong>Clear cache</strong> only when stale data is suspected</li>
              <li>• <strong>Export metrics</strong> weekly for performance tracking</li>
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
