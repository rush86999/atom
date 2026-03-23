import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/components/ui/use-toast";
import { TrendingUp, ExternalLink, BarChart3 } from "lucide-react";
import { jitVerificationAPI } from "@/lib/api-admin";
import { CitationDetail } from "./CitationDetail";
import type { TopCitation } from "@/types/jit-verification";

/**
 * Top Citations Component
 *
 * Displays most frequently accessed citations with metrics.
 */
export const TopCitations: React.FC = () => {
  const [topCitations, setTopCitations] = useState<TopCitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCitation, setSelectedCitation] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    fetchTopCitations();
  }, []);

  const fetchTopCitations = async () => {
    try {
      const response = await jitVerificationAPI.getTopCitations(20);
      setTopCitations(response.data.top_citations);
    } catch (error: any) {
      console.error("Failed to fetch top citations:", error);
      toast({
        title: "Error loading top citations",
        description: error.userMessage || "Failed to load top citations",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  // Get max access count for progress bar calculation
  const maxAccessCount = React.useMemo(() => {
    if (topCitations.length === 0) return 0;
    return Math.max(...topCitations.map((c) => c.access_count));
  }, [topCitations]);

  // Calculate total accesses
  const totalAccesses = React.useMemo(() => {
    return topCitations.reduce((sum, c) => sum + c.access_count, 0);
  }, [topCitations]);

  if (loading) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="flex items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center">
                <TrendingUp className="h-5 w-5 mr-2" />
                Top Citations by Access Frequency
              </CardTitle>
              <CardDescription>
                Most frequently verified citations in the system
              </CardDescription>
            </div>
            <Badge variant="secondary" className="text-xs">
              {topCitations.length} citations
            </Badge>
          </div>
        </CardHeader>
      </Card>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Citations</p>
                <p className="text-2xl font-bold">{topCitations.length}</p>
              </div>
              <BarChart3 className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Accesses</p>
                <p className="text-2xl font-bold">{totalAccesses.toLocaleString()}</p>
              </div>
              <TrendingUp className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Most Accessed</p>
                <p className="text-2xl font-bold text-green-600">
                  {topCitations[0]?.access_count || 0}
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Citations List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Access Leaderboard</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[500px]">
            {topCitations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <BarChart3 className="h-12 w-12 mb-4 opacity-50" />
                <p className="text-lg font-medium mb-2">No citation data</p>
                <p className="text-sm">
                  Citation access data will appear once verification runs
                </p>
              </div>
            ) : (
              <div className="divide-y">
                {topCitations.map((item, idx) => {
                  const percentage = maxAccessCount > 0 ? (item.access_count / maxAccessCount) * 100 : 0;

                  return (
                    <div
                      key={idx}
                      className="flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors cursor-pointer"
                      onClick={() => setSelectedCitation(item.citation)}
                    >
                      {/* Rank */}
                      <div className="flex-shrink-0 w-8">
                        <div
                          className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${
                            idx === 0
                              ? "bg-yellow-500 text-white"
                              : idx === 1
                              ? "bg-gray-400 text-white"
                              : idx === 2
                              ? "bg-orange-600 text-white"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {idx + 1}
                        </div>
                      </div>

                      {/* Citation URL */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <a
                            href={item.citation}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-mono text-sm hover:text-primary underline truncate"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {item.citation}
                          </a>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-5 px-1 flex-shrink-0"
                            asChild
                          >
                            <a
                              href={item.citation}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          </Button>
                        </div>

                        {/* Progress Bar */}
                        <div className="flex items-center gap-2">
                          <Progress value={percentage} className="flex-1 h-2" />
                          <span className="text-xs text-muted-foreground w-16 text-right">
                            {item.access_count}x
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Citation Detail Dialog */}
      {selectedCitation && (
        <CitationDetail
          citation={selectedCitation}
          accessCount={topCitations.find((c) => c.citation === selectedCitation)?.access_count || 0}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </div>
  );
};
