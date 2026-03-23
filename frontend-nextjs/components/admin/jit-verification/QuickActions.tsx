import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Play,
  Square,
  Database,
  Zap,
  Loader2,
} from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { jitVerificationAPI } from "@/lib/api-admin";

interface QuickActionsProps {
  isWorkerRunning: boolean;
  onUpdate: () => void;
}

/**
 * Quick Actions Component
 *
 * Provides quick action buttons for common admin operations.
 */
export const QuickActions: React.FC<QuickActionsProps> = ({
  isWorkerRunning,
  onUpdate,
}) => {
  const { toast } = useToast();
  const [loading, setLoading] = useState<string | null>(null);

  const handleStartWorker = async () => {
    setLoading("start");
    try {
      const response = await jitVerificationAPI.startWorker();
      toast({
        title: "Worker started",
        description: "JIT verification worker is now running",
      });
      onUpdate();
    } catch (error: any) {
      toast({
        title: "Failed to start worker",
        description: error.userMessage || "An error occurred",
        variant: "destructive",
      });
    } finally {
      setLoading(null);
    }
  };

  const handleStopWorker = async () => {
    setLoading("stop");
    try {
      const response = await jitVerificationAPI.stopWorker();
      toast({
        title: "Worker stopped",
        description: "JIT verification worker has been stopped",
      });
      onUpdate();
    } catch (error: any) {
      toast({
        title: "Failed to stop worker",
        description: error.userMessage || "An error occurred",
        variant: "destructive",
      });
    } finally {
      setLoading(null);
    }
  };

  const handleClearCache = async () => {
    setLoading("clear");
    try {
      const response = await jitVerificationAPI.clearCache();
      toast({
        title: "Cache cleared",
        description: "All JIT verification caches have been cleared",
      });
      onUpdate();
    } catch (error: any) {
      toast({
        title: "Failed to clear cache",
        description: error.userMessage || "An error occurred",
        variant: "destructive",
      });
    } finally {
      setLoading(null);
    }
  };

  const handleWarmCache = async () => {
    setLoading("warm");
    try {
      const response = await jitVerificationAPI.warmCache(100);
      toast({
        title: "Cache warmed",
        description: `Warmed ${response.data.citations_verified} citations in ${response.data.duration_seconds.toFixed(2)}s`,
      });
      onUpdate();
    } catch (error: any) {
      toast({
        title: "Failed to warm cache",
        description: error.userMessage || "An error occurred",
        variant: "destructive",
      });
    } finally {
      setLoading(null);
    }
  };

  const isLoading = (action: string): boolean => {
    return loading === action;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quick Actions</CardTitle>
        <CardDescription>
          Control the JIT verification system
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-3">
          {/* Start/Stop Worker */}
          {isWorkerRunning ? (
            <Button
              variant="destructive"
              onClick={handleStopWorker}
              disabled={isLoading("stop")}
            >
              {isLoading("stop") ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Square className="h-4 w-4 mr-2" />
              )}
              Stop Worker
            </Button>
          ) : (
            <Button
              onClick={handleStartWorker}
              disabled={isLoading("start")}
            >
              {isLoading("start") ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Start Worker
            </Button>
          )}

          {/* Clear Cache */}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="outline"
                disabled={isLoading("clear")}
              >
                {isLoading("clear") ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Database className="h-4 w-4 mr-2" />
                )}
                Clear Cache
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Clear JIT Verification Cache?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will clear all cached verification results (L1 memory cache and L2 Redis cache).
                  The system will need to re-verify citations on next access, which may temporarily slow down operations.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleClearCache}>
                  Clear Cache
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {/* Warm Cache */}
          <Button
            variant="outline"
            onClick={handleWarmCache}
            disabled={isLoading("warm")}
          >
            {isLoading("warm") ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Zap className="h-4 w-4 mr-2" />
            )}
            Warm Cache
          </Button>
        </div>

        {/* Action Description */}
        <div className="mt-4 p-4 bg-secondary/20 rounded-lg space-y-2 text-sm">
          <div className="flex items-start gap-2">
            <Play className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium">Start Worker</p>
              <p className="text-muted-foreground">
                Begin background verification of all citations
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <Square className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium">Stop Worker</p>
              <p className="text-muted-foreground">
                Halt background verification process
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <Database className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium">Clear Cache</p>
              <p className="text-muted-foreground">
                Remove all cached results (requires re-verification)
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <Zap className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium">Warm Cache</p>
              <p className="text-muted-foreground">
                Pre-verify top 100 citations for faster access
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
