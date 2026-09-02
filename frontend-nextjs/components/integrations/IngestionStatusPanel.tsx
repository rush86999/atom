import React, { useState, useEffect, useCallback } from "react";
import {
  CheckCircle,
  XCircle,
  Clock,
  Database,
  Loader2,
  Play,
  RefreshCw,
} from "lucide-react";
import { Card, CardContent } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { authFetch, authHeaders, handleSessionExpired } from "@/lib/auth-headers";

/**
 * Data-ingestion progress for one integration, from
 * GET /api/integrations/{id}/ingestion-status — the communication memory
 * pipeline's real record counts (records ingested into LanceDB, last
 * ingest time, poller/stream state). This is memory ingestion, distinct
 * from the live mailbox/board data the integration pages operate on.
 */
interface IngestionStatus {
  integration_id: string;
  app_type: string | null;
  connected: boolean;
  connection_source: string;
  ingestion_available: boolean;
  stream_running: boolean;
  records_ingested: number;
  last_ingested: string | null;
  ingestion_status: string | null;
  // Hybrid sync-service state (business integrations without a memory
  // poller — salesforce, jira, zendesk, …).
  last_synced?: string | null;
  auto_sync_enabled?: boolean;
  sync_frequency_minutes?: number | null;
  start_attempted?: boolean;
}

interface IngestionStatusPanelProps {
  integrationId: string;
  title?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
  className?: string;
}

const formatRelative = (iso: string | null): string => {
  if (!iso) return "Never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "Never";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
};

const formatCount = (n: number): string =>
  n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : `${n}`;

const IngestionStatusPanel: React.FC<IngestionStatusPanelProps> = ({
  integrationId,
  title = "Data Ingestion",
  autoRefresh = true,
  refreshInterval = 30000,
  className = "",
}) => {
  const [status, setStatus] = useState<IngestionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const response = await authFetch(
        `/api/integrations/${integrationId}/ingestion-status`,
        { headers: authHeaders() }
      );
      // A 401/403 means the session died (key rotation, expiry) — route to
      // login like every other fetch-based caller instead of throwing a raw
      // "returned 401" error into the console.
      if (response.status === 401 || response.status === 403) {
        handleSessionExpired();
        return;
      }
      if (!response.ok) {
        setStatus(null);
        return;
      }
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      // Network disconnect or momentary backend restart
      setStatus(null);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, [integrationId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(refresh, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, refresh]);

  const startSync = async () => {
    setStarting(true);
    setActionError(null);
    try {
      const response = await authFetch(
        `/api/integrations/${integrationId}/ingestion/start`,
        { method: "POST", headers: authHeaders() }
      );
      if (response.status === 409) {
        setActionError("No active connection — reconnect this integration first.");
      } else if (!response.ok) {
        setActionError(`Could not start sync (HTTP ${response.status}).`);
      }
      await refresh();
    } catch (error) {
      console.error("Failed to start ingestion:", error);
      setActionError("Could not start sync.");
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <Card className={className} data-testid="ingestion-status-panel-loading">
        <CardContent className="pt-6 flex items-center space-x-3 text-sm text-gray-500 dark:text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Loading ingestion status…</span>
        </CardContent>
      </Card>
    );
  }

  const connected = status?.connected ?? false;
  const streamRunning = status?.stream_running ?? false;

  return (
    <Card className={className} data-testid="ingestion-status-panel">
      <CardContent className="pt-6 space-y-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <Database className="h-5 w-5 text-blue-500" />
            <h3 className="font-bold text-gray-900 dark:text-gray-100">{title}</h3>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant={connected ? "success" : "secondary"}>
              {connected ? "Connected" : "Not connected"}
            </Badge>
            <Badge
              variant={streamRunning ? "success" : connected ? "warning" : "secondary"}
            >
              {streamRunning ? "Syncing" : connected ? "Sync stopped" : "—"}
            </Badge>
            <Button
              size="sm"
              variant="ghost"
              onClick={refresh}
              disabled={refreshing}
              aria-label="Refresh ingestion status"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {!status?.ingestion_available ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Ingestion pipeline is not available right now.
          </p>
        ) : status.app_type ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                Records ingested
              </p>
              <div className="text-2xl font-bold" data-testid="ingestion-records">
                {formatCount(status.records_ingested)}
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                Last ingested
              </p>
              <div
                className="text-2xl font-bold"
                data-testid="ingestion-last"
                title={status.last_ingested ?? undefined}
              >
                {formatRelative(status.last_ingested)}
              </div>
            </div>
            <div className="space-y-1 col-span-2 md:col-span-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                Memory status
              </p>
              <div className="text-2xl font-bold capitalize">
                {status.ingestion_status ?? "idle"}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-1" data-testid="ingestion-sync-only">
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Last record sync
            </p>
            <div className="text-2xl font-bold" data-testid="ingestion-last">
              {formatRelative(status.last_synced ?? null)}
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {status.auto_sync_enabled
                ? `Auto-sync on${
                    status.sync_frequency_minutes
                      ? ` (every ${status.sync_frequency_minutes} min)`
                      : ""
                  }`
                : "This integration syncs records without a memory poller."}
            </p>
          </div>
        )}

        {connected &&
        !streamRunning &&
        !!status?.app_type &&
        status?.ingestion_available && (
          <div className="flex items-center justify-between space-x-4">
            <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center">
              <Clock className="h-4 w-4 mr-2" />
              The sync stream isn&apos;t running — start it to ingest new data.
            </p>
            <Button size="sm" onClick={startSync} disabled={starting}>
              {starting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Start sync
            </Button>
          </div>
        )}

        {!connected && (
          <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center">
            {streamRunning ? (
              <CheckCircle className="h-4 w-4 mr-2 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 mr-2" />
            )}
            No connected account for this integration — connect it to ingest data.
          </p>
        )}

        {actionError && (
          <p className="text-sm text-red-500 flex items-center">
            <XCircle className="h-4 w-4 mr-2" />
            {actionError}
          </p>
        )}
      </CardContent>
    </Card>
  );
};

export default IngestionStatusPanel;
