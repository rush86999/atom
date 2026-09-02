import React, { useEffect, useState } from "react";
import { cn } from "../../lib/utils";

interface ZohoAppDetailProps {
  appName: string;
  description: string;
  category: string;
  /** Scopes/services this app's connect flow grants (all via one consent). */
  coveredServices: string[];
  /** Optional per-app deep links, used by the suite-level /integrations/zoho hub. */
  apps?: { name: string; href: string }[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

type TokenInfo = { provider: string; status: string; expires_at?: string | null };
type SyncInfo = { found: boolean; last_synced?: string | null; auto_sync_enabled?: boolean; entity_types?: string[]; sync_frequency_minutes?: number | null };

/**
 * Shared detail page for every Zoho suite app (Books, Inventory, CRM,
 * WorkDrive, Projects, Mail). One Server-based Zoho app consent connects the
 * whole suite — the Connect button opens the platform's unified
 * `GET /api/v1/auth/oauth/zoho/initiate` flow (same as the pilot doc).
 */
const ZohoIntegrationDetail: React.FC<ZohoAppDetailProps> = ({
  appName,
  description,
  category,
  coveredServices,
  apps,
}) => {
  const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(null);
  const [syncInfo, setSyncInfo] = useState<SyncInfo | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const token =
          typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
        const headers = { Authorization: `Bearer ${token || ""}` };
        const [tokRes, syncRes] = await Promise.all([
          fetch(`${API_BASE}/api/v1/auth/oauth/tokens`, { headers }),
          fetch(`${API_BASE}/api/data-ingestion/sync-status/zoho`, { headers }),
        ]);
        if (tokRes.ok) {
          const data = await tokRes.json();
          const zoho = (data.integrations || []).find(
            (t: TokenInfo) => t.provider === "zoho"
          );
          if (alive) setTokenInfo(zoho || null);
        }
        if (syncRes.ok) {
          const data = await syncRes.json();
          if (alive) setSyncInfo(data);
        }
      } catch {
        // status checks are best-effort; the connect flow works regardless
      } finally {
        if (alive) setChecked(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const connected = tokenInfo?.status === "active";

  return (
    // No <Layout> here — _app.tsx already wraps every page in the app shell;
    // wrapping again rendered a second nested sidebar (duplicate navbar bug).
    <div className="p-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold mb-2">{appName} Integration</h1>
        {checked && connected && (
          <span
            data-testid="zoho-connected-badge"
            className="mb-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
          >
            ● Connected
          </span>
        )}
      </div>
      <p className="text-gray-600 dark:text-gray-400 mb-4">{description}</p>

      <div className="mb-4">
        <span className="text-xs uppercase tracking-wide text-gray-500">
          Category
        </span>
        <span className="ml-2 text-sm">{category}</span>
      </div>

      <div className="mb-6">
        <span className="text-xs uppercase tracking-wide text-gray-500">
          Connected in this grant
        </span>
        <div className="mt-2 flex flex-wrap gap-2">
          {coveredServices.map((s) => (
            <span
              key={s}
              className={cn(
                "px-2 py-1 rounded-md text-xs font-medium",
                "bg-gray-100 dark:bg-gray-800",
                "text-gray-700 dark:text-gray-300",
              )}
            >
              {s}
            </span>
          ))}
        </div>
      </div>

      {apps && apps.length > 0 && (
        <div className="mb-6">
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Apps in this suite
          </span>
          <div className="mt-2 flex flex-wrap gap-2">
            {apps.map((a) => (
              <a
                key={a.href}
                href={a.href}
                className="px-2 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-300"
              >
                {a.name} →
              </a>
            ))}
          </div>
        </div>
      )}

      {checked && connected && (
        <div className="mb-6 p-4 rounded-lg border border-gray-200 dark:border-gray-700 text-sm space-y-1">
          <div>
            <span className="text-gray-500">Grant status: </span>
            <span className="font-medium">active</span>
            {tokenInfo?.expires_at && (
              <span className="text-gray-500">
                {" "}
                · token renews automatically (current expires{" "}
                {new Date(tokenInfo.expires_at).toLocaleString()})
              </span>
            )}
          </div>
          {syncInfo?.found && (
            <div>
              <span className="text-gray-500">Last synced: </span>
              <span className="font-medium">
                {syncInfo.last_synced
                  ? new Date(syncInfo.last_synced).toLocaleString()
                  : "never"}
              </span>
              <span className="text-gray-500">
                {" "}
                · auto-sync {syncInfo.auto_sync_enabled ? "on" : "off"} (every{" "}
                {syncInfo.sync_frequency_minutes ?? 60} min)
              </span>
            </div>
          )}
          <div className="text-gray-500 text-xs pt-1">
            Records land in the agent memory (Sales-tagged) and freshness is
            tracked per record (source modified time + last verified).
          </div>
        </div>
      )}

      <a
        href={`${API_BASE}/api/v1/auth/oauth/zoho/initiate`}
        data-testid="zoho-connect-link"
        className={cn(
          connected
            ? "inline-block border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 font-medium px-4 py-2 rounded-md"
            : "inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-md",
        )}
      >
        {connected ? `Reconnect ${appName}` : `Connect ${appName}`}
      </a>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
        One consent flow connects the entire Zoho suite (Books, Inventory,
        CRM, WorkDrive) with a single Zoho app grant. You must be signed in
        to the platform to start the flow.
      </p>
    </div>
  );
};

export default ZohoIntegrationDetail;
