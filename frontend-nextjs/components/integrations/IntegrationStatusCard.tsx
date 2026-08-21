import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, ExternalLink } from "lucide-react";

interface IntegrationStatusCardProps {
  title: string;
  description?: string;
  /** Public (or bearer-authed) endpoint returning a JSON payload that
   * includes a `status`/`health` string field, e.g. /api/xero/status. */
  statusEndpoint?: string;
  /** When true, the status fetch includes the user's Bearer token. */
  statusRequiresAuth?: boolean;
  /** URL to send the browser to for connect (OAuth start page). */
  connectUrl?: string;
  /** When true, `connectUrl` returns JSON with `url` or `authorization_url`
   * and we redirect the browser to that value instead of navigating directly. */
  connectUrlIsJson?: boolean;
  connectLabel?: string;
  statusKey?: string;
  children?: React.ReactNode;
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("auth_token") || window.localStorage.getItem("token");
}

export function redirectTo(url: string): void {
  window.location.href = url;
}

export function resolveConnectUrl(data: any): string | null {
  if (!data || typeof data !== "object") return null;
  return data?.url || data?.authorization_url || null;
}

const normalizeStatus = (data: any): string => {
  if (!data || typeof data !== "object") return "unknown";
  if (typeof data.status === "string") return data.status;
  if (typeof data.state === "string") return data.state;
  if (data.ok === true) return "connected";
  if (typeof data.health === "string") return data.health;
  return "unknown";
};

/** Shared connected/disconnected shell for integration pages that only need a
 * real status check + a real Connect (OAuth) button — wires the integrations
 * that previously had dead stubs or no page at all (dropbox/telegram/gitlab/
 * xero) into the app's actual backend endpoints. */
const IntegrationStatusCard: React.FC<IntegrationStatusCardProps> = ({
  title,
  description,
  statusEndpoint,
  statusRequiresAuth = false,
  connectUrl,
  connectUrlIsJson = false,
  connectLabel = "Connect",
  statusKey = "status",
  children,
}) => {
  const [status, setStatus] = useState<string>("unknown");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!statusEndpoint) {
      setStatus("unknown");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      let res: Response;
      if (statusRequiresAuth) {
        const token = getToken();
        res = await fetch(statusEndpoint, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
      } else {
        res = await fetch(statusEndpoint);
      }
      if (!res.ok) {
        setStatus("unavailable");
        setError(`Status check failed (HTTP ${res.status})`);
      } else {
        const data = await res.json();
        setStatus(normalizeStatus(data));
      }
    } catch (e: any) {
      setStatus("unavailable");
      setError(e?.message || "Status check failed");
    } finally {
      setLoading(false);
    }
  }, [statusEndpoint, statusRequiresAuth]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleConnect = async () => {
    if (!connectUrl) return;
    if (!connectUrlIsJson) {
      redirectTo(connectUrl);
      return;
    }
    try {
      const res = await fetch(connectUrl);
      const data = await res.json();
      const target = resolveConnectUrl(data);
      if (target) {
        redirectTo(target);
      } else {
        setError("Connect URL could not be resolved.");
      }
    } catch (e: any) {
      setError(e?.message || "Connect URL could not be resolved.");
    }
  };

  const connected =
    ["connected", "active", "healthy", "ok", "online", "success"].includes(status);

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg">{title}</CardTitle>
            <Badge variant={connected ? "default" : "secondary"}>
              {loading ? "Checking…" : status}
            </Badge>
          </div>
          <div className="flex gap-2">
            {statusEndpoint && (
              <Button variant="ghost" size="sm" onClick={fetchStatus} disabled={loading}>
                <RefreshCw className="h-4 w-4 mr-1" /> Refresh
              </Button>
            )}
            {!connected && connectUrl && (
              <Button size="sm" onClick={handleConnect}>
                <ExternalLink className="h-4 w-4 mr-1" /> {connectLabel}
              </Button>
            )}
          </div>
        </div>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}
        <div className="text-sm text-muted-foreground" data-testid={`${title.toLowerCase()}-status-${statusKey}`}>
          {connected
            ? "Integration is reachable. You can use it in agents, workflows and automations."
            : "This integration is not connected yet. Connect it to use it in agents and workflows."}
        </div>
        {children}
      </CardContent>
    </Card>
  );
};

export default IntegrationStatusCard;
