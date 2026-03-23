import React from "react";
import { Badge } from "@/components/ui/badge";
import { Clock, Info, AlertTriangle, AlertCircle, ExternalLink } from "lucide-react";
import type { VerificationLogEntry } from "@/types/jit-verification";

interface LogEntryProps {
  log: VerificationLogEntry;
}

/**
 * Single Log Entry Component
 *
 * Displays a single verification log entry with icon, timestamp, and details.
 */
export const LogEntry: React.FC<LogEntryProps> = ({ log }) => {
  const formatTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const formatRelativeTime = (dateStr: string): string => {
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

  const getLevelConfig = (level: string) => {
    switch (level) {
      case "info":
        return {
          icon: Info,
          color: "text-blue-600",
          bgColor: "bg-blue-500/10",
          badgeColor: "bg-blue-600 hover:bg-blue-700",
        };
      case "warning":
        return {
          icon: AlertTriangle,
          color: "text-yellow-600",
          bgColor: "bg-yellow-500/10",
          badgeColor: "bg-yellow-600 hover:bg-yellow-700 text-white",
        };
      case "error":
        return {
          icon: AlertCircle,
          color: "text-red-600",
          bgColor: "bg-red-500/10",
          badgeColor: "bg-destructive hover:bg-destructive/90",
        };
      default:
        return {
          icon: Info,
          color: "text-muted-foreground",
          bgColor: "bg-muted",
          badgeColor: "",
        };
    }
  };

  const config = getLevelConfig(log.level);
  const Icon = config.icon;

  return (
    <div className={`flex items-start gap-3 p-4 hover:bg-muted/50 transition-colors ${config.bgColor}`}>
      {/* Icon */}
      <div className="mt-0.5">
        <Icon className={`h-4 w-4 ${config.color} flex-shrink-0`} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-1">
        {/* Header */}
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={`text-xs ${config.badgeColor}`}>
            {log.level.toUpperCase()}
          </Badge>
          <span className="text-sm font-medium">{log.event}</span>
        </div>

        {/* Details */}
        {log.details && (
          <p className="text-sm text-muted-foreground">{log.details}</p>
        )}

        {/* Citation Link */}
        {log.citation && (
          <div className="flex items-center gap-1">
            <a
              href={log.citation}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-xs hover:text-primary underline"
            >
              {log.citation}
            </a>
            <ExternalLink className="h-3 w-3 text-muted-foreground" />
          </div>
        )}

        {/* Timestamp */}
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          <span>{formatTime(log.timestamp)}</span>
          <span className="text-muted-foreground/50">•</span>
          <span>{formatRelativeTime(log.timestamp)}</span>
        </div>
      </div>
    </div>
  );
};
