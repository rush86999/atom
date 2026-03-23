import React from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { CheckCircle2, XCircle, Clock, FileText, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { CitationVerificationResult } from "@/types/jit-verification";

interface VerificationResultsProps {
  results: CitationVerificationResult[];
}

/**
 * Verification Results Component
 *
 * Displays citation verification results with:
 * - Status icons (exists/missing)
 * - Citation URL with link
 * - Metadata (size, last modified, checked at)
 * - Color-coded status badges
 */
export const VerificationResults: React.FC<VerificationResultsProps> = ({
  results,
}) => {
  if (results.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p className="text-lg">No results to display</p>
        <p className="text-sm mt-2">Try changing the filter or verify more citations</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {results.map((result, idx) => (
        <ResultCard key={idx} result={result} />
      ))}
    </div>
  );
};

interface ResultCardProps {
  result: CitationVerificationResult;
}

const ResultCard: React.FC<ResultCardProps> = ({ result }) => {
  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return "Unknown size";

    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (dateStr?: string): string => {
    if (!dateStr) return "Unknown";

    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  return (
    <Card className={`p-4 ${result.exists ? "border-green-500/30 bg-green-500/5" : "border-red-500/30 bg-red-500/5"}`}>
      <div className="flex items-start gap-3">
        {/* Status Icon */}
        <div className="mt-1">
          {result.exists ? (
            <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
          ) : (
            <XCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-2">
          {/* Citation URL */}
          <div className="flex items-start gap-2">
            <a
              href={result.citation}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-xs hover:text-primary underline flex-1 break-all"
            >
              {result.citation}
            </a>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 flex-shrink-0"
              asChild
            >
              <a
                href={result.citation}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            </Button>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-2">
            <Badge variant={result.exists ? "default" : "destructive"} className="text-xs">
              {result.exists ? "EXISTS" : "MISSING"}
            </Badge>
            {!result.exists && (
              <Badge variant="outline" className="text-xs text-muted-foreground">
                File not found in storage
              </Badge>
            )}
          </div>

          {/* Metadata */}
          {result.exists && (result.size || result.last_modified) && (
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              {result.size && (
                <div className="flex items-center gap-1">
                  <FileText className="h-3 w-3" />
                  <span>{formatFileSize(result.size)}</span>
                </div>
              )}
              {result.last_modified && (
                <div className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  <span>Modified {formatDate(result.last_modified)}</span>
                </div>
              )}
            </div>
          )}

          {/* Checked At */}
          <div className="text-xs text-muted-foreground">
            Checked {formatDate(result.checked_at)}
          </div>
        </div>
      </div>
    </Card>
  );
};
