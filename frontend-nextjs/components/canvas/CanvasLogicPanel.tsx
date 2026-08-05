"use client";

/**
 * Canvas Logic Panel — P7 (Cloudflare OS G7b).
 *
 * A settings panel that lets a user view/edit a canvas's server-side Python
 * logic and run it in the isolated sandbox runtime. Mirrors the existing code-
 * artifact editor surface in CanvasPanel.tsx (Monaco editor + Run button +
 * stdout/stderr results).
 *
 * Save/run require an AUTONOMOUS agent (governance gate enforced server-side in
 * core/canvas_logic_service.check_governance). The agent_id is passed through
 * so the backend can authorize.
 *
 * Talks to the backend via the unified RPC client (POST /api/rpc/{action}) for
 * read/run and a direct PUT for save (logic is canvas-scoped, not a registry
 * action).
 */
import React, { useEffect, useState } from "react";
import Editor from "@monaco-editor/react";
import { Play, Save, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";

interface CanvasLogicPanelProps {
  canvasId: string;
  agentId?: string;
}

interface LogicRunResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  error?: string;
}

export function CanvasLogicPanel({ canvasId, agentId }: CanvasLogicPanelProps) {
  const [source, setSource] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<LogicRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load existing logic on mount / canvas change.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiClient
      .get<{ success: boolean; data?: { source: string } }>(`/api/canvas/${canvasId}/logic`)
      .then((resp) => {
        if (cancelled) return;
        setSource(resp.data?.data?.source ?? "");
      })
      .catch(() => {
        // 404 = no logic yet; leave empty source.
        if (!cancelled) setSource("");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [canvasId]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await apiClient.put(`/api/canvas/${canvasId}/logic`, {
        source,
        language: "python",
        agent_id: agentId,
      });
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "Failed to save logic");
    } finally {
      setSaving(false);
    }
  }

  async function handleRun() {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      // Save before running so the runtime executes the latest source.
      await apiClient.put(`/api/canvas/${canvasId}/logic`, {
        source,
        language: "python",
        agent_id: agentId,
      });
      const resp = await apiClient.post<{ success: boolean; data: LogicRunResult }>(
        `/api/canvas/${canvasId}/logic/run`,
        { inputs: {}, agent_id: agentId }
      );
      setResult(resp.data?.data ?? null);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "Failed to run logic");
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="p-4 flex items-center gap-2 text-sm text-zinc-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading canvas logic…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full border-t border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-200 dark:border-zinc-700">
        <span className="text-xs font-medium text-zinc-600 dark:text-zinc-300">
          Server Logic (Python)
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
            Save
          </button>
          <button
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {running ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            Run
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-[200px]">
        <Editor
          height="240px"
          defaultLanguage="python"
          theme="vs-dark"
          value={source}
          onChange={(val) => setSource(val ?? "")}
          options={{ minimap: { enabled: false }, fontSize: 12, scrollBeyondLastLine: false }}
        />
      </div>
      {error && (
        <div className="px-3 py-1 text-xs text-red-600 bg-red-50 dark:bg-red-900/20">
          {error}
        </div>
      )}
      {result && (
        <div className="px-3 py-2 text-xs font-mono border-t border-zinc-200 dark:border-zinc-700">
          {result.stdout && (
            <pre className="whitespace-pre-wrap text-emerald-600 dark:text-emerald-400">
              {result.stdout}
            </pre>
          )}
          {result.stderr && (
            <pre className="whitespace-pre-wrap text-red-600 dark:text-red-400">
              {result.stderr}
            </pre>
          )}
          <div className="text-zinc-400 mt-1">exit code: {result.exit_code}</div>
        </div>
      )}
    </div>
  );
}

export default CanvasLogicPanel;
