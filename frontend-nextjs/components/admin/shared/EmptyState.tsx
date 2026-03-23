import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, AlertCircle, CheckCircle2, Inbox } from "lucide-react";

interface EmptyStateProps {
  type?: "no-data" | "no-results" | "no-issues" | "error";
  title?: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

/**
 * Empty State Component
 *
 * Displays when there's no data to show.
 * Provides context and actionable next steps.
 */
export const EmptyState: React.FC<EmptyStateProps> = ({
  type = "no-data",
  title,
  description,
  action,
}) => {
  const config = {
    "no-data": {
      icon: Inbox,
      iconColor: "text-muted-foreground",
      defaultTitle: "No data available",
      defaultDescription: "There's no data to display yet. Check back later.",
    },
    "no-results": {
      icon: FileText,
      iconColor: "text-muted-foreground",
      defaultTitle: "No results found",
      defaultDescription: "Try adjusting your filters or search query.",
    },
    "no-issues": {
      icon: CheckCircle2,
      iconColor: "text-green-600",
      defaultTitle: "All clear!",
      defaultDescription: "No issues detected. Everything is running smoothly.",
    },
    "error": {
      icon: AlertCircle,
      iconColor: "text-red-600",
      defaultTitle: "Something went wrong",
      defaultDescription: "An error occurred while loading data. Please try again.",
    },
  };

  const { icon: Icon, iconColor, defaultTitle, defaultDescription } = config[type];

  return (
    <Card>
      <CardContent className="py-12">
        <div className="text-center">
          <Icon className={`h-12 w-12 mx-auto mb-4 ${iconColor} opacity-50`} />
          <p className="text-lg font-medium mb-2">{title || defaultTitle}</p>
          <p className="text-sm text-muted-foreground mb-6">{description || defaultDescription}</p>
          {action && (
            <Button onClick={action.onClick} size="sm">
              {action.label}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
