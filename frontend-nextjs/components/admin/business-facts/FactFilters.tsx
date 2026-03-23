import React from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import type { BusinessFactFilters } from "@/types/jit-verification";

interface FactFiltersProps {
  filters: BusinessFactFilters;
  onFilterChange: (filters: Partial<BusinessFactFilters>) => void;
  domains: string[];
}

/**
 * Fact Filters Component
 *
 * Provides filtering options for business facts table.
 */
export const FactFilters: React.FC<FactFiltersProps> = ({
  filters,
  onFilterChange,
  domains,
}) => {
  return (
    <div className="flex gap-2">
      {/* Status Filter */}
      <div className="space-y-1">
        <Label className="text-xs">Status</Label>
        <Select
          value={filters.status || "all"}
          onValueChange={(value) =>
            onFilterChange({ status: value as any })
          }
        >
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="verified">Verified</SelectItem>
            <SelectItem value="unverified">Unverified</SelectItem>
            <SelectItem value="outdated">Outdated</SelectItem>
            <SelectItem value="deleted">Deleted</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Domain Filter */}
      {domains.length > 0 && (
        <div className="space-y-1">
          <Label className="text-xs">Domain</Label>
          <Select
            value={filters.domain || ""}
            onValueChange={(value) =>
              onFilterChange({ domain: value || undefined })
            }
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All domains" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Domains</SelectItem>
              {domains.map((domain) => (
                <SelectItem key={domain} value={domain}>
                  {domain}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  );
};
