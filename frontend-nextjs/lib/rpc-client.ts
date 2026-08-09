/**
 * Unified RPC client — P1 (Cloudflare OS foundation).
 *
 * Typed frontend client for the unified action registry exposed at
 * `POST /api/rpc/{action_name}` (backend `api/rpc_routes.py`). Use this instead
 * of bespoke per-feature endpoints so capability gating (P2), gatekeeper checks
 * (P3), and sandbox enforcement (P9) all flow through a single dispatch path.
 *
 * Usage:
 *   import { rpc } from "@/lib/rpc-client";
 *   const result = await rpc.call<DocumentsSearchResult>("documents.search", { query: "q1", limit: 5 });
 *   const actions = await rpc.listActions();
 *
 * Auth: reuses the shared `apiClient` (axios) which attaches the Bearer token
 * from localStorage in its request interceptor — no extra auth wiring needed.
 */
import { apiClient } from "./api";

// Backend wire format: { success: boolean, data?: T, error_code?, message?, ... }
export interface RpcResponse<T = unknown> {
  success: boolean;
  data?: T;
  action?: string;
  error_code?: string;
  message?: string;
  details?: Record<string, unknown>;
}

export interface RpcActionSummary {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface RpcError extends Error {
  status?: number;
  action?: string;
  details?: unknown;
}

/**
 * Build a typed RPC error from an axios error, preserving status + backend
 * detail without leaking internal messages to end users.
 */
function toRpcError(action: string, err: unknown): RpcError {
  const e: RpcError = new Error("RPC call failed") as RpcError;
  e.action = action;
  // axios-shaped error
  const axiosErr = err as { response?: { status?: number; data?: unknown }; message?: string };
  e.status = axiosErr?.response?.status;
  e.details = axiosErr?.response?.data;
  if (axiosErr?.response?.status === 404) {
    e.message = `Action '${action}' is not available`;
  } else if (axiosErr?.response?.status === 401) {
    e.message = "Authentication required";
  } else if (axiosErr?.response?.status === 403) {
    e.message = "Not permitted to perform this action";
  } else {
    // Deliberately generic: axios messages ("Request failed with status code
    // 500", "Network Error", "timeout of 10000ms exceeded") leak client
    // configuration and transport internals into user-facing surfaces.
    e.message = "RPC call failed";
  }
  return e;
}

export const rpc = {
  /**
   * Call a registered action by name.
   * @param name  Dotted action name, e.g. "documents.search"
   * @param params Action arguments (validated against the action's parameter schema server-side)
   */
  async call<T = unknown>(name: string, params: Record<string, unknown> = {}): Promise<T> {
    try {
      const resp = await apiClient.post<RpcResponse<T>>(`/api/rpc/${name}`, { params });
      const body = resp.data;
      if (!body.success) {
        const e: RpcError = new Error(body.message || `Action '${name}' failed`) as RpcError;
        e.action = name;
        e.details = body.details;
        throw e;
      }
      return body.data as T;
    } catch (err) {
      // Re-throw already-shaped RpcError unchanged.
      if (err instanceof Error && (err as RpcError).action) {
        throw err;
      }
      throw toRpcError(name, err);
    }
  },

  /** List all registered actions available over RPC. */
  async listActions(): Promise<RpcActionSummary[]> {
    try {
      const resp = await apiClient.get<RpcResponse<RpcActionSummary[]>>("/api/rpc/actions");
      const body = resp.data;
      if (!body.success) {
        return [];
      }
      return body.data ?? [];
    } catch {
      // Best-effort listing — callers can degrade gracefully (e.g. hide an
      // action picker) when the registry is unreachable.
      return [];
    }
  },
};

export default rpc;
