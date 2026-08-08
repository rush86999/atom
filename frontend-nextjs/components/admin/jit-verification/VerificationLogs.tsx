import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { Activity, Download, RefreshCw, AlertCircle, Info, AlertTriangle } from "lucide-react";
import { jitVerificationAPI } from "@/lib/api-admin";
import { LogEntry } from "./LogEntry";
import type { VerificationLogEntry } from "@/types/jit-verification";

type LogLevel = "all" | "info" | "warning" | "error";

/**
 * Verification Logs Component
 *
 * Displays worker activity logs with filtering and export.
 */
export const VerificationLogs: React.FC = () => {
  const [logs, setLogs] = useState<VerificationLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<LogLevel>("all");
  const [timeRange, setTimeRange] = useState<"1h" | "24h" | "7d" | "30d">("24h");
  const { toast } = useToast();

  // BUG-066: Removed hardcoded mock log data. Logs load from the backend API.

  // Fetch real verification logs from the API (shared by initial load and Refresh)
  const fetchLogs = React.useCallback(
    async (range: "1h" | "24h" | "7d" | "30d") => {
      try {
        const res = await fetch(`/api/admin/governance/jit/logs?time_range=${range}`);
        const data = res.ok ? await res.json() : { logs: [] };
        setLogs(data.logs || []);
      } catch {
        setLogs([]);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    // Fetch real verification logs from the API.
    setLoading(true);
    fetchLogs(timeRange);
  }, [timeRange, fetchLogs]);

  // Filter logs by level
  const filteredLogs = React.useMemo(() => {
    if (filter === "all") return logs;

    return logs.filter((log) => log.level === filter);
  }, [logs, filter]);

  // Get log statistics
  const stats = React.useMemo(() => {
    return {
      total: logs.length,
      info: logs.filter((l) => l.level === "info").length,
      warning: logs.filter((l) => l.level === "warning").length,
      error: logs.filter((l) => l.level === "error").length,
    };
  }, [logs]);

  // Export logs as CSV
  const handleExportCSV = () => {
    const headers = ["Timestamp", "Level", "Event", "Details", "Citation"];
    const rows = filteredLogs.map((log) => [
      log.timestamp,
      log.level,
      log.event,
      log.details || "",
      log.citation || "",
    ]);

    const csv = [headers, ...rows]
      .map((row) => row.map((cell) => `"${cell}"`).join(","))
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `verification-logs-${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);

    toast({
      title: "Logs exported",
      description: `${filteredLogs.length} log entries exported as CSV`,
    });
  };

  // Refresh logs
  const handleRefresh = () => {
    setLoading(true);
    fetchLogs(timeRange);
    toast({
      title: "Logs refreshed",
      description: "Verification logs have been updated",
    });
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center">
                <Activity className="h-5 w-5 mr-2" />
                Verification Activity Logs
              </CardTitle>
              <CardDescription>
                Recent worker activity and system events
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <Button variant="outline" size="sm" onClick={handleExportCSV}>
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Statistics */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Events</p>
                <p className="text-2xl font-bold">{stats.total}</p>
              </div>
              <Activity className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Info</p>
                <p className="text-2xl font-bold text-blue-600">{stats.info}</p>
              </div>
              <Info className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Warnings</p>
                <p className="text-2xl font-bold text-yellow-600">{stats.warning}</p>
              </div>
              <AlertTriangle className="h-8 w-8 text-yellow-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Errors</p>
                <p className="text-2xl font-bold text-red-600">{stats.error}</p>
              </div>
              <AlertCircle className="h-8 w-8 text-red-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Log Level</p>
          <Select value={filter} onValueChange={(value) => setFilter(value as LogLevel)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Levels</SelectItem>
              <SelectItem value="info">Info</SelectItem>
              <SelectItem value="warning">Warning</SelectItem>
              <SelectItem value="error">Error</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Time Range</p>
          <Select value={timeRange} onValueChange={(value) => setTimeRange(value as any)}>
            <SelectTrigger className="w-[120px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1h">Last Hour</SelectItem>
              <SelectItem value="24h">Last 24h</SelectItem>
              <SelectItem value="7d">Last 7 Days</SelectItem>
              <SelectItem value="30d">Last 30 Days</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex-1" />

        <Badge variant="secondary" className="text-xs">
          {filteredLogs.length} entries
        </Badge>
      </div>

      {/* Log Entries */}
      <Card>
        <CardContent className="p-0">
          <ScrollArea className="h-[600px]">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : filteredLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Activity className="h-12 w-12 mb-4 opacity-50" />
                <p className="text-lg font-medium mb-2">No logs found</p>
                <p className="text-sm">Try changing the filter or time range</p>
              </div>
            ) : (
              <div className="divide-y">
                {filteredLogs.map((log, idx) => (
                  <LogEntry key={idx} log={log} />
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
};
