import React from "react";
import { Badge } from "@/components/ui/badge";

interface VerificationStatusBadgeProps {
  status: "verified" | "unverified" | "outdated" | "deleted";
}

/**
 * Verification Status Badge Component
 *
 * Displays verification status with appropriate styling.
 */
export const VerificationStatusBadge: React.FC<VerificationStatusBadgeProps> = ({
  status,
}) => {
  const statusConfigs = {
    verified: {
      variant: "default" as const,
      className: "bg-green-600 hover:bg-green-700",
      icon: "✓",
      label: "Verified",
    },
    unverified: {
      variant: "secondary" as const,
      className: "bg-yellow-600 hover:bg-yellow-700 text-white",
      icon: "○",
      label: "Unverified",
    },
    outdated: {
      variant: "destructive" as const,
      className: "",
      icon: "!",
      label: "Outdated",
    },
    deleted: {
      variant: "outline" as const,
      className: "border-red-500 text-red-600",
      icon: "×",
      label: "Deleted",
    },
  };

  const config = statusConfigs[status];

  return (
    <Badge variant={config.variant} className={config.className}>
      {config.icon} {config.label}
    </Badge>
  );
};
