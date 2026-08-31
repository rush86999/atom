import React, { useEffect, useState } from "react";
import { cn } from "../../lib/utils";

interface ZohoWebhookAppDetailProps {
  appName: string;
  description: string;
  category: string;
  /** Backend integration id ("zoho-forms" | "zoho-flow"). */
  integrationId: "zoho-forms" | "zoho-flow";
  /** Ingestion webhook path Zoho pushes to (display + setup instructions). */
  webhookPath: string;
  /** Env var holding the shared secret the webhook must present. */
  secretEnv: string;
  /** Human label for ingested records ("submissions" | "events"). */
  recordsLabel: string;
  /** Readback endpoint (relative to the frontend API proxy). */
  recordsPath: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

type RecentRecord = {
  id: string;
  title?: string;
  text_preview?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
};

/**
 * Shared detail page for the webhook-push Zoho apps (Forms, Flow). Zoho
 * exposes no public read API for either product — data ingests when Zoho
 * pushes it to the webhook, landing in the same per-integration memory
 * tables every other integration uses. There is no OAuth connect flow and
 * no pull-sync button here: both would be dishonest for a push-only app.
 */
const ZohoWebhookIntegrationDetail: React.FC<ZohoWebhookAppDetailProps> = ({
  appName,
  description,
  category,
  integrationId,
  webhookPath,
  secretEnv,
  recordsLabel,
  recordsPath,
}) => {
  const [recent, setRecent] = useState<RecentRecord[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const token =
          typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
        const res = await fetch(`${API_BASE}${recordsPath}`, {
          headers: { Authorization: `Bearer ${token || ""}` },
        });
        if (res.ok && alive) {
          const data = await res.json();
          setRecent(Array.isArray(data.data) ? data.data : []);
        }
      } catch {
        // readback is best-effort; the webhook ingests regardless
      } finally {
        if (alive) setLoaded(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, [recordsPath]);

  return (
    <div className="p-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold mb-2">{appName} Integration</h1>
        {loaded && recent.length > 0 && (
          <span
            data-testid={`${integrationId}-ingested-badge`}
            className="mb-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
          >
            ● {recent.length}+ {recordsLabel} ingested
          </span>
        )}
      </div>
      <p className="text-gray-600 dark:text-gray-400 mb-4">{description}</p>

      <div className="mb-6">
        <span className="text-xs uppercase tracking-wide text-gray-500">
          Category
        </span>
        <span className="ml-2 text-sm">{category}</span>
      </div>

      <div className="mb-6 p-4 rounded-lg border border-gray-200 dark:border-gray-700 text-sm space-y-2">
        <div className="font-medium">How data ingests</div>
        <p className="text-gray-600 dark:text-gray-400">
          Zoho does not offer a public read API for {appName} — records are
          ingested when {appName} pushes them to this webhook (any JSON
          shape; field values are flattened into searchable text):
        </p>
        <code className="block px-3 py-2 rounded bg-gray-100 dark:bg-gray-800 text-xs break-all">
          POST {API_BASE}
          {webhookPath}
        </code>
        <p className="text-gray-500 text-xs">
          Send it with{" "}
          <code>Authorization: Bearer {"${" + secretEnv + "}"}</code> — set{" "}
          <code>{secretEnv}</code> in the backend environment first. Pushed{" "}
          {recordsLabel} land in agent memory (freshness/role-stamped) and
          are recallable in chat like every other integration.
        </p>
      </div>

      {loaded && (
        <div className="mb-6">
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Recently ingested {recordsLabel}
          </span>
          {recent.length === 0 ? (
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              Nothing ingested yet — {recordsLabel} appear here (and in chat
              recall) once {appName} pushes the first event.
            </p>
          ) : (
            <ul className="mt-2 space-y-2" data-testid={`${integrationId}-recent-list`}>
              {recent.slice(0, 10).map((r) => (
                <li
                  key={r.id}
                  className={cn(
                    "p-3 rounded-lg border text-sm",
                    "border-gray-200 dark:border-gray-700",
                  )}
                >
                  <div className="font-medium">{r.title || "Untitled"}</div>
                  {r.text_preview && (
                    <div className="text-gray-500 dark:text-gray-400 text-xs mt-1 line-clamp-2">
                      {r.text_preview}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default ZohoWebhookIntegrationDetail;
