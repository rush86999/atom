import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { FileCheck, AlertCircle, CheckCircle2, XCircle, Copy, Download } from "lucide-react";
import { jitVerificationAPI } from "@/lib/api-admin";
import { CitationInput } from "./CitationInput";
import { VerificationResults } from "./VerificationResults";
import type { CitationVerificationResult } from "@/types/jit-verification";

/**
 * Citation Verification Panel
 *
 * Provides manual citation verification functionality with:
 * - Bulk citation input (one per line or comma-separated)
 * - Force refresh toggle for bypassing cache
 * - Status-based filtering (all/verified/failed)
 * - Export and copy functionality
 */
export const CitationVerificationPanel: React.FC = () => {
  const [citations, setCitations] = useState<string>("");
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [verifying, setVerifying] = useState<boolean>(false);
  const [results, setResults] = useState<CitationVerificationResult[] | null>(null);
  const [filter, setFilter] = useState<"all" | "verified" | "failed">("all");
  const { toast } = useToast();

  // Handle citation verification
  const handleVerify = async () => {
    // Parse citations from input
    const citationList = parseCitations(citations);

    if (citationList.length === 0) {
      toast({
        title: "No citations to verify",
        description: "Please enter at least one citation URL",
        variant: "destructive",
      });
      return;
    }

    setVerifying(true);

    try {
      const response = await jitVerificationAPI.verifyCitations({
        citations: citationList,
        force_refresh: forceRefresh,
      });

      setResults(response.data.results);

      toast({
        title: "Verification complete",
        description: `Verified ${response.data.verified_count} of ${response.data.total_count} citations in ${response.data.duration_seconds.toFixed(2)}s`,
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

  // Parse citations from input text
  const parseCitations = (text: string): string[] => {
    return text
      .split(/[\n,]+/)
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
  };

  // Filter results based on selected filter
  const filteredResults = React.useMemo(() => {
    if (!results) return [];

    if (filter === "all") return results;

    return results.filter((r) => {
      if (filter === "verified") return r.exists;
      if (filter === "failed") return !r.exists;
      return true;
    });
  }, [results, filter]);

  // Get summary statistics
  const stats = React.useMemo(() => {
    if (!results) return { total: 0, verified: 0, failed: 0 };

    return {
      total: results.length,
      verified: results.filter((r) => r.exists).length,
      failed: results.filter((r) => !r.exists).length,
    };
  }, [results]);

  // Copy results to clipboard
  const handleCopyResults = () => {
    if (!results) return;

    const text = results
      .map((r) => `${r.citation}: ${r.exists ? "✅ EXISTS" : "❌ MISSING"}`)
      .join("\n");

    navigator.clipboard.writeText(text);

    toast({
      title: "Copied to clipboard",
      description: "Results have been copied to your clipboard",
    });
  };

  // Export results as JSON
  const handleExportResults = () => {
    if (!results) return;

    const data = {
      exported_at: new Date().toISOString(),
      total_count: results.length,
      verified_count: stats.verified,
      failed_count: stats.failed,
      results,
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `citation-verification-${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);

    toast({
      title: "Exported",
      description: "Results have been exported as JSON",
    });
  };

  // Clear results
  const handleClearResults = () => {
    setResults(null);
    setFilter("all");
  };

  return (
    <div className="space-y-6">
      {/* Input Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <FileCheck className="h-5 w-5 mr-2" />
            Verify Citations
          </CardTitle>
          <CardDescription>
            Manually verify business fact citations against R2/S3 storage
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CitationInput
            value={citations}
            onChange={setCitations}
            forceRefresh={forceRefresh}
            onForceRefreshChange={setForceRefresh}
            onVerify={handleVerify}
            verifying={verifying}
          />
        </CardContent>
      </Card>

      {/* Results Section */}
      {results && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total</p>
                    <p className="text-2xl font-bold">{stats.total}</p>
                  </div>
                  <AlertCircle className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Verified</p>
                    <p className="text-2xl font-bold text-green-600">{stats.verified}</p>
                  </div>
                  <CheckCircle2 className="h-8 w-8 text-green-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Failed</p>
                    <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
                  </div>
                  <XCircle className="h-8 w-8 text-red-600" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleCopyResults}>
                <Copy className="h-4 w-4 mr-2" />
                Copy Results
              </Button>
              <Button variant="outline" size="sm" onClick={handleExportResults}>
                <Download className="h-4 w-4 mr-2" />
                Export JSON
              </Button>
            </div>
            <Button variant="ghost" size="sm" onClick={handleClearResults}>
              Clear Results
            </Button>
          </div>

          {/* Results with Filter Tabs */}
          <Card>
            <CardHeader>
              <CardTitle>Verification Results</CardTitle>
              <CardDescription>
                {stats.verified} of {stats.total} citations verified successfully
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs value={filter} onValueChange={(v) => setFilter(v as any)}>
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="all">
                    All ({stats.total})
                  </TabsTrigger>
                  <TabsTrigger value="verified">
                    Verified ({stats.verified})
                  </TabsTrigger>
                  <TabsTrigger value="failed">
                    Failed ({stats.failed})
                  </TabsTrigger>
                </TabsList>

                <TabsContent value={filter} className="mt-4">
                  <VerificationResults results={filteredResults} />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </>
      )}

      {/* Empty State */}
      {!results && citations.length === 0 && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center text-muted-foreground">
              <FileCheck className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium mb-2">No citations entered</p>
              <p className="text-sm">
                Enter citation URLs above (one per line or comma-separated) to verify their existence
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
