"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  HardDrive,
  RefreshCw,
  Folder,
  Database,
  Map,
  Loader2,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Universal selective-ingestion panel — "map the territory, not the contents".
 *
 * For any indexable integration (onedrive, zoho_workdrive, dropbox,
 * google_drive, zoho_crm, zoho_books, zoho_inventory):
 *  - Map structure: ingests the full LISTING (paths/sizes/records metadata —
 *    kilobytes) into agent memory so hires know what exists.
 *  - Selective contents: enable per-integration ingestion, pick file types,
 *    size cap and sync cadence — contents otherwise load just-in-time when
 *    an agent's task needs one file (integration_ingest_item tool).
 *
 * Backed by GET/PUT /api/document-ingestion/settings and the structure-index
 * routes. See docs/integrations/INGESTION_PROVENANCE_DESIGN.md.
 */

interface StructureRow {
  external_id: string;
  kind: string;
  entity_type: string;
  name: string;
  path: string;
  size: number;
  modified: string;
}

interface SettingsShape {
  enabled?: boolean;
  auto_sync_new_files?: boolean;
  file_types?: string[];
  sync_folders?: string[];
  exclude_folders?: string[];
  max_file_size_mb?: number;
  sync_frequency_minutes?: number;
}

const FILE_TYPE_OPTIONS = ["pdf", "docx", "xlsx", "csv", "txt", "md"];

function authHeaders(json = true): Record<string, string> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export default function IntegrationDataIngestion() {
  const [integrations, setIntegrations] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [structure, setStructure] = useState<StructureRow[]>([]);
  const [settings, setSettings] = useState<SettingsShape>({});
  const [loading, setLoading] = useState(true);
  const [indexing, setIndexing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadIntegrations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/document-ingestion/integrations", {
        headers: authHeaders(false),
      });
      const data = await res.json();
      const list: string[] = data.integrations || [];
      setIntegrations(list);
      if (list.length && !selected) setSelected(list[0]);
    } catch {
      setError("Could not load indexable integrations.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadSettings = useCallback(async (integrationId: string) => {
    if (!integrationId) return;
    try {
      const res = await fetch(
        `/api/document-ingestion/settings/${integrationId}`,
        { headers: authHeaders(false) }
      );
      const data = await res.json();
      setSettings(data?.settings || data || {});
    } catch {
      setSettings({});
    }
  }, []);

  const loadStructure = useCallback(async (integrationId: string) => {
    setStructure([]);
    if (!integrationId) return;
    try {
      const res = await fetch(
        `/api/document-ingestion/integrations/${integrationId}/structure`,
        { headers: authHeaders(false) }
      );
      const data = await res.json();
      setStructure(data?.rows || []);
    } catch {
      /* picker stays empty — mapping still works */
    }
  }, []);

  useEffect(() => {
    loadIntegrations();
  }, [loadIntegrations]);

  useEffect(() => {
    if (selected) {
      loadSettings(selected);
      loadStructure(selected);
    }
  }, [selected, loadSettings, loadStructure]);

  const mapStructure = async () => {
    if (!selected) return;
    setIndexing(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(
        `/api/document-ingestion/integrations/${selected}/index-structure`,
        {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({}),
        }
      );
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.detail || "Mapping failed");
      setNotice(
        `Structure mapped: ${data.rows_written} rows indexed (${Object.entries(
          data.counts || {}
        )
          .map(([k, v]) => `${v} ${k}s`)
          .join(", ")}) — agents can now see what exists and pull files just-in-time.`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIndexing(false);
    }
  };

  const saveSettings = async (patch: SettingsShape) => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    const next = { ...settings, ...patch };
    setSettings(next);
    try {
      await fetch("/api/document-ingestion/settings", {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify({ integration_id: selected, ...next }),
      });
      setNotice("Settings saved.");
    } catch {
      setError("Failed to save settings.");
    } finally {
      setSaving(false);
    }
  };

  const toggleType = (t: string) => {
    const current = settings.file_types || [];
    const next = current.includes(t)
      ? current.filter((x) => x !== t)
      : [...current, t];
    saveSettings({ file_types: next });
  };

  return (
    <div className="p-6 max-w-[1400px] mx-auto w-full space-y-4" data-testid="integration-data-ingestion">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <HardDrive className="h-5 w-5" />
          <h1 className="text-xl font-semibold">Data for your agents</h1>
        </div>
        <Button variant="ghost" size="sm" onClick={loadIntegrations} data-testid="ingestion-refresh">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>
      <p className="text-sm text-muted-foreground -mt-2">
        Map your integrations' structure so agents learn what exists — file
        contents are pulled just-in-time, one file at a time, only when a task
        needs them.
      </p>

      {error && (
        <p role="alert" className="text-xs text-red-600 bg-red-50 dark:bg-red-900/20 rounded px-2 py-1 flex items-center gap-1.5">
          <AlertTriangle className="h-3.5 w-3.5" /> {error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 rounded px-2 py-1 flex items-center gap-1.5">
          <CheckCircle className="h-3.5 w-3.5" /> {notice}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading integrations…
        </p>
      ) : integrations.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No indexable integrations connected yet. Connect OneDrive, Google
          Drive, Dropbox or a Zoho app first.
        </p>
      ) : (
        <>
          <div className="flex items-center gap-2 flex-wrap">
            {integrations.map((id) => (
              <button
                key={id}
                onClick={() => setSelected(id)}
                className={`px-3 py-1.5 rounded-md text-sm border transition-colors ${
                  selected === id
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-background border-border hover:bg-muted"
                }`}
                data-testid={`integration-tab-${id}`}
              >
                {id.replace(/_/g, " ")}
              </button>
            ))}
          </div>

          <div className="border rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Map className="h-4 w-4" />
                <p className="text-sm font-medium">Structure map</p>
              </div>
              <Button
                size="sm"
                onClick={mapStructure}
                disabled={indexing}
                data-testid="map-structure-button"
              >
                {indexing ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                ) : (
                  <Database className="h-4 w-4 mr-1" />
                )}
                {indexing ? "Mapping…" : "Map structure"}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Indexes every folder/file/record LISTING (names, paths, sizes,
              dates — never downloads contents) so agents can find what
              exists and pull individual files when a task needs them.
            </p>
            {!!structure.length && (
              <div className="border rounded-md max-h-40 overflow-y-auto divide-y" data-testid="structure-preview">
                {structure.slice(0, 50).map((row, i) => (
                  <div key={`${row.external_id}-${i}`} className="flex items-center gap-2 px-2 py-1 text-xs">
                    {row.kind === "folder" ? (
                      <Folder className="h-3 w-3 text-muted-foreground shrink-0" />
                    ) : (
                      <Database className="h-3 w-3 text-muted-foreground shrink-0" />
                    )}
                    <span className="truncate">{row.path ? `${row.path}/` : ""}{row.name}</span>
                    {!!row.size && (
                      <span className="ml-auto shrink-0 text-muted-foreground">
                        {(row.size / 1024).toFixed(0)} KB
                      </span>
                    )}
                  </div>
                ))}
                {structure.length > 50 && (
                  <div className="px-2 py-1 text-[10px] text-muted-foreground">
                    …and {structure.length - 50} more
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="border rounded-lg p-4 space-y-4">
            <p className="text-sm font-medium">Selective contents ingestion</p>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="ingest-enabled"
                checked={!!settings.enabled}
                onChange={(e) => saveSettings({ enabled: e.target.checked })}
                data-testid="ingest-enabled-toggle"
              />
              <label htmlFor="ingest-enabled" className="text-sm">
                Auto-ingest file contents on sync (off = structure + just-in-time only)
              </label>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1.5">File types</p>
              <div className="flex gap-1.5 flex-wrap">
                {FILE_TYPE_OPTIONS.map((t) => (
                  <button
                    key={t}
                    onClick={() => toggleType(t)}
                    className={`px-2 py-1 rounded text-xs border transition-colors ${
                      (settings.file_types || []).includes(t)
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-background border-border hover:bg-muted"
                    }`}
                    data-testid={`file-type-${t}`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Per-file cap (MB)</span>
                <Input
                  className="h-8 w-20 text-xs"
                  type="number"
                  min={1}
                  value={settings.max_file_size_mb ?? 50}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, max_file_size_mb: Number(e.target.value) }))
                  }
                  onBlur={(e) => saveSettings({ max_file_size_mb: Number(e.target.value) })}
                  data-testid="max-size-input"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Sync every (min)</span>
                <Input
                  className="h-8 w-20 text-xs"
                  type="number"
                  min={5}
                  value={settings.sync_frequency_minutes ?? 60}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, sync_frequency_minutes: Number(e.target.value) }))
                  }
                  onBlur={(e) => saveSettings({ sync_frequency_minutes: Number(e.target.value) })}
                  data-testid="sync-frequency-input"
                />
              </div>
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
