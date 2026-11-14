/**
 * Backend endpoint resolution for the menu bar frontend.
 *
 * Default behavior is unchanged: `http://localhost:8000` for HTTP and
 * `ws://localhost:8000/ws/menubar` for WebSocket.
 *
 * Precedence:
 * 1. A native environment override (`ATOM_MENUBAR_BACKEND_URL` or
 *    `ATOM_BACKEND_URL`) reported by the Tauri `get_backend_config` command.
 *    This wins over a stale stored value so an isolated loopback verification
 *    launch cannot silently fall back to the default backend.
 * 2. `localStorage.atom_server_url` (Settings > Server URL).
 * 3. The historical default.
 *
 * When native IPC is present but rejects the configured endpoint, no endpoint
 * is returned: the UI must prevent requests rather than fall back to the
 * localhost default. Browser-only launches (plain Vite/Jest, no Tauri bridge)
 * keep the stored/default fallback.
 */

import { invoke } from "@tauri-apps/api/core";

export const DEFAULT_BACKEND_HTTP_URL = "http://localhost:8000";
export const DEFAULT_BACKEND_WEBSOCKET_URL = "ws://localhost:8000/ws/menubar";
export const SERVER_URL_STORAGE_KEY = "atom_server_url";
export const WEBSOCKET_PATH = "/ws/menubar";

/** Source reported when native IPC rejected the endpoint configuration. */
export const BACKEND_CONFIG_ERROR_SOURCE = "invalid";

export interface BackendConfig {
  http_base_url: string;
  websocket_url: string;
  /** `environment` for a native override, `settings`/`default` otherwise. */
  http_base_url_source: string;
  /** Set when native IPC rejected the endpoint configuration. */
  error?: string;
}

export type ServerUrlValidation =
  | { ok: true; url: string }
  | { ok: false; error: string };

type StorageReader = Pick<Storage, "getItem">;
type StorageWriter = Pick<Storage, "setItem">;
type InvokeLike = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

const defaultInvoke = invoke as InvokeLike;

function defaultStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

/**
 * Whether a Tauri IPC bridge is present.
 *
 * `__TAURI_INTERNALS__` is injected by Tauri v2 in the webview even when
 * `withGlobalTauri` is disabled. Plain-browser launches have no bridge.
 */
export function hasNativeBridge(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const candidate = window as unknown as {
    __TAURI_INTERNALS__?: unknown;
    __TAURI__?: unknown;
  };
  return Boolean(candidate.__TAURI_INTERNALS__ || candidate.__TAURI__);
}

/**
 * Redact URL-like values from a diagnostic string.
 *
 * Explicit endpoint overrides can contain credentials, so errors are never
 * displayed or logged with the raw configured value.
 */
export function sanitizeDiagnostic(detail: unknown, fallback: string): string {
  const text =
    detail instanceof Error ? detail.message : typeof detail === "string" ? detail : "";
  const redacted = text
    .replace(/[a-z][a-z0-9+.-]*:\/\/[^\s"'<>]+/gi, "<redacted-url>")
    .replace(/\b[^\s@/"'<>]+@[^\s@/"'<>]+\b/g, "<redacted>")
    .trim();
  return redacted || fallback;
}

function invalid(error: string): ServerUrlValidation {
  return { ok: false, error };
}

/**
 * Validate and normalize an HTTP base URL without changing valid settings.
 *
 * Bare hosts (`127.0.0.1:8123`) get an `http://` scheme, trailing slashes are
 * removed, and a path prefix is preserved. Unsupported schemes, credentials,
 * queries, and fragments are rejected with a static message (never the raw
 * value).
 */
export function validateServerUrl(value?: string | null): ServerUrlValidation {
  const trimmed = (value ?? "").trim();
  if (!trimmed) {
    return invalid("Server URL is required.");
  }

  const schemeMatch = /^([a-z][a-z0-9+.-]*):\/\//i.exec(trimmed);
  if (schemeMatch && !/^https?$/i.test(schemeMatch[1])) {
    return invalid("Server URL must use http:// or https://.");
  }

  if (trimmed.includes("?")) {
    return invalid("Server URL must not include a query string.");
  }
  if (trimmed.includes("#")) {
    return invalid("Server URL must not include a fragment.");
  }

  let candidate = trimmed;
  if (!schemeMatch) {
    candidate = trimmed.startsWith("//") ? `http:${trimmed}` : `http://${trimmed}`;
  }

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    return invalid("Enter a valid server URL.");
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return invalid("Server URL must use http:// or https://.");
  }
  if (!parsed.hostname) {
    return invalid("Server URL must include a host.");
  }
  if (parsed.username || parsed.password) {
    return invalid("Server URL must not contain credentials.");
  }
  if (parsed.search) {
    return invalid("Server URL must not include a query string.");
  }
  if (parsed.hash) {
    return invalid("Server URL must not include a fragment.");
  }

  const path = parsed.pathname.replace(/\/+$/, "");
  const normalizedPath = path === "/" ? "" : path;
  return { ok: true, url: `${parsed.protocol}//${parsed.host}${normalizedPath}` };
}

/**
 * Validate an explicit WebSocket endpoint. Used for the native override; the
 * derived endpoint is built from an already-validated HTTP base.
 */
export function validateWebSocketUrl(value?: string | null): ServerUrlValidation {
  const trimmed = (value ?? "").trim();
  if (!trimmed) {
    return invalid("WebSocket URL is required.");
  }
  if (!/^wss?:\/\//i.test(trimmed)) {
    return invalid("WebSocket URL must use ws:// or wss://.");
  }
  if (trimmed.includes("?")) {
    return invalid("WebSocket URL must not include a query string.");
  }
  if (trimmed.includes("#")) {
    return invalid("WebSocket URL must not include a fragment.");
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return invalid("Enter a valid WebSocket URL.");
  }

  if (parsed.protocol !== "ws:" && parsed.protocol !== "wss:") {
    return invalid("WebSocket URL must use ws:// or wss://.");
  }
  if (!parsed.hostname) {
    return invalid("WebSocket URL must include a host.");
  }
  if (parsed.username || parsed.password) {
    return invalid("WebSocket URL must not contain credentials.");
  }
  if (parsed.search) {
    return invalid("WebSocket URL must not include a query string.");
  }
  if (parsed.hash) {
    return invalid("WebSocket URL must not include a fragment.");
  }

  const path = parsed.pathname.replace(/\/+$/, "");
  const normalizedPath = path === "/" ? "" : path;
  return { ok: true, url: `${parsed.protocol}//${parsed.host}${normalizedPath}` };
}

/**
 * Lenient normalizer for values that are not an explicit override (for example
 * an absent prop). Invalid input falls back to the default so a panel cannot
 * construct a malformed request; Settings uses `validateServerUrl` to reject.
 */
export function normalizeServerUrl(value?: string | null): string {
  const trimmed = (value ?? "").trim();
  if (!trimmed) {
    return DEFAULT_BACKEND_HTTP_URL;
  }
  const result = validateServerUrl(trimmed);
  return result.ok ? result.url : DEFAULT_BACKEND_HTTP_URL;
}

export function readStoredServerUrl(
  storage: StorageReader | null = defaultStorage()
): string | null {
  try {
    const value = storage?.getItem(SERVER_URL_STORAGE_KEY)?.trim();
    if (!value) {
      return null;
    }
    const result = validateServerUrl(value);
    return result.ok ? result.url : null;
  } catch {
    return null;
  }
}

/**
 * Persist a Settings server URL, rejecting invalid values instead of silently
 * writing the default.
 */
export function writeStoredServerUrl(
  value: string,
  storage: StorageWriter | null = defaultStorage()
): ServerUrlValidation {
  const result = validateServerUrl(value);
  if (!result.ok) {
    return result;
  }
  try {
    storage?.setItem(SERVER_URL_STORAGE_KEY, result.url);
  } catch {
    // Storage can be unavailable in a restricted webview; the in-memory
    // value still applies for this session.
  }
  return result;
}

/** Derive the menu bar WebSocket URL from an HTTP base. */
export function deriveWebSocketUrl(httpBaseUrl: string): string {
  const base = normalizeServerUrl(httpBaseUrl);
  const scheme = /^https:\/\//i.test(base) ? "wss" : "ws";
  const withoutScheme = base.replace(/^https?:\/\//i, "");
  return `${scheme}://${withoutScheme}${WEBSOCKET_PATH}`;
}

/** Whether a URL points at the local loopback interface. */
export function isLoopbackServerUrl(value: string): boolean {
  const result = validateServerUrl(value);
  if (!result.ok) {
    return false;
  }
  try {
    const host = new URL(result.url).hostname.toLowerCase();
    return (
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "::1" ||
      host === "[::1]" ||
      host.endsWith(".localhost")
    );
  } catch {
    return false;
  }
}

function isNativeBackendConfig(value: unknown): value is BackendConfig {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.http_base_url === "string" &&
    typeof candidate.websocket_url === "string" &&
    typeof candidate.http_base_url_source === "string"
  );
}

function invalidBackendConfig(detail: unknown): BackendConfig {
  return {
    http_base_url: "",
    websocket_url: "",
    http_base_url_source: BACKEND_CONFIG_ERROR_SOURCE,
    error: sanitizeDiagnostic(
      detail,
      "Native backend endpoint configuration was rejected."
    ),
  };
}

function resolveNativeWebSocket(
  value: string,
  httpBaseUrl: string
): ServerUrlValidation {
  const trimmed = (value ?? "").trim();
  if (!trimmed) {
    return { ok: true, url: deriveWebSocketUrl(httpBaseUrl) };
  }
  return validateWebSocketUrl(trimmed);
}

/**
 * Resolve the endpoints used by frontend fetches.
 *
 * `invokeFn` and `storage` are injectable so focused tests never need Tauri or
 * a network connection. `nativeBridgeAvailable` defaults to detecting the real
 * Tauri bridge; supplying a custom `invokeFn` also counts as native IPC, and
 * callers can force browser-only behavior with `false`.
 */
export async function loadBackendConfig(
  storage: StorageReader | null = defaultStorage(),
  invokeFn: InvokeLike = defaultInvoke,
  nativeBridgeAvailable: boolean = hasNativeBridge() ||
    invokeFn !== defaultInvoke
): Promise<BackendConfig> {
  if (nativeBridgeAvailable) {
    let candidate: unknown;
    try {
      candidate = await invokeFn<unknown>("get_backend_config");
    } catch (error) {
      return invalidBackendConfig(error);
    }

    if (!isNativeBackendConfig(candidate)) {
      return invalidBackendConfig(
        "Malformed response from get_backend_config."
      );
    }

    const http = validateServerUrl(candidate.http_base_url);
    if (!http.ok) {
      return invalidBackendConfig(http.error);
    }

    const websocket = resolveNativeWebSocket(candidate.websocket_url, http.url);
    if (!websocket.ok) {
      return invalidBackendConfig(websocket.error);
    }

    const native: BackendConfig = {
      http_base_url: http.url,
      websocket_url: websocket.url,
      http_base_url_source: candidate.http_base_url_source || "default",
    };

    if (native.http_base_url_source === "environment") {
      return native;
    }

    const stored = readStoredServerUrl(storage);
    if (stored) {
      return {
        http_base_url: stored,
        websocket_url: deriveWebSocketUrl(stored),
        http_base_url_source: "settings",
      };
    }

    return native;
  }

  const stored = readStoredServerUrl(storage);
  if (stored) {
    return {
      http_base_url: stored,
      websocket_url: deriveWebSocketUrl(stored),
      http_base_url_source: "settings",
    };
  }

  return {
    http_base_url: DEFAULT_BACKEND_HTTP_URL,
    websocket_url: DEFAULT_BACKEND_WEBSOCKET_URL,
    http_base_url_source: "default",
  };
}
