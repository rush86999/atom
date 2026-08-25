import { apiClient } from './api-client';

// Typed client for Admin Runtime Settings (env vars as UI admin settings).
// Admin-only surface: /api/v1/admin/settings/*.

export type SettingType = 'bool' | 'int' | 'float' | 'str' | 'json';

export type SettingSource = 'env' | 'db' | 'default' | 'unknown';

export interface SettingEntry {
  key: string;
  type: SettingType;
  default: unknown;
  category: string;
  description: string;
  secret: boolean;
  editable: boolean;
  value?: unknown;
  source?: SettingSource;
}

export interface SettingsCatalog {
  settings: SettingEntry[];
  categories: string[];
}

export interface SettingUpdateResult {
  success: boolean;
  message: string;
  data: { key: string; value: unknown; source: SettingSource };
}

export interface SettingChange {
  id: string;
  setting_key: string;
  old_value_json: unknown;
  new_value_json: unknown;
  changed_by: string | null;
  changed_at: string | null;
}

type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

function rawClient(): { fetch: FetchLike } {
  // apiClient.fetch exists at runtime (attached in lib/api.ts) but is not
  // part of the axios type surface — same accessor pattern as trust-api.
  return apiClient as unknown as { fetch: FetchLike };
}

/** Full catalog with resolved values + sources. */
export async function getSettings(): Promise<SettingsCatalog> {
  const res = await rawClient().fetch('/api/v1/admin/settings');
  if (!res.ok) throw new Error(`Settings failed (${res.status})`);
  const body = (await res.json()) as { data: SettingsCatalog };
  return body.data;
}

/** Distinct category names (tabbed navigation). */
export async function getSettingCategories(): Promise<{
  categories: string[];
  count: number;
}> {
  const res = await rawClient().fetch('/api/v1/admin/settings/categories');
  if (!res.ok) throw new Error(`Categories failed (${res.status})`);
  const body = (await res.json()) as { data: { categories: string[]; count: number } };
  return body.data;
}

/**
 * Persist a UI override. Explicit env vars still win at resolution time
 * (kill-switch semantics) — the response's `source` reports what a fresh
 * resolve now returns.
 */
export async function updateSetting(
  key: string,
  value: unknown
): Promise<SettingUpdateResult> {
  const res = await rawClient().fetch(`/api/v1/admin/settings/${encodeURIComponent(key)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value }),
  });
  if (!res.ok) {
    let detail = `Update failed (${res.status})`;
    try {
      const err = (await res.json()) as { detail?: string };
      if (err.detail) detail = err.detail;
    } catch {
      /* keep generic */
    }
    throw new Error(detail);
  }
  return res.json();
}

/** Remove the stored override — falls back to env or default. */
export async function resetSetting(key: string): Promise<SettingUpdateResult> {
  const res = await rawClient().fetch(`/api/v1/admin/settings/${encodeURIComponent(key)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Reset failed (${res.status})`);
  return res.json();
}

/** Recent change-audit rows, newest first. */
export async function getSettingChanges(
  opts: { limit?: number; settingKey?: string } = {}
): Promise<SettingChange[]> {
  const qs = new URLSearchParams();
  if (opts.limit !== undefined) qs.set('limit', String(opts.limit));
  if (opts.settingKey) qs.set('setting_key', opts.settingKey);
  const suffix = qs.toString() ? `?${qs}` : '';
  const res = await rawClient().fetch(`/api/v1/admin/settings/audit${suffix}`);
  if (!res.ok) throw new Error(`Audit failed (${res.status})`);
  const body = (await res.json()) as { data: { changes: SettingChange[] } };
  return body.data.changes;
}
