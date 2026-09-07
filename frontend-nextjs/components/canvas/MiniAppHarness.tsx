"use client";

/**
 * MiniAppHarness — agent-driven mini-app authoring panel (Aug 2026).
 *
 * A collapsible bottom panel for authoring stateful canvas mini-apps directly
 * from the canvas page: scaffold a draft → edit logic (Monaco, syntax-gated
 * server-side) → dev-run (dry: resulting state + proposed ops, NO commit) →
 * publish (credential-stripped blueprint) → install (fresh immutable instance).
 *
 * Live instance state arrives over the WS `canvas:update` channel with
 * `action: "mini_app_state"` and is previewed here as JSON — the user-facing
 * twin of `window.atom.canvas.getState()` (agent-facing dual-face access).
 *
 * Talks to the backend via the unified RPC client (POST /api/rpc/{action})
 * and a direct PUT for save (logic is canvas-scoped).
 */
import React, { useEffect, useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  Play,
  Save,
  Loader2,
  Plus,
  Rocket,
  Boxes,
  ChevronDown,
  ChevronUp,
  Code2,
  Radio,
  Sparkles,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { rpc } from "@/lib/rpc-client";

interface MiniAppHarnessProps {
  canvasId: string;
  lastMessage?: any; // WS stream from the page's useWebSocket
  agentId?: string;
  // The canvas type this panel is mounted on — the default base type for new
  // apps, so authoring from inside a sheets/email/… canvas builds ON it.
  canvasType?: string;
}

interface LogicRunResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  error?: string;
}

interface MiniAppScaffoldResult {
  success: boolean;
  app_id?: string;
  canvas_id?: string;
  logic_source?: string;
  error?: string;
}

interface DevRunResult extends LogicRunResult {
  state?: Record<string, unknown>;
  version?: number;
  proposed_ops?: Array<Record<string, unknown>>;
  op_results?: Record<string, unknown>;
  state_changed?: boolean;
}

export function MiniAppHarness({ canvasId, lastMessage, agentId, canvasType }: MiniAppHarnessProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [source, setSource] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [scaffolding, setScaffolding] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [result, setResult] = useState<DevRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Authoring target — set after scaffold (the app's blueprint source canvas).
  const [appId, setAppId] = useState<string | null>(null);
  const [blueprintCanvasId, setBlueprintCanvasId] = useState<string | null>(null);
  const [installedCanvasId, setInstalledCanvasId] = useState<string | null>(null);

  // Manifest editor fields.
  const [appName, setAppName] = useState<string>("");
  const [declaredScopes, setDeclaredScopes] = useState<string>("canvas_render");
  const [dependencies, setDependencies] = useState<string>("");
  // Base canvas kind the app builds ON — any slug (crm, accounting, inventory,
  // sheets, …); defaults to the host canvas's type so authoring from inside an
  // existing typed canvas extends it. The backend accepts any well-formed
  // slug and self-registers unknown kinds.
  const [baseType, setBaseType] = useState<string>(canvasType || "mini_app");

  // Live instance state previewed from the WS mini_app_state broadcast.
  const [liveState, setLiveState] = useState<{ version: number; data: Record<string, unknown> } | null>(null);

  const targetCanvasId = blueprintCanvasId ?? canvasId;

  // Load existing logic for the target canvas.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiClient
      .get<{ success: boolean; data?: { source: string } }>(`/api/canvas/${targetCanvasId}/logic`)
      .then((resp) => {
        if (cancelled) return;
        setSource(resp.data?.data?.source ?? "");
      })
      .catch((err) => {
        // 404 = no logic yet on this canvas; any other failure must not wipe
        // the source the user is editing (transient errors are not "no logic").
        if (!cancelled && (err as { response?: { status?: number } })?.response?.status === 404) setSource("");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [targetCanvasId]);

  // Consume live mini-app state broadcasts from the WS stream.
  useEffect(() => {
    const data = lastMessage?.data ?? lastMessage;
    if (
      lastMessage?.type === "canvas:update" &&
      data?.action === "mini_app_state" &&
      data?.canvas_id &&
      data.canvas_id === (installedCanvasId ?? canvasId)
    ) {
      setLiveState({ version: data.version ?? 0, data: data.data ?? {} });
    }
  }, [lastMessage, canvasId, installedCanvasId]);

  // Reconnect after a page reload: appId lives in component state, so a
  // refresh orphaned the draft — Dev-Run/Publish/Install stayed disabled
  // until a fresh scaffold. Match the host canvas against the user's apps'
  // blueprint canvases and restore the authoring target.
  useEffect(() => {
    let cancelled = false;
    Promise.resolve(rpc.call("mini_app_list", {}))
      .then((res: any) => {
        if (cancelled || !res?.apps?.length) return;
        const mine = res.apps.find((a: any) => a.blueprint_canvas_id === canvasId);
        if (mine?.id) {
          setAppId(mine.id);
          setBlueprintCanvasId(mine.blueprint_canvas_id);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [canvasId]);

  const scopesList = useMemo(
    () => declaredScopes.split(",").map((s) => s.trim()).filter(Boolean),
    [declaredScopes]
  );
  const depsList = useMemo(
    () => dependencies.split(",").map((s) => s.trim()).filter(Boolean),
    [dependencies]
  );

  async function handleScaffold() {
    setScaffolding(true);
    setError(null);
    setNotice(null);
    const normalizedType = baseType.trim().toLowerCase();
    try {
      const res = (await rpc.call("mini_app_scaffold", {
        name: appName.trim() || "Untitled Mini-App",
        declared_scopes: scopesList,
        dependencies: depsList,
        spec: normalizedType && normalizedType !== "mini_app" ? { canvas_type: normalizedType } : {},
      })) as MiniAppScaffoldResult;
      if (!res.success) {
        setError(res.error ?? "Scaffold failed");
        return;
      }
      setAppId(res.app_id ?? null);
      setBlueprintCanvasId(res.canvas_id ?? null);
      if (res.logic_source) setSource(res.logic_source);
      setNotice(
        `Draft app "${appName.trim() || "Untitled Mini-App"}"` +
          `${normalizedType && normalizedType !== "mini_app" ? ` (on ${normalizedType})` : ""} created (${res.app_id}). ` +
          `Source canvas: ${res.canvas_id}. Edit logic, then Dev-Run → Publish → Install.`
      );
    } catch (e) {
      const err = e as { message?: string };
      setError(err?.message || "Failed to scaffold mini-app");
    } finally {
      setScaffolding(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await apiClient.put(`/api/canvas/${targetCanvasId}/logic`, {
        source,
        language: "python",
        agent_id: agentId,
      });
      setNotice("Logic saved (checkpointed to the audit trail).");
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "Failed to save logic");
    } finally {
      setSaving(false);
    }
  }

  async function handleDevRun() {
    if (!appId) {
      setError("Scaffold the mini-app first (creates the draft app + source canvas).");
      return;
    }
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      // Save first so the run executes the latest source.
      await apiClient.put(`/api/canvas/${targetCanvasId}/logic`, {
        source,
        language: "python",
        agent_id: agentId,
      });
      // Backend derives the run canvas from app.blueprint_canvas_id — only app_id (+ optional inputs) is accepted.
      const res = (await rpc.call("mini_app_dev_run", {
        app_id: appId,
        inputs: {},
      })) as DevRunResult;
      setResult(res);
      if (res?.success && res.state) {
        setLiveState({ version: res.version ?? 0, data: res.state });
      }
    } catch (e) {
      const err = e as { message?: string };
      setError(err?.message || "Dev-run failed");
    } finally {
      setRunning(false);
    }
  }

  async function handlePublish() {
    if (!appId) {
      setError("Scaffold the mini-app first.");
      return;
    }
    setPublishing(true);
    setError(null);
    setNotice(null);
    try {
      const res = (await rpc.call("mini_app_publish", { app_id: appId })) as { success: boolean; error?: string };
      if (!res.success) {
        setError(res.error ?? "Publish failed (deps scan + rootfs must pass).");
        return;
      }
      setNotice(`Published v${(res as any).version ?? ""}. Snapshot is credential-stripped; installs are immutable.`);
    } catch (e) {
      const err = e as { message?: string };
      setError(err?.message || "Publish failed");
    } finally {
      setPublishing(false);
    }
  }

  async function handleInstall() {
    if (!appId) {
      setError("Scaffold the mini-app first.");
      return;
    }
    setInstalling(true);
    setError(null);
    setNotice(null);
    try {
      const res = (await rpc.call("mini_app_install", { app_id: appId })) as {
        success: boolean;
        canvas_id?: string;
        error?: string;
      };
      if (!res.success) {
        setError(res.error ?? "Install failed");
        return;
      }
      setInstalledCanvasId(res.canvas_id ?? null);
      setLiveState(null);
      setNotice(`Installed → instance canvas ${res.canvas_id}. Runs will broadcast state here.`);
    } catch (e) {
      const err = e as { message?: string };
      setError(err?.message || "Install failed");
    } finally {
      setInstalling(false);
    }
  }

  return (
    <div className="border-t border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 flex flex-col max-h-[45vh]">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-between px-3 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold text-zinc-700 dark:text-zinc-200">
          <Boxes className="h-3.5 w-3.5 text-indigo-500" />
          Mini-App Harness
          {appId && (
            <span className="text-[10px] font-normal px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
              {appId.slice(0, 8)}
            </span>
          )}
        </span>
        {collapsed ? (
          <ChevronUp className="h-3.5 w-3.5 text-zinc-400" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />
        )}
      </button>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-3 min-h-0">
          {/* Journey guidance: the panel is discoverable but the loop and its
              gates (chat-first authoring, Firecracker-only execution) aren't
              obvious from the button row alone. */}
          <div className="px-2 py-1.5 text-[11px] text-zinc-500 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-800/40 rounded flex gap-1.5">
            <Sparkles className="h-3 w-3 shrink-0 mt-0.5 text-indigo-400" />
            <span>
              Easiest path: give it to your agent to code — run your hire (Agent
              Workspace → Run) with e.g. &ldquo;scaffold a mini-app that tracks
              expenses&rdquo; — and it drives scaffold → code → dev-run → test →
              publish → install, while this panel shows the live state. Or author
              manually below. Executions run in a Firecracker microVM: on hosts
              without one, dev-run fails closed (operator setup:
              docs/deployment/FIRECRACKER_HOST_SETUP.md).
            </span>
          </div>

          {/* Manifest editor */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <label className="flex flex-col gap-1 text-[10px] text-zinc-500">
              App name
              <input
                value={appName}
                onChange={(e) => setAppName(e.target.value)}
                placeholder="Expense Tracker"
                className="px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-transparent"
              />
            </label>
            <label className="flex flex-col gap-1 text-[10px] text-zinc-500">
              Base canvas type (any kind)
              <input
                value={baseType}
                onChange={(e) => setBaseType(e.target.value)}
                list="miniapp-base-types"
                placeholder="crm · accounting · sheets …"
                className="px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-transparent"
              />
              <datalist id="miniapp-base-types">
                {["mini_app", "sheets", "docs", "email", "generic", "coding", "terminal", "orchestration"].map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
            </label>
            <label className="flex flex-col gap-1 text-[10px] text-zinc-500">
              Declared scopes (comma-sep)
              <input
                value={declaredScopes}
                onChange={(e) => setDeclaredScopes(e.target.value)}
                placeholder="canvas_render"
                className="px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-transparent"
              />
            </label>
            <label className="flex flex-col gap-1 text-[10px] text-zinc-500">
              Dependencies (comma-sep)
              <input
                value={dependencies}
                onChange={(e) => setDependencies(e.target.value)}
                placeholder="pandas==2.2"
                className="px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-transparent"
              />
            </label>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleScaffold}
              disabled={scaffolding}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-indigo-300 dark:border-indigo-700 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 disabled:opacity-50"
            >
              {scaffolding ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              Scaffold
            </button>
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
              Save Logic
            </button>
            <button
              onClick={handleDevRun}
              disabled={running || !appId}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {running ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
              Dev-Run (dry)
            </button>
            <button
              onClick={handlePublish}
              disabled={publishing || !appId}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {publishing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Rocket className="h-3 w-3" />}
              Publish
            </button>
            <button
              onClick={handleInstall}
              disabled={installing || !appId}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 disabled:opacity-50"
            >
              {installing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Boxes className="h-3 w-3" />}
              Install
            </button>
          </div>

          {/* Notice / error strips */}
          {notice && (
            <div className="px-2 py-1 text-xs text-indigo-700 bg-indigo-50 dark:bg-indigo-900/30 dark:text-indigo-300 rounded">
              {notice}
            </div>
          )}
          {error && (
            <div className="px-2 py-1 text-xs text-red-600 bg-red-50 dark:bg-red-900/20 rounded">
              {error}
            </div>
          )}

          {/* Logic editor */}
          <div className="flex items-center gap-1 text-[10px] text-zinc-500">
            <Code2 className="h-3 w-3" /> Python logic — <span className="font-mono">{targetCanvasId}</span>
          </div>
          {loading ? (
            <div className="p-2 text-xs text-zinc-500 flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin" /> Loading…
            </div>
          ) : (
            <Editor
              height="180px"
              defaultLanguage="python"
              theme="vs-dark"
              value={source}
              onChange={(val) => setSource(val ?? "")}
              options={{ minimap: { enabled: false }, fontSize: 12, scrollBeyondLastLine: false }}
            />
          )}

          {/* Dev-run result (stdout/stderr + state) */}
          {result && (
            <div className="px-2 py-2 text-xs font-mono border border-zinc-200 dark:border-zinc-700 rounded space-y-1">
              {result.error && (
                <pre className="whitespace-pre-wrap text-red-600 dark:text-red-400">{result.error}</pre>
              )}
              {result.stdout && (
                <pre className="whitespace-pre-wrap text-emerald-600 dark:text-emerald-400">{result.stdout}</pre>
              )}
              {result.stderr && (
                <pre className="whitespace-pre-wrap text-red-600 dark:text-red-400">{result.stderr}</pre>
              )}
              <div className="text-zinc-400">exit code: {result.exit_code ?? "—"} · state_changed: {String(!!result.state_changed)}</div>
              {result.state !== undefined && (
                <pre className="whitespace-pre-wrap text-zinc-300 bg-zinc-900/60 p-2 rounded">
                  {JSON.stringify({ state: result.state, proposed_ops: result.proposed_ops ?? [] }, null, 2)}
                </pre>
              )}
            </div>
          )}

          {/* Live instance state preview */}
          <div className="flex items-center gap-1 text-[10px] text-zinc-500">
            <Radio className="h-3 w-3 text-emerald-500" /> Live instance state
            {liveState ? ` (v${liveState.version})` : " — awaiting canvas:update"}
          </div>
          {liveState && (
            <pre className="whitespace-pre-wrap text-[11px] font-mono text-zinc-300 bg-zinc-900/60 p-2 rounded max-h-40 overflow-auto">
              {JSON.stringify(liveState.data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default MiniAppHarness;
