import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  getSettings,
  resetSetting,
  updateSetting,
  type SettingEntry,
  type SettingsCatalog,
} from "@/lib/runtime-settings-api";

/**
 * Admin — Runtime Settings (env vars as UI admin settings).
 *
 * Every tunable documented in CLAUDE.md is listed with its live resolved
 * value and source. Editing writes a DB override; an explicit environment
 * variable still wins at resolution time (kill-switch semantics), which
 * the source badge makes visible. Secrets (API keys, webhook secrets) are
 * listed but locked — they never leave the server.
 *
 * Backend: /api/v1/admin/settings (admin role required).
 */

const SOURCE_STYLES: Record<string, string> = {
  env: "bg-amber-100 text-amber-800 border-amber-300",
  db: "bg-blue-100 text-blue-800 border-blue-300",
  default: "bg-gray-100 text-gray-600 border-gray-300",
  unknown: "bg-red-100 text-red-700 border-red-300",
};

function SourceBadge({ source }: { source?: string }) {
  if (!source) return null;
  const label =
    source === "env"
      ? "env override"
      : source === "db"
        ? "UI setting"
        : source === "default"
          ? "default"
          : source;
  return (
    <span
      className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${SOURCE_STYLES[source] ?? SOURCE_STYLES.unknown}`}
    >
      {label}
    </span>
  );
}

function SettingRow({
  entry,
  onChanged,
}: {
  entry: SettingEntry;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [textValue, setTextValue] = useState<string>(() =>
    entry.type === "json" && entry.value !== undefined
      ? JSON.stringify(entry.value)
      : String(entry.value ?? "")
  );

  useEffect(() => {
    setTextValue(
      entry.type === "json" && entry.value !== undefined
        ? JSON.stringify(entry.value)
        : String(entry.value ?? "")
    );
  }, [entry.value, entry.type]);

  const save = async (value: unknown) => {
    setBusy(true);
    setError(null);
    try {
      await updateSetting(entry.key, value);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const saveText = () => {
    let parsed: unknown = textValue;
    if (entry.type === "int") parsed = parseInt(textValue, 10);
    else if (entry.type === "float") parsed = parseFloat(textValue);
    else if (entry.type === "json") {
      try {
        parsed = JSON.parse(textValue);
      } catch {
        setError("Invalid JSON");
        return;
      }
    }
    void save(parsed);
  };

  return (
    <tr className="border-b border-gray-100 align-top">
      <td className="px-3 py-2">
        <div className="font-mono text-xs font-semibold text-gray-900">{entry.key}</div>
        <div className="text-xs text-gray-500">{entry.description}</div>
      </td>
      <td className="w-56 px-3 py-2">
        {entry.secret ? (
          <span className="text-xs italic text-gray-400">Managed by environment</span>
        ) : entry.source === "env" ? (
          <span className="text-xs italic text-amber-700">
            Set via env — remove the export to edit here
          </span>
        ) : entry.type === "bool" ? (
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              className="h-4 w-4"
              disabled={busy}
              checked={entry.value === true}
              onChange={(e) => void save(e.target.checked)}
            />
            <span className="text-sm">{entry.value === true ? "On" : "Off"}</span>
          </label>
        ) : (
          <div className="flex items-center gap-2">
            <input
              type={entry.type === "int" || entry.type === "float" ? "number" : "text"}
              step={entry.type === "float" ? "0.01" : undefined}
              className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:border-blue-500 focus:outline-none"
              value={textValue}
              disabled={busy}
              onChange={(e) => setTextValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveText();
              }}
            />
            <button
              className="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              disabled={busy}
              onClick={saveText}
            >
              Save
            </button>
          </div>
        )}
        {error && <div className="mt-1 text-xs text-red-600">{error}</div>}
      </td>
      <td className="w-28 px-3 py-2">
        <SourceBadge source={entry.source} />
      </td>
      <td className="w-20 px-3 py-2 text-right">
        {!entry.secret && entry.source === "db" && (
          <button
            className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await resetSetting(entry.key);
                onChanged();
              } catch (e) {
                setError(e instanceof Error ? e.message : String(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            Reset
          </button>
        )}
      </td>
    </tr>
  );
}

export default function AdminRuntimeSettingsPage() {
  const [catalog, setCatalog] = useState<SettingsCatalog | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [filter, setFilter] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSettings();
      setCatalog(data);
      setActiveCategory((prev) => prev || data.categories[0] || "");
    } catch (e) {
      setError(
        e instanceof Error
          ? `${e.message} — admin access required`
          : "Failed to load settings"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(() => {
    if (!catalog) return [];
    const q = filter.trim().toLowerCase();
    return catalog.settings.filter((s) => {
      if (!q && s.category !== activeCategory) return false;
      if (q) {
        return (
          s.key.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [catalog, activeCategory, filter]);

  if (loading) {
    return <div className="p-8 text-sm text-gray-500">Loading settings…</div>;
  }

  if (error && !catalog) {
    return <div className="p-8 text-sm text-red-600">{error}</div>;
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Runtime Settings</h1>
          <p className="mt-1 max-w-3xl text-xs text-gray-500">
            Environment variables as administrable settings. Edits take effect within a
            minute (cache TTL) without restart.{" "}
            <button
              className="font-medium text-blue-600 underline hover:text-blue-800"
              onClick={() => setHelpOpen((v) => !v)}
            >
              {helpOpen ? "Hide help" : "How this works"}
            </button>
          </p>
        </div>
        <input
          type="search"
          placeholder="Filter by key or description…"
          className="w-72 rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      {helpOpen && (
        <div className="mb-4 space-y-2 rounded-lg border border-blue-200 bg-blue-50 p-4 text-xs text-gray-700">
          <p className="font-semibold text-gray-900">How resolution works</p>
          <ol className="list-inside list-decimal space-y-1">
            <li>
              <strong>Environment variable</strong> — always wins. Use it as the kill
              switch; rows show an amber &quot;env override&quot; badge and are read-only here.
            </li>
            <li>
              <strong>UI setting</strong> — what you save on this page (stored in the
              database, applied to all workers within ~60s, no restart).
            </li>
            <li>
              <strong>Default</strong> — the documented fallback when nothing else is set.
            </li>
          </ol>
          <p>
            <strong>Reset</strong> removes a UI setting and falls back to whatever the env
            says, or the default. Secrets (API keys, webhook secrets) are locked — they
            never leave the server. Every change is recorded in the audit trail
            (<code className="rounded bg-white px-1">GET /api/v1/admin/settings/audit</code>).
            Full guide: <code className="rounded bg-white px-1">docs/guides/RUNTIME_SETTINGS_GUIDE.md</code>.
          </p>
        </div>
      )}

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      {!filter && catalog && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {catalog.categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                cat === activeCategory
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <table className="w-full table-fixed">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                Setting
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                Value
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                Source
              </th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {visible.map((entry) => (
              <SettingRow key={entry.key} entry={entry} onChanged={() => void load()} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-gray-400">
        Showing {visible.length} of {catalog?.settings.length ?? 0} settings
      </p>
    </div>
  );
}
