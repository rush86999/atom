import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Info, Loader2 } from "lucide-react";
import { businessFactsAPI } from "@/lib/api-admin";
import type { BusinessFact, CreateBusinessFactRequest, UpdateBusinessFactRequest } from "@/types/jit-verification";

interface BusinessFactFormProps {
  fact?: BusinessFact | null;
  onSubmit: () => void;
  onCancel: () => void;
}

/**
 * Business Fact Form
 *
 * Provides create/edit form for business facts.
 */
export const BusinessFactForm: React.FC<BusinessFactFormProps> = ({
  fact,
  onSubmit,
  onCancel,
}) => {
  const [formData, setFormData] = useState({
    fact: fact?.fact || "",
    citations: fact?.citations.join("\n") || "",
    reason: fact?.reason || "",
    domain: fact?.domain || "",
    verification_status: fact?.verification_status || "unverified",
  });
  const [submitting, setSubmitting] = useState(false);
  const { toast } = useToast();

  const isEdit = !!fact;

  // Reset form when fact prop changes
  useEffect(() => {
    if (fact) {
      setFormData({
        fact: fact.fact,
        citations: fact.citations.join("\n"),
        reason: fact.reason,
        domain: fact.domain,
        verification_status: fact.verification_status,
      });
    }
  }, [fact]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate
    if (!formData.fact.trim()) {
      toast({
        title: "Validation error",
        description: "Fact text is required",
        variant: "destructive",
      });
      return;
    }

    if (!formData.domain.trim()) {
      toast({
        title: "Validation error",
        description: "Domain is required",
        variant: "destructive",
      });
      return;
    }

    // Parse citations
    const citations = formData.citations
      .split("\n")
      .map((c) => c.trim())
      .filter((c) => c.length > 0);

    if (citations.length === 0) {
      toast({
        title: "Validation error",
        description: "At least one citation is required",
        variant: "destructive",
      });
      return;
    }

    setSubmitting(true);

    try {
      if (isEdit && fact) {
        // Update existing fact
        const updateData: UpdateBusinessFactRequest = {
          fact: formData.fact,
          citations,
          reason: formData.reason,
          domain: formData.domain,
          verification_status: formData.verification_status as any,
        };

        await businessFactsAPI.updateFact(fact.id, updateData);

        toast({
          title: "Fact updated",
          description: "Business fact has been updated successfully",
        });
      } else {
        // Create new fact
        const createData: CreateBusinessFactRequest = {
          fact: formData.fact,
          citations,
          reason: formData.reason,
          domain: formData.domain,
        };

        await businessFactsAPI.createFact(createData);

        toast({
          title: "Fact created",
          description: "New business fact has been created successfully",
        });
      }

      onSubmit();
    } catch (error: any) {
      console.error("Failed to save fact:", error);
      toast({
        title: isEdit ? "Update failed" : "Creation failed",
        description: error.userMessage || `Failed to ${isEdit ? "update" : "create"} business fact`,
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (
    field: keyof typeof formData,
    value: string
  ) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <Dialog open={true} onOpenChange={onCancel}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit Business Fact" : "Create Business Fact"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update the business fact details and citations"
              : "Add a new business fact with citation verification"}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Fact Text */}
          <div className="space-y-2">
            <Label htmlFor="fact">Fact *</Label>
            <Textarea
              id="fact"
              placeholder="Invoices over $500 require VP approval"
              value={formData.fact}
              onChange={(e) => handleChange("fact", e.target.value)}
              rows={3}
              required
            />
          </div>

          {/* Domain */}
          <div className="space-y-2">
            <Label htmlFor="domain">Domain *</Label>
            <Input
              id="domain"
              placeholder="finance"
              value={formData.domain}
              onChange={(e) => handleChange("domain", e.target.value)}
              required
            />
            <p className="text-xs text-muted-foreground">
              The business domain this fact belongs to (e.g., finance, hr, operations)
            </p>
          </div>

          {/* Citations */}
          <div className="space-y-2">
            <Label htmlFor="citations">Citations *</Label>
            <Textarea
              id="citations"
              placeholder={`https://atom-citations-prod.bucket.s3.amazonaws.com/policy.pdf?page=4\nhttps://atom-citations-prod.bucket.s3.amazonaws.com/handbook.pdf#page=12`}
              value={formData.citations}
              onChange={(e) => handleChange("citations", e.target.value)}
              rows={6}
              className="font-mono text-sm"
              required
            />
            <p className="text-xs text-muted-foreground">
              One citation URL per line. These will be verified against R2/S3 storage.
            </p>
          </div>

          {/* Reason */}
          <div className="space-y-2">
            <Label htmlFor="reason">Reason</Label>
            <Textarea
              id="reason"
              placeholder="This policy ensures proper oversight of large expenditures"
              value={formData.reason}
              onChange={(e) => handleChange("reason", e.target.value)}
              rows={2}
            />
            <p className="text-xs text-muted-foreground">
              Explain why this fact exists or provide additional context
            </p>
          </div>

          {/* Verification Status (edit only) */}
          {isEdit && (
            <div className="space-y-2">
              <Label htmlFor="status">Verification Status</Label>
              <Select
                value={formData.verification_status}
                onValueChange={(value) => handleChange("verification_status", value)}
              >
                <SelectTrigger id="status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="verified">Verified</SelectItem>
                  <SelectItem value="unverified">Unverified</SelectItem>
                  <SelectItem value="outdated">Outdated</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Info Alert */}
          <Alert variant="default" className="border-blue-500/50 bg-blue-500/5">
            <Info className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-sm text-blue-700">
              {isEdit
                ? "Changes will be saved immediately. Citation verification status will be updated based on the latest verification results."
                : "After creation, citations will be verified automatically. You can check the verification status in the facts table."}
            </AlertDescription>
          </Alert>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {isEdit ? "Updating..." : "Creating..."}
                </>
              ) : (
                <>{isEdit ? "Update Fact" : "Create Fact"}</>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
