import React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, TrendingUp, Clock, FileText } from "lucide-react";

interface CitationDetailProps {
  citation: string;
  accessCount: number;
  onClose: () => void;
}

/**
 * Citation Detail Dialog
 *
 * Shows detailed information about a specific citation.
 */
export const CitationDetail: React.FC<CitationDetailProps> = ({
  citation,
  accessCount,
  onClose,
}) => {
  // Extract filename from citation URL
  const filename = citation.split("/").pop() || citation;

  return (
    <Dialog open={true} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <FileText className="h-5 w-5 mr-2" />
            Citation Details
          </DialogTitle>
          <DialogDescription>
            Detailed information and access statistics
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Citation URL */}
          <div>
            <p className="text-sm font-medium mb-2">Citation URL</p>
            <div className="flex items-center gap-2 p-3 rounded-lg bg-muted/30">
              <p className="font-mono text-sm flex-1 truncate">{citation}</p>
              <Button variant="outline" size="sm" asChild>
                <a href={citation} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Open
                </a>
              </Button>
            </div>
          </div>

          {/* Statistics */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-lg border bg-blue-500/5">
              <div className="flex items-center gap-2 mb-1">
                <TrendingUp className="h-4 w-4 text-blue-600" />
                <p className="text-sm text-muted-foreground">Total Accesses</p>
              </div>
              <p className="text-3xl font-bold text-blue-600">{accessCount}</p>
            </div>

            <div className="p-4 rounded-lg border bg-green-500/5">
              <div className="flex items-center gap-2 mb-1">
                <Clock className="h-4 w-4 text-green-600" />
                <p className="text-sm text-muted-foreground">Last Accessed</p>
              </div>
              <p className="text-lg font-semibold">Recently</p>
            </div>
          </div>

          {/* Metadata */}
          <div>
            <p className="text-sm font-medium mb-2">Metadata</p>
            <div className="space-y-2">
              <div className="flex items-center justify-between p-2 rounded bg-muted/20">
                <span className="text-sm text-muted-foreground">Filename</span>
                <span className="text-sm font-mono">{filename}</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-muted/20">
                <span className="text-sm text-muted-foreground">Access Rank</span>
                <Badge variant="secondary">
                  {accessCount > 100 ? "Hot" : accessCount > 50 ? "Popular" : "Normal"}
                </Badge>
              </div>
            </div>
          </div>

          {/* Usage Insights */}
          <div className="p-4 rounded-lg border border-blue-500/30 bg-blue-500/5">
            <p className="text-sm font-medium mb-2 text-blue-700">Usage Insights</p>
            <ul className="space-y-1 text-sm text-blue-600">
              <li>• This citation is frequently accessed by the verification system</li>
              <li>• Consider optimizing cache performance for this citation</li>
              <li>• High access count indicates important business document</li>
            </ul>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
