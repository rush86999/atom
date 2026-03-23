import React from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { AlertCircle, FileCheck, Info } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface CitationInputProps {
  value: string;
  onChange: (value: string) => void;
  forceRefresh: boolean;
  onForceRefreshChange: (value: boolean) => void;
  onVerify: () => void;
  verifying: boolean;
}

/**
 * Citation Input Component
 *
 * Provides:
 * - Text area for entering citations (one per line or comma-separated)
 * - Force refresh toggle for bypassing cache
 * - Verify button with loading state
 * - Input validation and helpful hints
 */
export const CitationInput: React.FC<CitationInputProps> = ({
  value,
  onChange,
  forceRefresh,
  onForceRefreshChange,
  onVerify,
  verifying,
}) => {
  const citationCount = value
    .split(/[\n,]+/)
    .map((c) => c.trim())
    .filter((c) => c.length > 0).length;

  return (
    <div className="space-y-4">
      {/* Input Text Area */}
      <div className="space-y-2">
        <Label htmlFor="citations">Citations</Label>
        <Textarea
          id="citations"
          placeholder={`https://atom-citations-prod.bucket.s3.amazonaws.com/policy.pdf?page=4\nhttps://atom-citations-prod.bucket.s3.amazonaws.com/handbook.pdf#page=12\n...`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={8}
          className="font-mono text-sm resize-none"
          disabled={verifying}
        />
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>Enter one citation per line or comma-separated</span>
          <span>{citationCount} citation{citationCount !== 1 ? "s" : ""}</span>
        </div>
      </div>

      {/* Force Refresh Toggle */}
      <div className="flex items-center justify-between p-4 rounded-lg border bg-secondary/20">
        <div className="flex items-center gap-3">
          <Switch
            id="force-refresh"
            checked={forceRefresh}
            onCheckedChange={onForceRefreshChange}
            disabled={verifying}
          />
          <div className="space-y-0.5">
            <Label htmlFor="force-refresh" className="cursor-pointer">
              Force refresh
            </Label>
            <p className="text-xs text-muted-foreground">
              Bypass cache and verify directly from R2/S3
            </p>
          </div>
        </div>
        <Info className="h-4 w-4 text-muted-foreground" />
      </div>

      {/* Force Refresh Warning */}
      {forceRefresh && (
        <Alert variant="default" className="border-yellow-500/50 bg-yellow-500/5">
          <AlertCircle className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-sm text-yellow-700">
            Force refresh enabled: Citations will be verified directly from R2/S3 storage,
            bypassing both L1 and L2 cache. This is slower but ensures fresh results.
          </AlertDescription>
        </Alert>
      )}

      {/* Verify Button */}
      <div className="flex items-center gap-2">
        <Button
          onClick={onVerify}
          disabled={verifying || citationCount === 0}
          className="flex-1"
        >
          {verifying ? (
            <>
              <div className="h-4 w-4 mr-2 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              Verifying {citationCount} citation{citationCount !== 1 ? "s" : ""}...
            </>
          ) : (
            <>
              <FileCheck className="h-4 w-4 mr-2" />
              Verify Citations
            </>
          )}
        </Button>
      </div>

      {/* Help Tips */}
      <Alert variant="default" className="border-blue-500/50 bg-blue-500/5">
        <Info className="h-4 w-4 text-blue-600" />
        <AlertDescription className="text-sm text-blue-700 space-y-1">
          <p className="font-medium">Tips for best results:</p>
          <ul className="list-disc list-inside space-y-0.5 text-xs ml-2">
            <li>Use full S3/R2 URLs (https://bucket.s3.amazonaws.com/path/to/file.pdf)</li>
            <li>One citation per line or comma-separated</li>
            <li>Enable force refresh only if you suspect cache is stale</li>
            <li>Large batches may take longer to verify</li>
          </ul>
        </AlertDescription>
      </Alert>
    </div>
  );
};
