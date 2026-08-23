/**
 * Integrations Panel (MenuBar / Desktop)
 *
 * Round 80r — desktop parity: read-only integration status plus connect /
 * disconnect actions, mirroring the mobile IntegrationsSection.
 *
 * Data sources (live Atom backend):
 *   GET  /api/v1/integrations/health                    aggregate + per-service
 *   GET  /api/integrations                              catalog
 *   GET  /api/v1/auth/oauth/:provider/initiate?format=json   connect URL
 *   DELETE /api/v1/auth/oauth/tokens/:provider           disconnect
 */

import React, { useCallback, useEffect, useState } from "react";
import { panelStyles as ps } from "../styles/panelStyles";

interface IntegrationHealthRow {
  service_name: string;
  status: string;
  enabled?: boolean;
  configured?: boolean;
  error_message?: string | null;
}

interface AllIntegrationsHealth {
  total_integrations: number;
  healthy_integrations: number;
  overall_health_percentage?: number;
  integration_status: IntegrationHealthRow[];
}

/** Providers whose stored OAuth tokens can be revoked from the desktop app. */
const DISCONNECTABLE_PROVIDERS = new Set([
  "google", "microsoft", "salesforce", "slack", "github",
  "asana", "notion", "trello", "dropbox", "whatsapp", "zoho",
]);

export const DEFAULT_SERVER_URL = "http://localhost:8000";

interface IntegrationsPanelProps {
  serverUrl?: string;
  /** JWT for auth-gated calls (connect/disconnect). */
  token?: string | null;
}

function normalizeServer(serverUrl?: string): string {
  const base = (serverUrl || DEFAULT_SERVER_URL).replace(/\/$/, "");
  return base.startsWith("http") ? base : `http://${base}`;
}

export default function IntegrationsPanel({
  serverUrl,
  token,
}: IntegrationsPanelProps) {
  const [health, setHealth] = useState<AllIntegrationsHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyProvider, setBusyProvider] = useState<string | null>(null);

  const base = normalizeServer(serverUrl);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${base}/api/v1/integrations/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setHealth(await res.json());
    } catch (e: any) {
      setError(e?.message || "Failed to load integrations");
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    load();
  }, [load]);

  const handleConnect = useCallback(
    async (provider: string) => {
      setBusyProvider(provider);
      setError(null);
      try {
        const headers: Record<string, string> = {};
        if (token) headers.Authorization = `Bearer ${token}`;
        const res = await fetch(
          `${base}/api/v1/auth/oauth/${provider}/initiate?format=json`,
          { headers }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!data?.url) throw new Error("No authorization URL returned");
        // Tauri webview + plain browser both handle target=_blank.
        window.open(data.url as string, "_blank");
        // Give the user time to complete consent, then refresh status.
        setTimeout(load, 4000);
      } catch (e: any) {
        setError(e?.message || "Failed to start connection");
      } finally {
        setBusyProvider(null);
      }
    },
    [base, token, load]
  );

  const handleDisconnect = useCallback(
    async (provider: string) => {
      setBusyProvider(provider);
      setError(null);
      try {
        const headers: Record<string, string> = {};
        if (token) headers.Authorization = `Bearer ${token}`;
        const res = await fetch(
          `${base}/api/v1/auth/oauth/tokens/${provider}`,
          { method: "DELETE", headers }
        );
        if (res.status === 404) {
          setError(`${provider} is not connected.`);
        } else if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        await load();
      } catch (e: any) {
        setError(e?.message || "Failed to disconnect");
      } finally {
        setBusyProvider(null);
      }
    },
    [base, token, load]
  );

  const healthy = health?.healthy_integrations ?? 0;
  const total = health?.total_integrations ?? 0;

  return (
    <div style={ps.container} data-testid="integrations-panel">
      <div style={ps.header}>
        <span style={ps.title}>Integrations</span>
        <span
          style={{...ps.count}} data-count= ${healthy === total && total > 0 ? "all-healthy" : ""}`}
          data-testid="integrations-summary"
        >
          {loading ? "Checking…" : `${healthy} of ${total} healthy`}
        </span>
        <button className="integrations-refresh" onClick={load}>
          Refresh
        </button>
      </div>

      {error && (
        <div style={ps.error} role="alert">
          {error}
        </div>
      )}

      {!loading && health && (
        <ul style={ps.list}>
          {health.integration_status.map((row) => {
            const name = row.service_name.toLowerCase();
            const canDisconnect =
              DISCONNECTABLE_PROVIDERS.has(name) && row.status === "healthy";
            const canConnect =
              DISCONNECTABLE_PROVIDERS.has(name) && row.status !== "healthy";
            return (
              <li
                key={row.service_name}
                className={`integrations-row ${row.status}`}
                data-testid={`integration-row-${name}`}
              >
                <span style={ps.name}>{row.service_name}</span>
                {row.error_message && row.status !== "healthy" ? (
                  <span className="service-error">{row.error_message}</span>
                ) : null}
                <span className={`service-status ${row.status}`}>
                  {row.status}
                </span>
                {canDisconnect && (
                  <button
                    className="service-disconnect"
                    disabled={busyProvider === name}
                    onClick={() => handleDisconnect(name)}
                    data-testid={`disconnect-${name}`}
                  >
                    {busyProvider === name ? "…" : "Disconnect"}
                  </button>
                )}
                {canConnect && (
                  <button
                    className="service-connect"
                    disabled={busyProvider === name}
                    onClick={() => handleConnect(name)}
                    data-testid={`connect-${name}`}
                  >
                    {busyProvider === name ? "…" : "Connect"}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
