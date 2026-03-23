import React, { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ExternalLink, FileText, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { jitVerificationAPI } from "@/lib/api-admin";
import { VerificationStatusBadge } from "./VerificationStatusBadge";
import type { CitationVerificationResult } from "@/types/jit-verification";

interface CitationViewerProps {
  citations: string[];
  factId: string;
}

/**
 * Citation Viewer Component
 *
 * Displays all citations for a fact with verification status.
 */
export const CitationViewer: React.FC<CitationViewerProps> = ({
  citations,
  factId,
}) => {
  const [verifying, setVerifying] = useState(false);
  const [results, setResults] = useState<CitationVerificationResult[] | null>(null);
  const { toast } = useToast();

  // Verify all citations for this fact
  const handleVerify = async () => {
    setVerifying(true);

    try {
      const response = await jitVerificationAPI.verifyFactCitations(factId);
      setResults(Object.values(response.data.results));

      toast({
        title: "Verification complete",
        description: `${response.data.citation_count} citations verified`,
      });
    } catch (error: any) {
      console.error("Verification failed:", error);
      toast({
        title: "Verification failed",
        description: error.userMessage || "Failed to verify citations",
        variant: "destructive",
      });
    } finally {
      setVerifying(false);
    }
  };

  if (citations.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        No citations associated with this fact
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">
          Citations ({citations.length})
        </h4>
        <Button
          variant="outline"
          size="sm"
          onClick={handleVerify}
          disabled={verifying}
        >
          {verifying ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Verifying...
            </>
          ) : (
            <>
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Verify All
            </>
          )}
        </Button>
      </div>

      <div className="space-y-2">
        {citations.map((citation, idx) => {
          const result = results?.[idx];
          const exists = result?.exists ?? null;

          return (
            <Card
              key={idx}
              className={`p-3 ${
                exists === true
                  ? "border-green-500/30 bg-green-500/5"
                  : exists === false
                  ? "border-red-500/30 bg-red-500/5"
                  : ""
              }`}
            >
              <div className="flex items-start gap-3">
                {/* Status Icon */}
                <div className="mt-0.5">
                  {exists === true ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
                  ) : exists === false ? (
                    <XCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
                  ) : (
                    <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  )}
                </div>

                {/* Citation URL */}
                <div className="flex-1 min-w-0">
                  <a
                    href={citation}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-xs hover:text-primary underline break-all"
                  >
                    {citation}
                  </a>

                  {/* Verification Result */}
                  {result && (
                    <div className="mt-2 flex items-center gap-2">
                      <Badge
                        variant={result.exists ? "default" : "destructive"}
                        className="text-xs"
                      >
                        {result.exists ? "EXISTS" : "MISSING"}
                      </Badge>
                      {result.size && (
                        <span className="text-xs text-muted-foreground">
                          {(result.size / 1024).toFixed(1)} KB
                        </span>
                      )}
                      {result.checked_at && (
                        <span className="text-xs text-muted-foreground">
                          Checked {new Date(result.checked_at).toLocaleTimeString()}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* External Link */}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 flex-shrink-0"
                  asChild
                >
                  <a
                    href={citation}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      {!results && (
        <p className="text-xs text-muted-foreground">
          Click "Verify All" to check citation status
        </p>
      )}
    </div>
  );
};
